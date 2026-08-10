"""Unit tests for CounterfactualSimulator."""

from decimal import Decimal
from app.fund.simulation import CounterfactualSimulator, PRESET_SCENARIOS


class FakeNavService:
    def compute(self):
        class FakeNav:
            total_nav_usd = Decimal("100000.00")
            breakdown = {"cash": Decimal("9000.00"), "positions": Decimal("91000.00")}
            positions = [
                {"symbol": "AAPL", "qty": 15.0, "mark": 220.50, "usd_value": 3307.50},
                {"symbol": "MSFT", "qty": 10.0, "mark": 410.00, "usd_value": 4100.00},
                {"symbol": "NVDA", "qty": 8.0, "mark": 125.00, "usd_value": 1000.00},
            ]
        return FakeNav()


def test_simulation_preset_oil_spike():
    sim = CounterfactualSimulator(nav_service=FakeNavService(), positions_projection=None)
    res = sim.simulate(scenario="oil_spike")
    assert res["summary"]["nav_usd_before"] == 100000.00
    assert res["summary"]["drawdown_usd"] < 0
    assert len(res["position_impacts"]) == 3
    assert "hedging_proposals" in res
    assert res["preset"]["name"] == "Geopolitical Oil Spike"


def test_simulation_custom_inputs():
    sim = CounterfactualSimulator(nav_service=FakeNavService(), positions_projection=None)
    res = sim.simulate(crude_oil_price=110.0, yield_10y_bps=40.0, market_shock_pct=-5.0)
    assert res["inputs"]["crude_oil_price"] == 110.0
    assert res["inputs"]["yield_10y_bps"] == 40.0
    assert res["summary"]["drawdown_pct"] < 0
