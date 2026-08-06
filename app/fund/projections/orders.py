"""Orders projection — approval queue, in-flight set, and per-order status.

Folds order events into each order's latest state:
  * ``pending()``   — awaiting a human decision (latest is ``OrderProposed``).
  * ``in_flight()`` — submitted to the venue but not yet terminal (latest is
    ``OrderSubmitted`` or ``OrderPartiallyFilled``); the settlement poller chases
    these to a terminal ``OrderFilled`` / ``OrderFailed``.
"""

from __future__ import annotations

from typing import Any

from app.fund.events import EventStore, EventType

_INFLIGHT = {EventType.ORDER_SUBMITTED.value, EventType.ORDER_PARTIALLY_FILLED.value}


class OrdersProjection:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _fold(self) -> dict[str, dict[str, Any]]:
        orders: dict[str, dict[str, Any]] = {}
        for e in self._store.stream(since_seq=0, limit=100_000):
            if e.get("aggregate_type") != "order":
                continue
            oid = e["aggregate_id"]
            rec = orders.setdefault(oid, {
                "order_id": oid, "proposed": None, "venue": None, "venue_ref": None,
                "last": None, "last_filled_qty": 0.0, "ts": None,
            })
            t = e["type"]
            p = e["payload"]
            if t == EventType.ORDER_PROPOSED.value:
                rec["proposed"] = p
            elif t == EventType.ORDER_SUBMITTED.value:
                rec["venue"] = p.get("venue")
                rec["venue_ref"] = p.get("venue_ref")
            elif t == EventType.ORDER_PARTIALLY_FILLED.value:
                rec["last_filled_qty"] = float(p.get("cumulative_qty", 0))
            rec["last"] = t
            rec["ts"] = e.get("ts")
        return orders

    def pending(self) -> list[dict[str, Any]]:
        out = []
        for rec in self._fold().values():
            if rec["last"] != EventType.ORDER_PROPOSED.value or rec["proposed"] is None:
                continue
            p = rec["proposed"]
            out.append({
                "order_id": rec["order_id"], "symbol": p.get("symbol"), "side": p.get("side"),
                "qty": p.get("qty"), "strategy_id": p.get("strategy_id"),
                "impact_preview": p.get("impact_preview"), "ts": rec["ts"],
            })
        return sorted(out, key=lambda r: r["ts"] or "")

    def in_flight(self) -> list[dict[str, Any]]:
        out = []
        for rec in self._fold().values():
            if rec["last"] not in _INFLIGHT:
                continue
            out.append({
                "order_id": rec["order_id"],
                "venue": rec["venue"],
                "venue_ref": rec["venue_ref"],
                "proposed": rec["proposed"] or {},
                "last_filled_qty": rec["last_filled_qty"],
            })
        return out
