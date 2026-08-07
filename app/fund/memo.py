"""Investment memo — the written case for a trade, drafted against a thesis.

This is the "AI researches → human decides" artifact. Clark drafts a memo
(recommendation + conviction + reasoned sections); the human reads it at the
approval card and signs off. Event-sourced like the thesis, so every revision
is auditable and the final signed memo is a fact in the log.

A memo always references a ``thesis_id`` — the thesis is the falsifiable idea,
the memo is the argued case for acting on it now. The ThesisRegistry folds
MemoCreated events back onto the thesis (``memo_ids``) so the two stay linked
without a second write.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from app.fund.events import Event, EventStore, EventType


class MemoStatus(str, Enum):
    DRAFT = "draft"      # Clark drafted it; awaiting human sign-off
    FINAL = "final"      # human accepted it as the record of decision


# Mutable memo fields carried on create/update events. ``sections`` is an
# ordered dict of {heading: markdown} so the memo renders as a real document.
_FIELDS = (
    "thesis_id", "title", "recommendation", "conviction", "summary",
    "sections", "author", "sources",
)


class MemoError(Exception):
    """Invalid memo operation (missing thesis_id/title, unknown id)."""


class MemoService:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def create(self, body: dict, actor: str) -> dict[str, Any]:
        if not (body or {}).get("thesis_id"):
            raise MemoError("a memo must reference a thesis_id")
        if not body.get("title"):
            raise MemoError("memo needs a title")
        mid = str(uuid.uuid4())
        payload = {k: body.get(k) for k in _FIELDS}
        payload["author"] = payload.get("author") or actor
        self._store.append(Event(mid, "memo", EventType.MEMO_CREATED, payload, actor))
        return self.get(mid)

    def update(self, memo_id: str, patch: dict, actor: str) -> dict[str, Any]:
        self._require(memo_id)
        payload = {k: patch[k] for k in _FIELDS if k in patch}
        if not payload:
            raise MemoError("no updatable fields supplied")
        self._store.append(Event(memo_id, "memo", EventType.MEMO_UPDATED, payload, actor))
        return self.get(memo_id)

    def finalize(self, memo_id: str, actor: str) -> dict[str, Any]:
        """Human signs off — the memo becomes the record of decision."""
        self._require(memo_id)
        self._store.append(
            Event(memo_id, "memo", EventType.MEMO_UPDATED, {"status": MemoStatus.FINAL.value}, actor)
        )
        return self.get(memo_id)

    def get(self, memo_id: str) -> dict[str, Any]:
        rec = MemoRegistry(self._store).get(memo_id)
        if rec is None:
            raise MemoError(f"unknown memo {memo_id}")
        return rec

    def list(self, thesis_id: Optional[str] = None) -> list[dict[str, Any]]:
        rows = MemoRegistry(self._store).list()
        if thesis_id:
            rows = [m for m in rows if m.get("thesis_id") == thesis_id]
        return rows

    def _require(self, memo_id: str) -> dict[str, Any]:
        rec = MemoRegistry(self._store).get(memo_id)
        if rec is None:
            raise MemoError(f"unknown memo {memo_id}")
        return rec


class MemoRegistry:
    """Projection: current state of every memo, folded from memo events."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _build(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            etype = e.get("type")
            aid = e.get("aggregate_id")
            p = e.get("payload", {}) or {}
            if etype == EventType.MEMO_CREATED.value:
                rec = {"memo_id": aid, "status": MemoStatus.DRAFT.value}
                rec.update({k: p.get(k) for k in _FIELDS})
                out[aid] = rec
            elif etype == EventType.MEMO_UPDATED.value and aid in out:
                if "status" in p and p["status"] is not None:
                    out[aid]["status"] = p["status"]
                out[aid].update({k: v for k, v in p.items() if k in _FIELDS and v is not None})
        return out

    def get(self, memo_id: str) -> Optional[dict[str, Any]]:
        return self._build().get(memo_id)

    def list(self) -> list[dict[str, Any]]:
        return list(self._build().values())
