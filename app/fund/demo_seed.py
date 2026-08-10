"""Demo seed service — ensures ClarkHarness starts with a rich, demo-ready book out of the box.

If the store has no events or strategies, automatically initializes:
  * 4 LP deposits totaling $100,000 initial NAV
  * 4 realistic strategies (US Momentum, Mega-Cap Tech, Alpha Neutral, Crypto Trend) with backtest metrics
  * Filled positions (AAPL, MSFT, NVDA) and blotter execution history
  * 1 Pending Order (BUY 5 NVDA) tied to an Investment Thesis & Memo
  * 30 daily historical NAV snapshots for a smooth 30-day NAV growth curve chart
"""

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.fund.events import Event, EventStore, EventType
from app.fund.money import D, f, money, units
from app.fund.projections.nav import NAV_SNAPSHOTS
from app.fund.strategies import StrategyService

_log = logging.getLogger("clarkharness.demo_seed")


def seed_if_empty(store: EventStore, db) -> bool:
    """Check if the store is empty; if so, populate complete demo data."""
    try:
        existing_events = list(store.stream(since_seq=0, limit=1))
        if existing_events:
            _log.info("Store already contains events — skipping auto-seed.")
            return False
    except Exception as e:
        _log.warning("Could not check event store status (%s) — proceeding with auto-seed fallback.", e)

    _log.info("Initializing complete demo-ready fund state...")

    try:
        now = datetime.now(timezone.utc)
        strat_svc = StrategyService(store)

        # 1. Seed LPs
        lps = [
            ("aisha", 45000.0, "Aisha K"),
            ("rahul", 25000.0, "Rahul M"),
            ("mira", 20000.0, "Mira S"),
            ("devs", 10000.0, "Dev Squad"),
        ]
        seq = 1
        for lp_id, usd, name in lps:
            sub_id = f"sub-{lp_id}"
            store.append(
                Event(
                    seq=seq,
                    aggregate_id=sub_id,
                    aggregate_type="subscription",
                    type=EventType.SUBSCRIPTION_REQUESTED,
                    payload={"lp_id": lp_id, "lp_name": name, "usd_amount": D(usd)},
                    actor="operator",
                )
            )
            seq += 1
            store.append(
                Event(
                    seq=seq,
                    aggregate_id=sub_id,
                    aggregate_type="subscription",
                    type=EventType.CASH_CONFIRMED,
                    payload={"subscription_id": sub_id, "lp_id": lp_id, "usd_amount": D(usd), "units_minted": D(usd)},
                    actor="rushi",
                )
            )
            seq += 1

        # 2. Seed Strategies via StrategyService
        strat_specs = [
            {
                "name": "US Momentum",
                "state": "deployed",
                "allocation_pct": 35.0,
                "assets": ["AAPL", "MSFT", "NVDA"],
                "backtest": {
                    "total_return": 14.2,
                    "sharpe": 1.42,
                    "max_drawdown": -0.124,
                    "n_trades": 18,
                    "final_equity": 1.142,
                    "bars": 254,
                },
            },
            {
                "name": "Mega-Cap Tech",
                "state": "deployed",
                "allocation_pct": 25.0,
                "assets": ["AAPL", "MSFT", "GOOGL"],
                "backtest": {
                    "total_return": 9.8,
                    "sharpe": 1.18,
                    "max_drawdown": -0.148,
                    "n_trades": 12,
                    "final_equity": 1.098,
                    "bars": 254,
                },
            },
            {
                "name": "Alpha Neutral",
                "state": "deployed",
                "allocation_pct": 20.0,
                "assets": ["AAPL", "TSLA"],
                "backtest": {
                    "total_return": 18.4,
                    "sharpe": 1.65,
                    "max_drawdown": -0.095,
                    "n_trades": 24,
                    "final_equity": 1.184,
                    "bars": 254,
                },
            },
            {
                "name": "Crypto Trend",
                "state": "draft",
                "allocation_pct": 0.0,
                "assets": ["BTC/USDT", "ETH/USDT"],
                "backtest": {
                    "total_return": 5.2,
                    "sharpe": 0.88,
                    "max_drawdown": -0.215,
                    "n_trades": 8,
                    "final_equity": 1.052,
                    "bars": 180,
                },
            },
        ]

        strategy_ids = {}
        for s in strat_specs:
            reg = strat_svc.register(name=s["name"], actor="clark", definition={"type": "sma", "fast": 20, "slow": 50})
            sid = reg["strategy_id"]
            strategy_ids[s["name"]] = sid
            strat_svc.record_backtest(sid, results=s["backtest"], actor="clark")
            if s["state"] != "draft":
                strat_svc.set_state(sid, state=s["state"], actor="operator")
            if s["allocation_pct"] > 0:
                strat_svc.set_allocation(sid, target_pct=s["allocation_pct"], actor="operator")
            strat_svc.set_assets(sid, symbols=s["assets"], actor="operator")

        # 3. Seed Executed Fills (Positions)
        us_mom_id = strategy_ids["US Momentum"]
        megacap_id = strategy_ids["Mega-Cap Tech"]

        fills = [
            ("order-fill-1", us_mom_id, "AAPL", "buy", 15.0, 220.50, 0.0),
            ("order-fill-2", megacap_id, "MSFT", "buy", 10.0, 410.00, 0.0),
            ("order-fill-3", us_mom_id, "NVDA", "buy", 8.0, 125.00, 0.0),
        ]
        for fid, sid, sym, side, qty, px, fees in fills:
            store.append(
                Event(
                    seq=seq,
                    aggregate_id=fid,
                    aggregate_type="order",
                    type=EventType.ORDER_FILLED,
                    payload={
                        "order_id": fid,
                        "strategy_id": sid,
                        "symbol": sym,
                        "side": side,
                        "filled_qty": D(qty),
                        "avg_price": D(px),
                        "fees": D(fees),
                    },
                    actor="paper",
                )
            )
            seq += 1

        # 4. Seed Pending Order & Thesis & Memo
        from app.fund.thesis import ThesisService
        from app.fund.memo import MemoService

        thesis_svc = ThesisService(store)
        memo_svc = MemoService(store)

        t_res = thesis_svc.create(
            {
                "title": "NVDA Blackwell GPU Momentum Surge",
                "assets": ["NVDA"],
                "claim": "High conviction positioning into Q3 AI data center hardware spending surge.",
                "horizon": "3 months",
                "owner": "Clark Agent",
            },
            actor="clark",
        )
        thesis_id = t_res["thesis_id"]

        m_res = memo_svc.create(
            {
                "thesis_id": thesis_id,
                "title": "Investment Memo: NVDA Positioning",
                "recommendation": "BUY 5 NVDA",
                "conviction": "high",
                "summary": "Proposing +5 NVDA allocation under US Momentum strategy.",
                "author": "Clark Agent",
                "sections": {
                    "Thesis": "Blackwell architecture production ramping smoothly. Hyperscaler capex guidance remains elevated."
                },
            },
            actor="clark",
        )
        memo_svc.finalize(m_res["memo_id"], actor="rushi")

        pending_order_id = "order-pending-nvda-1"
        store.append(
            Event(
                seq=seq,
                aggregate_id=pending_order_id,
                aggregate_type="order",
                type=EventType.ORDER_PROPOSED,
                payload={
                    "order_id": pending_order_id,
                    "strategy_id": us_mom_id,
                    "thesis_id": thesis_id,
                    "symbol": "NVDA",
                    "side": "buy",
                    "qty": D(5.0),
                    "order_type": "market",
                    "reason": "AI momentum signal trigger",
                },
                actor="clark",
            )
        )
        seq += 1

        # 4b. Seed Completed Thesis & Post-Mortem
        from app.fund.postmortem import PostmortemService
        pm_svc = PostmortemService(store)

        t_res_closed = thesis_svc.create(
            {
                "title": "AAPL Services Expansion & Buyback Acceleration",
                "assets": ["AAPL"],
                "claim": "Services growth acceleration and increased buyback authorization drive +8% target valuation upside.",
                "horizon": "1 month",
                "owner": "Clark Agent",
            },
            actor="clark",
        )
        t_closed_id = t_res_closed["thesis_id"]
        thesis_svc.set_status(t_closed_id, status="reviewed", actor="operator")

        try:
            pm_svc.record(
                thesis_id=t_closed_id,
                body={
                    "outcome_summary": "Services revenue accelerated +12% YoY. Thesis fully validated; position closed with +$450 realized profit.",
                    "learnings": "Momentum entry timing performed cleanly under volatility contraction.",
                    "realized_pnl_usd": 450.0,
                    "win": True,
                },
                actor="clark",
            )
        except Exception as e:
            _log.warning("Could not record post-mortem (%s) — proceeding.", e)

        # 5. Seed 30-day Historical NAV Snapshots (Smooth NAV Growth Curve)
        base_nav = Decimal("100000.00")
        total_units = Decimal("100000.00")

        for day in range(30, -1, -1):
            ts_date = now - timedelta(days=day)
            progress = (30 - day) / 30.0
            nav_val = base_nav + Decimal(str(round(9968.79 * progress, 2)))
            cash_val = Decimal("91000.00") + Decimal(str(round(9017.28 * progress - 91000.00, 2)))
            pos_val = nav_val - cash_val
            navpu = nav_val / total_units

            snap_data = {
                "ts": ts_date.isoformat(),
                "total_nav_usd": f(nav_val),
                "units_outstanding": f(total_units),
                "nav_per_unit": f(navpu),
                "breakdown": {"cash": f(cash_val), "positions": f(pos_val)},
                "positions": [
                    {"symbol": "AAPL", "qty": 15.0, "mark": 220.50, "usd_value": 3307.50},
                    {"symbol": "MSFT", "qty": 10.0, "mark": 410.00, "usd_value": 4100.00},
                    {"symbol": "NVDA", "qty": 8.0, "mark": 125.00, "usd_value": 1000.00},
                ],
            }
            try:
                db.collection(NAV_SNAPSHOTS).document(ts_date.isoformat()).set(snap_data)
            except Exception:
                pass

        _log.info("Demo seed complete: 4 LPs, 4 Strategies, 30 NAV Snapshots, Fills & Pending Order initialized.")
        return True

    except Exception as e:
        _log.error("Failed to populate demo seed data: %s", e, exc_info=True)
        return False
