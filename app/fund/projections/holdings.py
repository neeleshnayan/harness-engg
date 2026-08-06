"""Per-LP holdings projection — the answer to "what do I own?".

Folds ``UnitsIssued`` / ``UnitsBurned`` per LP into units held, and picks up a
display name from ``SubscriptionRequested``. Units are valued by multiplying by
the current NAV-per-unit (passed in), so a single NAV drives every LP's number.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.fund.events import EventStore, EventType
from app.fund.money import D, f, money


class HoldingsProjection:
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def build(self) -> dict[str, dict[str, Any]]:
        holdings: dict[str, dict[str, Any]] = {}

        def lp(lp_id: str) -> dict[str, Any]:
            return holdings.setdefault(lp_id, {"lp_id": lp_id, "name": None, "units": Decimal("0")})

        for e in self._store.stream(since_seq=0, limit=100_000):
            p = e.get("payload", {})
            etype = e.get("type")
            if etype == EventType.SUBSCRIPTION_REQUESTED.value:
                rec = lp(p["lp_id"])
                if p.get("lp_name"):
                    rec["name"] = p["lp_name"]
            elif etype == EventType.UNITS_ISSUED.value:
                lp(p["lp_id"])["units"] += D(p["units"])
            elif etype == EventType.UNITS_BURNED.value:
                lp(p["lp_id"])["units"] -= D(p["units"])

        return holdings

    def with_values(self, nav_per_unit: Decimal) -> list[dict[str, Any]]:
        navpu = D(nav_per_unit)
        out = []
        for rec in self.build().values():
            if abs(rec["units"]) < D("1e-9"):
                continue
            out.append({
                "lp_id": rec["lp_id"],
                "name": rec["name"],
                "units": f(rec["units"]),
                "value_usd": f(money(rec["units"] * navpu)),
            })
        return sorted(out, key=lambda r: r["value_usd"], reverse=True)
