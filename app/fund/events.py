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

import os
import time as _time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from firebase_admin import firestore

from app.fund.chain import GENESIS_HASH, event_hash, verify
from app.fund.money import encode

#: Memo of the full log, keyed by the database it came from. Keyed rather than
#: global because projections each construct their own EventStore over the same
#: db and must share one copy, while two DIFFERENT databases (a test fake and
#: the real client, or local and production) must never see each other's log.
#: A global dict made every test inherit the previous one's events.
_STREAM_CACHE: dict[int, tuple[float, list]] = {}
#: Short enough that another writer's append surfaces quickly, long enough to
#: collapse the burst of folds a single page render causes.
_STREAM_TTL_SECONDS = 5.0

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

    # Custody events — things the BROKER does to the book that we did not order.
    # Without these the ledger can only ever explain cash and share counts that
    # our own fills produced, so a dividend or a split shows up as unexplained
    # drift against the venue and stays there forever.
    DIVIDEND_RECEIVED = "DividendReceived"       # cash paid on a held position
    INTEREST_RECEIVED = "InterestReceived"       # interest on idle cash
    CORPORATE_ACTION_APPLIED = "CorporateActionApplied"   # split / reverse split

    # Valuation & reconciliation
    #: The mandate's fee terms — auditable config, like RiskLimitsSet. An
    #: explicit zero is a recorded decision; an absence is indistinguishable
    #: from an oversight.
    FEE_TERMS_SET = "FeeTermsSet"
    FEE_ACCRUED = "FeeAccrued"                  # fees owed but not yet paid
    FEE_CRYSTALLISED = "FeeCrystallised"        # accrued fees become payable

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
    # A mistagged fill is corrected by a COMPENSATING EVENT, never by editing
    # the log. Attribution keys on the fill's strategy_id, so a fill tagged to
    # the wrong strategy leaves two ledgers permanently wrong (the log is right
    # — the index into it is not). This event moves quantity, cost basis and
    # realised P&L between two strategy ledgers, with a written reason that the
    # fold REQUIRES: a correction nobody explained is indistinguishable from a
    # correction nobody authorised.
    STRATEGY_ATTRIBUTION_CORRECTED = "StrategyAttributionCorrected"

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
    # Pre-committed exits. In the log rather than a config table for one reason:
    # a rule in a document can be edited by the person it constrains and nobody
    # would know. Here it can only be superseded, and the supersession is visible.
    # The OVERRIDDEN event matters as much as the other two — an exit that can be
    # ignored without a trace is not an exit, it is a story about why this time
    # is different.
    # research desk — the operator asking the firm's bench for work. Recorded as
    # events so a clicked request is a durable fact, never a forgotten toast.
    DESK_REQUESTED = "DeskRequested"
    DESK_DISPATCHED = "DeskDispatched"
    DESK_REQUEST_RESOLVED = "DeskRequestResolved"
    DESK_RECOMMENDATION_DECIDED = "DeskRecommendationDecided"
    # The CEO endorsing a queued request for dispatch — the middle hop of the
    # seat-asks chain (seat files -> CEO approves -> CTO triggers). Governance,
    # therefore an event (2026-08-20 amendment: seat-filed asks, human keys).
    DESK_REQUEST_APPROVED = "DeskRequestApproved"

    # approval-channel guard v1 (2026-08-20): a refused approval is a FINDING —
    # a probe, a stray script, or a mistaken click — and findings are events.
    APPROVAL_REFUSED = "ApprovalRefused"

    EXIT_RULE_SET = "ExitRuleSet"               # committed before the position exists
    EXIT_RULE_TRIGGERED = "ExitRuleTriggered"   # fired; a closing proposal was raised
    EXIT_RULE_OVERRIDDEN = "ExitRuleOverridden" # fired and kept anyway, with a reason

    RISK_LIMITS_SET = "RiskLimitsSet"           # the mandate's limits (auditable config)
    RISK_ALARM_RAISED = "RiskAlarmRaised"       # a limit/adverse-move breach opened
    RISK_ALARM_CLEARED = "RiskAlarmCleared"     # a breach resolved
    TRADING_HALTED = "TradingHalted"            # kill switch engaged (drawdown/loss/manual)
    TRADING_RESUMED = "TradingResumed"          # trading re-enabled by a human or, for a
                                                # LOSS halt only, by the auto-resume policy

    # Halt acknowledgement (2026-08-21, CEO-approved): the CEO states, in the
    # log, that they have SEEN a specific halt. Distinct from resuming and
    # distinct from rebasing the loss reference — an acknowledgement changes no
    # number and re-arms nothing by itself; it is condition (1) of four for the
    # loss-halt auto-resume policy. Recorded against the halt it names, so an
    # acknowledgement cannot outlive the halt it was given for.
    HALT_ACKNOWLEDGED = "HaltAcknowledged"

    # Acknowledge-and-rebase (2026-08-20, CEO-blessed): the daily-loss reference
    # moved deliberately to current NAV, with a written reason. A circuit
    # breaker you can only reopen by waiting for midnight is a circuit breaker
    # that gets bypassed; one you can reopen by SAYING SO in the log is a
    # decision. Refused while an integrity halt is open — you cannot accept a
    # loss you cannot measure.
    LOSS_REFERENCE_REBASED = "LossReferenceRebased"

    # Rebalance — a BATCH of orders decided as one thing. Event-sourced
    # separately from the individual orders because the unit of human judgement
    # is the plan, not the twelve fills it becomes: approving nine buys one at a
    # time is not the same decision as approving the shape of the book.
    REBALANCE_PROPOSED = "RebalanceProposed"
    REBALANCE_APPROVED = "RebalanceApproved"
    REBALANCE_DECLINED = "RebalanceDeclined"


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


def store_backend() -> str:
    """Which store the fund is running on: ``postgres`` or ``firestore``."""
    return (os.getenv("FUND_STORE", "firestore") or "firestore").strip().lower()


class EventStore:
    """Append-only writer/reader over ``fund_events``.

    Firestore by default; ``FUND_STORE=postgres`` returns a PostgresEventStore
    instead.

    The switch lives in ``__new__`` rather than in a factory function called by
    every caller, and that is a deliberate trade. ``EventStore()`` is
    constructed in twenty-six places across twenty-two modules — including two
    owned by another engineer — and a rename would have put a mechanical diff
    through all of them to express one configuration decision. Returning a
    different object from ``__new__`` keeps every call site honest and
    unchanged; Python skips ``__init__`` when ``__new__`` returns something
    that is not an instance of the class, which is exactly what should happen
    here since the Postgres store has already initialised itself.
    """

    def __new__(cls, db=None):
        if db is None and store_backend() == "postgres":
            from app.fund.pgstore import PostgresEventStore
            return PostgresEventStore()
        return super().__new__(cls)

    def __init__(self, db=None):
        from app.core.firebase import db as _fs_db
        self._db = db or _fs_db()

    def append(self, event: Event) -> Event:
        """Assign a global seq + server timestamp and persist. Returns the stored event.

        The chain tip advances inside the same transaction as the seq counter.
        That pairing is the point: seq ordering and hash linkage are two views
        of the same ordering, and letting them be assigned by separate writes
        would allow an event to hold seq N while chaining onto seq N-2.

        The tip is stored on the counter document rather than derived by
        reading the previous event, which keeps append at zero extra reads.
        """
        counter_ref = self._db.collection(_COUNTER_DOC[0]).document(_COUNTER_DOC[1])

        # Set before the transaction so the hash covers the real timestamp.
        event.ts = datetime.now(timezone.utc).isoformat()
        sealed: dict[str, Any] = {}

        @firestore.transactional
        def _txn(txn) -> int:
            state = {}
            snap = counter_ref.get(transaction=txn)
            if snap.exists:
                state = snap.to_dict() or {}
            nxt = state.get("seq", 0) + 1
            prev = state.get("tip_hash") or GENESIS_HASH

            body = encode(event.to_dict())
            body["seq"] = nxt
            body["prev_hash"] = prev
            body["hash"] = event_hash(body, prev)

            txn.set(counter_ref, {"seq": nxt, "tip_hash": body["hash"]}, merge=True)
            sealed.update(body)
            return nxt

        event.seq = _txn(self._db.transaction())

        # If this write fails after the transaction committed, the tip points at
        # an event that does not exist and the next append chains onto a
        # phantom. That is a real hole — and verify() reports it as a break
        # rather than papering over it, which is the behaviour we want: a
        # missing event should be loud.
        self._db.collection(EVENTS_COLLECTION).document(event.event_id).set(sealed)
        # The writer must always see its own write: a fill hidden behind the
        # cache would let the idempotency check pass twice and double the
        # position. Appended in place rather than clearing, because clearing
        # would force a full re-read of the log on the very next fold — the
        # cost this cache exists to avoid, paid on every single write.
        # Keyed on presence, not truthiness: a cache that has been populated
        # and happens to be EMPTY is not the same as one never populated, and
        # treating them alike let a first append vanish behind a fresh empty
        # entry until the TTL expired.
        key = id(self._db)
        if key in _STREAM_CACHE:
            checked_at, rows = _STREAM_CACHE[key]
            _STREAM_CACHE[key] = (checked_at, rows + [sealed])
        return event

    def verify_chain(self, limit: int = 100_000) -> dict[str, Any]:
        """Walk the log and report the first link that does not hold."""
        return verify(self.stream(limit=limit)).to_dict()

    def by_aggregate(self, aggregate_id: str) -> list[dict[str, Any]]:
        """All events for one aggregate, in order.

        Served from the same memo as stream(). This one is on the trade path —
        _emit_fill asks "has this order already filled?" on every settlement
        poll for every in-flight order — so an uncached query here is a
        Firestore round trip per order per tick.

        The cache is cleared by append(), so a fill recorded a moment ago is
        always visible to the idempotency check that must see it.
        """
        rows = self.stream(limit=1_000_000)
        return [e for e in rows if e.get("aggregate_id") == str(aggregate_id)]

    def stream(self, since_seq: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        """The global log from ``since_seq`` (exclusive), oldest first — the audit trail.

        Memoised for a few seconds, and that is not an optimisation so much as
        the thing that makes running on Firestore viable at all.

        Every projection in the system folds by calling this. A single page
        render asks for NAV, risk, orders, compliance, TCA and the chain, and
        each of those re-reads the whole log — so one refresh of the cockpit
        costs several hundred document reads, and a browser tab polling every
        thirty seconds burns the entire 50,000/day free tier in about an hour.
        That is what exhausted the quota twice; the read amplification was
        invisible while the ledger was a local JSON file, where re-folding was
        free.

        Caching the log rather than each endpoint's response means every
        projection benefits at once and none of them had to change. Appends
        from this process invalidate immediately, so a fill is never hidden
        behind the cache from the writer's point of view; another process's
        append is visible within the TTL, which is why the scheduler holds a
        single-writer lease.
        """
        now = _time.time()
        key = id(self._db)
        checked_at, rows = _STREAM_CACHE.get(key, (0.0, []))

        if now - checked_at >= _STREAM_TTL_SECONDS:
            # Incremental, because the log is append-only. Re-reading all of it
            # every few seconds is what the free tier cannot afford: at 52
            # events and a 5s refresh that is 37k document reads an hour, which
            # blows the 50k/day allowance before lunch. Asking only for events
            # after the highest one we hold costs a single read when nothing
            # has happened, which is almost always.
            #
            # This is only sound because events are immutable and seq is
            # monotonic — an existing event can never change under us, so there
            # is nothing to re-read. If that ever stops being true, this cache
            # stops being correct.
            top = rows[-1].get("seq", 0) if rows else 0
            fresh = [
                d.to_dict() for d in (
                    self._db.collection(EVENTS_COLLECTION)
                    .where("seq", ">", top)
                    .order_by("seq")
                    .stream()
                )
            ]
            if fresh:
                rows = rows + fresh
            _STREAM_CACHE[key] = (now, rows)

        out = [e for e in rows if (e.get("seq") or 0) > since_seq]
        return out[:limit]

    @staticmethod
    def invalidate_cache() -> None:
        _STREAM_CACHE.clear()
