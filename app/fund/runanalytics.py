"""The evidence a verdict was computed from, kept so a human can check it.

The belt already measured everything a person needs to validate a run — an
equity curve against its benchmark, the fills, the cost sweep, the per-fold
walk-forward rows with each fold's own reason for being measurable or not. It
then threw all of it away. `CandidateFactory._run` computed `walk`, handed it to
the gate, and let it fall out of scope; the verification job's parsed result
lived only in `fund_lean_jobs`, keyed by a job id the candidate row never
recorded. What survived was the verdict: three failure sentences and a dozen
scalar `checks`.

That is the difference between "the gate says no" and "here is why, look".
The CEO's words, three times over on 2026-08-21: *"i can see
monthend_rebalance_flow but cant see the analytics behind"*. He is right, and
the cause was never that the analytics did not exist.

So this module is the ENVELOPE: one JSON document per candidate, written in the
same statement as the verdict, holding exactly what the belt saw. Two properties
carry the design.

**The verdict and its evidence are written together.** Capturing analytics on a
second pass would let the two drift — a re-read job, a re-run fold — and a
verdict whose evidence disagrees with it is worse than a verdict with none,
because it reassures.

**Absence stays typed.** There are four distinct reasons a candidate can have
nothing to show, and collapsing them into an empty panel would be the same error
this fund has fixed four times in other places:

  * ``NOT_CAPTURED``  — the run predates this envelope. 37 candidates in the
    live store are in exactly this state and always will be; re-running is the
    only way to see them, and the UI must say so rather than render a blank.
  * ``PRUNED``        — captured, then aged out by the retention policy. The
    tombstone is written IN PLACE of the payload, never as NULL, so pruned and
    never-captured cannot be confused.
  * ``UNAVAILABLE``   — the belt tried and failed (the walk-forward crashed, the
    verification job returned no result). A named failure.
  * ``NOT_TESTABLE``  — the fund's history cannot examine a rule this slow. Not
    a failure of anything; it is a fact about our data.

None of the four is zero, and none of them is the others.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

#: Bumped when the shape below changes incompatibly, so a stored envelope says
#: which reader can read it. Same reasoning as GATE_VERSION: an old document has
#: to stay interpretable rather than be reinterpreted by today's code.
ANALYTICS_SCHEMA = "v1"

#: Fills kept per run. The verification run for entry 11 placed 254 across 5.47
#: years, and a sweep point places tens — so this is roughly 4x the largest real
#: run measured on this belt, chosen to be a guard against a pathological
#: intraday algorithm rather than a limit anything normal reaches. Truncation is
#: ANNOUNCED (see ``orders_truncated``): an order list silently cut in half would
#: make the fills panel lie about what the strategy did.
MAX_ORDERS = 1_000

#: Engine-container paths (``/Results/...``). They are debug material that stops
#: resolving the moment the results directory is pruned — which happens within a
#: day — so storing them in the durable envelope would preserve a broken link.
_DROP_FROM_RESULT = ("raw_files",)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def trim_result(result: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """The engine's parsed result, minus what does not survive storage.

    Returns None for a missing result rather than ``{}``: an empty dict renders
    as "ran and produced nothing", which is a different claim from "there is no
    result here".
    """
    if not result:
        return None
    out = {k: v for k, v in result.items() if k not in _DROP_FROM_RESULT}
    orders = out.get("orders")
    if isinstance(orders, list) and len(orders) > MAX_ORDERS:
        out["orders_total"] = len(orders)
        out["orders_truncated"] = True
        out["orders_truncated_note"] = (
            f"{len(orders)} fills were placed; the first {MAX_ORDERS} are stored. "
            f"The statistics above are the engine's own and cover ALL of them — "
            f"only this table is cut")
        out["orders"] = orders[:MAX_ORDERS]
    return out


def trim_sweep_point(point: dict[str, Any]) -> dict[str, Any]:
    """One grid row, as the cost-sweep band needs it.

    The sweep's points are already trimmed by ``leanrunner._sweep_point``; this
    only guards against a point that carried a full result through some future
    change, because the cost band renders one line per point and a thousand-point
    grid is capped upstream at MAX_SWEEP_POINTS anyway.
    """
    keep = ("parameters", "state", "error", "total_return_pct", "sharpe",
            "max_drawdown_pct", "psr_pct", "total_orders", "window")
    return {k: point.get(k) for k in keep if k in point}


def absent(reason: str, note: str, **extra: Any) -> dict[str, Any]:
    """A typed absence. Never a bare None, never an empty dict.

    ``reason`` is one of the four machine-readable constants; ``note`` is the
    sentence a person reads. Both, always: a code with no sentence sends the
    reader to the source, and a sentence with no code makes the UI branch on
    prose.
    """
    return {"present": False, "reason": reason, "note": note, **extra}


NOT_CAPTURED = "not_captured"
PRUNED = "pruned"
UNAVAILABLE = "unavailable"
NOT_TESTABLE = "not_testable"

#: What a candidate judged before this envelope existed carries. Written by the
#: READER rather than stored, because backfilling 37 rows would be inventing a
#: capture that never happened.
NOT_CAPTURED_NOTE = (
    "this candidate was judged before the belt kept its analytics, so the "
    "equity curve, the fills and the per-fold rows are gone — the verdict below "
    "is the whole of what was stored. Re-run it to see the evidence")


def capture(*, job: Optional[dict[str, Any]],
            sweep: Optional[dict[str, Any]],
            walkforward: Optional[dict[str, Any]],
            walkforward_note: Optional[str] = None) -> dict[str, Any]:
    """Everything the belt saw, in one document, at the moment of the verdict.

    Every leg is optional and every missing leg is TYPED. A candidate whose
    walk-forward crashed and one whose walk-forward was never asked for produce
    different documents, because they demand different next actions: re-run one,
    supply a holdout to the other.
    """
    return {
        "schema": ANALYTICS_SCHEMA,
        "captured_at": _now(),
        "verification": _verification(job),
        "sweep": _sweep(sweep),
        "walkforward": _walkforward(walkforward, walkforward_note),
    }


def _verification(job: Optional[dict[str, Any]]) -> dict[str, Any]:
    """The winner's full re-run — the one that carries costs, benchmark, capacity.

    Named `verification` rather than `backtest` because that is its role in the
    belt: the sweep's own rows are trimmed and unenriched, and judging one would
    waive most of the bar. This is the run the verdict was actually computed on.
    """
    if not job:
        return absent(UNAVAILABLE,
                      "the verification run never returned — no equity curve, "
                      "no fills, no costs disclosure")
    result = trim_result(job.get("result"))
    if result is None:
        return absent(
            UNAVAILABLE,
            f"the verification run ended {job.get('state') or 'in an unknown state'} "
            f"and produced no parsable result"
            + (f": {job['error']}" if job.get("error") else ""),
            job_id=job.get("job_id"), state=job.get("state"))
    return {
        "present": True,
        "job_id": job.get("job_id"),
        "state": job.get("state"),
        "wall_seconds": job.get("wall_seconds"),
        "parameters": job.get("parameters"),
        "result": result,
    }


def _sweep(sweep: Optional[dict[str, Any]]) -> dict[str, Any]:
    """The grid, its winner, and the cost band.

    The cost band is the part with no other home. ``breakeven_cost`` lives in the
    sweep summary and the gate reads one scalar out of it; the SHAPE — return at
    each slip, and which side it stayed on when it never crossed — is what tells
    a reader whether an edge dies at 3bps or at 50, and it was reachable only by
    querying Postgres by hand.
    """
    if not sweep:
        return absent(UNAVAILABLE, "no sweep was recorded for this candidate")
    points = [trim_sweep_point(p) for p in (sweep.get("points") or [])]
    return {
        "present": True,
        "sweep_id": sweep.get("sweep_id"),
        "state": sweep.get("state"),
        "total": sweep.get("total"),
        "completed": sweep.get("completed"),
        "summary": sweep.get("summary"),
        "points": points,
        "holdout": sweep.get("holdout"),
        "holdout_result": sweep.get("holdout_result"),
    }


def _walkforward(walk: Optional[dict[str, Any]],
                 note: Optional[str]) -> dict[str, Any]:
    """The folds, each with its own measurable/unmeasurable reason.

    The rows the quant had to reconstruct "from sweeps by grid-key luck"
    (run-quant-entry11, accepted 2026-08-21). They existed in memory for the
    length of one gate call.
    """
    if not walk:
        return absent(UNAVAILABLE,
                      note or "the walk-forward leg produced no result, and no "
                              "reason was recorded — which is itself a gap")
    if walk.get("not_testable"):
        return absent(NOT_TESTABLE,
                      walk.get("note") or "the available history cannot supply "
                                          "enough folds for a rule this slow",
                      hold_days=walk.get("hold_days"),
                      hold_days_source=walk.get("hold_days_source"))
    return {"present": True, **walk}


# --- reading it back --------------------------------------------------------


def pruned(when: Optional[str] = None,
           retention_days: Optional[float] = None) -> dict[str, Any]:
    """The tombstone written IN PLACE of a payload the retention policy removed.

    Deliberately not NULL. A NULL is indistinguishable from a candidate that
    never captured anything, and the two send a reader to different places: one
    is re-runnable evidence that expired, the other never existed.
    """
    return {
        "schema": ANALYTICS_SCHEMA,
        "captured_at": None,
        "pruned": True,
        "pruned_at": when or _now(),
        "retention_days": retention_days,
        "note": ("the engine payload for this run was removed by the retention "
                 "policy — it was captured and has aged out, which is not the "
                 "same as never having been measured. Re-run to see it again"),
    }


def view(analytics: Optional[dict[str, Any]]) -> dict[str, Any]:
    """What a reader gets, including when there is nothing to read.

    One shape, always, so no consumer has to branch on null before it can branch
    on content. `available` is the only boolean a caller needs; `reason` and
    `note` say which of the four absences it is when it is false.
    """
    if not analytics:
        return {"available": False, "reason": NOT_CAPTURED,
                "note": NOT_CAPTURED_NOTE}
    if analytics.get("pruned"):
        return {"available": False, "reason": PRUNED,
                "note": analytics.get("note") or pruned()["note"],
                "pruned_at": analytics.get("pruned_at")}
    return {"available": True, **analytics}


def folds(analytics: Optional[dict[str, Any]]) -> Optional[list[dict[str, Any]]]:
    """The per-fold rows, or None when there are none TO return.

    None rather than `[]`, and the distinction is the whole point: an empty list
    reads as "the walk-forward ran and found no folds", which is a claim about
    the strategy. None says the rows are not here — ask ``view()`` why.
    """
    wf = ((analytics or {}).get("walkforward")) or {}
    rows = wf.get("folds")
    return rows if isinstance(rows, list) and rows else None


def daily_return_legs(analytics: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Every captured strategy-vs-benchmark daily series, by leg name.

    The reader gate v5 will use (adversary round 4, recommendation 4). Gathers
    what the belt actually captured and — the load-bearing half — names what it
    did NOT, so a premia statistic computed over three legs when five were
    expected is visibly that rather than silently narrower.

    Leg names are stable: ``verification`` (the winner's full re-run),
    ``holdout_test``, and ``fold_N_test`` per walk-forward fold. Train legs are
    deliberately absent everywhere — their jobs are released after the grid runs
    and re-running one would be a different run from the one the numbers came
    from. That absence is reported, not hidden.
    """
    a = analytics or {}
    legs: dict[str, Any] = {}
    missing: list[str] = []

    ver = (a.get("verification") or {})
    vr = (ver.get("result") or {}) if ver.get("present") else {}
    dr = vr.get("daily_returns")
    if isinstance(dr, dict) and dr.get("present"):
        legs["verification"] = dr
    else:
        missing.append("verification")

    ho = ((a.get("sweep") or {}).get("holdout_result") or {})
    hd = (ho.get("test") or {}).get("daily_returns")
    if isinstance(hd, dict) and hd.get("present"):
        legs["holdout_test"] = hd
    else:
        missing.append("holdout_test")

    for f in (folds(a) or []):
        name = f"fold_{f.get('fold')}_test"
        fd = f.get("daily_returns")
        if isinstance(fd, dict) and fd.get("present"):
            legs[name] = fd
        else:
            missing.append(name)

    with_bench = [k for k, v in legs.items() if v.get("benchmark_present")]
    return {
        "legs": legs,
        "captured": sorted(legs),
        "missing": missing,
        "legs_with_benchmark": sorted(with_bench),
        "total_observations": sum(int(v.get("n") or 0) for v in legs.values()),
        "note": (
            f"{len(legs)} leg(s) carry an aligned daily series"
            + (f"; {len(with_bench)} of them include the benchmark"
               if legs else "")
            + (f". NOT captured: {', '.join(missing)}" if missing else "")
            + ". Train legs are never captured — their jobs are released after "
              "the grid runs, and a re-run would be a different run"
            if legs or missing else "nothing captured"),
    }
