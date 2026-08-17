"""Put the strategies the fund actually holds through the belt.

Three strategies are deployed and every one carries `backtested=None`. They
predate the gate entirely, so the money in the book is governed by exactly the
standards the rest of the system exists to replace — and one of them, the INTC
mean-reversion, has a recorded verdict of "kept 0% of its edge out of sample"
that was almost certainly an artifact of warm-up starvation rather than a
finding.

This produces evidence, not a decision. Flattening or keeping a position is a
human click and nothing here takes it. What it removes is the excuse of not
knowing.

Judged under BOTH bars, deliberately. v1 is what these were implicitly held
against, and v2 is what a candidate would face today; showing them together makes
the gate's own change visible rather than asserted, and stops a v2 failure being
read as news about the strategy when it may be news about the bar.
"""
import json
import os
import sys
import time

import requests
from dotenv import load_dotenv

load_dotenv()

B = "http://127.0.0.1:8090/api/v1/fund"

#: algorithm -> (the position it stands behind, a small grid to sweep)
BOOK = {
    "mean_reversion_cyclicals": ("INTC", {"period": ["10", "14", "21"]}),
    "momentum_large_cap_tech": ("NVDA", {"slow": ["25", "50"]}),
    "trend_sector_commodity": ("SPY", {"slow": ["26", "40"]}),
}

HOLDOUT = {"train_start": "2025-01-01", "train_end": "2025-12-31",
           "test_start": "2026-01-01", "test_end": "2026-08-14"}

ONLY = sys.argv[1] if len(sys.argv) > 1 else None


def submit(algo: str, grid: dict) -> str:
    src = open(f"lean_workspace/algorithms/{algo}/main.py", encoding="utf-8").read()
    requests.post(f"{B}/lean/algorithms", json={"name": algo, "code": src},
                  timeout=120).raise_for_status()
    r = requests.post(f"{B}/factory/candidates",
                      json={"algorithm": algo, "grid": grid,
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
    out = []
    for algo, (position, grid) in BOOK.items():
        if ONLY and ONLY != algo:
            continue
        print(f"\n=== {algo}  (holds {position}) ===", flush=True)
        try:
            cid = submit(algo, grid)
        except Exception as e:  # noqa: BLE001
            print(f"  submit failed: {e}", flush=True)
            out.append({"algorithm": algo, "position": position,
                        "state": "submit_failed", "error": str(e)[:200]})
            continue
        print(f"  candidate {cid} running (grid + holdout + folds) ...", flush=True)
        c = await_candidate(cid)
        v = c.get("verdict") or {}
        ch = v.get("checks") or {}
        row = {
            "algorithm": algo, "position": position,
            "candidate_id": cid, "state": c.get("state"),
            "passed_v2": c.get("passed"),
            "failures_v2": c.get("failures") or [],
            "winner": c.get("winner"),
            "return_pct": ch.get("return_pct"),
            "benchmark_pct": ch.get("benchmark_pct"),
            "psr_pct": ch.get("psr_pct"),
            "orders": ch.get("orders"),
            "holdout_retention": ch.get("holdout_retention"),
            "wf_measurable": ch.get("walkforward_folds_measurable"),
            "wf_retained": ch.get("walkforward_folds_retained"),
            "wf_median": ch.get("walkforward_median_retention"),
            "capacity_usd": ch.get("capacity_usd"),
        }
        # The same evidence re-scored against the old bar, so the change in the
        # gate is visible rather than something the reader has to take on trust.
        if v:
            try:
                from app.fund.gate import CRITERIA_V1, evaluate
                v1 = evaluate(
                    {"total_return_pct": ch.get("return_pct"),
                     "benchmark_return_pct": ch.get("benchmark_pct"),
                     "capacity": {"capacity_usd": ch.get("capacity_usd")},
                     "robustness": {"total_orders": ch.get("orders"),
                                    "psr_pct": ch.get("psr_pct"),
                                    "costs": {"slippage_modelled": ch.get("priced")}}},
                    {"state": "done", "dates_honoured": True,
                     "train": {"return_pct": 1.0},
                     "test": {"return_pct": ch.get("holdout_retention") or 0.0,
                              "total_orders": ch.get("orders")}},
                    None, criteria=CRITERIA_V1)
                row["passed_v1_rescored"] = v1["passed"]
                row["failures_v1_rescored"] = v1["failures"]
            except Exception as e:  # noqa: BLE001
                row["v1_rescore_error"] = str(e)[:160]
        out.append(row)
        print(f"  v2 passed={row['passed_v2']}  return={row['return_pct']} "
              f"vs bench={row['benchmark_pct']}  psr={row['psr_pct']}  "
              f"folds={row['wf_retained']}/{row['wf_measurable']}", flush=True)
        for f in row["failures_v2"]:
            print(f"    - {f}", flush=True)

    print("\n" + "=" * 68, flush=True)
    print("THE BOOK, RE-JUDGED", flush=True)
    print("=" * 68, flush=True)
    for r in out:
        verdict = ("PASSES v2" if r.get("passed_v2") else
                   "FAILS v2" if r.get("passed_v2") is False else
                   f"UNJUDGED ({r.get('state')})")
        print(f"\n  {r['algorithm']} -> holds {r['position']}: {verdict}", flush=True)
        if r.get("return_pct") is not None:
            print(f"    {r['return_pct']}% vs {r['benchmark_pct']}% for owning it; "
                  f"PSR {r['psr_pct']}%", flush=True)
        for f in (r.get("failures_v2") or [])[:4]:
            print(f"    - {f}", flush=True)

    with open("docs/book_rejudged.json", "w") as fh:
        json.dump({"holdout": HOLDOUT, "results": out}, fh, indent=1)
    print("\n  written to docs/book_rejudged.json", flush=True)
    print("\n  NOTHING HERE FLATTENS ANYTHING. Every position change is a human", flush=True)
    print("  click, and the PDT counter leaves one day trade before the flag.", flush=True)


if __name__ == "__main__":
    main()
