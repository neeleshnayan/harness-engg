"""Factor attribution — is this alpha, or beta you already own?

The question that separates a strategy from a story. A backtest showing +40% in
a year when the market rose 35% has not found an edge; it has found leverage on
something you could have bought for nine basis points. Standalone Sharpe cannot
tell you which one you have. A regression against known factors can.

    r_t = alpha + sum_k beta_k * f_k,t + e_t

What matters in the output:

  * **alpha** — the part not explained by any factor, annualised, WITH a t-stat.
    An alpha of 4%/yr with t = 0.6 is not an alpha, it is noise wearing one.
  * **betas** — what you are actually exposed to. A "market neutral" strategy
    with market beta 0.8 is not market neutral.
  * **R-squared** — how much of the strategy IS the factors. High R-squared with
    zero alpha means the strategy is a repackaging you could buy cheaper.
  * **idiosyncratic share** — 1 - R-squared. The part that is genuinely yours.

The factors are built from liquid ETFs, long-short where the academic factor is
long-short. That is a deliberate, stated compromise: these are *tradeable
proxies*, not the Fama-French research factors, which are built from the full
cross-section of stocks and are not investable. The proxies answer the question
an operator actually has — "could I have got this exposure by buying something
simple?" — which is the more useful question anyway.
"""

from __future__ import annotations

import math
from typing import Any, Callable, Sequence

import numpy as np

from app.fund.correlation import aligned_returns
from app.fund.marketdata import fetch_daily_bars

TRADING_DAYS = 252

#: Each factor is a long leg minus an optional short leg. Where a factor is
#: naturally long-only (market, rates, commodity) the short leg is None.
FACTORS: tuple[dict[str, Any], ...] = (
    {"key": "market", "label": "Market", "long": "SPY", "short": None,
     "reads": "plain equity beta — the exposure you can buy for ~9bp"},
    {"key": "size", "label": "Size", "long": "IWM", "short": "SPY",
     "reads": "small-cap tilt (positive) vs large-cap tilt (negative)"},
    {"key": "value", "label": "Value", "long": "IWD", "short": "IWF",
     "reads": "value tilt (positive) vs growth tilt (negative)"},
    {"key": "momentum", "label": "Momentum", "long": "MTUM", "short": "SPY",
     "reads": "trend-following exposure beyond the market"},
    {"key": "rates", "label": "Rates", "long": "TLT", "short": None,
     "reads": "long-duration sensitivity — positive means you are long bonds"},
    {"key": "commodity", "label": "Commodity", "long": "GLD", "short": None,
     "reads": "gold / real-asset sensitivity"},
)

#: Below this, a regression on six factors is fitting noise.
MIN_OBS = 60


def _ols(y: np.ndarray, X: np.ndarray) -> dict[str, Any]:
    """OLS with an intercept prepended. Returns coefficients, standard errors,
    t-statistics and R-squared.

    Standard errors assume IID residuals. Financial residuals are usually
    heteroskedastic and mildly autocorrelated, which makes these t-stats a
    little generous — stated in the payload rather than silently ignored.
    """
    n = y.size
    design = np.column_stack([np.ones(n), X])
    k = design.shape[1]
    dof = n - k
    if dof <= 1:
        return {"usable": False, "reason": f"{n} observations for {k} parameters"}

    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    s2 = ss_res / dof
    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return {"usable": False, "reason": "factor matrix is singular — "
                                           "two factors are effectively identical here"}
    se = np.sqrt(np.maximum(np.diag(xtx_inv) * s2, 0.0))
    with np.errstate(divide="ignore", invalid="ignore"):
        t = np.where(se > 0, beta / se, 0.0)

    return {
        "usable": True,
        "beta": beta,
        "se": se,
        "t": t,
        "r_squared": (1.0 - ss_res / ss_tot) if ss_tot > 0 else 0.0,
        "dof": dof,
        "residuals": resid,
    }


class FactorModel:
    def __init__(self, fetcher: Callable[..., Any] = fetch_daily_bars,
                 factors: Sequence[dict] = FACTORS):
        self._fetch = fetcher
        self._factors = tuple(factors)

    def _legs(self) -> list[str]:
        out: set[str] = set()
        for f in self._factors:
            out.add(f["long"])
            if f["short"]:
                out.add(f["short"])
        return sorted(out)

    def factor_returns(self, lookback_days: int = 400) -> tuple[dict[str, list[float]], list[str], dict[str, str]]:
        """Daily factor returns on a common set of dates."""
        used, rets, dates, excluded = aligned_returns(
            self._legs(), lookback_days=lookback_days, fetcher=self._fetch
        )
        have = set(used)
        out: dict[str, list[float]] = {}
        missing: dict[str, str] = {}
        for f in self._factors:
            if f["long"] not in have or (f["short"] and f["short"] not in have):
                missing[f["key"]] = f"missing price history for {f['long']}" + (
                    f"/{f['short']}" if f["short"] else "")
                continue
            long_r = rets[f["long"]]
            if f["short"]:
                short_r = rets[f["short"]]
                n = min(len(long_r), len(short_r))
                out[f["key"]] = [long_r[i] - short_r[i] for i in range(n)]
            else:
                out[f["key"]] = list(long_r)
        return out, dates, {**missing, **{k: v for k, v in excluded.items()}}

    def analyse(self, returns: Sequence[float], dates: Sequence[str] | None = None,
                lookback_days: int = 400) -> dict[str, Any]:
        """Regress a return series on the factor set.

        ``dates`` must be the ISO date of each return. Without it the series is
        aligned to the most recent N factor observations, which is correct only
        if the series really does end today — so the payload says which
        alignment was used rather than leaving it ambiguous.
        """
        y_raw = [float(r) for r in (returns or [])
                 if r is not None and math.isfinite(float(r))]
        if len(y_raw) < MIN_OBS:
            return {"measurable": False,
                    "reason": f"{len(y_raw)} observations; a six-factor regression "
                              f"needs at least {MIN_OBS}"}

        f_rets, f_dates, missing = self.factor_returns(lookback_days)
        keys = [f["key"] for f in self._factors if f["key"] in f_rets]
        if len(keys) < 2:
            return {"measurable": False,
                    "reason": "not enough factor price history to build a model",
                    "missing": missing}

        if dates:
            idx = {d: i for i, d in enumerate(f_dates)}
            pairs = [(i, idx[d]) for i, d in enumerate(dates)
                     if d in idx and i < len(y_raw)]
            if len(pairs) < MIN_OBS:
                return {"measurable": False,
                        "reason": f"only {len(pairs)} dates overlap between the strategy "
                                  "and the factor series",
                        "missing": missing}
            y = np.array([y_raw[i] for i, _ in pairs], dtype=float)
            X = np.column_stack([[f_rets[k][j] for _, j in pairs] for k in keys])
            alignment = "matched on date"
        else:
            n = min(len(y_raw), min(len(f_rets[k]) for k in keys))
            y = np.array(y_raw[-n:], dtype=float)
            X = np.column_stack([f_rets[k][-n:] for k in keys])
            alignment = "aligned to the most recent common observations (no dates supplied)"

        fit = _ols(y, X)
        if not fit.get("usable"):
            return {"measurable": False, "reason": fit.get("reason"), "missing": missing}

        beta, se, t = fit["beta"], fit["se"], fit["t"]
        meta = {f["key"]: f for f in self._factors}
        rows = []
        for i, k in enumerate(keys, start=1):
            rows.append({
                "key": k,
                "label": meta[k]["label"],
                "proxy": meta[k]["long"] + (f" − {meta[k]['short']}" if meta[k]["short"] else ""),
                "beta": round(float(beta[i]), 4),
                "std_error": round(float(se[i]), 4),
                "t_stat": round(float(t[i]), 2),
                "significant": bool(abs(float(t[i])) >= 2.0),
                "reads": meta[k]["reads"],
            })
        rows.sort(key=lambda r: abs(r["beta"]), reverse=True)

        alpha_daily = float(beta[0])
        alpha_annual = alpha_daily * TRADING_DAYS
        alpha_t = float(t[0])
        r2 = float(fit["r_squared"])

        return {
            "measurable": True,
            "n_obs": int(y.size),
            "alignment": alignment,
            "missing_factors": missing,
            "alpha_daily": round(alpha_daily, 6),
            "alpha_annual_pct": round(alpha_annual * 100.0, 2),
            "alpha_t_stat": round(alpha_t, 2),
            "alpha_significant": bool(abs(alpha_t) >= 2.0),
            "r_squared": round(r2, 4),
            "idiosyncratic_share": round(1.0 - r2, 4),
            "factors": rows,
            "dominant_factor": rows[0] if rows else None,
            "verdict": self._verdict(alpha_annual, alpha_t, r2, rows),
            "caveats": [
                "Factors are liquid ETF proxies, not the Fama-French research "
                "factors — they answer 'could I have bought this exposure cheaply', "
                "which is the question that matters for a small fund.",
                "t-statistics assume IID residuals; real return residuals are "
                "heteroskedastic, so treat marginal significance (|t| near 2) as "
                "weaker than it looks.",
                f"Estimated over {int(y.size)} observations. Betas are not stable "
                "across regimes — a model fitted in a bull market says little about "
                "a crisis.",
            ],
        }

    @staticmethod
    def _verdict(alpha_annual: float, alpha_t: float, r2: float,
                 rows: list[dict]) -> list[str]:
        out: list[str] = []
        dom = rows[0] if rows else None
        if dom:
            out.append(
                f"Largest exposure is {dom['label'].lower()} (beta {dom['beta']:+.2f}"
                f", t {dom['t_stat']:+.1f}) via {dom['proxy']}."
            )
        out.append(
            f"{r2:.0%} of this strategy's variation is explained by the factor set; "
            f"{1 - r2:.0%} is idiosyncratic."
        )
        if abs(alpha_t) < 2.0:
            out.append(
                f"Alpha is {alpha_annual * 100:+.1f}%/yr but t = {alpha_t:+.1f} — "
                "not statistically distinguishable from zero. On this evidence the "
                "strategy is its factor exposures."
            )
        elif alpha_annual > 0:
            out.append(
                f"Alpha is {alpha_annual * 100:+.1f}%/yr with t = {alpha_t:+.1f} — "
                "significant on this sample. That is the part not available from "
                "the cheap exposures above."
            )
        else:
            out.append(
                f"Alpha is {alpha_annual * 100:+.1f}%/yr with t = {alpha_t:+.1f} — "
                "significantly NEGATIVE. The factor exposures alone would have done "
                "better than this strategy did."
            )
        if r2 > 0.85:
            out.append(
                "At this R-squared the strategy is close to a repackaging of its "
                "factors — check whether the fee and effort beat simply holding them."
            )
        return out


def eigen_factor_map(symbols: Sequence[str], returns: dict[str, list[float]],
                     weights: dict[str, float] | None = None,
                     n_components: int = 3) -> dict[str, Any]:
    """PCA of the book's own covariance — the *statistical* factors, unnamed.

    The regression above asks "are you exposed to factors we can name". This
    asks the complementary question: "how many distinct things is this book
    actually doing, and which holdings are doing the same one?"

    Positions are placed by their loading on the first components. Names that
    sit close together load on the same latent factor and are, statistically,
    the same bet — regardless of what sector or strategy they belong to.
    """
    syms = [s for s in symbols if s in returns and returns[s]]
    if len(syms) < 3:
        return {"measurable": False,
                "reason": f"{len(syms)} priced holdings; a factor map needs at least 3"}
    n = min(len(returns[s]) for s in syms)
    mat = np.array([returns[s][-n:] for s in syms], dtype=float).T
    if n < 40:
        return {"measurable": False, "reason": f"{n} observations; need 40"}

    # Correlation (not covariance) so a single volatile name does not define
    # every component purely by being loud.
    sd = mat.std(axis=0, ddof=1)
    sd[sd <= 0] = 1.0
    z = (mat - mat.mean(axis=0)) / sd
    corr = np.corrcoef(z, rowvar=False)
    vals, vecs = np.linalg.eigh(corr)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    total = float(vals.sum())
    k = min(n_components, len(syms))

    points = []
    for i, s in enumerate(syms):
        points.append({
            "symbol": s,
            "weight_pct": round(float((weights or {}).get(s, 0.0)), 2),
            "loadings": [round(float(vecs[i, c]), 4) for c in range(k)],
        })

    explained = [round(float(v / total), 4) for v in vals[:k]] if total > 0 else []
    cumulative = round(float(sum(vals[:k]) / total), 4) if total > 0 else 0.0
    return {
        "measurable": True,
        "symbols": syms,
        "n_obs": int(n),
        "n_components": k,
        "explained_variance": explained,
        "cumulative_explained": cumulative,
        "scree": [round(float(v / total), 4) for v in vals] if total > 0 else [],
        "points": points,
        "interpretation": [
            f"The first {k} statistical factors explain {cumulative:.0%} of how these "
            f"{len(syms)} holdings move."
            + (f" The first alone explains {explained[0]:.0%}." if explained else ""),
            "Holdings plotted close together load on the same latent factor — they "
            "are the same bet however different their tickers look.",
            "These components are statistical, not economic. They have no names and "
            "their composition drifts between regimes.",
        ],
    }
