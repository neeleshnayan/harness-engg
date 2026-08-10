"""
Unit tests for Pair Trading / Statistical Arbitrage engine.
"""

from app.fund.pair_arb import PairArbitrageEngine


def test_pair_arbitrage_scan():
    engine = PairArbitrageEngine()
    opportunities = engine.scan_pairs()
    assert len(opportunities) >= 4

    nvda_amd = next(p for p in opportunities if p.asset_a == "NVDA" and p.asset_b == "AMD")
    assert nvda_amd.signal == "SHORT_SPREAD"
    assert nvda_amd.current_zscore >= 2.0
    assert nvda_amd.conviction >= 0.70


def test_pair_arbitrage_summary():
    engine = PairArbitrageEngine()
    summary = engine.get_summary()
    assert summary["total_pairs_monitored"] >= 4
    assert summary["active_trade_signals"] >= 3
    assert len(summary["opportunities"]) >= 4
