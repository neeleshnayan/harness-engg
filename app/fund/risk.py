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
    """The mandate's risk limits — one auditable config the gate and monitor share.

    Fractions are of NAV unless noted. Defaults here are deliberately
    capital-preservation-first (a Friends-&-Family PoC posture): small single-name
    caps, a real cash floor, and a hard drawdown kill-switch.
    """
    # --- pre-trade gate (hard reject before human approval) ---
    max_position_pct: float = 0.20          # no single name > 20% of NAV
    min_cash_buffer: float = 0.0            # keep at least this much USD idle (absolute)
    max_order_notional_pct: float = 0.25    # a single order may deploy <= 25% of NAV
    max_strategy_pct: float = 0.40          # no single strategy > 40% of NAV
    # --- continuous monitor (alarms + kill switch) ---
    min_cash_pct: float = 0.10              # cash floor as a fraction of NAV (alarm below)
    max_drawdown_pct: float = 0.15          # halt trading if NAV falls this far from its peak
    max_daily_loss_pct: float = 0.05        # halt if NAV drops this much vs the last daily strike
    underwater_pct: float = 0.15            # per-name alarm when a position is this far underwater

    def to_dict(self) -> dict:
        return {
            "max_position_pct": self.max_position_pct,
            "min_cash_buffer": self.min_cash_buffer,
            "max_order_notional_pct": self.max_order_notional_pct,
            "max_strategy_pct": self.max_strategy_pct,
            "min_cash_pct": self.min_cash_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "underwater_pct": self.underwater_pct,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskLimits":
        base = cls()
        for k, v in (d or {}).items():
            if hasattr(base, k) and v is not None:
                setattr(base, k, float(v))
        return base


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
