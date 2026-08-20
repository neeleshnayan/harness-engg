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


class PriceUnavailable(ValueError):
    """No real price exists for this symbol right now.

    A ValueError subclass so existing per-symbol guards (correlation, risk
    monitor) catch it and degrade to a NAMED absence. It replaces the
    `_DEFAULT_PRICE = 100.0` fallback removed 2026-08-20 after the fund's
    first auto-approval fired on it: a transient feed miss on GLD returned
    the fabricated $100.00, the risk monitor marked a +2.9% position as
    "down -75.14%", the machinery-test 25% loss rule fired, the auto-policy
    approved the exit (every envelope check passed — the input was the lie),
    the fill executed at the same $100.00, and the real $133 ledger loss
    tripped the daily-loss halt. Every control worked; the price was
    fabricated. "An absent number is reported absent" is the fund's first
    non-negotiable, and a hardcoded default price violates it at the exact
    point every mark in the system is born.
    """


class PaperConnector(Connector):
    name = "paper"

    def __init__(self, db=None, prices: dict[str, float] | None = None, live_pricer=None):
        from app.core.firebase import db as _fs_db
        self._db = db or _fs_db()
        self._prices = {**_SEED_PRICES, **(prices or {})}
        # Optional callable(symbol)->float|None for live free marks. When set,
        # positions/NAV are marked at real market levels. A miss FALLS BACK to
        # an explicitly seeded price only — a seed is a chosen number; a
        # catch-all default was a fabricated one, and it cost real (paper) money.
        self._live_pricer = live_pricer

    # --- pricing -----------------------------------------------------------
    def price(self, symbol: str) -> float:
        if self._live_pricer is not None:
            try:
                px = self._live_pricer(symbol)
                if px and px > 0:
                    return float(px)
            except Exception:  # noqa: BLE001 — never let pricing take the venue down
                pass
        seeded = self._prices.get(symbol.upper())
        if seeded is not None:
            return seeded
        raise PriceUnavailable(
            f"no price available for {symbol} — the paper venue refuses to "
            f"fabricate one (a $100.00 default here once sold a real position)")

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

        try:
            px = self.quote(order).price
        except PriceUnavailable as e:
            # An order must NEVER fill at a number nobody quoted. The order
            # fails, the book is untouched, and the reason is on the record —
            # a failed order is recoverable; a fill at a fabricated price is a
            # realised loss (measured: -$133.21, 2026-08-20).
            ref_id = str(uuid.uuid4())
            record = {
                "ref_id": ref_id, "symbol": order.symbol,
                "side": order.side.value, "qty": order.qty,
                "avg_price": None, "fees": 0.0,
                "state": FillState.FAILED.value, "reason": str(e),
            }
            ref_doc.set(record)
            self._db.collection(_ORDERS).document(ref_id).set(record)
            return VenueRef(venue=self.name, ref_id=ref_id)

        ref_id = str(uuid.uuid4())
        record = {
            "ref_id": ref_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "qty": order.qty,
            "avg_price": px,
            "fees": 0.0,
            "state": FillState.FILLED.value,  # paper fills instantly
        }
        ref_doc.set(record)  # keyed by idempotency_key -> replay guard
        # Also key the record by ref_id so poll() is a deterministic *document*
        # read. The old where("ref_id"==) field query returned inconsistently on
        # real Firestore, leaving paper orders stuck at 'working'.
        self._db.collection(_ORDERS).document(ref_id).set(record)
        self._apply_to_book(order, px)
        return VenueRef(venue=self.name, ref_id=ref_id)

    def poll(self, ref: VenueRef) -> ExecStatus:
        # Paper orders settle instantly; read the record directly by ref_id.
        snap = self._db.collection(_ORDERS).document(ref.ref_id).get()
        rec = snap.to_dict() if snap.exists else None
        if rec is None:
            return ExecStatus(state=FillState.FAILED, reason="unknown ref")
        return ExecStatus(
            state=FillState(rec["state"]),
            filled_qty=rec["qty"] if rec["state"] == FillState.FILLED.value else 0.0,
            avg_price=rec["avg_price"],
            fees=rec["fees"],
            reason=rec.get("reason"),
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
