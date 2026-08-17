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
import threading
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

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
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


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

    def _run(self, candidate_id: str, algorithm: str,
             grid: dict[str, list[str]], holdout: Optional[dict[str, str]]) -> None:
        from app.fund.gate import evaluate
        runner = self._lean()
        try:
            sub = runner.submit_sweep(algorithm, grid, holdout)
            sweep = self._await(lambda: runner.sweep(sub["sweep_id"]))
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
            if job.get("state") != "done":
                return self._finish(candidate_id,
                                    error=f"verification run {job.get('state')}: {job.get('error')}")

            verdict = evaluate(job.get("result") or {},
                               sweep.get("holdout_result"),
                               sweep.get("summary"))
            self._finish(candidate_id, verdict=verdict, winner=params)
        except Exception as e:  # noqa: BLE001
            logger.warning("candidate %s failed: %s", candidate_id, e)
            self._finish(candidate_id, error=f"{type(e).__name__}: {e}"[:400])

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
                winner: Optional[dict] = None, error: Optional[str] = None) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fund_candidates
                       SET state = %s, passed = %s, failures = %s, winner = %s,
                           verdict = %s, error = %s, finished_at = now()
                     WHERE candidate_id = %s
                    """,
                    ("failed" if error else "done",
                     None if error else bool(verdict and verdict.get("passed")),
                     json.dumps((verdict or {}).get("failures") or []),
                     json.dumps(winner) if winner else None,
                     json.dumps(verdict) if verdict else None,
                     error, candidate_id))
            conn.commit()

    # --- memory -------------------------------------------------------------

    def get(self, candidate_id: str) -> Optional[dict[str, Any]]:
        rows = self._rows("WHERE candidate_id = %s", (candidate_id,), 1)
        return rows[0] if rows else None

    def history(self, algorithm: Optional[str] = None,
                limit: int = 50) -> list[dict[str, Any]]:
        """What has already been tried, and why it died.

        The point of keeping this: without it, research rediscovers the same
        broken idea every few weeks with the enthusiasm of the first time.
        """
        if algorithm:
            return self._rows("WHERE algorithm = %s ORDER BY started_at DESC LIMIT %s",
                              (algorithm, limit), limit)
        return self._rows("ORDER BY started_at DESC LIMIT %s", (limit,), limit)

    def _rows(self, where: str, params: tuple, limit: int) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT candidate_id, algorithm, grid, holdout, state, passed, "
                    "       failures, winner, error, started_at, finished_at "
                    f"FROM fund_candidates {where}", params)
                rows = cur.fetchall()
        return [{
            "candidate_id": r[0], "algorithm": r[1], "grid": r[2],
            "holdout": r[3], "state": r[4], "passed": r[5],
            "failures": r[6], "winner": r[7], "error": r[8],
            "started_at": r[9].isoformat() if r[9] else None,
            "finished_at": r[10].isoformat() if r[10] else None,
        } for r in rows]

    def scoreboard(self) -> dict[str, Any]:
        """How the factory is doing — kills are the product, not the waste."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FILTER (WHERE state='done'), "
                    "       count(*) FILTER (WHERE passed), "
                    "       count(*) FILTER (WHERE state='failed'), count(*) "
                    "FROM fund_candidates")
                done, passed, failed, total = cur.fetchone()
        judged = int(done or 0)
        return {
            "submitted": int(total or 0), "judged": judged,
            "passed": int(passed or 0), "killed": judged - int(passed or 0),
            "errored": int(failed or 0),
            "note": ("a low pass rate is the factory working: the bar exists to "
                     "kill things cheaply, and a gate that passes most of what "
                     "it sees is not a gate"),
        }
