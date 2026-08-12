"""Reconciler — event book vs. venue truth.

Compares the event-sourced positions projection (what we think we hold) against
the connector's ``positions()`` (what the broker says). Any per-symbol quantity
divergence beyond tolerance emits a ``ReconciliationMismatch`` event so it shows
up in the audit log / cockpit and can be investigated. Run on a schedule.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.fund.connectors.base import Connector
from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f
from app.fund.projections.positions import PositionsProjection

_TOL = Decimal("1e-6")


class Reconciler:
    def __init__(self, connector: Connector, store: EventStore | None = None,
                 projection: PositionsProjection | None = None,
                 nav_service: Any = None):
        self._connector = connector
        self._store = store or EventStore()
        self._proj = projection or PositionsProjection(self._store)
        self._nav = nav_service

    def drift(self) -> dict[str, Any]:
        """Read-only broker-vs-book drift SIGNAL. Writes NO events.

        NAV is folded from the event log and is the ONLY source of truth; the
        broker's equity is a *comparison*, never a replacement. (A prior change
        made NavService.compute() return live Alpaca equity AS the NAV, with a
        hardcoded units_outstanding fallback that destroyed the unit ledger — it
        was reverted in f0b18c9. This endpoint is the honest version of that idea.)

        A large delta means our book and the broker disagree: investigate before
        trading. Never silently reconcile by trusting the broker.
        """
        info = {}
        if hasattr(self._connector, "account_info"):
            try:
                info = self._connector.account_info() or {}
            except Exception as e:  # broker unreachable — say so, don't fake agreement
                return {"configured": False, "reason": f"broker error: {e}"}

        if not info.get("configured") or "equity" not in info:
            # Honest unconfigured state — NOT zeros, which would read as "in agreement".
            return {"configured": False,
                    "reason": info.get("message", "broker not configured")}

        book_nav = None
        if self._nav is not None:
            book_nav = D(self._nav.compute().total_nav_usd)

        broker_equity = D(str(info["equity"]))
        delta = (broker_equity - book_nav) if book_nav is not None else None
        delta_pct = None
        if delta is not None and book_nav and abs(book_nav) > _TOL:
            delta_pct = float(delta / book_nav) * 100.0

        book = self._proj.build()
        venue = {p.symbol: D(p.qty) for p in self._connector.positions()}
        per_symbol = []
        for s in sorted(set(book.positions) | set(venue)):
            b_qty = book.positions.get(s, {}).get("qty", Decimal("0"))
            v_qty = venue.get(s, Decimal("0"))
            per_symbol.append({
                "symbol": s,
                "book_qty": f(b_qty),
                "broker_qty": f(v_qty),
                "drift": f(v_qty - b_qty),
                "in_sync": abs(v_qty - b_qty) <= _TOL,
            })

        return {
            "configured": True,
            "book_nav": f(book_nav) if book_nav is not None else None,
            "broker_equity": f(broker_equity),
            "delta_usd": f(delta) if delta is not None else None,
            "delta_pct": round(delta_pct, 4) if delta_pct is not None else None,
            "per_symbol": per_symbol,
            "symbols_out_of_sync": sum(1 for p in per_symbol if not p["in_sync"]),
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

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
