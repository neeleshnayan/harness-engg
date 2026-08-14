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
