"""Async fill settlement + reconciliation, with a scriptable fake venue."""

import pytest

from app.fund.connectors.base import (
    Balance, ExecStatus, FillState, Order, Position, Quote, Side, ValidationResult, VenueRef,
)
from app.fund.events import Event, EventType
from app.fund.pipeline import CommandPipeline
from app.fund.projections.nav import NavService
from app.fund.projections.orders import OrdersProjection
from app.fund.projections.positions import PositionsProjection
from app.fund.reconcile import Reconciler
from app.fund.risk import RiskGate, RiskLimits


class FakeAsync:
    """A venue whose poll() returns scripted statuses (async settlement)."""
    name = "fake"

    def __init__(self):
        self.seq = []
        self.pos = []

    def price(self, s): return 200.0
    def quote(self, o): return Quote(o.symbol, o.limit_price or 200.0)
    def validate(self, o): return ValidationResult(ok=o.qty > 0, errors=[])
    def execute(self, o, idempotency_key): return VenueRef("fake", "ref-" + idempotency_key)
    def poll(self, ref): return self.seq.pop(0) if self.seq else ExecStatus(state=FillState.PENDING)
    def positions(self): return self.pos
    def balances(self): return [Balance("fake", "USD", 0.0)]
    # This stub plays a REAL venue with its own persistent book, so it must say
    # so: Reconciler.run() now refuses to write mismatch events against a venue
    # that cannot independently persist positions (the mock-mode footgun).
    def account_info(self): return {"configured": True, "equity": 0.0}


def build(store):
    conn = FakeAsync()
    proj = PositionsProjection(store)
    nav = NavService(pricer=conn.price, store=store, projection=proj)
    gate = RiskGate(RiskLimits(max_position_pct=10, max_order_notional_pct=10, min_cash_buffer=0))
    pipe = CommandPipeline(connector=conn, nav_service=nav, store=store, risk_gate=gate)
    return conn, proj, pipe


def seed(store, amt):
    store.append(Event("fund", "fund", EventType.CASH_CONFIRMED, {"usd_amount": amt}, "t"))


def test_async_fill_settles_via_poller(wire):
    store = wire.store
    conn, proj, pipe = build(store)
    seed(store, 100_000)
    # approve polls once -> still pending; settlement poll -> filled
    conn.seq = [ExecStatus(state=FillState.PENDING),
                ExecStatus(state=FillState.FILLED, filled_qty=10, avg_price=200.0)]

    r = pipe.propose_order(Order("fake", "AAPL", Side.BUY, 10), actor="rushi")
    out = pipe.approve_order(r["order_id"], approver="rushi")
    assert out["status"] == "working"          # not filled on the first poll
    assert proj.build().positions == {}        # nothing booked yet

    orders = OrdersProjection(store)
    assert len(orders.in_flight()) == 1

    res = pipe.poll_open_orders()
    assert res["results"][0]["status"] == "filled"
    assert proj.build().positions["AAPL"]["qty"] == pytest.approx(10)
    assert orders.in_flight() == []            # terminal -> leaves the in-flight set


def test_partial_then_fill_books_once(wire):
    store = wire.store
    conn, proj, pipe = build(store)
    seed(store, 100_000)
    conn.seq = [ExecStatus(state=FillState.PARTIAL, filled_qty=4, avg_price=200.0)]
    r = pipe.propose_order(Order("fake", "AAPL", Side.BUY, 10), actor="rushi")
    assert pipe.approve_order(r["order_id"], approver="rushi")["status"] == "working"
    assert proj.build().positions == {}        # a partial is informational, not booked

    conn.seq = [ExecStatus(state=FillState.FILLED, filled_qty=10, avg_price=200.0)]
    pipe.poll_open_orders()
    assert proj.build().positions["AAPL"]["qty"] == pytest.approx(10)  # booked once, in full


def test_reconcile_flags_position_mismatch(wire):
    store = wire.store
    conn, proj, pipe = build(store)
    seed(store, 100_000)
    conn.seq = [ExecStatus(state=FillState.FILLED, filled_qty=5, avg_price=200.0)]
    r = pipe.propose_order(Order("fake", "AAPL", Side.BUY, 5), actor="rushi")
    pipe.approve_order(r["order_id"], approver="rushi")   # book says 5 AAPL

    conn.pos = [Position("fake", "AAPL", 3.0, 200.0)]     # venue says 3
    rep = Reconciler(connector=conn, store=store, projection=proj).run()
    assert rep["mismatches"][0]["symbol"] == "AAPL"
    assert rep["mismatches"][0]["expected"] == pytest.approx(5)
    assert rep["mismatches"][0]["actual"] == pytest.approx(3)
    assert any(e["type"] == EventType.RECONCILIATION_MISMATCH.value for e in store.stream())
