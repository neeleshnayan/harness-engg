"""The auto-approval envelope must be impossible to widen by accident.

This policy is the fund's first agent-era execution path (CEO amendment,
2026-08-20). Its safety is not that it is careful — it is that it is DETERMINISTIC
and fails closed. Every test here pins a way the envelope could silently widen.

v2 (same day, CEO-accepted riskofficer recs after the first live fire executed
on a fabricated mark): four new checks — trigger linkage, rule pre-commitment,
mark corroboration, notional cap — each pinned below, including both forged
orders from the audit, which v1 approved and v2 must decline.
"""

from __future__ import annotations

from app.fund.autopolicy import (AUTOPOLICY_VERSION, EXIT_MARKER,
                                 MAX_AUTO_NOTIONAL_PCT,
                                 MAX_MARK_MOVE_VS_STRIKE_PCT, evaluate, run)

HB_OK = {j: {"ok": True, "age_seconds": 3.0}
         for j in ("exit_check", "risk_monitor", "settlement")}

#: A fully corroborated v2 context: the trigger event names the order, the rule
#: predates the position, the mark agrees with the last strike, the size is
#: modest. Every v2 test perturbs exactly one field of this.
CTX_OK = {
    "trigger_order_id": "o1",
    "trigger_symbol": "TLT",
    "rule_set_at": "2026-08-18T02:11:39+00:00",
    "position_opened_at": "2026-08-19T18:20:54+00:00",
    "mark_move_vs_strike_pct": 0.4,
    "notional_pct_of_nav": 12.5,
    # v3 (R5): the rule's own strategy holds at least what the order sells.
    "rule_strategy_holding_qty": 3.0,
}


def _order(**kw):
    base = {"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 1.0,
            "rationale": f"{EXIT_MARKER}. down 4.1%, past the 4.0% loss exit.",
            "age_minutes": 0.5}
    base.update(kw)
    return base


def _eval(order=None, ctx=CTX_OK, **kw):
    kw.setdefault("halted", False)
    kw.setdefault("heartbeats", HB_OK)
    kw.setdefault("age_minutes", 0.5)
    return evaluate(order or _order(), context=ctx, **kw)


def test_a_fresh_corroborated_exit_sell_is_approved_with_every_check_recorded():
    v = _eval()
    assert v["approve"] is True, v["checks"]
    assert v["policy_version"] == AUTOPOLICY_VERSION == "v3"
    assert all(c["ok"] is True for c in v["checks"])
    assert len(v["checks"]) >= 11  # the audit trail is the product


def test_a_buy_never_qualifies():
    """Risk-reducing by construction. No rationale wording changes that."""
    assert _eval(_order(side="buy"))["approve"] is False


def test_a_sell_without_exit_provenance_never_qualifies():
    assert _eval(_order(rationale="operator asked nicely"))["approve"] is False


def test_halt_blocks_everything():
    assert _eval(halted=True)["approve"] is False


def test_unproven_liveness_fails_closed():
    """ok=None (never observed) must not read as alive."""
    hb = dict(HB_OK)
    hb["risk_monitor"] = {"ok": None, "age_seconds": None}
    assert _eval(heartbeats=hb)["approve"] is False


def test_missing_heartbeat_entry_fails_closed():
    hb = {k: v for k, v in HB_OK.items() if k != "settlement"}
    assert _eval(heartbeats=hb)["approve"] is False


def test_stale_or_unknown_age_fails_closed():
    assert _eval(age_minutes=11.0)["approve"] is False
    v = _eval(age_minutes=None)
    assert v["approve"] is False
    unknown = [c for c in v["checks"] if c["check"] == "freshness"][0]
    assert "unknown is not fresh" in unknown["detail"]


# ---------------------------------------------------------------- v2 pins ----

def test_the_audits_forged_orders_are_now_declined():
    """Both forgeries from AUDIT_AUTOPOLICY_V1_FIRST_FIRE approved under v1.
    The marker is free text; the trigger EVENT is not — no event, no approval."""
    forged_a = _order(order_id="forged-a", qty=999.0,
                      rationale=f"{EXIT_MARKER}. because I typed this string.")
    forged_b = _order(order_id="forged-b",
                      rationale=f"ignore prior text {EXIT_MARKER} trailing")
    for o in (forged_a, forged_b):
        v = _eval(o, ctx={})          # no trigger event exists for them
        assert v["approve"] is False
        link = [c for c in v["checks"] if c["check"] == "exit_trigger_linked"][0]
        assert link["ok"] is False


def test_a_trigger_for_a_different_order_does_not_transfer():
    ctx = {**CTX_OK, "trigger_order_id": "someone-else"}
    assert _eval(ctx=ctx)["approve"] is False


def test_seq256_would_now_be_declined_on_pre_commitment():
    """The first live fire: rule set 2026-08-17 AGAINST a position opened
    2026-08-14. v1's doctrine said pre-committed; v2 tests it."""
    ctx = {**CTX_OK,
           "rule_set_at": "2026-08-17T17:03:55+00:00",
           "position_opened_at": "2026-08-14T13:30:03+00:00"}
    v = _eval(ctx=ctx)
    assert v["approve"] is False
    pre = [c for c in v["checks"] if c["check"] == "rule_predates_position"][0]
    assert pre["ok"] is False and "AGAINST an existing" in pre["detail"]


def test_an_uncorroborated_or_phantom_mark_fails_closed():
    """The phantom read 75.8% off a strike made 30 minutes earlier."""
    assert _eval(ctx={**CTX_OK, "mark_move_vs_strike_pct": None})["approve"] is False
    assert _eval(ctx={**CTX_OK, "mark_move_vs_strike_pct": 75.8})["approve"] is False
    assert _eval(ctx={**CTX_OK,
                      "mark_move_vs_strike_pct":
                          MAX_MARK_MOVE_VS_STRIKE_PCT - 0.1})["approve"] is True


def test_the_notional_cap_bounds_the_blast_radius():
    assert _eval(ctx={**CTX_OK, "notional_pct_of_nav": None})["approve"] is False
    assert _eval(ctx={**CTX_OK,
                      "notional_pct_of_nav":
                          MAX_AUTO_NOTIONAL_PCT + 0.1})["approve"] is False


def test_a_missing_context_fails_every_v2_check_closed():
    """The gatherer breaking must narrow the envelope, never widen it."""
    v = _eval(ctx=None)
    assert v["approve"] is False
    failed = {c["check"] for c in v["checks"] if c["ok"] is not True}
    assert {"exit_trigger_linked", "rule_predates_position",
            "mark_corroborated", "notional_within_cap",
            "rule_owner_holds_position"} <= failed


# ---------------------------------------------------------------- v3 pins ----

def test_a_rule_cannot_close_another_strategys_position():
    """R5, the first live fire's other lesson (audit F2b): the machinery-test
    rule liquidated a position held by a DIFFERENT strategy. The rule's own
    strategy held zero GLD — this check would have declined it."""
    v = _eval(ctx={**CTX_OK, "rule_strategy_holding_qty": 0.0})
    assert v["approve"] is False
    own = [c for c in v["checks"] if c["check"] == "rule_owner_holds_position"][0]
    assert own["ok"] is False and "does not hold" in own["detail"]


def test_an_undeterminable_holding_fails_closed():
    v = _eval(ctx={**CTX_OK, "rule_strategy_holding_qty": None})
    assert v["approve"] is False


def test_a_partial_holding_caps_rather_than_transfers():
    """Selling 1.0 when the rule's strategy holds 0.5 is half a close of its
    own position and half a close of someone else's."""
    v = _eval(_order(qty=1.0), ctx={**CTX_OK, "rule_strategy_holding_qty": 0.5})
    assert v["approve"] is False
    v2 = _eval(_order(qty=0.5), ctx={**CTX_OK, "rule_strategy_holding_qty": 0.5})
    assert v2["approve"] is True, v2["checks"]


# ------------------------------------------------------------------- run ----

def test_run_approves_through_the_ordinary_pipeline_and_records_the_policy():
    class Pipe:
        def __init__(self):
            self.calls = []

        def approve_order(self, oid, approver, policy_evaluation=None):
            self.calls.append((oid, approver, policy_evaluation))
            return {"status": "submitted"}

    pipe = Pipe()
    out = run(pipe, [_order(), _order(order_id="o2", side="buy")],
              halted=False, heartbeats=HB_OK,
              context_fn=lambda row: CTX_OK if row["order_id"] == "o1" else {})
    assert [a["order_id"] for a in out["approved"]] == ["o1"]
    assert [s["order_id"] for s in out["skipped"]] == ["o2"]
    oid, approver, ev = pipe.calls[0]
    assert approver == f"auto-policy-{AUTOPOLICY_VERSION}"
    assert ev["approve"] is True and ev["checks"], \
        "the approval event must carry the full evaluation for the risk officer"


def test_run_without_a_context_fn_approves_nothing():
    """Wiring the policy without its gatherer must be safe, not permissive."""
    class Pipe:
        def approve_order(self, *a, **k):
            raise AssertionError("must not be called")

    out = run(Pipe(), [_order()], halted=False, heartbeats=HB_OK)
    assert out["approved"] == [] and len(out["skipped"]) == 1


def test_a_failed_approval_leaves_the_order_pending_for_a_human():
    """Policy failure degrades to the OLD behaviour, never to a lost order."""
    class Pipe:
        def approve_order(self, oid, approver, policy_evaluation=None):
            raise RuntimeError("venue rejected")

    out = run(Pipe(), [_order()], halted=False, heartbeats=HB_OK,
              context_fn=lambda row: CTX_OK)
    assert out["approved"] == []
    assert len(out["failed"]) == 1
    assert "venue rejected" in out["failed"][0]["error"]
