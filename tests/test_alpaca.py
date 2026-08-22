"""AlpacaConnector — pure mappers + venue-side idempotency (no network)."""

import pytest

from app.fund.connectors.alpaca import AlpacaConnector, map_positions, map_status
from app.fund.connectors.base import FillState, Order, Side


class FakeOrder:
    def __init__(self, id="oid", client_order_id=None, status="new", filled_qty=0, filled_avg_price=None):
        self.id = id
        self.client_order_id = client_order_id
        self.status = status
        self.filled_qty = filled_qty
        self.filled_avg_price = filled_avg_price


class FakePos:
    def __init__(self, symbol, qty, avg_entry_price):
        self.symbol = symbol
        self.qty = qty
        self.avg_entry_price = avg_entry_price


class FakeTrading:
    def __init__(self, existing=None):
        self.existing = existing
        self.submitted = []

    def get_order_by_client_order_id(self, coid):
        if self.existing is not None and self.existing.client_order_id == coid:
            return self.existing
        raise Exception("order not found")

    def submit_order(self, order_data):
        self.submitted.append(order_data)
        return FakeOrder(id="new-order-id")


def test_map_status_filled():
    s = map_status("filled", "10", "214.5")
    assert s.state == FillState.FILLED and s.filled_qty == 10 and s.avg_price == 214.5


def test_map_status_partial_and_failed_and_pending():
    assert map_status("partially_filled", "3", "100").state == FillState.PARTIAL
    rej = map_status("rejected", 0, None)
    assert rej.state == FillState.FAILED and rej.reason == "rejected"
    assert map_status("accepted", 0, None).state == FillState.PENDING


def test_map_positions():
    pos = map_positions([FakePos("AAPL", "6", "210.0")])
    assert pos[0].symbol == "AAPL" and pos[0].qty == 6 and pos[0].avg_price == 210.0


def test_idempotency_returns_existing_without_resubmit():
    existing = FakeOrder(id="already-there", client_order_id="ord-1", status="filled")
    trading = FakeTrading(existing=existing)
    conn = AlpacaConnector(trading=trading, paper=True)
    ref = conn.execute(Order("alpaca", "AAPL", Side.BUY, 1), idempotency_key="ord-1")
    assert ref.ref_id == "already-there"
    assert trading.submitted == []  # never double-submitted


def test_price_cache_ttl():
    clock = {"t": 0.0}

    class Conn(AlpacaConnector):
        def __init__(self, **kw):
            super().__init__(**kw)
            self.fetches = 0

        def _fetch_price(self, symbol):
            self.fetches += 1
            return 100.0 + self.fetches  # changes each real fetch

    # paper= is REQUIRED as of 2026-08-22 (K8): the connector no longer
    # guesses, and ALPACA_PAPER no longer decides for it.
    c = Conn(price_ttl=5, clock=lambda: clock["t"], paper=True)
    p1 = c.price("AAPL")
    p2 = c.price("AAPL")          # within TTL -> cached, no refetch
    assert p1 == p2 and c.fetches == 1
    clock["t"] = 6.0              # past TTL
    p3 = c.price("AAPL")          # refetch
    assert c.fetches == 2 and p3 != p1


def test_fresh_submit_sets_client_order_id():
    class Conn(AlpacaConnector):
        # avoid importing alpaca-py for the request object in this unit test
        def _build_request(self, order, client_order_id):
            return {"symbol": order.symbol, "client_order_id": client_order_id}

    trading = FakeTrading(existing=None)
    conn = Conn(trading=trading, paper=True)
    ref = conn.execute(Order("alpaca", "AAPL", Side.BUY, 2), idempotency_key="ord-2")
    assert ref.ref_id == "new-order-id"
    assert trading.submitted[0]["client_order_id"] == "ord-2"
