"""Postgres is where the fund runs; Firestore is where it survives.

Postgres holds the operational log — cheap reads, one-transaction appends, no
daily quota to run out of mid-afternoon. But it is one container on one
machine, and a fund whose entire history lives on a laptop's D: drive is one
disk failure from having no history at all.

So the log is pushed to Firestore periodically. Deliberately a PUSH of new
events rather than a mirror: the ledger is append-only, so "what changed" is
always a contiguous tail, and a watermark makes each run cost exactly the
writes it needs and no reads at all. That matters — the free tier meters reads
AND writes, and a snapshot that re-read the destination to work out what to
send would spend the quota it exists to conserve.

The watermark lives in Postgres, not Firestore, for the same reason.

What this is NOT: a failover. Firestore lags by up to one snapshot interval,
so promoting it after a Postgres loss means losing whatever came after the last
run. It is a durable copy, and the honest description of it is "yesterday's
fund, offsite", which is worth a great deal and is not the same as "no data
loss".
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)

WATERMARK_SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_snapshot_state (
    id            INT         PRIMARY KEY DEFAULT 1,
    last_seq      BIGINT      NOT NULL DEFAULT 0,
    last_run_at   TIMESTAMPTZ,
    last_ok       BOOLEAN,
    last_error    TEXT,
    CONSTRAINT fund_snapshot_state_singleton CHECK (id = 1)
);
INSERT INTO fund_snapshot_state (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

-- THE FLIGHT RECORDER'S OFFSITE COPY (CTO finding, 2026-08-21: `fund_agent_runs`
-- is single-copy). Every agent run the firm has ever done lives in one Postgres
-- container on one machine, which is the exact condition this module was built
-- to end for the event log.
--
-- A SEQ WATERMARK DOES NOT WORK HERE and that is the whole design problem. The
-- event log is append-only, so "what changed" is always a contiguous tail. Runs
-- are UPSERTED: `record_run` rewrites output/verdict/recommendations on
-- conflict, and `decide_recommendation` mutates the recommendations JSONB —
-- neither touches `resolved_at`. A timestamp or sequence watermark would push a
-- run once and never notice that the CEO later accepted six of its
-- recommendations, leaving the offsite copy quietly wrong about every decision
-- the firm made.
--
-- So the unit of change is a CONTENT HASH per run, kept HERE rather than read
-- back from Firestore — reading the destination is the cost this whole module
-- exists to avoid. Steady state with nothing changed is zero writes; a run that
-- changes anywhere in its row is re-pushed whole.
CREATE TABLE IF NOT EXISTS fund_snapshot_runs_state (
    run_id       TEXT PRIMARY KEY,
    content_hash TEXT NOT NULL,
    pushed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

#: Firestore rejects a batch over 500 operations.
BATCH = 400

#: Where the runs land offsite. Mirrors the Postgres table name so a restore is
#: obvious rather than a lookup.
RUNS_COLLECTION = "fund_agent_runs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FirestoreSnapshotter:
    """Copies new events from Postgres to Firestore, and remembers where it got to."""

    def __init__(self, pg_store=None, db=None):
        from app.fund.pgstore import PostgresEventStore
        self._pg = pg_store or PostgresEventStore()
        self._db_override = db
        self._ensure_schema()

    @property
    def _db(self):
        if self._db_override is not None:
            return self._db_override
        from app.core.firebase import db as _fs_db
        return _fs_db()

    def _ensure_schema(self) -> None:
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(WATERMARK_SCHEMA)
            conn.commit()

    # --- watermark ----------------------------------------------------------

    def watermark(self) -> int:
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT last_seq FROM fund_snapshot_state WHERE id = 1")
                row = cur.fetchone()
                return int(row[0]) if row else 0

    def set_watermark(self, seq: int) -> int:
        """Declare that Firestore already holds everything up to ``seq``.

        Needed exactly once, after the migration: the ledger was copied INTO
        Postgres from a source that mirrors Firestore, so the destination
        already has those events and re-pushing them would spend a hundred and
        fifty writes to change nothing. Set deliberately rather than inferred,
        because inferring it means reading the destination — the cost this
        whole design exists to avoid.
        """
        self._record(int(seq), True, None)
        return int(seq)

    def _record(self, last_seq: int, ok: bool, error: Optional[str]) -> None:
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE fund_snapshot_state
                       SET last_seq = %s, last_run_at = now(), last_ok = %s,
                           last_error = %s
                     WHERE id = 1
                    """,
                    (last_seq, ok, error),
                )
            conn.commit()

    def status(self) -> dict[str, Any]:
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT last_seq, last_run_at, last_ok, last_error "
                    "FROM fund_snapshot_state WHERE id = 1"
                )
                row = cur.fetchone()
        head = self._pg.count()
        last_seq = int(row[0]) if row else 0
        out = {
            "snapshotted_through_seq": last_seq,
            "events_in_postgres": head,
            "behind_by": max(0, self._head_seq() - last_seq),
            "last_run_at": row[1].isoformat() if row and row[1] else None,
            "last_ok": row[2] if row else None,
            "last_error": row[3] if row else None,
        }
        # The runs leg reports its OWN behind-by, on the same accounting: how
        # many agent runs differ from what is offsite. Reported separately
        # rather than folded into `behind_by`, because a caller watching the
        # event log's lag must not have that number moved by an unrelated leg.
        out["runs"] = self.runs_status()
        return out

    def runs_status(self) -> dict[str, Any]:
        """How far the flight recorder's offsite copy is behind.

        `behind_by` counts runs whose CONTENT differs from what was pushed, not
        runs that are new — a run whose recommendations were decided since the
        last push is behind, and a copy that called it up-to-date would be wrong
        about every decision the firm made on it.
        """
        try:
            rows = self._runs_with_hashes()
        except Exception as e:  # noqa: BLE001
            return {"behind_by": None, "runs_in_postgres": None,
                    "note": f"the runs table could not be read ({type(e).__name__})"
                            f" — how far behind the offsite copy is, is UNKNOWN"}
        stale = [r for r in rows if r["content_hash"] != r["pushed_hash"]]
        return {
            "runs_in_postgres": len(rows),
            "behind_by": len(stale),
            "never_pushed": sum(1 for r in rows if r["pushed_hash"] is None),
            "changed_since_push": sum(
                1 for r in rows if r["pushed_hash"] is not None
                and r["pushed_hash"] != r["content_hash"]),
            "note": ("every run is offsite and unchanged since"
                     if not stale else
                     f"{len(stale)} of {len(rows)} run(s) differ from the offsite "
                     f"copy — new, or changed since they were pushed"),
        }

    def _runs_with_hashes(self) -> list[dict[str, Any]]:
        """Every run, its content hash, and the hash last pushed.

        The hash is taken over the WHOLE row, `recommendations` included, which
        is the point: a decision recorded on a recommendation changes the row
        without changing any timestamp, and that is precisely the update a
        timestamp watermark would miss.
        """
        import hashlib
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT r.run_id, r.seat, r.task, r.model, r.tokens, "
                    "       r.tool_uses, r.dispatched_at, r.resolved_at, "
                    "       r.artifact_path, r.verdict, r.reasoning, r.output, "
                    "       r.trace_id, r.recommendations, r.meta, s.content_hash "
                    "  FROM fund_agent_runs r "
                    "  LEFT JOIN fund_snapshot_runs_state s USING (run_id) "
                    " ORDER BY r.resolved_at DESC NULLS LAST")
                rows = cur.fetchall()
        import json as _json
        out = []
        for r in rows:
            doc = {
                "run_id": r[0], "seat": r[1], "task": r[2], "model": r[3],
                "tokens": r[4], "tool_uses": r[5],
                "dispatched_at": r[6].isoformat() if r[6] else None,
                "resolved_at": r[7].isoformat() if r[7] else None,
                "artifact_path": r[8], "verdict": r[9], "reasoning": r[10],
                "output": r[11], "trace_id": r[12],
                "recommendations": r[13] or [], "meta": r[14] or {},
            }
            blob = _json.dumps(doc, sort_keys=True, default=str)
            out.append({
                "doc": doc,
                "run_id": r[0],
                "content_hash": hashlib.sha256(blob.encode("utf-8")).hexdigest(),
                "pushed_hash": r[15],
            })
        return out

    def run_runs(self, dry_run: bool = False) -> dict[str, Any]:
        """Push every CHANGED agent run offsite. Same cadence, same accounting.

        Deliberately not watermarked by time or sequence — see the schema note.
        A run is pushed when its content hash differs from the hash last pushed,
        so an idle hour costs zero writes and a decided recommendation costs one.

        The hash is recorded ONLY after the batch commits, so a failure mid-way
        leaves the remaining runs looking stale and the next cycle finishes the
        job rather than skipping it.
        """
        try:
            rows = self._runs_with_hashes()
        except Exception as e:  # noqa: BLE001
            return {"pushed": 0, "error": f"{type(e).__name__}: {e}"[:400],
                    "note": "the runs table could not be read — nothing was pushed"}
        stale = [r for r in rows if r["content_hash"] != r["pushed_hash"]]
        if not stale:
            return {"pushed": 0, "examined": len(rows),
                    "note": "every run is already offsite and unchanged"}
        if dry_run:
            return {"pushed": 0, "would_push": len(stale), "examined": len(rows),
                    "note": "dry run"}

        db = self._db
        pushed = 0
        done: list[tuple[str, str]] = []
        try:
            for i in range(0, len(stale), BATCH):
                chunk = stale[i:i + BATCH]
                batch = db.batch()
                for r in chunk:
                    # run_id as the document id: re-pushing a run overwrites
                    # itself rather than duplicating, so a half-finished cycle
                    # is always safe to repeat.
                    batch.set(db.collection(RUNS_COLLECTION).document(r["run_id"]),
                              r["doc"])
                batch.commit()
                pushed += len(chunk)
                done += [(r["run_id"], r["content_hash"]) for r in chunk]
            self._record_run_hashes(done)
            return {"pushed": pushed, "examined": len(rows),
                    "note": f"{pushed} run(s) pushed offsite"}
        except Exception as e:  # noqa: BLE001
            # Whatever landed is recorded, so a retry resumes rather than
            # restarting — the same rule the event leg follows.
            self._record_run_hashes(done)
            logger.warning("run snapshot to Firestore failed after %d: %s", pushed, e)
            return {"pushed": pushed, "examined": len(rows),
                    "error": f"{type(e).__name__}: {e}"[:400]}

    def _record_run_hashes(self, pairs: list[tuple[str, str]]) -> None:
        if not pairs:
            return
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    "INSERT INTO fund_snapshot_runs_state (run_id, content_hash) "
                    "VALUES (%s,%s) ON CONFLICT (run_id) DO UPDATE SET "
                    "content_hash = EXCLUDED.content_hash, pushed_at = now()",
                    pairs)
            conn.commit()

    def _head_seq(self) -> int:
        with self._pg._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT coalesce(max(seq), 0) FROM fund_events")
                return int(cur.fetchone()[0])

    # --- the push -----------------------------------------------------------

    def run(self, dry_run: bool = False) -> dict[str, Any]:
        """Push everything after the watermark. Returns what it did."""
        from app.fund.events import EVENTS_COLLECTION, _COUNTER_DOC

        start = self.watermark()
        pending = self._pg.stream(since_seq=start, limit=1_000_000)
        if not pending:
            return {"pushed": 0, "from_seq": start, "to_seq": start,
                    "note": "already up to date"}

        if dry_run:
            return {"pushed": 0, "would_push": len(pending),
                    "from_seq": start + 1, "to_seq": pending[-1]["seq"],
                    "note": "dry run"}

        db = self._db
        pushed = 0
        last_seq = start
        try:
            for i in range(0, len(pending), BATCH):
                chunk = pending[i:i + BATCH]
                batch = db.batch()
                for e in chunk:
                    # event_id as the document id: the same event pushed twice
                    # overwrites itself instead of duplicating, so a snapshot
                    # that dies halfway is safe to re-run.
                    ref = db.collection(EVENTS_COLLECTION).document(e["event_id"])
                    batch.set(ref, e)
                batch.commit()
                pushed += len(chunk)
                last_seq = chunk[-1]["seq"]

            # Keep Firestore's counter honest too. Without this the copy holds
            # every event but still believes the log ends where it did before,
            # and an append against the restored copy would reuse a seq and
            # chain onto the wrong tip — a silent fork at the worst moment.
            tail = pending[-1]
            db.collection(_COUNTER_DOC[0]).document(_COUNTER_DOC[1]).set(
                {"seq": tail["seq"], "tip_hash": tail["hash"]}, merge=True)

            self._record(last_seq, True, None)
            return {"pushed": pushed, "from_seq": start + 1, "to_seq": last_seq,
                    "tip_hash": tail["hash"]}
        except Exception as e:  # noqa: BLE001
            # The watermark advances to whatever DID land, so a retry resumes
            # rather than restarting — and the error is recorded rather than
            # raised into a scheduler that would only log it anyway.
            self._record(last_seq, False, f"{type(e).__name__}: {e}"[:400])
            logger.warning("snapshot to Firestore failed after %d events: %s",
                           pushed, e)
            return {"pushed": pushed, "from_seq": start + 1, "to_seq": last_seq,
                    "error": f"{type(e).__name__}: {e}"[:400]}
