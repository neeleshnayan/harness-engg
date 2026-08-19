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

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from app.fund.compliance import (
    AccountState,
    ComplianceDecision,
    ComplianceGate,
    DayTradeLedger,
)
from app.fund.connectors.base import Connector, FillState, Order, Side, VenueRef
from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money
from app.fund.projections.nav import NavService
from app.fund.projections.orders import OrdersProjection
from app.fund.risk import RiskGate, RiskLimits
from app.fund.riskmonitor import RiskControl, RiskMonitor


#: How long a proposed order stays approvable. Past this the price and signal
#: behind the decision have moved and the impact preview shown at the approval
#: card is stale. Matches the rebalance planner's window so the two agree about
#: what "too old to act on" means.
PROPOSAL_STALE_AFTER_MINUTES = float(os.getenv("PROPOSAL_STALE_AFTER_MINUTES", "120"))


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
        compliance = self.compliance_check(order)

        breaches = (
            (venue_check.errors or [])
            + (risk.breaches or [])
            + (compliance.blocks or [])
        )
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
        # Compliance warnings ride along to the approval card. "One day trade
        # left before the account is flagged" is only useful while there is
        # still a decision to make about it.
        if compliance.warnings:
            preview["compliance_warnings"] = compliance.warnings
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

    def compliance_check(self, order: Order) -> ComplianceDecision:
        """Rules imposed from outside the mandate — see ``compliance.py``.

        A connector with no ``account_state`` is not a brokerage account: the
        simulated venue has no regulator and no day-trade counter, so there is
        nothing to enforce and pretending otherwise would block mock trading on
        a rule that does not apply to it. A connector that HAS the method but
        cannot answer is a different case entirely — that falls through to our
        own day-trade count, folded from the event log, so an unreachable
        broker degrades to our own books rather than to no check at all.
        """
        if not hasattr(self._connector, "account_state"):
            return ComplianceDecision(ok=True)
        try:
            account = self._connector.account_state()
        except Exception as e:  # noqa: BLE001
            account = AccountState.unknown(str(e))
        return ComplianceGate(DayTradeLedger(self._store)).check(order, account)

    def risk_gate_for_preview(self) -> RiskGate:
        """The gate as currently configured, for a read-only what-would-happen check.

        Exposed so a caller can ask the question without proposing: proposing a
        doomed order writes an ORDER_REJECTED event for a click that never had a
        chance, and shows the operator a button whose only outcome is failure.
        Reads limits fresh, exactly as propose_order does.
        """
        return self._explicit_risk_gate or RiskGate(limits=self._control.limits())

    # --- approve / decline -------------------------------------------------
    def approve_order(self, order_id: str, approver: str,
                      policy_evaluation: dict[str, Any] | None = None
                      ) -> dict[str, Any]:
        order, last_type = self._load_order(order_id)
        if last_type != EventType.ORDER_PROPOSED.value:
            raise CommandError(f"order {order_id} is '{last_type}', not awaiting approval")

        # A proposal is a decision made at a moment, against a price and a signal
        # that were true then. Approving a week-old proposal executes yesterday's
        # judgement at today's price, and the impact preview shown at the approval
        # card is stale by exactly as much. Rebalance plans already expire; a
        # single order had no such limit at all.
        age = self._proposal_age_minutes(order_id)
        if age is not None and age > PROPOSAL_STALE_AFTER_MINUTES:
            raise CommandError(
                f"order {order_id} was proposed {age:.0f} minutes ago, past the "
                f"{PROPOSAL_STALE_AFTER_MINUTES}-minute limit — the price and the "
                "signal behind it have moved. Re-propose it rather than approving "
                "a stale decision."
            )

        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_APPROVED,
                # When the approver is the auto-policy, the FULL check-by-check
                # evaluation rides on the approval event, so the risk officer
                # audits decisions rather than summaries and the log answers
                # "why did this execute" forever.
                payload={"approver": approver,
                         **({"policy_evaluation": policy_evaluation}
                            if policy_evaluation else {})},
                actor=approver,
            )
        )

        # The arrival price: the market as it stood the instant we submitted.
        #
        # Without it, the only measurable cost is fill-minus-decision, which
        # silently blends two very different things — the market drifting while
        # a human thought about the order, and the cost of actually crossing the
        # spread. Those have different fixes (approve faster / use a limit
        # order) so they are worth separating, and they cannot be separated
        # after the fact.
        #
        # Measurement, never a control: a quote failure must not stop a submit
        # the operator has already approved.
        arrival = None
        try:
            arrival = float(self._connector.quote(order).price)
        except Exception:  # noqa: BLE001
            arrival = None

        # order_id is the idempotency key -> retries never double-execute.
        ref = self._connector.execute(order, idempotency_key=order_id)
        self._store.append(
            Event(
                aggregate_id=order_id,
                aggregate_type="order",
                type=EventType.ORDER_SUBMITTED,
                payload={"venue": ref.venue, "venue_ref": ref.ref_id,
                         "arrival_price": arrival},
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

    def apply_venue_status(self, order_id: str, status) -> dict[str, Any]:
        """Apply a status the VENUE pushed at us, rather than one we asked for.

        The same path the poller takes, entered from the other end. Keeping them
        on one code path is the point: a fill must mean the same thing whether we
        discovered it or were told about it, and two implementations of "what a
        fill does to the book" would eventually disagree.

        An order we never proposed is reported, never invented into the ledger —
        somebody trading the same venue account by hand is not this fund's
        business to record.
        """
        try:
            order, _ = self._load_order(order_id)
        except CommandError:
            return {"status": "unknown_order", "order_id": order_id}

        rec = next(
            (r for r in OrdersProjection(self._store).in_flight()
             if r["order_id"] == order_id),
            None,
        )
        return self._apply_status(order_id, order, status,
                                  last_filled=(rec or {}).get("last_filled_qty", 0.0))

    def poll_open_orders(self) -> dict[str, Any]:
        """Chase every in-flight order — the settlement worker's tick."""
        results = [self.poll_order(r["order_id"]) for r in OrdersProjection(self._store).in_flight()]
        return {"polled": len(results), "results": results}

    def _terminal_types(self, order_id: str) -> set[str]:
        """Event types already recorded for this order."""
        try:
            return {e.get("type") for e in self._store.by_aggregate(order_id)}
        except Exception:  # noqa: BLE001 — an unreadable log must not double-book
            raise

    def _emit_fill(self, order_id: str, order: Order, qty, px, fees) -> bool:
        """Record the fill. Returns False if it was already recorded.

        Two independent things now observe fills — the settlement poller and the
        venue's trade-update stream — and they are deliberately redundant: the
        stream is fast but can drop frames or disconnect, the poller is slow but
        cannot miss. Redundancy only helps if the second observer is harmless,
        and a second ORDER_FILLED would double the position in every projection
        that folds the log.

        So the log itself is the idempotency key. ORDER_FILLED is terminal —
        exactly one per order — which makes "has this order already filled?" a
        question the event store can answer without any extra bookkeeping.
        """
        if EventType.ORDER_FILLED.value in self._terminal_types(order_id):
            return False
        self._store.append(Event(
            aggregate_id=order_id, aggregate_type="order", type=EventType.ORDER_FILLED,
            payload={
                "symbol": order.symbol, "side": order.side.value, "strategy_id": order.strategy_id,
                "filled_qty": D(qty), "avg_price": D(px or 0), "fees": D(fees or 0),
            },
            actor="system",
        ))
        return True

    def _apply_status(self, order_id: str, order: Order, status, last_filled: float = 0.0):
        if status.state == FillState.FILLED:
            fresh = self._emit_fill(order_id, order, status.filled_qty, status.avg_price, status.fees)
            # Re-evaluating risk is only worth it when the book actually moved.
            # On a duplicate — the stream saw it and the poller followed — the
            # book is unchanged and this is pure work.
            if fresh:
                try:
                    RiskMonitor(nav_service=self._nav, store=self._store, pricer=self._connector.price, control=self._control).run(actor="fill_re-eval")
                except Exception:
                    pass
            return {"status": "filled", "order_id": order_id, "duplicate": not fresh,
                    "filled_qty": f(D(status.filled_qty)), "avg_price": f(D(status.avg_price))}

        if status.state == FillState.FAILED:
            seen = self._terminal_types(order_id)
            # Book any already-executed portion before recording the failure.
            if status.filled_qty and status.filled_qty > last_filled:
                self._emit_fill(order_id, order, status.filled_qty, status.avg_price, status.fees)
            # ORDER_FAILED is terminal too, and the same two observers can both
            # deliver a cancel or a reject.
            if EventType.ORDER_FAILED.value in seen:
                return {"status": "failed", "order_id": order_id, "duplicate": True,
                        "reason": status.reason}
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

    def expire_stale_proposals(self, pending: list[dict[str, Any]],
                               max_age_minutes: float | None = None
                               ) -> dict[str, Any]:
        """Decline proposals too old to approve, so the queue never holds a trap.

        The approve path already refuses a stale proposal — correctly: approving a
        46-hour-old proposal executes yesterday's judgement at today's price. But
        refusal alone left the QUEUE in a broken state: the operator saw approve
        buttons whose only possible outcome was an error, and the one time it
        happened the underlying signal had actually inverted (a take-profit
        proposal on a position that had since fallen to -8%). A guard that only
        fires at the moment of approval protects the trade and abandons the
        operator.

        So expiry is a scheduled behaviour: anything past the limit is DECLINED by
        the worker with the reason on the record. Exit-rule-sourced proposals are
        deliberately NOT re-raised here — the exit tick re-evaluates its rules
        against FRESH marks every cycle anyway, so a still-true condition
        re-proposes itself within a tick, and a no-longer-true condition (the
        INTC case) correctly stays silent.
        """
        limit = (PROPOSAL_STALE_AFTER_MINUTES if max_age_minutes is None
                 else max_age_minutes)
        expired = []
        for row in pending or []:
            oid = row.get("order_id")
            if not oid:
                continue
            age = self._proposal_age_minutes(oid)
            if age is None or age <= limit:
                continue
            self._store.append(Event(
                aggregate_id=oid,
                aggregate_type="order",
                type=EventType.ORDER_DECLINED,
                payload={"approver": "worker",
                         "reason": (f"expired: proposed {age:.0f} minutes ago, "
                                    f"past the {limit:.0f}-minute staleness "
                                    f"limit. The price and signal behind it have "
                                    f"moved; a fresh proposal must be made "
                                    f"against fresh marks")},
                actor="worker"))
            expired.append({"order_id": oid, "symbol": row.get("symbol"),
                            "age_minutes": round(age, 1)})
        return {"expired": expired, "count": len(expired),
                "limit_minutes": limit,
                "note": (f"{len(expired)} stale proposal(s) declined by the "
                         f"worker, reason on the record"
                         if expired else "nothing past the staleness limit")}

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
            "rationale": order.rationale,
            "critique": order.critique,
        }

    def _proposal_age_minutes(self, order_id: str) -> float | None:
        """Minutes since the order was proposed, or None if we cannot tell.

        An unparseable timestamp returns None and the approval proceeds: refusing
        every approval because a clock format changed would be a worse failure
        than approving one order a little late.
        """
        proposed = next(
            (e for e in self._store.by_aggregate(order_id)
             if e["type"] == EventType.ORDER_PROPOSED.value),
            None,
        )
        ts = (proposed or {}).get("ts") or (proposed or {}).get("timestamp")
        if not ts:
            return None
        try:
            when = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except ValueError:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - when).total_seconds() / 60.0

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
