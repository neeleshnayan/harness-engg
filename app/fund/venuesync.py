"""Bringing the book into agreement with the venue — BY APPENDING.

CEO instruction, 2026-08-21, verbatim: *"alpaca paper would sync to what I can
see on my alpaca screen [if there is no strategy tracking it then its okay
too]"*.

THE ONE NON-NEGOTIABLE THAT HAS NEVER BENT IN THIS FUND'S HISTORY: *"NAV folds
from the event log only; broker equity is a comparison, never the truth."*
That instruction and that rule are reconcilable, and the distinction is the
whole design of this module. We do NOT read broker equity as NAV. We append a
reconciling event, with a stated basis, such that THE FOLD PRODUCES THE
MATCHING ANSWER. The history stays reconstructible; a reader can re-derive the
delta from the payload without trusting a note.

(A prior change did the forbidden version — ``NavService.compute()`` returned
live Alpaca equity AS the NAV, with a hardcoded units_outstanding fallback that
destroyed the unit ledger. It was reverted in f0b18c9. ``Reconciler.drift()``
is the honest read-only version of the same idea; this module is the honest
WRITE version.)

WHY THE BOOKS DISAGREE, measured rather than assumed (2026-08-22):

    book   cash   968.69 + positions 917.06 = NAV 1885.74
                  SPY 0.346119, DBC 8.122157, TLT 3.019871, DBA 5.314306
    broker cash   846.84 + positions 1166.42 = equity 2013.26
                  SPY 0.217757, GLD 0.424471, INTC 1.608762, MSFT 0.340051,
                  NVDA 0.749886, SOFI 9.188190, XLE 2.749912

Every fill on the Alpaca account is 13-14 August and nothing since; the
broker's numbers are internally perfect against its own order history (checked
three: INTC 6.70 bought − 5.091238 sold = 1.608762; SOFI 16 − 6.81181 =
9.18819; SPY 0.269789 − 0.052032 = 0.217757). The broker is not wrong. It is
recording a different fund: the sleeve's orders since then went to the
PaperConnector, so the book kept moving while the broker stayed a photograph.

WHY THIS IS NOT A TRADE, AND MUST NOT BE RECORDED AS ONE. The obvious
implementation — append compensating SELLs for what the broker does not hold —
would book realised P&L on a sale that never happened, credit cash that nobody
received, and put a fabricated execution into the cost model. Nothing was
bought and nothing was sold here. The book was ALIGNED, once, deliberately, to
a reading of the venue. So this emits its own event type
(``BookReconciledToVenue``), the folds treat it as an alignment rather than a
fill, and the P&L reader can subtract it — because a NAV step of $127 for a
bookkeeping reason must never be readable as return.

THE CLEAN FIELD RULE'S FIVE GUARD RAILS, and where each one lives:

  1. *The cause is fixed first.* The cause is the tangled mode flag, fixed in
     ``app/fund/mode.py`` in the same diff: the sleeve's orders went to the
     simulator because the venue was selected by omission.
  2. *The contaminated value is PRESERVED beside the new one.* Every payload
     carries ``book_*_before`` alongside the venue reading. Nothing is erased;
     ``since_inception`` reports the reconciliation total separately forever.
  3. *The magnitude is MEASURED, not estimated.* Every number in the payload
     comes from a broker round trip or the fold, at a recorded timestamp. This
     module NEVER computes a plug figure to make a total balance.
  4. *Direction is enforced in code where the shape allows it.* It does not
     here — a reconciliation can legitimately move NAV either way — so the
     protection is that the magnitude is derived from two readings and can be
     re-derived from the payload, not chosen.
  5. *A human decides and the record says who, why and when.* ``apply`` refuses
     without an actor and a reason, and the endpoint that calls it is behind
     the approval-channel guard.

SUPERSEDES the PM's R18 fence-the-cohort recommendation: the CEO chose to
reconcile rather than fence, and the two must not coexist in the record.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable, Optional

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money
from app.fund.projections.strategy import DISCRETIONARY

#: Below this a quantity difference is float noise, not a divergence. Matches
#: the reconciler's own tolerance so the two instruments agree about what
#: "in sync" means.
QTY_TOLERANCE = Decimal("1e-6")


class VenueSyncError(RuntimeError):
    """The reconciliation cannot be planned or applied honestly."""


@dataclass
class SymbolAlignment:
    symbol: str
    book_qty: Decimal
    venue_qty: Decimal
    venue_avg_price: Optional[Decimal]
    #: Which strategy ledgers currently carry this symbol, and at what cost.
    #: Recorded so a removal comes out of the ledger it went into, rather than
    #: out of "discretionary" by default — which would leave a strategy holding
    #: a position the book no longer has.
    holders: list[dict[str, Any]] = field(default_factory=list)
    #: The mark used to value the change. Absent when no price could be read —
    #: reported absent, never defaulted, and it makes the whole plan refuse.
    mark: Optional[Decimal] = None

    @property
    def delta_qty(self) -> Decimal:
        return self.venue_qty - self.book_qty

    @property
    def in_sync(self) -> bool:
        return abs(self.delta_qty) < QTY_TOLERANCE

    @property
    def direction(self) -> str:
        if self.in_sync:
            return "in_sync"
        return "adopt" if self.delta_qty > 0 else "release"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "book_qty": f(self.book_qty),
            "venue_qty": f(self.venue_qty),
            "delta_qty": f(self.delta_qty),
            "direction": self.direction,
            "venue_avg_price": f(self.venue_avg_price) if self.venue_avg_price is not None else None,
            "mark": f(self.mark) if self.mark is not None else None,
            "value_delta_usd": (f(money(self.delta_qty * self.mark))
                                if self.mark is not None else None),
            "holders": [{"strategy_id": h["strategy_id"], "qty": f(h["qty"]),
                         "cost_usd": f(h["cost"])} for h in self.holders],
        }


@dataclass
class SyncPlan:
    run_id: str
    basis: dict[str, Any]
    alignments: list[SymbolAlignment]
    book_cash: Decimal
    venue_cash: Decimal
    book_nav_before: Decimal
    venue_equity: Decimal

    @property
    def moving(self) -> list[SymbolAlignment]:
        return [a for a in self.alignments if not a.in_sync]

    @property
    def cash_delta(self) -> Decimal:
        return self.venue_cash - self.book_cash

    @property
    def adopted_unmanaged(self) -> list[SymbolAlignment]:
        """Positions entering the book that no strategy owns.

        The CEO accepted these explicitly (*"if there is no strategy tracking
        it then its okay too"*), which is why they are ADOPTED rather than
        refused — and why they are named here rather than folded in quietly.
        Exit coverage must be able to report them as uncovered.
        """
        return [a for a in self.moving
                if a.direction == "adopt" and not a.holders]

    def projected_nav(self) -> Decimal:
        """What the FOLD will produce after this event. Not the broker's number.

        Deliberately computed from the fund's OWN marks, so the difference
        against broker equity survives the reconciliation and stays visible.
        The two will not agree to the cent, and pretending otherwise is exactly
        the "read broker equity as NAV" move this module exists to avoid.
        """
        positions = sum(
            (a.venue_qty * a.mark for a in self.alignments if a.mark is not None),
            Decimal("0"))
        return money(self.venue_cash + positions)

    def to_payload(self) -> dict[str, Any]:
        """The event body. Everything needed to re-derive the delta."""
        return {
            "run_id": self.run_id,
            "basis": self.basis,
            "positions": [a.to_dict() for a in self.alignments if not a.in_sync],
            "positions_already_in_sync": [a.symbol for a in self.alignments
                                          if a.in_sync],
            "cash": {
                "book_before_usd": f(money(self.book_cash)),
                "venue_usd": f(money(self.venue_cash)),
                "delta_usd": f(money(self.cash_delta)),
            },
            "nav": {
                "book_before_usd": f(money(self.book_nav_before)),
                "venue_equity_usd": f(money(self.venue_equity)),
                "delta_vs_venue_usd": f(money(self.venue_equity - self.book_nav_before)),
                # The number that will actually appear, from the fund's own
                # marks. Recorded at plan time so a later reader can see
                # whether the fold did what the plan said it would.
                "projected_book_after_usd": f(self.projected_nav()),
                "projected_step_usd": f(money(self.projected_nav() - self.book_nav_before)),
            },
            "unmanaged_after": [a.symbol for a in self.adopted_unmanaged],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.to_payload(),
            "symbols_moving": len(self.moving),
            "note": ("this is a PLAN and writes nothing; applying it appends "
                     "one BookReconciledToVenue event"),
        }


def plan(connector: Any, store: EventStore, nav_service: Any,
         attribution: Any, pricer: Optional[Callable[[str], float]] = None,
         ) -> SyncPlan:
    """Read both sides and say exactly what applying would write. Writes nothing.

    Refuses rather than guesses on every absence: an unreadable broker, a
    missing cash figure, or a symbol with no mark all raise. A reconciliation
    computed against a partial reading would move NAV by a number nobody
    measured, which is the one thing the clean-field rule forbids outright.
    """
    if not hasattr(connector, "account_info"):
        raise VenueSyncError(
            f"connector {getattr(connector, 'name', '?')!r} has no account to "
            "reconcile against — a simulated venue is not a second opinion")
    info = connector.account_info() or {}
    if not info.get("configured"):
        raise VenueSyncError(
            f"the venue is not configured: {info.get('message') or 'no reason given'}")
    for key in ("cash", "equity"):
        if info.get(key) is None:
            raise VenueSyncError(
                f"the venue reading has no {key!r}. Unreadable is not zero, and "
                "a reconciliation against a missing number is a fabricated one.")

    venue_positions = {str(p.symbol).upper(): D(str(p.qty)) for p in connector.positions()}
    venue_costs = {str(p.symbol).upper(): D(str(p.avg_price))
                   for p in connector.positions()}

    snap = nav_service.compute()
    book_positions = {str(p["symbol"]).upper(): D(str(p["qty"]))
                      for p in (snap.positions or [])}
    book_marks = {str(p["symbol"]).upper(): D(str(p["mark"]))
                  for p in (snap.positions or [])}
    book_cash = D(snap.breakdown.get("cash", 0))

    # Which strategy ledgers hold what, so a release comes out of the right one.
    holders_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for sid, rec in _attribution_rows(attribution).items():
        for sym, pos in (rec.get("positions") or {}).items():
            qty = D(pos.get("qty", 0))
            if abs(qty) < QTY_TOLERANCE:
                continue
            holders_by_symbol.setdefault(str(sym).upper(), []).append(
                {"strategy_id": sid, "qty": qty, "cost": D(pos.get("cost", 0))})

    price = pricer or getattr(connector, "price", None)
    alignments: list[SymbolAlignment] = []
    unpriced: list[str] = []
    for symbol in sorted(set(book_positions) | set(venue_positions)):
        mark = book_marks.get(symbol)
        if mark is None and price is not None:
            try:
                got = price(symbol)
                mark = D(str(got)) if got else None
            except Exception:  # noqa: BLE001 — reported, never defaulted
                mark = None
        if mark is None:
            unpriced.append(symbol)
        alignments.append(SymbolAlignment(
            symbol=symbol,
            book_qty=book_positions.get(symbol, Decimal("0")),
            venue_qty=venue_positions.get(symbol, Decimal("0")),
            venue_avg_price=venue_costs.get(symbol),
            holders=holders_by_symbol.get(symbol, []),
            mark=mark,
        ))
    if unpriced:
        raise VenueSyncError(
            f"no mark could be read for {unpriced} — refusing to plan a "
            "reconciliation whose NAV effect cannot be measured. A $100.00 "
            "default here once sold a real position.")

    at = datetime.now(timezone.utc).isoformat()
    max_seq = 0
    seq = 0
    while True:
        batch = store.stream(since_seq=seq, limit=1000)
        if not batch:
            break
        seq = max(e.get("seq") or seq for e in batch)
        max_seq = max(max_seq, seq)
        if len(batch) < 1000:
            break

    return SyncPlan(
        run_id=str(uuid.uuid4()),
        basis={
            "venue": getattr(connector, "name", "unknown"),
            "venue_mode": info.get("mode"),
            "venue_read_at": at,
            "venue_equity_usd": f(money(D(str(info["equity"])))),
            "venue_cash_usd": f(money(D(str(info["cash"])))),
            "venue_position_count": len(venue_positions),
            "book_fold_seq": max_seq,
            "book_nav_struck_at": getattr(snap, "ts", None),
            "marks_from": "the fund's own pricer, not the venue's",
            "method": ("positions and cash SET TO the venue's own reading; "
                       "NAV is then re-folded from the log at the fund's marks, "
                       "never read off broker equity"),
        },
        alignments=alignments,
        book_cash=book_cash,
        venue_cash=D(str(info["cash"])),
        book_nav_before=D(snap.total_nav_usd),
        venue_equity=D(str(info["equity"])),
    )


def _attribution_rows(attribution: Any) -> dict[str, dict[str, Any]]:
    """Per-strategy raw positions, whatever shape the projection offers."""
    for name in ("raw", "_build"):
        fn = getattr(attribution, name, None)
        if callable(fn):
            try:
                return fn() or {}
            except Exception:  # noqa: BLE001
                continue
    return {}


def apply(store: EventStore, sync_plan: SyncPlan, actor: str, reason: str
          ) -> dict[str, Any]:
    """Append the ONE reconciling event. Idempotent by run_id.

    A human decides and the record says who, why and when — guard rail 5, and
    it is enforced here rather than only at the endpoint, because a service
    that can be called without a reason will eventually be.
    """
    actor = (actor or "").strip()
    reason = (reason or "").strip()
    if not actor:
        raise VenueSyncError("a reconciliation must name who decided it")
    if not reason:
        raise VenueSyncError(
            "a reconciliation must carry a written reason. NAV moves for a "
            "non-market reason here; an unexplained move is indistinguishable "
            "from an unauthorised one.")
    if not sync_plan.moving and abs(sync_plan.cash_delta) < Decimal("0.005"):
        return {"applied": False, "note": "book and venue already agree",
                "run_id": sync_plan.run_id}

    already = {e.get("payload", {}).get("run_id")
               for e in store.by_aggregate(sync_plan.run_id)}
    if sync_plan.run_id in already:
        return {"applied": False, "note": "already applied",
                "run_id": sync_plan.run_id}

    payload = {**sync_plan.to_payload(), "actor": actor, "reason": reason,
               "supersedes": "PM R18 (fence the cohort) — the CEO chose to "
                             "reconcile rather than fence, 2026-08-21"}
    store.append(Event(
        aggregate_id=sync_plan.run_id,
        aggregate_type="fund",
        type=EventType.BOOK_RECONCILED_TO_VENUE,
        payload=payload,
        actor=actor,
    ))
    return {"applied": True, "run_id": sync_plan.run_id, "event": payload}
