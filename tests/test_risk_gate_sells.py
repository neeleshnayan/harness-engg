"""A risk limit must never prevent de-risking."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.fund.connectors.base import Order, Side
from app.fund.projections.nav import NavSnapshot
from app.fund.risk import RiskGate, RiskLimits


def nav(total=2000.0, cash=500.0, positions=None):
    return NavSnapshot(
        ts="2026-08-13T00:00:00+00:00",
        total_nav_usd=Decimal(str(total)),
        units_outstanding=Decimal("1000"),
        nav_per_unit=Decimal("2"),
        breakdown={"positions": Decimal(str(total - cash)), "cash": Decimal(str(cash))},
        positions=[{"symbol": s, "qty": Decimal("1"), "mark": Decimal(str(v)),
                    "usd_value": Decimal(str(v))} for s, v in (positions or {}).items()],
    )


def gate(**kw):
    return RiskGate(limits=RiskLimits(**kw))


def order(side, qty, symbol="F"):
    return Order(venue="alpaca", symbol=symbol, side=side, qty=qty)


def test_exiting_a_position_bigger_than_the_order_cap_is_allowed():
    """The bug: F at 16.4% of NAV could not be sold under a 15% order cap —
    in one order or any number of them. A limit meant to stop an oversized
    deployment was forbidding de-risking."""
    g = gate(max_order_notional_pct=0.15, max_position_pct=1.0, min_cash_pct=0.0)
    d = g.check(order(Side.SELL, 24), quote_price=13.88, nav=nav(positions={"F": 333.12}))
    assert d.ok, d.breaches


def test_an_oversized_buy_is_still_capped():
    g = gate(max_order_notional_pct=0.15, max_position_pct=1.0, min_cash_pct=0.0)
    d = g.check(order(Side.BUY, 40), quote_price=13.88, nav=nav(cash=2000.0))
    assert not d.ok
    assert any("order notional" in b for b in d.breaches)


def test_selling_beyond_the_position_is_capped_because_it_opens_a_short():
    """Closing is exempt; the part that flips short is a deployment."""
    g = gate(max_order_notional_pct=0.15, max_position_pct=1.0, min_cash_pct=0.0)
    # holds $100 of F, sells $700 worth -> $600 of new short, over the $300 cap
    d = g.check(order(Side.SELL, 50), quote_price=14.0, nav=nav(positions={"F": 100.0}))
    assert not d.ok
    assert any("short this sell would open" in b for b in d.breaches)


def test_selling_a_symbol_we_do_not_hold_is_capped_in_full():
    g = gate(max_order_notional_pct=0.15, max_position_pct=1.0, min_cash_pct=0.0)
    d = g.check(order(Side.SELL, 40), quote_price=14.0, nav=nav())
    assert not d.ok


def test_a_small_sell_inside_the_cap_still_passes():
    g = gate(max_order_notional_pct=0.15, max_position_pct=1.0, min_cash_pct=0.0)
    d = g.check(order(Side.SELL, 5), quote_price=14.0, nav=nav(positions={"F": 333.0}))
    assert d.ok, d.breaches


def test_the_concentration_limit_still_applies_to_buys():
    """Relaxing the ORDER cap must not relax the POSITION cap."""
    g = gate(max_order_notional_pct=1.0, max_position_pct=0.20, min_cash_pct=0.0)
    d = g.check(order(Side.BUY, 40), quote_price=14.0, nav=nav(cash=2000.0))
    assert not d.ok
    assert any("of NAV" in b for b in d.breaches)
