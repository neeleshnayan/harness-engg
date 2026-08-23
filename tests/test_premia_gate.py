"""Gate v5r1: the premia bar, and the alpha bar's byte-identity beside it.

Every test here guards a specific way this criterion could be wrong, and the
named incidents are in the docstrings. The two that matter most:

  * THE CONSTITUTION'S OWN WORKED FAILURE (2026-08-21 amendment): "under rf=0
    with free leverage, T-bill carry impersonates edge". A cash-heavy mix must
    not certify as premia. ``test_the_cash_heavy_impersonator_*``.
  * THE DISCARDED BENCHMARK LEG (measured on four stored candidates,
    2026-08-23): ``daily_returns["benchmark"]`` is the series the belt threw
    away, and judging off it FLIPS the premia answer on three of the four.
    ``test_premia_inputs.py`` guards it.
"""
from __future__ import annotations

import datetime
import math

import pytest

from app.fund import statistics as st
from app.fund.gate import (CLAIM_TYPES, CRITERIA, GATE_VERSION,
                           GATE_VERSION_PREMIA, PREMIA_CRITERIA,
                           PREMIA_VERSION, evaluate)
from app.fund.leanrunner import premia_inputs

DAY0 = datetime.date(2021, 1, 4)


def _dates(n: int) -> list[str]:
    """n consecutive TRADING days (weekends skipped), as the belt's bar dates are."""
    out, d = [], DAY0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def _clock(dates: list[str]) -> float:
    """The observations-per-year the code under test will itself derive.

    Taken from the same function the gate uses rather than assumed to be 252 —
    a fixture that hardcodes an annualisation constant cannot test a criterion
    whose whole design is that the constant is derived.
    """
    got = st.observations_per_year(dates, len(dates))
    assert got["usable"], got
    return float(got["obs_per_year"])


def series_with_moments(dates: list[str], ann_return_pct: float,
                        ann_vol_pct: float, seed: int = 11) -> list[float]:
    """A deterministic return series with EXACTLY the requested annual moments.

    A pseudo-random shape, then re-centred and re-scaled so the realised
    moments hit the targets on THIS series' own clock to machine precision.
    Fixtures whose moments are only approximately right cannot pin a criterion
    that turns on a third decimal.

    ``ann_return_pct`` is the ARITHMETIC annualised mean, so that
    ``ann_return_pct / ann_vol_pct`` is the series' annualised Sharpe exactly —
    which is what lets a fixture be specified from a published Sharpe and a
    published volatility without a solver in the middle.
    """
    n = len(dates)
    k = _clock(dates)
    x = seed
    raw: list[float] = []
    for _ in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        raw.append(x / 2 ** 31 - 0.5)
    mu = sum(raw) / n
    var = sum((r - mu) ** 2 for r in raw) / (n - 1)
    sd = math.sqrt(var)
    target_sd = (ann_vol_pct / 100.0) / math.sqrt(k)
    target_mu = (ann_return_pct / 100.0) / k
    return [target_mu + (r - mu) / sd * target_sd for r in raw]


def rdates(n: int) -> list[str]:
    """The n dates a series of n RETURNS sits on (one behind the curve's)."""
    return _dates(n + 1)[1:]


def cdates(n: int) -> list[str]:
    """The n+1 dates the LEVEL curve behind those n returns sits on."""
    return _dates(n + 1)


R400 = rdates(400)
R600 = rdates(600)


def curve_from(returns: list[float], start: float = 100.0) -> list[float]:
    out, lvl = [], start
    for r in returns:
        out.append(lvl)
        lvl *= (1.0 + r)
    out.append(lvl)
    return out


def make_result(strategy: list[float], benchmark: list[float],
                engine_leg: list[float] | None = None,
                **over) -> dict:
    """A belt result carrying a measurable premia pair, everything else clean.

    ``engine_leg`` is what ``daily_returns["benchmark"]`` holds. It defaults to
    the same series as the bar so a test that is not about the discarded-leg
    defect is not silently exercising it.
    """
    n = len(strategy)
    # The benchmark leg is DERIVED from a level curve, exactly as the belt
    # derives it, so the test exercises the real path rather than injecting
    # returns the production code never builds.
    bcurve = curve_from(benchmark)
    res = {
        "total_return_pct": 40.0, "benchmark_return_pct": 20.0,
        "capacity": {"capacity_usd": 5_000_000.0},
        "robustness": {"psr_pct": 92.0, "total_orders": 300,
                       "costs": {"slippage_modelled": True}},
        "daily_returns": {
            "present": True, "dates": rdates(n),
            "strategy": strategy,
            "benchmark": (engine_leg if engine_leg is not None else benchmark),
            "benchmark_present": True, "n": n},
        "benchmark_curve": bcurve,
        "benchmark_dates": cdates(n),
        "benchmark_series_source": "recomputed_basket",
    }
    res.update(over)
    res["premia_inputs"] = premia_inputs(res)
    return res


CLEAN_HOLDOUT = {
    "state": "done",
    "train": {"return_pct": 20.0, "window": ["2021-01-01", "2021-12-31"]},
    "test": {"return_pct": 18.0, "total_orders": 40,
             "window": ["2022-01-01", "2022-12-31"]},
}
CLEAN_SWEEP = {"breakeven_cost": {"breakeven_bps": 45.0}}
CLEAN_WALK = {"folds_measurable": 4, "folds_retained": 4,
              "median_retention": 0.9,
              "requested_folds": [
                  {"train_start": "2021-01-01", "train_end": "2021-12-31",
                   "test_start": "2022-01-01", "test_end": "2022-03-31"},
                  {"train_start": "2021-04-01", "train_end": "2022-03-31",
                   "test_start": "2022-04-01", "test_end": "2022-06-30"},
                  {"train_start": "2021-07-01", "train_end": "2022-06-30",
                   "test_start": "2022-07-01", "test_end": "2022-09-30"},
                  {"train_start": "2021-10-01", "train_end": "2022-09-30",
                   "test_start": "2022-10-01", "test_end": "2022-12-31"}]}


def judge(result, claim_type=None, **kw):
    return evaluate(result, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    claim_type=claim_type, **kw)


def premia_failures(verdict) -> list[str]:
    """Only the sentences the premia leg can emit."""
    marks = ("risk-adjusted", "premia comparison", "deeper hole",
             "share only", "premium")
    return [f for f in verdict["failures"] if any(m in f for m in marks)]


# --- the alpha bar did not move ------------------------------------------

def test_the_alpha_criteria_dict_is_byte_identical_to_v43():
    """Every threshold, hardcoded — a test that reads CRITERIA cannot pin it.

    D16/D21: asserting `mine == CRITERIA[key]` cannot distinguish a hardcoded
    duplicate from a read, and a test parametrised by the constant it guards
    moves with the constant. So the whole v4.3 bar is written out here, and any
    edit to a threshold — in either direction — kills this test by name.
    """
    assert CRITERIA == {
        "min_psr_pct": 65.0,
        "min_orders": 20,
        "must_beat_benchmark": True,
        "min_breakeven_bps": 10.0,
        "require_breakeven_measured": True,
        "min_holdout_retention": 0.5,
        "min_walkforward_folds": 4,
        "min_walkforward_folds_retained_share": 0.5,
        "require_walkforward": True,
        "min_decisions_per_test_leg": 4,
        "require_priced": True,
        "min_capacity_usd": 100_000.0,
        "require_capacity_measured": True,
    }


def test_no_premia_knob_leaked_into_the_alpha_bar():
    """PREMIA_CRITERIA is separate so CRITERIA_V1..V3 gain no fiction.

    The doctrine's stage-07 check requires every preserved gate version to
    describe its bar COMPLETELY. A premia key in CRITERIA would have to be
    backfilled into v1, v2 and v3 with an invented value describing a criterion
    those versions had no concept of.
    """
    assert not [k for k in CRITERIA if k.startswith("premia")]
    assert set(PREMIA_CRITERIA) == {
        "premia_min_sharpe_advantage",
        "premia_require_drawdown_not_worse",
        "premia_rf_stress_pct",
        "premia_require_majority_window_coverage",
    }


def test_the_two_version_stamps_are_pinned_and_move_together():
    """Hardcoded from both sides, per the D21 lesson about self-reading pins."""
    assert PREMIA_VERSION == "v5r1"
    assert GATE_VERSION_PREMIA == "v5r1-premia"
    assert GATE_VERSION == "v4.3"


@pytest.mark.parametrize("claim", [None, "alpha"])
def test_an_alpha_verdict_is_unchanged_by_this_version(claim):
    """The default and the explicit word give the same verdict, stamped v4.3.

    The full identity claim — against the PRE-CHANGE tree over 62 enumerated
    cases, 24 distinct failure sentences and 2 passes — was measured with a
    second worktree at the base commit (builder D23; the D20 method). What this
    test can guard in-tree is that the new argument changes nothing when it is
    absent or says alpha, and that the premia leg never runs.
    """
    strat = series_with_moments(R400, 18.0, 12.0, seed=5)
    bench = series_with_moments(R400, 9.0, 20.0, seed=6)
    out = judge(make_result(strat, bench), claim_type=claim)
    assert out["gate_version"] == "v4.3"
    assert out["criteria"] == CRITERIA
    assert "premia" not in out["checks"]
    assert out["checks"]["claim_type"] == "alpha"
    assert out["checks"]["must_beat_benchmark_applied"] is True
    assert premia_failures(out) == []


def test_an_unrecognised_claim_type_is_judged_as_alpha_AND_fails():
    """Fail closed in BOTH directions: a typo must not select a bar.

    Not merely "defaults to alpha" — that would let `premai` inherit the alpha
    bar silently and pass. And not "defaults to premia" either, obviously. It
    is judged by the alpha criteria and fails for the declaration.
    """
    strat = series_with_moments(R400, 40.0, 12.0, seed=5)
    bench = series_with_moments(R400, 9.0, 20.0, seed=6)
    out = judge(make_result(strat, bench), claim_type="premai")
    assert out["gate_version"] == "v4.3"
    assert out["criteria"] == CRITERIA
    assert "premia" not in out["checks"]
    assert out["checks"]["claim_type_recognised"] is False
    assert any("unrecognised claim type" in f for f in out["failures"])
    assert out["passed"] is False


def test_the_claim_types_the_gate_knows_are_exactly_two():
    assert CLAIM_TYPES == ("alpha", "premia")


# --- the criterion the constitution asked for ----------------------------

def cash_mix(bench: list[float], weight: float, rf_true_pct: float,
             dates: list[str] | None = None) -> list[float]:
    """w of the benchmark plus (1-w) of cash earning ``rf_true_pct`` a year.

    Zero skill by construction: nothing here forecasts anything. The mix's
    Sharpe EXCESS OF the true cash rate is exactly the benchmark's, because
    sd(mix) = w*sd(bench) and mean(mix) - rf = w*(mean(bench) - rf).
    """
    k = _clock(dates or rdates(len(bench)))
    rf_d = (1.0 + rf_true_pct / 100.0) ** (1.0 / k) - 1.0
    return [weight * r + (1.0 - weight) * rf_d for r in bench]


def test_the_cash_heavy_impersonator_fails_the_premia_bar():
    """THE CONSTITUTION'S OWN WORKED FAILURE, reproduced and refused.

    Amendment of 2026-08-21, verbatim: "under rf=0 with free leverage, T-bill
    carry impersonates edge". A 30/70 mix of the benchmark and cash has ZERO
    skill — it forecasts nothing — and under rf=0 it posts a materially higher
    Sharpe than the benchmark, because the cash leg adds return at no
    volatility. It must not certify.

    The failing sentence must be the RF one. If the mix ever fails on drawdown
    or coverage instead, this test has stopped testing the thing it names.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    mix = cash_mix(bench, weight=0.30, rf_true_pct=3.5)
    out = judge(make_result(mix, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] > 0.30, p           # looks like edge at rf=0
    assert p["sharpe_advantage_at_stress"] < 0, p    # and is gone at 4%
    assert p["rf_sensitive"] is True
    assert p["drawdown_not_worse"] is True, "must not fail on the wrong leg"
    assert p["coverage_majority"] is True, "must not fail on the wrong leg"
    assert out["passed"] is False
    fails = premia_failures(out)
    assert len(fails) == 1, fails
    assert "DISAPPEARS at rf=4.0%" in fails[0]
    assert out["gate_version"] == "v5r1-premia"


def test_the_impersonators_breakeven_rate_is_the_rate_it_earned():
    """The reported crossing rate must be the mix's own cash rate, not a fit.

    For a cash mix the Sharpe difference vanishes EXACTLY at the rate the cash
    leg earns — that is the arithmetic, not an approximation — so this is a
    closed-form check on ``rf_breakeven_pct`` rather than a tolerance around a
    number somebody eyeballed.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    out = judge(make_result(cash_mix(bench, 0.30, 3.5), bench),
                claim_type="premia")
    assert out["checks"]["premia"]["rf_breakeven_pct"] == pytest.approx(
        3.5, abs=0.01)


def test_a_genuine_vol_scaler_clears_the_premia_bar():
    """Lower volatility AND a real edge: the shape the sleeve exists for.

    Half the benchmark's volatility at three quarters of its return is not
    reachable by mixing the benchmark with cash — that mix would return
    0.5*20 + 0.5*rf, well under 15 at any plausible rate — so the advantage
    survives the stress and the claim is established.
    """
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    strat = series_with_moments(R600, 15.0, 12.0, seed=32)
    out = judge(make_result(strat, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] > 0
    assert p["sharpe_advantage_at_stress"] > 0
    assert p["rf_sensitive"] is False
    assert premia_failures(out) == [], out["failures"]
    assert out["passed"] is True
    assert out["gate_version"] == "v5r1-premia"


def test_the_VOLSCALE_archetype_fails_the_rf_stress_AND_THAT_IS_THE_FINDING():
    """The validator's flagship premia archetype does not clear this bar.

    VALIDATOR_JOINTPOWER_2026-08-23.md, verbatim: "VOLSCALE: SR 0.57 on 27% vol
    vs holding's 0.54 on 44% — the exact shape the constitution protects."
    Those four numbers are the fixture, and they are the archetype's REPORTED
    MOMENTS rather than its return path, which is not in the record this seat
    could read (the run `run-validator-jointpower` is not in the desk store).

    At the fund's own measured cash rate those moments do not describe a
    premium. Excess Sharpe at 4%: (15.39-4)/27 = 0.4219 for VOLSCALE against
    (23.76-4)/44 = 0.4491 for holding. The crossing is at 2.1%/yr, and the
    validator measured this fund's window paying 3.97% (BIL). A 61.4% META /
    38.6% cash portfolio — zero skill, one decision — reproduces VOLSCALE's
    27.0% volatility at a HIGHER excess Sharpe, 0.4491 against 0.4219.

    So this test does not assert that the criterion is right. It asserts what
    the criterion SAYS about the archetype the CEO's decision was taken on, so
    that the trade-off is on the record and reversing it costs one number.
    """
    bench = series_with_moments(R600, 23.76, 44.0, seed=41)
    strat = series_with_moments(R600, 15.39, 27.0, seed=42)
    res = make_result(strat, bench)
    got = res["premia_inputs"]
    # The fixture really does carry the archetype's moments.
    assert got["strategy"]["ann_vol_pct"] == pytest.approx(27.0, abs=0.05)
    assert got["benchmark"]["ann_vol_pct"] == pytest.approx(44.0, abs=0.05)
    out = judge(res, claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_strategy"] == pytest.approx(0.57, abs=0.02)
    assert p["sharpe_benchmark"] == pytest.approx(0.54, abs=0.02)
    assert p["sharpe_advantage"] > 0                  # premia at rf=0
    assert p["sharpe_advantage_at_stress"] < 0        # and not at 4%
    assert p["rf_sensitive"] is True
    assert p["rf_breakeven_pct"] == pytest.approx(2.12, abs=0.02)
    assert out["passed"] is False


def test_a_premia_claim_that_trails_its_benchmark_on_TOTAL_return_can_pass():
    """The constitution: premia "does NOT need to beat buy-and-hold, and must
    not be judged as if it should". This is the whole point of the branch.
    """
    bench = series_with_moments(R600, 30.0, 40.0, seed=51)
    strat = series_with_moments(R600, 16.0, 12.0, seed=52)
    # THE HEADLINE NUMBERS TRAIL TOO, which is what makes this a test of the
    # replacement rather than of the premia leg alone. Mutation caught the
    # earlier version: turning the `elif` into an `if` — so that
    # `must_beat_benchmark` applied to premia claims as well — survived,
    # because the fixture's headline said the strategy beat its bar.
    res = make_result(strat, bench, total_return_pct=10.0,
                      benchmark_return_pct=80.0)
    out = judge(res, claim_type="premia")
    p = out["checks"]["premia"]
    assert p["beats_benchmark_total_return"] is False
    assert out["checks"]["must_beat_benchmark_applied"] is False
    assert not any("expensive way to hold the underlying" in f
                   for f in out["failures"]), out["failures"]
    assert out["passed"] is True
    # And the same evidence fails the ALPHA bar, on the sentence it always did.
    alpha = judge(res)
    assert alpha["checks"]["must_beat_benchmark_applied"] is True
    assert any("expensive way to hold the underlying" in f
               for f in alpha["failures"])


def test_a_deeper_drawdown_fails_even_with_a_sharpe_advantage():
    """Better risk-adjusted must not mean a bigger hole.

    Measured to bite on real evidence: stored candidate 01b61967c933 has a
    +0.054 Sharpe advantage and a 28.67% drawdown against its bar's 28.42%.
    """
    bench = series_with_moments(R600, 8.0, 14.0, seed=61)
    strat = list(series_with_moments(R600, 45.0, 14.0, seed=62))
    # One deliberate crash, deep enough to beat the benchmark's worst fall
    # while leaving the Sharpe advantage intact — measured: advantage +0.97,
    # drawdown 26.4% against the bar's 22.2%.
    strat[300] = -0.25
    out = judge(make_result(strat, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] > 0
    assert p["drawdown_not_worse"] is False
    assert any("deeper hole" in f for f in out["failures"])
    assert out["passed"] is False


def test_holding_the_bar_is_not_a_premium_over_holding_the_bar():
    """The exact-tie case, and it is the one the strict inequality is FOR.

    A strategy whose returns ARE the benchmark's has advantage exactly 0.00 at
    every risk-free rate and exactly the same drawdown, so every non-strict
    comparison in the criterion certifies it. Mutation found this gap: turning
    ``adv0 > margin`` into ``adv0 >= margin`` survived the whole suite.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    # The strategy leg is taken through the SAME arithmetic as the benchmark
    # leg — levels, then differences. Handing the raw list to one side and a
    # curve-derived series to the other makes the two disagree in the last bits
    # and turns an exact tie into a 1e-14 difference, which is a fact about
    # float addition rather than about the criterion.
    from app.fund.leanrunner import _returns_from_curve
    same = _returns_from_curve(curve_from(bench), cdates(600))
    strat = [same[d] for d in rdates(600)]
    out = judge(make_result(strat, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] == 0.0
    assert p["drawdown_not_worse"] is True          # equal, so "not worse"
    assert any("no premium over owning the thing" in f for f in out["failures"])
    assert out["passed"] is False


def test_exactly_half_the_window_is_not_a_majority_of_it():
    """The strict-majority boundary, at the value where strict matters.

    Mutation found this too: ``common * 2 >= total`` survived, because no
    fixture landed on exactly half. The integer form is deliberate — the
    walk-forward majority uses the same shape for the same reason.
    """
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    strat = series_with_moments(R600, 15.0, 12.0, seed=32)
    res = make_result(strat, bench)
    res["benchmark_curve"] = curve_from(bench[:300])
    res["benchmark_dates"] = cdates(300)
    res["premia_inputs"] = premia_inputs(res)
    assert res["premia_inputs"]["coverage"] == {
        "common_days": 300, "strategy_days": 600, "fraction": 0.5}
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["coverage_majority"] is False
    assert any("share only 300 of the strategy's 600" in f
               for f in out["failures"])


def test_no_sharpe_advantage_fails_with_the_no_premium_sentence():
    bench = series_with_moments(R600, 25.0, 15.0, seed=71)
    strat = series_with_moments(R600, 6.0, 15.0, seed=72)
    out = judge(make_result(strat, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] < 0
    # Not "rf sensitive": there was no premium to lose.
    assert p["rf_sensitive"] is False
    assert any("no premium over owning the thing" in f for f in out["failures"])


# --- the two endpoints ARE the interval ----------------------------------

@pytest.mark.parametrize("sv,bv", [(12.0, 24.0), (24.0, 12.0), (18.0, 18.0),
                                   (30.0, 8.0), (8.0, 30.0)])
def test_checking_two_endpoints_checks_every_rate_between_them(sv, bv):
    """The affine argument, executed rather than asserted.

    The premia rule evaluates the Sharpe advantage at rf=0 and rf=4 only, and
    claims that this establishes it over the whole interval. If the difference
    were not affine in the per-observation rate, a candidate could dip negative
    in the middle and pass both ends — so the claim is checked at 41 rates
    against the two the criterion actually evaluates.
    """
    s = st.leg_moments(series_with_moments(R600, 14.0, sv, seed=81), R600)
    b = st.leg_moments(series_with_moments(R600, 12.0, bv, seed=82), R600)
    ends = min(st.sharpe_at_rf(s, 0.0) - st.sharpe_at_rf(b, 0.0),
               st.sharpe_at_rf(s, 4.0) - st.sharpe_at_rf(b, 4.0))
    interior = min(st.sharpe_at_rf(s, i / 10.0) - st.sharpe_at_rf(b, i / 10.0)
                   for i in range(41))
    assert interior == pytest.approx(ends, abs=1e-9)


def test_the_stress_cannot_fail_a_candidate_at_or_above_its_bars_volatility():
    """Why the stress is unconditional and needs no "materially below" number.

    The slope of the advantage in rf is sqrt(K)*(1/sd_bench - 1/sd_strategy),
    so it is non-negative whenever the strategy is at least as volatile as its
    bar — the stress is then strictly weaker than the rf=0 check and cannot
    fail anything. This is what lets the criterion drop the brief's
    "materially below" condition instead of inventing a threshold for it.
    """
    bench = series_with_moments(R600, 10.0, 15.0, seed=91)
    strat = series_with_moments(R600, 24.0, 22.0, seed=92)
    out = judge(make_result(strat, bench), claim_type="premia")
    p = out["checks"]["premia"]
    assert p["strategy_ann_vol_pct"] > p["benchmark_ann_vol_pct"]
    assert p["sharpe_advantage_at_stress"] > p["sharpe_advantage"]
    assert p["rf_sensitive"] is False


# --- the thresholds are READ, not copied ---------------------------------

def test_moving_the_stress_rate_moves_the_verdict():
    """D16: to prove a value is READ rather than COPIED, MOVE it."""
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    res = make_result(cash_mix(bench, 0.30, 3.5), bench)
    assert judge(res, claim_type="premia")["passed"] is False
    # Below the mix's own 3.5% cash rate the impersonation survives — which is
    # exactly the loosening the shipped 4.0 is chosen to prevent.
    loose = judge(res, claim_type="premia",
                  premia_criteria={"premia_rf_stress_pct": 1.0})
    assert loose["checks"]["premia"]["rf_sensitive"] is False
    assert loose["passed"] is True


def test_moving_the_sharpe_margin_moves_the_verdict():
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    res = make_result(series_with_moments(R600, 15.0, 12.0, seed=32), bench)
    assert judge(res, claim_type="premia")["passed"] is True
    strict = judge(res, claim_type="premia",
                   premia_criteria={"premia_min_sharpe_advantage": 5.0})
    assert strict["passed"] is False
    assert any("no premium over owning the thing" in f
               for f in strict["failures"])


def test_switching_off_the_drawdown_condition_moves_the_verdict():
    bench = series_with_moments(R600, 8.0, 14.0, seed=61)
    strat = list(series_with_moments(R600, 45.0, 14.0, seed=62))
    strat[300] = -0.25
    res = make_result(strat, bench)
    assert judge(res, claim_type="premia")["passed"] is False
    off = judge(res, claim_type="premia",
                premia_criteria={"premia_require_drawdown_not_worse": False})
    assert off["checks"]["premia"]["drawdown_not_worse"] is False
    assert off["passed"] is True


def test_switching_off_the_coverage_condition_moves_the_verdict():
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    strat = series_with_moments(R600, 15.0, 12.0, seed=32)
    # A bar that covers only the first third of the strategy's record.
    res = make_result(strat, bench)
    res["benchmark_curve"] = curve_from(bench[:180])
    res["benchmark_dates"] = cdates(180)
    res["premia_inputs"] = premia_inputs(res)
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["coverage_majority"] is False
    assert any("a comparison over a minority of the run" in f
               for f in out["failures"])
    off = judge(res, claim_type="premia", premia_criteria={
        "premia_require_majority_window_coverage": False})
    assert not any("minority of the run" in f for f in off["failures"])


# --- absence is never a pass ---------------------------------------------

def test_a_premia_claim_with_no_captured_inputs_fails():
    """Every candidate judged before v5r1 is this case, and none of them pass."""
    strat = series_with_moments(R400, 18.0, 12.0, seed=5)
    bench = series_with_moments(R400, 9.0, 20.0, seed=6)
    res = make_result(strat, bench)
    res.pop("premia_inputs")
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["measurable"] is False
    assert any("premia comparison could not be measured" in f
               for f in out["failures"])
    assert out["passed"] is False


def test_a_premia_claim_whose_benchmark_leg_is_absent_fails():
    strat = series_with_moments(R400, 18.0, 12.0, seed=5)
    res = make_result(strat, series_with_moments(R400, 9.0, 20.0, seed=6))
    res.pop("benchmark_curve")
    res.pop("benchmark_dates")
    res["benchmark_unavailable"] = "only 2 of 20 names in the bar had usable bars"
    res["premia_inputs"] = premia_inputs(res)
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["measurable"] is False
    assert any("only 2 of 20 names" in f for f in out["failures"])
    assert out["passed"] is False


def test_a_malformed_stored_payload_fails_the_leg_and_never_raises():
    """A gate must return a VERDICT, not a traceback.

    ``_premia_leg`` reads a STORED payload — an older belt's, a JSON
    round-trip, a truncated capture — and one claiming `measurable: True`
    while carrying no drawdown would otherwise raise a TypeError inside
    ``evaluate`` and take out the whole judgement rather than one criterion.
    """
    strat = series_with_moments(R400, 18.0, 12.0, seed=5)
    res = make_result(strat, series_with_moments(R400, 9.0, 20.0, seed=6))
    res["premia_inputs"]["benchmark"]["max_drawdown_pct"] = None
    res["premia_inputs"]["strategy"]["ann_vol_pct"] = None
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["measurable"] is False
    assert "ann_vol_pct" in out["checks"]["premia"]["reason"]
    assert "max_drawdown_pct" in out["checks"]["premia"]["reason"]
    assert out["passed"] is False
    # And the rest of the gauntlet still ran: this failed ONE criterion.
    assert out["gate_version"] == "v5r1-premia"
    assert out["checks"]["psr_pct"] == 92.0


def test_a_flat_strategy_is_unmeasurable_not_a_zero_sharpe():
    bench = series_with_moments(R400, 9.0, 20.0, seed=6)
    res = make_result([0.0] * 400, bench)
    out = judge(res, claim_type="premia")
    assert out["checks"]["premia"]["measurable"] is False
    assert any("no usable dispersion" in f or "could not be measured" in f
               for f in out["failures"])


# --- the volatility field, capture only ----------------------------------

def test_the_volatility_field_is_recorded_on_BOTH_bars():
    """The 12x lever, made visible. Capture only: no criterion reads it.

    The validator measured a 12x pass-rate swing at FIXED skill (2.6% at 8%
    volatility to 29.7% at 25%) delivered entirely through
    `must_beat_benchmark`, and no field anywhere recorded a candidate's
    volatility.
    """
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    strat = series_with_moments(R600, 15.0, 12.0, seed=32)
    res = make_result(strat, bench)
    for claim in (None, "premia"):
        vol = judge(res, claim_type=claim)["checks"]["volatility"]
        assert vol["strategy_ann_vol_pct"] == pytest.approx(12.0, abs=0.05)
        assert vol["benchmark_ann_vol_pct"] == pytest.approx(24.0, abs=0.05)


def test_the_volatility_field_is_absent_not_zero_when_uncaptured():
    strat = series_with_moments(R400, 18.0, 12.0, seed=5)
    res = make_result(strat, series_with_moments(R400, 9.0, 20.0, seed=6))
    res.pop("premia_inputs")
    vol = evaluate(res, CLEAN_HOLDOUT, CLEAN_SWEEP,
                   walkforward=CLEAN_WALK)["checks"]["volatility"]
    assert vol["strategy_ann_vol_pct"] is None
    assert vol["benchmark_ann_vol_pct"] is None
    assert "absent, not zero" in vol["note"]


def test_the_volatility_field_does_not_change_any_alpha_verdict():
    """Capture only means capture only.

    An 8%-volatility and a 25%-volatility strategy with the SAME evidence on
    every criterion must produce the same failure list — otherwise the field
    has quietly acquired a consumer.
    """
    bench = series_with_moments(R600, 20.0, 24.0, seed=31)
    lo = judge(make_result(series_with_moments(R600, 15.0, 8.0, seed=32), bench))
    hi = judge(make_result(series_with_moments(R600, 15.0, 25.0, seed=32), bench))
    assert lo["failures"] == hi["failures"]
    assert lo["passed"] == hi["passed"]
    assert (lo["checks"]["volatility"]["strategy_ann_vol_pct"]
            != hi["checks"]["volatility"]["strategy_ann_vol_pct"])
