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
from dataclasses import dataclass, field
from typing import Protocol, Sequence


@dataclass
class BacktestResult:
    total_return: float
    sharpe: float
    max_drawdown: float
    n_trades: int
    final_equity: float
    bars: int

    # --- research detail -------------------------------------------------
    # The simulation always produced these; it used to discard them, which made
    # a strategy tester impossible — you cannot show an equity curve, a drawdown
    # chart or a trade list from summary statistics alone.
    equity_curve: list[float] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    exposure_pct: float = 0.0      # share of bars actually holding a position
    volatility: float = 0.0        # annualised

    def to_dict(self, include_series: bool = True) -> dict:
        d = {
            "total_return": round(self.total_return, 6),
            "sharpe": round(self.sharpe, 4),
            "max_drawdown": round(self.max_drawdown, 6),
            "n_trades": self.n_trades,
            "final_equity": round(self.final_equity, 6),
            "bars": self.bars,
            "win_rate": round(self.win_rate, 4),
            "avg_win": round(self.avg_win, 6),
            "avg_loss": round(self.avg_loss, 6),
            "profit_factor": round(self.profit_factor, 4),
            "exposure_pct": round(self.exposure_pct, 4),
            "volatility": round(self.volatility, 6),
        }
        if include_series:
            d["equity_curve"] = [round(e, 6) for e in self.equity_curve]
            d["trades"] = self.trades
        return d


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
        bars_in_market = 0

        # A "trade" is a run of bars at one non-flat position. Recording entry
        # and exit lets the tester show what was actually done, not just how it
        # ended — the difference between a summary and a research tool.
        open_trade: dict | None = None
        closed: list[dict] = []

        def close_trade(at_index: int, at_price: float) -> None:
            nonlocal open_trade
            if open_trade is None:
                return
            entry = open_trade["entry_price"]
            direction = open_trade["position"]
            pnl_pct = ((at_price / entry) - 1.0) * direction if entry else 0.0
            open_trade.update({
                "exit_index": at_index,
                "exit_price": round(at_price, 6),
                "pnl_pct": round(pnl_pct * 100.0, 4),
                "bars_held": at_index - open_trade["entry_index"],
            })
            closed.append(open_trade)
            open_trade = None

        for i in range(len(prices) - 1):
            sig = float(signals[i]) if i < len(signals) else 0.0
            bar_ret = (prices[i + 1] / prices[i] - 1.0) * sig
            equity *= (1.0 + bar_ret)
            curve.append(equity)
            rets.append(bar_ret)
            if sig != 0.0:
                bars_in_market += 1

            if sig != prev:
                trades += 1
                close_trade(i, float(prices[i]))
                if sig != 0.0:
                    open_trade = {
                        "entry_index": i,
                        "entry_price": round(float(prices[i]), 6),
                        "position": 1 if sig > 0 else -1,
                        "side": "long" if sig > 0 else "short",
                    }
                prev = sig

        close_trade(len(prices) - 1, float(prices[-1]))

        total_return = equity - 1.0
        sharpe = 0.0
        vol = 0.0
        if len(rets) > 1:
            sd = statistics.pstdev(rets)
            vol = sd * (periods_per_year ** 0.5)
            if sd > 0:
                sharpe = (statistics.mean(rets) / sd) * (periods_per_year ** 0.5)

        peak = curve[0]
        max_dd = 0.0
        for e in curve:
            peak = max(peak, e)
            max_dd = min(max_dd, e / peak - 1.0)

        wins = [t["pnl_pct"] for t in closed if t["pnl_pct"] > 0]
        losses = [t["pnl_pct"] for t in closed if t["pnl_pct"] < 0]
        gross_win, gross_loss = sum(wins), abs(sum(losses))

        return BacktestResult(
            total_return=total_return,
            sharpe=sharpe,
            max_drawdown=max_dd,
            n_trades=trades,
            final_equity=equity,
            bars=len(prices),
            equity_curve=curve,
            trades=closed,
            win_rate=(len(wins) / len(closed)) if closed else 0.0,
            avg_win=(gross_win / len(wins)) if wins else 0.0,
            avg_loss=(-gross_loss / len(losses)) if losses else 0.0,
            # no losses at all is not "infinitely profitable" — report 0 and let
            # the caller see n_trades rather than print an inf
            profit_factor=(gross_win / gross_loss) if gross_loss > 0 else 0.0,
            exposure_pct=(bars_in_market / max(1, len(prices) - 1)) * 100.0,
            volatility=vol,
        )


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


def _rsi(prices: Sequence[float], period: int = 14) -> list[float]:
    """Simple (SMA-based) RSI series aligned to ``prices``; warm-up bars are 50 (neutral)."""
    rsis = [50.0] * len(prices)
    if len(prices) <= period:
        return rsis
    gains, losses = [], []
    for i in range(1, len(prices)):
        ch = prices[i] - prices[i - 1]
        gains.append(max(ch, 0.0))
        losses.append(max(-ch, 0.0))
    # gains[j] corresponds to the move into prices[j+1]
    for i in range(period, len(prices)):
        ag = sum(gains[i - period:i]) / period
        al = sum(losses[i - period:i]) / period
        rsis[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return rsis


def rsi_signals(prices: Sequence[float], period: int = 14,
                low: float = 30.0, high: float = 70.0) -> list[float]:
    """Mean-reversion: go long when RSI dips below ``low``; exit when RSI rises above ``high``."""
    rsi = _rsi(prices, period)
    out, pos = [], 0.0
    for i in range(len(prices)):
        if pos == 0.0 and rsi[i] < low:
            pos = 1.0
        elif pos == 1.0 and rsi[i] > high:
            pos = 0.0
        out.append(pos)
    return out


def breakout_signals(prices: Sequence[float], lookback: int = 20) -> list[float]:
    """Donchian breakout: long when price breaks the prior ``lookback`` high; exit below the prior low."""
    out, pos = [], 0.0
    for i in range(len(prices)):
        if i < lookback:
            out.append(0.0)
            continue
        window = prices[i - lookback:i]
        if prices[i] >= max(window):
            pos = 1.0
        elif prices[i] <= min(window):
            pos = 0.0
        out.append(pos)
    return out


def _ema(prices: Sequence[float], span: int) -> list[float]:
    """Exponential moving average seeded on the first price."""
    if not prices:
        return []
    k = 2.0 / (span + 1)
    out = [float(prices[0])]
    for p in prices[1:]:
        out.append(out[-1] + k * (float(p) - out[-1]))
    return out


def macd_signals(prices: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> list[float]:
    """Trend: long when the MACD line is above its signal line, else flat."""
    n = len(prices)
    if n < slow:
        return [0.0] * n
    ef, es = _ema(prices, fast), _ema(prices, slow)
    macd = [ef[i] - es[i] for i in range(n)]
    sig = _ema(macd, signal)
    return [0.0 if i < slow else (1.0 if macd[i] > sig[i] else 0.0) for i in range(n)]


def bollinger_signals(prices: Sequence[float], period: int = 20, k: float = 2.0) -> list[float]:
    """Mean-reversion: long when price closes below the lower band; exit at the mid band."""
    out, pos = [], 0.0
    for i in range(len(prices)):
        if i + 1 < period:
            out.append(0.0)
            continue
        window = prices[i - period + 1:i + 1]
        mid = sum(window) / period
        sd = statistics.pstdev(window)
        if prices[i] <= mid - k * sd:
            pos = 1.0
        elif prices[i] >= mid:
            pos = 0.0
        out.append(pos)
    return out


def momentum_signals(prices: Sequence[float], lookback: int = 20) -> list[float]:
    """Time-series momentum: long when price is above its value ``lookback`` bars ago."""
    out = []
    for i in range(len(prices)):
        out.append(1.0 if i >= lookback and prices[i] > prices[i - lookback] else 0.0)
    return out


def atr_trailing_signals(prices: Sequence[float], period: int = 14, mult: float = 3.0) -> list[float]:
    """Ride the trend with a close-to-close ATR trailing stop: exit when price falls
    ``mult``×ATR below the running peak; re-enter on a fresh high."""
    n = len(prices)
    out, pos, peak = [], 0.0, prices[0] if prices else 0.0
    for i in range(n):
        if i < period:
            out.append(0.0)
            continue
        atr = sum(abs(prices[j] - prices[j - 1]) for j in range(i - period + 1, i + 1)) / period
        if pos == 0.0:
            if prices[i] >= peak:          # (re)enter long on a new high
                pos, peak = 1.0, prices[i]
        else:
            peak = max(peak, prices[i])
            if prices[i] <= peak - mult * atr:
                pos = 0.0                  # trailing stop hit -> flat
        out.append(pos)
    return out


def signals_for(strategy: str, prices: Sequence[float], *, fast: int = 10, slow: int = 30,
                rsi_period: int = 14, rsi_low: float = 30.0, rsi_high: float = 70.0,
                breakout_lookback: int = 20, macd_fast: int = 12, macd_slow: int = 26,
                macd_signal: int = 9, boll_period: int = 20, boll_k: float = 2.0,
                momentum_lookback: int = 20, atr_period: int = 14, atr_mult: float = 3.0) -> list[float]:
    """Dispatch a built-in strategy name to its signal series."""
    if strategy == "sma":
        return sma_crossover_signals(prices, fast, slow)
    if strategy == "rsi":
        return rsi_signals(prices, rsi_period, rsi_low, rsi_high)
    if strategy == "breakout":
        return breakout_signals(prices, breakout_lookback)
    if strategy == "macd":
        return macd_signals(prices, macd_fast, macd_slow, macd_signal)
    if strategy == "bollinger":
        return bollinger_signals(prices, boll_period, boll_k)
    if strategy == "momentum":
        return momentum_signals(prices, momentum_lookback)
    if strategy == "atr_trail":
        return atr_trailing_signals(prices, atr_period, atr_mult)
    return [1.0] * len(prices)  # buy_hold
