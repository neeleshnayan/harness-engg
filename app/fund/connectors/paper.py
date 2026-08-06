"""Paper connector — a fully in-Firestore simulation of a venue.

Lets the whole spine run end-to-end (command -> approval -> execute -> fill ->
events -> NAV) with no live account and no real money. In Step 2 the
``IBKRConnector`` implements the same ``Connector`` protocol and slots in
exactly where this sits; nothing upstream changes.

Idempotency is real even here: ``execute()`` keys submitted orders by
``idempotency_key`` and returns the existing ``VenueRef`` on replay instead of
placing a second order — the behaviour every venue must guarantee.
"""

from __future__ import annotations

import uuid

from firebase_admin import firestore

from app.fund.connectors.base import (
    Balance,
    Connector,
    ExecStatus,
    FillState,
    Order,
    Position,
    Quote,
    Side,
    ValidationResult,
    VenueRef,
)

_ORDERS = "fund_paper_orders"     # idempotency_key -> submitted order + fill
_BOOK = "fund_paper_book"         # venue truth: positions + cash (for reconciliation)
_BOOK_DOC = "current"

# Seed marks for the paper venue. Phase 2 replaces this with a real oracle.
_SEED_PRICES = {
    "AAPL": 220.0,
    "MSFT": 430.0,
    "SPY": 560.0,
    "NVDA": 120.0,
    "USDC": 1.0,
    "USD": 1.0,
}
_DEFAULT_PRICE = 100.0


class PaperConnector(Connector):
    name = "paper"

    def __init__(self, db=None, prices: dict[str, float] | None = None):
        self._db = db or firestore.client()
        self._prices = {**_SEED_PRICES, **(prices or {})}

    # --- pricing -----------------------------------------------------------
    def price(self, symbol: str) -> float:
        return self._prices.get(symbol.upper(), _DEFAULT_PRICE)

    def quote(self, order: Order) -> Quote:
        px = order.limit_price or self.price(order.symbol)
        return Quote(symbol=order.symbol, price=px, est_slippage_bps=2.0, est_fees=0.0)

    def validate(self, order: Order) -> ValidationResult:
        errors: list[str] = []
        if order.qty <= 0:
            errors.append("qty must be positive")
        if order.symbol.strip() == "":
            errors.append("symbol required")
        return ValidationResult(ok=not errors, errors=errors)

    # --- execution ---------------------------------------------------------
    def execute(self, order: Order, idempotency_key: str) -> VenueRef:
        ref_doc = self._db.collection(_ORDERS).document(idempotency_key)
        existing = ref_doc.get()
        if existing.exists:
            # Replay: return the same handle, do NOT place a second order.
            return VenueRef(venue=self.name, ref_id=existing.to_dict()["ref_id"])

        px = self.quote(order).price
        ref_id = str(uuid.uuid4())
        ref_doc.set(
            {
                "ref_id": ref_id,
                "symbol": order.symbol,
                "side": order.side.value,
                "qty": order.qty,
                "avg_price": px,
                "fees": 0.0,
                "state": FillState.FILLED.value,  # paper fills instantly
            }
        )
        self._apply_to_book(order, px)
        return VenueRef(venue=self.name, ref_id=ref_id)

    def poll(self, ref: VenueRef) -> ExecStatus:
        # Paper orders settle instantly; find the record by ref_id.
        q = self._db.collection(_ORDERS).where("ref_id", "==", ref.ref_id).limit(1).stream()
        rec = next((d.to_dict() for d in q), None)
        if rec is None:
            return ExecStatus(state=FillState.FAILED, reason="unknown ref")
        return ExecStatus(
            state=FillState(rec["state"]),
            filled_qty=rec["qty"],
            avg_price=rec["avg_price"],
            fees=rec["fees"],
        )

    # --- venue truth (for the reconciler) ----------------------------------
    def _book(self) -> dict:
        snap = self._db.collection(_BOOK).document(_BOOK_DOC).get()
        return snap.to_dict() if snap.exists else {"cash": 0.0, "positions": {}}

    def _apply_to_book(self, order: Order, px: float) -> None:
        book = self._book()
        positions = book.get("positions", {})
        signed = order.qty if order.side == Side.BUY else -order.qty
        pos = positions.get(order.symbol, {"qty": 0.0, "avg_price": px})
        new_qty = pos["qty"] + signed
        # Simple average-cost accounting; refine when real fills arrive.
        if signed > 0 and new_qty != 0:
            pos["avg_price"] = (pos["qty"] * pos["avg_price"] + signed * px) / new_qty
        pos["qty"] = new_qty
        positions[order.symbol] = pos
        book["positions"] = positions
        book["cash"] = book.get("cash", 0.0) - signed * px
        self._db.collection(_BOOK).document(_BOOK_DOC).set(book)

    def positions(self) -> list[Position]:
        book = self._book()
        return [
            Position(venue=self.name, symbol=s, qty=p["qty"], avg_price=p["avg_price"])
            for s, p in book.get("positions", {}).items()
            if abs(p["qty"]) > 1e-9
        ]

    def balances(self) -> list[Balance]:
        return [Balance(venue=self.name, asset="USD", amount=self._book().get("cash", 0.0))]
