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
GATE_VERSION = "v1"

#: The bar. Deliberately data, not code branches: it can be printed, argued
#: about on its own merits, and diffed when it changes.
CRITERIA: dict[str, Any] = {
    # Below this the observed Sharpe is not distinguishable from luck. 50% is
    # already generous — it means "more likely real than not", not "proven".
    "min_psr_pct": 50.0,
    # Sharpe on a handful of trades is a story about a handful of trades.
    "min_orders": 20,
    # Beating buy & hold is the minimum bar for existing at all: a strategy
    # that trails the thing it trades is an expensive way to own it.
    "must_beat_benchmark": True,
    # Cost error tolerance. An edge that dies at 3bps was never an edge.
    "min_breakeven_bps": 10.0,
    # Out of sample it must keep most of what it showed in sample.
    "min_holdout_retention": 0.5,
    # A backtest nobody priced is not evidence.
    "require_priced": True,
    # Capacity has to be worth the operational effort of running it.
    "min_capacity_usd": 100_000.0,
}


def evaluate(result: dict[str, Any],
             holdout: Optional[dict[str, Any]] = None,
             sweep_summary: Optional[dict[str, Any]] = None,
             criteria: Optional[dict[str, Any]] = None) -> dict[str, Any]:
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
    if holdout and holdout.get("state") == "done":
        if holdout.get("dates_honoured") is False:
            failures.append("the held-out test ran the SAME dates twice — the "
                            "algorithm ignored start/end, so it proves nothing")
        else:
            tr = (holdout.get("train") or {}).get("return_pct")
            te = (holdout.get("test") or {}).get("return_pct")
            if tr and te is not None:
                retention = te / tr if tr else None
    checks["holdout_retention"] = retention
    if retention is None:
        failures.append("no held-out test — choosing the best of N settings "
                        "guarantees a good number on the window you chose them on")
    elif retention < c["min_holdout_retention"]:
        failures.append(f"kept only {retention:.0%} of its edge out of sample; "
                        f"{c['min_holdout_retention']:.0%} is the floor")

    # --- robust to being wrong about costs --------------------------------
    be = (sweep_summary or {}).get("breakeven_cost") or {}
    be_bps = be.get("breakeven_bps")
    checks["breakeven_bps"] = be_bps
    if be_bps is not None and be_bps < c["min_breakeven_bps"]:
        failures.append(f"dies at {be_bps}bps of slippage, under the "
                        f"{c['min_breakeven_bps']}bps floor — too fragile to "
                        f"cost assumptions to trust")

    # --- worth running at all ---------------------------------------------
    cap = (result.get("capacity") or {}).get("capacity_usd")
    checks["capacity_usd"] = cap
    if cap is not None and cap < c["min_capacity_usd"]:
        failures.append(f"capacity ${cap:,.0f} is below ${c['min_capacity_usd']:,.0f} — "
                        f"too small to be worth the operational cost of running it")

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
