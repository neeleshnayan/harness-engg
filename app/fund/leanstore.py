"""LEAN runs, kept where the rest of the fund's state lives.

Jobs and sweeps were in-memory dicts, which was defensible only while a run was
throwaway compute. It is not. A sweep is the evidence that a good number sits on
a plateau rather than an island; a job carries the equity curve, the order list
and the cost disclosure a verdict was computed from. That is the audit trail for
every deployment decision the fund makes, and it was being lost on every restart
— including restarts nobody chose, which is precisely when you most want to know
what the machine had concluded.

Deliberately a write-through mirror rather than the primary store. The in-memory
dicts stay exactly as they were, so the hot path (a sweep polling its own
progress every few seconds, from a worker thread) never waits on a database, and
the concurrency model does not change. Postgres is written on each transition and
read only on a miss — which is to say, after a restart.

Persistence is OPTIONAL and silent when unavailable. A failed write must never
fail a backtest: losing the mirror of a result is a smaller harm than losing the
result, and the tests construct runners with no database at all.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_lean_jobs (
    job_id       TEXT PRIMARY KEY,
    algorithm    TEXT        NOT NULL,
    class_name   TEXT,
    parameters   JSONB,
    enrich       BOOLEAN     NOT NULL DEFAULT TRUE,
    state        TEXT        NOT NULL,
    error        TEXT,
    result       JSONB,
    log_tail     JSONB,
    submitted_at TIMESTAMPTZ,
    started_at   TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    wall_seconds NUMERIC,
    stored_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_lean_jobs_algo_idx
    ON fund_lean_jobs (algorithm, submitted_at DESC);

CREATE TABLE IF NOT EXISTS fund_lean_sweeps (
    sweep_id       TEXT PRIMARY KEY,
    algorithm      TEXT        NOT NULL,
    grid           JSONB       NOT NULL,
    state          TEXT        NOT NULL,
    total          INT,
    completed      INT,
    points         JSONB,
    summary        JSONB,
    holdout        JSONB,
    holdout_result JSONB,
    error          TEXT,
    submitted_at   TIMESTAMPTZ,
    finished_at    TIMESTAMPTZ,
    stored_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_lean_sweeps_algo_idx
    ON fund_lean_sweeps (algorithm, submitted_at DESC);
"""


def enabled() -> bool:
    """Only when the fund's state already lives in Postgres."""
    return os.getenv("FUND_STORE", "").lower() == "postgres"


class LeanStore:
    """Durable mirror of LEAN jobs and sweeps."""

    def __init__(self, dsn_str: Optional[str] = None):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._ensure_schema()

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    # --- writes ------------------------------------------------------------

    def save_job(self, job: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_lean_jobs
                        (job_id, algorithm, class_name, parameters, enrich, state,
                         error, result, log_tail, submitted_at, started_at,
                         finished_at, wall_seconds)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (job_id) DO UPDATE SET
                        state = EXCLUDED.state, error = EXCLUDED.error,
                        result = EXCLUDED.result, log_tail = EXCLUDED.log_tail,
                        started_at = EXCLUDED.started_at,
                        finished_at = EXCLUDED.finished_at,
                        wall_seconds = EXCLUDED.wall_seconds,
                        stored_at = now()
                    """,
                    (job.get("job_id"), job.get("algorithm"), job.get("class_name"),
                     _js(job.get("parameters")), bool(job.get("enrich", True)),
                     job.get("state"), job.get("error"), _js(job.get("result")),
                     _js(job.get("log_tail")), job.get("submitted_at"),
                     job.get("started_at"), job.get("finished_at"),
                     job.get("wall_seconds")))
            conn.commit()

    def save_sweep(self, sweep: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_lean_sweeps
                        (sweep_id, algorithm, grid, state, total, completed,
                         points, summary, holdout, holdout_result, error,
                         submitted_at, finished_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (sweep_id) DO UPDATE SET
                        state = EXCLUDED.state, completed = EXCLUDED.completed,
                        points = EXCLUDED.points, summary = EXCLUDED.summary,
                        holdout_result = EXCLUDED.holdout_result,
                        error = EXCLUDED.error,
                        finished_at = EXCLUDED.finished_at, stored_at = now()
                    """,
                    (sweep.get("sweep_id"), sweep.get("algorithm"),
                     _js(sweep.get("grid")), sweep.get("state"),
                     sweep.get("total"), sweep.get("completed"),
                     _js(sweep.get("points")), _js(sweep.get("summary")),
                     _js(sweep.get("holdout")), _js(sweep.get("holdout_result")),
                     sweep.get("error"), sweep.get("submitted_at"),
                     sweep.get("finished_at")))
            conn.commit()

    # --- reads -------------------------------------------------------------

    def job(self, job_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT job_id, algorithm, class_name, parameters, enrich, "
                    "       state, error, result, log_tail, submitted_at, "
                    "       started_at, finished_at, wall_seconds "
                    "FROM fund_lean_jobs WHERE job_id = %s", (job_id,))
                r = cur.fetchone()
        if not r:
            return None
        return {
            "job_id": r[0], "algorithm": r[1], "class_name": r[2],
            "parameters": r[3], "enrich": r[4], "state": r[5], "error": r[6],
            "result": r[7], "log_tail": r[8],
            "submitted_at": _iso(r[9]), "started_at": _iso(r[10]),
            "finished_at": _iso(r[11]),
            "wall_seconds": float(r[12]) if r[12] is not None else None,
            # Says where the answer came from. A run reloaded after a restart is
            # a record, not a live job, and a caller waiting for it to progress
            # would otherwise wait forever on something already finished.
            "restored": True,
        }

    def sweep(self, sweep_id: str) -> Optional[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sweep_id, algorithm, grid, state, total, completed, "
                    "       points, summary, holdout, holdout_result, error, "
                    "       submitted_at, finished_at "
                    "FROM fund_lean_sweeps WHERE sweep_id = %s", (sweep_id,))
                r = cur.fetchone()
        if not r:
            return None
        return {
            "sweep_id": r[0], "algorithm": r[1], "grid": r[2], "state": r[3],
            "total": r[4], "completed": r[5], "points": r[6] or [],
            "summary": r[7], "holdout": r[8], "holdout_result": r[9],
            "error": r[10], "submitted_at": _iso(r[11]),
            "finished_at": _iso(r[12]), "restored": True,
        }

    def recent_jobs(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT job_id, algorithm, state, submitted_at, wall_seconds "
                    "FROM fund_lean_jobs ORDER BY submitted_at DESC LIMIT %s",
                    (limit,))
                rows = cur.fetchall()
        return [{"job_id": r[0], "algorithm": r[1], "state": r[2],
                 "submitted_at": _iso(r[3]),
                 "wall_seconds": float(r[4]) if r[4] is not None else None}
                for r in rows]

    def recent_sweeps(self, limit: int = 25) -> list[dict[str, Any]]:
        # holdout_result is included since 2026-08-20: the validator's floor
        # review needed every sweep's train/test legs and found them reachable
        # only one detail-GET at a time, by ids the list mostly did not return.
        # An instrument audit should be a query, not an excavation.
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT sweep_id, algorithm, state, total, completed, "
                    "       summary, submitted_at, holdout_result "
                    "FROM fund_lean_sweeps ORDER BY submitted_at DESC LIMIT %s",
                    (limit,))
                rows = cur.fetchall()
        return [{"sweep_id": r[0], "algorithm": r[1], "state": r[2],
                 "total": r[3], "completed": r[4], "summary": r[5],
                 "submitted_at": _iso(r[6]), "holdout_result": r[7]}
                for r in rows]


def _js(v: Any) -> Optional[str]:
    """JSON for a JSONB column, with Decimals coerced the way the ledger does.

    ``default=str`` rather than a custom encoder: the alternative is a run
    failing to persist because one statistic arrived as a Decimal.
    """
    if v is None:
        return None
    return json.dumps(v, default=str)


def _iso(ts: Any) -> Optional[str]:
    return ts.isoformat() if hasattr(ts, "isoformat") else ts
