"""The event log on Postgres — the fund's operational store.

Firestore held the ledger first, and its free tier stopped a trading day in the
middle: every projection folds by replaying the log, so a page render costs
hundreds of reads and the daily quota is reachable by lunchtime. A hash-chained
append-only log is relational-shaped work, and this is what a relational
database is for.

Two things are BETTER here than they were on Firestore, and both are
correctness rather than cost:

  1. The append is one transaction. On Firestore the seq counter and chain tip
     advanced in a transaction and the event document was written AFTER it, so
     a process that died in between left the tip pointing at an event that does
     not exist and the next append chained onto a phantom. Here the insert and
     the counter update commit together or not at all, and that failure mode
     stops existing.

  2. Reads are cheap, so the log does not need a memo in front of it to be
     affordable. The Firestore store keeps a seconds-long stream cache, which
     is a correctness hazard it then has to manage by hand (append() has to
     patch its own write into the cache so an idempotency check can see it).
     ``ORDER BY seq`` needs none of that.

The hashes are IDENTICAL to the Firestore ones: chain.py hashes a dict, not a
row, and the migration copies stored hashes verbatim rather than recomputing
them. A migrated ledger verifies against the same evidence it always did.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from app.fund.chain import GENESIS_HASH, event_hash, verify
from app.fund.events import Event, EventType
from app.fund.money import encode

logger = logging.getLogger(__name__)

#: Fields the log stores as columns. `payload` is JSONB; everything the chain
#: hashes is a column so a break can be diagnosed with SQL.
SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_events (
    seq             BIGINT PRIMARY KEY,
    event_id        TEXT        NOT NULL UNIQUE,
    aggregate_id    TEXT        NOT NULL,
    aggregate_type  TEXT        NOT NULL,
    type            TEXT        NOT NULL,
    actor           TEXT        NOT NULL,
    ts              TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    prev_hash       TEXT        NOT NULL,
    hash            TEXT        NOT NULL,
    written_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS fund_events_aggregate_idx ON fund_events (aggregate_id, seq);
CREATE INDEX IF NOT EXISTS fund_events_type_idx      ON fund_events (type, seq);

-- One row. Holds the next seq and the chain tip, so an append never has to
-- read the previous event to know what to chain onto.
CREATE TABLE IF NOT EXISTS fund_chain (
    id       INT  PRIMARY KEY DEFAULT 1,
    seq      BIGINT NOT NULL DEFAULT 0,
    tip_hash TEXT   NOT NULL DEFAULT '""" + GENESIS_HASH + """',
    CONSTRAINT fund_chain_singleton CHECK (id = 1)
);

INSERT INTO fund_chain (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
"""


def dsn() -> str:
    """The BASE connection string — one server, one credential.

    The DATABASE in it is a placeholder: which of the fund's three databases a
    process talks to is decided by its MODE, not by this string.
    ``mode.pg_dsn_for(spec, dsn())`` replaces the last path segment with
    ``krypton_fund`` / ``krypton_fund_dev`` / ``krypton_fund_prod``.

    Kept as one base rather than three environment variables because three
    variables is three chances for two of them to point at the same database,
    which is precisely the failure this separation exists to prevent.
    """
    return os.getenv(
        "FUND_PG_DSN",
        "postgresql://krypton:krypton_local@127.0.0.1:5433/krypton_fund",
    )


def database_of(dsn_str: str) -> str:
    """The database name a DSN points at. For saying so out loud."""
    head = (dsn_str or "").partition("?")[0]
    return head.rsplit("/", 1)[-1] if "/" in head else ""


class PostgresEventStore:
    """Append-only writer/reader over ``fund_events``.

    Interface-compatible with the Firestore EventStore: append, stream,
    by_aggregate, verify_chain.
    """

    #: How long to keep trying to reach Postgres AT CONSTRUCTION. Deliberately
    #: bounded and deliberately applied only here, not to every query.
    #:
    #: The spine died on startup with a ConnectionTimeout against a Postgres that
    #: had come up three minutes earlier — it lost a boot race and stayed dead,
    #: because the store connects during __init__ and an exception there takes the
    #: whole process with it.
    #:
    #: Retrying every query would have "fixed" that too, and would have been the
    #: wrong fix: a real outage would then present as slowness, queries would
    #: silently take twenty seconds, and the health check would report a fund that
    #: was fine. A boot race and an outage deserve different answers. This retries
    #: the handshake only; once the process is up, a failed connection still fails
    #: loudly and immediately.
    STARTUP_RETRY_SECONDS = float(os.getenv("FUND_PG_STARTUP_RETRY_SECONDS", "30"))
    STARTUP_RETRY_DELAY = 1.0

    def __init__(self, dsn_str: Optional[str] = None, pool: Any = None):
        self._dsn = dsn_str or dsn()
        self._pool = pool
        self.ensure_schema(retry_seconds=self.STARTUP_RETRY_SECONDS)

    @property
    def database(self) -> str:
        """Which database this store actually opened.

        Exposed so a reader can NAME the store it folded rather than assume
        it. "Which of these dollars are real" is answered by the store, and a
        store that cannot say its own name cannot answer it.
        """
        return database_of(self._dsn)

    # --- plumbing -----------------------------------------------------------

    def _connect(self):
        import psycopg
        if self._pool is not None:
            return self._pool.connection()
        return psycopg.connect(self._dsn, autocommit=False)

    def ensure_schema(self, retry_seconds: float = 0.0) -> None:
        """Create the schema, optionally waiting for Postgres to accept us.

        ``retry_seconds`` of 0 means one attempt and a raised exception, which is
        the correct behaviour everywhere except process start.
        """
        import time as _time

        deadline = _time.monotonic() + max(0.0, retry_seconds)
        attempt = 0
        while True:
            attempt += 1
            try:
                with self._connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute(SCHEMA)
                    conn.commit()
                if attempt > 1:
                    logger.info(
                        "postgres reachable on attempt %d — the boot race was "
                        "waited out rather than crashed on", attempt)
                return
            except Exception as e:  # noqa: BLE001
                remaining = deadline - _time.monotonic()
                if remaining <= 0:
                    # Out of patience. Raise the ORIGINAL failure rather than a
                    # summary of it: "could not connect after 30s" would hide
                    # whether this was a wrong password, a wrong port, or an
                    # absent server, and those need different fixes.
                    if attempt > 1:
                        logger.error(
                            "postgres unreachable after %d attempts over %.0fs; "
                            "raising the underlying error", attempt,
                            max(0.0, retry_seconds))
                    raise
                logger.warning(
                    "postgres not ready (attempt %d, %.0fs left): %s",
                    attempt, remaining, e)
                _time.sleep(min(self.STARTUP_RETRY_DELAY, remaining))

    # --- writes -------------------------------------------------------------

    def append(self, event: Event) -> Event:
        """Assign seq + timestamp, seal the chain link, persist. One transaction.

        ``SELECT ... FOR UPDATE`` on the single chain row serialises concurrent
        appends: the second writer blocks until the first commits, so two
        events cannot claim the same seq or chain onto the same tip.
        """
        event.ts = datetime.now(timezone.utc).isoformat()

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT seq, tip_hash FROM fund_chain WHERE id = 1 FOR UPDATE")
                row = cur.fetchone()
                last_seq, prev = (row[0], row[1]) if row else (0, GENESIS_HASH)
                nxt = last_seq + 1

                # encode() FIRST, exactly as the Firestore store does. Two
                # reasons, and the second is the dangerous one.
                #
                # Money in this codebase is Decimal, and json.dumps cannot
                # serialize it — set_allocation appended a Decimal payload and
                # the whole call died with a 500 that never reached the log.
                #
                # And the hash is computed over this body. Hashing unencoded
                # Decimals would produce a different digest than Firestore
                # would have produced for the identical event, so the two
                # stores would silently disagree about the same history — a
                # chain that verifies in one place and breaks in the other.
                body = encode(event.to_dict())
                body["seq"] = nxt
                body["prev_hash"] = prev
                body["hash"] = event_hash(body, prev)

                cur.execute(
                    """
                    INSERT INTO fund_events
                        (seq, event_id, aggregate_id, aggregate_type, type,
                         actor, ts, payload, prev_hash, hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (nxt, body["event_id"], body["aggregate_id"],
                     body["aggregate_type"], body["type"], body["actor"],
                     body["ts"], json.dumps(body["payload"]),
                     body["prev_hash"], body["hash"]),
                )
                cur.execute(
                    "UPDATE fund_chain SET seq = %s, tip_hash = %s WHERE id = 1",
                    (nxt, body["hash"]),
                )
            conn.commit()

        event.seq = nxt
        return event

    def append_raw(self, row: dict[str, Any]) -> None:
        """Insert an already-sealed event, hash and all. MIGRATION ONLY.

        Recomputing hashes on the way in would produce a ledger that verifies
        against itself while proving nothing about the history it claims to be
        — exactly the dishonesty the chain exists to prevent. So the stored
        seq, prev_hash and hash are copied verbatim, and the migration verifies
        the result before anything is allowed to depend on it.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO fund_events
                        (seq, event_id, aggregate_id, aggregate_type, type,
                         actor, ts, payload, prev_hash, hash)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (event_id) DO NOTHING
                    """,
                    (row["seq"], row["event_id"], row["aggregate_id"],
                     row["aggregate_type"], row["type"], row["actor"],
                     row["ts"], json.dumps(row.get("payload") or {}),
                     row.get("prev_hash") or GENESIS_HASH, row.get("hash") or ""),
                )
            conn.commit()

    def sync_chain_head(self) -> dict[str, Any]:
        """Point the counter at the real tail. Run after a migration."""
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT seq, hash FROM fund_events ORDER BY seq DESC LIMIT 1")
                row = cur.fetchone()
                seq, tip = (row[0], row[1]) if row else (0, GENESIS_HASH)
                cur.execute(
                    "UPDATE fund_chain SET seq = %s, tip_hash = %s WHERE id = 1",
                    (seq, tip or GENESIS_HASH),
                )
            conn.commit()
        return {"seq": seq, "tip_hash": tip or GENESIS_HASH}

    # --- reads --------------------------------------------------------------

    def stream(self, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        """The global log from ``since_seq`` (exclusive), oldest first.

        No memo in front of it, deliberately. The Firestore store caches
        because a read costs money there; here an indexed scan of a few hundred
        rows is cheaper than the bookkeeping a cache would need to stay honest.
        """
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT seq, event_id, aggregate_id, aggregate_type, type,
                           actor, ts, payload, prev_hash, hash
                    FROM fund_events
                    WHERE seq > %s
                    ORDER BY seq ASC
                    LIMIT %s
                    """,
                    (since_seq, limit),
                )
                return [_row_to_event(r) for r in cur.fetchall()]

    def by_aggregate(self, aggregate_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT seq, event_id, aggregate_id, aggregate_type, type,
                           actor, ts, payload, prev_hash, hash
                    FROM fund_events
                    WHERE aggregate_id = %s
                    ORDER BY seq ASC
                    """,
                    (str(aggregate_id),),
                )
                return [_row_to_event(r) for r in cur.fetchall()]

    def verify_chain(self, limit: int = 100_000) -> dict[str, Any]:
        return verify(self.stream(limit=limit)).to_dict()

    def count(self) -> int:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM fund_events")
                return int(cur.fetchone()[0])

    @staticmethod
    def invalidate_cache() -> None:
        """No cache to invalidate. Present so callers do not branch on backend."""
        return None


def _row_to_event(r: tuple) -> dict[str, Any]:
    """A row in the shape the projections already fold over."""
    return {
        "seq": r[0], "event_id": r[1], "aggregate_id": r[2],
        "aggregate_type": r[3], "type": r[4], "actor": r[5], "ts": r[6],
        "payload": r[7] if isinstance(r[7], dict) else json.loads(r[7] or "{}"),
        "prev_hash": r[8], "hash": r[9],
    }
