"""Command pipeline — the spine's write path.

    propose_order -> [risk gate] -> ORDER_PROPOSED (awaiting human approval)
    approve_order -> ORDER_APPROVED -> connector.execute (idempotent)
                  -> ORDER_SUBMITTED -> poll -> ORDER_FILLED | ORDER_FAILED
    decline_order -> ORDER_DECLINED

The order id doubles as the idempotency key handed to the connector, so a
re-approval or retry can never place a second order. Every outcome — including
a risk rejection or a human decline — is an event, so the audit trail is
complete by construction.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.fund.connectors.base import Connector, FillState, Order, Side
from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money
from app.fund.projections.nav import NavService
from app.fund.risk import RiskGate


class CommandError(Exception):
    """Raised on an invalid state transition (e.g. approving a filled order)."""


class CommandPipeline:
    def __init__(
        self,
        connector: Connector,
        nav_service: NavService,
        store: EventStore | None = None,
        risk_gate: RiskGate | None = None,
    ):
        self._connector = connector
        self._nav = nav_service
        self._store = store or EventStore()
        self._risk = risk_gate or RiskGate()

    # --- propose -----------------------------------------------------------
    def propose_order(self, order: Order, actor: str) -> dict[str, Any]:
        order_id = str(uuid.uuid4())

        venue_check = self._connector.validate(order)
        quote = self._connector.quote(order)
        nav = self._nav.compute()
        risk = self._risk.check(order, quote.price, nav)

        breaches = (venue_check.errors or []) + (risk.breaches or [])
        if breaches:
            self._store.append(
                Event(
                    aggregate_id=order_id,
                    aggregate_type="order",
                    type=EventType.ORDER_REJECTED,
                    payload={**self._order_payload(order), "breaches": breaches},
                    actor=actor,
                )
            )
            return {"status": "rejected", "order_id": order_id, "breaches": breaches}

        notional = D(order.qty) * D(quote.price)
        cash_before = nav.breakdown.get("cash", D(0))
        cash_after = cash_before - (notional if order.side == Side.BUY else -notional)
        preview = {
            "quote_price": f(D(quote.price)),
            "notional_usd": f(money(notional)),
            "nav_before": f(nav.total_nav_usd),
            "cash_before": f(cash_before),
            "cash_after": f(money(cash_after)),
        }
        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_PROPOSED,
                payload={**self._order_payload(order), "impact_preview": preview},
                actor=actor,
            )
        )
        return {"status": "pending_approval", "order_id": order_id, "impact_preview": preview}

    # --- approve / decline -------------------------------------------------
    def approve_order(self, order_id: str, approver: str) -> dict[str, Any]:
        order, last_type = self._load_order(order_id)
        if last_type != EventType.ORDER_PROPOSED.value:
            raise CommandError(f"order {order_id} is '{last_type}', not awaiting approval")

        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_APPROVED,
                payload={"approver": approver},
                actor=approver,
            )
        )

        # order_id is the idempotency key -> retries never double-execute.
        ref = self._connector.execute(order, idempotency_key=order_id)
        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_SUBMITTED,
                payload={"venue": ref.venue, "venue_ref": ref.ref_id},
                actor="system",
            )
        )

        status = self._connector.poll(ref)
        if status.state == FillState.FILLED:
            self._store.append(
                Event(
                    aggregate_id=order_id,
                    aggregate_type="order",
                    type=EventType.ORDER_FILLED,
                    payload={
                        "symbol": order.symbol,
                        "side": order.side.value,
                        "strategy_id": order.strategy_id,
                        # Exact-decimal truth; venue floats converted at ingestion.
                        "filled_qty": D(status.filled_qty),
                        "avg_price": D(status.avg_price),
                        "fees": D(status.fees),
                    },
                    actor="system",
                )
            )
            return {"status": "filled", "order_id": order_id,
                    "filled_qty": f(D(status.filled_qty)), "avg_price": f(D(status.avg_price))}

        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_FAILED,
                payload={"reason": status.reason or "unknown"},
                actor="system",
            )
        )
        return {"status": "failed", "order_id": order_id, "reason": status.reason}

    def decline_order(self, order_id: str, approver: str) -> dict[str, Any]:
        _, last_type = self._load_order(order_id)
        if last_type != EventType.ORDER_PROPOSED.value:
            raise CommandError(f"order {order_id} is '{last_type}', not awaiting approval")
        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_DECLINED,
                payload={"approver": approver},
                actor=approver,
            )
        )
        return {"status": "declined", "order_id": order_id}

    # --- helpers -----------------------------------------------------------
    @staticmethod
    def _order_payload(order: Order) -> dict[str, Any]:
        return {
            "venue": order.venue,
            "symbol": order.symbol,
            "side": order.side.value,
            "qty": order.qty,
            "limit_price": order.limit_price,
            "strategy_id": order.strategy_id,
        }

    def _load_order(self, order_id: str) -> tuple[Order, str]:
        events = self._store.by_aggregate(order_id)
        if not events:
            raise CommandError(f"unknown order {order_id}")
        proposed = next(
            (e for e in events if e["type"] == EventType.ORDER_PROPOSED.value), None
        )
        if proposed is None:
            raise CommandError(f"order {order_id} was never proposed")
        p = proposed["payload"]
        order = Order(
            venue=p["venue"],
            symbol=p["symbol"],
            side=Side(p["side"]),
            qty=p["qty"],
            limit_price=p.get("limit_price"),
            strategy_id=p.get("strategy_id"),
        )
        return order, events[-1]["type"]
