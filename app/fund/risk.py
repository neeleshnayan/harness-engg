"""Risk gate — the deterministic check that runs *before* human approval.

Phase-1 scaffold: the hard-reject tier plus the duplicate-execution guard.
Every limit is read from live state (the NAV snapshot / book), so the gate is
stateful but never keeps its own copy of the truth. Step 4 fleshes out the
threshold/escalation tier; the seams are here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.fund.connectors.base import Order, Side
from app.fund.money import D
from app.fund.projections.nav import NavSnapshot


@dataclass
class RiskDecision:
    ok: bool
    breaches: list[str] = field(default_factory=list)


@dataclass
class RiskLimits:
    # Phase-1 defaults — tune per mandate. All fractions are of NAV.
    max_position_pct: float = 0.35          # no single name > 35% of NAV
    min_cash_buffer: float = 0.0            # keep at least this much USD idle
    max_order_notional_pct: float = 0.50    # a single order may deploy <= 50% of NAV


class RiskGate:
    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()

    def check(self, order: Order, quote_price: float, nav: NavSnapshot) -> RiskDecision:
        breaches: list[str] = []
        notional = D(order.qty) * D(quote_price)
        nav_usd = nav.total_nav_usd                       # Decimal
        max_order = D(self.limits.max_order_notional_pct)
        max_pos = D(self.limits.max_position_pct)
        buffer = D(self.limits.min_cash_buffer)

        # Sane bounds
        if order.qty <= 0:
            breaches.append("qty must be positive")

        if nav_usd > 0:
            # Single-order size cap
            if notional > max_order * nav_usd:
                breaches.append(
                    f"order notional {float(notional):.2f} exceeds "
                    f"{float(max_order):.0%} of NAV ({float(nav_usd):.2f})"
                )
            # Resulting single-name concentration (rough: current + this order)
            current = next(
                (p["usd_value"] for p in nav.positions if p["symbol"] == order.symbol),
                Decimal("0"),
            )
            projected = current + (notional if order.side == Side.BUY else -notional)
            if abs(projected) > max_pos * nav_usd:
                breaches.append(
                    f"{order.symbol} would be {float(abs(projected) / nav_usd):.0%} of NAV "
                    f"(limit {float(max_pos):.0%})"
                )

        # Cash buffer on buys
        if order.side == Side.BUY:
            post_cash = nav.breakdown.get("cash", Decimal("0")) - notional
            if post_cash < buffer:
                breaches.append(
                    f"buy would drop cash to {float(post_cash):.2f}, below buffer "
                    f"{float(buffer):.2f}"
                )

        return RiskDecision(ok=not breaches, breaches=breaches)
