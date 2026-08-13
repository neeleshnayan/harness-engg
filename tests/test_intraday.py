"""Intraday NAV samples are telemetry, not the record — these tests pin that."""

import pytest

from app.fund.intraday import IntradayNav


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_throttles_rapid_samples():
    """Sampling faster than marks refresh records the same price repeatedly and
    makes a chart look busier than reality."""
    clk = FakeClock()
    n = IntradayNav(min_interval=60.0, clock=clk)
    assert n.sample(2000.0, 1.0) is True
    assert n.sample(2001.0, 1.0005) is False      # 0s later
    clk.t = 61.0
    assert n.sample(2002.0, 1.001) is True
    assert len(n) == 2


def test_force_bypasses_the_throttle():
    n = IntradayNav(min_interval=60.0, clock=FakeClock())
    n.sample(2000.0, 1.0)
    assert n.sample(2001.0, 1.0, force=True) is True
    assert len(n) == 2


def test_buffer_is_bounded():
    """An always-on process must not grow without limit."""
    clk = FakeClock()
    n = IntradayNav(max_samples=10, min_interval=0.0, clock=clk)
    for i in range(50):
        clk.t = i
        n.sample(2000.0 + i, 1.0)
    assert len(n) == 10


def test_samples_are_marked_unstruck():
    """Nothing may mistake a sample for the official NAV mark."""
    n = IntradayNav(min_interval=0.0, clock=FakeClock())
    n.sample(2000.0, 1.0)
    assert n.series()["samples"][0]["struck"] is False
    assert "never struck" in n.series()["note"]


def test_change_is_computed_from_the_returned_endpoints():
    clk = FakeClock()
    n = IntradayNav(min_interval=0.0, clock=clk)
    for i, v in enumerate([2000.0, 2010.0, 2020.0]):
        clk.t = i
        n.sample(v, 1.0 + i / 1000)
    s = n.series()
    assert s["change_usd"] == pytest.approx(20.0)
    assert s["change_pct"] == pytest.approx(1.0, abs=0.01)


def test_empty_series_reports_nothing_rather_than_zero():
    """A flat zero would read as 'no P&L'; there is simply no data."""
    s = IntradayNav().series()
    assert s["n"] == 0
    assert s["change_usd"] is None
    assert s["change_pct"] is None


def test_missing_nav_per_unit_is_none_not_zero():
    n = IntradayNav(min_interval=0.0, clock=FakeClock())
    n.sample(2000.0, None)
    assert n.series()["samples"][0]["nav_per_unit"] is None
