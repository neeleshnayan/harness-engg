"""Reconciler — event book vs. venue truth.

Compares the event-sourced positions projection (what we think we hold) against
the connector's ``positions()`` (what the broker says). Any per-symbol quantity
divergence beyond tolerance emits a ``ReconciliationMismatch`` event so it shows
up in the audit log / cockpit and can be investigated. Run on a schedule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.fund.connectors.base import Connector
from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f
from app.fund.projections.positions import PositionsProjection

_TOL = Decimal("1e-6")


class Reconciler:
    def __init__(self, connector: Connector, store: EventStore | None = None,
                 projection: PositionsProjection | None = None):
        self._connector = connector
        self._store = store or EventStore()
        self._proj = projection or PositionsProjection(self._store)

    def run(self, actor: str = "system") -> dict[str, Any]:
        book = self._proj.build()
        venue = {p.symbol: D(p.qty) for p in self._connector.positions()}
        symbols = set(book.positions) | set(venue)

        mismatches = []
        for s in sorted(symbols):
            expected = book.positions.get(s, {}).get("qty", Decimal("0"))
            actual = venue.get(s, Decimal("0"))
            if abs(expected - actual) > _TOL:
                self._store.append(Event(
                    aggregate_id="fund", aggregate_type="fund",
                    type=EventType.RECONCILIATION_MISMATCH,
                    payload={"symbol": s, "expected": expected, "actual": actual},
                    actor=actor,
                ))
                mismatches.append({"symbol": s, "expected": f(expected), "actual": f(actual)})

        return {"checked": len(symbols), "mismatches": mismatches}
