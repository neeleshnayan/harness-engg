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
  3. THE SENTENCE TELLS THE TRUTH ABOUT A SKILL HURDLE — the target inverted
     out of THIS run, and the Sharpe the level demands AGAINST THAT TARGET.
     Never zero, and never absent-as-zero.
"""
from __future__ import annotations

import math

import pytest

from app.fund import statistics as st
from app.fund.gate import (CRITERIA, PREMIA_CRITERIA, PSR_BASES, evaluate)
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
    PortfolioStatistics.cs:311, an annualised Sharpe of exactly 1.00 for every
    candidate, on EXCESS returns. So the demand is solved against THAT, and
    annualised on the ENGINE's clock rather than the candidate's calendar one.

    THREE-WAY DISCRIMINATION, because two of the three candidate answers are
    the fund's own former ones and a test that only pins the right value cannot
    say it moved. The demand must equal the bar against 1/sqrt(252) on a 252
    clock, and must differ from BOTH the target-zero bar and the inverted-target
    bar on the candidate's clock.

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

    expected = round(float(want["sharpe_per_obs"]) * math.sqrt(252.0), 4)
    wrong_target = round(float(against_zero["sharpe_per_obs"]) * math.sqrt(252.0), 4)
    wrong_v44 = round(float(old["sharpe_per_obs"]) * math.sqrt(kk), 4)
    assert len({expected, wrong_target, wrong_v44}) == 3, (
        "the fixture cannot tell the three answers apart")
    assert luck["required_sharpe_annualised"] == expected
    assert luck["required_sharpe_clock"] == 252.0
    assert luck["target_sharpe"] == round(hurdle["per_obs"], 8)
    assert luck["engine_target_annualised"] == 1.0

    sentence = [f for f in out["failures"] if "probabilistic Sharpe" in f]
    assert len(sentence) == 1, out["failures"]
    s = sentence[0]
    assert "THIS IS A SKILL HURDLE, NOT A LUCK TEST." in s
    assert "HARDCODED target of 1/sqrt(252) per observation" in s
    assert "an annualised Sharpe of exactly 1.00" in s
    assert "on EXCESS returns, subtracting a daily risk-free rate" in s
    assert ("Clearing 65.0% against that target demands an annualised excess "
            "Sharpe") in s
    assert f"{expected:+.2f}" in s
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
    target never depended on the run, so it is stated here too.

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
    assert luck["engine_target_annualised"] == 1.0
    assert luck["target_sharpe"] == round(st.lean_psr_target()["per_obs"], 8)
    assert luck.get("required_sharpe_annualised") is None
    assert luck.get("required_sharpe_clock") is None
    # the retired fields are GONE, not renamed and left behind
    assert "engine_implied_target_annualised" not in luck
    assert "engine_implied_target_note" not in luck
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "an annualised Sharpe of exactly 1.00" in s
    assert "no usable return series, so what the level demands OF IT is unstated" in s
    assert "demands an annualised excess Sharpe" not in s
    assert "UNSTATED rather than zero" not in s
    assert "could not be recovered" not in s


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
    assert luck["engine_target_annualised"] == 1.0
    want = st.sharpe_bar_for_psr(65.0, series, st.lean_psr_target()["per_obs"])
    assert want["measurable"], want
    assert luck["required_sharpe_annualised"] == round(
        float(want["sharpe_per_obs"]) * math.sqrt(252.0), 4)
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

    The ANNUALISED target stays 1.00 by construction — 1/sqrt(K) annualised on
    sqrt(K) is 1.00 for any K — and that invariance is the point of the hurdle,
    so it is asserted rather than treated as a fixed constant that happens to
    agree.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 20.0
    r["robustness"]["psr_inputs"] = {"trading_days_per_year": 260}
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    assert luck["engine_trading_days_per_year"] == 260.0
    assert luck["engine_trading_days_assumed"] is False
    assert luck["required_sharpe_clock"] == 260.0
    assert luck["target_sharpe"] == round(1.0 / math.sqrt(260.0), 8)
    assert luck["target_sharpe"] != round(1.0 / math.sqrt(252.0), 8)
    assert luck["engine_target_annualised"] == 1.0
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "HARDCODED target of 1/sqrt(260) per observation" in s
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


@pytest.mark.parametrize("stored", [0, -1, 0.0, "252", True, None, {}])
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
