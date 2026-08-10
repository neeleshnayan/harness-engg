"""
Unit tests for Macro Regime Classifier engine.
"""

from app.fund.macro_regime import MacroRegimeClassifier


def test_macro_regime_classification():
    classifier = MacroRegimeClassifier()

    state1 = classifier.evaluate_regime(brent_crude_usd=82.5, yield_curve_slope_bps=45.0, vix_index=16.8)
    assert state1.regime == "RISK_ON_EXPANSION"
    assert state1.sentinel_conviction_modifier == 1.15

    state2 = classifier.evaluate_regime(brent_crude_usd=105.0, yield_curve_slope_bps=5.0, vix_index=22.0)
    assert state2.regime == "STAGFLATION"
    assert state2.sentinel_conviction_modifier == 0.85

    state3 = classifier.evaluate_regime(brent_crude_usd=75.0, yield_curve_slope_bps=-35.0, vix_index=32.0)
    assert state3.regime == "DEFLATIONARY_BEAR"
    assert state3.sentinel_conviction_modifier == 0.80


def test_macro_regime_summary():
    classifier = MacroRegimeClassifier()
    summary = classifier.get_regime_summary()
    assert "regime" in summary
    assert "conviction_modifier" in summary
    assert "description" in summary
