"""The scheduler lease on Postgres.

Same contract as the Firestore lease: one TTL lock deciding which process runs
the deterministic worker, so two spines cannot both strike NAV or both settle
the same order.

It moved for the same reason the ledger did. The lease is read and renewed on
every scheduler tick, and once Firestore's daily quota ran out those reads
started failing — which the lease correctly treats as "refuse to run", because
an unreachable lease is precisely the case where a process knows least about
whether it is alone. The safe behaviour was also the useless one: the fund
stopped striking NAV because a quota counter somewhere had rolled over.

``SELECT ... FOR UPDATE`` gives the same serialisation the Firestore
transaction did, and the row lives in the database the fund already depends on
to do anything at all. If Postgres is unreachable the fund has no ledger
either, so there is no longer a way for the lease alone to be the thing that
fails.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.fund.lease import DEFAULT_TTL_SECONDS, LEASE_DOC, LeaseState, identity

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS fund_leases (
    name        TEXT PRIMARY KEY,
    owner       TEXT,
    expires_at  TIMESTAMPTZ,
    acquired_at TIMESTAMPTZ,
    renewed_at  TIMESTAMPTZ,
    released_at TIMESTAMPTZ
);
"""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


class PostgresSchedulerLease:
    """A TTL lease over the deterministic worker, held in one Postgres row."""

    def __init__(self, dsn_str: Optional[str] = None,
                 ttl_seconds: int = DEFAULT_TTL_SECONDS,
                 owner: str | None = None, doc: str = LEASE_DOC):
        from app.fund.pgstore import dsn
        self._dsn = dsn_str or dsn()
        self._ttl = int(ttl_seconds)
        self._owner = owner or identity()
        self._name = doc
        self._held = False
        self._ensure_schema()

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def held(self) -> bool:
        return self._held

    def _connect(self):
        import psycopg
        return psycopg.connect(self._dsn, autocommit=False)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(SCHEMA)
            conn.commit()

    def acquire(self) -> LeaseState:
        """Take the lease if it is free or expired. Renew it if already ours.

        The read and the write are one transaction, so two processes racing for
        a free lease cannot both win: the second blocks on FOR UPDATE until the
        first commits, then sees the lease is taken.
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    # The row must exist before it can be locked; the insert is
                    # a no-op on every call after the first.
                    cur.execute(
                        "INSERT INTO fund_leases (name) VALUES (%s) "
                        "ON CONFLICT (name) DO NOTHING", (self._name,))
                    cur.execute(
                        "SELECT owner, expires_at, acquired_at FROM fund_leases "
                        "WHERE name = %s FOR UPDATE", (self._name,))
                    row = cur.fetchone()
                    holder, expires, acquired = row if row else (None, None, None)

                    now = _now()
                    mine = holder == self._owner
                    free = holder is None
                    stale = expires is not None and expires <= now
                    # An unreadable expiry is treated as expired rather than
                    # eternal: a corrupt field must not lock the scheduler out
                    # of its own book with no way back.
                    unreadable = holder is not None and expires is None

                    if not (mine or free or stale or unreadable):
                        conn.commit()
                        self._held = False
                        return LeaseState(
                            held=False, holder=holder, expires_at=_iso(expires),
                            reason=f"held by {holder} until {_iso(expires)}")

                    new_expiry = now + timedelta(seconds=self._ttl)
                    cur.execute(
                        """
                        UPDATE fund_leases
                           SET owner = %s, expires_at = %s,
                               acquired_at = %s, renewed_at = %s
                         WHERE name = %s
                        """,
                        (self._owner, new_expiry,
                         acquired if mine and acquired else now, now, self._name),
                    )
                conn.commit()
        except Exception as e:  # noqa: BLE001
            # Refuse to run rather than assume we are alone. The whole point is
            # not to double-write, and an unreachable lease is the case where
            # we know least.
            self._held = False
            return LeaseState(held=False, reason=f"lease unreadable: {e}")

        self._held = True
        return LeaseState(
            held=True, owner=self._owner, expires_at=_iso(new_expiry),
            reason=("renewed" if mine else
                    "taken (was free)" if free else
                    f"taken from {holder} (expired)" if stale else
                    f"taken from {holder} (unreadable expiry)"),
        )

    def release(self) -> bool:
        """Give the lease up on a clean shutdown, so the next process starts now.

        Only ever clears OUR ownership — the WHERE clause carries the owner, so
        a losing process cannot evict the winner on its way out.
        """
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE fund_leases
                           SET owner = NULL, expires_at = NULL, released_at = %s
                         WHERE name = %s AND owner = %s
                        """,
                        (_now(), self._name, self._owner),
                    )
                conn.commit()
        except Exception:  # noqa: BLE001
            return False       # it will expire on its own
        finally:
            self._held = False
        return True

    def state(self) -> LeaseState:
        """Who holds it right now, without trying to take it."""
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT owner, expires_at FROM fund_leases WHERE name = %s",
                        (self._name,))
                    row = cur.fetchone()
        except Exception as e:  # noqa: BLE001
            return LeaseState(held=False, reason=f"lease unreadable: {e}")

        holder, expires = row if row else (None, None)
        live = holder is not None and expires is not None and expires > _now()
        return LeaseState(
            held=live and holder == self._owner,
            owner=self._owner,
            expires_at=_iso(expires),
            holder=holder if live else None,
            reason=("free" if not live else
                    "ours" if holder == self._owner else f"held by {holder}"),
        )
