"""The venue's session, derived without a network and without waiting for 09:30.

The phase matters because it explains silence. "No signals proposed" reads as a
malfunction until something says it is 3am on a Saturday.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.fund.session import (
    MARKET_TZ,
    PHASE_AFTERHOURS,
    PHASE_CLOSED,
    PHASE_PREMARKET,
    PHASE_REGULAR,
    PHASE_WEEKEND,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNKNOWN,
    derive,
    unknown,
)


def et(y, m, d, hh, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=MARKET_TZ)


# 2026-08-14 is a Friday; 2026-08-15 a Saturday; 2026-08-17 a Monday.
FRI_OPEN = et(2026, 8, 14, 9, 30)
FRI_CLOSE = et(2026, 8, 14, 16, 0)
MON_OPEN = et(2026, 8, 17, 9, 30)
MON_CLOSE = et(2026, 8, 17, 16, 0)


# ------------------------------------------------------------------- unknown
def test_an_unreachable_clock_is_unknown_not_closed():
    s = derive(is_open=None, now=et(2026, 8, 14, 3, 44))
    assert s.state == STATE_UNKNOWN
    assert s.is_open is None                      # never collapses to False


def test_unknown_carries_a_reason():
    s = unknown("venue clock unreachable: timeout")
    assert "timeout" in s.note and s.is_open is None


# ---------------------------------------------------------------------- open
def test_an_open_market_counts_down_to_the_close():
    now = et(2026, 8, 14, 14, 0)
    s = derive(is_open=True, now=now, next_open=MON_OPEN, next_close=FRI_CLOSE)
    assert s.state == STATE_OPEN and s.phase == PHASE_REGULAR
    assert s.is_open is True
    assert s.seconds_to_close == 2 * 3600
    assert s.seconds_to_open is None              # already open


def test_an_open_market_says_orders_execute_now():
    s = derive(is_open=True, now=et(2026, 8, 14, 14, 0), next_close=FRI_CLOSE)
    assert "execute now" in s.note


# ------------------------------------------------------------------- closed
def test_the_small_hours_are_closed_not_pre_market():
    """03:44, the hour this fund's scheduler used to strike NAV in."""
    now = et(2026, 8, 14, 3, 44)
    s = derive(is_open=False, now=now, next_open=FRI_OPEN, next_close=FRI_CLOSE)
    assert s.phase == PHASE_CLOSED
    assert s.seconds_to_open == int((FRI_OPEN - now).total_seconds())


def test_the_morning_before_the_open_is_pre_market():
    s = derive(is_open=False, now=et(2026, 8, 14, 7, 0),
               next_open=FRI_OPEN, next_close=FRI_CLOSE)
    assert s.phase == PHASE_PREMARKET


def test_pre_market_says_this_fund_does_not_trade_in_it():
    """The phase is informational: we submit day orders with no extended flag."""
    s = derive(is_open=False, now=et(2026, 8, 14, 7, 0),
               next_open=FRI_OPEN, next_close=FRI_CLOSE)
    assert "nothing executes until the open" in s.note


def test_the_evening_after_the_close_is_after_hours():
    s = derive(is_open=False, now=et(2026, 8, 14, 17, 0),
               next_open=MON_OPEN, next_close=MON_CLOSE)
    assert s.phase == PHASE_AFTERHOURS


def test_late_evening_is_closed_again():
    s = derive(is_open=False, now=et(2026, 8, 14, 21, 0),
               next_open=MON_OPEN, next_close=MON_CLOSE)
    assert s.phase == PHASE_CLOSED


def test_a_weekend_is_named_as_one():
    s = derive(is_open=False, now=et(2026, 8, 15, 11, 0),
               next_open=MON_OPEN, next_close=MON_CLOSE)
    assert s.phase == PHASE_WEEKEND
    assert "venue is shut" in s.note


def test_a_holiday_morning_is_not_reported_as_after_hours():
    """A weekday with no session looks exactly like an evening from next_open
    alone — both say "tomorrow". Only the wall clock separates them, and
    calling a holiday 10am "after-hours" would be plainly wrong."""
    holiday_10am = et(2026, 8, 14, 10, 0)
    s = derive(is_open=False, now=holiday_10am,
               next_open=MON_OPEN, next_close=MON_CLOSE)
    assert s.phase == PHASE_CLOSED


def test_the_countdown_to_a_monday_open_spans_the_weekend():
    now = et(2026, 8, 15, 11, 0)
    s = derive(is_open=False, now=now, next_open=MON_OPEN, next_close=MON_CLOSE)
    assert s.seconds_to_open == int((MON_OPEN - now).total_seconds())
    # Saturday 11:00 -> Monday 09:30 is 46.5 hours: past midnight twice, but
    # short of two full days. The countdown must not wrap or truncate to a day.
    assert s.seconds_to_open == int(46.5 * 3600)


# ------------------------------------------------------- degraded inputs
def test_an_open_answer_with_no_timestamp_still_gates_trading():
    """The one bit that decides whether to act survives a missing clock."""
    s = derive(is_open=True, now=None)
    assert s.is_open is True and s.phase == PHASE_REGULAR
    assert s.seconds_to_close is None


def test_a_closed_answer_with_no_timestamp_is_closed_without_a_phase_guess():
    s = derive(is_open=False, now=None)
    assert s.state == STATE_CLOSED and s.phase == PHASE_CLOSED


def test_a_naive_timestamp_is_refused_rather_than_assumed_to_be_market_time():
    s = derive(is_open=False, now=datetime(2026, 8, 14, 3, 44))
    assert s.now is None


def test_a_missing_next_open_leaves_the_countdown_unknown():
    s = derive(is_open=False, now=et(2026, 8, 14, 3, 44), next_open=None)
    assert s.seconds_to_open is None
    assert s.state == STATE_CLOSED


# ------------------------------------------------------------- timezone
def test_a_utc_input_is_converted_to_market_time():
    """Alpaca returns tz-aware UTC; everything downstream reads market time."""
    from datetime import timezone

    utc_now = datetime(2026, 8, 14, 18, 0, tzinfo=timezone.utc)   # 14:00 ET
    s = derive(is_open=True, now=utc_now, next_close=FRI_CLOSE)
    assert s.now is not None and s.now.startswith("2026-08-14T14:00")
    assert s.timezone == "America/New_York"


def test_the_dict_is_complete_enough_to_render():
    s = derive(is_open=False, now=et(2026, 8, 14, 3, 44),
               next_open=FRI_OPEN, next_close=FRI_CLOSE)
    d = s.to_dict()
    for k in ("state", "phase", "note", "is_open", "now",
              "next_open", "seconds_to_open", "timezone"):
        assert k in d


def test_seconds_to_open_shrinks_as_the_open_approaches():
    a = derive(is_open=False, now=FRI_OPEN - timedelta(hours=6), next_open=FRI_OPEN)
    b = derive(is_open=False, now=FRI_OPEN - timedelta(hours=1), next_open=FRI_OPEN)
    assert a.seconds_to_open > b.seconds_to_open > 0
