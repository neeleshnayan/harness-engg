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

import itertools
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


#: Each sweep point is a full engine container (~10s), so a grid is minutes,
#: not seconds. The cap is a guard against a five-parameter grid nobody meant
#: to ask for.
MAX_SWEEP_POINTS = int(os.getenv("LEAN_MAX_SWEEP_POINTS", "24"))

_PARAM_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,31}$")


class LeanError(Exception):
    pass


def _param_value(v: Any) -> str:
    """LEAN packs the grid point into one comma-separated flag, so a value
    containing a comma or colon would silently split into other parameters."""
    s = str(v).strip()
    if not s:
        raise LeanError("empty parameter value")
    if "," in s or ":" in s:
        raise LeanError(f"parameter value {s!r} cannot contain ',' or ':'")
    return s


def _clean_parameters(parameters: Optional[dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (parameters or {}).items():
        if not _PARAM_KEY_RE.match(str(k)):
            raise LeanError(f"bad parameter name {k!r}")
        out[str(k)] = _param_value(v)
    return out


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _clean_holdout(holdout: Optional[dict[str, str]]) -> Optional[dict[str, str]]:
    """Validate the two windows, and refuse a test window that starts before
    training ends — an overlap would leak the answer into the exam."""
    if not holdout:
        return None
    keys = ("train_start", "train_end", "test_start", "test_end")
    out = {}
    for k in keys:
        v = str(holdout.get(k) or "").strip()
        if not _DATE_RE.match(v):
            raise LeanError(f"holdout {k} must be YYYY-MM-DD, got {v!r}")
        out[k] = v
    if out["train_end"] < out["train_start"] or out["test_end"] < out["test_start"]:
        raise LeanError("holdout windows must end after they start")
    if out["test_start"] < out["train_end"]:
        raise LeanError(
            "the test window starts before training ends — overlapping windows "
            "leak the answer into the exam, so the result would mean nothing")
    return out


def _window_of(job: dict[str, Any]) -> Optional[list[str]]:
    """The dates a run actually covered, per the engine's own equity curve."""
    dates = ((job.get("result") or {}).get("equity_dates")) or []
    return [dates[0], dates[-1]] if len(dates) >= 2 else None


def _sweep_point(params: dict[str, str], job: dict[str, Any]) -> dict[str, Any]:
    """One grid point, flattened to what a comparison needs."""
    res = job.get("result") or {}
    rb = res.get("robustness") or {}
    return {
        "parameters": dict(params),
        "state": job.get("state"),
        "error": job.get("error"),
        "total_return_pct": res.get("total_return_pct"),
        "sharpe": res.get("sharpe"),
        "max_drawdown_pct": res.get("max_drawdown_pct"),
        "psr_pct": rb.get("psr_pct"),
        "total_orders": rb.get("total_orders"),
    }


def breakeven_cost(points: list[dict[str, Any]], param: str = "slip") -> dict[str, Any]:
    """The trading cost at which this edge stops paying.

    A backtest reports its return at ONE cost assumption, and the number is
    only as good as that assumption. The useful question is not "what does
    trading cost" — nobody knows to a basis point — but "how wrong could I be
    about costs before this stops working". A strategy that survives 50bps is
    robust; one that dies at 3bps was never an edge, it was a rounding error
    with good marketing.

    Reads a sweep over a cost parameter and finds where return crosses zero,
    by linear interpolation between the two points that straddle it. Returns
    None when the grid never crosses — and says which side it stayed on,
    because "still profitable at every cost tested" and "unprofitable even for
    free" are opposite findings that a bare None would hide.
    """
    scored = []
    for p in points:
        if p.get("state") != "done" or p.get("total_return_pct") is None:
            continue
        raw = (p.get("parameters") or {}).get(param)
        if raw is None:
            continue
        try:
            scored.append((float(raw), float(p["total_return_pct"])))
        except (TypeError, ValueError):
            continue
    if len(scored) < 2:
        return {"parameter": param, "breakeven": None,
                "reason": "need at least two priced points to interpolate"}

    scored.sort(key=lambda x: x[0])
    for (c0, r0), (c1, r1) in zip(scored, scored[1:]):
        if (r0 > 0) != (r1 > 0):
            # Linear between the straddling points. The curve is not truly
            # linear, but over a basis-point-wide bracket the error is far
            # smaller than the uncertainty in the cost estimate itself.
            span = r0 - r1
            crossing = c0 if span == 0 else c0 + (c1 - c0) * (r0 / span)
            return {"parameter": param,
                    "breakeven": round(crossing, 6),
                    "breakeven_bps": round(crossing * 10_000, 1),
                    "bracket": [c0, c1],
                    "reason": "return crosses zero between these costs"}

    always_positive = all(r > 0 for _, r in scored)
    return {
        "parameter": param, "breakeven": None,
        "tested_range": [scored[0][0], scored[-1][0]],
        "reason": ("still profitable at every cost tested — raise the range to "
                   "find the limit" if always_positive else
                   "unprofitable at every cost tested, including the cheapest"),
    }


def _sweep_summary(points: list[dict[str, Any]]) -> dict[str, Any]:
    """Island or plateau — the only question a sweep exists to answer.

    A grid where one cell shines and its neighbours lose is a fit to this
    particular history. A grid where most of the neighbourhood works may hold
    something real. Reporting only the best cell hides exactly this, and the
    best cell is the one an operator will otherwise reach for.
    """
    scored = [p for p in points
              if p.get("state") == "done" and p.get("total_return_pct") is not None]
    if not scored:
        return {"scored": 0}
    returns = sorted(p["total_return_pct"] for p in scored)
    mid = len(returns) // 2
    median = (returns[mid] if len(returns) % 2
              else (returns[mid - 1] + returns[mid]) / 2)
    best = max(scored, key=lambda p: p["total_return_pct"])
    positive = sum(1 for r in returns if r > 0)
    return {
        "scored": len(scored),
        "failed": len(points) - len(scored),
        "best": best,
        "best_return_pct": round(returns[-1], 2),
        "median_return_pct": round(median, 2),
        "worst_return_pct": round(returns[0], 2),
        "positive_share": round(positive / len(returns), 3),
        # The best point standing far above the median is the signature of a
        # fit: the neighbourhood does not support it.
        "best_minus_median_pct": round(returns[-1] - median, 2),
        # Present only when the grid actually swept a cost parameter, so an
        # ordinary parameter sweep is not decorated with a field about costs it
        # never varied.
        **({"breakeven_cost": be}
           if (be := breakeven_cost(points)).get("breakeven") is not None
           or "tested_range" in be else {}),
    }


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
        self._sweeps: dict[str, dict[str, Any]] = {}
        self._live: dict[str, dict[str, Any]] = {}
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

    def submit_backtest(self, algorithm: str,
                        parameters: Optional[dict[str, Any]] = None,
                        enrich: bool = True) -> dict[str, Any]:
        """Run one backtest.

        ``enrich`` controls the extras that cost a NETWORK call — the buy-and-
        hold benchmark and the capacity estimate. Sweep points set it False:
        twenty-four grid points would otherwise make twenty-four fetches for
        numbers the comparison never reads, which is slow in production and
        was enough to make the suite flaky under load.
        """
        algo = self.get_algorithm(algorithm)  # raises on unknown
        m = _CLASS_RE.search(algo["code"])
        if not m:
            raise LeanError("algorithm lost its QCAlgorithm class")
        parameters = _clean_parameters(parameters)
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "algorithm": algorithm, "class_name": m.group(1),
            "state": "queued", "submitted_at": _now(),
            "started_at": None, "finished_at": None,
            "parameters": parameters,
            "enrich": enrich,
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

    # --- live sessions -------------------------------------------------------

    def start_live(self, algorithm: str, strategy_id: str = "",
                   signal_token: str = "", qty: float = 0.1) -> dict[str, Any]:
        """Run an algorithm in LEAN's live-paper environment, supervised.

        LEAN proposes, never executes — the same rule that governs Clark. The
        container gets a signal token and a strategy id and nothing else: no
        venue credentials, no broker keys. Its entire reach is a POST to the
        spine's token-gated intake, where the proposal joins the approval queue
        behind the risk and compliance gates. The human click stays the only
        path to the venue.

        Two things worth knowing before relying on this:

        * The algorithm MUST set its benchmark to its own custom symbol. LEAN
          otherwise adds a SPY minute subscription of its own accord, and
          live-paper's stub data queue cannot serve it — the run dies with
          "LiveDataQueue has not implemented live data" before a single bar of
          the fund's own data arrives.
        * On daily bars this is a once-a-day event, not a ticking feed. Live
          mode buys supervision and state that survives the day, not latency.
        """
        algo = self.get_algorithm(algorithm)
        m = _CLASS_RE.search(algo["code"])
        if not m:
            raise LeanError("algorithm lost its QCAlgorithm class")
        if "set_benchmark" not in algo["code"]:
            raise LeanError(
                "live mode needs `self.set_benchmark(<your custom symbol>)` — "
                "without it LEAN subscribes to SPY minute bars, which the "
                "live-paper data queue cannot serve, and the session dies at "
                "startup")
        with self._lock:
            running = [s for s in self._live.values() if s["state"] == "running"]
        if running:
            raise LeanError(
                f"a live session is already running ({running[0]['algorithm']}); "
                f"stop it before starting another")

        session_id = uuid.uuid4().hex[:12]
        session = {
            "session_id": session_id, "algorithm": algorithm,
            "class_name": m.group(1), "state": "starting",
            "started_at": _now(), "stopped_at": None,
            "container": f"lean-live-{session_id}",
            "strategy_id": strategy_id,
            # Never the token itself: this dict is returned over the API.
            "signal_configured": bool(strategy_id and signal_token),
            "error": None, "log_tail": [],
        }
        with self._lock:
            self._live[session_id] = session
        threading.Thread(target=self._run_live,
                         args=(session_id, signal_token, qty), daemon=True).start()
        return {"session_id": session_id, "state": "starting",
                "signal_configured": session["signal_configured"]}

    def live_sessions(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(s) for s in sorted(self._live.values(),
                                            key=lambda x: x["started_at"],
                                            reverse=True)]

    def live_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            s = self._live.get(session_id)
        if s is None:
            raise LeanError(f"unknown live session {session_id!r}")
        return dict(s)

    def stop_live(self, session_id: str) -> dict[str, Any]:
        s = self.live_session(session_id)
        subprocess.run(self._docker + ["kill", s["container"]],
                       capture_output=True, timeout=60)
        with self._lock:
            self._live[session_id]["state"] = "stopped"
            self._live[session_id]["stopped_at"] = _now()
        return {"session_id": session_id, "state": "stopped"}

    def _run_live(self, session_id: str, signal_token: str, qty: float) -> None:
        session = self._live[session_id]
        algo_dir = (self._ws / "algorithms" / session["algorithm"]).resolve()
        res_dir = (self._ws / "results" / f"live-{session_id}").resolve()
        res_dir.mkdir(parents=True, exist_ok=True)

        cmd = self._docker + [
            "run", "--rm", "--name", session["container"],
            "--add-host=host.docker.internal:host-gateway",
            "-v", f"{algo_dir}:/Algorithm:ro",
            "-v", f"{res_dir}:/Results",
            "-e", f"SIGNAL_TOKEN={signal_token}",
            "-e", f"STRATEGY_ID={session['strategy_id']}",
            "-e", f"SIGNAL_QTY={qty}",
            IMAGE,
            "--environment", "live-paper",
            "--algorithm-language", "Python",
            "--algorithm-type-name", session["class_name"],
            "--algorithm-location", "/Algorithm/main.py",
            "--results-destination-folder", "/Results",
        ]
        session["state"] = "running"
        try:
            # No timeout: a live session runs until it is stopped. That is the
            # difference between this and a backtest, and the reason the job
            # timeout must not be reused here.
            proc = subprocess.run(cmd, capture_output=True, text=True)
            session["log_tail"] = (proc.stdout or "").splitlines()[-40:]
            if proc.returncode != 0 and session["state"] != "stopped":
                session["state"] = "failed"
                session["error"] = (
                    (proc.stderr or "").strip().splitlines() or ["engine exited nonzero"]
                )[-1][:400]
            elif session["state"] != "stopped":
                session["state"] = "ended"
        except Exception as e:  # noqa: BLE001
            session["state"] = "failed"
            session["error"] = f"{type(e).__name__}: {e}"[:400]
        finally:
            if session["stopped_at"] is None:
                session["stopped_at"] = _now()

    # --- sweeps --------------------------------------------------------------

    def submit_sweep(self, algorithm: str,
                     grid: dict[str, list[Any]],
                     holdout: Optional[dict[str, str]] = None) -> dict[str, Any]:
        """Run one algorithm across a grid of parameters.

        The question a single backtest cannot answer. One good parameter set
        proves nothing — the neighbourhood is what matters. If the winner sits
        alone among losers it is a fit to this history; if its neighbours are
        also decent, there may be something there. Reading one number tells
        you which of those you have only by luck.
        """
        self.get_algorithm(algorithm)  # raises on unknown
        if not grid:
            raise LeanError("no parameters to sweep")
        clean: dict[str, list[str]] = {}
        for key, values in grid.items():
            if not _PARAM_KEY_RE.match(str(key)):
                raise LeanError(f"bad parameter name {key!r}")
            vals = [_param_value(v) for v in (values or [])]
            if not vals:
                raise LeanError(f"parameter {key!r} has no values to try")
            clean[str(key)] = vals

        names = list(clean)
        combos = [dict(zip(names, vals))
                  for vals in itertools.product(*(clean[n] for n in names))]
        if len(combos) > MAX_SWEEP_POINTS:
            raise LeanError(
                f"{len(combos)} combinations is more than the {MAX_SWEEP_POINTS} "
                f"this runs in one go — each point is a full engine run, so a "
                f"large grid costs minutes. Narrow the grid.")

        holdout = _clean_holdout(holdout)
        sweep_id = uuid.uuid4().hex[:12]
        sweep = {
            "sweep_id": sweep_id, "algorithm": algorithm, "grid": clean,
            "state": "running", "submitted_at": _now(), "finished_at": None,
            # +1 for the held-out run of the winner.
            "total": len(combos) + (1 if holdout else 0), "completed": 0,
            "points": [], "error": None,
            "holdout": dict(holdout) if holdout else None,
            "holdout_result": None,
        }
        with self._lock:
            self._sweeps[sweep_id] = sweep
        threading.Thread(target=self._run_sweep, args=(sweep_id, combos),
                         daemon=True).start()
        return {"sweep_id": sweep_id, "state": "running", "total": sweep["total"]}

    def sweep(self, sweep_id: str) -> dict[str, Any]:
        with self._lock:
            s = self._sweeps.get(sweep_id)
        if s is None:
            raise LeanError(f"unknown sweep {sweep_id!r} — sweeps do not survive "
                            f"a restart; re-run")
        return dict(s)

    def _run_point(self, algorithm: str, params: dict[str, str]) -> dict[str, Any]:
        """One engine run, waited out. Sequential on purpose: each point is a
        full container, and running the grid in parallel would have them
        fighting for the same cores — same wall time, different failures."""
        job_id = self.submit_backtest(algorithm, params, enrich=False)["job_id"]
        deadline = time.monotonic() + JOB_TIMEOUT_S + 60
        while time.monotonic() < deadline:
            j = self.job(job_id)
            if j["state"] in ("done", "failed"):
                return j
            time.sleep(1.0)
        return {"state": "failed", "error": "point outlasted its deadline"}

    def _run_sweep(self, sweep_id: str, combos: list[dict[str, str]]) -> None:
        sweep = self._sweeps[sweep_id]
        holdout = sweep.get("holdout")
        try:
            for params in combos:
                run_params = dict(params)
                if holdout:
                    run_params["start"] = holdout["train_start"]
                    run_params["end"] = holdout["train_end"]
                j = self._run_point(sweep["algorithm"], run_params)
                point = _sweep_point(params, j)
                point["window"] = _window_of(j)
                sweep["points"].append(point)
                sweep["completed"] = len(sweep["points"])

            sweep["summary"] = _sweep_summary(sweep["points"])
            if holdout:
                sweep["holdout_result"] = self._run_holdout(sweep, holdout)
                sweep["completed"] = sweep["total"]
            sweep["state"] = "done"
        except Exception as e:  # noqa: BLE001
            sweep["state"] = "failed"
            sweep["error"] = f"{type(e).__name__}: {e}"[:400]
        finally:
            sweep["finished_at"] = _now()
            sweep.setdefault("summary", _sweep_summary(sweep["points"]))

    def _run_holdout(self, sweep: dict[str, Any],
                     holdout: dict[str, str]) -> dict[str, Any]:
        """Run the grid's winner on data it was NOT chosen on.

        This is the only test that can catch the fit. Choosing the best of
        twenty-four settings on one window guarantees a good number on that
        window — the question is whether it survives contact with data that had
        no vote in its selection. A strategy that halves out of sample was
        fitted; one that holds up has earned a second look.
        """
        best = (sweep.get("summary") or {}).get("best")
        if not best:
            return {"state": "skipped",
                    "reason": "no point scored on the training window"}
        params = dict(best["parameters"])
        j = self._run_point(sweep["algorithm"],
                            {**params, "start": holdout["test_start"],
                             "end": holdout["test_end"]})
        point = _sweep_point(params, j)
        point["window"] = _window_of(j)

        train_window = next((p.get("window") for p in sweep["points"]
                             if p.get("parameters") == params and p.get("window")), None)
        # The guard that keeps this honest. If the algorithm ignores the start
        # and end parameters, both runs cover the SAME dates and the "held-out"
        # number is just the training number again — a validation that validates
        # nothing, which is worse than no validation at all because it reassures.
        honoured = bool(train_window and point["window"]
                        and train_window != point["window"])
        return {
            "state": "done" if j.get("state") == "done" else "failed",
            "parameters": params,
            "train": {"window": train_window,
                      "return_pct": best.get("total_return_pct"),
                      "sharpe": best.get("sharpe")},
            "test": {"window": point["window"],
                     "return_pct": point.get("total_return_pct"),
                     "sharpe": point.get("sharpe"),
                     "psr_pct": point.get("psr_pct"),
                     "total_orders": point.get("total_orders")},
            "dates_honoured": honoured,
            "error": point.get("error"),
        }

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
        # LEAN takes the whole grid point in ONE --parameters flag, comma
        # separated. Repeating the flag silently keeps only the first pair —
        # which would run a sweep where every point had the same slow period
        # and nobody would know.
        if job.get("parameters"):
            cmd += ["--parameters",
                    ",".join(f"{k}:{v}" for k, v in job["parameters"].items())]
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
                elif job.get("enrich", True):
                    # Network-backed extras, skipped for sweep points.
                    self._add_benchmark(job["result"])
                    self._add_cost_disclosure(job)
                    self._add_capacity(job["result"])
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

    @staticmethod
    def _add_capacity(result: dict[str, Any]) -> None:
        """How much money this could hold — the number a small fund needs most.

        Uses the symbol the strategy actually traded, and the engine's own
        turnover figure, so this is a property of the STRATEGY rather than of
        the ticker. Best effort: no volume, no estimate, and it says so instead
        of inventing a ceiling nobody checked.
        """
        orders = result.get("orders") or []
        rb = result.get("robustness") or {}
        symbols = [o["symbol"] for o in orders if o.get("symbol")]
        if not symbols:
            return
        symbol = max(set(symbols), key=symbols.count)
        try:
            from app.fund.capacity import estimate
            from app.fund.marketdata import fetch_daily_bars
            bars = fetch_daily_bars(symbol, lookback_days=120)
            result["capacity"] = estimate(
                symbol, list(bars.closes or []), list(bars.volumes or []),
                rb.get("turnover_pct"))
        except Exception as e:  # noqa: BLE001
            logger.info("capacity estimate unavailable for %s: %s", symbol, e)

    def _add_cost_disclosure(self, job: dict[str, Any]) -> None:
        """Record whether the run that just finished was actually priced."""
        result = job.get("result") or {}
        rb = result.setdefault("robustness", {})
        try:
            code = self.get_algorithm(job["algorithm"])["code"]
        except Exception:  # noqa: BLE001
            return
        rb["costs"] = cost_disclosure(
            code, rb.get("total_fees"), rb.get("total_orders") or 0)

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
            "robustness": _robustness(stats, equity, dates, _orders(best)),
            "raw_files": sorted(p.name for p in res_dir.glob("*")),
        }


def _robustness(stats: dict, equity: list[float], dates: list[str],
                orders: list[dict]) -> dict[str, Any]:
    """Can this result be believed? Measured, never assumed.

    A backtest reports its return with the same confidence whether it rests on
    five trades or five hundred, which is how a lucky streak gets promoted. The
    three questions that separate a result from a coincidence:

    - Is the Sharpe distinguishable from luck? LEAN already computes the
      Probabilistic Sharpe Ratio — the probability the true Sharpe beats zero,
      adjusted for skew, kurtosis and sample length. It was buried in the
      statistics fold; it belongs at the front.
    - Did it work throughout, or in one stretch? A strategy that made
      everything in one month is a different animal from one that ground it out.
    - What did trading cost? See ``fees_are_zero``.
    """
    def _num(key: str) -> Optional[float]:
        v = stats.get(key)
        if v is None:
            return None
        try:
            return float(str(v).replace("%", "").replace("$", "").replace(",", ""))
        except ValueError:
            return None

    fees = _num("Total Fees")
    out: dict[str, Any] = {
        "psr_pct": _num("Probabilistic Sharpe Ratio"),
        "total_orders": int(_num("Total Orders") or len(orders)),
        "win_rate_pct": _num("Win Rate"),
        "total_fees": fees,
        # Zero fees is the CORRECT answer for this fund: Alpaca charges no
        # commission on US equities. The cost that actually bites is the
        # spread, which is a slippage model, not a fee — so "fees are zero" on
        # its own says nothing about whether the run was priced. Whether costs
        # were modelled is decided by reading the algorithm (see
        # _cost_disclosure), because a warning that fires on every single run
        # is one an operator learns to scroll past.
        "turnover_pct": _num("Portfolio Turnover"),
        "periods": _periods(equity, dates),
    }
    return out


_SLIPPAGE_RE = re.compile(r"set_slippage_model\s*\(")
_FEE_RE = re.compile(r"set_fee_model\s*\(")
_ZERO_SLIP_RE = re.compile(r"ConstantSlippageModel\s*\(\s*0(?:\.0*)?\s*\)")


def cost_disclosure(code: str, fees: Optional[float],
                    orders: int) -> dict[str, Any]:
    """Was this backtest priced, and how would the operator know?

    Read from the algorithm's own source rather than inferred from the
    statistics, because the statistics cannot tell the two zero-cost cases
    apart: a fund whose broker genuinely charges no commission, and a backtest
    that forgot to model the spread. Those look identical in Total Fees and
    are opposite findings.
    """
    slipped = bool(_SLIPPAGE_RE.search(code or ""))
    explicit_zero = bool(_ZERO_SLIP_RE.search(code or ""))
    modelled = slipped and not explicit_zero
    return {
        "slippage_modelled": modelled,
        "fee_model_set": bool(_FEE_RE.search(code or "")),
        "commission_paid": fees,
        # The only case worth shouting about: it traded, and nothing priced it.
        "unpriced": orders > 0 and not modelled and not (fees or 0) > 0,
        "note": ("costs modelled" if modelled else
                 "slippage explicitly zeroed — this run assumes free fills"
                 if explicit_zero else
                 "no slippage model: fills happen at the close, so this "
                 "overstates every strategy that trades often"),
    }


def _periods(equity: list[float], dates: list[str], n: int = 3) -> list[dict[str, Any]]:
    """Return within each equal slice of the window — was it consistent?"""
    if len(equity) < n * 2 or len(dates) != len(equity):
        return []
    out: list[dict[str, Any]] = []
    size = len(equity) // n
    for i in range(n):
        lo = i * size
        hi = (i + 1) * size if i < n - 1 else len(equity) - 1
        start, end = equity[lo], equity[hi]
        if not start:
            continue
        out.append({
            "from": dates[lo], "to": dates[hi],
            "return_pct": round((end / start - 1.0) * 100.0, 2),
        })
    return out


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
