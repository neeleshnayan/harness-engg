"""Analytical risk layer — concentration + scenario shock over a live book."""

from app.fund.connectors.base import Order, Side


def _seed_book(wire):
    """10k cash, then buy 10 AAPL @200 -> NAV 10k (20% AAPL, 80% cash)."""
    sub = wire.ledger.request_subscription("lp1", 10_000, actor="mgr")
    wire.ledger.confirm_subscription(sub["subscription_id"], actor="mgr")
    res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=10), actor="op")
    wire.pipe_open.approve_order(res["order_id"], approver="op")


def test_concentration(wire):
    _seed_book(wire)
    a = wire.risk.analytics()
    assert a["nav_usd"] == 10_000.0
    assert a["cash_pct"] == 80.0
    assert a["largest_position"]["symbol"] == "AAPL"
    assert a["largest_position"]["weight_pct"] == 20.0
    assert a["n_positions"] == 1
    # default stress scenarios are attached
    labels = [s["label"] for s in a["scenarios"]]
    assert any("-20%" in l for l in labels)


def test_shock_single_name(wire):
    _seed_book(wire)
    s = wire.risk.shock("AAPL", -20.0)
    assert s["pnl_usd"] == -400.0          # 20% of the 2,000 AAPL position
    assert s["nav_after"] == 9_600.0
    assert s["affected"][0]["symbol"] == "AAPL"


def test_shock_whole_book(wire):
    _seed_book(wire)
    s = wire.risk.shock(None, -10.0)
    assert s["pnl_usd"] == -200.0          # only the 2,000 invested is exposed
    assert s["nav_after"] == 9_800.0
