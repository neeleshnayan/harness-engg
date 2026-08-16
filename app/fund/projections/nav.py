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

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from firebase_admin import firestore

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money, units
from app.fund.projections.positions import Book, PositionsProjection

logger = logging.getLogger(__name__)

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
        # Obtained lazily. NAV FOLDS from the event log and needs no database
        # of its own; this handle exists only for the nav_snapshots collection,
        # which strike() writes and the history readers read. Taking it in the
        # constructor made every read-only fold require a live Firestore —
        # which, once the log moved to Postgres, meant computing NAV still
        # failed on a Firestore outage it no longer depended on.
        self._db_override = db

    @property
    def _db(self):
        if self._db_override is not None:
            return self._db_override
        from app.core.firebase import db as _fs_db
        return _fs_db()

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

        gross = positions_value + book.cash

        # Accrued fees are a LIABILITY, not a future event. A fee is earned
        # continuously and paid occasionally, so NAV has to carry what is owed
        # from the moment it is owed — otherwise NAV drifts up all quarter and
        # drops on payment day, and every unit issued in between is priced
        # wrong. An investor subscribing the day before a payment would buy
        # into a liability the price does not show.
        #
        # Read defensively: fees must never be able to take NAV down with them.
        accrued = Decimal("0")
        try:
            from app.fund.fees import FeeLedger
            accrued = FeeLedger(self._store).outstanding()
        except Exception:  # noqa: BLE001
            accrued = Decimal("0")

        total = gross - accrued
        units_out = book.units_outstanding
        navpu = (total / units_out) if units_out > _EPS else BASE_NAV_PER_UNIT

        breakdown = {"positions": money(positions_value), "cash": money(book.cash)}
        if accrued > _EPS:
            # Only shown when non-zero, but named plainly when it is: a
            # liability the reader cannot see is one they will assume away.
            breakdown["accrued_fees"] = money(-accrued)

        return NavSnapshot(
            ts=datetime.now(timezone.utc).isoformat(),
            total_nav_usd=money(total),
            units_outstanding=units(units_out),
            nav_per_unit=navpu.quantize(_NAVPU_Q),
            breakdown=breakdown,
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
        # Best effort, and only a cache. The fact is already in the event log
        # above; this collection is a convenience copy that predates the log
        # being cheap to read. A failure here must not fail a strike, or an
        # outage in a cache would stop the fund marking its own book.
        try:
            self._db.collection(NAV_SNAPSHOTS).document(snap.ts).set(snap.to_dict())
        except Exception as e:  # noqa: BLE001
            logger.warning("nav snapshot cache write failed (the strike itself "
                           "is recorded in the event log): %s", e)
        return snap

    def since_inception(self, snap: Optional[NavSnapshot] = None) -> dict[str, Any]:
        """Cumulative P&L: NAV against net external cash, plus the per-unit return.

        Two figures because they answer different questions. The dollar figure
        is NAV minus everything LPs put in, plus everything paid back out —
        what the fund has actually made. The per-unit figure is flow-proof:
        what a dollar at inception is worth now, unchanged by a later
        subscription landing at a different unit price. Both fold from the
        event log; the broker is not consulted.
        """
        snap = snap or self.compute()
        subscribed = Decimal("0")
        paid_out = Decimal("0")
        for e in self._store.stream(since_seq=0, limit=100_000):
            t = e.get("type")
            p = e.get("payload") or {}
            if t == EventType.CASH_CONFIRMED.value:
                subscribed += D(p.get("usd_amount") or 0)
            elif t == EventType.PAYOUT_SENT.value:
                paid_out += D(p.get("usd_amount") or 0)
        pnl = snap.total_nav_usd - subscribed + paid_out
        return {
            "subscribed_usd": f(money(subscribed)),
            "paid_out_usd": f(money(paid_out)),
            "pnl_usd": f(money(pnl)),
            "return_pct": f((snap.nav_per_unit / BASE_NAV_PER_UNIT - 1) * 100),
        }

    def latest(self) -> Optional[dict[str, Any]]:
        struck = self._struck(limit=1)
        return struck[-1] if struck else None

    def history(self, limit: int = 90) -> list[dict[str, Any]]:
        """Recent struck snapshots, oldest first — for value/NAV trend charts."""
        return self._struck(limit=limit)

    def _struck(self, limit: int) -> list[dict[str, Any]]:
        """Struck snapshots, folded from the event log, oldest first.

        These used to be read from the nav_snapshots collection, which is a
        SECOND copy of something strike() already wrote to the log as a
        NAV_STRUCK event. Two copies of one fact is one too many: the
        collection could be missing a strike the log has, and the page would
        show a stale NAV that nothing in the system could explain.

        Reading the log instead also means the NAV endpoint stops depending on
        Firestore entirely — which is what made it fail while the event log had
        already moved to Postgres and was perfectly healthy.
        """
        rows = [
            e.get("payload") or {}
            for e in self._store.stream(since_seq=0, limit=100_000)
            if e.get("type") == EventType.NAV_STRUCK.value
        ]
        return rows[-limit:] if limit else rows
