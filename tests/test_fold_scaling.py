"""The fold floor is a DENSITY, not a constant — gate v4.3, item (a) of 58c4fff5.

THE DEFECT THIS FILE GUARDS, registered as BLOCKING since 2026-08-18
(``judgement.py``, ``min_walkforward_folds``, verbatim): "this is a FIXED floor
while the number of available folds grows with history, so a null can end up
with a handful of measurable folds and win a majority of that small subset.
Simulated false-positive rate rises 2.9% -> 12.5% between 30 months and 5 years
of data. It must be made to scale BEFORE any new history is trusted, or a data
purchase loosens the gate silently."

THE MEASURED TABLE IS NOT HERE. It lives once, in ``gate.py`` beside
``GATE_VERSION``, and this file used to carry a THIRD copy of it — a RETRACTED
copy, describing a five-fold arm the shipped code never produced, which survived
D19's own read-through and was found by the adversary. When a number propagates,
grep the NUMBER.

THE ACCEPTANCE TEST, and it is the first one below: at the 30-month window this
fund actually holds, the scaled requirement must equal the constant it replaced
for EVERY hold the generator produces, and the failure sentence must be byte
identical. A gate that judges yesterday's candidates differently has not been
made stricter, it has been made different.

D20 MADE THAT CLAIM TRUE RATHER THAN NEARLY TRUE. D19 asserted it and
parametrized EIGHT holds of an unbounded integer domain; widening the same test
to ``range(1,70)`` broke it on holds 16, 17 and 18 in 0.21 seconds, because the
anchor span was "what four folds occupy" and any hold whose 30-month window
fitted five folds priced at exactly 4.5 and rounded up. The anchor is now the
window the PRE-v4.3 floor actually supplied, so the ratio is exactly 1 whenever
the plan is the pre-v4.3 plan — identity by construction. The enumeration below
runs ``range(1,200)`` anyway: a claim of universality should cost a test that
can fail, and this one costs 0.2 seconds.
"""

from __future__ import annotations

import pytest

from app.fund.gate import CRITERIA, GATE_VERSION, covered_window, evaluate, folds_required
from app.fund.walkforward import (HISTORY_FLOOR_RATCHET, MAX_WALKFORWARD_FOLDS,
                                  V42_MAX_FOLDS, cal_days,
                                  decisions_per_test_leg, folds,
                                  span_for_folds, window_for, window_for_strategy)

END = "2026-08-04"
CURRENT_FLOOR = "2024-02-26"
FEED_FLOOR = "1993-01-29"
HOLDS = (1, 2, 3, 5, 10, 21, 42, 63)
#: The generator's hold domain is any positive integer. 200 is cheap (the whole
#: parametrization runs in under a second) and it is the difference between a
#: claim about every hold and a claim about the eight someone chose.
WIDE_HOLDS = tuple(range(1, 200))


def _plan(hold, floor, min_folds=None):
    return window_for_strategy(
        END, hold, min_folds=min_folds or CRITERIA["min_walkforward_folds"],
        floor=floor)


def _wf(plan):
    return {"requested_folds": plan["folds"]}


# --- THE ACCEPTANCE TEST ----------------------------------------------------


@pytest.mark.parametrize("hold", WIDE_HOLDS)
def test_the_thirty_month_window_is_judged_exactly_as_before(hold):
    """Byte-identical CRITERIA semantics on the window this fund holds.

    THE INCIDENT THIS GUARDS (adversary blind review of D19, 2026-08-23): the
    same claim was made for "every hold the generator produces" against a
    parametrization of eight. Holds 16, 17 and 18 required five folds where
    v4.2 required four. The domain is a positive integer, so the domain is what
    gets enumerated.
    """
    need = folds_required(_wf(_plan(hold, CURRENT_FLOOR)))
    assert need["required"] == CRITERIA["min_walkforward_folds"], (
        f"a {hold}-day hold is judged against {need['required']} folds where "
        f"the constant asked for {CRITERIA['min_walkforward_folds']} "
        f"(plan: {need.get('folds_planned')} folds over "
        f"{need.get('covered_days')} days against an anchor window of "
        f"{need.get('anchor_span_days')})")
    assert need["scaled"] is False


@pytest.mark.parametrize("hold", WIDE_HOLDS)
def test_the_thirty_month_PLAN_is_the_v42_plan_fold_for_fold(hold):
    """Identity of the REQUIREMENT is half of identity. The plan must match too.

    A candidate judged over different folds has been judged differently even if
    the number of folds it must win is the same. v4.2's planner is restated here
    deliberately — a TEST may hold the second copy of a law it guards; the
    production code may not, which is why ``window_for`` has only one.

    Cross-checked against the real v4.2 tree (536b427) rather than only against
    this restatement: ``scratchpad/d20_plans.py`` dumped both trees' plans for 73
    holds at this floor and the JSON was equal, folds, ``need``, ``test_days``
    and ``enough``.
    """
    from datetime import date, timedelta
    decisions = decisions_per_test_leg()
    test_days = max(1, hold * decisions)
    anchor = int(CRITERIA["min_walkforward_folds"])
    reach = cal_days(252 + test_days * (anchor + 1))
    start = max(date.fromisoformat(END) - timedelta(days=reach),
                date.fromisoformat(CURRENT_FLOOR))
    v42 = folds(start.isoformat(), END, train_days=252, test_days=test_days,
                max_folds=max(anchor, V42_MAX_FOLDS))
    assert _plan(hold, CURRENT_FLOOR)["folds"] == v42


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
    # v4.4: the luck filter reads the run's own observations, so the fixture
    # carries a series measuring the 80% its `psr_pct` claims.
    from premia_feed import daily_returns_block, series_with_psr
    result = {"total_return_pct": 20.0, "benchmark_return_pct": 10.0,
              "capacity": {"capacity_usd": 5_000_000.0},
              "daily_returns": daily_returns_block(series_with_psr(80.0)),
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
    assert need["required"] == 9, need
    out = evaluate({}, walkforward={"folds_measurable": 8, "folds_retained": 8,
                                    **_wf(plan)})
    starved = [f for f in out["failures"] if "could be measured" in f][0]
    assert "below the 9 required" in starved
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
    # And the SCALED value follows the anchor too, not just the floor: at three
    # folds per anchor span the same covered window is a smaller multiple.
    deep = _wf(_plan(21, FEED_FLOOR))
    assert folds_required(deep, {"min_walkforward_folds": 4})["required"] == 9
    assert folds_required(deep, {"min_walkforward_folds": 3})["required"] == 6


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


# --- D20: the plan REACHES, and only where the data got deeper ---------------


@pytest.mark.parametrize("hold", WIDE_HOLDS)
def test_the_extension_never_shortens_a_window_it_used_to_produce(hold):
    """The whole acceptance argument rests on this being structural.

    Deeper is the only direction the D20 reach can move a window. If any floor
    could make the plan SHALLOWER than v4.2's, the false-pass table would have
    to be re-measured for that case — and nobody would know to.
    """
    from datetime import date
    for floor in (CURRENT_FLOOR, FEED_FLOOR, "2021-03-02", "2010-06-30"):
        got = window_for_strategy(END, hold, min_folds=4, floor=floor)["folds"]
        base = _plan(hold, CURRENT_FLOOR)["folds"]
        if not got or not base:
            continue
        assert (date.fromisoformat(got[0]["train_start"])
                <= date.fromisoformat(base[0]["train_start"])), (
            f"hold={hold} floor={floor} starts LATER than the 30-month plan")
        assert len(got) >= len(base)


def test_the_extension_does_not_fire_at_or_above_the_ratchet():
    """A floor no deeper than the pre-v4.3 one buys nothing, by construction."""
    at = window_for(END, 4, test_days=84, floor=HISTORY_FLOOR_RATCHET)
    above = window_for(END, 4, test_days=84, floor="2025-01-01")
    assert len(at) == 4
    assert len(at) <= V42_MAX_FOLDS and len(above) <= V42_MAX_FOLDS
    deeper = window_for(END, 4, test_days=84, floor="2021-03-02")
    assert len(deeper) == MAX_WALKFORWARD_FOLDS


def test_the_deep_plan_ends_flush_with_the_holdout():
    """The extension tests the RECENT window, not an archaeological one.

    Anchoring the deepened window at its start would have laid twelve folds
    across 2021-2024 and left the last two years untested — more folds and less
    relevance.
    """
    deep = window_for(END, 4, test_days=84, floor="2021-03-02")
    assert deep[-1]["test_end"] == END


def test_the_fold_cap_and_the_ratchet_are_READ_not_copied(monkeypatch):
    """MOVE both. An assertion that the plan matches the constant cannot tell a
    read from a duplicate that happens to agree today (D16's lesson, twice)."""
    import app.fund.walkforward as wf
    monkeypatch.setattr(wf, "MAX_WALKFORWARD_FOLDS", 7)
    assert len(wf.window_for(END, 4, test_days=84, floor="2021-03-02")) == 7
    # And the ratchet is what decides whether the extension fires at all: move
    # it EARLIER than the deep floor and the same floor stops being "deeper",
    # so the plan falls back to the unextended reach — which is what a plan with
    # no floor at all gets, and is derived here rather than written down.
    monkeypatch.setattr(wf, "HISTORY_FLOOR_RATCHET", "2015-01-01")
    unextended = len(wf.window_for(END, 4, test_days=84, floor=None))
    assert unextended < 7
    assert len(wf.window_for(END, 4, test_days=84,
                             floor="2021-03-02")) == unextended


def test_the_fold_count_term_is_READ_from_v42s_own_ceiling(monkeypatch):
    """MOVE v4.2's planner ceiling and the fold-count term must follow it.

    The term exists because the days term is weak for fast rules: at a 1-day
    hold a fold costs five calendar days against a 365-day train leg, so a
    window barely deeper than the anchor's holds three times the folds while the
    days term barely moves. Measured at the deep floor, zero skill, n=6,000
    paired: without this term a 1-day hold would have planned 12 folds requiring
    4; with it, 12 requiring 8, and the false-pass came in at 12.53% against
    v4.2's 14.87% instead of above it (``scratchpad/d20_fp_holds.py``).
    """
    import app.fund.gate as g
    plan = _plan(21, FEED_FLOOR)
    assert folds_required(_wf(plan))["required_by_folds"] == 8
    monkeypatch.setattr(g, "V42_MAX_FOLDS", 3)
    assert g.folds_required(_wf(plan))["required_by_folds"] == 16


@pytest.mark.parametrize("hold,by_days", [(1, 2), (3, 3), (10, 5)])
def test_the_fold_count_term_DECIDES_the_requirement_for_a_fast_rule(hold, by_days):
    """FOUND BY MUTATION. Deleting the term from the ``max`` left the suite green.

    Every test above pins ``required_by_folds`` or a 21-day hold, where the days
    term is the larger. So the guard could have been computed, reported, and
    never applied — a control with no caller, which is this fund's oldest defect
    shape. A fast rule at the deep floor is where it decides: twelve folds whose
    days term prices at two or three, and the requirement is eight.
    """
    plan = _plan(hold, "2021-03-02")
    need = folds_required(_wf(plan))
    assert len(plan["folds"]) == MAX_WALKFORWARD_FOLDS
    assert need["required_by_days"] == by_days
    assert need["binding_term"] == "folds"
    assert need["required"] == need["required_by_folds"] == 8
    # And the verdict it produces changes with it: eight measurable folds of
    # twelve is not enough evidence under the term, and is under the days term.
    starved = evaluate({}, walkforward={"folds_measurable": 7,
                                        "folds_retained": 7, **_wf(plan)})
    assert any("below the 8 required" in f for f in starved["failures"])


def test_the_fold_count_term_is_non_binding_on_every_plan_v42_could_make():
    """Which is why it does not disturb the identity claim above."""
    for planned in range(1, V42_MAX_FOLDS + 1):
        rows = _plan(21, CURRENT_FLOOR)["folds"][:1] * planned
        got = folds_required({"requested_folds": rows})["required_by_folds"]
        assert got <= CRITERIA["min_walkforward_folds"], (planned, got)


@pytest.mark.parametrize("hold", WIDE_HOLDS)
@pytest.mark.parametrize("floor", [CURRENT_FLOOR, "2021-03-02", FEED_FLOOR])
def test_the_belt_gate_fixed_point_settles(hold, floor):
    """The window sizes the requirement and the requirement sizes the window.

    ``factory._walkforward`` iterates that at most four times and logs a warning
    if it does not settle. A geometry that never settles would ship whatever the
    fourth pass happened to hold, so the domain gets enumerated here too.
    """
    need = int(CRITERIA["min_walkforward_folds"])
    plan = window_for_strategy(END, hold, min_folds=need, floor=floor)
    for _ in range(4):
        req = int(folds_required(_wf(plan))["required"])
        if req <= need:
            break
        need = req
        plan = window_for_strategy(END, hold, min_folds=need, floor=floor)
    else:
        pytest.fail(f"hold={hold} floor={floor} did not settle: need={need}, "
                    f"folds={len(plan['folds'])}")


def test_a_bar_with_no_decision_requirement_gets_the_pre_v3_leg():
    """CRITERIA_V1 and V2 set this to 0 — meaning 'this bar had no such
    concept', NOT 'a one-day test leg'. Re-judging under them must not collapse
    every test window to a single session."""
    plan = window_for_strategy(END, 21, min_folds=2, floor=CURRENT_FLOOR,
                               criteria={"min_decisions_per_test_leg": 0})
    assert plan["test_days"] == 63
    assert plan["decisions_per_test_leg"] == 0
