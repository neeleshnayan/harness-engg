"""THE LUCK FILTER (gate v4.4 / premia v5r4) — the acceptance suite.

These are the conditions the change had to meet, written as tests rather than as
prose in a report:

  1. NO LEVEL WEARS ANOTHER LEVEL'S WORDS. The target-zero basis may say "not
     distinguishable from luck"; the engine basis may not, and must name the
     hurdle it actually is.
  2. THE CRITERION READS OUR OWN MODULE, and both readings are captured on every
     verdict so the 40x disagreement can never again be invisible.
  3. A PREMIA CLAIM IS SCORED ON ITS ADVANTAGE, not its absolute Sharpe.
  4. A MARGINAL ADVANTAGE IS REFUSED and a large one is admitted — the control
     round's `volscale` (+0.00756, inside the reviewer's +/-0.05 noise band) is
     the specimen for the first.
  5. THE CREDIT AND THE SUBTRACTION ARE ONE SERIES (the adversary's clearance
     condition on the cash-carry work).

The premia fixtures here deliberately carry TRACKING ERROR. A pure cash/beta
blend is an exact linear function of its bar, so its advantage has no sampling
variation at all and the filter refuses it as unmeasurable — correct, and tested
separately below, but useless for measuring what a level does.
"""
from __future__ import annotations

import math
import random

import pytest

from premia_feed import (cash_feed, daily_returns_block, series_with_psr,
                         weekdays_between)
from app.fund import statistics as st
from app.fund.gate import (CRITERIA, PREMIA_CRITERIA, PSR_BASES, evaluate)
from app.fund.leanrunner import (gross_exposure, invested_weights,
                                 premia_inputs)
from test_premia_gate import (CLEAN_HOLDOUT, CLEAN_SWEEP, CLEAN_WALK, feed,
                              exposure_chart, make_result, rdates,
                              series_with_moments, R600)

RF_PCT = 3.0


def judge(result, **pc):
    """The whole gate, with the luck filter ON — the opposite default from
    `test_premia_gate.judge`, whose subject is everything else."""
    return evaluate(result, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    claim_type="premia", premia_criteria=pc or None)


def overlay(bench: list[float], advantage: float, te_annual: float = 0.03,
            seed: int = 11) -> list[float]:
    """The bar plus a genuine edge and a realistic tracking error.

    ``advantage`` is the ANNUALISED Sharpe advantage the construction targets.
    Because the two legs then share a volatility to first order, the realised
    advantage is close to the target — the tests assert what is MEASURED, never
    the target, so an approximation here cannot manufacture a pass.
    """
    rnd = random.Random(seed)
    _mu, sd = st.mean_std(bench)
    edge = advantage * sd / math.sqrt(252.0)
    te = te_annual / math.sqrt(252.0)
    return [x + edge + rnd.gauss(0.0, te) for x in bench]


# =========================================================================
# 1. TRUTH IN LABELLING
# =========================================================================

def test_the_target_zero_basis_says_luck_and_states_what_it_demanded():
    """The sentence must carry the target, the bar and the measurement.

    The defect: "the edge is not distinguishable from luck on this much history"
    was printed while testing an implied annualised Sharpe of about 1.34. A
    reader could not tell which question had been asked.
    """
    r = _alpha(psr=20.0)
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"min_psr_pct": 65.0})
    sentence = [f for f in out["failures"] if "luck" in f]
    assert len(sentence) == 1, out["failures"]
    s = sentence[0]
    assert "the true Sharpe is above zero" in s
    assert "demands an annualised Sharpe of about" in s
    assert "this run measured" in s
    assert "not distinguishable from luck" in s
    # AND IT MUST NOT claim to be the other thing.
    assert "SKILL HURDLE" not in s


def test_the_engine_basis_REFUSES_to_say_luck_and_names_the_hurdle():
    """The falsifier's branch, and the reason it has to exist as real code.

    The chair's ruling: if no level held the invariant, the ~1.34 hurdle STAYS
    with its sentence corrected. A falsifier whose alternative configuration is
    not implemented cannot fire, so this configuration is shipped, tested, and
    labelled as what it is.
    """
    r = _alpha(psr=20.0)
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    sentence = [f for f in out["failures"] if "probabilistic Sharpe" in f]
    assert len(sentence) == 1, out["failures"]
    s = sentence[0]
    assert "THIS IS A SKILL HURDLE, NOT A LUCK TEST." in s
    assert "puts its target at an annualised Sharpe of" in s
    # THE WORDS THAT WERE FALSE HERE ARE GONE. Matching the whole clause rather
    # than the word "luck", which appears in the corrected sentence too — a
    # shared word is satisfiable by the wrong branch (D27).
    assert "is not distinguishable from luck on this much history" not in s


def test_an_unimplemented_basis_fails_closed_and_names_the_two_it_knows():
    r = _alpha(psr=90.0)
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "whatever_the_engine_said"})
    assert out["passed"] is False
    assert any("does not implement" in f and "engine_reported" in f
               and "target_zero_module" in f for f in out["failures"])
    assert set(PSR_BASES) == {"target_zero_module", "engine_reported"}


# =========================================================================
# 2. BOTH READINGS, ON EVERY VERDICT
# =========================================================================

def test_both_readings_are_captured_whichever_one_judged():
    """The 40x disagreement was invisible because nothing stored both numbers.

    The engine's figure keeps its own key AND appears inside the leg; the
    target-zero reading is computed and reported even when the engine basis is
    the one being applied.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 12.5
    for basis in PSR_BASES:
        out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                       criteria={"psr_basis": basis, "min_psr_pct": 65.0})
        luck = out["checks"]["luck"]
        assert out["checks"]["psr_pct"] == 12.5
        assert luck["engine_psr_pct"] == 12.5
        assert luck["luck_psr_pct"] == pytest.approx(90.0, abs=0.05)
        assert luck["basis"] == basis
        expect = 12.5 if basis == "engine_reported" else luck["luck_psr_pct"]
        assert luck["evaluated_pct"] == expect


def test_the_criterion_reads_the_SERIES_not_the_number_in_robustness():
    """MOVE IT, do not match it (D16). A payload whose stored `psr_pct` says one
    thing and whose observations say another is judged on the observations."""
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 2.0          # what the engine claimed
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    assert out["passed"] is True, out["failures"]

    r2 = _alpha(psr=20.0)
    r2["robustness"]["psr_pct"] = 99.0        # the engine loved it
    out2 = evaluate(r2, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    criteria={"min_psr_pct": 65.0})
    assert out2["passed"] is False
    assert any("not distinguishable from luck" in f for f in out2["failures"])


def test_an_absent_series_fails_closed_rather_than_passing():
    r = _alpha(psr=90.0)
    r.pop("daily_returns")
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    assert out["passed"] is False
    assert any("nothing to attach a probability to" in f
               for f in out["failures"])


# =========================================================================
# 3 & 4. THE PREMIA ADVANTAGE, AND WHAT EACH LEVEL DOES TO IT
# =========================================================================

def _premia(advantage: float, seed: int = 11, **kw):
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    return make_result(overlay(bench, advantage, seed=seed), bench,
                       rf_pct=RF_PCT, **kw)


def test_a_MARGINAL_advantage_is_refused_by_the_luck_filter():
    """THE CONTROL ROUND'S SPECIMEN. `volscale` measured a +0.00756 Sharpe
    advantage — inside the reviewer's +/-0.05 noise band — and the inequality
    alone passed it, because the inequality is a strict `> 0` with no margin.
    The luck filter is what refuses a number that size.
    """
    out = judge(_premia(-0.03))
    p = out["checks"]["premia"]
    assert p["measurable"] is True
    assert 0.0 < p["sharpe_advantage"] < 0.05, p["sharpe_advantage"]
    # The INEQUALITY is satisfied — this is not a test of the inequality.
    assert not [f for f in out["failures"] if "no premium over owning" in f]
    # The LUCK FILTER refuses it, and says what it demanded.
    luck = [f for f in out["failures"] if "risk-adjusted ADVANTAGE" in f]
    assert len(luck) == 1, out["failures"]
    assert "demands an annualised advantage of about" in luck[0]
    assert out["passed"] is False


def test_a_LARGE_advantage_clears_the_luck_filter():
    """The other half, and the half that keeps this from being rigour theatre:
    a genuine premium must survive. A criterion nothing can clear is not a bar,
    it is an outage."""
    out = judge(_premia(0.60))
    p = out["checks"]["premia"]
    assert p["sharpe_advantage"] > 0.3, p["sharpe_advantage"]
    assert out["checks"]["luck"]["evaluated_pct"] >= 65.0
    assert out["passed"] is True, out["failures"]


def test_the_premia_filter_scores_the_ADVANTAGE_not_the_absolute_sharpe():
    """The category error the split exists to end.

    A book with a LARGE absolute Sharpe and NO advantage over its bar must be
    refused; the alpha statistic would have waved it through. Both legs here are
    the same strong series, so the absolute Sharpe is high and the advantage is
    nil.
    """
    bench = series_with_moments(R600, 30.0, 12.0, seed=77)
    res = make_result(overlay(bench, 0.0, seed=5), bench, rf_pct=RF_PCT)
    p = res["premia_inputs"]
    strong = st.sharpe_at_rf(p["strategy_excess"], 0.0)
    assert strong > 1.0, strong                      # a large ABSOLUTE Sharpe
    out = judge(res)
    assert out["checks"]["luck"]["claim_scope"] == "premia advantage"
    assert out["passed"] is False
    assert any("risk-adjusted ADVANTAGE" in f or "no premium over owning" in f
               for f in out["failures"]), out["failures"]


def test_a_pure_cash_beta_blend_has_NO_measurable_advantage_and_is_refused():
    """The impersonator's shape, and the strongest thing the filter says.

    `w * bar + (1 - w) * cash` is an exact linear function of the bar, so the
    difference series is CONSTANT: the advantage has no sampling variation and
    no probability attaches to it. This is not a small probability — it is the
    absence of one, and the two must not share a sentence.
    """
    from test_premia_gate import cash_mix
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    out = judge(make_result(cash_mix(bench, 0.30, 3.5), bench, rf_pct=1.0))
    assert out["passed"] is False
    assert any("no dispersion and no probability attaches to it" in f
               for f in out["failures"]), out["failures"]


def test_the_level_is_SPLIT_from_the_alpha_one_and_moving_it_moves_the_verdict():
    """Two statistics, two levels — and the premia level is the one that bites.

    MOVED, not matched: the same candidate is judged under two levels and the
    verdict follows the premia level while the alpha level is held still.
    """
    res = _premia(-0.03)
    assert judge(res, premia_min_luck_pct=50.0)["passed"] is True
    assert judge(res, premia_min_luck_pct=95.0)["passed"] is False
    # and the ALPHA level does not reach it
    hard = evaluate(res, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    claim_type="premia", criteria={"min_psr_pct": 99.0},
                    premia_criteria={"premia_min_luck_pct": 50.0})
    assert hard["passed"] is True, hard["failures"]


def test_the_two_shipped_levels_are_pinned_from_both_sides():
    """Hardcoded, per D21: a test that reads the constant it guards pins
    nothing. The values and their written basis are in the version notes."""
    assert CRITERIA["min_psr_pct"] == 50.0
    assert CRITERIA["psr_basis"] == "target_zero_module"
    assert PREMIA_CRITERIA["premia_min_luck_pct"] == 65.0
    assert PREMIA_CRITERIA["premia_require_luck_filter"] is True
    assert PREMIA_CRITERIA["premia_credit_idle_cash"] is False


def test_a_declined_luck_filter_is_RECORDED_never_silently_skipped():
    """A criterion listed in a stored verdict and quietly not run reads exactly
    like one that was passed — the write-only-column shape."""
    res = _premia(-0.03)
    off = judge(res, premia_require_luck_filter=False)
    assert off["checks"]["luck"]["applied"] is False
    assert "declines to apply" in off["checks"]["luck"]["reason"]
    assert off["passed"] is True, off["failures"]
    assert judge(res)["passed"] is False


# =========================================================================
# 5. THE CASH CREDIT: THE PIN, AND THE DEFAULT
# =========================================================================

def test_the_credit_and_the_subtraction_are_ONE_series():
    """THE ADVERSARY'S CLEARANCE CONDITION (trace 9fb82050), made structural.

    A credit applied at a DIFFERENT rate from the subtraction is the D23
    constant-rf kill re-entering from inside the engine: a flat 4.0% credited
    against a realised subtraction buys a w=0.2 book roughly +0.167 of Sharpe
    out of nothing.

    The property is proved by MOVING the rate. Both legs are built from one
    `rfmap` inside `premia_inputs`, so changing the feed must move the credited
    strategy leg and the benchmark leg TOGETHER; if a second rate series ever
    appears, one of them stops tracking and this dies.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    strat = overlay(bench, 0.20, seed=9)
    seen = {}
    for rate in (1.0, 5.0):
        res = make_result(strat, bench, rf_pct=rate, gross=0.5)
        p = res["premia_inputs"]
        assert p["cash_credit"]["measurable"] is True
        seen[rate] = (p["benchmark_excess"]["mean"],
                      p["strategy_excess_credited"]["mean"],
                      p["strategy_excess_uncredited"]["mean"])
    b1, c1, u1 = seen[1.0]
    b5, c5, u5 = seen[5.0]
    # The bar's leg moves by the FULL change in the rate...
    d_bench = b1 - b5
    # ...the uncredited strategy leg by the same full amount (it is charged the
    # whole rate too)...
    assert (u1 - u5) == pytest.approx(d_bench, rel=1e-9)
    # ...and the CREDITED leg by exactly the invested share of it. w = 0.5 here,
    # so the credited leg must move by HALF. A credit on any other series would
    # not land on this number.
    assert (c1 - c5) == pytest.approx(d_bench * 0.5, rel=1e-6)


def test_the_credit_is_OFF_by_default_and_the_capture_ships_anyway():
    """It ADMITS candidates, so it does not arrive as a default. What ships
    unconditionally is the ability to SEE it."""
    res = _premia(0.20, gross=0.4)
    p = res["premia_inputs"]
    assert p["schema"] == 4
    assert p["cash_credit"]["measurable"] is True
    assert p["cash_credit"]["mean_cash_weight"] == pytest.approx(0.6, abs=1e-6)
    assert p["advantage"]["basis"] == "uncredited"
    assert p["advantage_credited"]["measurable"] is True

    out = judge(res)
    leg = out["checks"]["premia"]
    assert leg["idle_cash_credited"] is False
    # The other arm is REPORTED on every verdict, which is what makes the
    # decision not to apply it auditable rather than merely stated.
    assert leg["other_arm"] == "credited"
    assert leg["sharpe_advantage_other_arm"] > leg["sharpe_advantage"]


def test_switching_the_credit_ON_moves_the_verdict_and_names_the_arm():
    """MOVED, not matched. The flag must be the thing that decides, and the
    stored verdict must say which arm judged."""
    res = _premia(0.05, gross=0.3, seed=13)
    off = judge(res, premia_min_luck_pct=65.0)
    on = judge(res, premia_min_luck_pct=65.0, premia_credit_idle_cash=True)
    assert off["checks"]["premia"]["idle_cash_credited"] is False
    assert on["checks"]["premia"]["idle_cash_credited"] is True
    assert (on["checks"]["premia"]["sharpe_advantage"]
            > off["checks"]["premia"]["sharpe_advantage"])
    assert on["checks"]["luck"]["advantage_basis"] == "advantage_credited"
    assert off["checks"]["luck"]["advantage_basis"] == "advantage"


def test_crediting_without_a_readable_weight_REFUSES_rather_than_assuming_one():
    """Absence is never zero, and here "fully invested" is the flattering
    assumption: it credits nothing and keeps the bias."""
    res = _premia(0.20, gross=None)
    out = judge(res, premia_credit_idle_cash=True)
    assert out["passed"] is False
    assert out["checks"]["premia"]["measurable"] is False
    assert any("cash weight is unknown" in f or "GROSS EXPOSURE is unknown" in f
               for f in out["failures"]), out["failures"]


def test_a_short_book_refuses_the_weight_rather_than_guessing_its_cash():
    """Cash held against a short book is not one minus its gross, and modelling
    short proceeds is a different correction than this one."""
    chart = exposure_chart(rdates(len(R600)), 0.6, 0.3)
    got = invested_weights(chart)
    assert got["measurable"] is False
    assert "SHORT exposure" in got["reason"]
    # and the maxima reader is untouched by that refusal
    assert gross_exposure(chart)["max_gross"] == pytest.approx(0.9, abs=1e-9)


# =========================================================================
# helpers
# =========================================================================

def _alpha(psr: float, **over):
    r = {
        "total_return_pct": 20.0,
        "benchmark_return_pct": 10.0,
        "capacity": {"capacity_usd": 5_000_000.0},
        "daily_returns": daily_returns_block(series_with_psr(psr)),
        "robustness": {"total_orders": 40, "psr_pct": psr,
                       "costs": {"slippage_modelled": True}},
    }
    r.update(over)
    return r


# =========================================================================
# 6. THE MUTATION SURVIVORS, closed
#
# Five mutants survived the first pass. Each was re-derived by hand before
# being written down (a survivor is a gap or a retirement, never a note), and
# all five were REAL gaps rather than equivalent mutants.
# =========================================================================

def test_a_reading_EXACTLY_ON_the_level_passes():
    """`>= level` versus `> level`, probed AT the boundary.

    Mutant M05 changed one to the other and every test stayed green, because no
    fixture landed exactly on a level. The boundary is reachable — `psr_pct` is
    rounded to three decimals, so equality is an ordinary outcome, not a
    measure-zero curiosity. Exactness is arranged by moving the LEVEL onto the
    measured reading rather than by trying to hit a level with a series.
    """
    r = _alpha(psr=71.0)
    exact = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                     criteria={"min_psr_pct": 0.0})["checks"]["luck"]
    on_the_nose = exact["luck_psr_pct"]
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"min_psr_pct": on_the_nose})
    assert out["passed"] is True, out["failures"]
    # and one tick above it must fail, so the test pins a boundary and not a
    # direction that happens to hold everywhere.
    over = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    criteria={"min_psr_pct": on_the_nose + 0.001})
    assert over["passed"] is False


def test_the_demanded_advantage_is_on_the_SAME_SCALE_as_the_measured_one():
    """Mutant M10: the premia sentence quoted the difference series' Sharpe and
    called it an advantage — inflating the demand by a factor of 1/sd(d), about
    4x on these fixtures. Nothing caught it, because no test compared the two
    numbers the sentence puts side by side.

    The invariant is behavioural and needs no formula: a premia candidate clears
    the luck filter IF AND ONLY IF its measured advantage is at least the
    advantage the level demands. On the wrong scale those two disagree.
    """
    for target in (-0.05, -0.03, 0.0, 0.05, 0.20):
        res = _premia(target)
        out = judge(res)
        luck = out["checks"]["luck"]
        measured = out["checks"]["premia"]["sharpe_advantage"]
        demanded = luck["required_sharpe_annualised"]
        assert demanded is not None
        cleared = not [f for f in out["failures"] if "risk-adjusted ADVANTAGE" in f]
        assert cleared is (measured >= demanded - 1e-6), (
            target, measured, demanded, cleared)


def test_a_weight_series_that_MISSES_days_refuses_rather_than_filling_them():
    """Mutant M15: dropping the coverage check left the gap silently filled.

    A day with no invested weight would have to be assumed either fully invested
    (credit nothing, keep the bias) or fully in cash (credit the maximum). Both
    are inventions, so the credit is unmeasurable and the criterion refuses.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    res = make_result(overlay(bench, 0.20), bench, rf_pct=RF_PCT, gross=0.5)
    weights = dict(res["invested_weight"]["weights"])
    for day in sorted(weights)[10:15]:
        weights.pop(day)
    res["invested_weight"] = {**res["invested_weight"], "weights": weights}
    res["premia_inputs"] = premia_inputs(
        res, rf_bars=feed(RF_PCT, dates=rdates(len(R600))), rf_symbol="BIL")
    p = res["premia_inputs"]
    assert p["cash_credit"]["measurable"] is False
    assert "carries no invested weight for" in p["cash_credit"]["reason"]
    assert p["credited_measurable"] is False
    # the UNCREDITED pair survives the outage — the shipped bar still works
    assert p["excess_measurable"] is True
    assert judge(res)["checks"]["premia"]["measurable"] is True
    # and asking for the credit now refuses
    out = judge(res, premia_credit_idle_cash=True)
    assert out["passed"] is False
    assert out["checks"]["premia"]["measurable"] is False


def test_the_credit_guard_is_REACHABLE_and_not_masked_by_the_gross_ceiling():
    """Mutant M17 survived because the only test of a missing weight also had a
    missing EXPOSURE, so the gross ceiling refused first and the credit's own
    guard was never reached. A guard behind an earlier refusal is untested.

    This fixture has a perfectly readable gross AND no weight series.
    """
    bench = series_with_moments(R600, 12.0, 20.0, seed=21)
    res = make_result(overlay(bench, 0.20), bench, rf_pct=RF_PCT, gross=0.9)
    assert res["premia_inputs"]["gross_measurable"] is True
    res.pop("invested_weight")
    res["premia_inputs"] = premia_inputs(
        res, rf_bars=feed(RF_PCT, dates=rdates(len(R600))), rf_symbol="BIL")
    assert res["premia_inputs"]["gross_measurable"] is True   # 1b will PASS
    out = judge(res, premia_credit_idle_cash=True)
    assert out["passed"] is False
    leg = out["checks"]["premia"]
    assert leg["measurable"] is False
    # the reason must name the CASH WEIGHT, not the leverage — a diagnosis that
    # names the wrong cause sends the next reader to the wrong place.
    assert "invested-weight series" in (leg["reason"] or ""), leg["reason"]
    assert any("cash weight is unknown" in f for f in out["failures"])


def test_two_samples_on_one_day_keep_the_LARGER_invested_reading():
    """Mutant M18: `max` to `min` survived, because no chart in the fixtures
    samples a date twice. It is unreachable on today's engine output and it is
    NOT equivalent — so it is pinned rather than retired, and pinned in the
    conservative direction: the larger invested weight is the SMALLER cash
    credit, which is the one that cannot manufacture an advantage.
    """
    day = "2021-01-04"
    ts = 1609718400.0
    chart = {"Exposure": {"series": {
        "Base - Long Ratio": {"values": [[ts, 0.20], [ts + 3600, 0.80]]},
        "Base - Short Ratio": {"values": [[ts, 0.0], [ts + 3600, 0.0]]}}}}
    got = invested_weights(chart)
    assert got["measurable"] is True
    assert got["n"] == 1
    assert got["weights"][day] == pytest.approx(0.80, abs=1e-9)


# =========================================================================
# 7. A GATE MUST RETURN A VERDICT, NEVER RAISE
#
# Found by the Gauntlet on the finished diff, and it is a REPEAT of the defect
# v5r1 shipped: `_premia_leg` crashed on a stored payload that claimed to be
# measurable and carried no numbers. The new luck leg reads a stored block the
# same way and had the same hole. Two crash paths in one file, one round apart.
# =========================================================================

@pytest.mark.parametrize("label,advantage", [
    ("no numbers at all", {"measurable": True}),
    ("n is a string", {"measurable": True, "n": "ten", "sharpe_per_obs": 0.1,
                       "skew": 0.0, "kurtosis": 3.0, "stdev": 0.1}),
    ("every value None", {"measurable": True, "n": None, "sharpe_per_obs": None,
                          "skew": None, "kurtosis": None, "stdev": None}),
    ("stdev missing", {"measurable": True, "n": 100, "sharpe_per_obs": 0.1,
                       "skew": 0.0, "kurtosis": 3.0}),
    ("n is a bool", {"measurable": True, "n": True, "sharpe_per_obs": 0.1,
                     "skew": 0.0, "kurtosis": 3.0, "stdev": 0.1}),
])
def test_a_malformed_stored_advantage_is_a_VERDICT_not_a_crash(label, advantage):
    """Each of these raised before the fix — KeyError, ValueError, TypeError.

    A stored payload may have been written by an older belt, round-tripped
    through JSON or truncated, and a crash inside `evaluate` takes out the WHOLE
    judgement rather than failing one criterion.
    """
    out = evaluate({"premia_inputs": {"advantage": advantage}},
                   CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   claim_type="premia")
    assert out["passed"] is False
    assert out["checks"]["luck"]["measurable"] is False
    assert "carries no usable" in out["checks"]["luck"]["reason"], label


@pytest.mark.parametrize("series", [[], [0.0] * 100, [0.01], None])
def test_a_degenerate_alpha_series_is_a_VERDICT_not_a_crash(series):
    r = _alpha(psr=90.0)
    r["daily_returns"] = {"present": True, "strategy": series,
                          "dates": ["2021-01-04"] * (len(series or []))}
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    assert out["passed"] is False


def test_a_bar_with_no_readable_level_refuses_rather_than_raising():
    """`evaluate` merges defaults so this cannot arrive by the ordinary path,
    but a caller handing in a criteria dict directly must not crash the gate."""
    out = evaluate(_alpha(psr=90.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                   walkforward=CLEAN_WALK, criteria={"min_psr_pct": None})
    assert out["passed"] is False
    assert any("no readable level" in f for f in out["failures"])


def test_a_DECLINED_filter_does_not_refuse_over_a_level_it_never_reads():
    """The ordering the read-through caught.

    A bar that declines to apply the luck filter has no business refusing a
    candidate because that filter's level is unreadable. The first draft
    validated the level BEFORE the off-switch and would have done exactly that.
    """
    res = _premia(-0.03)
    out = judge(res, premia_require_luck_filter=False,
                premia_min_luck_pct=None)
    assert out["checks"]["luck"]["applied"] is False
    assert out["passed"] is True, out["failures"]
