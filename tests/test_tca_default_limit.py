"""The /fund/tca default must not cut the newest orders off the report.

SEPARABLE FROM THE REST OF D35, deliberately. The execution-quality
instrument does not depend on this and the chair may drop this commit without
touching anything else; it is here because the defect was found while reading
the module D35 sits beside, and a live defect in the fund's cost report is
worth more than tidiness about scope.

THE DEFECT, measured on the live log 2026-08-23 (1,254 events): ``limit``
counts EVENTS and is handed to ``EventStore.stream``, which serves the OLDEST
``limit`` of them. At the old default of 500 the report showed 20 of the 22
orders it can see, and the two it dropped were the fund's two most recent
filled orders — the 2026-08-21 experimental deployment placed specifically to
generate execution-cost observations. The whole DBA symbol vanished from
``by_symbol``. Nothing in the response said so.
"""

from __future__ import annotations

import inspect

from app.api.v1.fund import get_transaction_costs
from app.fund.tca import TransactionCosts


def _declared_default(fn, name):
    """The Query default and its upper bound, read off the live signature.

    fastapi keeps the bound in annotated-types metadata rather than as a ``le``
    attribute on this version — measured, because reading ``.le`` returns None
    and an assertion against None passes vacuously.
    """
    q = inspect.signature(fn).parameters[name].default
    caps = [m.le for m in getattr(q, "metadata", []) if hasattr(m, "le")]
    return q.default, (caps[0] if caps else None)


def test_the_tca_route_default_reaches_as_far_as_the_function_it_calls():
    """The route may not be stingier than ``tca.costs``' own default.

    Two defaults for one question is how the HTTP view came to describe a
    different set of orders from every in-process caller of the same function.
    Derived from ``costs``' signature rather than restated, so raising one and
    forgetting the other fails here.
    """
    route_default, route_cap = _declared_default(get_transaction_costs, "limit")
    fn_default = inspect.signature(TransactionCosts.costs).parameters["limit"].default
    assert route_default >= fn_default, (
        f"the HTTP default ({route_default}) reaches less far than "
        f"tca.costs' own ({fn_default}), so the route describes a different "
        f"set of orders from every other caller")
    assert route_cap is not None and route_cap >= fn_default


def test_a_growing_log_cannot_push_the_newest_order_out_of_the_default_view():
    """THE REGRESSION TEST FOR THE MEASURED DEFECT.

    Build a log longer than the OLD default of 500 events with a filled order
    at the very END, and assert the default view still contains it. Under the
    old default this fails: the newest order is invisible and the response
    reports no truncation.

    The old default is HARDCODED here rather than read from the code, so the
    test pins the boundary from the far side and cannot move with the value it
    guards.
    """
    OLD_DEFAULT = 500

    events = []
    for i in range(OLD_DEFAULT + 20):
        events.append({
            "seq": i + 1, "aggregate_id": f"noise-{i}",
            "aggregate_type": "nav", "type": "NavStruck", "actor": "system",
            "ts": "2026-08-01T00:00:00+00:00", "payload": {"total_nav_usd": 1},
        })
    tail = OLD_DEFAULT + 21
    for offset, (etype, payload) in enumerate([
        ("OrderProposed", {"qty": 5.0, "side": "buy", "venue": "alpaca",
                           "symbol": "ZZZ",
                           "impact_preview": {"quote_price": 10.0}}),
        ("OrderApproved", {"approver": "neelesh"}),
        ("OrderSubmitted", {"venue": "alpaca", "venue_ref": "r",
                            "arrival_price": 10.01}),
        ("OrderFilled", {"fees": "0", "side": "buy", "symbol": "ZZZ",
                         "avg_price": "10.02", "filled_qty": "5.0",
                         "strategy_id": "s"}),
    ]):
        events.append({
            "seq": tail + offset, "aggregate_id": "newest-order",
            "aggregate_type": "order", "type": etype, "actor": "cto",
            "ts": "2026-08-21T13:31:00+00:00", "payload": payload,
        })

    class Store:
        def stream(self, since_seq=0, limit=200):
            return [e for e in events if e["seq"] > since_seq][:limit]

    tca = TransactionCosts(Store())
    route_default, _ = _declared_default(get_transaction_costs, "limit")

    cut = tca.costs(limit=OLD_DEFAULT)
    served = tca.costs(limit=route_default)

    assert [r.order_id for r in cut] == [], (
        "the fixture must reproduce the defect at the old default, or this "
        "test is not guarding anything")
    assert [r.order_id for r in served] == ["newest-order"]
    assert served[0].symbol == "ZZZ"
