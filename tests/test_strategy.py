"""Strategy layer: lifecycle transitions + per-strategy attribution."""

import pytest

from app.fund.connectors.base import Order, Side
from app.fund.events import Event, EventType
from app.fund.strategies import StrategyError


def seed_cash(w, amount):
    w.store.append(Event("fund", "fund", EventType.CASH_CONFIRMED, {"usd_amount": amount}, "test"))


def buy(w, symbol, qty, strategy_id=None):
    o = w.pipe_open.propose_order(
        Order("paper", symbol, Side.BUY, qty, strategy_id=strategy_id), actor="rushi"
    )
    return w.pipe_open.approve_order(o["order_id"], approver="rushi")


def test_strategy_lifecycle(wire):
    sid = wire.strategies.register("Momentum", actor="rushi")["strategy_id"]
    assert wire.strategies.get(sid)["state"] == "draft"

    wire.strategies.record_backtest(sid, {"sharpe": 1.4}, actor="rushi")
    assert wire.strategies.get(sid)["state"] == "backtested"

    wire.strategies.set_state(sid, "deployed", actor="rushi")
    assert wire.strategies.get(sid)["state"] == "deployed"

    wire.strategies.set_allocation(sid, 40, actor="rushi")
    assert wire.strategies.get(sid)["allocation_pct"] == pytest.approx(40.0)


def test_illegal_transition_is_rejected(wire):
    sid = wire.strategies.register("X", actor="rushi")["strategy_id"]
    with pytest.raises(StrategyError):
        wire.strategies.set_state(sid, "deployed", actor="rushi")  # draft -> deployed not allowed


def test_bad_allocation_is_rejected(wire):
    sid = wire.strategies.register("X", actor="rushi")["strategy_id"]
    with pytest.raises(StrategyError):
        wire.strategies.set_allocation(sid, 150, actor="rushi")


def test_attribution_splits_pnl_by_strategy(wire):
    seed_cash(wire, 100_000)
    mom = wire.strategies.register("Momentum", actor="rushi")["strategy_id"]
    val = wire.strategies.register("Value", actor="rushi")["strategy_id"]

    buy(wire, "AAPL", 10, strategy_id=mom)   # 10 * 200 = 2,000 invested
    buy(wire, "MSFT", 5, strategy_id=val)    # 5 * 430 = 2,150 invested (seed price)
    wire.conn._prices["AAPL"] = 260.0        # Momentum's AAPL marks up

    attr = {a["strategy_id"]: a for a in wire.attribution.with_values(wire.conn.price)}
    assert attr[mom]["exposure_usd"] == pytest.approx(2_600.0)   # 10 * 260
    assert attr[mom]["pnl_usd"] == pytest.approx(600.0)          # 2,600 - 2,000
    assert attr[val]["pnl_usd"] == pytest.approx(0.0)            # MSFT flat


def test_untagged_orders_bucket_as_discretionary(wire):
    seed_cash(wire, 100_000)
    buy(wire, "AAPL", 3)  # no strategy_id
    attr = {a["strategy_id"]: a for a in wire.attribution.with_values(wire.conn.price)}
    assert "discretionary" in attr
    assert attr["discretionary"]["exposure_usd"] == pytest.approx(600.0)  # 3 * 200
