"""Lightweight backtester — the Studio's backtest step."""

import pytest

from app.fund.backtest import (
    SimpleBacktester,
    atr_trailing_signals,
    bollinger_signals,
    breakout_signals,
    macd_signals,
    momentum_signals,
    rsi_signals,
    signals_for,
    sma_crossover_signals,
)

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


def test_rsi_signals_enter_oversold_exit_overbought():
    # Sharp drop (RSI dips low -> enter long), then a sustained rally (RSI high -> exit).
    prices = [100, 98, 95, 90, 85, 80] + list(range(80, 130, 2))
    sig = rsi_signals(prices, period=5, low=35, high=65)
    assert len(sig) == len(prices)
    assert set(sig) <= {0.0, 1.0}
    assert 1.0 in sig                                          # took a long at some point


def test_breakout_signals_go_long_on_new_high():
    prices = [10] * 25 + [11, 12, 13]                         # flat then breaks out
    sig = breakout_signals(prices, lookback=20)
    assert len(sig) == len(prices)
    assert sig[:20] == [0.0] * 20                             # warm-up flat
    assert sig[-1] == 1.0                                     # long after the breakout


def test_macd_signals_long_in_uptrend():
    prices = list(range(1, 61))                              # steady uptrend
    sig = macd_signals(prices, fast=12, slow=26, signal=9)
    assert len(sig) == len(prices)
    assert set(sig) <= {0.0, 1.0}
    assert sig[:26] == [0.0] * 26                            # warm-up flat
    assert sig[-1] == 1.0                                    # MACD above signal in an uptrend


def test_bollinger_signals_buy_the_dip():
    prices = [100] * 25 + [80] + [100] * 5                   # a sharp dip below the lower band
    sig = bollinger_signals(prices, period=20, k=2.0)
    assert len(sig) == len(prices)
    assert set(sig) <= {0.0, 1.0}
    assert 1.0 in sig                                        # entered long on the dip


def test_signals_for_dispatch():
    prices = list(range(1, 61))
    assert signals_for("buy_hold", prices) == [1.0] * len(prices)
    assert signals_for("sma", prices, fast=5, slow=20) == sma_crossover_signals(prices, 5, 20)
    assert signals_for("rsi", prices, rsi_period=14) == rsi_signals(prices, 14, 30.0, 70.0)
    assert signals_for("breakout", prices, breakout_lookback=20) == breakout_signals(prices, 20)
    assert signals_for("macd", prices) == macd_signals(prices, 12, 26, 9)
    assert signals_for("bollinger", prices) == bollinger_signals(prices, 20, 2.0)
    assert signals_for("momentum", prices) == momentum_signals(prices, 20)
    assert signals_for("atr_trail", prices) == atr_trailing_signals(prices, 14, 3.0)


def test_momentum_long_in_uptrend():
    prices = list(range(1, 41))
    sig = momentum_signals(prices, lookback=20)
    assert sig[:20] == [0.0] * 20 and sig[-1] == 1.0


def test_atr_trailing_exits_on_crash():
    prices = list(range(100, 140)) + [139, 137, 120, 100, 90]   # uptrend then a crash
    sig = atr_trailing_signals(prices, period=14, mult=3.0)
    assert set(sig) <= {0.0, 1.0}
    assert 1.0 in sig            # was long in the uptrend
    assert sig[-1] == 0.0        # trailing stop flattened it in the crash
