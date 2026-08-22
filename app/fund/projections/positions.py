"""Positions + cash + units projection — a fold over the event log.

This is a read model: it holds no truth of its own, it *derives* the fund's
book by replaying events. Rebuildable from scratch at any time by re-folding
``fund_events``. The reconciler (Step 2) compares this event-sourced book
against each connector's ``positions()`` / ``balances()`` (venue truth) and
emits ``ReconciliationMismatch`` on drift.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.fund.events import EventStore, EventType
from app.fund.money import D

_ZERO = Decimal("0")

#: Quantity noise floor. PRESERVED from the inline ``Decimal("1e-9")`` this
#: logic already used, and equal to ``autopolicy.POSITION_EPS`` (1e-9) — not to
#: ``reconcile._TOL``, which is 1e-6 and answers a different question (how far
#: the BROKER may disagree with us, versus how small a leftover counts as
#: closed). Named so the two are not silently assumed to be the same number.
#:
#: MEASURED 2026-08-23, because the first version of this comment asserted a
#: residue from memory and the measurement disproved it: folding all 978 live
#: events through this projection leaves seven closed symbols at EXACTLY zero
#: and four open. Decimal arithmetic here is exact, so the ~1e-15 dust seen
#: when the same fills are folded in floats does not arise.
#:
#: The epsilon is kept anyway, and deliberately: a corporate action divides
#: quantities, ``BookReconciledToVenue`` SETS them from a broker string, and
#: either can produce a value that is not exactly zero. Treating a 1e-15 ghost
#: as an open position would weighted-average the next fill against it.
_QTY_EPS = Decimal("1e-9")


def _new_avg_price(old_qty: Decimal, old_avg: Decimal,
                   signed: Decimal, px: Decimal, new_qty: Decimal) -> Decimal:
    """The cost basis after a fill, for a position of EITHER sign.

    THE SHORT'S COST BASIS (desk 34338ef6, fixed 2026-08-23). This logic was
    one line — ``if signed > 0 and abs(new_qty) > 1e-9`` — which asks "was this
    a BUY", and a buy is not the same question as "did this position grow".
    Measured against the four cases a signed book actually has, it was wrong in
    three of them:

      * long 10 @ 100, SELL 20 @ 110  -> flips to short 10, basis stayed 100.
        The true basis of the new short is 110, so the position was born
        reporting a 10% gain it never made.
      * short 10 @ 100, SELL 10 @ 90  -> short grows to 20, basis stayed 100
        instead of averaging to 95. Adding to a short did not move its basis
        at all, because adding to a short is a SELL.
      * short 10 @ 100, BUY 5 @ 90    -> covering half. ``signed > 0`` fired,
        and the weighted-average line ran with a NEGATIVE denominator:
        (-10*100 + 5*90) / -5 = 110. Reducing a position CORRUPTED the basis of
        the part still open, and did it in the profitable-looking direction.

    Together with the sign-blind P&L formula in riskmonitor, that is why every
    exit rule on a short would have been inverted, and why this is the gating
    condition on any short-selling strategy.

    The four cases, which are the standard treatment and not an invention:

      1. OPENING or ADDING (same sign, or from flat) — weighted average.
      2. REDUCING (opposite sign, not through zero) — basis UNCHANGED. Closing
         part of a position realises P&L; it does not re-price what remains.
      3. CROSSING ZERO — the old position is fully closed and a new one opens
         in the other direction at this fill's price. Basis is ``px``.
      4. FLAT (new_qty ~ 0) — basis UNCHANGED rather than zeroed, so a closed
         symbol keeps a readable last basis instead of a 0.00 that the P&L
         formula's ``avg_cost <= 0`` branch would silently read as "unknown".

    Pure and total: every path returns a Decimal, and no path divides by a
    denominator it has not first checked against ``_QTY_EPS``.
    """
    # 4 — flat. Nothing to price.
    if abs(new_qty) <= _QTY_EPS:
        return old_avg
    # 1 — from flat, in either direction. This fill IS the basis.
    if abs(old_qty) <= _QTY_EPS:
        return px
    same_direction = (old_qty > 0) == (signed > 0)
    # 1 — adding to an existing position, long or short. The weighted average
    # is over MAGNITUDES, so it is the same arithmetic on both sides of zero;
    # written with abs() rather than relying on two negatives cancelling,
    # because relying on that is what produced case 3's silent corruption.
    if same_direction:
        return ((abs(old_qty) * old_avg + abs(signed) * px)
                / (abs(old_qty) + abs(signed)))
    # 3 — the fill was larger than the position and flipped it. Whatever was
    # there is closed; what is left was opened at this price.
    if (old_qty > 0) != (new_qty > 0):
        return px
    # 2 — reducing, still on the same side. The basis does not move.
    return old_avg


@dataclass
class Book:
    cash: Decimal = field(default_factory=lambda: Decimal("0"))          # USD, idle
    units_outstanding: Decimal = field(default_factory=lambda: Decimal("0"))
    positions: dict[str, dict[str, Decimal]] = field(default_factory=dict)  # symbol -> {qty, avg_price}


class PositionsProjection:
    def __init__(self, store: EventStore | None = None, snapshots: Any = None,
                 snapshot_every: int = 50):
        self._store = store or EventStore()
        self._snapshots = snapshots
        # a snapshot costs a write, so only take one once enough new events
        # have accumulated to pay for it on the next read
        self._snapshot_every = snapshot_every

    def build(self) -> Book:
        """Fold the book. With a snapshot store this reads only the events since
        the last snapshot; without one it folds the whole log exactly as before.
        The event log stays authoritative — a snapshot is a cache."""
        if self._snapshots is None:
            book = Book()
            for e in self._store.stream(since_seq=0, limit=100_000):
                self._apply(book, e)
            return book

        from app.fund.snapshots import SnapshottedFold

        return SnapshottedFold(
            "positions", self._store, self._snapshots, every=self._snapshot_every
        ).fold(
            empty=Book,
            apply=self._apply,
            to_state=self._to_state,
            from_state=self._from_state,
        )

    @staticmethod
    def _to_state(book: Book) -> dict[str, Any]:
        return {
            "cash": book.cash,
            "units_outstanding": book.units_outstanding,
            "positions": book.positions,
        }

    @staticmethod
    def _from_state(state: dict[str, Any]) -> Book:
        return Book(
            cash=state.get("cash", _ZERO),
            units_outstanding=state.get("units_outstanding", _ZERO),
            positions=state.get("positions", {}) or {},
        )

    @staticmethod
    def _apply(book: Book, e: dict[str, Any]) -> None:
        etype = e.get("type")
        p = e.get("payload", {})

        if etype == EventType.ORDER_FILLED.value:
            symbol = p["symbol"]
            side = p.get("side", "buy")
            qty = D(p.get("filled_qty", p.get("qty", 0)))
            px = D(p["avg_price"])
            signed = qty if side == "buy" else -qty
            pos = book.positions.get(symbol, {"qty": _ZERO, "avg_price": px})
            old_qty = pos["qty"]
            new_qty = old_qty + signed
            pos["avg_price"] = _new_avg_price(old_qty, pos["avg_price"],
                                              signed, px, new_qty)
            pos["qty"] = new_qty
            book.positions[symbol] = pos
            book.cash -= signed * px + D(p.get("fees", 0))

        elif etype in (EventType.DIVIDEND_RECEIVED.value,
                       EventType.INTEREST_RECEIVED.value):
            # Cash the fund earned without trading. It is NOT a subscription:
            # it changes NAV per unit (it is performance) whereas a subscription
            # changes NAV and units together and is not.
            book.cash += D(p.get("usd_amount", p.get("amount", 0)))

        elif etype == EventType.CORPORATE_ACTION_APPLIED.value:
            # A split changes the share count and the average price by the same
            # ratio, so the position's VALUE and cost basis are untouched. Only
            # the units it is expressed in change.
            symbol = p["symbol"]
            pos = book.positions.get(symbol)
            if pos is not None:
                old_qty, new_qty = D(p["old_qty"]), D(p["new_qty"])
                if old_qty != 0:
                    ratio = new_qty / old_qty
                    if ratio != 0:
                        pos["avg_price"] = pos["avg_price"] / ratio
                    pos["qty"] = new_qty
                    book.positions[symbol] = pos

        elif etype == EventType.BOOK_RECONCILED_TO_VENUE.value:
            # The book aligned to a reading of the venue. NOT a trade: nothing
            # was bought and nothing was sold, so no realised P&L is booked and
            # no fill enters the cost model. Quantities and cash are SET to the
            # venue's own numbers, and the payload carries both sides so the
            # move can be re-derived by anyone reading the log.
            #
            # Applied as an absolute SET rather than a delta, deliberately.
            # A delta re-applied — a replay, a double-append, a migration —
            # would move the book twice; setting to a recorded target is
            # idempotent under the fold, which is the property that matters in
            # an append-only log where nothing can be taken back.
            for row in (p.get("positions") or []):
                symbol = row.get("symbol")
                if not symbol:
                    continue
                target = D(row.get("venue_qty", 0))
                if abs(target) < Decimal("1e-9"):
                    book.positions.pop(symbol, None)
                    continue
                pos = book.positions.get(symbol)
                # Cost basis for an adopted position is the venue's own average
                # entry price. Absent (the venue did not say), the mark is used
                # and the payload records which — never a fabricated number.
                basis = row.get("venue_avg_price") or row.get("mark")
                pos = pos or {"qty": _ZERO,
                              "avg_price": D(basis) if basis is not None else _ZERO}
                if pos["qty"] == _ZERO and basis is not None:
                    pos["avg_price"] = D(basis)
                pos["qty"] = target
                book.positions[symbol] = pos
            cash = (p.get("cash") or {}).get("venue_usd")
            if cash is not None:
                book.cash = D(cash)

        elif etype == EventType.CASH_CONFIRMED.value:
            book.cash += D(p.get("usd_amount", p.get("amount", 0)))

        elif etype == EventType.PAYOUT_SENT.value:
            book.cash -= D(p["usd_amount"])

        elif etype == EventType.UNITS_ISSUED.value:
            book.units_outstanding += D(p["units"])

        elif etype == EventType.UNITS_BURNED.value:
            book.units_outstanding -= D(p["units"])
