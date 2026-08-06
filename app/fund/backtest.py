"""Backtesting behind a seam — lightweight now, LEAN later if ever.

A strategy is a pure function ``prices -> signals`` (target position per bar, in
{-1, 0, 1}); a ``Backtester`` simulates those signals over the price series and
reports metrics. This is the Studio's backtest step (create → backtest → deploy).

No Docker, no CLI, no data subscription — it runs in-process. If institutional
fill/slippage modelling or options/futures backtests are ever needed, implement
the same ``Backtester`` protocol with LEAN; the Studio and registry don't change.

Backtest metrics are *analytics* (research), so plain floats are fine here —
this is not the accounting path (that stays Decimal).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass
class BacktestResult:
    total_return: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    final_equity: float
    bars: int

    def to_dict(self) -> dict:
        return {
            "total_return": round(self.total_return, 6),
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "n_trades": self.n_trades,
            "final_equity": round(self.final_equity, 6),
            "bars": self.bars,
        }


class Backtester(Protocol):
    def run(self, prices: Sequence[float], signals: Sequence[float]) -> BacktestResult: ...


class SimpleBacktester:
    """Vectorless, dependency-free simulation. ``signals[i]`` is the position held
    from bar i to bar i+1; equity compounds bar-returns × position."""

    def run(self, prices, signals, periods_per_year: int = 252) -> BacktestResult:
        if len(prices) < 2:
            return BacktestResult(0.0, 0.0, 0.0, 0, 1.0, len(prices))

        equity = 1.0
        curve = [1.0]
        rets = []
        trades = 0
        prev = 0.0
        for i in range(len(prices) - 1):
            sig = float(signals[i]) if i < len(signals) else 0.0
            bar_ret = (prices[i + 1] / prices[i] - 1.0) * sig
            equity *= (1.0 + bar_ret)
            curve.append(equity)
            rets.append(bar_ret)
            if sig != prev:
                trades += 1
                prev = sig

        total_return = equity - 1.0
        sharpe = 0.0
        if len(rets) > 1:
            sd = statistics.pstdev(rets)
            if sd > 0:
                sharpe = (statistics.mean(rets) / sd) * (periods_per_year ** 0.5)

        peak = curve[0]
        max_dd = 0.0
        for e in curve:
            peak = max(peak, e)
            max_dd = min(max_dd, e / peak - 1.0)

        return BacktestResult(total_return, sharpe, max_dd, trades, equity, len(prices))


def sma_crossover_signals(prices: Sequence[float], fast: int = 10, slow: int = 30) -> list[float]:
    """Long (1) when the fast SMA is above the slow SMA, else flat (0)."""
    out = []
    for i in range(len(prices)):
        if i + 1 < slow:
            out.append(0.0)
            continue
        f = sum(prices[i - fast + 1:i + 1]) / fast
        s = sum(prices[i - slow + 1:i + 1]) / slow
        out.append(1.0 if f > s else 0.0)
    return out
