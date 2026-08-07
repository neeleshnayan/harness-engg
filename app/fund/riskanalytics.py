"""Analytical risk layer — concentration and scenario shocks over the live book.

Read-only and deterministic: it values the current positions through the same
NAV pricer the rest of the spine uses, then answers two questions a risk
manager asks constantly —

  * Concentration: how lopsided is the book? (per-name weight, largest position,
    a Herfindahl-Hirschman index, cash buffer, simple breach flags)
  * Scenario shock: "what if AAPL drops 20%?" — reprice one name (or the whole
    book) by a percentage move and show the hit to NAV and NAV-per-unit.

Nothing here writes events; risk analytics are a lens on the truth, not truth
themselves. The deterministic pre-trade ``RiskGate`` (app/fund/risk.py) is the
enforcement seam; this is the situational-awareness layer for the cockpit.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Optional

from app.fund.money import D, f
from app.fund.projections.nav import NavService

_EPS = Decimal("1e-9")

# Default what-ifs the cockpit shows without the user asking (symbol, pct).
_DEFAULT_SCENARIOS = (
    (None, -10.0),      # broad -10% across the book
    (None, -20.0),      # broad -20% (stress)
)

# Concentration breach thresholds (as % of NAV). Advisory, not enforced.
_MAX_POSITION_PCT = 25.0
_MIN_CASH_PCT = 5.0


class RiskAnalytics:
    def __init__(self, nav_service: NavService):
        self._nav = nav_service

    # --- concentration -----------------------------------------------------
    def analytics(self) -> dict[str, Any]:
        snap = self._nav.compute()
        total = snap.total_nav_usd
        cash = snap.breakdown.get("cash", D(0))
        gross = snap.breakdown.get("positions", D(0))

        rows: list[dict[str, Any]] = []
        for p in snap.positions:
            val = p["usd_value"]
            wt = (val / total * D(100)) if total > _EPS else D(0)
            rows.append({
                "symbol": p["symbol"],
                "qty": f(p["qty"]),
                "mark": f(p["mark"]),
                "usd_value": f(val),
                "weight_pct": round(f(wt), 4),
            })
        rows.sort(key=lambda r: abs(r["usd_value"]), reverse=True)

        # HHI over gross weights (share of gross exposure), 0..10000.
        hhi = 0.0
        if gross > _EPS:
            for p in snap.positions:
                share = f(p["usd_value"] / gross * D(100))
                hhi += share * share

        cash_pct = round(f(cash / total * D(100)), 4) if total > _EPS else 0.0
        largest = rows[0] if rows else None

        flags: list[str] = []
        if largest and largest["weight_pct"] > _MAX_POSITION_PCT:
            flags.append(
                f"{largest['symbol']} is {largest['weight_pct']:.1f}% of NAV "
                f"(> {_MAX_POSITION_PCT:.0f}% guideline)"
            )
        if total > _EPS and cash_pct < _MIN_CASH_PCT:
            flags.append(f"cash buffer {cash_pct:.1f}% (< {_MIN_CASH_PCT:.0f}% guideline)")
        if cash < -_EPS:
            flags.append("negative cash — book is levered")

        return {
            "nav_usd": f(total),
            "gross_exposure_usd": f(gross),
            "gross_exposure_pct": round(f(gross / total * D(100)), 4) if total > _EPS else 0.0,
            "cash_usd": f(cash),
            "cash_pct": cash_pct,
            "n_positions": len(rows),
            "largest_position": largest,
            "concentration_hhi": round(hhi, 1),
            "positions": rows,
            "flags": flags,
            "scenarios": [self.shock(sym, pct) for (sym, pct) in _DEFAULT_SCENARIOS],
        }

    # --- scenario shock ----------------------------------------------------
    def shock(self, symbol: Optional[str], pct: float, label: str | None = None) -> dict[str, Any]:
        """Reprice ``symbol`` (or the whole book if None) by ``pct`` percent.

        Returns the P&L, the shocked NAV and NAV-per-unit — a read-only what-if.
        """
        snap = self._nav.compute()
        total = snap.total_nav_usd
        move = D(str(pct)) / D(100)
        target = symbol.upper() if symbol else None

        pnl = D(0)
        affected: list[dict[str, Any]] = []
        for p in snap.positions:
            if target and p["symbol"].upper() != target:
                continue
            delta = p["usd_value"] * move
            pnl += delta
            affected.append({
                "symbol": p["symbol"],
                "shocked_mark": f(p["mark"] * (D(1) + move)),
                "pnl_usd": f(delta),
            })

        nav_after = total + pnl
        units_out = snap.units_outstanding
        npu_before = snap.nav_per_unit
        npu_after = (nav_after / units_out) if units_out > _EPS else npu_before

        return {
            "label": label or (f"{target} {pct:+.0f}%" if target else f"market {pct:+.0f}%"),
            "symbol": target,
            "pct": pct,
            "pnl_usd": f(pnl),
            "nav_before": f(total),
            "nav_after": f(nav_after),
            "nav_change_pct": round(f(pnl / total * D(100)), 4) if total > _EPS else 0.0,
            "nav_per_unit_before": f(npu_before),
            "nav_per_unit_after": round(f(npu_after), 6),
            "affected": affected,
        }
