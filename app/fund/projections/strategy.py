"""Per-strategy attribution — a fold over tagged fills.

For each ``strategy_id`` (``None`` → "discretionary") accumulates net position
per symbol and net invested (signed notional + fees). Valued at current marks:

    exposure   = Σ qty × mark
    realized   = Σ over sales of qty × (price − average cost)   [average-cost basis]
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
    def __init__(self, store: EventStore | None = None):
        self._store = store or EventStore()

    def _build(self) -> dict[str, dict[str, Any]]:
        """Fold fills into per-strategy positions, cost basis and realized P&L.

        Average-cost accounting: a sale realizes ``qty × (price − average cost)``
        and retires that share of the basis. What remains in ``cost`` is the basis
        of the open position, so unrealized P&L is ``mark value − cost``.
        """
        strats: dict[str, dict[str, Any]] = {}

        def s(key: str) -> dict[str, Any]:
            return strats.setdefault(
                key,
                {
                    "strategy_id": key,
                    "net_invested": Decimal("0"),
                    "realized": Decimal("0"),
                    "positions": {},   # symbol -> {"qty", "cost"}
                },
            )

        for e in self._store.stream(since_seq=0, limit=100_000):
            if e.get("type") != EventType.ORDER_FILLED.value:
                continue
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
                pos["qty"] += signed
                pos["cost"] += signed * px + fees
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

        return strats

    def with_values(self, pricer: Callable[[str], float]) -> list[dict[str, Any]]:
        out = []
        for rec in self._build().values():
            exposure = Decimal("0")
            open_cost = Decimal("0")
            positions = {}
            for symbol, pos in rec["positions"].items():
                qty = pos["qty"]
                if abs(qty) < D("1e-9"):
                    continue
                mark = D(pricer(symbol))
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
            })
        return sorted(out, key=lambda r: r["exposure_usd"], reverse=True)
