"""The D37 revert: what the engine hurdle IS, what it DEMANDS, and the split.

THE INCIDENT (adversary, run-adversary-d36-prodgate2). The v4.4 draft moved the
alpha luck leg onto a target-zero statistic at a level of 50.0. The blind
certified everything else in that diff and killed the constant: the level was
chosen by "the lowest that holds the invariant" over a sweep in which the
invariant holds at EVERY level from 50 to 99.9, and a flat curve cannot
calibrate anything — the rule hands you the most permissive value and calls the
result a measurement. The chair's ruling had already written the falsifier path
this file guards: *if no level holds, keep the hurdle and correct its words.*

So three things must be true at once, and each has a test here that fails if it
stops being:

  1. THE ALPHA PAIR IS THE ENGINE'S, AT 65.0 — the values every candidate this
     fund has ever judged was judged against.
  2. THE PREMIA PAIR IS UNTOUCHED — `target_zero_module` on the ADVANTAGE at
     65.0, certified in the same review. It survives the alpha revert only
     because the bases are SPLIT; before the split, reverting one re-pointed
     the other, which is the defect `test_reverting_the_alpha_basis_does_NOT_*`
     exists to catch.
  3. THE SENTENCE TELLS THE TRUTH ABOUT A SKILL HURDLE — the engine's own
     constant target, and the Sharpe the level demands AGAINST THAT TARGET,
     both stated ON THE SERIES' OWN MEASURED CLOCK. Never zero, never
     absent-as-zero, and never two clocks in one payload (D41).
"""
from __future__ import annotations

import math
import random
from datetime import date, timedelta

import pytest

from app.fund import statistics as st
from app.fund.gate import (CRITERIA, PREMIA_CRITERIA, PSR_BASES, _luck_leg,
                           evaluate)
from premia_feed import daily_returns_block
from test_luck_filter import _alpha, _premia, judge
from test_premia_gate import CLEAN_HOLDOUT, CLEAN_SWEEP, CLEAN_WALK


def _alpha_verdict(**criteria):
    return evaluate(_alpha(psr=20.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                    walkforward=CLEAN_WALK, criteria=criteria or None)


# =========================================================================
# 1. THE SPLIT — the defect the revert would have caused without it
# =========================================================================

def test_reverting_the_alpha_basis_does_NOT_repoint_the_premia_leg():
    """THE MEASURED ITEM INTERACTION, and the reason `premia_psr_basis` exists.

    Until D37 one `psr_basis` served both claim types. Reverting the ALPHA bar
    to `engine_reported` therefore also pointed the PREMIA leg at LEAN's
    published figure — the strategy's ABSOLUTE Sharpe — judged against a level
    calibrated on the ADVANTAGE. That is precisely the category error the whole
    premia luck leg was built to end, re-entering through a revert nobody would
    have read as touching it. Eighteen tests went red on the unsplit revert.

    This asserts the property directly: with the alpha basis at
    `engine_reported`, a premia claim is STILL scored on the advantage, and the
    engine's own figure — set here to a number that would sail through — does
    not decide it.
    """
    res = _premia(-0.03)
    # The engine adored this run. It is irrelevant to a premia claim.
    res["robustness"]["psr_pct"] = 99.9
    out = evaluate(res, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   claim_type="premia",
                   criteria={"psr_basis": "engine_reported"})
    luck = out["checks"]["luck"]
    assert luck["basis"] == "target_zero_module"
    assert luck["claim_scope"] == "premia advantage"
    assert luck["evaluated_pct"] != 99.9
    assert luck["evaluated_pct"] == luck["luck_psr_pct"]
    assert out["passed"] is False
    assert any("risk-adjusted ADVANTAGE" in f for f in out["failures"]), \
        out["failures"]


def test_the_premia_basis_is_read_from_the_premia_dict_and_MOVES_the_verdict():
    """MOVE IT, do not match it (D16). An assertion that the premia basis EQUALS
    `target_zero_module` cannot distinguish a criterion that reads the key from
    one that hardcodes the same string. So the key is moved and the verdict has
    to follow it.
    """
    res = _premia(-0.03)
    res["robustness"]["psr_pct"] = 99.9
    on_advantage = judge(res)
    on_engine = judge(res, premia_psr_basis="engine_reported")
    assert on_advantage["checks"]["luck"]["evaluated_pct"] != 99.9
    assert on_engine["checks"]["luck"]["evaluated_pct"] == 99.9
    # AND THE LABEL FOLLOWS THE STATISTIC, not the claim type. The engine knows
    # nothing about this fund's benchmark, so a premia claim judged on that
    # basis was not scored on its advantage and must not say it was.
    assert on_engine["checks"]["luck"]["claim_scope"] == "strategy sharpe"
    assert on_advantage["passed"] is False
    assert on_engine["passed"] is True, on_engine["failures"]


def test_an_unimplemented_premia_basis_fails_closed_like_the_alpha_one():
    """A typo in a bar's own definition must not select a statistic by accident,
    in either dict. The alpha side had this guard; the new key needs its own."""
    out = judge(_premia(0.20), premia_psr_basis="whatever_the_engine_said")
    assert out["passed"] is False
    assert any("does not implement" in f for f in out["failures"]), \
        out["failures"]
    assert set(PSR_BASES) == {"target_zero_module", "engine_reported"}


# =========================================================================
# 2. WHAT THE HURDLE DEMANDS — solved against the target, never against zero
# =========================================================================

def test_the_engine_sentence_states_the_demand_AGAINST_THE_CONSTANT_TARGET():
    """THE DEFECT THIS CLOSES, in two rounds.

    ROUND ONE (v4.4). `required_sharpe_annualised` was solved at target 0.0 for
    BOTH bases and then simply not quoted in the engine sentence. That left a
    precise, confident, wrong number on every stored verdict — the demand of a
    target-zero criterion, on a verdict produced by a criterion that does not
    test one.

    ROUND TWO (D38, adversary run-adversary-d37). The fix used a target
    INVERTED out of each run's own series, on the stated ground that the engine
    publishes none. LEAN hardcodes it: `1.0 / Math.Sqrt(tradingDaysPerYear)`,
    PortfolioStatistics.cs:311, 0.062994 per observation on EXCESS returns. So
    the demand is solved against THAT — and D38 then annualised it on the
    ENGINE's 252 clock.

    ROUND THREE (D41, adversary run-adversary-d38). Annualising on 252 states
    the target in the engine's CONVENTION, not in the units of the series being
    judged. LEAN applies the per-observation target to the series it was handed,
    and this fund's series carry 365.25 observations a year, so the bar the
    candidate actually faced is 0.062994*sqrt(365.25) = 1.2039 and what 65%
    demands of it is 1.34 — while the verdict payload said 1.00 and 1.11 beside
    a `sharpe_annualised` on the 365.25 clock. Three annualised fields, two
    clocks, and the demand understated by 21% in the permissive direction.

    FOUR-WAY DISCRIMINATION, because three of the four candidate answers are the
    fund's own former ones and a test that only pins the right value cannot say
    it moved. The demand must equal the bar against 1/sqrt(252) annualised on
    THIS SERIES' clock, and must differ from the target-zero bar, from the
    inverted-target bar, and from D38's same-bar-at-sqrt(252).

    THE FIXTURE HAS TO CARRY THE DISAGREEMENT, and the first draft of the round
    one test did not — `_alpha(psr=20.0)` writes 20.0 into `robustness` AND
    builds a series whose target-zero PSR is 20.0, so the inverted target came
    out at zero and both bars agreed to four decimals. So the series reads 90%
    at target zero while the engine published 20%, which is the shape the four
    positive controls actually had (2.128% published against 85.0% measured).
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 20.0
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    series = r["daily_returns"]["strategy"]
    k = st.observations_per_year(
        [str(d)[:10] for d in r["daily_returns"]["dates"]], len(series))
    assert k["usable"], k
    kk = float(k["obs_per_year"])
    assert kk != 252.0, "the fixture cannot tell the two clocks apart"

    hurdle = st.lean_psr_target()
    want = st.sharpe_bar_for_psr(65.0, series, hurdle["per_obs"])
    assert want["measurable"], want
    against_zero = st.sharpe_bar_for_psr(65.0, series, 0.0)
    assert against_zero["measurable"], against_zero
    inverted = st.implied_target_sharpe(20.0, series)
    assert inverted["measurable"], inverted
    old = st.sharpe_bar_for_psr(65.0, series, inverted["target_per_obs"])
    assert old["measurable"], old

    # THE RIGHT ANSWER: the engine's constant target, annualised on the clock
    # the series is actually observed at — the same clock every other annualised
    # figure in the payload uses.
    expected = round(float(want["sharpe_per_obs"]) * math.sqrt(kk), 4)
    # D38's answer: the same bar, restated in the engine's 252-day convention.
    wrong_engine_clock = round(float(want["sharpe_per_obs"]) * math.sqrt(252.0), 4)
    # v4.4 round one: solved against a target of ZERO.
    wrong_target = round(float(against_zero["sharpe_per_obs"]) * math.sqrt(kk), 4)
    # v4.4 round two: solved against a target INVERTED out of this run.
    wrong_inverted_target = round(float(old["sharpe_per_obs"]) * math.sqrt(kk), 4)
    assert len({expected, wrong_engine_clock, wrong_target,
                wrong_inverted_target}) == 4, (
        "the fixture cannot tell the four answers apart")
    assert luck["required_sharpe_annualised"] == expected
    # ONE CLOCK PER PAYLOAD, asserted as an identity between two fields rather
    # than against a literal — a hardcoded 365.25 in the leg would satisfy a
    # literal and this cannot be satisfied without reading the series' dates.
    assert luck["required_sharpe_clock"] == luck["obs_per_year"] == round(kk, 2)
    assert luck["required_sharpe_clock"] != 252.0
    # THE PER-OBSERVATION CONSTANT is the target that needs no clock, and it is
    # what a change to LEAN's numerator or default would move. Asserted here
    # instead of the annualised identity `1/sqrt(K) * sqrt(K) == 1.00`, which
    # holds for every K and therefore pins nothing.
    assert luck["target_sharpe"] == round(hurdle["per_obs"], 8)
    assert luck["target_sharpe"] == round(1.0 / math.sqrt(252.0), 8)
    # AND THE HURDLE ON THIS RUN'S CLOCK IS NOT THE CONVENTION. Both are on the
    # verdict; the one named for the run must not read as the one named for the
    # engine, which is exactly what shipped.
    assert luck["engine_target_annualised"] == round(
        float(hurdle["per_obs"]) * math.sqrt(kk), 4)
    assert luck["engine_target_annualised"] > 1.0
    assert luck["engine_convention_annualised"] == 1.0
    assert (luck["engine_target_annualised"]
            != luck["engine_convention_annualised"])

    sentence = [f for f in out["failures"] if "probabilistic Sharpe" in f]
    assert len(sentence) == 1, out["failures"]
    s = sentence[0]
    assert "THIS IS A SKILL HURDLE, NOT A LUCK TEST." in s
    assert "HARDCODED target of 1/sqrt(252) = 0.062994 per observation" in s
    # THE CONVENTION IS DISCLOSED AND LABELLED AS ONE — it is the conversion a
    # reader needs to reconcile this with LEAN's own docs, and it is exactly the
    # number D38 presented as the hurdle.
    assert "convention states that same target as an annualised Sharpe of exactly 1.00" in s
    assert "that is a CONVERSION, not the bar this run faced" in s
    # AND THE HURDLE IS STATED ON THE SERIES' OWN CLOCK, with the clock named.
    assert f"measured at {round(kk, 2)} observations a year" in s
    assert (f"the target is an annualised excess Sharpe of "
            f"{luck['engine_target_annualised']:.2f}") in s
    assert (f"P(this strategy's true excess Sharpe > "
            f"{luck['engine_target_annualised']:.2f}) >= 65.0%") in s
    assert "on EXCESS returns, subtracting a daily risk-free rate" in s
    assert ("Clearing 65.0% against that target demands an annualised excess "
            "Sharpe") in s
    assert f"{expected:+.2f}" in s
    # THE DEFECT'S OWN SENTENCE, asserted gone: D38 wrote the demand as a
    # statement about a hurdle of 1.00, which is the conversion and not the bar.
    assert "true excess Sharpe > 1.00)" not in s
    assert f"{wrong_engine_clock:+.2f}" not in s
    # and the words that are FALSE of this statistic stay gone — the luck
    # wording from before v4.4 AND the per-candidate wording from v4.4 itself.
    assert "is not distinguishable from luck on this much history" not in s
    assert "puts its target at an annualised Sharpe of" not in s
    assert "could not be recovered" not in s
    # MUTATION M22. The sibling clause that fires when the series cannot support
    # a demand must NOT fire here — a sentence stating a demand and then saying
    # the demand is unstated is worse than either alone, and nothing but this
    # assertion notices.
    assert "no usable return series" not in s
    # PUNCTUATION, because the read-through caught what the assertions could
    # not: a clause once borrowed the other branch's leading semicolon,
    # splicing a `.;` into the middle of the line.
    assert ".;" not in s
    assert "  " not in s


def test_a_run_with_NO_SERIES_still_states_the_target_and_only_drops_the_demand():
    """WHAT D38 ACTUALLY BOUGHT, and the row count behind it.

    Under v4.4 a run with no usable series had NO STATED TARGET: the sentence
    said the engine's target "could not be recovered" and that what the level
    demands "is UNSTATED rather than zero". That was honest about the fund's
    inversion and wrong about the engine — 368 stored verdicts carried it. The
    PER-OBSERVATION target never depended on the run, so it is stated here too.

    WHAT D41 TAKES BACK, and it takes back exactly one thing: the ANNUALISED
    restatement. Annualising needs a clock, the honest clock is the series' own
    measured observation rate, and a run with no series has none. D38 filled that
    hole with the engine's 252-day convention and printed 1.00 — a number
    belonging to a series this run does not have. Absent is the honest reading,
    and the constant that survives absence is the per-observation one.

    The DEMAND still does depend on the run's shape, and stays absent. That is
    the half that must not quietly acquire a fallback: a bar solved against
    nothing would be a confident number about a series that does not exist.
    """
    r = _alpha(psr=20.0)
    r.pop("daily_returns")
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    assert luck["measurable"] is True            # the engine number is readable
    assert luck["evaluated_pct"] == 20.0
    # THE CONSTANT THAT SURVIVES ABSENCE — per observation, no clock needed.
    assert luck["target_sharpe"] == round(st.lean_psr_target()["per_obs"], 8)
    # AND THE THREE FIGURES THAT NEED A CLOCK ARE ALL ABSENT TOGETHER. A payload
    # that annualised any one of them here would be quoting a clock it does not
    # have; they must go absent as a set or the set is not a set.
    assert luck["engine_target_annualised"] is None
    assert luck.get("required_sharpe_annualised") is None
    assert luck.get("required_sharpe_clock") is None
    assert luck.get("obs_per_year") is None
    assert luck.get("sharpe_annualised") is None
    # the ENGINE'S CONVENTION is not a fact about this run, so it is still
    # stated — it is what makes the per-observation figure checkable at all.
    assert luck["engine_convention_annualised"] == 1.0
    # the retired fields are GONE, not renamed and left behind
    assert "engine_implied_target_annualised" not in luck
    assert "engine_implied_target_note" not in luck
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "1/sqrt(252) = 0.062994 per observation" in s
    assert "convention states that same target as an annualised Sharpe of exactly 1.00" in s
    assert ("carries no measured observation rate, so that target cannot be "
            "restated on its own clock") in s
    assert "no usable return series, so what the level demands OF IT is unstated" in s
    assert "demands an annualised excess Sharpe" not in s
    assert "UNSTATED rather than zero" not in s
    assert "could not be recovered" not in s
    # THE D38 SENTENCE, asserted gone: a run with no series was told the bar it
    # faced was 1.00 annualised. It faced no stated annualised bar at all.
    assert "P(this strategy's true excess Sharpe > 1.00)" not in s


def test_an_engine_PSR_of_exactly_zero_NO_LONGER_suppresses_the_demand():
    """The v4.4 behaviour this fix deliberately reverses, kept as a test so the
    reversal is visible rather than incidental.

    A published PSR of exactly 0.0% pins the INVERSION at infinity, so under
    v4.4 both the target and the demand went absent on such a run. Neither
    depends on inverting anything: the target is a constant and the bar is a
    function of the level and the series' n, skew and kurtosis — the reported
    PSR is not an input to either. So a run the old code could say nothing
    about now gets the full disclosure.

    NOT HYPOTHETICAL: three of the fund's 339 stored results carrying a series
    publish exactly 0.0% (scratchpad/d37probe/target_census.py).
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 0.0
    series = r["daily_returns"]["strategy"]
    assert len(series) > 100                              # the series is fine
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    assert luck["measurable"] is True          # the engine's figure is readable
    assert luck["evaluated_pct"] == 0.0
    kk = float(st.observations_per_year(
        [str(d)[:10] for d in r["daily_returns"]["dates"]],
        len(series))["obs_per_year"])
    assert luck["engine_target_annualised"] == round(
        float(st.lean_psr_target()["per_obs"]) * math.sqrt(kk), 4)
    want = st.sharpe_bar_for_psr(65.0, series, st.lean_psr_target()["per_obs"])
    assert want["measurable"], want
    assert luck["required_sharpe_annualised"] == round(
        float(want["sharpe_per_obs"]) * math.sqrt(kk), 4)
    # AND THE OLD REFUSAL IS PROVABLY THE THING THAT MOVED: inverting still
    # cannot be done on this run, so a demand that reappeared by accident would
    # have had to come from somewhere else.
    assert st.implied_target_sharpe(0.0, series)["measurable"] is False
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "demands an annualised excess Sharpe" in s
    assert "UNSTATED rather than zero" not in s


def test_the_engine_target_clock_is_READ_from_the_run_not_hardcoded_twice():
    """MOVE IT, do not match it (D16).

    An assertion that the sentence says `1/sqrt(252)` cannot distinguish a leg
    that READS the run's stored `tradingDaysPerYear` from one that prints the
    module constant regardless. So the run's configuration is moved to a clock
    LEAN does not default to, and the whole disclosure has to follow it: the
    per-observation target, the demand's clock, the sentence, and the flag that
    says the clock was read rather than assumed.

    THE k=260 SELF-CORRECTION, kept and re-pointed. D38 asserted it on the
    ANNUALISED target — 1/sqrt(K) annualised at sqrt(K) is 1.00 for every K — and
    that is an identity a hardcoded 1.0 satisfies as happily as a computed one.
    D41 asserts it where it discriminates: the PER-OBSERVATION target moves with
    the stored clock, and so does the hurdle on the run's own clock, while
    `engine_convention_annualised` — the field whose whole job is to state the
    engine's 1.00 — is the only one that stays put.

    AND THE ANNUALISATION CLOCK IS NOT THIS CLOCK. `tradingDaysPerYear` is the
    convention the target was WRITTEN in; the series is OBSERVED at its own rate;
    D38 used the first to annualise and that is the defect this file's round
    three closes. So `required_sharpe_clock` must follow the SERIES even when the
    stored configuration says 260.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 20.0
    r["robustness"]["psr_inputs"] = {"trading_days_per_year": 260}
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    series = r["daily_returns"]["strategy"]
    kk = float(st.observations_per_year(
        [str(d)[:10] for d in r["daily_returns"]["dates"]],
        len(series))["obs_per_year"])
    assert luck["engine_trading_days_per_year"] == 260.0
    assert luck["engine_trading_days_assumed"] is False
    # THE SERIES' CLOCK, NOT THE CONFIGURATION'S — and they are close enough
    # (261.64 against 260) that only an exact assertion tells them apart, which
    # is why both are named here.
    assert luck["required_sharpe_clock"] == luck["obs_per_year"] == round(kk, 2)
    assert luck["required_sharpe_clock"] != 260.0
    assert luck["target_sharpe"] == round(1.0 / math.sqrt(260.0), 8)
    assert luck["target_sharpe"] != round(1.0 / math.sqrt(252.0), 8)
    # THE HURDLE FOLLOWS THE STORED CLOCK THROUGH THE TARGET, and the convention
    # field does not move at all — which is what makes it a conversion.
    assert luck["engine_target_annualised"] == round(
        (1.0 / math.sqrt(260.0)) * math.sqrt(kk), 4)
    assert luck["engine_convention_annualised"] == 1.0
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "HARDCODED target of 1/sqrt(260) = 0.062017 per observation" in s
    assert "The engine's own 260-day convention" in s
    assert "read from this run's own stored configuration" in s
    assert "1/sqrt(252)" not in s

    # and the DEFAULT arm says it is a default, in the same words the reader
    # needs to tell the two apart.
    plain = evaluate(_alpha(psr=90.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                     walkforward=CLEAN_WALK,
                     criteria={"psr_basis": "engine_reported",
                               "min_psr_pct": 65.0})["checks"]["luck"]
    assert plain["engine_trading_days_assumed"] is True
    assert plain["engine_trading_days_per_year"] == 252.0


@pytest.mark.parametrize("clock", [200, 252, 260, 365, None, 0, "x"])
def test_the_STORED_CLOCK_MOVES_A_DISCLOSURE_AND_NEVER_A_VERDICT(clock):
    """THE BOUNDARY, asserted rather than promised.

    `robustness.psr_inputs` is a CAPTURE block, and its docstring says no
    criterion's pass/fail reads any of it. D38 gave the gate one reader —
    `trading_days_per_year`, for the sentence — and a sentence about a boundary
    is worth nothing beside a test of it.

    The engine hurdle's verdict is `psr_pct >= min_psr_pct`. Neither side of
    that inequality involves the target or the clock, so moving the clock across
    its whole plausible range, and past every malformed value, must leave
    `passed`, `evaluated_pct`, `measurable` and the failure SET size untouched
    while the demand and the sentence follow it. If this ever fails, a capture
    field has become a threshold.
    """
    def judged(stored):
        r = _alpha(psr=90.0)
        r["robustness"]["psr_pct"] = 20.0
        if stored is not None:
            r["robustness"]["psr_inputs"] = {"trading_days_per_year": stored}
        return evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                        criteria={"psr_basis": "engine_reported",
                                  "min_psr_pct": 65.0})

    base, moved = judged(None), judged(clock)
    assert base["passed"] == moved["passed"] is False
    assert len(base["failures"]) == len(moved["failures"])
    for key in ("measurable", "evaluated_pct", "engine_psr_pct",
                "luck_psr_pct", "level_pct", "applied", "n_obs"):
        assert base["checks"]["luck"][key] == moved["checks"]["luck"][key], key
    # and the DISCLOSURE does move, for the clocks that are readable — without
    # this the invariance above would also hold for a leg that ignored the field
    if isinstance(clock, int) and clock > 0 and clock != 252:
        assert (moved["checks"]["luck"]["required_sharpe_annualised"]
                != base["checks"]["luck"]["required_sharpe_annualised"])


@pytest.mark.parametrize("stored", [0, -1, 0.0, "252", True, None, {},
                                    float("nan"), float("inf")])
def test_an_UNUSABLE_stored_clock_falls_back_and_SAYS_it_fell_back(stored):
    """A stored configuration is a stored value, so it arrives malformed.

    A zero or negative clock would make the target infinite or imaginary; a
    string would raise inside a square root; `True` is not 1 trading day per
    year. All of them fall back to the engine's default AND report
    `engine_trading_days_assumed`, because a 252 that was read and a 252 that
    was substituted are different facts about the run.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 20.0
    r["robustness"]["psr_inputs"] = {"trading_days_per_year": stored}
    luck = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    criteria={"psr_basis": "engine_reported",
                              "min_psr_pct": 65.0})["checks"]["luck"]
    assert luck["engine_trading_days_per_year"] == 252.0
    assert luck["engine_trading_days_assumed"] is True
    assert luck["measurable"] is True


def test_a_premia_claim_ON_THE_ENGINE_BASIS_solves_its_bar_from_the_STRATEGY():
    """THE BAR FOLLOWS THE STATISTIC, NOT THE CLAIM TYPE.

    `claim_scope` has said since v4.4 that a premia claim judged on
    `engine_reported` was scored on the strategy's ABSOLUTE Sharpe — the engine
    knows nothing about this fund's benchmark. The bar did not follow: it took
    the ADVANTAGE's moments and solved them against a target of ZERO, then
    printed the answer in a sentence whose stated target is 1.00. The rendered
    result was "demands an annualised excess Sharpe of about +0.04" beside "an
    annualised Sharpe of exactly 1.00" — a demand BELOW its own target, which
    cannot happen, and which reads as a trivial hurdle.

    THE INVARIANT THAT CATCHES IT WITHOUT REDERIVING ANYTHING: a bar solved at
    a level above 50% against a target T must exceed T. That is true of every
    shape and every sample size, so it needs no fixture arithmetic to defend —
    and it is exactly what the defect violated.

    Not shipped: `premia_psr_basis` defaults to `target_zero_module`. Real,
    selectable and declared in `PSR_BASES`, which is why it has a test.
    """
    r = _premia(-0.03)
    r["robustness"]["psr_pct"] = 20.0
    out = judge(r, premia_psr_basis="engine_reported",
                premia_min_luck_pct=65.0)
    luck = out["checks"]["luck"]
    assert luck["claim_scope"] == "strategy sharpe"
    tgt = luck["engine_target_annualised"]
    req = luck["required_sharpe_annualised"]
    assert req is not None
    assert req > tgt, (req, tgt)

    # AND IT IS THE STRATEGY'S SERIES, re-derived independently — the invariant
    # above would also hold for some other correct-looking number.
    series = r["daily_returns"]["strategy"]
    kk = float(luck["obs_per_year"])
    want = st.sharpe_bar_for_psr(65.0, series, st.lean_psr_target()["per_obs"])
    assert want["measurable"], want
    assert req == round(float(want["sharpe_per_obs"]) * math.sqrt(kk), 4)

    # THE DEFECT'S OWN VALUE, so the assertion above is known to discriminate:
    # the advantage's moments against zero give a completely different figure.
    adv = r["premia_inputs"]["advantage"]
    wrong = st.sharpe_bar_for_psr_from_moments(
        65.0, int(adv["n"]), float(adv["skew"]), float(adv["kurtosis"]), 0.0)
    wrong_v = round(float(wrong["sharpe_per_obs"]) * float(adv["stdev"])
                    * math.sqrt(kk), 4)
    assert req != wrong_v
    assert wrong_v < tgt, "the fixture no longer reproduces the defect's shape"

    # AND THE TRAILING CLAUSE NAMES THE RIGHT SERIES. The target-zero reading
    # quoted here comes from the ADVANTAGE, not from the strategy's returns, so
    # calling it "the same series" would be a third mislabelling inside the
    # sentence built to end mislabelling.
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "A target-zero reading of this run's ADVANTAGE series" in s
    assert "the same series" not in s
    # the alpha branch keeps the other wording, so the two cannot collapse.
    # `robustness.psr_pct` is moved BELOW the level on purpose: the sentence is
    # only emitted on a refusal, and `_alpha(psr=90.0)` alone would pass.
    ar = _alpha(psr=90.0)
    ar["robustness"]["psr_pct"] = 20.0
    alpha = evaluate(ar, CLEAN_HOLDOUT, CLEAN_SWEEP,
                     walkforward=CLEAN_WALK,
                     criteria={"psr_basis": "engine_reported",
                               "min_psr_pct": 65.0})
    a = [f for f in alpha["failures"] if "probabilistic Sharpe" in f][0]
    assert "A target-zero reading of the same series" in a
    assert "ADVANTAGE series" not in a

    # AND THE PREMIA DEFAULT IS UNTOUCHED: on its own basis the bar IS the
    # advantage's, which is the frozen behaviour this must not have disturbed.
    on_advantage = judge(r)
    assert on_advantage["checks"]["luck"]["claim_scope"] == "premia advantage"
    assert on_advantage["checks"]["luck"]["required_sharpe_annualised"] \
        != luck["required_sharpe_annualised"]


def test_a_microscopic_level_is_an_OFF_SWITCH_but_a_VISIBLE_one():
    """THE RESIDUAL THE RANGE CHECK DOES NOT CLOSE, pinned rather than papered.

    D37's range check refuses a level outside (0, 100), and its comment claimed
    that afterwards "the only way to decline the filter is the boolean". That
    over-claims and the adversary measured the counter-example: 1e-12 is
    strictly inside the interval, so it passes the check and then clears every
    measurable reading.

    No epsilon was invented to close it — a threshold with no measured basis is
    worse than an open one, and these levels are control-layer values a human
    moves in a versioned change. What this test pins is the pair of facts the
    corrected comment now claims: the level DOES pass everything, and it is
    VISIBLE in the verdict while doing so, which the silent skip was not.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 0.001        # would fail any honest level
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 1e-12})
    luck = out["checks"]["luck"]
    assert luck["measurable"] is True
    assert not [f for f in out["failures"] if "probabilistic Sharpe" in f]
    # THE VISIBILITY HALF — and it is the half the comment now rests on.
    assert luck["level_pct"] == 1e-12
    assert luck["applied"] is True
    assert out["criteria"]["min_psr_pct"] == 1e-12
    # the ENDPOINT next door is still a refusal, so this is a residual and not
    # a hole the range check failed to cover at all.
    zero = evaluate(_alpha(psr=90.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                    walkforward=CLEAN_WALK, criteria={"min_psr_pct": 0.0})
    assert zero["checks"]["luck"]["measurable"] is False


def test_both_readings_survive_the_revert_on_the_shipped_alpha_bar():
    """The capture is the reason the mislabelling was findable at all, and it
    must not have been a casualty of reverting the basis that consumed it. On a
    verdict judged by the engine, the target-zero reading of the same series is
    still recorded — and it is what a re-calibration will be argued from."""
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 12.5
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    luck = out["checks"]["luck"]
    assert luck["basis"] == "engine_reported"
    assert luck["evaluated_pct"] == 12.5
    assert luck["engine_psr_pct"] == 12.5
    assert luck["luck_psr_pct"] == pytest.approx(90.0, abs=0.05)


@pytest.mark.parametrize("stored", ["not-a-number", [], {}, True, False, None])
def test_a_malformed_stored_engine_PSR_is_a_VERDICT_not_a_crash(stored):
    """A GATE MUST RETURN A VERDICT, NEVER RAISE — on the field D37 put on the
    hot path.

    `robustness.psr_pct` is a STORED value: written by an older belt,
    round-tripped through JSON, possibly truncated. It was checked for `is
    None` and nothing else, so a string, list or dict reached
    `evaluated_pct >= level` and took the whole judgement down with a
    TypeError, and a stored `true` was read as a probability of 1.0 —
    `isinstance(True, int)` being how a bool gets in.

    THE DEFECT IS OLDER THAN THIS DIFF AND THE DIFF IS WHY IT MATTERS: before
    D37 the engine basis was an opt-in alternate, and after it every alpha
    verdict this fund produces reads this field. The premia advantage block six
    lines up has carried the presence-AND-numeric-type guard since v4.4; this
    is the same guard on the other branch, and this is the test that fails if
    either loses it. Found by the Gauntlet on the finished diff — the third
    dispatch running in which a raise-path in this leg was found by something
    other than the suite.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = stored
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    luck = out["checks"]["luck"]
    assert luck["measurable"] is False, luck
    assert out["passed"] is False
    assert any("the luck filter could not be applied" in f
               for f in out["failures"]), out["failures"]
    # AND THE TWO ABSENCES ARE NOT ONE SENTENCE: a field nobody wrote and a
    # field somebody wrote badly are different facts about the belt, and a
    # reader chasing one must not be sent to the other.
    if stored is None:
        assert "published no usable probabilistic Sharpe" in luck["reason"]
    else:
        assert "is not a number" in luck["reason"], luck["reason"]
        assert repr(stored) in luck["reason"]


@pytest.mark.parametrize("level,expect,forbid", [
    (0.0, "off-switch", "refusal and not a bar"),
    (-1.0, "off-switch", "refusal and not a bar"),
    (100.0, "refusal and not a bar", "off-switch"),
    (1e9, "refusal and not a bar", "off-switch"),
])
def test_the_range_refusal_explains_the_END_it_actually_failed(level, expect,
                                                               forbid):
    """A refusal sentence must be true of the value that caused it.

    The first draft appended one fixed clause — "at 0 the criterion would pass
    everything it can measure" — to EVERY out-of-range level, including 100.1,
    where the consequence is the exact opposite: a level at or above 100 can
    refuse a reading it measured perfectly. Explaining the wrong end of the
    interval is the same defect this whole leg exists to end, at one tenth the
    scale, and a test that only checks the interval "(0, 100)" appears cannot
    see it. Caught by reading the sentence, pinned here so it stays fixed.
    """
    out = evaluate(_alpha(psr=90.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                   walkforward=CLEAN_WALK, criteria={"min_psr_pct": level})
    reason = out["checks"]["luck"]["reason"]
    assert "(0, 100)" in reason, reason
    assert expect in reason, reason
    assert forbid not in reason, reason


# =========================================================================
# 3. WHERE AN AUDITOR LOOKS — the criteria a verdict records
# =========================================================================

def test_a_premia_verdict_records_the_PREMIA_criteria_where_the_comment_says():
    """`premia_require_luck_filter`'s comment promised the off-switch was
    "recorded in the stored verdict's own `criteria`". It was not: the
    top-level dict held the ALPHA bar alone and the premia keys lived two
    levels down. A control whose state cannot be found where its own
    documentation points is the write-only-column shape (adversary,
    run-adversary-d36-prodgate2).
    """
    out = judge(_premia(0.20))
    crit = out["criteria"]
    for key in PREMIA_CRITERIA:
        assert key in crit, key
    for key in CRITERIA:
        assert key in crit, key
    assert crit["premia_require_luck_filter"] is True
    # AND THE STATE IT RECORDS IS THE ONE THAT WAS APPLIED, not the default —
    # a dict that always prints the shipped bar would satisfy the assertion
    # above while telling an auditor the opposite of what happened.
    off = judge(_premia(0.20), premia_require_luck_filter=False)
    assert off["criteria"]["premia_require_luck_filter"] is False
    assert off["checks"]["luck"]["applied"] is False


def test_an_alpha_verdict_records_the_ALPHA_criteria_and_nothing_else():
    """The other half, and the one that must never move: an alpha verdict's
    `criteria` is byte-identical to `CRITERIA`. The premia merge is scoped to
    premia verdicts, and a leak would put premia keys into every stored alpha
    verdict this fund has."""
    out = evaluate(_alpha(psr=90.0), CLEAN_HOLDOUT, CLEAN_SWEEP,
                   walkforward=CLEAN_WALK)
    assert out["criteria"] == CRITERIA
    assert not [k for k in out["criteria"] if k.startswith("premia")]


# =========================================================================
# 4. THE ACCEPTANCE TEST — the demand IS the verdict boundary
# =========================================================================

RF_ANNUAL = 0.05
VOL_ANNUAL = 0.20
CALENDAR_YEAR = 365.25


def _calendar_series(true_ann_excess_sharpe: float, years: int = 8,
                     seed: int = 7) -> tuple[list[str], list[float]]:
    """A CALENDAR-daily return series whose true annualised excess Sharpe is
    known by construction — one observation per calendar day, which is the shape
    LEAN's ``listPerformance`` actually has on this fund's runs.

    The risk-free rate is added back in, because the engine subtracts
    ``riskFreeRate / tradingDaysPerYear`` per observation from whatever series it
    is handed: the raw series must carry it for the engine's own arithmetic to
    recover the intended excess Sharpe.
    """
    rnd = random.Random(seed)
    d0 = date(2016, 1, 1)
    n = int(CALENDAR_YEAR * years)
    sd_obs = VOL_ANNUAL / math.sqrt(CALENDAR_YEAR)
    rf_obs = RF_ANNUAL / 252.0                   # exactly what LEAN subtracts
    mu_excess = true_ann_excess_sharpe * VOL_ANNUAL / CALENDAR_YEAR
    dates = [(d0 + timedelta(days=i)).isoformat() for i in range(n)]
    rets = [mu_excess + rf_obs + rnd.gauss(0.0, sd_obs) for _ in range(n)]
    return dates, rets


def _engine_psr(rets: list[float], tdy: int = 252) -> float:
    """LEAN's published PSR, re-derived HERE from the engine's own source rather
    than imported from the module under test.

    ``PortfolioStatistics.cs:311-312`` feeds ``ProbabilisticSharpeRatio`` a
    benchmark of ``1/sqrt(tradingDaysPerYear)`` and a per-sample risk-free rate
    of ``riskFreeRate/tradingDaysPerYear``; ``Statistics.cs:231-237`` subtracts
    that rate from the mean. An independent re-derivation is the point: a test
    that computed the engine's number with `app.fund.statistics` could not tell
    a correct hurdle from a hurdle that agrees with our own arithmetic.
    """
    n = len(rets)
    mu = sum(rets) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in rets) / (n - 1))
    srx = (mu - RF_ANNUAL / tdy) / sd
    m2 = sum((v - mu) ** 2 for v in rets) / n
    m3 = sum((v - mu) ** 3 for v in rets) / n
    m4 = sum((v - mu) ** 4 for v in rets) / n
    g1, g2 = m3 / m2 ** 1.5, m4 / m2 ** 2 - 3.0
    skew = math.sqrt(n * (n - 1)) / (n - 2) * g1
    kurt = ((n - 1) * ((n + 1) * g2 + 6)) / ((n - 2) * (n - 3))
    shape = 1 - skew * srx + ((kurt - 1) / 4.0) * srx * srx
    z = (srx - 1.0 / math.sqrt(tdy)) / math.sqrt(shape / (n - 1))
    return 100.0 * 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _realised_excess_annualised(rets: list[float], k: float,
                                tdy: int = 252) -> float:
    """The number the sentence is ABOUT: this series' excess Sharpe, annualised
    on the clock it is observed at."""
    n = len(rets)
    mu = sum(rets) / n
    sd = math.sqrt(sum((v - mu) ** 2 for v in rets) / (n - 1))
    return (mu - RF_ANNUAL / tdy) / sd * math.sqrt(k)


def test_the_DEMAND_is_the_verdict_boundary_a_reader_can_check():
    """THE ADVERSARY'S DEMONSTRATION (run-adversary-d38), as an acceptance test.

    THE KILL. `checks["luck"]` shipped three `*_annualised` fields on TWO
    clocks: `sharpe_annualised` on the series' own ~365 obs/yr beside a target
    and a demand on the engine's 252. A reader comparing the run's annualised
    Sharpe with the annualised Sharpe the level demands — the only comparison
    those field names invite — read PASS on candidates the gate FAILED.

    THE PROPERTY THIS PINS, and it needs no formula from the module: for a
    series whose TRUE annualised excess Sharpe is known, the gate's verdict must
    agree with the reader's comparison of that Sharpe against
    `required_sharpe_annualised`. Six strategies are built spanning the
    boundary, the engine's PSR is re-derived from LEAN's own source, and the two
    answers must agree on all six.

    AND THE OLD ANSWER MUST DISAGREE, or this test would pass on the broken
    tree too. The same demand restated on the engine's 252 clock — exactly what
    D38 published — is compared row by row and must disagree on at least one:
    measured, it disagrees on three of six.
    """
    per_obs = float(st.lean_psr_target()["per_obs"])
    crit = {**CRITERIA, "psr_basis": "engine_reported", "min_psr_pct": 65.0}
    agree_own, agree_engine, margins = 0, 0, []
    for true_ann in (0.90, 1.00, 1.10, 1.19, 1.21, 1.30):
        dates, rets = _calendar_series(true_ann)
        res = {
            "robustness": {"psr_pct": round(_engine_psr(rets), 3),
                           "psr_inputs": {"trading_days_per_year": 252}},
            "daily_returns": {"present": True, "strategy": rets,
                              "dates": dates},
        }
        out, failures = _luck_leg(res, crit, False, {})
        cleared = not failures
        k = float(out["obs_per_year"])
        req = float(out["required_sharpe_annualised"])
        realised = _realised_excess_annualised(rets, k)

        # ONE CLOCK: the demand, the target and the series all on the same one.
        assert out["required_sharpe_clock"] == round(k, 2)
        assert out["engine_target_annualised"] == round(
            per_obs * math.sqrt(k), 4)
        # and the withdrawn field cannot be mistaken for the measurement
        assert out["sharpe_annualised"] is None
        assert out["sharpe_annualised_raw"] is not None

        # THE READER'S COMPARISON == THE GATE'S VERDICT.
        agree_own += int(cleared is (realised >= req))
        # D38's restatement of the same demand on the engine's 252 clock.
        agree_engine += int(cleared is (realised >= req / math.sqrt(k / 252.0)))
        margins.append(abs(realised - req))

    assert agree_own == 6, "the demand is not the boundary the gate applies"
    # NOT A KNIFE EDGE (D34): every row sits clear of the boundary, so the six
    # agreements are a property and not six coin flips that landed well.
    #
    # THE HEADROOM, MEASURED, because "clear of the boundary" is a claim and
    # not a feeling: the six margins are 0.373 / 0.273 / 0.173 / 0.083 / 0.063
    # / 0.027, so the TIGHTEST row sits 0.0267 above a guard of 0.02 — about a
    # third of headroom, and the thinnest number in this file. The row is the
    # `true_ann=1.30` one. Anyone who changes `_calendar_series`'s seed, its
    # year count, RF_ANNUAL or VOL_ANNUAL must re-read this figure: it is the
    # margin that decides whether this test is measuring the boundary or
    # sitting on it. (Recomputed by the Gauntlet on the finished diff.)
    assert min(margins) > 0.02, min(margins)
    # THE DISCRIMINATOR: the answer this dispatch replaced gets it wrong.
    assert agree_engine == 3, agree_engine


# =========================================================================
# 4. THE MUTATION SURVIVORS, closed
#
# Four mutants survived the D41 pass. Each was re-derived by hand before being
# written down — a survivor is a gap or a retirement, never a note — and three
# of the four were REAL gaps that all pointed at the same uncovered shape: a
# run whose SERIES is fine and whose DATES are not. The D41 diff added a branch
# for exactly that case and nothing exercised it.
#
# The fourth (`"annualised": per_obs * sqrt(kk)` hardcoded to `1.0`) is RETIRED
# rather than closed, with its proof in `test_the_derived_annualised_form_*`.
# =========================================================================

def _no_clock_verdict():
    """A usable series whose dates carry no readable spacing.

    Every date identical, so `observations_per_year` refuses with `usable:
    False` — the series is 400 real returns and the clock is absent. This is the
    ONLY shape that separates "no series" from "no clock", and the gate now says
    two different things about them.
    """
    r = _alpha(psr=20.0)
    n = len(r["daily_returns"]["strategy"])
    r["daily_returns"]["dates"] = ["2021-01-04"] * n
    return evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP,
                    walkforward=CLEAN_WALK)["checks"]["luck"], r


def test_a_run_with_a_SERIES_but_NO_READABLE_DATES_states_the_target_and_drops_only_the_clock():
    """Mutants M3 and M10, both survivors of the first pass, both here.

    M3 loosened the demand's guard from `and k` to `and (k or the engine's
    clock)`, so a run with no measured observation rate would have had its
    demand computed on 252 — the exact substitution this dispatch exists to
    remove, re-entering through a fallback. It survived because no fixture had
    a series without a clock.

    M10 collapsed the two absence sentences into one, telling a reader with 400
    perfectly good returns that the run "carries no usable return series". That
    sends them hunting for a missing series when what is missing is the dates,
    which is the misdirection D29's rule was written about.

    WHAT MUST BE TRUE: the per-observation target is a constant and is stated;
    everything that needs a clock is ABSENT rather than defaulted; and the
    sentence names the DATES.
    """
    luck, _ = _no_clock_verdict()

    # The clock is absent, and absence is not 252.
    assert luck["obs_per_year"] is None
    assert luck["engine_target_annualised"] is None
    assert "required_sharpe_annualised" not in luck
    assert "required_sharpe_clock" not in luck

    # The constant does not depend on the run, so it is still stated.
    assert luck["target_sharpe"] == round(st.lean_psr_target()["per_obs"], 8)
    assert luck["measurable"] is True

    # 400 real returns: this run is not short of a series, and the reading the
    # series supports was still taken.
    assert luck["n_obs"] == 400
    assert luck["luck_psr_pct"] is not None


def test_the_no_clock_sentence_names_the_DATES_and_not_a_missing_series():
    """The SHARED-WORD half of M10: both absence sentences end in the same
    fourteen words (`so what the level demands OF IT is unstated`), so an
    assertion on that phrase passes under the mutant. The discriminating clause
    is the only thing worth asserting on.
    """
    luck, r = _no_clock_verdict()
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK)
    sentence = next(f for f in out["failures"] if "probabilistic Sharpe" in f)

    assert "dates do not yield a usable observation rate" in sentence
    assert "carries no usable return series" not in sentence
    # And the restatement clause says why it cannot annualise, rather than
    # quietly annualising on the engine's convention.
    assert "no measured observation rate" in sentence
    assert "cannot be restated on its own clock" in sentence


def test_the_statistic_sentence_states_the_PER_OBSERVATION_target_and_its_own_clock():
    """Mutants M8 and M9.

    M8 rounded the per-observation target in `statistic` from six decimals to
    two — `0.06` — which is not a number a reader can check against
    1/sqrt(252). M9 dropped the annualised clause entirely, leaving a
    per-observation figure with no restatement in the units every other field
    on the payload uses. Both survived: nothing asserted on the CONTENT of
    `statistic`, only on its existence.

    `statistic` is the field a human reads to find out what the criterion
    asked. It carries both forms or it carries a riddle.
    """
    per_obs = st.lean_psr_target()["per_obs"]
    out = _alpha_verdict()["checks"]["luck"]
    k = float(out["obs_per_year"])

    # Six decimals, and PINNED — not "contains the word Sharpe".
    assert f"{per_obs:.6f}" in out["statistic"], out["statistic"]
    assert "per observation" in out["statistic"]
    # The annualised clause, on THIS run's measured clock, with the rate named
    # so a reader can redo the arithmetic.
    assert f"an annualised {round(per_obs * math.sqrt(k), 4):.2f}" in \
        out["statistic"], out["statistic"]
    assert f"{out['obs_per_year']} observations a year" in out["statistic"]

    # AND THE CLAUSE IS CONDITIONAL, not decoration: strip the clock and it
    # goes, rather than falling back to the engine's convention.
    no_clock, _ = _no_clock_verdict()
    assert "an annualised" not in no_clock["statistic"], no_clock["statistic"]
    assert f"{per_obs:.6f}" in no_clock["statistic"]


def test_the_derived_annualised_form_is_kept_though_no_test_can_kill_it():
    """THE RETIREMENT, with its proof — mutant M16, `"annualised": per_obs *
    sqrt(kk)` replaced by a literal `1.0`.

    It survives, and it survives HONESTLY: the two forms are equal to within
    one unit in the last place, and no field derived from them is rounded finer
    than 1e-4. No test that asserts a true thing can distinguish them, so
    writing one would be theatre.

    The derived form is kept anyway, and the reason is coupling rather than
    arithmetic: it gives a defect in `per_obs` a SECOND place to show up. Break
    the square root and this figure moves off 1.00 while a hardcoded literal
    would keep reassuring the reader. This test therefore pins the ULP claim —
    if it ever stops holding, the retirement stops being valid and the mutant
    becomes a real gap.
    """
    worst = 0.0
    for k in list(range(1, 2000)) + [252, 365, 365.25, 1e6]:
        out = st.lean_psr_target(k)
        worst = max(worst, abs(out["annualised"] - 1.0))
    # One ULP at 1.0 is 2.22e-16; allow two and no more.
    assert worst <= 2 * 2.220446049250313e-16, worst
    # ...and the verdict field that carries it rounds to 4 places, which is
    # twelve orders of magnitude coarser. That is why the mutant is equivalent.
    assert round(1.0 + worst, 4) == 1.0


# =========================================================================
# 5. THE GAUNTLET'S FINDING — a THIRD reason the demand can be absent
# =========================================================================

def _unsolvable_bar_result():
    """A run whose series and dates are both fine and whose BAR still refuses.

    Sixty ordinary days and one -30% crash: skew -7.21, kurtosis 54.65. At a
    level of 99.9% the quadratic in `statistics.sharpe_bar_for_psr` has no
    verifiable root, so `required_sharpe_annualised` is absent while
    `obs_per_year` and `engine_target_annualised` are both present.

    A CALL, not a model: the moments come from a real return series pushed
    through the production solver, not from hand-set skew and kurtosis.
    """
    rng = random.Random(0)
    series = [rng.gauss(0.0005, 0.004) for _ in range(60)]
    series[7] = -0.30
    r = _alpha(psr=20.0)
    r["daily_returns"] = daily_returns_block(series)
    return r


def test_an_UNSOLVABLE_BAR_is_not_reported_as_unreadable_dates():
    """THE VERDICT THAT CONTRADICTED ITSELF, found by the Gauntlet on the
    finished diff — after the same clause had already been split in two for
    exactly this kind of misattribution.

    `required_sharpe_annualised` goes absent for THREE reasons, and the code
    discriminated on only two of them: no series, no clock, and — the one
    nobody had enumerated — a bar the solver cannot state for a series of this
    shape. The third fell through to the second's sentence, so a run whose
    dates are perfectly readable was told its dates were not... in the same
    string that had just quoted its measured observation rate and annualised
    its target on that very clock.

    The assertions below therefore pin BOTH halves: the clock is quoted, AND
    the sentence does not deny the clock it just quoted.
    """
    out = evaluate(_unsolvable_bar_result(), CLEAN_HOLDOUT, CLEAN_SWEEP,
                   walkforward=CLEAN_WALK, criteria={"min_psr_pct": 99.9})
    luck = out["checks"]["luck"]

    # The precondition that makes this the THIRD case and not one of the two.
    assert luck["obs_per_year"] is not None
    assert luck["engine_target_annualised"] is not None
    assert len(_unsolvable_bar_result()["daily_returns"]["strategy"]) == 60
    assert "required_sharpe_annualised" not in luck

    sentence = next(f for f in out["failures"] if "probabilistic Sharpe" in f)
    # The real cause, named.
    assert "no Sharpe reproduces this level for a series of this shape" in \
        sentence, sentence
    assert "series and clock are both readable" in sentence
    # AND NOT the other two causes, either of which would be a false statement
    # about this run.
    assert "dates do not yield a usable observation rate" not in sentence
    assert "carries no usable return series" not in sentence
    # THE SELF-CONTRADICTION, asserted directly: the clock IS quoted here, so a
    # clause denying it cannot also be.
    assert f"measured at {luck['obs_per_year']} observations a year" in sentence


def test_the_three_absent_demand_sentences_are_mutually_exclusive():
    """Would catch: a fourth branch being added that overlaps an existing one,
    or two of the three becoming reachable together.

    Each cause is constructed independently and each verdict must carry exactly
    ONE of the three discriminating clauses — never zero, never two. The shared
    tail ("what the level demands OF IT is unstated") is deliberately NOT what
    is counted: it appears in all three and can tell them apart in none.
    """
    CLAUSES = ("carries no usable return series",
               "dates do not yield a usable observation rate",
               "series and clock are both readable")

    no_series = _alpha(psr=20.0)
    no_series["daily_returns"] = {"present": True, "strategy": [0.01],
                                  "dates": ["2021-01-04"]}
    no_clock = _alpha(psr=20.0)
    no_clock["daily_returns"]["dates"] = (
        ["2021-01-04"] * len(no_clock["daily_returns"]["strategy"]))

    cases = {
        "no series": (no_series, {}),
        "no clock": (no_clock, {}),
        "unsolvable bar": (_unsolvable_bar_result(), {"min_psr_pct": 99.9}),
    }
    for label, (res, extra) in cases.items():
        out = evaluate(res, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                       criteria=extra or None)
        sentence = next(f for f in out["failures"]
                        if "probabilistic Sharpe" in f)
        hits = [c for c in CLAUSES if c in sentence]
        assert len(hits) == 1, (label, hits, sentence)
