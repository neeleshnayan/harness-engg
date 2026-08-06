"""Unit ledger: fairness — subscriptions don't dilute, redemptions are NAV-neutral."""

import pytest

from app.fund.connectors.base import Order, Side


def subscribe(w, lp, amount, name=None):
    r = w.ledger.request_subscription(lp_id=lp, usd_amount=amount, actor="mgr", lp_name=name)
    return w.ledger.confirm_subscription(r["subscription_id"], actor="mgr")


def test_first_lp_sets_base_nav(wire):
    out = subscribe(wire, "alice", 1_000, "Alice")
    assert out["units_issued"] == pytest.approx(1_000)
    assert out["nav_per_unit"] == pytest.approx(1.0)


def test_subscription_does_not_dilute_existing_lps(wire):
    subscribe(wire, "alice", 1_000)
    subscribe(wire, "bob", 500)

    # Deploy and mark up: buy 6 AAPL @200, price -> 260. NAV 1_860 on 1_500 units.
    res = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 6), actor="rushi")
    wire.pipe_open.approve_order(res["order_id"], approver="rushi")
    wire.conn._prices["AAPL"] = 260.0

    nav_before = float(wire.nav.compute().nav_per_unit)
    assert nav_before == pytest.approx(1.24)

    carol = subscribe(wire, "carol", 620)  # 620 / 1.24 = 500 units
    assert carol["units_issued"] == pytest.approx(500, abs=1e-3)
    # The invariant: existing LPs' NAV-per-unit is unchanged by the new money.
    assert float(wire.nav.compute().nav_per_unit) == pytest.approx(nav_before)

    vals = {r["lp_id"]: r for r in wire.holdings.with_values(nav_before)}
    assert vals["alice"]["value_usd"] == pytest.approx(1_240, abs=0.01)
    assert vals["bob"]["value_usd"] == pytest.approx(620, abs=0.01)


def test_full_redemption_is_nav_neutral(wire):
    subscribe(wire, "alice", 1_000)
    subscribe(wire, "bob", 500)
    res = wire.pipe_open.propose_order(Order("paper", "AAPL", Side.BUY, 6), actor="rushi")
    wire.pipe_open.approve_order(res["order_id"], approver="rushi")
    wire.conn._prices["AAPL"] = 260.0

    navpu = float(wire.nav.compute().nav_per_unit)
    r = wire.ledger.request_redemption(lp_id="bob", actor="mgr")
    out = wire.ledger.confirm_redemption(r["redemption_id"], actor="mgr")

    assert out["usd_out"] == pytest.approx(620, abs=0.01)  # 500 units * 1.24
    assert float(wire.nav.compute().nav_per_unit) == pytest.approx(navpu)  # neutral
    remaining = {x["lp_id"] for x in wire.holdings.with_values(navpu)}
    assert remaining == {"alice"}
