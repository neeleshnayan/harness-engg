"""Realized vs unrealized P&L.

Previously attribution reported one pooled mark-to-market number, so the UI could
not honestly label it either way — conflating the two is a real desk error (it
drives both tax treatment and performance attribution).
"""

from decimal import Decimal

from app.fund.events import EventType
from app.fund.projections.strategy import StrategyAttribution


class FakeStore:
    def __init__(self, events):
        self._events = [dict(e, seq=i + 1) for i, e in enumerate(events)]

    def stream(self, since_seq: int = 0, limit: int = 200):
        return [e for e in self._events if e["seq"] > since_seq][:limit]


def _fill(symbol, side, qty, price, strategy_id="s1", fees=0):
    return {
        "type": EventType.ORDER_FILLED.value,
        "aggregate_id": f"{symbol}-{side}-{qty}-{price}",
        "payload": {"symbol": symbol, "side": side, "filled_qty": qty,
                    "avg_price": price, "fees": fees, "strategy_id": strategy_id},
    }


def _one(events, marks):
    rows = StrategyAttribution(FakeStore(events)).with_values(lambda s: marks[s])
    return rows[0]


def test_open_position_is_all_unrealized():
    row = _one([_fill("AAPL", "buy", 10, 100)], {"AAPL": 120})

    assert row["unrealized_pnl_usd"] == 200.0   # 10 * (120 - 100)
    assert row["realized_pnl_usd"] == 0.0
    assert row["pnl_usd"] == 200.0


def test_closed_position_is_all_realized():
    row = _one(
        [_fill("AAPL", "buy", 10, 100), _fill("AAPL", "sell", 10, 130)],
        {"AAPL": 999},   # mark is irrelevant once flat
    )

    assert row["realized_pnl_usd"] == 300.0     # 10 * (130 - 100)
    assert row["unrealized_pnl_usd"] == 0.0


def test_partial_sale_splits_both_ways():
    row = _one(
        [_fill("AAPL", "buy", 10, 100), _fill("AAPL", "sell", 4, 130)],
        {"AAPL": 120},
    )

    assert row["realized_pnl_usd"] == 120.0     # 4 * (130 - 100)
    assert row["unrealized_pnl_usd"] == 120.0   # 6 * (120 - 100)
    assert row["pnl_usd"] == 240.0


def test_average_cost_across_multiple_buys():
    row = _one(
        [_fill("AAPL", "buy", 10, 100), _fill("AAPL", "buy", 10, 200),
         _fill("AAPL", "sell", 5, 200)],
        {"AAPL": 200},
    )

    # average cost 150; selling 5 realizes 5 * (200-150) = 250
    assert row["realized_pnl_usd"] == 250.0
    assert row["cost_basis_usd"] == 2250.0      # 15 remaining * 150
    assert row["unrealized_pnl_usd"] == 750.0   # 15 * (200-150)


def test_split_always_sums_to_the_pooled_total():
    """The invariant the old single number satisfied must still hold."""
    events = [
        _fill("AAPL", "buy", 10, 100), _fill("MSFT", "buy", 5, 400),
        _fill("AAPL", "sell", 3, 150), _fill("MSFT", "buy", 5, 420),
    ]
    row = _one(events, {"AAPL": 130, "MSFT": 410})

    assert round(row["realized_pnl_usd"] + row["unrealized_pnl_usd"], 6) == row["pnl_usd"]


def test_fees_reduce_realized_pnl():
    row = _one(
        [_fill("AAPL", "buy", 10, 100), _fill("AAPL", "sell", 10, 130, fees=50)],
        {"AAPL": 130},
    )

    assert row["realized_pnl_usd"] == 250.0     # 300 gross - 50 fees
