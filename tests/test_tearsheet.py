"""Tearsheet metrics — and the refusals that keep them honest."""

from __future__ import annotations

import math
import random

import pytest

from app.fund import tearsheet
from app.fund.statistics import probabilistic_sharpe_ratio


def curve_from(returns):
    eq, out = 1.0, [1.0]
    for r in returns:
        eq *= (1.0 + r)
        out.append(eq)
    return out


# --------------------------------------------------------------- refusals
def test_too_short_a_curve_is_unmeasurable():
    out = tearsheet.build([1.0])
    assert out["measurable"] is False
    assert "fewer than 2" in out["reason"]


def test_no_benchmark_says_so_rather_than_reporting_beta_zero():
    out = tearsheet.build(curve_from([0.01] * 60))
    assert out["benchmark"]["measurable"] is False
    assert "no benchmark" in out["benchmark"]["reason"]


def test_short_sample_refuses_benchmark_regression():
    rets = [0.01] * 5
    out = tearsheet.build(curve_from(rets), benchmark_curve=curve_from(rets))
    assert out["benchmark"]["measurable"] is False
    assert "need" in out["benchmark"]["reason"]


def test_flat_benchmark_refuses_beta():
    rets = [0.001 * ((-1) ** i) for i in range(60)]
    flat = [0.0] * 60
    out = tearsheet.build(curve_from(rets), benchmark_curve=curve_from(flat))
    assert out["benchmark"]["measurable"] is False
    assert "zero variance" in out["benchmark"]["reason"]


# --------------------------------------------------------------- drawdown
def test_drawdown_recovery_is_counted():
    # up to 1.2, down to 0.9, back above 1.2
    curve = [1.0, 1.2, 1.0, 0.9, 1.0, 1.1, 1.25]
    dd = tearsheet.drawdown_profile(curve)
    assert dd["measurable"] is True
    assert dd["max_drawdown_pct"] == pytest.approx(-25.0)
    assert dd["trough_index"] == 3
    assert dd["recovery_index"] == 6
    assert dd["recovery_bars"] == 3
    assert dd["still_underwater"] is False


def test_unrecovered_drawdown_says_so_instead_of_implying_recovery():
    curve = [1.0, 1.5, 1.1, 1.2, 1.3]
    dd = tearsheet.drawdown_profile(curve)
    assert dd["still_underwater"] is True
    assert dd["recovery_bars"] is None
    assert "never recovered" in dd["note"]


def test_monotonic_curve_has_no_drawdown():
    dd = tearsheet.drawdown_profile([1.0, 1.1, 1.2, 1.3])
    assert dd["max_drawdown_pct"] == 0.0
    assert dd["still_underwater"] is False


# ---------------------------------------------------------------- ratios
def test_sortino_exceeds_sharpe_when_downside_is_rare():
    # Mostly small gains, few losses: downside deviation < total deviation.
    rets = [0.01] * 50 + [-0.005] * 5
    out = tearsheet.build(curve_from(rets))
    assert out["ratios"]["sortino_annual"] > out["ratios"]["sharpe_annual"]


def test_downside_deviation_divides_by_all_observations():
    # One -10% in 100 periods; dividing by the single loser would give 0.10.
    rets = [0.0] * 99 + [-0.10]
    dsd = tearsheet._downside_deviation(rets)
    assert dsd == pytest.approx(math.sqrt((0.10 ** 2) / 100))


def test_calmar_is_cagr_over_drawdown_depth():
    rets = [0.01] * 100 + [-0.02] * 10 + [0.01] * 150
    out = tearsheet.build(curve_from(rets))
    cagr = out["returns"]["cagr_pct"] / 100.0
    depth = abs(out["drawdown"]["max_drawdown_pct"]) / 100.0
    assert out["ratios"]["calmar"] == pytest.approx(cagr / depth, rel=1e-3)


# ------------------------------------------------------------- benchmark
def test_beta_of_one_when_strategy_is_the_benchmark():
    random.seed(3)
    rets = [random.gauss(0.0005, 0.01) for _ in range(300)]
    c = curve_from(rets)
    out = tearsheet.build(c, benchmark_curve=c)
    b = out["benchmark"]
    assert b["beta"] == pytest.approx(1.0, abs=1e-6)
    assert b["r_squared"] == pytest.approx(1.0, abs=1e-6)
    assert b["alpha_annual_pct"] == pytest.approx(0.0, abs=1e-6)
    # No active risk means the information ratio is undefined, not zero.
    assert b["information_ratio"] is None
    assert b["tracking_error_pct"] == pytest.approx(0.0, abs=1e-9)


def test_half_exposure_gives_beta_of_a_half():
    random.seed(5)
    bench = [random.gauss(0.0005, 0.01) for _ in range(300)]
    strat = [r * 0.5 for r in bench]
    out = tearsheet.build(curve_from(strat), benchmark_curve=curve_from(bench))
    assert out["benchmark"]["beta"] == pytest.approx(0.5, abs=0.02)
    assert out["benchmark"]["idiosyncratic_share"] == pytest.approx(0.0, abs=1e-6)


# ---------------------------------------------------------------- rolling
def test_rolling_windows_longer_than_the_sample_are_refused_not_truncated():
    rows = tearsheet.rolling_windows([0.001] * 30)
    by_label = {r["label"]: r for r in rows}
    assert by_label["1m"]["measurable"] is True
    assert by_label["1y"]["measurable"] is False
    assert "window needs" in by_label["1y"]["reason"]


def test_rolling_window_counts_are_right():
    rows = tearsheet.rolling_windows([0.001] * 100, windows=[("1m", 21)])
    r = rows[0]
    assert len(r["return_pct"]) == 100 - 21 + 1
    assert r["share_positive"] == 1.0


# --------------------------------------------------------------- turnover
def test_turnover_counts_position_changes():
    # flat -> long -> flat -> long over 4 bars = 3 units of turnover
    out = tearsheet.build(curve_from([0.0] * 3), signals=[0.0, 1.0, 0.0, 1.0])
    assert out["turnover_annual"] == pytest.approx((3.0 / 4.0) * 252)


def test_no_signals_means_turnover_unknown_not_zero():
    assert tearsheet.build(curve_from([0.01] * 40))["turnover_annual"] is None


# -------------------------------------------------------------- inference
def test_pure_noise_does_not_clear_the_selection_bar():
    """The whole point: a lucky sweep must not be reported as an edge."""
    random.seed(11)
    rets = [random.gauss(0.0004, 0.012) for _ in range(756)]
    out = tearsheet.build(curve_from(rets), n_trials=25)
    sel = out["inference"]["selection"]
    assert sel["applies"] is True
    assert sel["clears_noise"] is False
    assert sel["noise_threshold"] > sel["observed_sharpe"]


def test_single_trial_has_no_selection_penalty():
    random.seed(2)
    rets = [random.gauss(0.0005, 0.01) for _ in range(300)]
    out = tearsheet.build(curve_from(rets), n_trials=1)
    assert out["inference"]["selection"]["applies"] is False


def test_constant_returns_leave_sharpe_undefined_rather_than_infinite():
    """Zero variance is not an infinite Sharpe — it is an unmeasurable one."""
    out = tearsheet.build(curve_from([0.001] * 300))
    assert out["ratios"]["sharpe_annual"] is None
    assert out["inference"]["measurable"] is False


def test_psr_falls_as_the_sample_shrinks():
    """Same Sharpe, less data, less confidence — the correction that matters."""
    long_run = probabilistic_sharpe_ratio(0.05, 1000)
    short_run = probabilistic_sharpe_ratio(0.05, 30)
    assert long_run["psr"] > short_run["psr"]


def test_psr_penalises_negative_skew():
    """Two series, same Sharpe: the one that sells tails must score lower."""
    symmetric = [0.01, -0.01] * 100
    # same mean/sd shape but with a long left tail
    skewed = [0.012] * 190 + [-0.20] * 10
    sym = probabilistic_sharpe_ratio(0.05, 200, returns=symmetric)
    skw = probabilistic_sharpe_ratio(0.05, 200, returns=skewed)
    assert skw["skew"] < sym["skew"]
    assert skw["psr"] < sym["psr"]


def test_psr_refuses_below_two_observations():
    assert probabilistic_sharpe_ratio(1.0, 1)["usable"] is False


# ----------------------------------------------------------------- trades
def test_expectancy_decomposes_into_its_parts():
    trades = [
        {"pnl_pct": 30.0, "bars_held": 5},
        {"pnl_pct": -10.0, "bars_held": 3},
        {"pnl_pct": -10.0, "bars_held": 4},
    ]
    e = tearsheet.trade_expectancy(trades)
    assert e["win_rate"] == pytest.approx(1 / 3, abs=1e-4)
    assert e["payoff_ratio"] == pytest.approx(3.0)
    assert e["expectancy_pct"] == pytest.approx(30 / 3 - 20 / 3, abs=1e-3)
    assert e["top_trade_share_of_gross_profit"] == pytest.approx(1.0)


def test_no_trades_is_unmeasurable():
    assert tearsheet.trade_expectancy([])["measurable"] is False


def test_wiped_out_equity_does_not_produce_infinities():
    """A curve that touches zero must not poison every downstream mean."""
    out = tearsheet.build([1.0, 0.5, 0.0, 0.0, 0.2] + [0.2] * 40)
    assert out["measurable"] is True
    for v in out["risk"].values():
        assert v is None or math.isfinite(float(v))
