"""Backtest research detail — the equity curve and trade list.

The simulation always computed an equity curve and always knew when position
changed; it discarded both and returned summary statistics only. That made a
strategy tester impossible: you cannot draw an equity curve, a drawdown chart or
a trade list from a Sharpe ratio.
"""

from app.fund.backtest import SimpleBacktester


def run(prices, signals):
    return SimpleBacktester().run(prices, signals)


def test_equity_curve_is_returned_and_aligned_to_bars():
    prices = [100, 110, 121]          # +10% then +10%
    r = run(prices, [1, 1, 0])

    assert len(r.equity_curve) == len(prices)
    assert r.equity_curve[0] == 1.0
    assert round(r.equity_curve[-1], 6) == round(r.final_equity, 6)
    assert round(r.final_equity, 4) == 1.21


def test_flat_signal_leaves_equity_untouched():
    r = run([100, 150, 90], [0, 0, 0])

    assert r.equity_curve == [1.0, 1.0, 1.0]
    assert r.total_return == 0.0
    assert r.exposure_pct == 0.0
    assert r.trades == []


def test_trades_record_entry_exit_and_pnl():
    # long from bar 0 (price 100), exit at bar 2 (price 121)
    r = run([100, 110, 121, 121], [1, 1, 0, 0])

    assert len(r.trades) == 1
    t = r.trades[0]
    assert t["side"] == "long"
    assert t["entry_index"] == 0 and t["entry_price"] == 100
    assert t["exit_index"] == 2 and t["exit_price"] == 121
    assert round(t["pnl_pct"], 2) == 21.0
    assert t["bars_held"] == 2


def test_open_position_is_closed_at_the_final_bar():
    """A position still open at the end must appear, or the list lies by omission."""
    r = run([100, 120], [1, 1])

    assert len(r.trades) == 1
    assert r.trades[0]["exit_price"] == 120


def test_win_rate_and_profit_factor():
    # win +10%, then a loss -20%
    prices = [100, 110, 110, 88, 88]
    signals = [1, 0, 1, 0, 0]
    r = run(prices, signals)

    wins = [t for t in r.trades if t["pnl_pct"] > 0]
    losses = [t for t in r.trades if t["pnl_pct"] < 0]
    assert len(wins) == 1 and len(losses) == 1
    assert round(r.win_rate, 2) == 0.5
    assert r.profit_factor > 0


def test_no_losing_trades_does_not_report_infinite_profit_factor():
    r = run([100, 110, 110], [1, 0, 0])

    assert r.profit_factor == 0.0     # not inf, not nan
    assert r.win_rate == 1.0


def test_exposure_counts_only_bars_holding_a_position():
    r = run([100, 101, 102, 103, 104], [1, 1, 0, 0, 0])

    assert round(r.exposure_pct, 1) == 50.0   # 2 of 4 tradable bars


def test_to_dict_can_omit_series_for_light_responses():
    r = run([100, 110, 121], [1, 1, 0])

    light = r.to_dict(include_series=False)
    assert "equity_curve" not in light and "trades" not in light
    assert "sharpe" in light and "win_rate" in light

    full = r.to_dict()
    assert len(full["equity_curve"]) == 3
