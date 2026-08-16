"""The regime throttle — cut gross when fragile, and only ever cut.

Most of these assert what the rule REFUSES to do. A throttle that can raise
exposure, or that trims on missing data, has turned a warning system into a
trading strategy nobody signed off on.
"""

import pytest

from app.fund.throttle import (MAX_REDUCTION, apply_to, target_gross)


def _regime(t_pct=None, a_shift=None):
    return {
        "turbulence": ({"measurable": True, "recent_20d_percentile": t_pct}
                       if t_pct is not None else {"measurable": False}),
        "absorption": ({"measurable": True, "standardised_shift": a_shift}
                       if a_shift is not None else {"measurable": False}),
    }


def test_a_calm_regime_runs_full_gross():
    out = target_gross(_regime(t_pct=40.0, a_shift=0.2))
    assert out["gross_multiplier"] == 1.0
    assert out["driver"] is None


def test_the_rule_never_raises_gross_above_normal():
    """Even at the calmest possible reading. A system that can automatically
    increase exposure is one that can automatically get greedy."""
    out = target_gross(_regime(t_pct=0.0, a_shift=-5.0))
    assert out["gross_multiplier"] == 1.0
    assert "would not raise it" in out["reason"]


def test_high_turbulence_trims():
    out = target_gross(_regime(t_pct=90.0, a_shift=0.0))
    assert out["gross_multiplier"] < 1.0
    assert out["driver"] == "turbulence"
    assert "pays poorly" in out["reason"]


def test_converging_correlations_trim():
    out = target_gross(_regime(t_pct=10.0, a_shift=2.0))
    assert out["gross_multiplier"] < 1.0
    assert out["driver"] == "absorption"
    assert "diversification is quietly disappearing" in out["reason"]


def test_the_trim_is_capped():
    """Going fully to cash on a statistical reading has its own large cost —
    being out of the recovery — and belongs to a person."""
    out = target_gross(_regime(t_pct=100.0, a_shift=10.0))
    assert out["gross_multiplier"] == pytest.approx(1.0 - MAX_REDUCTION)


def test_the_worse_signal_wins_rather_than_the_average():
    """Averaging would let a calm reading on one measure pay for an alarming
    one on the other. They describe different ways to be in trouble."""
    both = target_gross(_regime(t_pct=97.0, a_shift=0.0))["gross_multiplier"]
    one = target_gross(_regime(t_pct=97.0, a_shift=3.0))["gross_multiplier"]
    assert both == pytest.approx(1.0 - MAX_REDUCTION)
    assert one == pytest.approx(both)      # already maxed, not averaged down


def test_the_ramp_is_gradual_not_a_cliff():
    """A stepped rule flips the book's size on a hovering reading, paying
    spread every time and protecting nothing."""
    a = target_gross(_regime(t_pct=85.0))["gross_multiplier"]
    b = target_gross(_regime(t_pct=90.0))["gross_multiplier"]
    c = target_gross(_regime(t_pct=95.0))["gross_multiplier"]
    assert 1.0 > a > b > c


def test_an_unmeasurable_regime_does_not_trim():
    """Trimming on missing data would turn a data outage into a trading
    decision. Absent evidence is not evidence of danger."""
    out = target_gross(_regime())
    assert out["gross_multiplier"] == 1.0
    assert out["measurable"] is False
    assert "absent evidence" in out["reason"]


def test_applying_it_scales_every_weight_equally():
    """Choosing WHICH position to cut is a view, and this rule has none."""
    out = apply_to({"A": 0.5, "B": 0.3}, _regime(t_pct=97.0))
    assert out["weights"]["A"] == pytest.approx(0.5 * (1 - MAX_REDUCTION))
    assert out["weights"]["B"] == pytest.approx(0.3 * (1 - MAX_REDUCTION))
    assert out["cash_weight"] > 0


def test_applying_it_in_a_calm_regime_changes_nothing():
    out = apply_to({"A": 0.5, "B": 0.3}, _regime(t_pct=20.0, a_shift=0.0))
    assert out["weights"] == {"A": 0.5, "B": 0.3}
    assert out["cash_weight"] == 0.0
