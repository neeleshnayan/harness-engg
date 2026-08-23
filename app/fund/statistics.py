"""Statistical honesty for performance numbers.

A Sharpe ratio computed from 240 daily bars and 11 trades is not a measurement,
it is an estimate with an enormous error bar — and if it was picked as the best
of twenty parameter sweeps, it is a *selected* estimate, which is worse. This
module computes the error bars and the selection penalty so the UI can show them
next to the point estimate instead of presenting a lucky draw as an edge.

Nothing here invents a number. Every function takes an observed return series
(or statistics derived from one) and returns properties of that series. Where a
result rests on an assumption the assumption is named in the return payload, not
buried in a docstring.

References (the formulas, not the prose):
  * Lo, A. (2002), "The Statistics of Sharpe Ratios", Financial Analysts Journal
    — the IID standard error, and the correction to the sqrt(q) annualisation
    rule when returns are serially correlated.
  * Bailey, D. & López de Prado, M. (2012), "The Sharpe Ratio Efficient
    Frontier" / (2014) "The Deflated Sharpe Ratio" — minimum track record
    length and the expected maximum Sharpe under N trials.
"""

from __future__ import annotations

import math
from statistics import NormalDist
from typing import Any, Sequence

# Euler-Mascheroni, used by the expected-maximum-Sharpe approximation.
_EULER_GAMMA = 0.5772156649015329

_N = NormalDist()

#: Below this many observations we refuse to dress an estimate up as a finding.
MIN_OBS_FOR_INFERENCE = 30


def _clean(returns: Sequence[float]) -> list[float]:
    return [float(r) for r in (returns or []) if r is not None and math.isfinite(float(r))]


def mean_std(returns: Sequence[float]) -> tuple[float, float]:
    """Sample mean and *sample* standard deviation (ddof=1)."""
    r = _clean(returns)
    n = len(r)
    if n < 2:
        return (r[0] if n else 0.0), 0.0
    mu = sum(r) / n
    var = sum((x - mu) ** 2 for x in r) / (n - 1)
    return mu, math.sqrt(var)


def skewness(returns: Sequence[float]) -> float:
    """Sample skewness (Fisher-Pearson, biased/moment estimator)."""
    r = _clean(returns)
    n = len(r)
    mu, sd = mean_std(r)
    if n < 3 or sd <= 0:
        return 0.0
    return sum(((x - mu) / sd) ** 3 for x in r) / n


def kurtosis(returns: Sequence[float]) -> float:
    """Sample kurtosis, NON-excess (a normal distribution gives 3.0)."""
    r = _clean(returns)
    n = len(r)
    mu, sd = mean_std(r)
    if n < 4 or sd <= 0:
        return 3.0
    return sum(((x - mu) / sd) ** 4 for x in r) / n


def autocorrelations(returns: Sequence[float], max_lag: int = 6) -> list[float]:
    """Sample autocorrelations rho_1..rho_max_lag.

    High rho_1 in a return series usually means one of two things, and both
    matter: the marks are stale/smoothed (an illiquidity signature), or the
    strategy holds through multi-day trends. Either way it breaks the
    independence assumption behind the sqrt(q) annualisation rule.
    """
    r = _clean(returns)
    n = len(r)
    mu, sd = mean_std(r)
    if n < 3 or sd <= 0:
        return [0.0] * max_lag
    denom = sum((x - mu) ** 2 for x in r)
    out: list[float] = []
    for k in range(1, max_lag + 1):
        if k >= n:
            out.append(0.0)
            continue
        num = sum((r[t] - mu) * (r[t - k] - mu) for t in range(k, n))
        out.append(num / denom if denom > 0 else 0.0)
    return out


def sharpe_per_period(returns: Sequence[float], rf_per_period: float = 0.0) -> float:
    """Per-observation Sharpe. NOT annualised — annualise deliberately, below."""
    mu, sd = mean_std(returns)
    if sd <= 0:
        return 0.0
    return (mu - rf_per_period) / sd


def annualisation_factor(returns: Sequence[float], periods_per_year: int = 252,
                         max_lag: int = 6) -> dict[str, Any]:
    """The honest multiplier for scaling a per-period Sharpe to a year.

    The reflex is ``sqrt(252)``. That is only right when returns are IID. With
    serial correlation rho_k, Lo (2002) gives

        eta(q) = q / sqrt( q + 2 * sum_{k=1}^{q-1} (q - k) * rho_k )

    Positive autocorrelation makes eta(q) < sqrt(q), so the reflex *overstates*
    the annual Sharpe — which is exactly the direction that flatters a strategy.

    Summing q-1 = 251 sample autocorrelations from a year of data would be
    mostly noise, so we use the first ``max_lag`` and treat the rest as zero;
    ``lags_used`` reports that truncation rather than hiding it.
    """
    q = int(periods_per_year)
    rhos = autocorrelations(returns, max_lag=min(max_lag, max(q - 1, 1)))
    naive = math.sqrt(q)
    acc = float(q)
    for k, rho in enumerate(rhos, start=1):
        if k >= q:
            break
        acc += 2.0 * (q - k) * rho
    # Strong negative autocorrelation can drive the variance term non-positive;
    # that is a sign the estimate is unusable, not a licence to divide by zero.
    if acc <= 0:
        return {
            "factor": naive,
            "naive_factor": naive,
            "usable": False,
            "lags_used": len(rhos),
            "autocorrelations": [round(r, 4) for r in rhos],
            "note": "autocorrelation-adjusted variance was non-positive; "
                    "fell back to the sqrt(q) rule, which is probably wrong here",
        }
    eta = q / math.sqrt(acc)
    return {
        "factor": eta,
        "naive_factor": naive,
        "usable": True,
        "lags_used": len(rhos),
        "autocorrelations": [round(r, 4) for r in rhos],
        "inflation_vs_naive": round((naive / eta - 1.0) * 100.0, 2) if eta > 0 else None,
        "note": ("the sqrt(q) rule overstates annual Sharpe here by "
                 f"{(naive / eta - 1.0) * 100.0:.1f}%" if eta < naive else
                 "returns show little positive serial correlation; sqrt(q) is close to right"),
    }


def sharpe_standard_error(sharpe: float, n_obs: int) -> float | None:
    """SE of a Sharpe estimate under IID normal returns (Lo 2002):

        SE(SR) ~= sqrt( (1 + SR^2 / 2) / T )

    Both the point estimate and this error bar must be on the SAME time base:
    pass an annual Sharpe with T = number of *years*, or a daily Sharpe with
    T = number of days. Mixing them is the classic way to make an error bar
    look ten times tighter than it is.
    """
    t = int(n_obs)
    if t < 2:
        return None
    return math.sqrt((1.0 + (float(sharpe) ** 2) / 2.0) / t)


def sharpe_confidence_interval(sharpe: float, n_obs: int,
                               confidence: float = 0.95) -> dict[str, Any]:
    """Confidence interval around a Sharpe estimate, plus the only question that
    matters for a young track record: could this be zero?"""
    se = sharpe_standard_error(sharpe, n_obs)
    if se is None:
        return {"usable": False, "reason": "fewer than 2 observations"}
    z = _N.inv_cdf(1.0 - (1.0 - confidence) / 2.0)
    lo, hi = float(sharpe) - z * se, float(sharpe) + z * se
    return {
        "usable": True,
        "sharpe": round(float(sharpe), 4),
        "standard_error": round(se, 4),
        "confidence": confidence,
        "low": round(lo, 4),
        "high": round(hi, 4),
        "includes_zero": lo <= 0.0 <= hi,
        "n_obs": int(n_obs),
        "assumes": "IID normal returns (Lo 2002); serial correlation or fat tails widen this",
    }


def probabilistic_sharpe_ratio(sharpe: float, n_obs: int,
                               returns: Sequence[float] | None = None,
                               target_sharpe: float = 0.0) -> dict[str, Any]:
    """The probability that the TRUE Sharpe exceeds ``target_sharpe``, given this
    estimate and the shape of the return distribution (Bailey & López de Prado):

        PSR(SR*) = Z[ (SR - SR*) * sqrt(n - 1)
                      / sqrt( 1 - g3*SR + (g4 - 1)/4 * SR^2 ) ]

    This is the same machinery as :func:`min_track_record_length`, asked the other
    way round: minTRL answers "how much more data do I need", PSR answers "with
    what I already have, how confident can I be at all". A headline Sharpe of 0.4
    can carry a PSR of 4% — meaning a 96% chance the real edge is zero or worse —
    and reporting the 0.4 without the 4% is how a coin flip gets deployed.

    Skew and kurtosis matter here and are not decoration: negative skew and fat
    tails both *lower* the probability for the same Sharpe, which is exactly the
    correction a strategy that sells tails needs applied to it.
    """
    g3 = skewness(returns) if returns else 0.0
    g4 = kurtosis(returns) if returns else 3.0
    return psr_from_moments(n_obs, sharpe, g3, g4, target_sharpe)


def psr_from_moments(n_obs: int, sharpe: float, skew: float, kurt: float,
                     target_sharpe: float = 0.0) -> dict[str, Any]:
    """PSR from the four sufficient statistics, with no series in hand.

    THE ONE PLACE THE z FORMULA IS WRITTEN. ``probabilistic_sharpe_ratio``
    derives the two shape moments from a series and delegates here; the premia
    luck filter reads the moments the belt STORED for a difference series it no
    longer has. Two spellings of Bailey & López de Prado's z would be two
    statistics wearing one name, and the difference would surface as a criterion
    that disagrees with the capture block beside it.

    ``sharpe`` and ``target_sharpe`` are PER OBSERVATION, on the same base as
    ``n_obs``; ``kurt`` is NON-excess (a normal distribution gives 3.0).
    """
    n = int(n_obs)
    if n < 2:
        return {"usable": False, "reason": "fewer than 2 observations", "n_obs": n}
    sr = float(sharpe)
    g3, g4 = float(skew), float(kurt)
    shape = _psr_shape(sr, g3, g4)
    if shape <= 0:
        # A degenerate moment estimate, not a licence to claim certainty.
        return {
            "usable": False,
            "reason": "return distribution gives a non-positive variance term; "
                      "PSR is undefined for this sample",
            "n_obs": n,
        }
    z = (sr - float(target_sharpe)) * math.sqrt(n - 1) / math.sqrt(shape)
    p = _N.cdf(z)
    return {
        "usable": True,
        "psr": round(p, 6),
        "psr_pct": round(p * 100.0, 3),
        "sharpe": round(sr, 4),
        "target_sharpe": float(target_sharpe),
        "n_obs": n,
        "skew": round(g3, 4),
        "kurtosis": round(g4, 4),
        "beats_target": p >= 0.95,
        "note": (
            f"{p * 100.0:.1f}% probability the true Sharpe exceeds "
            f"{float(target_sharpe):.2f}; anything under 95% is not evidence of an edge"
        ),
    }


#: A dispersion at or below this is NO dispersion, not a small one. The floor is
#: relative to the mean because that is the scale the cancellation happens on,
#: with an absolute backstop for a series centred on zero. Measured (D23): 100
#: copies of 0.001 give `sum((x - mu)**2)` around 1e-19 and a Sharpe of order
#: 1e16 — which a bare `sd > 0` accepts and a luck filter would then score at
#: 100%. ONE definition, shared by `leg_moments` and `psr_from_series`, because
#: two spellings of "is this leg flat" is the two-copies-of-one-belief defect.
def _no_dispersion(mu: float, sd: float) -> bool:
    return sd <= max(1e-12, abs(mu) * 1e-9)


def psr_from_series(returns: Sequence[float] | None,
                    target_sharpe: float = 0.0) -> dict[str, Any]:
    """The luck filter, derived from a return SERIES rather than a headline.

    ``probabilistic_sharpe_ratio`` takes a Sharpe and a sample size and trusts
    the caller to have put them on the same clock. This is the ONE place that
    derives them from the observations, and it exists because the derivation —
    not the formula — is where the two readings of "the PSR" diverged:

      * The per-observation Sharpe is ``mean / stdev`` over the SAME n the count
        reports, never an annualised figure. Bailey & López de Prado's z scales
        with ``sqrt(n - 1)`` against a per-observation SR; feeding it an
        annualised Sharpe multiplies the statistic by ``sqrt(K)`` and reports a
        confidence the sample does not support.
      * A flat leg is UNMEASURABLE, not certain. See ``_no_dispersion``.

    ``target_sharpe`` is on the same per-observation base. Zero is the
    documented job of this statistic — "is the true Sharpe above nothing" — and
    is the only target for which the sentence "not distinguishable from luck"
    is true. Any other target is a SKILL HURDLE and the caller must say so in
    its own words; this function will compute it and will not name it.

    THE CLOCK QUESTION, measured rather than argued (2026-08-24, four control
    candidates, ``scratchpad/d36probe/fold1.py``): a LEAN equity series carries
    one point per CALENDAR day, so roughly 29% of its observations are weekend
    zeros. Dropping them changes this statistic by at most 0.063pp on the four
    controls (85.030 -> 85.019, 90.357 -> 90.346, 50.153 -> 50.151, 78.339 ->
    78.276): the smaller n and the larger per-observation Sharpe very nearly
    cancel. So the series is scored AS THE BELT ALIGNED IT, and the reason that
    is safe is a measurement rather than an assumption.
    """
    r = _clean(returns)
    out: dict[str, Any] = {
        "measurable": False,
        "psr_pct": None,
        "sharpe_per_obs": None,
        "n_obs": len(r),
        "target_sharpe": float(target_sharpe),
        "skew": None,
        "kurtosis": None,
        "reason": None,
    }
    if len(r) < 2:
        out["reason"] = (f"{len(r)} usable observation(s) — a probability needs "
                         f"a sample, and an absent one is not a confident one")
        return out
    mu, sd = mean_std(r)
    if _no_dispersion(mu, sd):
        out["reason"] = ("the series has no dispersion, so no Sharpe exists for "
                         "it and no probability can be attached to one")
        return out
    sr = mu / sd
    inner = probabilistic_sharpe_ratio(sr, len(r), r, float(target_sharpe))
    if not inner.get("usable"):
        out["reason"] = inner.get("reason")
        return out
    out.update({
        "measurable": True,
        "psr_pct": inner["psr_pct"],
        "sharpe_per_obs": round(sr, 8),
        "skew": inner.get("skew"),
        "kurtosis": inner.get("kurtosis"),
    })
    return out


def sharpe_advantage_series(strategy: Sequence[float] | None,
                            benchmark: Sequence[float] | None) -> dict[str, Any]:
    """The moments of the SHARPE-ADVANTAGE series, so a luck filter can score it.

    A premia claim is "better risk-adjusted return than holding the asset", and
    the quantity it asserts is positive is ``SR_s - SR_b``, not ``SR_s``. Asking
    a luck filter about the strategy's ABSOLUTE Sharpe answers a question the
    claim never made — a low-volatility overlay with a real advantage can have a
    modest absolute Sharpe, and a beta-heavy book with no advantage at all can
    have a large one.

    THE CONSTRUCTION, and why it is this one. Scale each leg by its OWN standard
    deviation and difference them per observation:

        d_t = r_s,t / sd_s  -  r_b,t / sd_b

    Then ``mean(d) == SR_s - SR_b`` EXACTLY, per observation, so the series' own
    mean is the advantage itself and ``psr_from_moments`` applied to d answers
    "what is the probability the true advantage exceeds zero" using the same
    machinery, the same level and the same skew/kurtosis correction the alpha
    bar uses. Nothing new is invented and nothing is assumed normal.

    WHY NOT JOBSON-KORKIE / MEMMEL. The textbook standard error for a difference
    of Sharpe ratios is normal-theory and needs the two legs' correlation as a
    separate input. These candidates carry a kurtosis of 24 to 196, where the
    normal-theory error is UNDERSTATED — which points in the admitting
    direction, the one direction this fund does not accept a convenience in. The
    difference series carries the correlation implicitly (a pair that moves
    together has a small dispersion in d) and carries its own fat tails into the
    same correction the rest of the gate already applies.

    WHAT IT DOES NOT MODEL, said plainly: ``sd_s`` and ``sd_b`` are estimated on
    the same sample they scale, so d treats two estimates as known constants.
    This is the same simplification Bailey & López de Prado's PSR makes for a
    single leg, and at the sample sizes the belt produces it is small — but it
    is a simplification, not an exact distribution.

    PAIRED, OR NOTHING. Two series of different lengths are not a difference;
    they are two measurements of different things, and the honest answer is that
    the advantage is unmeasurable.
    """
    s = _clean(strategy)
    b = _clean(benchmark)
    out: dict[str, Any] = {
        "measurable": False, "n": len(s), "mean_per_obs": None, "stdev": None,
        "sharpe_per_obs": None, "skew": None, "kurtosis": None,
        "sharpe_strategy_per_obs": None, "sharpe_benchmark_per_obs": None,
        "reason": None,
    }
    if len(s) != len(b):
        out["reason"] = (f"the strategy leg has {len(s)} usable observations and "
                         f"the bar has {len(b)} — an unpaired difference is not "
                         f"an advantage")
        return out
    if len(s) < 2:
        out["reason"] = (f"{len(s)} paired observation(s) — nothing to measure, "
                         f"which is not the same as no advantage")
        return out
    mu_s, sd_s = mean_std(s)
    mu_b, sd_b = mean_std(b)
    if _no_dispersion(mu_s, sd_s) or _no_dispersion(mu_b, sd_b):
        out["reason"] = ("one leg has no dispersion, so it has no Sharpe and "
                         "their difference does not exist")
        return out
    d = [x / sd_s - y / sd_b for x, y in zip(s, b)]
    mu_d, sd_d = mean_std(d)
    if _no_dispersion(mu_d, sd_d):
        # Two legs that differ by an exact constant multiple. The advantage is
        # then a number with no sampling variation IN THIS SAMPLE, which is a
        # degenerate estimate rather than a certain one.
        out["reason"] = ("the two legs differ by a constant, so the advantage "
                         "has no dispersion and no probability attaches to it")
        return out
    out.update({
        "measurable": True,
        "n": len(d),
        "mean_per_obs": mu_d,
        "stdev": sd_d,
        "sharpe_per_obs": mu_d / sd_d,
        "skew": skewness(d),
        "kurtosis": kurtosis(d),
        "sharpe_strategy_per_obs": mu_s / sd_s,
        "sharpe_benchmark_per_obs": mu_b / sd_b,
    })
    return out


def _psr_shape(sr: float, g3: float, g4: float) -> float:
    """The variance term under PSR's square root. One spelling, three callers."""
    return 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * (sr ** 2)


def _psr_moments(returns: Sequence[float] | None) -> tuple | None:
    """(n, per-observation Sharpe, skew, kurtosis) or None when unmeasurable."""
    r = _clean(returns)
    if len(r) < 2:
        return None
    mu, sd = mean_std(r)
    if _no_dispersion(mu, sd):
        return None
    return len(r), mu / sd, skewness(r), kurtosis(r)


def implied_target_sharpe(psr_pct: float,
                          returns: Sequence[float] | None) -> dict[str, Any]:
    """WHAT TARGET was a reported PSR measured against? Inverted, not assumed.

    A PSR is meaningless without the ``SR*`` it was computed against, and LEAN
    publishes a ``Probabilistic Sharpe Ratio`` and no target for it (the engine's
    statistics block carries no ``Benchmark Sharpe Ratio`` key — verified on a
    real 27-key block, candidate 144387901688). The formula is invertible, so the
    target can be RECOVERED from the run's own series instead of guessed:

        z = Phi^-1(PSR);  SR* = SR - z * sqrt(shape(SR)) / sqrt(n - 1)

    This is the identification the fund previously carried as a table of four
    numbers in a comment. Computing it per candidate means the disclosure cannot
    go stale and cannot describe a different candidate than the one being judged.

    Returns ``measurable: False`` rather than a number at PSR of exactly 0% or
    100%, where the normal inverse is infinite and the target is unrecoverable.
    """
    out: dict[str, Any] = {"measurable": False, "target_per_obs": None,
                           "reason": None}
    m = _psr_moments(returns)
    if m is None:
        out["reason"] = ("no usable return series, so the target this PSR was "
                         "measured against cannot be recovered")
        return out
    n, sr, g3, g4 = m
    try:
        p = float(psr_pct) / 100.0
    except (TypeError, ValueError):
        out["reason"] = "the reported PSR is not a number"
        return out
    if not 0.0 < p < 1.0:
        out["reason"] = (f"a reported PSR of {psr_pct}% pins the target at "
                         f"infinity; it cannot be inverted")
        return out
    shape = _psr_shape(sr, g3, g4)
    if shape <= 0:
        out["reason"] = ("the return distribution gives a non-positive variance "
                         "term, so the inversion has no real solution")
        return out
    z = _N.inv_cdf(p)
    out.update({
        "measurable": True,
        "target_per_obs": sr - z * math.sqrt(shape) / math.sqrt(n - 1),
        "sharpe_per_obs": sr,
        "n_obs": n,
    })
    return out


def sharpe_bar_for_psr(level_pct: float, returns: Sequence[float] | None,
                       target_sharpe: float = 0.0) -> dict[str, Any]:
    """The per-observation Sharpe a series of THIS shape needs to clear a PSR level.

    This is what a PSR threshold actually TESTS, and a criterion that cannot
    state it is asking a question in units nobody can check. Solving
    ``(x - SR*)^2 (n-1) = z^2 * shape(x)`` for x is a quadratic:

        x^2 [ (n-1) - z^2 (g4-1)/4 ]  +  x [ z^2 g3 - 2 SR* (n-1) ]
                                      +  [ SR*^2 (n-1) - z^2 ]  =  0

    Solved in closed form and then VERIFIED by evaluating the PSR at the root:
    the squaring can introduce a solution below the target, and the shape term is
    not monotone in x, so a bisection would be unsound and an unverified root
    would be arithmetic rather than an answer. Unverifiable roots return
    ``measurable: False`` — this figure is a DISCLOSURE and must never be able to
    break the verdict it explains.
    """
    out: dict[str, Any] = {"measurable": False, "sharpe_per_obs": None,
                           "reason": None}
    m = _psr_moments(returns)
    if m is None:
        out["reason"] = "no usable return series to state a bar against"
        return out
    n, _sr, g3, g4 = m
    try:
        lv = float(level_pct) / 100.0
    except (TypeError, ValueError):
        out["reason"] = "the level is not a number"
        return out
    if not 0.0 < lv < 1.0:
        out["reason"] = (f"a level of {level_pct}% is not a probability strictly "
                         f"between 0 and 100, so no finite bar exists")
        return out
    z = _N.inv_cdf(lv)
    t = float(target_sharpe)
    a = (n - 1) - z * z * (g4 - 1.0) / 4.0
    b = z * z * g3 - 2.0 * t * (n - 1)
    c = t * t * (n - 1) - z * z
    roots: list[float] = []
    if abs(a) < 1e-18:
        if abs(b) > 1e-18:
            roots.append(-c / b)
    else:
        disc = b * b - 4.0 * a * c
        if disc >= 0:
            rt = math.sqrt(disc)
            roots.extend([(-b + rt) / (2.0 * a), (-b - rt) / (2.0 * a)])
    valid = []
    for x in sorted(roots):
        shape = _psr_shape(x, g3, g4)
        if shape <= 0:
            continue
        got = _N.cdf((x - t) * math.sqrt(n - 1) / math.sqrt(shape)) * 100.0
        if abs(got - float(level_pct)) < 1e-6:
            valid.append(x)
    if not valid:
        out["reason"] = ("no Sharpe reproduces this level for a series of this "
                         "shape, so the bar cannot be stated")
        return out
    out.update({"measurable": True, "sharpe_per_obs": min(valid), "n_obs": n})
    return out


def min_track_record_length(sharpe: float, n_obs: int, returns: Sequence[float] | None = None,
                            target_sharpe: float = 0.0,
                            confidence: float = 0.95) -> dict[str, Any]:
    """How many observations you need before this Sharpe beats ``target_sharpe``
    at the requested confidence (Bailey & López de Prado 2012):

        minTRL = 1 + [ 1 - g3*SR + (g4 - 1)/4 * SR^2 ] * ( z / (SR - SR*) )^2

    where g3 is skew and g4 is (non-excess) kurtosis of the return series, and
    SR / SR* are on the same per-observation base as the count.

    A negative or below-target Sharpe has no finite answer, and we say so rather
    than returning a number.
    """
    sr = float(sharpe)
    if sr <= target_sharpe:
        return {
            "usable": False,
            "reason": f"Sharpe {sr:.3f} is not above the target {target_sharpe:.3f}; "
                      "no amount of additional data makes it so",
            "n_obs": int(n_obs),
        }
    g3 = skewness(returns) if returns else 0.0
    g4 = kurtosis(returns) if returns else 3.0
    z = _N.inv_cdf(confidence)
    shape = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * (sr ** 2)
    # Negative skew and fat tails both raise `shape` — they demand MORE data.
    if shape <= 0:
        shape = 1.0
    need = 1.0 + shape * ((z / (sr - target_sharpe)) ** 2)
    have = int(n_obs)
    return {
        "usable": True,
        "required_obs": int(math.ceil(need)),
        "n_obs": have,
        "sufficient": have >= need,
        "shortfall_obs": max(0, int(math.ceil(need)) - have),
        "skew": round(g3, 4),
        "kurtosis": round(g4, 4),
        "confidence": confidence,
        "target_sharpe": target_sharpe,
    }


def expected_max_sharpe(n_trials: int, sharpe_variance: float = 1.0) -> float | None:
    """The Sharpe you should expect from the BEST of ``n_trials`` strategies that
    all have zero true edge (Bailey & López de Prado):

        E[max SR] ~= sqrt(V) * [ (1-g) * Z^-1(1 - 1/N) + g * Z^-1(1 - 1/(N*e)) ]

    This is the bar a backtest has to clear to be interesting. Sweep enough
    parameters and something will look brilliant purely by chance; this says how
    brilliant chance alone would look.
    """
    n = int(n_trials)
    if n < 2:
        return None
    v = max(float(sharpe_variance), 0.0)
    a = _N.inv_cdf(1.0 - 1.0 / n)
    b = _N.inv_cdf(1.0 - 1.0 / (n * math.e))
    return math.sqrt(v) * ((1.0 - _EULER_GAMMA) * a + _EULER_GAMMA * b)


def selection_penalty(observed_sharpe: float, n_trials: int, n_obs: int) -> dict[str, Any]:
    """Was this the best of many tries? Then compare it to the best of many
    tries on noise, not to zero."""
    if int(n_trials) < 2:
        return {
            "applies": False,
            "reason": "single configuration tested — no selection bias to correct for",
        }
    se = sharpe_standard_error(observed_sharpe, n_obs)
    if se is None:
        return {"applies": False, "reason": "too few observations"}
    threshold = expected_max_sharpe(n_trials, sharpe_variance=se ** 2)
    if threshold is None:
        return {"applies": False, "reason": "too few trials"}
    return {
        "applies": True,
        "n_trials": int(n_trials),
        "observed_sharpe": round(float(observed_sharpe), 4),
        "noise_threshold": round(threshold, 4),
        "clears_noise": float(observed_sharpe) > threshold,
        "note": (
            f"the best of {int(n_trials)} zero-edge configurations would be expected to "
            f"show Sharpe {threshold:.2f} by luck alone"
        ),
    }


def observations_per_year(dates: Sequence[str], n_obs: int) -> dict[str, Any]:
    """How many observations a year this series actually carries, from its OWN dates.

    NOT a constant, and that is the whole point. The reflex is 252, and on this
    fund's engine output the reflex is WRONG: LEAN emits an equity point for
    every CALENDAR day, so the return series carries a run of zeros across
    every weekend. Measured on the four stored candidates that carry analytics
    (2026-08-23): 584 zeros in 1,998 observations and 170 in 907 — 29.2% and
    18.7% — and this function returns EXACTLY 365.25 for all four, because
    ``n - 1`` equals the calendar span in days to the day. One observation per
    calendar day, measured rather than supposed.

    The consequence is not academic. LEAN's own ``Annual Standard Deviation``
    statistic is reproducible, on all four, as the standard deviation of that
    CALENDAR series times sqrt(252) — so the engine's published volatility is
    understated relative to the trading-day truth by a factor measured at
    1.2033, 1.2033, 1.2033 and 1.2047 (theory: sqrt(365.25/252) = 1.2039; the
    small spread is the window's own holidays). A 17% error, in the flattering
    direction. Reproduce: candidate 144387901688 stores ``Annual Standard
    Deviation: 0.116``; the calendar series gives sd*sqrt(252) = 0.11627
    (population) or 0.11634 (sample) and the trading-day subset gives 0.14016.
    The engine prints three decimals, so which of the two dispersion
    conventions it uses is NOT identified by this evidence — the clock is, and
    the clock is the 17%.

    Deriving the factor from the dates is self-correcting: a mean scales with K
    and a standard deviation with sqrt(K), so a Sharpe computed with the
    series' OWN K lands on the same number whichever clock the engine used.
    Verified on the same four candidates — strategy annualised volatility
    12.026% on the calendar clock (K = 365.25) against 12.021% on the
    trading-day subset (K = 251.25).

    Returns ``usable: False`` with a reason rather than a fallback constant. An
    unreadable clock is an absence, and 252 is not the honest guess.
    """
    n = int(n_obs or 0)
    if n < 2 or len(dates or []) != n:
        return {"usable": False, "obs_per_year": None,
                "reason": f"{n} observation(s) against {len(dates or [])} date(s) "
                          f"— a series and its clock must be the same length"}
    from datetime import date as _date
    try:
        first = _date.fromisoformat(str(dates[0])[:10])
        last = _date.fromisoformat(str(dates[-1])[:10])
    except ValueError:
        return {"usable": False, "obs_per_year": None,
                "reason": "the series' dates could not be parsed, so its spacing "
                          "is unknown — reported absent rather than assumed"}
    span_days = (last - first).days
    if span_days <= 0:
        return {"usable": False, "obs_per_year": None,
                "reason": f"the series spans {span_days} day(s), so no annual "
                          f"rate can be derived from it"}
    # n returns are differenced across n-1 intervals BETWEEN dates[0] and
    # dates[-1]; the observation before dates[0] has no date here. Using n
    # would overstate the rate by 1/(n-1), which is 0.07% at n=1374 and 4% at
    # n=25 — small, and there is no reason to carry an error we can avoid.
    return {"usable": True,
            "obs_per_year": (n - 1) / (span_days / 365.25),
            "n_obs": n, "span_days": span_days,
            "first": str(dates[0])[:10], "last": str(dates[-1])[:10]}


def max_drawdown(returns: Sequence[float]) -> float | None:
    """Deepest peak-to-trough fall of the compounded path, as a POSITIVE fraction.

    Computed from the return series rather than read off the engine, because the
    only comparison that means anything is one where both legs were measured the
    same way over the same window. LEAN's ``Drawdown`` statistic exists for the
    strategy and has no twin for a benchmark the engine discarded.
    """
    r = _clean(returns)
    if not r:
        return None
    level = 1.0
    peak = 1.0
    worst = 0.0
    for x in r:
        level *= (1.0 + x)
        if level > peak:
            peak = level
        if peak > 0:
            worst = max(worst, 1.0 - level / peak)
    return worst


def leg_moments(returns: Sequence[float], dates: Sequence[str]) -> dict[str, Any]:
    """The sufficient statistics for judging one return leg, and nothing more.

    Six numbers — n, the clock, the mean, the spread, the worst fall and the
    compounded total — are everything the premia criterion needs, and a Sharpe
    at ANY risk-free rate is recoverable from them exactly (see
    ``sharpe_at_rf``). Storing these instead of the series keeps the belt's
    payload small and, more importantly, makes it impossible for the gate to
    compute a volatility that disagrees with the one the belt reported: there
    is one measurement, carried, not two measurements that must be kept in step.

    ``measurable: False`` with a reason whenever the clock or the spread cannot
    be read. A leg that cannot be measured is not a leg that scored zero.
    """
    r = _clean(returns)
    clock = observations_per_year(dates, len(r))
    out: dict[str, Any] = {
        "n": len(r),
        "obs_per_year": clock.get("obs_per_year"),
        "clock": clock,
        "measurable": False,
        "mean": None, "stdev": None,
        "ann_return_pct": None, "ann_vol_pct": None,
        "max_drawdown_pct": None, "total_return_pct": None,
    }
    if len(r) < 2:
        out["reason"] = (f"{len(r)} usable observation(s) — nothing to measure, "
                         f"which is not the same as a flat leg")
        return out
    if not clock.get("usable"):
        out["reason"] = clock.get("reason")
        return out
    mu, sd = mean_std(r)
    k = float(clock["obs_per_year"])
    # A CONSTANT SERIES DOES NOT HAVE A TINY VOLATILITY, IT HAS NONE. The floor
    # itself lives once, in `_no_dispersion`, and is shared with the luck filter
    # — a leg this function calls flat and the filter calls measurable would be
    # two answers to one question.
    if _no_dispersion(mu, sd):
        sd = 0.0
    dd = max_drawdown(r)
    total = 1.0
    for x in r:
        total *= (1.0 + x)
    out.update({
        "measurable": sd > 0,
        "mean": mu, "stdev": sd,
        # Compounded, so it is the same quantity LEAN's Compounding Annual
        # Return reports (verified: 7.502% stored vs 7.51% recomputed on
        # candidate a663a592ff1d, 36.994% vs 37.02% on 144387901688).
        "ann_return_pct": ((1.0 + mu) ** k - 1.0) * 100.0,
        "ann_vol_pct": sd * math.sqrt(k) * 100.0,
        "max_drawdown_pct": None if dd is None else dd * 100.0,
        "total_return_pct": (total - 1.0) * 100.0,
    })
    if sd <= 0:
        out["reason"] = ("the leg has zero dispersion, so no Sharpe exists for "
                         "it — a constant return is not a risk-adjusted one")
    return out


def sharpe_at_rf(moments: dict[str, Any], rf_pct: float = 0.0) -> float | None:
    """Annualised Sharpe of one leg, excess of a risk-free rate, from its moments.

    The rate arrives as an ANNUAL percentage and is converted to the leg's own
    observation frequency by compounding, ``(1+rf)**(1/K) - 1`` — not by
    dividing by 252, which would be a different rate on a calendar clock.

    Subtracting a constant leaves the standard deviation untouched, so the
    Sharpe is exactly linear in that per-observation constant. That is the
    property the premia criterion's rf-stress test rests on: the DIFFERENCE
    between two legs' Sharpes is linear in rf, so checking it at two endpoints
    checks it over the whole interval between them.

    Returns None rather than a number when the leg was not measurable.
    """
    if not moments or not moments.get("measurable"):
        return None
    k = moments.get("obs_per_year")
    sd = moments.get("stdev")
    mu = moments.get("mean")
    if not k or not sd or sd <= 0 or mu is None:
        return None
    rf_per_obs = (1.0 + float(rf_pct) / 100.0) ** (1.0 / float(k)) - 1.0
    return (mu - rf_per_obs) / sd * math.sqrt(float(k))


def assess_series(returns: Sequence[float], periods_per_year: int = 252,
                  n_trials: int = 1) -> dict[str, Any]:
    """The whole statistical picture for one return series.

    This is what gets attached to a backtest so the UI can say *how much* to
    believe it. Returns ``reliable: False`` with a stated reason whenever the
    sample is too small to support inference — an unreliable verdict is a
    finding, not a failure.
    """
    r = _clean(returns)
    n = len(r)
    if n < MIN_OBS_FOR_INFERENCE:
        return {
            "n_obs": n,
            "reliable": False,
            "reason": f"{n} observations is below the {MIN_OBS_FOR_INFERENCE} needed for "
                      "any of this to mean something",
        }

    sr_period = sharpe_per_period(r)
    ann = annualisation_factor(r, periods_per_year=periods_per_year)
    sr_annual_naive = sr_period * ann["naive_factor"]
    sr_annual = sr_period * ann["factor"]

    # Error bars live on the per-period base, where n_obs is honest, then scale.
    ci_period = sharpe_confidence_interval(sr_period, n)
    trl = min_track_record_length(sr_period, n, returns=r)
    sel = selection_penalty(sr_period, n_trials, n)

    years = n / float(periods_per_year)
    warnings: list[str] = []
    if ci_period.get("includes_zero"):
        warnings.append(
            f"the 95% interval for Sharpe spans zero — {n} observations "
            f"({years:.1f} years) cannot distinguish this from no edge at all"
        )
    if ann.get("usable") and ann["factor"] < ann["naive_factor"] * 0.95:
        warnings.append(
            f"returns are serially correlated; the usual sqrt({periods_per_year}) "
            f"annualisation overstates Sharpe by {ann.get('inflation_vs_naive', 0):.0f}%"
        )
    rho1 = ann["autocorrelations"][0] if ann["autocorrelations"] else 0.0
    if rho1 > 0.2:
        warnings.append(
            f"first-order autocorrelation is {rho1:.2f} — returns look smoothed; "
            "in a fund context that signature usually means stale marks"
        )
    k = kurtosis(r)
    if k > 5.0:
        warnings.append(
            f"kurtosis {k:.1f} (normal is 3.0) — losses cluster in the tail, so "
            "volatility understates what a bad day looks like"
        )
    s = skewness(r)
    if s < -0.5:
        warnings.append(
            f"skew {s:.2f} — the profile is many small gains against occasional "
            "large losses, which is the shape that flatters Sharpe most"
        )
    if sel.get("applies") and not sel.get("clears_noise"):
        warnings.append(sel["note"] + " — this result does not clear that bar")
    if trl.get("usable") and not trl.get("sufficient"):
        warnings.append(
            f"needs ~{trl['required_obs']} observations to call this edge real; "
            f"has {n} ({trl['shortfall_obs']} short)"
        )

    return {
        "n_obs": n,
        "years": round(years, 2),
        "reliable": True,
        "sharpe_per_period": round(sr_period, 5),
        "sharpe_annual": round(sr_annual, 4),
        "sharpe_annual_naive": round(sr_annual_naive, 4),
        "annualisation": ann,
        "confidence_interval_per_period": ci_period,
        "sharpe_annual_low": round(ci_period["low"] * ann["factor"], 4) if ci_period.get("usable") else None,
        "sharpe_annual_high": round(ci_period["high"] * ann["factor"], 4) if ci_period.get("usable") else None,
        "could_be_zero": bool(ci_period.get("includes_zero")),
        "skew": round(s, 4),
        "kurtosis": round(k, 4),
        "min_track_record": trl,
        "selection": sel,
        "warnings": warnings,
    }
