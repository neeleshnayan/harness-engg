"""Whether the struck-NAV series has HOLES, and whether any hole ate a session.

WHY THIS EXISTS, measured: between ``2026-08-24T19:14:46Z`` and
``2026-08-26T13:52:04Z`` this fund struck no NAV at all — 42.6 hours, swallowing
the whole of Tuesday 2026-08-25, a trading day (verified independently: the
fund's own SPY daily series carries a bar for that date). Nothing noticed. The
stack was down; the host watchdog now removes that CAUSE, and this module is the
other half — DETECTION, so the record can say "I have a hole" instead of serving
a series whose missing days are indistinguishable from days that did not exist.

The doctrine gap this closes is named in the guide as
``doc-integrity-not-completeness``: an append-only log is tamper-EVIDENT and says
nothing at all about being COMPLETE. Every event in it can be genuine while a
day is missing.

WHY THE HEARTBEAT COULD NOT ANSWER THIS, and it is not a defect in the
heartbeat. ``heartbeat.BUDGETS_SECONDS["nav_strike"]`` watches whether the
strike LOOP ran; ``main.py`` deliberately beats it on a no-strike decision too
("a deliberate no-strike is the job WORKING"), which is right. And the heartbeat
is in memory, so a process that was not alive for the hole has nothing to report
about it — the only durable evidence of a missed strike is the absence of the
strike. That absence is what this module reads.

THE TOLERANCE IS READ, NEVER COPIED. What counts as "too long between strikes"
is already a declared number in this codebase — ``BUDGETS_SECONDS["nav_strike"]``
— and this module reads it at call time from ``heartbeat``. It does not restate
it, and there is a test that MOVES the value and watches the verdict follow,
because an assertion that two numbers are equal cannot tell a read from a
hardcoded duplicate that happens to agree today. If that key ever disappears,
the tolerance is ABSENT and gap classification reports UNDETERMINED rather than
inventing a number.

WHAT IS AND IS NOT A HOLE. Trading time is the only clock that matters here: a
weekend with no strikes is not a hole because there was nothing to strike. So a
gap is measured by the REGULAR-SESSION seconds it contains, not by its wall
duration — the 65-hour Friday-evening-to-Monday-morning gap in this fund's own
history contains 20 minutes of trading time and is not a finding; the 42.6-hour
one contains 6h52m and is.

WHAT THIS MODULE DOES NOT DO: it raises no alarm and appends no event.
``RiskMonitor.run()`` is the only code in this fund that raises alarms, and
adding a second raiser — casually, in a module like this — is exactly the defect
class the fund hunts. This module is a pure READER; wiring its verdict into the
monitor's own rule sequence is a sensitive change for a human to make.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable, Optional
from zoneinfo import ZoneInfo

#: Bumped when the payload's SHAPE or the meaning of a field changes, so a
#: consumer reading a cached response can tell which contract it holds.
NAVGAP_VERSION = "v1"

MARKET_TZ = ZoneInfo("America/New_York")

#: The REGULAR session only. Extended hours are excluded deliberately: the venue
#: clock this fund strikes on reports the regular session (``session.py``'s own
#: stated limit), so a strike is neither expected nor possible outside it.
SESSION_OPENS = time(9, 30)
SESSION_CLOSES = time(16, 0)
#: Half-days close at 13:00 ET (NYSE, "1:00 p.m. (1:15 p.m. for eligible
#: options)"). Options are irrelevant here; this fund holds none.
EARLY_SESSION_CLOSES = time(13, 0)

#: Source and coverage of the closure table below. Sourced from the venue rather
#: than derived from a rule, because the rules (observed holidays, Good Friday's
#: moving date, an unscheduled closure for a national day of mourning) are not
#: derivable and a wrong one silently converts a hole into a holiday.
CALENDAR_SOURCE = "https://www.nyse.com/markets/hours-calendars"
CALENDAR_SOURCED_ON = "2026-08-27"
CALENDAR_FIRST_DAY = date(2026, 1, 1)
CALENDAR_LAST_DAY = date(2027, 12, 31)

#: Full closures. VERIFIED against this fund's own data, not merely transcribed:
#: over the 170 weekdays from 2026-01-01 to 2026-08-26, every weekday without a
#: SPY daily bar is in this set and every weekday with one is not — zero
#: disagreements in either direction (reproduce:
#: ``scripts/data/verify_market_calendar.py``).
HOLIDAYS = frozenset({
    # 2026
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25",
    "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25",
    # 2027
    "2027-01-01", "2027-01-18", "2027-02-15", "2027-03-26", "2027-05-31",
    "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24",
})

#: 13:00 ET closes. A half-day is a TRADING day with a shorter session; treating
#: one as a full day would report a 3-hour hole every Black Friday.
EARLY_CLOSES = frozenset({
    "2026-11-27", "2026-12-24",
    "2027-11-26",
})

STATE_UNREADABLE = "unreadable"
STATE_HOLES = "holes"
STATE_UNDETERMINED = "undetermined"
STATE_COMPLETE = "complete"

#: The heartbeat key whose budget doubles as this module's gap tolerance.
TOLERANCE_KEY = "nav_strike"
TOLERANCE_SOURCE = f"heartbeat.BUDGETS_SECONDS[{TOLERANCE_KEY!r}]"

#: Default lookback. Twenty-one days covers roughly three trading weeks, which is
#: long enough for a hole to still be visible on the surface a human next opens
#: and short enough that a months-old, already-answered hole does not sit on the
#: liveness payload forever.
DEFAULT_LOOKBACK_HOURS = 21 * 24.0


# --------------------------------------------------------------------------
# The calendar
# --------------------------------------------------------------------------

def calendar_covers(day: date) -> bool:
    """Does the sourced closure table have an opinion about this date?

    Outside the sourced range the honest answer is "I do not know whether that
    was a trading day", and every caller here propagates that rather than
    guessing. A calendar that silently extrapolates would turn an unknown day
    into a confident weekday and a hole into a finding nobody can trust.
    """
    return CALENDAR_FIRST_DAY <= day <= CALENDAR_LAST_DAY


def session_bounds(day: date) -> Optional[tuple[datetime, datetime]]:
    """The regular session for ``day`` in UTC, or None if the venue was shut.

    Raises nothing on an uncovered date — ask ``calendar_covers`` first; this
    returns None for "shut" and the caller cannot distinguish that from "outside
    the table" without asking. That split is deliberate: one function answers one
    question.
    """
    if day.weekday() >= 5:
        return None
    iso = day.isoformat()
    if iso in HOLIDAYS:
        return None
    closes = EARLY_SESSION_CLOSES if iso in EARLY_CLOSES else SESSION_CLOSES
    opens_local = datetime.combine(day, SESSION_OPENS, tzinfo=MARKET_TZ)
    closes_local = datetime.combine(day, closes, tzinfo=MARKET_TZ)
    return (opens_local.astimezone(timezone.utc),
            closes_local.astimezone(timezone.utc))


def trading_overlap(start: datetime, end: datetime) -> dict[str, Any]:
    """Regular-session seconds inside ``[start, end)``, and what could not be read.

    Returns ``seconds`` plus ``uncovered_days`` — the dates the sourced calendar
    has no opinion about. ``seconds`` counts only the days it COULD read, so a
    caller that ignores ``uncovered_days`` gets a LOWER bound, never a fabricated
    total. ``covered`` is the single boolean a caller should branch on.
    """
    if end <= start:
        return {"seconds": 0.0, "uncovered_days": [], "covered": True,
                "trading_days": []}
    seconds = 0.0
    uncovered: list[str] = []
    days: list[str] = []
    # Walk in MARKET-LOCAL dates: a UTC date boundary falls in the middle of a
    # US session, and iterating UTC days would split one session across two.
    day = start.astimezone(MARKET_TZ).date()
    last = end.astimezone(MARKET_TZ).date()
    while day <= last:
        if not calendar_covers(day):
            uncovered.append(day.isoformat())
            day += timedelta(days=1)
            continue
        bounds = session_bounds(day)
        if bounds is not None:
            lo = max(bounds[0], start)
            hi = min(bounds[1], end)
            if hi > lo:
                seconds += (hi - lo).total_seconds()
                days.append(day.isoformat())
        day += timedelta(days=1)
    return {"seconds": seconds, "uncovered_days": uncovered,
            "covered": not uncovered, "trading_days": days}


# --------------------------------------------------------------------------
# The tolerance
# --------------------------------------------------------------------------

def tolerance_seconds() -> Optional[float]:
    """The declared budget between strikes, READ from the heartbeat.

    Imported inside the function on purpose: a module-level read would freeze
    the value at import and make the test that MOVES it pass against a stale
    copy — which is precisely the hardcoded-duplicate failure this is meant to
    exclude. Returns None when the key is absent, and every caller then reports
    UNDETERMINED instead of substituting a number of its own.
    """
    try:
        from app.fund import heartbeat
        value = heartbeat.BUDGETS_SECONDS.get(TOLERANCE_KEY)
    except Exception:  # noqa: BLE001 - an unimportable heartbeat is "absent"
        return None
    if value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


# --------------------------------------------------------------------------
# The reader
# --------------------------------------------------------------------------

def _parse(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        out = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if out.tzinfo is None:
        # A naive stamp in a UTC-only log is UTC; assuming local time here would
        # move every gap by the host's offset.
        out = out.replace(tzinfo=timezone.utc)
    return out.astimezone(timezone.utc)


def _iso(value: Optional[datetime]) -> Optional[str]:
    return None if value is None else value.astimezone(timezone.utc).isoformat()


def _gap_row(frm: datetime, to: datetime, tol: Optional[float],
             label: str) -> dict[str, Any]:
    overlap = trading_overlap(frm, to)
    seconds = (to - frm).total_seconds()
    trading = overlap["seconds"]
    covered = overlap["covered"]
    if not covered:
        verdict = "undetermined"
    elif tol is None:
        verdict = "undetermined"
    elif trading > tol:
        verdict = "hole"
    else:
        verdict = "ok"
    return {
        "kind": label,
        "from": _iso(frm),
        "to": _iso(to),
        "hours": round(seconds / 3600.0, 4),
        "trading_seconds": round(trading, 1),
        "trading_hours": round(trading / 3600.0, 4),
        "trading_days": overlap["trading_days"],
        "calendar_covered": covered,
        "uncovered_days": overlap["uncovered_days"],
        "verdict": verdict,
    }


def completeness(strikes: Optional[Iterable[dict[str, Any]]],
                 *,
                 now: datetime,
                 lookback_hours: float = DEFAULT_LOOKBACK_HOURS,
                 ) -> dict[str, Any]:
    """The whole verdict, computed HERE, from ONE input, in ONE pass.

    ``strikes`` is the fund's full struck-NAV history (rows carrying ``ts``), or
    **None meaning it could not be read**. Unreadable is its own input value, not
    an empty list a caller patches fields onto afterwards: this fund has already
    shipped a payload that said "nothing has ever run, so there is no liveness
    question to answer" on the one path where the list could not be read, because
    the caller passed ``[]`` and then corrected two fields of five. Every field
    below is decided in this function so no caller can produce half a state.

    An EMPTY list is a different and honest thing: the fund has struck no NAV.
    That is not "complete" — if the window contains trading time, an empty
    history is one large hole, and it is reported as one.

    The window is ``[now - lookback_hours, now]``. Gaps are measured between
    consecutive strikes, plus the trailing edge (newest strike to ``now``, which
    is staleness), plus a LEADING gap from the last strike BEFORE the window if
    the caller supplied one — that anchor is why the full history is the input
    rather than a pre-filtered slice: a hole straddling the window's start is
    still a hole, and pre-filtering is how it would be lost.
    """
    window_end = now.astimezone(timezone.utc)
    window_start = window_end - timedelta(hours=float(lookback_hours))
    tol = tolerance_seconds()
    base: dict[str, Any] = {
        "version": NAVGAP_VERSION,
        "lookback_hours": round(float(lookback_hours), 4),
        "window_start": _iso(window_start),
        "window_end": _iso(window_end),
        "tolerance_seconds": tol,
        "tolerance_source": TOLERANCE_SOURCE if tol is not None else "absent",
        "calendar": {
            "source": CALENDAR_SOURCE,
            "sourced_on": CALENDAR_SOURCED_ON,
            "covers_from": CALENDAR_FIRST_DAY.isoformat(),
            "covers_to": CALENDAR_LAST_DAY.isoformat(),
        },
    }

    if strikes is None:
        return {
            **base,
            "state": STATE_UNREADABLE,
            "readable": False,
            "strikes_total": None,
            "strikes_in_window": None,
            "unparsed_strikes": None,
            "newest_strike_at": None,
            "staleness_seconds": None,
            "staleness_trading_seconds": None,
            "stale": None,
            "gaps": [],
            "holes": [],
            "hole_count": None,
            "largest_gap": None,
            "leading_anchor": None,
            "note": ("the struck-NAV history could not be read, so this fund "
                     "cannot say whether its NAV record has holes — which is "
                     "not the same as saying it has none"),
        }

    rows = list(strikes)
    parsed: list[datetime] = []
    unparsed = 0
    for row in rows:
        at = _parse((row or {}).get("ts"))
        if at is None:
            unparsed += 1
        else:
            parsed.append(at)
    parsed.sort()

    if unparsed:
        # A strike whose timestamp cannot be read is a strike this fold must
        # drop, and a dropped strike MANUFACTURES a gap that never happened.
        # Reporting the series as unreadable is the only verdict that does not
        # rest on a row we could not read.
        return {
            **base,
            "state": STATE_UNREADABLE,
            "readable": False,
            "strikes_total": len(rows),
            "strikes_in_window": None,
            "unparsed_strikes": unparsed,
            "newest_strike_at": None,
            "staleness_seconds": None,
            "staleness_trading_seconds": None,
            "stale": None,
            "gaps": [],
            "holes": [],
            "hole_count": None,
            "largest_gap": None,
            "leading_anchor": None,
            "note": (f"{unparsed} of {len(rows)} struck-NAV rows carry no "
                     f"readable timestamp; a dropped strike would invent a gap "
                     f"that never happened, so no completeness verdict is "
                     f"offered over this series"),
        }

    in_window = [t for t in parsed if t >= window_start]
    before = [t for t in parsed if t < window_start]
    anchor = before[-1] if before else None

    boundaries: list[datetime] = ([anchor] if anchor is not None else []) + in_window
    gaps: list[dict[str, Any]] = []
    for a, b in zip(boundaries, boundaries[1:]):
        gaps.append(_gap_row(a, b, tol, "between-strikes"))

    newest = parsed[-1] if parsed else None
    tail: Optional[dict[str, Any]] = None
    if newest is not None:
        # Computed ONCE and used for both the gap list and the staleness fields.
        # Two calls would be two chances for the two surfaces to disagree about
        # the same interval, which is the shape of defect this module exists to
        # find in the fund's own record.
        tail = _gap_row(newest, window_end, tol, "since-newest")
        gaps.append(tail)
    else:
        # No strike has ever been recorded. The window itself is the gap — the
        # honest generalisation, and the branch that stops an empty history from
        # reading as a clean bill of health.
        gaps.append(_gap_row(window_start, window_end, tol, "no-strikes-ever"))

    holes = [g for g in gaps if g["verdict"] == "hole"]
    undetermined = [g for g in gaps if g["verdict"] == "undetermined"]
    holes.sort(key=lambda g: g["trading_seconds"], reverse=True)
    largest = max(gaps, key=lambda g: g["hours"]) if gaps else None

    staleness = None
    staleness_trading = None
    stale: Optional[bool] = None
    if newest is not None and tail is not None:
        staleness = round((window_end - newest).total_seconds(), 1)
        staleness_trading = tail["trading_seconds"]
        stale = None if tail["verdict"] == "undetermined" else (
            tail["verdict"] == "hole")

    if holes:
        state = STATE_HOLES
    elif undetermined:
        state = STATE_UNDETERMINED
    else:
        state = STATE_COMPLETE

    return {
        **base,
        "state": state,
        "readable": True,
        "strikes_total": len(parsed),
        "strikes_in_window": len(in_window),
        "unparsed_strikes": 0,
        "newest_strike_at": _iso(newest),
        "staleness_seconds": staleness,
        "staleness_trading_seconds": staleness_trading,
        "stale": stale,
        "gaps": gaps,
        "holes": holes,
        "hole_count": len(holes),
        "largest_gap": largest,
        "leading_anchor": _iso(anchor),
        "note": _note(state, holes, undetermined, gaps, tol, newest,
                      staleness_trading, len(in_window)),
    }


#: How many holes a summary carries. A surface that lists every hole for a fund
#: with a bad month becomes unreadable; one that lists a few without saying how
#: many exist is worse. Both numbers ride the payload.
SUMMARY_HOLE_LIMIT = 10


#: Every key a summary carries. ONE list, so the blank form below and the real
#: form below that cannot drift apart — a payload whose shape depends on which
#: branch produced it makes every consumer guess.
SUMMARY_KEYS = (
    "version", "state", "readable", "note", "lookback_hours",
    "strikes_in_window", "gaps_measured", "hole_count", "holes_shown",
    "holes_capped", "holes", "largest_gap", "newest_strike_at",
    "staleness_seconds", "staleness_trading_seconds", "stale",
    "tolerance_seconds", "tolerance_source", "warnings",
)


def blank_summary(note: str) -> dict[str, Any]:
    """The full summary shape with nothing in it, for a reader that broke.

    Deliberately a literal with no computation and no calls: it exists for the
    case where ``completeness`` itself raised, and a recovery path that runs the
    code it is recovering from is not a recovery path. That is not a
    hypothetical — the first version of this diff's fallback did exactly that
    and recursed straight back into the failure.

    Every key is present and null rather than absent, because a consumer that
    must ask "does this payload have a hole_count field" has been handed two
    different contracts wearing one name.
    """
    out: dict[str, Any] = {k: None for k in SUMMARY_KEYS}
    out["state"] = STATE_UNREADABLE
    out["readable"] = False
    out["holes"] = []
    out["note"] = note
    out["warnings"] = [{"level": "warn", "key": "nav_record_unreadable",
                        "message": note}]
    return out


def summary(report: dict[str, Any]) -> dict[str, Any]:
    """The small block, DERIVED from a completeness report — never recomputed.

    Two surfaces show this (the NAV history payload and the liveness payload) and
    they must not be able to disagree, so neither of them folds anything: they
    both take the one report this module produced and read fields off it. The
    gap list is dropped here because it is long and the summary is for a human
    glance; the holes are not, because they are the finding.
    """
    holes = report.get("holes") or []
    shown = holes[:SUMMARY_HOLE_LIMIT]
    return {
        "version": report.get("version"),
        "state": report.get("state"),
        "readable": report.get("readable"),
        "note": report.get("note"),
        "lookback_hours": report.get("lookback_hours"),
        "strikes_in_window": report.get("strikes_in_window"),
        "gaps_measured": len(report.get("gaps") or []),
        "hole_count": report.get("hole_count"),
        "holes_shown": len(shown),
        "holes_capped": len(holes) > len(shown),
        "holes": shown,
        "largest_gap": report.get("largest_gap"),
        "newest_strike_at": report.get("newest_strike_at"),
        "staleness_seconds": report.get("staleness_seconds"),
        "staleness_trading_seconds": report.get("staleness_trading_seconds"),
        "stale": report.get("stale"),
        "tolerance_seconds": report.get("tolerance_seconds"),
        "tolerance_source": report.get("tolerance_source"),
        "warnings": warnings(report),
    }


def warnings(report: dict[str, Any]) -> list[dict[str, str]]:
    """What a liveness reader should be told, worst first.

    An EMPTY list is a measured zero — this looked at a readable report and found
    nothing to say. An unreadable report never produces an empty list: it
    produces a warning saying it could not look, because "no warnings" and "no
    information" must not render the same.
    """
    out: list[dict[str, str]] = []
    state = report.get("state")
    if state == STATE_UNREADABLE:
        return [{"level": "warn", "key": "nav_record_unreadable",
                 "message": str(report.get("note"))}]
    if report.get("stale") is True:
        out.append({
            "level": "warn", "key": "nav_strike_stale",
            "message": (
                f"the newest struck NAV is {report.get('newest_strike_at')}, "
                f"and {float(report.get('staleness_trading_seconds') or 0.0) / 3600.0:.2f}h "
                f"of TRADING time has passed since — past the "
                f"{report.get('tolerance_seconds')}s budget. The strike loop "
                f"beating is not evidence that a strike happened"),
        })
    elif report.get("stale") is None:
        out.append({
            "level": "warn", "key": "nav_strike_staleness_unknown",
            "message": ("how stale the newest struck NAV is could not be "
                        "determined; unknown is not fresh"),
        })
    if report.get("hole_count"):
        out.append({
            "level": "warn", "key": "nav_record_holes",
            "message": str(report.get("note")),
        })
    if state == STATE_UNDETERMINED:
        out.append({
            "level": "warn", "key": "nav_record_undetermined",
            "message": str(report.get("note")),
        })
    return out


def _plural(n: int, one: str, many: str) -> str:
    return one if n == 1 else many


def _note(state: str, holes: list, undetermined: list, gaps: list,
          tol: Optional[float], newest: Optional[datetime],
          staleness_trading: Optional[float], in_window: int) -> str:
    if state == STATE_HOLES:
        worst = holes[0]
        days = ", ".join(worst["trading_days"]) or "no whole session"
        return (f"{len(holes)} {_plural(len(holes), 'hole', 'holes')} in the "
                f"struck-NAV record: the worst runs {worst['from']} to "
                f"{worst['to']} and swallows {worst['trading_hours']:.2f}h of "
                f"trading time ({days}). Those hours are not in the record and "
                f"nothing in the log explains them")
    if state == STATE_UNDETERMINED:
        if tol is None:
            return (f"{len(gaps)} {_plural(len(gaps), 'gap', 'gaps')} measured, "
                    f"but {TOLERANCE_SOURCE} is absent, so nothing here can say "
                    f"which of them is too long")
        return (f"{len(undetermined)} "
                f"{_plural(len(undetermined), 'gap falls', 'gaps fall')} outside "
                f"the sourced market calendar ({CALENDAR_FIRST_DAY} to "
                f"{CALENDAR_LAST_DAY}), so whether they ate a trading session is "
                f"unknown, not clear")
    if newest is None:
        return ("no NAV has ever been struck, and the window contains no "
                "trading time to have missed")
    tail = f"{staleness_trading / 3600.0:.2f}h" if staleness_trading is not None else "?"
    return (f"{in_window} strike(s) in the window with no gap exceeding the "
            f"{tol:.0f}s budget; {tail} of trading time has passed since the "
            f"newest strike")
