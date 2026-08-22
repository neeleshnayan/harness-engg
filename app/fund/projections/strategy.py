"""Per-strategy attribution — a fold over tagged fills.

For each ``strategy_id`` (``None`` → "discretionary") accumulates net position
per symbol and net invested (signed notional + fees). Valued at current marks:

    exposure   = Σ qty × mark
    realized   = Σ over closes of qty × (price − average cost)   [average-cost basis]
                 — a sale closing a long, or a buy covering a short (sign flipped)
    unrealized = exposure − cost basis of the open position
    pnl        = realized + unrealized

This is what the cockpit renders per strategy, and — joined with the registry's
target allocation and the fund NAV — gives target-vs-actual weight. Forensics is
the same fold filtered to one ``strategy_id`` over a time window.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money

DISCRETIONARY = "discretionary"


class AttributionCorrectionError(ValueError):
    """A proposed correction is not one — refused before it reaches the log."""


def append_attribution_correction(
    store: EventStore, *, symbol: str, qty: Any, cost_usd: Any,
    from_strategy_id: str, to_strategy_id: str, reason: str, actor: str,
    realized_usd: Any = 0, net_invested_usd: Any = 0,
) -> dict[str, Any]:
    """Record a ``StrategyAttributionCorrected`` — the ONLY way to repair a mistag.

    The log is append-only, so a fill tagged to the wrong strategy is never
    edited; it is compensated by this event, which is itself permanent and
    attributed. Validation is here rather than in the fold because a bad
    correction that reaches the log is a permanent bad fact, and the fold's
    job is to be honest about what it finds, not to launder it.

    Deliberately NOT exposed as an HTTP endpoint. The event moves nothing but
    an index, but it moves what every downstream money path (the rebalance
    composition above all) reads as truth — so it is fired by a human hand at
    the console with a written reason, not by anything that can be called.
    """
    reason = (reason or "").strip()
    if not reason:
        raise AttributionCorrectionError(
            "a correction must carry a written reason naming the mistagged "
            "fill — an unexplained correction is indistinguishable from an "
            "unauthorised one and the fold will ignore it"
        )
    if not from_strategy_id or not to_strategy_id:
        raise AttributionCorrectionError("both source and destination strategy are required")
    if from_strategy_id == to_strategy_id:
        raise AttributionCorrectionError(
            f"{from_strategy_id} is both source and destination — that is a no-op, not a repair"
        )
    if not symbol:
        raise AttributionCorrectionError("a correction must name the symbol it moves")
    payload = {
        "symbol": str(symbol).upper(),
        "qty": f(D(qty)),
        "cost_usd": f(D(cost_usd)),
        "realized_usd": f(D(realized_usd)),
        "net_invested_usd": f(D(net_invested_usd)),
        "from_strategy_id": from_strategy_id,
        "to_strategy_id": to_strategy_id,
        "reason": reason,
    }
    store.append(Event(
        aggregate_id=to_strategy_id, aggregate_type="strategy",
        type=EventType.STRATEGY_ATTRIBUTION_CORRECTED, payload=payload, actor=actor,
    ))
    return payload


class StrategyAttribution:
    def __init__(self, store: EventStore | None = None, snapshots: Any = None,
                 snapshot_every: int = 50):
        self._store = store or EventStore()
        self._snapshots = snapshots
        self._snapshot_every = snapshot_every

    def _build(self) -> dict[str, dict[str, Any]]:
        """Fold fills into per-strategy positions, cost basis and realized P&L.

        Average-cost accounting: a close realizes ``qty × (price − average cost)``
        and retires that share of the basis — a sale against a long, or a buy
        against a short, where the sign flips. What remains in ``cost`` is the
        basis of the open position, so unrealized P&L is ``mark value − cost``.
        """
        strats: dict[str, dict[str, Any]] = {}

        if self._snapshots is not None:
            from app.fund.snapshots import SnapshottedFold

            return SnapshottedFold(
                "attribution", self._store, self._snapshots, every=self._snapshot_every
            ).fold(
                empty=dict,
                apply=self._apply,
                to_state=lambda a: a,
                from_state=lambda st: dict(st or {}),
            )

        for e in self._store.stream(since_seq=0, limit=100_000):
            self._apply(strats, e)

        return strats

    @classmethod
    def _apply(cls, strats: dict[str, dict[str, Any]], e: dict[str, Any]) -> None:
        """Fold one fill into per-strategy positions, cost basis and realized P&L."""
        def s(key: str) -> dict[str, Any]:
            return strats.setdefault(
                key,
                {
                    "strategy_id": key,
                    "net_invested": Decimal("0"),
                    "realized": Decimal("0"),
                    "positions": {},
                },
            )

        if e.get("type") == EventType.STRATEGY_ATTRIBUTION_CORRECTED.value:
            cls._apply_correction(s, e.get("payload", {}) or {})
            return

        if e.get("type") == EventType.BOOK_RECONCILED_TO_VENUE.value:
            cls._apply_venue_reconciliation(s, e.get("payload", {}) or {})
            return

        if e.get("type") != EventType.ORDER_FILLED.value:
            return
        p = e.get("payload", {}) or {}
        key = p.get("strategy_id") or DISCRETIONARY
        qty = D(p.get("filled_qty", p.get("qty", 0)))
        px = D(p.get("avg_price", p.get("price", p.get("fill_price", 0))))
        fees = D(p.get("fees", 0))
        side = p.get("side", "buy")
        sym = p.get("symbol", "UNKNOWN")
        signed = qty if side == "buy" else -qty

        rec = s(key)
        rec["net_invested"] += signed * px + fees
        pos = rec["positions"].setdefault(sym, {"qty": Decimal("0"), "cost": Decimal("0")})

        if signed > 0:
            buying = signed
            # A buy against an open SHORT is a cover, and covers realize P&L —
            # profit when the price fell. Treating every buy as an opening trade
            # would silently drop the entire realized result of any short.
            if pos["qty"] < -D("1e-9"):
                short_qty = -pos["qty"]
                closing = min(buying, short_qty)
                avg = -pos["cost"] / short_qty     # cost is negative for a short
                rec["realized"] += closing * (avg - px) - fees
                pos["qty"] += closing
                pos["cost"] += closing * avg
                remainder = buying - closing
                if remainder <= D("1e-9"):
                    return
                buying = remainder       # the rest opens a long
                fees = D("0")            # already charged against the cover

            pos["qty"] += buying
            pos["cost"] += buying * px + fees
        else:
            sold = -signed
            open_qty = pos["qty"]
            if open_qty > D("1e-9"):
                # only the part that closes an existing long realizes P&L
                closing = min(sold, open_qty)
                avg = pos["cost"] / open_qty
                rec["realized"] += closing * (px - avg) - fees
                pos["cost"] -= closing * avg
                pos["qty"] -= closing
                remainder = sold - closing
                if remainder > D("1e-9"):     # flipped short
                    pos["qty"] -= remainder
                    pos["cost"] -= remainder * px
            else:
                # opening/extending a short: no realization yet
                pos["qty"] -= sold
                pos["cost"] -= sold * px - fees

    @staticmethod
    def _apply_venue_reconciliation(get: Callable[[str], dict[str, Any]],
                                    p: dict[str, Any]) -> None:
        """The book aligned to the venue, seen from the strategy ledgers.

        THREE cases, not two. v1 documented RELEASE and ADOPT and shipped a
        third the docstring did not mention: it emptied EVERY holder of the
        symbol and wrote any surviving quantity into ``discretionary``, so a
        position that was merely REDUCED changed owner (adversary review of
        builder D11, 2026-08-22, finding K3).

        On the live book that was not cosmetic. SPY 0.346119 -> 0.217757 would
        have left ``sleeve_premia_equity`` holding nothing, and autopolicy v3's
        envelope requires that "the rule's own strategy must hold the quantity
        it sells". So the sleeve's exit rules could never again be
        auto-approved: the control fails CLOSED, which is safe, but it stops
        working SILENTLY, and a control that quietly stops is the pattern this
        firm names most often. The premia sleeve would also have reported zero
        exposure while the fund still held the position.

        FULL RELEASE (the venue holds none of it) — every ledger that held it
        is emptied, at its own cost basis, WITH NO REALISED P&L. Nothing was
        sold. Booking a realised gain here would put an invented trade into
        every performance number the strategy has, permanently.

        PARTIAL RELEASE (the venue holds less than the book) — the survivors
        stay with the strategies that held them, scaled PRO RATA, cost basis
        per share unchanged and no realised P&L. Ownership is preserved
        because nothing about a broker reconciliation is a decision to stop
        managing a position: the fund still holds it, and the strategy that
        chose it still owns it.

        ADOPT (the venue holds more than the book) — the holders keep what they
        had and only the EXCESS lands in ``discretionary``, because no strategy
        chose that part. The CEO accepted the unmanaged remainder explicitly
        (*"if there is no strategy tracking it then its okay too"*), and this
        is the fold that makes the acceptance TRUE rather than assumed: exit
        coverage reads these ledgers, so an adopted quantity that quietly
        acquired a strategy would be reported as covered by an exit rule
        nobody wrote for it.

        The invariant, in every case: the strategy ledgers sum to the venue's
        quantity, which is what ``positions.py`` sets the book to. Pinned by a
        test, because the two folds reading one payload is exactly where they
        can drift apart.
        """
        for row in (p.get("positions") or []):
            symbol = row.get("symbol")
            if not symbol:
                continue
            target = D(row.get("venue_qty", 0))

            # The ledgers' OWN state, not the payload's copy of it. The payload
            # records holders as they were at PLAN time; the fold is the
            # authority on what each ledger holds now, and it carries the cost
            # basis the payload rounds.
            current = []
            for h in (row.get("holders") or []):
                rec = get(h.get("strategy_id") or DISCRETIONARY)
                pos = rec["positions"].get(symbol)
                if pos is not None:
                    current.append((rec, pos))
            held = sum((pos["qty"] for _, pos in current), Decimal("0"))

            def _empty_all():
                for rec, pos in current:
                    # net_invested falls by exactly what the ledger had in it,
                    # so the strategy's capital-employed figure stops counting
                    # a position it no longer holds.
                    rec["net_invested"] -= pos["cost"]
                    rec["positions"].pop(symbol, None)

            # A sign flip (the book is long, the venue is short, or the
            # reverse) is not a reduction of anything — there is no pro-rata
            # reading of it. Treated as a full release followed by a fresh
            # adoption, which is what it factually is.
            flipped = (held != 0 and target != 0
                       and (held > 0) != (target > 0))

            if abs(target) < Decimal("1e-9"):
                _empty_all()
                continue

            if abs(held) < Decimal("1e-9") or flipped:
                _empty_all()
                basis = row.get("venue_avg_price") or row.get("mark")
                if basis is None:
                    # Absent is absent. The plan refuses to reach here (it
                    # raises on an unpriced symbol), so this is a belt to that
                    # brace: a position is never adopted at a cost basis
                    # nobody stated.
                    continue
                rec = get(DISCRETIONARY)
                pos = rec["positions"].setdefault(symbol,
                                                  {"qty": Decimal("0"),
                                                   "cost": Decimal("0")})
                rec["net_invested"] -= pos["cost"]
                pos["qty"] = target
                pos["cost"] = target * D(basis)
                rec["net_invested"] += pos["cost"]
                continue

            if abs(target - held) < Decimal("1e-9"):
                continue                      # in sync per ledger; nothing to do

            if abs(target) < abs(held):
                # PARTIAL RELEASE. Scale every holder by the same ratio, so
                # cost PER SHARE is untouched and no P&L is realised.
                ratio = target / held
                for rec, pos in current:
                    new_cost = pos["cost"] * ratio
                    rec["net_invested"] += new_cost - pos["cost"]
                    pos["qty"] = pos["qty"] * ratio
                    pos["cost"] = new_cost
                continue

            # PARTIAL ADOPT: holders keep theirs, the excess is unmanaged.
            basis = row.get("venue_avg_price") or row.get("mark")
            if basis is None:
                continue
            excess = target - held
            rec = get(DISCRETIONARY)
            pos = rec["positions"].setdefault(symbol, {"qty": Decimal("0"),
                                                       "cost": Decimal("0")})
            pos["qty"] = pos["qty"] + excess
            add = excess * D(basis)
            pos["cost"] = pos["cost"] + add
            rec["net_invested"] += add

    @staticmethod
    def _apply_correction(get: Callable[[str], dict[str, Any]],
                          p: dict[str, Any]) -> None:
        """Fold one ``StrategyAttributionCorrected``.

        Moves ``qty`` shares of ``symbol`` at ``cost_usd`` of basis (and,
        optionally, ``realized_usd`` of booked P&L and ``net_invested_usd``)
        from ``from_strategy_id`` to ``to_strategy_id``. The fund's positions,
        cash and NAV are UNTOUCHED by design — nothing traded; only the index
        from fills to strategies is repaired.

        Fails closed twice. A correction without a non-empty ``reason`` is
        IGNORED, not applied: the whole justification for permitting a
        compensating write is that it carries its own explanation, so an
        unexplained one is not a weaker correction, it is not one. A correction
        naming the same strategy on both sides is also ignored — a no-op that
        looks like a repair is worse than no repair.
        """
        reason = str(p.get("reason") or "").strip()
        src, dst = p.get("from_strategy_id"), p.get("to_strategy_id")
        if not reason or not src or not dst or src == dst:
            return
        symbol = p.get("symbol")
        if not symbol:
            return

        qty = D(p.get("qty", 0))
        cost = D(p.get("cost_usd", 0))
        realized = D(p.get("realized_usd", 0))
        invested = D(p.get("net_invested_usd", 0))

        for key, sign in ((str(src), D(-1)), (str(dst), D(1))):
            rec = get(key)
            pos = rec["positions"].setdefault(
                str(symbol), {"qty": Decimal("0"), "cost": Decimal("0")})
            pos["qty"] += sign * qty
            pos["cost"] += sign * cost
            rec["realized"] += sign * realized
            rec["net_invested"] += sign * invested

    def with_values(self, pricer: Callable[[str], float]) -> list[dict[str, Any]]:
        out = []
        for rec in self._build().values():
            exposure = Decimal("0")
            open_cost = Decimal("0")
            positions = {}
            unmarked: list[str] = []
            for symbol, pos in rec["positions"].items():
                qty = pos["qty"]
                if abs(qty) < D("1e-9"):
                    continue
                try:
                    mark = D(pricer(symbol))
                except ValueError:
                    # PriceUnavailable (a ValueError): the symbol has no real
                    # mark right now. Named absence — the row must not silently
                    # value the position at a number nobody quoted, and must
                    # not read as "no position" either.
                    unmarked.append(symbol)
                    positions[symbol] = f(qty)
                    open_cost += pos["cost"]
                    continue
                exposure += qty * mark
                open_cost += pos["cost"]
                positions[symbol] = f(qty)

            realized = rec["realized"]
            unrealized = exposure - open_cost
            out.append({
                "strategy_id": rec["strategy_id"],
                "exposure_usd": f(money(exposure)),
                "net_invested_usd": f(money(rec["net_invested"])),
                # pnl_usd stays the pooled total for backwards compatibility;
                # the split is what a desk actually needs (tax + attribution).
                "pnl_usd": f(money(realized + unrealized)),
                "realized_pnl_usd": f(money(realized)),
                "unrealized_pnl_usd": f(money(unrealized)),
                "cost_basis_usd": f(money(open_cost)),
                "positions": positions,
                # Symbols held but unpriceable right now — their value is
                # ABSENT from exposure/unrealized above, not zero.
                "unmarked_symbols": unmarked,
            })
        return sorted(out, key=lambda r: r["exposure_usd"], reverse=True)
