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
    assert out["gate_version"] == "v4"
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


def test_profitable_beyond_the_tested_range_is_not_treated_as_unmeasured():
    """"Still profitable at every cost tested" IS an answer. Failing it would
    punish the most robust possible result for not having a crossing point."""
    out = evaluate(_good_result(), GOOD_HOLDOUT,
                   {"breakeven_cost": {
                       "breakeven_bps": None,
                       "reason": "still profitable at every cost tested — raise "
                                 "the range to find the limit"}},
                   walkforward=GOOD_WALKFORWARD)
    assert out["passed"] is True, out["failures"]
    assert out["checks"]["breakeven_bps"] == "beyond the tested range"


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
    assert GATE_VERSION == "v4"
    out = evaluate(_good_result(), GOOD_HOLDOUT, GOOD_SWEEP,
                   walkforward=GOOD_WALKFORWARD)
    assert out["gate_version"] == "v4"
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
