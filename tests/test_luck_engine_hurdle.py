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

def test_the_engine_sentence_states_the_demand_AGAINST_THE_INVERTED_TARGET():
    """THE DEFECT THIS CLOSES, and it was in the draft's own new code.

    `required_sharpe_annualised` was solved at target 0.0 for BOTH bases and
    then simply not quoted in the engine sentence. That left a precise,
    confident, wrong number on every stored verdict — the demand of a
    target-zero criterion, on a verdict produced by a criterion that does not
    test one. The disclosure had the same defect as the sentence it was added
    to fix.

    Asserted by RE-DERIVING the figure independently here: the demanded Sharpe
    must equal the bar solved against the run's own inverted target, and must
    NOT equal the bar solved against zero. Two numbers that differ is the whole
    proof; asserting only the first cannot tell them apart.

    THE FIXTURE HAS TO CARRY THE DISAGREEMENT, and the first draft of this test
    did not — `_alpha(psr=20.0)` writes 20.0 into `robustness` AND builds a
    series whose target-zero PSR is 20.0, so the inverted target came out at
    zero and both bars agreed to four decimals. A fixture in which the defect
    is invisible is not a test of it. So the series reads 90% at target zero
    while the engine published 20%, which is the shape the four positive
    controls actually had (2.128% published against 85.0% measured).
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

    ident = st.implied_target_sharpe(20.0, series)
    assert ident["measurable"], ident
    want = st.sharpe_bar_for_psr(65.0, series, ident["target_per_obs"])
    assert want["measurable"], want
    against_zero = st.sharpe_bar_for_psr(65.0, series, 0.0)
    assert against_zero["measurable"], against_zero

    expected = round(float(want["sharpe_per_obs"]) * math.sqrt(kk), 4)
    wrong = round(float(against_zero["sharpe_per_obs"]) * math.sqrt(kk), 4)
    assert expected != wrong, "the fixture cannot tell the two targets apart"
    assert luck["required_sharpe_annualised"] == expected
    assert luck["required_sharpe_annualised"] != wrong

    sentence = [f for f in out["failures"] if "probabilistic Sharpe" in f]
    assert len(sentence) == 1, out["failures"]
    s = sentence[0]
    assert "THIS IS A SKILL HURDLE, NOT A LUCK TEST." in s
    assert "puts its target at an annualised Sharpe of" in s
    assert "Clearing 65.0% against that target demands an annualised Sharpe" in s
    assert f"{expected:+.2f}" in s
    # and the words that are FALSE of this statistic stay gone.
    assert "is not distinguishable from luck on this much history" not in s
    # PUNCTUATION, because the read-through caught what the assertions could
    # not: the measurement clause borrowed the other branch's leading
    # semicolon, splicing a `.;` into the middle of the line.
    assert " This run measured " in s
    assert ".;" not in s


def test_an_unrecoverable_engine_target_leaves_the_demand_UNSTATED_not_zero():
    """ABSENCE IS NEVER ZERO, applied to a disclosure.

    With no usable series the engine's target cannot be inverted. The demand it
    implies is then UNKNOWN — and a bar solved against a fallback zero would be
    a confident number about a criterion nobody applied, which is the same
    defect one field over. The criterion itself still refuses on the engine's
    published figure, because that figure is what this basis reads: an absent
    series does not make the hurdle unmeasurable, only its explanation.
    """
    r = _alpha(psr=20.0)
    r.pop("daily_returns")
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    assert luck["measurable"] is True            # the engine number is readable
    assert luck["evaluated_pct"] == 20.0
    assert "engine_implied_target_annualised" not in luck
    assert luck.get("required_sharpe_annualised") is None
    assert luck.get("engine_implied_target_note")
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "UNSTATED rather than zero" in s
    assert "demands an annualised Sharpe" not in s


def test_an_UNINVERTIBLE_engine_psr_states_no_demand_even_with_a_full_series():
    """MUTATION SURVIVOR M13, and it has a real population.

    The sibling test above removes the series, so both the target and the bar
    go absent together and a `target = 0.0` fallback is invisible. THIS case
    separates them: a perfectly usable 400-observation series with a published
    PSR of exactly 0.0%, which pins the target at infinity and cannot be
    inverted. The bar COULD be solved against a zero fallback here — and doing
    so would put a precise, confident, wrong demand on the verdict, because the
    criterion is not testing a target of zero.

    NOT HYPOTHETICAL: three of the fund's 339 stored results carrying a series
    publish exactly 0.0% (scratchpad/d37probe/target_census.py). Absence is
    never zero, and this is the row where the difference is reachable.
    """
    r = _alpha(psr=90.0)
    r["robustness"]["psr_pct"] = 0.0
    assert len(r["daily_returns"]["strategy"]) > 100      # the series is fine
    out = evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                   criteria={"psr_basis": "engine_reported",
                             "min_psr_pct": 65.0})
    luck = out["checks"]["luck"]
    assert luck["measurable"] is True          # the engine's figure is readable
    assert luck["evaluated_pct"] == 0.0
    assert "engine_implied_target_annualised" not in luck
    assert luck.get("required_sharpe_annualised") is None
    assert "pins the target at infinity" in luck["engine_implied_target_note"]
    s = [f for f in out["failures"] if "probabilistic Sharpe" in f][0]
    assert "UNSTATED rather than zero" in s
    assert "demands an annualised Sharpe" not in s


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
