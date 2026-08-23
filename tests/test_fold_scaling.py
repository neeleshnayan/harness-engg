"""The fold floor is a DENSITY, not a constant — gate v4.3, item (a) of 58c4fff5.

THE DEFECT THIS FILE GUARDS, registered as BLOCKING since 2026-08-18
(``judgement.py``, ``min_walkforward_folds``, verbatim): "this is a FIXED floor
while the number of available folds grows with history, so a null can end up
with a handful of measurable folds and win a majority of that small subset.
Simulated false-positive rate rises 2.9% -> 12.5% between 30 months and 5 years
of data. It must be made to scale BEFORE any new history is trusted, or a data
purchase loosens the gate silently."

MEASURED 2026-08-23, on the fund's own SPY calendar, driving the real
``retention()`` over the real fold plans, 3,000 draws per arm at a 21-day hold:

    arm                              folds  need    FP     power@Sharpe 1.0
    today, floor 2024-02-26            4      4    3.03%        21.8%
    floor 1993-01-29, fixed 4          5      4    5.80%        35.3%
    floor 1993-01-29, scaled           5      5    4.17%        29.6%
    5y all-history, fixed 4           12      4   11.30%        50.9%
    5y all-history, scaled            12      9    2.90%        40.7%

Both registered figures reproduce, and the floor flip ALONE is a loosening even
under the shipped fold generator — which the register did not measure.

THE ACCEPTANCE TEST, and it is the first one below: at the 30-month window this
fund actually holds, the scaled requirement must equal the constant it replaced
for EVERY hold the generator produces, and the failure sentence must be byte
identical. A gate that judges yesterday's candidates differently has not been
made stricter, it has been made different.
"""

from __future__ import annotations

import pytest

from app.fund.gate import CRITERIA, GATE_VERSION, covered_window, evaluate, folds_required
from app.fund.walkforward import (cal_days, decisions_per_test_leg, folds,
                                  span_for_folds, window_for_strategy)

END = "2026-08-04"
CURRENT_FLOOR = "2024-02-26"
FEED_FLOOR = "1993-01-29"
HOLDS = (1, 2, 3, 5, 10, 21, 42, 63)


def _plan(hold, floor, min_folds=None):
    return window_for_strategy(
        END, hold, min_folds=min_folds or CRITERIA["min_walkforward_folds"],
        floor=floor)


def _wf(plan):
    return {"requested_folds": plan["folds"]}


# --- THE ACCEPTANCE TEST ----------------------------------------------------


@pytest.mark.parametrize("hold", HOLDS)
def test_the_thirty_month_window_is_judged_exactly_as_before(hold):
    """Byte-identical CRITERIA semantics on the window this fund holds."""
    need = folds_required(_wf(_plan(hold, CURRENT_FLOOR)))
    assert need["required"] == CRITERIA["min_walkforward_folds"], (
        f"a {hold}-day hold is judged against {need['required']} folds where "
        f"the constant asked for {CRITERIA['min_walkforward_folds']}")
    assert need["scaled"] is False


def test_the_failure_sentence_is_byte_identical_on_the_current_window():
    """The stored text of a verdict is part of the bar. Frozen literal."""
    plan = _plan(21, CURRENT_FLOOR)
    out = evaluate({}, walkforward={"folds_measurable": 3, "folds_retained": 3,
                                    **_wf(plan)})
    starved = [f for f in out["failures"] if "could be measured" in f]
    assert starved == [
        "only 3 fold(s) could be measured, below the 4 required — the "
        "consistency test did not run, which is not the same as passing it"]


def test_a_thirty_month_candidate_that_passed_still_passes():
    """End to end, with the whole bar, not just the fold leg."""
    plan = _plan(21, CURRENT_FLOOR)
    result = {"total_return_pct": 20.0, "benchmark_return_pct": 10.0,
              "capacity": {"capacity_usd": 5_000_000.0},
              "robustness": {"total_orders": 40, "psr_pct": 80.0,
                             "costs": {"slippage_modelled": True}}}
    out = evaluate(result,
                   {"state": "done", "dates_honoured": True,
                    "train": {"return_pct": 20.0}, "test": {"return_pct": 16.0}},
                   {"breakeven_cost": {"breakeven_bps": 25.0}},
                   walkforward={"folds_attempted": 4, "folds_measurable": 4,
                                "folds_retained": 3, "median_retention": 0.72,
                                **_wf(plan)})
    assert out["passed"] is True, out["failures"]
    assert out["gate_version"] == GATE_VERSION


# --- the scaling actually bites --------------------------------------------


def test_a_longer_covered_window_demands_proportionally_more_folds():
    """The five-year arm of the measured table: 12 folds planned, 9 required."""
    # A plan spanning train + 12 non-overlapping test legs, laid down exactly
    # the way folds() does, so the span is the generator's and not a guess.
    from datetime import date, timedelta
    test_cal, train_cal = cal_days(84), cal_days(252)
    start = date.fromisoformat("2021-08-04")
    twelve = []
    for i in range(12):
        ts = start + timedelta(days=i * test_cal)
        te = ts + timedelta(days=train_cal)
        twelve.append({"train_start": ts.isoformat(), "train_end": te.isoformat(),
                       "test_start": (te + timedelta(days=1)).isoformat(),
                       "test_end": (te + timedelta(days=1 + test_cal)).isoformat()})
    need = folds_required({"requested_folds": twelve})
    assert need["scaled"] is True
    assert need["required"] == 9, need
    assert need["folds_planned"] == 12


def test_the_starved_sentence_names_the_density_when_it_scaled():
    """A candidate must be able to see WHY the bar moved for it."""
    plan = _plan(21, FEED_FLOOR)
    need = folds_required(_wf(plan))
    assert need["required"] == 5, need
    out = evaluate({}, walkforward={"folds_measurable": 4, "folds_retained": 4,
                                    **_wf(plan)})
    starved = [f for f in out["failures"] if "could be measured" in f][0]
    assert "below the 5 required" in starved
    assert f"{need['anchor_folds']} folds per {need['anchor_span_days']} days" in starved


def test_four_measurable_folds_pass_the_old_bar_and_fail_the_scaled_one():
    """The loosening, closed. Same evidence, two windows, two verdicts.

    Four measurable folds with a 3-of-4 majority is a PASS on the 30-month
    window and must be a STARVED verdict on the window the deeper floor opens,
    because the deeper window handed the candidate five independent chances.
    """
    ev = {"folds_attempted": 5, "folds_measurable": 4, "folds_retained": 3,
          "median_retention": 0.72}
    short = evaluate({}, walkforward={**ev, **_wf(_plan(21, CURRENT_FLOOR))})
    deep = evaluate({}, walkforward={**ev, **_wf(_plan(21, FEED_FLOOR))})
    assert not any("could be measured" in f for f in short["failures"])
    assert any("could be measured" in f for f in deep["failures"]), deep["failures"]


# --- the anchor is READ, not copied ----------------------------------------


def test_the_anchor_is_read_from_the_criteria_not_hardcoded():
    """MOVE the criterion and the requirement must move with it.

    Asserting ``required == CRITERIA[...]`` cannot tell a read from a hardcoded
    duplicate that happens to agree today, so the criterion is overridden with
    a value the code has never seen.
    """
    plan = _plan(21, CURRENT_FLOOR)
    assert folds_required(_wf(plan), {"min_walkforward_folds": 3})["required"] == 3
    assert folds_required(_wf(plan), {"min_walkforward_folds": 7})["required"] == 7
    # And the SCALED value follows the anchor too, not just the floor: at seven
    # folds per anchor span the same covered window is a smaller multiple.
    deep = _wf(_plan(21, FEED_FLOOR))
    assert folds_required(deep, {"min_walkforward_folds": 4})["required"] == 5
    assert folds_required(deep, {"min_walkforward_folds": 3})["required"] == 4


def test_a_bar_that_asks_for_no_folds_is_not_scaled_into_asking_for_some():
    """CRITERIA_V1 sets this to 0. Scaling zero must stay zero."""
    need = folds_required(_wf(_plan(21, FEED_FLOOR)), {"min_walkforward_folds": 0})
    assert need["required"] == 0
    assert need["scaled"] is False


# --- absence -----------------------------------------------------------------


@pytest.mark.parametrize("wf", [
    {},
    {"folds_measurable": 4},
    {"requested_folds": []},
    {"requested_folds": [{"train_start": "not-a-date", "test_end": "nope"}]},
    {"requested_folds": [{"test_end": "2026-01-01"}]},
])
def test_an_unreadable_plan_falls_back_to_the_anchor_and_says_so(wf):
    """Unreadable is not a short window. It is unreadable, and it is stated."""
    need = folds_required(wf)
    assert need["required"] == CRITERIA["min_walkforward_folds"]
    assert need["covered_days"] is None
    assert need["basis"] == "anchor (covered window unreadable)"
    assert need["reason"]


def test_the_covered_window_prefers_the_plan_over_the_engines_own_rows():
    """The denominator is how many chances were GIVEN, not how many ran."""
    planned = _plan(21, FEED_FLOOR)["folds"]
    ran = planned[:2]
    win = covered_window({"requested_folds": planned, "folds": ran})
    assert win["folds_planned"] == len(planned) > len(ran)


# --- the closed form matches the generator ----------------------------------


@pytest.mark.parametrize("hold", HOLDS)
@pytest.mark.parametrize("floor", [CURRENT_FLOOR, FEED_FLOOR])
def test_span_for_folds_predicts_what_the_generator_lays_down(hold, floor):
    """Two expressions of one law is how the law stops holding.

    ``folds_required`` scales against a span computed in closed form; the belt
    plans with the generator. If the two ever disagree the requirement is being
    compared against a window that was never laid down.
    """
    from datetime import date
    plan = _plan(hold, floor)
    got = plan["folds"]
    if not got:
        pytest.skip("no folds fit")
    span = (date.fromisoformat(got[-1]["test_end"])
            - date.fromisoformat(got[0]["train_start"])).days
    assert span == span_for_folds(len(got), plan["test_days"]), (
        f"hold={hold} floor={floor}: generator laid down {span} days, the "
        f"closed form predicts {span_for_folds(len(got), plan['test_days'])}")


def test_span_for_folds_uses_the_same_conversion_as_the_generator():
    """MUTATION TARGET: a different 252/365 rounding here would drift silently."""
    got = folds("2020-01-01", "2026-01-01", train_days=252, test_days=84,
                max_folds=3)
    from datetime import date
    span = (date.fromisoformat(got[-1]["test_end"])
            - date.fromisoformat(got[0]["train_start"])).days
    assert span == span_for_folds(3, 84, 252)
    assert cal_days(252) == 365


# --- the decisions criterion is now the one in force ------------------------


def test_the_test_leg_is_sized_by_the_criterion_not_a_module_constant():
    """MOVE it. Until 2026-08-23 the geometry read a module constant and
    ``CRITERIA["min_decisions_per_test_leg"]`` had ZERO consumers in the repo —
    a declared criterion that decided nothing."""
    assert decisions_per_test_leg() == CRITERIA["min_decisions_per_test_leg"]
    assert decisions_per_test_leg({"min_decisions_per_test_leg": 6}) == 6
    plan = window_for_strategy(END, 21, min_folds=4, floor=CURRENT_FLOOR,
                               criteria={"min_decisions_per_test_leg": 6})
    assert plan["test_days"] == 21 * 6
    assert "to make 6 decisions" in plan["note"]


def test_a_bar_with_no_decision_requirement_gets_the_pre_v3_leg():
    """CRITERIA_V1 and V2 set this to 0 — meaning 'this bar had no such
    concept', NOT 'a one-day test leg'. Re-judging under them must not collapse
    every test window to a single session."""
    plan = window_for_strategy(END, 21, min_folds=2, floor=CURRENT_FLOOR,
                               criteria={"min_decisions_per_test_leg": 0})
    assert plan["test_days"] == 63
    assert plan["decisions_per_test_leg"] == 0
