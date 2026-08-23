"""Run strategies with no information in them through the belt.

The gate has failed every candidate it has ever judged. Read one way that is
rigour; read another it is a bar nothing could clear on two years of daily data.
Nobody has been able to tell those apart, which means "the gate works" has been
an assumption sitting underneath every verdict the fund has produced.

This measures it from one side. A random-entry strategy has no edge by
construction, so every one of them MUST fail. Any that passes is a leak in the
harness rather than a discovery - look-ahead in the feed, a cost model that does
not bite, or survivorship in the universe doing the work - and the pass rate over
enough seeds IS the false-positive rate.

The audit deliberately gives each null the SAME treatment a real candidate gets,
including grid selection on the training window. That is not incidental: picking
the best of six settings on one window is precisely where an overfit comes from,
so a calibration that skipped it would be testing a gentler process than the one
in use.

What this cannot show is that the gate is not too STRICT - a floor no real edge
could clear would also fail every null. That is the injected-edge audit's job;
the two bound the gate from opposite sides.
"""
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

# The preflight imports the fund's own fold geometry rather than reimplementing it,
# so the audit and the gate cannot disagree about what is testable. That needs the
# repo root importable — every other script under scripts/ does the same.
sys.path.insert(0, ".")

load_dotenv()

B = "http://127.0.0.1:8090/api/v1/fund"
ALGO = "null_random_smallcap"
SEEDS = [int(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1
                          else ["1", "2", "3", "4", "5"])]

#: The same shape of grid a real candidate is swept over, so the selection
#: pressure is identical. Seed is held fixed within a candidate: it identifies
#: the null, and varying it inside the grid would let the sweep pick the luckiest
#: coin rather than the best setting.
#: Holds are all TESTABLE on our history, and that is the whole point of the
#: change. The first v4 run used ["21", "63"] and produced a completely useless
#: result: every one of the six nulls came back NOT TESTABLE, because under v4 a
#: 63-day hold needs a 252-day test leg times four folds and ~30 months cannot
#: supply that. The audit reported "0% false positive rate" while its own
#: walk-forward block said "NO null reached a walk-forward result, so this audit
#: says NOTHING about the load-bearing criterion".
#:
#: The 0% was real and measured the rules UPSTREAM of walk-forward — PSR, the
#: benchmark comparison, the cost-sweep requirement. It was not the number the
#: audit exists to produce.
#:
#: From the fold-geometry table in gate.py: a 5-day hold fits 6 folds, 10 fits 6,
#: 21 fits exactly 4 — which is v4's minimum. 42 fits 2 and 63 fits 1, so both are
#: unjudgeable here and belong in an audit only when there is more history.
GRID = {"top_n": ["3", "5"], "hold_days": ["5", "10", "21"]}
HOLDOUT = {"train_start": "2025-01-01", "train_end": "2025-12-31",
           "test_start": "2026-01-01", "test_end": "2026-08-14"}


def submit(seed: int) -> str:
    src = open(f"lean_workspace/algorithms/{ALGO}/main.py", encoding="utf-8").read()
    r = requests.post(f"{B}/lean/algorithms",
                      json={"name": ALGO, "code": src}, timeout=120)
    r.raise_for_status()
    # The seed rides along as a fixed parameter on every grid point.
    grid = {**GRID, "seed": [str(seed)]}
    r = requests.post(f"{B}/factory/candidates",
                      json={"algorithm": ALGO, "grid": grid,
                            "holdout": HOLDOUT, "observation_ids": []},
                      timeout=120)
    r.raise_for_status()
    return r.json()["candidate_id"]


def await_candidate(cid: str, timeout_s: float = 5_400.0) -> dict:
    """Poll until the candidate settles, surviving a spine restart.

    An audit run of six nulls is hours of container time, and the first attempt
    lost all of it: the spine was restarted mid-poll and the unhandled
    ConnectionError took the whole script down. The CANDIDATE was unaffected — the
    factory runs it server-side — so the crash discarded work that had already
    been done, purely because the observer went away.

    Connection failures are therefore retried for as long as the deadline allows,
    while the candidate's own outcome is never retried or inferred. A run that
    genuinely times out still returns ``state: timeout``, which the report counts
    as unjudged rather than as a pass or a fail.
    """
    deadline = time.monotonic() + timeout_s
    unreachable_since = None
    while time.monotonic() < deadline:
        try:
            c = requests.get(f"{B}/factory/candidates/{cid}", timeout=60).json()
            if unreachable_since is not None:
                print(f"    spine back after "
                      f"{time.monotonic() - unreachable_since:.0f}s", flush=True)
                unreachable_since = None
            if c.get("state") != "running":
                return c
        except requests.exceptions.RequestException as e:
            if unreachable_since is None:
                unreachable_since = time.monotonic()
                print(f"    spine unreachable ({type(e).__name__}) — the candidate "
                      f"keeps running server-side, so this waits rather than "
                      f"discarding hours of container time", flush=True)
        time.sleep(10)
    return {"state": "timeout", "candidate_id": cid}


def preflight() -> None:
    """Refuse to run if the grid cannot reach the criterion being audited.

    The first v4 run burned container time to produce "0% false positive rate"
    alongside its own admission that no null had reached the walk-forward leg. The
    number was true and answered a different question than the one asked.

    A two-hour measurement that CANNOT produce its headline result should fail in
    the first second, not the last. So every hold in the grid is checked against
    the same fold geometry the gate uses, and a hold that cannot yield
    `min_walkforward_folds` aborts the run with the arithmetic shown.

    IT RUNS THE BELT'S OWN FLOOR PATH, NOT THE RAW CONSTANT (D20 repair). Until
    D20 this read `WALKFORWARD_HISTORY_FLOOR` directly, which since gate v4.3 is
    the FEED's start (1993) and not the depth any candidate is allowed — the
    belt ratchets that per candidate in `factory.effective_history_floor`. A
    calibration instrument planning a window the belt would never plan measures
    a gate the fund does not run, and the whole point of this preflight is that
    the audit and the gate cannot disagree about what is testable. It also
    iterates the SAME fold-requirement fixed point the belt iterates, because
    under v4.3 the requirement and the window size each other.
    """
    from datetime import date

    from app.fund.factory import effective_history_floor
    from app.fund.gate import CRITERIA, GATE_VERSION, folds_required
    from app.fund.walkforward import window_for_strategy

    anchor = int(CRITERIA.get("min_walkforward_folds") or 0)
    today = date.today().isoformat()
    code = None
    try:
        with open(f"lean_workspace/algorithms/{ALGO}/main.py",
                  encoding="utf-8") as fh:
            code = fh.read()
    except OSError as e:
        print(f"  (could not read {ALGO}/main.py: {e} — the data-path leg will "
              f"read UNKNOWN, which ratchets the floor rather than deepening "
              f"it)", flush=True)
    history = effective_history_floor(code, today)
    print(f"preflight against gate {GATE_VERSION}: anchor is {anchor} measurable "
          f"folds; window floor {history['effective']} "
          f"(binding leg: {history['binding_leg']})", flush=True)
    bad = []
    for h in sorted({int(x) for x in GRID.get("hold_days", [])}):
        need = anchor
        w = window_for_strategy(today, hold_days=h, min_folds=need,
                                floor=history["effective"])
        for _ in range(4):
            req = int(folds_required({"requested_folds": w["folds"]})["required"])
            if req <= need:
                break
            need = req
            w = window_for_strategy(today, hold_days=h, min_folds=need,
                                    floor=history["effective"])
        fits = len(w["folds"])
        enough = fits >= need
        mark = "ok" if enough else "NOT TESTABLE"
        print(f"  hold {h:>3}d -> {fits} fold(s) of {w['test_days']}d, "
              f"needs {need}   {mark}", flush=True)
        if not enough:
            bad.append((h, fits, w["test_days"]))
    if bad:
        detail = "; ".join(f"{h}-day hold fits {f} fold(s) of {t}d"
                           for h, f, t in bad)
        raise SystemExit(
            f"\nABORTING before spending container time.\n\n"
            f"These holds cannot be judged on the history available ({detail}), so "
            f"every null carrying them would return NOT TESTABLE and the audit "
            f"would report a false-positive rate for the criteria UPSTREAM of "
            f"walk-forward while saying nothing about walk-forward itself.\n\n"
            f"That is exactly what the previous run did. Either narrow GRID's "
            f"hold_days to values that fit, or buy history — do not lower the "
            f"gate to make the audit runnable, which would be calibrating the "
            f"instrument to the measurement.")
    print("  all holds are judgeable on this history\n", flush=True)


def main() -> None:
    preflight()
    results = []
    for seed in SEEDS:
        print(f"\n=== null seed {seed} ===", flush=True)
        try:
            cid = submit(seed)
        except Exception as e:  # noqa: BLE001
            print(f"  submit failed: {e}", flush=True)
            results.append({"seed": seed, "state": "submit_failed",
                            "error": str(e)[:200]})
            continue
        print(f"  candidate {cid} running ...", flush=True)
        c = await_candidate(cid)
        passed = c.get("passed")
        # The walk-forward leg, recorded per null. The BELT has always run it —
        # factory.py calls _walkforward for every candidate — this script simply
        # never wrote it down, so no null audit has ever reported the behaviour of
        # the criterion that replaced PSR as the load-bearing one. An outside
        # review read that as "null_audit has no walk-forward leg", which was the
        # right smell from slightly the wrong evidence: the leg runs, nobody
        # recorded it, and the audit had not been re-run since it existed.
        wf = c.get("walkforward") or {}
        results.append({"seed": seed, "candidate_id": cid,
                        "state": c.get("state"), "passed": passed,
                        "failures": c.get("failures"),
                        "winner": c.get("winner"),
                        "wf_measurable": wf.get("folds_measurable"),
                        "wf_retained": wf.get("folds_retained"),
                        "wf_not_testable": bool(wf.get("not_testable")),
                        "wf_note": (wf.get("note") or "")[:160]})
        print(f"  state={c.get('state')} passed={passed} "
              f"walkforward={wf.get('folds_retained')}/{wf.get('folds_measurable')}"
              f"{' NOT-TESTABLE' if wf.get('not_testable') else ''}", flush=True)
        for f in (c.get("failures") or []):
            print(f"    - {f}", flush=True)

    print("\n" + "=" * 64, flush=True)
    judged = [r for r in results if r.get("state") == "done"
              and r.get("passed") is not None]
    passes = [r for r in judged if r["passed"]]
    unjudged = [r for r in results if r not in judged]
    print(f"NULL AUDIT: {len(judged)} of {len(results)} nulls were judged", flush=True)
    if unjudged:
        # Kept separate from failures on purpose: a null that crashed was never
        # examined, and counting it as a pass or a fail would both be wrong.
        print(f"  {len(unjudged)} could not be judged (crash/timeout) - these are "
              f"NOT evidence either way", flush=True)
        for r in unjudged:
            print(f"    seed {r['seed']}: {r.get('state')} {str(r.get('error'))[:80]}",
                  flush=True)
    if not judged:
        print("  no null was judged - the audit produced no calibration, which is "
              "an absence of evidence and not a clean bill of health", flush=True)
        return
    rate = len(passes) / len(judged)
    print(f"  passes: {len(passes)}  ->  FALSE POSITIVE RATE {rate:.0%}", flush=True)
    if passes:
        print("\n  A NULL PASSED. This is a leak, not a discovery - look for "
              "look-ahead in the feed, a cost model that does not bite, or "
              "survivorship doing the work:", flush=True)
        for r in passes:
            print(f"    seed {r['seed']}: candidate {r['candidate_id']} "
                  f"winner {r.get('winner')}", flush=True)
    else:
        print("\n  No null passed. The gate is not trivially leaky - it still "
              "may be too strict, which only the injected-edge audit can say.",
              flush=True)
    # Which criteria did the work? A gate that only ever fires one rule is a
    # one-rule gate wearing five, and worth knowing about.
    from collections import Counter
    fired = Counter()
    for r in judged:
        for f in (r.get("failures") or []):
            fired[f.split("-")[0].split(",")[0].strip()[:60]] += 1
    print("\n  which criteria actually fired:", flush=True)
    for crit, n in fired.most_common():
        print(f"    {n:2d}x {crit}", flush=True)

    # What the walk-forward leg actually did. If every null died upstream of it,
    # this audit says nothing about the criterion the gate leans on hardest.
    reached = [r for r in judged if r.get("wf_measurable") is not None]
    nt = [r for r in reached if r.get("wf_not_testable")]
    print("", flush=True)
    print("  the walk-forward leg on these nulls:", flush=True)
    if not reached:
        print("    NO null reached a walk-forward result, so this audit says "
              "NOTHING about the load-bearing criterion — it measured the rules "
              "upstream of it.", flush=True)
    else:
        print(f"    {len(reached)} reached it; {len(nt)} came back NOT TESTABLE "
              f"(which is not a failure)", flush=True)
        for r in reached:
            print(f"      seed {r['seed']}: retained {r.get('wf_retained')} of "
                  f"{r.get('wf_measurable')} measurable folds", flush=True)

    # The honest bound. A handful of nulls cannot resolve a small rate, and
    # "0 of 6 passed, so the rate is 0%" is the absence-is-zero error wearing a
    # statistic. One-sided 95% upper bound given zero observed passes.
    n = len(judged)
    if not passes and n:
        upper = (1.0 - 0.05 ** (1.0 / n)) * 100.0
        print("", flush=True)
        print(f"  BOUND, stated rather than implied: 0 of {n} nulls passed, so the "
              f"true rate is under {upper:.0f}% at 95% confidence. That is the "
              f"resolution {n} LEAN runs buys — NOT a claim of zero. Bounding it "
              f"under 10% needs about 29 clean nulls.", flush=True)
        print("  The PRECISE estimate lives in scripts/gate_power_audit.py (2.9% "
              "over 4,000 draws). This run checks what that simulation cannot "
              "see: whether the REAL belt leaks — look-ahead in the feed, a cost "
              "model that does not bite, survivorship doing the work.", flush=True)

    out = "docs/null_audit_results.json"
    with open(out, "w") as fh:
        json.dump({"seeds": SEEDS, "grid": GRID, "holdout": HOLDOUT,
                   "results": results,
                   "judged": len(judged), "passes": len(passes),
                   "false_positive_rate": rate,
                   "walkforward_reached": len(reached),
                   "walkforward_not_testable": len(nt)}, fh, indent=1)
    print(f"\n  written to {out}", flush=True)


if __name__ == "__main__":
    main()
