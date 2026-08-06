"""Spine: event store, command pipeline, idempotency, risk, NAV."""

import pytest

from app.fund.connectors.base import Order, Side
from app.fund.events import Event, EventType
from app.fund.pipeline import CommandError


def seed_cash(w, amount):
    w.store.append(Event("fund", "fund", EventType.CASH_CONFIRMED, {"usd_amount": amount}, "test"))


def test_event_seq_is_monotonic(wire):
    for _ in range(3):
        seed_cash(wire, 1.0)
    seqs = [e["seq"] for e in wire.store.stream()]
    assert seqs == [1, 2, 3]


def test_propose_approve_fill(wire):
    seed_cash(wire, 10_000)
    res = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 10), actor="rushi")
    assert res["status"] == "pending_approval"
    out = wire.pipe_open.approve_order(res["order_id"], approver="rushi")
    assert out["status"] == "filled" and out["filled_qty"] == 10

    book = wire.proj.build()
    assert book.positions["AAPL"]["qty"] == pytest.approx(10)
    assert book.cash == pytest.approx(8_000)  # 10_000 - 10*200


def test_double_approve_is_refused(wire):
    seed_cash(wire, 10_000)
    res = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 5), actor="rushi")
    wire.pipe_open.approve_order(res["order_id"], approver="rushi")
    with pytest.raises(CommandError):
        wire.pipe_open.approve_order(res["order_id"], approver="rushi")


def test_risk_rejects_oversized_order(wire):
    seed_cash(wire, 10_000)
    # 40 * 200 = 8_000 = 80% of NAV, over the 50% single-order cap.
    res = wire.pipe.propose_order(Order("paper", "AAPL", Side.BUY, 40), actor="rushi")
    assert res["status"] == "rejected"
    assert any("notional" in b for b in res["breaches"])
    # A rejection is itself an event (audit completeness).
    assert any(e["type"] == EventType.ORDER_REJECTED.value for e in wire.store.stream())


def test_pending_queue_reflects_approvals(wire):
    seed_cash(wire, 10_000)
    a = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 2), actor="rushi")
    b = wire.pipe_open.propose_order(Order("paper", "MSFT", Side.BUY, 1), actor="rushi")
    pending_ids = {o["order_id"] for o in wire.orders.pending()}
    assert pending_ids == {a["order_id"], b["order_id"]}

    wire.pipe_open.approve_order(a["order_id"], approver="rushi")
    pending_ids = {o["order_id"] for o in wire.orders.pending()}
    assert pending_ids == {b["order_id"]}  # approved order leaves the queue


def test_nav_holds_across_a_fill(wire):
    seed_cash(wire, 10_000)
    res = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 10), actor="rushi")
    wire.pipe_open.approve_order(res["order_id"], approver="rushi")
    snap = wire.nav.strike()
    assert snap.total_nav_usd == pytest.approx(10_000)  # 2_000 AAPL + 8_000 cash
    assert wire.nav.latest()["total_nav_usd"] == pytest.approx(10_000)
