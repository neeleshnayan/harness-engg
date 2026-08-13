"""Two observers watch every fill. Exactly one gets recorded.

The settlement poller and the venue trade stream are deliberately redundant —
the stream is fast but can drop frames, the poller is slow but cannot miss. That
is only safe if the second one to arrive is harmless, because a second
ORDER_FILLED would double the position in every projection that folds the log.
"""

from __future__ import annotations

import pytest

from app.fund.connectors.base import ExecStatus, FillState, Order, Side, VenueRef
from app.fund.events import Event, EventType
from app.fund.pipeline import CommandPipeline


class MemStore:
    def __init__(self):
        self.events = []
        self._seq = 0

    def append(self, e: Event):
        self._seq += 1
        self.events.append({
            "seq": self._seq, "aggregate_id": e.aggregate_id,
            "aggregate_type": e.aggregate_type,
            "type": e.type.value if hasattr(e.type, "value") else e.type,
            "payload": e.payload, "actor": e.actor,
            "ts": f"2026-08-13T00:00:{self._seq:02d}+00:00",
        })
        return e

    def by_aggregate(self, aggregate_id):
        return [e for e in self.events if e["aggregate_id"] == str(aggregate_id)]

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


class FakeConnector:
    name = "fake"

    def __init__(self, status=None):
        self.status = status
        self.executed = 0

    def price(self, symbol): return 100.0
    def poll(self, ref): return self.status
    def execute(self, order, idempotency_key):
        self.executed += 1
        return VenueRef(venue="fake", ref_id="v1")


class FakeNav:
    def compute(self):
        raise AssertionError("not needed")


def pipeline(store, status=None):
    p = CommandPipeline.__new__(CommandPipeline)
    p._store = store
    p._connector = FakeConnector(status)
    p._nav = FakeNav()
    p._control = None
    p._explicit_risk_gate = None
    return p


def order():
    return Order(venue="fake", symbol="F", side=Side.SELL, qty=24, strategy_id="s1")


def filled(qty=24, px=13.87):
    return ExecStatus(state=FillState.FILLED, filled_qty=qty, avg_price=px, fees=0.0)


def fills_in(store):
    return [e for e in store.events if e["type"] == EventType.ORDER_FILLED.value]


# ------------------------------------------------------------- the core rule
def test_a_fill_recorded_twice_produces_one_event():
    store = MemStore()
    p = pipeline(store)
    assert p._emit_fill("o1", order(), 24, 13.87, 0) is True
    assert p._emit_fill("o1", order(), 24, 13.87, 0) is False
    assert len(fills_in(store)) == 1


def test_the_stream_then_the_poller_produces_one_event():
    """The exact live sequence: the socket sees it, the poller follows."""
    store = MemStore()
    p = pipeline(store, status=filled())

    stream_result = p._apply_status("o1", order(), filled())
    poller_result = p._apply_status("o1", order(), filled())

    assert len(fills_in(store)) == 1
    assert stream_result["duplicate"] is False
    assert poller_result["duplicate"] is True
    # Both still report the fill — the caller is not told it failed.
    assert stream_result["status"] == poller_result["status"] == "filled"


def test_the_poller_then_the_stream_produces_one_event():
    """Order of arrival must not matter."""
    store = MemStore()
    p = pipeline(store, status=filled())
    p._apply_status("o1", order(), filled())
    p._apply_status("o1", order(), filled())
    assert len(fills_in(store)) == 1


def test_different_orders_are_not_confused():
    store = MemStore()
    p = pipeline(store)
    p._emit_fill("o1", order(), 24, 13.87, 0)
    p._emit_fill("o2", order(), 10, 14.00, 0)
    assert len(fills_in(store)) == 2


def test_a_failure_recorded_twice_produces_one_event():
    store = MemStore()
    p = pipeline(store)
    rejected = ExecStatus(state=FillState.FAILED, filled_qty=0, avg_price=None,
                          fees=0.0, reason="rejected")
    first = p._apply_status("o1", order(), rejected)
    second = p._apply_status("o1", order(), rejected)
    failures = [e for e in store.events if e["type"] == EventType.ORDER_FAILED.value]
    assert len(failures) == 1
    assert first.get("duplicate") is None
    assert second["duplicate"] is True


def test_a_partially_filled_order_that_then_fails_books_the_executed_part_once():
    store = MemStore()
    p = pipeline(store)
    partial_then_dead = ExecStatus(state=FillState.FAILED, filled_qty=5,
                                   avg_price=13.9, fees=0.0, reason="canceled")
    p._apply_status("o1", order(), partial_then_dead, last_filled=0.0)
    p._apply_status("o1", order(), partial_then_dead, last_filled=0.0)
    assert len(fills_in(store)) == 1


def test_the_risk_re_evaluation_only_runs_on_a_real_fill():
    """A duplicate leaves the book unchanged, so re-running risk is pure work."""
    store = MemStore()
    p = pipeline(store, status=filled())
    calls = []

    class Nav:
        def compute(self):
            calls.append(1)
            raise RuntimeError("stop here")
    p._nav = Nav()

    p._apply_status("o1", order(), filled())     # real: attempts re-eval
    before = len(calls)
    p._apply_status("o1", order(), filled())     # duplicate: must not
    assert len(calls) == before


def test_an_unreadable_log_refuses_rather_than_double_booking():
    """If we cannot tell whether a fill was already recorded, guessing 'no' would
    double the position. Fail instead."""
    class Broken(MemStore):
        def by_aggregate(self, aggregate_id):
            raise RuntimeError("event store unavailable")

    p = pipeline(Broken())
    with pytest.raises(RuntimeError):
        p._emit_fill("o1", order(), 24, 13.87, 0)
