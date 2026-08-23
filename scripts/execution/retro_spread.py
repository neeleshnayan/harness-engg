"""What CAN be said about the fills we already made — read-only, honestly.

    ./venv/Scripts/python.exe -X utf8 scripts/execution/retro_spread.py
    ./venv/Scripts/python.exe -X utf8 scripts/execution/retro_spread.py --quotes
    ./venv/Scripts/python.exe -X utf8 scripts/execution/retro_spread.py --quotes --store --run-id <run>
    ./venv/Scripts/python.exe -X utf8 scripts/execution/retro_spread.py --census
    ./venv/Scripts/python.exe -X utf8 scripts/execution/retro_spread.py --probe-delay

The capture service starts measuring the next fill. This answers the other
question — what the record can already say about the thirty four fill events
the fund has ALREADY made — and it answers it in two clearly separated ways,
because they are two different measurements and averaging them would produce a
number describing neither.

**TABLE 1, THE MARK BASIS. Always available, never a quote.** Every fill leg
against ``OrderSubmitted.arrival_price``, the fund's own struck mark. That is
implementation shortfall, not effective spread — no bid, no ask, no midpoint —
and it is reported under the name ``arrival-mark`` and stored nowhere.
``app/fund/tca.py`` already computes the same family of number per ORDER; this
computes it per FILL LEG, which is a different denominator (a partially filled
order prints several times and every print has its own price), and it
classifies each row instead of averaging them:

    measured   a mark exists and the fill differs from it.
    identity   the fill EQUALS the mark bit for bit. The venue filled at the
               price it was handed. 0.0 bps is arithmetic, not execution, and
               it is counted and excluded rather than averaged in.
    no_mark    no OrderSubmitted, or one with no arrival_price. Not zero.
    unusable   a price that is not a positive number, or a side we cannot read.

**TABLE 2, THE QUOTE BASIS (``--quotes``). The real effective spread.** The
consolidated quote in force at each fill's own timestamp, fetched from the
vendor's historical tape. This is the NBBO number and it has never existed for
this fund. It is only available for events older than fifteen minutes — the
subscription refuses recent consolidated data, measured and reproducible with
``--probe-delay`` — which is exactly why the LIVE capture exists beside it and
why the live rows are labelled ``iex``.

With ``--store``, table 2's rows are written into ``fund_execution_quotes``
under ``basis='sip-quote-at-event'``, alongside whatever the live capture
wrote. They are genuine observations of a real market at a real fill; they were
simply observed late. Table 1 is NEVER stored: a marks table living in a quotes
table is the conflation this whole instrument exists to prevent.

READING THE LOG. Coverage is a claim about EVERY fill, so a truncated read
cannot support one. The event endpoint serves at most 1,000 rows and has no
forward paging, so this script reads the store directly and prints how many
events it saw. Asked to work over HTTP instead (``--spine``), it prints the cap
it hit and REFUSES to print a coverage percentage — a denominator that quietly
became "the newest thousand" is the silent off-switch the D22 review named.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fund.executionquality import (  # noqa: E402
    EVENT_KIND_OF_TYPE, MARK_BASIS, RETRO_BASIS, RETRO_FEED, QuoteStore,
    class_of_row, coverage, fill_legs, fold_order_lifecycles, retro_mark_rows,
    summarise_mark_rows, summarise_quote_rows)

#: The vendor's entitlement boundary, MEASURED 2026-08-23 against this fund's
#: own keys: a consolidated quote 14 minutes old is refused and one 16 minutes
#: old is served. Used only to explain a refusal and to pick the probe points;
#: nothing computes with it, so a vendor plan change makes ``--probe-delay``
#: print a different pair rather than making a stored number wrong.
MEASURED_SIP_DELAY_MINUTES = 15

#: How far either side of a fill's timestamp to look for the quote in force.
#:
#: Backwards only, in effect: the quote that governs a print is the last one
#: BEFORE it. Two seconds of reach-back is generous for a liquid ETF and short
#: enough that a quote from a different market state cannot be picked up. A leg
#: with no quote inside the window is reported absent, never widened silently.
QUOTE_LOOKBACK_S = 2.0


def read_events_from_store(dsn: Optional[str] = None) -> tuple[list[dict], dict]:
    """Every order event in the log, oldest first, plus how it was read.

    Reads ``fund_events`` directly rather than through ``EventStore``, which
    resolves the ACTIVE MODE's database and would make a read-only report
    depend on ``FUND_MODE`` being declared in whatever shell ran it.
    """
    import psycopg
    from app.fund.pgstore import dsn as default_dsn
    target = dsn or default_dsn()
    with psycopg.connect(target) as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM fund_events")
        total = int(cur.fetchone()[0])
        cur.execute(
            "SELECT seq, event_id, aggregate_id, aggregate_type, type, actor,"
            " ts, payload FROM fund_events WHERE aggregate_type = 'order'"
            " ORDER BY seq")
        rows = [
            {"seq": r[0], "event_id": r[1], "aggregate_id": r[2],
             "aggregate_type": r[3], "type": r[4], "actor": r[5],
             "ts": r[6], "payload": r[7]}
            for r in cur.fetchall()]
    return rows, {"source": "postgres:fund_events", "events_in_log": total,
                  "order_events_read": len(rows), "truncated": False}


def read_events_from_spine(spine: str) -> tuple[list[dict], dict]:
    """The newest page of the log over HTTP, and an honest note that it is one.

    ``/fund/events`` caps at 1,000 and offers no way to page backwards, so this
    path cannot see the head of the log. It says so, and the caller refuses to
    compute coverage from it.
    """
    import urllib.request
    cap = 1000
    url = f"{spine}/api/v1/fund/events?since_seq=0&limit={cap}"
    with urllib.request.urlopen(url, timeout=20) as r:
        body = json.loads(r.read().decode("utf-8"))
    evs = sorted(body.get("events") or [], key=lambda e: int(e.get("seq") or 0))
    orders = [e for e in evs if e.get("aggregate_type") == "order"]
    return orders, {"source": f"http:{spine}", "events_in_log": None,
                    "page_returned": len(evs), "page_cap": cap,
                    "order_events_read": len(orders),
                    "truncated": len(evs) >= cap}


def census(events: list[dict]) -> dict:
    """Every order event type and how many, plus the three this instrument reads.

    Reproduces the table in ``app/fund/executionquality.EVENT_KIND_OF_TYPE``'s
    comment, so a number in a comment has a command beside it.
    """
    counts: dict[str, int] = {}
    for e in events:
        counts[str(e.get("type"))] = counts.get(str(e.get("type")), 0) + 1
    return {"order_event_types": dict(sorted(counts.items(),
                                             key=lambda kv: -kv[1])),
            "read_by_this_instrument": sorted(EVENT_KIND_OF_TYPE),
            "ignored": sorted(set(counts) - set(EVENT_KIND_OF_TYPE))}


class SipQuotes:
    """Consolidated historical quotes. Isolated so tests replace it wholesale."""

    def __init__(self, key: Optional[str] = None, secret: Optional[str] = None):
        self._key = key or os.getenv("ALPACA_API_KEY")
        self._secret = secret or os.getenv("ALPACA_SECRET_KEY")
        self._client = None

    def _c(self):
        if self._client is None:
            if not (self._key and self._secret):
                raise RuntimeError(
                    "ALPACA_API_KEY / ALPACA_SECRET_KEY are not set")
            from alpaca.data.historical import StockHistoricalDataClient
            self._client = StockHistoricalDataClient(self._key, self._secret)
        return self._client

    def in_force(self, symbol: str, at: datetime,
                 lookback_s: float = QUOTE_LOOKBACK_S) -> Optional[dict]:
        """The LAST quote at or before ``at``, or None if there is none.

        Last-before, never nearest: a quote printed after the fill did not
        govern it, and picking the nearest one lets a post-trade quote move
        into the denominator of a cost measurement.
        """
        from alpaca.data.requests import StockQuotesRequest
        got = self._c().get_stock_quotes(StockQuotesRequest(
            symbol_or_symbols=symbol,
            start=at - timedelta(seconds=lookback_s),
            end=at + timedelta(milliseconds=1)))
        rows = (got.data or {}).get(symbol) or []
        best = None
        for q in rows:
            ts = getattr(q, "timestamp", None)
            if ts is None or ts > at:
                continue
            if best is None or ts > best[0]:
                best = (ts, q)
        if best is None:
            return None
        ts, q = best
        return {"bid": getattr(q, "bid_price", None),
                "ask": getattr(q, "ask_price", None),
                "bid_size": getattr(q, "bid_size", None),
                "ask_size": getattr(q, "ask_size", None),
                "quote_ts": ts.isoformat(),
                "bid_exchange": getattr(q, "bid_exchange", None),
                "ask_exchange": getattr(q, "ask_exchange", None)}


def _at(ts: Any) -> Optional[datetime]:
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def quote_rows_for(events: list[dict], quotes: Any, *, run_id: str,
                   store: Optional[QuoteStore] = None,
                   now: Optional[datetime] = None) -> list[dict]:
    """One row per fill leg, quoted from the consolidated tape.

    Writes through ``store`` when one is given; otherwise computes the same
    values through the same functions and returns them unstored, so the report
    reads identically with and without ``--store``.
    """
    from app.fund.executionquality import (effective_spread_bps, mid_of,
                                           signed_effective_spread_bps)
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=MEASURED_SIP_DELAY_MINUTES)
    out = []
    for leg in fill_legs(fold_order_lifecycles(events)):
        at, sym = _at(leg["event_ts"]), leg["symbol"]
        q, reason = {}, None
        if not sym:
            reason = "symbol_unknown:no event in this order names one"
        elif at is None:
            reason = "event_timestamp_unreadable"
        elif at > cutoff:
            # The refusal is the vendor's, and naming it beats a bare failure.
            reason = (f"within_sip_delay:{MEASURED_SIP_DELAY_MINUTES}min - "
                      "the consolidated tape is not served for events this "
                      "recent; the live IEX row is what exists for it")
        else:
            try:
                got = quotes.in_force(sym, at)
            except Exception as exc:  # noqa: BLE001 - the reason is the product
                got, reason = None, (f"quote_fetch_failed:{type(exc).__name__}:"
                                     f"{str(exc)[:120]}")
            else:
                if got is None:
                    reason = (f"no_consolidated_quote_within_{QUOTE_LOOKBACK_S:g}s"
                              f"_before_{leg['event_ts']}")
                else:
                    q = got
        row = dict(order_id=leg["order_id"], event_kind=leg["event_kind"],
                   event_seq=leg["event_seq"], event_ts=str(leg["event_ts"]),
                   symbol=sym, side=leg["side"],
                   submitted_venue=leg["submitted_venue"],
                   was_submitted=leg["was_submitted"],
                   bid=q.get("bid"), ask=q.get("ask"),
                   bid_size=q.get("bid_size"), ask_size=q.get("ask_size"),
                   quote_ts=q.get("quote_ts"),
                   feed=RETRO_FEED if q else None,
                   quote_absent_reason=reason,
                   fill_price=leg["fill_price"], filled_qty=leg["filled_qty"],
                   basis=RETRO_BASIS, capture_run=run_id)
        if store is not None:
            out.append(store.record(**row))
            continue
        mid, derived = mid_of(row["bid"], row["ask"])
        if reason:
            mid = None
        out.append({**row, "mid": mid,
                    "quote_absent_reason": reason or derived,
                    "effective_spread_bps":
                        effective_spread_bps(leg["fill_price"], mid),
                    "signed_effective_spread_bps":
                        signed_effective_spread_bps(leg["fill_price"], mid,
                                                    leg["side"]),
                    "stored": False})
    return out


def probe_delay(quotes: Any, symbol: str = "SPY",
                minutes: tuple[int, ...] = (5, 14, 16, 60),
                now: Optional[datetime] = None) -> list[dict]:
    """Re-measure the consolidated-data entitlement boundary. One command.

    The 15 minutes in this module is a vendor plan, not a law, and a number
    with no reproduction command beside it goes stale silently.
    """
    now = now or datetime.now(timezone.utc)
    out = []
    for m in minutes:
        at = now - timedelta(minutes=m)
        try:
            quotes.in_force(symbol, at, lookback_s=5.0)
        except Exception as exc:  # noqa: BLE001
            out.append({"minutes_ago": m, "served": False,
                        "error": f"{type(exc).__name__}: {str(exc)[:140]}"})
        else:
            out.append({"minutes_ago": m, "served": True, "error": None})
    return out


def _fmt(v: Any, nd: int = 2) -> str:
    return "absent" if v is None else f"{float(v):.{nd}f}"


def render(report: dict, out=sys.stdout) -> None:
    """The honest table. Absence is a word, never a blank and never a zero."""
    src = report["source"]
    print(f"\nSOURCE  {src['source']}  order_events={src['order_events_read']}"
          f"  log_events={src.get('events_in_log', 'unknown')}"
          f"  truncated={src['truncated']}", file=out)

    m = report["mark"]
    s = m["summary"]
    print(f"\nTABLE 1 - basis {s['basis']} (the fund's own struck mark; "
          f"NOT an effective spread)", file=out)
    print(f"  fill legs        {s['fills']}", file=out)
    for k, v in s["classifications"].items():
        print(f"    {k:<12} {v}", file=out)
    st = s["shortfall_bps"]
    if st is None:
        print("  shortfall_bps    ABSENT - no fill leg carries a usable mark "
              "that differs from its fill", file=out)
    else:
        print(f"  shortfall_bps    n={st['n']} mean={st['mean']} "
              f"median={st['median']} worst={st['worst']} best={st['best']}",
              file=out)
        print(f"                   (excludes {s['excluded_identities']} "
              f"identities, {s['excluded_cumulative']} cumulative legs, "
              f"{s['excluded_no_mark']} with no mark, "
              f"{s['excluded_unusable']} unusable)", file=out)
    print(f"\n  {'order':<10}{'kind':<18}{'sym':<7}{'side':<6}"
          f"{'fill':>12}{'incr':>12}{'mark':>12}{'bps':>10}  class", file=out)
    for r in m["rows"]:
        print(f"  {str(r['order_id'])[:8]:<10}{r['event_kind']:<18}"
              f"{str(r['symbol'] or '?'):<7}{str(r['side'] or '?'):<6}"
              f"{_fmt(r['fill_price'], 4):>12}"
              f"{_fmt(r['incremental_price'], 4):>12}"
              f"{_fmt(r['arrival_price'], 4):>12}"
              f"{_fmt(r['shortfall_bps']):>10}  {r['classification']}", file=out)

    q = report.get("quote")
    if q is None:
        print("\nTABLE 2 - not run. Pass --quotes to read the consolidated "
              "tape at each fill.", file=out)
    else:
        print(f"\nTABLE 2 - basis {RETRO_BASIS} (the consolidated quote in "
              f"force at the fill; THE effective spread)", file=out)
        print(f"  fill legs        {len(q['rows'])}   stored="
              f"{q['stored']}", file=out)
        print(f"  {'order':<10}{'sym':<7}{'side':<6}{'class':<14}"
              f"{'fill':>12}{'bid':>10}{'ask':>10}{'mid':>12}"
              f"{'eff_bps':>11}{'signed':>11}  absent", file=out)
        for r in q["rows"]:
            print(f"  {str(r['order_id'])[:8]:<10}{str(r['symbol'] or '?'):<7}"
                  f"{str(r['side'] or '?'):<6}{class_of_row(r):<14}"
                  f"{_fmt(r['fill_price'], 4):>12}"
                  f"{_fmt(r['bid'], 4):>10}{_fmt(r['ask'], 4):>10}"
                  f"{_fmt(r['mid'], 4):>12}"
                  f"{_fmt(r['effective_spread_bps']):>11}"
                  f"{_fmt(r['signed_effective_spread_bps']):>11}  "
                  f"{r['quote_absent_reason'] or ''}", file=out)
        qs = q["summary"]
        print(f"\n  BY EXECUTION CLASS - the headline is "
              f"'{qs['headline_class']}' and there is no undivided number",
              file=out)
        for cls, b in qs["by_execution_class"].items():
            head = cls == qs["headline_class"]
            for label, sub in (("", b), ("  single-leg", b["single_leg"]),
                               ("  multi-leg", b["multi_leg"])):
                e = sub["effective_spread_bps"]
                mark = ("  <-- THE FUND'S EXECUTION COST"
                        if head and label == "  single-leg" else "")
                print(f"    {(cls + label):<26} fills={sub['fills']:<3} "
                      f"measured={sub['measured']:<3} "
                      f"unmeasured={sub['unmeasured']:<3} "
                      f"eff_bps={'ABSENT' if e is None else e}{mark}", file=out)
        print("\n  BY SYMBOL", file=out)
        for row in qs["by_symbol"]:
            e = row["effective_spread_bps"]
            print(f"    {row['symbol']:<7} fills={row['fills']} "
                  f"measured={row['measured']} unmeasured={row['unmeasured']} "
                  f"classes={row['classes']} "
                  f"eff_bps={'ABSENT' if e is None else e}", file=out)

    c = report["coverage"]
    print("\nCOVERAGE - fills measured against a real QUOTE, out of all fills",
          file=out)
    if c is None:
        print("  REFUSED: the log was read over HTTP and capped, so a "
              "percentage would describe the newest page and not the fund.",
              file=out)
    elif not c["readable"]:
        print(f"  fill_events_total {c['fill_events_total']}", file=out)
        print(f"  measured          ABSENT ({c['reason']})", file=out)
    else:
        print(f"  fill_events_total {c['fill_events_total']}", file=out)
        print(f"  measured          {c['measured']}", file=out)
        print(f"  quote_absent      {c['quote_absent']}", file=out)
        print(f"  uncaptured        {c['uncaptured']}", file=out)
        print(f"  pct_measured      {_fmt(c['pct_measured'])}%", file=out)
    print("", file=out)


def build_report(events: list[dict], source: dict, *,
                 quotes: Any = None, store: Optional[QuoteStore] = None,
                 run_id: str = "", now: Optional[datetime] = None) -> dict:
    mark_rows = retro_mark_rows(events)
    report: dict = {
        "source": source,
        "mark": {"rows": mark_rows, "summary": summarise_mark_rows(mark_rows)},
        "quote": None,
        "coverage": None,
    }
    if quotes is not None:
        rows = quote_rows_for(events, quotes, run_id=run_id, store=store,
                              now=now)
        if store is not None:
            # ``record`` returns the stored projection, not the row. Re-read so
            # the table below shows what the STORE holds rather than what this
            # process believed it sent - the two disagreeing is exactly the
            # class of defect a report should surface.
            stored, _ = store.rows(limit=len(rows) + 1, basis=RETRO_BASIS)
            rows = stored
        report["quote"] = {"rows": rows, "stored": store is not None,
                           "summary": summarise_quote_rows(rows)}
    if source["truncated"]:
        return report
    legs = fill_legs(fold_order_lifecycles(events))
    if store is not None:
        try:
            all_rows, _ = store.rows(limit=10_000)
        except Exception:  # noqa: BLE001 - SchemaAbsent or an unreachable store
            all_rows = None
        report["coverage"] = coverage(legs, all_rows)
    elif report["quote"] is not None:
        report["coverage"] = coverage(legs, report["quote"]["rows"])
    else:
        report["coverage"] = coverage(legs, [])
    return report


def load_env() -> None:
    """Read ``ClarkHarness/.env`` — FROM ``main`` ONLY, never at import.

    Resolved from this file, not from the working directory, so the script
    finds the same credentials wherever it is launched (D20: a relative path in
    a control is a control that fails permissive).

    Called from ``main`` and nowhere else, deliberately. A ``load_dotenv()`` at
    module scope leaks the operator's real ``FUND_STORE``/``FUND_MODE`` into
    every test process that imports the module, which is how one merge night
    produced 109 false reds.
    """
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(str(ROOT / ".env"))


def main(argv: Optional[list[str]] = None) -> int:
    load_env()
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--spine", default=None,
                   help="read the log over HTTP instead of from Postgres; "
                        "capped at 1000 rows, so coverage is refused")
    p.add_argument("--dsn", default=None)
    p.add_argument("--quotes", action="store_true",
                   help="fetch the consolidated quote in force at each fill")
    p.add_argument("--store", action="store_true",
                   help="write the --quotes rows into fund_execution_quotes")
    p.add_argument("--run-id", default=None,
                   help="required with --store; stamped on every stored row")
    p.add_argument("--census", action="store_true")
    p.add_argument("--probe-delay", action="store_true",
                   help="re-measure the consolidated-data entitlement boundary")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)

    if a.probe_delay:
        rows = probe_delay(SipQuotes())
        print(json.dumps({"probe_delay": rows,
                          "documented_minutes": MEASURED_SIP_DELAY_MINUTES},
                         indent=1))
        return 0
    if a.store and not (a.run_id and a.run_id.strip()):
        p.error("--store needs --run-id: a stored row that cannot name the "
                "process that wrote it cannot be fenced off later")
    if a.store and not a.quotes:
        p.error("--store stores the --quotes rows; there is nothing to store "
                "without them (the mark table is never stored, by design)")

    events, source = (read_events_from_spine(a.spine) if a.spine
                      else read_events_from_store(a.dsn))
    if a.census:
        print(json.dumps(census(events), indent=1))
        return 0

    store = None
    if a.store:
        store = QuoteStore(a.dsn)
        store.ensure_schema()
    report = build_report(events, source, quotes=SipQuotes() if a.quotes else None,
                          store=store, run_id=a.run_id or "")
    if a.json:
        print(json.dumps(report, indent=1, default=str))
    else:
        render(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
