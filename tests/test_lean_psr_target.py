"""Guards LEAN's Probabilistic Sharpe Ratio target against a silent drift back
into the per-candidate spread this fund published and then retracted.

LEAN scores every candidate's PSR against ONE constant:
``1/sqrt(tradingDaysPerYear)`` per observation, an annualised Sharpe of
exactly 1.00, measured on EXCESS returns. The fund spent two dispatches
inverting that constant back out of stored runs instead of reading it off the
engine's own source, and the inversion — done on raw returns and the
candidate's own calendar clock instead of excess returns and the engine's
252-day clock — manufactured a spurious per-candidate hurdle (1.17 to 2.26
annualised). This file pins down the four surfaces in ``app/fund/statistics.py``
that make that mistake impossible to reintroduce silently: the constant
itself, the clock-aware target, the exact algebraic inversion (both
directions — with and without the rf/clock correction), and the recovery of
the engine's own risk-free rate. A regression in any of these should fail a
test here before it fails a verdict.
"""

from __future__ import annotations

import json
import math
import pathlib
import random

import pytest

from app.fund import statistics as st

FIXTURE = json.load(
    open(pathlib.Path(__file__).parent / "fixtures" / "lean_psr_target_candidates.json",
         encoding="utf-8"))


# ---------------------------------------------------------------------------
# A. lean_psr_target() with no argument
# ---------------------------------------------------------------------------

def test_default_target_is_the_engines_constant():
    """Would catch: the fallback clock silently changing from 252, or the
    default target drifting off an annualised Sharpe of 1.00."""
    out = st.lean_psr_target()
    assert out["trading_days_per_year"] == pytest.approx(252.0, abs=0.0)
    assert out["assumed"] is True
    assert out["per_obs"] == pytest.approx(1.0 / math.sqrt(252), abs=1e-12)
    assert out["annualised"] == pytest.approx(1.0, abs=1e-9)
    assert isinstance(out["source"], str) and out["source"]
    assert "PortfolioStatistics.cs" in out["source"]


# ---------------------------------------------------------------------------
# B. Move the clock, do not match the constant
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("k", [200, 252, 260, 365])
def test_target_per_obs_tracks_the_supplied_clock(k):
    """Would catch: a hardcoded 1/sqrt(252) that ignores the caller's own
    trading_days_per_year — this is checked for four different clocks so a
    constant masquerading as clock-aware cannot pass by accident."""
    out = st.lean_psr_target(k)
    assert out["per_obs"] == pytest.approx(1.0 / math.sqrt(k), abs=1e-12)
    assert out["annualised"] == pytest.approx(1.0, abs=1e-9)
    assert out["assumed"] is False


def test_different_clocks_give_different_per_obs_targets():
    """Would catch: the clock argument being accepted but silently discarded
    (per_obs always landing on 1/sqrt(252) regardless of K)."""
    a = st.lean_psr_target(200)["per_obs"]
    b = st.lean_psr_target(365)["per_obs"]
    assert a != pytest.approx(b, abs=1e-9)


# ---------------------------------------------------------------------------
# C. Unusable clocks fall back AND say so
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad", [None, 0, -5, 0.0, "252", True, [], {},
                                 float("nan"), float("inf"), float("-inf")])
def test_unusable_clock_falls_back_and_reports_assumed(bad):
    """Would catch: a falsy-but-numeric clock (0, 0.0) being silently treated
    as unusable without saying so, a non-numeric clock crashing instead of
    falling back, or a bool being accepted as a number (True == 1 in Python,
    which would silently score against K=1).

    NaN AND inf ARE THE CASES THAT ACTUALLY SHIPPED BROKEN, and this list did
    not include them until the Gauntlet ran. Every NaN comparison is False, so
    `k <= 0` did not fire: NaN produced a NaN target reported as READ, and inf
    produced a per-observation target of **0.0** — which on the engine basis
    turns a skill hurdle into a target-zero criterion. A loosening, arriving
    through a malformed field in a stored engine payload. Both live here now.
    """
    out = st.lean_psr_target(bad)
    assert out["trading_days_per_year"] == pytest.approx(252.0, abs=0.0)
    assert out["assumed"] is True


# ---------------------------------------------------------------------------
# D. Exact round trip for implied_target_sharpe
# ---------------------------------------------------------------------------

def _series(seed: int, n: int = 320, mu: float = 0.0006, sd: float = 0.01) -> list[float]:
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


def test_implied_target_sharpe_exact_round_trip():
    """Would catch: any arithmetic slip in the z-inversion
    (SR* = SR_excess - z*sqrt(shape)/sqrt(n-1)) — forming a PSR from a known
    target and then inverting it must recover that target.

    THE TOLERANCE IS THE QUANTISATION, MEASURED, and this test's first draft
    asked for 1e-9 and was refused. The round trip is not exact and cannot be:
    the reported PSR is a PERCENTAGE ROUNDED TO THREE DECIMALS
    (`psr_from_series` -> `round(p * 100.0, 3)`, statistics.py; LEAN's own
    published figure is rounded the same way), so the inversion inherits a
    +/-5e-6 quantisation in p. Through `dz/dp = 1/phi(z)` that lands as roughly
    1e-6 per observation and 1.6e-5 annualised. The two arms below therefore
    assert to 1e-5 per observation and 1e-4 annualised — four orders inside the
    0.02 the real-candidate acceptance test uses, and the honest limit of an
    instrument fed a rounded input.

    A TIGHTER ARM IS KEPT BESIDE IT and it is what separates "the algebra is
    right and the input is quantised" from "the algebra is approximately
    right": fed the probability from `psr_from_moments`, rounded to six
    decimals rather than the percentage's three, the same inversion tightens by
    two orders to 1e-6. The error tracks the input's precision, which is the
    signature of quantisation and not of a formula.
    """
    series = _series(seed=1)
    rf = 0.0002
    target = 1.0 / math.sqrt(252)
    excess = [x - rf for x in series]
    reading = st.psr_from_series(excess, target)
    p = reading["psr_pct"]
    assert p is not None
    out = st.implied_target_sharpe(p, series, rf_per_obs=rf)
    assert out["measurable"] is True
    assert out["target_per_obs"] == pytest.approx(target, abs=1e-5)
    assert out["target_annualised"] == pytest.approx(1.0, abs=1e-4)

    # THE LESS-QUANTISED ARM. `psr_from_series` publishes only the percentage
    # rounded to three decimals; `psr_from_moments` publishes the probability
    # rounded to six, which is a hundred times finer, and the recovered target
    # tightens by the same factor. Sixteen decimals are available from neither,
    # so "exact" is not on the menu at any layer — which is the finding.
    mu_e, sd_e = st.mean_std(excess)
    finer = st.psr_from_moments(len(excess), mu_e / sd_e, st.skewness(excess),
                                st.kurtosis(excess), target)
    assert finer["usable"], finer
    exact = st.implied_target_sharpe(finer["psr"] * 100.0, series,
                                     rf_per_obs=rf)
    assert exact["target_per_obs"] == pytest.approx(target, abs=1e-6)
    # and the two arms DISAGREE, which is what makes the looser tolerance above
    # a measurement of the rounding rather than a shrug.
    assert exact["target_per_obs"] != out["target_per_obs"]


# ---------------------------------------------------------------------------
# E. rf matters
# ---------------------------------------------------------------------------

def test_implied_target_sharpe_rf_shifts_target_by_rf_over_sd():
    """Would catch: implied_target_sharpe ignoring rf_per_obs entirely (the
    exact defect this fund shipped: inverting on raw returns instead of
    excess returns), which would make the rf=0 and rf=0.0002 answers
    identical instead of differing by about rf/sd.

    `rf/sd` IS THE LEADING TERM AND NOT THE WHOLE GAP, measured after this
    test's first draft demanded `rel=1e-6` and was refused. The observed Sharpe
    does shift by exactly rf/sd, but the recovered target is
    `sr - z*sqrt(shape(sr))/sqrt(n-1)` and `shape` is itself a function of sr,
    so the correction term is the SAME ORDER in rf as rf/sd and the relative
    discrepancy does not vanish as rf shrinks — it converges to a ratio set by
    z, skew, kurtosis and n. Measured here: 0.49% on this series. The assertion
    is therefore a 2% band around the leading term, which is still far tighter
    than the defect it guards (ignoring rf gives a gap of exactly ZERO).
    """
    series = _series(seed=2)
    rf = 0.0002
    target = 1.0 / math.sqrt(252)
    excess = [x - rf for x in series]
    p = st.psr_from_series(excess, target)["psr_pct"]

    with_rf = st.implied_target_sharpe(p, series, rf_per_obs=rf)
    without_rf = st.implied_target_sharpe(p, series, rf_per_obs=0.0)
    assert with_rf["measurable"] is True
    assert without_rf["measurable"] is True

    _, sd = st.mean_std(series)
    gap = without_rf["target_per_obs"] - with_rf["target_per_obs"]
    assert without_rf["target_per_obs"] > with_rf["target_per_obs"]
    assert gap == pytest.approx(rf / sd, rel=0.02)
    # THE DEFECT'S OWN VALUE, asserted separately: a leg that ignored rf would
    # return a gap of zero, and `approx(rf/sd, rel=0.02)` alone would not say
    # how far that is from passing.
    assert gap > 0.5 * (rf / sd)


# ---------------------------------------------------------------------------
# F. The clock matters for annualisation
# ---------------------------------------------------------------------------

def test_implied_target_sharpe_clock_scales_annualisation():
    """Would catch: target_annualised being computed with a hardcoded
    sqrt(252) instead of sqrt(trading_days_per_year) — the annualised figure
    for a 365-day clock must be strictly larger than the 252-day one for the
    identical per-observation target."""
    series = _series(seed=3)
    rf = 0.0002
    target = 1.0 / math.sqrt(252)
    excess = [x - rf for x in series]
    p = st.psr_from_series(excess, target)["psr_pct"]

    at_252 = st.implied_target_sharpe(p, series, rf_per_obs=rf, trading_days_per_year=252)
    at_365 = st.implied_target_sharpe(p, series, rf_per_obs=rf, trading_days_per_year=365)
    assert at_252["measurable"] is True
    assert at_365["measurable"] is True

    assert at_365["target_annualised"] == pytest.approx(
        at_365["target_per_obs"] * math.sqrt(365), abs=1e-9)
    assert at_365["target_annualised"] > at_252["target_annualised"]


# ---------------------------------------------------------------------------
# G. Absence/refusal paths for implied_target_sharpe
# ---------------------------------------------------------------------------

_SOME_SERIES = _series(seed=4)

_REFUSAL_CASES = [
    pytest.param(0.0, _SOME_SERIES, 0.0, "infinity", id="psr_zero"),
    pytest.param(100.0, _SOME_SERIES, 0.0, "infinity", id="psr_hundred"),
    pytest.param(50.0, None, 0.0, None, id="returns_none"),
    pytest.param(50.0, [0.5], 0.0, None, id="returns_single_obs"),
    pytest.param(50.0, [0.001] * 100, 0.0, None, id="returns_flat"),
    pytest.param("x", _SOME_SERIES, 0.0, "not a number", id="psr_not_a_number"),
    # MUTATION M08. Both of these refuse either way — a non-finite rf turns
    # every return non-finite and `_clean` drops them, so the series goes empty
    # and the function refuses for the WRONG REASON. A reader chasing a bad rate
    # would be sent to look for a missing series. The two absences are different
    # facts, so the reason is asserted and not just the refusal.
    pytest.param(50.0, _SOME_SERIES, float("nan"), "risk-free rate", id="rf_is_nan"),
    pytest.param(50.0, _SOME_SERIES, float("inf"), "risk-free rate", id="rf_is_inf"),
    pytest.param(50.0, _SOME_SERIES, "x", "risk-free rate", id="rf_not_a_number"),
]


@pytest.mark.parametrize("psr_pct, returns, rf_per_obs, reason_substr", _REFUSAL_CASES)
def test_implied_target_sharpe_refuses_without_a_number(psr_pct, returns, rf_per_obs, reason_substr):
    """Would catch: any of these unmeasurable inputs (PSR pinned at the
    normal-inverse's infinity, an absent/degenerate/flat series, a
    non-numeric PSR, a non-finite rf) silently producing a fabricated
    target_per_obs / target_annualised instead of refusing with a reason."""
    out = st.implied_target_sharpe(psr_pct, returns, rf_per_obs=rf_per_obs)
    assert out["measurable"] is False
    assert out["target_per_obs"] is None
    assert out["target_annualised"] is None
    if reason_substr is not None:
        assert reason_substr in out["reason"]


# ---------------------------------------------------------------------------
# H. engine_risk_free_per_obs exact inversion
# ---------------------------------------------------------------------------

def test_engine_risk_free_per_obs_exact_inversion():
    """Would catch: any arithmetic slip in inverting
    rf_annual = (1+mean(r))^K - 1 - SharpeRatio*AnnualStdDev — this is exact
    closed-form algebra, constructed so the true answer is known up front."""
    series = _series(seed=5)
    mu, sd = st.mean_std(series)
    k = 252
    rf_annual = 0.0525
    annual_perf = (1.0 + mu) ** k - 1.0
    asd = sd * math.sqrt(k)
    sharpe = (annual_perf - rf_annual) / asd

    out = st.engine_risk_free_per_obs(sharpe, asd, series, k)
    assert out["measurable"] is True
    assert out["rf_annual"] == pytest.approx(0.0525, abs=1e-12)
    assert out["rf_per_obs"] == pytest.approx(0.0525 / 252, abs=1e-15)
    assert out["reproduces_annual_stdev"] is True
    assert out["annual_stdev_gap"] == pytest.approx(0.0, abs=1e-12)


# ---------------------------------------------------------------------------
# I. engine_risk_free_per_obs refusals
# ---------------------------------------------------------------------------

_SOME_SERIES_I = _series(seed=6)

_RF_REFUSAL_CASES = [
    pytest.param(None, 0.12, _SOME_SERIES_I, id="sharpe_none"),
    pytest.param(1.0, None, _SOME_SERIES_I, id="stdev_none"),
    pytest.param(True, 0.12, _SOME_SERIES_I, id="sharpe_is_bool"),
    pytest.param(1.0, 0.12, [], id="returns_empty"),
    pytest.param(1.0, 0.12, [0.01], id="returns_single_obs"),
    pytest.param(1.0, 0.12, [0.001] * 50, id="returns_flat"),
]


@pytest.mark.parametrize("published_sharpe, published_annual_stdev, returns", _RF_REFUSAL_CASES)
def test_engine_risk_free_per_obs_refuses_without_a_number(published_sharpe, published_annual_stdev, returns):
    """Would catch: a bool being accepted as a numeric Sharpe/stdev (True is
    an int in Python and would silently score as 1.0), or an absent/short/
    flat series producing a fabricated rate instead of refusing."""
    out = st.engine_risk_free_per_obs(published_sharpe, published_annual_stdev, returns)
    assert out["measurable"] is False
    assert out["rf_per_obs"] is None
    assert isinstance(out["reason"], str) and out["reason"]


# ---------------------------------------------------------------------------
# J. reproduces_annual_stdev is a report, not a gate
# ---------------------------------------------------------------------------

def test_reproduces_annual_stdev_reports_but_does_not_block():
    """Would catch: reproduces_annual_stdev being wired as a hard gate that
    flips measurable to False on a mismatch, instead of the documented
    behaviour of reporting the gap and still returning a rate."""
    series = _series(seed=7)
    mu, sd = st.mean_std(series)
    k = 252
    rf_annual = 0.03
    annual_perf = (1.0 + mu) ** k - 1.0
    true_asd = sd * math.sqrt(k)
    sharpe = (annual_perf - rf_annual) / true_asd

    wrong_asd = true_asd + 0.01
    out = st.engine_risk_free_per_obs(sharpe, wrong_asd, series, k)
    assert out["measurable"] is True
    assert isinstance(out["rf_per_obs"], float)
    assert out["reproduces_annual_stdev"] is False
    assert out["annual_stdev_gap"] == pytest.approx(0.01, abs=1e-9)


# ---------------------------------------------------------------------------
# K. The real-candidate acceptance test
# ---------------------------------------------------------------------------

def test_corrected_inversion_lands_near_one_on_real_candidates():
    """Would catch: the excess-returns/252-clock correction breaking on real
    engine output — the whole reason this instrument exists. Tolerance basis
    (stated, not invented): measured over all 336 invertible stored
    candidates the corrected inversion has median 0.9996, and the three
    fixture candidates individually read 1.00706 / 0.99918 / 0.99913; the
    residual is the estimators' skew/kurtosis differing from MathNet's, not
    the target moving, so 0.02 absolute is generous against that measured
    spread."""
    k = FIXTURE["trading_days_per_year"]
    assert k == 252
    for cand in FIXTURE["candidates"]:
        returns = cand["daily_returns"]
        rf = st.engine_risk_free_per_obs(
            cand["published_sharpe_ratio"],
            cand["published_annual_standard_deviation"],
            returns, k)
        assert rf["measurable"] is True, cand["job_id"]
        assert 0.0 <= rf["rf_annual"] <= 0.10, cand["job_id"]

        implied = st.implied_target_sharpe(
            cand["published_psr_pct"], returns,
            rf_per_obs=rf["rf_per_obs"], trading_days_per_year=k)
        assert implied["measurable"] is True, cand["job_id"]
        assert implied["target_annualised"] == pytest.approx(1.0, abs=0.02), cand["job_id"]


# ---------------------------------------------------------------------------
# L. The discriminating half of K
# ---------------------------------------------------------------------------

def test_uncorrected_inversion_overshoots_on_the_same_candidates():
    """Would catch: test K passing vacuously because the correction does
    nothing observable — this shows the SAME three candidates, inverted with
    no rf (raw returns, not excess) and no explicit clock, land well above
    the true annualised-1.00 target, which is what proves the correction in
    test K is load-bearing rather than a no-op."""
    for cand in FIXTURE["candidates"]:
        uncorrected = st.implied_target_sharpe(
            cand["published_psr_pct"], cand["daily_returns"])
        assert uncorrected["measurable"] is True, cand["job_id"]
        assert uncorrected["target_annualised"] > 1.20, cand["job_id"]
