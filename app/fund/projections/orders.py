"""Orders projection — approval queue, in-flight set, and per-order status.

Folds order events into each order's latest state:
  * ``pending()``   — awaiting a human decision (latest is ``OrderProposed``).
  * ``in_flight()`` — submitted to the venue but not yet terminal (latest is
    ``OrderSubmitted`` or ``OrderPartiallyFilled``); the settlement poller chases
    these to a terminal ``OrderFilled`` / ``OrderFailed``.
"""

from __future__ import annotations

from typing import Any

from app.fund.events import ORDER_ANNOTATION_EVENTS, EventStore, EventType

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
        # AN ANNOTATION IS NOT A LIFECYCLE STEP. Folding one into ``last``
        # knocks a legitimate pending ticket off the CEO's queue: the order
        # stops being `pending` here and stops being approvable in
        # ``pipeline._load_order``, which reads the same distinction.
        #
        # Two events have now made this mistake — a failed 403 probe hiding the
        # very order it could not steal (SOFI, guard v1's first day) and an
        # autopolicy decline hiding an order whose own event says the CEO can
        # still approve it. The membership set is in ``app/fund/events.py`` with
        # both incidents written out, so the next order event type is classified
        # once instead of at each fold that happens to be remembered.
        if e["type"] in ORDER_ANNOTATION_EVENTS:
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
                # The case for the trade, and the case against it. Both belong
                # at the approval card: reasoning the operator cannot see at
                # the moment they decide is reasoning that did not happen.
                "rationale": p.get("rationale"),
                "critique": p.get("critique"),
                # The order type is part of what is being approved. A limit at
                # $101 and a market order are different risks wearing the same
                # symbol and quantity; an approval card that hides which one it
                # is asks the operator to sign a blank.
                "limit_price": p.get("limit_price"),
                "impact_preview": p.get("impact_preview"), "ts": rec["ts"],
                # Age and staleness, computed here so the approval card can say
                # "expiring soon" or "stale" instead of showing an approve button
                # whose only possible outcome is an error. None when the
                # timestamp cannot be parsed — unknown age is not zero age.
                "age_minutes": _age_minutes(rec["ts"]),
                "stale": _is_stale(rec["ts"]),
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

def _age_minutes(ts: str | None) -> float | None:
    if not ts:
        return None
    from datetime import datetime, timezone
    try:
        t = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        return round((datetime.now(timezone.utc) - t).total_seconds() / 60.0, 1)
    except ValueError:
        return None


def _is_stale(ts: str | None) -> bool | None:
    """None means could-not-tell, which is not the same as fresh."""
    from app.fund.pipeline import PROPOSAL_STALE_AFTER_MINUTES
    age = _age_minutes(ts)
    return None if age is None else age > PROPOSAL_STALE_AFTER_MINUTES
