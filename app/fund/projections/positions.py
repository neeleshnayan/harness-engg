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
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def build(self) -> Book:
        book = Book()
        for e in self._store.stream(since_seq=0, limit=100_000):
            self._apply(book, e)
        return book

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
