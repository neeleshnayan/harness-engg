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

import ast
import itertools
import json
import logging
import math
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

#: Wall clock allowed one engine container. 300 -> 900 on 2026-08-21, by
#: measurement, on the quant seat's accepted finding (run-quant-entry11: "2 of 37
#: container runs died on LEAN_JOB_TIMEOUT=300s under three concurrent
#: candidates").
#:
#: The measurement that decided the number, taken from the 50 most recent jobs in
#: the durable store on 2026-08-21:
#:
#:     min 1.0s   median 14.8s   p90 300.4s   max 301.2s
#:     44 jobs under 120s;  SIX pinned at 300.4-301.2s;  NOTHING in between.
#:
#: That gap is the whole argument. A healthy tail arrives gradually — 150s, 220s,
#: 280s. A cliff at exactly the ceiling with an empty approach means the
#: distribution is CENSORED: those six runs did not take 300 seconds, they were
#: killed at 300 and their true duration has never been observed. So the old
#: value was not sampling a tail, it was manufacturing one, and every one of
#: those kills entered the belt as missing evidence.
#:
#: 900s is 3x the censoring point and ~60x the median, chosen because the honest
#: answer to "how long do they need" is that we do not know and cannot know until
#: one finishes. It stays inside every enclosing deadline: `_run_point` waits
#: JOB_TIMEOUT_S + 60, the sweep waits 5,400s and the factory 3,600s, so a single
#: slow point can no longer be reported as an unmeasurable strategy — it will
#: either finish or be reported as a TIMEOUT by name.
#:
#: RE-MEASURE THIS once a job lands between 300s and 900s: that will be the first
#: real observation of the tail, and the number should follow it rather than this
#: reasoning.
JOB_TIMEOUT_S = float(os.getenv("LEAN_JOB_TIMEOUT", "900"))

_CLASS_RE = re.compile(r"class\s+(\w+)\s*\(\s*QCAlgorithm\s*\)")
_NAME_RE = re.compile(r"^[a-z0-9_\-]{1,64}$")


#: Each sweep point is a full engine container (~10s), so a grid is minutes,
#: not seconds. The cap is a guard against a five-parameter grid nobody meant
#: to ask for.
MAX_SWEEP_POINTS = int(os.getenv("LEAN_MAX_SWEEP_POINTS", "24"))

#: How many engine containers may run at once, fund-wide.
#:
#: This was 1, and the reason on file was `WinError 1455: the paging file is too
#: small` — a sweep stacked against a factory batch killed a holdout run outright.
#: That crash was real. The DIAGNOSIS was wrong, and it cost this fund a lot of
#: wall clock.
#:
#: Measured 2026-08-17 on a live sweep point: a LEAN container uses **~450 MiB**,
#: against a cap that reserved **3 GiB**. Three stacked containers therefore
#: reserved 9 GiB on a 15.2 GB host with ~10 GB already committed, and the host
#: refused — not because LEAN wanted the memory, but because we had promised it on
#: LEAN's behalf. The fix is the cap, not the concurrency.
#:
#: The machine is a 12-core / 24-thread Ryzen 9 7900X that was running one
#: container at a few percent of one core. Cores are not the constraint, and
#: neither is the GPU — LEAN is single-threaded .NET per backtest with no GPU path.
#:
#: MEASURED A/B against the real engine (`scripts/parallelism_bench.py`, results in
#: docs/parallelism_bench.json), same sweep serialised then concurrent:
#:
#:     slots   points   serial   concurrent   speedup   peak containers seen
#:       4        4      141.0s      44.0s     3.20x    4
#:       8        8      286.1s      54.0s     5.30x    8
#:
#: 8 is faster in absolute terms and is NOT the shipped default, deliberately. It
#: only fit because actual usage was ~459 MiB rather than the 1 GiB cap: eight caps
#: is 8 GiB against ~5 GB free, so it worked by relying on Docker not committing
#: the reservation — which is precisely the assumption that produced WinError 1455
#: the first time. The sizing rule has to be `slots x cap <= free RAM`, holding
#: even if every container claimed its ceiling.
#:
#: So 6 slots at a 768 MiB cap = 4.5 GiB worst case, inside ~5 GB free, and it
#: captures most of a gain measured between 3.2x and 5.3x. Raise it with
#: LEAN_MAX_CONCURRENT once there is more RAM, not once it "seems fine".
MAX_CONCURRENT_CONTAINERS = int(os.getenv("LEAN_MAX_CONCURRENT", "6"))

#: Hard ceiling per container. Without it one runaway algorithm can exhaust the
#: host and take unrelated runs down with it — the failure is never contained to
#: the job that caused it.
#:
#: 768 MiB is ~1.7x the highest peak observed across the benchmark arms (459 MiB at
#: 8-way concurrency, 398 MiB at 1-way — it does creep up under load). Chosen with
#: the slot count rather than separately, because only the PRODUCT has to fit free
#: RAM: 6 x 768 MiB = 4.5 GiB.
#:
#: If a genuinely heavier universe OOMs at this cap it fails loudly and in
#: isolation, which is what this ceiling is for, and is a far better failure than
#: the silent host-wide crash the old 3 GiB reservation caused. That is the trade
#: being made: a contained failure we will see, instead of an uncontained one we
#: misdiagnosed for a week.
CONTAINER_MEMORY = os.getenv("LEAN_CONTAINER_MEMORY", "768m")

#: Backtests and sweeps queue against this. Live sessions deliberately do NOT:
#: a live session holds its container for the whole session, so letting it draw
#: from the same pool would starve research for the rest of the day.
_ENGINE_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_CONTAINERS)

_PARAM_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_\-]{0,31}$")

#: The parameter an algorithm reads to fill FRACTIONAL shares.
#:
#: The engine fills whole shares by default and the venue does not: Alpaca
#: supports fractional equities, so a $2,000 book that LEAN rounds to whole
#: shares is being tested under a constraint the fund does not actually have.
#:
#: MEASURED 2026-08-21 with `lean_workspace/algorithms/frac_probe`, one window,
#: same rule, $2,000 book, a 49% target in each of SPY and TLT:
#:
#:     fractional:0   SPY 1.0000   TLT 11.0000   <- the engine's default
#:     fractional:1   SPY 1.4298   TLT 11.1207
#:
#: SPY printed at $685, so 49% of the book is $980 = 1.43 shares. Whole-share
#: rounding holds ONE share — 34% of the book against a 49% target, a 15
#: percentage-point error. That is an order of magnitude larger than the 1-2%/yr
#: effect entry 11 was trying to measure, and it is why the quant had to run that
#: candidate at a $100k notional and report the $2k deployment answer separately
#: (run-quant-entry11, accepted 2026-08-21).
#:
#: The mechanism, verified rather than assumed — an algorithm opts in with:
#:
#:     if str(self.get_parameter("fractional") or "0") == "1":
#:         old = sec.symbol_properties
#:         sec.symbol_properties = SymbolProperties(
#:             old.description, old.quote_currency, old.contract_multiplier,
#:             old.minimum_price_variation, 0.0001, old.market_ticker)
FRACTIONAL_PARAM = "fractional"

#: Source tokens that prove an algorithm actually READS the switch.
#:
#: This check exists because of the failure it prevents, which is the worst kind:
#: the runner can set a parameter, but only the ALGORITHM can act on it. Setting
#: `fractional:1` for a file that ignores it would leave the caller believing the
#: run was fractional when it was whole-share — a silent lie about the conditions
#: a verdict was produced under. So the request is checked against the source and
#: an unhonoured one is REPORTED, never assumed to have taken effect.
_FRACTIONAL_TOKENS = (FRACTIONAL_PARAM, "symbol_properties")


def honours_fractional(code: Optional[str]) -> bool:
    """Whether this algorithm's source reads the fractional switch at all.

    A source scan rather than a runtime check, for the same reason
    `walkforward.declared_hold_days` reads HOLD_DAYS statically: the engine has
    exited by the time anyone asks, so the file is the only thing left to ask.

    Conservative in the safe direction — it must find BOTH the parameter name
    and the symbol-properties override. A file mentioning one without the other
    is not honouring the switch, and reporting that it might be would put the
    caller back where they started.
    """
    if not code:
        return False
    return all(t in code for t in _FRACTIONAL_TOKENS)


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
        # Carried STRUCTURALLY rather than left to be recovered from the error
        # sentence. A killed run and a strategy that had nothing to say produce
        # the same shape downstream — every figure absent — and the quant seat
        # read six of them as "unmeasurable" when they were "never measured".
        # A boolean cannot be mistaken for a result; a prose match on an error
        # string can, and would break the first time the sentence is reworded.
        "timed_out": bool(job.get("timed_out")),
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
        # Durable mirror, built on first use so a runner with no database (every
        # test) behaves exactly as before.
        self._store: Any = None
        self._store_tried = False

    # --- durable mirror ------------------------------------------------------

    def _durable(self):
        """The Postgres mirror, or None. Resolved once."""
        if self._store_tried:
            return self._store
        self._store_tried = True
        try:
            from app.fund.leanstore import LeanStore, enabled
            if enabled():
                self._store = LeanStore()
        except Exception as e:  # noqa: BLE001
            logger.info("LEAN runs will not be persisted: %s", e)
            self._store = None
        return self._store

    def _mirror_job(self, job: dict[str, Any]) -> None:
        """Best-effort. A failed mirror must never fail the run it describes —
        losing the copy of a result is a far smaller harm than losing the
        result, so this swallows and logs rather than raising into the worker."""
        st = self._durable()
        if st is None:
            return
        try:
            st.save_job(job)
        except Exception as e:  # noqa: BLE001
            logger.warning("could not persist job %s: %s", job.get("job_id"), e)

    def _mirror_sweep(self, sweep: dict[str, Any]) -> None:
        st = self._durable()
        if st is None:
            return
        try:
            st.save_sweep(sweep)
        except Exception as e:  # noqa: BLE001
            logger.warning("could not persist sweep %s: %s",
                           sweep.get("sweep_id"), e)

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
                        enrich: bool = True,
                        fractional: Optional[bool] = None) -> dict[str, Any]:
        """Run one backtest.

        ``enrich`` controls the extras that cost a NETWORK call — the buy-and-
        hold benchmark and the capacity estimate. Sweep points set it False:
        twenty-four grid points would otherwise make twenty-four fetches for
        numbers the comparison never reads, which is slow in production and
        was enough to make the suite flaky under load.

        ``fractional`` asks for fractional share fills. The engine rounds to
        whole shares and the VENUE does not, so a $2,000 book tested whole-share
        is being judged under a constraint the fund does not have — measured, a
        15 percentage-point error on a 49% target (see FRACTIONAL_PARAM).

        Asking is not the same as getting, and the job says which. Only the
        ALGORITHM can honour the switch, so the source is checked; a request an
        algorithm ignores is recorded as `fractional_honoured: False` with a
        note, rather than leaving the caller believing a whole-share run was
        fractional.
        """
        algo = self.get_algorithm(algorithm)  # raises on unknown
        m = _CLASS_RE.search(algo["code"])
        if not m:
            raise LeanError("algorithm lost its QCAlgorithm class")
        parameters = _clean_parameters(parameters)
        honoured: Optional[bool] = None
        frac_note: Optional[str] = None
        if fractional is not None:
            honoured = honours_fractional(algo.get("code"))
            parameters[FRACTIONAL_PARAM] = "1" if fractional else "0"
            if fractional and not honoured:
                frac_note = (
                    f"fractional fills were REQUESTED and this algorithm does "
                    f"not read the '{FRACTIONAL_PARAM}' parameter, so the run is "
                    f"WHOLE-SHARE. Any weight this rule targets is being held to "
                    f"the nearest whole share — at a small book that error can "
                    f"exceed the effect under test. Add the opt-in shown in "
                    f"leanrunner.FRACTIONAL_PARAM and re-run")
                logger.warning("job for %s: %s", algorithm, frac_note)
        # The fund's cost assumption travels WITH the run, so the number the
        # backtest charges is the same one TCA grades realised fills against.
        # The algorithm's own `or 0.0005` stays as a fallback for anyone
        # running the file outside the harness, but it is no longer the source
        # of truth — two copies of one belief is exactly how the old 2bps and
        # 5bps managed to disagree.
        #
        # An explicit slip is never overridden: a cost SWEEP is the one case
        # that must vary it, and that is the whole point of breakeven_cost.
        if "slip" not in parameters:
            from app.fund.costassumption import slippage_fraction
            parameters["slip"] = _param_value(slippage_fraction())
        job_id = uuid.uuid4().hex[:12]
        job = {
            "job_id": job_id, "algorithm": algorithm, "class_name": m.group(1),
            "state": "queued", "submitted_at": _now(),
            "started_at": None, "finished_at": None,
            "parameters": parameters,
            "enrich": enrich,
            # Travels with the job because it is a CONDITION THE VERDICT WAS
            # PRODUCED UNDER, in exactly the way the cost assumption is. None
            # means nobody asked either way — which is the engine's whole-share
            # default, and is not the same as having asked for it.
            "fractional_requested": fractional,
            "fractional_honoured": honoured,
            "fractional_note": frac_note,
            "error": None, "result": None, "log_tail": [],
        }
        with self._lock:
            self._jobs[job_id] = job
        self._mirror_job(job)
        threading.Thread(target=self._run, args=(job_id,), daemon=True).start()
        return {"job_id": job_id, "state": "queued"}

    def job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            j = self._jobs.get(job_id)
        if j is not None:
            return dict(j)
        st = self._durable()
        if st is not None:
            restored = st.job(job_id)
            if restored is not None:
                return restored
        raise LeanError(f"unknown job {job_id!r} — no record of it, in memory "
                        f"or in the ledger")

    def jobs(self) -> list[dict[str, Any]]:
        """This process's jobs first, then anything older from the mirror.

        Merged rather than served from one or the other: the in-memory copies are
        live and complete, while the mirror knows about runs from before the last
        restart. Showing only memory makes the Lab look empty after a restart;
        showing only the mirror loses whatever is still in flight.
        """
        with self._lock:
            live = [
                {k: v for k, v in j.items() if k != "result"}
                for j in sorted(self._jobs.values(),
                                key=lambda x: x["submitted_at"], reverse=True)
            ]
        st = self._durable()
        if st is None:
            return live
        try:
            known = {j["job_id"] for j in live}
            older = [j for j in st.recent_jobs(limit=50)
                     if j["job_id"] not in known]
        except Exception as e:  # noqa: BLE001
            logger.warning("could not read persisted jobs: %s", e)
            return live
        for j in older:
            j["restored"] = True
        return live + older

    def sweeps(self) -> list[dict[str, Any]]:
        """Sweep history, same merge as ``jobs``."""
        with self._lock:
            live = [
                {k: v for k, v in s.items() if k not in ("points",)}
                for s in sorted(self._sweeps.values(),
                                key=lambda x: x["submitted_at"], reverse=True)
            ]
        st = self._durable()
        if st is None:
            return live
        try:
            known = {s["sweep_id"] for s in live}
            # limit=200 (was 25): the durable store held 84 sweeps while the
            # list served 25, so most of the belt's history was unreachable
            # except by per-id GETs — see docs/MIN_TRAIN_RETURN_REVIEW.
            older = [s for s in st.recent_sweeps(limit=200)
                     if s["sweep_id"] not in known]
        except Exception as e:  # noqa: BLE001
            logger.warning("could not read persisted sweeps: %s", e)
            return live
        for s in older:
            s["restored"] = True
        return live + older

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
        self._mirror_sweep(sweep)
        threading.Thread(target=self._run_sweep, args=(sweep_id, combos),
                         daemon=True).start()
        return {"sweep_id": sweep_id, "state": "running", "total": sweep["total"]}

    def sweep(self, sweep_id: str) -> dict[str, Any]:
        with self._lock:
            s = self._sweeps.get(sweep_id)
        if s is not None:
            return dict(s)
        st = self._durable()
        if st is not None:
            restored = st.sweep(sweep_id)
            if restored is not None:
                # A sweep reloaded mid-flight is NOT still running: the thread
                # that drove it died with the process. Reporting "running"
                # would leave a poller waiting on work nobody is doing.
                if restored.get("state") == "running":
                    restored["state"] = "interrupted"
                    restored["error"] = (
                        "the process restarted while this sweep was running, so "
                        f"it stopped after {restored.get('completed') or 0} of "
                        f"{restored.get('total')} points — the points it did "
                        f"finish are below; re-run for the rest")
                return restored
        raise LeanError(f"unknown sweep {sweep_id!r} — no record of it, in "
                        f"memory or in the ledger")

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
        return {"state": "failed", "job_id": job_id, "timed_out": True,
                "error": (f"the point outlasted its deadline of "
                          f"{JOB_TIMEOUT_S + 60:.0f}s — the container was still "
                          f"alive and produced nothing readable")}

    #: How long an engine's raw output is kept on disk. Every backtest writes a
    #: results directory and nothing ever removed one, so 501 of them had
    #: accumulated to 188 MB — unbounded growth on the one resource this machine is
    #: already short of. The parsed result is mirrored to Postgres, so after a job
    #: settles the directory is debug material rather than the record.
    #: 1 day, not 3. MEASURED age distribution when this was written: 175 dirs
    #: under 6h, 263 more within a day, 63 within two — roughly 440 directories and
    #: 165 MB PER DAY of active research. A 3-day window would therefore cap steady
    #: state near half a gigabyte, which is not a retention policy so much as a
    #: slower leak. A failure gets debugged the same day it happens, and the parsed
    #: result is in Postgres either way.
    RESULTS_RETENTION_DAYS = float(os.getenv("LEAN_RESULTS_RETENTION_DAYS", "1"))

    #: Kept regardless of age, newest first. Age alone is the wrong rule on its own:
    #: after an idle week every directory is stale and a fresh failure would have
    #: its evidence swept before anyone read it.
    RESULTS_KEEP_NEWEST = int(os.getenv("LEAN_RESULTS_KEEP_NEWEST", "40"))

    def prune_results(self, max_age_days: Optional[float] = None,
                      keep_newest: Optional[int] = None) -> dict[str, Any]:
        """Delete engine output that is neither recent nor in use.

        Deliberately conservative on all three axes, because the cost of deleting
        a directory someone needed is a lost debugging session and the cost of
        keeping one is a few megabytes:

          * a job that is queued or running is NEVER touched, whatever its age
          * live-session directories are never touched — a live session holds its
            directory for the whole session
          * the newest N survive regardless of age

        Returns what it removed and what it reclaimed rather than logging silently,
        so a sweep that deletes far more than expected is visible.
        """
        import shutil

        age = self.RESULTS_RETENTION_DAYS if max_age_days is None else max_age_days
        keep = self.RESULTS_KEEP_NEWEST if keep_newest is None else keep_newest
        root = self._ws / "results"
        if not root.exists():
            return {"removed": 0, "reclaimed_mb": 0.0, "note": "no results dir"}

        # In-flight work, by id. A directory is named for its job or session.
        busy = set()
        for jid, j in list(self._jobs.items()):
            if j.get("state") in ("queued", "running"):
                busy.add(jid)
        for sid in list(getattr(self, "_live", {}) or {}):
            busy.add(f"live-{sid}")

        try:
            dirs = [p for p in root.iterdir() if p.is_dir()]
        except OSError as e:
            return {"removed": 0, "reclaimed_mb": 0.0,
                    "note": f"could not list results: {e}"}
        dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

        cutoff = time.time() - age * 86400.0
        removed, bytes_freed, skipped_busy = 0, 0, 0
        for i, p in enumerate(dirs):
            if i < keep:
                continue
            if p.name in busy or p.name.startswith("live-"):
                skipped_busy += 1
                continue
            try:
                if p.stat().st_mtime >= cutoff:
                    continue
                size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
                shutil.rmtree(p)
                removed += 1
                bytes_freed += size
            except OSError as e:  # noqa: PERF203
                logger.info("could not prune %s: %s", p.name, e)

        mb = round(bytes_freed / (1024 * 1024), 1)
        if removed:
            logger.info("pruned %d engine result dir(s), reclaimed %.1f MB "
                        "(kept newest %d, retention %.1fd)", removed, mb, keep, age)
        return {
            "removed": removed, "reclaimed_mb": mb, "kept_newest": keep,
            "retention_days": age, "skipped_in_use": skipped_busy,
            "remaining": len(dirs) - removed,
            "note": (f"removed {removed} dir(s), reclaimed {mb} MB; "
                     f"{len(dirs) - removed} remain"
                     if removed else
                     f"nothing older than {age:.1f}d outside the newest {keep}"),
        }

    def _run_sweep(self, sweep_id: str, combos: list[dict[str, str]]) -> None:
        sweep = self._sweeps[sweep_id]
        holdout = sweep.get("holdout")
        try:
            # Grid points run CONCURRENTLY, bounded by _ENGINE_SLOTS.
            #
            # They were serial, and that serialisation — not the hardware — was the
            # real ceiling on this fund's research throughput. A candidate is a
            # sweep per walk-forward fold, so 6 grid points across 4 folds is 24
            # strictly sequential engine runs, every one of them independent, on a
            # 12-core machine using about one core. Raising the container limit
            # alone would have changed nothing, because the belt never asked for a
            # second slot.
            #
            # The semaphore still governs how many containers exist at once; this
            # only stops the code from queuing behind itself. Points are appended
            # under a lock and the summary is computed after the join, so ordering
            # of `points` is completion order rather than grid order — which was
            # already true of nothing that reads it, since _sweep_summary selects
            # by score.
            lock = threading.Lock()

            def _one(params: dict[str, str]) -> None:
                run_params = dict(params)
                if holdout:
                    run_params["start"] = holdout["train_start"]
                    run_params["end"] = holdout["train_end"]
                j = self._run_point(sweep["algorithm"], run_params)
                point = _sweep_point(params, j)
                point["window"] = _window_of(j)
                with lock:
                    sweep["points"].append(point)
                    sweep["completed"] = len(sweep["points"])
                    # After each point, so a restart keeps the grid computed so
                    # far rather than discarding twenty minutes of engine time.
                    self._mirror_sweep(sweep)

            workers = max(1, min(MAX_CONCURRENT_CONTAINERS, len(combos)))
            if workers == 1:
                for params in combos:
                    _one(params)
            else:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=workers,
                                        thread_name_prefix="sweep") as pool:
                    # list() forces every future, so an exception in any point
                    # surfaces here rather than being swallowed by the pool.
                    list(pool.map(_one, combos))

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
            self._mirror_sweep(sweep)

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
        # The out-of-sample leg's aligned daily series (adversary r4 rec 4).
        # Carried on the HOLDOUT only, never on every grid point: a 24-point
        # cost sweep would otherwise store two dozen full return series for a
        # comparison that reads four scalars. The train leg's series is NOT
        # here and the payload says so — see `daily_returns_note` below.
        test_daily = ((j.get("result") or {}).get("daily_returns")
                      if isinstance(j, dict) else None)

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
                     "total_orders": point.get("total_orders"),
                     "daily_returns": test_daily,
                     # Travels with the leg it describes. The walk-forward reads
                     # `test` and nothing else when it decides why a fold could
                     # not be measured.
                     "timed_out": bool(point.get("timed_out"))},
            "dates_honoured": honoured,
            "timed_out": bool(point.get("timed_out")),
            "error": point.get("error"),
            # Stated rather than left to be noticed: the TRAIN leg's daily
            # series is not captured. Its numbers come from a stored sweep
            # row, and the job that produced them was released after the grid
            # ran. The out-of-sample leg is the one a premia statistic is
            # computed on, so this is a known and deliberate half rather than
            # an oversight — capturing the train leg needs the winner's job
            # held open, which is a separate change.
            "daily_returns_note": (
                "test leg captured; TRAIN leg NOT captured — its job was "
                "released after the grid ran, and re-running it would be a "
                "different run rather than the one these numbers came from"),
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
            "--memory", CONTAINER_MEMORY,
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
        # Wait for a slot BEFORE claiming to run and before starting the clock.
        # A queued job that reported "running" would look hung, and counting
        # queue time against JOB_TIMEOUT_S would kill honest runs for the crime
        # of being second in line.
        waited_for_slot = time.monotonic()
        _ENGINE_SLOTS.acquire()
        queued_s = round(time.monotonic() - waited_for_slot, 1)
        if queued_s > 1:
            job["queued_seconds"] = queued_s
            logger.info("job %s waited %.0fs for an engine slot", job_id, queued_s)
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
                if not job["result"]:
                    job["state"] = "failed"
                    job["error"] = "engine finished but wrote no parsable results"
                else:
                    if job.get("enrich", True):
                        # Network-backed extras, skipped for sweep points.
                        self._add_benchmark(job["result"], self._source_or_none(job))
                        self._add_cost_disclosure(job)
                        self._add_capacity(job["result"])
                    # Published LAST, deliberately. `state` is the signal every
                    # caller polls on, so marking the job done before enrichment
                    # finishes exposes a half-built result: the gate, arriving
                    # the instant the flag flips, would find no benchmark and no
                    # costs disclosure and fail the candidate for missing
                    # evidence that was seconds away. A verdict that depends on
                    # who polled first is not a verdict.
                    job["state"] = "done"
        except subprocess.TimeoutExpired:
            job["state"] = "failed"
            job["error"] = f"timed out after {JOB_TIMEOUT_S:.0f}s — engine killed"
            # The flag, not the sentence, is what downstream reads. A killed run
            # produced NO evidence; without this it arrives at the walk-forward
            # looking exactly like a strategy that declined to trade.
            job["timed_out"] = True
            subprocess.run(self._docker + ["kill", container],
                           capture_output=True, timeout=30)
        except Exception as e:  # noqa: BLE001
            job["state"] = "failed"
            job["error"] = f"{type(e).__name__}: {e}"[:400]
        finally:
            _ENGINE_SLOTS.release()
            job["finished_at"] = _now()
            job["wall_seconds"] = round(time.monotonic() - t0, 1)
            # Mirrored once, at the end, with the result attached. Writing on
            # every intermediate transition would put a database round-trip
            # inside the engine loop for states nobody reads back.
            self._mirror_job(job)

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

    def _source_or_none(self, job: dict[str, Any]) -> Optional[str]:
        try:
            return self.get_algorithm(job["algorithm"])["code"]
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _add_benchmark(result: dict[str, Any],
                       code: Optional[str] = None) -> None:
        """Buy & hold of what the strategy could have held, from the fund's own bars.

        LEAN's own Benchmark series is unusable for these algorithms: the data
        is a custom type, so the engine emits zeros rather than a comparison.
        Rather than drop the question, it is answered on the same closes the
        fund marks its book with — the identical feed the algorithm traded, so
        the comparison is like-for-like rather than two vendors disagreeing.

        Best-effort by design: if the bars cannot be fetched, the benchmark
        stays absent. An absent comparison is honest; an invented one is not.
        """
        # Whether to trust the engine's own series. Deferring to it blindly is
        # how a fund ends up measured against a bar that is not a bar:
        #
        #   * for custom data types LEAN emits a full-length curve of ZEROS,
        #     and that curve is truthy, so a bare `if benchmark_curve` accepts
        #     it and every profitable strategy "beats the market";
        #   * where it does emit prices, it zero-PADS the leading days before
        #     the subscription starts, and a return computed off a zero base is
        #     not a number anyone should see;
        #   * it tracks whatever single symbol set_benchmark named, which for a
        #     strategy that CHOOSES among names is one arbitrary constituent.
        #
        # So trust it only when it is strictly positive throughout AND the
        # strategy traded a single name. Otherwise recompute below from the
        # fund's own bars, which is like-for-like anyway: the same closes the
        # algorithm traded, rather than two vendors disagreeing.
        engine_curve = result.get("benchmark_curve") or []
        traded_syms = {o["symbol"] for o in (result.get("orders") or [])
                       if o.get("symbol")}
        if engine_curve:
            usable = all(isinstance(v, (int, float)) and v > 0
                         for v in engine_curve)
            if usable and len(traded_syms) <= 1:
                return
            logger.info("discarding engine benchmark (%d points, %d distinct, "
                        "%d symbols traded): %s", len(engine_curve),
                        len(set(engine_curve)), len(traded_syms),
                        "zero-padded or non-positive" if not usable
                        else "single-constituent bar for a multi-name strategy")
            result.pop("benchmark_curve", None)
            result.pop("benchmark_return_pct", None)
            result.pop("benchmark_dates", None)
        dates = result.get("equity_dates") or []
        orders = result.get("orders") or []
        equity = result.get("equity_curve") or []
        if len(dates) < 2 or not orders or not equity:
            return
        # WHAT to hold as the bar. Prefer the universe the strategy declared
        # over the names it actually bought, because those answer different
        # questions. A selection rule only ever buys the names it liked, so
        # benchmarking against those asks "did you time your favourites well"
        # when the decision under test was "were these the right names to pick
        # at all" — and it quietly grades the rule on a curve it drew itself.
        declared = _declared_universe(code)
        traded = sorted({o["symbol"] for o in orders if o.get("symbol")})
        basis = "declared_universe" if declared else "traded_symbols"
        wanted = declared or traded
        if not wanted:
            return

        # The right bar depends on the SHAPE of the strategy, and getting this
        # wrong quietly rigs the gate.
        #
        # A timing strategy on one name should be measured against holding that
        # name — the question is whether the timing added anything.
        #
        # A strategy that CHOOSES among several names must not be measured
        # against whichever one it traded most. That comparison is close to
        # meaningless: it flatters a selector that happened to avoid the worst
        # name and punishes one that happened to trade the best. The honest bar
        # is holding the whole basket in equal weight, which is what a
        # non-selective investor with the same universe would have done.
        from app.fund.marketdata import fetch_daily_bars

        series: list[list[float]] = []
        used: list[str] = []
        ref_dates: list[str] = []
        for sym in wanted:
            try:
                bars = fetch_daily_bars(sym, start=dates[0], end=dates[-1])
            except Exception as e:  # noqa: BLE001
                logger.info("benchmark leg unavailable for %s: %s", sym, e)
                continue
            closes = list(bars.closes or [])
            if len(closes) < 2 or not closes[0]:
                continue
            series.append([c / closes[0] for c in closes])
            used.append(sym)
            if len(bars.dates or []) > len(ref_dates):
                ref_dates = list(bars.dates or [])
        if not series:
            return

        # How much of the intended bar actually resolved. A "basket" built from
        # 2 of 20 names is not that basket, and reporting it as one would let a
        # strategy be graded against an accidental sub-portfolio — which is the
        # same failure as the single-constituent bar, arrived at by data gaps
        # instead of by configuration. Refuse below a majority, and state the
        # fraction either way so a thin bar is never mistaken for a full one.
        if len(used) * 2 < len(wanted):
            logger.info("benchmark refused: only %d of %d legs resolved",
                        len(used), len(wanted))
            result["benchmark_unavailable"] = (
                f"only {len(used)} of {len(wanted)} names in the bar had usable "
                f"bars — too thin to stand for the universe, so no comparison "
                f"is reported rather than a misleading one")
            return

        # Legs can differ in length when a name has a gap. Truncate to the
        # shortest rather than pad: a padded leg would be a made-up price.
        n = min(len(x) for x in series)
        start_equity = equity[0]
        curve = [round(start_equity * sum(x[i] for x in series) / len(series), 2)
                 for i in range(n)]

        result["benchmark_curve"] = curve
        result["benchmark_dates"] = ref_dates[:n]
        result["benchmark_return_pct"] = _total_return(curve)
        result["benchmark_symbol"] = (used[0] if len(used) == 1
                                      else f"equal-weight {'/'.join(used)}")
        result["benchmark_basket"] = used
        result["benchmark_kind"] = "single" if len(used) == 1 else "equal_weight_basket"
        result["benchmark_basis"] = basis
        result["benchmark_legs"] = {"used": len(used), "wanted": len(wanted)}
        if len(used) < len(wanted):
            result.setdefault("benchmark_caveat", (
                f"{len(used)} of {len(wanted)} names had usable bars; the bar is "
                f"the equal-weight basket of those that did"))
        if basis == "traded_symbols" and len(traded) > 1:
            # Say so rather than let a favourable bar pass as the honest one.
            result["benchmark_caveat"] = (
                "measured against the names this strategy traded, not the "
                "universe it chose from — the algorithm declares no UNIVERSE, "
                "so the bar excludes names the rule never bought")
        result["benchmark_source"] = "fund bars"

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
        # The benchmark's OWN dates are kept now (they used to be dropped):
        # the daily-return alignment below joins the two legs by date, and a
        # positional pairing would misalign them the first time the engine
        # emitted a different number of benchmark points.
        bench, bench_dates = _curve(charts, "Benchmark", "Benchmark")

        # THE DAILY RETURN SERIES, TAKEN BEFORE THE DOWNSAMPLE (adversary r4
        # rec 4, CEO-accepted 2026-08-21). Computed here and nowhere else,
        # because four lines below the curves are thinned to 400 points and the
        # raw series is gone — a 5.47-year run loses roughly two thirds of its
        # observations, and no premia statistic is computable from a series
        # whose spacing was chosen for a chart.
        #
        # Aligned BY DATE rather than by index: the strategy and benchmark
        # series come from different charts and are not guaranteed to be the
        # same length, and a positional zip would silently pair Tuesday's
        # strategy return with Wednesday's benchmark.
        daily = _daily_returns(equity, dates, bench, bench_dates)

        # The dates travel WITH the curve. Downstream, "is this alpha or beta"
        # regresses the curve against factor returns by date — an equity series
        # with no dates cannot be evaluated, only admired.
        equity, dates = _downsample2(equity, dates, 400)
        bench, _ = _downsample2(bench, [], 400) if _usable(bench) else ([], [])

        return {
            "engine": "lean",
            "statistics": stats,
            # Undownsampled, one feed, aligned. The prerequisite for gate v5
            # round 5 — without it no premia statistic is computable.
            "daily_returns": daily,
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


def _daily_returns(equity: list[float], dates: list[str],
                   bench: list[float], bench_dates: list[str]) -> dict[str, Any]:
    """Aligned daily returns for the strategy and its benchmark, UNDOWNSAMPLED.

    The prerequisite for gate v5's premia statistics (adversary round 4,
    recommendation 4, CEO-accepted 2026-08-21). Every existing curve on a stored
    result has been thinned to 400 points for drawing; a premia claim needs the
    real observations, on one clock, with no gaps invented.

    THREE RULES, each of which is a way the series could lie:

      * ALIGNED BY DATE, never by index. The two series come from different
        engine charts and are not guaranteed to be the same length; a
        positional zip pairs Tuesday's strategy with Wednesday's benchmark and
        every downstream beta is then wrong by one day.
      * A day present in only ONE series is DROPPED, and the count of dropped
        days is reported. Carrying it with a zero on the missing side would
        invent a flat day for an instrument that did not trade.
      * A non-positive or non-finite previous level breaks the chain rather than
        dividing — the same rule `factors.daily_returns` follows, and for the
        same reason: one bad bar otherwise emits an infinity into every
        regression built on the series.

    Returns the series plus an honest description of what is missing. `absent`
    is not an empty list: a run whose benchmark never arrived must be
    distinguishable from one whose benchmark was flat.

    ONE DISCLOSED SUBTLETY. Returns are differenced between CONSECUTIVE COMMON
    observations, which is what any aligned-series treatment does — so when a
    day is dropped for being present on only one side, the following return
    spans that gap and is a two-day return wearing a daily label. Both series
    come from the same engine run and normally share every date, so
    `dropped_unmatched_days` is normally 0; it is reported precisely because a
    non-zero value means a handful of the observations are wider than they look,
    and a reader computing daily volatility should know before they do.
    """
    if len(dates) != len(equity) or len(equity) < 2:
        return {"present": False, "dates": [], "strategy": [], "benchmark": [],
                "n": 0,
                "reason": "the equity curve carries no usable dates, so a daily "
                          "series cannot be placed on a clock — absent, not empty"}

    eq_by_date = {d: v for d, v in zip(dates, equity)}
    bm_by_date = ({d: v for d, v in zip(bench_dates, bench)}
                  if bench and len(bench_dates) == len(bench) else {})
    have_bench = bool(bm_by_date)

    ordered = sorted(eq_by_date)
    common = [d for d in ordered if d in bm_by_date] if have_bench else ordered
    dropped = len(ordered) - len(common)

    out_dates: list[str] = []
    strat: list[float] = []
    mark: list[float] = []
    prev_e: float | None = None
    prev_b: float | None = None
    for d in common:
        e = eq_by_date[d]
        b = bm_by_date.get(d)
        ok_e = isinstance(e, (int, float)) and math.isfinite(e) and e > 0
        ok_b = (not have_bench) or (
            isinstance(b, (int, float)) and math.isfinite(b) and b > 0)
        if prev_e is not None and ok_e and ok_b and prev_e > 0 and (
                not have_bench or (prev_b or 0) > 0):
            out_dates.append(d)
            strat.append(e / prev_e - 1.0)
            if have_bench:
                mark.append(b / prev_b - 1.0)
        prev_e = e if ok_e else None
        prev_b = b if ok_b else None

    return {
        "present": bool(out_dates),
        "dates": out_dates,
        "strategy": [round(r, 10) for r in strat],
        "benchmark": [round(r, 10) for r in mark] if have_bench else [],
        "benchmark_present": have_bench,
        "n": len(out_dates),
        "dropped_unmatched_days": dropped,
        "reason": None if out_dates else
                  "no two consecutive usable levels — nothing to difference",
        "note": (f"{len(out_dates)} aligned daily observations"
                 + ("" if have_bench else
                    "; NO benchmark series was emitted by the engine, so the "
                    "benchmark leg is ABSENT rather than flat")
                 + (f"; {dropped} day(s) present in only one series were dropped "
                    f"rather than zero-filled" if dropped else "")),
    }


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



def _declared_universe(code: Optional[str]) -> list[str]:
    """The tickers an algorithm says it chooses among, read from its source.

    Read statically rather than asked of the running algorithm: the engine has
    exited by the time results are enriched, and re-running it to ask a
    question about its inputs would double every backtest.

    Deliberately narrow — a module-level `UNIVERSE` of plain strings and nothing
    else. A cleverer parser would start guessing, and a guessed benchmark is
    the exact failure this is meant to prevent.
    """
    if not code:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "UNIVERSE" not in names:
            continue
        if not isinstance(node.value, (ast.List, ast.Tuple)):
            return []
        out = [e.value for e in node.value.elts
               if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        return sorted(set(out))
    return []

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
