"""Shared base context. PRECONDITION assertions are labelled; the measurement is
whatever the caller changes. Written fresh against r2's documented contract."""
import copy

RAISED = "2026-08-27T12:00:00+00:00"

def base():
    order = {"symbol": "HYG", "side": "buy", "qty": 3.7, "strategy_id": "s1"}
    ctx = {
        "engine_entries_enabled": True,
        "execution_venue_kind": "alpaca_paper",
        "execution_venue_real_money": False,
        "strategy": {"strategy_id": "s1", "state": "deployed",
                     "archived": False, "assets": ["HYG"]},
        "strategy_allocation_pct": 25.0,
        "live_sessions": [{"session_id": "sess-1", "strategy_id": "s1",
                           "state": "running",
                           "started_at": "2026-08-27T10:00:00+00:00"}],
        "pending_approved": [],
        "signal_raised_at": RAISED,
        "nav_usd": 2000.0,
        "order_mark_usd": 80.0,
        "mark_move_vs_strike_pct": 0.5,
        "day_auto_notional_usd": 0.0,
        "book_qty_signed": 0.0,
        "strategy_qty_signed": 0.0,
        "venue_qty_signed": 0.0,
        "venue_readable": True,
        "strategy_exposure_usd": 0.0,
        "gross_exposure_usd": 0.0,
        "mandate_gross_fraction": 0.9,
        "throttle_multiplier": 1.0,
        "throttle_measurable": True,
        "max_position_fraction": 0.20,
        "committed_exit": {"set_at": "2026-08-27T09:00:00+00:00", "live": True},
    }
    beats = {j: {"ok": True, "age_seconds": 12.0}
             for j in ("exit_check", "risk_monitor", "settlement", "nav_strike")}
    return copy.deepcopy(order), copy.deepcopy(ctx), copy.deepcopy(beats)

def run(mod, order, ctx, beats, age=1.0, halted=False):
    return mod.evaluate(order, halted=halted, heartbeats=beats,
                        signal_age_minutes=age, context=ctx)
