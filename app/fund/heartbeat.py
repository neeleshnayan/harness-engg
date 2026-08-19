"""Which periodic jobs have actually run, so a dead one reads as dead.

The fund had a recurring bug with one shape. A control gets built, tested, and
documented; nothing calls it; and the documentation then describes a mechanism
that does not operate. It happened to the snapshot — `main.py` still carries the
line about a backup existing "in the same sense that an unplugged smoke alarm is
a smoke alarm" — and it happened again, undetected, to the two that matter most:

  * `RiskMonitor.run()` — the ONLY code that raises alarms and trips the
    drawdown and daily-loss kill switches — had zero callers. The framework
    document said "kill switches that will act without asking". They would not
    have acted, because nothing asked them to.
  * `ExitRules.check()` — the pre-committed exit evaluation — was reachable only
    from an endpoint nothing called. `EXIT_RULE_TRIGGERED` was emitted by no code
    at all.

Both were found by an outside review, not by the system. That is the failure this
module addresses: **the harness could not tell the difference between a control
that reported nothing and a control that never ran.** Silence read as good news.

So every periodic job beats here, and staleness is a first-class, queryable fact.
Deliberately in memory rather than in the event log: a heartbeat every 30 seconds
would add ~2,900 events a day to an append-only chain whose value is that a human
can read it. The trade-off is stated rather than hidden — after a restart nothing
has beaten yet, and this module reports exactly that ("never observed by this
process"), which is true, rather than inventing a last-seen time it cannot know.

Durable evidence of liveness already exists where it should: alarms append events
when they fire, and NAV_STRUCK lands every 30 minutes during a session.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

#: Named jobs and how stale each may get before it is a finding. Values are
#: generous multiples of the intended interval — the purpose is to catch a job
#: that STOPPED, not to alarm on a slow tick.
BUDGETS_SECONDS: dict[str, float] = {
    "settlement": 300.0,
    "risk_monitor": 300.0,
    "exit_check": 300.0,
    "auto_policy": 300.0,
    "snapshot": 7200.0,
    "nav_strike": 5400.0,
}

_lock = threading.Lock()
#: name -> (monotonic_at, wall_iso, note)
_beats: dict[str, tuple[float, str, Optional[str]]] = {}


def beat(name: str, note: Optional[str] = None) -> None:
    """Record that ``name`` just completed a tick."""
    from datetime import datetime, timezone
    with _lock:
        _beats[name] = (time.monotonic(),
                        datetime.now(timezone.utc).isoformat(), note)


def _age(name: str) -> Optional[float]:
    """Raw seconds since the last beat. Unrounded on purpose.

    `status()` compares THIS against the budget, not the rounded value it
    displays. Comparing the display value meant a job could sit fractionally past
    its budget and still report healthy, because the age had been rounded back
    under the line — the same class of off-by-one that let 1-of-2 folds pass for a
    majority. Display rounds; decisions do not.
    """
    with _lock:
        hit = _beats.get(name)
    return None if hit is None else (time.monotonic() - hit[0])


def last(name: str) -> Optional[dict[str, Any]]:
    with _lock:
        hit = _beats.get(name)
    if hit is None:
        return None
    mono, iso, note = hit
    return {"at": iso, "age_seconds": round(time.monotonic() - mono, 1),
            "note": note}


def status(name: str) -> dict[str, Any]:
    """Is this job alive? ``ok: None`` means unknown, which is not ``ok: True``.

    A job that has never beaten since this process started is reported as
    unobserved rather than as failing OR as fine. Both of the other answers would
    be assertions the process cannot support: it does not know whether another
    holder of the scheduler lease is doing the work.
    """
    budget = BUDGETS_SECONDS.get(name)
    hit = last(name)
    if hit is None:
        return {"job": name, "ok": None, "budget_seconds": budget,
                "note": f"{name} has never run in this process. That is not the "
                        f"same as broken — another process may hold the scheduler "
                        f"lease — and it is not the same as fine either"}
    if budget is None:
        return {"job": name, "ok": None, **hit,
                "note": f"{name} beat, but no staleness budget is declared for "
                        f"it, so nothing can say whether that was recent enough"}
    stale = (_age(name) or 0.0) > budget
    return {"job": name, "ok": not stale, "budget_seconds": budget, **hit,
            "note": (f"{name} last ran {hit['age_seconds']:.0f}s ago, past its "
                     f"{budget:.0f}s budget — treat anything it is responsible "
                     f"for as UNCHECKED, not as clear"
                     if stale else
                     f"{name} ran {hit['age_seconds']:.0f}s ago")}


def report() -> dict[str, Any]:
    """Every declared job, worst news first."""
    rows = [status(n) for n in BUDGETS_SECONDS]
    stale = [r for r in rows if r["ok"] is False]
    unobserved = [r for r in rows if r["ok"] is None]
    return {
        "jobs": rows,
        "stale": [r["job"] for r in stale],
        "unobserved": [r["job"] for r in unobserved],
        "note": _note(rows, stale, unobserved),
    }


def _note(rows: list, stale: list, unobserved: list) -> str:
    if stale:
        return (f"{len(stale)} scheduled job(s) are OVERDUE "
                f"({', '.join(r['job'] for r in stale)}) — whatever they enforce "
                f"is currently unenforced, and the absence of an alarm from them "
                f"is not evidence of calm")
    if unobserved:
        return (f"{len(unobserved)} job(s) not yet observed in this process "
                f"({', '.join(r['job'] for r in unobserved)}) — unknown, which is "
                f"neither broken nor fine")
    return f"all {len(rows)} scheduled job(s) beat within budget"


def reset() -> None:
    """Test helper. Never called in the app."""
    with _lock:
        _beats.clear()
