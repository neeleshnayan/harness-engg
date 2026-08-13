"""Append-only event store — the fund's single source of truth.

Everything the harness knows about the fund is derived by folding these events.
Audit, reconciliation, NAV, positions and the unit ledger are all projections
over this log (see ``app/fund/projections``). Events are immutable: state is
never mutated in place, only appended.

Storage: Firestore collection ``fund_events``. A global monotonic ``seq`` is
assigned via an atomic counter so the log has a total order that is cheap to
page through. Per-aggregate ordering is recovered by filtering on
``aggregate_id`` and sorting by ``seq``.

At Friends & Family scale this is more than enough; if throughput ever
outgrows Firestore the same ``EventStore`` interface can front a real event
store or a Temporal-backed pipeline without touching callers.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from firebase_admin import firestore

from app.fund.money import encode

EVENTS_COLLECTION = "fund_events"
_COUNTER_DOC = ("fund_meta", "event_counter")


class EventType(str, Enum):
    """The phase-1 event catalog (see docs/architecture.md §4 in ClarkHarness)."""

    # Order lifecycle
    ORDER_PROPOSED = "OrderProposed"
    ORDER_REJECTED = "OrderRejected"            # failed the risk gate (terminal)
    ORDER_APPROVED = "OrderApproved"
    ORDER_DECLINED = "OrderDeclined"            # human rejected (terminal)
    ORDER_SUBMITTED = "OrderSubmitted"          # connector accepted it
    ORDER_PARTIALLY_FILLED = "OrderPartiallyFilled"
    ORDER_FILLED = "OrderFilled"                # terminal
    ORDER_FAILED = "OrderFailed"                # terminal

    # Subscription / redemption (unit ledger — Step 3)
    SUBSCRIPTION_REQUESTED = "SubscriptionRequested"
    CASH_CONFIRMED = "CashConfirmed"
    UNITS_ISSUED = "UnitsIssued"
    REDEMPTION_REQUESTED = "RedemptionRequested"
    UNITS_BURNED = "UnitsBurned"
    PAYOUT_SENT = "PayoutSent"

    # Valuation & reconciliation
    NAV_STRUCK = "NavStruck"
    RECONCILIATION_MISMATCH = "ReconciliationMismatch"

    # Strategy lifecycle (event-sourced so allocations/deploys are auditable)
    STRATEGY_REGISTERED = "StrategyRegistered"
    STRATEGY_BACKTESTED = "StrategyBacktested"
    STRATEGY_STATE_CHANGED = "StrategyStateChanged"
    STRATEGY_ALLOCATION_SET = "StrategyAllocationSet"
    STRATEGY_RENAMED = "StrategyRenamed"
    STRATEGY_ARCHIVED = "StrategyArchived"
    STRATEGY_ASSETS_SET = "StrategyAssetsSet"   # the universe of symbols a strategy scopes
    # Many-to-many composition (a strategy can compose into multiple parents).
    STRATEGY_ADDED_TO_PARENT = "StrategyAddedToParent"
    STRATEGY_REMOVED_FROM_PARENT = "StrategyRemovedFromParent"
    STRATEGY_MEMBERSHIP_WEIGHTED = "StrategyMembershipWeighted"

    # Thesis lifecycle — the versioned investment idea a trade must reference
    # (or be marked discretionary). Makes post-mortems meaningful.
    THESIS_CREATED = "ThesisCreated"
    THESIS_UPDATED = "ThesisUpdated"
    THESIS_STATUS_CHANGED = "ThesisStatusChanged"

    # Investment memo — the written case Clark drafts against a thesis and a
    # human signs off on. Rendered at the approval card. Auditable like the rest.
    MEMO_CREATED = "MemoCreated"
    MEMO_UPDATED = "MemoUpdated"

    # Post-mortem — the closing entry that diffs a thesis's prediction against
    # what actually happened. Closes the loop and builds the reasoning dataset.
    POSTMORTEM_RECORDED = "PostmortemRecorded"

    # Risk monitoring & controls — continuous surveillance + the kill switch.
    # Alarms are events so the audit trail shows exactly what tripped and when.
    RISK_LIMITS_SET = "RiskLimitsSet"           # the mandate's limits (auditable config)
    RISK_ALARM_RAISED = "RiskAlarmRaised"       # a limit/adverse-move breach opened
    RISK_ALARM_CLEARED = "RiskAlarmCleared"     # a breach resolved
    TRADING_HALTED = "TradingHalted"            # kill switch engaged (drawdown/loss/manual)
    TRADING_RESUMED = "TradingResumed"          # trading re-enabled by a human


@dataclass
class Event:
    """An immutable fact. ``seq`` is assigned by the store on append."""

    aggregate_id: str                 # e.g. order id, lp id, or "fund"
    aggregate_type: str               # "order" | "lp" | "fund"
    type: EventType
    payload: dict[str, Any]
    actor: str                        # who/what caused it: user id, "agent", "system"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    seq: Optional[int] = None
    ts: Optional[str] = None          # ISO-8601 UTC, set on append

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = self.type.value
        return d


class EventStore:
    """Append-only writer/reader over ``fund_events``."""

    def __init__(self, db=None):
        from app.core.firebase import db as _fs_db
        self._db = db or _fs_db()

    def append(self, event: Event) -> Event:
        """Assign a global seq + server timestamp and persist. Returns the stored event."""

        counter_ref = self._db.collection(_COUNTER_DOC[0]).document(_COUNTER_DOC[1])

        @firestore.transactional
        def _txn(txn) -> int:
            snap = counter_ref.get(transaction=txn)
            current = (snap.to_dict() or {}).get("seq", 0) if snap.exists else 0
            nxt = current + 1
            txn.set(counter_ref, {"seq": nxt}, merge=True)
            return nxt

        event.seq = _txn(self._db.transaction())
        event.ts = datetime.now(timezone.utc).isoformat()

        self._db.collection(EVENTS_COLLECTION).document(event.event_id).set(encode(event.to_dict()))
        return event

    def by_aggregate(self, aggregate_id: str) -> list[dict[str, Any]]:
        """All events for one aggregate, in order."""
        q = (
            self._db.collection(EVENTS_COLLECTION)
            .where("aggregate_id", "==", aggregate_id)
            .order_by("seq")
        )
        return [d.to_dict() for d in q.stream()]

    def stream(self, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        """The global log from ``since_seq`` (exclusive), oldest first — the audit trail."""
        q = (
            self._db.collection(EVENTS_COLLECTION)
            .where("seq", ">", since_seq)
            .order_by("seq")
            .limit(limit)
        )
        return [d.to_dict() for d in q.stream()]
