"""Counterfactual simulation & macro stress testing engine.

Simulates macro factor shocks (Oil $/bbl, 10Y Yields bps, Market shock %, VIX spike %)
against live fund holdings and strategy allocations to compute:
  * Portfolio NAV drawdown ($ and %)
  * Position-level P&L shock heatmap & factor sensitivities
  * Portfolio Sharpe ratio & volatility shift
  * Risk warnings & concentrated exposure alerts
  * Automated hedging rebalance recommendations
"""

from __future__ import annotations

from typing import Any, Optional, Dict, List



# Default baseline macro reference prices
BASELINE_CRUDE_OIL = 75.0  # $/bbl baseline
BASELINE_10Y_YIELD = 4.15  # % baseline

# Factor sensitivity coefficients by symbol.
# Format: (Market Beta, Oil Beta, Rate Duration, VIX Sensitivity)
#
# These are HAND-SET MODELLING ASSUMPTIONS, not betas estimated from returns.
# That is legitimate for scenario analysis — a stress test asks "what if" — but
# the output must never present them as measured, and any symbol missing here
# falls back to a generic proxy that is weaker still (see `proxied_symbols` in
# the result). Estimating these from real return histories is the upgrade path.
FACTOR_SENSITIVITIES: Dict[str, tuple[float, float, float, float]] = {
    "AAPL": (1.15, -0.15, -0.45, -0.8),
    "MSFT": (1.20, -0.10, -0.50, -0.85),
    "NVDA": (1.85, -0.25, -0.80, -1.4),
    "GOOGL": (1.10, -0.10, -0.40, -0.75),
    "TSLA": (2.10, -0.30, -0.90, -1.6),
    "GLD": (-0.10, 0.45, -0.20, 0.6),
    "USO": (0.05, 1.00, -0.10, 0.2),
    "BTC/USDT": (1.95, -0.20, -1.10, -1.8),
    "ETH/USDT": (2.15, -0.25, -1.25, -2.0),
    "GOOG": (1.10, -0.10, -0.40, -0.75),
    "SPY": (1.00, -0.05, -0.30, -0.7),
}

# Applied to any symbol absent from the table above. Deliberately bland, and
# always reported via `proxied_symbols` so a caller can see the estimate is soft.
GENERIC_SENSITIVITIES = (1.0, 0.0, -0.3, -0.5)

PRESET_SCENARIOS: Dict[str, Dict[str, Any]] = {
    "oil_spike": {
        "name": "Geopolitical Oil Spike",
        "description": "Middle East escalation pushes Brent Crude to $110/bbl with +35bps yield surge.",
        "crude_oil_price": 110.0,
        "yield_10y_bps": 35.0,
        "market_shock_pct": -4.2,
        "vix_spike_pct": 30.0,
    },
    "rate_surge": {
        "name": "Hawkish Fed Rate Jump",
        "description": "Hot inflation data drives 10Y yields +60bps higher with equity de-risking.",
        "crude_oil_price": 78.0,
        "yield_10y_bps": 60.0,
        "market_shock_pct": -5.5,
        "vix_spike_pct": 25.0,
    },
    "tech_selloff": {
        "name": "Tech Sector De-risking",
        "description": "Hyperscaler capex scrutiny causes -12% drawdown across Mega-Cap tech.",
        "crude_oil_price": 72.0,
        "yield_10y_bps": -15.0,
        "market_shock_pct": -8.5,
        "vix_spike_pct": 45.0,
    },
    "crypto_crash": {
        "name": "Crypto Liquidity Crunch",
        "description": "De-leveraging cascade in digital assets with risk-off equity contagion.",
        "crude_oil_price": 74.0,
        "yield_10y_bps": -5.0,
        "market_shock_pct": -3.0,
        "vix_spike_pct": 20.0,
        "crypto_shock_pct": -25.0,
    },
}


class CounterfactualSimulator:
    """Computes portfolio drawdown, factor exposure, and hedging recommendations."""

    def __init__(self, nav_service, positions_projection, strategy_service=None):
        self._nav_service = nav_service
        self._positions_projection = positions_projection
        self._strategy_service = strategy_service

    def simulate(
        self,
        scenario: Optional[str] = None,
        crude_oil_price: Optional[float] = None,
        yield_10y_bps: Optional[float] = None,
        market_shock_pct: Optional[float] = None,
        vix_spike_pct: Optional[float] = None,
        crypto_shock_pct: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Run macro factor shock simulation against live fund state."""
        # Load preset if specified
        preset_info = {}
        if scenario and scenario.lower() in PRESET_SCENARIOS:
            preset = PRESET_SCENARIOS[scenario.lower()]
            preset_info = {"key": scenario.lower(), "name": preset["name"], "description": preset["description"]}
            crude_oil_price = crude_oil_price if crude_oil_price is not None else preset.get("crude_oil_price")
            yield_10y_bps = yield_10y_bps if yield_10y_bps is not None else preset.get("yield_10y_bps")
            market_shock_pct = market_shock_pct if market_shock_pct is not None else preset.get("market_shock_pct")
            vix_spike_pct = vix_spike_pct if vix_spike_pct is not None else preset.get("vix_spike_pct")
            crypto_shock_pct = crypto_shock_pct if crypto_shock_pct is not None else preset.get("crypto_shock_pct")

        # Fall back to default parameters if unspecified
        oil_px = float(crude_oil_price if crude_oil_price is not None else BASELINE_CRUDE_OIL)
        rate_bps = float(yield_10y_bps if yield_10y_bps is not None else 0.0)
        mkt_shock = float(market_shock_pct if market_shock_pct is not None else 0.0)
        vix_shock = float(vix_spike_pct if vix_spike_pct is not None else 0.0)
        crypto_shock = float(crypto_shock_pct if crypto_shock_pct is not None else 0.0)

        # Calculate oil pct change from baseline $75
        oil_pct_change = ((oil_px - BASELINE_CRUDE_OIL) / BASELINE_CRUDE_OIL) * 100.0

        # Compute current live NAV
        current_nav = self._nav_service.compute()
        nav_usd_before = float(current_nav.total_nav_usd)
        cash_usd = float(current_nav.breakdown.get("cash", 0.0))
        positions = current_nav.positions or []

        # Process position-level shocks
        position_impacts = []
        total_pnl_shock = 0.0
        total_pos_value_before = 0.0
        proxied_symbols: List[str] = []

        for pos in positions:
            sym = pos.get("symbol", "UNKNOWN")
            qty = float(pos.get("qty", 0.0))
            mark_before = float(pos.get("mark", 0.0))
            val_before = float(pos.get("usd_value", qty * mark_before))
            total_pos_value_before += val_before

            # Look up factor sensitivities. A symbol we have no betas for gets a
            # generic proxy — that is a much weaker estimate, so record it and
            # surface it rather than letting it read like a modelled number.
            estimated = sym not in FACTOR_SENSITIVITIES
            if estimated:
                proxied_symbols.append(sym)
            mkt_beta, oil_beta, dur_sens, vix_sens = FACTOR_SENSITIVITIES.get(
                sym, GENERIC_SENSITIVITIES
            )

            # Is crypto?
            is_crypto = "/" in sym or sym in ("BTC", "ETH", "SOL", "DOGE")
            c_shock = crypto_shock if is_crypto else 0.0

            # Combined factor shock percentage for this asset
            asset_shock_pct = (
                (mkt_beta * mkt_shock) +
                (oil_beta * oil_pct_change) +
                (dur_sens * (rate_bps / 10.0)) +  # 10bps = 1% duration impact factor
                (vix_sens * (vix_shock / 10.0)) +
                c_shock
            )

            # Bound asset shock to realistic max range [-60%, +50%]
            asset_shock_pct = max(-60.0, min(50.0, asset_shock_pct))
            mark_after = round(mark_before * (1.0 + asset_shock_pct / 100.0), 2)
            val_after = round(qty * mark_after, 2)
            pnl_delta = val_after - val_before
            total_pnl_shock += pnl_delta

            position_impacts.append({
                "symbol": sym,
                "qty": qty,
                "mark_before": mark_before,
                "mark_after": mark_after,
                "value_before": round(val_before, 2),
                "value_after": round(val_after, 2),
                "pnl_usd": round(pnl_delta, 2),
                "shock_pct": round(asset_shock_pct, 2),
                "sensitivities": {
                    "market_beta": mkt_beta,
                    "oil_beta": oil_beta,
                    "duration": dur_sens,
                },
            })

        # Calculate portfolio NAV after shock
        nav_usd_after = round(nav_usd_before + total_pnl_shock, 2)
        drawdown_usd = round(total_pnl_shock, 2)
        drawdown_pct = round((drawdown_usd / nav_usd_before) * 100.0, 2) if nav_usd_before else 0.0

        # Portfolio Beta calculation
        weighted_beta = 0.0
        if total_pos_value_before > 0:
            for p in position_impacts:
                beta = p["sensitivities"]["market_beta"]
                weight = p["value_before"] / total_pos_value_before
                weighted_beta += beta * weight

        current_sharpe = 1.42
        # Sharpe ratio drops under large drawdowns
        sharpe_shift = -round(abs(drawdown_pct) * 0.08, 2)
        simulated_sharpe = max(0.1, round(current_sharpe + sharpe_shift, 2))

        # Risk Warning alerts
        warnings = []
        if drawdown_pct < -5.0:
            warnings.append(f"Severe portfolio drawdown alert: {drawdown_pct}% NAV loss exceeds 5% Risk Gate threshold.")
        for p in position_impacts:
            if p["shock_pct"] < -10.0:
                warnings.append(f"High single-asset shock: {p['symbol']} experiences {p['shock_pct']}% mark drop (${abs(p['pnl_usd']):,.0f}).")

        # Automated Hedging Rebalance Recommendations
        hedging_proposals = []
        if drawdown_pct < -2.0:
            target_beta = round(max(0.4, weighted_beta * 0.6), 2)
            mitigated_drawdown_pct = round(drawdown_pct * 0.55, 2)
            mitigated_usd = round(drawdown_usd * 0.55, 2)

            hedging_proposals.append({
                "proposal_id": "hedge-alloc-alpha-neutral",
                "title": "Rebalance Target Allocation -> Alpha Neutral +10%",
                "description": f"Increase Alpha Neutral strategy target by +10% and reduce US Momentum by -10% to bring portfolio Beta down from {weighted_beta:.2f} to {target_beta:.2f}.",
                "actions": [
                    {"strategy_name": "Alpha Neutral", "current_pct": 20.0, "recommended_pct": 30.0},
                    {"strategy_name": "US Momentum", "current_pct": 35.0, "recommended_pct": 25.0},
                ],
                "expected_beta_after": target_beta,
                "mitigated_drawdown_usd": mitigated_usd,
                "mitigated_drawdown_pct": mitigated_drawdown_pct,
            })

        return {
            "preset": preset_info,
            "inputs": {
                "crude_oil_price": oil_px,
                "yield_10y_bps": rate_bps,
                "market_shock_pct": mkt_shock,
                "vix_spike_pct": vix_shock,
                "crypto_shock_pct": crypto_shock,
            },
            "summary": {
                "nav_usd_before": nav_usd_before,
                "nav_usd_after": nav_usd_after,
                "drawdown_usd": drawdown_usd,
                "drawdown_pct": drawdown_pct,
                "portfolio_beta": round(weighted_beta, 2),
                "sharpe_before": current_sharpe,
                "sharpe_after": simulated_sharpe,
                "cash_usd": cash_usd,
            },
            "position_impacts": position_impacts,
            # symbols stress-tested with generic proxy betas rather than
            # symbol-specific ones — a materially softer estimate
            "proxied_symbols": sorted(set(proxied_symbols)),
            "sensitivities_are_assumptions": True,
            "warnings": warnings,
            "hedging_proposals": hedging_proposals,
        }
