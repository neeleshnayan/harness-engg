"""Projection snapshots — make reads O(new events) instead of O(all history).

Every projection folded the entire event log on every request, so a NAV read
cost one Firestore read per event ever written. That grows without bound and it
exhausted the read quota (429 ResourceExhausted) under normal polling.

A snapshot stores the folded state plus the sequence number it covers. A read
loads the snapshot and folds only what has happened since:

    build() = snapshot(seq N) + events where seq > N

Correctness rule: a snapshot is a cache, never a source of truth. The event log
remains authoritative — deleting every snapshot must change nothing but latency,
and there is a test that pins exactly that.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

_SNAPSHOT_COLLECTION = "fund_snapshots"


def _encode(value: Any) -> Any:
    """Decimals are exact money; store them as strings, never floats."""
    if isinstance(value, Decimal):
        return {"__dec__": str(value)}
    if isinstance(value, dict):
        return {k: _encode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    return value


def _decode(value: Any) -> Any:
    if isinstance(value, dict):
        if "__dec__" in value and len(value) == 1:
            return Decimal(value["__dec__"])
        return {k: _decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_decode(v) for v in value]
    return value


class SnapshotStore:
    """Persists folded projection state, keyed by projection name."""

    def __init__(self, db=None):
        self._db = db
        if self._db is None:
            from firebase_admin import firestore
            self._db = firestore.client()

    def load(self, name: str) -> tuple[int, dict[str, Any]] | None:
        """Returns (covered_seq, state) or None when there is no snapshot."""
        try:
            doc = self._db.collection(_SNAPSHOT_COLLECTION).document(name).get()
            if not getattr(doc, "exists", False):
                return None
            data = doc.to_dict() or {}
            seq = int(data.get("seq", 0))
            state = _decode(data.get("state", {}))
            if seq <= 0 or not isinstance(state, dict):
                return None
            return seq, state
        except Exception:
            # A snapshot is only a cache — if it cannot be read, fall back to a
            # full fold rather than failing the request.
            return None

    def save(self, name: str, seq: int, state: dict[str, Any]) -> bool:
        try:
            self._db.collection(_SNAPSHOT_COLLECTION).document(name).set(
                {"seq": int(seq), "state": _encode(state)}
            )
            return True
        except Exception:
            return False


class SnapshottedFold:
    """Folds a projection from its latest snapshot plus the events since.

    ``every`` controls how often a fresh snapshot is written — a snapshot costs
    one write, so it is only worth taking after enough new events to have paid
    for itself on the next read.
    """

    def __init__(self, name: str, store, snapshots: SnapshotStore | None = None,
                 every: int = 50):
        self._name = name
        self._store = store
        self._snapshots = snapshots
        self._every = every

    def fold(
        self,
        empty: Callable[[], Any],
        apply: Callable[[Any, dict[str, Any]], None],
        to_state: Callable[[Any], dict[str, Any]],
        from_state: Callable[[dict[str, Any]], Any],
    ) -> Any:
        since = 0
        acc = None

        if self._snapshots is not None:
            snap = self._snapshots.load(self._name)
            if snap is not None:
                since, state = snap
                try:
                    acc = from_state(state)
                except Exception:
                    acc, since = None, 0   # unreadable snapshot -> full rebuild

        if acc is None:
            acc = empty()

        last_seq = since
        applied = 0
        for e in self._store.stream(since_seq=since, limit=100_000):
            apply(acc, e)
            last_seq = max(last_seq, int(e.get("seq", last_seq)))
            applied += 1

        if self._snapshots is not None and applied >= self._every and last_seq > since:
            self._snapshots.save(self._name, last_seq, to_state(acc))

        return acc
