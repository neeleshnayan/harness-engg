"""The venue's session, as a thing the fund can reason about.

``market_open()`` answers one bit, and a bit is enough to decide whether to act
but not enough to explain anything. "No signals were proposed" reads as a
malfunction when the real answer is "it is 3am on a Friday and the next open is
in six hours". The scheduler, the signal runner and the operator all need the
same richer answer, and they should get it from one place rather than each
re-deriving it from a boolean.

Everything here is pure. ``derive()`` takes the four fields Alpaca's clock
returns and computes the rest, so the session logic is testable without a
network and without waiting for 09:30 to come around.

A deliberate limit on what this claims: the venue clock reports the *regular*
session only. Extended-hours boundaries below are the standard US equity
pre/post windows, and the phase they produce is informational — this fund
submits day orders without the extended-hours flag, so nothing executes outside
the regular session regardless of what the phase says. The phase exists to
explain the silence, not to license trading into it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from typing import Any, Optional
from zoneinfo import ZoneInfo

MARKET_TZ = ZoneInfo("America/New_York")

#: Standard US equity extended-hours window, in market time.
PREMARKET_OPENS = time(4, 0)
REGULAR_CLOSES = time(16, 0)
AFTERHOURS_CLOSES = time(20, 0)

STATE_OPEN = "open"
STATE_CLOSED = "closed"
STATE_UNKNOWN = "unknown"

PHASE_REGULAR = "regular"
PHASE_PREMARKET = "pre-market"
PHASE_AFTERHOURS = "after-hours"
PHASE_CLOSED = "closed"
PHASE_WEEKEND = "weekend"
PHASE_UNKNOWN = "unknown"

#: What each phase means for this fund specifically, rather than in general.
PHASE_NOTE = {
    PHASE_REGULAR: "orders execute now",
    PHASE_PREMARKET: "pre-market — this fund submits day orders, so nothing executes until the open",
    PHASE_AFTERHOURS: "after-hours — the regular session is over; orders queue for the next open",
    PHASE_CLOSED: "closed",
    PHASE_WEEKEND: "weekend — the venue is shut",
    PHASE_UNKNOWN: "the venue clock is unreachable, which is not the same as closed",
}


@dataclass
class MarketSession:
    state: str
    phase: str
    note: str
    #: All ISO-8601 in market time, so a reader never has to guess the zone.
    now: Optional[str] = None
    next_open: Optional[str] = None
    next_close: Optional[str] = None
    seconds_to_open: Optional[int] = None
    seconds_to_close: Optional[int] = None
    timezone: str = "America/New_York"

    @property
    def is_open(self) -> Optional[bool]:
        """Tri-state, matching the connector: None when genuinely unknown.

        Never collapses unknown to closed. A caller that stops trading on an
        unreachable clock halts during an API blip; one that treats it as open
        sends orders into the dark. Both are the caller's decision to make.
        """
        if self.state == STATE_UNKNOWN:
            return None
        return self.state == STATE_OPEN

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "phase": self.phase,
            "note": self.note,
            "is_open": self.is_open,
            "now": self.now,
            "next_open": self.next_open,
            "next_close": self.next_close,
            "seconds_to_open": self.seconds_to_open,
            "seconds_to_close": self.seconds_to_close,
            "timezone": self.timezone,
        }


def unknown(reason: str | None = None) -> MarketSession:
    return MarketSession(
        state=STATE_UNKNOWN,
        phase=PHASE_UNKNOWN,
        note=reason or PHASE_NOTE[PHASE_UNKNOWN],
    )


def _market(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(MARKET_TZ)


def _delta(frm: datetime | None, to: datetime | None) -> int | None:
    if frm is None or to is None:
        return None
    return int((to - frm).total_seconds())


def derive(
    is_open: bool | None,
    now: datetime | None,
    next_open: datetime | None = None,
    next_close: datetime | None = None,
) -> MarketSession:
    """Build a session from what the venue clock reports.

    ``is_open`` is authoritative for the regular session — it is the venue's own
    answer and already accounts for holidays and early closes, which is why no
    holiday calendar is carried here. The phase adds only what can be derived
    without inventing a calendar of our own.
    """
    if is_open is None:
        return unknown()

    n = _market(now)
    no = _market(next_open)
    nc = _market(next_close)

    if n is None:
        # An open/closed answer with no usable timestamp still tells us the one
        # thing that gates trading, so it is not thrown away — but nothing that
        # depends on the clock can be computed.
        state = STATE_OPEN if is_open else STATE_CLOSED
        phase = PHASE_REGULAR if is_open else PHASE_CLOSED
        return MarketSession(state=state, phase=phase, note=PHASE_NOTE[phase])

    if is_open:
        return MarketSession(
            state=STATE_OPEN,
            phase=PHASE_REGULAR,
            note=PHASE_NOTE[PHASE_REGULAR],
            now=n.isoformat(),
            next_open=no.isoformat() if no else None,
            next_close=nc.isoformat() if nc else None,
            seconds_to_open=None,          # already open; the question is the close
            seconds_to_close=_delta(n, nc),
        )

    phase = _closed_phase(n, no)
    return MarketSession(
        state=STATE_CLOSED,
        phase=phase,
        note=PHASE_NOTE[phase],
        now=n.isoformat(),
        next_open=no.isoformat() if no else None,
        next_close=nc.isoformat() if nc else None,
        seconds_to_open=_delta(n, no),
        seconds_to_close=None,
    )


def _closed_phase(now: datetime, next_open: datetime | None) -> str:
    """Why it is closed — as far as that is derivable without a calendar."""
    if now.weekday() >= 5:                       # Sat/Sun in market time
        return PHASE_WEEKEND

    # The venue's own next_open is the only reliable signal for whether today
    # still has a session coming. Inferring it from the wall clock alone would
    # call a holiday "pre-market" every morning.
    if next_open is not None and next_open.date() == now.date():
        return PHASE_PREMARKET if now.time() >= PREMARKET_OPENS else PHASE_CLOSED

    # Today's session is done, or there was never one. Both look identical from
    # next_open alone — on a holiday and on a normal evening the next open is
    # equally "tomorrow" — so the wall clock breaks the tie: after-hours only
    # exists after the regular close has actually passed. Without this, every
    # holiday morning would report as after-hours.
    #
    # Known imprecision: on an early-close day the 13:00-16:00 stretch reports
    # "closed" rather than "after-hours". Recognising it would mean carrying an
    # early-close calendar, and "closed" is true either way — the fund is not
    # trading in it. Under-claiming beats a calendar that silently goes stale.
    if REGULAR_CLOSES <= now.time() < AFTERHOURS_CLOSES:
        return PHASE_AFTERHOURS
    return PHASE_CLOSED
