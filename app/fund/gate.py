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
GATE_VERSION = "v2"

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
    # MAJORITY of independent folds, which is the property a lucky window cannot
    # supply and the reason this replaces "raise the PSR floor" as the real test.
    "min_walkforward_folds": 3,
    "min_walkforward_folds_retained_share": 0.5,
    "require_walkforward": True,
    # A backtest nobody priced is not evidence.
    "require_priced": True,
    # Capacity has to be worth the operational effort of running it.
    "min_capacity_usd": 100_000.0,
    # NEW in v2: and it must have been estimated. Same hole as breakeven.
    "require_capacity_measured": True,
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
            elif tr and te is not None:
                retention = te / tr if tr else None
    checks["holdout_retention"] = retention
    if no_holdout_trades:
        failures.append("the held-out test placed no trades at all, so it says "
                        "nothing either way — usually the algorithm needs more "
                        "history than the test window gives it, so it never "
                        "warmed up. Give it warm-up and re-run before believing "
                        "any out-of-sample number")
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
        elif (measurable or 0) < c["min_walkforward_folds"]:
            # Distinct from failing it. Too few measurable folds means the test
            # did not happen, which is not the same as happening and going badly.
            failures.append(
                f"only {measurable or 0} fold(s) could be measured, below the "
                f"{c['min_walkforward_folds']} required — the consistency test "
                f"did not run, which is not the same as passing it")
        else:
            share = (retained or 0) / measurable
            if share < c["min_walkforward_folds_retained_share"]:
                failures.append(
                    f"kept its edge in only {retained} of {measurable} "
                    f"independent folds ({share:.0%}), under the "
                    f"{c['min_walkforward_folds_retained_share']:.0%} floor — "
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
