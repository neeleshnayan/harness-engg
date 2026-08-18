"""Turn a persisted research thesis into a sized, non-executing trade idea."""

from __future__ import annotations

from typing import Any


class RecommendationError(ValueError):
    """The thesis is not sufficiently specified to form a trade idea."""


def build_thesis_trade_recommendation(
    thesis_id: str, thesis: dict[str, Any], *, mark: float, nav_usd: float,
) -> dict[str, Any]:
    """Validate the research record and calculate the order shape.

    This function deliberately has no store, pipeline, or connector dependency:
    reading a recommendation must not be capable of writing an order.
    """
    direction = (thesis.get("direction") or "").upper()
    if direction not in ("LONG", "SHORT"):
        raise RecommendationError(
            "thesis has no direction; regenerate and promote it before requesting a trade recommendation")
    assets = thesis.get("assets") or []
    if len(assets) != 1:
        raise RecommendationError("a trade recommendation needs exactly one thesis asset")
    backtest = thesis.get("backtest") or {}
    result = backtest.get("result", backtest)
    if not result or int(result.get("bars") or 0) < 60:
        raise RecommendationError(
            "run and attach a backtest with at least 60 bars before requesting a trade recommendation")
    if mark <= 0 or nav_usd <= 0:
        raise RecommendationError("cannot size recommendation without a positive mark and NAV")
    target_pct = float(thesis.get("target_exposure_pct") or 0)
    if target_pct <= 0:
        raise RecommendationError("thesis needs a positive target_exposure_pct")

    symbol = str(assets[0]).upper()
    notional = nav_usd * target_pct / 100.0
    qty = round(notional / mark, 6)
    if qty <= 0:
        raise RecommendationError("target exposure is too small to form an order")
    side = "buy" if direction == "LONG" else "sell"
    rationale = (
        f"{direction} {symbol} from thesis '{thesis.get('title')}'. "
        f"Backtest: {float(result.get('total_return') or 0) * 100:.2f}% return, "
        f"Sharpe {float(result.get('sharpe') or 0):.2f}, {int(result.get('bars') or 0)} bars."
    )
    return {
        "thesis_id": thesis_id, "symbol": symbol, "direction": direction,
        "side": side, "qty": qty, "mark": mark, "notional_usd": round(notional, 2),
        "target_exposure_pct": target_pct, "backtest": result, "rationale": rationale,
        "execution": "not submitted — human approval remains required",
    }
