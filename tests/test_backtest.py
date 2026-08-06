"""Lightweight backtester — the Studio's backtest step."""

import pytest

from app.fund.backtest import SimpleBacktester, sma_crossover_signals

BT = SimpleBacktester()


def test_buy_and_hold_uptrend():
    prices = [100, 102, 104, 103, 108, 112]
    r = BT.run(prices, [1.0] * len(prices))
    assert r.total_return == pytest.approx(0.12, abs=1e-6)   # 112/100 - 1
    assert r.max_drawdown < 0                                 # the 104->103 dip
    assert r.n_trades == 1                                    # entered long once
    assert r.bars == len(prices)


def test_flat_signals_do_nothing():
    r = BT.run([100, 90, 120, 110], [0.0, 0.0, 0.0, 0.0])
    assert r.total_return == pytest.approx(0.0)
    assert r.n_trades == 0
    assert r.max_drawdown == pytest.approx(0.0)


def test_short_avoids_a_drawdown():
    # Falling market: a short (-1) profits where buy-and-hold would lose.
    prices = [100, 95, 90, 85]
    short = BT.run(prices, [-1.0] * len(prices))
    hold = BT.run(prices, [1.0] * len(prices))
    assert short.total_return > 0 > hold.total_return


def test_sma_crossover_signal_shape():
    prices = list(range(1, 41))  # steady uptrend
    sig = sma_crossover_signals(prices, fast=5, slow=20)
    assert len(sig) == len(prices)
    assert set(sig) <= {0.0, 1.0}
    assert sig[-1] == 1.0                                     # fast above slow in an uptrend
    assert sig[0] == 0.0                                      # warm-up period is flat
