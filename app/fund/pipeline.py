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

from app.fund.connectors.base import Connector, FillState, Order, Side, VenueRef
from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money
from app.fund.projections.nav import NavService
from app.fund.projections.orders import OrdersProjection
from app.fund.risk import RiskGate, RiskLimits
from app.fund.riskmonitor import RiskControl, RiskMonitor


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
        self._control = RiskControl(self._store)
        self._explicit_risk_gate = risk_gate
        # Do NOT read the event log here. This runs at module import, so a
        # database that is unreachable (or over quota) would take the whole
        # service down at boot instead of letting it start and report itself
        # unhealthy. propose_order() reads limits fresh anyway — that is what
        # makes a limit change take effect without a restart.
        self._risk = risk_gate or RiskGate(limits=RiskLimits())

    # --- propose -----------------------------------------------------------
    def propose_order(self, order: Order, actor: str) -> dict[str, Any]:
        order_id = str(uuid.uuid4())

        # Risk kill-switch halt check (block BUYs, allow SELLs)
        if self._control.is_halted() and order.side == Side.BUY:
            breaches = ["trading halted (risk kill-switch)"]
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

        venue_check = self._connector.validate(order)
        quote = self._connector.quote(order)
        nav = self._nav.compute()
        gate = self._explicit_risk_gate or RiskGate(limits=self._control.limits())
        risk = gate.check(order, quote.price, nav)

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

        # One poll now: instant-fill venues settle here; async venues stay
        # 'working' and the settlement poller drives them to terminal later.
        return self._apply_status(order_id, order, self._connector.poll(ref))

    # --- settlement (async fill path) --------------------------------------
    def poll_order(self, order_id: str) -> dict[str, Any]:
        """Re-poll one in-flight order and emit any resulting terminal/partial event."""
        rec = next(
            (r for r in OrdersProjection(self._store).in_flight() if r["order_id"] == order_id),
            None,
        )
        if rec is None:
            return {"status": "not_in_flight", "order_id": order_id}
        order, _ = self._load_order(order_id)
        ref = VenueRef(venue=rec["venue"], ref_id=rec["venue_ref"])
        return self._apply_status(order_id, order, self._connector.poll(ref),
                                  last_filled=rec["last_filled_qty"])

    def poll_open_orders(self) -> dict[str, Any]:
        """Chase every in-flight order — the settlement worker's tick."""
        results = [self.poll_order(r["order_id"]) for r in OrdersProjection(self._store).in_flight()]
        return {"polled": len(results), "results": results}

    def _emit_fill(self, order_id: str, order: Order, qty, px, fees) -> None:
        self._store.append(Event(
            aggregate_id=order_id, aggregate_type="order", type=EventType.ORDER_FILLED,
            payload={
                "symbol": order.symbol, "side": order.side.value, "strategy_id": order.strategy_id,
                "filled_qty": D(qty), "avg_price": D(px or 0), "fees": D(fees or 0),
            },
            actor="system",
        ))

    def _apply_status(self, order_id: str, order: Order, status, last_filled: float = 0.0):
        if status.state == FillState.FILLED:
            self._emit_fill(order_id, order, status.filled_qty, status.avg_price, status.fees)
            try:
                RiskMonitor(nav_service=self._nav, store=self._store, pricer=self._connector.price, control=self._control).run(actor="fill_re-eval")
            except Exception:
                pass
            return {"status": "filled", "order_id": order_id,
                    "filled_qty": f(D(status.filled_qty)), "avg_price": f(D(status.avg_price))}

        if status.state == FillState.FAILED:
            # Book any already-executed portion before recording the failure.
            if status.filled_qty and status.filled_qty > last_filled:
                self._emit_fill(order_id, order, status.filled_qty, status.avg_price, status.fees)
            self._store.append(Event(
                aggregate_id=order_id, aggregate_type="order", type=EventType.ORDER_FAILED,
                payload={"reason": status.reason or "unknown"}, actor="system",
            ))
            return {"status": "failed", "order_id": order_id, "reason": status.reason}

        if status.state == FillState.PARTIAL:
            if status.filled_qty > last_filled:
                self._store.append(Event(
                    aggregate_id=order_id, aggregate_type="order",
                    type=EventType.ORDER_PARTIALLY_FILLED,
                    payload={"cumulative_qty": D(status.filled_qty), "avg_price": D(status.avg_price or 0)},
                    actor="system",
                ))
            return {"status": "working", "order_id": order_id, "filled_qty": f(D(status.filled_qty))}

        return {"status": "working", "order_id": order_id}  # PENDING

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
            "thesis_id": order.thesis_id,
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
