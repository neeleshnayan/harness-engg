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

from app.fund.events import EventStore, EventType
from app.fund.money import D, f, money

DISCRETIONARY = "discretionary"


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
