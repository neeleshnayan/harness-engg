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
                else:
                    self._add_benchmark(job["result"])
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

    # --- benchmark -----------------------------------------------------------

    @staticmethod
    def _add_benchmark(result: dict[str, Any]) -> None:
        """Buy & hold for the traded symbol, from the fund's own bars.

        LEAN's own Benchmark series is unusable for these algorithms: the data
        is a custom type, so the engine emits zeros rather than a comparison.
        Rather than drop the question, it is answered on the same closes the
        fund marks its book with — the identical feed the algorithm traded, so
        the comparison is like-for-like rather than two vendors disagreeing.

        Best-effort by design: if the bars cannot be fetched, the benchmark
        stays absent. An absent comparison is honest; an invented one is not.
        """
        if result.get("benchmark_curve"):
            return  # the engine produced a real one
        dates = result.get("equity_dates") or []
        orders = result.get("orders") or []
        equity = result.get("equity_curve") or []
        if len(dates) < 2 or not orders or not equity:
            return
        symbols = [o["symbol"] for o in orders if o.get("symbol")]
        if not symbols:
            return
        symbol = max(set(symbols), key=symbols.count)
        try:
            from app.fund.marketdata import fetch_daily_bars
            bars = fetch_daily_bars(symbol, start=dates[0], end=dates[-1])
        except Exception as e:  # noqa: BLE001
            logger.info("benchmark unavailable for %s: %s", symbol, e)
            return
        closes = list(bars.closes or [])
        if len(closes) < 2 or not closes[0]:
            return
        # Normalised to the strategy's starting equity so the two curves are
        # readable on one axis: same money, different decisions.
        start_equity = equity[0]
        curve = [round(start_equity * (c / closes[0]), 2) for c in closes]
        result["benchmark_curve"] = curve
        result["benchmark_dates"] = list(bars.dates or [])
        result["benchmark_return_pct"] = _total_return(curve)
        result["benchmark_symbol"] = symbol
        result["benchmark_source"] = getattr(bars, "source", None)

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

        charts = best.get("charts") or best.get("Charts") or {}
        equity, dates = _curve(charts, "Strategy Equity", "Equity")
        bench, _ = _curve(charts, "Benchmark", "Benchmark")

        # The dates travel WITH the curve. Downstream, "is this alpha or beta"
        # regresses the curve against factor returns by date — an equity series
        # with no dates cannot be evaluated, only admired.
        equity, dates = _downsample2(equity, dates, 400)
        bench, _ = _downsample2(bench, [], 400) if _usable(bench) else ([], [])

        return {
            "engine": "lean",
            "statistics": stats,
            "total_return_pct": _pct("Net Profit"),
            "sharpe": _pct("Sharpe Ratio"),
            "max_drawdown_pct": _pct("Drawdown"),
            "total_trades": _pct("Total Orders") or _pct("Total Trades"),
            "equity_curve": equity,
            "equity_dates": dates,
            # Buy & hold, from the engine's own benchmark series. A strategy
            # that cannot beat owning the thing is not interesting, and that
            # comparison should be impossible to skip.
            "benchmark_curve": bench,
            "benchmark_return_pct": _total_return(bench),
            "orders": _orders(best),
            "raw_files": sorted(p.name for p in res_dir.glob("*")),
        }


def _curve(charts: dict, chart: str, series: str) -> tuple[list[float], list[str]]:
    """One chart series as (values, ISO dates).

    LEAN points arrive as ``[unix_ts, value]`` or ``[unix_ts, o, h, l, c]``;
    the last element is the value in both shapes.
    """
    c = charts.get(chart) or {}
    ser = c.get("series") or c.get("Series") or {}
    s = ser.get(series) or {}
    values: list[float] = []
    dates: list[str] = []
    for pt in (s.get("values") or s.get("Values") or []):
        if not isinstance(pt, (list, tuple)) or len(pt) < 2:
            continue
        # Both or neither: appending the value first and letting the date
        # conversion raise would leave the two lists a different length, and
        # the downsampler drops dates entirely when they fall out of step —
        # so one unconvertible timestamp would silently cost every date.
        try:
            value = float(pt[-1])
            date = datetime.fromtimestamp(
                float(pt[0]), tz=timezone.utc).date().isoformat()
        except (ValueError, TypeError, OSError, OverflowError):
            continue
        values.append(value)
        dates.append(date)
    return values, dates


def _downsample2(values: list[float], dates: list[str],
                 cap: int) -> tuple[list[float], list[str]]:
    """Thin a series to `cap` points, keeping values and dates in step.

    Endpoints are always kept: the first and last points are the two the
    reader actually reasons about.
    """
    n = len(values)
    if n <= cap:
        return values, dates
    step = n / cap
    idx = [int(i * step) for i in range(cap - 1)] + [n - 1]
    return ([values[i] for i in idx],
            [dates[i] for i in idx] if len(dates) == n else [])


def _total_return(curve: list[float]) -> Optional[float]:
    if len(curve) < 2 or not curve[0]:
        return None
    return round((curve[-1] / curve[0] - 1.0) * 100.0, 2)


def _usable(curve: list[float]) -> bool:
    """Is this series a measurement, or the engine's shrug?

    LEAN cannot benchmark an algorithm whose data is a custom type it does not
    recognise — it emits a series of zeros rather than an error. Plotting that
    flatline beside the strategy and labelling it "buy & hold" would invent a
    comparison the engine never made. An unknown is not a zero.
    """
    return len(curve) >= 2 and any(v != 0.0 for v in curve)


def _orders(doc: dict) -> list[dict[str, Any]]:
    """Filled orders, in the fund's vocabulary.

    LEAN keys orders by id and encodes direction as 0=buy, 1=sell and
    status 3=filled. Only fills are reported: an order that never filled
    changed nothing and belongs in the log, not the trade list.
    """
    raw = doc.get("orders") or doc.get("Orders") or {}
    if isinstance(raw, dict):
        raw = list(raw.values())
    out: list[dict[str, Any]] = []
    for o in raw:
        if not isinstance(o, dict) or o.get("status") not in (3, "Filled", "filled"):
            continue
        sym = o.get("symbol")
        out.append({
            "time": o.get("lastFillTime") or o.get("time"),
            "symbol": (sym or {}).get("value") if isinstance(sym, dict) else sym,
            "side": "sell" if o.get("direction") in (1, "Sell", "sell") else "buy",
            "qty": o.get("quantity"),
            "price": o.get("price"),
            "value": o.get("value"),
        })
    out.sort(key=lambda x: str(x.get("time") or ""))
    return out
