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
    def __init__(self, store: EventStore | None = None, snapshots: Any = None,
                 snapshot_every: int = 50):
        self._store = store or EventStore()
        self._snapshots = snapshots
        self._snapshot_every = snapshot_every

    @staticmethod
    def _apply(holdings: dict[str, dict[str, Any]], e: dict[str, Any]) -> None:
        p = e.get("payload", {})
        etype = e.get("type")

        def lp(lp_id: str) -> dict[str, Any]:
            return holdings.setdefault(lp_id, {"lp_id": lp_id, "name": None, "units": Decimal("0")})

        if etype == EventType.SUBSCRIPTION_REQUESTED.value:
            rec = lp(p["lp_id"])
            if p.get("lp_name"):
                rec["name"] = p["lp_name"]
        elif etype == EventType.UNITS_ISSUED.value:
            lp(p["lp_id"])["units"] += D(p["units"])
        elif etype == EventType.UNITS_BURNED.value:
            lp(p["lp_id"])["units"] -= D(p["units"])

    def build(self) -> dict[str, dict[str, Any]]:
        """Fold the LP register. Snapshotted when a snapshot store is supplied;
        the event log remains the source of truth either way."""
        if self._snapshots is None:
            holdings: dict[str, dict[str, Any]] = {}
            for e in self._store.stream(since_seq=0, limit=100_000):
                self._apply(holdings, e)
            return holdings

        from app.fund.snapshots import SnapshottedFold

        return SnapshottedFold(
            "holdings", self._store, self._snapshots, every=self._snapshot_every
        ).fold(
            empty=dict,
            apply=self._apply,
            to_state=lambda h: h,
            from_state=lambda s: dict(s or {}),
        )

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
