"""Thesis — the versioned investment idea a trade references (or is discretionary).

Event-sourced like strategies: a thesis is folded from ThesisCreated /
ThesisUpdated / ThesisStatusChanged events, so every field change and status
transition is auditable. Clark can *draft* a thesis; the human owns it and the
trade decision. The "a trade references a thesis or is discretionary" rule is
what makes post-mortems meaningful — see docs/architecture.md.
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Optional

from app.fund.events import Event, EventStore, EventType


class ThesisStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INVALIDATED = "invalidated"
    EXITED = "exited"
    REVIEWED = "reviewed"


# Allowed status transitions (auditable lifecycle).
_ALLOWED: dict[ThesisStatus, set[ThesisStatus]] = {
    # REVIEWED is reachable from any live state — a post-mortem can close a
    # thesis you never acted on as readily as one you traded.
    ThesisStatus.DRAFT: {ThesisStatus.ACTIVE, ThesisStatus.INVALIDATED, ThesisStatus.REVIEWED},
    ThesisStatus.ACTIVE: {ThesisStatus.INVALIDATED, ThesisStatus.EXITED, ThesisStatus.REVIEWED},
    ThesisStatus.INVALIDATED: {ThesisStatus.REVIEWED, ThesisStatus.EXITED},
    ThesisStatus.EXITED: {ThesisStatus.REVIEWED},
    ThesisStatus.REVIEWED: set(),
}

# Mutable thesis fields carried on create/update events.
_FIELDS = (
    "title", "assets", "strategy_id", "owner", "claim", "horizon",
    "entry_rationale", "key_risks", "invalidation_conditions",
    "target_exposure_pct", "review_cadence", "evidence_ids", "memo_ids",
    # Research belongs with the investment idea it supports.  Keeping this on
    # the thesis lets the recommendation endpoint prove which backtest it used
    # instead of accepting an untraceable client-side number.
    "direction", "backtest",
)


class ThesisError(Exception):
    """Invalid thesis operation (unknown id, bad transition, missing title)."""


class ThesisService:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def create(self, body: dict, actor: str) -> dict[str, Any]:
        if not (body or {}).get("title"):
            raise ThesisError("thesis needs a title")
        tid = str(uuid.uuid4())
        payload = {k: body.get(k) for k in _FIELDS}
        self._store.append(Event(tid, "thesis", EventType.THESIS_CREATED, payload, actor))
        return self.get(tid)

    def update(self, thesis_id: str, patch: dict, actor: str) -> dict[str, Any]:
        self._require(thesis_id)
        payload = {k: patch[k] for k in _FIELDS if k in patch}
        if not payload:
            raise ThesisError("no updatable fields supplied")
        self._store.append(Event(thesis_id, "thesis", EventType.THESIS_UPDATED, payload, actor))
        return self.get(thesis_id)

    def set_status(self, thesis_id: str, status: str, actor: str, note: Optional[str] = None) -> dict[str, Any]:
        cur = ThesisStatus(self._require(thesis_id)["status"])
        target = ThesisStatus(status)
        if target != cur and target not in _ALLOWED[cur]:
            raise ThesisError(f"cannot move thesis from '{cur.value}' to '{target.value}'")
        self._store.append(
            Event(thesis_id, "thesis", EventType.THESIS_STATUS_CHANGED,
                  {"status": target.value, "note": note}, actor)
        )
        return self.get(thesis_id)

    def archive(self, thesis_id: str, actor: str) -> dict[str, Any]:
        """Hide an unused thesis without erasing its audit history.

        An order can refer to a thesis for years, so deleting its events would
        make the order and its post-mortem unverifiable.  Archive is the safe
        user-facing delete: it disappears from the Studio list but remains
        available to audit reads.  A thesis with an order is deliberately not
        archivable because it still provides that order's stated rationale.
        """
        thesis = self._require(thesis_id)
        if thesis.get("order_ids"):
            raise ThesisError("cannot delete a thesis with linked orders; retain it for the trade audit")
        if thesis.get("archived"):
            return thesis
        self._store.append(Event(thesis_id, "thesis", EventType.THESIS_ARCHIVED, {}, actor))
        return self.get(thesis_id)

    def get(self, thesis_id: str) -> dict[str, Any]:
        rec = ThesisRegistry(self._store).get(thesis_id)
        if rec is None:
            raise ThesisError(f"unknown thesis {thesis_id}")
        return rec

    def list(self) -> list[dict[str, Any]]:
        return ThesisRegistry(self._store).list()

    def _require(self, thesis_id: str) -> dict[str, Any]:
        rec = ThesisRegistry(self._store).get(thesis_id)
        if rec is None:
            raise ThesisError(f"unknown thesis {thesis_id}")
        return rec


class ThesisRegistry:
    """Projection: current state of every thesis, folded from thesis + order events."""

    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _build(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            etype = e.get("type")
            aid = e.get("aggregate_id")
            p = e.get("payload", {}) or {}
            if etype == EventType.THESIS_CREATED.value:
                rec = {"thesis_id": aid, "status": ThesisStatus.DRAFT.value,
                       "order_ids": [], "memo_ids": [], "has_postmortem": False,
                       "archived": False, "created_at": e.get("ts")}
                rec.update({k: p.get(k) for k in _FIELDS})
                rec["memo_ids"] = rec.get("memo_ids") or []
                out[aid] = rec
            elif etype == EventType.THESIS_UPDATED.value and aid in out:
                out[aid].update({k: v for k, v in p.items() if v is not None})
            elif etype == EventType.THESIS_STATUS_CHANGED.value and aid in out:
                out[aid]["status"] = p["status"]
            elif etype == EventType.THESIS_ARCHIVED.value and aid in out:
                out[aid]["archived"] = True
            elif etype == EventType.ORDER_PROPOSED.value:
                tid = p.get("thesis_id")
                if tid in out:
                    out[tid]["order_ids"].append(aid)
            elif etype == EventType.MEMO_CREATED.value:
                tid = p.get("thesis_id")
                if tid in out and aid not in out[tid]["memo_ids"]:
                    out[tid]["memo_ids"].append(aid)
            elif etype == EventType.POSTMORTEM_RECORDED.value:
                tid = p.get("thesis_id")
                if tid in out:
                    out[tid]["has_postmortem"] = True
        return out

    def get(self, thesis_id: str) -> Optional[dict[str, Any]]:
        return self._build().get(thesis_id)

    def list(self) -> list[dict[str, Any]]:
        return [t for t in self._build().values() if not t.get("archived")]
