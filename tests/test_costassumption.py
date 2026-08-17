"""One cost assumption, in one place.

It lived in two and they disagreed: LEAN priced slippage at 5bps a side while
TCA graded realised fills against 2. So "we are 4bps over assumption" meant
nothing, because there were two assumptions — and the entire argument for
measuring realised cost is that it VALIDATES the backtest premise. A comparison
against a number no backtest uses validates nothing.
"""

import pytest

from app.fund.costassumption import (DEFAULT_SLIPPAGE_BPS, RELIABLE_SAMPLE,
                                     compare, slippage_bps, slippage_fraction)


def test_the_backtests_and_the_report_card_read_the_same_number():
    """The bug this file exists to prevent, asserted directly."""
    from app.fund.tca import ASSUMED_COST_BPS_PER_SIDE
    assert ASSUMED_COST_BPS_PER_SIDE == slippage_bps()


def test_the_fraction_is_the_bps_number_lean_can_consume():
    assert slippage_fraction() == pytest.approx(DEFAULT_SLIPPAGE_BPS / 10_000.0)


def test_no_fills_is_unchallenged_not_validated():
    """The distinction matters: an assumption nobody has tested reads as fine
    right up until it doesn't."""
    out = compare(None, 0)
    assert out["reliable"] is False
    assert "unchallenged" in out["verdict"]
    assert "not the same as validated" in out["verdict"]


def test_paying_more_than_modelled_says_returns_are_overstated():
    out = compare(12.0, 50)
    assert out["excess_bps"] == pytest.approx(7.0)
    assert "overstated" in out["verdict"]
    assert "trades most" in out["verdict"]


def test_paying_less_than_modelled_is_called_conservative():
    out = compare(2.0, 50)
    assert out["excess_bps"] < 0
    assert "conservative" in out["verdict"]


def test_close_enough_is_reported_as_agreement():
    out = compare(DEFAULT_SLIPPAGE_BPS + 0.4, 50)
    assert "about what trading costs" in out["verdict"]


def test_a_small_sample_is_named_as_an_anecdote():
    """The failure this guards: re-tuning the assumption to match six fills in
    a calm week, then being surprised by a volatile one."""
    out = compare(5.5, 10)
    assert out["reliable"] is False
    assert "anecdote" in out["verdict"]


def test_a_large_sample_drops_the_caveat():
    out = compare(5.5, RELIABLE_SAMPLE)
    assert out["reliable"] is True
    assert "anecdote" not in out["verdict"]


def test_the_assumption_is_environment_overridable(monkeypatch):
    """One place to change it, so the two consumers cannot drift again."""
    import importlib
    monkeypatch.setenv("FUND_SLIPPAGE_BPS", "9.5")
    import app.fund.costassumption as ca
    importlib.reload(ca)
    try:
        assert ca.slippage_bps() == pytest.approx(9.5)
        assert ca.slippage_fraction() == pytest.approx(0.00095)
    finally:
        monkeypatch.delenv("FUND_SLIPPAGE_BPS", raising=False)
        importlib.reload(ca)
