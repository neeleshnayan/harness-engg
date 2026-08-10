"""Per-strategy attribution — a fold over tagged fills.

For each ``strategy_id`` (``None`` → "discretionary") accumulates net position
per symbol and net invested (signed notional + fees). Valued at current marks:

    exposure = Σ qty × mark
    pnl      = exposure − net_invested      (realized + unrealized, one pooled MTM)

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
        strats: dict[str, dict[str, Any]] = {}

        def s(key: str) -> dict[str, Any]:
            return strats.setdefault(
                key, {"strategy_id": key, "net_invested": Decimal("0"), "positions": {}}
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
            rec["positions"][sym] = rec["positions"].get(sym, Decimal("0")) + signed
            rec["net_invested"] += signed * px + fees

        return strats

    def with_values(self, pricer: Callable[[str], float]) -> list[dict[str, Any]]:
        out = []
        for rec in self._build().values():
            exposure = Decimal("0")
            positions = {}
            for symbol, qty in rec["positions"].items():
                if abs(qty) < D("1e-9"):
                    continue
                mark = D(pricer(symbol))
                exposure += qty * mark
                positions[symbol] = f(qty)
            pnl = exposure - rec["net_invested"]
            out.append({
                "strategy_id": rec["strategy_id"],
                "exposure_usd": f(money(exposure)),
                "net_invested_usd": f(money(rec["net_invested"])),
                "pnl_usd": f(money(pnl)),
                "positions": positions,
            })
        return sorted(out, key=lambda r: r["exposure_usd"], reverse=True)
