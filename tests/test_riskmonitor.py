"""Unit tests for the Risk Engine & Observability Pane (RiskControl, RiskMonitor, RiskGate halt-check).

Guards the fund's safety contracts:
  1. Drawdown kill-switch auto-halts trading when drawdown crosses max_drawdown_pct.
  2. Kill-switch halt blocks BUY orders while ALWAYS allowing SELL orders (de-risking).
  3. Alarms dedup across ticks (raised once, cleared once).
  4. Alarm rules (concentration, underwater, cash_floor, strategy_cap, daily_loss) trigger at exact thresholds.
  5. assess() output matches the canonical single-pane contract.
  6. Resuming trading is human-only (run() never auto-resumes).
"""

import pytest
from app.fund.connectors.base import Order, Side
from app.fund.events import EventType
from app.fund.pipeline import CommandPipeline
from app.fund.risk import RiskGate, RiskLimits
from app.fund.riskmonitor import Alarm, RiskControl, RiskMonitor


def subscribe(w, lp, amount, name=None):
    r = w.ledger.request_subscription(lp_id=lp, usd_amount=amount, actor="mgr", lp_name=name)
    return w.ledger.confirm_subscription(r["subscription_id"], actor="mgr")


def test_drawdown_killswitch(wire):
    """Seed capital, buy asset, strike NAV peak, then drop asset price past max_drawdown_pct -> auto-halt."""
    # 1. Deposit $100k cash
    subscribe(wire, "lp-1", 100_000.0)

    # 2. Buy 200 shares of AAPL @ $200 ($40k position)
    order_res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=200), actor="operator"
    )
    wire.pipe_open.approve_order(order_res["order_id"], "operator")

    # 3. Strike peak NAV ($100k)
    wire.nav.strike()

    # 4. Crash AAPL price from $200 to $50 ($30k loss on $100k NAV => 30% drawdown vs 15% limit)
    wire.conn._prices["AAPL"] = 50.0

    control = RiskControl(wire.store)
    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)

    assert not control.is_halted()

    # 5. Run monitor tick
    res = monitor.run(actor="monitor")

    assert control.is_halted()
    assert res["halted"] is True
    raised_keys = [a["key"] for a in res["raised"]]
    assert "drawdown" in raised_keys


def test_halt_blocks_buys_allows_sells(wire):
    """While halted, BUY orders are rejected by the pipeline while SELL orders pass."""
    control = RiskControl(wire.store)
    control.halt(reason="Testing safety kill-switch", actor="operator")
    assert control.is_halted()

    pipe = CommandPipeline(connector=wire.conn, nav_service=wire.nav, store=wire.store)

    # BUY proposed -> rejected
    buy_res = pipe.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=10), actor="operator"
    )
    assert buy_res["status"] == "rejected"
    assert "trading halted (risk kill-switch)" in buy_res["breaches"]

    # SELL proposed -> allowed (pending_approval)
    sell_res = pipe.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.SELL, qty=10), actor="operator"
    )
    assert sell_res["status"] == "pending_approval"


def test_alarm_dedup(wire):
    """Standing breaches raise an alarm event ONCE and clear ONCE when resolved."""
    # Set high min_cash_pct threshold (50%) with 0 cash to force cash_floor breach
    control = RiskControl(wire.store)
    control.set_limits({"min_cash_pct": 0.50}, actor="operator")

    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)

    # Tick 1: raises cash_floor alarm
    res1 = monitor.run(actor="monitor")
    raised1 = [a["key"] for a in res1["raised"]]
    assert "cash_floor" in raised1

    # Tick 2: standing breach -> no new alarm raised
    res2 = monitor.run(actor="monitor")
    raised2 = [a["key"] for a in res2["raised"]]
    assert "cash_floor" not in raised2

    # Lower cash threshold to 0.0 -> resolves breach
    control.set_limits({"min_cash_pct": 0.0}, actor="operator")

    # Tick 3: clears cash_floor alarm
    res3 = monitor.run(actor="monitor")
    assert "cash_floor" in res3["cleared"]


def test_alarm_threshold_types(wire):
    """Verify concentration, underwater, strategy_cap, and daily_loss alarm evaluations."""
    # Seed $100k
    subscribe(wire, "lp-1", 100_000.0)

    # Buy 200 shares of AAPL @ $200 ($40k = 40% of NAV) with strategy_id "strat-momentum"
    order_res = wire.pipe_open.propose_order(
        Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=200, strategy_id="strat-momentum"),
        actor="operator",
    )
    wire.pipe_open.approve_order(order_res["order_id"], "operator")

    # Mark price down to $150 (underwater by 25%)
    wire.conn._prices["AAPL"] = 150.0

    control = RiskControl(wire.store)
    # Set strict limits: max_position=20%, max_strategy=30%, underwater=15%
    control.set_limits(
        {"max_position_pct": 0.20, "max_strategy_pct": 0.30, "underwater_pct": 0.15},
        actor="operator",
    )

    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)
    assessment = monitor.assess()
    alarms = monitor.evaluate_alarms(assessment)

    alarm_keys = {a.key: a for a in alarms}

    assert "concentration:AAPL" in alarm_keys
    assert alarm_keys["concentration:AAPL"].severity in ("warn", "critical")

    assert "underwater:AAPL" in alarm_keys
    assert alarm_keys["underwater:AAPL"].severity == "warn"

    assert "strategy_cap:strat-momentum" in alarm_keys
    assert alarm_keys["strategy_cap:strat-momentum"].severity == "warn"


def test_assess_shape(wire):
    """assess() must return every key specified in the canonical observability contract."""
    # Seed capital
    subscribe(wire, "lp-1", 50_000.0)

    control = RiskControl(wire.store)
    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)

    a = monitor.assess()

    required_keys = {
        "nav_usd", "cash_usd", "cash_pct", "gross_exposure_usd", "gross_exposure_pct",
        "halted", "drawdown", "positions", "strategies", "limits", "utilization",
        "alarms", "worst_position", "ts",
    }
    assert required_keys.issubset(a.keys())

    assert a["nav_usd"] == 50_000.0
    assert a["cash_usd"] == 50_000.0
    assert a["cash_pct"] == 100.0
    assert a["gross_exposure_usd"] == 0.0
    assert a["halted"] is False
    assert "peak_nav" in a["drawdown"]
    assert "utilization" in a


def test_resume_human_only(wire):
    """run() tick never auto-resumes trading; resuming requires an explicit human action."""
    control = RiskControl(wire.store)
    control.halt(reason="Manual halt for inspection", actor="operator")
    assert control.is_halted()

    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)

    # Multiple monitor ticks under healthy conditions
    monitor.run(actor="monitor")
    monitor.run(actor="monitor")

    # Still halted
    assert control.is_halted()

    # Human resumes
    res = control.resume(actor="rushi")
    assert res["status"] == "resumed"
    assert not control.is_halted()


def test_daily_loss_prior_day_reference(wire):
    """daily_loss alarm uses prior-day NAV strike reference; subsequent same-day strikes do NOT neuter it."""
    subscribe(wire, "lp-1", 100_000.0)

    control = RiskControl(wire.store)
    monitor = RiskMonitor(nav_service=wire.nav, store=wire.store, pricer=wire.conn.price, control=control)

    # Assessment today (2026-08-12) with a >5% loss vs prior day (2026-08-11)
    partial_assessment = {
        "nav_usd": 93_000.0,
        "ts": "2026-08-12T12:00:00Z",
        "limits": control.limits().to_dict(),
        "history_snaps": [{"total_nav_usd": 100_000.0, "ts": "2026-08-11T12:00:00Z"}],
    }

    alarms = monitor.evaluate_alarms(partial_assessment)
    alarm_keys = [a.key for a in alarms]
    assert "daily_loss" in alarm_keys

    # Simulate frequent same-day strikes on 2026-08-12 (e.g. seconds ago)
    partial_assessment_second_strike = {
        "nav_usd": 93_000.0,
        "ts": "2026-08-12T12:05:00Z",
        "limits": control.limits().to_dict(),
        "history_snaps": [
            {"total_nav_usd": 100_000.0, "ts": "2026-08-11T12:00:00Z"},
            {"total_nav_usd": 93_000.0, "ts": "2026-08-12T12:00:00Z"},
        ],
    }

    # Should STILL compare against 2026-08-11 ($100k), raising daily_loss!
    alarms2 = monitor.evaluate_alarms(partial_assessment_second_strike)
    alarm_keys2 = [a.key for a in alarms2]
    assert "daily_loss" in alarm_keys2


def test_pretrade_gate_reads_limits_fresh(wire):
    """Tightening limits via set_limits immediately updates pre-trade gate in propose_order without restart."""
    pipe = CommandPipeline(connector=wire.conn, nav_service=wire.nav, store=wire.store)

    subscribe(wire, "lp-1", 100_000.0)

    # Under default 20% max_position_pct, a $15k AAPL order passes
    order = Order(venue="paper", symbol="AAPL", side=Side.BUY, qty=75)  # 75 * 200 = $15k = 15% NAV
    res1 = pipe.propose_order(order, actor="operator")
    assert res1["status"] == "pending_approval"

    # Tighten max_position_pct limit to 10% via control.set_limits
    control = RiskControl(wire.store)
    control.set_limits({"max_position_pct": 0.10}, actor="operator")

    # Now the exact same $15k order (15% of NAV) is rejected by the gate dynamically!
    res2 = pipe.propose_order(order, actor="operator")
    assert res2["status"] == "rejected"

