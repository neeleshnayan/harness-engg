"""Mark sanity on manually approved orders — the $128.26 check.

The incident (docs/INCIDENT_GLD_PHANTOM_PRICE_2026-08-20.md): a GLD sell was
proposed against a quote of $100.00 while the fund's own last struck mark for
GLD was $415.04. A human approved it, it filled, and the fund lost $128.26. The
auto-approval policy has refused that exact shape since v2; the manual path —
the path the phantom actually took — had no check at all.

Every test here pins one way this guard could fail to close, and the first one
pins the incident's own numbers so the fix cannot be "improved" into letting it
through again.
"""

from __future__ import annotations

import pytest

from app.fund import marksanity
from app.fund.autopolicy import MAX_MARK_MOVE_VS_STRIKE_PCT


class MemStore:
    """Enough of the event store for the gatherer: dict rows with the four keys
    it reads. Mirrors what pgstore.stream() returns."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def add(self, type_, payload, aggregate_id="x", ts="2026-08-20T08:00:00Z"):
        self.rows.append({"type": type_, "payload": payload,
                          "aggregate_id": aggregate_id, "ts": ts})
        return self

    def stream(self, since_seq=0, limit=100_000):
        return list(self.rows)


def _proposed(store, order_id, symbol, quote_price, side="sell", qty=1.0):
    return store.add("OrderProposed",
                     {"symbol": symbol, "side": side, "qty": qty,
                      "impact_preview": {"quote_price": quote_price}},
                     aggregate_id=order_id)


def _struck(store, marks, ts="2026-08-20T07:30:00Z"):
    return store.add("NavStruck",
                     {"ts": ts, "total_nav_usd": 2011.81,
                      "positions": [{"symbol": s, "mark": m}
                                    for s, m in marks.items()]},
                     aggregate_id="nav", ts=ts)


def _filled(store, symbol, side, qty):
    return store.add("OrderFilled",
                     {"symbol": symbol, "side": side, "filled_qty": qty})


# ---------------------------------------------------------------- the incident


def test_the_gld_phantom_is_refused_with_both_numbers_in_the_reason():
    """2026-08-20: $100.00 proposed against a $415.04 strike. $128.26 lost.

    If this test ever passes an approval, the exact incident is live again.
    """
    s = MemStore()
    _struck(s, {"GLD": 415.04}, ts="2026-08-20T07:30:00Z")
    _filled(s, "GLD", "buy", 1.0)          # the fund held it
    _proposed(s, "ord-gld", "GLD", 100.00)

    v = marksanity.check(s, "ord-gld")
    assert v["refuse"] is True
    assert v["basis"] == "corroborated"
    # 1 - 100/415.04 = 75.9%
    assert abs(v["move_pct"] - 75.9) < 0.1
    assert v["quote_price"] == 100.00
    assert v["reference_mark"] == 415.04
    # BOTH numbers must be in the sentence the CEO reads. "refused: mark
    # sanity" is a verdict word; these are the facts behind it.
    assert "100.00" in v["reason"]
    assert "415.04" in v["reason"]
    assert "75.9%" in v["reason"]
    assert "30%" in v["reason"]


def test_the_bound_is_autopolicys_constant_and_not_a_second_copy():
    """One threshold, one home. A copy is a threshold that has already drifted."""
    import inspect
    src = inspect.getsource(marksanity)
    assert "from app.fund.autopolicy import MAX_MARK_MOVE_VS_STRIKE_PCT" in src
    # No literal re-declaration of the number anywhere in the module.
    assert "MAX_MARK_MOVE_VS_STRIKE_PCT = " not in src
    s = MemStore()
    _struck(s, {"GLD": 100.0})
    _filled(s, "GLD", "buy", 1.0)
    _proposed(s, "o", "GLD", 100.0)
    assert marksanity.check(s, "o")["bound_pct"] == MAX_MARK_MOVE_VS_STRIKE_PCT


# ------------------------------------------------------------- the boundary --


def test_a_move_inside_the_bound_passes_and_a_move_past_it_does_not():
    for quote, expect_refuse in [(100.0, False),    # 0%
                                 (129.9, False),    # 29.9%
                                 (130.0, False),    # exactly at the bound
                                 (130.1, True),     # past it
                                 (70.0, False),     # -30%, at the bound
                                 (69.9, True)]:     # -30.1%
        s = MemStore()
        _struck(s, {"X": 100.0})
        _filled(s, "X", "buy", 1.0)
        _proposed(s, "o", "X", quote)
        v = marksanity.check(s, "o")
        assert v["refuse"] is expect_refuse, (
            f"quote {quote} against a 100.00 strike: refuse={v['refuse']}, "
            f"expected {expect_refuse} ({v['reason']})")


# ------------------------------------------------------- the absence cases ---


def test_a_held_symbol_with_no_struck_mark_is_REFUSED():
    """The integrity case the brief names: strike NAV first, then approve."""
    s = MemStore()
    _struck(s, {"TLT": 82.0})              # the last strike does not price GLD
    _filled(s, "GLD", "buy", 3.0)          # but the fund holds GLD
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "held_but_unpriced"
    assert "Strike NAV first" in v["reason"]


def test_a_first_purchase_of_a_never_held_symbol_is_ALLOWED_and_says_so():
    """The one judgement in the module, pinned so it stays deliberate.

    A literal "no struck mark -> refuse" would block every first purchase of
    every new instrument FOREVER, because NAV is struck over what the fund
    holds and can never mint a reference for something it has never owned. That
    is not fail-closed, it is fail-shut, and it freezes deployment.

    The allowance is recorded as an ABSENCE, never as a corroboration.
    """
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    _proposed(s, "o", "NEWCO", 12.34, side="buy")
    v = marksanity.check(s, "o")
    assert v["refuse"] is False
    assert v["basis"] == "no_reference_new_symbol"
    assert "did not apply" in v["reason"]
    assert "NOT a corroboration" in v["reason"]


def test_the_strict_flag_makes_the_new_symbol_case_refuse_in_one_line(monkeypatch):
    """The CEO's switch. Flipping it must change exactly that one branch."""
    monkeypatch.setattr(marksanity, "NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES", True)
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    _proposed(s, "o", "NEWCO", 12.34, side="buy")
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "no_reference_strict"


def test_a_proposal_with_no_quote_price_is_refused():
    """An order whose own raising price is unknown is not approvable."""
    s = MemStore()
    _struck(s, {"GLD": 415.04})
    s.add("OrderProposed", {"symbol": "GLD", "side": "sell", "qty": 1.0},
          aggregate_id="o")
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "no_quote_price"


def test_an_unknown_order_id_is_refused_rather_than_waved_through():
    """No proposal found means no symbol and no quote — absent, so refused."""
    s = MemStore()
    _struck(s, {"GLD": 415.04})
    v = marksanity.check(s, "not-an-order")
    assert v["refuse"] is True
    assert v["basis"] == "no_quote_price"


def test_a_zero_struck_mark_is_a_data_fault_not_a_price():
    """0 cannot be divided by, and a 0 mark would otherwise read as 100% off."""
    s = MemStore()
    _struck(s, {"GLD": 0.0})
    _filled(s, "GLD", "buy", 1.0)
    _proposed(s, "o", "GLD", 415.04)
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "zero_reference"


def test_a_broken_log_read_refuses_rather_than_widening():
    """The gatherer can only narrow this check by failing, never widen it."""
    class Broken:
        def stream(self, since_seq=0, limit=100_000):
            raise RuntimeError("postgres is down")

    v = marksanity.check(Broken(), "o")
    assert v["refuse"] is True
    assert v["basis"] == "gather_failed"
    assert "postgres is down" in v["reason"]


def test_only_the_LAST_strike_is_a_reference_never_an_older_one():
    """A mark from three strikes ago is stale by an unknown amount.

    Here the fund holds GLD, an early strike priced it at 415.04, and the most
    recent strike does not carry it at all. Reaching back would produce a
    confident comparison against a number nobody currently vouches for; the
    honest answer is the integrity refusal.
    """
    s = MemStore()
    _struck(s, {"GLD": 415.04}, ts="2026-08-19T07:30:00Z")
    _struck(s, {"TLT": 82.0}, ts="2026-08-20T07:30:00Z")
    _filled(s, "GLD", "buy", 1.0)
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "held_but_unpriced"
    assert v["reference_mark"] is None


def test_a_closed_out_position_is_not_held_and_the_check_does_not_claim_it_is():
    """Bought 3, sold 3 → holds none. With no mark, that is the new-symbol case.

    Reading the wrong fill key would break this: fill payloads carry
    `filled_qty`, not `qty` (the defect that made autopolicy v2 fail closed on
    everything for a day).
    """
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    _filled(s, "GLD", "buy", 3.0)
    _filled(s, "GLD", "sell", 3.0)
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    assert v["refuse"] is False
    assert v["basis"] == "no_reference_new_symbol"


def test_float_residue_on_a_closed_position_does_not_count_as_held():
    """Measured on the live log, 2026-08-21, before shipping this guard.

    Folding every fill in the real record leaves five fully-closed symbols with
    residues of ~1e-15 (INTC 4.44e-16, SOFI -1.78e-15, SPY 2.78e-17). A
    "held" test of `!= 0` would classify all of them as positions the fund
    holds, and every one of them would then hit the `held_but_unpriced`
    refusal — a guard that blocks approvals on arithmetic dust. 1e-9 is nine
    orders of magnitude above the observed residue and far below any real
    fractional share.
    """
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    _filled(s, "SOFI", "buy", 1.0)
    _filled(s, "SOFI", "sell", 1.0000000000000002)   # residue ~ -2e-16
    _proposed(s, "o", "SOFI", 10.0, side="buy")
    v = marksanity.check(s, "o")
    assert abs(v.get("reference_mark") or 0) == 0
    assert v["basis"] == "no_reference_new_symbol", (
        "arithmetic dust was treated as a held position")
    assert v["refuse"] is False


def test_a_fill_payload_using_the_wrong_key_leaves_the_position_absent_not_wrong():
    """`qty` instead of `filled_qty` must not silently count as a holding."""
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    s.add("OrderFilled", {"symbol": "GLD", "side": "buy", "qty": 3.0})
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    # held reads 0 from the wrong key, so this lands in the new-symbol branch —
    # which is why THAT branch records its absence rather than claiming a check.
    assert v["basis"] == "no_reference_new_symbol"
    assert "NOT a corroboration" in v["reason"]


# --------------------------------------------------------- the endpoint -----


def test_the_approval_endpoint_refuses_and_records_the_refusal():
    """End to end: the phantom's own path, through the HTTP guard.

    Asserts the three things a refusal owes: a non-2xx, an ApprovalRefused
    event carrying BOTH numbers, and NO OrderApproved event.
    """
    from fastapi.testclient import TestClient
    from app.api.v1 import fund as fundapi

    refused: list = []
    approved: list = []

    class Store:
        def stream(self, since_seq=0, limit=100_000):
            return [
                {"type": "NavStruck", "aggregate_id": "nav",
                 "ts": "2026-08-20T07:30:00Z",
                 "payload": {"ts": "2026-08-20T07:30:00Z",
                             "positions": [{"symbol": "GLD", "mark": 415.04}]}},
                {"type": "OrderFilled", "aggregate_id": "f",
                 "ts": "2026-08-20T07:40:00Z",
                 "payload": {"symbol": "GLD", "side": "buy", "filled_qty": 1.0}},
                {"type": "OrderProposed", "aggregate_id": "ord-gld",
                 "ts": "2026-08-20T08:00:00Z",
                 "payload": {"symbol": "GLD", "side": "sell", "qty": 1.0,
                             "impact_preview": {"quote_price": 100.00}}},
            ]

        def append(self, e):
            refused.append(e)
            return e

    class Pipe:
        def approve_order(self, order_id, approver, policy_evaluation=None):
            approved.append(order_id)
            return {"status": "submitted"}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fundapi, "_store", Store())
        mp.setattr(fundapi, "_pipeline", Pipe())
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        r = TestClient(app).post(
            "/api/v1/fund/orders/ord-gld/approve",
            json={"approver": "neelesh", "confirm": "ord-gld"})

    assert r.status_code == 409, r.text
    assert "415.04" in r.text and "100.00" in r.text
    assert approved == [], "the order EXECUTED despite a refused approval"
    marks = [e for e in refused
             if getattr(e, "type", None) is not None
             and getattr(getattr(e, "type", None), "value", "") == "ApprovalRefused"]
    assert len(marks) == 1
    p = marks[0].payload
    assert p["guard"] == "mark_sanity_v1"
    assert p["quote_price"] == 100.00
    assert p["reference_mark"] == 415.04
    assert abs(p["move_pct"] - 75.9) < 0.1


def test_a_mark_sanity_refusal_does_NOT_freeze_the_order():
    """The denial-of-approval defect, guarded for the SECOND guard.

    Guard v1's first live day: two refused probes wrote ApprovalRefused events
    and SOFI vanished from the pending queue — the order froze in
    'ApprovalRefused' and the legitimate approver was blocked. The fix made a
    refusal an ANNOTATION, never a lifecycle step, in both the orders
    projection and pipeline._load_order.

    Mark sanity writes the SAME event type, so it inherits that fix — and this
    test is here so a future change to either filter breaks loudly instead of
    quietly locking an order the CEO still needs to approve.
    """
    from app.fund.events import EventType
    from app.fund.projections.orders import OrdersProjection

    events = [
        {"aggregate_id": "o1", "aggregate_type": "order", "ts": "2026-08-20T08:00:00Z",
         "type": EventType.ORDER_PROPOSED.value,
         "payload": {"symbol": "GLD", "side": "sell", "qty": 1.0, "venue": "paper",
                     "impact_preview": {"quote_price": 100.0}}},
        {"aggregate_id": "o1", "aggregate_type": "order", "ts": "2026-08-20T08:05:00Z",
         "type": EventType.APPROVAL_REFUSED.value,
         "payload": {"guard": "mark_sanity_v1", "reason": "…"}},
    ]

    class S:
        def stream(self, since_seq=0, limit=100_000):
            return list(events)

    rec = OrdersProjection(S())._fold()["o1"]
    assert rec["last"] == EventType.ORDER_PROPOSED.value, (
        "a mark-sanity refusal moved the order's lifecycle — the CEO can no "
        "longer approve the ticket they still owe a decision on")


def test_the_endpoint_lets_a_corroborated_order_through():
    """The guard must not be a wall. A sane price still executes."""
    from fastapi.testclient import TestClient
    from app.api.v1 import fund as fundapi

    approved: list = []

    class Store:
        def stream(self, since_seq=0, limit=100_000):
            return [
                {"type": "NavStruck", "aggregate_id": "nav",
                 "ts": "2026-08-20T07:30:00Z",
                 "payload": {"ts": "2026-08-20T07:30:00Z",
                             "positions": [{"symbol": "GLD", "mark": 415.04}]}},
                {"type": "OrderFilled", "aggregate_id": "f",
                 "ts": "2026-08-20T07:40:00Z",
                 "payload": {"symbol": "GLD", "side": "buy", "filled_qty": 1.0}},
                {"type": "OrderProposed", "aggregate_id": "ord-ok",
                 "ts": "2026-08-20T08:00:00Z",
                 "payload": {"symbol": "GLD", "side": "sell", "qty": 1.0,
                             "impact_preview": {"quote_price": 410.00}}},
            ]

        def append(self, e):
            return e

    class Pipe:
        def approve_order(self, order_id, approver, policy_evaluation=None):
            approved.append((order_id, approver))
            return {"status": "submitted", "order_id": order_id}

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(fundapi, "_store", Store())
        mp.setattr(fundapi, "_pipeline", Pipe())
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        r = TestClient(app).post(
            "/api/v1/fund/orders/ord-ok/approve",
            json={"approver": "neelesh", "confirm": "ord-ok"})

    assert r.status_code == 200, r.text
    assert approved == [("ord-ok", "neelesh")]
