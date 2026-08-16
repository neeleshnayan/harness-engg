"""One scheduler at a time.

The spine starts its worker unconditionally in every process. That was
harmless while the ledger was a local file per process, and stopped being
harmless the moment the book moved to a shared Firestore: a Railway container
overlapping its predecessor during a redeploy, or a laptop pointed at
production alongside it, and two schedulers tick against one book.

What that actually costs is worth being precise about, because the obvious
answer is wrong. It does NOT corrupt the hash chain — the seq counter and the
chain tip advance inside a single Firestore transaction, which serialises
concurrent appends properly. The damage is semantic:

  - Two NAV strikes for the same moment. NAV_STRUCK is the official record of
    what a unit was worth; two of them for one instant is not a duplicate row,
    it is two contradictory answers to a question that has one.
  - Two reconciliation passes raising the same mismatch twice.
  - Double the broker and Firestore traffic, against a quota this fund has
    already exhausted once.

So the worker holds a lease. It is deliberately a lease and not a lock: a lock
held by a process that dies is held forever, while a lease expires and the next
scheduler picks the work up. Losing the lease is not an error either — it means
another process is doing the work, which is the desired state, so the loser
goes quiet rather than crashing.

The TTL must be comfortably longer than the tick interval. A lease that expires
between two ticks of its own holder hands the work back and forth and produces
exactly the double-execution it exists to prevent.
"""

from __future__ import annotations

import os
import socket
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

LEASE_COLLECTION = "fund_meta"
LEASE_DOC = "scheduler_lease"

#: How long a lease is good for without renewal. Long enough that a slow tick
#: does not drop it, short enough that a dead process is replaced promptly.
DEFAULT_TTL_SECONDS = 180


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(raw: Any) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def identity() -> str:
    """Who this process is, in a form a human can act on.

    A bare uuid tells an operator that someone else holds the lease but not
    where to go and stop it.
    """
    return f"{socket.gethostname()}/{os.getpid()}/{uuid.uuid4().hex[:8]}"


@dataclass
class LeaseState:
    held: bool
    owner: Optional[str] = None
    expires_at: Optional[str] = None
    #: Set when we do NOT hold it, naming who does.
    holder: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "held": self.held, "owner": self.owner, "expires_at": self.expires_at,
            "holder": self.holder, "reason": self.reason,
        }


class SchedulerLease:
    """A TTL lease over the deterministic worker, held in one Firestore doc.

    ``FUND_STORE=postgres`` returns a PostgresSchedulerLease instead, by the
    same ``__new__`` dispatch the event store uses: the lease travels with the
    ledger, because a lease in a database the fund is no longer reading is a
    dependency it cannot afford and does not need.
    """

    def __new__(cls, db=None, ttl_seconds: int = DEFAULT_TTL_SECONDS,
                owner: str | None = None, doc: str = LEASE_DOC):
        if db is None:
            import os
            if (os.getenv("FUND_STORE", "") or "").strip().lower() == "postgres":
                from app.fund.pglease import PostgresSchedulerLease
                return PostgresSchedulerLease(
                    ttl_seconds=ttl_seconds, owner=owner, doc=doc)
        return super().__new__(cls)

    def __init__(self, db=None, ttl_seconds: int = DEFAULT_TTL_SECONDS,
                 owner: str | None = None, doc: str = LEASE_DOC):
        if db is None:
            from app.core.firebase import db as _fs_db
            db = _fs_db()
        self._db = db
        self._ttl = int(ttl_seconds)
        self._owner = owner or identity()
        self._doc = doc
        self._held = False

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def held(self) -> bool:
        return self._held

    def _ref(self):
        return self._db.collection(LEASE_COLLECTION).document(self._doc)

    def acquire(self) -> LeaseState:
        """Take the lease if it is free or expired. Renews it if already ours.

        The read and the write happen in one transaction so two processes
        racing for a free lease cannot both win.
        """
        from firebase_admin import firestore

        ref = self._ref()
        result: dict[str, Any] = {}

        @firestore.transactional
        def _txn(txn) -> None:
            snap = ref.get(transaction=txn)
            state = (snap.to_dict() or {}) if getattr(snap, "exists", False) else {}
            holder = state.get("owner")
            expires = _parse(state.get("expires_at"))
            now = _now()

            mine = holder == self._owner
            free = holder is None
            stale = expires is not None and expires <= now
            # A lease with an unparseable expiry is treated as expired rather
            # than as eternal: the alternative is a corrupt field locking the
            # scheduler out of its own book with no way back.
            unreadable = holder is not None and expires is None

            if not (mine or free or stale or unreadable):
                result.update(held=False, holder=holder,
                              expires_at=state.get("expires_at"),
                              reason=f"held by {holder} until {state.get('expires_at')}")
                return

            new_expiry = (now + timedelta(seconds=self._ttl)).isoformat()
            txn.set(ref, {
                "owner": self._owner,
                "expires_at": new_expiry,
                "acquired_at": state.get("acquired_at") if mine else now.isoformat(),
                "renewed_at": now.isoformat(),
            }, merge=True)
            result.update(
                held=True, owner=self._owner, expires_at=new_expiry,
                reason=("renewed" if mine else
                        "taken (was free)" if free else
                        f"taken from {holder} (expired)" if stale else
                        f"taken from {holder} (unreadable expiry)"),
            )

        try:
            _txn(self._db.transaction())
        except Exception as e:  # noqa: BLE001
            # Cannot reach the lease doc. Refuse to run rather than assume we
            # are alone — the whole point is to not double-write, and an
            # unreachable lease is the case where we know least.
            self._held = False
            return LeaseState(held=False, reason=f"lease unreadable: {e}")

        self._held = bool(result.get("held"))
        return LeaseState(
            held=self._held, owner=result.get("owner"),
            expires_at=result.get("expires_at"), holder=result.get("holder"),
            reason=str(result.get("reason", "")),
        )

    def release(self) -> bool:
        """Give the lease up on a clean shutdown, so the next process starts now.

        Only ever clears OUR ownership. Deleting the document unconditionally
        would let a losing process evict the winner on its way out.
        """
        from firebase_admin import firestore

        ref = self._ref()

        @firestore.transactional
        def _txn(txn) -> None:
            snap = ref.get(transaction=txn)
            state = (snap.to_dict() or {}) if getattr(snap, "exists", False) else {}
            if state.get("owner") != self._owner:
                return
            txn.set(ref, {"owner": None, "expires_at": None,
                          "released_at": _now().isoformat()}, merge=True)

        try:
            _txn(self._db.transaction())
        except Exception:  # noqa: BLE001
            return False       # it will expire on its own
        finally:
            self._held = False
        return True

    def state(self) -> LeaseState:
        """Who holds it right now, without trying to take it."""
        try:
            snap = self._ref().get()
        except Exception as e:  # noqa: BLE001
            return LeaseState(held=False, reason=f"lease unreadable: {e}")
        data = (snap.to_dict() or {}) if getattr(snap, "exists", False) else {}
        holder = data.get("owner")
        expires = _parse(data.get("expires_at"))
        live = holder is not None and expires is not None and expires > _now()
        return LeaseState(
            held=live and holder == self._owner,
            owner=self._owner,
            expires_at=data.get("expires_at"),
            holder=holder if live else None,
            reason=("free" if not live else
                    "ours" if holder == self._owner else f"held by {holder}"),
        )
