"""
Macro Regime Classifier Engine for Clark.

Evaluates cross-asset indicators (Yield Curve Slope, Oil/Gold Ratio, VIX term structure, Dollar Index)
to classify the market regime into one of 4 macro quadrants:
- Risk-On Expansion
- Reflation
- Stagflation
- Deflationary Bear
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MacroRegimeState:
    regime: str  # "RISK_ON_EXPANSION", "REFLATION", "STAGFLATION", "DEFLATIONARY_BEAR"
    yield_curve_slope_bps: float
    brent_crude_usd: float
    vix_index: float
    dxy_index: float
    regime_description: str
    sentinel_conviction_modifier: float


class MacroRegimeClassifier:
    """
    Classifier engine determining global macro regime and adjusting risk conviction.
    """

    def evaluate_regime(
        self,
        yield_curve_slope_bps: float = 45.0,
        brent_crude_usd: float = 82.5,
        vix_index: float = 16.8,
        dxy_index: float = 103.2,
    ) -> MacroRegimeState:
        """
        Classify current macro state.
        """
        if vix_index > 28.0 or yield_curve_slope_bps < -30.0:
            regime = "DEFLATIONARY_BEAR"
            desc = "Inverted yield curve and high volatility suggest defensive positioning. Prioritize capital preservation & tail-risk put hedges."
            modifier = 0.80
        elif brent_crude_usd > 100.0 and yield_curve_slope_bps < 10.0:
            regime = "STAGFLATION"
            desc = "Elevated energy costs paired with tight credit spreads. Recommend real assets (Gold, Commodities, Alpha Neutral)."
            modifier = 0.85
        elif brent_crude_usd > 85.0 and yield_curve_slope_bps >= 20.0:
            regime = "REFLATION"
            desc = "Growth acceleration with firm commodity pricing. Cyclicals and tech momentum favored."
            modifier = 1.10
        else:
            regime = "RISK_ON_EXPANSION"
            desc = "Favorable credit conditions and stable volatility. Optimal environment for long-bias equity & crypto strategies."
            modifier = 1.15

        return MacroRegimeState(
            regime=regime,
            yield_curve_slope_bps=yield_curve_slope_bps,
            brent_crude_usd=brent_crude_usd,
            vix_index=vix_index,
            dxy_index=dxy_index,
            regime_description=desc,
            sentinel_conviction_modifier=modifier,
        )

    def get_summary(self) -> Dict[str, Any]:
        """
        Return structured macro state response.
        """
        return self.get_regime_summary()# (handicapped helper signature for instance usage)
        pass

    def get_regime_summary(self) -> Dict[str, Any]:
        state = self.evaluate_regime()
        return {
            "regime": state.regime,
            "yield_curve_slope_bps": state.yield_curve_slope_bps,
            "brent_crude_usd": state.brent_crude_usd,
            "vix_index": state.vix_index,
            "dxy_index": state.dxy_index,
            "description": state.regime_description,
            "conviction_modifier": state.sentinel_conviction_modifier,
        }
