"""Capture the quoted market at every order event, while it is still there.

    ./venv/Scripts/python.exe -X utf8 scripts/execution/nbbo_capture.py --run-id <run>

WHY THIS RUNS BEFORE THE OPEN AND NOT AFTER. A quote is the only thing in this
fund's whole record that is UNRECOVERABLE. A fill, a NAV strike, an approval —
all of them are in the log forever. The bid and ask at 13:31:07.412Z exist for
that instant and then they are the vendor's problem. The fund has placed thirty
four fill events and holds the market state for exactly none of them, which is
why "zero real fills ever measured" has been true for eleven days of trading.

WHAT IT DOES. Polls ``GET /api/v1/fund/events`` for order lifecycle events,
and for each one snapshots the best bid and offer for that order's symbol into
``fund_execution_quotes``. At a fill it also computes the effective spread
against the mid — the P5 measurement. It writes NOTHING to the event log, holds
no lock, and touches no order path: the whole blast radius is one append-only
table nothing else reads.

THE FEED IS IEX AND THE ROWS SAY SO. Measured 2026-08-23 against this fund's
own subscription: a real-time consolidated (SIP) quote is REFUSED
("subscription does not permit querying recent SIP data") and the same query
succeeds at sixteen minutes old. So the live pass can only see the IEX book —
one venue, whose best bid/offer is at or wider than the consolidated NBBO. Every
row it writes carries ``basis='live-iex-bbo'`` and ``feed='iex'``, and
``scripts/execution/retro_spread.py --store`` writes the CONSOLIDATED row for
the same event afterwards, as a second row with a second basis. Neither
overwrites the other; a reader picks the market it means.

THE THREE THINGS THAT MAKE THIS SAFE TO LEAVE RUNNING
-----------------------------------------------------

**1. A live quote may only be attached to an event that just happened.**
``--max-event-age`` (default 120s). Reading today's IEX book and stamping it on
a fill from 2026-08-14 would fabricate a market that never existed, and the
fabrication would be indistinguishable from a measurement forever after. An
event older than the bound gets a row with ``quote_absent_reason`` naming its
age. This is a REFUSAL, not a skip: the row exists and says it is unmeasured.

**2. The checkpoint starts at NOW, not at zero.** A first run with no
checkpoint file watches from the current tail and prints the seq it started
from. ``--from-seq`` overrides it deliberately. Combined with the age bound
above, replaying history through this service produces absence rows and never
a price.

**3. Nothing is ever skipped silently.** A vendor timeout, an unknown symbol,
an empty quote, a stale event: each one writes a row whose
``quote_absent_reason`` says which. An unmeasured fill must be VISIBLY
unmeasured, because a fill that produced no row and a fill measured at zero
cost look the same in every average anyone computes later.

THE POLL'S OWN BLIND SPOT, STATED. ``/fund/events`` returns the NEWEST ``limit``
events after ``since_seq`` — so if more than ``limit`` events land between two
polls, the OLDEST of them are never returned and advancing the checkpoint loses
them. At a few seconds a poll and a cap of 1000 that needs a burst of a
thousand events inside one tick, but it is not impossible and it is not
silent: the loop compares the lowest seq it received against its checkpoint and
prints a GAP line naming the missing range. The durable detector is
``coverage`` in ``app/fund/executionquality.py``, which counts fill events from
the LOG and captured rows from the TABLE, so anything this loop missed shows up
as ``uncaptured`` rather than disappearing from both sides of the fraction.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timezone
from typing import Any, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fund.executionquality import (  # noqa: E402
    EVENT_KIND_OF_TYPE, FILL_KINDS, LIVE_BASIS, LIVE_FEED, QuoteStore,
    effective_spread_bps, fold_order_lifecycles, mid_of,
    signed_effective_spread_bps)

#: Seconds. How old an event may be and still be given a LIVE quote.
#:
#: Two minutes, not two seconds: a fill can land while the poller is mid-tick
#: and the spine's own settle loop runs on an interval. Two minutes of drift on
#: a mid is real and is reported per row (``event_to_quote_lag_s``), but it is
#: an error bar. Two hours is a different market.
DEFAULT_MAX_EVENT_AGE_S = 120.0

#: Seconds between polls. Fast enough that an ordinary fill is quoted within
#: one tick; slow enough that a day of this is a few thousand HTTP calls.
DEFAULT_POLL_S = 3.0

#: The spine, locally. Overridable because a capture pointed at the wrong spine
#: would write rows describing another fund's orders.
DEFAULT_SPINE = os.getenv("FUND_SPINE_URL", "http://127.0.0.1:8090")

#: Where the last-seen seq is remembered between restarts. Resolved from THIS
#: FILE, never from the working directory: a relative path in a control is a
#: control that fails permissive when someone runs it from elsewhere (D20).
DEFAULT_CHECKPOINT = ROOT / ".execution_capture.seq"

#: The events endpoint's own cap. Named so the gap arithmetic below and the
#: request agree by construction rather than by memory.
EVENTS_PAGE = 1000


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_ts(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def age_seconds(event_ts: Any, now: Optional[datetime] = None) -> Optional[float]:
    """How old the event is, in seconds, or None if its timestamp is unreadable.

    None is NOT zero and NOT infinity: an event whose timestamp cannot be read
    is refused a live quote by :func:`too_old`, because the guard cannot say it
    is fresh.
    """
    t = _parse_ts(event_ts)
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return ((now or _now()) - t).total_seconds()


def too_old(event_ts: Any, max_age_s: float,
            now: Optional[datetime] = None) -> Optional[str]:
    """The refusal reason, or None if this event may carry a live quote.

    FAILS CLOSED on an unreadable timestamp. The alternative — treating an
    unparseable ts as fresh — hands a live quote to an event of unknown age,
    which is exactly the fabrication the bound exists to prevent.
    """
    age = age_seconds(event_ts, now)
    if age is None:
        return "event_timestamp_unreadable"
    if age > max_age_s:
        return f"event_too_old_for_live_quote:{age:.0f}s>{max_age_s:.0f}s"
    if age < -max_age_s:
        # A clock disagreement large enough to matter. Reported, not silently
        # accepted as "very fresh".
        return f"event_timestamp_in_the_future:{-age:.0f}s"
    return None


class IexQuotes:
    """The vendor call, isolated so every test can replace it with a function.

    Nothing else in this file imports the Alpaca SDK, so the loop, the
    checkpoint, the gap detector and the absence rules are all testable with no
    network and no credentials.
    """

    def __init__(self, key: Optional[str] = None, secret: Optional[str] = None):
        self._key = key or os.getenv("ALPACA_API_KEY")
        self._secret = secret or os.getenv("ALPACA_SECRET_KEY")
        self._client = None

    def _c(self):
        if self._client is None:
            if not (self._key and self._secret):
                raise RuntimeError(
                    "ALPACA_API_KEY / ALPACA_SECRET_KEY are not set - the "
                    "capture cannot read a quote and will write absence rows")
            from alpaca.data.historical import StockHistoricalDataClient
            self._client = StockHistoricalDataClient(self._key, self._secret)
        return self._client

    def latest(self, symbols: list[str]) -> dict[str, dict]:
        """symbol -> ``{bid, ask, bid_size, ask_size, quote_ts}``.

        One call for the whole batch. A symbol the vendor does not return is
        simply absent from the dict, and the caller writes an absence row for
        it — never a default.
        """
        from alpaca.data.enums import DataFeed
        from alpaca.data.requests import StockLatestQuoteRequest
        got = self._c().get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=sorted(set(symbols)),
                                    feed=DataFeed.IEX))
        out = {}
        for sym, q in got.items():
            ts = getattr(q, "timestamp", None)
            out[str(sym)] = {
                "bid": getattr(q, "bid_price", None),
                "ask": getattr(q, "ask_price", None),
                "bid_size": getattr(q, "bid_size", None),
                "ask_size": getattr(q, "ask_size", None),
                "quote_ts": ts.isoformat() if ts is not None else None,
            }
        return out


def fetch_events(spine: str, since_seq: int, limit: int = EVENTS_PAGE,
                 timeout: float = 10.0) -> list[dict]:
    """The newest ``limit`` events after ``since_seq``, OLDEST FIRST.

    The endpoint serves newest-first (``fund.py:1029`` reverses the tail); this
    reverses it back, because a capture loop must process a lifecycle in the
    order it happened or a fill's row can be written before its submit's.
    """
    import urllib.request
    url = f"{spine}/api/v1/fund/events?since_seq={int(since_seq)}&limit={int(limit)}"
    with urllib.request.urlopen(url, timeout=timeout) as r:
        body = json.loads(r.read().decode("utf-8"))
    evs = body.get("events") or []
    return sorted(evs, key=lambda e: int(e.get("seq") or 0))


def capturable(events: list[dict]) -> list[dict]:
    """The order lifecycle events this instrument snapshots, in seq order.

    Filters on :data:`app.fund.executionquality.EVENT_KIND_OF_TYPE`, which is
    the ONE place the type list lives. A new order event type is invisible to
    this loop until it is added there, which is a deliberate fail-quiet: the
    coverage report counts fills from the log, so a type this loop cannot see
    still shows as ``uncaptured`` rather than as measured.
    """
    return [e for e in sorted(events, key=lambda e: int(e.get("seq") or 0))
            if (e or {}).get("aggregate_type") == "order"
            and str(e.get("type") or "") in EVENT_KIND_OF_TYPE]


def read_checkpoint(path: pathlib.Path) -> Optional[int]:
    """The last seq processed, or None if there is no checkpoint.

    None means "never run here" and is NOT 0: a checkpoint of 0 would replay
    the whole log, and the age guard would then write an absence row for every
    historical event. Correct, but noise; the caller decides explicitly.
    """
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def write_checkpoint(path: pathlib.Path, seq: int) -> None:
    """Atomic-enough: write a temp file beside it and replace.

    A half-written checkpoint read as a smaller number would re-process events
    (harmless, the natural key absorbs it); read as a LARGER one it would skip
    them (not harmless). ``os.replace`` is atomic on Windows and POSIX alike.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(str(int(seq)), encoding="utf-8")
    os.replace(tmp, path)


def gap_below(batch: list[dict], since_seq: int) -> Optional[tuple[int, int]]:
    """``(first_missing, last_missing)`` if the page cut off older events.

    ``/fund/events`` returns the NEWEST page after ``since_seq``. If the batch
    is full AND its lowest seq is more than one past the checkpoint, everything
    between was served to nobody. Returns None when the page is not full,
    because a short page proves it reached back to the checkpoint.
    """
    if len(batch) < EVENTS_PAGE:
        return None
    lo = min(int(e.get("seq") or 0) for e in batch)
    if lo > since_seq + 1:
        return (since_seq + 1, lo - 1)
    return None


def capture_batch(events: list[dict], store: QuoteStore, quotes: Any, *,
                  run_id: str, max_age_s: float,
                  now: Optional[datetime] = None,
                  dry_run: bool = False) -> list[dict]:
    """Snapshot one batch. Returns one result dict per event, in seq order.

    THE SHAPE OF THE WHOLE INSTRUMENT IS HERE, so read it as the contract:

      * symbol and side come from the order's WHOLE lifecycle, because the
        submitted and partially-filled payloads carry neither (measured);
      * a symbol we cannot name gets a row saying so — it cannot be quoted;
      * an event too old for a live quote gets a row saying so;
      * one vendor call per batch, and a vendor failure writes an absence row
        per event rather than dropping the batch;
      * every path writes exactly one row per event. There is no branch that
        returns without a row, which is what makes ``uncaptured`` in the
        coverage report mean "this loop never saw it" and nothing else.
    """
    todo = capturable(events)
    if not todo:
        return []
    lifecycles = fold_order_lifecycles(events)
    now = now or _now()

    # Which symbols do we need? Only for events that will actually get a quote.
    wanted, staleness = set(), {}
    for e in todo:
        seq = int(e.get("seq") or 0)
        stale = too_old(e.get("ts"), max_age_s, now)
        staleness[seq] = stale
        sym = (lifecycles.get(str(e.get("aggregate_id")), {}) or {}).get("symbol")
        if stale is None and sym:
            wanted.add(sym)

    quoted: dict[str, dict] = {}
    vendor_error: Optional[str] = None
    if wanted:
        try:
            quoted = quotes.latest(sorted(wanted))
        except Exception as exc:  # noqa: BLE001 - the reason is the product
            # A vendor outage must not stop the loop and must not vanish. Every
            # event in the batch gets an absence row naming the exception, so a
            # bad hour is visible as a bad hour rather than as a coverage hole.
            vendor_error = f"quote_fetch_failed:{type(exc).__name__}:{str(exc)[:120]}"

    out = []
    for e in todo:
        seq = int(e.get("seq") or 0)
        oid = str(e.get("aggregate_id") or "")
        kind = EVENT_KIND_OF_TYPE[str(e.get("type"))]
        rec = lifecycles.get(oid, {}) or {}
        sym, side = rec.get("symbol"), rec.get("side")
        pay = e.get("payload") or {}
        fill_price = pay.get("avg_price") if kind in FILL_KINDS else None
        filled_qty = (pay.get("filled_qty") or pay.get("cumulative_qty")
                      if kind in FILL_KINDS else None)

        q, reason = {}, None
        if staleness[seq] is not None:
            reason = staleness[seq]
        elif not sym:
            reason = "symbol_unknown:no event in this order names one"
        elif vendor_error is not None:
            reason = vendor_error
        elif sym not in quoted:
            reason = f"no_quote_returned_for:{sym}"
        else:
            q = quoted[sym]

        row = dict(
            order_id=oid, event_kind=kind, event_seq=seq,
            event_ts=str(e.get("ts") or ""), symbol=sym, side=side,
            submitted_venue=rec.get("submitted_venue"),
            was_submitted=bool(rec.get("was_submitted")),
            bid=q.get("bid"), ask=q.get("ask"),
            bid_size=q.get("bid_size"), ask_size=q.get("ask_size"),
            quote_ts=q.get("quote_ts"),
            feed=LIVE_FEED if q else None,
            quote_absent_reason=reason,
            fill_price=fill_price, filled_qty=filled_qty,
            basis=LIVE_BASIS, capture_run=run_id)
        if dry_run:
            # THE DRY RUN COMPUTES THE SAME NUMBERS THROUGH THE SAME
            # FUNCTIONS. A preview that shows only the raw quote cannot tell an
            # operator whether the instrument would have measured this fill,
            # which is the one question a dry run is for.
            mid, derived = mid_of(row["bid"], row["ask"])
            if row["quote_absent_reason"]:
                mid = None
            out.append({
                "dry_run": True, "order_id": oid, "event_kind": kind,
                "event_seq": seq, "basis": LIVE_BASIS, "symbol": sym,
                "bid": row["bid"], "ask": row["ask"], "mid": mid,
                "effective_spread_bps": effective_spread_bps(fill_price, mid),
                "signed_effective_spread_bps":
                    signed_effective_spread_bps(fill_price, mid, side),
                "quote_absent_reason": row["quote_absent_reason"] or derived})
        else:
            out.append(store.record(**row))
    return out


def run_loop(*, spine: str, store: QuoteStore, quotes: Any, run_id: str,
             checkpoint: pathlib.Path, from_seq: Optional[int],
             poll_s: float, max_age_s: float, max_ticks: Optional[int],
             dry_run: bool, out=sys.stdout) -> dict:
    """The service. Returns a summary when ``max_ticks`` runs out.

    ``max_ticks`` exists so the loop is testable and so an operator can prove
    the thing works for five minutes before leaving it running. ``None`` runs
    until interrupted.
    """
    cp = from_seq
    if cp is None:
        cp = read_checkpoint(checkpoint)
    started_from_now = False
    if cp is None:
        # No checkpoint, no explicit start: watch from the current tail. See
        # the module docstring - starting at 0 would walk the whole log through
        # a live-quote path.
        tail = fetch_events(spine, 0, limit=1)
        cp = max((int(e.get("seq") or 0) for e in tail), default=0)
        started_from_now = True
    print(f"[capture] run={run_id} spine={spine} basis={LIVE_BASIS} "
          f"from_seq={cp}{' (tail, no checkpoint)' if started_from_now else ''} "
          f"poll={poll_s}s max_event_age={max_age_s}s dry_run={dry_run}",
          file=out, flush=True)

    ticks = 0
    written = absent = measured = 0
    gaps: list[tuple[int, int]] = []
    errors = 0
    try:
        while max_ticks is None or ticks < max_ticks:
            ticks += 1
            try:
                batch = fetch_events(spine, cp)
            except Exception as exc:  # noqa: BLE001
                # The spine being down is not this loop's business to fix. Say
                # so once per tick and keep the checkpoint where it is.
                errors += 1
                print(f"[capture] tick={ticks} spine unreachable: "
                      f"{type(exc).__name__}: {str(exc)[:120]}",
                      file=out, flush=True)
                time.sleep(poll_s)
                continue
            gap = gap_below(batch, cp)
            if gap is not None:
                gaps.append(gap)
                print(f"[capture] GAP seq {gap[0]}..{gap[1]} was never served "
                      f"to this loop (page cap {EVENTS_PAGE}); coverage will "
                      f"report them uncaptured", file=out, flush=True)
            results = capture_batch(batch, store, quotes, run_id=run_id,
                                    max_age_s=max_age_s, dry_run=dry_run)
            for r in results:
                written += 1
                if r.get("quote_absent_reason"):
                    absent += 1
                if r.get("effective_spread_bps") is not None:
                    measured += 1
                print(f"[capture] seq={r.get('event_seq')} "
                      f"{r.get('order_id','')[:8]} {r.get('basis','')} "
                      f"mid={r.get('mid')} eff_bps={r.get('effective_spread_bps')} "
                      f"absent={r.get('quote_absent_reason')}",
                      file=out, flush=True)
            if batch:
                cp = max(int(e.get("seq") or 0) for e in batch)
                if not dry_run:
                    write_checkpoint(checkpoint, cp)
            if max_ticks is None or ticks < max_ticks:
                time.sleep(poll_s)
    except KeyboardInterrupt:
        print("[capture] interrupted", file=out, flush=True)
    summary = {"run_id": run_id, "ticks": ticks, "last_seq": cp,
               "rows_written": written, "rows_absent": absent,
               "rows_measured": measured, "gaps": gaps,
               "spine_errors": errors, "dry_run": dry_run}
    print(f"[capture] {json.dumps(summary)}", file=out, flush=True)
    return summary


def load_env() -> None:
    """Read ``ClarkHarness/.env`` — FROM ``main`` ONLY, never at import.

    Resolved from this file rather than the working directory, and called only
    from ``main``: a module-scope ``load_dotenv()`` leaks the operator's real
    ``FUND_STORE``/``FUND_MODE`` into every test process that imports this
    file, which is how one merge night produced 109 false reds.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(str(ROOT / ".env"))


def main(argv: Optional[list[str]] = None) -> int:
    load_env()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--run-id", required=True,
                   help="the dispatch/run this capture belongs to; stored on "
                        "every row so a bad capture can be fenced off later")
    p.add_argument("--spine", default=DEFAULT_SPINE)
    p.add_argument("--dsn", default=None)
    p.add_argument("--checkpoint", default=str(DEFAULT_CHECKPOINT))
    p.add_argument("--from-seq", type=int, default=None,
                   help="start here instead of the checkpoint or the tail")
    p.add_argument("--poll", type=float, default=DEFAULT_POLL_S)
    p.add_argument("--max-event-age", type=float,
                   default=DEFAULT_MAX_EVENT_AGE_S,
                   help="an event older than this is refused a LIVE quote and "
                        "gets an absence row naming its age")
    p.add_argument("--ticks", type=int, default=None,
                   help="stop after N polls (proving the loop); default runs "
                        "until interrupted")
    p.add_argument("--dry-run", action="store_true",
                   help="print what would be written; touches no table and "
                        "does not move the checkpoint")
    a = p.parse_args(argv)

    store = QuoteStore(a.dsn)
    if not a.dry_run:
        store.ensure_schema()
    summary = run_loop(spine=a.spine, store=store, quotes=IexQuotes(),
                       run_id=a.run_id,
                       checkpoint=pathlib.Path(a.checkpoint),
                       from_seq=a.from_seq, poll_s=a.poll,
                       max_age_s=a.max_event_age, max_ticks=a.ticks,
                       dry_run=a.dry_run)
    return 0 if not summary["spine_errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
