"""One call from hypothesis to verdict, and a memory of what has already died.

Every piece of this existed and none of them touched: sweep, hold out, verify
the winner in full, judge against the bar. Each was a separate manual call, so
throughput was bounded by how many candidates a person could hand-carry — which
is the wrong bottleneck for a factory whose whole premise is that the gate kills
most things cheaply.

The second half matters as much as the first. Every verdict is recorded with
its failures, so a dead end stays dead. Without that, research rediscovers the
same broken idea every few weeks, each time with the enthusiasm of the first
time, because nothing anywhere says "we tried this in August and it kept minus
ten percent of its edge out of sample".

Deliberately NOT autonomous past the verdict. The belt ends at a judgement, and
what happens to a candidate that clears the bar remains a human decision — a
factory that could deploy its own output would be a fund with no one
accountable for its positions.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.fund.walkforward import HISTORY_FLOOR_RATCHET as _HISTORY_FLOOR_RATCHET

logger = logging.getLogger(__name__)

#: Earliest date with bars in this fund's feed. Folds are not built before it —
#: reaching further back is harmless (a fold with no bars places no trades and is
#: reported unmeasurable) but spends engine time on runs that cannot speak.
#: Widen as history accumulates; the number is a property of the data, not a
#: preference.
#:
#: MOVED 2024-02-26 -> 1993-01-29 on 2026-08-23, part (b) of the CEO-approved
#: ordered pair (58c4fff5), and it ships BEHIND the fold-scaling half because
#: alone it is a gate loosening arriving as a data improvement — measured, see
#: the v4.3 note in gate.py.
#:
#: MEASURED, not inherited: ``GET /fund/marketdata/bars?symbol=SPY&
#: start_date=1990-01-01&end_date=2026-08-23&format=csv`` returns 8,448 rows
#: beginning 1993-01-29 (SPY's inception), served by Yahoo — the start/end route
#: falls to Yahoo by construction (marketdata.py: Alpaca is used only for a
#: trailing lookback). The old value was never the feed's start; it was the
#: reach of a trailing window nobody re-measured.
WALKFORWARD_HISTORY_FLOOR = os.getenv("FUND_HISTORY_FLOOR", "1993-01-29")

#: THE RATCHET: a per-candidate floor may move the window BACKWARD and never
#: forward past this date, which is the floor this fund enforced before v4.3.
#:
#: Written because the honest per-candidate floor is LATER than the old constant
#: for most algorithms, not earlier. COUNTED, not eyeballed: of the sixteen
#: algorithms in this repo, ELEVEN fetch ``lookback_days=700``, three fetch 900
#: and two fetch 2000 — and the bars endpoint caps that parameter at
#: 2000 (fund.py, ``Query(180, gt=1, le=2000)``) — so a 700-day container cannot
#: see before roughly today minus 700 days whatever the fold plan asks for.
#: Enforcing that as a floor would take the available span for a 21-day hold
#: from 850 days to 700, which fits 2 folds against a requirement of 4, and
#: EVERY 21-day-hold candidate would return NOT TESTABLE. That is not a
#: tightening, it is a gate that can only say no, and it would block the Entry
#: 20 re-judge this pair was sequenced in front of.
#:
#: The legs before that date are not empty either — they are PARTIALLY fed, so
#: the fold still produces a measurement, just over a shorter series than it
#: asked for. Discarding a partial measurement is a different (and unmandated)
#: decision from not planning an impossible one.
#:
#: So the reach is REPORTED, loudly, per candidate, and the floor ratchets: it
#: deepens where the candidate's own declared data path can serve the depth
#: (``lookback_days=2000`` reaches 2021), and it never shortens a window that
#: already exists. The real unlock is teaching the algorithms' bar URLs to pass
#: start_date/end_date — the other half of 58c4fff5, on the quant's surface and
#: NOT in this change.
#:
#: THE VALUE MOVED HOUSE IN D20 AND DID NOT CHANGE. It now lives in
#: ``walkforward`` because three modules need the same date — this ratchet, the
#: fold-plan extension, and the gate's density calibration — and only
#: ``walkforward`` is below all three in the import graph. Re-exported here so
#: the register pointer, the tests and every existing caller keep resolving.
HISTORY_FLOOR_RATCHET = _HISTORY_FLOOR_RATCHET

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_candidates (
    candidate_id TEXT PRIMARY KEY,
    algorithm    TEXT        NOT NULL,
    grid         JSONB       NOT NULL,
    holdout      JSONB,
    state        TEXT        NOT NULL,
    passed       BOOLEAN,
    failures     JSONB,
    winner       JSONB,
    verdict      JSONB,
    error        TEXT,
    started_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at  TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS fund_candidates_algo_idx
    ON fund_candidates (algorithm, started_at DESC);

-- The evidence the verdict was computed from: equity curve, fills, the cost
-- sweep's grid, and the per-fold walk-forward rows. Added 2026-08-21 because
-- the belt measured all of it and stored none of it — see app/fund/runanalytics.py.
-- NULL means "judged before this column existed", which the reader renders as a
-- named absence rather than as an empty panel; a pruned payload writes a
-- tombstone into the column instead of returning to NULL.
ALTER TABLE fund_candidates ADD COLUMN IF NOT EXISTS analytics JSONB;
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


#: The cost parameter every algorithm here reads and every cost sweep varies.
#: Named once: `leanrunner.breakeven_cost` defaults to the same key and
#: `submit_backtest` fills it from the fund's own cost assumption when a caller
#: leaves it out.
COST_PARAM = "slip"


def effective_history_floor(code: Optional[str] = None,
                            end: Optional[str] = None,
                            floor: Optional[str] = None,
                            ratchet: Optional[str] = None,
                            run_date: Optional[str] = None) -> dict[str, Any]:
    """How far back THIS candidate's folds may reach, and which leg decides it.

    Three legs, and the report names all three whether or not they bind,
    because a window is bounded by its LEAST CAPACIOUS leg and a reader who
    cannot see which leg that is cannot act on it:

      * ``configured`` — the feed's earliest bar (``WALKFORWARD_HISTORY_FLOOR``).
      * ``data_path`` — how far back the candidate's OWN containers can fetch.
        Read statically from its bar URL's ``lookback_days``; absent when the
        algorithm declares none or declares two, which is reported as UNKNOWN
        and never as unlimited. MEASURED FROM THE WALL CLOCK, NOT FROM THE
        HOLDOUT (D20 repair). The bar URLs carry ``lookback_days`` and no end
        date, so the window a container receives is the last N days ending WHEN
        IT RUNS — ``format=csv`` honours ``start_date``/``end_date`` but no
        algorithm passes them yet. Anchoring the reach on ``holdout.test_end``
        made a backdated holdout look deeper than the data path really is: the
        window opened before the first bar the container would ever see, and
        ``folds_before_data_path_reach`` then counted zero starved folds
        because it was comparing against a reach that does not exist. The
        anchor is therefore the LATER of the run date and the holdout end,
        which is the conservative side in both directions.
      * ``per_symbol`` — the first bar of each name in the universe. UNMEASURED
        at plan time and said so: the bar archive holds only what has been
        fetched, so its earliest row is a lower bound on availability and using
        it would shorten windows on the strength of our own fetch history. The
        spread is real — measured 2026-08-23 off this fund's own feed, SPY
        serves from 1993-01-29 and UUP from 2007-03-01, fourteen years apart —
        and a fold that starts before a leg's first bar simply contributes
        nothing for that leg. What CATCHES it downstream is the benchmark's
        truncation detector (``_add_benchmark``, ``benchmark_truncated``),
        which reports a short leg rather than quietly cutting the bar to it.

    THE RATCHET CAPS THE DATA PATH, NOT THE FEED. A data-path reach later than
    ``HISTORY_FLOOR_RATCHET`` is recorded and refused — see that constant for
    the measured reason, which is that enforcing it would return NOT TESTABLE
    for every 21-day hold in this repo. A CONFIGURED floor later than the
    ratchet is a different thing entirely and wins over everything: no
    container can serve a bar that does not exist.
    """
    from datetime import date as _date

    conf = floor or WALKFORWARD_HISTORY_FLOOR
    cap = ratchet or HISTORY_FLOOR_RATCHET
    out: dict[str, Any] = {
        "configured": conf,
        "ratchet": cap,
        "data_path": None,
        "data_path_lookback_days": None,
        "per_symbol": None,
        "per_symbol_note": (
            "UNMEASURED at plan time: the bar archive holds only what has been "
            "fetched, so its earliest row is a LOWER BOUND on availability and "
            "would shorten windows on the strength of our own fetch history. "
            "A leg that starts before a symbol's first bar is caught "
            "downstream by the benchmark truncation detector."),
    }
    lookback = None
    try:
        from app.fund.leanrunner import _declared_lookback_days
        lookback = _declared_lookback_days(code)
    except Exception as e:  # noqa: BLE001
        logger.info("declared lookback unreadable: %s", e)
    if lookback and end:
        try:
            # The container's fetch window ends when the container RUNS, not
            # when the holdout ends — see the docstring. Whichever of the two
            # is later gives the shallower (honest) reach.
            asof = max(_date.fromisoformat(str(end)[:10]),
                       _date.fromisoformat(str(run_date)[:10]) if run_date
                       else _now().date())
            reach = asof - timedelta(days=int(lookback))
            out["data_path"] = reach.isoformat()
            out["data_path_lookback_days"] = int(lookback)
            out["data_path_reach_asof"] = asof.isoformat()
            out["data_path_reach_basis"] = (
                "wall clock" if asof != _date.fromisoformat(str(end)[:10])
                else "holdout end (it is not earlier than the run date)")
        except ValueError:
            out["data_path"] = None
    if out["data_path"] is None:
        out["data_path_note"] = (
            "the algorithm declares no single lookback_days in its bar URL, so "
            "how far back its containers can fetch is UNKNOWN — reported "
            "absent rather than treated as unlimited")

    # HOW DEEP THIS CANDIDATE IS ALLOWED TO GO. The ratchet is the default and
    # the data path is the only thing that can beat it — in EITHER direction:
    #
    #   * a reach EARLIER than the ratchet is proof the containers can serve a
    #     deeper window, so the window deepens;
    #   * a reach LATER than the ratchet is recorded and refused, because a
    #     floor may deepen a window and never shorten one (see the constant);
    #   * a reach that is UNKNOWN deepens NOTHING. The note above says an
    #     unknown reach is "never treated as unlimited", and treating it as
    #     non-binding here would be exactly that — an algorithm declaring no
    #     lookback gets the endpoint's 180-day default, which is the shallowest
    #     data path in the repo, not the deepest.
    reach = out.get("data_path")
    if reach is None:
        allowed, binding = cap, "ratchet (data-path reach unknown)"
    elif reach > cap:
        out["ratcheted_from"] = reach
        out["ratchet_note"] = (
            f"the container data path reaches only {reach}, LATER than the "
            f"{cap} floor this fund already enforces — a floor may deepen a "
            f"window and never shorten one, so {cap} stands and the reach is "
            f"reported instead. Legs before {reach} are PARTIALLY fed, not "
            f"empty")
        allowed, binding = cap, "ratchet (data-path reach refused)"
    else:
        allowed, binding = reach, "data_path"
    # The configured floor is a fact about the feed and wins over everything:
    # no container can serve a bar that does not exist.
    effective = max(conf, allowed)
    out["binding_leg"] = "configured" if effective == conf and conf > allowed \
        else binding
    out["effective"] = effective
    out["deepened"] = effective < cap
    return out


def _reach_report(algorithm: str, history: dict[str, Any],
                  planned: list[dict[str, str]]) -> dict[str, Any]:
    """How many planned folds start before the containers' bars do.

    Not a failure and not silently swallowed: a starved leg is PARTIALLY fed, so
    the fold still measures something, over a shorter series than it asked for.
    Counted because a reader of a thin verdict must be able to tell "the
    strategy had nothing to say" from "we asked the engine a question its data
    path could not answer".

    ABSENCE, NOT ZERO, when the reach is unknown. Until D20 the key was simply
    left out, which reads as "no fold was starved" to a human and to the gate's
    own history-floor block — an absence rendered as zero in a counter added to
    report exactly that absence.
    """
    reach = history.get("data_path")
    if not reach:
        return {
            "folds_before_data_path_reach": None,
            "folds_before_data_path_reach_note": (
                "UNCOUNTABLE: this algorithm declares no single lookback_days, "
                "so how far back its containers reach is unknown and the number "
                "of starved folds cannot be counted — this is not a count of "
                "zero"),
        }
    short = [f for f in planned if f["train_start"] < reach]
    if short:
        logger.warning(
            "%s: %d of %d planned folds begin before the container data-path "
            "reach %s (lookback_days=%s)", algorithm, len(short), len(planned),
            reach, history.get("data_path_lookback_days"))
    return {"folds_before_data_path_reach": len(short)}


def check_cost_grid(grid: Any,
                    criteria: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Can this grid answer the cost question the gate is going to ask it?

    THE MEASURED REASON, and it cost 96 minutes of containers to learn. Entry 20
    (candidate `144387901688`) declared a cost grid of 1/3/5 bps and was judged
    against a 10 bps floor. Every point stayed profitable, so the sweep reported
    no crossing, and gate v4.2 now fails exactly that — with the only sentence
    the evidence supports, "you did not test far enough". By then the candidate
    has spent its entire engine budget producing an answer the bar cannot use.
    The same sentence costs nothing here, and the remedy is one grid point.

    NARROW ON PURPOSE, in three directions:

      * It fires only when the grid DECLARES a cost parameter. A grid that
        sweeps something else entirely still fails the gate ("cost robustness
        was never measured"), which is a different, older defect and not this
        one's business to pre-empt.
      * It does not require two distinct cost points. One point priced AT OR
        ABOVE the floor and still profitable genuinely establishes that the
        breakeven is past the floor — it just cannot say where. The floor is
        the question; the exact breakeven is not.
      * It stands down when the criteria do not ask for a measured breakeven,
        so re-judging against a historical bar that never had the requirement
        is unaffected.

    Returns a verdict rather than raising, so a caller can annotate instead of
    refusing; ``submit`` refuses.
    """
    from app.fund.gate import CRITERIA, fmt_bps, max_tested_bps
    c = {**CRITERIA, **(criteria or {})}
    floor = c.get("min_breakeven_bps")
    out: dict[str, Any] = {"adequate": True, "reason": None,
                           "max_tested_bps": None, "floor_bps": floor}
    if not c.get("require_breakeven_measured") or floor is None:
        return out
    values = (grid or {}).get(COST_PARAM) if isinstance(grid, dict) else None
    if not values:
        return out
    widest = max_tested_bps(values)
    if widest is None:
        out.update(adequate=False, reason=(
            f"the cost grid declares {COST_PARAM} values that do not read as "
            f"numbers ({values!r}), so the sweep cannot price them and the "
            f"{fmt_bps(floor)}bps cost floor cannot be answered"))
        return out
    out["max_tested_bps"] = round(widest, 4)
    if widest < floor:
        out.update(adequate=False, reason=(
            f"this cost grid tests {COST_PARAM} only to {fmt_bps(widest)} bps "
            f"and the gate's cost floor is {fmt_bps(floor)} — a candidate whose "
            f"sweep never reaches the floor it is judged against has not been "
            f"tested against it, and the gate will now say so after the "
            f"containers have run. Add a grid point at or above "
            f"{fmt_bps(floor)} bps and resubmit."))
    return out


class CandidateFactory:
    """Sweep, hold out, verify, judge — and remember the answer."""

    def __init__(self, runner: Any = None, dsn_str: Optional[str] = None):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._runner = runner
        self._ensure_schema()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    def _lean(self):
        if self._runner is None:
            from app.fund.leanrunner import LeanRunner
            self._runner = LeanRunner()
        return self._runner

    # --- the belt -----------------------------------------------------------

    def submit(self, algorithm: str, grid: dict[str, list[str]],
               holdout: Optional[dict[str, str]] = None,
               observation_ids: Optional[list[str]] = None) -> dict[str, Any]:
        """Start a candidate down the belt. Returns immediately with an id.

        ``observation_ids`` records WHAT PROMPTED this — the filing sentences a
        human read before forming the hypothesis. Optional, because a candidate
        can come from anywhere, but the link cannot be reconstructed later: it
        exists only at the moment someone decides to test something, and
        without it no report can ever say which kinds of reading pay.
        """
        self._lean().get_algorithm(algorithm)      # fail fast on a typo
        # Fail fast on a grid that cannot answer the bar, for the same reason
        # and in the same breath. Refusing here costs the submitter one extra
        # grid point; refusing at the gate costs the whole engine budget first.
        grid_check = check_cost_grid(grid)
        if not grid_check["adequate"]:
            from app.fund.leanrunner import LeanError
            raise LeanError(grid_check["reason"])
        candidate_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO fund_candidates "
                    "(candidate_id, algorithm, grid, holdout, state) "
                    "VALUES (%s, %s, %s, %s, 'running')",
                    (candidate_id, algorithm, json.dumps(grid),
                     json.dumps(holdout) if holdout else None))
            conn.commit()
        linked = 0
        if observation_ids:
            try:
                from app.fund.provenance import Provenance
                linked = Provenance(self._dsn).link(
                    candidate_id, observation_ids).get("linked", 0)
            except Exception as e:  # noqa: BLE001
                # A broken trail must not stop the research. The candidate is
                # worth running either way; what is lost is the ability to ask
                # later which observations led here.
                logger.warning("could not link sources for %s: %s", candidate_id, e)
        threading.Thread(target=self._run, args=(candidate_id, algorithm, grid,
                                                 holdout), daemon=True).start()
        return {"candidate_id": candidate_id, "state": "running",
                "sources_linked": linked}

    def _snapshot(self, candidate_id: str, algorithm: str, runner: Any):
        """Pin every leg this candidate will read, ONCE, before any container runs.

        The belt's cost and two of its correctness defects have the same cause:
        each of a candidate's ~22 containers re-asks the vendor the same question
        and quietly accepts whatever it gets. Measured on this host 2026-08-22,
        one leg costs ~1.94s and does not get cheaper on a repeat, so a 170-name
        candidate spends most of its ~96-minute wall clock re-downloading bytes
        the harness already had — and the answers it gets are allowed to differ
        between containers (ticket 0178d2e8, and the 11.85pp Entry 20 benchmark
        truncation).

        Best effort by design. If the universe cannot be read or the prefetch
        fails, the candidate runs exactly as it did before, on live fetches. A
        cache is an optimisation; it must never be the reason a candidate dies.
        """
        from app.fund import barcache
        from app.fund.leanrunner import (_declared_lookback_days,
                                         _declared_universe)
        # OFF SWITCH. This component sits in the measurement instrument's data
        # path, so it gets a documented way to be turned off without a code
        # change — set FUND_BAR_SNAPSHOT=0 and every candidate goes back to
        # per-container live fetches. It is also how the A/B in
        # scripts/belt/verify_bar_snapshot_e2e.py runs both arms on one spine.
        if (os.getenv("FUND_BAR_SNAPSHOT", "1").strip().lower()
                in ("0", "false", "no", "off")):
            logger.info("FUND_BAR_SNAPSHOT is off; %s runs on live fetches",
                        candidate_id)
            return None
        try:
            code = runner.get_algorithm(algorithm)["code"]
        except Exception as e:  # noqa: BLE001
            logger.info("no source for %s, running without a bar snapshot: %s",
                        algorithm, e)
            return None
        universe = _declared_universe(code)
        if not universe:
            # Read statically from a module-level UNIVERSE, exactly as the
            # benchmark does. An algorithm that declares none is not guessed at
            # — it simply runs on live fetches as before.
            logger.info("%s declares no UNIVERSE; running without a bar snapshot",
                        algorithm)
            return None
        lookback = _declared_lookback_days(code)
        if lookback is None:
            # The snapshot must be pinned at the EXACT shape the containers will
            # ask for, or it cannot answer them without inventing a window. An
            # algorithm whose lookback cannot be read unambiguously runs live.
            logger.info("%s does not state a single lookback_days; running "
                        "without a bar snapshot", algorithm)
            return None
        try:
            snap = barcache.prefetch(universe, candidate=candidate_id,
                                     lookback_days=lookback)
        except Exception as e:  # noqa: BLE001
            logger.warning("bar prefetch failed for %s, falling back to live "
                           "fetches: %s", candidate_id, e)
            return None
        if not snap.legs:
            logger.warning("bar prefetch for %s pinned no legs (%s); falling back",
                           candidate_id, snap.unavailable)
            return None
        try:
            # Checkpointed as soon as it exists: a dispatch that dies keeps what
            # it already paid for, and the pinned bytes are the evidence for
            # what this candidate actually ran on.
            snapshot_dir = Path(runner._ws) / "snapshots"
            snap.save(snapshot_dir / f"{candidate_id}.json")
            # Bounded on the way in, not by a sweep nobody runs. One 170-leg
            # candidate is 7.40 MB of regenerable vendor data.
            barcache.prune_snapshots(snapshot_dir)
        except Exception as e:  # noqa: BLE001
            logger.info("snapshot checkpoint failed for %s: %s", candidate_id, e)
        return snap

    def _run(self, candidate_id: str, algorithm: str,
             grid: dict[str, list[str]], holdout: Optional[dict[str, str]]) -> None:
        from app.fund import barcache
        from app.fund.gate import evaluate
        runner = self._lean()
        snap = self._snapshot(candidate_id, algorithm, runner)
        # The snapshot is active for the WHOLE candidate — sweep, verification
        # run, walk-forward folds and enrichment alike. That is the point: every
        # container and every enrichment step of this candidate reads one pinned
        # series per symbol, so they cannot disagree about what the data was.
        with barcache.activate(snap):
            return self._run_pinned(candidate_id, algorithm, grid, holdout,
                                    runner, snap)

    def _run_pinned(self, candidate_id: str, algorithm: str,
                    grid: dict[str, list[str]], holdout: Optional[dict[str, str]],
                    runner: Any, snap: Any) -> None:
        from app.fund.gate import evaluate
        try:
            sub = runner.submit_sweep(algorithm, grid, holdout)
            sweep = self._await(lambda: runner.sweep(sub["sweep_id"]))
            sweep.setdefault("sweep_id", sub.get("sweep_id"))
            if sweep.get("state") != "done":
                return self._finish(candidate_id, error=f"sweep {sweep.get('state')}")

            best = (sweep.get("summary") or {}).get("best") or {}
            params = best.get("parameters") or {}
            if not params:
                return self._finish(candidate_id,
                                    error="no point in the grid scored — nothing to judge")

            # The winner is re-run IN FULL. The sweep's own rows are trimmed to
            # what a comparison needs and carry no costs disclosure, benchmark
            # or capacity — which is most of what the bar actually asks about,
            # so judging the trimmed row would mean waiving those criteria.
            job_id = runner.submit_backtest(algorithm, params)["job_id"]
            job = self._await(lambda: runner.job(job_id))
            job.setdefault("job_id", job_id)
            if job.get("state") != "done":
                return self._finish(candidate_id,
                                    error=f"verification run {job.get('state')}: {job.get('error')}")

            # Gate v2 asks for consistency across independent windows, so the
            # belt has to produce it. Shipping the criterion without the
            # evidence would make the gate unclearable — which is the same
            # pathology as a gate that passes noise, arrived at from the other
            # side, and it would look like rigour while being a bug.
            #
            # Expensive and deliberately so: one grid per fold. That cost IS the
            # finding from the null audit — a single window is cheap and a
            # coin flip cleared it half the time.
            walk, walk_note = self._walkforward(algorithm, grid, holdout)

            verdict = evaluate(job.get("result") or {},
                               sweep.get("holdout_result"),
                               sweep.get("summary"),
                               walkforward=walk)
            # Captured in the SAME statement as the verdict, deliberately. A
            # second pass could re-read a job or re-run a fold, and a verdict
            # whose evidence disagrees with it is worse than one with no
            # evidence, because it reassures. See app/fund/runanalytics.py.
            from app.fund import runanalytics
            analytics = runanalytics.capture(job=job, sweep=sweep,
                                             walkforward=walk,
                                             walkforward_note=walk_note)
            # WHAT DATA PATH THIS CANDIDATE ACTUALLY RAN ON, recorded beside the
            # verdict rather than left in a log nobody folds. A miss means one
            # container fell back to a live fetch while its siblings read pinned
            # bytes — the verdict is still honest, but it was measured on a
            # data path that was not uniform, and a reader must be able to see
            # that without re-deriving it. Absent snapshot is stated as absent.
            if analytics is not None:
                try:
                    analytics["bar_snapshot"] = (
                        snap.report() if snap is not None else
                        {"taken": False,
                         "note": "no bar snapshot was taken for this candidate; "
                                 "every container fetched its own bars live"})
                except Exception as e:  # noqa: BLE001
                    logger.info("snapshot report unavailable for %s: %s",
                                candidate_id, e)
            self._finish(candidate_id, verdict=verdict, winner=params,
                         analytics=analytics)
        except Exception as e:  # noqa: BLE001
            logger.warning("candidate %s failed: %s", candidate_id, e)
            self._finish(candidate_id, error=f"{type(e).__name__}: {e}"[:400])

    def _walkforward(self, algorithm: str, grid: dict[str, list[str]],
                     holdout: Optional[dict[str, str]]
                     ) -> tuple[Optional[dict[str, Any]], Optional[str]]:
        """Walk-forward folds, and — separately — why there are none.

        Returns ``(result, note)``. The RESULT is None when folds cannot be built
        rather than an empty dict: the gate treats a missing walk-forward as a
        failure, and handing it an empty dict would let "we could not test this"
        read as "it was tested and had no folds".

        The NOTE exists because the gate cannot carry it. Both the no-holdout
        case and the crashed case previously returned a bare None, so the stored
        verdict said "no walk-forward test" in each — a sentence that is true of
        the first and misleading about the second, where the leg ran and threw.
        The gate's input and its sentence are unchanged; the reason now survives
        alongside the evidence instead of only in a log line nobody folds.
        """
        if not holdout:
            return None, ("no holdout window was supplied, so no folds could be "
                          "built — the walk-forward leg was never attempted")
        try:
            from app.fund.gate import CRITERIA, folds_required
            from app.fund.walkforward import (WalkForward, declared_hold_days,
                                              window_for_strategy)

            need = int(CRITERIA.get("min_walkforward_folds") or 2)
            # Sized from what the GATE asks for AND from the strategy's own clock.
            # Deriving it from the holdout fit two folds against a three-fold
            # requirement; deriving the LEG from a fixed calendar window gave a
            # 63-day-hold strategy one rebalance per test, which perfect
            # foreknowledge could not pass.
            code = None
            try:
                code = self._lean().get_algorithm(algorithm)["code"]
            except Exception:  # noqa: BLE001
                pass
            hold = declared_hold_days(code, grid)
            # HOW FAR BACK THIS CANDIDATE MAY REACH, per candidate rather than
            # per fund. The configured floor is the feed's; the binding leg is
            # whichever of the candidate's own constraints is least capacious,
            # and the report names all of them so a reader never has to guess
            # which one produced a short window.
            history = effective_history_floor(code, holdout["test_end"])
            plan = window_for_strategy(holdout["test_end"], hold["hold_days"],
                                       min_folds=need,
                                       floor=history["effective"])
            # THE BELT PLANS WHAT THE GATE WILL ASK FOR, and the two are
            # coupled: the requirement scales with the window covered, and the
            # window covered is sized from the requirement. Solved by iterating
            # to a fixed point rather than by keeping two numbers in step by
            # hand — the same reason ``span_for_folds`` is a closed form of the
            # generator instead of a second guess at it. The map contracts (a
            # fold costs a whole test leg of span and buys well under one fold
            # of requirement), so it settles in one or two passes on every
            # geometry this fund runs; the bound exists so a future geometry
            # that does NOT contract says so instead of spinning.
            settled = True
            for _ in range(4):
                req = int(folds_required({"requested_folds": plan["folds"]})
                          ["required"])
                if req <= need:
                    break
                need = req
                plan = window_for_strategy(holdout["test_end"],
                                           hold["hold_days"], min_folds=need,
                                           floor=history["effective"])
            else:
                settled = False
                logger.warning("fold requirement did not settle for %s "
                               "(need=%d, folds=%d)", algorithm, need,
                               len(plan["folds"]))
            # Folds whose TRAIN leg begins before the candidate's containers can
            # fetch — computed ONCE, for both exits. A NOT TESTABLE verdict
            # needs it as much as a judged one: "we could not fit enough folds"
            # and "the folds we fitted were starved" are different sentences,
            # and the second was invisible on that path.
            reach = _reach_report(algorithm, history, plan["folds"])
            if not plan["enough"]:
                # Untestable is a verdict of its own; the gate must not read it as
                # a failure of the strategy.
                logger.info("walk-forward not testable for %s: %s",
                            algorithm, plan["note"])
                return {"not_testable": True, "note": plan["note"],
                        "hold_days": hold["hold_days"],
                        "hold_days_source": hold["source"],
                        "requested_folds": plan["folds"],
                        "folds_required": need,
                        "fold_requirement_settled": settled,
                        "history_floor": history, **reach,
                        "folds_measurable": 0, "folds_retained": 0}, None
            out = WalkForward(runner=self._lean()).evaluate(
                algorithm, grid, plan["folds"])
            out["hold_days"] = hold["hold_days"]
            out["hold_days_source"] = hold["source"]
            out["requested_folds"] = plan["folds"]
            out["test_days"] = plan["test_days"]
            # What the belt PLANNED against. The gate recomputes this from the
            # fold windows rather than reading it — a criterion that trusts a
            # number the payload asserts about itself is not a criterion — so
            # this is here for a human comparing the two, not for the gate.
            out["folds_required"] = need
            out["fold_requirement_settled"] = settled
            out["history_floor"] = history
            out.update(reach)
            return out, None
        except Exception as e:  # noqa: BLE001
            logger.warning("walk-forward unavailable for %s: %s", algorithm, e)
            return None, (f"the walk-forward leg raised {type(e).__name__}: {e} — "
                          f"it was attempted and failed, which is not the same as "
                          f"never having been asked for"[:400])

    @staticmethod
    def _await(fetch, timeout_s: float = 3_600.0, poll_s: float = 2.0) -> dict[str, Any]:
        import time
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            out = fetch()
            if out.get("state") in ("done", "failed"):
                return out
            time.sleep(poll_s)
        return {"state": "timeout"}

    def _finish(self, candidate_id: str, verdict: Optional[dict] = None,
                winner: Optional[dict] = None, error: Optional[str] = None,
                analytics: Optional[dict] = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fund_candidates
                       SET state = %s, passed = %s, failures = %s, winner = %s,
                           verdict = %s, error = %s, analytics = %s,
                           finished_at = now()
                     WHERE candidate_id = %s
                    """,
                    ("failed" if error else "done",
                     None if error else bool(verdict and verdict.get("passed")),
                     json.dumps((verdict or {}).get("failures") or []),
                     json.dumps(winner) if winner else None,
                     json.dumps(verdict) if verdict else None,
                     error,
                     # default=str for the same reason leanstore._js has it: one
                     # statistic arriving as a Decimal must not cost the whole
                     # capture. A failed capture would be silent otherwise, and
                     # the row would read as never-captured — which is a lie.
                     json.dumps(analytics, default=str) if analytics else None,
                     candidate_id))
            conn.commit()

    #: A candidate takes ~20 minutes through the belt. Anything still `running`
    #: after this cannot be: the thread that would finish it is in-process, so it
    #: died with whatever restarted the spine. Generous, because the cost of
    #: waiting is nothing and the cost of orphaning a live run is a wasted hour.
    ORPHAN_AFTER_HOURS = 3.0

    def reconcile_orphans(self, max_age_hours: Optional[float] = None
                          ) -> dict[str, Any]:
        """Close out candidates whose runner died, WITHOUT inventing a verdict.

        The row lives in Postgres; the thread that finishes it does not. So every
        spine restart leaves any in-flight candidate stuck in `running` forever —
        and it stays in the scoreboard as neither judged nor failed, quietly
        subtracting from the judged count and making the survival rate wrong.
        Three of them had accumulated before this existed.

        The new state is `orphaned`, and that word is doing real work. It is NOT
        `failed`: a run that was interrupted produced no evidence, and recording it
        as a failure would mean the fund had learned something from a restart. It
        is not `done` either. It is the same distinction the gate draws between a
        strategy that lost and a strategy that was never examined — an interrupted
        run is an absence, and absences are never scored.
        """
        ceiling = self.ORPHAN_AFTER_HOURS if max_age_hours is None else max_age_hours
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fund_candidates
                       SET state = 'orphaned', finished_at = now(),
                           error = %s
                     WHERE state = 'running'
                       AND started_at < now() - (%s * INTERVAL '1 hour')
                 RETURNING candidate_id, algorithm, started_at
                    """,
                    ("the runner died before this could be judged — most likely the "
                     "spine restarted. NOT a failure and NOT a result: an "
                     "interrupted run produced no evidence, and re-running it is "
                     "the only way to learn anything from it",
                     ceiling))
                rows = cur.fetchall() or []
            conn.commit()
        out = [{"candidate_id": r[0], "algorithm": r[1],
                "started_at": r[2].isoformat() if r[2] else None} for r in rows]
        if out:
            logger.warning(
                "reconciled %d orphaned candidate(s) older than %.1fh: %s",
                len(out), ceiling, ", ".join(r["candidate_id"] for r in out))
        return {
            "orphaned": out, "count": len(out), "ceiling_hours": ceiling,
            "note": (f"{len(out)} candidate(s) had been stuck 'running' since "
                     f"their runner died. Marked ORPHANED, which is neither passed "
                     f"nor failed — re-run them to learn anything"
                     if out else
                     "no candidate has been running longer than the ceiling"),
        }

    #: How long a candidate's captured analytics is kept. Deliberately far longer
    #: than the engine's own results directories (1 day): those are debug
    #: material that the parsed result supersedes, while THIS is the evidence a
    #: deployment decision rested on. 90 days covers a full quarter of review —
    #: long enough that a verdict argued about in October still has its curve.
    #:
    #: Sized from measurement, not taste: a captured envelope is ~11 KB for a
    #: short window and ~80 KB for a five-year one, and this belt has judged 37
    #: candidates in its lifetime. Ninety days of that pace is single-digit
    #: megabytes in one JSONB column.
    ANALYTICS_RETENTION_DAYS = float(os.getenv("FUND_ANALYTICS_RETENTION_DAYS", "90"))

    #: Kept regardless of age, newest first — the same rule the engine's result
    #: directories use, and for the same reason: after an idle month every row is
    #: stale, and age alone would sweep the most recent evidence anyone has.
    ANALYTICS_KEEP_NEWEST = int(os.getenv("FUND_ANALYTICS_KEEP_NEWEST", "50"))

    def prune_analytics(self, max_age_days: Optional[float] = None,
                        keep_newest: Optional[int] = None) -> dict[str, Any]:
        """Age out captured payloads, leaving a TOMBSTONE rather than a NULL.

        The distinction is the whole point and it is the reason this is not one
        line of SQL setting the column back to NULL. A NULL is indistinguishable
        from a candidate judged before the column existed — and the two send a
        reader to different places: one had evidence that expired and can be
        re-run to get it back, the other never had any. Writing the same value
        for both would be a fresh instance of the absence-is-not-zero error this
        fund has now fixed in the gate, the NAV fold and the risk monitor.

        A candidate that is still `running` is never touched, whatever its age:
        its analytics are about to be written.
        """
        from app.fund import runanalytics
        age = (self.ANALYTICS_RETENTION_DAYS if max_age_days is None
               else max_age_days)
        keep = self.ANALYTICS_KEEP_NEWEST if keep_newest is None else keep_newest
        stone = json.dumps(runanalytics.pruned(retention_days=age))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fund_candidates
                       SET analytics = %s::jsonb
                     WHERE analytics IS NOT NULL
                       AND (analytics ? 'pruned') IS NOT TRUE
                       AND state <> 'running'
                       AND started_at < now() - (%s * INTERVAL '1 day')
                       AND candidate_id NOT IN (
                             SELECT candidate_id FROM fund_candidates
                              WHERE analytics IS NOT NULL
                           ORDER BY started_at DESC LIMIT %s)
                 RETURNING candidate_id
                    """,
                    (stone, age, keep))
                rows = cur.fetchall() or []
            conn.commit()
        ids = [r[0] for r in rows]
        if ids:
            logger.info("pruned analytics for %d candidate(s) older than %.0fd "
                        "(kept newest %d)", len(ids), age, keep)
        return {
            "pruned": ids, "count": len(ids), "retention_days": age,
            "kept_newest": keep,
            "note": (f"{len(ids)} candidate(s) had their captured analytics aged "
                     f"out. Each row now carries a tombstone saying so — pruned "
                     f"is NOT the same as never captured, and the Lab says which"
                     if ids else
                     f"nothing captured longer than {age:.0f}d ago outside the "
                     f"newest {keep}"),
        }

    # --- memory -------------------------------------------------------------

    def get(self, candidate_id: str) -> Optional[dict[str, Any]]:
        """One candidate, WITH its full analytics payload.

        The detail read is the only one that carries the equity curve and the
        fills. A verification run is ~11 KB for a short window and around 80 KB
        for a five-year one (measured on job 53ef3e67d89a and on entry 11's
        254-fill run), so serving 50 of them on the list read would be several
        megabytes to render a table — see `history`.
        """
        rows = self._rows("WHERE candidate_id = %s", (candidate_id,), 1, detail=True)
        return rows[0] if rows else None

    def history(self, algorithm: Optional[str] = None,
                limit: int = 50) -> list[dict[str, Any]]:
        """What has already been tried, and why it died.

        The point of keeping this: without it, research rediscovers the same
        broken idea every few weeks with the enthusiasm of the first time.

        Carries the walk-forward FOLD ROWS but not the equity curves or the
        fills. The folds are what the index has to show — a run reading "2 of 4"
        is unreadable without the four rows behind it — and they are about a
        kilobyte per candidate. The curves are two orders of magnitude larger and
        have exactly one reader, the panel for the run you opened.
        """
        if algorithm:
            return self._rows("WHERE algorithm = %s ORDER BY started_at DESC LIMIT %s",
                              (algorithm, limit), limit)
        return self._rows("ORDER BY started_at DESC LIMIT %s", (limit,), limit)

    def _rows(self, where: str, params: tuple, limit: int,
              detail: bool = False) -> list[dict[str, Any]]:
        from app.fund import runanalytics
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT candidate_id, algorithm, grid, holdout, state, passed, "
                    "       failures, winner, error, started_at, finished_at, "
                    "       verdict, analytics "
                    f"FROM fund_candidates {where}", params)
                rows = cur.fetchall()
        out = []
        for r in rows:
            # The verdict was WRITTEN to this column from the first day and never
            # SELECTed, so nothing could read it back. Two consequences, both of
            # which were found downstream and misdiagnosed there:
            #
            #   * the null audit recorded `walkforward=None/None` while the same
            #     candidate's failure text said "1 of 4 independent folds" — the
            #     leg had run and the structured capture was reading a key no
            #     endpoint returned.
            #   * the mechanics view reported that a stored verdict "does not
            #     record which gate version judged it". It does. GATE_VERSION is
            #     in here, and has been all along.
            #
            # Hoisted to the top level as well as left nested, because the fold
            # counts and the gate version are the two things every reader wants
            # and neither should require knowing the verdict's shape.
            v = r[11] or {}
            checks = (v.get("checks") or {}) if isinstance(v, dict) else {}
            raw = r[12] if isinstance(r[12], dict) else None
            # ONE shape whether or not there is anything to show, so no consumer
            # has to branch on null before it can branch on content. The four
            # absences (never captured / pruned / unavailable / not testable) are
            # each named — see app/fund/runanalytics.py for why they are not one.
            seen = runanalytics.view(raw)
            out.append({
                "candidate_id": r[0], "algorithm": r[1], "grid": r[2],
                "holdout": r[3], "state": r[4], "passed": r[5],
                "failures": r[6], "winner": r[7], "error": r[8],
                "started_at": r[9].isoformat() if r[9] else None,
                "finished_at": r[10].isoformat() if r[10] else None,
                "verdict": v or None,
                "gate_version": v.get("gate_version") if isinstance(v, dict) else None,
                "walkforward": {
                    "folds_measurable": checks.get("walkforward_folds_measurable"),
                    "folds_retained": checks.get("walkforward_folds_retained"),
                    "median_retention": checks.get("walkforward_median_retention"),
                    "retained_share": checks.get("walkforward_retained_share"),
                    "not_testable": checks.get("not_testable"),
                    # Requested by the quant seat 2026-08-21 (run-quant-entry11,
                    # accepted): "per-fold rows had to be reconstructed from
                    # sweeps by grid-key luck". Each row carries its requested
                    # dates, the window the engine actually covered via
                    # `dates_honoured`, and its own measurable/why-not reason.
                    # None, not [], when there are no rows — an empty list would
                    # read as a claim about the strategy.
                    "folds": runanalytics.folds(raw),
                } if checks else None,
                # Availability travels on BOTH reads; the payload only on detail.
                # A list row that carried `analytics: null` would be ambiguous
                # between "nothing was captured" and "the list does not serve it".
                "analytics_available": bool(seen.get("available")),
                "analytics_absence": None if seen.get("available") else {
                    "reason": seen.get("reason"), "note": seen.get("note"),
                    "pruned_at": seen.get("pruned_at"),
                },
                **({"analytics": seen} if detail else {}),
            })
        return out

    def scoreboard(self) -> dict[str, Any]:
        """How the factory is doing — kills are the product, not the waste."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FILTER (WHERE state='done'), "
                    "       count(*) FILTER (WHERE passed), "
                    "       count(*) FILTER (WHERE state='failed'), "
                    "       count(*) FILTER (WHERE state='orphaned'), "
                    "       count(*) FILTER (WHERE state='running'), count(*) "
                    "FROM fund_candidates")
                done, passed, failed, orphaned, running, total = cur.fetchone()
        judged = int(done or 0)
        return {
            "submitted": int(total or 0), "judged": judged,
            "passed": int(passed or 0), "killed": judged - int(passed or 0),
            "errored": int(failed or 0),
            # Reported rather than folded into anything. An interrupted run is an
            # absence: counting it as judged would invent a verdict, and counting
            # it as killed would credit the gate with a decision it never made.
            "orphaned": int(orphaned or 0),
            "running": int(running or 0),
            "note": ("a low pass rate is the factory working: the bar exists to "
                     "kill things cheaply, and a gate that passes most of what "
                     "it sees is not a gate"),
            "absence_note": (
                f"{int(orphaned or 0)} orphaned and {int(running or 0)} still in "
                f"flight, both EXCLUDED from judged. An interrupted run produced no "
                f"evidence — scoring it either way would be inventing one."
                if (orphaned or running) else None),
        }
