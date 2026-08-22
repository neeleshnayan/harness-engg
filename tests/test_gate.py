"""The candidate gate — the bar, applied identically to everything.

The property under test throughout: MISSING evidence must fail. A candidate
that was never held out has not survived a holdout, and a factory that treats
absent evidence as satisfied evidence quietly lowers its own bar until it
approves everything.
"""

import pytest

from app.fund.gate import CRITERIA, evaluate


def _good_result(**over):
    r = {
        "total_return_pct": 20.0,
        "benchmark_return_pct": 10.0,
        "capacity_usd": None,
        "capacity": {"capacity_usd": 5_000_000.0},
        "robustness": {
            "total_orders": 40,
            "psr_pct": 80.0,
            "costs": {"slippage_modelled": True},
        },
    }
    r.update(over)
    return r


GOOD_HOLDOUT = {"state": "done", "dates_honoured": True,
                "train": {"return_pct": 20.0}, "test": {"return_pct": 16.0}}
GOOD_SWEEP = {"breakeven_cost": {"breakeven_bps": 25.0}}

#: v2 requires consistency across independent folds, so a candidate that clears
#: the bar has to carry a walk-forward result. Under v1 a single lucky window was
#: enough, which is exactly what the null audit exploited.
GOOD_WALKFORWARD = {"folds_attempted": 4, "folds_measurable": 4,
                    "folds_retained": 3, "median_retention": 0.72}


def test_a_clean_candidate_passes():
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is True, out["failures"]
    assert out["gate_version"] == "v4.2"
    # Passing is not deployment, and the wording says so.
    assert "different claim from" in out["verdict"]


def test_an_unpriced_backtest_fails():
    r = _good_result()
    r["robustness"]["costs"] = {"slippage_modelled": False}
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("not priced" in f for f in out["failures"])


def test_too_few_trades_fails():
    r = _good_result()
    r["robustness"]["total_orders"] = 3
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("anecdote" in f for f in out["failures"])


def test_low_psr_fails_even_with_a_great_return():
    """The trap the whole system exists to catch: 100% win rate on 3 trades."""
    r = _good_result(total_return_pct=500.0)
    r["robustness"]["psr_pct"] = 22.0
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("distinguishable from luck" in f for f in out["failures"])


def test_trailing_buy_and_hold_fails():
    out = evaluate(_good_result(total_return_pct=5.0, benchmark_return_pct=30.0),
                   GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("expensive way to hold" in f for f in out["failures"])


def test_a_missing_holdout_fails_rather_than_passes():
    out = evaluate(_good_result(), None, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("no held-out test" in f for f in out["failures"])


def test_a_holdout_that_ran_the_same_dates_fails():
    bad = {**GOOD_HOLDOUT, "dates_honoured": False}
    out = evaluate(_good_result(), bad, GOOD_SWEEP)
    assert any("SAME dates twice" in f for f in out["failures"])


def test_an_edge_that_collapses_out_of_sample_fails():
    ho = {**GOOD_HOLDOUT, "test": {"return_pct": 1.0}}   # kept 5%
    out = evaluate(_good_result(), ho, GOOD_SWEEP)
    assert any("out of sample" in f for f in out["failures"])


def test_a_double_loss_holdout_cannot_pass_as_retained_edge():
    """v4.1. The raw `te / tr` this closed scored train −10% / test −8% as
    retention 0.80 — "kept 80% of its edge" for a strategy that lost money in
    both legs — and PASSED. Found by the validator's real-belt floor review."""
    ho = {**GOOD_HOLDOUT, "train": {"return_pct": -10.0},
          "test": {"return_pct": -8.0}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    assert out["checks"]["holdout_retention"] is None
    assert any("no edge to retain" in f for f in out["failures"]), out["failures"]


def test_a_near_zero_train_leg_cannot_explode_the_holdout_ratio():
    """v4.1. A real belt fold: train +0.03% / test +6.94% scored retention 231
    under the raw ratio and passed. Strictly positive is not enough — the
    MIN_TRAIN_RETURN_PCT floor now applies to the holdout leg too."""
    ho = {**GOOD_HOLDOUT, "train": {"return_pct": 0.03},
          "test": {"return_pct": 6.94}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    assert out["checks"]["holdout_retention"] is None
    assert any("explodes" in f for f in out["failures"]), out["failures"]


def test_holdout_retention_annualises_when_windows_are_known():
    """v4.1. With leg windows supplied the ratio compares RATES, so a short
    lucky test leg is no longer divided by a year-long train leg raw."""
    ho = {"state": "done", "dates_honoured": True,
          "train": {"return_pct": 20.0,
                    "window": ["2024-01-01", "2024-12-31"]},
          "test": {"return_pct": 16.0,
                   "window": ["2025-01-01", "2025-12-31"]}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is True, out["failures"]
    assert out["checks"]["holdout_retention_basis"] == "annualised"


def test_fragility_to_costs_fails():
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   {"breakeven_cost": {"breakeven_bps": 3.0}})
    assert any("dies at 3.0bps" in f for f in out["failures"])


def test_capacity_too_small_to_bother_fails():
    r = _good_result(capacity={"capacity_usd": 5_000.0})
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP)
    assert any("operational cost" in f for f in out["failures"])


def test_every_failure_is_reported_not_just_the_first():
    """The operator should see the whole picture, not fix one thing and
    resubmit into the next objection."""
    r = _good_result(total_return_pct=1.0, benchmark_return_pct=30.0)
    r["robustness"] = {"total_orders": 2, "psr_pct": 5.0,
                       "costs": {"slippage_modelled": False}}
    out = evaluate(r, None, {"breakeven_cost": {"breakeven_bps": 1.0}})
    assert len(out["failures"]) >= 5


def test_the_bar_is_data_and_can_be_tightened():
    tighter = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                       criteria={"min_psr_pct": 95.0})
    assert tighter["passed"] is False
    assert tighter["criteria"]["min_psr_pct"] == 95.0
    # and the default is untouched by that call
    # v2 raised this from 50%: measured nulls reached ~57% on this history, so
    # the old floor sat inside the noise it was meant to exclude.
    assert CRITERIA["min_psr_pct"] == 65.0


def test_a_holdout_that_placed_no_trades_is_not_read_as_a_lost_edge():
    """Zero orders in the test window is the ABSENCE of a result, not a 0%
    result. A strategy needing 180 days of history cannot fill its window
    inside a shorter test run started cold, so it trades nothing and scores a
    flat zero that looks identical to an edge that evaporated. Both fail — but
    saying the wrong one condemns strategies nobody actually examined, and
    sounds like evidence while doing it."""
    ho = {"state": "done", "dates_honoured": True,
          "train": {"return_pct": 20.0},
          "test": {"return_pct": 0.0, "total_orders": 0}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("no trades at all" in f for f in out["failures"]), out["failures"]
    # The train leg DID trade here, so the honest reading is that the rule never
    # met its entry condition — not that it lacked warm-up.
    assert any("never met its own entry condition" in f for f in out["failures"])
    # The misleading sentence must NOT also appear.
    assert not any("of its edge out of sample" in f for f in out["failures"])
    assert out["checks"]["holdout_retention"] is None


def test_a_holdout_that_traded_and_lost_its_edge_still_says_so():
    """The fix must not swallow the real finding it sits next to."""
    ho = {"state": "done", "dates_honoured": True,
          "train": {"return_pct": 20.0},
          "test": {"return_pct": 1.0, "total_orders": 12}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP)
    assert any("out of sample" in f for f in out["failures"]), out["failures"]
    assert not any("no trades at all" in f for f in out["failures"])


# --- v2: the holes the null audit found -------------------------------------
#
# Random-entry strategies passed gate v1 about half the time. These pin the three
# specific leaks so they cannot reopen quietly.

def test_an_unmeasured_cost_robustness_fails_rather_than_passes():
    """v1 wrote `if be_bps is not None and be_bps < floor`, so a candidate that
    was never cost-swept SATISFIED the cost-robustness bar by never being tested
    against it. In a gate whose doctrine is that missing evidence fails, that was
    the doctrine inverted."""
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   {"breakeven_cost": {"breakeven_bps": None,
                                       "reason": "no cost sweep was run"}},
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    assert any("never measured" in f for f in out["failures"]), out["failures"]


# --- v4.2: the floor that could not be reached -------------------------------
#
# The shape of a sweep that survived its whole cost grid, taken from the stored
# summary of candidate 144387901688 (announcement_premium, "Entry 20") rather
# than invented: `breakeven_bps: None`, the "still profitable" reason, and a
# `tested_range` of raw slip FRACTIONS. Entry 20's grid was 1/3/5 bps against a
# 10 bps floor, and it PASSED with zero failures.

def _survived_the_grid(*slips: float) -> dict:
    return {"breakeven_cost": {
        "parameter": "slip",
        "breakeven": None,
        "tested_range": [min(slips), max(slips)],
        "reason": "still profitable at every cost tested — raise the range to "
                  "find the limit"}}


ENTRY20_SWEEP = _survived_the_grid(0.0001, 0.0003, 0.0005)


def test_entry20s_grid_no_longer_certifies_a_floor_it_never_reached():
    """THE REGRESSION. Candidate 144387901688 passed gate v4.1 with ZERO
    failures on exactly this evidence: a 1/3/5 bps cost grid, all points
    profitable, judged against `min_breakeven_bps: 10.0`.

    A three-point grid stopping at 5 bps establishes breakeven > 5. The floor is
    10. v4.1 wrote the string "beyond the tested range" into `checks` and
    appended nothing — the register reading an absence as a pass, in the gate
    whose founding lesson is that missing evidence fails.

    Note the direction the old branch made invisible: the verdict would have
    been identical had the true breakeven been 7 bps.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT, ENTRY20_SWEEP,
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False, "v4.1 passed this; v4.2 must not"
    assert any("tested only to 5 bps and the floor is 10" in f
               for f in out["failures"]), out["failures"]
    assert any("widen the grid past the floor" in f for f in out["failures"])
    # The string stays as the annotation it always was, and the evidence the
    # verdict rests on is now visible rather than implied.
    assert out["checks"]["breakeven_bps"] == "beyond the tested range"
    assert out["checks"]["breakeven_max_tested_bps"] == 5.0


def test_profitable_beyond_a_grid_that_DID_reach_the_floor_is_a_genuine_pass():
    """The other half, and the reason this is not simply "fail the branch".

    "Still profitable at every cost tested" IS an answer when the grid went past
    the floor: a strategy priced at 20 bps and still making money has shown it
    survives being twice as wrong about costs as the bar demands. Failing that
    would punish the most robust possible result for not having a crossing
    point — which was the correct instinct behind the v2 branch this replaces.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   _survived_the_grid(0.0001, 0.0010, 0.0020),
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is True, out["failures"]
    assert out["checks"]["breakeven_bps"] == "beyond the tested range"
    assert out["checks"]["breakeven_max_tested_bps"] == 20.0


def test_a_grid_stopping_exactly_ON_the_floor_passes():
    """The boundary, pinned so it cannot drift either way. Tested TO 10 bps and
    still profitable means the breakeven is past 10, which is what a floor of
    10.0 asks. `<` not `<=`, matching every other floor in this file."""
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   _survived_the_grid(0.0001, 0.0010),
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is True, out["failures"]
    assert out["checks"]["breakeven_max_tested_bps"] == 10.0


def test_an_unreadable_tested_range_fails_rather_than_passes():
    """A sweep that claims survival but will not say how far it looked has not
    cleared anything. This is the same doctrine as the unmeasured breakeven one
    test up: absence is never zero, and it is never a pass either.

    Reachable in practice — `tested_range` is only written by the no-crossing
    branch of `breakeven_cost`, so any other producer of that reason string
    arrives here with nothing to check.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   {"breakeven_cost": {
                       "breakeven_bps": None,
                       "reason": "still profitable at every cost tested — raise "
                                 "the range to find the limit"}},
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    assert any("does not say how far it tested" in f
               for f in out["failures"]), out["failures"]
    assert out["checks"]["breakeven_max_tested_bps"] is None


def test_the_floor_comparison_is_not_made_on_a_rounded_figure():
    """A display convention must not become a quiet loosening.

    9.996 bps rounds to "10.0" at one decimal — the precision `breakeven_bps`
    itself uses — so a grid stopping just short of a 10.0 floor would print as
    having reached it. The comparison is on the raw float and the message keeps
    the digits that make it true.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   _survived_the_grid(0.0001, 0.0009996),
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    joined = " ".join(out["failures"])
    assert "tested only to 9.996 bps" in joined, joined
    assert "tested only to 10 bps" not in joined


def test_the_verdict_says_which_return_scale_the_breakeven_is_on():
    """Entry 20's total-return breakeven is 64.6 bps/side and its ACTIVE-return
    breakeven — the alpha claim's own fragility — is 13.9. Reading the first as
    the second overstates cost robustness by 4.6x.

    The belt cannot currently produce the active figure (sweep points carry no
    benchmark, and the one benchmark the candidate owns spans a different
    window), so the gate LABELS the scale rather than computing a number it
    would have to approximate. See the v4.2 note in gate.py.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward=GOOD_WALKFORWARD)
    assert out["checks"]["breakeven_basis"] == "total_return"
    # A tested range is an answer too, and carries the same label.
    assert evaluate(_good_result(), GOOD_HOLDOUT, ENTRY20_SWEEP,
                    walkforward=GOOD_WALKFORWARD
                    )["checks"]["breakeven_basis"] == "total_return"
    # And it is NOT invented where nothing was measured. Labelling the scale of
    # a measurement that never happened decorates an absence, which is the
    # habit this criterion exists to break.
    bare = evaluate(_good_result(), GOOD_HOLDOUT, None,
                    walkforward=GOOD_WALKFORWARD)
    assert "breakeven_basis" not in bare["checks"]
    unswept = evaluate(_good_result(), GOOD_HOLDOUT,
                       {"breakeven_cost": {"breakeven_bps": None,
                                           "reason": "no cost sweep was run"}},
                       walkforward=GOOD_WALKFORWARD)
    assert "breakeven_basis" not in unswept["checks"]


def test_an_unestimated_capacity_fails():
    """The same inverted criterion in a second place: an unmeasured capacity is
    not an adequate capacity, and a strategy whose ceiling nobody knows cannot
    be sized."""
    r = _good_result()
    r["capacity"] = {}
    out = evaluate(r, GOOD_HOLDOUT, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is False
    assert any("never estimated" in f for f in out["failures"]), out["failures"]


def test_a_missing_walkforward_fails():
    """One holdout is one draw. This is the criterion that replaces raising the
    PSR floor, because luck scales with dispersion and a threshold race against
    it cannot be won."""
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP)
    assert out["passed"] is False
    assert any("no walk-forward" in f for f in out["failures"]), out["failures"]


def test_inconsistent_retention_across_folds_fails():
    """What a lucky window looks like from the inside: it works once."""
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward={"folds_measurable": 4, "folds_retained": 1,
                                "median_retention": 0.1})
    assert out["passed"] is False
    assert any("only 1 of 4" in f for f in out["failures"]), out["failures"]


def test_too_few_measurable_folds_is_not_the_same_as_failing_them():
    """A consistency test that did not run has not been passed. Saying "failed"
    here would report an absence of evidence as evidence."""
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward={"folds_measurable": 1, "folds_retained": 1,
                                "median_retention": 0.9})
    assert out["passed"] is False
    assert any("did not run" in f for f in out["failures"]), out["failures"]


def test_the_version_records_which_bar_was_applied():
    """A candidate approved under v1 has not been approved under v2, and a stored
    verdict has to say which one it cleared — otherwise re-reading old passes
    under today's criteria silently rewrites history."""
    from app.fund.gate import CRITERIA_V1, GATE_VERSION
    # v4.2 (2026-08-22) moved NO threshold and changed which candidates pass:
    # the `min_breakeven_bps` floor became reachable, and Entry 20's evidence
    # no longer clears it. Two different bars must never share one name, so the
    # version moves even though `CRITERIA` is byte-identical to v4.1's.
    assert GATE_VERSION == "v4.2"
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward=GOOD_WALKFORWARD)
    assert out["gate_version"] == "v4.2"
    # v1 is kept intact so an old verdict remains interpretable.
    assert CRITERIA_V1["min_psr_pct"] == 50.0
    # v1 must state what it did NOT require, not merely omit it: `evaluate`
    # merges a criteria dict over the current defaults, so an omitted key would
    # inherit v2's demand and make a v1 re-judgement impossible.
    assert CRITERIA_V1["require_walkforward"] is False


def test_v1_criteria_still_pass_a_v1_candidate():
    """Judging an old candidate against the old bar must still work — the point
    of versioning is that history is not rewritten."""
    from app.fund.gate import CRITERIA_V1
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   criteria=CRITERIA_V1)
    assert out["passed"] is True, out["failures"]


def test_a_silent_signal_is_not_reported_as_missing_warm_up():
    """Measured on the real book: the INTC mean-reversion traded in-sample, then
    placed zero orders across 226 fully warmed-up 2026 sessions because its RSI
    never crossed the entry threshold. The old message told us to add warm-up it
    already had, which sends the reader to fix the wrong thing.

    The distinction is decision-relevant, not cosmetic: a rule that does not act
    is not managing the position it is credited with — the position is an inert
    static long wearing a strategy's name."""
    ho = {"state": "done", "dates_honoured": True,
          "train": {"return_pct": 64.56},
          "test": {"return_pct": 0.0, "total_orders": 0}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    joined = " ".join(out["failures"])
    assert "never met its own entry condition" in joined
    assert "not managing the position" in joined
    assert "warm-up" not in joined.replace("about warm-up", "")


def test_a_strategy_silent_in_BOTH_legs_still_points_at_warm_up():
    """When neither leg traded, starvation really is the likely cause and the
    message must still say so — the fix must not overcorrect into never
    mentioning it."""
    ho = {"state": "done", "dates_honoured": True,
          "train": {"return_pct": None},
          "test": {"return_pct": 0.0, "total_orders": 0}}
    out = evaluate(_good_result(), ho, GOOD_SWEEP, walkforward=GOOD_WALKFORWARD)
    joined = " ".join(out["failures"])
    assert "never warmed up" in joined


# --- v3: untestable is not the same as failed --------------------------------

def test_a_strategy_too_slow_for_our_history_is_untestable_not_failed():
    """An oracle with perfect foreknowledge failed v2 because a 91-day test leg
    gave its 63-day hold ONE rebalance. Measured against ~30 months of history, a
    5-day hold supports 6 folds and a 63-day hold supports one — so the same fold
    geometry is generous for a fast rule and meaningless for a slow one.

    Marking the slow one FAILED would repeat the error this gate spent a week
    removing: reading an absence of evidence as evidence."""
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward={"not_testable": True,
                                "note": "a 63-day hold needs a 252-day test leg",
                                "folds_measurable": 0, "folds_retained": 0})
    assert out["passed"] is False
    assert out["checks"]["not_testable"] is True
    joined = " ".join(out["failures"])
    assert "NOT TESTABLE" in joined
    assert "not a judgement about the strategy" in joined
    # And it must NOT be described as having lost or failed a consistency test.
    assert "consistent with a lucky window" not in joined


def test_v3_was_a_loosening_and_v4_reverses_it():
    """These two tests previously asserted the BUG.

    v3 dropped the fold requirement to 2 and left the retained share at 0.5
    compared with `<`, so 1 of 2 folds passed — and 1 of 2 is not a majority. The
    tests here asserted that as correct behaviour, which is why the suite stayed
    green through a regression: a test can only catch what it was not written to
    bless.

    v4 requires 4 folds and a strict majority. Both prior versions are preserved
    whole so old verdicts remain readable against the bar they actually cleared.
    """
    from app.fund.gate import CRITERIA, CRITERIA_V2, CRITERIA_V3
    assert CRITERIA["min_walkforward_folds"] == 4
    assert CRITERIA_V3["min_walkforward_folds"] == 2, "v3 must stay readable as it was"
    assert CRITERIA_V2["min_walkforward_folds"] == 3, "v2 must stay readable as it was"
    # Kept COMPLETE, not partial: evaluate() MERGES a supplied dict over current
    # defaults, so a partial historical copy would silently inherit v4 values.
    assert set(CRITERIA_V3) == set(CRITERIA)


def test_one_retained_fold_of_two_is_not_a_majority():
    """The exact regression. 1 of 2 passed under v3."""
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward={"folds_measurable": 2, "folds_retained": 1,
                                "median_retention": 0.8})
    assert out["passed"] is False


def test_two_of_two_no_longer_suffices_because_two_folds_is_not_a_test():
    """Not a majority failure — an insufficient-evidence failure.

    2 of 2 IS a strict majority, so this must be rejected for the other reason:
    two folds cannot discriminate. The distinction matters because the two
    failures call for different responses — a faster rule or more history, versus
    a better strategy.
    """
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward={"folds_measurable": 2, "folds_retained": 2,
                                "median_retention": 0.8})
    assert out["passed"] is False
    joined = " ".join(out["failures"])
    assert "below the 4 required" in joined
    assert "not a majority" not in joined


def test_the_majority_rule_is_integer_arithmetic_not_a_float_share():
    """A float share compared with `<` is how the off-by-one got in.

    `retained * 2 <= measurable` fails 1/2, 2/4 and 2/5; passes 2/2, 3/4, 3/5.
    Checked at 4 measurable folds, where v4 has enough evidence to judge.
    """
    def fold_rejected(measurable, retained):
        out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                       walkforward={"folds_measurable": measurable,
                                    "folds_retained": retained,
                                    "median_retention": 0.8})
        return any("not a majority" in f for f in out["failures"])

    assert fold_rejected(4, 2) is True      # exactly half is NOT a majority
    assert fold_rejected(4, 3) is False
    assert fold_rejected(4, 4) is False
    assert fold_rejected(5, 2) is True
    assert fold_rejected(5, 3) is False
