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


# ---------------------------------------------------------------------------
# THE FACTOR PACK v0 (2026-08-21)
#
# Everything above answers "is this alpha or beta you already own" for a
# FINISHED return series. What the analyst and adversary seats kept needing was
# the raw material: the daily factor SERIES themselves, a rolling beta, and the
# residual left after taking a known exposure out. Those had no home, so each
# seat rebuilt them by hand from `marketdata/bars` — which is how two seats end
# up quoting different betas for the same pair.
#
# Pure read-and-compute. No thresholds, no verdicts, nothing that decides
# anything: every function here returns a number and the reason it might not
# have one, and the judgement stays with the reader.
#
# THE PROXIES ARE VERIFIED, NOT ASSUMED. Checked against the fund's own feed on
# 2026-08-21 (GET /fund/marketdata/bars, lookback_days=800):
#
#     SPY TLT DBC UUP XBI IBB GLD DBA IWM SRPT
#     551 bars each, 2024-06-10 .. 2026-08-20, source=alpaca
#
# So the dollar leg (UUP) and the biotech pair (XBI/IBB) are both available and
# both are included. A symbol the feed stops serving is reported ABSENT with its
# reason rather than dropped — a factor pack that quietly loses a leg produces a
# residual against a model nobody chose.

#: The premia legs, long-only. Each is a thing the fund could actually buy, so a
#: beta against one answers "could I have got this by owning something simple?".
PREMIA_PROXIES: dict[str, str] = {
    "mkt": "SPY",
    "duration": "TLT",
    "commodity": "DBC",
    "dollar": "UUP",
}

#: The biotech pair the SRPT revival condition is stated against — the first
#: named consumer of this pack. A single-name biotech's moves are mostly the
#: sector's; the question that decides a revival is what is left AFTER the
#: sector beta comes out, which is exactly `beta_adjusted_residual` below.
BIOTECH_PROXIES: dict[str, str] = {"xbi": "XBI", "ibb": "IBB"}

#: Below this many overlapping observations a beta is a line through noise.
#: Sixty trading days ~ one quarter, the same floor `MIN_OBS` uses above and for
#: the same reason; stated separately so a future change to one is a decision
#: about that one.
MIN_BETA_OBS = 60

#: Default rolling window. 63 trading days ~ one quarter — short enough that a
#: regime change shows up, long enough that a single gap day does not swing it.
#: A judgement, labelled as one; every caller may pass its own.
DEFAULT_BETA_WINDOW = 63


def daily_returns(closes: Sequence[float]) -> list[float]:
    """Simple daily returns from a close series.

    A close is usable only if it is finite AND strictly positive. Anything else
    is a BAD BAR: it produces no return and it breaks the chain, so the next
    good close is not differenced against it.

    That second half is deliberate and was caught in test. Treating a zero close
    as a price rather than as a fault emits a −100% return — arithmetically
    correct, and a fabricated catastrophe manufactured out of a data gap. It
    would then propagate into every beta, residual and rolling window built on
    the series. A skipped day produces NO return, which shortens the series;
    callers that need dates aligned should use `factor_series`, which intersects
    on dates rather than on position.
    """
    out: list[float] = []
    prev: float | None = None
    for c in closes or []:
        try:
            v = float(c)
        except (TypeError, ValueError):
            prev = None
            continue
        if not math.isfinite(v) or v <= 0.0:
            prev = None
            continue
        if prev is not None and prev > 0:
            out.append(v / prev - 1.0)
        prev = v
    return out


def factor_series(proxies: dict[str, str] | None = None,
                  lookback_days: int = 400,
                  fetcher: Callable[..., Any] = fetch_daily_bars,
                  ) -> dict[str, Any]:
    """Daily factor returns on a COMMON set of dates, plus what is missing.

    Returns ``{"factors": {key: [r, ...]}, "dates": [...], "symbols": {...},
    "absent": {key: reason}, "n_obs": int}``.

    `absent` is the load-bearing key. A leg the feed cannot serve is named with
    its reason and is NOT in `factors`; it is never zero-filled, and it never
    silently narrows the model. A caller regressing against three legs when it
    asked for four must be able to see that it did.
    """
    px = dict(proxies or PREMIA_PROXIES)
    used, rets, dates, excluded = aligned_returns(
        sorted(set(px.values())), lookback_days=lookback_days, fetcher=fetcher)
    have = set(used)
    factors: dict[str, list[float]] = {}
    absent: dict[str, str] = {}
    for key, sym in px.items():
        if sym in have:
            factors[key] = list(rets[sym])
        else:
            absent[key] = excluded.get(
                sym, f"{sym} was not served by the feed over this window")
    return {
        "factors": factors,
        "dates": list(dates),
        "symbols": px,
        "absent": absent,
        "n_obs": len(dates),
        "note": (f"{len(factors)} of {len(px)} legs available over "
                 f"{len(dates)} common dates"
                 + ("; ABSENT: " + ", ".join(f"{k} ({v})"
                                             for k, v in sorted(absent.items()))
                    if absent else "")),
    }


def beta(y: Sequence[float], x: Sequence[float]) -> dict[str, Any]:
    """Univariate beta of ``y`` on ``x``, or a stated reason there is none.

    Never returns 0.0 for "could not compute". A zero beta is a real and
    meaningful answer — it says the two are unrelated — so it must stay
    distinguishable from an absent one, which says nobody looked.
    """
    n = min(len(y or []), len(x or []))
    if n < MIN_BETA_OBS:
        return {"beta": None, "measurable": False, "n_obs": n,
                "reason": f"{n} overlapping observations, under the "
                          f"{MIN_BETA_OBS} a beta needs to be a measurement "
                          f"rather than a line through noise"}
    ya = np.asarray([float(v) for v in y[-n:]], dtype=float)
    xa = np.asarray([float(v) for v in x[-n:]], dtype=float)
    if not (np.all(np.isfinite(ya)) and np.all(np.isfinite(xa))):
        return {"beta": None, "measurable": False, "n_obs": n,
                "reason": "the series contain non-finite values — unmeasured, "
                          "which is not the same as zero"}
    var = float(np.var(xa, ddof=1))
    if var <= 0.0:
        return {"beta": None, "measurable": False, "n_obs": n,
                "reason": "the factor did not move over this window, so nothing "
                          "can be said about sensitivity to it"}
    cov = float(np.cov(ya, xa, ddof=1)[0, 1])
    b = cov / var
    alpha_daily = float(np.mean(ya) - b * np.mean(xa))
    y_var = float(np.var(ya, ddof=1))
    corr = (float(np.corrcoef(ya, xa)[0, 1]) if y_var > 0 else 0.0)
    return {
        "beta": round(b, 6),
        "alpha_daily": round(alpha_daily, 8),
        "alpha_annual_pct": round(alpha_daily * TRADING_DAYS * 100.0, 4),
        "r_squared": round(corr * corr, 4),
        "measurable": True, "n_obs": n, "reason": None,
    }


def rolling_beta(y: Sequence[float], x: Sequence[float],
                 window: int = DEFAULT_BETA_WINDOW) -> list[Any]:
    """Beta over a trailing window, aligned to ``y``'s index.

    Entries before the window fills are **None, not zero** — the single most
    important property of this function. A zero-padded head makes a chart open
    at "no exposure" and makes a mean over the series wrong by however many
    periods were padded, in the direction of "less exposed than we are".
    """
    n = min(len(y or []), len(x or []))
    w = max(2, int(window))
    out: list[Any] = [None] * n
    if n < w:
        return out
    ya = np.asarray([float(v) for v in y[:n]], dtype=float)
    xa = np.asarray([float(v) for v in x[:n]], dtype=float)
    for i in range(w - 1, n):
        ys, xs = ya[i - w + 1:i + 1], xa[i - w + 1:i + 1]
        if not (np.all(np.isfinite(ys)) and np.all(np.isfinite(xs))):
            continue
        var = float(np.var(xs, ddof=1))
        if var <= 0.0:
            continue
        out[i] = round(float(np.cov(ys, xs, ddof=1)[0, 1]) / var, 6)
    return out


def residual_series(y: Sequence[float], x: Sequence[float],
                    b: Any = None) -> dict[str, Any]:
    """``y`` with its exposure to ``x`` removed: e_t = y_t - beta * x_t.

    The part of a name's move that is NOT the sector's. Uses a full-sample beta
    unless one is supplied — a caller with a pre-registered beta should pass it,
    because re-fitting on the same window you are judging is how a residual
    becomes a curve fit.
    """
    fit = beta(y, x) if b is None else {"beta": float(b), "measurable": True,
                                        "n_obs": min(len(y or []), len(x or [])),
                                        "reason": None}
    if not fit.get("measurable"):
        return {"measurable": False, "reason": fit.get("reason"),
                "beta": None, "residuals": None,
                "cumulative_residual_pct": None}
    n = min(len(y), len(x))
    bb = float(fit["beta"])
    ys, xs = list(y[-n:]), list(x[-n:])
    res = [float(ys[i]) - bb * float(xs[i]) for i in range(n)]
    # Compounded, not summed: these are returns, and a sum overstates by the
    # cross terms — the same error that made retention divide cumulative windows.
    cum = 1.0
    for r in res:
        cum *= (1.0 + r)
    return {
        "measurable": True, "reason": None,
        "beta": round(bb, 6),
        "beta_source": "supplied" if b is not None else "fitted on this window",
        "n_obs": n,
        "residuals": [round(r, 8) for r in res],
        "cumulative_residual_pct": round((cum - 1.0) * 100.0, 4),
        "residual_vol_annual_pct": (
            round(float(np.std(np.asarray(res), ddof=1))
                  * math.sqrt(TRADING_DAYS) * 100.0, 4) if n > 1 else None),
    }


def beta_adjusted_residual(symbol: str, against: str = "XBI",
                           lookback_days: int = 400,
                           window: int = DEFAULT_BETA_WINDOW,
                           fetcher: Callable[..., Any] = fetch_daily_bars,
                           ) -> dict[str, Any]:
    """A name's move with its sector beta taken out — the SRPT revival shape.

    The first named consumer of this pack. SRPT was killed on a thesis whose
    revival condition is stated as a beta-adjusted residual against the biotech
    sector: a single-name biotech's moves are mostly XBI's, and what decides a
    revival is what is left after that comes out.

    Reports the full-sample beta AND the rolling one, because a residual is only
    as good as the beta that produced it: a name whose sector beta has drifted
    from 0.6 to 1.4 has no single residual worth quoting, and the rolling series
    is how a reader sees that before believing the number.

    Computes NOTHING about whether the condition is met. That is a judgement and
    it belongs to the seat that pre-registered it.
    """
    sym, ref = symbol.upper(), against.upper()
    used, rets, dates, excluded = aligned_returns(
        [sym, ref], lookback_days=lookback_days, fetcher=fetcher)
    have = set(used)
    miss = [s for s in (sym, ref) if s not in have]
    if miss:
        return {
            "measurable": False, "symbol": sym, "against": ref,
            "reason": "; ".join(
                f"{s}: {excluded.get(s, 'not served by the feed')}" for s in miss),
            "beta": None, "cumulative_residual_pct": None,
        }
    y, x = rets[sym], rets[ref]
    out = residual_series(y, x)
    roll = rolling_beta(y, x, window=window)
    seen = [b for b in roll if b is not None]
    return {
        "symbol": sym, "against": ref,
        "dates": list(dates),
        "window": window,
        "rolling_beta": roll,
        # None, not 0.0, when the window never filled — the whole point of the
        # rolling series returning Nones is that they survive the summary.
        "rolling_beta_min": round(min(seen), 4) if seen else None,
        "rolling_beta_max": round(max(seen), 4) if seen else None,
        "rolling_beta_last": seen[-1] if seen else None,
        "rolling_beta_note": (
            f"{len(seen)} of {len(roll)} points have a beta; the first "
            f"{window - 1} cannot have one and are ABSENT rather than zero"
            if roll else "no rolling beta could be computed"),
        **out,
    }
