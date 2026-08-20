"""The paper venue must never fabricate a price.

Pinned after the 2026-08-20 incident: a transient feed miss on GLD returned the
connector's hardcoded `_DEFAULT_PRICE = 100.0`, the risk monitor read a +2.9%
position as "down -75.14%", the machinery-test loss rule fired, the auto-policy
approved the exit (its first live fire, every envelope check passing on the
fabricated input), the fill executed at the same $100.00, and the real $133.21
ledger loss tripped the daily-loss halt. Every control worked; the input was
made up. These tests pin the fix: absence is an ERROR, never a number.
"""

import pytest

from app.fund.connectors.base import FillState, Order, Side
from app.fund.connectors.paper import PaperConnector, PriceUnavailable


def _order(symbol="GLD", side=Side.SELL, qty=0.424471):
    return Order(venue="paper", symbol=symbol, side=side, qty=qty)


def test_an_unpriceable_symbol_raises_instead_of_fabricating_100(wire):
    conn = wire.conn  # seeded with AAPL only; live pricer absent
    with pytest.raises(PriceUnavailable):
        conn.price("GLD")


def test_a_live_pricer_miss_falls_back_to_a_seed_only_if_one_was_chosen(wire):
    conn = PaperConnector(prices={"AAPL": 200.0}, live_pricer=lambda s: None)
    assert conn.price("AAPL") == 200.0          # a seed is a CHOSEN number
    with pytest.raises(PriceUnavailable):       # a default was a fabricated one
        conn.price("GLD")


def test_an_order_on_an_unpriceable_symbol_fails_and_leaves_the_book_alone(wire):
    conn = wire.conn
    book_before = conn._book()
    ref = conn.execute(_order(), idempotency_key="incident-regression-1")
    status = conn.poll(ref)
    assert status.state == FillState.FAILED
    assert status.avg_price is None, "a failed order must not carry a price"
    assert status.filled_qty == 0.0
    assert "refuses to fabricate" in (status.reason or "")
    assert conn._book() == book_before, "a failed order must not move the book"


def test_a_priced_order_still_fills_normally(wire):
    conn = wire.conn
    ref = conn.execute(_order(symbol="AAPL", side=Side.BUY, qty=1.0),
                       idempotency_key="incident-regression-2")
    status = conn.poll(ref)
    assert status.state == FillState.FILLED
    assert status.avg_price == 200.0


def test_the_failed_order_is_idempotent_like_any_other(wire):
    conn = wire.conn
    a = conn.execute(_order(), idempotency_key="incident-regression-3")
    b = conn.execute(_order(), idempotency_key="incident-regression-3")
    assert a.ref_id == b.ref_id, "replaying a failed order must not place a second one"
