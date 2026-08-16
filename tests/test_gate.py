"""The candidate gate — the bar, applied identically to everything.

The property under test throughout: MISSING evidence must fail. A candidate
that was never held out has not survived a holdout, and a factory that treats
absent evidence as satisfied evidence quietly lowers its own bar until it
approves everything.
"""

import pytest

from app.fund.gate import CRITERIA, evaluate


def _good_result(**over):
    r = {
        "total_return_pct": 20.0,
        "benchmark_return_pct": 10.0,
        "capacity_usd": None,
        "capacity": {"capacity_usd": 5_000_000.0},
        "robustness": {
            "total_orders": 40,
            "psr_pct": 80.0,
            "costs": {"slippage_modelled": True},
        },
    }
    r.update(over)
    return r


GOOD_HOLDOUT = {"state": "done", "dates_honoured": True,
                "train": {"return_pct": 20.0}, "test": {"return_pct": 16.0}}
GOOD_SWEEP = {"breakeven_cost": {"breakeven_bps": 25.0}}


def test_a_clean_candidate_passes():
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP)
    assert out["passed"] is True, out["failures"]
    assert out["gate_version"] == "v1"
    # Passing is not deployment, and the wording says so.
    assert "different claim from" in out["verdict"]


def test_an_unpriced_backtest_fails():
    r = _good_result()
    r["robustness"]["costs"] = {"slippage_modelled": False}
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("not priced" in f for f in out["failures"])


def test_too_few_trades_fails():
    r = _good_result()
    r["robustness"]["total_orders"] = 3
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("anecdote" in f for f in out["failures"])


def test_low_psr_fails_even_with_a_great_return():
    """The trap the whole system exists to catch: 100% win rate on 3 trades."""
    r = _good_result(total_return_pct=500.0)
    r["robustness"]["psr_pct"] = 22.0
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("distinguishable from luck" in f for f in out["failures"])


def test_trailing_buy_and_hold_fails():
    out = evaluate(_good_result(total_return_pct=5.0, benchmark_return_pct=30.0),
                   GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("expensive way to hold" in f for f in out["failures"])


def test_a_missing_holdout_fails_rather_than_passes():
    out = evaluate(_good_result(), None, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("no held-out test" in f for f in out["failures"])


def test_a_holdout_that_ran_the_same_dates_fails():
    bad = {**GOOD_HOLDOUT, "dates_honoured": False}
    out = evaluate(_good_result(), bad, GOOD_SWEEP)
    assert any("SAME dates twice" in f for f in out["failures"])


def test_an_edge_that_collapses_out_of_sample_fails():
    ho = {**GOOD_HOLDOUT, "test": {"return_pct": 1.0}}   # kept 5%
    out = evaluate(_good_result(), ho, GOOD_SWEEP)
    assert any("out of sample" in f for f in out["failures"])


def test_fragility_to_costs_fails():
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   {"breakeven_cost": {"breakeven_bps": 3.0}})
    assert any("dies at 3.0bps" in f for f in out["failures"])


def test_capacity_too_small_to_bother_fails():
    r = _good_result(capacity={"capacity_usd": 5_000.0})
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("operational cost" in f for f in out["failures"])


def test_every_failure_is_reported_not_just_the_first():
    """The operator should see the whole picture, not fix one thing and
    resubmit into the next objection."""
    r = _good_result(total_return_pct=1.0, benchmark_return_pct=30.0)
    r["robustness"] = {"total_orders": 2, "psr_pct": 5.0,
                       "costs": {"slippage_modelled": False}}
    out = evaluate(r, None, {"breakeven_cost": {"breakeven_bps": 1.0}})
    assert len(out["failures"]) >= 5


def test_the_bar_is_data_and_can_be_tightened():
    tighter = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                       criteria={"min_psr_pct": 95.0})
    assert tighter["passed"] is False
    assert tighter["criteria"]["min_psr_pct"] == 95.0
    # and the default is untouched by that call
    assert CRITERIA["min_psr_pct"] == 50.0
