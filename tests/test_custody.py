"""Custody events: dividends, interest and splits the broker applies for us."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.fund.custody import CustodyIngest
from app.fund.events import Event, EventStore, EventType
from app.fund.projections.positions import PositionsProjection


class FakeConnector:
    def __init__(self, rows, boom=False):
        self._rows = rows
        self._boom = boom
        self.calls = []

    def activities(self, after=None):
        self.calls.append(after)
        if self._boom:
            raise RuntimeError("venue unreachable")
        return list(self._rows)


class MemStore:
    """Minimal append-only store with the two methods the ingest uses."""

    def __init__(self):
        self.events = []

    def append(self, e):
        d = {"seq": len(self.events) + 1, "aggregate_id": e.aggregate_id,
             "aggregate_type": e.aggregate_type,
             "type": e.type.value if hasattr(e.type, "value") else e.type,
             "payload": e.payload, "actor": e.actor}
        self.events.append(d)
        return d

    def by_aggregate(self, aggregate_id):
        return [e for e in self.events if e["aggregate_id"] == str(aggregate_id)]

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


def div(aid="a1", symbol="INTC", amount=12.34, date="2026-08-13"):
    return {"id": aid, "activity_type": "DIV", "symbol": symbol,
            "net_amount": amount, "date": date, "per_share_amount": 0.5,
            "qty": 6.7, "description": "INTC cash dividend"}


# ------------------------------------------------------------------ dry run
def test_plan_writes_nothing():
    store = MemStore()
    out = CustodyIngest(FakeConnector([div()]), store).plan()
    assert out["applied"] is False
    assert out["counts"]["new"] == 1
    assert store.events == []
    assert "nothing was written" in out["note"]


def test_apply_appends_a_dividend_event():
    store = MemStore()
    out = CustodyIngest(FakeConnector([div()]), store).apply()
    assert out["counts"]["new"] == 1
    assert len(store.events) == 1
    e = store.events[0]
    assert e["type"] == EventType.DIVIDEND_RECEIVED.value
    assert e["payload"]["usd_amount"] == pytest.approx(12.34)
    assert e["payload"]["symbol"] == "INTC"
    assert e["payload"]["activity_id"] == "a1"


# -------------------------------------------------------------- idempotency
def test_running_twice_appends_once():
    """The venue's activity id is the idempotency key, as with client_order_id."""
    store = MemStore()
    conn = FakeConnector([div()])
    first = CustodyIngest(conn, store).apply()
    second = CustodyIngest(conn, store).apply()
    assert first["counts"]["new"] == 1
    assert second["counts"]["new"] == 0
    assert second["counts"]["skipped"] == 1
    assert "already in the event log" in second["skipped"][0]["reason"]
    assert len(store.events) == 1


def test_an_activity_without_an_id_is_refused():
    rows = [{**div(), "id": None}]
    out = CustodyIngest(FakeConnector(rows), MemStore()).apply()
    assert out["counts"]["new"] == 0
    assert "cannot be made idempotent" in out["unhandled"][0]["reason"]


# ------------------------------------------------------------- what we skip
def test_trade_activities_belong_to_the_order_path():
    rows = [{"id": "f1", "activity_type": "FILL", "symbol": "INTC", "net_amount": 100.0}]
    out = CustodyIngest(FakeConnector(rows), MemStore()).apply()
    assert out["counts"]["new"] == 0
    assert "order path" in out["skipped"][0]["reason"]


def test_an_unmodelled_type_is_surfaced_not_silently_dropped():
    """The whole failure mode this module exists to prevent."""
    rows = [{"id": "x1", "activity_type": "SPINOFF", "symbol": "ABC", "net_amount": 5.0}]
    out = CustodyIngest(FakeConnector(rows), MemStore()).apply()
    assert out["counts"]["new"] == 0
    assert out["counts"]["unhandled"] == 1
    assert "not modelled" in out["unhandled"][0]["reason"]
    assert "disagree with the venue" in out["unhandled"][0]["reason"]


def test_splits_are_refused_rather_than_guessed():
    """Alpaca reports the change in quantity, not the resulting position —
    applying a ratio guess would corrupt the share count."""
    rows = [{"id": "s1", "activity_type": "SPLIT", "symbol": "NVDA", "qty": 30.0}]
    out = CustodyIngest(FakeConnector(rows), MemStore()).apply()
    assert out["counts"]["unhandled"] == 1
    assert out["counts"]["new"] == 0


def test_a_dividend_without_an_amount_is_not_applied():
    rows = [{**div(), "net_amount": None}]
    out = CustodyIngest(FakeConnector(rows), MemStore()).apply()
    assert out["counts"]["new"] == 0
    assert out["counts"]["unhandled"] == 1


def test_interest_is_recorded_separately_from_dividends():
    rows = [{"id": "i1", "activity_type": "INT", "net_amount": 0.42, "date": "2026-08-01"}]
    store = MemStore()
    CustodyIngest(FakeConnector(rows), store).apply()
    assert store.events[0]["type"] == EventType.INTEREST_RECEIVED.value


def test_a_venue_failure_raises_rather_than_reporting_nothing_to_do():
    """An unreachable venue must not look like 'no dividends'."""
    with pytest.raises(RuntimeError):
        CustodyIngest(FakeConnector([], boom=True), MemStore()).apply()


# ---------------------------------------------------- the fold into the book
def _fold(events):
    store = MemStore()
    store.events = events
    return PositionsProjection(store).build()


def _ev(seq, etype, payload):
    return {"seq": seq, "aggregate_id": f"x{seq}", "aggregate_type": "custody",
            "type": etype, "payload": payload, "actor": "test"}


def test_a_dividend_increases_cash():
    book = _fold([
        _ev(1, EventType.CASH_CONFIRMED.value, {"usd_amount": 1000}),
        _ev(2, EventType.DIVIDEND_RECEIVED.value, {"symbol": "INTC", "usd_amount": 12.34}),
    ])
    assert book.cash == Decimal("1012.34")


def test_interest_increases_cash():
    book = _fold([
        _ev(1, EventType.CASH_CONFIRMED.value, {"usd_amount": 100}),
        _ev(2, EventType.INTEREST_RECEIVED.value, {"usd_amount": 0.5}),
    ])
    assert book.cash == Decimal("100.5")


def test_a_split_changes_shares_and_price_but_not_value():
    book = _fold([
        _ev(1, EventType.CASH_CONFIRMED.value, {"usd_amount": 10_000}),
        _ev(2, EventType.ORDER_FILLED.value,
            {"symbol": "NVDA", "side": "buy", "filled_qty": 10, "avg_price": 400}),
        _ev(3, EventType.CORPORATE_ACTION_APPLIED.value,
            {"symbol": "NVDA", "old_qty": 10, "new_qty": 40}),
    ])
    pos = book.positions["NVDA"]
    assert pos["qty"] == Decimal("40")
    assert pos["avg_price"] == Decimal("100")
    # The position is worth exactly what it was worth before.
    assert pos["qty"] * pos["avg_price"] == Decimal("4000")


def test_a_split_on_a_symbol_we_do_not_hold_is_ignored():
    book = _fold([
        _ev(1, EventType.CASH_CONFIRMED.value, {"usd_amount": 100}),
        _ev(2, EventType.CORPORATE_ACTION_APPLIED.value,
            {"symbol": "ZZZZ", "old_qty": 1, "new_qty": 2}),
    ])
    assert "ZZZZ" not in book.positions
    assert book.cash == Decimal("100")
