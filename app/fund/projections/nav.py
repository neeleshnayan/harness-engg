"""NAV service — strikes the fund's net asset value and NAV-per-unit.

NAV = Σ(position qty × mark) across venues + idle cash, in USD.
NAV per unit = NAV ÷ units outstanding (base 1.00 before any units exist).

Rules that keep the accounting honest (docs/architecture.md §6):
  * Strike at a defined moment; subscriptions/redemptions transact at the
    *next* strike, never intraday.
  * A strike folds only confirmed positions. In-flight (unconfirmed) orders are
    excluded — modelled naturally here because only ``OrderFilled`` events move
    the positions projection.

Marks come from a ``pricer`` (the paper connector in phase 1; a real oracle in
phase 2). Each ``NavStruck`` is appended to the event log and mirrored to
``fund_nav_snapshots`` for cheap reads by the frontend / LP view.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from firebase_admin import firestore

from app.fund.events import Event, EventStore, EventType
from app.fund.projections.positions import Book, PositionsProjection

NAV_SNAPSHOTS = "fund_nav_snapshots"
BASE_NAV_PER_UNIT = 1.00


@dataclass
class NavSnapshot:
    ts: str
    total_nav_usd: float
    units_outstanding: float
    nav_per_unit: float
    breakdown: dict[str, float]                 # {"positions": x, "cash": y}
    positions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "total_nav_usd": self.total_nav_usd,
            "units_outstanding": self.units_outstanding,
            "nav_per_unit": self.nav_per_unit,
            "breakdown": self.breakdown,
            "positions": self.positions,
        }


class NavService:
    def __init__(
        self,
        pricer: Callable[[str], float],
        store: EventStore | None = None,
        projection: PositionsProjection | None = None,
        db=None,
    ):
        self._price = pricer
        self._store = store or EventStore()
        self._proj = projection or PositionsProjection(self._store)
        self._db = db or firestore.client()

    def compute(self, book: Optional[Book] = None) -> NavSnapshot:
        """Value the current book without persisting — safe to call any time."""
        book = book or self._proj.build()

        positions_value = 0.0
        positions_detail: list[dict[str, Any]] = []
        for symbol, pos in book.positions.items():
            if abs(pos["qty"]) < 1e-9:
                continue
            mark = self._price(symbol)
            value = pos["qty"] * mark
            positions_value += value
            positions_detail.append(
                {"symbol": symbol, "qty": pos["qty"], "mark": mark, "usd_value": value}
            )

        total = positions_value + book.cash
        units = book.units_outstanding
        nav_per_unit = (total / units) if units > 1e-9 else BASE_NAV_PER_UNIT

        return NavSnapshot(
            ts=datetime.now(timezone.utc).isoformat(),
            total_nav_usd=round(total, 6),
            units_outstanding=round(units, 6),
            nav_per_unit=round(nav_per_unit, 6),
            breakdown={"positions": round(positions_value, 6), "cash": round(book.cash, 6)},
            positions=positions_detail,
        )

    def strike(self, actor: str = "system") -> NavSnapshot:
        """Strike and persist a NAV — the scheduled valuation moment."""
        snap = self.compute()
        self._store.append(
            Event(
                aggregate_id="fund",
                aggregate_type="fund",
                type=EventType.NAV_STRUCK,
                payload=snap.to_dict(),
                actor=actor,
            )
        )
        self._db.collection(NAV_SNAPSHOTS).document(snap.ts).set(snap.to_dict())
        return snap

    def latest(self) -> Optional[dict[str, Any]]:
        q = (
            self._db.collection(NAV_SNAPSHOTS)
            .order_by("ts", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        return next((d.to_dict() for d in q), None)
