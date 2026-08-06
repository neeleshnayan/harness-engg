"""Unit ledger — subscriptions and redemptions for the pooled fund.

Standard open-ended-fund accounting. LPs never own specific positions; they own
*units*. The fund trades the pool, NAV moves, and every LP's units revalue
pro-rata automatically.

Lifecycles (each is its own event-sourced aggregate):

    subscribe: SubscriptionRequested → (confirm) → CashConfirmed + UnitsIssued
    redeem:    RedemptionRequested   → (confirm) → UnitsBurned  + PayoutSent

v0 deposits/payouts move off-platform (the manager wires money and records it),
so "confirm" is the manager attesting the cash landed / the payout was sent.

The invariant that keeps it fair: units are minted at the NAV-per-unit struck
*before* the new cash is counted, so a subscription leaves everyone else's
NAV-per-unit unchanged. Concretely, units = amount / nav_per_unit and we append
the cash and the units together — the new LP's cash exactly backs their units.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from app.fund.events import Event, EventStore, EventType
from app.fund.projections.nav import NavService


class LedgerError(Exception):
    """Invalid ledger transition (e.g. confirming an already-issued subscription)."""


class LedgerService:
    def __init__(self, nav_service: NavService, store: EventStore | None = None):
        self._nav = nav_service
        self._store = store or EventStore()

    # --- subscribe ---------------------------------------------------------
    def request_subscription(
        self, lp_id: str, usd_amount: float, actor: str, lp_name: Optional[str] = None
    ) -> dict[str, Any]:
        if usd_amount <= 0:
            raise LedgerError("usd_amount must be positive")
        sub_id = str(uuid.uuid4())
        self._store.append(
            Event(
                aggregate_id=sub_id,
                aggregate_type="subscription",
                type=EventType.SUBSCRIPTION_REQUESTED,
                payload={"lp_id": lp_id, "lp_name": lp_name, "usd_amount": usd_amount},
                actor=actor,
            )
        )
        return {"status": "pending_cash", "subscription_id": sub_id,
                "lp_id": lp_id, "usd_amount": usd_amount}

    def confirm_subscription(self, subscription_id: str, actor: str) -> dict[str, Any]:
        """Cash has landed → mint units at the current (pre-deposit) NAV-per-unit."""
        req = self._require_last(subscription_id, EventType.SUBSCRIPTION_REQUESTED, "subscription")
        lp_id = req["lp_id"]
        amount = float(req["usd_amount"])

        nav_per_unit = self._nav.compute().nav_per_unit  # struck before this deposit
        units = amount / nav_per_unit

        # Cash and units enter together so NAV-per-unit is unchanged for everyone else.
        self._store.append(
            Event(subscription_id, "subscription", EventType.CASH_CONFIRMED,
                  {"lp_id": lp_id, "usd_amount": amount}, actor)
        )
        self._store.append(
            Event(subscription_id, "subscription", EventType.UNITS_ISSUED,
                  {"lp_id": lp_id, "units": units, "nav_per_unit": nav_per_unit}, actor)
        )
        return {"status": "issued", "subscription_id": subscription_id, "lp_id": lp_id,
                "usd_amount": amount, "units_issued": round(units, 6),
                "nav_per_unit": nav_per_unit}

    # --- redeem ------------------------------------------------------------
    def request_redemption(
        self, lp_id: str, actor: str, units: Optional[float] = None
    ) -> dict[str, Any]:
        """Redeem ``units`` (or the LP's full holding when units is None)."""
        from app.fund.projections.holdings import HoldingsProjection

        held = HoldingsProjection(self._store).build().get(lp_id, {}).get("units", 0.0)
        units = held if units is None else units
        if units <= 0:
            raise LedgerError(f"{lp_id} has no units to redeem")
        if units - held > 1e-9:
            raise LedgerError(f"{lp_id} holds {held} units, cannot redeem {units}")

        red_id = str(uuid.uuid4())
        self._store.append(
            Event(red_id, "redemption", EventType.REDEMPTION_REQUESTED,
                  {"lp_id": lp_id, "units": units}, actor)
        )
        return {"status": "pending_payout", "redemption_id": red_id,
                "lp_id": lp_id, "units": round(units, 6)}

    def confirm_redemption(self, redemption_id: str, actor: str) -> dict[str, Any]:
        """Payout sent → burn units and remove cash at the current NAV-per-unit."""
        req = self._require_last(redemption_id, EventType.REDEMPTION_REQUESTED, "redemption")
        lp_id = req["lp_id"]
        units = float(req["units"])

        nav_per_unit = self._nav.compute().nav_per_unit
        usd_out = units * nav_per_unit

        self._store.append(
            Event(redemption_id, "redemption", EventType.UNITS_BURNED,
                  {"lp_id": lp_id, "units": units, "nav_per_unit": nav_per_unit}, actor)
        )
        self._store.append(
            Event(redemption_id, "redemption", EventType.PAYOUT_SENT,
                  {"lp_id": lp_id, "usd_amount": usd_out}, actor)
        )
        return {"status": "paid_out", "redemption_id": redemption_id, "lp_id": lp_id,
                "units_burned": round(units, 6), "usd_out": round(usd_out, 2),
                "nav_per_unit": nav_per_unit}

    # --- helpers -----------------------------------------------------------
    def _require_last(self, agg_id: str, expected: EventType, kind: str) -> dict[str, Any]:
        events = self._store.by_aggregate(agg_id)
        if not events:
            raise LedgerError(f"unknown {kind} {agg_id}")
        if events[-1]["type"] != expected.value:
            raise LedgerError(
                f"{kind} {agg_id} is '{events[-1]['type']}', expected '{expected.value}'"
            )
        return events[0]["payload"]
