"""THE r2 REGRESSION SUITE — the two kills and the four residuals.

Every test here is named for an incident. run-adversary-night2 KILLED the r1
draft on two structural grounds and filed four residuals with the kill; this
file is what must go red if any of the six ever comes back.

**A SEPARATE FILE ON PURPOSE.** ``test_autopolicy_v5_draft.py`` is the
envelope's own suite and its fixture is a context in which every check passes.
These tests exist because that fixture's ANCESTOR passed while the envelope was
wrong, so they carry their own numbers — the adversary's, verbatim, at
$1,885.74 NAV and an $80 mark — rather than inheriting a fixture that has since
been corrected. A regression test that shares a fixture with the code under
repair can be made green by editing the fixture.
"""

import pytest

from app.fund import autopolicy_v5_draft as V5

# The adversary's own numbers, from run-adversary-night2. Not rounded, not
# tidied: the point of a regression test is to reproduce the incident.
NAV = 1885.74
MARK = 80.0
SID = "sleeve_premia_equity"
#: 14.9% of NAV at an $80 mark — one tick under the 15% per-order ceiling, which
#: is what let two of them stack to 29.8% inside a 20% per-name ceiling.
QTY = round(0.149 * NAV / MARK, 4)


def ctx(**over):
    base = {
        "engine_entries_enabled": True,
        "execution_venue_kind": "alpaca_paper",
        "execution_venue_real_money": False,
        "strategy": {"strategy_id": SID, "state": "deployed",
                     "archived": False, "assets": ["HYG"]},
        "strategy_allocation_pct": 40.0,
        "live_sessions": [{"session_id": "2f3492903246", "strategy_id": SID,
                           "state": "running",
                           "started_at": "2026-08-28T09:00:00+00:00"}],
        "signal_raised_at": "2026-08-28T12:00:00+00:00",
        "nav_usd": NAV,
        "order_mark_usd": MARK,
        "mark_move_vs_strike_pct": 0.0,
        "day_auto_notional_usd": 0.0,
        "pending_approved": [],
        "book_qty_signed": 0.0,
        "strategy_qty_signed": 0.0,
        "venue_qty_signed": 0.0,
        "venue_readable": True,
        "strategy_exposure_usd": 0.0,
        "gross_exposure_usd": 0.0,
        "mandate_gross_fraction": 0.95,
        "throttle_multiplier": 1.0,
        "throttle_measurable": True,
        "max_position_fraction": 0.20,
        "committed_exit": {"set_at": "2026-08-28T08:00:00+00:00", "live": True},
    }
    base.update(over)
    return base


HB = {j: {"ok": True, "age_seconds": 20.0} for j in V5.REQUIRED_HEARTBEATS}


#: A SENTINEL RATHER THAN ``None`` AS THE DEFAULT, because ``None`` is one of
#: the values these tests must be able to FEED. The first version of this
#: helper used ``qty=None`` as its default and silently substituted the good
#: quantity for the bad one — a test that fed an absent quantity and asserted a
#: refusal was really asserting an approval.
_KEEP = object()


def order(side="buy", qty=_KEEP, symbol="HYG", **over):
    o = {"order_id": "o1", "symbol": symbol, "side": side,
         "qty": QTY if qty is _KEEP else qty, "strategy_id": SID}
    o.update(over)
    return o


def run(o=None, age=0.5, halted=False, beats=None, **ctx_over):
    return V5.evaluate(o or order(), halted=halted,
                       heartbeats=HB if beats is None else beats,
                       signal_age_minutes=age, context=ctx(**ctx_over))


def failed(**ctx_over):
    return set(run(**ctx_over)["failed"])


def detail(out, name):
    rows = [c["detail"] for c in out["checks"] if c["check"] == name]
    assert len(rows) == 1, f"{name} appears {len(rows)} times"
    return rows[0]


def pending(qty=None, side="buy", symbol="HYG", strategy_id=SID, mark=MARK,
            age=0.2, oid="p1", **over):
    row = {"order_id": oid, "symbol": symbol, "side": side,
           "qty": QTY if qty is None else qty, "mark_usd": mark,
           "age_minutes": age, "strategy_id": strategy_id}
    row.update(over)
    return row


# ============================================================ THE POSITIVE CONTROL

def test_the_base_context_approves():
    """WITHOUT THIS EVERY REFUSAL TEST BELOW IS VACUOUS. An envelope that
    refused everything would satisfy all of them, and the r2 diff adds four new
    checks that could each have done exactly that."""
    out = run()
    assert out["approve"] is True, out["failed"]
    assert out["failed"] == []


# ==================================================== KILL 1 — THE IN-FLIGHT LEDGER

class TestTheInFlightLedger:
    """KILL 1, run-adversary-night2 (probes p3_inflight.py, p4_bestcase.py).

    Every r1 bound was computed from the FILLED book. An order this envelope
    had approved forty milliseconds earlier was in neither the fund's fold
    (nothing filled) nor the broker's snapshot (the broker holds no unfilled
    order), so five signals in one tick each measured a flat book and each
    approved: 5 x 14.9% = 74.5% of NAV in one name against a 20% ceiling.
    """

    def test_TWO_ORDERS_THAT_STACK_TO_29_8_PERCENT_ARE_REFUSED(self):
        """THE INCIDENT, reproduced at its own numbers. The second order is the
        one r1 approved."""
        first = run()
        assert first["approve"] is True, first["failed"]

        second = run(pending_approved=[pending(oid="o1")])
        assert second["approve"] is False
        assert "post_fill_name_within_concentration" in second["failed"]
        # THE NUMBER, not just the refusal. 29.80% is the figure the adversary
        # measured the book reaching; asserting only ``approve is False`` would
        # pass on an envelope that refused for an unrelated reason.
        assert "29.80% of NAV against a 20.00% ceiling (OVER)" in detail(
            second, "post_fill_name_within_concentration")

    def test_an_UNREADABLE_ledger_refuses_and_an_EMPTY_one_does_not(self):
        """THE THREE-VALUED INPUT, both ends. ``None`` is "we could not ask";
        ``[]`` is "we asked and nothing is in flight". Collapsing them is how
        "we could not look" becomes "everything is fine" — and the opposite
        collapse would make the envelope refuse every order forever, which is
        the failure mode a control dies of quietly."""
        assert "in_flight_ledger_readable" in failed(pending_approved=None)
        assert "in_flight_ledger_readable" not in failed(pending_approved=[])
        assert run(pending_approved=[])["approve"] is True

    def test_an_ABSENT_ledger_is_an_unreadable_one(self):
        """A gatherer that forgets the field must not be treated as one that
        read it and found nothing."""
        c = ctx()
        c.pop("pending_approved")
        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=c)
        assert "in_flight_ledger_readable" in out["failed"]

    @pytest.mark.parametrize("junk", [0, 0.0, -1, "rows", True, {}, 1e308,
                                      float("nan")])
    def test_a_ledger_that_is_not_a_LIST_refuses_rather_than_iterating(self, junk):
        """A string is iterable and a dict is iterable, and folding a session
        of characters or keys is worse than refusing. Eight of r1's seventeen
        exceptions came from iterating one of these."""
        assert "in_flight_ledger_readable" in failed(pending_approved=junk)

    @pytest.mark.parametrize("bad,why", [
        ({"symbol": "", "side": "buy", "qty": 1.0, "mark_usd": MARK,
          "age_minutes": 0.1}, "names no symbol"),
        ({"symbol": "HYG", "side": "short", "qty": 1.0, "mark_usd": MARK,
          "age_minutes": 0.1}, "neither buy nor sell"),
        ({"symbol": "HYG", "side": "buy", "qty": None, "mark_usd": MARK,
          "age_minutes": 0.1}, "non-positive quantity"),
        ({"symbol": "HYG", "side": "buy", "qty": 0.0, "mark_usd": MARK,
          "age_minutes": 0.1}, "non-positive quantity"),
        ({"symbol": "HYG", "side": "buy", "qty": -5.0, "mark_usd": MARK,
          "age_minutes": 0.1}, "non-positive quantity"),
        ({"symbol": "HYG", "side": "buy", "qty": True, "mark_usd": MARK,
          "age_minutes": 0.1}, "non-positive quantity"),
        ({"symbol": "HYG", "side": "buy", "qty": 1.0, "mark_usd": 0.0,
          "age_minutes": 0.1}, "non-positive mark"),
        ({"symbol": "HYG", "side": "buy", "qty": 1.0, "mark_usd": None,
          "age_minutes": 0.1}, "non-positive mark"),
        ("not a row", "not an order"),
        (7, "not an order"),
    ])
    def test_ONE_bad_row_makes_the_WHOLE_fold_unreadable(self, bad, why):
        """A sum with an unknown term is unknown, not the sum of its known
        terms — the same rule the engine ledger applies to an unquantified
        signal. A partial in-flight sum is worse than none: it looks like a
        measurement and bounds nothing.

        The reason is asserted as well as the refusal, and each ``why`` above
        appears in exactly one branch of ``in_flight`` — a shared phrase would
        let the wrong branch satisfy this test.
        """
        good = pending(qty=1.0, oid="good")
        out = run(pending_approved=[good, bad])
        assert "in_flight_ledger_readable" in out["failed"]
        assert why in detail(out, "in_flight_ledger_readable")

    def test_the_fold_reports_its_DOMAIN_when_it_can_be_read(self):
        """A null result with no domain is not a result. ``0 in flight`` and
        ``we did not look`` must read differently on the payload."""
        assert "none" in detail(run(pending_approved=[]),
                                "in_flight_ledger_readable")
        assert "1 approved order(s) still in flight" in detail(
            run(pending_approved=[pending(qty=0.01)]),
            "in_flight_ledger_readable")

    def test_in_flight_in_ANOTHER_symbol_consumes_GROSS_and_not_the_NAME(self):
        """The two bounds are different quantities and r1 had neither. A
        pending SPY order must not move HYG's concentration and must move the
        fund's gross."""
        out = run(pending_approved=[pending(symbol="SPY", qty=20.0)],
                  mandate_gross_fraction=0.10)
        assert "post_fill_gross_within_throttle" in out["failed"]
        assert "post_fill_name_within_concentration" not in out["failed"]

    def test_in_flight_for_ANOTHER_strategy_does_not_consume_THIS_allocation(self):
        """An allocation is per-strategy. Another strategy's in-flight order
        consumes the fund's gross and not this strategy's envelope."""
        other = pending(symbol="SPY", qty=20.0, strategy_id="someone_else")
        out = run(pending_approved=[other], strategy_allocation_pct=15.0)
        assert "post_fill_strategy_within_allocation" not in out["failed"]
        mine = pending(symbol="SPY", qty=20.0)
        assert "post_fill_strategy_within_allocation" in set(
            run(pending_approved=[mine], strategy_allocation_pct=15.0)["failed"])

    def test_the_bound_is_the_WORST_corner_and_not_the_NET(self):
        """MUTANT: net the in-flight set. A pending SELL that may never fill
        would then pay for a pending BUY that will, and the pair would report a
        flat book. The corner that matters for concentration is buys-only."""
        both = [pending(qty=QTY, side="buy", oid="b"),
                pending(qty=QTY, side="sell", oid="s")]
        out = run(pending_approved=both)
        # Netted, these two cancel and the book reads 14.90% — inside 20%.
        assert "post_fill_name_within_concentration" in out["failed"]
        assert "29.80%" in detail(out, "post_fill_name_within_concentration")


class TestTheInFlightFreshness:
    def test_a_STALE_in_flight_order_refuses(self):
        old = pending(qty=0.01, age=V5.MAX_PENDING_AGE_MINUTES + 0.01)
        out = run(pending_approved=[old])
        assert "in_flight_orders_fresh" in out["failed"]
        # It is NOT the readability check that fires: the ledger was read fine.
        assert "in_flight_ledger_readable" not in out["failed"]

    def test_the_freshness_boundary_is_inclusive(self):
        """Strict-vs-non-strict, probed AT the boundary. Two mutation survivors
        on this seat's D23 were exactly this class."""
        at = pending(qty=0.01, age=V5.MAX_PENDING_AGE_MINUTES)
        assert "in_flight_orders_fresh" not in failed(pending_approved=[at])
        over = pending(qty=0.01, age=V5.MAX_PENDING_AGE_MINUTES + 0.001)
        assert "in_flight_orders_fresh" in failed(pending_approved=[over])

    @pytest.mark.parametrize("age", [None, "", "soon", -1, True, float("nan")])
    def test_an_UNREADABLE_age_is_STALE_and_not_fresh(self, age):
        """Absence is never zero and unknown is never recent. It must not make
        the fold unreadable either — the exposure arithmetic does not need the
        age, so refusing the whole ledger would lose a bound we can compute."""
        row = pending(qty=0.01)
        row["age_minutes"] = age
        out = run(pending_approved=[row])
        assert "in_flight_orders_fresh" in out["failed"]
        assert "in_flight_ledger_readable" not in out["failed"]

    def test_an_unreadable_ledger_cannot_claim_freshness_either(self):
        out = run(pending_approved=None)
        assert "in_flight_orders_fresh" in out["failed"]
        assert "unknown is not fresh" in detail(out, "in_flight_orders_fresh")


class TestTheLedgersAreSeparate:
    """THE DESIGN CONSTRAINT THAT KILLED THE NAIVE FIX (probe p4, part B).

    Check 14 requires book == venue, and the broker cannot hold an unfilled
    order. So folding in-flight quantity into ``book_qty_signed`` — the obvious
    repair — makes every pending order look like a reconciliation break and
    refuses every order in the class. A control that refuses everything is not
    a control, it is an outage with a nice sentence.
    """

    def test_in_flight_orders_do_NOT_break_the_book_venue_comparison(self):
        out = run(pending_approved=[pending(qty=0.01)])
        assert "book_venue_in_sync" not in out["failed"]

    def test_the_book_venue_check_still_catches_a_REAL_drift(self):
        """The positive control for the test above: excluding in-flight must
        not have excluded everything."""
        assert "book_venue_in_sync" in failed(
            book_qty_signed=5.0, venue_qty_signed=0.0,
            gross_exposure_usd=400.0)

    def test_the_exclusion_is_stated_on_the_payload(self):
        """A reader of the record must be able to see WHY the two ledgers are
        allowed to disagree with the exposure arithmetic above them."""
        assert "cannot hold an unfilled order" in detail(
            run(), "book_venue_in_sync")


# ================================================== KILL 2 — SELLS ARE REDUCE-ONLY

class TestReduceOnly:
    """KILL 2, run-adversary-night2 (probe p1_short.py).

    r1 auto-approved a naked short of 14.9% of NAV from a flat book with all 23
    checks green. ``exitrule.py:326`` can only raise a SELL, so the position's
    own pre-committed exit DEEPENS it — check 15 was satisfied by a rule that
    makes the trade worse.
    """

    def test_A_NAKED_SHORT_FROM_A_FLAT_BOOK_IS_REFUSED(self):
        out = run(order("sell"))
        assert out["approve"] is False
        assert "post_fill_position_not_short" in out["failed"]
        d = detail(out, "post_fill_position_not_short")
        assert "opening a short from a flat book" in d
        assert "SETTLED book alone" in d

    def test_a_sell_that_CROSSES_zero_from_a_long_is_refused(self):
        out = run(order("sell", qty=10.0),
                  book_qty_signed=4.0, venue_qty_signed=4.0,
                  strategy_qty_signed=4.0, strategy_exposure_usd=320.0,
                  gross_exposure_usd=320.0)
        assert "post_fill_position_not_short" in out["failed"]
        assert "crossing zero from a long" in detail(
            out, "post_fill_position_not_short")

    def test_a_sell_that_DEEPENS_an_existing_short_is_refused(self):
        """Named separately because the sign is preserved — a rule written as
        "sign(book) must not flip" would let this through, and an un-exitable
        position getting bigger is the worst of the three."""
        out = run(order("sell", qty=1.0),
                  book_qty_signed=-4.0, venue_qty_signed=-4.0,
                  strategy_qty_signed=-4.0, strategy_exposure_usd=320.0,
                  gross_exposure_usd=320.0)
        assert "post_fill_position_not_short" in out["failed"]
        assert "already short" in detail(out, "post_fill_position_not_short")

    def test_a_sell_that_flattens_EXACTLY_to_zero_is_allowed(self):
        """The boundary, and the direction that must NOT be closed: an exit is
        the one thing the fund's machinery can always do."""
        out = run(order("sell", qty=4.0),
                  book_qty_signed=4.0, venue_qty_signed=4.0,
                  strategy_qty_signed=4.0, strategy_exposure_usd=320.0,
                  gross_exposure_usd=320.0)
        assert "post_fill_position_not_short" not in out["failed"], out["failed"]

    def test_a_partial_sell_of_a_long_is_allowed(self):
        out = run(order("sell", qty=1.0),
                  book_qty_signed=4.0, venue_qty_signed=4.0,
                  strategy_qty_signed=4.0, strategy_exposure_usd=320.0,
                  gross_exposure_usd=320.0)
        assert "post_fill_position_not_short" not in out["failed"], out["failed"]

    def test_an_ordinary_LONG_entry_is_allowed(self):
        """The class this envelope exists to admit. If this ever fails, the
        reduce-only rule has eaten the feature."""
        assert "post_fill_position_not_short" not in failed()

    def test_TWO_SELLS_THAT_EACH_REACH_ZERO_CROSS_IT_TOGETHER(self):
        """THE IN-FLIGHT HALF OF KILL 2, and the reason the bound is a corner
        rather than a sum. Each sell alone flattens the book exactly; the pair
        takes it to twice negative, and only a worst-case bound sees it."""
        book = 4.0
        alone = run(order("sell", qty=book),
                    book_qty_signed=book, venue_qty_signed=book,
                    strategy_qty_signed=book, strategy_exposure_usd=320.0,
                    gross_exposure_usd=320.0)
        assert "post_fill_position_not_short" not in alone["failed"]

        out = run(order("sell", qty=book),
                  book_qty_signed=book, venue_qty_signed=book,
                  strategy_qty_signed=book, strategy_exposure_usd=320.0,
                  gross_exposure_usd=320.0,
                  pending_approved=[pending(qty=book, side="sell", oid="s1")])
        assert "post_fill_position_not_short" in out["failed"]
        assert "in-flight SELL fills" in detail(
            out, "post_fill_position_not_short")

    def test_a_pending_BUY_does_not_excuse_a_sell_that_would_go_short(self):
        """MUTANT: use the NET in-flight quantity here. A buy that may never
        fill would then pay for a sell that will, which is the corner this
        bound exists to take."""
        out = run(order("sell", qty=4.0),
                  pending_approved=[pending(qty=4.0, side="buy", oid="b1")])
        assert "post_fill_position_not_short" in out["failed"]

    def test_an_unbounded_in_flight_set_refuses_with_its_OWN_sentence(self):
        """A definite defect must never be reported as a gap, and a gap must
        never be reported as a defect. The settled book here does NOT go short;
        only the unreadable ledger stops the bound."""
        out = run(pending_approved=None)
        assert "post_fill_position_not_short" in out["failed"]
        d = detail(out, "post_fill_position_not_short")
        assert "could not be bounded" in d
        assert "SETTLED book alone" not in d


# ================================================ RESIDUAL 1 — THE EXIT ORDERING

class TestTheExitOrderingIsCompared_AS_TIME:
    """RESIDUAL, run-adversary-night2: r1 compared ISO timestamps as raw
    STRINGS. That is a false ACCEPT and not merely an imprecision."""

    def test_THE_FALSE_ACCEPT_r1_shipped(self):
        """``"2026-08-28T05:00:00+00:00" < "2026-08-28T06:00:00+05:00"`` is
        True as text. As time, 05:00Z is FOUR HOURS AFTER 01:00Z — so r1
        counted an exit written four hours after the signal as
        pre-commitment."""
        set_at = "2026-08-28T05:00:00+00:00"
        raised = "2026-08-28T06:00:00+05:00"      # = 01:00Z
        assert set_at < raised                     # the string comparison
        out = run(signal_raised_at=raised,
                  committed_exit={"set_at": set_at, "live": True},
                  live_sessions=[{"session_id": "s", "strategy_id": SID,
                                  "state": "running",
                                  "started_at": "2026-08-28T00:00:00+00:00"}])
        assert "exit_committed_for_entry" in out["failed"]

    def test_the_TRUE_ordering_across_offsets_still_passes(self):
        """The positive control. Refusing everything with an offset in it would
        satisfy the test above and break the feature."""
        out = run(signal_raised_at="2026-08-28T06:00:00+05:00",   # 01:00Z
                  committed_exit={"set_at": "2026-08-28T00:30:00+00:00",
                                  "live": True},
                  live_sessions=[{"session_id": "s", "strategy_id": SID,
                                  "state": "running",
                                  "started_at": "2026-08-28T00:00:00+00:00"}])
        assert "exit_committed_for_entry" not in out["failed"], out["failed"]

    def test_a_NAIVE_instant_beside_an_AWARE_one_refuses(self):
        """``datetime`` raises ``TypeError`` on the comparison, which lands on
        the refusing direction here — the OPPOSITE of the engine fence's use of
        the same primitive."""
        assert "exit_committed_for_entry" in failed(
            committed_exit={"set_at": "2026-08-28T00:00:00", "live": True})

    @pytest.mark.parametrize("junk", ["", "yesterday", "2026-13-45", None, 7])
    def test_an_unparseable_instant_proves_no_ordering(self, junk):
        assert "exit_committed_for_entry" in failed(
            committed_exit={"set_at": junk, "live": True})

    def test__iso_lt_is_STRICT_and__iso_le_is_not(self):
        """The two are a pair and their boundary behaviour is the whole reason
        there are two. A boolean argument at the call site is how the wrong one
        gets chosen."""
        t = "2026-08-28T05:00:00+00:00"
        assert V5._iso_le(t, t) is True
        assert V5._iso_lt(t, t) is False
        assert V5._iso_lt("2026-08-28T04:59:59+00:00", t) is True
        assert V5._iso_lt(t, "2026-08-28T04:59:59+00:00") is False

    def test_the_session_claim_still_accepts_an_EQUAL_instant(self):
        """``_iso_le``'s caller must not have been switched to the strict one:
        a container that starts and signals in the same instant genuinely
        raised that signal."""
        t = "2026-08-28T09:00:00+00:00"
        assert "signal_from_live_session" not in failed(
            signal_raised_at=t,
            committed_exit={"set_at": "2026-08-28T08:00:00+00:00",
                            "live": True})


# ================================================= RESIDUAL 2 — THE MARK MAGNITUDE

class TestTheMarkIsBoundedBY_MAGNITUDE:
    """RESIDUAL, run-adversary-night2: r1 compared the SIGNED figure, so a mark
    reported at -75.9% of the struck mark satisfied ``<= 30``. That is the GLD
    phantom's shape, in the check written to catch it."""

    def test_a_signed_negative_move_is_refused(self):
        out = run(mark_move_vs_strike_pct=-75.9)
        assert "mark_corroborated" in out["failed"]
        assert "75.9% from the last struck mark" in detail(
            out, "mark_corroborated")

    @pytest.mark.parametrize("sign", [1, -1])
    def test_both_directions_are_bounded_at_the_SAME_magnitude(self, sign):
        at = V5.MAX_MARK_MOVE_VS_STRIKE_PCT
        assert "mark_corroborated" not in failed(
            mark_move_vs_strike_pct=sign * at)
        assert "mark_corroborated" in failed(
            mark_move_vs_strike_pct=sign * (at + 0.01))

    def test_a_small_move_of_EITHER_sign_still_passes(self):
        """The positive control: taking an absolute value must not have turned
        into refusing anything negative."""
        assert "mark_corroborated" not in failed(mark_move_vs_strike_pct=-1.0)
        assert "mark_corroborated" not in failed(mark_move_vs_strike_pct=1.0)


# =============================================== RESIDUAL 3 — THE DECLARED UNITS

class TestTheContextValuesMustBeINSIDE_THEIR_UNIT:
    """RESIDUAL, run-adversary-night2: r1 STATED that ``_fraction`` means 0..1
    and ``_pct`` means 0..100, and enforced neither. Measured on r1: a NAV of
    1e308 made every percentage vacuously tiny and the order approved; so did
    ``max_position_fraction = 1e308`` and ``throttle_multiplier = 1e308``. And
    ``float(True) == 1.0``, so a boolean reached a threshold comparison as a
    full-gross multiplier and a 100%-of-NAV position limit.
    """

    @pytest.mark.parametrize("key,bad", [
        ("nav_usd", 1e308),
        ("nav_usd", 0.0),
        ("nav_usd", -1.0),
        ("max_position_fraction", 1e308),
        ("max_position_fraction", 1.5),
        ("max_position_fraction", -0.1),
        ("mandate_gross_fraction", 1e308),
        ("mandate_gross_fraction", 2.0),
        ("throttle_multiplier", 1e308),
        # ABOVE 1.0 IS THE PERMISSIVE DIRECTION AND IS IMPOSSIBLE:
        # ``throttle.target_gross`` is reduction-only and returns
        # ``1.0 - reduction``. A multiplier above one would be the regime feed
        # authorising MORE gross than the mandate.
        ("throttle_multiplier", 1.01),
        ("strategy_allocation_pct", 1e308),
        ("strategy_allocation_pct", 101.0),
        ("day_auto_notional_usd", -1.0),
        ("order_mark_usd", 0.0),
        ("order_mark_usd", -1.0),
        ("gross_exposure_usd", -1.0),
        ("strategy_exposure_usd", -1.0),
    ])
    def test_a_value_outside_its_declared_unit_refuses(self, key, bad):
        out = run(**{key: bad})
        assert out["approve"] is False
        assert "context_values_in_range" in out["failed"]
        assert key in detail(out, "context_values_in_range")

    @pytest.mark.parametrize("key", [
        "nav_usd", "order_mark_usd", "day_auto_notional_usd",
        "mark_move_vs_strike_pct", "max_position_fraction",
        "strategy_allocation_pct", "mandate_gross_fraction",
        "throttle_multiplier", "book_qty_signed", "strategy_qty_signed",
        "venue_qty_signed", "strategy_exposure_usd", "gross_exposure_usd",
    ])
    @pytest.mark.parametrize("flag", [True, False])
    def test_a_BOOLEAN_is_not_a_number_in_any_numeric_field(self, key, flag):
        """``bool`` subclasses ``int`` and ``float(True) == 1.0``. Every one of
        r1's boolean readings was in the permissive direction, and none of them
        was a number anybody wrote down."""
        out = run(**{key: flag})
        assert "context_values_in_range" in out["failed"]
        assert key in detail(out, "context_values_in_range")

    def test_the_offending_field_is_NAMED_and_not_merely_counted(self):
        """The audit reads the sentence. "The order notional could not be
        computed" does not tell the riskofficer that the gatherer handed a
        boolean where a fraction belongs, and that is the sentence that gets
        the defect fixed."""
        d = detail(run(nav_usd=1e308, throttle_multiplier=True),
                   "context_values_in_range")
        assert "nav_usd=1e+308" in d
        assert "throttle_multiplier=True" in d

    def test_an_out_of_range_value_ALSO_makes_its_own_check_refuse(self):
        """Two refusals for one cause, deliberately. The range check names the
        defect; the dependent check says the number could not be read. An
        envelope with only the first would approve on a vacuous bound the day
        somebody deleted it."""
        out = run(nav_usd=1e308)
        assert "order_notional_within_cap" in out["failed"]
        assert "nav=None" in detail(out, "order_notional_within_cap")

    def test_an_ABSENT_value_is_not_a_MALFORMED_one(self):
        """The two need different sentences: a missing field is a gatherer that
        did not run, a malformed one is a gatherer that is wrong."""
        c = ctx()
        c.pop("nav_usd")
        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=c)
        assert "context_values_in_range" not in out["failed"]
        assert "order_notional_within_cap" in out["failed"]

    @pytest.mark.parametrize("bad", [0, 0.0, -1.0, True, False, None, "x",
                                     float("nan"), float("inf")])
    def test_an_order_QUANTITY_must_be_a_finite_positive_number(self, bad):
        """r1 accepted ``qty=-1`` through ``abs()`` — a sign error silently
        absorbed by the one function that decides the direction of the trade —
        and ``qty=True`` as one share."""
        out = run(order(qty=bad))
        assert out["approve"] is False
        assert "side_is_readable" in out["failed"]

    def test_the_range_check_passes_on_a_clean_context(self):
        """The positive control: a check that fired on everything would satisfy
        every test above."""
        assert "context_values_in_range" not in failed()
        assert "declares" in detail(run(), "context_values_in_range")


class TestTheExposureLedgersMustNotContradictThemselves:
    def test_a_gross_smaller_than_this_symbol_alone_refuses(self):
        """r1 approved a context declaring a strategy short one share at $80
        with a strategy exposure of $0 — every allocation bound then divided
        into a ledger that contradicted itself."""
        out = run(strategy_qty_signed=-1.0, strategy_exposure_usd=0.0,
                  book_qty_signed=-1.0, venue_qty_signed=-1.0,
                  gross_exposure_usd=80.0)
        assert "exposure_ledgers_coherent" in out["failed"]
        assert "strategy gross is $0.00" in detail(
            out, "exposure_ledgers_coherent")

    def test_the_fund_leg_is_checked_too_and_not_only_the_strategy_leg(self):
        out = run(book_qty_signed=10.0, venue_qty_signed=10.0,
                  gross_exposure_usd=0.0, strategy_qty_signed=0.0)
        assert "exposure_ledgers_coherent" in out["failed"]
        assert "fund gross is $0.00" in detail(out, "exposure_ledgers_coherent")

    def test_an_unreadable_exposure_makes_coherence_UNKNOWN_not_fine(self):
        out = run(gross_exposure_usd=None)
        assert "exposure_ledgers_coherent" in out["failed"]
        assert "UNKNOWN rather than fine" in detail(
            out, "exposure_ledgers_coherent")

    def test_a_coherent_pair_passes(self):
        assert "exposure_ledgers_coherent" not in failed(
            book_qty_signed=1.0, venue_qty_signed=1.0, strategy_qty_signed=1.0,
            gross_exposure_usd=80.0, strategy_exposure_usd=80.0)


# ============================================== RESIDUAL 4 — IT MUST NEVER RAISE

class TestItReturnsAVerdictForEveryInput:
    """RESIDUAL, run-adversary-night2: seventeen context values made r1 THROW.
    ``evaluate`` is the deterministic core of an execution path; an exception
    here aborts the tick and leaves every remaining order unevaluated, which is
    a fund-wide outage raised by one malformed field.
    """

    JUNK = [None, "", 0, 0.0, "nan", float("nan"), float("inf"), -1, "true",
            True, False, [], {}, "ALPACA_PAPER", 1e308, "1e400", object()]

    #: THE CLAIM IS "IT COMPLETES", NOT "IT REFUSES", AND THE DIFFERENCE IS
    #: LOAD-BEARING. Three of the values above are legitimate on some fields —
    #: ``[]`` is a readable empty in-flight ledger, ``0`` is a genuinely fresh
    #: signal age — and a test that demanded a refusal for all seventeen would
    #: be asserting that the envelope refuses a valid input. It would also have
    #: passed on an envelope that refuses EVERYTHING, which is the failure a
    #: control dies of quietly. So each case asserts the evaluation FINISHED,
    #: and the refusal is asserted where refusal is the right answer.
    @staticmethod
    def _completed(out):
        rows = [c for c in out["checks"] if c["check"] == "evaluate_completed"]
        assert len(rows) == 1
        return rows[0]["ok"]

    @pytest.mark.parametrize("key", ["strategy", "live_sessions",
                                     "pending_approved", "committed_exit",
                                     "heartbeats"])
    def test_the_five_container_fields_never_raise(self, key):
        """THE EXACT SEVENTEEN. Nine came from ``strategy`` reaching ``.get``
        and eight from ``live_sessions`` reaching a ``for`` or a ``len``."""
        for junk in self.JUNK:
            if key == "heartbeats":
                out = V5.evaluate(order(), halted=False, heartbeats=junk,
                                  signal_age_minutes=0.5, context=ctx())
            else:
                out = run(**{key: junk})
            assert self._completed(out) is True, (key, junk)
            # ``[]`` on the in-flight ledger is a readable empty one and is the
            # ONE value in this table that may legitimately still approve.
            if not (key == "pending_approved" and junk == []):
                assert out["approve"] is False, (key, junk)

    @pytest.mark.parametrize("junk", JUNK)
    def test_the_ORDER_itself_may_be_anything(self, junk):
        out = V5.evaluate(junk, halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=ctx())
        assert self._completed(out) is True
        assert out["approve"] is False

    @pytest.mark.parametrize("junk", JUNK)
    def test_the_CONTEXT_itself_may_be_anything(self, junk):
        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=junk)
        assert self._completed(out) is True
        assert out["approve"] is False

    @pytest.mark.parametrize("junk", JUNK)
    def test_the_SIGNAL_AGE_may_be_anything(self, junk):
        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=junk, context=ctx())
        assert self._completed(out) is True
        # 0 and 0.0 are a genuinely fresh signal and approve. Everything else
        # in the table is unreadable, out of range, or a boolean.
        #
        # ``junk in (0, 0.0)`` WOULD BE WRONG AND WAS: ``False == 0`` is True in
        # Python, so the expected value silently included ``False`` — the exact
        # bool-is-an-int confusion this module refuses, reproduced in the test
        # that checks it. Identity, and a type test, or the expectation is
        # computed by the bug.
        fresh_zero = (not isinstance(junk, bool)
                      and isinstance(junk, (int, float)) and junk == 0)
        assert out["approve"] is fresh_zero, junk

    def test_a_NEGATIVE_signal_age_is_a_signal_from_the_FUTURE(self):
        """FOUND WHILE WRITING THIS TABLE, not by the review. r1's
        ``age <= MAX_SIGNAL_AGE_MINUTES`` accepted -1, so a clock skew or a
        gatherer subtracting the wrong way round would buy an arbitrarily stale
        signal a pass on the one check that exists to stop that."""
        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=-1.0, context=ctx())
        assert "signal_fresh" in out["failed"]
        assert "UNKNOWN" in detail(out, "signal_fresh")
        # ...and zero, the boundary just inside it, is still fresh.
        assert "signal_fresh" not in set(V5.evaluate(
            order(), halted=False, heartbeats=HB, signal_age_minutes=0.0,
            context=ctx())["failed"])

    def test_evaluate_completed_is_on_EVERY_payload_and_true_when_it_did(self):
        out = run()
        names = [c["check"] for c in out["checks"]]
        assert "evaluate_completed" in names
        assert out["approve"] is True

    def test_an_unforeseen_fault_becomes_a_REFUSAL_and_names_itself(self):
        """A blanket ``except`` that swallowed would hide the defect; this one
        REFUSES and puts the exception on the record. Provoked through a
        context whose ``get`` raises, which is the only way to reach the guard
        now that the known shapes are normalised — and the point of the guard
        is the shapes nobody foresaw."""
        class Hostile(dict):
            def get(self, *a, **k):
                raise RuntimeError("the gatherer exploded")

        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=Hostile())
        assert out["approve"] is False
        assert "evaluate_completed" in out["failed"]
        d = detail(out, "evaluate_completed")
        assert "RuntimeError" in d and "the gatherer exploded" in d

    def test_the_partial_check_list_survives_a_fault(self):
        """Whatever was evaluated before the fault is exactly what the
        riskofficer needs to find where it happened. Discarding it would leave
        a payload with one check on it."""
        class HostileLater(dict):
            def __init__(self):
                super().__init__(ctx())
                self.n = 0

            def get(self, *a, **k):
                self.n += 1
                if self.n > 3:
                    raise RuntimeError("boom")
                return dict.get(self, *a, **k)

        out = V5.evaluate(order(), halted=False, heartbeats=HB,
                          signal_age_minutes=0.5, context=HostileLater())
        assert out["approve"] is False
        assert len(out["checks"]) > 1
        assert out["checks"][-1]["check"] == "evaluate_completed"


# ============================================================== THE FOLD, ALONE

class TestTheInFlightFoldItself:
    def test_an_unreadable_ledger_gives_ABSENT_for_every_quantity(self):
        """A caller that forgets to check ``readable`` must still fail closed
        through ``within`` rather than bounding against a partial sum."""
        f = V5.in_flight(None, "HYG", SID)
        assert f["readable"] is False
        for k in ("symbol_buy_qty", "symbol_sell_qty", "strategy_buy_qty",
                  "strategy_sell_qty", "other_gross_usd",
                  "strategy_other_gross_usd", "rows", "fresh"):
            assert f[k] is None, k

    def test_an_empty_ledger_gives_MEASURED_ZEROS(self):
        f = V5.in_flight([], "HYG", SID)
        assert f["readable"] is True
        assert f["rows"] == 0
        assert f["symbol_buy_qty"] == 0.0
        assert f["other_gross_usd"] == 0.0
        assert f["fresh"] is True

    def test_the_split_by_direction_and_by_strategy(self):
        rows = [
            {"order_id": "a", "symbol": "HYG", "side": "buy", "qty": 3.0,
             "mark_usd": 80.0, "age_minutes": 1.0, "strategy_id": SID},
            {"order_id": "b", "symbol": "hyg", "side": "sell", "qty": 1.0,
             "mark_usd": 80.0, "age_minutes": 1.0, "strategy_id": "other"},
            {"order_id": "c", "symbol": "SPY", "side": "buy", "qty": 2.0,
             "mark_usd": 500.0, "age_minutes": 1.0, "strategy_id": SID},
        ]
        f = V5.in_flight(rows, "HYG", SID)
        assert f["symbol_buy_qty"] == 3.0
        assert f["symbol_sell_qty"] == -1.0      # case-folded onto HYG
        assert f["strategy_buy_qty"] == 3.0
        assert f["strategy_sell_qty"] == 0.0     # b belongs to "other"
        assert f["other_gross_usd"] == 1000.0
        assert f["strategy_other_gross_usd"] == 1000.0

    def test_the_symbol_match_is_case_and_whitespace_insensitive(self):
        rows = [{"order_id": "a", "symbol": " hyg ", "side": "buy", "qty": 2.0,
                 "mark_usd": 80.0, "age_minutes": 1.0, "strategy_id": SID}]
        assert V5.in_flight(rows, "HYG", SID)["symbol_buy_qty"] == 2.0
        assert V5.in_flight(rows, "HYG", SID)["other_gross_usd"] == 0.0

    def test_worst_short_takes_the_sells_and_ignores_the_buys(self):
        assert V5.worst_short_position(4.0, -4.0, -1.0) == -1.0
        assert V5.worst_short_position(4.0, 0.0, -4.0) == 0.0
        assert V5.worst_short_position(None, -1.0, 1.0) is None
        assert V5.worst_short_position(1.0, None, 1.0) is None
        assert V5.worst_short_position(1.0, -1.0, None) is None

    def test_worst_abs_takes_the_largest_of_four_corners(self):
        # book 1, +5 pending buy, -3 pending sell, order +1:
        #   corners 2, 7, -1, 4  ->  7
        assert V5.worst_abs_position(1.0, 5.0, -3.0, 1.0) == 7.0
        # a short book: the SELL corner is the large one.
        #   book -1, +1 buy, -5 sell, order -1: corners -2, -1, -7, -6 -> -7
        assert V5.worst_abs_position(-1.0, 1.0, -5.0, -1.0) == -7.0
        assert V5.worst_abs_position(None, 0.0, 0.0, 0.0) is None

    def test_post_fill_exposure_adds_the_other_symbols_pending(self):
        # 500 gross, this symbol worth 100 before and 200 after, 50 elsewhere.
        assert V5.post_fill_exposure(500.0, 100.0, 200.0, 50.0) == 650.0
        assert V5.post_fill_exposure(500.0, 100.0, 200.0, None) is None
        # It defaults to zero so the pure swap is still testable on its own.
        assert V5.post_fill_exposure(500.0, 100.0, 200.0) == 600.0


class TestTheNumberReader:
    @pytest.mark.parametrize("flag", [True, False])
    def test_a_bool_is_never_a_number(self, flag):
        assert V5._number(flag) is None
        # ...while ``_as_float`` — the COPY pinned against v4 — still converts
        # it, which is exactly why the two are separate functions.
        assert V5._as_float(flag) == float(flag)

    def test_the_range_is_inclusive_at_both_ends(self):
        assert V5._number(0.0, lo=0.0, hi=1.0) == 0.0
        assert V5._number(1.0, lo=0.0, hi=1.0) == 1.0
        assert V5._number(-1e-9, lo=0.0, hi=1.0) is None
        assert V5._number(1.0000001, lo=0.0, hi=1.0) is None

    def test_out_of_range_is_ABSENT_rather_than_CLAMPED(self):
        """A clamp would let a corrupt value become a valid one and pass
        silently. Absence makes its checks say the number could not be read."""
        assert V5._number(5.0, hi=1.0) is None

    @pytest.mark.parametrize("v", [None, "", "x", float("nan"), float("inf"),
                                   float("-inf"), [], {}, "1e400"])
    def test_it_inherits_every_absent_case_from_the_copy(self, v):
        assert V5._number(v) is None
        assert V5._as_float(v) is None
