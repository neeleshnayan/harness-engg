"""Market regime and systemic fragility.

Position limits and drawdown halts are *reactive*: they fire once the damage is
in the NAV. This module is the forward-looking half — two published indicators
that measure whether the market itself is becoming dangerous, before the book
has lost anything.

**Financial Turbulence** (Chow, Jacquier, Kritzman & Lowrey 1999; Kritzman & Li
2010). The Mahalanobis distance of today's cross-section of returns from its
historical joint distribution:

    d_t = (r_t - mu)' * S^-1 * (r_t - mu)

It is not "how big was the move" — it is "how *unusual* was this combination of
moves, given how these assets normally move together". A day where everything
falls 1% together can be far more turbulent than a day where one name falls 5%,
because the first breaks the correlation structure and the second does not.
Turbulence is persistent, and returns to risk-taking are historically poor while
it is elevated.

**Absorption Ratio** (Kritzman, Li, Page & Rigobon 2010). The fraction of total
variance across a broad asset set that is absorbed by its few largest
eigenvectors:

    AR = sum(largest n eigenvalues) / sum(all N eigenvalues)

A high ratio means the market has become tightly coupled — few independent
sources of risk — and shocks propagate across everything instead of being
contained. Their central empirical finding is about the *shift*, not the level:
a standardised rise in AR precedes drawdowns, and calm follows a fall.

Both are computed over a basket of liquid sector ETFs, NOT the fund's own
holdings. That is deliberate: a four-name book cannot tell you anything about
market-wide coupling, and using it to try would be measuring our own portfolio
and calling it the market. Turbulence is *also* computed on the book itself,
where it answers a different and equally useful question — is today unusual for
*us*.
"""

from __future__ import annotations

import math
import time
from typing import Any, Callable, Sequence

import numpy as np

from app.fund.correlation import aligned_returns
from app.fund.marketdata import fetch_daily_bars

#: SPDR sector ETFs — a standard, liquid, free-to-fetch decomposition of the US
#: equity market. Broad enough that "how coupled is the market" is a real
#: question about the market rather than about one portfolio.
SECTOR_BASKET = (
    "XLK",   # technology
    "XLF",   # financials
    "XLE",   # energy
    "XLV",   # health care
    "XLI",   # industrials
    "XLY",   # consumer discretionary
    "XLP",   # consumer staples
    "XLU",   # utilities
    "XLB",   # materials
    "XLRE",  # real estate
    "XLC",   # communication services
)

#: Kritzman et al. estimate eigenvectors over a long trailing window; we need
#: this much history plus a year of rolling values to standardise the shift.
AR_WINDOW = 500
AR_HISTORY = 250
REGIME_LOOKBACK_DAYS = 1500

#: Equation (1)'s variances are exponentially weighted, with a half-life of half
#: the estimation window (250 days) — the paper's assumption that the market's
#: memory of old events fades rather than dropping out of a rectangular window.
AR_HALFLIFE = AR_WINDOW / 2.0
AR_LAMBDA = 0.5 ** (1.0 / AR_HALFLIFE)

#: Equation (2): dAR = (AR_15day - AR_1year) / sigma(AR_1year). A +1 sigma shift
#: is their signal. Over 1998-2010 every one of the 1% worst monthly drawdowns
#: was preceded by one — which makes it close to a necessary condition for a
#: crash, and emphatically NOT a sufficient one. Stocks often rose after a spike.
AR_SHIFT_WINDOW = 15
AR_SHIFT_THRESHOLD = 1.0

#: Exhibit 8 — fraction of worst drawdowns preceded by a +1 sigma AR shift, and
#: Exhibit 9 — annualised returns following one. Carried here so the UI can state
#: the base rates instead of implying the indicator is a forecast.
AR_EMPIRICAL = {
    "source": "Kritzman, Li, Page & Rigobon (2010), Exhibits 8-9; 1998-01-01 to 2010-05-10",
    "drawdowns_preceded_by_spike": {
        "1_month_worst_1pct": 1.0000,
        "1_month_worst_2pct": 0.9846,
        "1_month_worst_5pct": 0.8944,
        "1_day_worst_1pct": 0.8485,
        "1_week_worst_1pct": 0.8485,
    },
    "annualised_return_after_shift": {
        "1_day_up_1sigma": -0.0828, "1_day_down_1sigma": 0.0927,
        "1_week_up_1sigma": -0.0844, "1_week_down_1sigma": 0.1006,
        "1_month_up_1sigma": -0.0586, "1_month_down_1sigma": 0.1216,
    },
    "caveat": "a spike is a near-necessary but NOT sufficient condition for a "
              "drawdown; stocks frequently rose after one",
}

#: Regime data moves on a daily bar. Refetching a 1,100-day history of 11 ETFs
#: on every risk poll would be absurd, and on a metered data source, expensive.
_CACHE_TTL_SECONDS = 3600.0
_cache: dict[str, tuple[float, Any]] = {}


def _cached(key: str, produce: Callable[[], Any], ttl: float = _CACHE_TTL_SECONDS) -> Any:
    hit = _cache.get(key)
    if hit is not None and (time.monotonic() - hit[0]) < ttl:
        return hit[1]
    val = produce()
    _cache[key] = (time.monotonic(), val)
    return val


def mahalanobis_series(returns: np.ndarray, min_history: int = 250) -> tuple[list[float], int]:
    """Turbulence d_t for each row, using the trailing history before it.

    Each day is scored against the distribution of the days *preceding* it, so
    the series is causal — no observation is judged using information from its
    own future. A backward-looking index that peeks ahead would look far more
    prescient than it is.

    Returns ``(values, offset)`` where ``offset`` is how many leading rows had
    no usable history and were skipped.
    """
    t, n = returns.shape
    if t <= min_history or n == 0:
        return [], t
    out: list[float] = []
    for i in range(min_history, t):
        hist = returns[:i]
        mu = hist.mean(axis=0)
        cov = np.cov(hist, rowvar=False, ddof=1)
        dev = returns[i] - mu
        try:
            inv = np.linalg.pinv(cov)   # pinv: the basket can be near-collinear
        except np.linalg.LinAlgError:
            continue
        out.append(float(dev @ inv @ dev))
    return out, min_history


def _ew_covariance(window: np.ndarray, lam: float = AR_LAMBDA) -> np.ndarray:
    """Exponentially-weighted covariance, as Equation (1) specifies.

    Kept local to this module rather than shared with ``riskmetrics.ewma_covariance``
    because the decay is a different animal: 250-day half-life for a slow
    structural read, versus RiskMetrics' 0.94 for a fast tactical one.
    """
    t = window.shape[0]
    if t < 2:
        return np.zeros((window.shape[1], window.shape[1]))
    w = lam ** np.arange(t - 1, -1, -1, dtype=float)
    w /= w.sum()
    dev = window - np.average(window, axis=0, weights=w)
    return (dev * w[:, None]).T @ dev


def absorption_ratio(cov: np.ndarray, n_eigen: int | None = None) -> float:
    """Fraction of total variance absorbed by the largest ``n_eigen`` eigenvectors.

    The eigenvalues of the covariance matrix *are* the variances of the
    eigenportfolios, and they sum to the trace, which is the sum of the
    individual asset variances — so this is exactly the published definition
    with no approximation.

    ``n_eigen`` defaults to N/5 (rounded up), following Kritzman et al.
    """
    vals = np.linalg.eigvalsh(cov)
    vals = np.sort(vals)[::-1]
    vals = vals[vals > 0]
    if vals.size == 0:
        return float("nan")
    k = n_eigen if n_eigen is not None else max(1, int(math.ceil(vals.size / 5.0)))
    k = min(k, vals.size)
    return float(vals[:k].sum() / vals.sum())


class RegimeAnalytics:
    """Market-wide fragility indicators, plus turbulence scoped to our own book."""

    def __init__(self, fetcher: Callable[..., Any] = fetch_daily_bars,
                 basket: Sequence[str] = SECTOR_BASKET):
        self._fetch = fetcher
        self._basket = tuple(basket)

    # --- market ------------------------------------------------------------
    def market(self, force: bool = False) -> dict[str, Any]:
        if force:
            _cache.pop("market", None)
        return _cached("market", self._market_uncached)

    def _market_uncached(self) -> dict[str, Any]:
        used, rets, dates, excluded = aligned_returns(
            self._basket, lookback_days=REGIME_LOOKBACK_DAYS, fetcher=self._fetch
        )
        if len(used) < 5:
            return {
                "measurable": False,
                "reason": f"only {len(used)} of {len(self._basket)} sector ETFs had usable "
                          "history; a market-wide reading needs at least 5",
                "excluded": excluded,
            }

        t = min(len(rets[s]) for s in used)
        mat = np.array([rets[s][-t:] for s in used], dtype=float).T
        obs_dates = dates[-t:] if len(dates) >= t else dates

        result: dict[str, Any] = {
            "measurable": True,
            "basket": list(used),
            "excluded": excluded,
            "n_obs": int(t),
            "window_end": obs_dates[-1] if obs_dates else None,
        }
        result.update(self._turbulence_block(mat, obs_dates))
        result.update(self._absorption_block(mat, obs_dates))
        result["interpretation"] = self._interpret(result)
        return result

    def _turbulence_block(self, mat: np.ndarray, dates: Sequence[str]) -> dict[str, Any]:
        vals, offset = mahalanobis_series(mat)
        if len(vals) < 60:
            return {"turbulence": {"measurable": False,
                                   "reason": f"only {len(vals)} scored days; need 60"}}
        arr = np.array(vals)
        latest = float(arr[-1])
        pct = float((arr <= latest).mean() * 100.0)
        recent = float(arr[-20:].mean())
        recent_pct = float((arr <= recent).mean() * 100.0)
        elevated = pct >= 80.0
        return {"turbulence": {
            "measurable": True,
            "latest": round(latest, 3),
            "percentile": round(pct, 1),
            "median": round(float(np.median(arr)), 3),
            "p90": round(float(np.quantile(arr, 0.90)), 3),
            "recent_20d_mean": round(recent, 3),
            "recent_20d_percentile": round(recent_pct, 1),
            "elevated": elevated,
            "n_scored_days": int(arr.size),
            "as_of": dates[-1] if dates else None,
            "verdict": (
                f"today's cross-section of sector moves is more unusual than "
                f"{pct:.0f}% of the past {arr.size} days"
                + (" — turbulence is persistent, and risk-taking historically pays "
                   "poorly while it is elevated" if elevated else "")
            ),
        }}

    def _absorption_block(self, mat: np.ndarray, dates: Sequence[str]) -> dict[str, Any]:
        t = mat.shape[0]
        if t < AR_WINDOW + AR_HISTORY:
            return {"absorption": {
                "measurable": False,
                "reason": f"{t} days of history; the absorption ratio needs "
                          f"{AR_WINDOW + AR_HISTORY} (a {AR_WINDOW}-day estimation window "
                          f"plus {AR_HISTORY} days to standardise the shift)",
            }}
        series: list[float] = []
        for i in range(AR_WINDOW, t + 1):
            series.append(absorption_ratio(_ew_covariance(mat[i - AR_WINDOW:i])))
        arr = np.array([v for v in series if np.isfinite(v)])
        if arr.size < AR_HISTORY:
            return {"absorption": {"measurable": False,
                                   "reason": f"only {arr.size} usable AR observations"}}

        current = float(arr[-1])
        short = float(arr[-AR_SHIFT_WINDOW:].mean())
        year = arr[-AR_HISTORY:]
        long_mean, long_sd = float(year.mean()), float(year.std(ddof=1))
        shift = ((short - long_mean) / long_sd) if long_sd > 1e-12 else 0.0
        flagged = shift >= AR_SHIFT_THRESHOLD
        return {"absorption": {
            "measurable": True,
            "current": round(current, 4),
            "short_window_mean": round(short, 4),
            "one_year_mean": round(long_mean, 4),
            "one_year_sd": round(long_sd, 4),
            "standardised_shift": round(shift, 3),
            "threshold": AR_SHIFT_THRESHOLD,
            "flagged": flagged,
            "n_eigenvectors": max(1, int(math.ceil(mat.shape[1] / 5.0))),
            "n_assets": int(mat.shape[1]),
            "estimation_window_days": AR_WINDOW,
            "halflife_days": AR_HALFLIFE,
            "as_of": dates[-1] if dates else None,
            "empirical": AR_EMPIRICAL,
            "verdict": (
                f"the largest eigenvectors absorb {current:.0%} of sector variance; "
                f"the 15-day level sits {shift:+.2f} standard deviations from its one-year mean"
                + (" — in 1998-2010 every one of the 1% worst monthly drawdowns was "
                   "preceded by a shift this size, but stocks also frequently rose "
                   "after one: it is close to a necessary condition for a crash, "
                   "not a sufficient one"
                   if flagged else " — no meaningful tightening")
            ),
        }}

    # --- portfolio ---------------------------------------------------------
    def portfolio_turbulence(self, returns_by_symbol: dict[str, list[float]],
                             symbols: Sequence[str]) -> dict[str, Any]:
        """Turbulence scoped to the names we actually hold.

        Different question from the market reading: not "is the market strange"
        but "is today strange *for this book*" — which can be true even in a calm
        market if our own names break their usual relationship.
        """
        syms = [s for s in symbols if s in returns_by_symbol and returns_by_symbol[s]]
        if len(syms) < 2:
            return {"measurable": False,
                    "reason": "need at least two priced holdings to measure a joint distribution"}
        t = min(len(returns_by_symbol[s]) for s in syms)
        mat = np.array([returns_by_symbol[s][-t:] for s in syms], dtype=float).T
        vals, _ = mahalanobis_series(mat, min_history=min(120, max(t - 20, 2)))
        if len(vals) < 20:
            return {"measurable": False,
                    "reason": f"only {len(vals)} scored days for the book; need 20"}
        arr = np.array(vals)
        latest = float(arr[-1])
        pct = float((arr <= latest).mean() * 100.0)
        return {
            "measurable": True,
            "symbols": syms,
            "latest": round(latest, 3),
            "percentile": round(pct, 1),
            "elevated": pct >= 80.0,
            "n_scored_days": int(arr.size),
            "verdict": (f"today ranks at the {pct:.0f}th percentile of unusualness for "
                        f"this book's own joint behaviour"),
        }

    # --- narrative ---------------------------------------------------------
    @staticmethod
    def _interpret(r: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        turb, ab = r.get("turbulence", {}), r.get("absorption", {})
        if turb.get("measurable"):
            lines.append(turb["verdict"] + ".")
        else:
            lines.append("Turbulence not measurable: " + turb.get("reason", "unknown"))
        if ab.get("measurable"):
            lines.append(ab["verdict"] + ".")
        else:
            lines.append("Absorption ratio not measurable: " + ab.get("reason", "unknown"))
        if turb.get("elevated") and ab.get("flagged"):
            lines.append(
                "Both indicators are elevated at once: the market is behaving unusually "
                "AND has become tightly coupled. That is the configuration in which "
                "diversification stops working, so treat position-level limits as "
                "insufficient protection right now."
            )
        lines.append(
            "These describe the market, not this fund's positions, and they are "
            "indicators rather than forecasts — elevated readings have preceded "
            "drawdowns historically, which is not the same as predicting one."
        )
        return lines
