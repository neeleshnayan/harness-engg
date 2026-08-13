"""The full research tearsheet for a backtest.

``BacktestResult`` reports what a run *did*: return, Sharpe, drawdown, trades.
That is enough to rank two runs and nowhere near enough to decide whether a run
means anything. This module answers the second question, and it is deliberately
organised around the three ways a good-looking backtest lies:

  1. **It was never risk-adjusted honestly.** A 117% return with a 52% drawdown
     and Sharpe 0.41 is not a good strategy, it is leverage. Sortino, Calmar and
     drawdown *recovery* say what the return cost to obtain.
  2. **It never had to beat the alternative.** Alpha, beta, tracking error and
     information ratio against a benchmark separate skill from exposure. A beta
     of 1.45 in a bull market explains most "edges".
  3. **It is one draw from a distribution.** PSR says how likely the true Sharpe
     is above zero at all; the selection penalty says what the best of N noise
     runs would have looked like. Both live in :mod:`app.fund.statistics`; this
     module wires them to a backtest so they cannot be skipped.

Every metric returns ``None`` with a stated reason when the sample cannot support
it. A tearsheet full of zeros for a 12-bar backtest is worse than an empty one,
because zeros look like findings.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

from app.fund.statistics import (
    annualisation_factor,
    kurtosis,
    mean_std,
    min_track_record_length,
    probabilistic_sharpe_ratio,
    selection_penalty,
    sharpe_confidence_interval,
    skewness,
)

#: Below this, ratios computed from the sample are noise dressed as numbers.
MIN_BARS_FOR_RATIOS = 20

#: Rolling windows, in trading days. Named the way an operator thinks about them.
ROLLING_WINDOWS = [("1m", 21), ("3m", 63), ("6m", 126), ("1y", 252)]


def _returns_from_curve(curve: Sequence[float]) -> list[float]:
    """Period returns from an equity curve, skipping any non-positive level.

    A zero or negative equity level means the account is wiped out; dividing
    through it produces an infinity that then poisons every downstream mean.
    """
    out: list[float] = []
    for prev, cur in zip(curve, curve[1:]):
        p = float(prev)
        if p > 0:
            r = float(cur) / p - 1.0
            if math.isfinite(r):
                out.append(r)
    return out


def _downside_deviation(returns: Sequence[float], mar: float = 0.0) -> float | None:
    """Root-mean-square of returns BELOW the minimum acceptable return.

    Divided by the full observation count, not by the count of losing periods —
    dividing by the losers alone would make a strategy that rarely loses look
    riskier the fewer times it lost, which is backwards.
    """
    rs = [float(r) for r in returns if math.isfinite(float(r))]
    if len(rs) < 2:
        return None
    shortfalls = [min(0.0, r - mar) ** 2 for r in rs]
    return math.sqrt(sum(shortfalls) / len(rs))


def drawdown_profile(curve: Sequence[float]) -> dict[str, Any]:
    """The worst drawdown, and — the part usually left out — how long it took to
    come back.

    Depth alone is only half of the pain. A 20% drawdown recovered in a month and
    a 20% drawdown that took three years are different strategies, and only one
    of them keeps its investors. Where the curve never regains its high, we say
    so instead of quietly reporting the recovery as of the last bar.
    """
    levels = [float(e) for e in curve if math.isfinite(float(e))]
    if len(levels) < 2:
        return {"measurable": False, "reason": "fewer than 2 equity points"}

    peak = levels[0]
    peak_i = 0
    worst = 0.0
    worst_peak_i = worst_trough_i = 0
    for i, e in enumerate(levels):
        if e > peak:
            peak, peak_i = e, i
        dd = (e / peak - 1.0) if peak > 0 else 0.0
        if dd < worst:
            worst, worst_peak_i, worst_trough_i = dd, peak_i, i

    if worst == 0.0:
        return {
            "measurable": True,
            "max_drawdown_pct": 0.0,
            "peak_index": 0,
            "trough_index": 0,
            "recovery_index": None,
            "recovery_bars": None,
            "underwater_bars": 0,
            "still_underwater": False,
            "note": "equity never fell below a prior high over this window",
        }

    peak_level = levels[worst_peak_i]
    recovery_i = None
    for j in range(worst_trough_i + 1, len(levels)):
        if levels[j] >= peak_level:
            recovery_i = j
            break

    return {
        "measurable": True,
        "max_drawdown_pct": round(worst * 100.0, 4),
        "peak_index": worst_peak_i,
        "trough_index": worst_trough_i,
        "recovery_index": recovery_i,
        "recovery_bars": (recovery_i - worst_trough_i) if recovery_i is not None else None,
        "underwater_bars": (recovery_i - worst_peak_i) if recovery_i is not None
                           else (len(levels) - 1 - worst_peak_i),
        "still_underwater": recovery_i is None,
        "note": ("never recovered its prior high within this window"
                 if recovery_i is None else
                 f"took {recovery_i - worst_trough_i} bars to regain the prior high"),
    }


def benchmark_relative(strategy_returns: Sequence[float],
                       benchmark_returns: Sequence[float],
                       periods_per_year: int = 252,
                       rf_per_period: float = 0.0) -> dict[str, Any]:
    """Alpha, beta and the tracking statistics, by OLS against a benchmark.

    The point of this block is to make exposure and skill impossible to confuse.
    A strategy that is long the index 80% of the time will post a fine Sharpe in
    a rising market; beta reveals it, and alpha is what is left after beta has
    been paid for.

    Alpha is reported annualised but built from *arithmetic* per-period means
    (Jensen's alpha), which is what the regression estimates — compounding it
    would be a different quantity wearing the same name.
    """
    rs = [float(r) for r in strategy_returns if math.isfinite(float(r))]
    rb = [float(r) for r in benchmark_returns if math.isfinite(float(r))]
    n = min(len(rs), len(rb))
    if n < MIN_BARS_FOR_RATIOS:
        return {"measurable": False,
                "reason": f"{n} aligned observations, need {MIN_BARS_FOR_RATIOS}"}
    rs, rb = rs[:n], rb[:n]

    mean_s, _ = mean_std(rs)
    mean_b, sd_b = mean_std(rb)
    if sd_b <= 0:
        return {"measurable": False, "reason": "benchmark has zero variance over this window"}

    cov = sum((a - mean_s) * (b - mean_b) for a, b in zip(rs, rb)) / (n - 1)
    beta = cov / (sd_b ** 2)
    alpha_per_period = (mean_s - rf_per_period) - beta * (mean_b - rf_per_period)

    # R^2 of the single-factor fit: how much of the strategy is just the benchmark.
    _, sd_s = mean_std(rs)
    corr = (cov / (sd_s * sd_b)) if sd_s > 0 else 0.0
    r2 = corr ** 2

    active = [a - b for a, b in zip(rs, rb)]
    mean_a, sd_a = mean_std(active)
    tracking_error = sd_a * math.sqrt(periods_per_year)
    info_ratio = (mean_a / sd_a) * math.sqrt(periods_per_year) if sd_a > 0 else None
    treynor = (((mean_s - rf_per_period) * periods_per_year) / beta) if beta != 0 else None

    return {
        "measurable": True,
        "n_obs": n,
        "beta": round(beta, 4),
        "alpha_annual_pct": round(alpha_per_period * periods_per_year * 100.0, 4),
        "correlation": round(corr, 4),
        "r_squared": round(r2, 4),
        "idiosyncratic_share": round(1.0 - r2, 4),
        "tracking_error_pct": round(tracking_error * 100.0, 4),
        "information_ratio": round(info_ratio, 4) if info_ratio is not None else None,
        "treynor_ratio": round(treynor, 4) if treynor is not None else None,
        "assumes": "single-factor OLS on aligned periods; alpha is arithmetic (Jensen), "
                   "annualised by scaling not compounding",
    }


def rolling_windows(returns: Sequence[float], periods_per_year: int = 252,
                    windows: Sequence[tuple[str, int]] = tuple(ROLLING_WINDOWS)) -> list[dict]:
    """Rolling return and Sharpe for each window that the sample can support.

    A single headline Sharpe over five years hides whether the edge was present
    throughout or arrived entirely in one quarter. Windows longer than the sample
    are omitted rather than computed on a truncated slice and labelled "1y".
    """
    rs = [float(r) for r in returns if math.isfinite(float(r))]
    out: list[dict] = []
    for label, w in windows:
        if len(rs) < w + 1:
            out.append({"label": label, "window_bars": w, "measurable": False,
                        "reason": f"{len(rs)} observations, window needs {w + 1}"})
            continue
        rets: list[float] = []
        sharpes: list[float | None] = []
        for end in range(w, len(rs) + 1):
            chunk = rs[end - w:end]
            compounded = 1.0
            for r in chunk:
                compounded *= (1.0 + r)
            rets.append(round((compounded - 1.0) * 100.0, 4))
            m, sd = mean_std(chunk)
            sharpes.append(round((m / sd) * math.sqrt(periods_per_year), 4) if sd > 0 else None)
        finite = [s for s in sharpes if s is not None]
        out.append({
            "label": label,
            "window_bars": w,
            "measurable": True,
            "first_index": w,
            "return_pct": rets,
            "sharpe": sharpes,
            "worst_return_pct": min(rets),
            "best_return_pct": max(rets),
            "share_positive": round(sum(1 for r in rets if r > 0) / len(rets), 4),
            "median_sharpe": round(sorted(finite)[len(finite) // 2], 4) if finite else None,
        })
    return out


def trade_expectancy(trades: Sequence[dict]) -> dict[str, Any]:
    """Expectancy per trade, in percent, decomposed into its parts.

    Expectancy is win_rate * avg_win + loss_rate * avg_loss. It is reported with
    both halves visible because the same expectancy is produced by "wins often,
    small" and "wins rarely, huge", and those two demand completely different
    position sizing and tolerance for a losing streak.
    """
    rows = [t for t in (trades or []) if t.get("pnl_pct") is not None]
    if not rows:
        return {"measurable": False, "reason": "no closed trades"}
    pnl = [float(t["pnl_pct"]) for t in rows]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p < 0]
    n = len(pnl)
    win_rate = len(wins) / n
    loss_rate = len(losses) / n
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0
    held = [float(t["bars_held"]) for t in rows if t.get("bars_held") is not None]
    return {
        "measurable": True,
        "n_trades": n,
        "win_rate": round(win_rate, 4),
        "loss_rate": round(loss_rate, 4),
        "avg_win_pct": round(avg_win, 4),
        "avg_loss_pct": round(avg_loss, 4),
        "expectancy_pct": round(win_rate * avg_win + loss_rate * avg_loss, 4),
        "payoff_ratio": round(avg_win / abs(avg_loss), 4) if avg_loss < 0 else None,
        "best_trade_pct": round(max(pnl), 4),
        "worst_trade_pct": round(min(pnl), 4),
        "avg_bars_held": round(sum(held) / len(held), 2) if held else None,
        # A single trade carrying the whole result is the most common way a
        # backtest is really a story about one lucky week.
        "top_trade_share_of_gross_profit": (
            round(max(wins) / sum(wins), 4) if wins and sum(wins) > 0 else None
        ),
    }


def build(equity_curve: Sequence[float],
          *,
          benchmark_curve: Sequence[float] | None = None,
          benchmark_label: str = "buy & hold",
          trades: Sequence[dict] | None = None,
          signals: Sequence[float] | None = None,
          periods_per_year: int = 252,
          n_trials: int = 1,
          rf_annual: float = 0.0) -> dict[str, Any]:
    """The whole tearsheet for one backtest.

    ``n_trials`` is the number of configurations tried to arrive at this one. It
    defaults to 1, which is the honest value only when a single configuration was
    ever run; pass the real sweep size or the selection penalty understates.
    """
    curve = [float(e) for e in (equity_curve or []) if math.isfinite(float(e))]
    if len(curve) < 2:
        return {"measurable": False, "reason": "fewer than 2 equity points",
                "bars": len(curve)}

    rets = _returns_from_curve(curve)
    n = len(rets)
    years = n / float(periods_per_year) if periods_per_year else 0.0
    rf_per_period = rf_annual / float(periods_per_year) if periods_per_year else 0.0

    total_return = curve[-1] / curve[0] - 1.0
    cagr = None
    if years > 0 and curve[0] > 0 and curve[-1] > 0:
        cagr = (curve[-1] / curve[0]) ** (1.0 / years) - 1.0

    mean_r, sd_r = mean_std(rets)
    vol_annual = sd_r * math.sqrt(periods_per_year) if n >= 2 else None

    # Sharpe is annualised through the serial-correlation-aware factor, not a
    # bare sqrt(252): positive autocorrelation makes sqrt(q) OVERSTATE the ratio,
    # and trend-following returns are positively autocorrelated by construction.
    ann = annualisation_factor(rets, periods_per_year=periods_per_year)
    sharpe_per_period = ((mean_r - rf_per_period) / sd_r) if sd_r > 0 else None
    sharpe_annual = None
    if sharpe_per_period is not None:
        factor = ann.get("factor") or math.sqrt(periods_per_year)
        sharpe_annual = sharpe_per_period * factor

    dsd = _downside_deviation(rets, mar=rf_per_period)
    sortino = None
    if dsd and dsd > 0:
        sortino = ((mean_r - rf_per_period) / dsd) * math.sqrt(periods_per_year)

    dd = drawdown_profile(curve)
    calmar = None
    if cagr is not None and dd.get("measurable") and dd.get("max_drawdown_pct"):
        depth = abs(float(dd["max_drawdown_pct"])) / 100.0
        if depth > 0:
            calmar = cagr / depth

    # Turnover: how much of the book is traded, annualised. A strategy whose edge
    # is smaller than its turnover cost does not have an edge, and turnover is
    # the input that decides that.
    turnover = None
    if signals:
        sig = [float(s) for s in signals if math.isfinite(float(s))]
        if len(sig) >= 2:
            traded = sum(abs(b - a) for a, b in zip(sig, sig[1:]))
            turnover = (traded / len(sig)) * periods_per_year

    bench = {"measurable": False, "reason": "no benchmark supplied"}
    if benchmark_curve is not None:
        bench = benchmark_relative(rets, _returns_from_curve(benchmark_curve),
                                   periods_per_year=periods_per_year,
                                   rf_per_period=rf_per_period)
        bench["label"] = benchmark_label

    # Inference is on the ANNUAL base: an annual Sharpe with T in years. Feeding
    # a daily count to an annual estimate is the classic way to shrink an error
    # bar by a factor of sixteen.
    inference: dict[str, Any] = {"measurable": False,
                                 "reason": f"{n} observations is too few to infer from"}
    if sharpe_annual is not None and n >= 2:
        n_years = max(years, 0.0)
        inference = {
            "measurable": True,
            "basis": "annual Sharpe with T measured in years",
            "n_years": round(n_years, 4),
            "confidence_interval": sharpe_confidence_interval(sharpe_annual, max(int(n_years), 2)),
            "psr": probabilistic_sharpe_ratio(sharpe_per_period, n, returns=rets),
            "min_track_record": min_track_record_length(sharpe_per_period, n, returns=rets),
            "selection": selection_penalty(sharpe_annual, n_trials, max(int(n_years), 2)),
        }

    return {
        "measurable": True,
        "bars": len(curve),
        "observations": n,
        "years": round(years, 4),
        "periods_per_year": periods_per_year,

        "returns": {
            "total_return_pct": round(total_return * 100.0, 4),
            "cagr_pct": round(cagr * 100.0, 4) if cagr is not None else None,
            "final_equity": round(curve[-1], 6),
        },
        "risk": {
            "volatility_annual_pct": round(vol_annual * 100.0, 4) if vol_annual is not None else None,
            "downside_deviation_annual_pct": (
                round(dsd * math.sqrt(periods_per_year) * 100.0, 4) if dsd is not None else None
            ),
            "skew": round(skewness(rets), 4) if n >= 3 else None,
            "kurtosis": round(kurtosis(rets), 4) if n >= 4 else None,
            "worst_period_pct": round(min(rets) * 100.0, 4) if rets else None,
            "best_period_pct": round(max(rets) * 100.0, 4) if rets else None,
        },
        "ratios": {
            "sharpe_annual": round(sharpe_annual, 4) if sharpe_annual is not None else None,
            "sortino_annual": round(sortino, 4) if sortino is not None else None,
            "calmar": round(calmar, 4) if calmar is not None else None,
            "annualisation": ann,
        },
        "drawdown": dd,
        "turnover_annual": round(turnover, 4) if turnover is not None else None,
        "trades": trade_expectancy(trades or []),
        "benchmark": bench,
        "inference": inference,
    }
