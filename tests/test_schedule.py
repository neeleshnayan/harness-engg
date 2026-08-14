"""A struck NAV is permanent. These decide when the worker is allowed to write one.

The failure this guards against is quiet: a 3am strike produces a plausible
number, folded from real events, at a price that was real seven hours earlier.
Nothing about it looks wrong afterwards, and nothing removes it.
"""

from __future__ import annotations

from app.fund.schedule import StrikeWindow


def test_an_open_market_strikes():
    w = StrikeWindow()
    d = w.evaluate(True)
    assert d.strike is True and d.reason == "market open"


def test_a_closed_market_that_was_never_open_does_not_strike():
    """Boot on a Sunday: there is no close to mark."""
    w = StrikeWindow()
    assert w.evaluate(False).strike is False


def test_the_close_is_marked_exactly_once():
    w = StrikeWindow()
    w.evaluate(True)
    first = w.evaluate(False)
    second = w.evaluate(False)
    third = w.evaluate(False)
    assert first.strike is True and first.reason == "closing mark"
    assert second.strike is False and third.strike is False


def test_a_full_session_strikes_through_and_marks_the_close():
    w = StrikeWindow()
    ticks = [False, False, True, True, True, False, False, False]
    got = [w.evaluate(t) for t in ticks]
    assert [g.strike for g in got] == [False, False, True, True, True, True, False, False]
    assert got[5].reason == "closing mark"


def test_the_next_session_marks_its_own_close():
    """The window must re-arm, or only the first day of the fund's life gets a
    closing NAV."""
    w = StrikeWindow()
    for t in (True, False):
        w.evaluate(t)
    w.evaluate(True)
    assert w.evaluate(False).reason == "closing mark"


# ------------------------------------------------------- the unknown clock
def test_an_unreachable_clock_does_not_strike():
    w = StrikeWindow()
    assert w.evaluate(None).strike is False


def test_an_unreachable_clock_is_not_read_as_a_close():
    """A blip mid-session must not fabricate a closing mark."""
    w = StrikeWindow()
    w.evaluate(True)
    assert w.evaluate(None).strike is False
    assert w.last_known_open is True


def test_a_blip_across_the_close_still_marks_it_afterwards():
    """Unknown must not clear the memory of having been open, or the day's
    official NAV is lost because the clock happened to be down at 16:00."""
    w = StrikeWindow()
    w.evaluate(True)
    w.evaluate(None)
    w.evaluate(None)
    assert w.evaluate(False).reason == "closing mark"


def test_a_blip_before_ever_opening_does_not_arm_the_close():
    w = StrikeWindow()
    w.evaluate(None)
    assert w.evaluate(False).strike is False


def test_the_session_resumes_normally_after_a_blip():
    w = StrikeWindow()
    w.evaluate(True)
    w.evaluate(None)
    assert w.evaluate(True).strike is True
