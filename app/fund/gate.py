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
GATE_VERSION = "v4"

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
    if c["must_beat_benchmark"]:
        if strat is None or bench is None:
            failures.append("no benchmark to compare against — 'better than "
                            "nothing' is not the question")
        elif strat <= bench:
            failures.append(f"returns {strat}% against {bench}% for simply "
                            f"owning it: an expensive way to hold the underlying")

    # --- survives data it was not chosen on -------------------------------
    retention = None
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
            elif tr and te is not None:
                retention = te / tr if tr else None
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
        failures.append("no held-out test — choosing the best of N settings "
                        "guarantees a good number on the window you chose them on")
    elif retention < c["min_holdout_retention"]:
        failures.append(f"kept only {retention:.0%} of its edge out of sample; "
                        f"{c['min_holdout_retention']:.0%} is the floor")

    # --- robust to being wrong about costs --------------------------------
    be = (sweep_summary or {}).get("breakeven_cost") or {}
    be_bps = be.get("breakeven_bps")
    checks["breakeven_bps"] = be_bps
    if be_bps is None:
        # v1 let this through, and a null strategy used the gap: never having
        # been cost-swept satisfied the cost-robustness criterion. "Still
        # profitable at every cost tested" is a real answer and is reported as a
        # reason, so the only case left here is genuinely untested.
        if c.get("require_breakeven_measured"):
            reason = be.get("reason") or "no cost sweep was run"
            if "still profitable at every cost tested" in str(reason):
                checks["breakeven_bps"] = "beyond the tested range"
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
        elif (measurable or 0) < c["min_walkforward_folds"]:
            # Distinct from failing it. Too few measurable folds means the test
            # did not happen, which is not the same as happening and going badly.
            failures.append(
                f"only {measurable or 0} fold(s) could be measured, below the "
                f"{c['min_walkforward_folds']} required — the consistency test "
                f"did not run, which is not the same as passing it")
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
