"""Venue-agnostic execution interface.

Every venue (paper today; IBKR in Step 2; Uniswap in Phase 2) implements this
one ``Connector`` protocol. The command pipeline and the agent speak only to
this interface — never to a venue SDK directly — so adding a venue is a new
connector with zero upstream change.

``execute()`` is deliberately *not* request/response: real fills settle
asynchronously and can fail after submit. ``execute()`` returns a ``VenueRef``
immediately; a poller/webhook later calls ``poll()`` and the resulting status
is what gets turned into ``OrderFilled`` / ``OrderFailed`` events. This is why
the whole system is event-driven rather than synchronous CRUD.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Protocol, runtime_checkable


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class FillState(str, Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    FAILED = "failed"


@dataclass
class Order:
    venue: str
    symbol: str
    side: Side
    qty: float
    # None => market order. Limit price otherwise.
    limit_price: Optional[float] = None
    # Which strategy generated this order (None => discretionary). One pooled
    # account; strategies are tags for attribution, not separate accounts.
    strategy_id: Optional[str] = None
    # The investment thesis this order acts on (None => discretionary trade).
    thesis_id: Optional[str] = None
    # WHY this order exists, in the proposer's own words, and what a sceptic
    # said about it. Both ride on the order because the approval card is where
    # they are read, and reasoning that lives anywhere else is reasoning the
    # human never sees at the moment they decide.
    rationale: Optional[str] = None
    critique: Optional[str] = None


@dataclass
class Quote:
    symbol: str
    price: float
    est_slippage_bps: float = 0.0
    est_fees: float = 0.0


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class VenueRef:
    """Opaque handle to a submitted order at a venue. Maps 1:1 to an idempotency key."""

    venue: str
    ref_id: str


@dataclass
class ExecStatus:
    state: FillState
    filled_qty: float = 0.0
    avg_price: Optional[float] = None
    fees: float = 0.0
    reason: Optional[str] = None          # populated when state == FAILED


@dataclass
class Position:
    venue: str
    symbol: str
    qty: float
    avg_price: float


@dataclass
class Balance:
    venue: str
    asset: str            # e.g. "USD", "USDC"
    amount: float


@runtime_checkable
class Connector(Protocol):
    """One venue. Implementations: PaperConnector (now), IBKRConnector (Step 2)."""

    name: str

    def quote(self, order: Order) -> Quote: ...

    def validate(self, order: Order) -> ValidationResult: ...

    # Returns immediately with a handle; settlement is observed via poll().
    def execute(self, order: Order, idempotency_key: str) -> VenueRef: ...

    def poll(self, ref: VenueRef) -> ExecStatus: ...

    # Venue truth, used by the reconciler to catch drift from the event log.
    def positions(self) -> list[Position]: ...

    def balances(self) -> list[Balance]: ...
