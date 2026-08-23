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
            "last_test_end": str(last.get("test_end")),
            "first_train_start": str(first.get("train_start"))}


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
    every plan v4.2 could produce (six folds price at four, which is the
    anchor), and it binds only where the extension has bought folds term one
    does not price.

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
    out["binding_term"] = ("anchor" if out["required"] == anchor else
                           "days" if by_days >= by_folds else "folds")
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
#:   shipped geometry     algos  v4.2 plan  v4.3 plan   FP v4.2  FP v4.3   diff
#:   floor 2024-02-26      14      4f/4       4f/4       2.95%    2.95%   +0.00pp
#:   floor 2021-03-02       2      4f/4      12f/9       2.95%    2.90%   -0.05pp
#:
#:   power at Sharpe 1.0: 22.18% -> 22.18% (unchanged) and 22.18% -> 39.91%.
#:   n=20,000 paired draws, seed 7717; paired SE 0.16pp on the false-pass
#:   difference and 0.42pp on the power difference. An independent run at
#:   n=6,000 seed 2026 agreed: +0.00pp and -0.13pp on false-pass, 22.63% ->
#:   39.88% on power.
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
GATE_VERSION = "v4.3"

#: The bar. Deliberately data, not code branches: it can be printed, argued
#: about on its own merits, and diffed when it changes.
CRITERIA: dict[str, Any] = {
    # Raised from 50%. Measured nulls reached ~57% on this history, so 50% was
    # inside the noise. This is a floor, not the load-bearing test — see the
    # walk-forward criteria, which is what actually separates signal here.
    "min_psr_pct": 65.0,
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


def evaluate(result: dict[str, Any],
             holdout: Optional[dict[str, Any]] = None,
             sweep_summary: Optional[dict[str, Any]] = None,
             criteria: Optional[dict[str, Any]] = None,
             walkforward: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Apply the bar. Returns failures in plain sentences, not a score.

    An input that is MISSING fails rather than passes. A candidate that was
    never held out has not survived a holdout, and treating absent evidence as
    satisfied evidence is how a factory quietly lowers its own bar.
    """
    c = {**CRITERIA, **(criteria or {})}
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
    psr = rb.get("psr_pct")
    checks["psr_pct"] = psr
    if psr is None or psr < c["min_psr_pct"]:
        failures.append(f"probabilistic Sharpe {psr if psr is not None else 'unknown'}% "
                        f"is below {c['min_psr_pct']}% — the edge is not "
                        f"distinguishable from luck on this much history")

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
    if c["must_beat_benchmark"]:
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

    return {
        "gate_version": GATE_VERSION,
        "passed": not failures,
        "failures": failures,
        "checks": checks,
        "criteria": c,
        "verdict": ("clears every criterion — worth a human look, which is a "
                    "different claim from 'deploy it'"
                    if not failures else
                    f"fails {len(failures)} of the bar"),
    }
