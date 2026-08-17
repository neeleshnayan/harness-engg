"""Find the smallest real edge gate v2 can actually detect.

The null audit bounded the gate from below: v1 passed noise half the time, so v2
raised the bar. That leaves the opposite question unanswered and it is not a
smaller one — a floor no genuine edge could clear would ALSO reject every null,
and from failures alone the two are indistinguishable. A gate that rejects
everything is as broken as one that accepts everything; it just looks like rigour
while doing it.

So: dial in a KNOWN edge and see where the gate starts saying yes.
`oracle_calibration_only` ranks names by returns that have not happened yet, with
probability `foresight`. At 0.0 it is the null; at 1.0 it is perfect
foreknowledge. Everything between is a strategy whose edge size we chose rather
than hoped for.

The output is a detection threshold: the foresight level at which v2 first passes.
Read it as "an edge this large is detectable on the history we have". If that
level is high — if only near-perfect foresight clears the bar — then v2 is
measuring history length rather than skill, and the honest response is a v3 with
a written reason, not a shrug.

Every run here is a calibration instrument and never a proposal. The digest
excludes `oracle_calibration_only` by name for exactly that reason.
"""
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

B = "http://127.0.0.1:8090/api/v1/fund"
ALGO = "oracle_calibration_only"

#: Coarse bracket first. Each level is a full candidate — grid, holdout, and
#: three walk-forward folds, all serialised behind one engine slot — so this is
#: minutes per level and a fine sweep would be an hour for precision the
#: conclusion does not need.
LEVELS = [float(x) for x in (sys.argv[1].split(",") if len(sys.argv) > 1
                             else ["0.0", "0.5", "1.0"])]

GRID = {"top_n": ["3", "5"]}
HOLDOUT = {"train_start": "2025-01-01", "train_end": "2025-12-31",
           "test_start": "2026-01-01", "test_end": "2026-08-14"}


def submit(foresight: float) -> str:
    src = open(f"lean_workspace/algorithms/{ALGO}/main.py", encoding="utf-8").read()
    requests.post(f"{B}/lean/algorithms",
                  json={"name": ALGO, "code": src}, timeout=120).raise_for_status()
    grid = {**GRID, "foresight": [str(foresight)], "seed": ["1"]}
    r = requests.post(f"{B}/factory/candidates",
                      json={"algorithm": ALGO, "grid": grid,
                            "holdout": HOLDOUT, "observation_ids": []},
                      timeout=120)
    r.raise_for_status()
    return r.json()["candidate_id"]


def await_candidate(cid: str, timeout_s: float = 7_200.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        c = requests.get(f"{B}/factory/candidates/{cid}", timeout=60).json()
        if c.get("state") != "running":
            return c
        time.sleep(15)
    return {"state": "timeout", "candidate_id": cid}


def main() -> None:
    results = []
    for fs in LEVELS:
        print(f"\n=== foresight {fs} ===", flush=True)
        try:
            cid = submit(fs)
        except Exception as e:  # noqa: BLE001
            print(f"  submit failed: {e}", flush=True)
            results.append({"foresight": fs, "state": "submit_failed"})
            continue
        print(f"  candidate {cid} running (grid + holdout + folds) ...", flush=True)
        c = await_candidate(cid)
        v = c.get("verdict") or {}
        ch = v.get("checks") or {}
        row = {"foresight": fs, "candidate_id": cid, "state": c.get("state"),
               "passed": c.get("passed"), "failures": c.get("failures") or [],
               "psr_pct": ch.get("psr_pct"),
               "return_pct": ch.get("return_pct"),
               "benchmark_pct": ch.get("benchmark_pct"),
               "holdout_retention": ch.get("holdout_retention"),
               "wf_measurable": ch.get("walkforward_folds_measurable"),
               "wf_retained": ch.get("walkforward_folds_retained"),
               "wf_median": ch.get("walkforward_median_retention")}
        results.append(row)
        print(f"  passed={row['passed']} psr={row['psr_pct']} "
              f"ret={row['return_pct']} folds={row['wf_retained']}/"
              f"{row['wf_measurable']}", flush=True)
        for f in row["failures"]:
            print(f"    - {f}", flush=True)

    print("\n" + "=" * 66, flush=True)
    print("ORACLE AUDIT - the smallest edge gate v2 detects", flush=True)
    print("=" * 66, flush=True)
    judged = [r for r in results if r.get("passed") is not None]
    if not judged:
        print("  no level was judged - no calibration produced, which is an "
              "absence of evidence and not a clean bill of health", flush=True)
        return
    print(f"  {'foresight':>10} {'passed':>7} {'PSR':>8} {'return':>9} "
          f"{'folds':>7}", flush=True)
    for r in judged:
        print(f"  {r['foresight']:>10} {str(r['passed']):>7} "
              f"{str(r['psr_pct']):>8} {str(r['return_pct']):>9} "
              f"{r['wf_retained']}/{r['wf_measurable']:>5}", flush=True)

    passing = [r for r in judged if r["passed"]]
    if not passing:
        print("\n  NOTHING PASSED, INCLUDING PERFECT FORESIGHT (if tested).",
              flush=True)
        print("  That is not rigour. A gate no real edge can clear is measuring",
              flush=True)
        print("  the length of our history, not skill, and needs a v3 with a",
              flush=True)
        print("  written reason - the same rule that produced v2.", flush=True)
    else:
        lo = min(r["foresight"] for r in passing)
        print(f"\n  DETECTION THRESHOLD: foresight >= {lo}", flush=True)
        print(f"  An edge of that size is detectable on the history we have.",
              flush=True)
        if lo >= 1.0:
            print("  But ONLY perfect foreknowledge cleared it, which means the",
                  flush=True)
            print("  bar is not usefully clearable by anything real.", flush=True)

    out = "docs/oracle_audit_results.json"
    with open(out, "w") as fh:
        json.dump({"levels": LEVELS, "grid": GRID, "holdout": HOLDOUT,
                   "results": results}, fh, indent=1)
    print(f"\n  written to {out}", flush=True)


if __name__ == "__main__":
    main()
