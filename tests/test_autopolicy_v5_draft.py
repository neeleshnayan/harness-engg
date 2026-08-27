"""The v5 DRAFT envelope — and the tests that must fail if it is ever wired.

Written to be attacked. The adversary reads the draft blind; these tests are
what the builder could prove about it without a reviewer, and they are
deliberately weighted toward the two things that decide whether an envelope is
safe: **it must refuse when it cannot measure**, and **it must not be reachable
from anything that executes**.

The isolation tests come FIRST because they are the ones that stop mattering
the day someone imports this module by accident, and a test that only runs
after twelve behavioural ones is a test that gets skipped in a hurry.
"""

import ast
import pathlib

import pytest

from app.fund import autopolicy as V4
from app.fund import autopolicy_v5_draft as V5

REPO = pathlib.Path(__file__).resolve().parents[1]


# ==================================================== IT MUST NOT BE REACHABLE

class TestTheDraftIsUnreachable:
    def test_nothing_in_the_repo_imports_the_draft(self):
        """THE ONE THAT MATTERS MOST. A draft envelope that something imports
        is not a draft — it is an unversioned policy that nobody reviewed,
        which is the exact shape of the quiet loosening the constitution names
        as the one forbidden move.

        Grepped over the SOURCE rather than over ``sys.modules``, because an
        import that only happens on one code path would be invisible to the
        second and perfectly visible to the first.
        """
        offenders = []
        for path in list((REPO / "app").rglob("*.py")) + \
                list((REPO / "scripts").rglob("*.py")):
            if path.name == "autopolicy_v5_draft.py":
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if "autopolicy_v5_draft" in text:
                offenders.append(str(path.relative_to(REPO)))
        assert offenders == [], (
            f"the v5 draft is referenced from production code: {offenders}. "
            f"It reaches the approval path only through the adversary blind, "
            f"the riskofficer and the CEO's click on the version.")

    def test_the_draft_imports_nothing_from_the_fund(self):
        """The other direction, and it is not symmetric. An import FROM the
        fund would make the draft depend on modules whose behaviour can change
        under it — and would give a reviewer reading the draft a second file to
        hold in their head. It reads nothing; the caller hands it everything.
        """
        src = (REPO / "app" / "fund" / "autopolicy_v5_draft.py").read_text(
            encoding="utf-8")
        modules = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ImportFrom):
                modules.add(node.module or "")
            elif isinstance(node, ast.Import):
                modules |= {a.name for a in node.names}
        assert not any(m.startswith("app.") for m in modules), modules

    def test_the_live_policy_is_untouched_at_v4(self):
        """A positive control on the boundary this whole file guards. If a
        later diff bumps the live version, this fails and whoever did it has to
        say so out loud rather than discovering it in an audit."""
        assert V4.AUTOPOLICY_VERSION == "v4"

    def test_every_evaluation_says_DRAFT_on_its_own_face(self):
        """If it IS wired by accident, the riskofficer finds it in one query
        over the approval payloads rather than by reading code."""
        out = V5.evaluate({}, halted=False, heartbeats={},
                          signal_age_minutes=None)
        assert out["draft"] is True
        assert out["wired"] is False
        assert "draft" in out["policy_version"]
        assert out["policy_version"] != V4.AUTOPOLICY_VERSION


# ============================================ the duplicated helpers, pinned

class TestTheDuplicatedHelpersStillAgree:
    """The draft copies ``_as_float`` and ``order_delta`` to stay unreachable.
    A copy is a second idea of one thing waiting to happen, so it is compared
    by BEHAVIOUR over a table rather than by reading both — an assertion that
    the source text matches would pass on two functions that were both wrong.
    """

    VALUES = [None, "", "x", 0, 0.0, -0.0, 1, -1, 2.5, "3.5", float("nan"),
              float("inf"), float("-inf"), True, [], {}, "1e400"]

    @pytest.mark.parametrize("v", VALUES)
    def test_as_float_agrees(self, v):
        a, b = V4._as_float(v), V5._as_float(v)
        assert (a is None) == (b is None)
        if a is not None:
            assert a == b

    @pytest.mark.parametrize("side", ["buy", "sell", "BUY", "short", "", None])
    @pytest.mark.parametrize("qty", [None, 0, 1.5, -1.5, "2", "x"])
    def test_order_delta_agrees(self, side, qty):
        o = {"side": side, "qty": qty}
        assert V4.order_delta(o) == V5.order_delta(o)

    def test_the_two_marks_bounds_are_the_same_number(self):
        """Two definitions of "the mark is sane" is the second-opinion defect
        ``marksanity`` was written to name."""
        assert V5.MAX_MARK_MOVE_VS_STRIKE_PCT == V4.MAX_MARK_MOVE_VS_STRIKE_PCT

    def test_the_two_epsilons_and_drift_tolerances_match(self):
        assert V5.POSITION_EPS == V4.POSITION_EPS
        assert V5.MAX_POSITION_DRIFT_QTY == V4.MAX_POSITION_DRIFT_QTY


# ================================================================ the helpers

class TestPostFillArithmetic:
    def test_a_buy_adds_and_a_sell_subtracts(self):
        assert V5.post_fill_position(10.0, 5.0) == 15.0
        assert V5.post_fill_position(10.0, -5.0) == 5.0

    @pytest.mark.parametrize("pre,delta", [(None, 1.0), (1.0, None),
                                           (None, None)])
    def test_an_absent_term_makes_the_result_absent(self, pre, delta):
        assert V5.post_fill_position(pre, delta) is None

    def test_gross_swaps_the_symbol_rather_than_adding_the_notional(self):
        """MUTANT: ``total + notional``. Correct only when the order increases a
        long. A sell that halves a $100 position in a $500 book takes gross to
        $450 — ``+ notional`` would report $600, on the wrong side of every
        ceiling."""
        assert V5.post_fill_exposure(500.0, 100.0, 50.0) == 450.0

    def test_gross_uses_absolute_values_so_a_short_still_consumes_it(self):
        """MUTANT: drop the ``abs``. A $100 short would then read as -$100 and
        a book of one long and one equal short would report as flat, which is
        the opposite of what gross means."""
        assert V5.post_fill_exposure(500.0, 0.0, -100.0) == 600.0
        assert V5.post_fill_exposure(500.0, -100.0, 0.0) == 400.0

    @pytest.mark.parametrize("args", [(None, 1.0, 1.0), (1.0, None, 1.0),
                                      (1.0, 1.0, None)])
    def test_gross_is_absent_when_any_term_is(self, args):
        assert V5.post_fill_exposure(*args) is None

    def test_usd_of_an_absent_quantity_is_absent_not_zero(self):
        assert V5._usd(None, 10.0) is None
        assert V5._usd(2.0, None) is None
        assert V5._usd(0.0, 10.0) == 0.0     # a genuine zero still reads zero


class TestPctOfNav:
    def test_the_ordinary_case(self):
        assert V5._pct_of(50.0, 200.0) == 25.0

    def test_a_zero_nav_is_ABSENT_and_not_zero_or_infinity(self):
        """MUTANT: return 0.0. A fund with no struck NAV would then pass every
        percentage cap it has, which is every cap in this envelope."""
        assert V5._pct_of(50.0, 0.0) is None
        assert V5._pct_of(50.0, None) is None
        assert V5._pct_of(None, 200.0) is None


class TestWithinIsThreeValued:
    def test_inside_outside_and_unreadable_are_three_answers(self):
        assert V5.within(5.0, 10.0) is True
        assert V5.within(50.0, 10.0) is False
        assert V5.within(None, 10.0) is None
        assert V5.within(5.0, None) is None

    def test_the_boundary_is_inclusive(self):
        """Strict-vs-non-strict, probed AT the boundary rather than near it."""
        assert V5.within(10.0, 10.0) is True
        assert V5.within(10.0 + 1e-12, 10.0) is True     # inside the epsilon
        assert V5.within(10.001, 10.0) is False

    def test_it_bounds_the_MAGNITUDE_so_a_short_cannot_slip_under(self):
        """MUTANT: drop the ``abs``. A -50% concentration would then be
        'within' a 20% ceiling, and every one of these ceilings is on an
        exposure that can be negative."""
        assert V5.within(-50.0, 10.0) is False


# ============================================================ the full envelope

def _ok_ctx(**over):
    """A context in which EVERY check passes. Each test breaks exactly ONE
    field, so a failure names the check it belongs to rather than a fixture."""
    ctx = {
        "engine_entries_enabled": True,
        "execution_venue_kind": "alpaca_paper",
        "execution_venue_real_money": False,
        "strategy": {"strategy_id": "s1", "state": "deployed",
                     "archived": False, "assets": ["HYG"]},
        "strategy_allocation_pct": 25.0,
        "live_sessions": [{"session_id": "abc", "state": "running",
                           "strategy_id": "s1",
                           "started_at": "2026-08-27T09:00:00+00:00"}],
        "signal_raised_at": "2026-08-27T10:00:00+00:00",
        "nav_usd": 2000.0,
        "order_mark_usd": 10.0,
        "mark_move_vs_strike_pct": 0.4,
        # ``notional_usd`` IS DELIBERATELY ABSENT AND MUST STAY ABSENT. r2
        # computes the order notional as ``|qty| x order_mark_usd`` rather than
        # accepting a third number that can disagree with the two that
        # determine it. A fixture still carrying the key would let a reader
        # believe the envelope reads it — and would hide the day the envelope
        # stopped.  qty 10 x mark 10 = $100.
        "day_auto_notional_usd": 0.0,
        # A MEASURED ZERO, NOT AN ABSENCE. ``[]`` says the in-flight ledger was
        # read and nothing is in flight; ``None`` says it could not be read and
        # refuses. The happy path has to state which one it is, because those
        # are the two facts the kill was about.
        "pending_approved": [],
        "book_qty_signed": 0.0,
        "strategy_qty_signed": 0.0,
        "venue_qty_signed": 0.0,
        "venue_readable": True,
        "strategy_exposure_usd": 0.0,
        "gross_exposure_usd": 500.0,
        "mandate_gross_fraction": 0.90,
        "throttle_multiplier": 1.0,
        "throttle_measurable": True,
        "max_position_fraction": 0.20,
        "committed_exit": {"set_at": "2026-08-26T00:00:00+00:00", "live": True},
    }
    ctx.update(over)
    return ctx


def _beats(**over):
    rows = {j: {"ok": True, "age_seconds": 10.0}
            for j in V5.REQUIRED_HEARTBEATS}
    rows.update(over)
    return rows


ORDER = {"order_id": "o1", "symbol": "HYG", "side": "buy", "qty": 10.0,
         "strategy_id": "s1", "venue": "paper"}


def _run(order=None, ctx=None, halted=False, beats=None, age=1.0):
    return V5.evaluate(order or ORDER, halted=halted,
                       heartbeats=_beats() if beats is None else beats,
                       signal_age_minutes=age, context=ctx or _ok_ctx())


def _failed(**over):
    """The set of checks that refused, for a context with one field broken."""
    return set(_run(ctx=_ok_ctx(**over))["failed"])


class TestTheHappyPath:
    def test_a_clean_engine_entry_passes_every_check(self):
        """THE POSITIVE CONTROL. Without it every refusal test below is
        vacuous: an envelope that refuses everything would pass all of them."""
        out = _run()
        assert out["approve"] is True, out["failed"]
        assert out["failed"] == []
        assert out["class"] == "engine_entry"

    def test_the_check_list_is_complete_and_not_short_circuited(self):
        """v4's first audit was possible from the log alone BECAUSE every check
        is evaluated and recorded even after one has failed. A policy that
        stops at the first refusal tells the riskofficer nothing about the
        rest."""
        out = _run(ctx=_ok_ctx(engine_entries_enabled=False, nav_usd=None))
        names = [c["check"] for c in out["checks"]]
        assert names[0] == "engine_entries_armed"
        assert len(set(names)) == len(names), "a check name is duplicated"
        assert len(names) >= 18
        assert "risk_monitor_fresh" in names

    def test_every_recorded_ok_is_a_strict_bool(self):
        """The payload must not carry a third value the audit tooling has to
        learn. Coerced in exactly one place."""
        for c in _run(ctx=_ok_ctx(nav_usd=None))["checks"]:
            assert c["ok"] in (True, False)
            assert isinstance(c["ok"], bool)


class TestTheKillSwitch:
    @pytest.mark.parametrize("flag", [False, None, "true", 1, 0])
    def test_anything_but_True_reverts_the_book_to_manual(self, flag):
        """MUTANT: ``if not flag`` instead of ``is True``. The string "false"
        and the integer 1 are both truthy, and an env var read that returned
        either would arm an envelope nobody armed."""
        out = _run(ctx=_ok_ctx(engine_entries_enabled=flag))
        assert out["approve"] is False
        assert "engine_entries_armed" in out["failed"]

    def test_it_is_read_on_every_order_and_not_at_import(self):
        """A control that is read once at start-up reverts the book at the next
        DEPLOY, not at the next tick — which is the difference between a kill
        switch and a configuration option."""
        armed = _run(ctx=_ok_ctx(engine_entries_enabled=True))
        off = _run(ctx=_ok_ctx(engine_entries_enabled=False))
        assert armed["approve"] is True and off["approve"] is False


class TestTheVenue:
    def test_only_the_alpaca_PAPER_kind(self):
        for bad in ("simulated", "paper", "alpaca", None, "", "ALPACA_LIVE"):
            assert "venue_kind_is_permitted" in _failed(
                execution_venue_kind=bad), bad

    def test_the_REAL_MONEY_venue_is_refused_by_BOTH_checks(self):
        """THE ONE THAT MATTERS, AND IT WAS MEASURED ON THE LIVE SPINE
        (2026-08-27, GET /fund/mode). ``alpaca-paper`` and ``alpaca-prod``
        BOTH carry ``permitted_connectors: ["alpaca"]``, so an envelope written
        against the connector name — which is what a first draft of this used —
        passes with real money behind it. The KIND separates them and the
        ``real_money`` flag separates them again."""
        out = _run(ctx=_ok_ctx(execution_venue_kind="alpaca_live",
                               execution_venue_real_money=True))
        assert "venue_kind_is_permitted" in out["failed"]
        assert "venue_is_not_real_money" in out["failed"]

    def test_the_two_venue_checks_are_INDEPENDENT(self):
        """Two checks for one condition is only worth its cost if a gatherer
        can get one right and the other wrong. Each is asserted failing while
        the other passes."""
        only_kind_bad = _failed(execution_venue_kind="alpaca_live")
        assert "venue_kind_is_permitted" in only_kind_bad
        assert "venue_is_not_real_money" not in only_kind_bad
        only_money_bad = _failed(execution_venue_real_money=True)
        assert "venue_is_not_real_money" in only_money_bad
        assert "venue_kind_is_permitted" not in only_money_bad

    @pytest.mark.parametrize("flag", [True, None, "false", 0, 1])
    def test_anything_but_an_explicit_False_is_not_paper(self, flag):
        """MUTANT: ``not real_money``. The string "false" is truthy and 0 is
        falsy — an unreadable flag must refuse, and a zero must not pass by
        accident of Python."""
        failed = _failed(execution_venue_real_money=flag)
        assert ("venue_is_not_real_money" in failed) is (flag is not False)

    def test_the_venue_kind_values_are_the_REAL_enum_s_values(self):
        """PIN THE PREMISE. The constant is a ``mode.VenueKind`` value and the
        table in its comment is copied from the live spine; if the enum is ever
        re-spelled, the comment and the check would go stale together and
        nothing else in this file would notice."""
        from app.fund.mode import VenueKind
        assert V5.PERMITTED_VENUE_KIND == VenueKind.ALPACA_PAPER.value
        assert VenueKind.ALPACA_LIVE.value != V5.PERMITTED_VENUE_KIND

    def test_the_two_alpaca_modes_really_do_share_a_connector(self):
        """The measured fact the whole check rests on, asserted against
        ``mode.MODES`` rather than trusted from a comment. If this ever stops
        being true, the reason written into the constant has gone stale."""
        from app.fund.mode import FundMode, MODES
        paper = MODES[FundMode.ALPACA_PAPER]
        prod = MODES[FundMode.ALPACA_PROD]
        assert paper.permitted_connectors == prod.permitted_connectors == ("alpaca",)
        # The two fields that DO separate them, both asserted, because the
        # draft checks both and one of them alone would be a single point.
        assert paper.venue_kind != prod.venue_kind
        assert paper.real_money is False and prod.real_money is True

    def test_the_ORDER_s_own_venue_field_is_never_read(self):
        """v4's measured lesson: ``exitrule.py`` hardcodes ``venue="paper"`` on
        every exit it raises whatever connector will execute it, so a check
        against the order's field would have passed the exact orders that went
        to Alpaca. ORDER carries ``venue: "paper"`` and must still pass.

        THE SOURCE CHECK IS AN AST WALK AND NOT A SUBSTRING SEARCH, and the
        first version of it was the substring — which failed against the
        module's own COMMENT explaining why it must not read that field. A
        negative assertion over prose is satisfied, or broken, by prose. Only
        the parse tree knows the difference between a warning and a read.
        """
        assert _run()["approve"] is True
        assert ORDER["venue"] == "paper"
        tree = ast.parse(pathlib.Path(V5.__file__).read_text(encoding="utf-8"))
        reads = []
        for node in ast.walk(tree):
            # order["venue"]
            if (isinstance(node, ast.Subscript)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "order"
                    and isinstance(node.slice, ast.Constant)
                    and node.slice.value == "venue"):
                reads.append(ast.unparse(node))
            # order.get("venue")
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "get"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "order"
                    and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and node.args[0].value == "venue"):
                reads.append(ast.unparse(node))
        assert reads == [], reads


class TestTheStrategy:
    @pytest.mark.parametrize("strat", [
        {"strategy_id": "s1", "state": "backtested", "archived": False,
         "assets": ["HYG"]},
        {"strategy_id": "s1", "state": "paused", "archived": False,
         "assets": ["HYG"]},
        {"strategy_id": "s1", "state": "deployed", "archived": True,
         "assets": ["HYG"]},
        {},
        None,
    ])
    def test_only_a_deployed_unarchived_strategy_qualifies(self, strat):
        assert "strategy_deployed" in _failed(strategy=strat)

    def test_an_archived_flag_that_is_absent_is_not_False(self):
        """MUTANT: ``not archived``. A registry row that lost the field would
        then read as unarchived, which is a claim nobody made."""
        assert "strategy_deployed" in _failed(
            strategy={"strategy_id": "s1", "state": "deployed",
                      "assets": ["HYG"]})

    def test_an_EMPTY_asset_scope_refuses_rather_than_permitting_everything(self):
        """MEASURED, NOT HYPOTHETICAL. On 2026-08-27 the live registry held GLD
        with ``assets: []`` beside HYG with ``assets: ["HYG"]``. Reading the
        empty list as 'no restriction' would give the LEAST specified strategy
        the WIDEST mandate."""
        for empty in ([], None, "", {}):
            out = _run(ctx=_ok_ctx(strategy={"strategy_id": "s1",
                                             "state": "deployed",
                                             "archived": False,
                                             "assets": empty}))
            assert "symbol_in_scoped_assets" in out["failed"], empty
            detail = [c for c in out["checks"]
                      if c["check"] == "symbol_in_scoped_assets"][0]["detail"]
            assert "not an unlimited one" in detail

    def test_a_symbol_outside_the_scope_refuses(self):
        assert "symbol_in_scoped_assets" in _failed(
            strategy={"strategy_id": "s1", "state": "deployed",
                      "archived": False, "assets": ["TLT"]})

    def test_the_scope_match_is_case_and_whitespace_insensitive(self):
        """The registry upper-cases on ``set_assets``; a fold reads what was
        written THEN. ``"  hyg "`` is the same symbol and must not refuse."""
        assert _run(ctx=_ok_ctx(
            strategy={"strategy_id": "s1", "state": "deployed",
                      "archived": False, "assets": ["  hyg "]}))["approve"]


class TestProvenance:
    def test_a_signal_with_no_live_session_behind_it_refuses(self):
        assert "signal_from_live_session" in _failed(live_sessions=[])

    def test_an_UNREADABLE_session_registry_refuses(self):
        """MUTANT: treat ``None`` as ``[]`` — same refusal here, but the DETAIL
        differs and the audit reads the detail. Both are asserted so the two
        cannot silently become one."""
        out = _run(ctx=_ok_ctx(live_sessions=None))
        assert "signal_from_live_session" in out["failed"]
        detail = [c for c in out["checks"]
                  if c["check"] == "signal_from_live_session"][0]["detail"]
        assert "could not be read" in detail

    def test_a_session_for_ANOTHER_strategy_does_not_claim_it(self):
        assert "signal_from_live_session" in _failed(
            live_sessions=[{"session_id": "x", "state": "running",
                            "strategy_id": "other",
                            "started_at": "2026-08-27T09:00:00+00:00"}])

    def test_a_session_naming_NO_strategy_does_not_claim_it(self):
        """STRICTER THAN THE ENGINE FENCE ON PURPOSE, and the asymmetry is the
        point: ``engineledger._claiming_session`` lets an unidentified session
        claim EVERYTHING, because a false claim there costs a dismissed
        divergence. Here a false claim EXECUTES AN ORDER."""
        assert "signal_from_live_session" in _failed(
            live_sessions=[{"session_id": "x", "state": "running",
                            "strategy_id": "",
                            "started_at": "2026-08-27T09:00:00+00:00"}])

    @pytest.mark.parametrize("state", ["stopped", "ended", "failed",
                                       "vanished", "", None])
    def test_a_dead_session_does_not_claim_it(self, state):
        assert "signal_from_live_session" in _failed(
            live_sessions=[{"session_id": "x", "state": state,
                            "strategy_id": "s1",
                            "started_at": "2026-08-27T09:00:00+00:00"}])

    def test_a_signal_raised_BEFORE_the_session_started_does_not_claim_it(self):
        """A LEAN container starts FLAT, so a signal predating the session
        moved a book that no longer exists."""
        assert "signal_from_live_session" in _failed(
            signal_raised_at="2026-08-27T08:59:59+00:00")

    def test_a_signal_raised_AT_the_session_start_DOES_claim_it(self):
        """The boundary, probed rather than assumed: ``<=``, not ``<``. A
        session that raises on its first bar is the normal case."""
        assert _run(ctx=_ok_ctx(
            signal_raised_at="2026-08-27T09:00:00+00:00"))["approve"] is True

    @pytest.mark.parametrize("bad", ["", "   ", "not-a-time", None])
    def test_an_unreadable_timestamp_on_either_side_refuses(self, bad):
        """``datetime.fromisoformat`` raises TypeError on mixed naive/aware and
        ValueError on junk; both land on the REFUSING side here — the opposite
        of the engine fence's use of the same primitive, where False keeps a
        signal LIVE."""
        assert "signal_from_live_session" in _failed(signal_raised_at=bad)
        assert "signal_from_live_session" in _failed(
            live_sessions=[{"session_id": "x", "state": "running",
                            "strategy_id": "s1", "started_at": bad}])

    def test_a_naive_timestamp_beside_an_aware_one_refuses(self):
        assert "signal_from_live_session" in _failed(
            signal_raised_at="2026-08-27T10:00:00")


class TestFreshness:
    def test_an_unknown_age_is_not_fresh(self):
        assert "signal_fresh" in set(_run(age=None)["failed"])

    def test_the_boundary_is_inclusive(self):
        assert _run(age=V5.MAX_SIGNAL_AGE_MINUTES)["approve"] is True
        assert "signal_fresh" in set(
            _run(age=V5.MAX_SIGNAL_AGE_MINUTES + 0.1)["failed"])

    def test_it_is_tighter_than_v4_s_exit_ceiling(self):
        """Stated as a test because the REASON is asymmetric and easy to
        reverse: a refused entry comes back on the next bar, and v4's own
        comment records that a refused EXIT does not come back at all."""
        assert V5.MAX_SIGNAL_AGE_MINUTES < V4.MAX_AGE_MINUTES


class TestTheCaps:
    def test_an_oversized_order_refuses(self):
        # DRIVEN THROUGH THE MARK, because r2 computes the notional from the
        # quantity and the mark rather than accepting it. 10 units at $40 is
        # $400 = 20% of a $2,000 NAV against a 15% ceiling.
        assert "order_notional_within_cap" in _failed(order_mark_usd=40.0)

    def test_the_order_cap_boundary_is_inclusive(self):
        at = 2000.0 * V5.MAX_ENGINE_ORDER_NOTIONAL_PCT / 100.0
        assert "order_notional_within_cap" not in _failed(
            order_mark_usd=at / 10.0)
        assert "order_notional_within_cap" in _failed(
            order_mark_usd=at * 1.01 / 10.0)

    def test_the_notional_is_COMPUTED_and_a_supplied_one_is_ignored(self):
        """r1 READ ``notional_usd`` from the context beside the quantity and
        the mark that determine it, and approved an order declaring a notional
        of ZERO for ten units at $10. Two ideas of one number, in a module
        whose own header warns against exactly that.

        Both halves are asserted: a supplied figure cannot make an oversized
        order look small, and it cannot make a small one look oversized. A test
        that only checked the first would pass on a module that had started
        reading the key again in the other direction.
        """
        assert "order_notional_within_cap" in _failed(
            order_mark_usd=40.0, notional_usd=0.0)
        assert "order_notional_within_cap" not in _failed(
            notional_usd=1e9)
        out = _run(ctx=_ok_ctx(notional_usd=0.0))
        detail = [c for c in out["checks"]
                  if c["check"] == "order_notional_within_cap"][0]["detail"]
        assert "5.00%" in detail, detail  # 10 x $10 / $2,000, not the zero

    def test_the_order_cap_is_never_wider_than_the_pre_trade_gate_s(self):
        """An auto-approved order a HUMAN could not have submitted through the
        ordinary gate would be a second, looser door into the same book."""
        from app.fund.risk import RiskLimits
        assert (V5.MAX_ENGINE_ORDER_NOTIONAL_PCT
                <= RiskLimits().max_order_notional_pct * 100.0)

    def test_the_DAY_is_what_bounds_the_damage_not_the_order(self):
        """THE FAILURE THIS STOPS IS NOT A LARGE ORDER; IT IS A HUNDRED SMALL
        ONES. Each of these orders is well inside the per-order cap and the
        day is not."""
        assert "order_notional_within_cap" not in _failed(
            notional_usd=100.0, day_auto_notional_usd=595.0)
        assert "daily_cumulative_within_cap" in _failed(
            notional_usd=100.0, day_auto_notional_usd=595.0)

    def test_the_day_cap_counts_THIS_order_too(self):
        """MUTANT: compare only what has already been approved. The order in
        front of you is the one that breaches the day."""
        just_under = 2000.0 * V5.MAX_ENGINE_DAILY_NOTIONAL_PCT / 100.0 - 50.0
        assert "daily_cumulative_within_cap" in _failed(
            notional_usd=100.0, day_auto_notional_usd=just_under)

    def test_an_UNREADABLE_day_is_not_an_empty_day(self):
        """The absence-is-zero error, landing on the one number that bounds
        what a bad day costs."""
        out = _run(ctx=_ok_ctx(day_auto_notional_usd=None))
        assert "daily_cumulative_within_cap" in out["failed"]
        detail = [c for c in out["checks"]
                  if c["check"] == "daily_cumulative_within_cap"][0]["detail"]
        assert "not an empty day" in detail

    def test_an_unreadable_NAV_refuses_every_percentage_cap(self):
        """Every cap in this envelope is a percent of NAV. MUTANT: let
        ``_pct_of`` return 0.0 on a missing NAV and all four pass at once."""
        failed = _failed(nav_usd=None)
        for c in ("order_notional_within_cap", "daily_cumulative_within_cap",
                  "post_fill_name_within_concentration",
                  "post_fill_strategy_within_allocation",
                  "post_fill_gross_within_throttle"):
            assert c in failed, c


class TestPostFillBounds:
    def test_concentration_is_measured_AFTER_the_fill(self):
        """MUTANT: check the position BEFORE. The book holds nothing here, so a
        before-check passes every order however large."""
        assert "post_fill_name_within_concentration" in _failed(
            book_qty_signed=0.0, order_mark_usd=100.0)   # 10 x 100 = 50% of NAV

    def test_a_position_that_stays_inside_the_limit_passes(self):
        """The venue must be moved WITH the book. The first version of this
        moved only ``book_qty_signed`` and refused on ``book_venue_in_sync``
        instead — a test that would have passed for the wrong reason if the
        concentration check had been broken."""
        out = _run(ctx=_ok_ctx(book_qty_signed=20.0, venue_qty_signed=20.0))
        assert out["approve"] is True, out["failed"]

    def test_the_concentration_limit_is_read_as_a_FRACTION(self):
        """UNITS. ``RiskLimits.max_position_pct`` is 0.20 meaning 20%. Reading
        it as 20 (percent) would multiply the ceiling by 100 — the permissive
        direction, silently."""
        assert "post_fill_name_within_concentration" in _failed(
            book_qty_signed=39.0)      # (39+10) x 10 = 24.5% > 20%
        assert "post_fill_name_within_concentration" not in _failed(
            book_qty_signed=29.0)      # 19.5% < 20%

    def test_the_strategy_allocation_is_read_as_a_PERCENT(self):
        """The other unit, from the other source. ``allocation_pct`` is 25
        meaning 25%; reading it as a fraction would divide the ceiling by 100
        and refuse everything — over-tight, and still wrong."""
        assert _run(ctx=_ok_ctx(strategy_allocation_pct=25.0))["approve"] is True
        assert "post_fill_strategy_within_allocation" in _failed(
            strategy_allocation_pct=0.25)

    def test_gross_is_bounded_by_the_mandate_TIMES_the_throttle(self):
        assert "post_fill_gross_within_throttle" in _failed(
            throttle_multiplier=0.30)

    def test_an_UNMEASURABLE_regime_refuses_rather_than_permitting_full_gross(self):
        """THE TRAP, AND IT POINTS THE PERMISSIVE WAY. ``throttle.target_gross``
        returns ``gross_multiplier: 1.0`` when NEITHER signal is measurable —
        correct for a module whose doctrine is 'reduction only', and exactly
        wrong to read here. MUTANT: read the multiplier without checking
        ``measurable`` and an unreadable regime feed authorises full gross."""
        out = _run(ctx=_ok_ctx(throttle_measurable=False,
                               throttle_multiplier=1.0))
        assert "post_fill_gross_within_throttle" in out["failed"]
        detail = [c for c in out["checks"]
                  if c["check"] == "post_fill_gross_within_throttle"][0]["detail"]
        assert "absence as permission" in detail

    def test_the_throttle_module_really_does_return_1_0_when_unmeasurable(self):
        """PIN THE PREMISE, not the belief about it. The refusal above is only
        worth having if this is true of the real module — and if it ever stops
        being true, the reason written into the draft has gone stale."""
        from app.fund import throttle
        out = throttle.target_gross({})
        assert out["measurable"] is False
        assert out["gross_multiplier"] == 1.0

    @pytest.mark.parametrize("field", ["gross_exposure_usd", "order_mark_usd",
                                       "mandate_gross_fraction"])
    def test_an_absent_exposure_term_refuses(self, field):
        assert "post_fill_gross_within_throttle" in _failed(**{field: None})


class TestTheWayOut:
    def test_an_entry_with_no_committed_exit_refuses(self):
        """THE TRADE THAT KILLS A FUND. v4 never had to consider it because v4
        only ever closed."""
        for missing in (None, {}, "yes", []):
            assert "exit_committed_for_entry" in _failed(committed_exit=missing)

    def test_an_exit_written_AFTER_the_order_is_not_pre_commitment(self):
        """It is regret with a timestamp. Same argument as v4's
        ``rule_predates_position``, moved to the moment that matters for an
        entry."""
        assert "exit_committed_for_entry" in _failed(
            committed_exit={"set_at": "2026-08-27T10:00:01+00:00",
                            "live": True})

    def test_a_dead_exit_rule_does_not_count_as_cover(self):
        for live in (False, None, "true"):
            assert "exit_committed_for_entry" in _failed(
                committed_exit={"set_at": "2026-08-26T00:00:00+00:00",
                                "live": live})

    def test_an_unreadable_set_at_refuses(self):
        assert "exit_committed_for_entry" in _failed(
            committed_exit={"set_at": "", "live": True})


class TestTheLedgers:
    def test_an_unreadable_venue_refuses(self):
        assert "book_venue_in_sync" in _failed(venue_readable=False)
        assert "book_venue_in_sync" in _failed(venue_readable=None)
        assert "book_venue_in_sync" in _failed(venue_qty_signed=None)

    def test_a_book_the_venue_does_not_confirm_refuses(self):
        """Every bound above is computed from the position BEFORE the fill, so
        an unreconciled book makes all of them arithmetic on a number nobody
        verified."""
        assert "book_venue_in_sync" in _failed(book_qty_signed=5.0,
                                               venue_qty_signed=0.0)

    def test_drift_inside_the_reconciler_s_own_tolerance_passes(self):
        assert _run(ctx=_ok_ctx(
            book_qty_signed=V4.MAX_POSITION_DRIFT_QTY / 2,
            venue_qty_signed=0.0))["approve"] is True


class TestTheControls:
    def test_a_halt_refuses(self):
        assert _run(halted=True)["approve"] is False
        assert "not_halted" in set(_run(halted=True)["failed"])

    @pytest.mark.parametrize("job", V5.REQUIRED_HEARTBEATS)
    def test_every_required_control_must_be_provably_alive(self, job):
        out = _run(beats=_beats(**{job: {"ok": False, "age_seconds": 10.0}}))
        assert f"liveness_{job}" in out["failed"]

    @pytest.mark.parametrize("job", V5.REQUIRED_HEARTBEATS)
    def test_an_UNOBSERVED_control_is_not_a_healthy_one(self, job):
        """``heartbeat.status`` returns ``ok: None`` for a job that has never
        run in this process — neither broken nor fine, and the only safe
        reading of neither is no."""
        out = _run(beats=_beats(**{job: {"ok": None, "age_seconds": None}}))
        assert f"liveness_{job}" in out["failed"]

    def test_missing_heartbeats_entirely_refuse(self):
        out = _run(beats={})
        for job in V5.REQUIRED_HEARTBEATS:
            assert f"liveness_{job}" in out["failed"]

    def test_the_risk_monitor_carries_its_OWN_freshness_requirement(self):
        """Named separately from ``liveness_risk_monitor`` because that flag is
        computed against a budget declared elsewhere, and an envelope that
        self-executes should state its own number rather than inherit whatever
        that budget becomes next year."""
        out = _run(beats=_beats(risk_monitor={
            "ok": True, "age_seconds": V5.MAX_RISK_MONITOR_AGE_SECONDS + 1}))
        assert "liveness_risk_monitor" not in out["failed"]
        assert "risk_monitor_fresh" in out["failed"]

    def test_an_unreadable_heartbeat_age_is_not_recent(self):
        out = _run(beats=_beats(risk_monitor={"ok": True,
                                              "age_seconds": "unknown"}))
        assert "risk_monitor_fresh" in out["failed"]

    def test_nav_strike_is_a_real_declared_job_with_a_stated_budget(self):
        """PIN THE PREMISE. The draft's comment cites 5400s from
        heartbeat.py; a comment claiming a number is a comment that goes stale.
        """
        from app.fund import heartbeat
        assert heartbeat.BUDGETS_SECONDS["nav_strike"] == 5400.0
        for job in V5.REQUIRED_HEARTBEATS:
            assert job in heartbeat.BUDGETS_SECONDS, job


class TestTheEmptyInput:
    def test_an_empty_everything_approves_nothing_and_raises_nothing(self):
        """``evaluate`` is the deterministic core of an execution path: it must
        return a verdict for every input it is handed, including a malformed
        one, because an exception here would abort the tick and leave every
        remaining order unevaluated."""
        out = V5.evaluate({}, halted=False, heartbeats={},
                          signal_age_minutes=None, context=None)
        assert out["approve"] is False
        # EVERY check refuses EXCEPT THREE, and each of the three is genuinely
        # true rather than passing on nothing. Naming them rather than
        # asserting "all of them" is what keeps this test honest — the loose
        # version would have hidden a fourth check that passed on absence.
        #
        #   not_halted            — the caller passed ``halted=False`` and that
        #                           is a real reading.
        #   context_values_in_range — nothing was MALFORMED. Every field was
        #                           absent, and absent is not malformed: the
        #                           checks that need those fields refuse on
        #                           their own, which is where the refusal
        #                           belongs. A version of this check that also
        #                           fired on absence would report the same
        #                           sentence for a missing NAV and a boolean
        #                           one, which are different defects in the
        #                           gatherer.
        #   evaluate_completed    — the evaluation DID complete. It says
        #                           whether the envelope reached the end, not
        #                           whether it liked what it found, and an
        #                           empty input is precisely the case r1 threw
        #                           on and r2 must not.
        assert set(out["failed"]) == {c["check"] for c in out["checks"]} - {
            "not_halted", "context_values_in_range", "evaluate_completed"}
        # ...and with the kill switch ALSO engaged, the only survivors are the
        # two that describe the evaluation rather than the order.
        halted = V5.evaluate({}, halted=True, heartbeats={},
                             signal_age_minutes=None, context=None)
        assert set(halted["failed"]) == {c["check"] for c in out["checks"]} - {
            "context_values_in_range", "evaluate_completed"}
        assert halted["approve"] is False

    @pytest.mark.parametrize("junk", [
        {"side": "buy", "qty": "abc"}, {"side": None, "qty": 1},
        {"side": "buy", "qty": float("nan")},
        {"side": "buy", "qty": float("inf")},
    ])
    def test_a_malformed_order_refuses_without_raising(self, junk):
        out = V5.evaluate({**ORDER, **junk}, halted=False,
                          heartbeats=_beats(), signal_age_minutes=1.0,
                          context=_ok_ctx())
        assert out["approve"] is False
        assert "side_is_readable" in out["failed"]

    def test_determinism_same_inputs_same_answer(self):
        """Same inputs, same answer, forever — the property that makes this a
        policy rather than a judgement, and the reason an LLM is permanently
        out of the per-order decision."""
        a = _run()
        b = _run()
        assert a == b


# ===================================== the boundaries, probed AT the boundary

class TestTheMarkCheck:
    """CHECK 13 HAD ZERO TESTS — not the boundary, not the over-limit case, not
    even the absence branch. Found by the Gauntlet's boundary pass, and it is
    the check that carries v4's R1 forward: the phantom read 75.8% off a strike
    made half an hour earlier and nothing consulted it.

    A whole check with no negative path is a check that could have been
    ``ok=True`` all along and no test in this file would have noticed.
    """

    def test_a_mark_far_from_the_last_strike_refuses(self):
        assert "mark_corroborated" in _failed(mark_move_vs_strike_pct=75.8)

    def test_an_UNCORROBORATABLE_mark_refuses(self):
        """Absence, separately from over-limit: the two have different fixes
        and the riskofficer reads the detail."""
        out = _run(ctx=_ok_ctx(mark_move_vs_strike_pct=None))
        assert "mark_corroborated" in out["failed"]
        detail = [c for c in out["checks"]
                  if c["check"] == "mark_corroborated"][0]["detail"]
        assert "could not be compared" in detail

    @pytest.mark.parametrize("junk", ["", "abc", float("nan"), float("inf")])
    def test_a_mark_move_that_will_not_parse_refuses(self, junk):
        assert "mark_corroborated" in _failed(mark_move_vs_strike_pct=junk)

    def test_the_boundary_is_inclusive(self):
        b = V5.MAX_MARK_MOVE_VS_STRIKE_PCT
        assert "mark_corroborated" not in _failed(mark_move_vs_strike_pct=b)
        assert "mark_corroborated" in _failed(mark_move_vs_strike_pct=b + 0.01)


class TestEveryOtherBoundary:
    """One row per inequality the Gauntlet listed as unprobed. Each asserts the
    exact ceiling PASSES and one step past it REFUSES — strict-vs-non-strict is
    the class that produced two mutation survivors on this seat's D23, and a
    test near a boundary cannot tell the two apart."""

    NAV = 2000.0

    def test_the_daily_cap_at_exactly_the_ceiling(self):
        at = self.NAV * V5.MAX_ENGINE_DAILY_NOTIONAL_PCT / 100.0
        assert "daily_cumulative_within_cap" not in _failed(
            notional_usd=100.0, day_auto_notional_usd=at - 100.0)
        assert "daily_cumulative_within_cap" in _failed(
            notional_usd=100.0, day_auto_notional_usd=at - 100.0 + 1.0)

    def test_the_name_concentration_at_exactly_the_ceiling(self):
        # 20% of 2000 = $400 = 40 units at a $10 mark; the order adds 10.
        assert "post_fill_name_within_concentration" not in _failed(
            book_qty_signed=30.0, venue_qty_signed=30.0)
        assert "post_fill_name_within_concentration" in _failed(
            book_qty_signed=30.1, venue_qty_signed=30.1)

    def test_the_strategy_allocation_at_exactly_the_ceiling(self):
        # post-fill strategy exposure = 0 - 0 + |10 x 10| = $100 = 5% of NAV.
        assert "post_fill_strategy_within_allocation" not in _failed(
            strategy_allocation_pct=5.0)
        assert "post_fill_strategy_within_allocation" in _failed(
            strategy_allocation_pct=4.99)

    def test_the_gross_throttle_at_exactly_the_ceiling(self):
        # post-fill gross = 500 - 0 + 100 = $600 = 30% of NAV.
        assert "post_fill_gross_within_throttle" not in _failed(
            mandate_gross_fraction=0.30, throttle_multiplier=1.0)
        assert "post_fill_gross_within_throttle" in _failed(
            mandate_gross_fraction=0.2999, throttle_multiplier=1.0)

    def test_the_book_venue_drift_at_exactly_the_tolerance(self):
        tol = V5.MAX_POSITION_DRIFT_QTY
        assert "book_venue_in_sync" not in _failed(
            book_qty_signed=tol, venue_qty_signed=0.0)
        assert "book_venue_in_sync" in _failed(
            book_qty_signed=tol * 10, venue_qty_signed=0.0)

    def test_the_risk_monitor_freshness_at_exactly_the_ceiling(self):
        at = V5.MAX_RISK_MONITOR_AGE_SECONDS
        assert "risk_monitor_fresh" not in set(_run(beats=_beats(
            risk_monitor={"ok": True, "age_seconds": at}))["failed"])
        assert "risk_monitor_fresh" in set(_run(beats=_beats(
            risk_monitor={"ok": True, "age_seconds": at + 0.01}))["failed"])

    def test_an_exit_committed_at_the_SAME_INSTANT_is_not_pre_commitment(self):
        """MUTATION SURVIVOR M51. ``<=`` would count an exit written in the
        same instant as the signal, and the whole content of the word "pre" is
        that ordering. Sub-second timestamps make equality rare rather than
        impossible — and 'usually right' is the shape of bound this fund keeps
        finding at boundaries."""
        same = _ok_ctx()["signal_raised_at"]
        assert "exit_committed_for_entry" in _failed(
            committed_exit={"set_at": same, "live": True})
        one_earlier = "2026-08-27T09:59:59.999999+00:00"
        assert "exit_committed_for_entry" not in _failed(
            committed_exit={"set_at": one_earlier, "live": True})

    def test_a_zero_NAV_is_absent_at_exactly_the_epsilon(self):
        """``_pct_of`` treats |nav| <= POSITION_EPS as absent. Probed AT the
        epsilon, not merely at zero."""
        assert V5._pct_of(1.0, V5.POSITION_EPS) is None
        assert V5._pct_of(1.0, V5.POSITION_EPS * 10) is not None
