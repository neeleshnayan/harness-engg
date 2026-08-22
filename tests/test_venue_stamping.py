"""The venue on an event is DERIVED FROM THE RUNTIME, never declared.

THE INCIDENT THIS FILE EXISTS FOR — order
``17d64dcd-0f39-4ce1-9632-ff27f0907964``, read verbatim out of the live
``krypton_fund`` log on 2026-08-22:

    seq 588  OrderProposed   actor=cto     payload.venue = "alpaca"
    seq 592  OrderApproved   actor=neelesh
    seq 593  OrderSubmitted  actor=system  payload.venue = "paper"
    seq 594  OrderFilled     actor=system  payload.venue = "alpaca"

DBA, 5.314306 shares at $28.38 — the CEO-authorised experimental deployment of
2026-08-21 whose entire learning goal was *"the fund's first informative
execution-cost observations"*. The proposer asked for ``alpaca``; the
PaperConnector executed it; ``pipeline._emit_fill`` wrote ``order.venue`` onto
the fill, so the fill claimed a venue it never touched. TCA counted it among
its informative orders, contributing 0.00bps of execution cost by
construction, and the experiment measured nothing while reporting that it had.

The same forgery is available to anything that proposes: ``exitrule.py:303``
hardcodes ``venue="paper"`` on EVERY exit it raises regardless of the executing
connector, and the propose schema defaults the field to ``"paper"``. Autopolicy
v4 already refuses to read ``order["venue"]`` for exactly this reason
(``autopolicy.py:452``); these tests make the WRITE path agree with the read
path.

If any test in this file ever asserts that a fill carries the venue the
proposer asked for, the defect is back.
"""

from __future__ import annotations

import pytest

from app.fund import mode as fundmode
from app.fund.connectors.base import Order, Side
from app.fund.events import EventType
from app.fund.pipeline import CommandPipeline


def _fund(wire, usd=50_000.0):
    """Give the book cash, so the risk gate has a NAV to size against."""
    r = wire.ledger.request_subscription(lp_id="lp", usd_amount=usd, actor="m")
    wire.ledger.confirm_subscription(r["subscription_id"], actor="m")


def _events(store, order_id, etype):
    return [e for e in store.by_aggregate(order_id)
            if e["type"] == etype.value]


def _one(store, order_id, etype):
    rows = _events(store, order_id, etype)
    assert len(rows) == 1, f"expected one {etype.value}, got {len(rows)}"
    return rows[0]["payload"]


class TestTheFillCannotWearAnotherVenuesName:
    def test_the_dba_forgery_cannot_happen_again(self, wire):
        """The receipt, reproduced: propose with venue='alpaca', execute on the
        paper connector, and demand that the FILL says paper."""
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        oid = res["order_id"]
        wire.pipe_open.approve_order(oid, "neelesh")

        fill = _one(wire.store, oid, EventType.ORDER_FILLED)
        assert fill["venue"] == "paper", (
            "a fill executed on the PaperConnector claimed a different venue "
            "— this is order 17d64dcd all over again")

    def test_the_proposers_request_is_kept_not_erased(self, wire):
        """Annotate, never erase. A proposer asking for a venue it did not get
        is worth seeing — silently rewriting the field would hide the very
        disagreement that made this defect findable."""
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        oid = res["order_id"]
        proposed = _one(wire.store, oid, EventType.ORDER_PROPOSED)
        assert proposed["venue"] == "paper"
        assert proposed["venue_requested"] == "alpaca"
        assert proposed["venue_source"] == "connector"

    def test_no_venue_requested_field_when_the_proposer_was_right(self, wire):
        """No noise on the normal path: the field appears only on a
        disagreement, so its presence in a log is itself the finding."""
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        proposed = _one(wire.store, res["order_id"], EventType.ORDER_PROPOSED)
        assert "venue_requested" not in proposed

    def test_the_hardcoded_exit_rule_venue_cannot_mislabel_a_fill(self, wire):
        """exitrule.py stamps venue='paper' on every exit it raises whatever
        connector will run it. Under a real broker that string would be a lie
        in the other direction — and a paper-labelled fill is EXCLUDED from the
        cost model, so this one loses real measurements rather than inventing
        them."""

        class FakeAlpaca:
            name = "alpaca"

            def quote(self, order):
                from app.fund.connectors.base import Quote
                return Quote(symbol=order.symbol, price=100.0)

            def price(self, symbol):
                return 100.0

            def validate(self, order):
                from app.fund.connectors.base import ValidationResult
                return ValidationResult(ok=True)

            def execute(self, order, idempotency_key):
                from app.fund.connectors.base import VenueRef
                return VenueRef(venue=self.name, ref_id="ref-1")

            def poll(self, ref):
                from app.fund.connectors.base import ExecStatus, FillState
                return ExecStatus(state=FillState.FILLED, filled_qty=1.0,
                                  avg_price=100.0, fees=0.0)

            def positions(self):
                return []

            def balances(self):
                return []

        _fund(wire)
        from app.fund.risk import RiskGate, RiskLimits

        pipe = CommandPipeline(
            connector=FakeAlpaca(), nav_service=wire.nav, store=wire.store,
            risk_gate=RiskGate(RiskLimits(max_position_pct=100.0,
                                          max_order_notional_pct=100.0,
                                          min_cash_buffer=0.0)))
        # Exactly the Order exitrule.py builds.
        res = pipe.propose_order(
            Order(venue="paper", symbol="TLT", side=Side.SELL, qty=1.0),
            actor="worker")
        oid = res["order_id"]
        pipe.approve_order(oid, "neelesh")

        # The correction lands ONCE, where the disagreement happened: on the
        # proposal. By fill time the order has been reloaded from that
        # corrected proposal, so there is nothing left to disagree with — and a
        # `venue_requested` on the fill would be a stale echo of a mismatch
        # already resolved, which is worse than absent.
        proposed = _one(wire.store, oid, EventType.ORDER_PROPOSED)
        assert proposed["venue"] == "alpaca"
        assert proposed["venue_requested"] == "paper"

        fill = _one(wire.store, oid, EventType.ORDER_FILLED)
        assert fill["venue"] == "alpaca"
        assert "venue_requested" not in fill


    def test_the_fill_leg_stamps_the_runtime_venue_ON_ITS_OWN(self, wire):
        """DEFENCE IN DEPTH, and this test exists because a mutation check
        found the gap.

        Every other test here goes through ``propose_order``, which corrects
        the venue at the proposal — so by fill time ``_load_order`` hands
        ``_emit_fill`` an order that already says the right thing, and
        reverting ``_emit_fill`` alone to ``order.venue`` passed all of them.
        That is precisely the line the DBA forgery came out of, so it gets a
        test that reaches it directly with a LYING order object."""
        lying = Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=1.0)
        assert wire.pipe._emit_fill("order-x", lying, 1.0, 200.0, 0.0) is True

        fill = _one(wire.store, "order-x", EventType.ORDER_FILLED)
        assert fill["venue"] == "paper"
        assert fill["venue_requested"] == "alpaca"


class TestEveryMoneyShapedEventCarriesTheRuntimeVenue:
    def test_submit_and_fill_agree(self, wire):
        """They disagreed on the live log — submit said paper, fill said
        alpaca — which is only possible because two different fields fed
        them."""
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        oid = res["order_id"]
        wire.pipe_open.approve_order(oid, "neelesh")
        submitted = _one(wire.store, oid, EventType.ORDER_SUBMITTED)
        fill = _one(wire.store, oid, EventType.ORDER_FILLED)
        assert submitted["venue"] == fill["venue"] == "paper"

    def test_a_rejected_order_records_the_runtime_venue_too(self, wire):
        """A rejection is where an order DIED, and 'died on which venue' is
        part of the record."""
        res = wire.pipe.propose_order(
            Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=100_000.0),
            actor="cto")
        assert res["status"] == "rejected"
        rejected = _one(wire.store, res["order_id"], EventType.ORDER_REJECTED)
        assert rejected["venue"] == "paper"
        assert rejected["venue_requested"] == "alpaca"


class TestModeTravelsWithTheArtifact:
    def test_no_mode_is_stamped_when_none_was_declared(self, wire):
        """Absence is reported as absence. A hand-built pipeline in a unit test
        has genuinely not declared a mode, and writing 'unknown' into a payload
        would put a mode nobody chose into an append-only log."""
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        proposed = _one(wire.store, res["order_id"], EventType.ORDER_PROPOSED)
        assert "mode" not in proposed

    def test_the_mode_rides_on_every_leg_once_declared(self, wire):
        """Requirement 4 of desk 0ffa4aee: mode travels with the fill, the
        event, the book, NAV, the TCA reader and the UI. A mock NAV and a paper
        NAV are different numbers and must never be confusable."""
        fundmode.activate(fundmode.MODES[fundmode.FundMode.TEST])
        _fund(wire)
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        oid = res["order_id"]
        wire.pipe_open.approve_order(oid, "neelesh")
        for etype in (EventType.ORDER_PROPOSED, EventType.ORDER_SUBMITTED,
                      EventType.ORDER_FILLED):
            assert _one(wire.store, oid, etype)["mode"] == "test", etype

    def test_a_connector_that_names_no_venue_says_the_label_is_unverified(
            self, wire):
        """Never promote a declaration to a fact. If the runtime cannot say
        where the order went, the record says the label came from the
        proposer."""
        class Nameless:
            def quote(self, order):
                from app.fund.connectors.base import Quote
                return Quote(symbol=order.symbol, price=1.0)

            def price(self, symbol):
                return 1.0

            def validate(self, order):
                from app.fund.connectors.base import ValidationResult
                return ValidationResult(ok=True)

        _fund(wire)
        from app.fund.risk import RiskGate, RiskLimits

        pipe = CommandPipeline(
            connector=Nameless(), nav_service=wire.nav, store=wire.store,
            risk_gate=RiskGate(RiskLimits(max_position_pct=100.0,
                                          max_order_notional_pct=100.0,
                                          min_cash_buffer=0.0)))
        res = pipe.propose_order(
            Order(venue="alpaca", symbol="AAPL", side=Side.BUY, qty=1.0),
            actor="cto")
        proposed = _one(wire.store, res["order_id"], EventType.ORDER_PROPOSED)
        assert proposed["venue"] == "alpaca"
        assert "declared" in proposed["venue_source"]


class TestTcaReadsTheExecutedVenue:
    def test_a_fill_labelled_alpaca_off_a_paper_submit_is_not_informative(self):
        """The re-baseline half of the clean-field rule. The cause is fixed
        above; this is the contaminated MEASUREMENT being re-derived, without
        editing a single historical event.

        Rows shaped exactly like the live 17d64dcd lifecycle."""
        from app.fund.tca import TransactionCosts

        class MemStore:
            rows = [
                {"seq": 1, "type": "OrderProposed", "aggregate_id": "17d64dcd",
                 "ts": "2026-08-21T06:49:00+00:00",
                 "payload": {"symbol": "DBA", "side": "buy", "venue": "alpaca",
                             "impact_preview": {"quote_price": "28.30"}}},
                {"seq": 2, "type": "OrderSubmitted", "aggregate_id": "17d64dcd",
                 "ts": "2026-08-21T06:51:30+00:00",
                 "payload": {"venue": "paper", "venue_ref": "4a8f97cc",
                             "arrival_price": 28.3799991607666}},
                {"seq": 3, "type": "OrderFilled", "aggregate_id": "17d64dcd",
                 "ts": "2026-08-21T06:51:30+00:00",
                 "payload": {"symbol": "DBA", "side": "buy", "venue": "alpaca",
                             "filled_qty": "5.314306",
                             "avg_price": "28.3799991607666", "fees": "0"}},
            ]

            def stream(self, since_seq=0, limit=100_000):
                return list(self.rows)

        rows = TransactionCosts(MemStore()).costs()
        assert len(rows) == 1
        row = rows[0]
        assert row.venue == "paper", "the connector's answer must win"
        assert row.venue_declared == "alpaca", "and the claim must be kept"
        assert row.venue_disputed is True
        assert row.informative is False, (
            "a PaperConnector fill carries zero cost information at any "
            "sample size; counting it is how the DBA experiment 'succeeded'")

    def test_the_summary_names_the_disputed_rows_rather_than_hiding_them(self):
        from app.fund.tca import OrderCost, summarise

        forged = OrderCost(
            order_id="17d64dcd", symbol="DBA", side="buy", strategy_id=None,
            qty=5.314306, decision_price=28.30, arrival_price=28.38,
            fill_price=28.38, notional_usd=150.8, fees_usd=0.0,
            approval_latency_s=150.0, submit_to_fill_s=0.05,
            total_bps=28.0, delay_bps=28.0, execution_bps=0.0, fees_bps=0.0,
            total_usd=0.42, has_split=True,
            proposed_ts=None, filled_ts=None,
            venue="paper", venue_declared="alpaca", venue_disputed=True)
        s = summarise([forged])
        assert s["informative"]["orders"] == 0
        assert s["informative"]["measurable"] is False
        assert s["informative"]["venue_disputed"] == 1
        assert s["informative"]["venue_disputed_orders"][0] == {
            "order_id": "17d64dcd", "symbol": "DBA",
            "executed_on": "paper", "labelled": "alpaca"}

    def test_a_backfilled_fill_with_no_submit_leg_keeps_its_own_label(self):
        """The eight adopted broker fills (seq 24-30) have no OrderSubmitted.
        Their 'alpaca' label came from BrokerBackfill replaying Alpaca's own
        records, so it is the broker's answer, not a proposer's, and falling
        back to it is correct."""
        from app.fund.tca import TransactionCosts

        class MemStore:
            rows = [
                {"seq": 1, "type": "OrderProposed", "aggregate_id": "adopted",
                 "ts": "2026-08-14T10:00:00+00:00",
                 "payload": {"symbol": "INTC", "side": "buy", "venue": "alpaca",
                             "impact_preview": {"quote_price": "20.00"}}},
                {"seq": 2, "type": "OrderFilled", "aggregate_id": "adopted",
                 "ts": "2026-08-14T10:00:01+00:00",
                 "payload": {"symbol": "INTC", "side": "buy", "venue": "alpaca",
                             "filled_qty": "1.0", "avg_price": "20.10",
                             "fees": "0", "backfill_reason": "replayed"}},
            ]

            def stream(self, since_seq=0, limit=100_000):
                return list(self.rows)

        row = TransactionCosts(MemStore()).costs()[0]
        assert row.venue == "alpaca"
        assert row.venue_disputed is False
        assert row.informative is True
