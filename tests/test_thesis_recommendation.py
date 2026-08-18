"""The research-to-trade hand-off stays a recommendation until approval."""

import pytest

from app.fund.recommendation import RecommendationError, build_thesis_trade_recommendation
from app.fund.thesis import ThesisService


def _thesis(wire):
    return ThesisService(wire.store).create({
        "title": "Long AAPL", "assets": ["AAPL"], "direction": "LONG",
        "target_exposure_pct": 5.0,
        "backtest": {"result": {"total_return": 0.2, "sharpe": 1.4,
                                  "bars": 252, "n_trades": 8}},
    }, actor="clark")


def test_recommendation_consumes_stored_backtest_without_writing(wire):
    thesis = _thesis(wire)
    out = build_thesis_trade_recommendation(
        thesis["thesis_id"], thesis, mark=200.0, nav_usd=10_000.0)

    assert out["side"] == "buy"
    assert out["qty"] == 2.5
    assert "not submitted" in out["execution"]


def test_recommendation_keeps_short_direction(wire):
    thesis = _thesis(wire)
    thesis["direction"] = "SHORT"
    out = build_thesis_trade_recommendation(
        thesis["thesis_id"], thesis, mark=200.0, nav_usd=10_000.0)

    assert out["side"] == "sell"


def test_recommendation_refuses_an_unbacktested_thesis(wire):
    thesis = ThesisService(wire.store).create({
        "title": "Long AAPL", "assets": ["AAPL"], "direction": "LONG",
        "target_exposure_pct": 5.0,
    }, actor="clark")
    with pytest.raises(RecommendationError, match="attach a backtest"):
        build_thesis_trade_recommendation(thesis["thesis_id"], thesis, mark=200.0, nav_usd=10_000.0)
