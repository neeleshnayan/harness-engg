"""Broker backfill tests.

The trap these guard: a prior repair adopted positions via synthetic
``alpaca_adopt_*`` events that overlap the real broker fills. Replaying the real
fills without reversing those adoptions overstates the book — during the 2026-08
investigation that would have added 15 phantom AAPL and 6 phantom MSFT to the
permanent log.
"""

from decimal import Decimal

import pytest

from app.fund.backfill import BrokerBackfill
from app.fund.events import Event, EventType
from app.fund.projections.positions import PositionsProjection


class FakeStore:
    """In-memory event log with the same stream/append surface."""

    def __init__(self, events=None):
        self._events = []
        for e in events or []:
            self.append_raw(e)

    def append_raw(self, e):
        e = dict(e)
        e["seq"] = len(self._events) + 1
        self._events.append(e)
        return e

    def append(self, event: Event):
        return self.append_raw({
            "aggregate_id": event.aggregate_id,
            "aggregate_type": event.aggregate_type,
            "type": event.type.value if hasattr(event.type, "value") else str(event.type),
            "payload": event.payload,
            "actor": event.actor,
            "ts": "2026-08-13T00:00:00",
        })

    def stream(self, since_seq: int = 0, limit: int = 200):
        return [e for e in self._events if e["seq"] > since_seq][:limit]


def _fill(agg, symbol, qty, price, side="buy", etype=None):
    return {
        "aggregate_id": agg,
        "aggregate_type": "order",
        "type": etype or EventType.ORDER_FILLED.value,
        "payload": {"symbol": symbol, "side": side, "filled_qty": qty,
                    "avg_price": price, "fees": 0},
        "actor": "system",
        "ts": "2026-08-07T00:00:00",
    }


def _book(store):
    b = PositionsProjection(store).build()
    return {s: Decimal(str(p["qty"])) for s, p in b.positions.items()}


def test_replays_only_fills_absent_from_the_log():
    store = FakeStore([_fill("coid-A", "AAPL", 2, 300)])
    broker = [
        {"client_order_id": "coid-A", "symbol": "AAPL", "side": "buy", "qty": 2, "price": 300},
        {"client_order_id": "coid-B", "symbol": "AAPL", "side": "buy", "qty": 3, "price": 310},
    ]
    plan = BrokerBackfill(store=store).plan(broker)

    assert [p.aggregate_id for p in plan.replay] == ["coid-B"]
    assert "coid-A" in plan.skipped_already_logged


def test_reverses_prior_adoption_so_real_fills_do_not_double_count():
    """The 2026-08 trap: adoption + real fills for the same shares."""
    store = FakeStore([
        # a prior repair adopted 13 AAPL with no coid
        {"aggregate_id": "alpaca_adopt_AAPL_99985", "aggregate_type": "order",
         "type": EventType.ORDER_FILLED.value,
         "payload": {"symbol": "AAPL", "qty": 13, "avg_price": 313.43, "fees": 0},
         "actor": "system", "ts": "2026-08-09T12:22:55"},
    ])
    # the broker's real history covers those same 13 shares plus 8 more
    broker = [
        {"client_order_id": f"real-{i}", "symbol": "AAPL", "side": "buy", "qty": q, "price": 313.0}
        for i, q in enumerate([13, 8])
    ]
    bf = BrokerBackfill(store=store)
    plan = bf.plan(broker)
    bf.apply(plan)

    # 13 adopted, reversed -13, replayed +21 => 21, NOT 34
    assert _book(store)["AAPL"] == Decimal("21")


def test_reverses_phantom_position_absent_at_the_broker():
    store = FakeStore([
        {"aggregate_id": "paper-1", "aggregate_type": "order",
         "type": EventType.ORDER_SUBMITTED.value,
         "payload": {"venue": "paper"}, "actor": "system", "ts": "2026-08-07T00:00:00"},
        _fill("paper-1", "AAPL", 2, 312.41),
    ])
    bf = BrokerBackfill(store=store)
    plan = bf.plan([], phantom_coids=["paper-1"])
    bf.apply(plan)

    assert _book(store).get("AAPL", Decimal("0")) == Decimal("0")


def test_apply_is_idempotent():
    store = FakeStore()
    broker = [{"client_order_id": "coid-X", "symbol": "MSFT", "side": "buy", "qty": 4, "price": 500}]
    bf = BrokerBackfill(store=store)
    bf.apply(bf.plan(broker))
    first = _book(store)["MSFT"]

    # a second run must be a no-op — the coid is now in the log
    plan2 = bf.plan(broker)
    assert plan2.replay == []
    bf.apply(plan2)

    assert _book(store)["MSFT"] == first == Decimal("4")


def test_replaying_fills_also_corrects_cash():
    """Unlogged fills leave cash overstated — the fold must charge for them."""
    store = FakeStore()
    bf = BrokerBackfill(store=store)
    bf.apply(bf.plan([
        {"client_order_id": "c1", "symbol": "NVDA", "side": "buy", "qty": 8, "price": 224.09},
    ]))
    book = PositionsProjection(store).build()

    assert book.cash == Decimal("-1792.72")  # 8 * 224.09 charged to cash


def test_plan_writes_nothing():
    store = FakeStore([_fill("coid-A", "AAPL", 2, 300)])
    before = len(store.stream(limit=1000))
    BrokerBackfill(store=store).plan(
        [{"client_order_id": "new", "symbol": "AAPL", "side": "buy", "qty": 1, "price": 300}]
    )
    assert len(store.stream(limit=1000)) == before
