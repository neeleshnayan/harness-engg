"""Acknowledge-and-rebase, through the approval channel — the endpoint.

C2 of builder dispatch 4. This is a money-adjacent control: it re-arms an
execution path the fund deliberately closed, so it goes through the SAME guard
as an order approval (allowlist, confirm echo, via-cto citation) and it fails
closed on every axis.

The confirm echo is the twist worth pinning. An order approval echoes the order
id; a rebase has no id, so the echo is a digest of the STATE being rebased —
current NAV, the reference it would replace, and the halt. That makes a confirm
copied off a stale panel refusable, which an id never could: an id is still the
right id an hour later, and by then the book has moved.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

import app.api.v1.fund as api
from app.fund.events import EventType
from app.fund.riskmonitor import HALT_INTEGRITY, HALT_LOSS
from app.schemas.fund import LossRebaseRequest


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)
        return e


class FakeControl:
    """Records what it was asked to do; refuses like the real one."""

    def __init__(self, halted=False, halt_class=None):
        self._halted = halted
        self._halt_class = halt_class
        self.rebased = []

    def rebase_loss_reference(self, nav_usd, reason, actor):
        if not (reason or "").strip():
            raise ValueError("acknowledging a loss requires a written reason")
        if self._halted and self._halt_class == HALT_INTEGRITY:
            raise ValueError("an INTEGRITY halt is open")
        self.rebased.append({"nav_usd": nav_usd, "reason": reason, "actor": actor})
        return {"status": "rebased", "nav_usd": nav_usd, "reason": reason,
                "at": "2026-08-20T12:00:00+00:00", "actor": actor}


class FakeNav:
    def compute(self, stale_ok=False):
        class S:
            total_nav_usd = 1878.60
        return S()


class FakeMonitor:
    TOKEN = "a1b2c3d4"

    def rebase_token(self, nav_usd=None):
        return self.TOKEN


@pytest.fixture()
def wired(monkeypatch):
    store = MemStore()
    control = FakeControl()
    monkeypatch.setattr(api, "_store", store)
    monkeypatch.setattr(api, "_control", control)
    monkeypatch.setattr(api, "_nav", FakeNav())
    monkeypatch.setattr(api, "_monitor", FakeMonitor())
    return store, control


def _req(**kw):
    kw.setdefault("approver", "neelesh")
    kw.setdefault("confirm", FakeMonitor.TOKEN)
    kw.setdefault("reason", "the drop is the corrected GLD mark, not a trading loss")
    return LossRebaseRequest(**kw)


# --- the guard --------------------------------------------------------------

def test_a_valid_ceo_rebase_is_accepted_and_uses_current_nav(wired):
    _, control = wired
    out = api.rebase_loss_reference(_req())
    assert out["status"] == "rebased"
    assert control.rebased[0]["nav_usd"] == 1878.60
    assert control.rebased[0]["actor"] == "neelesh"


def test_a_seat_cannot_rebase_and_the_refusal_is_recorded(wired):
    store, control = wired
    with pytest.raises(HTTPException) as ei:
        api.rebase_loss_reference(_req(approver="riskofficer"))
    assert ei.value.status_code == 403
    assert "allowlist" in ei.value.detail
    assert store.events[-1].type == EventType.APPROVAL_REFUSED
    assert store.events[-1].payload["kind"] == "loss_reference_rebase"
    assert control.rebased == [], "a refused rebase must move nothing"


def test_a_wrong_or_missing_confirm_is_refused(wired):
    _, control = wired
    for bad in (None, "", "deadbeef", "A1B2C3D4"):
        with pytest.raises(HTTPException) as ei:
            api.rebase_loss_reference(_req(confirm=bad))
        assert ei.value.status_code == 403
    assert control.rebased == []


def test_a_stale_confirm_is_refused_because_the_token_moved(wired, monkeypatch):
    """The point of a state-derived echo: the panel was read, then the book
    moved, and the confirm the operator is holding no longer describes it."""
    _, control = wired

    class MovedMonitor:
        def rebase_token(self, nav_usd=None):
            return "99999999"          # NAV moved since the panel rendered

    monkeypatch.setattr(api, "_monitor", MovedMonitor())
    with pytest.raises(HTTPException) as ei:
        api.rebase_loss_reference(_req(confirm=FakeMonitor.TOKEN))
    assert ei.value.status_code == 403
    assert control.rebased == []


def test_via_cto_must_quote_the_ceo_instruction(wired):
    _, control = wired
    with pytest.raises(HTTPException) as ei:
        api.rebase_loss_reference(_req(approver="neelesh-via-cto", instruction=None))
    assert "instruction" in ei.value.detail
    assert control.rebased == []


def test_via_cto_with_the_quote_lands_and_carries_it(wired):
    _, control = wired
    api.rebase_loss_reference(_req(approver="neelesh-via-cto",
                                   instruction="accept the GLD mark correction"))
    assert control.rebased[0]["actor"] == \
        "neelesh-via-cto [accept the GLD mark correction]"


# --- the refusals that are about the FUND, not the channel ------------------

def test_a_rebase_without_a_reason_is_refused_by_the_schema(wired):
    with pytest.raises(Exception):
        LossRebaseRequest(approver="neelesh", confirm=FakeMonitor.TOKEN)


def test_an_empty_reason_is_refused_as_a_conflict_not_silently_accepted(wired):
    _, control = wired
    with pytest.raises(HTTPException) as ei:
        api.rebase_loss_reference(_req(reason="   "))
    assert ei.value.status_code == 409
    assert control.rebased == []


def test_a_rebase_is_refused_while_an_integrity_halt_is_open(wired):
    """Rebasing onto 'current NAV' when current NAV is the number we do not
    trust would launder a bad mark into the fund's own reference — the
    phantom-price incident with a signature on it."""
    _, control = wired
    control._halted = True
    control._halt_class = HALT_INTEGRITY
    with pytest.raises(HTTPException) as ei:
        api.rebase_loss_reference(_req())
    assert ei.value.status_code == 409
    assert "INTEGRITY" in ei.value.detail
    assert control.rebased == []


def test_a_rebase_is_permitted_while_a_loss_halt_is_open(wired):
    _, control = wired
    control._halted = True
    control._halt_class = HALT_LOSS
    assert api.rebase_loss_reference(_req())["status"] == "rebased"
    assert len(control.rebased) == 1
