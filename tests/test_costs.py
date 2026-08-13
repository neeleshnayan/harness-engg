"""Transaction costs — the difference between a backtest and a strategy."""

from __future__ import annotations

import pytest

from app.fund.backtest import NO_COSTS, CostModel, SimpleBacktester


def flat_prices(n=50):
    """A market that goes nowhere. Any P&L here is pure cost."""
    return [100.0] * n


def alternating(n=50):
    """In, out, in, out — one unit of turnover per bar."""
    return [float(i % 2) for i in range(n)]


# ----------------------------------------------------------------- defaults
def test_default_is_frictionless_and_says_so_loudly():
    r = SimpleBacktester().run(flat_prices(), alternating())
    c = r.to_dict()["costs"]
    assert c["frictionless"] is True
    assert "NO transaction costs" in c["warning"]
    assert r.total_costs == 0.0


def test_costed_run_carries_no_warning():
    r = SimpleBacktester(CostModel(slippage_bps=2.0)).run(flat_prices(), alternating())
    c = r.to_dict()["costs"]
    assert c["frictionless"] is False
    assert c["warning"] is None


def test_costs_block_is_always_present():
    """A missing costs section reads as 'not applicable'; it must read as zero."""
    assert "costs" in SimpleBacktester().run(flat_prices(), alternating()).to_dict()


# ------------------------------------------------------------- the charging
def test_costs_only_bite_a_strategy_that_trades():
    """Buy and hold pays to get in and out; a flipper pays on every flip."""
    px = flat_prices(50)
    costs = CostModel(slippage_bps=10.0)
    hold = SimpleBacktester(costs).run(px, [1.0] * 50)
    flip = SimpleBacktester(costs).run(px, alternating(50))
    assert hold.turnover == pytest.approx(2.0)      # in once, out once
    assert flip.turnover > hold.turnover
    assert flip.total_costs > hold.total_costs
    # In a flat market every cent of loss is cost.
    assert hold.total_return < 0 and flip.total_return < hold.total_return


def test_a_flip_turns_over_two_units_not_one():
    px = flat_prices(4)
    r = SimpleBacktester(CostModel(slippage_bps=1.0)).run(px, [1.0, -1.0, -1.0, -1.0])
    # 1 unit in, 2 to flip long->short, 1 to close = 4
    assert r.turnover == pytest.approx(4.0)


def test_cost_rate_is_the_sum_of_slippage_and_commission():
    a = CostModel(slippage_bps=3.0, commission_bps=2.0)
    assert a.per_unit_turnover == pytest.approx(5.0 / 10_000)
    assert a.to_dict()["total_bps_per_unit_turnover"] == pytest.approx(5.0)


def test_final_open_position_is_charged_its_exit():
    """A position never closed must not dodge half its round trip."""
    px = flat_prices(30)
    costed = SimpleBacktester(CostModel(slippage_bps=50.0)).run(px, [1.0] * 30)
    # entry + exit at 50bps each on a flat market
    assert costed.total_return == pytest.approx(-0.01, abs=5e-4)


def test_never_trading_costs_nothing():
    r = SimpleBacktester(CostModel(slippage_bps=100.0)).run(flat_prices(), [0.0] * 50)
    assert r.turnover == 0.0
    assert r.total_costs == 0.0
    assert r.total_return == pytest.approx(0.0)


# ------------------------------------------------- costs reach the RISK stats
def test_sharpe_and_drawdown_are_computed_after_costs():
    """Cost-free risk stats beside a costed return would be the worst of both."""
    px = flat_prices(60)
    free = SimpleBacktester(NO_COSTS).run(px, alternating(60))
    paid = SimpleBacktester(CostModel(slippage_bps=25.0)).run(px, alternating(60))
    # Flat market, no costs: nothing moves at all.
    assert free.sharpe == pytest.approx(0.0)
    assert free.max_drawdown == pytest.approx(0.0)
    # With costs the equity curve only ever falls, so both must register it.
    assert paid.sharpe < 0
    assert paid.max_drawdown < 0
    assert paid.equity_curve[-1] < paid.equity_curve[0]


def test_costs_do_not_change_a_zero_bar_backtest():
    r = SimpleBacktester(CostModel(slippage_bps=10.0)).run([100.0], [1.0])
    assert r.bars == 1
    assert r.to_dict()["costs"]["frictionless"] is False


def test_higher_costs_never_improve_a_result():
    px = [100.0 + (i % 7) for i in range(120)]
    sig = alternating(120)
    prev = None
    for bps in (0.0, 1.0, 5.0, 20.0):
        r = SimpleBacktester(CostModel(slippage_bps=bps)).run(px, sig)
        if prev is not None:
            assert r.total_return <= prev + 1e-12
        prev = r.total_return
