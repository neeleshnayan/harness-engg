"""Thesis aggregate — lifecycle, transitions, and order linkage."""

import pytest

from app.fund.thesis import ThesisError, ThesisService, ThesisStatus


def test_create_and_get(wire):
    svc = ThesisService(store=wire.store)
    t = svc.create({"title": "AAPL revisions", "assets": ["AAPL"],
                    "claim": "earnings revisions improve over 3-6mo",
                    "invalidation_conditions": ["guidance cut", "price < 180"]}, actor="rushi")
    assert t["status"] == ThesisStatus.DRAFT.value
    assert t["title"] == "AAPL revisions" and t["assets"] == ["AAPL"]
    got = svc.get(t["thesis_id"])
    assert got["invalidation_conditions"] == ["guidance cut", "price < 180"]
    assert got["order_ids"] == []


def test_requires_title(wire):
    svc = ThesisService(store=wire.store)
    with pytest.raises(ThesisError):
        svc.create({"claim": "no title"}, actor="rushi")


def test_status_transitions(wire):
    svc = ThesisService(store=wire.store)
    t = svc.create({"title": "T"}, actor="r")["thesis_id"]
    assert svc.set_status(t, "active", actor="r")["status"] == "active"
    assert svc.set_status(t, "invalidated", actor="r", note="guidance cut")["status"] == "invalidated"
    # reviewed is terminal — cannot go back to active
    svc.set_status(t, "reviewed", actor="r")
    with pytest.raises(ThesisError):
        svc.set_status(t, "active", actor="r")


def test_update_merges(wire):
    svc = ThesisService(store=wire.store)
    t = svc.create({"title": "T", "horizon": "3mo"}, actor="r")["thesis_id"]
    svc.update(t, {"horizon": "6mo", "target_exposure_pct": 15}, actor="r")
    got = svc.get(t)
    assert got["horizon"] == "6mo" and got["target_exposure_pct"] == 15
    assert got["title"] == "T"  # untouched


def test_orders_link_back_to_thesis(wire):
    """An OrderProposed event carrying thesis_id shows up under the thesis."""
    from app.fund.events import Event, EventType
    svc = ThesisService(store=wire.store)
    t = svc.create({"title": "Buy AAPL", "assets": ["AAPL"]}, actor="r")["thesis_id"]
    wire.store.append(Event("ord-1", "order", EventType.ORDER_PROPOSED,
                            {"symbol": "AAPL", "thesis_id": t}, "r"))
    assert svc.get(t)["order_ids"] == ["ord-1"]


def test_pending_order_surfaces_thesis_id(wire):
    """The approval card needs thesis_id on the pending row to render the case."""
    from app.fund.connectors.base import Order, Side
    svc = ThesisService(store=wire.store)
    t = svc.create({"title": "Long AAPL"}, actor="r")["thesis_id"]
    sub = wire.ledger.request_subscription("lp1", 10_000, actor="mgr")
    wire.ledger.confirm_subscription(sub["subscription_id"], actor="mgr")
    res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1, thesis_id=t), actor="r")
    row = next(o for o in wire.orders.pending() if o["order_id"] == res["order_id"])
    assert row["thesis_id"] == t
