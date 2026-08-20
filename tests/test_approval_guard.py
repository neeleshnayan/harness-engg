"""Approval-channel guard v1 — approvals are allowlisted, echoed, attributed.

The defect this closes (2026-08-20, CEO decision): the approver field was
free text accepted from anything on localhost — the same forgeability as
autopolicy v1's marker string, one layer up. These tests pin the three
checks fail-closed and the refusal-as-event behaviour: a probe becomes a
finding, not a fill. Declines are deliberately outside the guard (they are
reversible and staging hygiene needs them) — visible in the endpoints, not
re-tested here.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.api.v1.fund as api
from app.fund.events import EventType


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)
        return e


@pytest.fixture()
def store(monkeypatch):
    s = MemStore()
    monkeypatch.setattr(api, "_store", s)
    return s


OID = "20ab9a86-1234-5678-9abc-def012345678"


def _refused(store, **kw):
    with pytest.raises(HTTPException) as ei:
        api._guard_approval(kw.pop("kind", "order"), kw.pop("target", OID),
                            kw.pop("approver"), kw.pop("confirm", None),
                            kw.pop("instruction", None),
                            kw.pop("allowlist", api.APPROVAL_ALLOWLIST))
    assert ei.value.status_code == 403
    ev = store.events[-1]
    assert ev.type == EventType.APPROVAL_REFUSED
    return ei.value.detail, ev


def test_seat_name_is_refused_and_recorded(store):
    detail, ev = _refused(store, approver="pm", confirm=OID[:8])
    assert "allowlist" in detail
    assert ev.payload["approver"] == "pm"
    assert ev.payload["target_id"] == OID


def test_free_text_cto_cannot_approve(store):
    # The CTO alone is NOT on the order allowlist — only the CEO's click or
    # the CTO carrying the CEO's quoted instruction.
    detail, _ = _refused(store, approver="cto", confirm=OID[:8])
    assert "allowlist" in detail


def test_missing_echo_is_refused(store):
    detail, _ = _refused(store, approver="rushi")
    assert "confirm" in detail


def test_wrong_echo_is_refused(store):
    detail, _ = _refused(store, approver="rushi", confirm="deadbeef")
    assert "confirm" in detail


def test_via_cto_without_citation_is_refused(store):
    detail, _ = _refused(store, approver="rushi-via-cto", confirm=OID[:8])
    assert "instruction" in detail


def test_the_ceo_click_passes_clean(store):
    out = api._guard_approval("order", OID, "rushi", OID[:8], None,
                              api.APPROVAL_ALLOWLIST)
    assert out == "rushi"
    assert store.events == []  # a clean approval records no refusal


def test_via_cto_passes_only_with_the_quote_attached(store):
    out = api._guard_approval("order", OID, "rushi-via-cto", OID[:8],
                              "good to approve my tickets",
                              api.APPROVAL_ALLOWLIST)
    assert out == "rushi-via-cto [good to approve my tickets]"
    assert store.events == []


def test_desk_allowlist_admits_the_ui_ceo_actor(store):
    out = api._guard_approval("desk_request", OID, "ceo", OID[:8], None,
                              api.DESK_APPROVAL_ALLOWLIST)
    assert out == "ceo"


def test_case_is_normalised_but_attribution_is_preserved(store):
    out = api._guard_approval("order", OID, "Rushi", OID[:8], None,
                              api.APPROVAL_ALLOWLIST)
    assert out == "Rushi"


def test_a_refused_probe_does_not_hide_the_pending_order():
    """Found live on the guard's first day: ApprovalRefused folded into the
    order's ``last`` state, so two 403 probes made a legitimate pending
    ticket vanish from the CEO's queue — a denial-of-approval vector. The
    refusal is an annotation, never a lifecycle step."""
    from app.fund.projections.orders import OrdersProjection
    orders: dict = {}
    OrdersProjection._apply(orders, {
        "aggregate_type": "order", "aggregate_id": "x", "ts": "t1",
        "type": "OrderProposed", "payload": {"symbol": "SOFI", "qty": 1.0}})
    OrdersProjection._apply(orders, {
        "aggregate_type": "order", "aggregate_id": "x", "ts": "t2",
        "type": "ApprovalRefused", "payload": {"approver": "pm"}})
    assert orders["x"]["last"] == "OrderProposed"  # still pending


def test_a_refused_probe_does_not_freeze_the_pipeline_state():
    """Second face of the same defect: pipeline._load_order returned the raw
    latest event type, so after a failed probe the legitimate approver got
    409 \"order is 'ApprovalRefused', not awaiting approval\"."""
    from app.fund.pipeline import CommandPipeline

    class S:
        @staticmethod
        def by_aggregate(oid):
            return [
                {"type": "OrderProposed",
                 "payload": {"venue": "paper", "symbol": "SOFI",
                             "side": "sell", "qty": 1.0}},
                {"type": "ApprovalRefused", "payload": {"approver": "pm"}},
            ]

    p = object.__new__(CommandPipeline)
    p._store = S()
    _, last = p._load_order("x")
    assert last == "OrderProposed"  # still awaiting the legitimate approver
