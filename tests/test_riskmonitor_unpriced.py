"""One unpriceable holding must not take the kill switches dark.

Written 2026-08-20 as the falsifier for the builder's read-only audit finding
H2, which contradicted a claim in docs/INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md
("the risk monitor already dropped unpriceable symbols into `unpriced`"). The
audit's claim: NavService.compute() raises PriceUnavailable at nav.py:108
BEFORE riskmonitor's per-symbol guard can run, so the `unpriced` alarm is
unreachable on the live wiring and the drawdown / daily-loss halts are simply
not evaluated while a symbol is unpriceable. One of the two claims is a
confirmed defect in our own beliefs; this test decides which.
"""

from app.fund.connectors.base import Order, Side
from app.fund.connectors.paper import PriceUnavailable
from app.fund.events import Event, EventType
from app.fund.projections.nav import NavService
from app.fund.riskmonitor import RiskMonitor


def _book_with_position(wire, symbol="AAPL"):
    wire.store.append(Event("fund", "fund", EventType.CASH_CONFIRMED,
                            {"usd_amount": 10_000}, "test"))
    order = Order(venue="paper", symbol=symbol, side=Side.BUY, qty=1.0)
    res = wire.pipe_open.propose_order(order, actor="test")
    assert res.get("status") == "pending_approval", res
    wire.pipe_open.approve_order(res["order_id"], approver="test")


def test_one_unpriceable_holding_does_not_take_the_risk_monitor_down(wire):
    _book_with_position(wire, "AAPL")

    def flaky_pricer(symbol: str) -> float:
        if symbol == "AAPL":
            raise PriceUnavailable(f"no price for {symbol}")
        return wire.conn.price(symbol)

    nav = NavService(pricer=flaky_pricer, store=wire.store)
    mon = RiskMonitor(nav_service=nav, store=wire.store, pricer=flaky_pricer)

    # The audit's claim is that this raises. The incident doc's claim is that
    # it returns with the symbol named in `unpriced`. The fund's doctrine says
    # what SHOULD happen: the tick completes, the halts are evaluated on what
    # is priceable, and the absence is a named alarm — never a dead monitor.
    out = mon.assess()

    unpriced = (out.get("unpriced_symbols") or []) \
        + (out.get("stale_nav_symbols") or [])
    assert "AAPL" in unpriced, (
        "the unpriceable symbol must be NAMED, not silently absent")
    assert any(a.get("key") in ("unpriced", "stale_nav_marks")
               for a in out.get("alarms", [])), (
        "a degraded valuation must raise a data-quality alarm")
    # The kill-switch inputs must still exist: a drawdown block computed from
    # the priceable book (marked degraded), not an exception.
    assert out.get("drawdown") is not None, (
        "the drawdown check must still be evaluated while a symbol is "
        "unpriceable — a dark monitor is the unwired kill switch")
