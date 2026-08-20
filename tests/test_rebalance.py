"""Tests for the rebalance plan queue.

The queue's whole purpose is to put a gap between deciding and doing, so the
tests concentrate on what can go wrong *inside that gap*: prices move, the kill
switch engages, a limit that passed at proposal time now rejects, and the same
person tries to approve their own plan.
"""

from decimal import Decimal

import pytest

from app.fund.events import EventStore, EventType
from app.fund.rebalance import RebalanceError, RebalanceService


# --- fakes -----------------------------------------------------------------

class FakeStore:
    """Minimal in-memory EventStore stand-in with the two methods used here."""

    def __init__(self):
        self.events, self._seq = [], 0

    def append(self, event):
        self._seq += 1
        self.events.append({
            "seq": self._seq,
            "type": event.type.value,
            "aggregate_id": event.aggregate_id,
            "payload": event.payload,
            "actor": event.actor,
        })
        return self._seq

    def stream(self, since_seq=0, limit=100_000):
        return [e for e in self.events if e["seq"] > since_seq][:limit]


class FakeBook:
    def __init__(self, positions):
        self.positions = {
            s: {"qty": Decimal(str(q)), "avg_price": Decimal("1")}
            for s, q in (positions or {}).items()
        }
        self.cash = Decimal("0")
        self.units_outstanding = Decimal("0")


class FakeNav:
    """``book()`` is the authoritative position fold the attribution guard checks
    against; by default it AGREES with the attribution rows, because a healthy
    book is the case every other test in this file is about."""

    def __init__(self, nav=2000.0, book=None):
        self.nav = nav
        self._book = FakeBook(book or {})

    def book(self):
        return self._book

    def compute(self):
        class S:
            total_nav_usd = Decimal(str(self.nav))
            positions = []
            breakdown = {"cash": Decimal("0")}
        return S()


class FakeAttribution:
    def __init__(self, rows):
        self.rows = rows

    def with_values(self, pricer):
        return self.rows


class FakeStrategies:
    def __init__(self):
        self.allocations = {}

    def set_allocation(self, sid, pct, actor):
        self.allocations[sid] = pct

    def list(self):
        return [{"strategy_id": "s1", "name": "Strategy One"},
                {"strategy_id": "s2", "name": "Strategy Two"}]


class FakeLimits:
    max_strategy_pct = 0.40
    min_cash_pct = 0.05


class FakeControl:
    def __init__(self, halted=False, limits=None):
        self.halted = halted
        self._limits = limits or FakeLimits()

    def is_halted(self, fresh=True):
        return self.halted

    def limits(self):
        return self._limits


class FakeConnector:
    name = "paper"


class FakePipeline:
    """Records what it was asked to do; can be told to reject specific symbols."""

    def __init__(self, reject=None):
        self._connector = FakeConnector()
        self.proposed, self.approved = [], []
        self.reject = set(reject or [])

    def propose_order(self, order, actor):
        self.proposed.append(order)
        if order.symbol in self.reject:
            return {"status": "rejected", "order_id": "x",
                    "breaches": [f"{order.symbol} breached a limit"]}
        return {"status": "pending_approval", "order_id": f"oid-{len(self.proposed)}"}

    def approve_order(self, order_id, approver):
        self.approved.append(order_id)
        return {"status": "submitted"}


PRICES = {"AAA": 100.0, "BBB": 50.0, "CCC": 25.0}


def pricer(sym):
    return PRICES[sym.upper()]


def make_service(**kw):
    rows = kw.pop("rows", [
        {"strategy_id": "s1", "positions": {"AAA": 6.0, "BBB": 4.0}},   # $600 + $200 = $800
        {"strategy_id": "s2", "positions": {"CCC": 8.0}},               # $200
    ])
    store = kw.pop("store", FakeStore())
    pipeline = kw.pop("pipeline", FakePipeline())
    control = kw.pop("control", FakeControl())
    strategies = kw.pop("strategies", FakeStrategies())
    book = kw.pop("book", None)
    if book is None:                       # the book the rows add up to
        book = {}
        for r in rows:
            for sym, q in (r.get("positions") or {}).items():
                book[sym.upper()] = book.get(sym.upper(), 0.0) + float(q)
    svc = RebalanceService(
        nav_service=FakeNav(kw.pop("nav", 2000.0), book=book),
        pricer=pricer,
        attribution=FakeAttribution(rows),
        strategies=strategies,
        pipeline=pipeline,
        control=control,
        risk_engine=None,
        store=store,
    )
    return svc, store, pipeline, control, strategies


# --- building ---------------------------------------------------------------

class TestBuild:
    def test_orders_close_the_gap_to_target(self):
        svc, *_ = make_service()
        # s1 is $800 of $2000 = 40%. Target 50% -> +$200, split by composition
        # (AAA 75%, BBB 25%) -> +$150 AAA, +$50 BBB.
        plan = svc.build({"s1": 50.0, "s2": 10.0})
        by = {o["symbol"]: o for o in plan["orders"]}
        assert by["AAA"]["side"] == "buy"
        assert by["AAA"]["notional_usd"] == pytest.approx(150.0, abs=0.5)
        assert by["AAA"]["qty"] == pytest.approx(1.5, abs=0.01)
        assert by["BBB"]["notional_usd"] == pytest.approx(50.0, abs=0.5)
        assert "CCC" not in by      # s2 already at 10%

    def test_sells_are_ordered_before_buys(self):
        """A rebalance that buys first can breach the cash floor mid-batch and
        have its own buys rejected."""
        svc, *_ = make_service()
        plan = svc.build({"s1": 10.0, "s2": 40.0})
        sides = [o["side"] for o in plan["orders"]]
        assert sides == sorted(sides, key=lambda s: 0 if s == "sell" else 1)
        assert sides[0] == "sell"

    def test_dust_is_skipped_not_traded(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 40.01, "s2": 10.0})
        assert plan["orders"] == []
        assert any(s["reason"].startswith("below the") for s in plan["skipped"])

    def test_strategy_with_no_holdings_is_reported_not_invented(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 40.0, "s2": 10.0, "empty": 25.0})
        assert "empty" in plan["unallocatable"]

    def test_cash_and_turnover_are_reported(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 50.0, "s2": 10.0})
        assert plan["cash_after_pct"] == pytest.approx(40.0, abs=0.1)
        assert plan["turnover_usd"] == pytest.approx(200.0, abs=1.0)

    def test_zero_nav_refuses(self):
        svc, *_ = make_service(nav=0.0)
        with pytest.raises(RebalanceError, match="NAV is zero"):
            svc.build({"s1": 50.0})


# --- queue ------------------------------------------------------------------

class TestQueue:
    def test_propose_queues_without_placing_orders(self):
        svc, store, pipeline, *_ = make_service()
        res = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        assert res["status"] == "pending_approval"
        assert pipeline.proposed == []          # nothing hit the venue
        assert [e["type"] for e in store.events] == [EventType.REBALANCE_PROPOSED.value]
        assert len(svc.pending()) == 1

    def test_a_no_op_plan_is_refused(self):
        svc, *_ = make_service()
        with pytest.raises(RebalanceError, match="already in place"):
            svc.propose({"s1": 40.0, "s2": 10.0}, actor="rushi")

    def test_halt_is_surfaced_on_the_pending_plan(self):
        svc, _, _, control, _ = make_service(control=FakeControl(halted=True))
        svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        assert any("HALTED" in w for w in svc.pending()[0]["warnings"])

    def test_price_drift_since_proposal_is_reported(self):
        """The reviewer must know the analysis describes a book that has moved."""
        svc, *_ = make_service()
        svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        PRICES["AAA"] = 110.0                    # +10% while the plan sat
        try:
            plan = svc.pending()[0]
            assert any(d["symbol"] == "AAA" and d["move_pct"] > 9 for d in plan["price_drift"])
            assert any("moved more than 0.5%" in w for w in plan["warnings"])
        finally:
            PRICES["AAA"] = 100.0

    def test_decline_closes_the_plan(self):
        svc, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        svc.decline(p["plan_id"], actor="vishesh", reason="too concentrated")
        assert svc.pending() == []
        assert svc.history()[0]["status"] == "declined"

    def test_cannot_act_on_a_closed_plan(self):
        svc, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        svc.decline(p["plan_id"], actor="vishesh")
        with pytest.raises(RebalanceError, match="already declined"):
            svc.approve(p["plan_id"], approver="vishesh")

    def test_unknown_plan_raises(self):
        svc, *_ = make_service()
        with pytest.raises(RebalanceError, match="no rebalance plan"):
            svc.get("nope")


# --- approval ---------------------------------------------------------------

class TestApproval:
    def test_approval_places_and_approves_each_order(self):
        svc, store, pipeline, _, strategies = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        out = svc.approve(p["plan_id"], approver="vishesh")
        assert out["status"] == "approved"
        assert out["n_placed"] == len(pipeline.proposed) == 2
        assert len(pipeline.approved) == 2
        assert strategies.allocations == {"s1": 50.0, "s2": 10.0}

    def test_orders_are_repriced_at_approval_not_replayed(self):
        """Quantities computed against stale prices would land the book
        somewhere nobody chose. The targets are the decision; the quantities are
        only ever an implementation of them.

        Concretely: at proposal, AAA is 75% of s1 and underweight, so the plan
        BUYS it. If AAA then doubles it becomes 86% of s1 and overweight — the
        correct action inverts to a SELL. Replaying the stored quantity would
        have bought more of the thing that just ran up.
        """
        svc, _, pipeline, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        stale = next(o for o in p["orders"] if o["symbol"] == "AAA")
        assert stale["side"] == "buy"

        PRICES["AAA"] = 200.0                    # price doubles while queued
        try:
            svc.approve(p["plan_id"], approver="vishesh")
        finally:
            PRICES["AAA"] = 100.0

        placed = next(o for o in pipeline.proposed if o.symbol == "AAA")
        assert placed.side.value == "sell"
        assert placed.qty != pytest.approx(stale["qty"])

    def test_a_rejected_order_does_not_abort_the_batch(self):
        svc, _, pipeline, *_ = make_service(pipeline=FakePipeline(reject={"AAA"}))
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        out = svc.approve(p["plan_id"], approver="vishesh")
        assert out["n_rejected"] == 1
        assert out["n_placed"] == 1
        assert out["rejected"][0]["symbol"] == "AAA"
        assert "breached a limit" in out["rejected"][0]["breaches"][0]

    def test_self_approval_is_recorded(self):
        svc, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        out = svc.approve(p["plan_id"], approver="rushi")
        assert out["self_approved"] is True

    def test_self_approval_can_be_forbidden(self):
        """Four-eyes, when the fund wants it enforced rather than merely noted."""
        svc, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        with pytest.raises(RebalanceError, match="cannot also approve"):
            svc.approve(p["plan_id"], approver="rushi", allow_self_approval=False)

    def test_outcome_is_event_sourced(self):
        svc, store, *_ = make_service()
        p = svc.propose({"s1": 50.0, "s2": 10.0}, actor="rushi")
        svc.approve(p["plan_id"], approver="vishesh")
        types = [e["type"] for e in store.events]
        assert types == [EventType.REBALANCE_PROPOSED.value,
                         EventType.REBALANCE_APPROVED.value]
        assert store.events[-1]["actor"] == "vishesh"


# --- destination limits -----------------------------------------------------

class TestDestinationLimits:
    """The pre-trade gate sees one order at a time. It cannot see that nine
    individually legal orders add up to a strategy above its cap."""

    def test_target_above_the_strategy_cap_is_warned_before_proposing(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 60.0, "s2": 10.0})     # cap is 40%
        assert any("above the 40% strategy cap" in w for w in plan["limit_warnings"])
        assert any("Strategy One" in w for w in plan["limit_warnings"])

    def test_target_inside_the_cap_is_not_warned(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 35.0, "s2": 10.0})
        assert not any("strategy cap" in w for w in plan["limit_warnings"])

    def test_cash_below_the_floor_is_warned(self):
        svc, *_ = make_service()
        plan = svc.build({"s1": 60.0, "s2": 38.0})     # 98% deployed, 2% cash
        assert any("below the 5% floor" in w for w in plan["limit_warnings"])

    def test_the_warning_reaches_the_reviewer_in_the_queue(self):
        svc, *_ = make_service()
        svc.propose({"s1": 60.0, "s2": 10.0}, actor="rushi")
        assert any("strategy cap" in w for w in svc.pending()[0]["warnings"])
