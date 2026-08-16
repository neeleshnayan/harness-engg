"""Capacity — the AUM at which a strategy's own trading becomes the problem.

The number that turns "we are too small to compete" into "we are small enough
that this is ours". Every assertion here is about not overstating it: an
inflated capacity is how a strategy gets funded past the point where it works.
"""

import pytest

from app.fund.capacity import (BIG_FUND_FLOOR_USD, adv_usd, estimate, headroom)


def test_adv_uses_the_median_not_the_mean():
    """One earnings day at ten times normal volume must not buy capacity the
    strategy could never actually use."""
    closes = [100.0] * 10
    volumes = [1_000.0] * 9 + [1_000_000.0]      # one enormous print
    adv = adv_usd(closes, volumes)
    assert adv == pytest.approx(100_000.0)        # median day, not the spike


def test_adv_ignores_zero_and_missing_days():
    adv = adv_usd([100.0, 0.0, 100.0], [1_000.0, 5_000.0, 1_000.0])
    assert adv == pytest.approx(100_000.0)


def test_no_volume_means_no_estimate_rather_than_a_guess():
    out = estimate("X", [100.0, 101.0], [], 5.0)
    assert out["capacity_usd"] is None
    assert "cannot be estimated" in out["reason"]


def test_capacity_falls_as_turnover_rises():
    """The same symbol supports far less money if the strategy flips daily —
    which is why turnover is the lever when capacity binds."""
    closes, volumes = [100.0] * 60, [100_000.0] * 60     # $10m ADV
    slow = estimate("X", closes, volumes, 1.0)["capacity_usd"]
    fast = estimate("X", closes, volumes, 10.0)["capacity_usd"]
    assert slow == pytest.approx(fast * 10)


def test_capacity_is_participation_times_adv_over_turnover():
    closes, volumes = [100.0] * 60, [100_000.0] * 60     # $10m ADV
    out = estimate("X", closes, volumes, 5.0, participation=0.01)
    # 0.01 * 10_000_000 / 0.05
    assert out["capacity_usd"] == pytest.approx(2_000_000.0)


def test_halving_participation_halves_capacity():
    closes, volumes = [100.0] * 60, [100_000.0] * 60
    a = estimate("X", closes, volumes, 5.0, participation=0.01)["capacity_usd"]
    b = estimate("X", closes, volumes, 5.0, participation=0.005)["capacity_usd"]
    assert b == pytest.approx(a / 2)


def test_a_small_capacity_is_reported_as_an_ADVANTAGE():
    """The whole point. Below the big-fund floor is not a warning."""
    closes, volumes = [10.0] * 60, [50_000.0] * 60       # $500k ADV, thin
    out = estimate("SMALLCAP", closes, volumes, 5.0)
    assert out["capacity_usd"] < BIG_FUND_FLOOR_USD
    assert out["below_big_fund_floor"] is True


def test_a_liquid_name_says_size_is_not_what_protects_it():
    closes, volumes = [500.0] * 60, [80_000_000.0] * 60   # SPY-ish, huge ADV
    out = estimate("SPY", closes, volumes, 5.0)
    assert out["below_big_fund_floor"] is False
    assert "everyone can trade it" in out["verdict"]


def test_a_thin_tape_distrusts_the_backtest_fills():
    closes, volumes = [5.0] * 60, [20_000.0] * 60         # $100k ADV
    out = estimate("THIN", closes, volumes, 2.0)
    assert out["thin_market"] is True
    assert "too thin to trust" in out["verdict"]


def test_zero_turnover_is_not_infinite_capacity():
    """A strategy that never trades has no TRADING limit — saying 'unlimited'
    would be answering a different question."""
    out = estimate("X", [100.0] * 60, [100_000.0] * 60, 0.0)
    assert out["capacity_usd"] is None
    assert "never trades" in out["reason"]


def test_headroom_is_honest_about_a_tiny_fund():
    h = headroom(2_000_000.0, 2_026.86)
    assert h["used_pct"] < 1.0
    assert "not the binding constraint" in h["note"]


def test_headroom_warns_when_size_starts_to_matter():
    h = headroom(10_000.0, 2_000.0)
    assert h["used_pct"] == pytest.approx(20.0)
    assert "turnover is the lever" in h["note"]
