"""Derived daily rollups over the fund's own record — read-side only.

**A METRICS TABLE IS DERIVED, REBUILDABLE, AND NEVER A SOURCE OF TRUTH. NAV
FOLDS FROM THE EVENT LOG ONLY; NOTHING DOWNSTREAM MAY READ A ROLLUP AS THE
BOOK. IF A ROLLUP CANNOT BE COMPUTED IT REPORTS UNKNOWN — ABSENCE IS NEVER
ZERO — AND A FAILED REFRESH MUST NEVER RENDER AS A QUIET ZERO ROW.**

Why this module exists, measured rather than asserted (CEO, 2026-08-22:
*"why are all of our agent runs so slow ... Are we having every agent
re-compute a lot of stuff?"*). The secretary's end-of-day brief cost **80 tool
uses, 26 minutes and 271k tokens**, most of it re-deriving the same aggregates
from the raw log by hand: events by type, decision tallies by actor, NAV
strikes, fills, the friction table. The CFO assembled the firm's first spend
meter with ad-hoc queries and was silently truncated by the desk payload's
25-run cap. Three seats computed the same thing three ways and one of them was
wrong. That is not only a token problem — it is a **correctness** problem
wearing a cost problem's clothes, because a hand-rolled fold is a fold nobody
reviewed.

So: one place computes the day, one place documents the traps, and every seat
reads the same number.

WHAT KEEPS IT HONEST
--------------------

1. **Compute-first, cache-second.** ``compute_daily`` folds from the store on
   every call; ``MetricsStore.refresh`` merely *records* what was computed.
   A reader is served live arithmetic, and the stored row is reported beside
   it with ``agrees`` — so a stale rollup is *visible*, never authoritative.
   A cache that can silently disagree with the log is the write-only verdict
   column in a new costume.
2. **Absence is typed, not zeroed.** Every section that cannot be computed
   returns ``unknown(reason, note)`` — a dict with ``state: "UNKNOWN"`` and
   ``value: None``. The four reasons are distinct on purpose: the recorder
   being unreachable, the day holding no such event, a field the writer never
   wrote, and a value that could not be parsed are four different facts and
   collapsing them into ``0`` is this fund's oldest mistake.
3. **A partial day says so.** ``complete_day`` is False while the UTC day is
   still running. A rollup for today is a snapshot; one for yesterday is a
   measurement, and a reader must be able to tell them apart.

TRAPS THIS MODULE ABSORBS SO NO SEAT RE-LEARNS THEM (all measured against the
live log, 2026-08-22: 965 events, 52 runs)
-------------------------------------------

* Event types are **PascalCase** (``OrderFilled``); the column is ``type``,
  not ``event_type``; ``ts`` is **TEXT**, not a timestamp.
* ``OrderFilled`` money is **mixed-typed**: ``avg_price`` is a JSON *string*
  on 22 of 29 fills and a *number* on 7. Anything summing it without coercion
  either raises or concatenates.
* **20 of 29 ``OrderFilled`` payloads carry no ``venue`` key at all.** A venue
  split that buckets them as "paper" invents a fact; they are counted under
  ``venue_unstated``.
* ``DeskDispatched`` is **excluded from the request fold**: 14 of 24 carry no
  ``request_id``, and one carries a ``request_id`` with no matching
  ``DeskRequested`` — folding it in creates phantom requests with a None id.
* The runs recorder's token column is ``tokens``, not ``tokens_used``, and
  ``DeskStore.runs(limit=…)`` is capped **across all seats**, so a per-seat
  count folded from it is a floor wearing the costume of a count.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

logger = logging.getLogger(__name__)

#: Bumped when the SHAPE or the ARITHMETIC of a rollup changes, so a stored row
#: computed under an older definition is never silently compared with a new
#: one. A version that never moves is how two different numbers end up wearing
#: the same name.
METRICS_VERSION = "v1 (2026-08-22)"

#: Why a section could not be computed. A closed set, because "we could not
#: reach the recorder" and "the day genuinely had none" must never render as
#: the same word — and a free-text reason makes that distinction ungreppable.
UNKNOWN_REASONS = (
    "RECORDER_UNREACHABLE",   # the store/table could not be read at all
    "NONE_ON_DAY",            # read fine; the day holds no such event
    "FIELD_NEVER_WRITTEN",    # the event exists; the field we need is absent
    "UNREADABLE_VALUE",       # the field exists and could not be parsed
)


def unknown(reason: str, note: str, **extra: Any) -> dict[str, Any]:
    """A section that could not be computed, stated as such.

    Mirrors ``runanalytics.absent`` deliberately — a reader who has learned one
    absence shape in this codebase should not have to learn a second. The
    ``value: None`` key is present so a consumer that reaches for a number gets
    ``None`` (which fails loudly in arithmetic) rather than a zero that adds.
    """
    if reason not in UNKNOWN_REASONS:
        raise ValueError(f"reason must be one of {UNKNOWN_REASONS}, got {reason!r}")
    return {"state": "UNKNOWN", "value": None, "reason": reason,
            "note": note, **extra}


def is_unknown(section: Any) -> bool:
    return isinstance(section, dict) and section.get("state") == "UNKNOWN"


# --- day arithmetic ---------------------------------------------------------

def day_bounds(day: Any) -> tuple[str, str]:
    """Half-open ISO bounds ``[start, end)`` for one UTC day.

    UTC because the event log is UTC and the fund's day boundary is the
    venue's, not the reader's — the same rule ``desk.utc_day_bounds`` follows.

    The bounds are ISO strings with an explicit ``+00:00`` offset, which is what
    the log itself writes: all 965 stored ``ts`` values are exactly 32
    characters and end ``+00:00`` (measured 2026-08-22). That makes a *string*
    range comparison correct against the TEXT column — and it stays correct for
    a hypothetical ``…Z`` row too, since ``Z`` sorts after ``+`` and the date
    prefix dominates either way.
    """
    d = parse_day(day)
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


def parse_day(day: Any) -> date:
    """``YYYY-MM-DD`` (or a date/datetime) as a UTC calendar date.

    Refuses anything else rather than guessing. A malformed date that silently
    became "today" would serve a reader a different day from the one they
    asked for, and they would have no way to notice.
    """
    if isinstance(day, datetime):
        return day.astimezone(timezone.utc).date()
    if isinstance(day, date):
        return day
    if isinstance(day, str):
        try:
            return date.fromisoformat(day.strip()[:10])
        except ValueError:
            pass
    raise ValueError(f"day must be YYYY-MM-DD, got {day!r}")


def _ts_in(ts: Any, start: str, end: str) -> bool:
    """Is this event's timestamp inside the window?

    Compared as STRINGS on purpose (see ``day_bounds``), but only after the
    value is confirmed to be a non-empty string — an event with a missing
    ``ts`` is not silently placed on a day.
    """
    return isinstance(ts, str) and bool(ts) and start <= ts < end


def _num(raw: Any) -> Optional[Decimal]:
    """A Decimal, or None if the value is not one.

    ``OrderFilled`` writes ``avg_price`` as a JSON string on most rows and as a
    number on a few (22 vs 7, measured), because ``money.encode`` stringifies
    Decimals and some writers pass floats. Anything that sums this column
    without coercing raises ``TypeError`` or, worse, concatenates strings.

    ``None`` is returned rather than ``Decimal(0)``: an unreadable price is an
    unreadable price, and the caller counts it under ``unreadable`` instead of
    quietly adding nothing to a total that then looks complete.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None


# --- reading events ---------------------------------------------------------

def _get(e: Any, key: str) -> Any:
    if isinstance(e, dict):
        return e.get(key)
    return getattr(e, key, None)


def _etype(e: Any) -> Optional[str]:
    t = _get(e, "type")
    return getattr(t, "value", t)


def _payload(e: Any) -> dict[str, Any]:
    p = _get(e, "payload")
    return p if isinstance(p, dict) else {}


def _events_for_day(store: Any, start: str, end: str) -> list[dict[str, Any]]:
    """Every event on the day, from the store's own reader.

    Deliberately goes through ``store.stream`` rather than SQL: the same fold
    must work on either backend and must be testable against the in-memory
    fake, which is the only reason this module has unit tests at all.
    ``desk._requests`` makes the same call with the same limit.
    """
    rows = store.stream(since_seq=0, limit=100_000)
    return [e for e in rows if _ts_in(_get(e, "ts"), start, end)]


# --- sections ---------------------------------------------------------------

def _events_section(day_events: list[dict[str, Any]]) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    untyped = 0
    for e in day_events:
        t = _etype(e)
        if not isinstance(t, str) or not t:
            untyped += 1
            continue
        by_type[t] = by_type.get(t, 0) + 1
    return {"total": len(day_events),
            "by_type": dict(sorted(by_type.items(),
                                   key=lambda kv: (-kv[1], kv[0]))),
            # An event whose type could not be read is counted here and NOT
            # dropped: a fold whose parts do not sum to its total is lying
            # about one of the two.
            "untyped": untyped}


def _decisions_section(day_events: list[dict[str, Any]]) -> dict[str, Any]:
    """``DeskRecommendationDecided`` by actor and by status.

    The ACTOR is the event's own actor column (``ceo`` / ``cto`` / ``co-cto``
    on the live log), never anything read out of prose — the wider log's
    ``actor`` field holds 200-character sentences on other event types, so this
    reads only the one type where it is a short identity.
    """
    rows = [e for e in day_events if _etype(e) == "DeskRecommendationDecided"]
    by_actor: dict[str, int] = {}
    by_status: dict[str, int] = {}
    pairs: dict[str, int] = {}
    for e in rows:
        actor = _get(e, "actor")
        actor = actor if isinstance(actor, str) and actor else "UNSTATED"
        status = _payload(e).get("status")
        status = status if isinstance(status, str) and status else "UNSTATED"
        by_actor[actor] = by_actor.get(actor, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
        key = f"{actor}/{status}"
        pairs[key] = pairs.get(key, 0) + 1
    return {"total": len(rows), "by_actor": by_actor, "by_status": by_status,
            "by_actor_status": pairs}


def _nav_section(day_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Open, close and strike count from ``NavStruck``.

    A DERIVED READING OF THE LOG, never the book. The authoritative NAV is what
    ``NavService`` folds; this reports the strikes recorded on a day so a
    reader can ask "how many times did we mark, and where did we start and end"
    without replaying anything.

    A day with no strike returns UNKNOWN, not ``0.0``. A fund that was not
    marked is not a fund worth nothing.
    """
    rows = [e for e in day_events if _etype(e) == "NavStruck"]
    if not rows:
        return unknown("NONE_ON_DAY",
                       "no NavStruck on this UTC day — the fund was not marked, "
                       "which is not the same as being marked at zero")
    ordered = sorted(rows, key=lambda e: (_get(e, "seq") or 0, _get(e, "ts") or ""))

    def _nav_of(e: Any) -> Optional[float]:
        v = _num(_payload(e).get("total_nav_usd"))
        return None if v is None else float(v)

    unreadable = sum(1 for e in ordered if _nav_of(e) is None)
    return {
        "strikes": len(ordered),
        "open_usd": _nav_of(ordered[0]),
        "close_usd": _nav_of(ordered[-1]),
        "open_ts": _get(ordered[0], "ts"),
        "close_ts": _get(ordered[-1], "ts"),
        # Named rather than inferred from a None above: "the strike carried no
        # readable total" and "there was no strike" are different facts and a
        # caller must be able to tell them apart.
        "unreadable_strikes": unreadable,
        "complete": unreadable == 0,
    }


def nav_strikes(day: Any, store: Any) -> dict[str, Any]:
    """Each individual NavStruck on a day, oldest first — the DETAIL view.

    ``compute_daily``'s ``nav`` section answers "how many, and open to close".
    This answers "show me each one", which is the question asked when a strike
    looks wrong. Kept in the module rather than in the script so both readings
    come from one fold; a second copy in a script drifts and the drift is
    invisible because both copies look plausible.

    A DERIVED READING OF THE LOG, never the book — same rule as every other
    section here. A strike whose total cannot be parsed is listed with
    ``total_nav_usd: None``, not dropped: a strike that happened and could not
    be read is a fact worth seeing.
    """
    d = parse_day(day)
    start, end = day_bounds(d)
    rows = [e for e in _events_for_day(store, start, end)
            if _etype(e) == "NavStruck"]
    rows.sort(key=lambda e: (_get(e, "seq") or 0, _get(e, "ts") or ""))
    out = []
    for e in rows:
        p = _payload(e)
        total = _num(p.get("total_nav_usd"))
        bd = p.get("breakdown") if isinstance(p.get("breakdown"), dict) else {}
        positions = p.get("positions")
        out.append({
            "seq": _get(e, "seq"),
            "ts": _get(e, "ts"),
            "total_nav_usd": None if total is None else float(total),
            "cash_usd": _f(bd.get("cash")),
            "positions_usd": _f(bd.get("positions")),
            # A count, not the whole list: the strike payload carries every
            # position and a detail script does not need 60 KB per row.
            "position_count": (len(positions) if isinstance(positions, list)
                               else None),
        })
    return {"day": d.isoformat(), "strikes": out, "count": len(out),
            "note": (f"{len(out)} strike(s) on {d.isoformat()}" if out else
                     f"no NavStruck on {d.isoformat()} — the fund was not "
                     "marked, which is not the same as being marked at zero")}


def _f(raw: Any) -> Optional[float]:
    v = _num(raw)
    return None if v is None else float(v)


def _fills_section(day_events: list[dict[str, Any]]) -> dict[str, Any]:
    """``OrderFilled`` count, notional and venue split.

    THREE MEASURED HAZARDS ARE HANDLED HERE AND NOWHERE ELSE:

    * ``avg_price`` and ``filled_qty`` are strings on most rows and numbers on
      some. Both are coerced through ``Decimal(str(x))``.
    * **20 of 29 fills carry no ``venue`` key.** They are counted under
      ``venue_unstated`` and are NOT bucketed as paper. The distinction is not
      pedantry: the firm's R15 cost-measurement experiment was falsely marked
      done because a fill labelled ``alpaca`` had executed on paper, and a
      venue split that invents labels is that same failure pointed the other
      way.
    * A fill whose numbers cannot be read raises ``complete: False`` on the
      notional rather than contributing zero to a total that then reads full.
    """
    rows = [e for e in day_events if _etype(e) == "OrderFilled"]
    total = Decimal("0")
    unreadable = 0
    by_venue: dict[str, int] = {}
    by_side: dict[str, int] = {}
    unstated = 0
    for e in rows:
        p = _payload(e)
        px, qty = _num(p.get("avg_price")), _num(p.get("filled_qty"))
        if px is None or qty is None:
            unreadable += 1
        else:
            total += abs(px * qty)
        v = p.get("venue")
        if isinstance(v, str) and v.strip():
            by_venue[v] = by_venue.get(v, 0) + 1
        else:
            unstated += 1
        s = p.get("side")
        s = s if isinstance(s, str) and s else "UNSTATED"
        by_side[s] = by_side.get(s, 0) + 1
    return {
        "count": len(rows),
        "notional_usd": float(round(total, 2)),
        "complete": unreadable == 0,
        "unreadable": unreadable,
        "by_venue": by_venue,
        # NOT folded into by_venue. See the docstring.
        "venue_unstated": unstated,
        "by_side": by_side,
    }


def _requests_section(day_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Desk request lifecycle EVENTS that landed on this day.

    Counts events, not folded states — "three were approved today" is a
    different question from "three are approved now", and ``friction()``
    answers the second. ``DeskDispatched`` is excluded for the reason in the
    module docstring.
    """
    counts = {"filed": 0, "approved": 0, "resolved": 0, "declined": 0}
    keys = {"DeskRequested": "filed", "DeskRequestApproved": "approved",
            "DeskRequestResolved": "resolved", "DeskRequestDeclined": "declined"}
    for e in day_events:
        k = keys.get(_etype(e) or "")
        if k:
            counts[k] += 1
    return counts


def _runs_section(deskstore: Any, start: str, end: str) -> dict[str, Any]:
    """Per-seat runs, tokens and tool uses for the day — UNCAPPED.

    Uses ``DeskStore.runs_between``, which filters in SQL. The desk payload's
    ``runs(limit=25)`` is capped ACROSS ALL SEATS, so folding a per-seat count
    out of it silently truncates the quietest seat first; the CFO's first spend
    meter was built on exactly that payload and under-reported lifetime runs by
    more than half.

    A recorder that cannot be reached returns UNKNOWN. It does **not** return
    an empty seat table — "no runs today" and "we could not look" are the two
    facts this whole module exists to keep apart.
    """
    if deskstore is None:
        return unknown("RECORDER_UNREACHABLE",
                       "the run recorder is not configured (FUND_STORE is not "
                       "postgres) — no statement is made about how many runs "
                       "happened, which is not a statement that none did")
    try:
        rows = deskstore.runs_between(start, end, limit=10_000)
    except Exception as e:  # noqa: BLE001
        logger.warning("metrics: run recorder unreadable for [%s,%s): %s",
                       start, end, e)
        return unknown("RECORDER_UNREACHABLE",
                       f"the run recorder raised while being read: {e}")
    return summarise_runs(rows)


def summarise_runs(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Per-seat aggregates over run rows. Shared by the day and the lifetime.

    ``tokens`` and ``tool_uses`` are nullable columns, so each is summed over
    the rows that HAVE one and the rows that do not are counted. A seat whose
    every run predates token capture reports ``tokens: None`` with
    ``runs_missing_tokens`` equal to its run count — never ``0``, which would
    make the least-measured seat also the cheapest one on the meter.
    """
    seats: dict[str, dict[str, Any]] = {}
    total_runs = 0
    durations: dict[str, list[float]] = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        total_runs += 1
        seat = r.get("seat")
        seat = seat if isinstance(seat, str) and seat else "UNSTATED"
        s = seats.setdefault(seat, {
            "runs": 0, "tokens": 0, "tool_uses": 0,
            "runs_missing_tokens": 0, "runs_missing_tool_uses": 0,
            "first_resolved_at": None, "last_resolved_at": None,
            "runs_missing_duration": 0, "by_status": {},
        })
        durations.setdefault(seat, [])
        s["runs"] += 1
        tok, tools = r.get("tokens"), r.get("tool_uses")
        if isinstance(tok, int) and not isinstance(tok, bool):
            s["tokens"] += tok
        else:
            s["runs_missing_tokens"] += 1
        if isinstance(tools, int) and not isinstance(tools, bool):
            s["tool_uses"] += tools
        else:
            s["runs_missing_tool_uses"] += 1
        res = r.get("resolved_at")
        if isinstance(res, str) and res:
            if s["first_resolved_at"] is None or res < s["first_resolved_at"]:
                s["first_resolved_at"] = res
            if s["last_resolved_at"] is None or res > s["last_resolved_at"]:
                s["last_resolved_at"] = res
        d = _duration_seconds(r.get("dispatched_at"), res)
        if d is None:
            s["runs_missing_duration"] += 1
        else:
            durations[seat].append(d)
        # A run that carries no status made NO STATEMENT about whether it
        # delivered. `unrecorded` is that absence with a name; it is not a
        # synonym for `delivered`, and every run written before the column
        # existed sits here permanently and correctly.
        st = r.get("status")
        st = st if isinstance(st, str) and st else "unrecorded"
        s["by_status"][st] = s["by_status"].get(st, 0) + 1

    for seat, s in seats.items():
        ds = durations.get(seat, [])
        # None, not 0: nobody wrote dispatched_at on these runs, so their
        # wall-clock is unknown. A zero here would make the firm's slowest work
        # look instantaneous, which is precisely the bias this field exists to
        # remove.
        s["median_duration_seconds"] = _median(ds)
        s["runs_with_duration"] = len(ds)
        if s["runs_missing_tokens"] == s["runs"]:
            s["tokens"] = None
        if s["runs_missing_tool_uses"] == s["runs"]:
            s["tool_uses"] = None

    tok_total = sum(v["tokens"] for v in seats.values()
                    if isinstance(v["tokens"], int))
    tools_total = sum(v["tool_uses"] for v in seats.values()
                      if isinstance(v["tool_uses"], int))
    missing_tok = sum(v["runs_missing_tokens"] for v in seats.values())
    missing_dur = sum(v["runs_missing_duration"] for v in seats.values())
    failed = sum(v["by_status"].get("failed", 0) + v["by_status"].get("aborted", 0)
                 for v in seats.values())
    unrecorded = sum(v["by_status"].get("unrecorded", 0) for v in seats.values())
    return {
        "total_runs": total_runs,
        "total_tokens": tok_total,
        "total_tool_uses": tools_total,
        "runs_missing_tokens": missing_tok,
        "runs_missing_duration": missing_dur,
        # Leg 1 of the firm's self-knowledge: work that DIED. Today's meter
        # records at resolve, so a dispatch that dies costs zero by
        # construction. `runs_unrecorded_status` is the size of the blind spot
        # that remains, and it must be read next to `runs_failed` — a zero
        # failure count beside a large unrecorded count is not a clean record.
        "runs_failed": failed,
        "runs_unrecorded_status": unrecorded,
        "by_seat": dict(sorted(seats.items())),
        "note": (
            f"{total_runs} run(s); {tok_total} token(s) summed over "
            f"{total_runs - missing_tok} run(s) that carry the field"
            + (f"; {missing_tok} run(s) carry NO token count and contribute "
               "nothing rather than zero" if missing_tok else "")
            + (f"; {missing_dur} run(s) carry no dispatched_at so their "
               "wall-clock is UNKNOWN" if missing_dur else "")
            + (f"; {unrecorded} run(s) state no outcome, so the {failed} "
               "recorded failure(s) are a FLOOR" if unrecorded else "")
        ),
    }


def run_stats(deskstore: Any) -> dict[str, Any]:
    """LIFETIME per-seat run aggregates, and a proof they are not truncated.

    Built because the firm's first spend meter was assembled by hand from
    ``GET /fund/desk/runs``'s default payload, whose 25-run cap is documented
    in ``deskstore`` as "a FLOOR wearing the costume of a count" — and lifetime
    runs were 49+. Nobody knew until someone queried the uncapped endpoint.

    So this does not merely raise the limit; it CHECKS it. ``row_count`` comes
    from ``SELECT count(*)`` and ``truncated`` compares it against how many
    rows were actually read. A meter that cannot tell you whether it saw
    everything is not a meter.
    """
    if deskstore is None:
        return unknown("RECORDER_UNREACHABLE",
                       "the run recorder is not configured (FUND_STORE is not "
                       "postgres) — no lifetime figures are available, which "
                       "is not a statement that they are zero")
    try:
        rows = deskstore.all_runs()
        total = deskstore.run_count()
    except Exception as e:  # noqa: BLE001
        logger.warning("metrics: run recorder unreadable: %s", e)
        return unknown("RECORDER_UNREACHABLE",
                       f"the run recorder raised while being read: {e}")
    body = summarise_runs(rows)
    truncated = len(rows) < total
    body["row_count"] = total
    body["rows_read"] = len(rows)
    body["truncated"] = truncated
    body["complete"] = not truncated
    if truncated:
        # Loud, because the failure this whole function exists to prevent is a
        # partial answer read as a full one.
        body["note"] = (f"TRUNCATED: {len(rows)} of {total} rows were read, so "
                        "every figure below is a FLOOR. " + body["note"])
    return body


def _duration_seconds(dispatched: Any, resolved: Any) -> Optional[float]:
    a, b = _instant(dispatched), _instant(resolved)
    if a is None or b is None:
        return None
    d = (b - a).total_seconds()
    # A negative duration is a clock or data error, not a fast run. Reported as
    # unknown rather than as a number that would drag a median downward.
    return d if d >= 0 else None


def _instant(v: Any) -> Optional[datetime]:
    """An ISO string (or datetime) as a comparable instant, or None.

    A naive timestamp is read as UTC, the same assumption ``desk._ts`` makes
    and for the same reason: Python refuses to order naive against aware, so
    one unzoned string would otherwise raise from inside a payload builder.
    """
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if not isinstance(v, str) or not v.strip():
        return None
    try:
        t = datetime.fromisoformat(v.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _median(xs: list[float]) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return float(s[mid]) if n % 2 else float((s[mid - 1] + s[mid]) / 2)


# --- the public rollup ------------------------------------------------------

def compute_daily(day: Any, store: Any, deskstore: Any = None,
                  now: Optional[datetime] = None) -> dict[str, Any]:
    """Everything the firm did on one UTC day, folded once.

    Pure with respect to the database: it READS and returns; it never writes.
    Persisting is ``MetricsStore.refresh``'s job, and keeping the two apart is
    what makes "the rollup disagrees with the log" a detectable condition
    rather than an invisible one.
    """
    d = parse_day(day)
    start, end = day_bounds(d)
    n = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    day_events = _events_for_day(store, start, end)
    body: dict[str, Any] = {
        "day": d.isoformat(),
        "window": {"start": start, "end": end},
        "metrics_version": METRICS_VERSION,
        # A rollup for TODAY is a snapshot of a day still happening. Saying so
        # is the difference between "the firm did four things" and "the firm
        # has done four things so far".
        "complete_day": end <= n.isoformat(),
        "events": _events_section(day_events),
        "decisions": _decisions_section(day_events),
        "nav": _nav_section(day_events),
        "fills": _fills_section(day_events),
        "reconciliation_mismatches": sum(
            1 for e in day_events if _etype(e) == "ReconciliationMismatch"),
        "desk_requests": _requests_section(day_events),
        "runs": _runs_section(deskstore, start, end),
    }
    body["unknown_sections"] = sorted(k for k, v in body.items() if is_unknown(v))
    body["digest"] = digest(body)
    body["computed_at"] = n.isoformat()
    return body


def digest(body: dict[str, Any]) -> str:
    """A stable fingerprint of a rollup's CONTENT, excluding when it was made.

    Used to answer one question and only one: does the stored row still say
    what a fresh computation says? ``computed_at`` and ``digest`` itself are
    excluded, so re-running the same fold over the same log is a match rather
    than a diff — otherwise every read would report drift and the signal would
    be worthless within a day.
    """
    trimmed = {k: v for k, v in body.items()
               if k not in ("computed_at", "digest")}
    blob = json.dumps(trimmed, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --- the friction view ------------------------------------------------------

#: What a desk request can be, folded forward from its events. Four terminal-ish
#: states plus the one this view exists to name.
#:
#: ``approved_undispatched`` is a REFINEMENT of ``approved``, not a rival to it:
#: the CEO said yes and nothing has been dispatched. It is a first-class state
#: because it is the firm's largest measured queue and it was invisible — the
#: secretary's first friction ledger found **28 requests approved and
#: undispatched at midnight on 2026-08-21, all waiting on the chair, the oldest
#: 14h34m, and only 3 of the 28 answered the next day.** A ledger that only
#: measures agents measures the cheap half.
REQUEST_STATES = ("open", "approved_undispatched", "approved_dispatched",
                  "resolved", "declined")

#: Whose move it is in each state. Derived from the record, not assumed:
#: every ``DeskRequestApproved`` on the live log carries actor ``ceo`` or
#: ``neelesh-via-cto``/``-via-co-cto`` — i.e. the CEO's instruction — so an
#: OPEN request is waiting on the CEO, and an approved one is waiting on the
#: chair to dispatch it. Terminal states wait on nobody.
WAITING_ON = {
    "open": "ceo",
    "approved_undispatched": "chair",
    "approved_dispatched": "seat",
    "resolved": None,
    "declined": None,
}


def friction(store: Any, now: Optional[datetime] = None) -> dict[str, Any]:
    """Every desk request, folded forward, aged, oldest first.

    THE FOLD IS ORDER-HONEST AND MIRRORS ``desk._requests``: an approval only
    moves an OPEN request; a decline lands on open-or-approved; a resolution
    completes open-or-approved and must never overwrite a decline, because
    executing a declined ask would be the chair overriding the CEO's no.

    **``DeskDispatched`` IS EXCLUDED FROM THE FOLD ITSELF** and used only to
    annotate a row that already exists. Measured on the live log 2026-08-22:
    14 of 24 dispatch events carry no ``request_id``, and one carries a
    ``request_id`` for which no ``DeskRequested`` was ever written. A fold that
    included them would create a phantom request with a ``None`` id and then
    age it forever.

    **THE UNDISPATCHED COUNT IS AN UPPER BOUND AND THE PAYLOAD SAYS SO.**
    Because only 10 of 24 dispatch events are linkable, a request may have been
    dispatched without this view being able to see it. Every row carries
    ``dispatch_detectable``; the summary carries ``dispatch_link_coverage``.
    Reporting 30 as though it were a count would be a confident number resting
    on an instrument that cannot see half its own input.
    """
    n = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows: dict[str, dict[str, Any]] = {}
    dispatches: dict[str, list[str]] = {}
    dispatch_total = 0
    dispatch_unlinkable = 0
    dispatch_orphan = 0

    for e in store.stream(since_seq=0, limit=100_000):
        t = _etype(e)
        p = _payload(e)
        rid = p.get("request_id")
        if t == "DeskRequested":
            if rid:
                rows[rid] = {
                    "request_id": rid,
                    # Seat-filed asks write subject/serves where CEO-typed
                    # requests write task/seat. Normalised here exactly as
                    # `desk._requests` does, because an unnormalised seat ask
                    # is COUNTED and renders blank — an invisible item.
                    "task": p.get("task") or p.get("subject"),
                    "seat": p.get("seat") or p.get("serves"),
                    "kind": p.get("kind"),
                    "filed_by": p.get("actor"),
                    "filed_at": p.get("at"),
                    "status": "open",
                    "status_at": p.get("at"),
                    "approved_at": None, "approved_by": None,
                    "resolved_at": None, "declined_at": None,
                }
        elif t == "DeskRequestApproved":
            r = rows.get(rid) if rid else None
            if r is not None and r["status"] == "open":
                r.update(status="approved", approved_at=p.get("at"),
                         approved_by=p.get("actor"), status_at=p.get("at"))
        elif t == "DeskRequestDeclined":
            r = rows.get(rid) if rid else None
            if r is not None and r["status"] in ("open", "approved"):
                r.update(status="declined", declined_at=p.get("at"),
                         status_at=p.get("at"))
        elif t == "DeskRequestResolved":
            r = rows.get(rid) if rid else None
            if r is not None and r["status"] in ("open", "approved"):
                r.update(status="resolved", resolved_at=p.get("at"),
                         status_at=p.get("at"))
        elif t == "DeskDispatched":
            dispatch_total += 1
            if not rid:
                dispatch_unlinkable += 1
            elif rid not in rows:
                # A dispatch naming a request that was never filed. Counted,
                # never folded — this is the exact row that becomes a phantom.
                dispatch_orphan += 1
            else:
                dispatches.setdefault(rid, []).append(p.get("at") or "")

    out = []
    for r in rows.values():
        rid = r["request_id"]
        seen = rid in dispatches
        if r["status"] == "approved":
            state = "approved_dispatched" if seen else "approved_undispatched"
        else:
            state = r["status"]
        age = _age_hours(r["filed_at"], n)
        out.append({
            **r,
            "state": state,
            "waiting_on": WAITING_ON.get(state),
            "terminal": state in ("resolved", "declined"),
            # Hours since FILING. None when the filing timestamp cannot be
            # read — an unaged row sorts last and says why, rather than
            # claiming an age of zero and jumping to the top of the queue.
            "age_hours": age,
            "age_in_state_hours": _age_hours(r.get("status_at"), n),
            "dispatch_seen": seen,
            "dispatch_at": sorted(dispatches.get(rid, []))[0] if seen else None,
            # False for every row while the log carries unlinkable dispatch
            # events: we cannot prove this one was NOT dispatched.
            "dispatch_detectable": dispatch_unlinkable == 0,
        })

    # Oldest first. Rows whose age could not be read sort LAST (None is not
    # "brand new"), and request_id breaks ties so the order is stable across
    # calls — an unstable sort makes two identical reads look like a change.
    out.sort(key=lambda r: (r["age_hours"] is None,
                            -(r["age_hours"] or 0.0), r["request_id"]))

    by_state = {s: 0 for s in REQUEST_STATES}
    for r in out:
        by_state[r["state"]] = by_state.get(r["state"], 0) + 1
    waiting: dict[str, int] = {}
    for r in out:
        if r["waiting_on"]:
            waiting[r["waiting_on"]] = waiting.get(r["waiting_on"], 0) + 1
    open_rows = [r for r in out if not r["terminal"]]
    oldest = open_rows[0] if open_rows else None
    undispatched = by_state["approved_undispatched"]
    linkable = dispatch_total - dispatch_unlinkable
    return {
        "requests": out,
        "count": len(out),
        "by_state": by_state,
        "waiting_on": waiting,
        "open_count": len(open_rows),
        "oldest_open_hours": oldest["age_hours"] if oldest else None,
        "oldest_open_request_id": oldest["request_id"] if oldest else None,
        "approved_undispatched": undispatched,
        "dispatch_link_coverage": {
            "dispatch_events": dispatch_total,
            "linkable": linkable,
            "unlinkable_no_request_id": dispatch_unlinkable,
            "orphan_request_id": dispatch_orphan,
            "complete": dispatch_unlinkable == 0 and dispatch_orphan == 0,
        },
        "computed_at": n.isoformat(),
        "note": (
            f"{len(open_rows)} request(s) still on the path"
            + (f", oldest {oldest['age_hours']:.1f}h since filing"
               if oldest and oldest["age_hours"] is not None else "")
            + f"; {undispatched} approved and not visibly dispatched"
            + (f". THIS IS AN UPPER BOUND: {dispatch_unlinkable} of "
               f"{dispatch_total} DeskDispatched events carry no request_id, "
               "so a dispatched request can look undispatched here"
               if dispatch_unlinkable else "")
            + (f". {dispatch_orphan} dispatch event(s) naming a request that "
               "was never filed; counted, never folded" if dispatch_orphan else "")
            + "."
        ),
    }


def _age_hours(at: Any, now: datetime) -> Optional[float]:
    t = _instant(at)
    if t is None:
        return None
    return round((now - t).total_seconds() / 3600.0, 2)


# --- persistence (Postgres) -------------------------------------------------

#: The rollup table. ONE ROW PER UTC DAY, holding a whole computed body.
#:
#: A wide column-per-metric table was considered and rejected: every new metric
#: would be a migration, and the thing this table is FOR — letting a seat ask a
#: question without re-deriving it — is exactly what a rigid schema makes
#: expensive. The body is JSONB, the identity is the day, and the row carries
#: the version and digest of the computation that produced it so a stored value
#: can never be read as though it came from today's definition.
#:
#: `fund_metrics_` prefix so a reader of `\dt` can see at a glance which tables
#: are DERIVED. Nothing in here is a source of truth; dropping the whole table
#: loses nothing that `compute_daily` cannot rebuild from the log.
SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_metrics_daily (
    day             DATE        PRIMARY KEY,
    metrics_version TEXT        NOT NULL,
    digest          TEXT        NOT NULL,
    complete_day    BOOLEAN     NOT NULL,
    payload         JSONB       NOT NULL,
    computed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS fund_metrics_daily_computed_idx
    ON fund_metrics_daily (computed_at DESC);
"""


class MetricsStore:
    """Records what ``compute_daily`` computed. Never the authority for it.

    Every read path in this module recomputes; this class exists so a rollup
    can be KEPT — for a trend line, for a day whose events are one day pruned,
    and so a reader can see that a stored number no longer matches the log.
    """

    def __init__(self, dsn: Optional[str] = None):
        from app.fund.pgstore import dsn as default_dsn
        self._dsn = dsn or default_dsn()
        self._ensure()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    def refresh(self, day: Any, store: Any, deskstore: Any = None,
                now: Optional[datetime] = None) -> dict[str, Any]:
        """Compute the day and record it. IDEMPOTENT.

        Running it twice over an unchanged log produces an unchanged row —
        ``digest`` is the test, and ``changed`` in the return says whether the
        content actually moved. That is not decoration: a refresh of a CLOSED
        day whose digest moves means the log gained events after the day ended
        (a backfill, a late correction), and a chair should see that rather
        than have the row silently replaced.

        **A FAILED COMPUTATION IS NOT WRITTEN.** If ``compute_daily`` raises,
        the exception propagates and the previous row stands; nothing writes a
        zero row on failure. That is the module's founding rule, enforced by the
        simplest possible means — there is no except clause here to get it
        wrong.
        """
        body = compute_daily(day, store, deskstore=deskstore, now=now)
        prev = self.stored(body["day"])
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_metrics_daily
                        (day, metrics_version, digest, complete_day, payload,
                         computed_at)
                    VALUES (%s, %s, %s, %s, %s, now())
                    ON CONFLICT (day) DO UPDATE SET
                        metrics_version = EXCLUDED.metrics_version,
                        digest          = EXCLUDED.digest,
                        complete_day    = EXCLUDED.complete_day,
                        payload         = EXCLUDED.payload,
                        computed_at     = now()
                    """,
                    (body["day"], body["metrics_version"], body["digest"],
                     bool(body["complete_day"]), json.dumps(body, default=str)))
            conn.commit()
        return {
            "day": body["day"],
            "digest": body["digest"],
            "metrics_version": body["metrics_version"],
            "complete_day": body["complete_day"],
            "previous_digest": (prev or {}).get("digest"),
            "changed": bool(prev) and prev.get("digest") != body["digest"],
            "first_write": prev is None,
            "unknown_sections": body["unknown_sections"],
        }

    def stored(self, day: Any) -> Optional[dict[str, Any]]:
        """The recorded row for a day, or None. None means NOT RECORDED."""
        d = parse_day(day)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT day, metrics_version, digest, complete_day, "
                    "       payload, computed_at "
                    "FROM fund_metrics_daily WHERE day = %s", (d,))
                row = cur.fetchone()
        if not row:
            return None
        return {"day": row[0].isoformat(), "metrics_version": row[1],
                "digest": row[2], "complete_day": row[3], "payload": row[4],
                "computed_at": row[5].isoformat() if row[5] else None}

    def days(self, limit: int = 90) -> list[dict[str, Any]]:
        """Recorded days, newest first — headers only, not whole bodies.

        The payload can be tens of kilobytes; a trend line needs the day, the
        version and when it was computed. Shipping every body to answer "which
        days do we have" is how a convenience endpoint becomes the slow thing
        it was built to replace.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT day, metrics_version, digest, complete_day, "
                    "       computed_at "
                    "FROM fund_metrics_daily ORDER BY day DESC LIMIT %s",
                    (limit,))
                rows = cur.fetchall()
        return [{"day": r[0].isoformat(), "metrics_version": r[1],
                 "digest": r[2], "complete_day": r[3],
                 "computed_at": r[4].isoformat() if r[4] else None}
                for r in rows]
