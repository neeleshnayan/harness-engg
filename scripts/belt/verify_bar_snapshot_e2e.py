"""Evidence (b) and (c): the same candidate, both data paths, compared.

Runs ONE algorithm through a real LEAN container twice — once served from a
candidate-scoped bar snapshot, once fetching live per container — and compares
the GATE INPUTS the two runs produce. They must be identical. If they are not,
the cache changes what the gate judges, which is the one outcome that would make
it unshippable however fast it is.

TOPOLOGY, and why it is this shape: the LEAN container fetches its bars over
HTTP from the spine, so the snapshot must be active IN THE PROCESS SERVING THAT
HTTP. That is exactly how production works — ``CandidateFactory._run`` executes
in a thread inside the spine process — so this script starts the spine in a
background thread and drives the runner in the main thread rather than faking
the arrangement.

    python scripts/belt/verify_bar_snapshot_e2e.py

Requires Docker and the LEAN image. Runs the two arms SEQUENTIALLY: a wall-clock
number measured under contention is a corrupted measurement, not a slow one.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

PORT = int(os.getenv("E2E_PORT", "8099"))
ALGO = os.getenv("E2E_ALGO", "monthend_snapshot_probe")

#: The gate's inputs. Compared field by field rather than as one blob so a
#: difference names itself instead of printing two thousand lines of JSON.
GATE_FIELDS = [
    "total_return_pct", "sharpe", "max_drawdown_pct", "win_rate_pct",
    "total_orders", "total_fees", "turnover_pct", "psr", "annual_return_pct",
    "benchmark_return_pct", "benchmark_symbol", "benchmark_kind",
    "benchmark_basis", "benchmark_legs", "benchmark_basket", "capacity",
]


def _write_fixture() -> None:
    """Generate the probe algorithm rather than commit it.

    It is a copy of monthend_rebalance_flow pointing at this script's spine
    instead of the live one on :8090. Generated, not committed, for two reasons:
    a directory under ``lean_workspace/algorithms`` looks exactly like a
    candidate and this is not one, and a committed copy would silently rot the
    moment the real algorithm changed.
    """
    src = ROOT / "lean_workspace" / "algorithms" / "monthend_rebalance_flow" / "main.py"
    dst = ROOT / "lean_workspace" / "algorithms" / ALGO / "main.py"
    code = src.read_text(encoding="utf-8")
    marker = 'SPINE = "http://host.docker.internal:8090/api/v1/fund"'
    if marker not in code:
        raise SystemExit(f"{src} no longer contains the expected SPINE line; "
                         f"the fixture generator needs updating rather than guessing")
    code = code.replace(
        marker, f'SPINE = "http://host.docker.internal:{PORT}/api/v1/fund"')
    # A short window: the question under test is whether two DATA PATHS agree,
    # not how the strategy did, and a 5-year run would cost minutes per arm.
    code = code.replace("DEFAULT_START = (2021, 3, 1)", "DEFAULT_START = (2025, 1, 1)")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(
        "#: GENERATED TEST FIXTURE - not a candidate, do not commit.\n"
        "#: Written by scripts/belt/verify_bar_snapshot_e2e.py.\n" + code,
        encoding="utf-8")


def _start_spine() -> None:
    import uvicorn
    from app.main import app

    cfg = uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning")
    threading.Thread(target=uvicorn.Server(cfg).run, daemon=True).start()
    import urllib.request
    for _ in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/v1/fund/liveness",
                                   timeout=2)
            return
        except Exception:                                           # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"spine did not come up on :{PORT}")


def _flatten(result: dict) -> dict:
    out = {}
    rb = result.get("robustness") or {}
    for f in GATE_FIELDS:
        out[f] = result.get(f, rb.get(f))
    # The curves decide every ratio above; compare them by length and endpoints
    # so a silently shifted window cannot hide behind matching summary stats.
    for key in ("equity_curve", "benchmark_curve", "equity_dates",
                "benchmark_dates"):
        seq = result.get(key) or []
        out[f"{key}__len"] = len(seq)
        out[f"{key}__first"] = seq[0] if seq else None
        out[f"{key}__last"] = seq[-1] if seq else None
    out["benchmark_truncated"] = result.get("benchmark_truncated")
    out["benchmark_feeds"] = result.get("benchmark_feeds")
    return out


def _run_arm(label: str, snapshot_on: bool) -> tuple[dict, float, dict]:
    from app.fund import barcache
    from app.fund.leanrunner import (LeanRunner, _declared_lookback_days,
                                     _declared_universe)

    runner = LeanRunner(workspace=ROOT / "lean_workspace")
    code = runner.get_algorithm(ALGO)["code"]

    snap = None
    if snapshot_on:
        snap = barcache.prefetch(_declared_universe(code), candidate=f"e2e-{label}",
                                 lookback_days=_declared_lookback_days(code))
        print(f"[{label}] prefetched {len(snap.legs)} legs in "
              f"{snap.prefetch_seconds}s")

    t0 = time.monotonic()
    with barcache.activate(snap):
        job_id = runner.submit_backtest(ALGO, {})["job_id"]
        while True:
            job = runner.job(job_id)
            if job.get("state") in ("done", "failed"):
                break
            time.sleep(1.0)
    wall = time.monotonic() - t0

    if job.get("state") != "done":
        print(f"[{label}] FAILED: {job.get('error')}")
        for line in (job.get("log_tail") or [])[-15:]:
            print(f"    {line}")
        raise SystemExit(1)

    rep = snap.report() if snap is not None else {"taken": False}
    print(f"[{label}] container wall {job.get('wall_seconds')}s, "
          f"arm wall {wall:.1f}s, snapshot hits={rep.get('hits')} "
          f"misses={rep.get('miss_count')}")
    return _flatten(job["result"]), wall, rep


def main() -> int:
    _write_fixture()
    _start_spine()
    print(f"spine up on :{PORT}; algorithm {ALGO}\n")

    # DIRECT FIRST, deliberately. Running the cache arm first would leave the
    # vendor's own edge caches warm for the direct arm and flatter the "before"
    # number, which would understate the saving rather than overstate it — but
    # the honest ordering is the one that cannot be accused of either.
    direct, direct_wall, _ = _run_arm("direct", snapshot_on=False)
    cached, cached_wall, rep = _run_arm("cached", snapshot_on=True)

    print("\n--- gate inputs ---")
    diffs = []
    for key in sorted(set(direct) | set(cached)):
        a, b = direct.get(key), cached.get(key)
        if a != b:
            diffs.append((key, a, b))
        else:
            print(f"  MATCH  {key:<28} {a!r}")
    print()
    for key, a, b in diffs:
        print(f"  DIFFER {key:<28} direct={a!r}  cached={b!r}")

    print(f"\ndirect arm : {direct_wall:.1f}s")
    print(f"cached arm : {cached_wall:.1f}s")
    print(f"snapshot   : hits={rep.get('hits')} misses={rep.get('miss_count')} "
          f"prefetch={rep.get('prefetch_seconds')}s")
    print(f"\nfields compared : {len(set(direct) | set(cached))}")
    print(f"fields differing: {len(diffs)}")
    Path("e2e_evidence.json").write_text(json.dumps(
        {"direct": direct, "cached": cached,
         "direct_wall_s": direct_wall, "cached_wall_s": cached_wall,
         "snapshot": rep}, indent=2, default=str), encoding="utf-8")
    return 1 if diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
