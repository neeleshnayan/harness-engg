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


def session_schema_sql() -> str:
    """The session registry's DDL, with its uniqueness predicate DERIVED.

    **THE ALIVE STATES ARE READ FROM ``leansessions.ALIVE``, NOT RETYPED HERE.**
    The database's partial unique index and the runner's in-process guard are
    two halves of ONE rule, and a rule spelled twice is two rules that agree
    until the day one is edited. Building the predicate makes the copy
    impossible; ``tests/test_leansessions.py`` proves the read by MOVING the
    constant, because an assertion that the SQL merely CONTAINS 'running'
    cannot tell a read from a hardcoded duplicate that happens to agree today.

    ``fund_lean_sessions`` is OPERATIONAL STATE, not a fund fact: it records
    which engine processes exist, never what the fund owns. Fund facts go in the
    event log and nowhere else. This is the same distinction ``fund_lean_jobs``
    already makes, one table over.
    """
    from app.fund import leansessions
    alive = ", ".join(f"'{s}'" for s in leansessions.ALIVE)
    return f"""
CREATE TABLE IF NOT EXISTS fund_lean_sessions (
    session_id        TEXT PRIMARY KEY,
    scope_key         TEXT        NOT NULL,
    algorithm         TEXT        NOT NULL,
    class_name        TEXT,
    strategy_id       TEXT,
    state             TEXT        NOT NULL,
    container         TEXT        NOT NULL,
    signal_configured BOOLEAN     NOT NULL DEFAULT FALSE,
    mode              TEXT,
    error             TEXT,
    log_tail          JSONB,
    started_at        TIMESTAMPTZ,
    stopped_at        TIMESTAMPTZ,
    stored_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ATOMIC UNIQUENESS, IN THE DATABASE, BECAUSE A DICT READ CANNOT BE ATOMIC.
-- The guard this replaces read the session table, released its lock, and then
-- inserted: two identical POSTs two milliseconds apart both got 200 on
-- 2026-08-26 (ticket dc12903f). A partial unique index refuses the second
-- INSERT inside the transaction, with no window at all, and it holds ACROSS
-- PROCESSES — which no in-process lock can.
CREATE UNIQUE INDEX IF NOT EXISTS fund_lean_sessions_one_live_per_scope
    ON fund_lean_sessions (scope_key)
    WHERE state IN ({alive});

CREATE INDEX IF NOT EXISTS fund_lean_sessions_started_idx
    ON fund_lean_sessions (started_at DESC);

-- WHEN THE REGISTRY BEGAN RECORDING. The fence's anchor: no session started
-- before this instant can have a row, because the table did not exist. One
-- row, stamped at creation and never updated -- ON CONFLICT DO NOTHING is what
-- makes every later start-up leave the original instant alone.
CREATE TABLE IF NOT EXISTS fund_lean_session_epoch (
    id       INT PRIMARY KEY,
    began_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO fund_lean_session_epoch (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
"""


class SessionConflict(Exception):
    """A live session already holds this scope. Raised by the DATABASE's own
    constraint, not by a read — which is the entire point of it."""


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
                # Built rather than pasted: its uniqueness predicate is derived
                # from leansessions.ALIVE so the database and the runner cannot
                # hold two different ideas of "a session is alive".
                cur.execute(session_schema_sql())
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


    # --- the live-session registry -----------------------------------------
    #
    # NOT a best-effort mirror like the two above, and the difference matters.
    # A lost copy of a finished backtest costs a re-run; a lost session row
    # costs the fund a container it cannot stop and cannot account for, which
    # is exactly the orphan `engineledger.ORPHAN_NOTE` describes. So these
    # methods RAISE, and `leanrunner` refuses to start a session it could not
    # register rather than starting one nobody will remember.

    _SESSION_COLS = ("session_id, scope_key, algorithm, class_name, strategy_id, "
                     "state, container, signal_configured, mode, error, log_tail, "
                     "started_at, stopped_at")

    def claim_session(self, session: dict[str, Any]) -> None:
        """Insert the row, or raise ``SessionConflict``.

        The claim IS the insert. There is no read-then-write here on purpose:
        the check and the write must be one statement or the window between
        them is the race this replaces.
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"INSERT INTO fund_lean_sessions ({self._SESSION_COLS}) "
                        f"VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                        (session.get("session_id"), session.get("scope_key"),
                         session.get("algorithm"), session.get("class_name"),
                         session.get("strategy_id"), session.get("state"),
                         session.get("container"),
                         bool(session.get("signal_configured")),
                         session.get("mode"), session.get("error"),
                         _js(session.get("log_tail")), session.get("started_at"),
                         session.get("stopped_at")))
                conn.commit()
        except Exception as e:  # noqa: BLE001 — classified, then re-raised
            # 23505 is unique_violation. Read off the exception rather than
            # imported, so this does not depend on which psycopg version's
            # error class hierarchy is installed — the SQLSTATE is the stable
            # contract and the class name is not.
            if getattr(e, "sqlstate", None) == "23505":
                raise SessionConflict(
                    f"a live session already holds "
                    f"{session.get('scope_key')!r}") from e
            raise

    def update_session(self, session: dict[str, Any]) -> None:
        """Write a session's current state back. Raises like ``claim_session``.

        Only the fields that CHANGE after a claim are written: everything else
        was decided when the session was created, and an UPDATE that rewrote
        them could silently move a row's identity out from under the unique
        index.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE fund_lean_sessions SET state = %s, error = %s, "
                    "       log_tail = %s, stopped_at = %s, stored_at = now() "
                    "WHERE session_id = %s",
                    (session.get("state"), session.get("error"),
                     _js(session.get("log_tail")), session.get("stopped_at"),
                     session.get("session_id")))
            conn.commit()

    def session_rows(self, limit: int = 200) -> list[dict[str, Any]]:
        """Every session the registry knows, newest first.

        ``limit`` is NAMED and returned on the payload by the caller rather than
        left inline: HW1's lesson is that two folds over "the same rows" agree
        until one of them is capped, and the day the cap binds nothing on either
        surface points at it.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._SESSION_COLS} FROM fund_lean_sessions "
                    f"ORDER BY started_at DESC NULLS LAST LIMIT %s", (limit,))
                rows = cur.fetchall()
        return [_session_row(r) for r in rows]

    def live_session_rows(self) -> list[dict[str, Any]]:
        """Only the sessions claiming a container. Uncapped BY CONSTRUCTION:
        the partial unique index bounds this set by the number of distinct
        scopes, so there is no cap to hide behind."""
        from app.fund import leansessions
        marks = ",".join(["%s"] * len(leansessions.ALIVE))
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT {self._SESSION_COLS} FROM fund_lean_sessions "
                    f"WHERE state IN ({marks}) ORDER BY started_at DESC",
                    tuple(leansessions.ALIVE))
                rows = cur.fetchall()
        return [_session_row(r) for r in rows]

    def registry_epoch(self) -> Optional[str]:
        """When this registry began recording, or ``None`` if it cannot say.

        ``None`` propagates all the way to the fence, which then proves nothing
        — see ``leansessions.known_since`` for why that is the only safe
        fallback and the process's own birth is not.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT began_at FROM fund_lean_session_epoch "
                            "WHERE id = 1")
                r = cur.fetchone()
        return _iso(r[0]) if r and r[0] is not None else None


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


def _session_row(r: Any) -> dict[str, Any]:
    """One registry row, in the SAME SHAPE ``LeanRunner.start_live`` builds.

    Deliberately identical key-for-key: ``live_sessions()`` merges in-memory
    sessions with restored ones and every consumer — the fence, the engine page,
    ``engine_status`` — reads one shape. A restored row that dropped a key would
    make a session's fields depend on whether the spine had restarted, which is
    the class of defect the fence exists to keep out of this area.
    """
    return {
        "session_id": r[0], "scope_key": r[1], "algorithm": r[2],
        "class_name": r[3], "strategy_id": r[4], "state": r[5],
        "container": r[6], "signal_configured": bool(r[7]), "mode": r[8],
        "error": r[9], "log_tail": r[10] or [],
        "started_at": _iso(r[11]), "stopped_at": _iso(r[12]),
        # Says where the answer came from, exactly as ``job()`` does. A session
        # read back out of the registry was NOT started by this process, so its
        # ``_run_live`` thread does not exist and nothing here will update it
        # until the reconciler does.
        "restored": True,
    }
