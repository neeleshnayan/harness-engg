"""The auto-approval envelope must be impossible to widen by accident.

This policy is the fund's first agent-era execution path (CEO amendment,
2026-08-20). Its safety is not that it is careful — it is that it is DETERMINISTIC
and fails closed. Every test here pins a way the envelope could silently widen.

v2 (same day, CEO-accepted riskofficer recs after the first live fire executed
on a fabricated mark): four new checks — trigger linkage, rule pre-commitment,
mark corroboration, notional cap — each pinned below, including both forged
orders from the audit, which v1 approved and v2 must decline.

v4 (2026-08-21, riskofficer R19). THE INCIDENT THIS SECTION GUARDS AGAINST HAS
A DATE ON IT: 2026-09-08, when the TLT and DBC `kind: time` exits (ExitRuleSet
seq 178 and 181, verified on the live log) fire against a broker holding ZERO
of either. v3 approves them twelve checks out of twelve and opens $652.09 of
real short exposure, because every check v3 makes reads the fund's own ledger
and none of them asks the broker what it holds. If
``test_the_2026_09_08_time_exit_is_refused_by_the_venue_check`` ever passes an
approval, that is live again.
"""

from __future__ import annotations

import logging

from app.fund.autopolicy import (AUTOPOLICY_VERSION, EXIT_MARKER,
                                 MAX_AUTO_NOTIONAL_PCT,
                                 MAX_MARK_MOVE_VS_STRIKE_PCT,
                                 MAX_POSITION_DRIFT_QTY, POSITION_EPS,
                                 context_for, evaluate, order_delta,
                                 reduces_exposure, run, venue_snapshot)

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
    # SIGNED from v4 on — v3's gatherer clamped it at zero, which read a short
    # as flat.
    "rule_strategy_holding_qty": 3.0,
    # v4: the three ledgers agree and the broker actually holds the shares.
    # Note `venue_readable` is a SEPARATE field from the quantity, on purpose.
    "book_qty_signed": 3.0,
    "venue_readable": True,
    "venue_qty_signed": 3.0,
}

#: The v4 fields alone, for tests that build a context from scratch.
VENUE_OK = {"book_qty_signed": 3.0, "venue_readable": True,
            "venue_qty_signed": 3.0}


def _checks(verdict):
    return {c["check"]: c for c in verdict["checks"]}


def _failed(verdict):
    return {c["check"] for c in verdict["checks"] if c["ok"] is not True}


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
    assert v["policy_version"] == AUTOPOLICY_VERSION == "v4"
    assert all(c["ok"] is True for c in v["checks"])
    assert len(v["checks"]) >= 14  # the audit trail is the product


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
    failed = _failed(v)
    assert {"exit_trigger_linked", "rule_predates_position",
            "mark_corroborated", "notional_within_cap",
            "rule_owner_holds_position",
            # v4's three fail closed on an absent context too. A gatherer that
            # breaks must never leave a ledger check unasked.
            "exit_reduces_exposure", "venue_holds_position",
            "book_venue_in_sync"} <= failed


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


# ================================================================= v4 pins ====
#
# R19. Every test below pins one way the exposure invariant could fail to hold:
#
#   an exit must REDUCE exposure and must never cross zero into a position in
#   the opposite direction
#
# applied at three ledgers — the rule's own strategy, the fund's book, and the
# BROKER — with the last two required to agree.


# --------------------------------------------- the predicate, sign by sign ----
#
# Seven sign-flipped cases. The predicate is deliberately SIGN-AGNOSTIC, which
# is a property of the invariant and NOT a widening: `side_is_sell` is a
# separate check and T4 below pins that it still refuses buys.

def test_t1_selling_exactly_what_is_held_closes_the_position():
    assert reduces_exposure(10.0, -10.0) is True


def test_t2_selling_part_of_what_is_held_reduces_exposure():
    assert reduces_exposure(10.0, -3.0) is True


def test_t3_selling_more_than_is_held_crosses_zero_and_is_refused():
    """Closing 10 and SHORTING 1 is not an exit. The second conjunct exists
    entirely for this case."""
    assert reduces_exposure(10.0, -11.0) is False


def test_t4_the_keystone_sign_agnostic_but_still_no_buys():
    """T4, the keystone (spec section 7).

    pre = −10, BUY 10: the predicate must say True (buying back a short does
    reduce exposure — the invariant is about direction, not about the word
    "sell"), AND the overall verdict must still be DECLINE, because
    `side_is_sell` is untouched by v4.

    One test, two claims: v4 generalised the predicate, and v4 did NOT smuggle
    in the `side_is_sell` -> `side_reduces_exposure` relaxation. That relaxation
    is a WIDENING and goes to the adversary blind before it goes anywhere else.
    """
    assert reduces_exposure(-10.0, 10.0) is True

    short_ctx = {**CTX_OK, "rule_strategy_holding_qty": -10.0,
                 "book_qty_signed": -10.0, "venue_qty_signed": -10.0}
    v = _eval(_order(side="buy", qty=10.0), ctx=short_ctx)
    c = _checks(v)
    assert c["exit_reduces_exposure"]["ok"] is True
    assert c["venue_holds_position"]["ok"] is True
    assert c["rule_owner_holds_position"]["ok"] is True
    assert c["side_is_sell"]["ok"] is False
    assert v["approve"] is False, "v4 must not have widened the envelope to buys"


def test_t5_buying_back_more_than_the_short_crosses_zero_the_other_way():
    assert reduces_exposure(-10.0, 11.0) is False


def test_t6_a_flat_ledger_can_never_be_exited():
    """THE 2026-09-08 SHAPE, at the predicate level. `pre * delta < -EPS`
    kills the flat case for free: 0 * anything is 0, which is not < −EPS."""
    assert reduces_exposure(0.0, -10.0) is False
    assert reduces_exposure(0.0, 10.0) is False
    assert reduces_exposure(-0.0, -10.0) is False


def test_t7_buying_more_of_what_is_already_held_increases_exposure():
    assert reduces_exposure(10.0, 10.0) is False
    assert reduces_exposure(-10.0, -10.0) is False


def test_the_predicate_fails_closed_on_absence_and_on_nan():
    """An unmeasurable position is never a permitted one — and NaN, which
    fails every comparison, must land on False rather than on an exception."""
    assert reduces_exposure(None, -1.0) is False
    assert reduces_exposure(10.0, None) is False
    assert reduces_exposure(None, None) is False
    assert reduces_exposure(float("nan"), -1.0) is False
    assert reduces_exposure(10.0, float("nan")) is False


def test_the_epsilon_is_one_number_not_three():
    """Three ledgers must not acquire three ideas of "zero"."""
    assert POSITION_EPS == 1e-9
    # Just inside the epsilon reads as flat; just outside reads as a position.
    assert reduces_exposure(POSITION_EPS / 2, -1.0) is False
    assert reduces_exposure(1.0, -1.0 - POSITION_EPS / 2) is True


# ------------------------------------------------------- the order's delta ----

def test_order_delta_signs_by_side_and_is_absent_when_unreadable():
    assert order_delta({"side": "sell", "qty": 3.0}) == -3.0
    assert order_delta({"side": "buy", "qty": 3.0}) == 3.0
    # A negative qty on a sell is still a sell of that size, not a buy.
    assert order_delta({"side": "sell", "qty": -3.0}) == -3.0
    assert order_delta({"side": "sell"}) is None
    assert order_delta({"side": "", "qty": 3.0}) is None
    assert order_delta({"side": "sell", "qty": "banana"}) is None
    assert order_delta({"side": "sell", "qty": float("nan")}) is None


def test_a_missing_quantity_no_longer_sails_through_the_ownership_check():
    """v3 read the quantity as `float(order.get("qty") or 0.0)`, so an order
    with NO quantity became 0.0 and passed `0 <= held`. Absent is now absent."""
    o = _order()
    o.pop("qty")
    v = _eval(o)
    assert v["approve"] is False
    assert "rule_owner_holds_position" in _failed(v)
    assert "exit_reduces_exposure" in _failed(v)


# ------------------------------------- THE INCIDENT WITH A DATE ON IT ---------

#: The live measurement, 2026-08-21, from GET /fund/venue/reconcile: the fund's
#: book against the broker's own answer. Not a scenario — a reading.
LIVE_BOOK_TLT = 3.019871
LIVE_BROKER_TLT = 0.0
LIVE_BOOK_SPY = 0.346119
LIVE_BROKER_SPY = 0.217757


def _the_2026_09_08_context(**over):
    """v3's context for the TLT time exit, EXACTLY as v3 gathered it: every one
    of v3's twelve checks true. The sleeve holds 3.019871 TLT in the book, the
    rule was committed 2026-08-18 before the position opened 2026-08-19, the
    mark agrees with the strike, the notional is 12.5% of NAV."""
    ctx = {**CTX_OK,
           "rule_strategy_holding_qty": LIVE_BOOK_TLT,
           "book_qty_signed": LIVE_BOOK_TLT,
           "venue_readable": True,
           "venue_qty_signed": LIVE_BROKER_TLT}
    ctx.update(over)
    return ctx


def test_the_2026_09_08_time_exit_is_refused_by_the_venue_check():
    """THE KEYSTONE. ExitRuleSet seq 178 (TLT), kind: time, on_date 2026-09-08,
    strategy sleeve_beta_500 — verified on the live event log.

    On that date the rule fires and raises a SELL of 3.019871 TLT. The fund's
    book holds 3.019871. The BROKER holds ZERO (live /fund/venue/reconcile,
    2026-08-21). v3 approves it twelve checks out of twelve and opens a real
    short. Every v3 check is factually true; none of them asks the broker.

    If this test ever asserts an approval, $652.09 of date-certain short
    exposure is live again.
    """
    v = _eval(_order(symbol="TLT", qty=LIVE_BOOK_TLT),
              ctx=_the_2026_09_08_context())
    assert v["approve"] is False
    c = _checks(v)

    # The venue check is the one that refuses it...
    assert c["venue_holds_position"]["ok"] is False
    assert "ZERO TLT" in c["venue_holds_position"]["detail"]
    assert "short" in c["venue_holds_position"]["detail"]
    # ...and the drift check catches it independently, so removing either one
    # alone does not re-open the hole.
    assert c["book_venue_in_sync"]["ok"] is False

    # And EVERY v3 check is still true, which is the whole point: the envelope
    # was not malfunctioning, it was answering a question about the wrong ledger.
    for name in ("side_is_sell", "exit_rule_provenance", "exit_trigger_linked",
                 "rule_predates_position", "mark_corroborated",
                 "rule_owner_holds_position", "notional_within_cap",
                 "not_halted", "freshness"):
        assert c[name]["ok"] is True, f"{name} should still pass: {c[name]}"


def test_the_same_exit_is_approved_once_the_broker_actually_holds_it():
    """v4 must refuse the 2026-09-08 shape WITHOUT refusing everything — an
    envelope that declines all exits is a kill switch, not a policy, and leg 3
    of the team metric is capital deployed under mandate."""
    v = _eval(_order(symbol="TLT", qty=LIVE_BOOK_TLT),
              ctx=_the_2026_09_08_context(venue_qty_signed=LIVE_BOOK_TLT))
    assert v["approve"] is True, v["checks"]


def test_the_live_spy_drift_declines_on_both_the_venue_and_the_sync_check():
    """The live SPY row, 2026-08-21: book 0.346119, broker 0.217757. The exit
    would sell the BOOK's quantity, which is 0.128362 more than the broker
    holds — so it closes the real position and shorts the difference."""
    ctx = {**CTX_OK, "trigger_symbol": "SPY",
           "rule_strategy_holding_qty": LIVE_BOOK_SPY,
           "book_qty_signed": LIVE_BOOK_SPY,
           "venue_readable": True,
           "venue_qty_signed": LIVE_BROKER_SPY}
    v = _eval(_order(symbol="SPY", qty=LIVE_BOOK_SPY), ctx=ctx)
    assert v["approve"] is False
    c = _checks(v)
    assert c["venue_holds_position"]["ok"] is False, \
        "selling 0.346119 against a broker holding 0.217757 shorts 0.128362"
    assert c["book_venue_in_sync"]["ok"] is False
    # The fund's OWN book says this is a clean full close — which is exactly
    # why checking only the book is not enough.
    assert c["exit_reduces_exposure"]["ok"] is True


# ------------------------------- the three absences, and their three reasons --

def test_the_three_venue_absence_modes_give_three_DIFFERENT_reasons():
    """"We could not look", "we looked and it is zero", and "we looked and the
    read had a hole in it" have three different fixes — reconnect the broker,
    stop the order, fix the gatherer — and the audit reads the DETAIL, not the
    boolean. A single shared string would collapse three incidents into one.

    All three decline. That they decline is not the assertion here; that they
    decline DIFFERENTLY is.
    """
    unreadable = _eval(ctx={**CTX_OK, "venue_readable": False,
                            "venue_qty_signed": None})
    zero = _eval(ctx={**CTX_OK, "venue_readable": True,
                      "venue_qty_signed": 0.0})
    hole = _eval(ctx={**CTX_OK, "venue_readable": True,
                      "venue_qty_signed": None})

    details = [_checks(v)["venue_holds_position"]["detail"]
               for v in (unreadable, zero, hole)]
    for v in (unreadable, zero, hole):
        assert v["approve"] is False
        assert _checks(v)["venue_holds_position"]["ok"] is False
    assert len(set(details)) == 3, details

    assert "could not be read" in details[0]
    assert "not a zero position" in details[0]
    assert "ZERO" in details[1]
    assert "carried no quantity" in details[2]


def test_an_unreadable_venue_is_never_read_as_a_flat_account():
    """The single most dangerous confusion on this path: an empty positions
    list is what a flat account AND an unreachable broker both return."""
    v = _eval(ctx={**CTX_OK, "venue_readable": None, "venue_qty_signed": None})
    assert v["approve"] is False
    assert _checks(v)["venue_holds_position"]["ok"] is False
    assert _checks(v)["book_venue_in_sync"]["ok"] is False


def test_a_venue_readable_flag_that_is_merely_truthy_is_not_enough():
    """`is True`, not truthiness: a gatherer returning the string "no" must not
    read as readable."""
    v = _eval(ctx={**CTX_OK, "venue_readable": "no", "venue_qty_signed": 3.0})
    assert _checks(v)["venue_holds_position"]["ok"] is False


# --------------------------------------------------- the two ledgers agree ----

def test_the_drift_tolerance_is_the_reconcilers_own_number():
    """Two definitions of "in sync" is the second-opinion defect marksanity.py
    was written to name. If the reconciler's tolerance ever moves, this fails
    rather than letting the approval policy quietly keep the old one."""
    from app.fund.reconcile import _TOL
    assert MAX_POSITION_DRIFT_QTY == float(_TOL) == 1e-6


def test_drift_within_the_tolerance_is_in_sync_and_past_it_is_not():
    """Each side asserts its OWN arithmetic before asserting the verdict.

    Written that way because the first draft of this test used
    `3.0 - MAX_POSITION_DRIFT_QTY` as the "exactly at tolerance" case and
    failed: in binary that subtraction leaves a drift of
    1.0000000000287557e-06, which is genuinely OVER the bound. The code was
    right and the test was wrong — and a test that asserts a threshold it has
    not checked its own inputs against is how a boundary gets "fixed" in the
    loosening direction.
    """
    inside = 3.0 - MAX_POSITION_DRIFT_QTY / 2
    assert abs(3.0 - inside) <= MAX_POSITION_DRIFT_QTY
    at = _eval(ctx={**CTX_OK, "book_qty_signed": 3.0,
                    "venue_qty_signed": inside})
    assert _checks(at)["book_venue_in_sync"]["ok"] is True
    assert at["approve"] is True, at["checks"]

    outside = 3.0 - MAX_POSITION_DRIFT_QTY * 10
    assert abs(3.0 - outside) > MAX_POSITION_DRIFT_QTY
    past = _eval(ctx={**CTX_OK, "book_qty_signed": 3.0,
                      "venue_qty_signed": outside})
    assert _checks(past)["book_venue_in_sync"]["ok"] is False
    assert past["approve"] is False


def test_a_venue_holding_MORE_than_the_book_is_still_out_of_sync():
    """Drift in the comfortable direction is still drift: the fund does not
    know what it holds, and a check that only looks one way is half a check."""
    v = _eval(ctx={**CTX_OK, "book_qty_signed": 3.0, "venue_qty_signed": 9.0})
    assert _checks(v)["book_venue_in_sync"]["ok"] is False
    # The venue check alone would have PASSED this one — selling 1.0 against a
    # broker long 9.0 reduces exposure — which is why sync is its own check.
    assert _checks(v)["venue_holds_position"]["ok"] is True
    assert v["approve"] is False


# ------------------------------------------------- the ledgers are separate ---

def test_the_book_can_be_right_while_the_strategy_ledger_is_wrong():
    """Three ledgers, three checks. A fund-wide book that nets to a healthy
    long must not excuse a rule whose own strategy holds nothing."""
    v = _eval(ctx={**CTX_OK, "rule_strategy_holding_qty": 0.0})
    c = _checks(v)
    assert c["rule_owner_holds_position"]["ok"] is False
    assert c["exit_reduces_exposure"]["ok"] is True
    assert v["approve"] is False


def test_a_strategy_that_is_SHORT_is_no_longer_read_as_flat():
    """v3's gatherer clamped the strategy holding with `max(0.0, ...)`, so a
    strategy holding −5 reported 0.0 — absence-is-zero, one ledger over. The
    sign now survives, and a SELL against a short correctly refuses (it would
    deepen the short, not close it)."""
    v = _eval(ctx={**CTX_OK, "rule_strategy_holding_qty": -5.0,
                  "book_qty_signed": -5.0, "venue_qty_signed": -5.0})
    c = _checks(v)
    assert c["rule_owner_holds_position"]["ok"] is False
    assert c["exit_reduces_exposure"]["ok"] is False
    assert c["venue_holds_position"]["ok"] is False
    assert v["approve"] is False


# ----------------------------------------------- v4 tightens and only tightens

def test_v4_did_not_rename_side_is_sell():
    """A previous approval-path diff from this seat was killed for a guard
    predicate RENAME that flipped a refusal into an allow while reading as a
    tidy-up. `side_is_sell` -> `side_reduces_exposure` is the specific widening
    R19 names and defers to the adversary blind, so its absence is pinned at
    the source level, not just behaviourally."""
    import pathlib

    import app.fund.autopolicy as ap
    src = pathlib.Path(ap.__file__).read_text(encoding="utf-8")
    assert 'check("side_is_sell"' in src
    assert 'check("side_reduces_exposure"' not in src
    assert "side_is_sell" in {c["check"] for c in _eval()["checks"]}


#: Exactly the checks v3 made. The spec's headline number — "v3 approves the
#: 2026-09-08 exits TWELVE CHECKS OUT OF TWELVE" — is this set's size, and the
#: keystone test above asserts every one of them is still TRUE for that order.
V3_CHECKS = {"side_is_sell", "exit_rule_provenance", "exit_trigger_linked",
             "rule_predates_position", "mark_corroborated",
             "rule_owner_holds_position", "notional_within_cap", "not_halted",
             "liveness_exit_check", "liveness_risk_monitor",
             "liveness_settlement", "freshness"}


def test_v4_added_three_checks_and_removed_none():
    """v4 is strictly tightening: it may only ADD to the conjunction. Dropping
    a v3 check while adding three new ones would read as a net tightening in
    any summary and be a loosening in fact."""
    names = {c["check"] for c in _eval()["checks"]}
    assert len(V3_CHECKS) == 12, "the spec's 'twelve out of twelve' is this set"
    assert V3_CHECKS <= names
    assert names - V3_CHECKS == {"exit_reduces_exposure",
                                 "venue_holds_position", "book_venue_in_sync"}


def test_evaluate_returns_a_verdict_for_a_malformed_context_and_never_raises():
    """evaluate() is the deterministic core of an execution path. An exception
    here aborts the whole tick and leaves every REMAINING order unevaluated —
    so a value that will not parse must become a decline, not a traceback."""
    for bad in ("banana", float("nan"), float("inf"), object(), [1, 2]):
        v = _eval(ctx={**CTX_OK, "book_qty_signed": bad,
                       "venue_qty_signed": bad,
                       "rule_strategy_holding_qty": bad})
        assert v["approve"] is False
        assert {"exit_reduces_exposure", "venue_holds_position",
                "book_venue_in_sync", "rule_owner_holds_position"} <= _failed(v)


def test_venue_snapshot_fails_the_whole_read_on_one_unreadable_row():
    """A row with a symbol but no readable quantity must NOT be skipped: the
    symbol it names would then be absent from the dict, and absent from a read
    list means flat. Silently dropping it is absence-is-zero one layer down."""
    class MissingQty:
        def positions(self):
            return [FakePos("TLT", 3.0), FakePos("DBC", None)]

    class MissingSymbol:
        def positions(self):
            return [FakePos("TLT", 3.0), FakePos(None, 1.0)]

    assert venue_snapshot(MissingQty()) == (False, {})
    assert venue_snapshot(MissingSymbol()) == (False, {})


def test_v4_never_adds_a_check_on_the_orders_own_venue_string():
    """exitrule.py hardcodes venue="paper" on EVERY exit it raises, whatever
    connector executes it — so an `order["venue"] == "paper"` check would have
    passed the exact orders that go to Alpaca. The broker's own answer is the
    only venue fact worth reading. Pinned behaviourally: the order's venue
    string must make no difference to the verdict."""
    paper = _eval(_order(venue="paper"), ctx=_the_2026_09_08_context())
    alpaca = _eval(_order(venue="alpaca"), ctx=_the_2026_09_08_context())
    none_ = _eval(_order(), ctx=_the_2026_09_08_context())
    assert paper["approve"] is alpaca["approve"] is none_["approve"] is False
    assert (_checks(paper)["venue_holds_position"]["detail"]
            == _checks(alpaca)["venue_holds_position"]["detail"])


# ---------------------------------------------- the gatherer, first tests ever

class MemStore:
    """Enough of the event store for the gatherer: dict rows with the keys it
    reads. Mirrors what pgstore.stream() returns, same as test_marksanity."""

    def __init__(self):
        self.rows = []

    def add(self, type_, payload, aggregate_id="x", ts="2026-08-20T08:00:00Z"):
        self.rows.append({"type": type_, "payload": payload,
                          "aggregate_id": aggregate_id, "ts": ts})
        return self

    def stream(self, since_seq=0, limit=100_000):
        return list(self.rows)


def _log_with_a_tlt_position(qty=3.019871, strategy="sleeve_beta_500"):
    s = MemStore()
    s.add("ExitRuleSet", {"strategy_id": strategy, "symbol": "TLT",
                          "kind": "time", "at": "2026-08-18T02:11:39+00:00"})
    s.add("OrderFilled", {"symbol": "TLT", "side": "buy", "filled_qty": qty,
                          "strategy_id": strategy,
                          "at": "2026-08-19T18:20:54+00:00"})
    s.add("NavStruck", {"total_nav_usd": 1885.74,
                        "positions": [{"symbol": "TLT", "mark": 82.045}]})
    s.add("ExitRuleTriggered", {"order_id": "o1", "symbol": "TLT",
                                "kind": "time", "strategy_id": strategy})
    return s


def test_context_for_exposes_the_signed_book_it_used_to_throw_away():
    """`context_for` had NO tests before v4 — the gatherer, where the venue read
    now lives, was entirely untested. This is the first."""
    s = _log_with_a_tlt_position()
    ctx = context_for(s, {"order_id": "o1", "symbol": "TLT", "side": "sell",
                          "qty": 3.019871}, None,
                      venue_positions={"TLT": 3.019871}, venue_readable=True)
    assert ctx["book_qty_signed"] == 3.019871
    assert ctx["rule_strategy_holding_qty"] == 3.019871
    assert ctx["venue_readable"] is True
    assert ctx["venue_qty_signed"] == 3.019871


def test_context_for_reports_a_symbol_absent_from_a_READ_list_as_zero():
    """Both connectors OMIT flat symbols, so absence from a list we DID read
    means zero. That inference is legitimate ONLY because `venue_readable`
    records that we read one — and this is the 2026-09-08 gather."""
    s = _log_with_a_tlt_position()
    ctx = context_for(s, {"order_id": "o1", "symbol": "TLT", "side": "sell",
                          "qty": 3.019871}, None,
                      venue_positions={"SPY": 0.217757}, venue_readable=True)
    assert ctx["venue_readable"] is True
    assert ctx["venue_qty_signed"] == 0.0
    assert ctx["book_qty_signed"] == 3.019871
    # And the whole thing declines, gathered end to end rather than hand-built.
    v = evaluate({"order_id": "o1", "symbol": "TLT", "side": "sell",
                  "qty": 3.019871,
                  "rationale": f"{EXIT_MARKER}. 21 calendar days."},
                 halted=False, heartbeats=HB_OK, age_minutes=0.5, context=ctx)
    assert v["approve"] is False
    assert _checks(v)["venue_holds_position"]["ok"] is False


def test_a_caller_that_passes_no_venue_at_all_fails_closed():
    """The fail-closed default. A caller not yet updated for v4 — or a test,
    or a future second call site — must decline, never approve on a phantom
    flat book. An empty dict is NOT the same as an unread one, and the
    difference is carried by the flag, never inferred from the dict."""
    s = _log_with_a_tlt_position()
    order = {"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 3.019871}

    unread = context_for(s, order, None)
    assert unread["venue_readable"] is False
    assert unread["venue_qty_signed"] is None

    read_and_flat = context_for(s, order, None, venue_positions={},
                                venue_readable=True)
    assert read_and_flat["venue_readable"] is True
    assert read_and_flat["venue_qty_signed"] == 0.0

    # Same empty dict, opposite meaning, different detail string.
    d_unread = _checks(evaluate(order, halted=False, heartbeats=HB_OK,
                                age_minutes=0.5,
                                context=unread))["venue_holds_position"]
    d_flat = _checks(evaluate(order, halted=False, heartbeats=HB_OK,
                              age_minutes=0.5,
                              context=read_and_flat))["venue_holds_position"]
    assert d_unread["ok"] is False and d_flat["ok"] is False
    assert d_unread["detail"] != d_flat["detail"]


def test_context_for_keeps_the_venue_read_even_when_the_log_walk_explodes():
    """The venue read is independent of the event log, so a broken store must
    not erase what the broker said. The order still declines — `book_qty_signed`
    is absent — but the audit records the broker's answer instead of losing it."""
    class Exploding:
        def stream(self, *a, **k):
            raise RuntimeError("store unreachable")

    ctx = context_for(Exploding(), {"order_id": "o1", "symbol": "TLT",
                                    "side": "sell", "qty": 1.0}, None,
                      venue_positions={"TLT": 3.0}, venue_readable=True)
    assert ctx["venue_readable"] is True
    assert ctx["venue_qty_signed"] == 3.0
    assert "book_qty_signed" not in ctx
    v = evaluate({"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 1.0},
                 halted=False, heartbeats=HB_OK, age_minutes=0.5, context=ctx)
    assert v["approve"] is False
    assert {"exit_reduces_exposure", "book_venue_in_sync"} <= _failed(v)


def test_a_corporate_action_is_not_folded_and_that_fails_CLOSED():
    """A NAMED narrowness, pinned so it cannot be mistaken for an oversight.

    `context_for` folds ORDER_FILLED only. PositionsProjection also folds
    CORPORATE_ACTION_APPLIED (positions.py:101-114), which rewrites a symbol's
    quantity outright on a split. So after a split, `book_qty_signed` disagrees
    with the fund's official book.

    That disagreement may only fail CLOSED, and this test is what says so: the
    stale fold differs from the venue by the split ratio, `book_venue_in_sync`
    trips, and the order waits for the CEO. If someone later "fixes" this by
    widening the tolerance instead of folding the projection, this test fails.
    """
    s = _log_with_a_tlt_position(qty=3.0)
    s.add("CorporateActionApplied", {"symbol": "TLT", "old_qty": 3.0,
                                     "new_qty": 6.0})
    order = {"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 6.0}
    # The venue HAS applied the split; our fold has not.
    ctx = context_for(s, order, None, venue_positions={"TLT": 6.0},
                      venue_readable=True)
    assert ctx["book_qty_signed"] == 3.0, "the split is deliberately not folded"

    v = evaluate(order, halted=False, heartbeats=HB_OK, age_minutes=0.5,
                 context={**CTX_OK, **{k: ctx[k] for k in
                                       ("book_qty_signed", "venue_readable",
                                        "venue_qty_signed")}})
    assert v["approve"] is False
    assert _checks(v)["book_venue_in_sync"]["ok"] is False
    # The venue check is unaffected — it reads the broker, not our fold.
    assert _checks(v)["venue_holds_position"]["ok"] is True


def test_context_for_keeps_a_short_strategy_holding_negative():
    s = _log_with_a_tlt_position(qty=-4.0)
    ctx = context_for(s, {"order_id": "o1", "symbol": "TLT", "side": "sell",
                          "qty": 1.0}, None,
                      venue_positions={"TLT": -4.0}, venue_readable=True)
    # A "buy" fill of −4.0 folds to −4.0; the point is that the clamp is gone.
    assert ctx["rule_strategy_holding_qty"] == -4.0
    assert ctx["book_qty_signed"] == -4.0


# ------------------------------------------------- the venue snapshot itself --

class FakePos:
    def __init__(self, symbol, qty):
        self.symbol, self.qty = symbol, qty


def test_venue_snapshot_separates_could_not_look_from_looked_and_flat():
    class Flat:
        def positions(self):
            return []

    class Unreachable:
        def positions(self):
            raise ConnectionError("alpaca timeout")

    flat_ok, flat = venue_snapshot(Flat())
    dead_ok, dead = venue_snapshot(Unreachable())
    assert (flat_ok, flat) == (True, {})
    assert (dead_ok, dead) == (False, {})
    # Identical dicts, opposite meanings. The flag is the only thing that tells
    # them apart, which is why it is not carried inside the dict.
    assert flat == dead and flat_ok != dead_ok


def test_venue_snapshot_reads_signs_and_both_row_shapes():
    class Conn:
        def positions(self):
            return [FakePos("TLT", 3.019871), FakePos("SPY", -2.0),
                    {"symbol": "DBC", "qty": 8.122157}]

    ok, pos = venue_snapshot(Conn())
    assert ok is True
    assert pos == {"TLT": 3.019871, "SPY": -2.0, "DBC": 8.122157}


def test_venue_snapshot_discards_a_partial_parse_rather_than_half_reading():
    """A partial read is not a read. Returning the rows parsed before the bad
    one would report the remaining symbols as flat."""
    class Conn:
        def positions(self):
            return [FakePos("TLT", 3.0), FakePos("SPY", "not-a-number")]

    ok, pos = venue_snapshot(Conn())
    assert ok is False and pos == {}


def test_venue_snapshot_has_no_connector_at_all():
    assert venue_snapshot(None) == (False, {})


def test_venue_snapshot_sums_duplicate_rows_rather_than_dropping_half():
    class Conn:
        def positions(self):
            return [FakePos("TLT", 2.0), FakePos("TLT", 1.019871)]

    ok, pos = venue_snapshot(Conn())
    assert ok is True and abs(pos["TLT"] - 3.019871) < 1e-12


# --------------------------------------------------- a decline must be heard --

def test_every_decline_is_logged_with_the_checks_that_failed(caplog):
    """THE OTHER HALF OF R19, and it is not optional.

    Before this, run() logged approvals and errors only, and the worker
    discards run()'s return value — so an order the envelope REFUSED produced
    no event, no log line and no alarm. Shipping v4's refusal without this line
    converts "the machine silently opens a $652 short" into "the machine
    silently stops honouring the fund's exits". Both are the unwired kill
    switch; only the costume differs.

    Worse, the refused proposal does not come back: it expires at 120 minutes,
    and ExitRules skips any rule carrying `triggered_at` (only a fresh
    EXIT_RULE_SET clears it — seq 195 is a human doing that by hand).
    """
    class Pipe:
        def approve_order(self, *a, **k):
            raise AssertionError("must not be called")

    with caplog.at_level(logging.WARNING, logger="app.fund.autopolicy"):
        out = run(Pipe(), [_order(symbol="TLT", qty=LIVE_BOOK_TLT)],
                  halted=False, heartbeats=HB_OK,
                  context_fn=lambda row: _the_2026_09_08_context())

    assert out["approved"] == [] and len(out["skipped"]) == 1
    text = caplog.text
    assert "AUTOPOLICY DECLINED" in text
    assert "TLT" in text
    # The failed check must be NAMED, not merely counted — the fix for a venue
    # refusal and the fix for a stale mark are different fixes.
    assert "venue_holds_position" in text


def test_the_skipped_row_still_carries_every_failed_check_for_the_audit():
    class Pipe:
        def approve_order(self, *a, **k):
            raise AssertionError("must not be called")

    out = run(Pipe(), [_order(symbol="TLT", qty=LIVE_BOOK_TLT)],
              halted=False, heartbeats=HB_OK,
              context_fn=lambda row: _the_2026_09_08_context())
    failed = set(out["skipped"][0]["failed_checks"])
    assert {"venue_holds_position", "book_venue_in_sync"} <= failed
    assert out["skipped"][0]["symbol"] == "TLT"
