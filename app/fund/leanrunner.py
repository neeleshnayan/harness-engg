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

#: How many live sessions may hold a container at once.
#:
#: **THIS BOUND USED TO BE 1 AND IT WAS NOT WRITTEN DOWN — it was the shape of a
#: refusal ("a live session is already running") in ``start_live``. Multi-session
#: support removes that refusal, which MOVES AN IMPLICIT LIMIT IN THE PERMISSIVE
#: DIRECTION, so it gets a name, a number and this note rather than silence.**
#:
#: The number is a RATIO of the one limit here with a measured basis, not a new
#: measurement: half of ``MAX_CONCURRENT_CONTAINERS``, floored at 1. The ratio is
#: a choice and is stated as one.
#:
#: THE RESIDUAL, NAMED RATHER THAN GLOSSED. The sizing rule written at
#: MAX_CONCURRENT_CONTAINERS is `slots x cap <= free RAM`, and live sessions
#: deliberately do NOT draw from the research pool (a session holds its container
#: all day and would starve the belt). So the joint worst case is
#: `(MAX_CONCURRENT_CONTAINERS + MAX_LIVE_SESSIONS) x CONTAINER_MEMORY` =
#: 9 x 768 MiB = 6.75 GiB, against the ~5 GB free the benchmark was sized in.
#: That product does not satisfy the rule, and it did not satisfy it at 1 live
#: session either (7 x 768 MiB = 5.25 GiB) — this change makes an existing
#: overdraft larger, it does not create one. Closing it means deciding which
#: pool live sessions draw from, which is a human's call about starving research
#: versus bounding memory, and is left to one.
MAX_LIVE_SESSIONS = int(os.getenv("LEAN_MAX_LIVE_SESSIONS",
                                  str(max(1, MAX_CONCURRENT_CONTAINERS // 2))))

#: How often the deterministic worker reconciles the session registry against
#: ``docker ps``. Proposed at five minutes, matching the cadence of the other
#: CONTROL ticks rather than the settle poll: an unaccounted container holds a
#: signal token and can POST proposals into the approval queue, so the window
#: in which one can exist unnoticed belongs beside the risk monitor's, not
#: beside the snapshot's.
#:
#: The cost is one ``docker ps`` and one registry page per pass. Both are
#: bounded and neither writes; the ACTIONS write, and they only fire on a
#: difference.
RECONCILE_INTERVAL_SECONDS = float(os.getenv("LEAN_RECONCILE_INTERVAL", "300"))

#: How long a live registry row is protected from being called ``vanished``
#: because no container backs it. See ``leansessions.YOUNG`` for the race; this
#: is its width, and three minutes is chosen against the SLOW path (a cold
#: ``docker run`` that has to pull the LEAN image) rather than the fast one.
#:
#: THE COST OF EACH DIRECTION IS NOT SYMMETRIC AND THAT IS WHY IT IS GENEROUS.
#: Too long and a genuinely dead session keeps its scope claimed for an extra
#: few minutes, which the next pass corrects. Too short and a session that is
#: starting correctly is retired mid-start, its scope released, and the
#: container that then appears is stopped by the following pass as an orphan.
RECONCILE_GRACE_SECONDS = float(os.getenv("LEAN_RECONCILE_GRACE", "180"))

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


class LeanConflict(LeanError):
    """This request lost a race for a resource another one holds.

    A SUBCLASS so every existing ``except LeanError`` still catches it, and its
    own class so the API can answer 409 rather than 400: "you asked for
    something impossible" and "someone else got there first" are different
    facts, and a caller retrying is right about exactly one of them.
    """


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


def _by_started_at(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first, then by session id, tolerating a row with no start.

    One helper because the two branches of ``live_sessions`` sorted the same
    list two ways — one with ``x["started_at"]`` and one with
    ``x.get("started_at")`` — so a row missing the key raised on one path and
    sorted last on the other. Same list, two behaviours, decided by whether a
    database happened to be configured.

    **THE SESSION ID IS A TIE-BREAK, NOT DECORATION, AND IT WAS MEASURED.**
    ``_now()`` has microsecond resolution and the Windows clock does not: two
    sessions started in the same tick get the SAME ``started_at``, and a stable
    sort then hands back dict-insertion order — which is arbitrary and which
    nothing would have noticed while only one session could exist at a time.
    Multi-session support is what made it reachable, and a page that renders
    the head of this list as "the current session" would have picked between
    them by accident. The tie-break does not make the order truthful (nothing
    can, when two things happened at the same recorded instant) — it makes it
    DETERMINISTIC and reproducible, which is the property a reader can actually
    rely on. This is the unseeded-hash tie-break the belt was bitten by, caught
    at a smaller scale.
    """
    return sorted(rows,
                  key=lambda x: (x.get("started_at") or "",
                                 x.get("session_id") or ""),
                  reverse=True)


class LeanRunner:
    """Algorithms on disk, jobs in memory, the engine in Docker.

    Jobs are in-memory by design: a backtest is a computation, not fund
    state. Losing the job table on restart costs a re-run, never a fact.

    LIVE SESSIONS ARE NOT, and the difference is why they got a registry. A
    session is a RUNNING PROCESS holding a signal token — losing its record does
    not cost a re-run, it costs a container nobody can stop and nobody can
    account for. ``_live`` is now a cache of ``fund_lean_sessions``; the rows are
    the record.
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
        # WHEN THIS PROCESS'S SESSION MEMORY BEGAN — the fence's anchor ONLY
        # when there is no registry.
        #
        # CORRECTED 2026-08-27, and the correction is the point of the change.
        # This used to be the anchor unconditionally, on the argument that
        # ``_live`` is born empty right here so no session record can exist
        # from before this instant. That argument was sound and it is now
        # false: sessions are rows in ``fund_lean_sessions`` and they survive
        # restarts, so a record CAN exist from before this process. The line
        # that matters became the REGISTRY's epoch, which is earlier — and
        # earlier fences strictly fewer signals, which is the safe direction.
        # ``leansessions.known_since`` holds the three-case decision and the
        # direction argument; this value is now one of its three inputs.
        self._born = _now()
        #: The last reconciliation that ACTED, or ``None`` — never a zeroed
        #: record. ``None`` here is what makes ``last_reconciliation`` able to
        #: say NEVER RUN, which is a louder fact than STALE and calls for a
        #: different response: a stale reading means the worker stopped, a
        #: never-run reading means the start-up pass itself failed and an
        #: inherited container is still holding a signal token.
        self._last_reconcile: Optional[dict[str, Any]] = None
        self._lock = threading.Lock()
        # Durable mirror, built on first use so a runner with no database (every
        # test) behaves exactly as before.
        self._store: Any = None
        self._store_tried = False
        # The session registry, built on first use. Separate from ``_store``
        # because its failure semantics are the opposite: the job mirror
        # degrades silently, the session registry refuses.
        self._registry_store: Any = None

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
    #
    # DURABLE SINCE 2026-08-27. Sessions used to live only in ``_live``, an
    # in-memory dict, and three measured consequences followed from that one
    # fact: a session died with every spine restart; a container OUTLIVED the
    # spine (``_run_live`` starts ``docker run`` from a daemon thread, so the
    # container lives in the docker daemon) and became an orphan nothing could
    # stop; and the single-session guard read the dict, released its lock and
    # then inserted, so two identical POSTs two milliseconds apart both got 200
    # (ticket dc12903f, verified live). The registry closes all three: rows
    # survive restarts, start-up reconciles them against ``docker ps``, and the
    # database's own partial unique index decides who wins a race.

    def _registry(self):
        """The session registry, or ``None`` when this deployment has none.

        DIFFERENT FAILURE SEMANTICS FROM ``_durable()`` AND DELIBERATELY SO. The
        job mirror is best-effort because losing a copy of a finished backtest
        costs a re-run. Losing a SESSION row costs a container the fund cannot
        stop and cannot account for. So when Postgres is configured and the
        registry cannot be built, this RAISES rather than degrading to memory —
        and ``start_live`` refuses. An unregistrable session is an orphan we
        have not created yet.
        """
        if not self._registry_required:
            return None
        if self._registry_store is not None:
            return self._registry_store
        from app.fund.leanstore import LeanStore
        self._registry_store = LeanStore()
        return self._registry_store

    @property
    def _registry_required(self) -> bool:
        from app.fund.leanstore import enabled
        return enabled()

    def _our_mode(self) -> Optional[str]:
        """This process's fund mode, for the container label. ``None`` when it
        cannot be read — which ``leansessions.ownership`` treats as "cannot
        judge another container's ownership", never as "it is mine"."""
        try:
            from app.fund import mode
            return mode.current_label()
        except Exception:  # noqa: BLE001 — an unreadable mode is not a mode
            return None

    def start_live(self, algorithm: str, strategy_id: str = "",
                   signal_token: str = "", qty: float = 0.1) -> dict[str, Any]:
        """Run an algorithm in LEAN's live-paper environment, supervised.

        LEAN proposes, never executes — the same rule that governs Clark. The
        container gets a signal token and a strategy id and nothing else: no
        venue credentials, no broker keys. Its entire reach is a POST to the
        spine's token-gated intake, where the proposal joins the approval queue
        behind the risk and compliance gates.

        Two things worth knowing before relying on this:

        * The algorithm MUST set its benchmark to its own custom symbol. LEAN
          otherwise adds a SPY minute subscription of its own accord, and
          live-paper's stub data queue cannot serve it — the run dies with
          "LiveDataQueue has not implemented live data" before a single bar of
          the fund's own data arrives.
        * On daily bars this is a once-a-day event, not a ticking feed. Live
          mode buys supervision and state that survives the day, not latency.

        **N STRATEGIES, N SESSIONS, ONE PER SCOPE.** The old refusal was global
        — one live session at a time, whatever it was running — and the CEO's
        autopilot decision needs several deployed strategies live together. What
        replaces it is NARROWER where it matters and wider only where it was
        never the point: a scope (a strategy, or an algorithm when the session
        is unscoped) may hold exactly ONE live session, enforced by the
        database, and a bounded number of scopes may be live at once.
        """
        from app.fund import leansessions
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

        # Resolved BEFORE the claim: if the registry is configured and cannot be
        # reached, nothing is started. Refusing costs a retry; starting an
        # unregistered session costs an orphan.
        try:
            registry = self._registry()
        except Exception as e:  # noqa: BLE001
            raise LeanError(
                f"the session registry is configured and unreachable ({e}) — "
                f"refusing to start a session nothing would remember, because "
                f"an unregistered container cannot be stopped after a restart"
            ) from e

        key = leansessions.scope_key(strategy_id, algorithm)
        session_id = uuid.uuid4().hex[:12]
        session = {
            "session_id": session_id, "algorithm": algorithm,
            "class_name": m.group(1), "state": "starting",
            "started_at": _now(), "stopped_at": None,
            "container": f"{leansessions.CONTAINER_PREFIX}{session_id}",
            "strategy_id": strategy_id,
            # Never the token itself: this dict is returned over the API.
            "signal_configured": bool(strategy_id and signal_token),
            "error": None, "log_tail": [],
            "scope_key": key,
            "mode": self._our_mode(),
        }

        # THE IN-PROCESS HALF OF THE GUARD: check and insert under ONE lock.
        # v1 released the lock between the two and that window is the race. This
        # closes it for a single process; the database closes it across
        # processes, and both are needed — a deployment with no Postgres has
        # only this one.
        with self._lock:
            alive = [s for s in self._live.values()
                     if leansessions.is_alive(s)]
            if any(s.get("scope_key") == key for s in alive):
                raise LeanConflict(
                    f"a live session already holds {key} — one live session per "
                    f"strategy; stop that one before starting another")
            # THE CEILING IS PER PROCESS AND THE REGISTRY DOES NOT ENFORCE
            # IT. Counted from ``_live`` deliberately: reading the registry here
            # would put a database round trip inside the lock that decides
            # uniqueness, and the two are not the same guarantee. In practice
            # ``_live`` holds every session this host is running, because
            # start-up reconciliation re-attaches the ones it inherited — but a
            # SECOND spine on the same daemon could jointly exceed this bound,
            # and nothing here would notice. Said out loud because a limit whose
            # scope is unstated reads as a limit on the host.
            if len(alive) >= MAX_LIVE_SESSIONS:
                raise LeanError(
                    f"{len(alive)} live sessions is already this process's "
                    f"ceiling of {MAX_LIVE_SESSIONS} (LEAN_MAX_LIVE_SESSIONS); "
                    f"each holds a container for its whole life, and the host's "
                    f"RAM is what bounds them")
            self._live[session_id] = session

        if registry is not None:
            from app.fund.leanstore import SessionConflict
            try:
                registry.claim_session(session)
            except SessionConflict as e:
                with self._lock:
                    self._live.pop(session_id, None)
                raise LeanConflict(
                    f"a live session already holds {key} — the registry refused "
                    f"the claim, which is how two simultaneous starts are "
                    f"decided") from e
            except Exception as e:  # noqa: BLE001 — unwritable is not written
                with self._lock:
                    self._live.pop(session_id, None)
                raise LeanError(
                    f"the session could not be registered ({e}) — refusing to "
                    f"start a container nothing would remember") from e

        threading.Thread(target=self._run_live,
                         args=(session_id, signal_token, qty), daemon=True).start()
        return {"session_id": session_id, "state": "starting",
                "signal_configured": session["signal_configured"],
                "scope_key": key,
                # Which mechanism decided this session was unique. A deployment
                # with no registry has only the in-process lock, which cannot
                # see a second spine — stated on the response rather than
                # assumed, because the two guarantees are not the same one.
                "uniqueness_basis": ("registry" if registry is not None
                                     else "process_memory")}

    def sessions_known_since(self) -> Optional[str]:
        """The instant a session record COULD first have existed.

        Read by the engine fence to decide whether an old signal testifies about
        a live engine or a dead one. The decision itself lives in
        ``leansessions.known_since`` — with the direction argument for why an
        unreadable registry returns ``None`` here and NOT this process's birth,
        which would be the more permissive value.

        Not a control and nothing acts on it; it is a fact about the instrument,
        published so a fold does not have to guess at it.
        """
        from app.fund import leansessions
        epoch = None
        required = self._registry_required
        if required:
            try:
                registry = self._registry()
                epoch = registry.registry_epoch() if registry else None
            except Exception as e:  # noqa: BLE001 — unreadable is not absent
                logger.warning("session registry epoch unreadable: %s", e)
                epoch = None
        return leansessions.known_since(required, epoch, self._born)

    def live_sessions(self) -> list[dict[str, Any]]:
        """Every session this fund knows about, newest first.

        Merged the way ``jobs()`` and ``sweeps()`` are: this process's sessions
        are live and complete, the registry knows about sessions from before the
        last restart, and serving only one of the two either loses what is in
        flight or forgets everything after a restart.

        **RAISES WHEN THE REGISTRY IS CONFIGURED AND UNREADABLE, AND THAT IS THE
        POINT.** ``fund._live_sessions_or_none`` turns an exception into
        ``None`` ("could not be read") and an empty list into ``[]`` ("nothing
        is running"), and the fence takes OPPOSITE decisions on the two. After a
        restart, ``_live`` is empty; returning it as ``[]`` while the registry
        was unreachable would claim nothing is running on the exact path where
        we cannot know.
        """
        with self._lock:
            live = [dict(s) for s in self._live.values()]
        if not self._registry_required:
            return _by_started_at(live)
        registry = self._registry()
        known = {s["session_id"] for s in live}
        # ONLY THE REGISTRY'S *LIVE* ROWS, not its whole history. ``jobs()``
        # merges history because the Lab wants a history; this endpoint is
        # called ``/fund/lean/live`` and its consumers COUNT what it returns —
        # the engine fence publishes ``sessions`` and ``sessions_running`` off
        # it, and folding a fortnight of ended rows in would move one of those
        # numbers from 1 to 200 without any session having started. This
        # process's OWN finished sessions still appear, exactly as they always
        # did, because they are in ``_live``.
        rows = [r for r in registry.live_session_rows()
                if r["session_id"] not in known]
        return _by_started_at(live + rows)

    def live_session(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            s = self._live.get(session_id)
        if s is not None:
            return dict(s)
        if self._registry_required:
            # BY ID, NOT BY SCANNING ``session_rows()``. That list is CAPPED
            # (200), so a scan would answer "unknown session" for a real
            # session as soon as 200 newer ones existed — a lookup whose
            # correctness quietly expires. HW1's lesson, one layer down.
            found = self._registry().session(session_id)
            if found is not None:
                return found
        raise LeanError(f"unknown live session {session_id!r}")

    def stop_live(self, session_id: str) -> dict[str, Any]:
        """Kill the container and record the stop, in that order.

        **WHAT DOCKER SAID IS RECORDED RATHER THAN DISCARDED.** The previous
        version ran ``docker kill`` with ``capture_output=True`` and threw the
        output away, so a session whose container was already gone — the normal
        case for a restored row after a restart — was marked ``stopped`` with
        exactly the same confidence as one we really killed. The state is the
        same either way (it is not running now), but the REASON is not, and the
        reason is what tells a reader whether the orphan problem just bit them.
        """
        s = self.live_session(session_id)
        killed, detail = self._kill_container(s.get("container") or "")
        stopped_at = _now()
        with self._lock:
            row = self._live.get(session_id)
            if row is not None:
                row["state"] = "stopped"
                row["stopped_at"] = stopped_at
                s = dict(row)
            else:
                s = {**s, "state": "stopped", "stopped_at": stopped_at}
        self._register_state(s)
        # THE DETAIL IS RETURNED AND LOGGED, NEVER STORED ON THE SESSION. An
        # earlier version of this put it on the session dict, which would have
        # made it a field that exists on a session this process stopped and
        # vanishes on the next restart — one key meaning two things depending
        # on when you asked, which is the shape of defect this whole change
        # exists to remove.
        logger.info("live session %s stopped: %s", session_id, detail)
        return {"session_id": session_id, "state": "stopped",
                "container_killed": killed, "detail": detail}

    def _kill_container(self, container: str) -> tuple[bool, str]:
        """``(killed, one sentence)``. Never raises — a stop that cannot reach
        docker still has to record what it could not do."""
        if not container:
            return False, ("the session carries no container name, so nothing "
                           "could be killed.")
        try:
            proc = subprocess.run(self._docker + ["kill", container],
                                  capture_output=True, text=True, timeout=60)
        except Exception as e:  # noqa: BLE001
            return False, (f"docker could not be reached to kill {container} "
                           f"({type(e).__name__}: {e}), so whether it is still "
                           f"running is UNKNOWN.")
        if proc.returncode == 0:
            return True, f"docker killed {container}."
        return False, (f"docker refused to kill {container} "
                       f"({(proc.stderr or '').strip()[:200] or 'no detail'}) — "
                       f"most often because it was already gone.")

    def _register_state(self, session: dict[str, Any], *,
                        only_if_alive: bool = False) -> None:
        """Write a session's state back to the registry. Best-effort AFTER the
        claim, unlike the claim itself.

        ``only_if_alive`` is for a write that must LOSE a race rather than win
        one — see ``LeanStore.update_session``. The one caller is the
        ``running`` stamp in ``_run_live``, which arrives from a daemon thread
        and must never resurrect a row something else has already retired.

        The claim must succeed or nothing starts; an UPDATE that fails leaves a
        stale row, and a stale row is self-healing — start-up reconciliation
        finds a live row with no container and marks it ``vanished``, which
        releases the scope. So this logs loudly and does not raise into a worker
        thread, where an exception would kill the only thread that could ever
        correct the row.
        """
        if not self._registry_required:
            return
        try:
            affected = self._registry().update_session(
                session, only_if_alive=only_if_alive)
            if only_if_alive and not affected:
                # NOT AN ERROR — it is the guard doing its job, and it is worth
                # a line because a session whose `running` stamp lost to a
                # retirement is a session whose container may still be alive.
                logger.warning(
                    "session %s was already retired when its running stamp "
                    "arrived; the stamp was dropped rather than resurrecting "
                    "the row — if its container is still up, the next "
                    "reconciliation will find and stop it",
                    session.get("session_id"))
        except Exception as e:  # noqa: BLE001
            logger.warning("session %s state %r not written to the registry: "
                           "%s — start-up reconciliation will correct it",
                           session.get("session_id"), session.get("state"), e)

    def registry_durable(self) -> bool:
        """Do sessions survive a restart here? A fact about the instrument, so
        a reader of an empty session list can tell "nothing is running" from
        "this process forgot"."""
        return self._registry_required

    def registry_rows_or_none(self) -> Optional[list[dict[str, Any]]]:
        """Every registry row, or ``None`` when the registry could not be read —
        never ``[]``. Written once here because BOTH the reconciler and the
        read-only endpoint need the distinction, and reading it twice is how one
        of the two ends up half-right."""
        if not self._registry_required:
            return []
        try:
            return self._registry().session_rows()
        except Exception as e:  # noqa: BLE001 — unreadable proves no orphan
            logger.warning("session registry unreadable: %s", e)
            return None

    def registry_page_size(self) -> Optional[int]:
        """The cap on ``registry_rows_or_none``, or ``None`` when there is no
        registry to cap. Published so a reconciliation can say whether its own
        page bound."""
        if not self._registry_required:
            return None
        from app.fund.leanstore import LeanStore
        return LeanStore.SESSION_PAGE

    def docker_live_containers(self) -> Optional[list[dict[str, Any]]]:
        """Running LEAN live containers, or ``None`` when docker cannot be asked.

        ``None`` and ``[]`` are different facts and this fund has paid for
        collapsing them: ``[]`` says the daemon answered and nothing is running;
        ``None`` says we do not know. The reconciler stops nothing on ``None``.
        """
        from app.fund import leansessions
        fmt = '{{.Names}}\t{{.Label "' + leansessions.MODE_LABEL + '"}}'
        try:
            proc = subprocess.run(
                self._docker + ["ps", "--filter",
                                f"name={leansessions.CONTAINER_PREFIX}",
                                "--format", fmt],
                capture_output=True, text=True, timeout=30)
        except Exception as e:  # noqa: BLE001 — unreachable is not empty
            logger.warning("docker could not be asked what is running: %s", e)
            return None
        if proc.returncode != 0:
            logger.warning("docker ps failed: %s",
                           (proc.stderr or "").strip()[:200])
            return None
        out: list[dict[str, Any]] = []
        for line in (proc.stdout or "").splitlines():
            if not line.strip():
                continue
            name, _, label = line.partition("\t")
            out.append({"name": name.strip(), "mode": label.strip() or None})
        return out

    def reconcile_containers(self, *, trigger: str = "startup",
                             grace_seconds: float = 0.0) -> dict[str, Any]:
        """Match the registry against ``docker ps`` and act on the difference.

        **THIS IS THE HALF OF THE FIX THAT MAKES THE OTHER HALF TRUE.** A
        durable registry alone would still leave a container running that no
        process remembers; ``engineledger.ORPHAN_NOTE`` names that exact gap and
        says closing it needs the runner to reconcile against ``docker ps``.

        Called at spine start-up (``app.main.lifespan``) and, since 2026-08-27,
        on the deterministic worker's tick — the start-up pass left the whole
        window BETWEEN start-ups open, which is where a session that goes quiet
        mid-run actually lives. Never raises: a reconciliation that cannot run
        must not stop the spine from starting, nor kill the tick that will try
        again — it reports what it could not do, and every action it did not
        take is visible in the counts beside the domain it compared.

        ``grace_seconds`` is what makes the periodic caller SAFE and the
        start-up caller UNCHANGED. ``start_live`` writes its registry row before
        launching ``docker run``, so a pass landing in that window sees a live
        row with no container — which is the shape of ``vanished``. See
        ``leansessions.YOUNG``. The default of 0 is the start-up behaviour to
        the byte; the worker passes this module's ``RECONCILE_GRACE_SECONDS``
        (set by the ``LEAN_RECONCILE_GRACE`` environment variable).
        """
        from app.fund import leansessions
        rows = self.registry_rows_or_none()
        containers = self.docker_live_containers()
        plan = leansessions.reconcile(rows, containers,
                                      our_mode=self._our_mode(),
                                      rows_cap=self.registry_page_size(),
                                      now=_now(),
                                      grace_seconds=grace_seconds)

        performed: list[dict[str, Any]] = []
        for act in plan["actions"]:
            what, sid = act["action"], act["session_id"]
            row = next((r for r in (rows or ()) if r.get("session_id") == sid),
                       None)
            if what in (leansessions.REATTACH, leansessions.ADOPT):
                # A SESSION THIS PROCESS ALREADY HOLDS IS NEVER RE-TAKEN, AND
                # THIS BECAME LOAD-BEARING THE DAY THE PASS BECAME PERIODIC.
                #
                # ``_run_live`` binds ``session = self._live[session_id]`` ONCE
                # and mutates that object for the rest of the session's life.
                # Replacing the entry hands the process a DIFFERENT dict from
                # the one its own thread is writing to: when the engine exits,
                # the thread records ``ended`` on the object it holds while
                # ``_live`` — which is what ``live_sessions()`` and
                # ``stop_live()`` read — still says ``running``, forever.
                #
                # At start-up this could not happen: ``_live`` is empty, there
                # is no thread, and taking the row back in is the entire point.
                # Every five minutes it happens on the FIRST pass after any
                # session starts. Demonstrated by identity, not equality:
                # ``scratchpad/clobber_probe.py``.
                #
                # Recording it as ``done: False`` rather than skipping it
                # silently: the reconciliation's job is to say what it found,
                # and "this one is already ours" is a finding, not a no-op.
                with self._lock:
                    held = sid in self._live
                if held:
                    performed.append({
                        **act, "done": False,
                        "detail": ("this process already holds the session; "
                                   "its own thread owns that object and "
                                   "replacing it would leave `_live` reporting "
                                   "a state the thread no longer writes to.")})
                    continue
                taken = dict(row or {})
                taken.update({"session_id": sid, "state": "running",
                              "container": act.get("container"),
                              "restored": True})
                if what == leansessions.ADOPT:
                    # THE REGISTRY WRITE BELOW CAN BE REFUSED, and the safe
                    # direction is to adopt anyway. If a NEWER session already
                    # holds this scope, the partial unique index rejects moving
                    # this row back to ``running``; ``_register_state`` logs
                    # that and does not raise. The container is still taken into
                    # ``_live``, which is what makes it stoppable — and being
                    # able to stop a container we can see beats a tidy row.
                    taken["error"] = (
                        f"the registry recorded this session as "
                        f"{act.get('row_state')!r} and its container was still "
                        f"running at start-up; the container is the fact, so "
                        f"the row was corrected.")
                with self._lock:
                    self._live[sid] = taken
                self._register_state(taken)
                performed.append({**act, "done": True})
            elif what == leansessions.STOP:
                killed, detail = self._kill_container(act.get("container") or "")
                logger.warning("stopped an unaccounted LEAN container %s: %s",
                               act.get("container"), detail)
                performed.append({**act, "done": killed, "detail": detail})
            elif what == leansessions.VANISHED:
                gone = dict(row or {})
                gone.update({"session_id": sid,
                             "state": leansessions.VANISHED,
                             "stopped_at": _now(),
                             "error": ("no container backed this session at "
                                       "start-up, so how it ended is UNKNOWN; "
                                       "it is recorded vanished rather than "
                                       "ended, which would claim we read an "
                                       "exit code.")})
                self._register_state(gone)
                performed.append({**act, "done": True})
            else:  # LEAVE or YOUNG — recorded, never touched
                performed.append({**act, "done": False})
        report = {**plan, "actions": performed}
        # RECORDED IN ONE PLACE, SO BOTH CALLERS RECORD IT. A stamp written by
        # the worker tick and not by the start-up pass would make a fresh spine
        # report ``never_run`` for its first five minutes — and the field exists
        # precisely so that reading means something.
        self._last_reconcile = {"at": _now(), "trigger": trigger,
                                "report": report}
        return report

    def last_reconciliation(self, *, stale_after_seconds: Optional[float] = None,
                            interval_seconds: Optional[float] = None
                            ) -> dict[str, Any]:
        """When a reconciliation last ACTED, folded into one readable state.

        The decision is ``leansessions.reconciliation_status``; this supplies
        the clock and the bound. ``stale_after_seconds`` defaults to twice the
        configured tick interval — one missed tick is a slow host, two is a
        worker that has stopped.
        """
        from app.fund import leansessions
        every = (RECONCILE_INTERVAL_SECONDS if interval_seconds is None
                 else interval_seconds)
        ceiling = (2.0 * every if stale_after_seconds is None
                   else stale_after_seconds)
        return leansessions.reconciliation_status(
            self._last_reconcile, _now(), ceiling, interval_seconds=every)

    def _run_live(self, session_id: str, signal_token: str, qty: float) -> None:
        from app.fund import leansessions
        session = self._live[session_id]
        algo_dir = (self._ws / "algorithms" / session["algorithm"]).resolve()
        res_dir = (self._ws / "results" / f"live-{session_id}").resolve()
        res_dir.mkdir(parents=True, exist_ok=True)

        # WHOSE CONTAINER THIS IS, on the container itself. Two spines in
        # different modes share one docker daemon and one `lean-live-`
        # namespace; without this the reconciler would call the other's session
        # an unaccounted orphan and stop it.
        #
        # OMITTED ENTIRELY WHEN THE MODE CANNOT BE READ, rather than written as
        # an empty string: `docker ps --format {{.Label "x"}}` returns "" for
        # BOTH "no such label" and "the label is empty", so an empty label would
        # be a claim indistinguishable from an absence. An absent label already
        # means "legacy, ours by name", which is the honest reading of a
        # container whose mode we could not record.
        label = ([] if not session.get("mode") else
                 ["--label", f"{leansessions.MODE_LABEL}={session['mode']}"])
        cmd = self._docker + [
            "run", "--rm", "--name", session["container"],
            *label,
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
        # ONLY IF THE ROW IS STILL ALIVE. This stamp arrives from a daemon
        # thread and can land after something else has retired the row; writing
        # it unconditionally resurrects a session with no container and
        # re-claims its strategy's scope.
        self._register_state(session, only_if_alive=True)
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
            # THE ROW MUST BE RELEASED OR THE SCOPE STAYS CLAIMED FOREVER. The
            # unique index is partial on the alive states, so a session that
            # ends without writing its terminal state would block every future
            # session for that strategy until start-up reconciliation cleared
            # it. In the `finally` for exactly that reason.
            self._register_state(session)

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
                        # LAST of the enrichers, because it reads what
                        # `_add_benchmark` decided: which series is the bar.
                        self._add_premia_inputs(job["result"])
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
            # DELIBERATELY NOT SERVED FROM THE BAR SNAPSHOT, and the reason is
            # worth recording because the first draft of this diff did consult
            # it. A snapshot is pinned at the lookback the ALGORITHM asks for
            # (700/900/2000); capacity wants 120 days. That request can never
            # match, so the consult was guaranteed to miss — and every miss is
            # recorded, so it marked EVERY candidate's data path non-uniform and
            # turned an honest signal into one that always cries wolf.
            #
            # It also buys nothing: capacity is computed ONCE per candidate, not
            # once per container, so this is a single fetch against a belt that
            # was making thousands.
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
                       code: Optional[str] = None,
                       population: Optional[dict[str, Any]] = None) -> None:
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
                # Labelled too, so no benchmark leaves here unlabelled. This
                # one bar genuinely carries no CROSS-SECTIONAL survivor
                # selection — it is the single name the strategy itself traded,
                # so the question is "did the timing add anything", not "were
                # these the right names". The name still came out of a
                # today-screened universe at research time, which is a
                # selection this payload cannot see and does not claim to.
                result["benchmark_population"] = {
                    "as_of": (result.get("equity_dates") or [None])[0],
                    "basis": "engine_single_name",
                    "population": sorted(traded_syms),
                    "wanted_count": len(traded_syms),
                    "usable": True,
                    "listing_asof_applied": False,
                    "survivorship_corrected": False,
                    "point_in_time": False,
                    "reason": (
                        "the engine's own bar for the one name this strategy "
                        "traded — no cross-sectional survivor selection is "
                        "possible in a single-name bar, but the name itself "
                        "was picked from a universe screened TODAY"),
                }
                # WHICH SERIES THE HEADLINE BENCHMARK NUMBER CAME FROM, stated
                # rather than inferred. On this branch the engine's own curve
                # is kept, so `daily_returns["benchmark"]` and
                # `benchmark_return_pct` describe the SAME bar. On the
                # recompute branch below they do not, and nothing said so —
                # see `premia_inputs`.
                result["benchmark_series_source"] = "engine_single_name"
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

        # WHICH POPULATION, not just which names. Both candidate sources above
        # are screened as of TODAY — `universe.py:115` builds the hunting ground
        # with `AssetStatus.ACTIVE`, and a strategy's UNIVERSE constant is a
        # frozen page of that screen — so a 2024 backtest is benchmarked against
        # the names that made it to 2026. This fund MEASURED that bias and never
        # wired the correction in (docs/SURVIVORSHIP_2026-08-17.md; the error
        # runs in the KILL direction, because the vanished names gained LESS
        # than the survivors rather than dying).
        #
        # The correction is only half available and the payload says which half:
        # look-ahead listing is closable where an as-of snapshot exists, and
        # survivorship is not closable at all while the delisted names carry no
        # bars. So the bar is still computed — an absent benchmark helps nobody —
        # and it now travels with a population label instead of arriving as a
        # bare number nothing can interrogate.
        population = population or _population_report(wanted, dates[0])
        result["benchmark_population"] = population
        if not population.get("usable"):
            result["benchmark_unavailable"] = (
                f"no name in the intended bar was listed on {dates[0]}, so "
                f"there is no population to hold — reported absent rather than "
                f"served from the survivor screen")
            return
        wanted = list(population["population"])

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
        from app.fund import barcache
        from app.fund.marketdata import fetch_daily_bars

        series: list[list[float]] = []
        used: list[str] = []
        ref_dates: list[str] = []
        feeds: list[str] = []
        leg_lengths: dict[str, int] = {}
        for sym in wanted:
            try:
                # Prefer the candidate's pinned leg. This is not only about
                # speed: it is the only way the sentence in this docstring —
                # "the identical feed the algorithm traded" — is actually TRUE.
                #
                # MEASURED 2026-08-22: it was not true before. fetch_daily_bars
                # takes Alpaca for a trailing lookback but falls to Yahoo the
                # moment BOTH start and end are given (marketdata.py:380), and
                # this call always gives both. So the strategy traded Alpaca
                # closes and was benchmarked against Yahoo ones. The two agree
                # to 0.46 bps mean / 0.7 bps max on SPY and TLT over 373 shared
                # sessions, and buy-and-hold total return moved 0.00pp — so this
                # was immaterial in magnitude, and it was still a comparison
                # between two vendors described in the record as one feed.
                # Serving both sides from one pinned leg removes the question.
                pinned = barcache.serve(sym, start=dates[0], end=dates[-1])
                bars = (pinned if pinned is not None
                        else fetch_daily_bars(sym, start=dates[0], end=dates[-1]))
            except Exception as e:  # noqa: BLE001
                logger.info("benchmark leg unavailable for %s: %s", sym, e)
                continue
            closes = list(bars.closes or [])
            if len(closes) < 2 or not closes[0]:
                continue
            series.append([c / closes[0] for c in closes])
            used.append(sym)
            feeds.append(getattr(bars, "source", None) or "unknown")
            leg_lengths[sym] = len(closes)
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
        #
        # TRUNCATION IS NOW REPORTED, NOT ONLY PERFORMED. This line cost 11.85pp
        # on Entry 20: one leg came back transiently short, every other leg was
        # cut to match it, and the benchmark return was computed over a window
        # shorter than the strategy's — with nothing in the result saying so, so
        # the gate compared two different windows and called it a comparison.
        # The candidate-scoped snapshot is the CAUSE fix (one fetch per leg, so
        # legs cannot disagree transiently); this is the DETECTOR, kept because
        # a genuine data gap can still shorten a leg and the reader must be told.
        n = min(len(x) for x in series)
        longest = max(len(x) for x in series)
        start_equity = equity[0]
        curve = [round(start_equity * sum(x[i] for x in series) / len(series), 2)
                 for i in range(n)]

        result["benchmark_curve"] = curve
        result["benchmark_dates"] = ref_dates[:n]
        if n < longest:
            short = sorted(s for s, ln in leg_lengths.items() if ln == n)
            result["benchmark_truncated"] = {
                "bars_used": n, "bars_longest_leg": longest,
                "dropped": longest - n, "shortest_legs": short,
                "note": (f"legs disagreed in length ({n} vs {longest} bars); the "
                         f"bar is computed over the shorter window, so it does "
                         f"NOT span the same period as the strategy's curve"),
            }
            logger.warning(
                "benchmark truncated to %d of %d bars — shortest leg(s): %s",
                n, longest, ", ".join(short))
        if len(set(feeds)) > 1:
            # Two vendors in one bar is not one feed, whatever the docstring
            # above says. Say it on the result rather than leave it to be
            # rediscovered by measurement, as it was on 2026-08-22.
            result["benchmark_feed_mixed"] = sorted(set(feeds))
        result["benchmark_feeds"] = sorted(set(feeds))
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
        # The engine's series was DISCARDED above and this one installed in its
        # place — so from here on `benchmark_return_pct` and
        # `daily_returns["benchmark"]` are two different bars. Marked, and the
        # size of the disagreement is measured in `premia_inputs`.
        result["benchmark_series_source"] = "recomputed_basket"

    @staticmethod
    def _add_premia_inputs(result: dict[str, Any]) -> None:
        """Both legs' moments, on ONE clock, against the bar the gate judges by.

        The cash leg's fetcher is passed EXPLICITLY rather than defaulted inside
        ``premia_inputs``, so that a caller which has no feed gets a stated
        absence instead of a network call it did not ask for — and so that the
        one production wiring of the rf source is visible at the belt's own call
        site rather than buried in a default argument.
        """
        result["premia_inputs"] = premia_inputs(result,
                                                rf_bars=_default_rf_bars)

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
            # WHAT THE BOOK ACTUALLY WEIGHED, from the engine's own chart. The
            # premia bar refuses a levered book because a backtest lends for
            # free (adversary D29, G1), and it can only refuse what it can see.
            # Read here rather than downstream because `charts` is discarded
            # four lines below — the same reason `daily_returns` is computed
            # here and not from the downsampled curve.
            "exposure": gross_exposure(charts),
            # AND WHAT IT WEIGHED ON EACH DAY, for the cash-carry credit. The
            # maxima above answer "was this book levered"; only the dated series
            # answers "how much of it sat in cash on the day the bar charged it
            # a cash rate". Stored rather than threaded through the enricher
            # because a premia payload that cannot be REBUILT from a stored
            # result is a payload no probe and no re-judgement can check — and
            # this fund verifies far more off stored results than off live runs.
            # MEASURED, not estimated (candidate 331b61ee31b1, 2026-08-24):
            # 42,490 bytes of invested weight — 1,937 dated readings — on a
            # 117,544-byte result whose `daily_returns` block is already 71,944
            # bytes and is carried for exactly the same reason. Reproduce with
            # `len(json.dumps(invested_weights(charts)))`.
            "invested_weight": invested_weights(charts),
            "orders": _orders(best),
            # `daily` is handed in UNDOWNSAMPLED and before the thinning above,
            # because the PSR capture needs the sample length the engine
            # actually scored — `equity` here is already 400 points.
            # `best.get("algorithmConfiguration")` carries the engine's own
            # `tradingDaysPerYear`, which is the clock the PSR's hardcoded
            # target is written against. Read from the RESULT rather than from
            # the sibling `-summary.json`, because the result is what this fund
            # stores and a hurdle recoverable only from a file on the belt
            # host's disk is not recoverable from a stored verdict.
            "robustness": _robustness(stats, equity, dates, _orders(best),
                                      daily,
                                      best.get("algorithmConfiguration")),
            "raw_files": sorted(p.name for p in res_dir.glob("*")),
        }


#: Every statistic in LEAN's block that could identify the formula behind the
#: number the gate's most binding criterion reads. Captured verbatim as the
#: engine wrote them (strings included) — a parsed float loses the "%" that
#: says which scale the engine was on, and this list exists precisely because
#: nobody could tell what scale ``Probabilistic Sharpe Ratio`` was on.
#:
#: THE MEASURED REASON (validator run-validator-jointpower, 2026-08-23,
#: docs/validator/VALIDATOR_JOINTPOWER_2026-08-23.md): ``min_psr_pct`` reads
#: this number verbatim, our own module's PSR describes a target-0 luck filter,
#: and the two disagree by 15x on the gate's true-positive rate at Sharpe 1.0
#: (24.7% documented vs 1.6% calibrated). Independently reproduced here on the
#: four stored candidates that carry analytics, by inverting the shipped form:
#: the implied target Sharpe is 1.3920 / 1.3917 / 1.3915 / 1.4907 annualised at
#: sqrt(252) — NOT zero, stable within a benchmark and window, and moving when
#: the window moves. Four constructions of a "benchmark Sharpe" from the
#: engine's own benchmark leg were tested against those figures and all four
#: were rejected (0.746 / 1.039 / 0.786 / 1.095 against a target of 1.392), so
#: the SOURCE of the target is still unidentified and only a run that captures
#: these fields can close it.
_PSR_IDENTIFYING_STATISTICS = (
    "Probabilistic Sharpe Ratio",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Annual Standard Deviation",
    "Annual Variance",
    "Compounding Annual Return",
    "Net Profit",
    # Benchmark-relative, and therefore the only trace in the block of what the
    # engine thought the benchmark was doing. The engine publishes no
    # "Benchmark Sharpe Ratio" key — verified against a real 27-key block
    # (candidate 144387901688) — so these FIVE are the identification.
    "Beta",
    "Alpha",
    "Information Ratio",
    "Tracking Error",
    "Treynor Ratio",
)


#: The engine statistics whose annualisation multiplies by ``sqrt(K)``, and
#: those that multiply by ``K``. Named rather than described, because the
#: correction factor differs between the two groups and a reader holding one
#: number for "the annualisation error" would apply the wrong one to variance.
#:
#: Source: LEAN annualises the per-observation moments by
#: ``Settings.TradingDaysPerYear``; standard deviation, Sharpe, Sortino,
#: tracking error and information ratio all carry ``sqrt(K)`` while variance
#: carries ``K``. ``Compounding Annual Return`` is deliberately in NEITHER
#: list: it is derived from the window's own elapsed time, not from K, so a
#: wrong K does not move it.
SQRT_ANNUALISED_STATISTICS: tuple[str, ...] = (
    "Annual Standard Deviation",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Tracking Error",
    "Information Ratio",
)
LINEARLY_ANNUALISED_STATISTICS: tuple[str, ...] = ("Annual Variance",)

#: How far the engine's annualisation factor may sit from the one the series'
#: own calendar asks for before the two are reported as DIFFERENT clocks.
#:
#: STATED, not measured, and the reason is stated with it so the next reader
#: does not have to guess which it was. The clocks that actually appear are a
#: small set of conventions — 252 (equity), 360, 365 and 365.25 — and the
#: question this tolerance answers is "same convention, or a different one?":
#:
#:   * 365 against 365.25 (the same convention, one carrying leap years) is
#:     0.034% on the factor and must read AGREE.
#:   * 360 against 365 is 0.69% and reads DISAGREE deliberately. It is small,
#:     but it is a real re-scaling of every statistic above and the reader is
#:     entitled to be told rather than to have it rounded away.
#:   * 252 against 365.25 — the case this whole function exists for — is 20.4%.
#:
#: 0.5% sits between the first two with room on both sides. It is a reporting
#: boundary and moves no verdict; see ``annualisation_clock``.
CLOCK_AGREEMENT_TOLERANCE = 0.005


def clocks_agree(series_obs_per_year: float, engine_obs_per_year: float) -> bool:
    """Are these two the SAME annualisation convention?

    Extracted as a named predicate rather than left inline, so the boundary is
    an ARGUMENT and can be probed from either side; through
    ``annualisation_clock`` it is whatever the date arithmetic happens to
    produce.

    Compares the ANNUALISATION FACTORS (``sqrt(K)``), not the clocks, because
    that is the number every statistic in ``SQRT_ANNUALISED_STATISTICS`` is
    actually multiplied by.

    The comparison is written ``<=``, and EXACT equality with the tolerance is
    provably unreachable rather than merely unlikely: ``factor - 1.0`` is exact
    for any factor in [0.5, 2), so its magnitude is always an integer multiple
    of 2^-53, while the double written ``0.005`` is 5764607523034235 / 2^60 —
    not such a multiple. Outside [0.5, 2) the difference exceeds 0.5. So a
    ``<``/``<=`` slip here changes no answer, and the proof is executable in
    ``tests/test_annualisation_clock.py`` so that it fails if the tolerance is
    ever moved to a value the comparison CAN land on.
    """
    factor = math.sqrt(series_obs_per_year) / math.sqrt(engine_obs_per_year)
    return abs(factor - 1.0) <= CLOCK_AGREEMENT_TOLERANCE


def _engine_clock(config: Optional[dict[str, Any]]) -> Optional[int | float]:
    """The run's own ``tradingDaysPerYear``, or None when it did not carry one.

    ONE reader, because ``psr_inputs`` and ``annualisation_clock`` both need
    it and two copies of "is this clock usable" is two beliefs wearing one
    name. Returns the value AS THE RUN WROTE IT — an int stays an int, so a
    stored payload does not change shape for having been read twice.

    ``math.isfinite`` as well as ``> 0``: a NaN fails every comparison, so
    ``tdy <= 0`` alone let NaN and inf through and the capture then reported
    them as the run's clock. Same guard, same reason, as
    ``statistics.lean_psr_target``.
    """
    tdy = (config or {}).get("tradingDaysPerYear") if isinstance(config, dict) else None
    if (isinstance(tdy, bool) or not isinstance(tdy, (int, float))
            or not math.isfinite(tdy) or tdy <= 0):
        return None
    return tdy


def annualisation_clock(daily: Optional[dict[str, Any]] = None,
                        config: Optional[dict[str, Any]] = None
                        ) -> dict[str, Any]:
    """On what clock did the ENGINE annualise, and does the series agree?

    THE CRYPTO BLOCKER, MADE VISIBLE RATHER THAN SILENTLY CORRECTED.

    LEAN annualises every statistic in ``SQRT_ANNUALISED_STATISTICS`` by
    ``Settings.TradingDaysPerYear``, and it takes that from the BROKERAGE
    MODEL rather than from the security type: 252 unless a crypto brokerage
    model is set, 365 when one is (LEAN documentation for
    ``Settings.TradingDaysPerYear``, read 2026-08-27). So a crypto algorithm
    that never calls ``set_brokerage_model`` is scored on an equity clock and
    every one of those statistics is understated by ``sqrt(365/252) = 1.2035``
    — including the Sharpe a human reads off the belt.

    OUR OWN numbers do not have this problem and that is worth saying plainly,
    because it decides what this function is for. Everything the fund computes
    itself — the premia legs, ``sharpe_annualised``, the advantage series —
    annualises by ``statistics.observations_per_year``, derived from the
    series' own dates, which is self-correcting across clocks (a mean scales
    with K and a standard deviation with sqrt(K), so the Sharpe lands on the
    same number either way; measured on four candidates in that function's
    docstring). The engine's published block is the part nobody can re-derive
    after the fact, so it is the part that needs a disclosure.

    **THIS FUNCTION RESCALES NOTHING.** It reports two clocks and the factor
    between them. Applying that factor to a criterion would be a threshold
    change, which is a versioned human decision and not a builder's.

    THE SIX STATES, each its own value, because "could not compare" covers
    three different facts and collapsing them is how an absence gets read as
    an agreement:

      * ``agree`` — the two factors are within ``CLOCK_AGREEMENT_TOLERANCE``.
      * ``engine_understates`` — the engine's clock is SHORTER than the
        series', so every sqrt-annualised statistic above is too small.
      * ``engine_overstates`` — the engine's clock is LONGER, so they are too
        large.
      * ``series_absent`` — no undownsampled daily series accompanied the
        result, so there is nothing to compare the engine against.
      * ``series_clock_unreadable`` — a series was present and its own clock
        could not be derived; ``series_clock_note`` carries
        ``observations_per_year``'s own reason verbatim.
      * ``engine_clock_absent`` — the series' clock is readable and the run's
        ``algorithmConfiguration`` did not carry ``tradingDaysPerYear``.

    PRECEDENCE IS STATED because two sides can fail at once: the state names
    the FIRST reason the comparison is impossible, and each side's own note
    field keeps its own reason regardless. A result with neither clock reads
    ``series_absent`` in ``state`` and still says so in ``engine_clock_note``.
    """
    from app.fund import statistics as _stats

    series = (daily or {}).get("strategy") if isinstance(daily, dict) else None
    dates = (daily or {}).get("dates") if isinstance(daily, dict) else None

    tdy = _engine_clock(config)
    engine_k: Optional[float] = None if tdy is None else float(tdy)
    engine_note: Optional[str] = (
        "this run's configuration carried no usable `tradingDaysPerYear`, so "
        "the clock the engine annualised on is UNKNOWN — absent, not the "
        "engine's default" if tdy is None else None)

    out: dict[str, Any] = {
        "engine_obs_per_year": engine_k,
        "engine_clock_note": engine_note,
        "series_obs_per_year": None,
        "series_clock_note": None,
        "engine_annualisation_factor": (None if engine_k is None
                                        else math.sqrt(engine_k)),
        "series_annualisation_factor": None,
        "factor_for_sqrt_annualised": None,
        "factor_for_linearly_annualised": None,
        "sqrt_annualised_statistics": list(SQRT_ANNUALISED_STATISTICS),
        "linearly_annualised_statistics": list(LINEARLY_ANNUALISED_STATISTICS),
        "tolerance": CLOCK_AGREEMENT_TOLERANCE,
        "state": None,
        "note": None,
    }

    # `observations_per_year` returns exactly two shapes — usable with a rate,
    # or unusable with a reason — and a third case never reaches it: no series
    # at all. All three get a disposition here rather than one falling through.
    if not isinstance(series, list) or not series:
        out["state"] = "series_absent"
        out["series_clock_note"] = (
            "no undownsampled daily series accompanied this result, so the "
            "clock it was actually observed on is UNKNOWN — absent, not 252")
        out["note"] = ("the engine's clock cannot be checked against anything: "
                       + out["series_clock_note"])
        return out

    clock = _stats.observations_per_year(dates or [], len(series))
    if not clock.get("usable"):
        out["state"] = "series_clock_unreadable"
        out["series_clock_note"] = clock.get("reason")
        out["note"] = ("the engine's clock cannot be checked against the "
                       "series: " + str(clock.get("reason")))
        return out

    series_k = float(clock["obs_per_year"])
    out["series_obs_per_year"] = round(series_k, 4)
    out["series_annualisation_factor"] = math.sqrt(series_k)

    if engine_k is None:
        out["state"] = "engine_clock_absent"
        out["note"] = ("the series carries "
                       f"{series_k:.2f} observations a year; " + str(engine_note))
        return out

    # The correction a reader would apply to the engine's own figures: the
    # factor the series asks for, over the factor the engine used.
    sqrt_factor = math.sqrt(series_k) / math.sqrt(engine_k)
    out["factor_for_sqrt_annualised"] = round(sqrt_factor, 6)
    out["factor_for_linearly_annualised"] = round(series_k / engine_k, 6)

    if clocks_agree(series_k, engine_k):
        out["state"] = "agree"
        out["note"] = (f"the engine annualised on {engine_k:g} observations a "
                       f"year and the series carries {series_k:.2f} — the same "
                       f"clock within {CLOCK_AGREEMENT_TOLERANCE:.1%}")
        return out

    out["state"] = ("engine_understates" if sqrt_factor > 1.0
                    else "engine_overstates")
    direction = "UNDERSTATES" if sqrt_factor > 1.0 else "OVERSTATES"
    out["note"] = (
        f"the engine annualised on {engine_k:g} observations a year while the "
        f"series carries {series_k:.2f}, so every statistic in "
        f"`sqrt_annualised_statistics` {direction} by x{sqrt_factor:.4f} "
        f"(variance by x{series_k / engine_k:.4f}). Nothing here rescales the "
        f"engine's figures — moving a verdict on this factor is a threshold "
        f"change")
    return out


def psr_inputs(stats: dict, daily: Optional[dict[str, Any]] = None,
               config: Optional[dict[str, Any]] = None
               ) -> dict[str, Any]:
    """Everything that could identify the formula behind the reported PSR.

    Capture, and NO CRITERION'S PASS/FAIL READS ANY OF IT — wiring one to a
    verdict would be a threshold change. What it buys is that the next reader
    can answer "against what target?" from a stored verdict instead of from a
    new belt run.

    ONE FIELD IS READ ON THE GATE SIDE, and D38 states the boundary rather than
    leaving the sentence above quietly false: `_luck_leg` reads
    ``trading_days_per_year`` to state the engine's hurdle in the failure
    sentence. The engine hurdle's verdict is ``psr_pct >= min_psr_pct`` and
    touches neither the target nor the clock, so what this field moves is a
    DISCLOSURE. A future change that let it move a verdict is the threshold
    change this paragraph exists to make visible.

    Four things travel together and they answer different halves of the
    question:

      * ``statistics`` — the engine's own numbers, verbatim, unparsed.
      * ``observations`` — how long the series the engine scored actually was.
        PSR's z-statistic scales with sqrt(n-1), so a PSR without an n is not
        interpretable at all, and the belt has never stored one.
      * ``engine_volatility_reproduction`` — whether the engine's published
        ``Annual Standard Deviation`` is still the calendar-clock standard
        deviation times sqrt of THE RUN'S OWN CLOCK. It was on all four stored
        candidates (0.11627 computed against 0.116 published, at the 252 they
        all carry); if a future engine build changes the FORMULA, this is the
        field that says so instead of a silent 17% shift in a statistic nobody
        re-derives. A run at a different CLOCK is not a formula change, which
        is why the clock is read here rather than typed.
      * ``annualisation_clock`` — whether the clock the engine used is the one
        the series it scored was actually observed on. That is a different
        question from the one above and it is the crypto blocker: a 24/7
        series annualised at 252 understates every sqrt-annualised statistic
        by 1.2035, and no other field on a stored verdict would say so.
      * ``trading_days_per_year`` and ``target`` — the run's OWN
        ``algorithmConfiguration.tradingDaysPerYear``, and the PSR hurdle that
        follows from it. This is the falsifier for the whole engine-hurdle
        story made mechanical: the target is ``1/sqrt(tradingDaysPerYear)``
        (``statistics.lean_psr_target``), so a LEAN image that ships a
        different clock moves the hurdle, and the only way to notice was to
        grep new summary files by hand. Captured, so a stored verdict can be
        re-read against the hurdle it was actually judged against. MEASURED at
        capture time: 252 on 276 of 276 stored ``-summary.json`` files.
    """
    tdy = _engine_clock(config)
    # Computed ONCE, before the early return below, so a result with no daily
    # series still carries the clock block saying WHY it could not be checked
    # rather than carrying nothing at all.
    clock_block = annualisation_clock(daily, config)
    from app.fund import statistics as _stats
    out: dict[str, Any] = {
        "statistics": {k: stats.get(k) for k in _PSR_IDENTIFYING_STATISTICS
                       if k in stats},
        "statistics_missing": [k for k in _PSR_IDENTIFYING_STATISTICS
                               if k not in stats],
        # ABSENT WHEN ABSENT. A run whose configuration this fund did not
        # capture must not report the engine's default as if it had been read;
        # `target.assumed` then says the hurdle rests on the default.
        "trading_days_per_year": tdy,
        "target": _stats.lean_psr_target(tdy),
        # WHICH CLOCK, AND DOES THE SERIES AGREE. The field above says what the
        # engine used; this says whether that was the right one for the series
        # it scored. On a crypto run those differ by 1.2035 and nothing else on
        # a stored verdict would say so.
        "annualisation_clock": clock_block,
        "benchmark_sharpe_published": (
            # Named as an ABSENCE rather than left out. The engine's statistics
            # block does not carry the target; its SOURCE does, and the two are
            # different statements — see the note below.
            stats.get("Benchmark Sharpe Ratio")),
        "benchmark_sharpe_note": (
            None if "Benchmark Sharpe Ratio" in stats else
            "the engine's statistics block publishes NO benchmark Sharpe, so "
            "the PSR's target is not readable from the RESULT — but it is not "
            "unpublished: LEAN hardcodes it at 1/sqrt(tradingDaysPerYear), an "
            "annualised Sharpe of exactly 1.00, and `target` above states it. "
            "Inverting it out of the reported PSR is a CHECK on that constant "
            "(statistics.implied_target_sharpe), never the way to learn it"),
    }
    series = (daily or {}).get("strategy") if isinstance(daily, dict) else None
    dates = (daily or {}).get("dates") if isinstance(daily, dict) else None
    if not isinstance(series, list) or not series:
        out["observations"] = {
            "n": None,
            "note": ("no undownsampled daily series accompanied this result, so "
                     "the sample length behind the PSR is UNKNOWN — absent, not "
                     "zero"),
        }
        return out
    clock = _stats.observations_per_year(dates or [], len(series))
    out["observations"] = {
        "n": len(series),
        "first": clock.get("first"),
        "last": clock.get("last"),
        "obs_per_year": (None if not clock.get("usable")
                         else round(float(clock["obs_per_year"]), 2)),
        "zero_return_days": sum(1 for x in series if x == 0.0),
        "clock_note": (None if clock.get("usable") else clock.get("reason")),
    }
    # ONE unit reader, shared with `_robustness`. Two copies of "is this a
    # fraction or a percentage" is the two-copies-of-one-belief defect, and the
    # failure would be a `reproduces: False` that means nothing more than the
    # engine changed its formatting.
    published = _annual_vol_fraction(stats)
    _, sd = _stats.mean_std(series)
    # THE CLOCK IS READ FROM THE RUN, NOT RE-TYPED. This was a literal
    # `sqrt(252.0)` — a hardcoded duplicate of the `tradingDaysPerYear` this
    # same function already read at its top. The duplicate AGREED on every
    # result this fund has stored, which is exactly why nothing noticed:
    # MEASURED 2026-08-27, 196 of 196 stored result files carrying an
    # `algorithmConfiguration` write 252 and no other value appears (359 result
    # files read in total; reproduce by folding
    # `lean_workspace/results/*/*.json` through `_engine_clock`). It would have
    # started disagreeing on the first crypto run: a candidate scored at 365
    # would have reported `reproduces: False`, which reads as "the engine
    # changed its formula" when what actually happened is that the checker used
    # the wrong clock.
    #
    # When the run's configuration did not carry a clock, the DOCUMENTED
    # default is used and the payload SAYS SO (`clock_assumed`), the same way
    # `statistics.lean_psr_target` names its own assumption — a 252 that was
    # read and a 252 that was assumed are different facts.
    repro_clock = clock_block.get("engine_obs_per_year")
    clock_assumed = repro_clock is None
    if clock_assumed:
        repro_clock = float(_stats.LEAN_TRADING_DAYS_PER_YEAR)
    recomputed = sd * math.sqrt(float(repro_clock)) if sd else None
    out["engine_volatility_reproduction"] = {
        "published_annual_standard_deviation": published,
        # Named for what it IS rather than for the constant it used to carry.
        # The old key was `series_stdev_times_sqrt_252`, whose name would have
        # been a lie on any run at another clock; nothing outside this module's
        # own tests ever read it.
        "series_stdev_annualised": (None if recomputed is None
                                    else round(recomputed, 5)),
        "clock": float(repro_clock),
        "clock_assumed": clock_assumed,
        # The rule holds when the two agree to the three decimals the engine
        # prints. Stated as a comparison rather than asserted as a fact,
        # because this is the check, not the claim.
        "reproduces": (None if published is None or recomputed is None
                       else abs(published - recomputed) < 5e-4),
        "note": ("the engine's annualisation multiplies a CALENDAR-day series "
                 f"by sqrt({repro_clock:g})"
                 + (" — ASSUMED, this run's configuration carried no clock"
                    if clock_assumed else " — the clock this run reported")
                 + "; whether that clock matches the one the series was "
                   "actually observed on is `annualisation_clock` above, and "
                   "on this fund's equity runs it does not: the trading-day "
                   "truth is larger by roughly sqrt(365.25/252) = 1.2039, "
                   "measured 1.2033 to 1.2047 across the four stored "
                   "candidates, since the real calendar-to-trading ratio "
                   "varies with the window's holidays"),
    }
    return out


def _returns_from_curve(curve: Any, dates: Any) -> dict[str, float]:
    """Date -> simple return, from a level series. Breaks the chain on a bad level.

    Same rule as ``_daily_returns``: a non-positive or non-finite level ends the
    chain instead of dividing, so one bad bar cannot emit an infinity.
    """
    out: dict[str, float] = {}
    if not isinstance(curve, list) or not isinstance(dates, list):
        return out
    if len(curve) != len(dates) or len(curve) < 2:
        return out
    prev: Optional[float] = None
    for level, d in zip(curve, dates):
        ok = isinstance(level, (int, float)) and math.isfinite(level) and level > 0
        if ok and prev is not None and prev > 0:
            out[str(d)[:10]] = level / prev - 1.0
        prev = float(level) if ok else None
    return out


#: The cash leg is fetched with a PAD on BOTH ends, for two different measured
#: reasons, and the pad cannot widen what is reported because the rf series is
#: intersected with the strategy's own dates before anything is computed.
#:
#:   * AT THE END, because the feed's window is EXCLUSIVE there. Measured
#:     2026-08-23: ``fetch_daily_bars("BIL", start="2026-08-01",
#:     end="2026-08-21")`` returns 14 bars ending **2026-08-20**. Without a pad
#:     the last session of every candidate's window would silently drop out of
#:     the comparison.
#:   * AT THE START, because a return is keyed on its LATER date. The first
#:     date of a window has no return unless the price series reaches one
#:     session behind it.
#:
#: Seven CALENDAR days covers the longest ordinary US market closure — a
#: Thursday holiday plus the Friday and the weekend is four consecutive closed
#: days, so the gap between two sessions reaches five — and nothing depends on
#: the exact figure: a pad that is too short shows up as ``rf_dropped_days``,
#: never as a silently shorter window.
RF_FETCH_PAD_DAYS = 7


def _round_or_none(value: Any, places: int) -> Optional[float]:
    """Round for storage, keeping an ABSENCE absent. ``round(None)`` raises and
    ``round(x or 0)`` would turn an unreadable figure into a zero, which is the
    one thing this codebase does not do."""
    return None if value is None else round(float(value), places)


def _shift_date(iso: str, days: int) -> str:
    """ISO date shifted by whole calendar days. Returns the input if unparseable."""
    from datetime import date as _date, timedelta as _timedelta
    try:
        return (_date.fromisoformat(str(iso)[:10])
                + _timedelta(days=days)).isoformat()
    except ValueError:
        return str(iso)[:10]


#: How far the SESSION CALENDAR may fall short of either end of the strategy's
#: span — or gap in the middle of it — and still be said to COVER it, in
#: calendar days.
#:
#: THE MEASURED BASIS, and it is the same fact ``RF_FETCH_PAD_DAYS`` is sized
#: from rather than a second guess at it: the longest run of consecutive CLOSED
#: days on a US equity calendar is four (a Thursday holiday, the Friday and the
#: weekend), so two consecutive SESSIONS can be five calendar days apart. The
#: strategy's own first and last dates come from LEAN's equity curve, which
#: emits a point every CALENDAR day, so either end can legitimately land on a
#: day the market was shut. Five is therefore the largest gap a fully-covering
#: session series can show at an end; anything beyond it is missing data, not a
#: weekend. (``RF_FETCH_PAD_DAYS`` is seven — the same five with two days of
#: slack, because a pad that is too short is visible as `rf_dropped_days` while
#: a tolerance that is too long is not visible at all.)
SESSION_SPAN_TOLERANCE_DAYS = 5


def _days_between(first: str, last: str) -> Optional[int]:
    """Whole calendar days from ``first`` to ``last``, or absent if unparseable.

    Absent, never zero: a date this cannot read must not be reported as a
    perfect fit, which is exactly what a ``0`` would mean to the caller.
    """
    from datetime import date as _date
    try:
        return (_date.fromisoformat(str(last)[:10])
                - _date.fromisoformat(str(first)[:10])).days
    except (ValueError, TypeError):
        return None


def _session_span(session_days: list[str], first: str, last: str
                  ) -> dict[str, Any]:
    """Does the session calendar actually COVER the strategy's whole span?

    Written for ground G2 of the D29 blind review: the session denominator is
    the union of the bar's dates and the cash leg's, and both are fetched
    through the same function — so a vendor tail-lag truncates them TOGETHER,
    the union collapses onto the shared window, and the majority test compares a
    window with itself. Measured on the reviewer's own characteriser
    (``scratchpad/adv29/probeF.py``): with the bar and the cash leg both cut at
    15.6% of the run, the test read 214 of 214 and PASSED.

    THE CHECK IS ON THE UNION, NOT ON THE CASH LEG ALONE, and that is a
    deliberate departure from the review's wording — stated here rather than
    quietly. "The cash leg spans the run" would ALSO refuse the case where the
    bar is complete and only the cash leg is short, where the bar is a perfectly
    truthful session calendar and the comparison already fails on `common_days`
    anyway; measured, that wording turns an existing invariant
    (`test_a_cash_series_that_stops_early_drops_days_and_SAYS_SO`: a short cash
    leg must make the majority test HARDER, not easier) into a fallback to the
    CALENDAR basis, which is the very weekends-versus-sessions comparison v5r2
    removed. The union form refuses exactly the correlated-truncation case the
    kill describes and nothing else.

    AND IT CHECKS FOR A HOLE, which neither wording covers: a vendor outage over
    the same middle stretch of BOTH legs reaches the run's first and last dates
    while covering none of its centre, and the union would then undercount the
    denominator exactly where the comparison is thinnest. The largest gap
    BETWEEN consecutive session dates is therefore checked with the same
    tolerance as the two ends. (A bar cut at the END beside a cash leg starting
    LATE is the shape one reaches for first and it cannot arrive here: with no
    overlap the two legs share no common window and `premia_inputs` refuses
    earlier — verified, not assumed.)

    Reports the gaps in days rather than a bare boolean, because the interesting
    question when this fires is *by how much* — a two-day lag and a five-year
    truncation are the same `False`.
    """
    out: dict[str, Any] = {
        "vouched": False,
        "strategy_first": first, "strategy_last": last,
        "session_first": None, "session_last": None,
        "head_shortfall_days": None, "tail_shortfall_days": None,
        "largest_internal_gap_days": None,
        "tolerance_days": SESSION_SPAN_TOLERANCE_DAYS,
        "basis": "the union of the bar's dates and the cash leg's",
        "reason": None,
    }
    if not session_days:
        out["reason"] = ("no session calendar was readable, so nothing vouches "
                         "for how many sessions this run contained")
        return out
    out["session_first"], out["session_last"] = session_days[0], session_days[-1]
    head = _days_between(first, session_days[0])
    tail = _days_between(session_days[-1], last)
    gaps = [_days_between(a, b)
            for a, b in zip(session_days, session_days[1:])]
    if head is None or tail is None or any(g is None for g in gaps):
        out["reason"] = ("the strategy's span or the session dates could not be "
                         "read as dates, so their coverage is unknown")
        return out
    head, tail = max(head, 0), max(tail, 0)
    biggest = max(gaps) if gaps else 0
    out["head_shortfall_days"] = head
    out["tail_shortfall_days"] = tail
    out["largest_internal_gap_days"] = biggest
    worst = max(head, tail, biggest)
    if worst > SESSION_SPAN_TOLERANCE_DAYS:
        out["reason"] = (
            f"the session calendar {session_days[0]}..{session_days[-1]} does "
            f"not cover the strategy's span {first}..{last}: {head} day(s) "
            f"missing at the start, {tail} at the end and a largest internal "
            f"gap of {biggest}, past the {SESSION_SPAN_TOLERANCE_DAYS}-day "
            f"tolerance a closed market can explain — so it cannot say how many "
            f"sessions the run contained")
        return out
    out["vouched"] = True
    return out


def _default_rf_bars(symbol: str, start: str, end: str) -> Any:
    """The fund's own feed. Kept as a NAMED function, not a lambda, so a caller
    can substitute it and a test can assert which one ran.

    IT DOES NOT CONSULT THE BAR SNAPSHOT, and that is deliberate — the first
    version did, and `test_the_consult_sites_are_exactly_the_two_belt_side_ones`
    caught it within the hour. A candidate's snapshot pins the legs the
    ALGORITHM declares; the cash instrument is never one of them, so the consult
    would MISS on every candidate that ever ran, and a recorded miss is what
    makes `uniform_data_path` False. That is the `_add_capacity` defect
    (leanrunner, 2026-08-22: a 120-day request against legs pinned at 700/900/
    2000, guaranteed to miss, marking every candidate's data path non-uniform)
    arriving a second time on a different symbol. A consult site that can never
    hit is worse than none.

    THE HONEST CONSEQUENCE, and it is reported rather than hidden: the cash leg
    is NOT pinned to the candidate's snapshot, so it is fetched live and its
    vendor is whatever `fetch_daily_bars` resolves for a start+end window
    (Yahoo, measured 2026-08-23). `rf.pinned` is therefore False on every run
    today, and `rf.source` names the vendor. Pinning it properly means adding
    the cash symbol to the snapshot the belt takes, which is a belt change and
    is not in this diff.
    """
    from app.fund.marketdata import fetch_daily_bars
    return fetch_daily_bars(symbol, start=start, end=end)


def rf_series(symbol: str, first: str, last: str,
              fetcher: Any = None) -> tuple[dict[str, float], dict[str, Any]]:
    """The REALISED cash return per observation over a window, from the feed.

    Returns ``(date -> return, meta)``. ``meta["measurable"]`` is False with a
    stated reason whenever the series cannot be read — never an assumed zero and
    never an assumed constant, because assuming either is exactly the defect the
    constitution's excess-returns amendment (2026-08-21) was written against:
    *"under rf=0 with free leverage, T-bill carry impersonates edge."*

    The returns are keyed on their LATER date and derived by the same function
    that derives the benchmark leg (``_returns_from_curve``), so the cash leg,
    the strategy leg and the bar all span the same session-to-session intervals.
    """
    meta: dict[str, Any] = {
        "symbol": symbol,
        "measurable": False,
        "reason": None,
        # STATED, not detected. The first version wrote
        # `bool(getattr(bars, "taken_at", None))` — and `SnapshotLeg` has no
        # `taken_at` (it lives on `BarSnapshot`), so the field could never have
        # been True. A flag that can only report one value is not a measurement;
        # it is a decoration that a reader will eventually believe. The cash leg
        # is not pinned today, for the reason in `_default_rf_bars`, and this
        # says so in every stored payload until that changes.
        "pinned": False,
        "pinned_note": ("the cash leg is fetched live, not served from the "
                        "candidate's bar snapshot — the snapshot pins the "
                        "algorithm's declared legs and the cash symbol is never "
                        "one of them"),
        "source": None,
        # TWO WINDOWS, because they are two different facts and conflating them
        # would make a reader think the feed was asked a question it was not.
        # `span_requested` is what the run is ABOUT; `fetch_window` is what the
        # feed was asked FOR, padded at both ends for the reasons in
        # RF_FETCH_PAD_DAYS.
        "span_requested": {"first": first, "last": last},
        "fetch_window": None,
    }
    if fetcher is None:
        meta["reason"] = (
            f"no risk-free source was supplied for this run, so the cash return "
            f"over its window is UNKNOWN — a premia claim is measured over "
            f"EXCESS returns (constitution, 2026-08-21), and an unknown cash "
            f"rate is not a zero one")
        return {}, meta
    start = _shift_date(first, -RF_FETCH_PAD_DAYS)
    end = _shift_date(last, RF_FETCH_PAD_DAYS)
    meta["fetch_window"] = {"first": start, "last": end}
    try:
        bars = fetcher(symbol, start, end)
    except Exception as e:  # noqa: BLE001
        meta["reason"] = (f"the cash series {symbol} could not be fetched over "
                          f"{start}..{end}: {e}")
        return {}, meta
    if bars is None:
        meta["reason"] = (f"the feed returned no cash series for {symbol} over "
                          f"{start}..{end}")
        return {}, meta
    meta["source"] = getattr(bars, "source", None) or "unknown"
    rmap = _returns_from_curve(list(getattr(bars, "closes", None) or []),
                               [str(d)[:10] for d in
                                (getattr(bars, "dates", None) or [])])
    if len(rmap) < 2:
        meta["reason"] = (f"the cash series {symbol} yielded {len(rmap)} usable "
                          f"return(s) over {start}..{end}")
        return {}, meta
    meta["measurable"] = True
    return rmap, meta


def premia_inputs(result: dict[str, Any], rf_bars: Any = None,
                  rf_symbol: Optional[str] = None) -> dict[str, Any]:
    """The two legs a premia claim is judged on, measured the SAME way.

    THE DEFECT THIS EXISTS TO CLOSE, and it is measured, not argued. The
    payload already carries an aligned daily pair in ``daily_returns`` — and
    its BENCHMARK leg is the series ``_add_benchmark`` DISCARDED. On the three
    stored ``monthend_rebalance_flow`` candidates the discarded engine leg
    compounds to +110.9% while the bar the gate's own ``must_beat_benchmark``
    criterion uses returned +41.55%; on ``announcement_premium`` it is +19.8%
    against +84.78%. Judging a Sharpe comparison off the wrong leg FLIPS the
    premia answer on three of those four: the monthend runs read 0.662 against
    a benchmark 0.898 (fail) on the discarded leg and 0.681 against 0.574
    (pass) on the real one.

    So the benchmark leg here is derived from ``benchmark_curve`` /
    ``benchmark_dates`` — the same numbers ``benchmark_return_pct`` is computed
    from, and the derivation reproduces it to 0.002pp on all four stored
    candidates (41.552 vs 41.55; 84.782 vs 84.78). Where the engine's own curve
    was KEPT (a single-name strategy), the two legs are the same series and
    ``daily_returns`` is used directly.

    THE SECOND DEFECT THIS CLOSES, added 2026-08-23 after the adversary's blind
    KILL of v5r1 (docs/reviews/ADVERSARY_D23_D24_2026-08-23.md). v5r1 judged the
    inequality at an ASSUMED risk-free rate of 0% and stressed it at a CONSTANT
    4.0%. The constant was rounded up from BIL's 3.97%/yr on ONE window and the
    belt does not run on that window; on three of the four windows the belt
    actually uses, the stress was SOFTER than the cash the window paid, which is
    the one condition under which a cash tilt survives it. Eleven of sixteen
    zero-skill cash/beta blends PASSED while their true excess-Sharpe advantage
    was between −0.0004 and +0.03.

    THE PER-WINDOW RATES ARE A TABLE IN ``gate.PREMIA_VERSION``'s note and are
    deliberately NOT restated here. Two copies of one measurement is how a
    comment stops describing the thing it names (D19: a gate shipped with the
    same arm at "5 folds / 4.17%" in one docstring and "6 folds / 5.17%" in
    another, both true of something and only one true of what shipped).

    So this function now carries the REALISED cash series over the candidate's
    own window — ``strategy_excess`` and ``benchmark_excess``, both legs net of
    the SAME per-observation cash return, read from the fund's own feed — and
    reports ``excess_measurable: False`` with a reason when no rf series covers
    the window. Absence is never zero, and a premia claim whose cash rate is
    unknown is NOT MEASURABLE rather than passed.

    THREE PROPERTIES, each of which is a way the comparison could lie:

      * ONE WINDOW. All three legs — strategy, bar and cash — are cut to the
        dates they share, and the window is reported. ``must_beat_benchmark``
        compares two totals measured over DIFFERENT windows — on candidate
        144387901688 the strategy runs to 2026-08-21 and its bar stops at
        2026-08-04 — and that is a pre-existing defect this function declines to
        inherit. What the cash leg's own alignment costs is reported as
        ``coverage.rf_dropped_days`` rather than absorbed silently.
      * ONE CLOCK. The intersection is a SESSION calendar — the benchmark's
        dates, narrowed by the cash series' — so the weekend zeros LEAN pads
        the equity curve with drop out of every leg. The annualisation factor
        is then derived from the surviving dates
        (``statistics.observations_per_year``), never assumed.
      * ONE METHOD. Volatility, drawdown and total return come from the same
        function for both legs. Reading the strategy's drawdown off the engine
        and the benchmark's off a series is two measurements pretending to be
        a comparison.

    Returns ``measurable: False`` with a reason whenever either leg is absent.
    A premia claim that cannot be measured has not been established.

    THE THIRD DEFECT THIS CLOSES, added 2026-08-23 after the adversary's blind
    KILL of v5r2 (docs/reviews/ADVERSARY_D29_2026-08-23.md, ground G1).
    Subtracting a realised cash rate closes the carry channel only for a book
    whose GROSS EXPOSURE is at most 100%. A backtest lends for free, so above
    that the borrow is a gift that grows with the cash weight, and the payload
    said nothing about leverage at all. ``max_gross_exposure`` and
    ``gross_measurable`` are carried here from the engine's own exposure chart
    (``gross_exposure``), and the gate refuses what it cannot measure.

    THE FOURTH DEFECT THIS CLOSES, added 2026-08-24 from the positive-control
    round (quant, run-quant-metacontrols). Subtracting the realised cash rate
    from a book that HELD cash charges it a rate the engine never paid it: LEAN
    pays 0% on idle balances. The correction is per observation and it is
    ``w_t * rf_t`` in place of ``rf_t`` — see ``invested_weights`` for the
    arithmetic and for why the benchmark leg is not credited. It ADMITS
    candidates, which is why it is versioned, disclosed and adversary-reviewed
    rather than shipped as a bug fix.

    AND THE ADVANTAGE ITSELF IS NOW MEASURED, not only the two legs. A premia
    claim asserts that ``SR_s - SR_b`` is positive, so ``advantage`` carries the
    moments of the series whose mean IS that difference
    (``statistics.sharpe_advantage_series``) and the gate's luck filter scores
    THAT rather than the strategy's absolute Sharpe.

    FOUR MEASURABILITY FLAGS, deliberately, because they answer different
    questions and only three of them are read by a criterion.
    ``measurable`` is the RAW pair — it gates ``gate.volatility_check``, which
    is capture only, and its meaning is unchanged from schema 1.
    ``excess_measurable`` is the pair the premia CRITERION is judged on, and it
    is False whenever the cash leg could not be read. ``gross_measurable`` says
    whether the book's leverage is known, and it is INDEPENDENT of both: a run
    can have a perfect excess pair and an unreadable exposure chart, and that
    run's premia claim is not measurable even though its Sharpe is.
    ``cash_credit["measurable"]`` says whether the invested weight is known, and
    ``excess_measurable`` is INDEPENDENT of it — deliberately, and this sentence
    is the corrected one (the draft claimed a dependency the code never had;
    adversary, run-adversary-d36-prodgate2). ``excess_measurable`` keeps its
    v5r3 meaning and is computed from the UNCREDITED pair, because the uncredited
    pair is what the shipped criterion judges: ``premia_credit_idle_cash`` is
    OFF, and a candidate whose invested weight could not be read must still be
    judgeable on the bar that is actually applied. Coupling the two would have
    made a credit outage refuse candidates the shipped bar can measure
    perfectly well. Collapsing any of them would make one outage delete another
    capture.
    """
    from app.fund import statistics as _stats

    out: dict[str, Any] = {"measurable": False, "excess_measurable": False,
                           "gross_measurable": False, "schema": 4}
    # THE BOOK'S LEVERAGE, carried into the premia payload BEFORE any of the
    # early returns below. A payload that says nothing about gross exposure is
    # the payload the D29 kill was written about, and a reader should get the
    # answer — including "unknown, and here is why" — from every one of them,
    # not only from the ones that got as far as computing a Sharpe.
    ex = result.get("exposure")
    ex = ex if isinstance(ex, dict) else {
        "measurable": False, "max_gross": None,
        "reason": ("this result carries no exposure capture at all — it was "
                   "measured by a belt older than the one that reads the "
                   "engine's exposure chart")}
    out["exposure"] = ex
    out["gross_measurable"] = bool(ex.get("measurable")
                                   and ex.get("max_gross") is not None)
    out["max_gross_exposure"] = (float(ex["max_gross"])
                                 if out["gross_measurable"] else None)
    daily = result.get("daily_returns")
    if not isinstance(daily, dict) or not daily.get("present"):
        out["reason"] = (
            "no undownsampled daily series on this result, so neither leg can "
            "be measured — absent, not zero"
            + (f" ({daily.get('reason')})" if isinstance(daily, dict)
               and daily.get("reason") else ""))
        return out

    s_dates = [str(d)[:10] for d in (daily.get("dates") or [])]
    s_rets = list(daily.get("strategy") or [])
    if len(s_dates) != len(s_rets) or len(s_rets) < 2:
        out["reason"] = ("the strategy leg and its dates are not the same "
                         "length, so the pair cannot be placed on a clock")
        return out
    smap = dict(zip(s_dates, s_rets))

    source = result.get("benchmark_series_source")
    bmap: dict[str, float] = {}
    if source == "recomputed_basket":
        bmap = _returns_from_curve(result.get("benchmark_curve"),
                                   result.get("benchmark_dates"))
    elif source == "engine_single_name":
        b_rets = list(daily.get("benchmark") or [])
        if daily.get("benchmark_present") and len(b_rets) == len(s_dates):
            bmap = dict(zip(s_dates, b_rets))
    out["benchmark_leg_source"] = source
    if not bmap:
        out["reason"] = (
            f"no benchmark leg could be built (series source "
            f"{source!r}) — a premia claim is a comparison, and there is "
            f"nothing here to compare against"
            + (f": {result['benchmark_unavailable']}"
               if result.get("benchmark_unavailable") else ""))
        return out

    pair_days = sorted(set(smap) & set(bmap))
    if len(pair_days) < 2:
        out["reason"] = (f"the two legs share {len(pair_days)} date(s); there is "
                         f"no common window to measure either of them on")
        return out

    # --- the cash leg -----------------------------------------------------
    # READ OVER THE CANDIDATE'S OWN WINDOW, never a fixed one: a rate fitted on
    # one window is a threshold that silently changes meaning with every
    # backtest date (the adversary's rule, D23 review).
    #
    # And specifically over the STRATEGY'S SPAN, not the strategy-and-bar
    # intersection. Fetching over the intersection looked equivalent and is not:
    # when the BAR is the short leg — the Entry 20 truncation, 11.85pp — the
    # cash leg would be cut to match it, and then neither series could say how
    # many sessions the strategy's run actually contained. The coverage
    # denominator below depends on exactly that, and a denominator that shrinks
    # with the leg it is measuring is a majority test that gets EASIER the more
    # is missing.
    if rf_symbol is None:
        from app.fund.gate import PREMIA_CRITERIA as _PC
        rf_symbol = str(_PC["premia_rf_symbol"])
    rfmap, rf_meta = rf_series(rf_symbol, s_dates[0], s_dates[-1],
                               fetcher=rf_bars)
    out["rf"] = rf_meta

    # ONE WINDOW for everything the criterion reads. When the cash leg is
    # readable the window is the three-way intersection; when it is not, the
    # raw pair is still captured on its own window so the volatility fields
    # survive an rf outage, and `excess_measurable` stays False.
    common = sorted(set(pair_days) & set(rfmap)) if rfmap else pair_days
    if len(common) < 2:
        rf_meta["measurable"] = False
        rf_meta["reason"] = (
            f"the cash series {rf_symbol} shares {len(common)} date(s) with the "
            f"strategy/bar window {pair_days[0]}..{pair_days[-1]} — there is no "
            f"window on which an excess return could be formed")
        common, rfmap = pair_days, {}
    strat = _stats.leg_moments([smap[d] for d in common], common)
    bench = _stats.leg_moments([bmap[d] for d in common], common)

    # THE HONEST DENOMINATOR for "did this comparison cover the run".
    #
    # v5r1 divided TRADING days by CALENDAR days: LEAN emits one equity point
    # per calendar day, so `strategy_days` counts weekends the market was shut
    # and the fraction sat at 0.67-0.69 on all 15 real specimens — roughly
    # 252/365 — leaving ~19pp of slack in a majority test and telling a reader
    # nothing about whether anything was actually missing.
    #
    # The session calendar is the UNION of the bar's dates and the cash series'
    # dates over the strategy's own span: if the bar was truncated, the cash
    # leg — fetched over the strategy's span, above — still supplies those
    # sessions.
    #
    # v5r2 SAID THE UNION "CAN ONLY MOVE THE COUNT TOWARD THE TRUTH" AND THAT
    # WAS FALSE. Both legs come through `fetch_daily_bars`, so they are not two
    # independent witnesses: one vendor tail-lag truncates them TOGETHER and the
    # union collapses onto the shared window, at which point the majority test
    # compares a window with itself. Measured, 15.6% coverage read as 214 of 214
    # and PASSED. So the union is now CHECKED for coverage before it is
    # believed — `_session_span`, whose docstring carries the shapes.
    #
    # WITH NO CASH LEG THERE IS NO SESSION COUNT, and this is not a detail. The
    # bar alone is exactly the leg that gets truncated, so deriving the
    # denominator from it lets a truncation shrink its own test: a bar covering
    # 180 of 600 sessions would report 180 of 180 and clear a strict majority.
    # That defect was written here, and an EXISTING coverage test caught it. So
    # the count is reported only when the cash leg vouches for the span, and the
    # gate's fallback is the CALENDAR figure, which is larger and therefore
    # stricter.
    #
    # AND VOUCHING IS A SPAN, NOT A PRESENCE — this is the D29 kill's second
    # ground (G2) and it is the same defect one level up. The bar and the cash
    # leg BOTH come through `fetch_daily_bars`, so one vendor tail-lag truncates
    # them together; the union then degenerates to common/common and 15.6%
    # coverage read as a strict majority and PASSED, where v5r1 refused. "The
    # cash leg exists" is not "the cash leg covers the run". So the count is
    # reported only when the cash series actually REACHES both ends of the
    # strategy's own span, and when it does not the gate falls back to the
    # CALENDAR figure, which is larger and therefore stricter.
    union = sorted(d for d in (set(bmap) | set(rfmap))
                   if s_dates[0] <= d <= s_dates[-1]) if rfmap else []
    span = _session_span(union, s_dates[0], s_dates[-1])
    sessions = (len(union) or None) if span["vouched"] else None
    coverage: dict[str, Any] = {
        "common_days": len(common),
        "strategy_days": len(s_dates),
        "fraction": round(len(common) / len(s_dates), 4),
        "strategy_sessions": sessions,
        "session_fraction": (None if not sessions
                             else round(len(common) / sessions, 4)),
        "session_basis": ("benchmark+cash" if sessions else None),
        "session_span": span,
        "rf_dropped_days": len(pair_days) - len(common),
        "note": ("`fraction` divides sessions by CALENDAR days and is kept only "
                 "so the two are comparable; `session_fraction` is the one the "
                 "majority test reads, and it is absent — never assumed — when "
                 "no cash leg vouched for the session calendar"),
    }
    out.update({
        "measurable": bool(strat.get("measurable") and bench.get("measurable")),
        "strategy": strat,
        "benchmark": bench,
        "window": {"first": common[0], "last": common[-1], "n": len(common)},
        # HOW MUCH of the strategy's own record the comparison covers. A
        # comparison over a third of the run is not a comparison over the run,
        # and the gate refuses below a majority for the same reason
        # `_add_benchmark` refuses a basket built from a minority of its legs.
        "coverage": coverage,
    })
    if not out["measurable"]:
        out["reason"] = (strat.get("reason") or bench.get("reason")
                         or "one leg carried no usable dispersion")

    # --- the CASH CREDIT, which decides what "excess" even means -----------
    #
    # The engine pays 0% on idle cash and the bar subtracts the realised rate
    # from both legs, so a cash-heavy book is charged a rate it never earned.
    # `invested_weights` carries the why; what happens HERE is the alignment,
    # and the alignment is where it could go wrong quietly: a weight read off
    # the wrong date credits the wrong day's rate.
    #
    # FAIL CLOSED ON A WEIGHT THIS CANNOT PLACE. Every observation in the common
    # window needs a weight. A missing day is NOT assumed fully invested (that
    # would credit nothing and keep the bias) and NOT assumed all cash (that
    # would credit the maximum) — it makes the excess pair unmeasurable, exactly
    # as an unreadable cash rate does.
    credit: dict[str, Any] = {
        "measurable": False,
        "basis": "invested weight per date, from the engine's exposure chart",
        "reason": None,
    }
    wmap: dict[str, float] = {}
    invested_weight = result.get("invested_weight")
    if not isinstance(invested_weight, dict):
        credit["reason"] = (
            "this result carries no invested-weight series, so the share of the "
            "book sitting in cash is UNKNOWN — it was measured by a belt older "
            "than the one that reads the engine's exposure chart per date. The "
            "engine pays 0% on that cash and this bar subtracts the realised "
            "rate from it, so judging without it charges the book a rate it "
            "never earned")
    elif not invested_weight.get("measurable"):
        credit["reason"] = invested_weight.get("reason") or (
            "the invested-weight series could not be read")
    else:
        supplied = invested_weight.get("weights") or {}
        missing = [d for d in common if d not in supplied]
        if missing:
            credit["reason"] = (
                f"the exposure chart carries no invested weight for "
                f"{len(missing)} of the {len(common)} days in the comparison "
                f"window (first {missing[0]}) — an unweighted day would have to "
                f"be assumed either fully invested or fully in cash, and both "
                f"are inventions")
        else:
            wmap = {d: float(supplied[d]) for d in common}
            vals = [wmap[d] for d in common]
            credited = [(1.0 - wmap[d]) * rfmap[d] for d in common] if rfmap else []
            cr_leg = (_stats.leg_moments(credited, common) if credited else {})
            credit.update({
                "measurable": True,
                "n": len(vals),
                "mean_invested_weight": round(sum(vals) / len(vals), 6),
                "mean_cash_weight": round(1.0 - sum(vals) / len(vals), 6),
                "min_invested_weight": round(min(vals), 6),
                "max_invested_weight": round(max(vals), 6),
                # WHAT THE CREDIT IS WORTH, annualised on the legs' own clock, so
                # a reader can see the size of the correction without re-deriving
                # it from two Sharpes.
                "credited_annual_pct": _round_or_none(
                    cr_leg.get("ann_return_pct"), 4),
            })
    out["cash_credit"] = credit

    # --- the EXCESS pair, which is what the criterion is judged on ---------
    #
    # TWO STAGES, deliberately. The UNCREDITED pair needs only the cash series,
    # so it is captured whenever the cash series is readable — a credit outage
    # must not delete the capture that would let a reader see what the previous
    # version of this bar would have said. Only the CREDITED strategy leg
    # depends on the weights; `excess_measurable` does NOT, and is set below
    # from the uncredited pair alone. (The draft's docstring and this comment
    # both claimed the dependency; the code never had it. Second copy of one
    # false sentence, four lines from the assignment that refutes it.)
    if rfmap and out["measurable"]:
        rf_leg = _stats.leg_moments([rfmap[d] for d in common], common)
        # THE BENCHMARK IS NOT CREDITED, and that is not an oversight: every
        # benchmark leg this belt builds is a fully-invested buy-and-hold basket
        # or the engine's own single-name curve, so its invested weight is 1 by
        # construction and `w_b * rf` IS `rf`.
        b_ex = _stats.leg_moments([bmap[d] - rfmap[d] for d in common], common)
        # KEPT FOR COMPARABILITY, never judged. This is the leg v5r3 judged, and
        # the gap between the two advantages is the size of the bias — a reader
        # who cannot see it cannot audit the correction that removed it.
        s_ex_unc = _stats.leg_moments(
            [smap[d] - rfmap[d] for d in common], common)
        # THE JUDGED PAIR IS THE UNCREDITED ONE AND `excess_measurable` KEEPS
        # ITS v5r3 MEANING. The credit is CAPTURED here and SELECTED at judge
        # time by `premia_credit_idle_cash`, which ships OFF — crediting admits
        # candidates, and a loosening does not get to arrive as a parse-time
        # default nobody voted on. Storing both pairs is what lets the criterion
        # own the choice instead of the belt baking it in before anyone reads a
        # threshold.
        out["strategy_excess"] = s_ex_unc
        out["benchmark_excess"] = b_ex
        out["strategy_excess_uncredited"] = s_ex_unc
        out["excess_measurable"] = bool(s_ex_unc.get("measurable")
                                        and b_ex.get("measurable"))
        if credit["measurable"]:
            # THE CREDITED LEG: `w_t * rf_t`, not `rf_t`. The book is charged
            # the cash rate only on the part of it that was actually invested.
            #
            # THE FORMULA IS SYMMETRIC AND THAT IS WORTH SAYING OUT LOUD. At
            # w < 1 it CREDITS idle cash; at w > 1 it CHARGES the borrow, which
            # is engine-priced financing — the thing v5r3's note named as the
            # open policy question and as the CEO's click rather than a code
            # change. It is not reachable here: `premia_max_gross_exposure`
            # refuses any book whose MAXIMUM gross exceeds the ceiling before
            # the gate reads a single one of these numbers, and a maximum at or
            # below 1.0 means every w_t is too. No clamp is applied precisely
            # because a clamp would be a SECOND copy of the ceiling's belief
            # living in a different file, and two copies of one predicate is a
            # defect this fund has already paid for. The ceiling owns leverage;
            # this owns cash.
            #
            # THE PIN, AND IT IS STRUCTURAL RATHER THAN CHECKED. The credit uses
            # `rfmap` — the SAME object, over the same dates, that the benchmark
            # leg two lines above is subtracted with, and that the gate's
            # `premia_rf_basis`/`premia_rf_symbol` selected. There is no second
            # rate series anywhere in this function to drift from it. This
            # matters because a credit applied at a DIFFERENT rate is the D23
            # constant-rf kill re-entering from the other side: a flat 4.0%
            # credited against a realised subtraction buys a book at w=0.2
            # roughly +0.167 of Sharpe out of nothing. `test_the_credit_and_the_
            # subtraction_are_ONE_series` fails if anyone introduces a second.
            s_ex_cr = _stats.leg_moments(
                [smap[d] - wmap[d] * rfmap[d] for d in common], common)
            out["strategy_excess_credited"] = s_ex_cr
            out["credited_measurable"] = bool(s_ex_cr.get("measurable")
                                              and b_ex.get("measurable"))
        else:
            out["credit_absent_reason"] = (
                f"the cash credit could not be measured, so no credited pair "
                f"was formed: {credit.get('reason')}")
        rf_meta.update({
            "window": {"first": common[0], "last": common[-1],
                       "n": len(common)},
            # The cash return the window ACTUALLY paid, compounded and
            # annualised on the same clock as the legs it is subtracted from.
            # This is the number v5r1 assumed at 4.0 and the belt's windows
            # disagreed with.
            #
            # ROUNDED like every other reported figure in this payload. Reading
            # the raw float back gave `4.5000000000020135` for a series built to
            # pay exactly 4.5%, which is a fact about binary compounding and not
            # about the cash rate — and a stored record should not carry the
            # arithmetic's residue as though it were precision.
            "realised_annual_pct": _round_or_none(rf_leg.get("ann_return_pct"), 4),
            "realised_total_pct": _round_or_none(rf_leg.get("total_return_pct"), 4),
            "obs_per_year": _round_or_none(rf_leg.get("obs_per_year"), 2),
            "basis": "realised_series",
        })
    elif rfmap:
        # ON ITS OWN KEY, not on `rf["reason"]`. The cash leg WAS readable here;
        # what failed is the raw pair. Overwriting the rf block's reason would
        # make a stored payload say the cash series was the problem when it was
        # not — a diagnosis that names the wrong cause sends the next reader to
        # the wrong place. The credit's own outage is reported on the same key
        # from inside the branch above, with its own sentence.
        out["excess_absent_reason"] = (
            "the raw pair was not measurable, so no excess pair was formed")
    out.setdefault("strategy_excess", None)
    out.setdefault("benchmark_excess", None)
    out.setdefault("strategy_excess_uncredited", None)
    out.setdefault("strategy_excess_credited", None)
    out.setdefault("credited_measurable", False)

    # --- the ADVANTAGE, which is what a PREMIA luck filter must score -------
    #
    # A premia claim asserts `SR_s - SR_b > 0`, so the luck filter belongs on
    # THAT quantity and not on the strategy's absolute Sharpe. The moments of the
    # advantage series are stored here (the series itself is not, for the same
    # reason `leg_moments` stores six numbers instead of a curve) and the gate
    # scores them with the same `psr_from_moments` the alpha bar uses.
    #
    # BOTH ARMS, because the criterion chooses between them at judge time and a
    # probability attached to the quantity nobody is testing is worse than none.
    # `advantage` is the SHIPPED one (uncredited); `advantage_credited` is what
    # the same statistic says once idle cash is credited, and the pair is what
    # makes the loosening auditable instead of arguable.
    def _advantage(strategy_leg: list[float], basis: str) -> dict[str, Any]:
        block = _stats.sharpe_advantage_series(
            strategy_leg, [bmap[d] - rfmap[d] for d in common])
        block["basis"] = basis
        # THE CROSS-CHECK, computed rather than asserted in a comment: the
        # advantage series' own mean, annualised, IS the Sharpe advantage the
        # criterion compares against its margin. If these two ever disagree, the
        # difference series is not measuring the inequality it is named after.
        if block.get("measurable"):
            kk = (out.get("strategy_excess") or {}).get("obs_per_year")
            block["advantage_annualised"] = (
                None if not kk else block["mean_per_obs"] * math.sqrt(float(kk)))
        return block

    no_pair = {"measurable": False, "reason": (
        "no excess pair was formed, so the advantage between the two legs does "
        "not exist to be scored")}
    out["advantage"] = (_advantage([smap[d] - rfmap[d] for d in common],
                                   "uncredited")
                        if out["excess_measurable"] and rfmap else dict(no_pair))
    out["advantage_credited"] = (
        _advantage([smap[d] - wmap[d] * rfmap[d] for d in common], "credited")
        if out["credited_measurable"] and rfmap and wmap else
        {"measurable": False,
         "reason": (credit.get("reason")
                    or "no credited pair was formed, so its advantage does not "
                       "exist to be scored")})

    # THE DISAGREEMENT, measured on every run rather than rediscovered. When
    # the engine's leg was discarded, `daily_returns["benchmark"]` still holds
    # it — so the payload contains two benchmarks and, until this field, said
    # nothing about it.
    engine_leg = list(daily.get("benchmark") or [])
    if daily.get("benchmark_present") and len(engine_leg) == len(s_dates):
        total = 1.0
        for x in engine_leg:
            total *= (1.0 + x)
        engine_total = (total - 1.0) * 100.0
        headline = result.get("benchmark_return_pct")
        out["daily_returns_benchmark_leg"] = {
            "compounded_total_pct": round(engine_total, 3),
            "headline_benchmark_return_pct": headline,
            "agrees_with_headline": (
                None if headline is None
                else abs(engine_total - float(headline)) <= 0.05),
            "note": ("`daily_returns[\"benchmark\"]` is the series the engine "
                     "emitted; where the belt replaced it with a recomputed "
                     "basket these two are DIFFERENT bars, and only the "
                     "headline one is what the gate's benchmark criterion "
                     "reads"),
        }
    return out


def _annual_vol_fraction(stats: dict) -> Optional[float]:
    """LEAN's ``Annual Standard Deviation`` as a FRACTION, unit-checked.

    The engine writes this one bare (0.116) while writing ``Drawdown`` and
    ``Compounding Annual Return`` with a "%" in the same block, so the unit has
    to be read off the string rather than assumed. Returns None when it is
    absent or unparseable — an unreadable volatility is not a zero one.

    The fraction is the base and the percentage is derived from it, rather than
    the other way round: reading 0.116, scaling to 11.6 and dividing back gives
    0.11600000000000002, and a stored payload should not carry a float artefact
    of the order in which two callers happened to want the number.
    """
    raw = stats.get("Annual Standard Deviation")
    if raw is None:
        return None
    text = str(raw).strip()
    try:
        value = float(text.replace("%", "").replace(",", ""))
    except ValueError:
        return None
    return value / 100.0 if "%" in text else value


def _annual_vol_pct(stats: dict) -> Optional[float]:
    """The same figure as a percentage. One law, expressed once."""
    fraction = _annual_vol_fraction(stats)
    return None if fraction is None else fraction * 100.0


def _robustness(stats: dict, equity: list[float], dates: list[str],
                orders: list[dict],
                daily: Optional[dict[str, Any]] = None,
                config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
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
        # The engine's OWN annualised volatility, which the belt has always had
        # in hand and always thrown away. Parsed beside the raw capture below
        # so a reader who wants one number has one; the raw string is what
        # identifies the formula. See ``psr_inputs`` for the measured reason
        # this is not the trading-day volatility.
        #
        # SCALED ONLY WHERE THE ENGINE WROTE A FRACTION. Every real block seen
        # writes it bare — "0.116" on candidate 144387901688 — while sibling
        # statistics in the SAME block carry a "%" ("15.300%", "36.994%"). A
        # blind x100 would turn a future "11.600%" into 1160%, which is the
        # unit-confusion shape and would be invisible in a payload nobody
        # re-derives.
        "engine_annual_vol_pct": _annual_vol_pct(stats),
        "periods": _periods(equity, dates),
        # THE STATISTIC IS IDENTIFIED NOW (D38) — this block is the evidence,
        # carried on every future verdict. Its one reader on the gate side is
        # `trading_days_per_year`, and that read moves a DISCLOSURE and never a
        # verdict: the engine hurdle's pass/fail is `psr_pct >= level` and
        # touches neither the target nor the clock. See `psr_inputs`.
        "psr_inputs": psr_inputs(stats, daily, config),
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
        # conversion fail would leave the two lists a different length, and
        # the downsampler drops dates entirely when they fall out of step —
        # so one unconvertible timestamp would silently cost every date.
        try:
            value = float(pt[-1])
        except (ValueError, TypeError):
            continue
        date = _iso_or_none(pt[0])
        if date is None:
            continue
        values.append(value)
        dates.append(date)
    return values, dates


#: LEAN's own exposure chart, and the two series suffixes it writes per
#: security type ("Base - Long Ratio", "Base - Short Ratio"; a futures leg would
#: add "Future - Long Ratio"). Named constants rather than inline strings
#: because the reader below FAILS CLOSED on a series it cannot classify, and a
#: reader that fails closed must say exactly what it was looking for.
EXPOSURE_CHART = "Exposure"
LONG_RATIO_SUFFIX = "Long Ratio"
SHORT_RATIO_SUFFIX = "Short Ratio"


def _exposure_by_timestamp(series: dict) -> tuple[dict, dict, list[str]]:
    """The engine's exposure chart, joined per timestamp. ONE reader, two users.

    ``gross_exposure`` wants the maxima; ``invested_weights`` wants the dated
    series. Writing the classify-and-sum loop twice would be two answers to "what
    was this book holding" that could drift apart silently — and the drift would
    land in a criterion (the ceiling) and a correction (the cash credit) that
    must agree about the same book by construction.
    """
    longs: dict[Any, float] = {}
    shorts: dict[Any, float] = {}
    unclassified: list[str] = []
    for name, block in (series or {}).items():
        label = str(name)
        if label.endswith(LONG_RATIO_SUFFIX):
            bucket = longs
        elif label.endswith(SHORT_RATIO_SUFFIX):
            bucket = shorts
        else:
            unclassified.append(label)
            continue
        for pt in ((block or {}).get("values")
                   or (block or {}).get("Values") or []):
            if not isinstance(pt, (list, tuple)) or len(pt) < 2:
                continue
            try:
                value = abs(float(pt[-1]))
            except (ValueError, TypeError):
                continue
            bucket[pt[0]] = bucket.get(pt[0], 0.0) + value
    return longs, shorts, unclassified


def invested_weights(charts: Any) -> dict[str, Any]:
    """The book's INVESTED FRACTION per date, for the cash-carry credit.

    THE DEFECT THIS EXISTS TO CLOSE (quant, run-quant-metacontrols, 2026-08-24).
    LEAN pays 0% on idle cash, and the premia bar subtracts the realised cash
    return from BOTH legs. So a book that sat half in cash is charged a rate it
    never earned, while its fully-invested benchmark is charged one it did:

        engine    r_t = w_t * a_t                       (cash pays nothing)
        reality   r_t = w_t * a_t + (1 - w_t) * rf_t
        excess    r_t - rf_t   is charged, when the honest figure is
                  r_t - w_t * rf_t

    The bias is exactly ``(1 - w_t) * rf_t`` per observation, it runs in the
    KILL direction, and it is the symmetric twin of the free-borrow hole the
    gross-exposure ceiling closes above 1.0x.

    LONG-ONLY, AND IT REFUSES OTHERWISE. Cash held against a SHORT book is not
    ``1 - gross``: short proceeds earn interest the engine also does not pay, and
    modelling that is a different correction. Every LEAN run this fund has on
    disk is long-only (max short 0.0 on 108 of 108 runs with a statistics block,
    scratchpad/d32/census_exposure2.py; re-confirmed on the four control
    candidates 2026-08-24), so the shape is refused rather than guessed at.

    ABOVE 1.0x THE CREDIT GOES NEGATIVE, and that is left alone deliberately: it
    is arithmetic, not a financing model, and the premia bar refuses a book above
    the gross ceiling before any of it is read. This function does not decide
    that question and must not be read as pricing leverage.
    """
    out: dict[str, Any] = {
        "measurable": False, "weights": {}, "n": 0,
        "source": f"lean chart {EXPOSURE_CHART!r}", "reason": None,
    }
    if not isinstance(charts, dict):
        out["reason"] = ("this result carries no charts block, so the book's "
                         "invested weight could not be read")
        return out
    chart = charts.get(EXPOSURE_CHART)
    series = ((chart or {}).get("series") or (chart or {}).get("Series")
              if isinstance(chart, dict) else None)
    if not isinstance(series, dict) or not series:
        out["reason"] = (f"this run has no readable {EXPOSURE_CHART!r} chart, so "
                         f"the share of the book sitting in cash is UNKNOWN — "
                         f"and an unknown cash weight is not a zero one")
        return out
    longs, shorts, unclassified = _exposure_by_timestamp(series)
    if unclassified:
        out["reason"] = (
            f"the {EXPOSURE_CHART!r} chart carries series this reader cannot "
            f"classify as long or short ({', '.join(sorted(unclassified))}); an "
            f"invested weight summed over an unknown series is wrong in a "
            f"direction nobody can see")
        return out
    if any(v > 0 for v in shorts.values()):
        out["reason"] = (
            "this book holds SHORT exposure, and the cash a short book earns is "
            "not one minus its gross — short proceeds earn interest the engine "
            "also does not pay, which is a different correction than this one")
        return out
    weights: dict[str, float] = {}
    for ts, value in longs.items():
        day = _iso_or_none(ts)
        if day is None:
            continue
        # A DAY THAT APPEARS TWICE KEEPS ITS LARGEST READING. The chart is one
        # point per day on every run measured, so this cannot fire today; if a
        # future engine samples intraday, the largest invested reading is the
        # SMALLEST cash credit, which is the direction that cannot manufacture
        # an advantage.
        weights[day] = max(weights.get(day, 0.0), float(value))
    if not weights:
        out["reason"] = (f"the {EXPOSURE_CHART!r} chart's series carry no values "
                         f"this reader could place on a date")
        return out
    out.update({"measurable": True, "weights": weights, "n": len(weights)})
    return out


def gross_exposure(charts: Any) -> dict[str, Any]:
    """MAX GROSS EXPOSURE over the run, read from the engine's own chart.

    THE DEFECT THIS EXISTS TO CLOSE (adversary D29, blind, 2026-08-23 —
    docs/reviews/ADVERSARY_D29_2026-08-23.md, ground G1). LEAN's default
    brokerage charges NO margin interest (``NullMarginInterestRateModel``), so a
    levered book's excess return in a backtest is ``sum(w_i r_i) - rf`` and not
    ``sum(w_i (r_i - rf))``: the borrow is free. Subtracting a realised cash
    return therefore closes the carry channel only for gross <= 100%, and above
    it the gift GROWS with the cash weight. Executed on the fund's own pinned
    feed, a 1.25x book of 25% SPY and 75% BIL scored +0.153..+0.239 against SPY
    on all four belt windows where the financed answer is 0.0000, and a 3.0x
    version scored +2.49..+3.92. The premia payload carried no gross-exposure
    field at all, so a reader could not see the borrow.

    So the belt now MEASURES gross, and the gate refuses a premia claim it
    cannot measure. The engine publishes exactly what is needed: an ``Exposure``
    chart carrying a long-ratio and a short-ratio series per security type,
    sampled once per day, each value a fraction of portfolio value.

    WHY THE SUM IS TAKEN PER TIMESTAMP. ``max(long) + max(short)`` is an upper
    bound, not a measurement — the two maxima can fall on different days.
    Gross is a property of one instant, so the series are joined on their own
    timestamps and the maximum is taken over the joined totals.

    ABSOLUTE VALUES. The short ratio is written as a MAGNITUDE on every run this
    fund has (108 of 108 with a non-empty statistics block, measured
    2026-08-23 by scratchpad/d32/census_exposure2.py), but a sign convention is
    a vendor's to change and ``abs`` is right under both.

    FAIL CLOSED ON A SERIES THIS CANNOT CLASSIFY. If a future engine adds a
    third series to this chart — a net ratio, say — summing it would either
    double-count or miss, and both are silent. An unclassified series makes the
    reading UNMEASURABLE with the offending names in the reason. Measured cost
    today: zero, because the only two series names across all 108 runs are the
    long and short ratios.

    Returns a block that always states ``measurable``; ``max_gross`` is absent,
    never zero, when it could not be read. Absence is never zero, and for this
    field zero would be the single most permissive answer available.
    """
    out: dict[str, Any] = {
        "measurable": False,
        "max_gross": None,
        "max_long": None,
        "max_short": None,
        "max_gross_on": None,
        "observations": 0,
        "series": [],
        "unclassified_series": [],
        "source": f"lean chart {EXPOSURE_CHART!r}",
        "reason": None,
    }
    if not isinstance(charts, dict):
        out["reason"] = ("this result carries no charts block, so the engine's "
                         "exposure series could not be read")
        return out
    chart = charts.get(EXPOSURE_CHART)
    if not isinstance(chart, dict):
        out["reason"] = (
            f"this run has no {EXPOSURE_CHART!r} chart, so the book's gross "
            f"exposure is UNKNOWN — the charts present are "
            f"{', '.join(sorted(str(k) for k in charts)) or '(none)'}")
        return out
    series = chart.get("series") or chart.get("Series") or {}
    if not isinstance(series, dict) or not series:
        out["reason"] = (f"the {EXPOSURE_CHART!r} chart carries no series, so "
                         f"the book's gross exposure is UNKNOWN")
        return out
    out["series"] = sorted(str(k) for k in series)
    longs, shorts, unclassified = _exposure_by_timestamp(series)
    if unclassified:
        out["unclassified_series"] = sorted(unclassified)
        out["reason"] = (
            f"the {EXPOSURE_CHART!r} chart carries series this reader cannot "
            f"classify as long or short ({', '.join(sorted(unclassified))}); "
            f"summing an unknown series would either double-count the book or "
            f"miss part of it, and both are silent")
        return out
    stamps = sorted(set(longs) | set(shorts))
    if not stamps:
        out["reason"] = (f"the {EXPOSURE_CHART!r} chart's series carry no "
                         f"readable values")
        return out
    best_ts, best = None, None
    for ts in stamps:
        total = longs.get(ts, 0.0) + shorts.get(ts, 0.0)
        if best is None or total > best:
            best, best_ts = total, ts
    out.update({
        "measurable": True,
        "max_gross": round(float(best), 6),
        "max_long": round(max(longs.values()), 6) if longs else 0.0,
        "max_short": round(max(shorts.values()), 6) if shorts else 0.0,
        "max_gross_on": _iso_or_none(best_ts),
        "observations": len(stamps),
    })
    return out


def _iso_or_none(stamp: Any) -> Optional[str]:
    """A LEAN chart timestamp as an ISO date, or absent if it will not convert.

    THE ONE PLACE THIS CONVERSION LIVES. ``_curve`` had its own copy inside a
    combined try/except; two copies of "how a LEAN timestamp becomes a date" is
    the same defect class as two copies of a constant. The callers differ only
    in what an absence COSTS — ``_curve`` drops the whole point, because a
    values list and a dates list of different lengths silently mis-pairs
    downstream; ``gross_exposure`` drops only the LABEL, because the instant a
    maximum fell on is not the maximum.
    """
    try:
        return datetime.fromtimestamp(
            float(stamp), tz=timezone.utc).date().isoformat()
    except (ValueError, TypeError, OSError, OverflowError):
        return None


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



def _population_report(wanted: list[str], as_of: str) -> dict[str, Any]:
    """The benchmark's population label. Never absent, never assumed clean.

    A one-line seam, kept for two reasons: the suite monkeypatches it so a unit
    test never reaches Postgres, and the import stays lazy so an install with
    no psycopg still enriches a benchmark.

    It carries no try/except of its own. ``read_population`` already degrades
    every failed read DOWNWARD to "unknown" — a register nobody could read
    reports membership UNKNOWN and the bar keeps its survivor-only label — so
    a second guard here would be a branch nothing can reach, and an unreachable
    branch cannot be shown to work.
    """
    from app.fund.asof import read_population
    return read_population(wanted, as_of)


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


def _declared_lookback_days(code: Optional[str]) -> Optional[int]:
    """The ``lookback_days`` an algorithm's own bar URL asks the spine for.

    Read statically from the source, the same way and for the same reason as
    ``_declared_universe``: the engine has exited by the time anyone wants to
    know, and re-running it to ask about its inputs would double every backtest.

    Used to pin a candidate's bar snapshot at EXACTLY the shape its containers
    will request. That exactness is the whole point — a snapshot pinned at a
    different lookback cannot serve the container's question without inventing a
    truncation, so it declines instead (see barcache.BarSnapshot.serve).

    Deliberately narrow, and narrow in the safe direction: a single integer
    literal spelled ``lookback_days=N`` inside a STRING in the module. Anything
    computed, parameterised, or spelled more than one way returns None, which
    means "no snapshot" — the candidate then runs on live fetches exactly as it
    does today. A wrong guess here would silently feed a strategy a window it
    did not ask for, so guessing is not on the table.

    READ FROM THE AST, NOT THE TEXT, AND THAT IS NOT A STYLE CHOICE. Scanning
    raw source finds the number in COMMENTS as well as in code. The 170-name
    Entry 20 algorithm — the exact candidate this cache was built for — carries
    the line "2000, not 1200. MEASURED 2026-08-22 on ACGL: lookback_days=1200
    ..." above a URL that asks for 2000. A text scan sees two lookbacks, calls
    the algorithm ambiguous and silently declines to snapshot it, so the one
    candidate that most needed this would have got none of it. Comments are not
    in the AST; string literals are, and the URL is a string literal.
    """
    if not code:
        return None
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None
    found: set[int] = set()
    for node in ast.walk(tree):
        # Plain strings and the literal parts of f-strings both arrive here.
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.update(int(m) for m in
                         re.findall(r"lookback_days=(\d+)", node.value))
    if len(found) != 1:
        return None
    n = found.pop()
    # The endpoint's own bound (fund.py: gt=1, le=2000). A source asking outside
    # it would 422 live, and pinning it would hide that behind a cache hit.
    return n if 1 < n <= 2000 else None


def declared_algorithm_class(code: Optional[str]) -> Optional[str]:
    """The ``class X(QCAlgorithm)`` LEAN will instantiate, read from the source.

    NOT the same thing as ``declared_datasource()["class_name"]``, and the
    difference is why this is its own function: that one names the custom DATA
    class (``SpineBars``), this one names the ALGORITHM class
    (``HygFastFlipProbe``). Both live in one file and a card showing one under
    the other's label would be quietly wrong.

    Uses the same ``_CLASS_RE`` ``save_algorithm`` validates with and
    ``_run_live`` passes to ``--algorithm-type-name``, so what this reports is
    what the container is actually told to run — not a second opinion about it.
    """
    if not code:
        return None
    m = _CLASS_RE.search(code)
    return m.group(1) if m else None


def declared_datasource(code: Optional[str]) -> dict[str, Any]:
    """What data an algorithm says it subscribes to, read from its own source.

    THE QUESTION THIS ANSWERS (CEO, 2026-08-26, verbatim): *"I would like to
    see which datasource; which asset; which strategy which signals etc etc to
    get a quick sense."* Nothing recorded it. A strategy's ``definition`` names
    the algorithm and the rule; the FEED is declared only inside the algorithm
    file, in the URL its custom data class fetches.

    Read statically, for the third time in this module and for the same reason
    as ``_declared_universe`` and ``_declared_lookback_days``: the engine has
    exited by the time anyone asks, and re-running it to ask a question about
    its inputs would double every backtest. A live session cannot be asked
    either — its record carries state, container and a log tail, nothing else.

    **NARROW, AND NARROW IN THE ABSENT DIRECTION.** Every field is independently
    optional and an unreadable one comes back ``None`` with the reason on the
    payload, never a plausible default. A datasource this fund GUESSED at would
    be worse than no datasource panel at all: the whole point of the panel is
    that the reader stops having to open the file.

    **FROM THE AST, NOT THE TEXT.** ``_declared_lookback_days`` records what
    that costs when ignored: a text scan finds the number in COMMENTS as well
    as in code, and the one algorithm that most needed the cache carried a
    contradicting figure in a comment above the URL it actually asks for. The
    same trap applies to every field here, so string literals are read from the
    tree — comments are not in it.

    CONFIRMED ON THE LIVE RECORD, not only on a fixture (2026-08-27):
    ``announcement_premium/main.py`` carries ``lookback_days=1200`` in a
    COMMENT on line 372, above a URL asking for 2000 on line 383, and this
    returns 2000. A text scan would find two values, call the algorithm
    ambiguous, and report the window absent for the candidate that most
    needed it.
    """
    absent = {
        "readable": False,
        "reason": "the algorithm's source is not available, so its feed cannot be read",
        "class_name": None, "base": None, "resolution": None,
        "transport": None, "feed_path": None, "feed_origin": None,
        "lookback_days": None, "format": None, "symbols": [],
    }
    if not code:
        return absent
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {**absent,
                "reason": f"the algorithm's source does not parse ({e.msg}), "
                          f"so its feed cannot be read"}

    #: A module-level ``NAME = "…"``. The bar URL is an f-string built from one
    #: of these (``SPINE``), so resolving them is what turns a relative path
    #: into the origin a reader can recognise.
    consts: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    consts[t.id] = node.value.value

    class_name: str | None = None
    base: str | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        # PythonData is LEAN's custom-data base. A QCAlgorithm subclass is the
        # algorithm itself, not a feed, and must not be reported as one.
        if "PythonData" in bases:
            class_name, base = node.name, "PythonData"
            break

    resolution: str | None = None
    subscribed_class: str | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr in ("add_data", "AddData")):
            continue
        if node.args and isinstance(node.args[0], ast.Name):
            subscribed_class = node.args[0].id
        for a in node.args:
            # ``Resolution.DAILY`` — the attribute name IS the resolution.
            if isinstance(a, ast.Attribute) and isinstance(a.value, ast.Name) \
                    and a.value.id == "Resolution":
                resolution = a.attr.lower()
        break

    transport: str | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "SubscriptionTransportMedium":
            transport = node.attr
            break

    #: The feed URL. Collected from every string constant in the tree —
    #: including the literal halves of f-strings, which arrive here as
    #: ``ast.Constant`` exactly like a plain string does.
    paths: set[str] = set()
    lookbacks: set[int] = set()
    formats: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        v = node.value
        m = re.search(r"(/[A-Za-z0-9_\-/]*marketdata/bars)", v)
        if m:
            paths.add(m.group(1))
        lookbacks.update(int(x) for x in re.findall(r"lookback_days=(\d+)", v))
        formats.update(re.findall(r"format=([A-Za-z0-9_]+)", v))

    #: Where those paths hang off. Reported ONLY when the module declares
    #: exactly one such constant; two would make "which one is the feed" a
    #: guess, and this function does not guess.
    origins = {v for k, v in consts.items()
               if v.startswith("http://") or v.startswith("https://")}

    def one(s):
        return next(iter(s)) if len(s) == 1 else None

    readable = bool(class_name or paths or subscribed_class)
    return {
        "readable": readable,
        "reason": None if readable else (
            "the algorithm declares no custom data class and no bar URL this "
            "reader recognises, so its feed is UNKNOWN rather than absent"),
        "class_name": class_name or subscribed_class,
        "base": base,
        "resolution": resolution,
        "transport": transport,
        "feed_path": one(paths),
        "feed_origin": one(origins),
        "lookback_days": one(lookbacks),
        "format": one(formats),
        "symbols": _declared_universe(code),
    }


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
