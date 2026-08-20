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

    **A default may never be looser than the mandate in force.** `RiskControl`
    folds the latest RISK_LIMITS_SET *over these defaults*, so the defaults are
    what governs whenever that event is absent — an empty log, a fresh deployment,
    or a restore from a snapshot taken before the limits were set. Three of these
    were looser than the running fund (drawdown 0.15 vs 0.10, daily loss 0.05 vs
    0.04, order cap 0.25 vs 0.15), which meant a restore could have widened the
    drawdown kill switch by half without anyone deciding to. That is the one
    forbidden move — a quiet loosening — arriving by accident rather than by
    argument, which is worse, because nobody would have been asked.

    Found by the judgement register (`app/fund/judgement.py`), which reads limits
    as they are IN FORCE and compares them against what was written down.
    `test_no_default_is_looser_than_the_mandate` now guards it permanently, and it
    is the test rather than this paragraph that will still be true next year.

    Left deliberately unchanged: `min_cash_pct` defaults to 0.10 against 0.05 in
    force. It is a FLOOR, so the higher default is the safer one, and a missing
    event should fail toward more cash, not less.
    """
    # --- pre-trade gate (hard reject before human approval) ---
    max_position_pct: float = 0.20          # no single name > 20% of NAV
    min_cash_buffer: float = 0.0            # keep at least this much USD idle (absolute)
    max_order_notional_pct: float = 0.15    # a single order may deploy <= 15% of NAV
    max_strategy_pct: float = 0.40          # no single strategy > 40% of NAV
    # --- continuous monitor (alarms + kill switch) ---
    min_cash_pct: float = 0.10              # cash floor as a fraction of NAV (alarm below)
    max_drawdown_pct: float = 0.10          # halt trading if NAV falls this far from its peak
    max_daily_loss_pct: float = 0.04        # halt if NAV drops this much vs the last daily strike
    underwater_pct: float = 0.15            # per-name alarm when a position is this far underwater

    # --- structural risk (measured, not counted) ---
    # A position-count limit cannot see that four names are one bet. These do.
    min_effective_bets: float = 2.0         # correlation-adjusted independent bets
    max_avg_correlation: float = 0.75       # mean pairwise correlation across holdings
    max_strategy_correlation: float = 0.90  # two "different" strategies moving as one
    # RETIRED 2026-08-20 (CEO-accepted validator finding, run-validator-r6d2):
    # risk_share_pct sums to 100% by Euler, so a 100%-single-name book read
    # 100.00% — BETTER than the healthy hedged book's 102.49% — and the alarm
    # got louder as the hedge improved. Kept only so stored limits payloads
    # still load; consumed nowhere. Replaced by max_component_vol_pct below.
    max_risk_concentration_pct: float = 0.50
    #: One name's contribution to annualised NAV volatility, in vol points —
    #: cardinality-free and monotone in the concentration accident (measured
    #: 2026-08-20: 9.78 healthy hedged sleeve, 20.09 at a 90/10 book, 22.35
    #: single-name, 4.87 at risk parity). 15.0 sits between health and the
    #: 90/10 accident. Advisory alarm only — wiring it into gating would be
    #: its own versioned change.
    max_component_vol_pct: float = 15.0
    max_expected_shortfall_pct: float = 0.05  # 97.5% one-day ES as a fraction of NAV

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
            "min_effective_bets": self.min_effective_bets,
            "max_avg_correlation": self.max_avg_correlation,
            "max_strategy_correlation": self.max_strategy_correlation,
            "max_risk_concentration_pct": self.max_risk_concentration_pct,
            "max_component_vol_pct": self.max_component_vol_pct,
            "max_expected_shortfall_pct": self.max_expected_shortfall_pct,
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
            current = next(
                (p["usd_value"] for p in nav.positions if p["symbol"] == order.symbol),
                Decimal("0"),
            )

            # Single-order size cap — on the notional that INCREASES exposure.
            #
            # This used to apply to every order regardless of side, which made a
            # position larger than the cap impossible to exit: a name at 16% of
            # NAV could not be sold under a 15% order cap, in one order or any
            # number of them, because each sell was measured against the same
            # ceiling. A limit meant to stop an oversized deployment was
            # forbidding de-risking, and it bit hardest exactly when a position
            # had grown large — which is when you most need to get out.
            #
            # So the cap measures the exposure-increasing part only. Closing an
            # existing long is exempt; selling BEYOND it opens a short, and that
            # part is a deployment like any other.
            if order.side == Side.BUY:
                increasing = notional
            else:
                closing = min(notional, max(current, Decimal("0")))
                increasing = notional - closing

            if increasing > max_order * nav_usd:
                what = ("order notional" if order.side == Side.BUY
                        else "the short this sell would open")
                breaches.append(
                    f"{what} {float(increasing):.2f} exceeds "
                    f"{float(max_order):.0%} of NAV ({float(nav_usd):.2f})"
                )
            # Resulting single-name concentration (rough: current + this order)
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
            # The percentage cash floor used to exist only as a post-hoc alarm,
            # so the book could be traded to zero cash and merely be told about
            # it afterwards. A floor that only warns after the fact is not a
            # floor; enforce it where it can still stop the order.
            min_cash = D(self.limits.min_cash_pct)
            if nav_usd > 0 and min_cash > 0:
                required = min_cash * nav_usd
                if post_cash < required:
                    breaches.append(
                        f"buy would drop cash to {float(post_cash / nav_usd):.1%} of NAV "
                        f"(floor {float(min_cash):.1%}, i.e. {float(required):.2f})"
                    )

        return RiskDecision(ok=not breaches, breaches=breaches)
