"""Positions + cash + units projection — a fold over the event log.

This is a read model: it holds no truth of its own, it *derives* the fund's
book by replaying events. Rebuildable from scratch at any time by re-folding
``fund_events``. The reconciler (Step 2) compares this event-sourced book
against each connector's ``positions()`` / ``balances()`` (venue truth) and
emits ``ReconciliationMismatch`` on drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.fund.events import EventStore, EventType
from app.fund.money import D

_ZERO = Decimal("0")


@dataclass
class Book:
    cash: Decimal = field(default_factory=lambda: Decimal("0"))          # USD, idle
    units_outstanding: Decimal = field(default_factory=lambda: Decimal("0"))
    positions: dict[str, dict[str, Decimal]] = field(default_factory=dict)  # symbol -> {qty, avg_price}


class PositionsProjection:
    def __init__(self, store: EventStore | None = None, snapshots: Any = None,
                 snapshot_every: int = 50):
        self._store = store or EventStore()
        self._snapshots = snapshots
        # a snapshot costs a write, so only take one once enough new events
        # have accumulated to pay for it on the next read
        self._snapshot_every = snapshot_every

    def build(self) -> Book:
        """Fold the book. With a snapshot store this reads only the events since
        the last snapshot; without one it folds the whole log exactly as before.
        The event log stays authoritative — a snapshot is a cache."""
        if self._snapshots is None:
            book = Book()
            for e in self._store.stream(since_seq=0, limit=100_000):
                self._apply(book, e)
            return book

        from app.fund.snapshots import SnapshottedFold

        return SnapshottedFold(
            "positions", self._store, self._snapshots, every=self._snapshot_every
        ).fold(
            empty=Book,
            apply=self._apply,
            to_state=self._to_state,
            from_state=self._from_state,
        )

    @staticmethod
    def _to_state(book: Book) -> dict[str, Any]:
        return {
            "cash": book.cash,
            "units_outstanding": book.units_outstanding,
            "positions": book.positions,
        }

    @staticmethod
    def _from_state(state: dict[str, Any]) -> Book:
        return Book(
            cash=state.get("cash", _ZERO),
            units_outstanding=state.get("units_outstanding", _ZERO),
            positions=state.get("positions", {}) or {},
        )

    @staticmethod
    def _apply(book: Book, e: dict[str, Any]) -> None:
        etype = e.get("type")
        p = e.get("payload", {})

        if etype == EventType.ORDER_FILLED.value:
            symbol = p["symbol"]
            side = p.get("side", "buy")
            qty = D(p.get("filled_qty", p.get("qty", 0)))
            px = D(p["avg_price"])
            signed = qty if side == "buy" else -qty
            pos = book.positions.get(symbol, {"qty": _ZERO, "avg_price": px})
            new_qty = pos["qty"] + signed
            if signed > 0 and abs(new_qty) > Decimal("1e-9"):
                pos["avg_price"] = (pos["qty"] * pos["avg_price"] + signed * px) / new_qty
            pos["qty"] = new_qty
            book.positions[symbol] = pos
            book.cash -= signed * px + D(p.get("fees", 0))

        elif etype == EventType.CASH_CONFIRMED.value:
            book.cash += D(p.get("usd_amount", p.get("amount", 0)))

        elif etype == EventType.PAYOUT_SENT.value:
            book.cash -= D(p["usd_amount"])

        elif etype == EventType.UNITS_ISSUED.value:
            book.units_outstanding += D(p["units"])

        elif etype == EventType.UNITS_BURNED.value:
            book.units_outstanding -= D(p["units"])
