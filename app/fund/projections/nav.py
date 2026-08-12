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
from decimal import Decimal
from typing import Any, Callable, Optional

from firebase_admin import firestore

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money, units
from app.fund.projections.positions import Book, PositionsProjection

NAV_SNAPSHOTS = "fund_nav_snapshots"
BASE_NAV_PER_UNIT = Decimal("1.00")
_NAVPU_Q = Decimal("0.000001")
_EPS = Decimal("1e-9")


@dataclass
class NavSnapshot:
    ts: str
    total_nav_usd: Decimal
    units_outstanding: Decimal
    nav_per_unit: Decimal
    breakdown: dict[str, Decimal]               # {"positions": x, "cash": y}
    positions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        # Downcast to float at the JSON/storage edge — display, not accounting.
        return {
            "ts": self.ts,
            "total_nav_usd": f(self.total_nav_usd),
            "units_outstanding": f(self.units_outstanding),
            "nav_per_unit": f(self.nav_per_unit),
            "breakdown": {k: f(v) for k, v in self.breakdown.items()},
            "positions": [
                {"symbol": p["symbol"], "qty": f(p["qty"]),
                 "mark": f(p["mark"]), "usd_value": f(p["usd_value"])}
                for p in self.positions
            ],
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
        """Value the current book without persisting — safe to call any time.

        NAV is folded from the append-only event log ONLY. The broker (Alpaca)
        is NEVER the source of truth here: a live-equity read is non-deterministic
        and would make struck NAV non-reproducible. Broker equity is surfaced
        separately as a reconciliation/risk signal (broker-vs-book delta), not by
        overwriting the ledger. See GET /fund/venue/account and the reconciliation
        task in GEMINI.md.
        """
        book = book or self._proj.build()

        positions_value = Decimal("0")
        positions_detail: list[dict[str, Any]] = []
        for symbol, pos in book.positions.items():
            if abs(pos["qty"]) < _EPS:
                continue
            mark = D(self._price(symbol))
            value = pos["qty"] * mark
            positions_value += value
            positions_detail.append(
                {"symbol": symbol, "qty": pos["qty"], "mark": mark, "usd_value": value}
            )

        total = positions_value + book.cash
        units_out = book.units_outstanding
        navpu = (total / units_out) if units_out > _EPS else BASE_NAV_PER_UNIT

        return NavSnapshot(
            ts=datetime.now(timezone.utc).isoformat(),
            total_nav_usd=money(total),
            units_outstanding=units(units_out),
            nav_per_unit=navpu.quantize(_NAVPU_Q),
            breakdown={"positions": money(positions_value), "cash": money(book.cash)},
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

    def history(self, limit: int = 90) -> list[dict[str, Any]]:
        """Recent struck snapshots, oldest first — for value/NAV trend charts."""
        q = (
            self._db.collection(NAV_SNAPSHOTS)
            .order_by("ts", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return list(reversed([d.to_dict() for d in q]))
