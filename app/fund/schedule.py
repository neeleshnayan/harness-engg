"""When the deterministic worker is allowed to write to the permanent record.

The scheduler used to strike NAV on a wall-clock interval, which meant it
struck at 3am — against marks last updated at the previous close, on a book
that could not have moved. A struck NAV is not telemetry: it is the official
record of what a unit was worth at a moment, it persists to the event log, and
it is the basis on which units are issued and redeemed. Writing a fabricated
overnight mark into that record is not a display bug that a later refresh
fixes; nothing removes it.

So striking follows the venue's session rather than a timer:

    open            -> strike (the marks are live and mean something)
    open -> closed  -> strike once (the closing mark, the official daily NAV)
    closed          -> silence
    unknown         -> silence, but remember what we last knew

The unknown case is the subtle one. ``market_open()`` returns None when the
clock cannot be read, and the codebase's standing rule is that unknown must
never silently become closed. Here that means an unreadable clock does not
trigger the closing mark and does not clear the memory of having been open —
so a blip during the session does not fabricate a close, and a blip *across*
the close still produces the closing mark on the next readable tick.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class StrikeDecision:
    strike: bool
    reason: str


class StrikeWindow:
    """Tracks the session transition so the closing mark is struck exactly once.

    Stateful by necessity — "the market just closed" is not observable from a
    single reading. Held in memory rather than the log because a missed closing
    mark after a restart is a gap in a series, while a duplicated one is a
    second official NAV for the same moment, and the first is the cheaper
    failure.
    """

    def __init__(self) -> None:
        #: The last *known* state. None only before the first readable tick.
        self._was_open: bool | None = None

    @property
    def last_known_open(self) -> bool | None:
        return self._was_open

    def evaluate(self, market_open: bool | None) -> StrikeDecision:
        if market_open is None:
            # Deliberately does not touch _was_open: an unreachable clock is
            # not evidence of a close, and forgetting we were open would lose
            # the closing mark entirely.
            return StrikeDecision(False, "venue clock unreachable — not striking")

        if market_open:
            self._was_open = True
            return StrikeDecision(True, "market open")

        if self._was_open:
            self._was_open = False
            return StrikeDecision(True, "closing mark")

        self._was_open = False
        return StrikeDecision(False, "market closed")


# ---------------------------------------------------------------- the clock
#
# A PERIODIC TICK MUST COUNT TIME, NOT TICKS. The worker's accumulators used to
# advance by the NOMINAL sleep constant — ``since_strike += settle_every`` --
# which is only the truth if the loop body costs nothing. It does not: one pass
# settles fills, re-screens the universe, snapshots, runs the risk monitor, the
# exit check, the autopolicy, the factory and proposal reconciles, prunes
# results and, every fifth minute, shells out to ``docker ps``. Every one of
# those seconds is real and none of them was counted, so the accumulator
# under-reported elapsed time by exactly the loop's own cost and the strike
# interval stretched by the same fraction.
#
# MEASURED, from the fund's own NavStruck series (n=76 strikes, 2026-08-13 to
# 2026-08-26, per-day median of the single-interval gaps against a configured
# 3600s):
#
#     2026-08-13  3656s  1.016x        2026-08-20  3841s  1.067x
#     2026-08-14  3859s  1.072x        2026-08-21  3834s  1.065x
#     2026-08-15  3619s  1.005x        2026-08-24  4110s  1.142x
#     2026-08-17  3698s  1.027x        2026-08-26  4321s  1.200x
#     2026-08-18  3823s  1.062x
#     2026-08-19  3817s  1.060x
#
# The stretch GROWS, because the loop keeps gaining work: 1.6% on the fund's
# FIRST day of struck NAVs, 20.0% thirteen days later. That last figure is
# 4321s against the heartbeat's 5400s nav_strike budget, so 1.25x more loop
# growth fires that alarm — and note WHAT it watches: the beat fires on a
# deliberate no-strike too, so the budget bounds the strike CHECK's cadence,
# which is exactly the quantity this defect stretched. The fix is here rather
# than in the budget for that reason.

#: THE INPUT VALUE for "the strike record could not be read". It exists so the
#: caller has something to pass that is not ``None`` — because ``None`` already
#: means "the log is readable and holds no strike", and a fund that has never
#: struck a NAV and a log that cannot be read are different facts with different
#: fixes. Collapsing them is the failure this codebase keeps paying for.
UNREADABLE = "unreadable"

#: ``ResumedClock.basis`` — what code branches on, one value per cause.
NEVER_STRUCK = "never-struck"
FUTURE = "future"
OVERDUE = "overdue"
RESUMED = "resumed"


@dataclass
class ResumedClock:
    """How much of the strike interval a freshly-started worker has served."""

    seconds_served: float
    #: One of ``resumed`` / ``overdue`` / ``never-struck`` / ``unreadable`` /
    #: ``future``. The BASIS is what code should branch on.
    basis: str
    #: The sentence an operator reads. Two causes must never share one, because
    #: the log is where a cause is diagnosed and a shared sentence is an
    #: absence collapse with a timestamp on it.
    note: str


def advance(seconds_served: float, elapsed: float,
            interval: float) -> tuple[float, bool]:
    """Advance a periodic accumulator by MEASURED elapsed seconds.

    Returns ``(seconds_served, due)``. When it is due the accumulator resets to
    zero rather than carrying the overshoot forward: carrying it would let a
    single long stall (a suspended laptop, a 40-minute universe refresh) fire
    several periods back to back, and for the strike tick that means several
    official NAVs for one moment. The cost of resetting is that the effective
    period is the interval plus at most ONE tick of overshoot, which is the
    tolerance the tests assert against.

    A non-positive interval is NOT a period and is never due — that is what
    disables a tick (``LEAN_RECONCILE_INTERVAL=0`` is a supported setting).
    A negative ``elapsed`` cannot come from a monotonic clock, and is treated as
    zero rather than winding the accumulator backwards, because the one thing a
    periodic control must never do is become less due than it already was.

    BOTH GUARDS ARE WRITTEN ``not (x > 0)`` RATHER THAN ``x <= 0`` / ``x < 0``,
    and the reason is NaN. Every comparison against NaN is False, so ``x <= 0``
    lets a NaN interval through and ``x < 0`` lets a NaN elapsed through — and a
    NaN that reaches the accumulator makes ``seconds_served`` NaN forever, after
    which ``>= interval`` is False on every future tick. That is a periodic
    control that has silently died, permanently, with nothing in the log: the
    exact shape this codebase calls an unwired kill switch. ``not (x > 0)``
    catches negative, zero and NaN in one condition, so the safe reading is the
    DEFAULT rather than a special case somebody has to remember to add.

    ``seconds_served`` is not separately guarded and does not need to be: it is
    only ever this function's own output plus a guarded ``elapsed``, and both
    are finite by construction.
    """
    if not (interval > 0):
        return seconds_served, False
    if not (elapsed > 0):
        elapsed = 0.0
    seconds_served = seconds_served + elapsed
    if seconds_served >= interval:
        return 0.0, True
    return seconds_served, False


def resume_strike_clock(latest: Any, interval: float,
                        now: datetime) -> ResumedClock:
    """Where a fresh worker's strike clock should start, from the durable record.

    A worker used to start its strike clock at zero, so every spine restart and
    every lease handoff bought the fund a full interval of silence however long
    it had already been since the last strike. That is a measured cause and not
    a theoretical one: of the ten over-budget in-session gaps in the fund's
    NavStruck series (2026-08-13..26), five sit in windows where the spine was
    demonstrably up — it appended dozens of other events — and where the strike
    PHASE moved, which is the signature of an accumulator reset or frozen
    rather than of a tick that ran and wrote nothing.

    The record already holds the answer, so this needs no new store, and it is
    self-limiting: once a strike is written the newest event is seconds old, so
    a restart loop resumes at ~0 and waits rather than manufacturing strikes.

    ONE INPUT, ONE FUNCTION, and ``UNREADABLE`` IS ITS OWN INPUT VALUE. The
    caller hands over exactly what it got from the store — a payload, ``None``
    for a log with no strike in it, or ``UNREADABLE`` for a read that failed —
    and every field of the answer is computed here. The alternative shape, a
    caller that passes an empty value and then corrects two of the three fields
    afterwards, is how a payload comes to say "nothing has ever run" on the one
    path where the answer was unknown; the field nobody looks at is the field
    nobody patches.

    ``basis`` is what code branches on. ``note`` is what an operator reads, and
    no two causes share one: the log is where a cause is diagnosed, and two
    different faults printing one sentence is an absence collapse with a
    timestamp on it.
    """
    if latest is UNREADABLE or latest == UNREADABLE:
        return ResumedClock(
            0.0, UNREADABLE,
            "the last struck NAV could NOT BE READ, so the strike clock "
            "restarts from zero — the first strike may be a full interval "
            "late, and that is a fault, not a young fund")
    if latest is None:
        return ResumedClock(
            0.0, NEVER_STRUCK,
            "no NAV has ever been struck, so there is no clock to resume — "
            "the first strike lands one interval from now")
    if not isinstance(latest, dict):
        return ResumedClock(
            0.0, UNREADABLE,
            f"the newest strike came back as a {type(latest).__name__} rather "
            f"than a payload, so the strike clock restarts from zero")
    raw = latest.get("ts")
    if raw is None:
        # A readable log holding an unreadable answer. NOT "never struck":
        # something was written and cannot be dated, which is a different
        # problem with a different fix.
        return ResumedClock(
            0.0, UNREADABLE,
            "the newest strike carries no timestamp, so the strike clock "
            "restarts from zero")
    try:
        struck = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return ResumedClock(
            0.0, UNREADABLE,
            f"the newest strike is dated {raw!r}, which is not a timestamp, "
            f"so the strike clock restarts from zero")
    if struck.tzinfo is None:
        # The fund writes offset-aware timestamps. One without an offset is
        # assumed UTC rather than refused, because the alternative is throwing
        # away a reading that is almost certainly right; the assumption is
        # named here so nobody has to guess it later.
        struck = struck.replace(tzinfo=timezone.utc)
    age = (now - struck).total_seconds()
    if age < 0:
        return ResumedClock(
            0.0, FUTURE,
            f"the newest strike is dated {-age:.0f}s in the FUTURE — this "
            f"clock disagrees with the one that wrote the record, so the "
            f"strike clock restarts from zero")
    if age >= interval:
        return ResumedClock(
            age, OVERDUE,
            f"the last NAV was struck {age:.0f}s ago against a {interval:.0f}s "
            f"interval — OVERDUE, so the next tick strikes")
    return ResumedClock(
        age, RESUMED,
        f"resuming the strike clock {age:.0f}s into its {interval:.0f}s "
        f"interval, from the last struck NAV")
