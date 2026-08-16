"""Sizing — the step that turns an edge into a return.

Most of these assert restraint rather than cleverness, because that is where
sizing rules do damage: a formula that can concentrate the fund, short on a
sign flip, or size a position from an unmeasured number has replaced one risk
with a worse one.
"""

import math

import pytest

from app.fund.sizing import (KELLY_CAP, MAX_WEIGHT, annualised_vol,
                             inverse_vol_weights, kelly_fraction,
                             risk_contributions, size)


def test_the_noisier_name_gets_less_money():
    w = inverse_vol_weights({"CALM": 0.10, "WILD": 0.40})
    assert w["CALM"] == pytest.approx(0.8)
    assert w["WILD"] == pytest.approx(0.2)
    assert sum(w.values()) == pytest.approx(1.0)


def test_a_name_with_unknown_volatility_is_dropped_not_defaulted():
    """Defaulting would size a position on a number nobody measured."""
    w = inverse_vol_weights({"KNOWN": 0.2, "UNKNOWN": None, "ZERO": 0.0})
    assert set(w) == {"KNOWN"}


def test_volatility_needs_enough_points_to_be_called_one():
    assert annualised_vol([0.01] * 5) is None
    v = annualised_vol([0.01, -0.01] * 30)
    assert v is not None and v > 0


def test_annualisation_uses_trading_days():
    daily = [0.01, -0.01] * 60
    v = annualised_vol(daily)
    assert v == pytest.approx(0.01 * math.sqrt(252), rel=1e-6)


def test_kelly_is_capped_far_below_full():
    """Full Kelly is optimal only if the edge is known exactly, and an edge
    estimated from a backtest never is."""
    huge = kelly_fraction(edge_annual=5.0, vol_annual=0.10)
    assert huge == pytest.approx(KELLY_CAP)


def test_kelly_refuses_to_short_on_a_negative_edge():
    """Deciding to be short is a strategy decision, not something that falls
    out of a sizing formula."""
    assert kelly_fraction(edge_annual=-0.2, vol_annual=0.2) == 0.0


def test_no_name_can_take_over_the_book():
    """A near-zero-vol name would otherwise get almost everything."""
    out = size({"TINYVOL": 0.001, "A": 0.30, "B": 0.30})
    assert out["weights"]["TINYVOL"] <= MAX_WEIGHT + 1e-9


def test_an_unmeetable_cap_holds_cash_rather_than_relaxing_itself():
    """The bug this replaced: capping the calm name and redistributing handed
    65% to the WILDEST name in the book — the exact concentration the cap
    existed to prevent. When the limit cannot be met while fully invested, the
    honest answer is cash."""
    out = size({"CALM": 0.05, "WILD": 0.60})
    assert out["weights"]["CALM"] == pytest.approx(MAX_WEIGHT)
    assert out["weights"]["WILD"] < MAX_WEIGHT
    assert out["gross"] < 1.0
    assert out["cash_weight"] > 0


def test_dust_positions_are_dropped():
    """At a $2k book a 2% weight is $40, where the spread outweighs the idea."""
    out = size({"BIG": 0.10, "DUST": 20.0})
    assert "DUST" not in out["weights"]
    assert out["dropped_too_small"] == ["DUST"]
    assert out["cash_weight"] > 0        # nothing was inflated to fill the gap


def test_the_equal_weight_baseline_is_always_shown():
    """It beats most optimised portfolios out of sample, so the comparison
    belongs next to the answer rather than in a footnote."""
    out = size({"A": 0.2, "B": 0.4})
    assert out["equal_weight_would_be"] == pytest.approx(0.5)
    assert "strong baseline" in out["caveat"]


def test_gross_cap_is_a_ceiling_never_a_target():
    out = size({"A": 0.2, "B": 0.2}, gross_cap=0.5)
    assert out["gross"] <= 0.5 + 1e-9
    assert out["gross"] + out["cash_weight"] == pytest.approx(0.5, abs=1e-6)


def test_dollar_sizes_follow_nav():
    out = size({"A": 0.2, "B": 0.2}, nav_usd=2000.0)
    assert sum(out["usd"].values()) == pytest.approx(out["gross"] * 2000.0, abs=0.02)


def test_risk_contributions_sum_to_one():
    rets = {"A": [0.01, -0.01] * 30, "B": [0.02, -0.02] * 30}
    rc = risk_contributions({"A": 0.5, "B": 0.5}, rets)
    assert sum(rc.values()) == pytest.approx(1.0, abs=1e-6)


def test_equal_weights_do_not_mean_equal_risk():
    """The gap between weight and risk is the entire argument for sizing."""
    rets = {"CALM": [0.002, -0.002] * 40, "WILD": [0.05, -0.05] * 40}
    rc = risk_contributions({"CALM": 0.5, "WILD": 0.5}, rets)
    assert rc["WILD"] > rc["CALM"] * 10


def test_no_measurable_candidate_is_an_honest_empty_answer():
    out = size({"A": None})
    assert out["weights"] == {}
    assert "no candidate" in out["reason"]
