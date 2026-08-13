"""Execution history: round-trips, outcomes and the P&L distribution."""

from __future__ import annotations

import pytest

from app.fund.execution import (
    BREAKEVEN_BAND_PCT, ExecutionHistory, histogram, streaks, summarise,
)


class FakeStore:
    """Just enough EventStore to fold over."""

    def __init__(self, events):
        self._events = events

    def stream(self, since_seq: int = 0, limit: int = 100_000):
        return list(self._events)


def fill(seq, ts, symbol, side, qty, price, strategy="s1", fees=0.0):
    return {
        "seq": seq,
        "ts": ts,
        "type": "OrderFilled",
        "payload": {
            "strategy_id": strategy, "symbol": symbol, "side": side,
            "filled_qty": qty, "avg_price": price, "fees": fees,
            "order_id": f"o{seq}", "venue": "alpaca",
        },
    }


def hist_for(events):
    return ExecutionHistory(FakeStore(events)).for_strategy("s1")


def test_no_fills_is_unmeasurable_not_zero():
    out = ExecutionHistory(FakeStore([])).for_strategy("s1")
    assert out["measurable"] is False
    assert out["summary"]["measurable"] is False
    assert "no fills" in out["reason"]
    # Shape matches a populated strategy so callers need no special case.
    assert (out["n_fills"], out["n_round_trips"]) == (0, 0)


def test_buys_alone_produce_no_round_trips():
    out = hist_for([fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0)])
    assert out["n_fills"] == 1
    assert out["n_round_trips"] == 0
    # An open position is not a result. Refusing to summarise is the point.
    assert out["summary"]["measurable"] is False
    assert out["open_positions"]["AAPL"]["qty"] == 10.0


def test_simple_round_trip_realizes_pnl():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "AAPL", "sell", 10, 110.0),
    ])
    assert out["n_round_trips"] == 1
    t = out["round_trips"][0]
    assert t["pnl_usd"] == pytest.approx(100.0)
    assert t["pnl_pct"] == pytest.approx(10.0)
    assert t["outcome"] == "win"
    assert t["exit_ts"] == "2026-02-01T00:00:00Z"
    assert t["avg_entry_ts"] == "2026-01-01T00:00:00Z"
    assert out["open_positions"] == {}


def test_partial_sale_closes_only_what_it_sold():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "AAPL", "sell", 4, 120.0),
    ])
    t = out["round_trips"][0]
    assert t["qty"] == 4.0
    assert t["pnl_usd"] == pytest.approx(80.0)
    # the untouched 6 shares keep their basis
    assert out["open_positions"]["AAPL"]["qty"] == 6.0
    assert out["open_positions"]["AAPL"]["cost_basis_usd"] == pytest.approx(600.0)


def test_average_cost_basis_across_multiple_buys():
    # 10 @ 100 then 10 @ 200 -> average 150. Selling 20 @ 150 is flat, not a
    # win from the first lot and a loss from the second.
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0),
        fill(2, "2026-01-15T00:00:00Z", "AAPL", "buy", 10, 200.0),
        fill(3, "2026-02-01T00:00:00Z", "AAPL", "sell", 20, 150.0),
    ])
    t = out["round_trips"][0]
    assert t["avg_entry_price"] == pytest.approx(150.0)
    assert t["pnl_usd"] == pytest.approx(0.0)
    assert t["outcome"] == "breakeven"


def test_fees_reduce_realized_pnl():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "AAPL", "sell", 10, 110.0, fees=25.0),
    ])
    t = out["round_trips"][0]
    assert t["gross_pnl_usd"] == pytest.approx(100.0)
    assert t["pnl_usd"] == pytest.approx(75.0)


def test_tiny_move_is_a_scratch_not_a_win():
    # A move inside the breakeven band must not inflate the win rate.
    px = 100.0 * (1 + BREAKEVEN_BAND_PCT / 200.0)
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "AAPL", "buy", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "AAPL", "sell", 10, px),
    ])
    t = out["round_trips"][0]
    assert t["pnl_usd"] > 0
    assert t["outcome"] == "breakeven"
    assert out["summary"]["winners"] == 0
    assert out["summary"]["breakevens"] == 1


def test_summary_counts_and_payoff():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "buy", 10, 100.0),
        fill(2, "2026-01-05T00:00:00Z", "A", "sell", 10, 130.0),   # +300
        fill(3, "2026-01-06T00:00:00Z", "B", "buy", 10, 100.0),
        fill(4, "2026-01-09T00:00:00Z", "B", "sell", 10, 90.0),    # -100
        fill(5, "2026-01-10T00:00:00Z", "C", "buy", 10, 100.0),
        fill(6, "2026-01-14T00:00:00Z", "C", "sell", 10, 90.0),    # -100
    ])
    s = out["summary"]
    assert (s["winners"], s["losers"]) == (1, 2)
    assert s["win_rate"] == pytest.approx(1 / 3, abs=1e-4)   # reported to 4dp
    assert s["total_realized_usd"] == pytest.approx(100.0)
    assert s["payoff_ratio"] == pytest.approx(3.0)      # 300 avg win / 100 avg loss
    assert s["profit_factor"] == pytest.approx(1.5)     # 300 gross win / 200 gross loss
    # One winner IS the whole gross profit here — the concentration must show.
    assert s["top_trade_share_of_gross_profit"] == pytest.approx(1.0)


def test_strategies_are_kept_apart():
    events = [
        fill(1, "2026-01-01T00:00:00Z", "A", "buy", 10, 100.0, strategy="s1"),
        fill(2, "2026-01-05T00:00:00Z", "A", "sell", 10, 110.0, strategy="s1"),
        fill(3, "2026-01-01T00:00:00Z", "B", "buy", 10, 100.0, strategy="s2"),
    ]
    h = ExecutionHistory(FakeStore(events))
    assert h.for_strategy("s1")["n_round_trips"] == 1
    assert h.for_strategy("s2")["n_round_trips"] == 0
    assert len(h.all()) == 2


def test_untagged_fills_land_in_discretionary():
    e = fill(1, "2026-01-01T00:00:00Z", "A", "buy", 10, 100.0)
    e["payload"]["strategy_id"] = None
    rows = ExecutionHistory(FakeStore([e])).all()
    assert rows[0]["strategy_id"] == "discretionary"


def test_non_fill_events_are_ignored():
    events = [
        {"seq": 1, "ts": "2026-01-01T00:00:00Z", "type": "nav.struck", "payload": {}},
        fill(2, "2026-01-02T00:00:00Z", "A", "buy", 10, 100.0),
    ]
    assert hist_for(events)["n_fills"] == 1


def test_selling_without_a_position_opens_a_short_and_realizes_nothing():
    out = hist_for([fill(1, "2026-01-01T00:00:00Z", "A", "sell", 10, 100.0)])
    assert out["n_round_trips"] == 0
    assert out["open_positions"]["A"]["qty"] == -10.0


def test_histogram_needs_spread_and_says_so():
    assert histogram([1.0])["measurable"] is False
    assert histogram([2.0, 2.0, 2.0])["measurable"] is False
    h = histogram([-5.0, -1.0, 0.5, 3.0, 8.0], bins=4)
    assert h["measurable"] is True
    assert sum(b["count"] for b in h["bins"]) == 5
    assert h["min_pct"] == -5.0 and h["max_pct"] == 8.0


def test_summarise_on_nothing_is_unmeasurable():
    assert summarise([])["measurable"] is False


# ------------------------------------------------- shorts, streaks, holding
def test_covering_a_short_realizes_pnl():
    """A buy that closes a short is a round-trip — profit when price FELL."""
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "sell", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "A", "buy", 10, 80.0),
    ])
    assert out["n_round_trips"] == 1
    t = out["round_trips"][0]
    assert t["side"] == "short"
    assert t["pnl_usd"] == pytest.approx(200.0)
    assert t["outcome"] == "win"
    assert out["open_positions"] == {}


def test_short_loses_when_price_rises():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "sell", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "A", "buy", 10, 120.0),
    ])
    assert out["round_trips"][0]["pnl_usd"] == pytest.approx(-200.0)


def test_buy_covering_then_flipping_long_leaves_the_remainder_open():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "sell", 10, 100.0),
        fill(2, "2026-02-01T00:00:00Z", "A", "buy", 15, 90.0),
    ])
    assert out["n_round_trips"] == 1
    assert out["round_trips"][0]["qty"] == 10.0
    assert out["open_positions"]["A"]["qty"] == 5.0


def test_by_side_keeps_longs_and_shorts_apart():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "buy", 10, 100.0),
        fill(2, "2026-01-05T00:00:00Z", "A", "sell", 10, 110.0),    # long +100
        fill(3, "2026-01-06T00:00:00Z", "B", "sell", 10, 100.0),
        fill(4, "2026-01-09T00:00:00Z", "B", "buy", 10, 130.0),     # short -300
    ])
    s = out["by_side"]
    assert s["long"]["total_realized_usd"] == pytest.approx(100.0)
    assert s["short"]["total_realized_usd"] == pytest.approx(-300.0)
    assert s["all"]["total_realized_usd"] == pytest.approx(-200.0)


def test_streaks_ignore_breakevens():
    trips = [{"outcome": o} for o in
             ["win", "win", "breakeven", "win", "loss", "loss", "loss"]]
    s = streaks(trips)
    assert s["longest_win_streak"] == 3      # the scratch does not break the run
    assert s["longest_loss_streak"] == 3
    assert s["current_streak_kind"] == "loss"
    assert s["current_streak"] == 3


def test_holding_periods_split_by_outcome():
    out = hist_for([
        fill(1, "2026-01-01T00:00:00Z", "A", "buy", 10, 100.0),
        fill(2, "2026-01-11T00:00:00Z", "A", "sell", 10, 110.0),   # winner, 10d
        fill(3, "2026-01-01T00:00:00Z", "B", "buy", 10, 100.0),
        fill(4, "2026-01-03T00:00:00Z", "B", "sell", 10, 90.0),    # loser, 2d
    ])
    h = out["summary"]["holding"]
    assert h["avg_days_winners"] == pytest.approx(10.0)
    assert h["avg_days_losers"] == pytest.approx(2.0)
    assert h["longest_days"] == pytest.approx(10.0)


def test_holding_unknown_without_timestamps():
    events = [
        fill(1, None, "A", "buy", 10, 100.0),
        fill(2, None, "A", "sell", 10, 110.0),
    ]
    for e in events:
        e.pop("ts", None)
    h = hist_for(events)["summary"]["holding"]
    assert h["measurable"] is False
