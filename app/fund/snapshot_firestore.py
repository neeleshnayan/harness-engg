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
"""

#: Firestore rejects a batch over 500 operations.
BATCH = 400


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
        return {
            "snapshotted_through_seq": last_seq,
            "events_in_postgres": head,
            "behind_by": max(0, self._head_seq() - last_seq),
            "last_run_at": row[1].isoformat() if row and row[1] else None,
            "last_ok": row[2] if row else None,
            "last_error": row[3] if row else None,
        }

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
