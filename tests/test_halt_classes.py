"""Halt classes, acknowledge-and-rebase, and tick-to-halt latency.

Two incidents behind this file:

  * **The phantom price (2026-08-20)** — a $100.00 GLD mark against a true
    413.84 was executed on. "Halted" was one word for two different situations:
    the fund could not MEASURE itself (integrity) and the fund did not like
    what it measured (loss). Only the second has a reopening procedure.
  * **riskofficer F4 (2026-08-20)** — fill seq 258 at 08:01:27.147Z, first
    TradingHalted seq 265 at 08:16:08.932Z: **14m41s across ~29 monitor
    ticks**. The audit filed the WHY as an open measurement. The tests below
    measure tick-to-halt directly, so any future regression in that number is
    a failing test rather than an archaeology exercise.

Nothing here asserts a threshold VALUE. The limits used are constructed in the
test; the machinery is what is under test.
"""

from decimal import Decimal

import pytest

from app.fund.connectors.base import Order, Side
from app.fund.events import Event, EventType
from app.fund.risk import RiskLimits
from app.fund.riskmonitor import (
    HALT_INTEGRITY,
    HALT_LOSS,
    HALT_MANUAL,
    RiskControl,
    RiskMonitor,
    classify_halt_cause,
)


def subscribe(w, lp, amount):
    r = w.ledger.request_subscription(lp_id=lp, usd_amount=amount, actor="mgr")
    return w.ledger.confirm_subscription(r["subscription_id"], actor="mgr")


def _breached_book(wire, *, buy_qty=200, crash_to=150.0):
    """$100k in, $40k of AAPL, a strike dated YESTERDAY, then a crash.

    The prior-day strike is the daily-loss reference; without one the rule has
    nothing to measure from (which is its own test below).
    """
    subscribe(wire, "lp-1", 100_000.0)
    res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=buy_qty), actor="op")
    wire.pipe_open.approve_order(res["order_id"], "op")
    payload = wire.nav.compute().to_dict()
    payload["ts"] = "2026-08-19T20:00:00+00:00"
    wire.store.append(Event(aggregate_id="fund", aggregate_type="fund",
                            type=EventType.NAV_STRUCK, payload=payload, actor="system"))
    wire.conn._prices["AAPL"] = crash_to
    return float(payload["total_nav_usd"])


# --- C1: halt classes -------------------------------------------------------

class TestHaltClasses:
    def test_a_daily_loss_auto_halt_is_classified_loss(self):
        assert classify_halt_cause("daily_loss") == HALT_LOSS
        assert classify_halt_cause("drawdown") == HALT_LOSS

    def test_a_data_quality_cause_is_classified_integrity(self):
        assert classify_halt_cause("data_quality") == HALT_INTEGRITY
        assert classify_halt_cause("unpriced") == HALT_INTEGRITY

    def test_an_unknown_cause_is_manual_never_loss(self):
        """Misfiling an unrecognised cause as `loss` would make it eligible for
        acknowledge-and-rebase — the one action that must never be reachable by
        accident."""
        assert classify_halt_cause("something_new") == HALT_MANUAL
        assert classify_halt_cause(None) == HALT_MANUAL
        assert classify_halt_cause("") == HALT_MANUAL

    def test_the_class_is_carried_on_the_event_and_the_fold(self, wire):
        control = RiskControl(wire.store)
        control.halt(reason="feed dead", actor="op", halt_class=HALT_INTEGRITY)
        assert control.halt_class() == HALT_INTEGRITY
        assert control.halt_state()["halt_reason"] == "feed dead"
        halts = [e for e in wire.store.stream(0, 100_000)
                 if e["type"] == EventType.TRADING_HALTED.value]
        assert halts[-1]["payload"]["halt_class"] == HALT_INTEGRITY

    def test_an_auto_halt_from_a_loss_breach_carries_the_loss_class(self, wire):
        _breached_book(wire)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        out = monitor.run(actor="monitor")
        assert out["halted"] is True
        assert out["halt_class"] == HALT_LOSS

    def test_resume_clears_the_class_and_is_not_a_kind_of_halt(self, wire):
        control = RiskControl(wire.store)
        control.halt(reason="x", actor="op", halt_class=HALT_LOSS)
        control.resume(actor="op")
        assert control.halt_class() is None
        assert control.halt_state()["halted"] is False

    def test_a_pre_classes_halt_reports_class_none_not_manual(self, wire):
        """A halt recorded before classes existed carries no class. Reporting it
        as `manual` would invent a fact about a historical event."""
        wire.store.append(Event(aggregate_id="fund", aggregate_type="fund",
                                type=EventType.TRADING_HALTED,
                                payload={"reason": "legacy"}, actor="monitor"))
        control = RiskControl(wire.store)
        assert control.is_halted() is True
        assert control.halt_class() is None

    def test_a_bogus_class_falls_back_to_manual(self, wire):
        control = RiskControl(wire.store)
        control.halt(reason="x", actor="op", halt_class="whatever-i-like")
        assert control.halt_class() == HALT_MANUAL

    def test_sells_still_pass_while_halted_whatever_the_class(self, wire):
        """The asymmetry is unchanged by classification: de-risking always works."""
        from app.fund.pipeline import CommandPipeline
        control = RiskControl(wire.store)
        control.halt(reason="feed dead", actor="op", halt_class=HALT_INTEGRITY)
        pipe = CommandPipeline(connector=wire.conn, nav_service=wire.nav, store=wire.store)
        assert pipe.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.SELL, qty=1),
            actor="op")["status"] == "pending_approval"
        assert pipe.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1),
            actor="op")["status"] == "rejected"


# --- C2: acknowledge-and-rebase --------------------------------------------

class TestAcknowledgeAndRebase:
    def test_a_rebase_without_a_reason_is_refused(self, wire):
        control = RiskControl(wire.store)
        with pytest.raises(ValueError) as e:
            control.rebase_loss_reference(nav_usd=1000.0, reason="  ", actor="neelesh")
        assert "written reason" in str(e.value)
        assert control.loss_reference() is None, "a refused rebase must not reach the log"

    def test_a_rebase_is_refused_while_an_integrity_halt_is_open(self, wire):
        """Rebasing onto 'current NAV' when current NAV is the number we do not
        trust would launder a bad mark into the fund's own reference — the
        phantom-price incident with a signature on it."""
        control = RiskControl(wire.store)
        control.halt(reason="GLD mark disagrees with the last strike", actor="monitor",
                     halt_class=HALT_INTEGRITY)
        with pytest.raises(ValueError) as e:
            control.rebase_loss_reference(nav_usd=1000.0, reason="accepted", actor="neelesh")
        assert "INTEGRITY" in str(e.value)
        assert control.loss_reference() is None

    def test_a_rebase_is_permitted_while_a_loss_halt_is_open(self, wire):
        control = RiskControl(wire.store)
        control.halt(reason="Auto-halt: daily loss", actor="monitor", halt_class=HALT_LOSS)
        out = control.rebase_loss_reference(
            nav_usd=1878.60, reason="the drop is the corrected GLD mark, not a loss",
            actor="neelesh")
        assert out["status"] == "rebased"
        assert control.loss_reference()["nav_usd"] == 1878.60

    def test_a_non_positive_reference_is_refused(self, wire):
        control = RiskControl(wire.store)
        for bad in (0.0, -1.0):
            with pytest.raises(ValueError):
                control.rebase_loss_reference(nav_usd=bad, reason="why", actor="neelesh")

    def test_the_daily_loss_alarm_reads_the_rebased_reference(self, wire):
        """The whole point: after acknowledging, the same NAV is no longer a
        breach — and the alarm's own message says the reference was rebased."""
        _breached_book(wire)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        before = [a for a in monitor.evaluate_alarms() if a.type == "daily_loss"]
        assert before, "the fixture is supposed to be in breach"

        control.rebase_loss_reference(
            nav_usd=float(wire.nav.compute().total_nav_usd),
            reason="acknowledged: the -25% is a corrected mark, not a trading loss",
            actor="neelesh")
        control._invalidate()
        after = [a for a in monitor.evaluate_alarms() if a.type == "daily_loss"]
        assert not after, "the rebased reference was not read by the daily-loss rule"

    def test_a_rebase_does_not_move_any_threshold(self, wire):
        """Acknowledge-and-rebase moves the point the limit is measured FROM.
        If it ever moves the limit itself, that is a quiet loosening."""
        control = RiskControl(wire.store)
        before = control.limits().to_dict()
        control.rebase_loss_reference(nav_usd=1000.0, reason="because", actor="neelesh")
        control._invalidate()
        assert control.limits().to_dict() == before

    def test_a_rebase_after_a_prior_day_strike_wins_and_before_it_loses(self, wire):
        """Whichever reference is NEWER wins. A rebase from last week must not
        override yesterday's strike."""
        ref_nav = _breached_book(wire)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        wire.store.append(Event(
            aggregate_id="fund", aggregate_type="fund",
            type=EventType.LOSS_REFERENCE_REBASED,
            payload={"nav_usd": 10.0, "reason": "stale", "at": "2026-08-01T00:00:00+00:00"},
            actor="neelesh"))
        control._invalidate()
        ref, kind, _ = monitor._loss_reference({"ts": "2026-08-20T12:00:00+00:00"})
        assert kind == "prior_strike" and ref == pytest.approx(ref_nav)


# --- C3: tick-to-halt latency ----------------------------------------------

class TestTickToHalt:
    def test_a_daily_loss_breach_halts_within_one_tick(self, wire):
        """riskofficer F4 measured 14m41s (~29 ticks) from breach to halt. This
        measures the same interval in ticks and requires exactly one.

        The number this test guards is 1. If a future change makes the monitor
        need two ticks to act on a breach that is fully visible on the first,
        this fails — which is the only way "the kill switch is fast" stops
        being a story we tell ourselves.
        """
        _breached_book(wire)          # AAPL 200 -> 150 = -10% daily vs a 4% limit
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        assert not control.is_halted()

        ticks = 0
        for _ in range(30):           # F4's ~29 ticks; one is the pass mark
            ticks += 1
            out = monitor.run(actor="monitor")
            if out["halted"]:
                break
        assert ticks == 1, f"breach-to-halt took {ticks} ticks, not 1"
        assert control.halt_class() == HALT_LOSS

    def test_a_drawdown_breach_halts_within_one_tick(self, wire):
        subscribe(wire, "lp-1", 100_000.0)
        res = wire.pipe_open.propose_order(
            Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=200), actor="op")
        wire.pipe_open.approve_order(res["order_id"], "op")
        wire.nav.strike()
        wire.conn._prices["AAPL"] = 50.0
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        assert monitor.run(actor="monitor")["halted"] is True

    def test_the_daily_loss_rule_says_so_when_it_has_no_reference(self, wire):
        """A fund that has never struck a prior-day NAV has NO daily-loss kill
        switch. That used to be a silent return, which reads on every surface as
        'the limit is fine'. Absence is not a pass."""
        subscribe(wire, "lp-1", 100_000.0)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        keys = [a.key for a in monitor.evaluate_alarms()]
        assert "daily_loss_unevaluable" in keys
        assert "daily_loss" not in keys, "an absent reference must never read as a breach"

    def test_a_post_fill_reeval_failure_is_reported_not_swallowed(self, wire, caplog):
        """`except Exception: pass` meant the ONE risk evaluation triggered by
        the event that moves the book could fail in silence — and did, while
        assess() raised on an unpriceable symbol (builder audit H2). The fill is
        still recorded; the failure is now named to the caller and the log."""
        import logging
        from app.fund import pipeline as pipeline_mod

        class ExplodingMonitor:
            def __init__(self, *a, **kw):
                pass

            def run(self, actor="monitor"):
                raise RuntimeError("nav unreadable")

        subscribe(wire, "lp-1", 100_000.0)
        original = pipeline_mod.RiskMonitor
        pipeline_mod.RiskMonitor = ExplodingMonitor
        try:
            with caplog.at_level(logging.ERROR):
                res = wire.pipe_open.propose_order(
                    Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=1), actor="op")
                out = wire.pipe_open.approve_order(res["order_id"], "op")
        finally:
            pipeline_mod.RiskMonitor = original

        assert out["status"] == "filled", "the fill must still be recorded"
        assert "risk_reeval" in out and "failed" in out["risk_reeval"]
        assert "were NOT evaluated" in caplog.text

    def test_assess_reports_the_halt_class_and_a_rebase_token(self, wire):
        _breached_book(wire)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        monitor.run(actor="monitor")
        a = monitor.assess()
        assert a["halted"] is True
        assert a["halt_class"] == HALT_LOSS
        assert a["halt_reason"].startswith("Auto-halt")
        assert len(a["rebase_token"]) == 8
        assert a["loss_reference"]["kind"] == "prior_strike"
        assert a["loss_reference"]["nav_usd"] is not None

    def test_the_rebase_token_changes_when_the_state_it_describes_changes(self, wire):
        """A confirm copied off a stale panel must not still work."""
        _breached_book(wire)
        control = RiskControl(wire.store)
        monitor = RiskMonitor(nav_service=wire.nav, store=wire.store,
                              pricer=wire.conn.price, control=control)
        before = monitor.rebase_token()
        wire.conn._prices["AAPL"] = 120.0
        assert monitor.rebase_token() != before
