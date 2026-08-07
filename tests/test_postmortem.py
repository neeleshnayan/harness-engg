"""Post-mortem — grades a thesis, derives realized P&L, moves it to reviewed."""

import pytest

from app.fund.connectors.base import Order, Side
from app.fund.postmortem import PostmortemError, PostmortemService
from app.fund.thesis import ThesisService


def _thesis_with_fill(wire):
    """Create a thesis, buy 10 AAPL @200 against it, and fill it."""
    theses = ThesisService(store=wire.store)
    t = theses.create({"title": "Long AAPL", "assets": ["AAPL"],
                       "claim": "re-rates on services growth",
                       "invalidation_conditions": ["services decel"]}, actor="rushi")["thesis_id"]
    sub = wire.ledger.request_subscription("lp1", 10_000, actor="mgr")
    wire.ledger.confirm_subscription(sub["subscription_id"], actor="mgr")
    res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=10, thesis_id=t), actor="op")
    wire.pipe_open.approve_order(res["order_id"], approver="op")
    return theses, t


def test_postmortem_derives_pnl_and_reviews(wire):
    theses, t = _thesis_with_fill(wire)
    # price moves up after entry -> unrealized gain
    wire.conn._prices["AAPL"] = 220.0
    pm = PostmortemService(store=wire.store, pricer=wire.conn.price)
    rec = pm.record(t, verdict="correct", actor="rushi",
                    what_happened="services beat", lessons=["size up conviction"])
    assert rec["verdict"] == "correct"
    assert theses.get(t)["has_postmortem"] is True
    got = pm.get(t)
    assert got["verdict"] == "correct"
    assert got["outcome_pnl_usd"] == 200.0        # 10 * (220 - 200)
    assert got["predicted_claim"] == "re-rates on services growth"
    # recording a post-mortem moves the thesis to its terminal reviewed state
    assert theses.get(t)["status"] == "reviewed"


def test_postmortem_rejects_bad_verdict(wire):
    _, t = _thesis_with_fill(wire)
    pm = PostmortemService(store=wire.store, pricer=wire.conn.price)
    with pytest.raises(PostmortemError):
        pm.record(t, verdict="nailed_it", actor="rushi")
