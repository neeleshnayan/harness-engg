"""Tests for HRP portfolio optimization & skfolio-style Purged Cross Validation."""

import pandas as pd
import numpy as np
import pytest

from app.fund.optimization import optimize_portfolio, purged_cross_validation


def test_hrp_optimization_with_mock_bars(monkeypatch):
    """Test Hierarchical Risk Parity optimization produces valid weights summing to 1.0."""
    dates = [f"2025-01-{i:02d}" for i in range(1, 31)]
    np.random.seed(42)
    closes1 = (100 + np.cumsum(np.random.randn(30))).tolist()
    closes2 = (150 + np.cumsum(np.random.randn(30))).tolist()
    closes3 = (200 + np.cumsum(np.random.randn(30))).tolist()

    class MockBars:
        def __init__(self, closes):
            self.dates = dates
            self.closes = closes

    def mock_fetch_daily_bars(symbol, lookback_days=365):
        if symbol == "AAPL":
            return MockBars(closes1)
        elif symbol == "NVDA":
            return MockBars(closes2)
        else:
            return MockBars(closes3)

    monkeypatch.setattr("app.fund.optimization.fetch_daily_bars", mock_fetch_daily_bars)

    result = optimize_portfolio(["AAPL", "NVDA", "MSFT"], method="hrp")

    assert result["method"] == "hrp"
    assert "weights" in result
    weights = result["weights"]
    assert set(weights.keys()) == {"AAPL", "NVDA", "MSFT"}
    total_weight = sum(weights.values())
    assert pytest.approx(total_weight, 0.01) == 1.0
    assert "cv_metrics" in result
    assert "correlation" in result


def test_purged_cross_validation():
    """Test Purged Cross Validation calculates OOS metrics & PBO without error."""
    dates = pd.date_range("2025-01-01", periods=100)
    np.random.seed(123)
    data = {
        "AAPL": 100 + np.cumsum(np.random.randn(100) * 0.5),
        "NVDA": 200 + np.cumsum(np.random.randn(100) * 0.8),
        "MSFT": 300 + np.cumsum(np.random.randn(100) * 0.4),
    }
    df = pd.DataFrame(data, index=dates)

    cv = purged_cross_validation(df, method="hrp", n_splits=5, purge_days=3)

    assert "oos_sharpe" in cv
    assert "oos_annual_return" in cv
    assert "oos_max_drawdown" in cv
    assert "pbo" in cv
    assert len(cv["folds"]) <= 5
    assert 0.0 <= cv["pbo"] <= 1.0
