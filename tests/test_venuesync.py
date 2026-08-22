"""Reconciling the book to the venue BY APPENDING — never by reading equity.

Built from the real 2026-08-22 divergence, verbatim off the live spine:

    book   cash   968.69 + positions  917.06 = NAV      1885.74
                  SPY 0.346119, DBC 8.122157, TLT 3.019871, DBA 5.314306
    broker cash   846.84 + positions 1166.42 = equity   2013.26
                  SPY 0.217757, GLD 0.424471, INTC 1.608762, MSFT 0.340051,
                  NVDA 0.749886, SOFI 9.188190, XLE 2.749912

The one non-negotiable that has never bent in this fund's history is *"NAV
folds from the event log only; broker equity is a comparison, never the
truth."* A prior change violated it directly — ``NavService.compute()``
returned live Alpaca equity AS the NAV, with a hardcoded units_outstanding
fallback that destroyed the unit ledger (reverted in f0b18c9). Several tests
here exist purely so that cannot come back through this door.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.fund import venuesync
from app.fund.connectors.base import Position
from app.fund.events import EventType
from app.fund.money import D

# The live reading, to the cent and the six decimals.
BROKER_CASH = 846.84
BROKER_EQUITY = 2013.26
BROKER_POSITIONS = {
    "SPY": (0.217757, 640.00),
    "GLD": (0.424471, 300.00),
    "INTC": (1.608762, 20.00),
    "MSFT": (0.340051, 480.00),
    "NVDA": (0.749886, 170.00),
    "SOFI": (9.188190, 22.00),
    "XLE": (2.749912, 90.00),
}
MARKS = {"SPY": 765.55, "DBC": 31.25, "TLT": 82.045, "DBA": 28.32,
         "GLD": 310.00, "INTC": 21.00, "MSFT": 500.00, "NVDA": 175.00,
         "SOFI": 23.00, "XLE": 92.00, "AAPL": 200.0}
#: The fixture enters positions 10% below the mark it later values them at, so
#: every holding carries a NON-ZERO unrealised gain. See the fixture.
ENTRY_DISCOUNT = 0.90


class FakeBroker:
    """The Alpaca paper account as it actually read on 2026-08-22."""

    name = "alpaca"

    def __init__(self, cash=BROKER_CASH, equity=BROKER_EQUITY,
                 positions=None, configured=True):
        self._cash, self._equity, self._configured = cash, equity, configured
        self._positions = BROKER_POSITIONS if positions is None else positions

    def account_info(self):
        if not self._configured:
            return {"venue": self.name, "configured": False,
                    "message": "credentials missing"}
        return {"venue": self.name, "configured": True, "mode": "alpaca_paper",
                "cash": self._cash, "equity": self._equity,
                "portfolio_value": self._equity}

    def positions(self):
        return [Position(venue=self.name, symbol=s, qty=q, avg_price=p)
                for s, (q, p) in self._positions.items()]

    def price(self, symbol):
        px = MARKS.get(symbol)
        if px is None:
            raise ValueError(f"no price for {symbol}")
        return px

    def quote(self, order):
        from app.fund.connectors.base import Quote
        return Quote(symbol=order.symbol, price=self.price(order.symbol))

    def validate(self, order):
        from app.fund.connectors.base import ValidationResult
        return ValidationResult(ok=True)

    def execute(self, order, idempotency_key):
        from app.fund.connectors.base import VenueRef
        return VenueRef(venue=self.name, ref_id="ref")

    def poll(self, ref):
        from app.fund.connectors.base import ExecStatus, FillState
        return ExecStatus(state=FillState.FILLED, filled_qty=1.0,
                          avg_price=1.0, fees=0.0)

    def balances(self):
        from app.fund.connectors.base import Balance
        return [Balance(venue=self.name, asset="USD", amount=self._cash)]


@pytest.fixture
def book(wire):
    """A book shaped like the live one: cash plus four simulated-venue holdings."""
    from app.fund.connectors.base import Order, Side
    from app.fund.pipeline import CommandPipeline
    from app.fund.projections.nav import NavService
    from app.fund.risk import RiskGate, RiskLimits

    r = wire.ledger.request_subscription(lp_id="lp", usd_amount=2000.0, actor="m")
    wire.ledger.confirm_subscription(r["subscription_id"], actor="m")

    conn = wire.conn
    # BUY AT A DIFFERENT PRICE FROM THE CURRENT MARK, deliberately. An earlier
    # version of this fixture bought at the same price it later marked at, so
    # every held position carried exactly zero unrealised P&L — which made the
    # mutation "realise the gain on a release" arithmetically a no-op, and
    # `test_no_realised_pnl_is_invented_by_a_reconciliation` passed against a
    # broken fold. A fixture with no P&L cannot test that P&L is not invented.
    conn._prices.update({s: px * ENTRY_DISCOUNT for s, px in MARKS.items()})
    nav = NavService(pricer=conn.price, store=wire.store, projection=wire.proj)
    pipe = CommandPipeline(
        connector=conn, nav_service=nav, store=wire.store,
        risk_gate=RiskGate(RiskLimits(max_position_pct=100.0,
                                      max_order_notional_pct=100.0,
                                      min_cash_buffer=0.0)))
    for sym, qty, sid in (("SPY", 0.346119, "sleeve_beta_500"),
                          ("DBC", 8.122157, "sleeve_beta_500"),
                          ("TLT", 3.019871, "sleeve_beta_500"),
                          ("DBA", 5.314306, "sleeve_premia_carry")):
        res = pipe.propose_order(
            Order(venue="paper", symbol=sym, side=Side.BUY, qty=qty,
                  strategy_id=sid), actor="cto")
        pipe.approve_order(res["order_id"], "neelesh")
    # Now the market has moved: every holding sits on an unrealised gain that a
    # reconciliation must NOT turn into a realised one.
    conn._prices.update(MARKS)
    wire.nav_service = nav
    return wire


def _plan(book, broker=None):
    return venuesync.plan(connector=broker or FakeBroker(), store=book.store,
                          nav_service=book.nav_service,
                          attribution=book.attribution,
                          pricer=(broker or FakeBroker()).price)


class TestThePlanIsReadOnlyAndMeasured:
    def test_the_plan_writes_nothing(self, book):
        before = len(book.store.stream(0, 100_000))
        _plan(book)
        assert len(book.store.stream(0, 100_000)) == before

    def test_it_names_every_symbol_on_both_sides(self, book):
        plan = _plan(book)
        assert {a.symbol for a in plan.alignments} == {
            "SPY", "DBC", "TLT", "DBA", "GLD", "INTC", "MSFT", "NVDA",
            "SOFI", "XLE"}

    def test_releases_and_adoptions_are_labelled_separately(self, book):
        plan = _plan(book)
        by_dir = {}
        for a in plan.moving:
            by_dir.setdefault(a.direction, set()).add(a.symbol)
        assert by_dir["release"] == {"DBC", "TLT", "DBA", "SPY"}
        assert by_dir["adopt"] == {"GLD", "INTC", "MSFT", "NVDA", "SOFI", "XLE"}

    def test_the_basis_lets_a_reader_re_derive_the_delta(self, book):
        """Requirement 5: a future reader must be able to re-derive the delta
        without trusting the note."""
        payload = _plan(book).to_payload()
        b = payload["basis"]
        assert b["venue"] == "alpaca"
        assert b["venue_read_at"]
        assert b["venue_equity_usd"] == pytest.approx(BROKER_EQUITY)
        assert b["venue_cash_usd"] == pytest.approx(BROKER_CASH)
        assert b["book_fold_seq"] > 0
        # The book NAV as the FOLD produced it at plan time — not a number
        # copied in from anywhere. (The live fund reads 1885.74; this fixture's
        # simulated fills are at the same marks, so it reads its subscription.)
        assert payload["nav"]["book_before_usd"] == pytest.approx(
            float(book.nav_service.compute().total_nav_usd), abs=0.01)
        # Every moving row carries both sides, so delta_qty is checkable.
        for row in payload["positions"]:
            assert row["delta_qty"] == pytest.approx(
                row["venue_qty"] - row["book_qty"], abs=1e-9)

    def test_an_unreadable_broker_refuses_rather_than_planning_a_flat_account(
            self, book):
        """The single most dangerous confusion on this path: an empty positions
        list is what both an unreachable broker and a flat account return.
        Planning against the first would release EVERY position the fund
        holds."""
        with pytest.raises(venuesync.VenueSyncError):
            _plan(book, FakeBroker(configured=False))

    def test_a_missing_cash_figure_refuses(self, book):
        class NoCash(FakeBroker):
            def account_info(self):
                info = super().account_info()
                info.pop("cash")
                return info

        with pytest.raises(venuesync.VenueSyncError) as e:
            _plan(book, NoCash())
        assert "not zero" in str(e.value)

    def test_a_symbol_with_no_mark_refuses(self, book):
        broker = FakeBroker(positions={**BROKER_POSITIONS, "ZZZZ": (1.0, 5.0)})
        with pytest.raises(venuesync.VenueSyncError) as e:
            _plan(book, broker)
        assert "ZZZZ" in str(e.value)

    def test_a_venue_that_reports_no_cost_basis_does_not_crash_the_plan(self, book):
        """FOUND BY RUNNING THIS AGAINST THE LIVE ACCOUNT, not by a test.

        ``Position.avg_price`` is typed float, but a real reading can carry a
        quantity with no cost basis — the fund's own /fund/venue/reconcile is
        one such reading — and ``D(str(None))`` raises InvalidOperation. An
        absent cost basis is ABSENT: the row says so, and the mark is used
        instead, which the payload records rather than leaving the reader to
        infer from a null."""
        broker = FakeBroker(positions={s: (q, None)
                                       for s, (q, _) in BROKER_POSITIONS.items()})
        payload = _plan(book, broker).to_payload()
        adopted = next(r for r in payload["positions"] if r["symbol"] == "GLD")
        assert adopted["venue_avg_price"] is None
        assert adopted["cost_basis_from"].startswith("mark")
        assert adopted["mark"] == MARKS["GLD"]

    def test_a_cost_basis_the_venue_DID_report_is_used(self, book):
        payload = _plan(book).to_payload()
        adopted = next(r for r in payload["positions"] if r["symbol"] == "GLD")
        assert adopted["venue_avg_price"] == BROKER_POSITIONS["GLD"][1]
        assert adopted["cost_basis_from"] == "venue_avg_price"

    def test_the_venue_is_asked_for_its_positions_exactly_once(self, book):
        """Two round trips can disagree, and a plan built from two readings of
        a moving account is a plan of a book that never existed."""
        broker = FakeBroker()
        calls = {"n": 0}
        inner = broker.positions

        def counting():
            calls["n"] += 1
            return inner()

        broker.positions = counting
        _plan(book, broker)
        assert calls["n"] == 1, calls

    def test_a_simulated_connector_has_no_second_opinion(self, book):
        with pytest.raises(venuesync.VenueSyncError):
            venuesync.plan(connector=book.conn, store=book.store,
                           nav_service=book.nav_service,
                           attribution=book.attribution)


class TestApplyIsGuardedAndIdempotent:
    def test_it_refuses_without_a_written_reason(self, book):
        with pytest.raises(venuesync.VenueSyncError) as e:
            venuesync.apply(book.store, _plan(book), actor="neelesh", reason="  ")
        assert "unexplained" in str(e.value)

    def test_it_refuses_without_an_actor(self, book):
        with pytest.raises(venuesync.VenueSyncError):
            venuesync.apply(book.store, _plan(book), actor="", reason="because")

    def test_it_appends_exactly_one_event(self, book):
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        rows = [e for e in book.store.stream(0, 100_000)
                if e["type"] == EventType.BOOK_RECONCILED_TO_VENUE.value]
        assert len(rows) == 1

    def test_replaying_the_same_run_id_does_nothing(self, book):
        plan = _plan(book)
        venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        again = venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        assert again["applied"] is False
        rows = [e for e in book.store.stream(0, 100_000)
                if e["type"] == EventType.BOOK_RECONCILED_TO_VENUE.value]
        assert len(rows) == 1

    def test_an_agreeing_book_writes_nothing(self, wire):
        """No event for a no-op. An append-only log should not accumulate
        entries recording that nothing happened."""
        from app.fund.projections.nav import NavService

        wire.conn._prices.update(MARKS)
        wire.nav_service = NavService(pricer=wire.conn.price, store=wire.store,
                                      projection=wire.proj)
        broker = FakeBroker(cash=0.0, equity=0.0, positions={})
        out = venuesync.apply(wire.store, _plan(wire, broker),
                              actor="neelesh", reason="CEO")
        assert out["applied"] is False


class TestTheFoldProducesTheMatchingAnswer:
    def test_positions_become_the_venues_after_the_fold(self, book):
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        held = {s: p["qty"] for s, p in book.proj.build().positions.items()
                if abs(p["qty"]) > Decimal("1e-9")}
        assert set(held) == set(BROKER_POSITIONS)
        for sym, (qty, _) in BROKER_POSITIONS.items():
            assert float(held[sym]) == pytest.approx(qty, abs=1e-9)

    def test_cash_becomes_the_venues_after_the_fold(self, book):
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        assert float(book.proj.build().cash) == pytest.approx(BROKER_CASH, abs=0.01)

    def test_nav_is_still_folded_and_is_NOT_broker_equity(self, book):
        """THE non-negotiable. NAV after the sync is cash plus positions at the
        FUND'S OWN marks. It will be close to broker equity and it must not be
        equal to it by construction — if it ever is, someone has wired equity
        into the fold again (f0b18c9)."""
        plan = _plan(book)
        venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        after = book.nav_service.compute()

        expected = D(str(BROKER_CASH)) + sum(
            (D(str(q)) * D(str(MARKS[s])) for s, (q, _) in BROKER_POSITIONS.items()),
            Decimal("0"))
        assert float(after.total_nav_usd) == pytest.approx(float(expected), abs=0.01)
        # The fund's marks are not the broker's, so the two must still differ.
        assert float(after.total_nav_usd) != pytest.approx(BROKER_EQUITY, abs=0.01)

    def test_the_plan_predicted_what_the_fold_produced(self, book):
        """The plan states projected_book_after_usd BEFORE the write. If the
        fold disagrees with it, one of the two is wrong and the operator
        approved a number that did not happen."""
        plan = _plan(book)
        predicted = float(plan.projected_nav())
        venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        assert float(book.nav_service.compute().total_nav_usd) == pytest.approx(
            predicted, abs=0.01)

    def test_applying_twice_by_replaying_the_event_does_not_double_the_book(
            self, book):
        """The fold SETS to a recorded target rather than applying a delta, so
        a replayed or duplicated event is idempotent under the fold. In an
        append-only log nothing can be taken back, so this property is the only
        protection there is."""
        from app.fund.events import Event

        plan = _plan(book)
        venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        once = book.proj.build()
        # A second, differently-identified copy of the same fact.
        book.store.append(Event(
            aggregate_id="replay", aggregate_type="fund",
            type=EventType.BOOK_RECONCILED_TO_VENUE,
            payload=plan.to_payload(), actor="replay"))
        book.store.invalidate_cache()
        twice = book.proj.build()
        assert twice.cash == once.cash
        assert {s: p["qty"] for s, p in twice.positions.items()} == \
               {s: p["qty"] for s, p in once.positions.items()}


class TestTheStepIsNotReadableAsReturn:
    def test_since_inception_reports_the_reconciliation_separately(self, book):
        before = book.nav_service.since_inception()
        assert before["reconciliation_usd"] == 0.0

        plan = _plan(book)
        step = float(plan.projected_nav() - plan.book_nav_before)
        venuesync.apply(book.store, plan, actor="neelesh", reason="CEO")
        book.store.invalidate_cache()

        after = book.nav_service.since_inception()
        assert after["reconciliation_usd"] == pytest.approx(step, abs=0.01)
        assert after["pnl_ex_reconciliation_usd"] == pytest.approx(
            after["pnl_usd"] - after["reconciliation_usd"], abs=0.01)
        assert after["return_pct"] != after["return_pct_ex_reconciliation"]
        assert "non-market reason" in after["reconciliation_note"]

    def test_the_reconciliation_names_who_and_why_forever(self, book):
        venuesync.apply(book.store, _plan(book), actor="neelesh",
                        reason="CEO instruction 2026-08-21: sync to the alpaca screen")
        book.store.invalidate_cache()
        rows = book.nav_service.since_inception()["reconciliations"]
        assert len(rows) == 1
        assert rows[0]["actor"] == "neelesh"
        assert "alpaca screen" in rows[0]["reason"]
        assert rows[0]["at"]

    def test_a_zero_here_is_a_measured_zero(self, book):
        """The field is always present, so a reader never has to decide whether
        its absence means 'none' or 'this build does not report it'."""
        assert "reconciliation_usd" in book.nav_service.since_inception()

    def test_the_reconciliation_is_not_counted_as_subscribed_capital(self, book):
        before = book.nav_service.since_inception()["subscribed_usd"]
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        assert book.nav_service.since_inception()["subscribed_usd"] == before


class TestStrategyLedgersAndExitCoverage:
    def test_released_positions_leave_the_ledger_that_held_them(self, book):
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        rows = {r["strategy_id"]: r for r in book.attribution.with_values(
            lambda s: MARKS.get(s, 1.0))}
        beta = rows.get("sleeve_beta_500", {})
        held = {sym for sym, qty in (beta.get("positions") or {}).items()
                if abs(float(qty)) > 1e-9}
        assert "DBC" not in held and "TLT" not in held

    def test_no_realised_pnl_is_invented_by_a_reconciliation(self, book):
        """Nothing was sold. Booking a realised gain here would put an invented
        trade into every performance number the strategy has, permanently."""
        realised_before = {
            r["strategy_id"]: r["realized_pnl_usd"]
            for r in book.attribution.with_values(lambda s: MARKS.get(s, 1.0))}
        # The fixture holds real unrealised gains, so "realise them" is not a
        # no-op the arithmetic can hide. Asserted, because that assumption is
        # what makes the rest of this test mean anything.
        unrealised = {r["strategy_id"]: r["unrealized_pnl_usd"]
                      for r in book.attribution.with_values(
                          lambda s: MARKS.get(s, 1.0))}
        assert all(abs(v) > 1.0 for v in unrealised.values()), unrealised
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        realised_after = {
            r["strategy_id"]: r["realized_pnl_usd"]
            for r in book.attribution.with_values(lambda s: MARKS.get(s, 1.0))}
        for sid, before in realised_before.items():
            assert realised_after.get(sid, before) == pytest.approx(before, abs=1e-6)

    def test_adopted_positions_belong_to_no_strategy(self, book):
        """The CEO accepted this explicitly. The fold makes the acceptance TRUE
        rather than assumed: an adopted position that quietly acquired a
        strategy would be reported as covered by an exit rule nobody wrote."""
        venuesync.apply(book.store, _plan(book), actor="neelesh", reason="CEO")
        book.store.invalidate_cache()
        rows = {r["strategy_id"]: r for r in book.attribution.with_values(
            lambda s: MARKS.get(s, 1.0))}
        disc = rows.get("discretionary", {})
        # with_values renders positions as {symbol: qty}.
        held = {sym for sym, qty in (disc.get("positions") or {}).items()
                if abs(float(qty)) > 1e-9}
        assert {"GLD", "INTC", "MSFT", "NVDA", "SOFI", "XLE"} <= held

    def test_the_plan_names_what_will_be_unmanaged(self, book):
        plan = _plan(book)
        assert {a.symbol for a in plan.adopted_unmanaged} == {
            "GLD", "INTC", "MSFT", "NVDA", "SOFI", "XLE"}
        assert set(plan.to_payload()["unmanaged_after"]) == {
            "GLD", "INTC", "MSFT", "NVDA", "SOFI", "XLE"}


class TestExitCoverageCanSeeUncoveredHoldings:
    def test_a_held_position_with_no_rule_is_reported_uncovered(self, wire):
        """Before 2026-08-22 this method iterated over RULES, so a holding with
        no rule appeared in NO list — and a reader summing fired + holding +
        unevaluable saw a complete-looking picture of an incomplete book."""
        from app.fund.exitrule import ExitRules

        out = ExitRules(wire.store).check(
            [{"symbol": "GLD", "qty": 0.424471, "usd_value": 131.6,
              "unrealized_pnl_pct": 1.2}])
        assert [u["symbol"] for u in out["uncovered"]] == ["GLD"]
        assert "NO exit rule" in out["note"]

    def test_unreadable_marks_are_not_reported_as_full_coverage(self, wire):
        """An empty positions list because the marks could not be read must not
        read as 'nothing uncovered'."""
        from app.fund.exitrule import ExitRules

        out = ExitRules(wire.store).check([])
        assert out["uncovered"] == []
        assert out["coverage_known"] is False
        assert "UNKNOWN" in out["note"]
