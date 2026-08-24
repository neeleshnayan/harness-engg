"""The bar a candidate must clear, declared before the result is known.

A signal factory is not a place that produces strategies. It is a place that
KILLS them cheaply, and the only thing that makes that work is deciding what
counts as good before you see the number. Every criterion here is written down,
versioned, and applied identically to every candidate — because the failure
mode of hand-picked research is not bad statistics, it is a person looking at a
result they like and finding a reason the rule should not apply this once.

So the gate returns a list of specific failures rather than a score. A score
invites negotiation ("0.61 is nearly 0.65"); a sentence saying "the edge did
not survive data it was not chosen on" does not.

Nothing here is clever. Every input is already computed elsewhere — costs,
probabilistic Sharpe, the held-out test, capacity, the benchmark. The value is
that they are applied together, automatically, to everything, and that the
threshold was fixed in advance.
"""

from __future__ import annotations

import math
from typing import Any, Optional

# The two window constants the fold-density rule is calibrated on. Imported
# rather than restated: the ratchet date and v4.2's planner ceiling each have
# more than one consumer now, and a criterion that keeps its own copy of a
# number the planner also holds is the two-copies-of-one-belief defect at the
# level of the bar. ``walkforward`` imports this module only from inside
# functions, so this direction is the safe one.
from app.fund.walkforward import HISTORY_FLOOR_RATCHET, V42_MAX_FOLDS


def _window_days(window: Any) -> Optional[int]:
    """Calendar days a leg actually covered, from its [first, last] dates.

    Feeds annualisation in the holdout retention. Returns None rather than
    guessing when the window is absent or malformed — retention() then falls
    back to cumulative returns AND SAYS SO, which is the honest degradation.
    """
    if not window or len(window) < 2:
        return None
    try:
        from datetime import date
        a = date.fromisoformat(str(window[0])[:10])
        b = date.fromisoformat(str(window[1])[:10])
    except ValueError:
        return None
    return (b - a).days or None


def max_tested_bps(tested_range: Any) -> Optional[float]:
    """The widest cost a sweep actually priced, in basis points.

    ``leanrunner.breakeven_cost`` reports ``tested_range`` as the sorted
    [cheapest, dearest] slip values it scored, as FRACTIONS — 0.0005 is 5 bps —
    matching the ``breakeven_bps = crossing * 10_000`` it reports on the
    crossing branch. Verified against the stored sweep of candidate
    144387901688: ``tested_range: [0.0001, 0.0005]`` for a 1/3/5 bps grid.

    PUBLIC, and imported by ``factory.check_cost_grid``, because the belt now
    asks the same question at submission time that the gate asks at judgement
    time. Two copies of that arithmetic is the two-copies-of-one-belief failure
    leanrunner already names about the cost assumption itself.

    Returns None rather than guessing when the range is absent or malformed.
    The caller FAILS on None: a tested range nobody can read is not a cleared
    floor, and absence is never zero.
    """
    if not isinstance(tested_range, (list, tuple)) or not tested_range:
        return None
    try:
        return max(float(v) for v in tested_range) * 10_000.0
    except (TypeError, ValueError):
        return None


def _fold_windows(wf: Any) -> list[dict[str, Any]]:
    """The fold PLAN inside a walk-forward payload, from whichever key holds it.

    The plan is the denominator that matters: it is how many independent
    chances the candidate was given, which is the thing that grows when the
    history floor moves. ``requested_folds`` is preferred over ``folds``
    because it is the plan as declared, before the engine shortened anything.
    """
    if not isinstance(wf, dict):
        return []
    for key in ("requested_folds", "folds"):
        rows = wf.get(key)
        if isinstance(rows, list) and rows:
            ok = [r for r in rows if isinstance(r, dict)
                  and r.get("train_start") and r.get("test_end")]
            if ok:
                return ok
    return []


def covered_window(wf: Any) -> dict[str, Any]:
    """The calendar span a walk-forward plan covered, read from its own folds.

    Read from the EVIDENCE rather than from a field the payload asserts about
    itself: ``test_days`` is a number the belt writes down, and a criterion
    that scales with a self-reported number scales with whatever the submitter
    says. The fold dates are the measurement.

    Returns ``readable: False`` with a reason when the windows are absent or
    malformed. Absence is never zero here either — the caller falls back to the
    unscaled anchor and SAYS it could not read the span, rather than quietly
    treating an unreadable plan as a short one.
    """
    rows = _fold_windows(wf)
    if not rows:
        return {"readable": False, "reason": "no fold windows in the evidence"}
    first, last = rows[0], rows[-1]
    a = _window_days([first.get("train_start"), last.get("test_end")])
    train = _window_days([first.get("train_start"), first.get("train_end")])
    test = _window_days([first.get("test_start"), first.get("test_end")])
    if not a or not train or not test:
        return {"readable": False,
                "reason": "the fold windows could not be parsed as dates"}
    return {"readable": True, "covered_days": a, "train_cal_days": train,
            "test_cal_days": test, "folds_planned": len(rows),
            # The plan's own end date, needed to size the window the PRE-v4.3
            # floor would have supplied for this same candidate. Read from the
            # last fold rather than from any field the payload asserts, for the
            # same reason the span is.
            "last_test_end": str(last.get("test_end"))}


def folds_required(wf: Any, criteria: Optional[dict[str, Any]] = None
                   ) -> dict[str, Any]:
    """How many measurable folds THIS covered window must supply.

    THE DEFECT THIS CLOSES, registered as blocking since 2026-08-18
    (``judgement.py``, ``min_walkforward_folds``): the fold floor is FIXED
    while the folds a window can hold grow with history, so a candidate handed
    more history gets more independent chances and still has to win only four
    of them — and the four it wins are POST-SELECTED, because a fold only
    becomes measurable when its train leg cleared MIN_TRAIN_RETURN_PCT. The
    register's words: "a null can end up with a handful of measurable folds and
    win a majority of that small subset".

    MEASURED — the single table for this criterion lives in the ``GATE_VERSION``
    note below, is labelled with the configurations that actually SHIP, and is
    not repeated here. Two copies of one measurement is how D19 shipped a
    docstring claiming five folds beside one claiming six.

    THE RULE, in two terms, and the requirement is the larger:

        required = max(anchor,
                       round_half_up(anchor * covered_days / anchor_span),
                       ceil(anchor * folds_planned / V42_MAX_FOLDS))

    TERM ONE — DENSITY OVER DAYS. The anchor is whatever
    ``min_walkforward_folds`` currently says, and ``anchor_span`` is the window
    THE PRE-v4.3 FLOOR would have supplied for this same candidate: the folds
    that fit between ``walkforward.HISTORY_FLOOR_RATCHET`` and this plan's own
    last test date, at this strategy's own clock.

    Anchoring on the strategy's clock rather than on the calendar is
    deliberate. A "folds per year" rule is unsatisfiable for a slow rule — a
    63-day hold needs a one-year test leg, so it can never produce 1.6
    independent folds a year — and imposing one would re-introduce the fixed
    calendar window that gate v3 removed for exactly that reason.

    ANCHORING ON THE PRE-v4.3 WINDOW rather than on "the span four folds
    occupy" is the D20 repair, and it is what makes the identity claim TRUE
    rather than nearly true. Under D19 the anchor span was
    ``train + 4*test + 1`` regardless of what the old floor actually supplied,
    so any hold whose 30-month window fitted FIVE folds priced at exactly
    ``4 * 5/4.5 = 4.5`` and rounded UP: holds 16, 17 and 18 required five where
    v4.2 required four. The adversary found it by widening the acceptance
    test's own parametrization to ``range(1,70)``; it failed in 0.21s. Now the
    numerator and the denominator are the same window whenever the plan is the
    pre-v4.3 plan, so the ratio is exactly 1 and the requirement is exactly the
    anchor — for EVERY positive integer hold, by construction rather than by
    enumeration. ``test_fold_scaling`` enumerates ``range(1,200)`` anyway,
    because a claim of universality should cost a test that can fail.

    TERM TWO — DENSITY OVER FOLDS, and it exists because term one is weak for
    fast rules. Folds are cheap in CALENDAR days when the test leg is short: at
    a 1-day hold a fold costs five days against a 365-day train leg, so a
    window barely deeper than the anchor's can hold three times the folds while
    term one barely moves. More chances at an unmoved bar is the exact defect
    this function was written to close, so the requirement also carries the
    LOOSEST fold-count density v4.2 could reach — its planner ceiling of
    ``V42_MAX_FOLDS`` folds against the anchor's four. It is non-binding on
    every plan v4.2's planner could produce — its ceiling was six folds, which
    price at exactly four, and the deepest it was ever measured actually laying
    was five — so it binds only where the D20 extension has bought folds that
    term one does not price.

    NEITHER TERM MOVES A THRESHOLD. ``min_walkforward_folds`` is untouched at
    4; both terms are ``max``-ed against it, so both can only ever ask for MORE
    folds than v4.2 did, never fewer.
    """
    c = {**CRITERIA, **(criteria or {})}
    anchor = int(c.get("min_walkforward_folds") or 0)
    win = covered_window(wf)
    out: dict[str, Any] = {"anchor_folds": anchor, "required": anchor,
                           "scaled": False, "covered_days": None,
                           "anchor_span_days": None,
                           "basis": "anchor (covered window unreadable)"}
    if not win.get("readable"):
        out["reason"] = win.get("reason")
        return out
    covered = int(win["covered_days"])
    planned = int(win["folds_planned"])
    train_cal, test_cal = win["train_cal_days"], win["test_cal_days"]
    # THE ANCHOR SPAN: the window the floor this fund enforced BEFORE v4.3
    # would have supplied for this candidate, in the same calendar units the
    # covered span is measured in and from the same closed form the fold
    # generator obeys — so a rounding artefact in the conversion cannot
    # masquerade as extra history.
    anchor_folds = anchor
    ratchet_days = _window_days([HISTORY_FLOOR_RATCHET, win["last_test_end"]])
    if ratchet_days and test_cal > 0:
        # How many folds fitted between the old floor and this plan's end. At
        # least the anchor: a window too short for four folds does not get a
        # SMALLER denominator (that would scale the requirement UP on a
        # candidate the old floor could barely test at all).
        anchor_folds = max(anchor, (ratchet_days - train_cal - 1) // test_cal)
    anchor_span = train_cal + anchor_folds * test_cal + 1
    out.update({"covered_days": covered, "anchor_span_days": anchor_span,
                "anchor_window_folds": anchor_folds,
                "anchor_window_floor": HISTORY_FLOOR_RATCHET,
                "folds_planned": planned,
                "basis": "scaled to the covered window"})
    if anchor <= 0 or anchor_span <= 0:
        # A bar that asks for no folds is not scaled up into asking for some.
        out["basis"] = "anchor (no fold requirement in force)"
        return out
    # round-half-up in integers. Python's round() is banker's rounding and
    # would send 4.5 down and 5.5 up, which is not a rule anyone can predict
    # from the docstring above.
    by_days = (2 * anchor * covered + anchor_span) // (2 * anchor_span)
    # ceil in integers, for the same reason.
    by_folds = -((-anchor * planned) // max(1, V42_MAX_FOLDS))
    out["required_by_days"] = int(by_days)
    out["required_by_folds"] = int(by_folds)
    out["required"] = max(anchor, int(by_days), int(by_folds))
    out["scaled"] = out["required"] > anchor
    # Which term decided it, named so a candidate can see WHY its bar moved. A
    # TIE is reported as a tie: saying "days" when both terms landed on the
    # same number would let a reader conclude the other one is slack.
    out["binding_term"] = ("anchor" if out["required"] == anchor else
                           "days and folds" if by_days == by_folds else
                           "days" if by_days > by_folds else "folds")
    # The calendar lengths above come from the evidence, so this needs no
    # conversion back to trading days. ``walkforward.span_for_folds`` is the
    # trading-day twin of the same closed form and is what the BELT plans
    # against; a test pins the two agreeing on the shipped geometry, because
    # two expressions of one law is how the law stops holding.
    return out


def fmt_bps(x: float) -> str:
    """A basis-point figure with enough digits to not lie about a comparison.

    The comparison is always made on the raw float and never on this string.
    Measured: a slip of 0.0009996 is 9.996 bps and ``round(x, 1)`` renders it
    "10.0" — which would print a candidate as having tested TO a 10.0 floor it
    did not reach, turning a display convention into a quiet loosening.
    """
    return f"{x:.4f}".rstrip("0").rstrip(".") or "0"


#: Bump when a threshold changes, so a stored verdict says which bar it cleared.
#: A candidate approved under v1 has not been approved under v2.
#:
#: v1 -> v2 (2026-08-17), forced by measurement rather than taste. A null audit
#: ran random-entry strategies — no information in them by construction — down
#: the same belt real candidates use. Under v1 they passed roughly half the time.
#: The specific leaks, all three now closed below:
#:
#:   1. TWO CRITERIA PASSED WHEN UNMEASURED. `min_breakeven_bps` and
#:      `min_capacity_usd` were written `if x is not None and x < floor`, so a
#:      candidate that was never cost-swept satisfied the cost-robustness bar by
#:      never being tested against it. In a gate whose stated doctrine is that
#:      missing evidence fails, that was the doctrine inverted in two places.
#:   2. A 50% PSR FLOOR DOES NOT SEPARATE NOISE at this sample length. Nulls
#:      reached the high fifties; the real candidate scored 26.9%. The floor was
#:      not measuring skill, it was measuring luck plus history length.
#:   3. BEATING THE BENCHMARK ONCE IS A COIN FLIP. A concentrated random draw
#:      from a high-dispersion basket clears a 20-name equal-weight bar about
#:      half the time, and v1 had no notion of significance — only of ordering.
#:
#: The fix deliberately is NOT "raise the number". A higher threshold starts an
#: arms race against luck and loses, because luck scales with dispersion. What
#: noise cannot fake is CONSISTENCY ACROSS INDEPENDENT WINDOWS, so v2 requires a
#: walk-forward result and treats its absence as a failure like any other.
#:
#: MEASURED CORRECTION (2026-08-17, docs/GATE_CALIBRATION_2026-08-18.md section 7):
#: that last sentence is the intent and NOT what mostly happens. Splitting
#: rejections by mode, a null is rejected 89.6% of the time because too few folds
#: were MEASURABLE — its training legs cannot clear MIN_TRAIN_RETURN_PCT — and only
#: 7.1% of the time by actually failing the majority. The consistency test usually
#: never runs. The false-positive rate is real; it is delivered by an EVIDENCE
#: requirement with a persistence test attached, which is a weaker claim than this
#: paragraph makes and is the true one. Kept rather than rewritten because the
#: intent still explains the design.
#:
#: v2 -> v3 (2026-08-18), forced by the other half of the calibration. An oracle
#: with PERFECT FOREKNOWLEDGE failed v2, on two counts that were both ours rather
#: than its:
#:
#:   1. Retention divided a 12-month cumulative return by a 3-month one, so
#:      perfect foresight "kept 3% of its edge". Fixed by annualising both legs.
#:   2. Even annualised it failed, because a 91-day test leg gives a 63-day-hold
#:      strategy ONE rebalance. One decision is not a test of a selection rule.
#:
#: So v3 makes the fold geometry conditional on the strategy's own clock: a test
#: leg must contain about four of its decisions. Measured against our ~30 months,
#: that supports 6 folds for a 5-day hold, 4 for 21 days, and ONE for 63 days.
#: `min_walkforward_folds` therefore drops 3 -> 2, because 3 was unsatisfiable for
#: anything but fast rules and an unsatisfiable criterion fails everything while
#: looking like rigour.
#:
#: And the honest consequence, which is a finding rather than a threshold: a
#: strategy too slow for the available history is NOT TESTABLE, and v3 reports
#: that separately from failing. Marking it failed would repeat the exact error
#: this gate spent a week removing — reading an absence of evidence as evidence.
#:
#: v3 -> v4 (2026-08-18). **v3 was a LOOSENING, and it was not noticed at the
#: time.** It was written and committed with a message about rigour. An outside
#: review found it; the arithmetic below is why it was wrong.
#:
#: Dropping `min_walkforward_folds` 3 -> 2 while leaving the retained share at
#: 0.5, compared with `<`, meant a strategy passed by keeping its edge in **1 of
#: 2** folds. One of two is not a majority, and the comment directly above the
#: criterion claimed it was. Worse than loose, it was close to uninformative —
#: P(pass) for the walk-forward leg alone, by rule:
#:
#:     rule       noise p=.5   edge p=.7   strong p=.85   discrimination
#:     1 of 2          75.0%       91.0%          97.7%       1.21   <- v3
#:     2 of 2          25.0%       49.0%          72.2%       1.96
#:     3 of 4          31.2%       65.2%          89.0%       2.09   <- v4
#:     4 of 4           6.2%       24.0%          52.2%       3.84
#:
#: v3's discrimination ratio of 1.21 means the test barely told a real edge from
#: noise. Gate v1's measured failure — passing nulls ~50% of the time — is what
#: started this whole calibration, and v3 was plausibly WORSE than v1 on the
#: criterion that had replaced PSR as the load-bearing one. It was also the sole
#: birth condition for the unfunded alpha sleeve.
#:
#: The fix is not a threshold tweak, because the fold count and the majority rule
#: have to be chosen together. `4 of 4` discriminates best but passes a genuine
#: p=0.7 edge only 24% of the time — a gate that can only ever say no, which
#: would make the declared-beta sleeve the terminal state of the design rather
#: than a stepping stone. `3 of 4` is the balance our history actually supports:
#: the fold geometry from v3 gives 4 folds at a 21-day hold.
#:
#: So v4 sets `min_walkforward_folds` to 4 and requires a STRICT majority, in
#: integer arithmetic (`retained * 2 <= measurable` fails), so the off-by-one
#: cannot recur. The honest cost: holds of 42 days or more now return NOT
#: TESTABLE, because 30 months cannot supply 4 folds for them. That is the true
#: state of our evidence rather than a verdict about those strategies.
#:
#: Two things this did NOT do when v4 shipped. Both are now done, and the results
#: are recorded here rather than left as open TODOs that quietly become folklore:
#:
#:   * The real false-positive rate. `scripts/null_audit.py` DOES send every
#:     candidate through the walk-forward leg — the factory always ran it — but the
#:     script never recorded the outcome, and had not been re-run since the leg
#:     existed. It records it now. A live v4 run is in flight.
#:   * POWER against a plausible edge, which had never been measured at all.
#:     Simulated at 4,000 draws per level: 2.9% false positives, and only 22.8%
#:     power at Sharpe 1.0, with 80% power unreachable at any Sharpe on ~30 months
#:     of history. See docs/GATE_CALIBRATION_2026-08-18.md.
#:
#: v4.1 (2026-08-20, written reason): the single-window holdout retention was a
#: raw `te / tr` guarded only by `if tr` — so a NEGATIVE train leg inverted the
#: sign (train −10% / test −8% passed as "kept 80% of its edge") and a near-zero
#: positive one exploded the ratio (a real fold: train +0.03% → ratio 231). The
#: walk-forward leg had carried the full discipline — strict-positive guard,
#: MIN_TRAIN_RETURN_PCT floor, annualisation — since it shipped; the holdout leg
#: was simply never given it. Found by the validator's first real-belt execution
#: of the floor register's falsifier (docs/MIN_TRAIN_RETURN_REVIEW_2026-08-20.md),
#: latent on every verdict issued to date (all five negative-retention candidates
#: failed the criterion anyway). The holdout leg now calls the SAME
#: walkforward.retention() the folds use. No threshold moved.
#:
#: v4.1 -> v4.2 (2026-08-22, written reason). NO THRESHOLD MOVED — this makes an
#: existing floor REACHABLE, it does not make it different. `min_breakeven_bps`
#: stays 10.0.
#:
#: The cost-robustness criterion was unevaluable on the branch that every
#: candidate surviving its whole cost grid takes, and the first candidate ever
#: to survive one took it immediately. Measured on candidate `144387901688`
#: (announcement_premium, "Entry 20", the fund's first substantive pass —
#: docs/quant/QUANT_ENTRY20_2026-08-22.md): the grid was slip 1/3/5 bps, all
#: three points stayed profitable, so the sweep reported no crossing. This
#: branch then wrote the string "beyond the tested range" into `checks` and
#: appended NO failure. A 10.0 bps floor was certified on evidence that
#: establishes 5.0 — a register reading an absence as a pass, which is the one
#: pattern the non-negotiables forbid, sitting in the fund's own gate.
#:
#: The v2 comment this branch carries was right about the case it was written
#: for — a candidate never cost-swept — and wrong about the case it produces.
#: "Still profitable at every cost tested" is not an answer. It is an answer
#: BOUNDED BY THE GRID THE SUBMITTER CHOSE, and the submitter chose a grid that
#: stopped at half the floor.
#:
#: So v4.2 compares the sweep's MAXIMUM TESTED slip against the floor:
#:
#:   * tested past the floor and still profitable -> a genuine pass, and the
#:     figure is recorded in `checks["breakeven_max_tested_bps"]` so the
#:     evidence is visible rather than implied;
#:   * tested short of the floor -> a failure naming both numbers;
#:   * tested range unreadable -> a failure, because a range nobody can read is
#:     not a cleared floor.
#:
#: The submission-side half is `factory.check_cost_grid`, so a grid too narrow
#: to answer the question is refused BEFORE it spends the 96 minutes of
#: containers Entry 20 spent proving it.
#:
#: WHAT v4.2 DOES NOT FIX, stated so the pass is not over-read. This floor
#: judges a breakeven computed on TOTAL return. For an ALPHA claim the
#: fragility that matters is where ACTIVE return — strategy minus benchmark —
#: crosses zero, and on Entry 20 those two numbers are 64.6 and 13.9 bps/side,
#: 4.6x apart. The belt cannot currently produce the active number: sweep
#: points run `enrich=False` (leanrunner.py:808) so they carry no benchmark at
#: all, and the only benchmark the candidate owns was measured over a DIFFERENT
#: WINDOW than the sweep ran (verified on 144387901688: points cover the train
#: leg 2024-02-26..2025-08-21, the benchmark covers 2024-02-26..2026-08-04).
#: Subtracting those is not an approximation, it is a category error — it puts
#: the naive active return at -31.8pp at 1 bp and would KILL a candidate whose
#: true active breakeven is 13.9. So the scale is LABELLED
#: (`checks["breakeven_basis"]`) and not computed. Closing it needs the sweep
#: points to carry a benchmark measured over each point's OWN window — a belt
#: change, listed as item 1 of docs/GATE_V5_DESIGN_2026-08-19.md, not a gate
#: change — and until they do, a computed active breakeven here would be a
#: fabricated number wearing a criterion's name.
#:
#: v4.2 -> v4.3 (2026-08-23, CEO-approved ordered pair, ticket 58c4fff5;
#: REBUILT the same day as builder D20 after the adversary's blind review killed
#: the first attempt — run `run-adversary-d19`, docs/reviews/
#: ADVERSARY_D19_2026-08-23.md). NO THRESHOLD MOVED and `CRITERIA` is
#: byte-identical to v4.2.
#:
#: THE CEO'S RULING, which is what this version is shaped by: the pair ships
#: ONLY in the configuration that honours "not a net loosening on ANY window"
#: literally. D19 shipped a six-fold configuration whose zero-skill false-pass
#: was 3.33% -> 5.00% on the two algorithms it reached, disclosed by its author
#: and killed on the criterion. It bought power with false passes; that trade is
#: the CEO's to take and he declined it.
#:
#: The pair, and (b) may never ship without (a):
#:
#:   (a) `folds_required` scales `min_walkforward_folds` with the covered
#:       window. The defect is registered as blocking since 2026-08-18
#:       (judgement.py, `min_walkforward_folds`): the floor is fixed while the
#:       folds a window can hold grow with history, so a candidate handed more
#:       history gets more independent chances and still has to win four — and
#:       the four it wins are POST-SELECTED, since a fold only becomes
#:       measurable when its train leg cleared MIN_TRAIN_RETURN_PCT.
#:   (b) `factory.WALKFORWARD_HISTORY_FLOOR` moves to the feed's true start,
#:       ratcheted per candidate at the depth its own containers can be fed.
#:
#: WHAT D20 ADDED so that (a)+(b) could clear the ruling: the fold plan now
#: REACHES. Under D19 `window_for` capped the reach-back at
#: `train + test*(min_folds+1)` and the plan at `max(min_folds, 6)` folds, so a
#: candidate whose containers can be fed a five-year window still got six folds
#: — and the twelve-fold configuration that dominates today was unreachable.
#: See `walkforward.MAX_WALKFORWARD_FOLDS`.
#:
#: THE MEASURED TABLE. This is the only copy in the repo; anything else citing
#: these figures points here. Method: the adversary's own paired harness
#: (`scratchpad/adv19/fp2.py`, generalised to
#: `scratchpad/d20_fp.py` — one arm per geometry the fleet actually ships),
#: common random numbers, the real `retention()`, the real strict-majority rule,
#: the real belt fixed point, over SPY's own 8,448-session calendar. Every
#: algorithm in this repo holds 21 days, so there are exactly two shipped
#: geometries and the survey that says so is `scratchpad/d20_fleet.py`.
#: Reproduce: `python ../d20_fp.py 20000 7717` from the worktree root.
#:
#:   geometry             algos  v4.2 plan  v4.3 plan   FP v4.2  FP v4.3   diff
#:   floor 2024-02-26      14      4f/4       4f/4       2.95%    2.95%   +0.00pp
#:   floor 2021-03-02       2      4f/4      12f/9       2.95%    2.90%   -0.05pp
#:   ...the same pair as D19 shipped it, KILLED, not in this code:
#:   floor 2021-03-02       2      4f/4       6f/5       2.95%    4.96%   +2.01pp
#:
#:   power at Sharpe 1.0: 22.18% -> 22.18% (unchanged), 22.18% -> 39.91%
#:   (shipped) and 22.18% -> 32.46% (the killed arm — it bought less power for
#:   a real cost in false passes). n=20,000 paired draws, seed 7717; paired SE
#:   0.16pp on the false-pass differences and 0.42pp on the power difference.
#:   An independent run at n=6,000 seed 2026 agreed on the shipped rows:
#:   +0.00pp and -0.13pp on false-pass, 22.63% -> 39.88% on power. The killed
#:   row also reproduces the adversary's own independent figure for it (they
#:   measured 3.33% -> 5.00% on a different seed; the +2pp is the finding, and
#:   two harnesses agree on it).
#:
#: HOW TO READ IT, precisely, because the honest claim is narrower than "we
#: lowered the false-pass rate". On the 14-algorithm geometry the plan is
#: IDENTICAL — 0 discordant pairs out of 20,000, which is identity rather than
#: agreement. On the 2-algorithm geometry the false-pass difference (-0.05pp)
#: is INDISTINGUISHABLE FROM ZERO at this sample; what is decisive is that it is
#: not HIGHER, in two independent runs, which is exactly the criterion. The
#: power gain is not marginal: +17.7pp, forty times its paired standard error.
#: So v4.3 buys power at no measurable cost in false passes, which is the trade
#: D19 failed to make.
#:
#: WHAT v4.3 STILL DOES NOT FIX, stated so the pass is not over-read. The
#: strict-majority rule's strictness OSCILLATES WITH PARITY: three of four is
#: 31.2% under noise and three of five is 50.0%, so an odd fold count is a
#: looser bar than the even one below it at every scale. Moving that means
#: changing `min_walkforward_folds_retained_share` or replacing the majority
#: with a binomial test at a declared alpha — both are THRESHOLD changes and
#: belong to a human, so this version reports the parity effect and does not
#: touch it.
#: v4.4 (2026-08-24) — THE LUCK FILTER GETS ITS DOCUMENTED JOB BACK, AND A
#: SENTENCE THAT SAYS WHAT IT TESTED.
#:
#: THE DEFECT. `min_psr_pct` read LEAN's published `Probabilistic Sharpe Ratio`
#: verbatim and failed candidates with "the edge is not distinguishable from
#: luck on this much history". The positive-control round (quant,
#: run-quant-metacontrols) put four known-good archetypes with POSITIVE mean
#: returns through it and they scored 2.128, 1.398, 0.051 and 0.315 percent — on
#: a statistic documented as P(true Sharpe > 0), which is impossible against a
#: target of zero at any sample size. Inverting the engine's own figure on each
#: run's own series recovers the target it was really measured against: an
#: annualised Sharpe of 1.34 / 1.49 / 1.43 / 1.51 on those four. It was a SKILL
#: HURDLE wearing a luck filter's sentence, and our own module at target zero
#: reads the identical series at 85.0 / 90.4 / 50.2 / 78.3 — a disagreement of
#: roughly 40x that nobody could see because nothing captured both.
#:
#: THE CHAIR'S RULING (cto.md, 2026-08-24) fixed the sentence unconditionally
#: and set the level by measurement under a hard invariant: full-gauntlet
#: zero-skill false passes may not RISE. With a falsifier attached — if no level
#: holds, keep the hurdle and correct its words. Both configurations are
#: therefore REAL (`PSR_BASES`), because a falsifier whose alternative does not
#: exist cannot fire.
#:
#: THE MEASUREMENT (scripts/instruments/d36/calibrate.py, 200 Dirichlet
#: zero-skill draws per window, seed 20260824, the adversary's pinned feed;
#: every draw judged by the WHOLE gate with its holdout, folds, cost sweep,
#: orders and benchmark derived from the draw itself). The shipped arm is
#: EMULATED as a PSR at target 0.0755/obs — the engine is not run over a
#: synthetic series, so its statistic has to be reconstructed from the target
#: inverted out of the real candidates; the emulation is swept across the whole
#: measured range 0.0700..0.0792 and the conclusion does not move.
#:
#:     window  arm                        luck only   FULL GATE   invariant
#:     700d    engine-equivalent @65%         44.0%        1.0%   (today)
#:     700d    target-0, any level 50..99.9  100.0%        1.0%   HOLDS
#:     full    engine-equivalent @65%          0.0%        0.0%   (today)
#:     full    target-0, any level 50..99.9  100.0%        0.0%   HOLDS
#:
#: SO THE FALSIFIER DOES NOT FIRE, and the reason is worth more than the level:
#: the luck filter was never what refused this population. Under the shipped bar
#: 198 of 200 draws are refused, by `must_beat_benchmark` (194), the breakeven
#: floor (194) and the fold count (189). The level is chosen by the ruling's
#: rule — the LOWEST holding the invariant — which is 50.0, and at 50.0 this
#: criterion asserts exactly one thing: the sample Sharpe is not negative.
#:
#: WHAT WOULD CHANGE THIS DECISION'S MIND: a zero-skill population on which the
#: full-gauntlet rate MOVES with this level (any market-neutral or short-capable
#: universe, where absolute Sharpe is no longer market beta in disguise), or a
#: candidate refused by this criterion alone. Either makes the level load-bearing
#: and it must then be re-calibrated rather than inherited.
#:
#: NOT FIXED HERE, and it is the honest limit of this pass: the 2000-day
#: geometry two algorithms declare is UNREACHABLE on the pinned feed (1,378
#: shared sessions), so it is absent from both tables — not passing, not
#: failing, absent.
GATE_VERSION = "v4.4"

#: THE PREMIA BAR, versioned separately and on purpose.
#:
#: v5r1 (2026-08-23). The fund declared two claim types on 2026-08-19 and the
#: gate has only ever known one of them. Constitution, Identity:
#:
#:   * **premia** — better risk-adjusted return than holding the asset. Does
#:     NOT need to beat buy-and-hold, and must not be judged as if it should.
#:     AMENDED 2026-08-21: "risk-adjusted" is measured over EXCESS returns —
#:     above the risk-free rate, with financing charged on any leverage.
#:   * **alpha** — beats the benchmark after costs. Judged by the full gate.
#:
#: MEASURED CONSEQUENCE OF THE GAP (validator, run-validator-jointpower,
#: docs/validator/VALIDATOR_JOINTPOWER_2026-08-23.md): of four archetypes
#: computed on real META bars, two are premia-shaped — VOLSCALE scores Sharpe
#: 0.57 on 27% volatility against holding's 0.54 on 44% — and **0 of 2 are
#: certifiable BY CONSTRUCTION**: `gate.py` contained zero volatility
#: statistics, `must_beat_benchmark` was unconditional, and no claim-type field
#: existed. The premia sleeve has had no criterion since 2026-08-19.
#:
#: WHY A SEPARATE DICT rather than more keys in ``CRITERIA``. ``CRITERIA`` is
#: the alpha bar and v5r1 leaves it BYTE-IDENTICAL, which is the acceptance
#: condition this version ships under. Adding premia keys to it would force
#: them into ``CRITERIA_V1``/``_V2``/``_V3`` as well — the doctrine's stage-07
#: check requires every preserved version to describe its bar completely — and
#: any value invented there would be a fiction about what v1 asked for. A
#: premia verdict records this dict beside the alpha one, so it still states
#: its whole bar.
#:
#: WHAT THE PREMIA BAR CHANGES: exactly one criterion, for exactly one declared
#: claim type. ``must_beat_benchmark`` is replaced by the inequality below. PSR,
#: breakeven, orders, capacity, folds, retention and the holdout apply to a
#: premia claim unchanged.
#:
#: v5r2 (2026-08-23) — THE ASSUMED RATE IS GONE; THE REALISED ONE IS READ.
#: v5r1 shipped a CONSTANT rf stress of 4.0% and the adversary killed it blind
#: (docs/reviews/ADVERSARY_D23_D24_2026-08-23.md). Two facts settled it:
#:
#:   * The constant was BELOW the cash the belt's own windows pay. It was
#:     rounded up from BIL 3.97%/yr on ONE window (gate v5 round 5, G1) and the
#:     belt does not run on that window.
#:
#:     THE ONE TABLE, measured on the fund's own pinned BIL feed with the same
#:     function this code uses (``leg_moments``: the per-observation mean
#:     compounded to the series' OWN derived clock), reproducible with
#:     scratchpad/d29/rates.py:
#:
#:         window                sessions   realised %/yr   vs the 4.00 stress
#:         belt 700d                  480            4.05        SOFTER by 0.05
#:         belt 900d                  619            4.35        SOFTER by 0.35
#:         2023-01 onward             912            4.57        SOFTER by 0.57
#:         2021-01 onward (~2000d)   1378            3.25        harsher by 0.75
#:
#:     On three of four the stress was SOFTER than the realised rate — the one
#:     condition under which a cash tilt survives it. The adversary's own
#:     figures (4.07 / 4.37 / 4.59) are the same fact under a CAGR-at-252
#:     convention and agree with these to within 0.021pp; they are NOT a second
#:     measurement and must not be carried as one.
#:   * Executed, not argued: ELEVEN of sixteen zero-skill cash/beta blends
#:     PASSED the v5r1 leg while their TRUE excess-Sharpe advantage, computed
#:     against the realised BIL series per the constitution's own definition,
#:     lay between −0.0004 and +0.03. (The review's prose says twelve; the
#:     re-run of its own probe3 at this base counts eleven passes and five
#:     failures. The kill is unaffected and the smaller number is the one this
#:     comment carries, because it is the one that was re-measured.)
#:
#: And the fund had already measured that this remedy SHAPE fails:
#: docs/GATE_V5_ROUND5_MEASURED_2026-08-21.md:88-96, verbatim — *"A plausible
#: static assumption is not safe"*; *"the risk is static vs realised, not which
#: bill fund."* v5r1 shipped a static assumption and cited that document for the
#: number.
#:
#: So v5r2 subtracts the REALISED per-observation cash return, read from the
#: fund's own feed over the CANDIDATE'S OWN WINDOW, from both legs before either
#: Sharpe is formed. This is the CEO's standing excess-returns amendment
#: (constitution, Identity, 2026-08-21) reaching the code that judges the claim
#: it governs.
#:
#: THE DIRECTION IS NOT UNIFORM, AND SAYING SO IS THE POINT. A constant can be
#: wrong both ways and this one was: replacing it TIGHTENS on every window that
#: paid more than 4.0% and LOOSENS on every window that paid less. Measured
#: against the shipped fleet and the table above: 11 of 16 algorithms declare a
#: 700-day lookback and 3 declare 900 — those 14 tighten. The 2 that declare
#: 2000 days reach back into the zero-rate era — those loosen, and measurably:
#: a cash-heavy zero-skill census over that window passes 15.4% under v5r1 and
#: 29.5% under v5r2 (n=1,000 each, same draws, scratchpad/d29/probe8c.py).
#: That second direction is v5r1 refusing candidates against a rate their window
#: never paid, which is a false rejection rather than a protection — but it is
#: still permissive movement, and the CEO owns that trade rather than a comment
#: burying it under the word "tightening".
#:
#: WHAT IS UNAMBIGUOUSLY TIGHTER: a candidate whose window has no readable cash
#: series is NOT MEASURABLE rather than passed, and no window can be judged
#: against a rate softer than the one it actually paid.
#:
#: WHAT v5r2 EXPLICITLY DOES NOT FIX, stated so no pass is over-read:
#:
#:   1. **The fold and holdout legs still judge RAW return retention.** A
#:      premia claim's consistency across folds is therefore not a premia
#:      consistency — the fold legs run `enrich=False` and carry no benchmark
#:      at all (leanrunner.py, the sweep-point path), so there is nothing to
#:      compare against inside a fold. Closing it is a BELT change.
#:   2. **A single-window inequality is one draw, AND v5r2 DOES NOT IMPROVE
#:      THAT — measured, not assumed.** The validator's J3 estimate was 18.2%
#:      (4 of 22 windows). Measured directly on the belt's own geometry with
#:      1,000 Dirichlet zero-skill portfolios per cell, same draws under both
#:      versions: 700d 22.7% -> 23.2%, 900d 27.4% -> 29.3%, 2021+ 8.7% -> 8.8%.
#:      Unchanged within noise (SE ~1.4pp).
#:
#:      THAT IS NOT A FAILURE OF THE REPAIR, IT IS A DIFFERENT DEFECT, and the
#:      distinction matters for whoever fixes it next. Those false passes are
#:      SELECTION NOISE on the UNLEVERED census that measured them — a random
#:      long-only tilt across eight ETFs beats equal-weight on Sharpe about a
#:      quarter of the time — and subtracting a cash rate from BOTH legs cannot
#:      touch them. (v5r2 also called every false pass selection noise, which was
#:      wrong in the other direction: every levered construction in the review's
#:      probeD is DETERMINISTIC, not a draw.) What v5r2 removed is the CARRY
#:      illusion, and BELOW GROSS 1.0 the movement is total: on the reviewer's
#:      own cells the advantage falls from +0.7208 to −0.0003, and the answer is
#:      INVARIANT to the cash weight (a 10% risk blend and a 90% one score
#:      identically, spread < 1e-6, where v5r1 spread them by an order of
#:      magnitude).
#:
#:      BOTH OF THOSE SENTENCES WERE SHIPPED UNSCOPED AND BOTH WERE FALSIFIED
#:      BY EXECUTION (adversary D29, ground G1). "The movement is total" —
#:      counterexample: a 1.25x book of 25% SPY and 75% BIL still scores
#:      +0.153..+0.239 against SPY on all four belt windows where its financed
#:      advantage is 0.0000 (scratchpad/adv29/probeD.py, re-run at this base).
#:      "INVARIANT to the cash weight" — counterexample: one step across gross
#:      1.0 the dependence INVERTS and grows, +0.153 / +0.318 / +0.952 / +2.494
#:      at 1.25x / 1.5x / 2.0x / 3.0x on the 2021+ window, because an unfinanced
#:      borrow adds rf/(G*sd) to the excess Sharpe. v5r3 closes that by refusing
#:      above gross 1.0 rather than by re-deriving either sentence, so both are
#:      true again WITHIN the scope this bar now judges.
#:
#:      Closing the selection-noise half needs per-fold premia consistency,
#:      which is note 1's belt change, not a gate change.
#:   3. **THE BENCHMARK-RELATIVE CLASS IS TWO CRITERIA WIDE — COUNTED, NOT
#:      ASSERTED.** Enumerated because "the rest of the gauntlet stands beside
#:      it" was the sentence the adversary struck, and a replacement sentence
#:      guessing "one" would have been the same error with a smaller number.
#:
#:      Method (scratchpad/d29/classcount.py): judge one candidate against a
#:      far WORSE bar and a far BETTER one, everything else held identical, and
#:      count the criteria whose verdict moves. Control: the ALPHA bar must show
#:      exactly one, ``must_beat_benchmark`` — it does, and the first run of
#:      that script showed ZERO because the fixture pinned
#:      ``benchmark_return_pct``, so the number below is the one taken after the
#:      control came alive.
#:
#:      For a premia claim: **2** — the excess-Sharpe inequality AND
#:      ``premia_require_drawdown_not_worse``, which compares the strategy's
#:      hole with the BAR'S hole and is a benchmark-relative test that is easy
#:      to overlook because its name does not say "benchmark". A third,
#:      ``premia_require_majority_window_coverage``, depends on the bar's DATES
#:      without comparing performance. PSR, breakeven, orders, capacity, fold
#:      count, retention share and the holdout are absolute or self-consistency
#:      checks: 0 of them moved.
#:
#:      That is why the inequality has to be right, and why an unreadable cash
#:      rate fails closed.
#:   4. **The claim type is SUBMITTER-DECLARED.** A submitter picks which bar
#:      it is judged against. That is the constitution's design, and it is also
#:      an obvious loosening vector, so every premia verdict records
#:      `declared_by: "submitter"` for the audit that will eventually ask
#:      whether candidates are shopping for the easier bar.
#:   5. **The cash instrument is ONE ETF's total return, not a T-bill curve.**
#:      BIL is what this fund's feed can serve. Financing is not modelled at
#:      all — v5r3 REFUSES the books that would need it rather than pricing
#:      them, see below.
#:
#: v5r3 (2026-08-23) — LEVERAGE IS REFUSED, AND THE SESSION DENOMINATOR MUST BE
#: VOUCHED FOR. The adversary killed v5r2 blind on a hole v5r2's own notes
#: denied (docs/reviews/ADVERSARY_D29_2026-08-23.md). The rf work above was
#: CERTIFIED CORRECT in the same review — reproduced to four decimals on all
#: twelve measurable cells — and is untouched here. Two grounds:
#:
#:   * **G1, the kill.** Subtracting a realised cash rate closes the carry
#:     channel only for gross <= 100%. LEAN's default brokerage charges no
#:     margin interest, so a levered book's excess is `sum(w_i r_i) - rf`, a
#:     free gift of (1 - 1/G)*rf/sd that GROWS with the cash weight. Executed:
#:     a 1.25x book (25% SPY, 75% BIL) passed all four belt windows at
#:     +0.153..+0.239 with a financed advantage of 0.0000, and a degenerate
#:     1.05x BIL book scored +11.4..+18.1 at 0.01% drawdown — clearing the
#:     drawdown leg *because* it is cash-heavy. For scale, the largest advantage
#:     this fund has measured on a real candidate is the +0.054 recorded once
#:     below, against `premia_require_drawdown_not_worse`.
#:
#:     v5r3 CAPTURES gross exposure from the engine's own chart
#:     (`leanrunner.gross_exposure`) and refuses a premia claim above
#:     `premia_max_gross_exposure`, in the fail-closed shape of an unreadable
#:     cash rate. An ABSENT reading refuses too.
#:
#:     THE HONEST COST, measured rather than promised: NO STORED RESULT CARRIES
#:     THE READING. Of the 55 enriched job results in the store, 0 have an
#:     `exposure` block, because the belt discarded `charts` before this
#:     version read them — so every stored candidate re-judged as premia now
#:     refuses until it is re-run. The criterion is nevertheless CLEARABLE and
#:     that was checked, not assumed: of 110 LEAN result files on disk, all 108
#:     that carry a non-empty statistics block also carry the exposure chart,
#:     and the two that do not carry zero statistics.
#:
#:     THE SHAPE IS THE CEO'S TO CHANGE, and this note must not read as though
#:     it were settled. The reviewer's clearing condition was "refuse above
#:     gross 1.0 OR charge financing in the engine"; the refusal is the
#:     fail-closed half and is what a builder may ship. Pricing financing
#:     instead would ADMIT levered books, which is a WIDENING and takes his
#:     click. It is a live question, not a formality: the sleeve exists to
#:     admit vol-scaled books and those lever by construction.
#:
#:   * **G2, supporting.** The session denominator is the union of the bar's
#:     dates and the cash leg's, and both come through `fetch_daily_bars` — so
#:     one vendor tail-lag truncates them together, the union degenerates onto
#:     the shared window, and the majority test compares a window with itself.
#:     Measured: with both cut at 15.6% of the run the test read 214 of 214 and
#:     PASSED where v5r1 refused. The belt now reports `strategy_sessions` only
#:     when the UNION of the bar's dates and the cash leg's actually covers the
#:     strategy's span — both ends and no internal hole — and this gate's
#:     fallback to the calendar count, larger and therefore stricter, is
#:     unchanged and is what now fires. The check is on the union rather than on
#:     the cash leg alone, which is a stated departure from the review's wording
#:     for a measured reason; `leanrunner._session_span` carries it.
#:
#: BOTH ARE TIGHTENINGS, and the falsifying arm was run before the word was
#: written. probeD's seven levered books over four windows: 28 of 28 refuse
#: (scratchpad/d32/probeD2.py — probeD's own fixture writes no exposure block,
#: so unchanged it cannot tell a ceiling refusal from an absent reading).
#: probeF's seven truncation shapes: exactly the two joint-truncation rows move,
#: pass to fail, the other five byte-identical. And 28 UNLEVERED cells judged
#: against the base commit leaf by leaf (scratchpad/d32/identity_unlevered.py):
#: zero changed values, zero changed failure sentences, and exactly six added
#: paths — `exposure`, `max_gross_exposure`, `max_gross_exposure_allowed`,
#: `gross_within_ceiling`, `criteria.premia_max_gross_exposure` and
#: `coverage.session_span`.
#: v5r4 (2026-08-24) — THE LUCK FILTER SCORES THE ADVANTAGE, AND THE CASH-CARRY
#: BIAS IS MEASURED AND LEFT OFF.
#:
#: THE STATISTIC. A premia claim asserts that `SR_s - SR_b` is positive, so
#: asking a luck filter about the strategy's ABSOLUTE Sharpe answers a question
#: the claim never made. `premia_inputs["advantage"]` carries the moments of the
#: series whose mean IS that difference and the gate scores them with the same
#: machinery the alpha bar uses. It discriminates where the absolute version
#: cannot: on 200 zero-skill draws the false-pass rate runs 10.0% at level 50 to
#: 1.0% at 95 (700d), against a flat 100% for absolute Sharpe at every level.
#: The level is `premia_min_luck_pct`, split from the alpha one for the reason
#: recorded there.
#:
#: THE CASH-CARRY BIAS, MEASURED AND NOT APPLIED. LEAN pays 0% on idle balances
#: while this bar subtracts the realised cash return from both legs, so a
#: cash-heavy book is charged a rate it never earned. On the four controls the
#: mean cash weights are 0.013 / 0.543 / 0.938 / 0.692 and correcting it moves
#: the advantage by +0.001 / +0.089 / +0.116 / +0.121. The correction is real
#: and it runs in the kill direction — and it ships OFF, because the adversary
#: measured it blind (trace 9fb82050) and this harness reproduced it: crediting
#: takes zero-skill false passes from 10.0% to 40.5% (700d) and 5.5% to 26.0%
#: (full), since `premia_min_sharpe_advantage` is 0.0, a margin silently
#: calibrated AGAINST the bias the credit removes.
#:
#: THE MARGIN THAT WOULD SUPPORT IT, delivered as a table rather than applied —
#: raising a threshold is a human's act in either direction:
#:
#:     window   shipped (uncredited, margin 0.00)   lowest credited margin
#:                                                   holding that rate
#:     700d                 10.0%                          0.25
#:     full                  5.5%                          0.15
#:
#: So 0.25 is the binding proposal. Turning `premia_credit_idle_cash` on without
#: it in the same versioned change is a loosening wearing a bug fix's clothes.
#:
#: THE PIN, which is the adversary's clearance condition and is STRUCTURAL: the
#: credit multiplies the SAME `rfmap` the benchmark leg is subtracted with,
#: inside one function, over one date list. There is no second rate series to
#: drift from it, and `test_the_credit_and_the_subtraction_are_ONE_series` fails
#: if anyone introduces one. A flat 4.0% credited against a realised subtraction
#: would buy a w=0.2 book about +0.167 of Sharpe out of nothing — the D23
#: constant-rf kill re-entering from the inside.
PREMIA_VERSION = "v5r4"

#: Derived, never restated. Two literals for one version is how the stamp on a
#: stored verdict stops matching the bar that produced it.
GATE_VERSION_PREMIA = f"{PREMIA_VERSION}-premia"

#: The claim types this gate knows. Anything else is judged by the ALPHA bar
#: AND fails: a typo must not be able to select a criterion by accident, in
#: either direction.
CLAIM_TYPES = ("alpha", "premia")
CLAIM_TYPE_DEFAULT = "alpha"

#: The risk-free bases this gate implements. Anything else fails closed, for the
#: same reason an unrecognised claim type does: a typo in the bar's own
#: definition must not be able to select a rate by accident, in either
#: direction. Declared beside the vocabulary it belongs to rather than inline in
#: the check, so `PREMIA_CRITERIA["premia_rf_basis"]` can be read against it.
RF_BASES = ("realised_series", "constant")

#: The luck-filter statistics this gate implements. Anything else fails closed,
#: for the same reason an unrecognised rf basis does. BOTH ARE REAL and both are
#: exercised by tests: the chair's ruling set the level by measurement under a
#: hard invariant and wrote its own falsifier — "if no level holds full-gauntlet
#: zero-skill FP constant, the ~1.34 hurdle STAYS with its sentence corrected to
#: say so" — and a falsifier whose alternative branch does not exist cannot fire.
#:
#:   "target_zero_module"  — P(true Sharpe > 0), or for a premia claim P(true
#:     advantage > 0), from `statistics.psr_from_moments`. The documented job.
#:   "engine_reported"     — LEAN's published figure verbatim: an undisclosed
#:     skill hurdle, labelled as one, with its target inverted per candidate.
PSR_BASES = ("target_zero_module", "engine_reported")

PREMIA_CRITERIA: dict[str, Any] = {
    # NO MARGIN. A strict inequality and nothing added to it. The temptation is
    # to require the advantage to exceed some number, and the validator swept
    # exactly that in gate v5 round 5: margins of 1/2/3/5/8 %/yr gave
    # discrimination 0.61/0.69/0.54/0.49/0.26 — no margin fixed it, and the
    # round closed measured-NO rather than adopting one. Picking a margin here
    # would be inventing a threshold the evidence does not support, and a
    # threshold is a human's to move in either direction.
    "premia_min_sharpe_advantage": 0.0,
    # Better risk-adjusted return must not mean a bigger hole. A Sharpe
    # advantage bought by fattening the left tail is the shape a Sharpe ratio
    # is worst at seeing, and the drawdown is the cheapest independent check on
    # it. Measured to bite: of the four stored candidates carrying analytics,
    # 01b61967c933 has a +0.054 Sharpe advantage and a 28.67% drawdown against
    # its bar's 28.42% — this condition is what fails it.
    "premia_require_drawdown_not_worse": True,
    # WHERE THE RISK-FREE RATE COMES FROM. A NAMED, VERSIONED CHOICE — not a
    # code branch nobody can see, and not a number rounded off one window.
    #
    #   "realised_series" — subtract the cash return the candidate's OWN window
    #     actually paid, per observation, read from the fund's own feed. This is
    #     what ships, and it is the constitution's excess-returns amendment
    #     (2026-08-21) applied literally.
    #   "constant" — judge at rf=0 AND at `premia_rf_stress_pct`, the v5r1 rule,
    #     unchanged. Kept selectable and kept STRICT (both endpoints, so the
    #     advantage must hold across the whole interval) so that if the CEO
    #     decides a fixed stress rate is the bar he wants, it is a value change
    #     on his desk and not a code change here.
    #
    # Anything else FAILS CLOSED. A typo in a bar's own definition must not be
    # able to select a rate by accident, in either direction.
    "premia_rf_basis": "realised_series",
    # The instrument the realised series is read from. BIL is the fund's
    # shortest-duration cash ETF and the one the validator measured in gate v5
    # round 5; the gate REFUSES a stored payload measured against a different
    # symbol rather than comparing across instruments silently.
    "premia_rf_symbol": "BIL",
    # UNCHANGED VALUE, NARROWED SCOPE. Under "realised_series" this is not read
    # at all. It is the v5r1 constant and it is left at exactly the number that
    # version shipped, because moving a threshold is a human's act in either
    # direction — what changed here is which basis is selected by default, and
    # that change is a tightening the constitution already mandated.
    #
    # Its provenance, kept for whoever revisits it: the validator measured BIL
    # at 3.97%/yr and SHV at 3.94% over the gate's window (gate v5 round 5, G1),
    # rounded up to a whole percent. The belt's own windows then measured
    # higher on three of four — the table in the PREMIA_VERSION note above,
    # which is the ONLY copy of those figures — which is why this is no longer
    # the default basis.
    "premia_rf_stress_pct": 4.0,
    # A comparison over a minority of the run is not a comparison over the run.
    # Not a new number: this is the same majority rule `_add_benchmark`
    # already applies when it refuses a basket built from a minority of its
    # legs. Compared with a STRICT majority, in the same shape as the
    # walk-forward rule (`retained * 2 <= measurable` fails).
    #
    # THE DENOMINATOR MOVED IN v5r2 AND IT IS A LOOSENING, said plainly. v5r1
    # divided sessions by CALENDAR days (LEAN emits an equity point every
    # calendar day), scoring 0.67-0.69 on all 15 real specimens with nothing
    # actually missing. The denominator is now the session count, which is
    # SMALLER, so the majority is easier to reach: on a 500-return LEAN-shaped
    # run with 358 sessions, a bar covering 180 to 250 of them now passes where
    # v5r1 refused. That is the correct answer — the old test compared trading
    # days with weekends — but it is permissive movement and a reader should not
    # have to derive that from a fraction. Both numbers are reported, and
    # `test_the_SESSION_denominator_changes_a_verdict_on_LEANs_real_shape`
    # is the verdict flip made explicit.
    "premia_require_majority_window_coverage": True,
    # THE GROSS-EXPOSURE CEILING. A premia claim above this is REFUSED, not
    # scored — see `_premia_leg`'s step (1b) for why an unfinanced borrow makes
    # the excess pair the wrong arithmetic rather than a losing number.
    #
    # 1.0 IS NOT A TUNED THRESHOLD; it is the point at which the engine's
    # financing model stops being harmless. Below it a book borrows nothing and
    # `NullMarginInterestRateModel` costs the comparison nothing; above it the
    # backtest lends free money and the gift is exactly (1 - 1/G)*rf/sd.
    #
    # AND IT IS APPLIED WITH NO EPSILON, measured rather than assumed: over
    # every LEAN run this fund has on disk that produced a statistics block
    # (108 of 108, scratchpad/d32/census_exposure2.py, 2026-08-23) the maximum
    # per-timestamp gross is 1.0 on four runs, 0.9999 on most, 0.9782 at the
    # lowest, and ZERO runs exceed 1.0. A tolerance would therefore buy no
    # false refusals back and would be a loosening nobody asked for.
    "premia_max_gross_exposure": 1.0,
    # WHETHER IDLE CASH IS CREDITED THE RATE THE BAR SUBTRACTS. Ships OFF.
    #
    # THE BIAS IS REAL AND IT RUNS IN THE KILL DIRECTION: LEAN pays 0% on idle
    # balances while this bar subtracts the realised cash return from both legs,
    # so a cash-heavy book is charged a rate the engine never paid it. Measured
    # on the four positive controls (2026-08-24): mean cash weights of 0.013,
    # 0.543, 0.938 and 0.692, moving the advantage by +0.001, +0.089, +0.116 and
    # +0.121 respectively.
    #
    # AND CORRECTING IT ADMITS CANDIDATES, WHICH IS WHY IT IS OFF. The adversary
    # executed the correction blind against the Dirichlet zero-skill population
    # and measured the false-pass rate going 36.0% -> 50.5% on the 700-day
    # window and 30.5% -> 44.5% on the 2000-day one, with six of six zero-skill
    # cash mixes moving from refused to passing. The cause is not the credit: it
    # is that `premia_min_sharpe_advantage` is 0.0, a margin silently calibrated
    # AGAINST the uncredited bias — remove the bias and the strict inequality
    # has nothing left holding it up, at |advantage| around 0.01, five times
    # inside the +/-0.05 noise band the same reviewer established.
    #
    # So the two move TOGETHER or neither moves. Turning this on without raising
    # the margin in the same versioned change is a loosening wearing a bug fix's
    # clothes, and the margin is a threshold — a human's, in either direction.
    # The measured margin table that would support it is the D36 calibration
    # deliverable; the capture (`cash_credit`, `advantage_credited`,
    # `strategy_excess_credited`) ships regardless, because a bias nobody can
    # see is the thing that let this sit here in the first place.
    "premia_credit_idle_cash": False,
    # THE LUCK LEVEL FOR A PREMIA CLAIM, AND IT IS NOT THE ALPHA ONE.
    #
    # WHY IT IS SPLIT, measured rather than preferred. The alpha bar scores the
    # strategy's ABSOLUTE Sharpe, and on a long-only equity population that
    # statistic is dominated by market beta: 100% of 200 zero-skill Dirichlet
    # baskets clear it at every level from 50 to 95, so the alpha path is
    # INDIFFERENT across that whole range and the ruling's "lowest" rule picks
    # its bottom. The premia bar scores the ADVANTAGE, where the same population
    # gives a real curve — 10.0% false passes at 50 falling to 1.0% at 95 on the
    # 700-day window. One number cannot be calibrated for both, and the ruling's
    # own judgment principle is the answer: when a criterion's job differs by
    # claim type, split rather than compromise.
    #
    # 65.0 BY A RULE, not by taste. The adversary established a +/-0.05 band
    # inside which a Sharpe advantage is indistinguishable from nothing, so a
    # luck filter that demands LESS than that band admits what the reviewer has
    # already called noise. The demanded annualised advantage by level, median
    # over 40 real draws' shapes (scripts/instruments/d36 + the req_adv probe):
    #
    #        level    @50    @55    @60    @65    @70    @80    @90    @95
    #        700d   0.000  0.025  0.050  0.076  0.103  0.165  0.251  0.321
    #        full   0.000  0.018  0.036  0.054  0.074  0.118  0.180  0.231
    #
    # 60 sits ON the band at 700 days and BELOW it over the full window; 65 is
    # the lowest level clearing it on both. This is a NEW criterion and
    # therefore a pure tightening — there is no prior rate for it to not-loosen,
    # which is why the not-loosen rule could not choose it and a rule from the
    # record had to.
    "premia_min_luck_pct": 65.0,
    # WHETHER THE LUCK FILTER IS APPLIED AT ALL. Same shape as
    # `premia_require_drawdown_not_worse` and `require_walkforward` — a
    # criterion the bar can decline to apply, recorded in the stored verdict's
    # own `criteria` and echoed in `checks["luck"]["applied"]`, so a reader can
    # never mistake a criterion that was switched off for one that was passed.
    # This is the write-only-column lesson applied before the column exists.
    #
    # IT IS NOT A LEVEL. Setting `premia_min_luck_pct` to 0 does NOT turn the
    # filter off, because an UNMEASURABLE advantage refuses at any level — and
    # the shape that produces one is exactly the impersonator: a pure cash/beta
    # blend is an exact linear function of its bar, so the difference series is
    # constant, the advantage has no sampling variation, and no probability
    # attaches to it. That refusal is the correct answer and a strong one; it
    # must not be reachable by writing a small number into a level.
    "premia_require_luck_filter": True,
}

#: The bar. Deliberately data, not code branches: it can be printed, argued
#: about on its own merits, and diffed when it changes.
CRITERIA: dict[str, Any] = {
    # WHICH LUCK STATISTIC. See `PSR_BASES` for the two and the `GATE_VERSION`
    # note for the calibration that chose between them. Added as a criterion
    # rather than a code branch so a stored verdict says which statistic judged
    # it — the previous version could not, which is how a Sharpe hurdle passed
    # for a luck filter across every candidate this fund has ever run.
    "psr_basis": "target_zero_module",
    # THE LEVEL IS CALIBRATED, NOT INHERITED. The old 65.0 was set against the
    # engine's statistic and means something completely different against this
    # one; carrying the number across unchanged would have been the quietest
    # possible way to change a bar. See the `GATE_VERSION` v4.4 note for the
    # sweep, the invariant it had to hold, and the row that was chosen.
    #
    # 50.0 IS THE RULING'S RULE APPLIED LITERALLY — the LOWEST level holding
    # full-gauntlet zero-skill false passes at or below today's measured rate —
    # and the honest gloss is that on this population EVERY level from 50 to
    # 99.9 holds it, because the luck filter is not what refuses zero-skill
    # equity baskets. At 50.0 this criterion says exactly one thing: THE SAMPLE
    # SHARPE MUST NOT BE NEGATIVE. That is a floor, not a discriminator, and the
    # v4 comment above already said the walk-forward criteria are what separates
    # signal here. The measurement now says the same of the benchmark and cost
    # criteria: 194 of 200 draws refused by each, 189 by the fold count.
    "min_psr_pct": 50.0,
    # Sharpe on a handful of trades is a story about a handful of trades.
    "min_orders": 20,
    # Beating buy & hold is the minimum bar for existing at all: a strategy
    # that trails the thing it trades is an expensive way to own it.
    "must_beat_benchmark": True,
    # Cost error tolerance. An edge that dies at 3bps was never an edge.
    "min_breakeven_bps": 10.0,
    # NEW in v2: it must actually have been measured. Never cost-swept is not
    # the same as robust to costs, and v1 could not tell the difference.
    "require_breakeven_measured": True,
    # Out of sample it must keep most of what it showed in sample.
    "min_holdout_retention": 0.5,
    # NEW in v2: one holdout is one draw. A strategy must keep its edge in a
    # STRICT majority of independent folds, which is the property a lucky window
    # cannot supply and the reason this replaces "raise the PSR floor" as the real
    # test. Four folds, three required — see the v3 -> v4 note above for why the
    # number of folds and the majority rule have to be chosen together.
    "min_walkforward_folds": 4,
    "min_walkforward_folds_retained_share": 0.5,
    "require_walkforward": True,
    # A test leg must contain roughly this many of the strategy's own decisions.
    # Sized from its holding period, not from a fixed calendar window.
    "min_decisions_per_test_leg": 4,
    # A backtest nobody priced is not evidence.
    "require_priced": True,
    # Capacity has to be worth the operational effort of running it.
    "min_capacity_usd": 100_000.0,
    # NEW in v2: and it must have been estimated. Same hole as breakeven.
    "require_capacity_measured": True,
}

#: Kept so a stored v3 verdict stays interpretable. v3 is the LOOSENING described
#: above; it is preserved exactly so old verdicts can be re-read against the bar
#: they were actually judged by, not against v4's.
CRITERIA_V3: dict[str, Any] = {
    # HISTORICALLY ACCURATE, not inherited. Every verdict this dict exists to
    # keep readable was judged by the ENGINE's published statistic, so that is
    # what it names. `evaluate` merges a supplied dict over today's defaults,
    # so leaving the key out would silently re-judge an old candidate with the
    # v4.4 statistic and call the result the old bar.
    "psr_basis": "engine_reported",
    "min_psr_pct": 65.0,
    "min_orders": 20,
    "must_beat_benchmark": True,
    "min_breakeven_bps": 10.0,
    "require_breakeven_measured": True,
    "min_holdout_retention": 0.5,
    "min_walkforward_folds": 2,
    "min_walkforward_folds_retained_share": 0.5,
    "require_walkforward": True,
    "require_priced": True,
    "min_capacity_usd": 100_000.0,
    "require_capacity_measured": True,
    "min_decisions_per_test_leg": 4,
}

#: Kept so a stored v2 verdict stays interpretable, on the same reasoning as v1.
CRITERIA_V2: dict[str, Any] = {
    # HISTORICALLY ACCURATE, not inherited. Every verdict this dict exists to
    # keep readable was judged by the ENGINE's published statistic, so that is
    # what it names. `evaluate` merges a supplied dict over today's defaults,
    # so leaving the key out would silently re-judge an old candidate with the
    # v4.4 statistic and call the result the old bar.
    "psr_basis": "engine_reported",
    "min_psr_pct": 65.0,
    "min_orders": 20,
    "must_beat_benchmark": True,
    "min_breakeven_bps": 10.0,
    "require_breakeven_measured": True,
    "min_holdout_retention": 0.5,
    "min_walkforward_folds": 3,
    "min_walkforward_folds_retained_share": 0.5,
    "require_walkforward": True,
    "require_priced": True,
    "min_capacity_usd": 100_000.0,
    "require_capacity_measured": True,
    "min_decisions_per_test_leg": 0,
}

#: Kept so a stored v1 verdict stays interpretable. A verdict records the bar it
#: was judged against; re-reading an old pass under today's criteria would
#: rewrite history, and the point of versioning is that it cannot.
CRITERIA_V1: dict[str, Any] = {
    # HISTORICALLY ACCURATE, not inherited. Every verdict this dict exists to
    # keep readable was judged by the ENGINE's published statistic, so that is
    # what it names. `evaluate` merges a supplied dict over today's defaults,
    # so leaving the key out would silently re-judge an old candidate with the
    # v4.4 statistic and call the result the old bar.
    "psr_basis": "engine_reported",
    "min_psr_pct": 50.0,
    "min_orders": 20,
    "must_beat_benchmark": True,
    "min_breakeven_bps": 10.0,
    "min_holdout_retention": 0.5,
    "require_priced": True,
    "min_capacity_usd": 100_000.0,
    # v1's new-evidence requirements, stated as the False they were. `evaluate`
    # MERGES a supplied criteria dict over the current defaults, so omitting
    # these would let v2's requirements leak into a v1 judgement and make
    # re-judging an old candidate impossible — which would defeat the whole
    # point of keeping this. A version has to be a COMPLETE description of its
    # bar, including what it did not ask for.
    "require_walkforward": False,
    "require_breakeven_measured": False,
    "require_capacity_measured": False,
    # Added 2026-08-18. The comment above stated the principle correctly and this
    # dict then fell behind it: these three keys arrived with v2/v3 and were never
    # backfilled here, so `set(CRITERIA_V1) != set(CRITERIA)` and a v1 verdict
    # re-read today would have inherited v4's fold geometry — 4 folds, a strict
    # majority, 4 decisions per test leg — none of which v1 had any concept of.
    #
    # Zero rather than absent, for the same reason `require_walkforward: False` is
    # written out: v1's bar has to be describable in full, including the parts it
    # did not ask about. Found by the doctrine surface's own stage-07 check on the
    # day it was built, which is the best possible advertisement for the check.
    "min_walkforward_folds": 0,
    "min_walkforward_folds_retained_share": 0.0,
    "min_decisions_per_test_leg": 0,
}


def volatility_check(result: dict[str, Any]) -> dict[str, Any]:
    """Realised annualised volatility of the strategy and of its bar.

    CAPTURE ONLY — no criterion reads this, and wiring one to it would be a
    threshold change. It exists because the validator measured a **12x
    pass-rate swing at FIXED skill** (2.6% at 8% volatility rising to 29.7% at
    25%), delivered entirely through ``must_beat_benchmark``, and observed that
    no field anywhere recorded a candidate's volatility — so the lever was
    invisible in every stored verdict. A number nobody can read is a lever
    nobody can audit.

    Reported ABSENT with a reason when the belt did not capture the premia
    inputs, which is the case for every candidate judged before this version.
    """
    p = result.get("premia_inputs")
    rb = result.get("robustness") or {}
    engine = rb.get("engine_annual_vol_pct")
    # The same defensive read as `_premia_leg`, and for the same reason: this
    # runs on EVERY verdict including alpha ones, so a stored payload that
    # claims to be measurable and carries no volatility would take out the
    # whole judgement — on a field that exists only to be looked at.
    readable = (isinstance(p, dict) and p.get("measurable")
                and (p.get("strategy") or {}).get("ann_vol_pct") is not None
                and (p.get("benchmark") or {}).get("ann_vol_pct") is not None)
    if not readable:
        return {
            "strategy_ann_vol_pct": None,
            "benchmark_ann_vol_pct": None,
            "engine_ann_vol_pct": engine,
            "note": ("this run carries no measurable premia inputs, so neither "
                     "leg's volatility could be computed — absent, not zero"
                     + (f": {p.get('reason')}" if isinstance(p, dict)
                        and p.get("reason") else "")),
        }
    s, b = p["strategy"], p["benchmark"]
    return {
        "strategy_ann_vol_pct": round(float(s["ann_vol_pct"]), 4),
        "benchmark_ann_vol_pct": round(float(b["ann_vol_pct"]), 4),
        # The engine's own figure, carried beside ours because they are NOT the
        # same measurement and the difference is systematic: LEAN annualises a
        # calendar-day series at sqrt(252), which understates by
        # sqrt(365.25/252) = 1.2039 in theory and by 1.2033 to 1.2047 as
        # measured on the four stored candidates — see leanrunner.psr_inputs.
        "engine_ann_vol_pct": engine,
        "basis": ("both legs from the same daily returns over the window they "
                  "share, annualised at the series' OWN observed frequency"),
        "obs_per_year": (None if s.get("obs_per_year") is None
                         else round(float(s["obs_per_year"]), 2)),
        "window": p.get("window"),
    }


def _rf_breakeven_pct(s: dict[str, Any], b: dict[str, Any]
                      ) -> Optional[float]:
    """The annual risk-free rate at which the two legs' Sharpes cross.

    Returns None when the legs have equal dispersion (the difference does not
    move with rf, so there is no crossing) or when the implied per-observation
    rate is not a rate a portfolio could earn — a crossing at -300%/yr is
    arithmetic, not information.
    """
    sd_s, sd_b = s.get("stdev"), b.get("stdev")
    mu_s, mu_b = s.get("mean"), b.get("mean")
    k = s.get("obs_per_year")
    if None in (sd_s, sd_b, mu_s, mu_b, k) or not k:
        return None
    if abs(float(sd_b) - float(sd_s)) < 1e-15:
        return None
    c = (float(mu_s) * float(sd_b) - float(mu_b) * float(sd_s)) / (
        float(sd_b) - float(sd_s))
    if c <= -1.0:
        return None
    try:
        return round(((1.0 + c) ** float(k) - 1.0) * 100.0, 4)
    except OverflowError:
        return None


def _luck_leg(result: dict[str, Any], c: dict[str, Any], is_premia: bool,
              pc: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """"Is this distinguishable from luck?" — asked of the right quantity, in
    units the sentence can state.

    THE DEFECT THIS CLOSES (quant, run-quant-metacontrols, 2026-08-24; the
    chair's calibration ruling, cto.md, same day). `min_psr_pct` read LEAN's
    published ``Probabilistic Sharpe Ratio`` verbatim and failed the candidate
    with the words "the edge is not distinguishable from luck on this much
    history". Four positive controls with POSITIVE mean returns scored 2.128,
    1.398, 0.051 and 0.315 percent on a statistic documented as P(true Sharpe >
    0) — impossible against a target of zero at any sample size. Inverting the
    engine's own number on each run's own series recovers its target: an
    annualised Sharpe of 1.34 to 1.51 on the four controls, stable within a
    window and moving when the window moves. It is a SKILL HURDLE wearing a luck
    filter's sentence, and our own module at target zero disagrees with it by
    about 40x on the identical series.

    TWO REAL CONFIGURATIONS, and the shipped one is chosen by measurement:

      * ``target_zero_module`` — the documented job. Our own
        ``statistics.psr_from_series`` at target 0, scored on the run's own
        return series. The level is calibrated so that FULL-GAUNTLET zero-skill
        false passes do not rise (see the ``GATE_VERSION`` note).
      * ``engine_reported`` — the engine's number, kept selectable and kept
        HONEST. Whoever selects it gets a sentence that says it is a skill
        hurdle and states the target inverted out of the run itself.

    Anything else FAILS CLOSED, the same way an unrecognised rf basis does: a
    typo in a bar's own definition must not select a statistic by accident.

    THE SENTENCE STATES WHAT WAS TESTED. This is the half of the ruling that
    ships unconditionally, and it is not decoration: a criterion that reports a
    percentage without the target it was measured against, and without the
    Sharpe that percentage demands at this sample size, is asking a question in
    units nobody can check. Both are computed per candidate — never restated
    from a table, which is how the previous four-number identification would
    have gone stale the first time a window moved.

    WHICH QUANTITY, by claim type. An ALPHA claim asserts an edge, so the filter
    scores the strategy's own Sharpe. A PREMIA claim asserts a risk-adjusted
    ADVANTAGE over the thing it replaces — "better risk-adjusted return than
    holding the asset" — and a luck filter on its ABSOLUTE Sharpe answers a
    question the claim never made. A low-volatility overlay with a real
    advantage can carry a modest absolute Sharpe; a beta-heavy book with no
    advantage at all can carry a large one. So the premia path scores the
    advantage series the belt measured (``premia_inputs["advantage"]``), whose
    mean IS ``SR_s - SR_b``, with the same statistic and the same level.

    FAIL CLOSED, in both directions of absence. No series, no advantage block, a
    degenerate sample: the criterion is UNMEASURED, and an unmeasured criterion
    is not a passed one.
    """
    from app.fund import statistics as st

    basis = str(c.get("psr_basis"))
    # TWO LEVELS FOR TWO STATISTICS. See `premia_min_luck_pct` for the
    # measurement that forced the split; reading the alpha level here would
    # apply a number calibrated on absolute Sharpe to a statistic about an
    # advantage, which is the same category error one layer down.
    level = float(pc["premia_min_luck_pct"] if is_premia else c["min_psr_pct"])
    rb = result.get("robustness") or {}
    engine = rb.get("psr_pct")
    out: dict[str, Any] = {
        "basis": basis,
        "level_pct": level,
        "claim_scope": "premia advantage" if is_premia else "strategy sharpe",
        # BOTH READINGS ON EVERY VERDICT, whichever one the criterion used.
        # Comparability is the whole reason the disagreement was found at all,
        # and a verdict that carries only the number it acted on cannot be
        # re-read against the other when the question comes up again.
        "engine_psr_pct": engine,
        "luck_psr_pct": None,
        "evaluated_pct": None,
        "measurable": False,
        "reason": None,
    }
    # APPLIED, OR SAID NOT TO BE. Never silently skipped: a criterion listed in
    # a stored verdict and quietly not run reads as one that was passed.
    out["applied"] = (not is_premia) or bool(pc.get("premia_require_luck_filter"))
    if not out["applied"]:
        out["reason"] = ("this bar declines to apply the luck filter to a "
                         "premia claim (premia_require_luck_filter is off)")
        return out, []
    if basis not in PSR_BASES:
        out["reason"] = (f"the bar names a luck-filter basis this gate does not "
                         f"implement ({basis!r}); it knows "
                         f"{' and '.join(sorted(PSR_BASES))}")
        return out, [
            f"the luck filter could not be applied: {out['reason']} — a "
            f"criterion whose own statistic is unreadable has not been applied, "
            f"and an unapplied criterion is not a passed one"]

    # --- the series or moments this claim type is scored on ----------------
    series: list[float] = []
    moments: Optional[dict[str, Any]] = None
    k: Optional[float] = None
    absent: Optional[str] = None
    if is_premia:
        p = result.get("premia_inputs")
        # THE ARM THE CRITERION IS JUDGING. A probability attached to an
        # advantage the inequality is not testing is a confidence about the
        # wrong number — the exact defect this leg exists to close, one level up.
        key = ("advantage_credited" if pc.get("premia_credit_idle_cash")
               else "advantage")
        out["advantage_basis"] = key
        adv = (p.get(key) if isinstance(p, dict) else None) or {}
        if adv.get("measurable"):
            moments = adv
            k = ((p.get("strategy_excess") or {}).get("obs_per_year")
                 if isinstance(p, dict) else None)
        else:
            absent = (adv.get("reason")
                      or "this run carries no measured risk-adjusted advantage")
    else:
        daily = result.get("daily_returns")
        if isinstance(daily, dict) and daily.get("present"):
            series = [x for x in (daily.get("strategy") or [])
                      if isinstance(x, (int, float))]
            clock = st.observations_per_year(
                [str(d)[:10] for d in (daily.get("dates") or [])], len(series))
            k = clock.get("obs_per_year") if clock.get("usable") else None
        if len(series) < 2:
            absent = ("this run carries no undownsampled daily return series, "
                      "so there is nothing to attach a probability to")
    out["obs_per_year"] = None if k is None else round(float(k), 2)

    # --- the luck reading, captured whether or not the criterion reads it ---
    if absent is None:
        reading = (st.psr_from_moments(moments["n"], moments["sharpe_per_obs"],
                                       moments["skew"], moments["kurtosis"], 0.0)
                   if moments is not None else st.psr_from_series(series, 0.0))
        ok = reading.get("usable") if moments is not None else reading.get(
            "measurable")
        if ok:
            out["luck_psr_pct"] = reading.get("psr_pct")
            out["n_obs"] = reading.get("n_obs")
            sr = (moments["sharpe_per_obs"] if moments is not None
                  else reading.get("sharpe_per_obs"))
            out["sharpe_per_obs"] = None if sr is None else round(float(sr), 8)
            # THE SCALE THE SENTENCE QUOTES, and the two claim types do NOT
            # share it. For alpha, `sr` is the strategy's own Sharpe and
            # `sr * sqrt(K)` is the annualised Sharpe a reader expects.
            #
            # For premia, `sr` is the Sharpe OF THE DIFFERENCE SERIES — mean(d)
            # over sd(d) — and annualising THAT gives a number in units of
            # tracking error, not a Sharpe advantage. The quantity the claim is
            # about is `mean(d) * sqrt(K)`, which is `sr * sd(d) * sqrt(K)`.
            # Writing the first and calling it the second is the exact
            # mislabelling this whole leg exists to end; caught by a power probe
            # whose demanded advantage came out at 0.99 while a candidate
            # passing the same level measured 0.37.
            scale = (float(moments["stdev"]) if moments is not None else 1.0)
            out["sharpe_annualised"] = (
                None if sr is None or k is None
                else round(float(sr) * scale * math.sqrt(float(k)), 4))
        else:
            absent = reading.get("reason")

    # --- WHAT THE LEVEL DEMANDS, in the claim's own units ------------------
    bar = (st.sharpe_bar_for_psr(level, series, 0.0) if not is_premia
           else _bar_from_moments(level, moments))
    if bar.get("measurable") and k:
        scale = (float(moments["stdev"])
                 if is_premia and moments is not None else 1.0)
        out["required_sharpe_annualised"] = round(
            float(bar["sharpe_per_obs"]) * scale * math.sqrt(float(k)), 4)

    if basis == "engine_reported":
        # THE IDENTIFICATION, per candidate. The engine publishes no target and
        # no benchmark Sharpe, so the only honest way to say what this number
        # tests is to invert it out of the run's own series.
        ident = st.implied_target_sharpe(engine, series) if series else {}
        if ident.get("measurable") and k:
            out["engine_implied_target_annualised"] = round(
                float(ident["target_per_obs"]) * math.sqrt(float(k)), 4)
        out["evaluated_pct"] = engine
        out["statistic"] = (
            "LEAN's published Probabilistic Sharpe Ratio, whose target is not "
            "zero and is not published")
        if engine is None:
            out["reason"] = ("the engine published no probabilistic Sharpe for "
                             "this run")
        else:
            out["measurable"] = True
    else:
        out["evaluated_pct"] = out["luck_psr_pct"]
        out["statistic"] = (
            "P(true risk-adjusted advantage over the bar > 0)" if is_premia
            else "P(true Sharpe > 0)")
        out["target_sharpe"] = 0.0
        if absent is not None:
            out["reason"] = absent
        else:
            out["measurable"] = True

    if not out["measurable"]:
        return out, [
            f"the luck filter could not be applied: {out['reason']} — an "
            f"unmeasured criterion is not a passed one"]
    if out["evaluated_pct"] >= level:
        return out, []

    # --- the failure sentence, which must say WHAT WAS TESTED --------------
    #
    # NO LEVEL MAY WEAR ANOTHER LEVEL'S WORDS. The words "not distinguishable
    # from luck" are TRUE of a target-zero reading and FALSE of the engine's
    # statistic, so the two bases get two sentences and neither can be reached
    # by the other's configuration.
    measured = ("" if out.get("sharpe_annualised") is None else
                f"; this run measured {out['sharpe_annualised']:+.2f}")
    if basis == "engine_reported":
        target = out.get("engine_implied_target_annualised")
        identified = ("" if target is None else
                      f" Inverting the engine's own statistic on this run's "
                      f"series puts its target at an annualised Sharpe of "
                      f"{target:+.2f}, NOT at zero.")
        luck_note = ("" if out.get("luck_psr_pct") is None else
                     f" A target-zero reading of the same series is "
                     f"{out['luck_psr_pct']}%.")
        return out, [
            f"the engine's probabilistic Sharpe {out['evaluated_pct']}% is "
            f"below {level}%. THIS IS A SKILL HURDLE, NOT A LUCK TEST."
            f"{identified}{luck_note}{measured}"]
    demanded = ("" if out.get("required_sharpe_annualised") is None else
                f", which on {out.get('n_obs')} observations of this shape "
                f"demands an annualised "
                f"{'advantage' if is_premia else 'Sharpe'} of about "
                f"{out['required_sharpe_annualised']:+.2f}")
    what = ("the risk-adjusted ADVANTAGE over the bar is above zero"
            if is_premia else "the true Sharpe is above zero")
    return out, [
        f"the probability that {what} is {out['evaluated_pct']}%, below the "
        f"{level}% this bar requires{demanded}{measured} — on this much history "
        f"that is not distinguishable from luck"]


def _bar_from_moments(level: float, moments: Optional[dict[str, Any]]
                      ) -> dict[str, Any]:
    """The level's Sharpe bar for a leg whose SERIES the payload does not hold.

    The advantage is stored as moments (the series is deliberately not kept), so
    the bar is solved from those by the same solver the alpha path uses. Absent
    moments give an absent bar: a disclosure must never be able to break the
    verdict it explains.
    """
    if not moments or not moments.get("measurable"):
        return {"measurable": False}
    from app.fund import statistics as st
    return st.sharpe_bar_for_psr_from_moments(
        level, int(moments["n"]), float(moments["skew"]),
        float(moments["kurtosis"]), 0.0)


def _premia_leg(result: dict[str, Any], pc: dict[str, Any]
                ) -> tuple[dict[str, Any], list[str]]:
    """The premia inequality: is this better RISK-ADJUSTED than holding the bar?

    THE FORMULATION, stated in full because it is the whole criterion and the
    adversary should attack it as written:

        A premia claim passes iff, on the window the strategy, its benchmark
        AND the cash series all share,

          (1) both legs are measurable and that window covers a STRICT
              MAJORITY of the strategy's own SESSIONS;
          (1b) the book's MAX GROSS EXPOSURE is known and is at most
              ``premia_max_gross_exposure`` — a levered backtest borrows for
              free, so above the ceiling the excess pair below is the wrong
              arithmetic and the claim is refused rather than scored;
          (2) the strategy's annualised Sharpe on returns NET OF THE REALISED
              PER-OBSERVATION CASH RETURN exceeds the benchmark's, computed the
              same way; AND
          (3) the strategy's maximum drawdown does not exceed the benchmark's.

    WHERE THE CASH RETURN COMES FROM, and why this replaced a constant. v5r1
    ran the inequality at rf=0 and again at a fixed 4.0%. The adversary
    executed it: eleven of sixteen zero-skill cash/beta blends passed while
    their true excess-Sharpe advantage was between −0.0004 and +0.03, because on
    three of the four windows the belt uses the realised rate was ABOVE the 4.00
    stress (the table is in the ``PREMIA_VERSION`` note and is not restated
    here). A constant fitted on one window is a threshold that silently changes
    meaning with every backtest date. So the belt now reads the cash series over
    the CANDIDATE'S OWN window and subtracts it per observation; this function
    reads the excess pair it stored and never assumes a rate.

    WHY THE RAW (rf=0) ARM IS NO LONGER A CONDITION. Under a constant rate the
    Sharpe difference is affine in that rate, so two endpoint checks pinned the
    whole interval and BOTH were needed. Under a realised series there is no
    free parameter left to sweep: the excess pair IS the comparison, in one
    evaluation. The raw pair is still REPORTED — ``sharpe_advantage_raw`` beside
    ``sharpe_advantage`` — because the gap between them is exactly the size of
    the T-bill carry the constitution's amendment is about, and a reader should
    be able to see it. It is capture, not a criterion.

    FAIL CLOSED ON AN UNREADABLE RATE. An absent cash series does not become
    rf=0; it becomes NOT MEASURABLE. Absence is never zero, and rf=0 is the
    single most flattering assumption available to a cash-heavy mix — which is
    the shape the CEO's 2026-08-21 amendment exists to refuse.
    """
    from app.fund import statistics as st

    basis = str(pc.get("premia_rf_basis"))
    want_symbol = str(pc.get("premia_rf_symbol"))
    out: dict[str, Any] = {
        "declared_by": "submitter",
        "rf_basis": basis,
        "rf_symbol": want_symbol,
        "criteria": dict(pc),
        "measurable": False,
    }
    if basis not in RF_BASES:
        out["reason"] = (f"the premia bar names an rf basis this gate does not "
                         f"implement ({basis!r}); it knows "
                         f"{' and '.join(sorted(RF_BASES))}")
        return out, [
            f"the premia comparison could not be measured: {out['reason']} — a "
            f"criterion whose own risk-free basis is unreadable has not been "
            f"applied, and an unapplied criterion is not a passed one"]
    p = result.get("premia_inputs")
    if not isinstance(p, dict) or not p.get("measurable"):
        reason = (p.get("reason") if isinstance(p, dict) else None) or (
            "the belt captured no premia inputs for this run")
        out["reason"] = reason
        return out, [
            f"the premia comparison could not be measured: {reason} — a premia "
            f"claim is 'better risk-adjusted return than holding the asset', "
            f"and an unmeasured comparison establishes neither side"]

    s, b = p.get("strategy") or {}, p.get("benchmark") or {}
    # A GATE MUST RETURN A VERDICT, NEVER RAISE. `premia_inputs` always writes
    # these four beside `measurable: True`, but this function reads a STORED
    # payload — one that may have been written by an older belt, round-tripped
    # through JSON, or truncated — and a TypeError inside `evaluate` would take
    # out the whole judgement rather than fail one criterion. A payload that
    # claims to be measurable and is not is reported as unmeasurable.
    needed = ("ann_vol_pct", "max_drawdown_pct", "total_return_pct", "stdev")
    absent = [k for k in needed
              if s.get(k) is None or b.get(k) is None]
    if absent:
        out["reason"] = (f"the stored premia inputs claim to be measurable but "
                         f"carry no {', '.join(absent)}")
        return out, [
            f"the premia comparison could not be measured: {out['reason']} — "
            f"a payload that cannot state both legs has not compared them"]
    failures: list[str] = []
    cov = p.get("coverage") or {}
    common = int(cov.get("common_days") or 0)
    total = int(cov.get("strategy_days") or 0)
    out.update({
        "measurable": True,
        "window": p.get("window"),
        "coverage": cov,
        "benchmark_leg_source": p.get("benchmark_leg_source"),
        "strategy_ann_vol_pct": round(float(s["ann_vol_pct"]), 4),
        "benchmark_ann_vol_pct": round(float(b["ann_vol_pct"]), 4),
        "strategy_max_drawdown_pct": round(float(s["max_drawdown_pct"]), 4),
        "benchmark_max_drawdown_pct": round(float(b["max_drawdown_pct"]), 4),
        # Recorded, NOT enforced. A premia claim does not have to beat
        # buy-and-hold — the constitution says so in as many words — but a
        # reader should be able to see when it did, and on the common window
        # rather than across the two different windows the alpha criterion
        # compares.
        "beats_benchmark_total_return":
            float(s["total_return_pct"]) > float(b["total_return_pct"]),
        "strategy_total_return_pct": round(float(s["total_return_pct"]), 4),
        "benchmark_total_return_pct": round(float(b["total_return_pct"]), 4),
    })

    # (1) A strict majority of the strategy's own SESSIONS, in integer
    # arithmetic, for the same reason the walk-forward majority is: a float
    # share compared with `<` is where the off-by-one lives.
    #
    # THE DENOMINATOR. v5r1 used `strategy_days`, which counts CALENDAR days
    # because LEAN emits an equity point every one of them — so the test was
    # comparing sessions with weekends and scored 0.67-0.69 on all 15 real
    # specimens, ~19pp of pure slack. `strategy_sessions` is the session count
    # over the strategy's own span, taken from the union of the bar's and the
    # cash series' dates. Falling back to the calendar count when the belt did
    # not record sessions is the STRICT direction — a calendar denominator is
    # larger, so the majority is harder to reach, and an old payload cannot
    # pass a test a new one would fail.
    sessions = cov.get("strategy_sessions")
    denominator = int(sessions) if sessions else total
    denominator_basis = ("sessions" if sessions else "calendar_days")
    coverage_ok = common * 2 > denominator if denominator else False
    out["coverage_majority"] = coverage_ok
    out["coverage_denominator"] = denominator
    out["coverage_denominator_basis"] = denominator_basis
    if pc.get("premia_require_majority_window_coverage") and not coverage_ok:
        failures.append(
            f"the strategy, its bar and the cash leg share only {common} of the "
            f"strategy's {denominator} {denominator_basis.replace('_', ' ')} "
            f"({total} calendar days in the run) — a comparison over a minority "
            f"of the run is not a comparison over the run")

    # (2) THE INEQUALITY. Which pair of legs it runs on is the versioned choice
    # `premia_rf_basis` names, and an unreadable cash rate FAILS CLOSED — it
    # never silently becomes rf=0, which is the assumption most flattering to
    # the cash-heavy mix the constitution's amendment was written against.
    margin = float(pc["premia_min_sharpe_advantage"])
    raw0 = st.sharpe_at_rf(s, 0.0)
    raw_b0 = st.sharpe_at_rf(b, 0.0)
    out["rf_breakeven_pct"] = _rf_breakeven_pct(s, b)
    if raw0 is not None and raw_b0 is not None:
        # CAPTURE, NOT A CRITERION. The gap between this and the excess
        # advantage below IS the T-bill carry, and a reader who cannot see it
        # cannot audit the criterion that removed it.
        out.update({"sharpe_strategy_raw": round(raw0, 5),
                    "sharpe_benchmark_raw": round(raw_b0, 5),
                    "sharpe_advantage_raw": round(raw0 - raw_b0, 5)})

    # (1b) GROSS EXPOSURE, and this one REFUSES rather than scores.
    #
    # PLACED AFTER THE RAW CAPTURE AND BEFORE THE INEQUALITY, deliberately. A
    # refused book still reports `sharpe_advantage_raw` — capture, never a
    # criterion — but must NOT publish `sharpe_advantage`: a reader who found
    # +2.49 sitting beside a refusal would quote it, and that figure is the
    # engine's free borrow, not an edge.
    #
    # THE HOLE IT CLOSES (adversary D29, blind, 2026-08-23, ground G1). LEAN's
    # default brokerage charges no margin interest, so a levered backtest's
    # excess return is `sum(w_i r_i) - rf` and not `sum(w_i (r_i - rf))`: the
    # borrow is free, and the gift in annualised Sharpe units is exactly
    # (1 - 1/G) * rf / sd. It is not a losing number the inequality can catch —
    # it is the WRONG ARITHMETIC, growing with the cash weight, and it is
    # invisible to a reader because the payload carried no exposure field.
    # Executed on the fund's own feed, a 1.25x book of 25% SPY and 75% BIL
    # cleared this bar on all four belt windows at +0.153..+0.239 where the
    # financed answer is 0.0000. The figures live once, in the ``PREMIA_VERSION``
    # note's v5r3 section, and are deliberately not restated here.
    #
    # SO THE REFUSAL IS `measurable: False`, THE SAME SHAPE AS AN UNREADABLE
    # CASH RATE, and deliberately not a plain failure. A plain failure would
    # assert that the comparison was made and lost; what actually happened is
    # that this gate cannot form the comparison for a book whose financing the
    # engine did not charge. And an ABSENT exposure reading refuses too:
    # absence is never zero, and for gross exposure zero — or an assumed 1.0 —
    # is the single most permissive answer available.
    #
    # THE OPEN POLICY QUESTION, recorded so this text does not foreclose it.
    # The clearing condition the reviewer wrote is "refuse above gross 1.0 OR
    # charge financing in the engine". This ships the refusal, which is the
    # fail-closed half and the half a builder may ship. Replacing it with
    # engine-priced financing would ADMIT levered books — a WIDENING of what
    # this bar accepts, and therefore the CEO's click, not a code change. The
    # sleeve exists to admit vol-scaled books, which lever by construction, so
    # this is a live question and not a formality.
    gross = p.get("max_gross_exposure")
    ceiling = float(pc["premia_max_gross_exposure"])
    out["exposure"] = p.get("exposure")
    out["max_gross_exposure"] = gross
    out["max_gross_exposure_allowed"] = ceiling
    if not p.get("gross_measurable") or gross is None:
        exposure = p.get("exposure")
        why = ((exposure or {}).get("reason") if isinstance(exposure, dict)
               else None) or "the belt captured no exposure reading for this run"
        out["measurable"] = False
        out["reason"] = why
        failures.append(
            f"the premia comparison could not be measured because the book's "
            f"GROSS EXPOSURE is unknown: {why} — a backtest charges no margin "
            f"interest, so above 100% gross the excess pair this bar reads is "
            f"the wrong arithmetic, and an unknown leverage is not an absent "
            f"one")
        return out, failures
    out["gross_within_ceiling"] = gross <= ceiling
    if not gross <= ceiling:
        out["measurable"] = False
        out["reason"] = (
            f"this book reached {gross:.4f}x gross exposure and the premia bar "
            f"is defined only to {ceiling:.2f}x")
        failures.append(
            f"the premia comparison could not be measured: {out['reason']} — "
            f"the engine charges no margin interest, so the borrowed "
            f"{(gross - ceiling) * 100:.1f}% earned the cash rate for free and "
            f"the excess pair overstates this book by "
            f"(1 - 1/{gross:.4f}) x rf / sd. Judging it would certify financing "
            f"the account never paid")
        return out, failures

    if basis == "realised_series":
        rf = p.get("rf") if isinstance(p.get("rf"), dict) else {}
        out["rf"] = rf
        got_symbol = rf.get("symbol")
        # WHICH EXCESS PAIR, and it is a criterion rather than a code branch so
        # a stored verdict says which one judged it. See
        # `premia_credit_idle_cash` for why the default is the uncredited pair.
        credit_on = bool(pc.get("premia_credit_idle_cash"))
        out["idle_cash_credited"] = credit_on
        out["cash_credit"] = p.get("cash_credit")
        if credit_on and not p.get("credited_measurable"):
            out["measurable"] = False
            out["reason"] = (
                (p.get("cash_credit") or {}).get("reason")
                or p.get("credit_absent_reason")
                or "the belt captured no credited excess pair for this run")
            failures.append(
                f"the premia comparison could not be measured with idle cash "
                f"credited: {out['reason']} — the bar subtracts a cash return "
                f"from a book whose cash weight is unknown, and an unknown "
                f"weight is NOT a fully-invested one")
            return out, failures
        if not p.get("excess_measurable"):
            out["measurable"] = False
            out["reason"] = (rf.get("reason")
                             or "the belt captured no excess-return pair for "
                                "this run")
            failures.append(
                f"the premia comparison could not be measured against a "
                f"realised cash rate: {out['reason']} — the constitution "
                f"measures a premia claim over EXCESS returns (2026-08-21), and "
                f"an unknown cash rate is NOT a zero one")
            return out, failures
        if got_symbol != want_symbol:
            out["measurable"] = False
            out["reason"] = (f"this run's excess returns were measured against "
                             f"{got_symbol!r} and the bar names {want_symbol!r}")
            failures.append(
                f"the premia comparison could not be measured: {out['reason']} "
                f"— two cash instruments are not one comparison, and re-judging "
                f"against a series the run never saw would be an invention")
            return out, failures
        s_leg = ((p.get("strategy_excess_credited") if credit_on
                  else p.get("strategy_excess")) or {})
        b_leg = p.get("benchmark_excess") or {}
        out["rf_realised_annual_pct"] = rf.get("realised_annual_pct")
        # THE OTHER ARM, always reported. The gap between these two IS the size
        # of the idle-cash bias on this candidate, and a reader who cannot see
        # it cannot audit either the correction or the decision not to apply it.
        other = ((p.get("strategy_excess") if credit_on
                  else p.get("strategy_excess_credited")) or {})
        alt_s = st.sharpe_at_rf(other, 0.0)
        alt_b = st.sharpe_at_rf(b_leg, 0.0)
        out["sharpe_advantage_other_arm"] = (
            None if alt_s is None or alt_b is None else round(alt_s - alt_b, 5))
        out["other_arm"] = "uncredited" if credit_on else "credited"
    else:
        # "constant": the v5r1 rule, unchanged and still two-armed. The Sharpe
        # difference is affine in a constant rate, so positivity at both ends of
        # [0, stress] is positivity throughout it — dropping either arm would
        # LOOSEN this basis relative to the version it preserves.
        s_leg, b_leg = s, b
        out["rf_stress_pct"] = float(pc["premia_rf_stress_pct"])

    s0 = st.sharpe_at_rf(s_leg, 0.0)
    b0 = st.sharpe_at_rf(b_leg, 0.0)
    if s0 is None or b0 is None:
        # `measurable` means the comparison WAS measured, so it goes back to
        # False here rather than staying True beside a reason saying it was not.
        out["measurable"] = False
        out["reason"] = "a Sharpe could not be computed for one of the legs"
        failures.append(
            "the risk-adjusted comparison could not be computed — one leg has "
            "no usable dispersion, and a constant return is not a "
            "risk-adjusted one")
        return out, failures
    adv0 = s0 - b0
    out.update({
        "sharpe_basis": ("excess of the realised cash series"
                         if basis == "realised_series"
                         else "raw returns, rf assumed 0%"),
        "sharpe_strategy": round(s0, 5), "sharpe_benchmark": round(b0, 5),
        "sharpe_advantage": round(adv0, 5),
    })
    if basis == "constant":
        rf_stress = float(pc["premia_rf_stress_pct"])
        s1 = st.sharpe_at_rf(s, rf_stress)
        b1 = st.sharpe_at_rf(b, rf_stress)
        if s1 is None or b1 is None:
            out["measurable"] = False
            out["reason"] = "a stressed Sharpe could not be computed"
            failures.append(
                "the risk-adjusted comparison could not be computed at the "
                "stressed rate — one leg has no usable dispersion")
            return out, failures
        adv1 = s1 - b1
        out.update({"sharpe_strategy_at_stress": round(s1, 5),
                    "sharpe_benchmark_at_stress": round(b1, 5),
                    "sharpe_advantage_at_stress": round(adv1, 5)})
        # rf_sensitive names the SHAPE the constitution warns about, so it is
        # set only where that shape is what happened: the advantage exists at
        # rf=0 and is gone by the stressed rate. A candidate that had no
        # advantage in the first place is not "rf sensitive", it simply had no
        # premium.
        out["rf_sensitive"] = bool(adv0 > margin and not adv1 > margin)
        if adv0 > margin and out["rf_sensitive"]:
            failures.append(
                f"the risk-adjusted advantage (+{adv0:.3f} at rf=0%) DISAPPEARS "
                f"at rf={rf_stress:.1f}% ({adv1:+.3f}): the strategy runs at "
                f"{out['strategy_ann_vol_pct']:.1f}% volatility against the "
                f"bar's {out['benchmark_ann_vol_pct']:.1f}%, so what looks like "
                f"a premium is consistent with cash earning the risk-free rate"
                + ("" if out.get("rf_breakeven_pct") is None else
                   f". The premium vanishes above a "
                   f"{out['rf_breakeven_pct']:.2f}%/yr cash rate"))
    if not adv0 > margin:
        # THE CARRY SENTENCE. When the raw advantage was positive and the excess
        # one is not, the premium WAS the cash — say so with both numbers and
        # the rate, because "no premium" alone loses the finding.
        raw_adv = out.get("sharpe_advantage_raw")
        realised = out.get("rf_realised_annual_pct")
        carry = ""
        if (basis == "realised_series" and raw_adv is not None
                and raw_adv > margin and realised is not None):
            carry = (f" The apparent advantage of {raw_adv:+.3f} before the cash "
                     f"rate was removed is CARRY: {want_symbol} paid "
                     f"{float(realised):.2f}%/yr over this window, and the "
                     f"strategy runs at {out['strategy_ann_vol_pct']:.1f}% "
                     f"volatility against the bar's "
                     f"{out['benchmark_ann_vol_pct']:.1f}%.")
        failures.append(
            f"risk-adjusted return {s0:.3f} against {b0:.3f} for simply "
            f"holding the bar: no premium over owning the thing, and a premia "
            f"claim is exactly the claim that there is one." + carry)

    # (3) The drawdown stays on the RAW legs deliberately. An excess-return
    # drawdown is not a hole anyone lived through: the money in the account fell
    # by the raw amount, and netting a cash return out of it would shrink a real
    # loss by an amount the account never received.
    dd_ok = float(s["max_drawdown_pct"]) <= float(b["max_drawdown_pct"])
    out["drawdown_not_worse"] = dd_ok
    if pc.get("premia_require_drawdown_not_worse") and not dd_ok:
        failures.append(
            f"kept a deeper hole than the thing it replaces: drawdown "
            f"{out['strategy_max_drawdown_pct']:.1f}% against "
            f"{out['benchmark_max_drawdown_pct']:.1f}% — better risk-adjusted "
            f"return must not mean bigger drawdowns")
    return out, failures


def evaluate(result: dict[str, Any],
             holdout: Optional[dict[str, Any]] = None,
             sweep_summary: Optional[dict[str, Any]] = None,
             criteria: Optional[dict[str, Any]] = None,
             walkforward: Optional[dict[str, Any]] = None,
             claim_type: Optional[str] = None,
             premia_criteria: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Apply the bar. Returns failures in plain sentences, not a score.

    An input that is MISSING fails rather than passes. A candidate that was
    never held out has not survived a holdout, and treating absent evidence as
    satisfied evidence is how a factory quietly lowers its own bar.

    ``claim_type`` selects WHICH bar, and defaults to ``alpha`` so every
    existing caller, every stored candidate and every re-judgement is
    byte-identical to v4.3. A ``premia`` claim swaps exactly one criterion —
    see ``PREMIA_VERSION`` above for what that does and does not change. An
    UNRECOGNISED claim type is judged by the alpha bar and fails: a typo must
    not be able to select a criterion by accident.
    """
    c = {**CRITERIA, **(criteria or {})}
    declared = CLAIM_TYPE_DEFAULT if claim_type is None else str(claim_type)
    known = declared in CLAIM_TYPES
    is_premia = declared == "premia"
    pc = {**PREMIA_CRITERIA, **(premia_criteria or {})}
    rb = result.get("robustness") or {}
    failures: list[str] = []
    checks: dict[str, Any] = {}

    # --- was it priced at all --------------------------------------------
    costs = rb.get("costs") or {}
    priced = bool(costs.get("slippage_modelled"))
    checks["priced"] = priced
    if c["require_priced"] and not priced:
        failures.append("not priced: no slippage model, so every fill happened "
                        "at the close and the return is overstated")

    # --- enough evidence to say anything ----------------------------------
    orders = rb.get("total_orders")
    checks["orders"] = orders
    if orders is None or orders < c["min_orders"]:
        failures.append(f"only {orders if orders is not None else 'unknown'} "
                        f"fills; {c['min_orders']} is the minimum before a "
                        f"Sharpe describes a strategy rather than an anecdote")

    # --- distinguishable from luck ----------------------------------------
    # `psr_pct` KEEPS ITS KEY AND ITS MEANING: the engine's number, verbatim, on
    # every verdict. It is no longer what the criterion reads, and a stored
    # verdict must not have to be re-derived to say which of the two figures
    # moved. `checks["luck"]` carries the whole leg, both readings included.
    checks["psr_pct"] = rb.get("psr_pct")
    luck, luck_failures = _luck_leg(result, c, is_premia, pc)
    checks["luck"] = luck
    failures.extend(luck_failures)

    # --- better than owning the thing -------------------------------------
    strat = result.get("total_return_pct")
    bench = result.get("benchmark_return_pct")
    checks["return_pct"], checks["benchmark_pct"] = strat, bench
    # WHICH POPULATION the bar was built from, recorded in the verdict rather
    # than left in the belt's result payload. A stored verdict already says
    # which THRESHOLD it cleared; a benchmark criterion that cannot say which
    # POPULATION it cleared is half a record. The bias is measured and it runs
    # in the kill direction (docs/SURVIVORSHIP_2026-08-17.md), so a reader must
    # be able to tell a survivor-only comparison from a corrected one without
    # re-deriving it. No threshold reads this: labelling is what the evidence
    # supports, and failing every candidate that predates the label would be
    # judging strategies for a defect in our own data.
    pop = result.get("benchmark_population")
    if isinstance(pop, dict):
        unjudgeable = pop.get("unjudgeable_by_snapshot")
        checks["benchmark_population"] = {
            "basis": pop.get("basis"),
            "point_in_time": pop.get("point_in_time"),
            "listing_asof_applied": pop.get("listing_asof_applied"),
            "survivorship_corrected": pop.get("survivorship_corrected"),
            "as_of": pop.get("as_of"),
            "names": len(pop.get("population") or []),
            # HOW MANY OF THOSE NAMES THE SNAPSHOT COULD ACTUALLY JUDGE, and
            # which ones it could not. Dropped from the stored verdict until
            # D20, which made the two most reachable cases indistinguishable:
            # a bar of four ETFs on the fund's only snapshot date judges ZERO
            # of them (the snapshot holds CS and ADRC and nothing else) and
            # read exactly like a bar the snapshot had checked and cleared.
            # The honesty fields have to survive into the stored record or the
            # label is honest only in the payload nobody keeps.
            "names_judged": pop.get("names_judged"),
            "unjudgeable_by_snapshot": list(unjudgeable) if unjudgeable else [],
            "unjudgeable_note": pop.get("unjudgeable_note"),
        }
    elif bench is not None:
        # A benchmark with no population label. Absent, and said so — an
        # unlabelled bar is not a corrected one.
        checks["benchmark_population"] = {
            "basis": None,
            "note": ("this benchmark carries NO population label, so the "
                     "verdict cannot say which universe it was measured "
                     "against — unlabelled is not corrected"),
        }
    # WHICH BAR. For an ALPHA claim this is unchanged from v4.3, down to the
    # sentence. For a PREMIA claim `must_beat_benchmark` is REPLACED — the
    # constitution says a premia claim "does NOT need to beat buy-and-hold, and
    # must not be judged as if it should" — by the risk-adjusted inequality in
    # `_premia_leg`. Nothing else in this function branches on claim type.
    #
    # `criteria` on a premia verdict still CONTAINS `must_beat_benchmark: True`
    # — it is the alpha dict, preserved whole — so this flag says plainly
    # whether it was applied. A criterion listed in a stored verdict and
    # silently skipped is the write-only-column shape, and it would be read as
    # "this candidate beat its benchmark" by anyone who did not know v5r1
    # existed.
    checks["must_beat_benchmark_applied"] = bool(
        c["must_beat_benchmark"]) and not is_premia
    if is_premia:
        premia, premia_failures = _premia_leg(result, pc)
        premia["replaces_criterion"] = "must_beat_benchmark"
        checks["premia"] = premia
        failures.extend(premia_failures)
    elif c["must_beat_benchmark"]:
        if strat is None or bench is None:
            failures.append("no benchmark to compare against — 'better than "
                            "nothing' is not the question")
        elif strat <= bench:
            failures.append(f"returns {strat}% against {bench}% for simply "
                            f"owning it: an expensive way to hold the underlying")

    # --- survives data it was not chosen on -------------------------------
    retention = None
    retention_reason = None
    no_holdout_trades = False
    trained_ok = False
    if holdout and holdout.get("state") == "done":
        if holdout.get("dates_honoured") is False:
            failures.append("the held-out test ran the SAME dates twice — the "
                            "algorithm ignored start/end, so it proves nothing")
        else:
            tr = (holdout.get("train") or {}).get("return_pct")
            test = holdout.get("test") or {}
            te = test.get("return_pct")
            # A test window in which nothing was traded is not a 0% result. It
            # is the absence of a result, and the two must not share a sentence:
            # a strategy needing 180 days of history cannot fill its window
            # inside a 155-day test run started cold, so it places no orders and
            # scores a flat zero that looks exactly like a lost edge. Reporting
            # that as "kept 0% of its edge" would condemn strategies that were
            # never actually examined — and, worse, sound like evidence.
            if test.get("total_orders") == 0:
                no_holdout_trades = True
                # Two very different causes, and asserting the wrong one sends the
                # reader to fix the wrong thing. If the TRAIN leg traded, the rule
                # is demonstrably capable of firing and simply did not in the test
                # window — which is a fact about the signal, not about warm-up.
                # Measured: the INTC mean-reversion traded in-sample and then
                # placed zero orders across 226 warmed-up 2026 sessions, because
                # its RSI never crossed the entry threshold. The old message told
                # us to add warm-up it already had.
                trained_ok = bool(tr and (holdout.get("train") or {})
                                  .get("return_pct") is not None)
            elif tr is not None and te is not None:
                # v4.1: the SAME discipline the walk-forward folds carry —
                # strict-positive denominator, the MIN_TRAIN_RETURN_PCT floor,
                # and annualisation over each leg's actual window. The raw
                # `te / tr` this replaces inverted the sign on a negative
                # train leg and exploded on a near-zero one; see the version
                # note above GATE_VERSION.
                from app.fund.walkforward import retention as _leg_retention
                r = _leg_retention(
                    tr, te, test.get("total_orders"),
                    _window_days((holdout.get("train") or {}).get("window")),
                    _window_days(test.get("window")))
                retention = r.get("retention")
                retention_reason = r.get("reason")
                checks["holdout_retention_basis"] = r.get("basis")
    checks["holdout_retention"] = retention
    if no_holdout_trades:
        if trained_ok:
            failures.append(
                "the held-out test placed no trades at all, while the training "
                "leg did trade — so the rule can fire and simply never met its "
                "own entry condition in this window. That is a fact about the "
                "signal, not about warm-up, and it is not evidence about the "
                "edge either way: a strategy that does not act is not managing "
                "the position it is credited with")
        else:
            failures.append(
                "the held-out test placed no trades at all and neither did the "
                "training leg, so nothing here says anything either way — the "
                "usual cause is an algorithm needing more history than the "
                "window gives it, so it never warmed up. Check warm-up and "
                "re-run before believing any out-of-sample number")
    elif retention is None:
        if retention_reason:
            # The holdout RAN; the ratio is unmeasurable for a stated reason
            # (negative or sub-floor train leg). Collapsing this into "no
            # held-out test" sent the reader to re-run a test that had run.
            failures.append(f"the held-out retention could not be measured: "
                            f"{retention_reason}")
        else:
            failures.append("no held-out test — choosing the best of N settings "
                            "guarantees a good number on the window you chose "
                            "them on")
    elif retention < c["min_holdout_retention"]:
        failures.append(f"kept only {retention:.0%} of its edge out of sample; "
                        f"{c['min_holdout_retention']:.0%} is the floor")

    # --- robust to being wrong about costs --------------------------------
    be = (sweep_summary or {}).get("breakeven_cost") or {}
    be_bps = be.get("breakeven_bps")
    checks["breakeven_bps"] = be_bps
    # WHICH RETURN SCALE THIS FRAGILITY NUMBER IS ON, stated beside it in the
    # same shape as `holdout_retention_basis`. The sweep varies cost and reads
    # TOTAL return, so this is the cost at which the strategy stops making
    # money — not the cost at which it stops beating its benchmark. For an
    # alpha claim only the second is the claim's own fragility, and the two are
    # 4.6x apart on the one candidate that has reached here. A label is what
    # the data supports; see the version note above.
    #
    # Set only where there IS an answer to describe. Labelling the scale of a
    # measurement that was never taken would decorate an absence, which is the
    # habit this whole criterion exists to break.
    if be_bps is not None:
        checks["breakeven_basis"] = "total_return"
    if be_bps is None:
        # v1 let this through, and a null strategy used the gap: never having
        # been cost-swept satisfied the cost-robustness criterion.
        if c.get("require_breakeven_measured"):
            reason = be.get("reason") or "no cost sweep was run"
            if "still profitable at every cost tested" in str(reason):
                # v4.2. "Still profitable at every cost tested" is bounded by
                # the grid the submitter chose, so the floor is checked against
                # HOW FAR THE GRID WENT. Before this, the string below was the
                # whole of the check and `min_breakeven_bps` was unreachable —
                # see the version note. The string is kept as the annotation it
                # always was; what changes is that it no longer substitutes for
                # the evaluation.
                floor = c["min_breakeven_bps"]
                widest = max_tested_bps(be.get("tested_range"))
                checks["breakeven_bps"] = "beyond the tested range"
                checks["breakeven_max_tested_bps"] = (
                    None if widest is None else round(widest, 4))
                # A tested range IS a cost answer, so it carries the same scale
                # label as a crossing does.
                checks["breakeven_basis"] = "total_return"
                if widest is None:
                    failures.append(
                        f"the cost sweep says the edge survived every cost it "
                        f"tested but does not say how far it tested, so the "
                        f"{fmt_bps(floor)}bps floor could not be checked — an "
                        f"unreadable tested range is not a cleared floor")
                elif widest < floor:
                    # The comparison is on the raw float; fmt_bps only prints.
                    failures.append(
                        f"cost robustness was tested only to {fmt_bps(widest)} "
                        f"bps and the floor is {fmt_bps(floor)} — widen the "
                        f"grid past the floor")
            else:
                failures.append(
                    f"cost robustness was never measured ({reason}) — a "
                    f"candidate that was not cost-swept has not shown it "
                    f"survives being wrong about costs")
    elif be_bps < c["min_breakeven_bps"]:
        failures.append(f"dies at {be_bps}bps of slippage, under the "
                        f"{c['min_breakeven_bps']}bps floor — too fragile to "
                        f"cost assumptions to trust")

    # --- worth running at all ---------------------------------------------
    cap = (result.get("capacity") or {}).get("capacity_usd")
    checks["capacity_usd"] = cap
    if cap is None:
        # The second of v1's two inverted criteria. An unestimated capacity is
        # not an adequate capacity.
        if c.get("require_capacity_measured"):
            failures.append("capacity was never estimated — an unmeasured "
                            "capacity is not an adequate one, and a strategy "
                            "whose ceiling nobody knows cannot be sized")
    elif cap < c["min_capacity_usd"]:
        failures.append(f"capacity ${cap:,.0f} is below ${c['min_capacity_usd']:,.0f} — "
                        f"too small to be worth the operational cost of running it")

    # --- survives more than one window ------------------------------------
    # The criterion that replaces "raise the PSR floor". Luck scales with
    # dispersion, so any single-window threshold can be cleared by a lucky draw
    # from a volatile basket — measured, not theorised: random strategies cleared
    # v1 about half the time. What a lucky draw cannot do is repeat across
    # independent folds, so consistency is the test and its ABSENCE is a failure
    # rather than a waiver.
    wf = walkforward or {}
    measurable = wf.get("folds_measurable")
    retained = wf.get("folds_retained")
    checks["walkforward_folds_measurable"] = measurable
    checks["walkforward_folds_retained"] = retained
    checks["walkforward_median_retention"] = wf.get("median_retention")
    # HOW MANY folds this window had to supply, scaled to the window it
    # actually covered. Identical to the constant at 30 months and stricter in
    # proportion beyond it — see ``folds_required`` for the measured table and
    # the reason the anchor is the strategy's clock rather than the calendar.
    need = folds_required(wf, criteria)
    checks["walkforward_folds_required"] = need
    required_folds = int(need["required"])
    # HOW DEEP the belt was allowed to look, and how much of that depth the
    # candidate's own containers could actually be fed. Recorded rather than
    # recomputed — the gate cannot know an algorithm's bar URL — and recorded
    # as an ABSENCE when the belt did not say, because a verdict that cannot
    # state its window is not interpretable later.
    hist = wf.get("history_floor")
    if isinstance(hist, dict):
        checks["walkforward_history_floor"] = {
            "effective": hist.get("effective"),
            "binding_leg": hist.get("binding_leg"),
            "data_path": hist.get("data_path"),
            "deepened": hist.get("deepened"),
            "folds_before_data_path_reach":
                wf.get("folds_before_data_path_reach"),
            # Carried so an UNCOUNTABLE reach cannot be read as "no fold was
            # starved" — the count above is None in that case, and a None with
            # no sentence beside it is exactly how an absence becomes a zero
            # in the next reader's head.
            "folds_before_data_path_reach_note":
                wf.get("folds_before_data_path_reach_note"),
        }
    elif wf:
        checks["walkforward_history_floor"] = {
            "effective": None,
            "note": ("this walk-forward does not say how far back it was "
                     "allowed to reach — judged before the per-candidate "
                     "floor existed, so the window is UNSTATED, not default"),
        }
    if c.get("require_walkforward"):
        if not wf:
            failures.append("no walk-forward test — a single held-out window is "
                            "one draw, and random strategies cleared the old "
                            "single-window bar about half the time")
        elif wf.get("not_testable"):
            # A separate verdict, not a failure. A slow strategy on short history
            # has not been examined, and calling that a failure is the same error
            # as reading a no-trade holdout as a lost edge.
            checks["not_testable"] = True
            failures.append(
                f"NOT TESTABLE on the history available: {wf.get('note')}. This "
                f"is not a judgement about the strategy — it says the fund cannot "
                f"yet examine a rule this slow, and the answer is a faster rule or "
                f"more history, not a different threshold")
        elif (measurable or 0) < required_folds:
            # Distinct from failing it. Too few measurable folds means the test
            # did not happen, which is not the same as happening and going badly.
            failures.append(
                f"only {measurable or 0} fold(s) could be measured, below the "
                f"{required_folds} required — the consistency test "
                f"did not run, which is not the same as passing it"
                + (f" (the floor is {need['anchor_folds']} folds per "
                   f"{need['anchor_span_days']} days of covered window and this "
                   f"candidate covered {need['covered_days']})"
                   if need.get("scaled") else ""))
        else:
            share = (retained or 0) / measurable
            checks["walkforward_retained_share"] = round(share, 3)
            # STRICT majority, in integer arithmetic, deliberately not a float
            # share compared with `<`. v3 tested `share < 0.5`, which PASSES 1 of
            # 2 — and 1 of 2 is not a majority, while the comment above the
            # criterion claimed it was. Integer arithmetic here so the off-by-one
            # cannot come back: `retained * 2 <= measurable` fails 1/2, 2/4 and
            # 2/5, and passes 2/2, 3/4 and 3/5.
            if (retained or 0) * 2 <= measurable:
                failures.append(
                    f"kept its edge in only {retained} of {measurable} "
                    f"independent folds ({share:.0%}) — not a majority, which is "
                    f"consistent with a lucky window rather than an edge")

    # THE CLAIM TYPE, recorded on every verdict including the alpha ones, so
    # the record can be read without knowing which version introduced the
    # field. Capture in `checks` rather than at the top level: the top-level
    # shape of an alpha verdict is unchanged by this version.
    checks["claim_type"] = declared
    if not known:
        # Fail closed, in BOTH directions: an unrecognised word is judged by
        # the alpha bar (so it cannot pick up the premia criterion) and fails
        # anyway (so it cannot quietly inherit the alpha one either).
        checks["claim_type_recognised"] = False
        failures.append(
            f"unrecognised claim type {declared!r} — a candidate is judged as "
            f"{' or '.join(CLAIM_TYPES)}, and a bar selected by a typo is not "
            f"a bar. Judged against the alpha criteria here, and failed for "
            f"the declaration rather than for the evidence")
    # CAPTURE ONLY, both claim types: the volatility lever the validator
    # measured at 12x, made visible. See `volatility_check`.
    checks["volatility"] = volatility_check(result)
    return {
        # A premia verdict is stamped with the premia bar's own version. An
        # alpha verdict is stamped v4.3 and is byte-identical to v4.3 — the
        # criteria dict, the failures and the version all unchanged.
        "gate_version": GATE_VERSION_PREMIA if is_premia else GATE_VERSION,
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "criteria": c,
        "verdict": ("clears every criterion — worth a human look, which is a "
                    "different claim from 'deploy it'"
                    if not failures else
                    f"fails {len(failures)} of the bar"),
    }
