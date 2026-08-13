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
    def __init__(self, store: EventStore | None = None, snapshots: Any = None,
                 snapshot_every: int = 50):
        self._store = store or EventStore()
        self._snapshots = snapshots
        self._snapshot_every = snapshot_every

    def _fold(self) -> dict[str, dict[str, Any]]:
        """Snapshotted when a snapshot store is supplied; the event log stays
        authoritative either way."""
        if self._snapshots is None:
            orders: dict[str, dict[str, Any]] = {}
            for e in self._store.stream(since_seq=0, limit=100_000):
                self._apply(orders, e)
            return orders

        from app.fund.snapshots import SnapshottedFold

        return SnapshottedFold(
            "orders", self._store, self._snapshots, every=self._snapshot_every
        ).fold(
            empty=dict,
            apply=self._apply,
            to_state=lambda o: o,
            from_state=lambda s: dict(s or {}),
        )

    @staticmethod
    def _apply(orders: dict[str, dict[str, Any]], e: dict[str, Any]) -> None:
        if e.get("aggregate_type") != "order":
            return
        oid = e["aggregate_id"]
        rec = orders.setdefault(oid, {
            "order_id": oid, "proposed": None, "venue": None, "venue_ref": None,
            "last": None, "last_filled_qty": 0.0, "ts": None,
            "proposed_ts": None, "filled_qty": None, "avg_price": None, "filled_ts": None,
        })
        t = e["type"]
        p = e["payload"]
        if t == EventType.ORDER_PROPOSED.value:
            rec["proposed"] = p
            rec["proposed_ts"] = e.get("ts")
        elif t == EventType.ORDER_SUBMITTED.value:
            rec["venue"] = p.get("venue")
            rec["venue_ref"] = p.get("venue_ref")
        elif t == EventType.ORDER_PARTIALLY_FILLED.value:
            rec["last_filled_qty"] = float(p.get("cumulative_qty", 0))
        elif t == EventType.ORDER_FILLED.value:
            rec["filled_qty"] = float(p.get("filled_qty", 0) or 0)
            rec["avg_price"] = float(p.get("avg_price", 0) or 0)
            rec["filled_ts"] = e.get("ts")
        rec["last"] = t
        rec["ts"] = e.get("ts")

    # Terminal/label for a folded order's latest event type.
    _STATUS = {
        EventType.ORDER_PROPOSED.value: "pending",
        EventType.ORDER_APPROVED.value: "approved",
        EventType.ORDER_SUBMITTED.value: "working",
        EventType.ORDER_PARTIALLY_FILLED.value: "partial",
        EventType.ORDER_FILLED.value: "filled",
        EventType.ORDER_FAILED.value: "failed",
        EventType.ORDER_REJECTED.value: "rejected",
        EventType.ORDER_DECLINED.value: "declined",
    }

    def history(self, strategy_ids: set[str] | None = None, limit: int = 200) -> list[dict[str, Any]]:
        """Order lifecycle rows, newest first — the trade blotter.

        When ``strategy_ids`` is given, only orders tagged with one of those
        strategies are returned (the caller rolls a container up over its
        children by passing the whole subtree).
        """
        rows = []
        for rec in self._fold().values():
            p = rec.get("proposed") or {}
            sid = p.get("strategy_id")
            if strategy_ids is not None and sid not in strategy_ids:
                continue
            rows.append({
                "order_id": rec["order_id"],
                "symbol": p.get("symbol"),
                "side": p.get("side"),
                "qty": p.get("qty"),
                "strategy_id": sid,
                "thesis_id": p.get("thesis_id"),
                "status": self._STATUS.get(rec["last"], rec["last"]),
                "filled_qty": rec.get("filled_qty"),
                "avg_price": rec.get("avg_price"),
                "ts": rec.get("filled_ts") or rec.get("proposed_ts") or rec.get("ts"),
            })
        return sorted(rows, key=lambda r: r["ts"] or "", reverse=True)[:limit]

    def pending(self) -> list[dict[str, Any]]:
        out = []
        for rec in self._fold().values():
            if rec["last"] != EventType.ORDER_PROPOSED.value or rec["proposed"] is None:
                continue
            p = rec["proposed"]
            out.append({
                "order_id": rec["order_id"], "symbol": p.get("symbol"), "side": p.get("side"),
                "qty": p.get("qty"), "strategy_id": p.get("strategy_id"),
                "thesis_id": p.get("thesis_id"),  # so the approval card can render the case
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
