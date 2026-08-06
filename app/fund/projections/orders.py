"""Orders projection — the approval queue and per-order status.

Folds order events into each order's latest state. ``pending()`` returns the
orders awaiting a human decision (latest event is ``OrderProposed``) with their
impact preview — the cockpit's approval queue, and where LEAN signals land.
"""

from __future__ import annotations

from typing import Any

from app.fund.events import EventStore, EventType


class OrdersProjection:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _fold(self) -> dict[str, dict[str, Any]]:
        orders: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            if e.get("aggregate_type") != "order":
                continue
            oid = e["aggregate_id"]
            rec = orders.setdefault(oid, {"order_id": oid, "proposed": None, "last": None, "ts": None})
            if e["type"] == EventType.ORDER_PROPOSED.value:
                rec["proposed"] = e["payload"]
            rec["last"] = e["type"]
            rec["ts"] = e.get("ts")
        return orders

    def pending(self) -> list[dict[str, Any]]:
        out = []
        for rec in self._fold().values():
            if rec["last"] != EventType.ORDER_PROPOSED.value or rec["proposed"] is None:
                continue
            p = rec["proposed"]
            out.append({
                "order_id": rec["order_id"],
                "symbol": p.get("symbol"),
                "side": p.get("side"),
                "qty": p.get("qty"),
                "strategy_id": p.get("strategy_id"),
                "impact_preview": p.get("impact_preview"),
                "ts": rec["ts"],
            })
        return sorted(out, key=lambda r: r["ts"] or "")
