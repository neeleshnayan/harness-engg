"""Modern risk measurement primitives.

The estimators a real risk desk uses, implemented over the fund's own realised
returns. Three choices here are deliberate and worth knowing about:

**Expected Shortfall, not VaR.** VaR answers "how bad is the 2.5% day?" and says
nothing about what lies beyond it — a strategy that loses $50 on a bad day and
$50,000 on a terrible one has the same VaR as one that loses $50 and $51. It is
also not subadditive, so it can report a merged book as riskier than its parts
and thereby penalise diversification. Basel's FRTB replaced 99% VaR with 97.5%
Expected Shortfall for exactly these reasons; we follow that, and report VaR
alongside only for reference.

**EWMA covariance, not just equal-weighted.** An equal-weighted 250-day
covariance treats a quiet day last October as informative as yesterday's
sell-off, so a volatility regime change takes months to appear. The RiskMetrics
exponentially-weighted estimator (lambda = 0.94 daily) reacts in days. We
compute both: the *gap* between them is itself the signal that the regime is
turning.

**Euler risk decomposition, not position size.** Capital weight is not risk
weight. A 20% position in a volatile, highly-correlated name can be 50% of the
book's risk. Euler's theorem splits portfolio volatility into per-position
contributions that sum exactly to the total, which is the only defensible way to
answer "what is actually driving our risk".

Everything is computed from observed returns. Nothing is assumed, proxied or
defaulted; where an estimate is unreliable the payload says so.
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import numpy as np

TRADING_DAYS = 252

#: RiskMetrics daily decay. 0.94 is J.P. Morgan's published daily parameter
#: (0.97 for monthly); it gives an effective memory of roughly 1/(1-lambda) ~ 17
#: days, which is why it turns much faster than an equal-weighted window.
RISKMETRICS_LAMBDA = 0.94

#: Expected Shortfall level mandated by Basel FRTB for the trading book.
FRTB_ES_LEVEL = 0.975

#: Historical simulation needs enough tail observations to mean anything. At
#: 97.5% you need ~40 days to have even one observation past the threshold.
MIN_OBS_FOR_TAIL = 100


def _matrix(returns_by_symbol: dict[str, Sequence[float]],
            symbols: Sequence[str]) -> np.ndarray:
    """(T x N) matrix of returns, truncated to the shortest common history."""
    if not symbols:
        return np.zeros((0, 0))
    t = min(len(returns_by_symbol[s]) for s in symbols)
    return np.array([list(returns_by_symbol[s])[-t:] for s in symbols], dtype=float).T


def ewma_covariance(returns: np.ndarray, lam: float = RISKMETRICS_LAMBDA) -> np.ndarray:
    """Exponentially-weighted covariance (RiskMetrics).

    Weights decay geometrically into the past: w_t proportional to lam^(T-1-t),
    normalised to sum to 1. Recent observations dominate, so a volatility regime
    shift shows up in days rather than being averaged away over the window.
    """
    t = returns.shape[0]
    if t < 2:
        return np.zeros((returns.shape[1], returns.shape[1]))
    ages = np.arange(t - 1, -1, -1, dtype=float)     # newest row -> age 0
    w = lam ** ages
    w /= w.sum()
    mu = np.average(returns, axis=0, weights=w)
    dev = returns - mu
    return (dev * w[:, None]).T @ dev


def sample_covariance(returns: np.ndarray) -> np.ndarray:
    """Equal-weighted sample covariance (ddof=1).

    ``np.cov`` collapses a single-column input to a 0-d scalar, which silently
    breaks every matrix operation downstream — and a one-position book is an
    entirely realistic state for a small fund. ``atleast_2d`` keeps the shape
    contract (N x N) at every N.
    """
    if returns.shape[0] < 2:
        return np.zeros((returns.shape[1], returns.shape[1]))
    return np.atleast_2d(np.cov(returns, rowvar=False, ddof=1))


def portfolio_vol(weights: np.ndarray, cov: np.ndarray, annualise: bool = True) -> float:
    var = float(weights @ cov @ weights)
    vol = math.sqrt(max(var, 0.0))
    return vol * math.sqrt(TRADING_DAYS) if annualise else vol


def risk_contributions(symbols: Sequence[str], weights: np.ndarray,
                       cov: np.ndarray) -> dict[str, Any]:
    """Euler decomposition of portfolio volatility.

        sigma_p       = sqrt(w' S w)
        MCTR_i        = (S w)_i / sigma_p        marginal: d sigma_p / d w_i
        CCTR_i        = w_i * MCTR_i             component, and sum(CCTR) == sigma_p

    The last identity is what makes this the defensible decomposition: the parts
    add up to the whole exactly, with no residual to explain away.

    ``risk_share_pct`` vs ``capital_weight_pct`` is the number to look at. When
    they diverge, the book is not allocated the way anyone intended — capital
    was split evenly and risk was not.
    """
    n = len(symbols)
    if n == 0:
        return {"measurable": False, "reason": "no positions"}
    sig_daily = math.sqrt(max(float(weights @ cov @ weights), 0.0))
    if sig_daily <= 1e-12:
        return {"measurable": False, "reason": "portfolio volatility is zero — "
                                               "no usable return variation in the window"}
    mctr = (cov @ weights) / sig_daily
    cctr = weights * mctr
    ann = math.sqrt(TRADING_DAYS)

    rows = []
    for i, s in enumerate(symbols):
        rows.append({
            "symbol": s,
            "capital_weight_pct": round(float(weights[i]) * 100.0, 2),
            "marginal_contribution": round(float(mctr[i]) * ann * 100.0, 4),
            "component_risk_pct": round(float(cctr[i]) * ann * 100.0, 4),
            "risk_share_pct": round(float(cctr[i] / sig_daily) * 100.0, 2),
        })
    for r in rows:
        r["risk_vs_capital_gap_pct"] = round(
            r["risk_share_pct"] - r["capital_weight_pct"], 2
        )
    rows.sort(key=lambda r: r["risk_share_pct"], reverse=True)

    # Residual should be ~0 by construction; report it so a silent maths error
    # cannot hide behind plausible-looking numbers.
    residual = float(cctr.sum() - sig_daily)

    return {
        "measurable": True,
        "portfolio_vol_pct": round(sig_daily * ann * 100.0, 2),
        "contributions": rows,
        "largest_risk_contributor": rows[0] if rows else None,
        "decomposition_residual": round(residual, 12),
        "concentration_of_risk_pct": round(rows[0]["risk_share_pct"], 2) if rows else 0.0,
    }


def historical_tail(port_returns: Sequence[float],
                    levels: Sequence[float] = (FRTB_ES_LEVEL, 0.99),
                    nav_usd: float | None = None) -> dict[str, Any]:
    """Historical-simulation VaR and Expected Shortfall — no distribution assumed.

    We sort the actual realised daily returns and read the quantile off the
    empirical distribution. That means fat tails and skew are included by
    construction, because they are in the data. The cost is that we can only see
    losses as bad as the worst day in the window: this method cannot extrapolate
    beyond observed history, and says so in ``caveats``.
    """
    r = np.array([x for x in port_returns if x is not None and np.isfinite(x)], dtype=float)
    n = r.size
    if n < MIN_OBS_FOR_TAIL:
        return {
            "measurable": False,
            "reason": f"{n} observations; need {MIN_OBS_FOR_TAIL} for a credible tail estimate",
            "n_obs": int(n),
        }

    out: dict[str, Any] = {"measurable": True, "n_obs": int(n), "levels": {}}
    for lvl in levels:
        # Loss convention: positive numbers are losses.
        losses = -r
        var = float(np.quantile(losses, lvl))
        tail = losses[losses >= var]
        es = float(tail.mean()) if tail.size else var
        entry = {
            "confidence": lvl,
            "var_pct": round(var * 100.0, 3),
            "expected_shortfall_pct": round(es * 100.0, 3),
            "tail_observations": int(tail.size),
        }
        if nav_usd:
            entry["var_usd"] = round(var * nav_usd, 2)
            entry["expected_shortfall_usd"] = round(es * nav_usd, 2)
        out["levels"][f"{lvl:.3f}"] = entry

    worst_idx = int(np.argmin(r))
    out["worst_day_pct"] = round(float(r[worst_idx]) * 100.0, 3)
    # Worst 5-day compounded stretch actually observed.
    if n >= 5:
        windows = [float(np.prod(1.0 + r[i:i + 5]) - 1.0) for i in range(n - 4)]
        out["worst_5day_pct"] = round(min(windows) * 100.0, 3)
        if nav_usd:
            out["worst_5day_usd"] = round(min(windows) * nav_usd, 2)
    if nav_usd:
        out["worst_day_usd"] = round(float(r[worst_idx]) * nav_usd, 2)

    out["headline"] = (
        f"Expected Shortfall {FRTB_ES_LEVEL:.1%}: on the worst 2.5% of days the average "
        f"loss is {out['levels'][f'{FRTB_ES_LEVEL:.3f}']['expected_shortfall_pct']:.2f}%"
        + (f" (${abs(out['levels'][f'{FRTB_ES_LEVEL:.3f}']['expected_shortfall_usd']):,.0f})"
           if nav_usd else "")
    )
    out["caveats"] = [
        "Historical simulation cannot see a loss larger than the worst day in its "
        f"window ({out['worst_day_pct']:.2f}%). A crisis worse than anything in the "
        "last year will exceed every number here.",
        "Expected Shortfall is reported at 97.5% because that is the Basel FRTB "
        "standard; VaR at the same level is shown only for comparison and should "
        "not be used to size risk — it ignores everything past the threshold.",
        "These are one-day figures at today's weights. They do not compound, and "
        "they assume the book is held unchanged.",
    ]
    return out


def loss_surface(symbols: Sequence[str], weights: np.ndarray, returns: np.ndarray,
                 port_returns: Sequence[float], nav_usd: float,
                 rho_steps: int = 21, max_horizon_days: int = 60,
                 horizon_steps: int = 20) -> dict[str, Any]:
    """Expected Shortfall as a surface over (correlation, holding horizon).

    Two axes, because the two questions a small fund actually faces are "what if
    these names stop being different" and "what if I am still holding this in a
    month". Neither is visible in a single ES number.

    Portfolio variance under an assumed uniform correlation rho, holding each
    name's own volatility at its measured level:

        var(rho) = sum_i w_i^2 s_i^2  +  rho * sum_{i != j} w_i w_j s_i s_j

    At rho = 1 this collapses to the weighted-average volatility — the
    phase-locking case where diversification has stopped existing. The book's
    *measured* correlation sits somewhere on this axis and is marked, so the
    surface reads as "here is where we are, and here is the cliff".

    The tail multiplier is NOT the textbook normal one (2.34). It is this book's
    own realised ES/sigma ratio, so the surface inherits the actual fat-tailedness
    of these holdings rather than assuming a bell curve. Horizon scaling uses
    sqrt(h), which assumes returns do not compound trends — stated in caveats.
    """
    n = len(symbols)
    if n == 0 or returns.shape[0] < MIN_OBS_FOR_TAIL:
        return {"measurable": False,
                "reason": "not enough history to build a loss surface"}

    sd = returns.std(axis=0, ddof=1)
    ws = weights * sd
    sum_sq = float((ws ** 2).sum())
    total_sq = float(ws.sum() ** 2)
    cross = total_sq - sum_sq          # sum over i != j of w_i w_j s_i s_j

    # Empirical tail multiplier: how many sigmas is this book's real 97.5% ES?
    pr = np.array([x for x in port_returns if x is not None and np.isfinite(x)], dtype=float)
    daily_sigma = float(pr.std(ddof=1)) if pr.size > 2 else 0.0
    multiplier = None
    if daily_sigma > 1e-12:
        losses = -pr
        var = float(np.quantile(losses, FRTB_ES_LEVEL))
        tail = losses[losses >= var]
        if tail.size:
            multiplier = float(tail.mean()) / daily_sigma
    if multiplier is None or not np.isfinite(multiplier) or multiplier <= 0:
        return {"measurable": False,
                "reason": "could not measure a tail multiplier from the book's returns"}

    # Where the book actually sits on the correlation axis today.
    measured_var = float(weights @ sample_covariance(returns) @ weights)
    measured_rho = None
    if cross > 1e-18:
        measured_rho = max(0.0, min(1.0, (measured_var - sum_sq) / cross))

    rhos = [i / (rho_steps - 1) for i in range(rho_steps)]
    horizons = [max(1, round(1 + i * (max_horizon_days - 1) / (horizon_steps - 1)))
                for i in range(horizon_steps)]

    z: list[list[float]] = []
    for h in horizons:
        row = []
        for rho in rhos:
            var_rho = max(sum_sq + rho * cross, 0.0)
            es = multiplier * math.sqrt(var_rho) * math.sqrt(h)
            row.append(round(es * nav_usd, 2))
        z.append(row)

    return {
        "measurable": True,
        "x_correlation": [round(r, 4) for r in rhos],
        "y_horizon_days": horizons,
        "z_loss_usd": z,
        "measured_correlation": round(measured_rho, 4) if measured_rho is not None else None,
        "tail_multiplier": round(multiplier, 3),
        "nav_usd": round(nav_usd, 2),
        "n_obs": int(returns.shape[0]),
        "axis_labels": {
            "x": "assumed average correlation",
            "y": "holding horizon (trading days)",
            "z": "expected shortfall (USD)",
        },
        "caveats": [
            f"the tail multiplier {multiplier:.2f} is measured from this book's own "
            "returns, not assumed normal (a normal distribution would give 2.34)",
            "horizon scales as sqrt(time), which assumes days are independent; a "
            "trending sell-off compounds and would exceed this",
            "each name keeps its own measured volatility — only the correlation "
            "between them is varied along the x axis",
        ],
    }


def vol_regime(returns: np.ndarray, weights: np.ndarray) -> dict[str, Any]:
    """Equal-weighted vs EWMA volatility for the same book.

    The ratio is a regime indicator: EWMA materially above the long window means
    the market has become more volatile than the year-long average admits, and
    every risk number built on the equal-weighted estimate is stale-low.
    """
    if returns.shape[0] < 2 or returns.shape[1] == 0:
        return {"measurable": False, "reason": "not enough return history"}
    slow = portfolio_vol(weights, sample_covariance(returns))
    fast = portfolio_vol(weights, ewma_covariance(returns))
    ratio = (fast / slow) if slow > 1e-12 else 1.0
    if ratio >= 1.25:
        verdict = ("recent volatility is well above the annual average — long-window "
                   "risk numbers understate today's risk")
    elif ratio <= 0.8:
        verdict = ("recent volatility is below the annual average — calm now, but the "
                   "long window is the better guide to what this book can do")
    else:
        verdict = "recent and long-run volatility broadly agree"
    return {
        "measurable": True,
        "equal_weighted_vol_pct": round(slow * 100.0, 2),
        "ewma_vol_pct": round(fast * 100.0, 2),
        "ratio": round(ratio, 3),
        "lambda": RISKMETRICS_LAMBDA,
        "verdict": verdict,
    }
