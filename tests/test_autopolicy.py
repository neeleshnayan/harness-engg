"""The auto-approval envelope must be impossible to widen by accident.

This policy is the fund's first agent-era execution path (CEO amendment,
2026-08-20). Its safety is not that it is careful — it is that it is DETERMINISTIC
and fails closed. Every test here pins a way the envelope could silently widen.
"""

from __future__ import annotations

from app.fund.autopolicy import (AUTOPOLICY_VERSION, EXIT_MARKER, evaluate, run)

HB_OK = {j: {"ok": True, "age_seconds": 3.0}
         for j in ("exit_check", "risk_monitor", "settlement")}


def _order(**kw):
    base = {"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 1.0,
            "rationale": f"{EXIT_MARKER}. down 4.1%, past the 4.0% loss exit.",
            "age_minutes": 0.5}
    base.update(kw)
    return base


def test_a_fresh_exit_sell_is_approved_with_every_check_recorded():
    v = evaluate(_order(), halted=False, heartbeats=HB_OK, age_minutes=0.5)
    assert v["approve"] is True
    assert v["policy_version"] == AUTOPOLICY_VERSION
    assert all(c["ok"] is True for c in v["checks"])
    assert len(v["checks"]) >= 6  # the audit trail is the product


def test_a_buy_never_qualifies():
    """v1 is risk-reducing by construction. No rationale wording changes that."""
    v = evaluate(_order(side="buy"), halted=False, heartbeats=HB_OK,
                 age_minutes=0.5)
    assert v["approve"] is False


def test_a_sell_without_exit_provenance_never_qualifies():
    v = evaluate(_order(rationale="operator asked nicely"), halted=False,
                 heartbeats=HB_OK, age_minutes=0.5)
    assert v["approve"] is False


def test_halt_blocks_everything():
    v = evaluate(_order(), halted=True, heartbeats=HB_OK, age_minutes=0.5)
    assert v["approve"] is False


def test_unproven_liveness_fails_closed():
    """ok=None (never observed) must not read as alive.

    A fund that cannot prove its controls are ticking does not self-execute —
    the not-yet-observed state is neither broken nor fine, and for an execution
    decision 'not fine' is the only safe reading.
    """
    hb = dict(HB_OK)
    hb["risk_monitor"] = {"ok": None, "age_seconds": None}
    v = evaluate(_order(), halted=False, heartbeats=hb, age_minutes=0.5)
    assert v["approve"] is False


def test_missing_heartbeat_entry_fails_closed():
    hb = {k: v for k, v in HB_OK.items() if k != "settlement"}
    v = evaluate(_order(), halted=False, heartbeats=hb, age_minutes=0.5)
    assert v["approve"] is False


def test_stale_or_unknown_age_fails_closed():
    v = evaluate(_order(), halted=False, heartbeats=HB_OK, age_minutes=11.0)
    assert v["approve"] is False
    v = evaluate(_order(), halted=False, heartbeats=HB_OK, age_minutes=None)
    assert v["approve"] is False
    unknown = [c for c in v["checks"] if c["check"] == "freshness"][0]
    assert "unknown is not fresh" in unknown["detail"]


def test_run_approves_through_the_ordinary_pipeline_and_records_the_policy():
    class Pipe:
        def __init__(self):
            self.calls = []

        def approve_order(self, oid, approver, policy_evaluation=None):
            self.calls.append((oid, approver, policy_evaluation))
            return {"status": "submitted"}

    pipe = Pipe()
    out = run(pipe, [_order(), _order(order_id="o2", side="buy")],
              halted=False, heartbeats=HB_OK)
    assert [a["order_id"] for a in out["approved"]] == ["o1"]
    assert [s["order_id"] for s in out["skipped"]] == ["o2"]
    oid, approver, ev = pipe.calls[0]
    assert approver == f"auto-policy-{AUTOPOLICY_VERSION}"
    assert ev["approve"] is True and ev["checks"], \
        "the approval event must carry the full evaluation for the risk officer"


def test_a_failed_approval_leaves_the_order_pending_for_a_human():
    """Policy failure degrades to the OLD behaviour, never to a lost order."""
    class Pipe:
        def approve_order(self, oid, approver, policy_evaluation=None):
            raise RuntimeError("venue rejected")

    out = run(Pipe(), [_order()], halted=False, heartbeats=HB_OK)
    assert out["approved"] == []
    assert len(out["failed"]) == 1
    assert "venue rejected" in out["failed"][0]["error"]
