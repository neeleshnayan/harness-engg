"""Did the parallelism actually buy anything? Measure it, do not assume it.

The constraint this fund quoted for a week - "one LEAN container, 15.2 GB, ~230
hours for a population" - turned out to be two separate mistakes stacked. A
container was capped at 3 GiB while using ~450 MiB, and the belt ran its grid
points in a plain `for` loop, so raising the container limit alone would have
changed nothing. Both are fixed. Neither fix means anything until it is measured.

So this runs the SAME sweep twice against the REAL engine, once serialised and once
concurrent, and reports the ratio. Three things are recorded rather than inferred:

  * wall clock for each arm, so the speedup is observed and not predicted
  * PEAK CONCURRENT CONTAINERS, sampled from docker, because a concurrency claim
    that never verifies overlap is the same class of error as the semaphore bump
    that would have done nothing
  * PEAK MEMORY per container, which is the number the original 3 GiB reservation
    got wrong by 7x and the reason a wrong answer here is expensive

Run with the spine stopped, or its scheduler will compete for the same slots and
both arms will be measuring contention instead of concurrency.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import threading
import time

sys.path.insert(0, ".")

ALGO = "momentum_large_cap_tech"


def _sampler(stop: threading.Event, out: list[dict]) -> None:
    """Poll docker for live LEAN containers and their memory."""
    while not stop.is_set():
        try:
            ids = subprocess.run(
                ["docker", "ps", "-q", "--filter", "name=lean-job"],
                capture_output=True, text=True, timeout=20).stdout.split()
            mems = []
            if ids:
                stats = subprocess.run(
                    ["docker", "stats", "--no-stream", "--format",
                     "{{.MemUsage}}", *ids],
                    capture_output=True, text=True, timeout=30).stdout
                for line in stats.strip().splitlines():
                    used = line.split("/")[0].strip()
                    try:
                        n = float(used.rstrip("aAbBiIkKmMgG"))
                        if used.upper().endswith("GIB") or used.upper().endswith("GB"):
                            n *= 1024.0
                        mems.append(n)
                    except ValueError:
                        pass
            out.append({"at": time.monotonic(), "live": len(ids), "mems": mems})
        except Exception:  # noqa: BLE001
            pass
        stop.wait(1.5)


def _arm(concurrency: int, points: int, workspace) -> dict:
    """One arm of the A/B. Reloads the runner so the semaphore is rebuilt."""
    import importlib

    import app.fund.leanrunner as lr
    importlib.reload(lr)
    lr.MAX_CONCURRENT_CONTAINERS = concurrency
    lr._ENGINE_SLOTS = threading.BoundedSemaphore(concurrency)

    r = lr.LeanRunner(workspace=workspace)
    grid = {"fast": [str(5 + i) for i in range(points)]}

    samples: list[dict] = []
    stop = threading.Event()
    t = threading.Thread(target=_sampler, args=(stop, samples), daemon=True)
    t.start()

    t0 = time.monotonic()
    sid = r.submit_sweep(ALGO, grid)["sweep_id"]
    deadline = t0 + 3600
    state = "running"
    while time.monotonic() < deadline:
        s = r.sweep(sid)
        state = s.get("state")
        if state in ("done", "failed"):
            break
        time.sleep(1.0)
    wall = time.monotonic() - t0
    stop.set()
    t.join(timeout=5)

    sweep = r.sweep(sid)
    peak_live = max((s["live"] for s in samples), default=0)
    all_mem = [m for s in samples for m in s["mems"]]
    return {
        "concurrency": concurrency, "points": points, "state": state,
        "wall_seconds": round(wall, 1),
        "points_completed": len(sweep.get("points") or []),
        "peak_concurrent_containers": peak_live,
        "peak_container_mib": round(max(all_mem), 1) if all_mem else None,
        "median_container_mib": (round(statistics.median(all_mem), 1)
                                 if all_mem else None),
        "samples": len(samples),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--points", type=int, default=4,
                    help="grid points per arm; must exceed 1 to show anything")
    ap.add_argument("--concurrency", type=int, default=4)
    a = ap.parse_args()

    import pathlib

    ws = pathlib.Path("lean_workspace")
    if not (ws / "algorithms" / ALGO).exists():
        print(f"algorithm {ALGO} not in {ws}/algorithms — cannot benchmark")
        return 1

    print(f"A/B on the real engine: {a.points} grid points, algorithm {ALGO}")
    print("Stop the spine first, or its scheduler competes for the same slots.\n")

    serial = _arm(1, a.points, ws)
    print(f"  serial     : {serial['wall_seconds']:>7.1f}s  "
          f"peak containers {serial['peak_concurrent_containers']}  "
          f"peak mem {serial['peak_container_mib']} MiB  "
          f"({serial['points_completed']}/{a.points} points, {serial['state']})")

    par = _arm(a.concurrency, a.points, ws)
    print(f"  concurrent : {par['wall_seconds']:>7.1f}s  "
          f"peak containers {par['peak_concurrent_containers']}  "
          f"peak mem {par['peak_container_mib']} MiB  "
          f"({par['points_completed']}/{a.points} points, {par['state']})")

    print()
    if serial["state"] != "done" or par["state"] != "done":
        print("  ONE ARM DID NOT COMPLETE — no speedup is claimed. An arm that "
              "failed is not a slow arm.")
        return 1
    if par["peak_concurrent_containers"] <= 1:
        print("  NEVER SAW MORE THAN ONE CONTAINER ALIVE. Whatever the clock says, "
              "this did not run concurrently — do not report a speedup.")
        return 1

    speedup = serial["wall_seconds"] / max(par["wall_seconds"], 1e-9)
    ideal = min(a.concurrency, a.points)
    print(f"  SPEEDUP {speedup:.2f}x  (ideal {ideal}x at {a.points} points and "
          f"{a.concurrency} slots -> {100 * speedup / ideal:.0f}% of ideal)")
    print(f"  Efficiency below ideal is expected: container start-up and the "
          f"holdout run after the grid are both serial.")
    print()
    # Read the cap rather than restating it. An earlier version printed "against a
    # 1 GiB cap" from a literal, and kept printing it after the cap moved to 768m —
    # a benchmark that misreports its own configuration is worse than no benchmark.
    import app.fund.leanrunner as _lr
    cap = _lr.CONTAINER_MEMORY
    print(f"  Memory: peak {par['peak_container_mib']} MiB per container against a "
          f"{cap} cap. The original cap reserved 3g while using ~450 MiB.")
    if par["peak_container_mib"]:
        cap_mib = (float(cap.rstrip("gGmM")) *
                   (1024.0 if cap.lower().endswith("g") else 1.0))
        print(f"  Sizing rule is slots x CAP <= free RAM, which must hold even if "
              f"every container claimed its ceiling: "
              f"{a.concurrency} x {cap_mib:.0f} MiB = "
              f"{a.concurrency * cap_mib / 1024:.1f} GiB.")
        print(f"  Observed usage would allow ~"
              f"{int(5100 / par['peak_container_mib'])} containers, but sizing on "
              f"observed rather than reserved is what caused WinError 1455.")

    out = "docs/parallelism_bench.json"
    with open(out, "w") as fh:
        json.dump({"serial": serial, "concurrent": par,
                   "speedup": round(speedup, 3),
                   "ideal": ideal}, fh, indent=1)
    print(f"\n  written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
