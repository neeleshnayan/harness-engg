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


def _filled(store, symbol, side, qty, avg_price=100.0):
    """A fill, carrying ``avg_price`` because a real one always does.

    The price is required by ``PositionsProjection`` — the fund's one true
    holdings fold, which this guard now reads instead of summing fills itself
    (ticket d79f65b1). Every OrderFilled in the live log carries it; a fixture
    that omitted it was describing an event the fund has never emitted, and
    ``test_a_fill_with_no_avg_price_cannot_be_folded_so_the_guard_refuses``
    pins what happens if one ever appears.
    """
    return store.add("OrderFilled",
                     {"symbol": symbol, "side": side, "filled_qty": qty,
                      "avg_price": avg_price})


def _reconciled(store, venue_qty: dict, ts="2026-08-24T12:36:46Z"):
    """A ``BookReconciledToVenue``: the venue sync, which SETS quantities.

    The event at the centre of ticket d79f65b1. It is not a trade — nothing was
    bought or sold — and it is applied as an absolute SET, so it can both erase
    a position the fill history still remembers and adopt one the fill history
    has never seen.
    """
    return store.add("BookReconciledToVenue",
                     {"positions": [{"symbol": s, "venue_qty": q,
                                     "venue_avg_price": 10.0}
                                    for s, q in venue_qty.items()],
                      "run_id": "sync-1414", "actor": "cto"},
                     aggregate_id="book", ts=ts)


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


def test_a_fill_payload_using_the_wrong_key_is_still_a_holding_to_the_true_fold():
    """`qty` instead of `filled_qty` — and the two folds read it DIFFERENTLY.

    CHANGED BY d79f65b1, deliberately, and this is the honest record of it.
    The old fill-sum read `filled_qty` only, so a fill written with the wrong
    key vanished and the order took the new-symbol branch — an ALLOW.
    ``PositionsProjection`` falls back to `qty` (positions.py:162), so the same
    event IS a holding to the fund's real book, and an unmarked holding refuses.

    That is a TIGHTENING, and it is the correct direction: the guard's answer
    to "does the fund hold this" now agrees with the book NAV values and the
    reconciler compares, instead of with a private sum that agreed with
    neither. A guard that disagrees with the fund's own book about what the
    fund owns is the whole defect this ticket names.
    """
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    s.add("OrderFilled", {"symbol": "GLD", "side": "buy", "qty": 3.0,
                          "avg_price": 100.0})
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    assert v["basis"] == "held_but_unpriced"
    assert v["refuse"] is True
    assert v["held_qty"] == 3.0
    # And the divergence is visible rather than silent: the retired fill-sum
    # saw nothing where the book sees three.
    assert v["held_qty_from_fills"] == 0.0


def test_a_fill_with_no_avg_price_cannot_be_folded_so_the_guard_refuses():
    """Fail-closed on an unfoldable book — the projection needs a price.

    ``PositionsProjection._apply`` indexes ``p["avg_price"]`` directly, so a
    fill without one raises. The guard must then report the holding ABSENT and
    refuse; it must never fall back to the fill-sum, because falling back on
    the failure path would quietly restore the exact defect d79f65b1 removes.
    """
    s = MemStore()
    _struck(s, {"TLT": 82.0})
    s.add("OrderFilled", {"symbol": "GLD", "side": "buy", "filled_qty": 3.0})
    _proposed(s, "o", "GLD", 100.0)
    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "holdings_unreadable"
    assert v["held_qty"] is None, "an unreadable book reported a quantity"
    assert "avg_price" in v["reason"]


# ------------------------------------- the venue sync (ticket d79f65b1) -----
#
# Every fixture below is built from the fund's own state at the reconciliation
# of 2026-08-24T12:36:46Z (seq 1414), measured before the repair. At that one
# event the guard's fill-sum and the fund's true book disagreed about NINE of
# eleven symbols, in BOTH directions — and the guard was wrong in both.


def test_a_position_erased_by_the_sync_is_NOT_held_and_the_repurchase_proceeds():
    """THE LIVE BLOCKER. DBC: fill-sum 8.122157, true book ZERO.

    2026-08-24: the venue sync set DBC/TLT/DBA to zero. The guard, still summing
    fills, believed the fund held all three, refused each approved repurchase as
    ``held_but_unpriced``, and told the operator to "strike NAV first" — which
    can never work, because NAV marks ``book.positions`` and the sync had popped
    the symbol out of it. Three approved orders were unclickable by anyone, and
    the guard was carrying forward the exact phantom the sync existed to erase.

    DIRECTION: this is a LOOSENING of the ``held_but_unpriced`` branch, and it
    is loosening a refusal that was FALSE. The fund does not hold DBC. The
    corroboration this branch demands is not being skipped — there is nothing
    to corroborate, which is what the new-symbol branch records.
    """
    s = MemStore()
    _filled(s, "DBC", "buy", 8.122157)          # the fill history, still there
    _reconciled(s, {"DBC": 0.0})                # the sync erased the position
    _struck(s, {"SPY": 762.95})                 # NAV cannot mark what it lost
    _proposed(s, "ord-dbc", "DBC", 21.79, side="buy", qty=8.122157)

    v = marksanity.check(s, "ord-dbc")
    assert v["refuse"] is False, (
        "the phantom is still being mistaken for a holding: " + v["reason"])
    assert v["basis"] == "no_reference_new_symbol"
    assert v["held_qty"] == 0.0
    # The fill-sum that caused it is preserved, so the divergence is legible.
    assert abs(v["held_qty_from_fills"] - 8.122157) < 1e-9
    assert v["holdings_basis"] == "positions_projection"


def test_a_position_ADOPTED_by_the_sync_with_no_fill_history_is_REFUSED():
    """The other direction, and it was LIVE too — not hypothetical.

    At the same event the sync adopted GLD 0.424471, INTC 1.608762, MSFT
    0.340051, NVDA 0.749886, SOFI 9.188190 and XLE 2.749912 — six real
    positions with NO fill history, the custody schema's ``foreign`` class (an
    actor outside the harness). The fill-sum read every one of them as zero, so
    the guard took the never-owned branch and skipped corroboration on six
    positions the fund genuinely held. That is precisely the integrity case this
    module exists to catch, walked past by a wrong input.

    DIRECTION: a TIGHTENING. A sync-adopted, unmarked position now refuses.
    """
    s = MemStore()
    _reconciled(s, {"GLD": 0.424471})           # adopted; no fill ever occurred
    _struck(s, {"SPY": 762.95})                 # and no mark for it
    _proposed(s, "ord-gld", "GLD", 415.04, side="buy")

    v = marksanity.check(s, "ord-gld")
    assert v["refuse"] is True, (
        "a position the fund holds with no fill history was waved through as "
        "a never-owned symbol — the foreign-custody hole")
    assert v["basis"] == "held_but_unpriced"
    assert abs(v["held_qty"] - 0.424471) < 1e-9
    assert v["held_qty_from_fills"] == 0.0
    # The remedy this branch names is now reachable: the fund really does hold
    # it, so the next NAV strike really can mark it.
    assert "Strike NAV first" in v["reason"]


def test_the_two_folds_disagree_on_SPY_and_the_verdict_follows_the_TRUE_one():
    """SPY's real numbers, pinned so the folds cannot silently diverge again.

    Live at head 2026-08-24: fill-sum 0.474481, true book 0.346119 — a 37%
    overstatement that no test could see, because both numbers are non-zero and
    the branch only asks "is it held". The quantity is not decorative: it is
    quoted verbatim in the refusal the CEO reads, so the old guard printed a
    holding the fund does not have.
    """
    s = MemStore()
    _filled(s, "SPY", "buy", 0.474481)
    _reconciled(s, {"SPY": 0.346119})
    _struck(s, {"TLT": 82.0})                   # SPY unmarked, so we see held
    _proposed(s, "o", "SPY", 762.95, side="sell", qty=0.1)

    v = marksanity.check(s, "o")
    assert v["basis"] == "held_but_unpriced"
    assert abs(v["held_qty"] - 0.346119) < 1e-9
    assert abs(v["held_qty_from_fills"] - 0.474481) < 1e-9
    assert v["held_qty"] != v["held_qty_from_fills"], (
        "the fixture no longer contains a divergence, so it can no longer "
        "prove which fold the verdict follows")
    # The number the CEO reads is the one the fund actually holds.
    assert "0.346119" in v["reason"]
    assert "0.474481" not in v["reason"]


def test_the_held_quantity_is_READ_from_the_projection_not_copied_from_fills():
    """Move the value; the verdict must move with it.

    An assertion that ``held_qty`` equals the projection's number cannot tell a
    genuine read from a duplicate that happens to agree today. So the venue
    number is MOVED across the branch boundary — 0 to 5 — with the fill history
    held constant, and the verdict must flip from ALLOW to REFUSE. Nothing that
    reads the fill-sum can produce this table.
    """
    seen = []
    for venue_qty, expect_refuse, expect_basis in [
            (0.0, False, "no_reference_new_symbol"),
            (5.0, True, "held_but_unpriced")]:
        s = MemStore()
        _filled(s, "DBC", "buy", 8.122157)      # identical in both arms
        _reconciled(s, {"DBC": venue_qty})
        _struck(s, {"SPY": 762.95})
        _proposed(s, "o", "DBC", 21.79, side="buy")
        v = marksanity.check(s, "o")
        assert v["refuse"] is expect_refuse and v["basis"] == expect_basis, (
            f"venue_qty={venue_qty} gave {v['basis']}/{v['refuse']}")
        seen.append(v["held_qty"])
    assert seen == [0.0, 5.0], seen


def test_an_unreadable_book_refuses_even_when_the_mark_agrees():
    """Fail-closed, on the branch that does not read holdings at all.

    A quote that agrees with the last strike would pass ``corroborated`` on its
    own. It must still refuse when the book cannot be folded: the guard should
    never approve while the fund's own holdings are unknown, and a projection
    that raises means NAV cannot strike either, so the mark it agreed with is
    going stale in the same minute. Stated plainly because it is a TIGHTENING.
    """
    s = MemStore()
    _struck(s, {"GLD": 415.04})
    s.add("OrderFilled", {"symbol": "GLD", "side": "buy",
                          "filled_qty": 1.0})   # no avg_price -> fold raises
    _proposed(s, "o", "GLD", 415.04)            # 0% move; would corroborate

    v = marksanity.check(s, "o")
    assert v["refuse"] is True
    assert v["basis"] == "holdings_unreadable"


def test_an_absent_holding_is_never_read_as_zero():
    """`evaluate` is pure, so drive the exact absence the gatherer can produce.

    The retired code said ``_num(facts.get("held_qty")) or 0.0``. That idiom
    turns "the book was not read" into "the fund holds none", which is the
    new-symbol branch, which APPROVES. Absence is never zero — and here that
    non-negotiable is the difference between refusing and approving.
    """
    v = marksanity.evaluate({"symbol": "GLD", "quote_price": 415.04,
                             "reference_mark": None, "held_qty": None})
    assert v["refuse"] is True
    assert v["basis"] == "holdings_unreadable"
    assert v["basis"] != "no_reference_new_symbol"


def test_the_fill_sum_is_a_diagnostic_and_no_branch_reads_it():
    """Poison the diagnostic; every verdict must be byte-identical.

    ``held_qty_from_fills`` is preserved beside the true number so a future
    divergence is legible in the refusal record (the Clean Field Rule's
    "annotate, never erase"). It is NOT an input, and this proves it: if any
    branch ever starts reading it, one of these verdicts changes.
    """
    base = {"symbol": "GLD", "quote_price": 415.04, "reference_mark": None}
    for held, poison in [(0.0, 8.122157), (0.0, -8.122157),
                         (5.0, 0.0), (5.0, 999.0)]:
        clean = marksanity.evaluate({**base, "held_qty": held,
                                     "held_qty_from_fills": None})
        dirty = marksanity.evaluate({**base, "held_qty": held,
                                     "held_qty_from_fills": poison})
        assert clean["refuse"] == dirty["refuse"]
        assert clean["basis"] == dirty["basis"]
        assert clean["reason"] == dirty["reason"]


def test_a_broken_book_fold_does_not_crash_the_guard():
    """A projection import or fold that explodes must REFUSE, never raise.

    The endpoint calls this inside a request; an exception here would surface
    as a 500 and the operator would learn nothing. The guard's contract is that
    it can only ever narrow itself by failing.
    """
    class Exploding:
        def stream(self, since_seq=0, limit=100_000):
            # The gatherer's own pass must succeed, so this yields a valid
            # proposal and then a fill the projection cannot fold.
            return [
                {"type": "OrderProposed", "aggregate_id": "o",
                 "ts": "2026-08-24T12:00:00Z",
                 "payload": {"symbol": "DBC", "side": "buy", "qty": 1.0,
                             "impact_preview": {"quote_price": 21.79}}},
                {"type": "OrderFilled", "aggregate_id": "f",
                 "ts": "2026-08-24T12:01:00Z",
                 "payload": {"symbol": "DBC", "side": "buy",
                             "filled_qty": "not-a-number",
                             "avg_price": "also-not-a-number"}},
            ]

    v = marksanity.check(Exploding(), "o")      # must not raise
    assert v["refuse"] is True
    assert v["basis"] == "holdings_unreadable"


def test_the_repair_did_not_touch_the_bound_or_the_CEOs_flag():
    """Two values this ticket was explicitly forbidden to move.

    The bound is autopolicy's single constant; the flag is a versioned CEO
    decision. A correctness repair of one INPUT must leave both exactly where
    it found them, and a reviewer should be able to see that in one test.
    """
    import inspect
    src = inspect.getsource(marksanity)
    assert "MAX_MARK_MOVE_VS_STRIKE_PCT = " not in src
    assert "from app.fund.autopolicy import MAX_MARK_MOVE_VS_STRIKE_PCT" in src
    assert marksanity.NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES is False
    assert "NEW_SYMBOL_WITHOUT_REFERENCE_REFUSES = False" in src


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
                 "payload": {"symbol": "GLD", "side": "buy", "filled_qty": 1.0,
                             "avg_price": 415.04}},
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
                 "payload": {"symbol": "GLD", "side": "buy", "filled_qty": 1.0,
                             "avg_price": 415.04}},
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
