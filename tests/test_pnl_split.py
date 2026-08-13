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


# --------------------------------------------------------------------------
# Shorts. A buy that covers an open short closes it and realizes P&L, the same
# way a sale closes a long. Attribution used to treat every buy as an opening
# trade, which silently dropped the entire realized result of any short.
# --------------------------------------------------------------------------

def test_cover_at_a_profit_realizes():
    """Short at 100, cover at 80 — a short makes money when the price falls."""
    row = _one(
        [_fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 10, 80)],
        {"AAPL": 999},   # mark is irrelevant once flat
    )

    assert row["realized_pnl_usd"] == 200.0     # 10 * (100 - 80)
    assert row["unrealized_pnl_usd"] == 0.0
    assert row["pnl_usd"] == 200.0
    assert row["positions"] == {}


def test_cover_at_a_loss_realizes():
    """Short at 100, cover at 130 — the loss must land in realized, not vanish."""
    row = _one(
        [_fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 10, 130)],
        {"AAPL": 999},
    )

    assert row["realized_pnl_usd"] == -300.0    # 10 * (100 - 130)
    assert row["unrealized_pnl_usd"] == 0.0
    assert row["pnl_usd"] == -300.0


def test_buy_covers_then_flips_long():
    """One buy of 25 against a short of 10: covers the 10, opens a long of 15."""
    row = _one(
        [_fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 25, 80)],
        {"AAPL": 90},
    )

    assert row["realized_pnl_usd"] == 200.0     # the cover: 10 * (100 - 80)
    assert row["positions"] == {"AAPL": 15.0}
    assert row["cost_basis_usd"] == 1200.0      # 15 opened at 80
    assert row["unrealized_pnl_usd"] == 150.0   # 15 * (90 - 80)
    assert row["pnl_usd"] == 350.0


def test_cover_fees_are_charged_once_not_to_the_new_long():
    """On a flip the fee belongs to the cover; the opened long must not re-pay it."""
    row = _one(
        [_fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 25, 80, fees=25)],
        {"AAPL": 80},
    )

    assert row["realized_pnl_usd"] == 175.0     # 200 gross - 25 fees
    assert row["cost_basis_usd"] == 1200.0      # 15 * 80, fee not charged again
    assert row["unrealized_pnl_usd"] == 0.0


def test_partial_cover_leaves_the_rest_short():
    """Covering 4 of a 10 short realizes only the closed part."""
    row = _one(
        [_fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 4, 80)],
        {"AAPL": 80},
    )

    assert row["realized_pnl_usd"] == 80.0      # 4 * (100 - 80)
    assert row["positions"] == {"AAPL": -6.0}
    assert row["unrealized_pnl_usd"] == 120.0   # 6 * (100 - 80), still open
    assert row["pnl_usd"] == 200.0


def test_short_split_still_sums_to_the_pooled_total():
    events = [
        _fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 6, 90, fees=3),
        _fill("MSFT", "sell", 5, 400), _fill("MSFT", "buy", 12, 380),
    ]
    row = _one(events, {"AAPL": 95, "MSFT": 370})

    assert round(row["realized_pnl_usd"] + row["unrealized_pnl_usd"], 6) == row["pnl_usd"]


def test_attribution_and_execution_agree_on_realized_shorts():
    """The two projections are two views of one book — one realized total.

    This is the reason the fix matters: execution history already closed shorts
    against the running average, so a divergence here means the same events
    produce two different realized numbers.
    """
    from app.fund.execution import ExecutionHistory

    events = [
        _fill("AAPL", "sell", 10, 100), _fill("AAPL", "buy", 4, 80, fees=2),
        _fill("AAPL", "buy", 6, 130),
        _fill("MSFT", "sell", 8, 400), _fill("MSFT", "buy", 20, 380, fees=5),
        _fill("MSFT", "sell", 12, 390),
    ]
    row = _one(events, {"AAPL": 1, "MSFT": 1})
    trips = ExecutionHistory(FakeStore(events)).for_strategy("s1")

    assert trips["summary"]["n_round_trips"] == 4
    assert row["realized_pnl_usd"] == trips["summary"]["total_realized_usd"]
