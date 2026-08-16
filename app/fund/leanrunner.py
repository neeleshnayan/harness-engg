"""LEAN orchestration — the engine as a harness service, not a CLI ritual.

Drives the open-source LEAN engine in Docker directly (no QuantConnect
account; their CLI's login gates their cloud, which we never touch). The
harness owns algorithms as files, runs backtests as async jobs, and parses
the engine's results back into the shapes the fund already speaks — so a
LEAN backtest can become a strategy's recorded promise via the same
``record_backtest`` path as everything else. One engine of record.

Sandbox model, stated plainly: Lab-submitted code is arbitrary Python and it
RUNS. The container is the sandbox — algorithm mounted read-only, no
credentials or signal token in the environment, wall-clock timeout enforced
with ``docker kill``. Lab code can reach the spine's read endpoints exactly
like any process on this machine; it cannot propose (no token) and cannot
reach the venue (no keys).
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

IMAGE = os.getenv("LEAN_IMAGE", "quantconnect/lean:latest")
WORKSPACE = Path(os.getenv("LEAN_WORKSPACE_DIR", "lean_workspace"))
JOB_TIMEOUT_S = float(os.getenv("LEAN_JOB_TIMEOUT", "300"))

_CLASS_RE = re.compile(r"class\s+(\w+)\s*\(\s*QCAlgorithm\s*\)")
_NAME_RE = re.compile(r"^[a-z0-9_\-]{1,64}$")


class LeanError(Exception):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeanRunner:
    """Algorithms on disk, jobs in memory, the engine in Docker.

    Jobs are in-memory by design: a backtest is a computation, not fund
    state. Losing the job table on restart costs a re-run, never a fact.
    """

    def __init__(self, workspace: Path | None = None,
                 docker_cmd: Optional[list[str]] = None):
        self._ws = Path(workspace or WORKSPACE)
        (self._ws / "algorithms").mkdir(parents=True, exist_ok=True)
        (self._ws / "results").mkdir(parents=True, exist_ok=True)
        # Injectable for tests: replaces ["docker"] with a fake executable.
        self._docker = docker_cmd or ["docker"]
        self._jobs: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    # --- algorithms ---------------------------------------------------------

    def save_algorithm(self, name: str, code: str) -> dict[str, Any]:
        if not _NAME_RE.match(name or ""):
            raise LeanError(f"bad algorithm name {name!r} — lowercase, digits, _ or -")
        m = _CLASS_RE.search(code or "")
        if not m:
            raise LeanError("no `class X(QCAlgorithm)` found — LEAN needs an algorithm class")
        d = self._ws / "algorithms" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "main.py").write_text(code, encoding="utf-8")
        return {"name": name, "class_name": m.group(1), "saved_at": _now(),
                "path": str(d / "main.py")}

    def list_algorithms(self) -> list[dict[str, Any]]:
        out = []
        for d in sorted((self._ws / "algorithms").iterdir()):
            f = d / "main.py"
            if f.is_file():
                code = f.read_text(encoding="utf-8")
                m = _CLASS_RE.search(code)
                out.append({"name": d.name,
                            "class_name": m.group(1) if m else None,
                            "lines": code.count("\n") + 1,
                            "modified_at": datetime.fromtimestamp(
                                f.stat().st_mtime, tz=timezone.utc).isoformat()})
        return out

    def get_algorithm(self, name: str) -> dict[str, Any]:
        f = self._ws / "algorithms" / name / "main.py"
        if not f.is_file():
            raise LeanError(f"unknown algorithm {name!r}")
        return {"name": name, "code": f.read_text(encoding="utf-8")}

    # --- jobs ----------------------------------------------------------------

    def submit_backtest(self, algorithm: str) -> dict[str, Any]:
        algo = self.get_algorithm(algorithm)  # raises on unknown
        m = _CLASS_RE.search(algo["code"])
        if not m:
            raise LeanError("algorithm lost its QCAlgorithm class")
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "algorithm": algorithm, "class_name": m.group(1),
            "state": "queued", "submitted_at": _now(),
            "started_at": None, "finished_at": None,
            "error": None, "result": None, "log_tail": [],
        }
        with self._lock:
            self._jobs[job_id] = job
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return {"job_id": job_id, "state": "queued"}

    def job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            j = self._jobs.get(job_id)
        if j is None:
            raise LeanError(f"unknown job {job_id!r} — jobs do not survive a restart; re-run")
        return dict(j)

    def jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {k: v for k, v in j.items() if k != "result"}
                for j in sorted(self._jobs.values(),
                                key=lambda x: x["submitted_at"], reverse=True)
            ]

    # --- the engine run ------------------------------------------------------

    def _run(self, job_id: str) -> None:
        job = self._jobs[job_id]
        algo_dir = (self._ws / "algorithms" / job["algorithm"]).resolve()
        res_dir = (self._ws / "results" / job_id).resolve()
        res_dir.mkdir(parents=True, exist_ok=True)
        container = f"lean-job-{job_id}"

        cmd = self._docker + [
            "run", "--rm", "--name", container,
            "--add-host=host.docker.internal:host-gateway",
            "-v", f"{algo_dir}:/Algorithm:ro",
            "-v", f"{res_dir}:/Results",
            IMAGE,
            "--environment", "backtesting",
            "--algorithm-language", "Python",
            "--algorithm-type-name", job["class_name"],
            "--algorithm-location", "/Algorithm/main.py",
            "--results-destination-folder", "/Results",
            "--close-automatically", "true",
        ]
        job["state"] = "running"
        job["started_at"] = _now()
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=JOB_TIMEOUT_S,
            )
            tail = (proc.stdout or "").splitlines()[-40:]
            job["log_tail"] = tail
            if proc.returncode != 0:
                job["state"] = "failed"
                job["error"] = ((proc.stderr or "").strip().splitlines() or ["engine exited nonzero"])[-1][:400]
            else:
                job["result"] = self._parse_results(res_dir)
                job["state"] = "done" if job["result"] else "failed"
                if not job["result"]:
                    job["error"] = "engine finished but wrote no parsable results"
        except subprocess.TimeoutExpired:
            job["state"] = "failed"
            job["error"] = f"timed out after {JOB_TIMEOUT_S:.0f}s — engine killed"
            subprocess.run(self._docker + ["kill", container],
                           capture_output=True, timeout=30)
        except Exception as e:  # noqa: BLE001
            job["state"] = "failed"
            job["error"] = f"{type(e).__name__}: {e}"[:400]
        finally:
            job["finished_at"] = _now()
            job["wall_seconds"] = round(time.monotonic() - t0, 1)

    # --- results -------------------------------------------------------------

    @staticmethod
    def _parse_results(res_dir: Path) -> Optional[dict[str, Any]]:
        """LEAN's results JSON -> the fund's vocabulary.

        The engine writes <AlgorithmName>.json with statistics and charts.
        Only what the fund already speaks is extracted; everything else stays
        on disk for anyone who wants the raw file.
        """
        candidates = [p for p in res_dir.glob("*.json")
                      if not p.name.endswith(("-order-events.json", "-summary.json",
                                              "alpha-results.json"))]
        best = None
        for p in candidates:
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(d, dict) and ("statistics" in d or "Statistics" in d):
                best = d
                break
        if best is None:
            return None

        stats = best.get("statistics") or best.get("Statistics") or {}

        def _pct(key: str) -> Optional[float]:
            v = stats.get(key)
            if v is None:
                return None
            try:
                return float(str(v).replace("%", "").replace("$", "").replace(",", ""))
            except ValueError:
                return None

        equity: list[float] = []
        charts = best.get("charts") or best.get("Charts") or {}
        se = charts.get("Strategy Equity") or {}
        series = (se.get("series") or se.get("Series") or {})
        eq = series.get("Equity") or {}
        for pt in (eq.get("values") or eq.get("Values") or []):
            # points arrive as [ts, open, high, low, close] or [ts, value]
            if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                equity.append(float(pt[-1]))
        if len(equity) > 400:
            step = len(equity) / 400
            equity = [equity[int(i * step)] for i in range(399)] + [equity[-1]]

        return {
            "engine": "lean",
            "statistics": stats,
            "total_return_pct": _pct("Net Profit"),
            "sharpe": _pct("Sharpe Ratio"),
            "max_drawdown_pct": _pct("Drawdown"),
            "total_trades": _pct("Total Orders") or _pct("Total Trades"),
            "equity_curve": equity,
            "raw_files": sorted(p.name for p in res_dir.glob("*")),
        }
