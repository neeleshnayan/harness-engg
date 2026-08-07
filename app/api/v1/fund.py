"""Fund harness API — the spine's HTTP surface.

Order path (venue-agnostic, human-gated): propose → risk gate → approve/decline
→ idempotent execution. Ledger path (LP-facing): subscribe/redeem with a
two-phase confirm, minting/burning units at NAV. Read routes expose NAV,
positions, per-LP holdings, and the audit event log.

The pipeline is wired to the PaperConnector today; swapping in the IBKRConnector
(Step 2) changes only the construction block below.
"""

import os

from fastapi import APIRouter, HTTPException, Query

from app.fund.connectors.alpaca import AlpacaConnector
from app.fund.connectors.base import Order, Side
from app.fund.backtest import SimpleBacktester, signals_for
from app.fund.marketdata import BarsError, fetch_daily_bars
from app.fund.connectors.paper import PaperConnector
from app.fund.events import EventStore
from app.fund.ledger import LedgerError, LedgerService
from app.fund.money import D, f
from app.fund.pipeline import CommandError, CommandPipeline
from app.fund.projections.holdings import HoldingsProjection
from app.fund.projections.nav import NavService
from app.fund.projections.orders import OrdersProjection
from app.fund.projections.positions import PositionsProjection
from app.fund.projections.strategy import StrategyAttribution
from app.fund.reconcile import Reconciler
from app.fund.strategies import StrategyError, StrategyService
from app.schemas.fund import (
    ActorRequest,
    ApprovalRequest,
    BacktestBySymbolRequest,
    BacktestResultRequest,
    BacktestRunRequest,
    ProposeOrderRequest,
    RedeemRequest,
    StrategyAllocationRequest,
    StrategyRegisterRequest,
    StrategyStateRequest,
    StrikeNavRequest,
    SubscribeRequest,
)

router = APIRouter()

# --- spine wiring (single place to swap the venue) -------------------------
# Alpaca when configured, else the in-Firestore paper venue. Same protocol.
def _paper_live_pricer():
    """Live free marks for the paper venue when FUND_LIVE_MARKS is truthy."""
    if os.getenv("FUND_LIVE_MARKS", "false").lower() in ("1", "true", "yes"):
        from app.fund.marketdata import live_price
        return live_price
    return None


_connector = (
    AlpacaConnector()
    if os.getenv("ALPACA_API_KEY")
    else PaperConnector(live_pricer=_paper_live_pricer())
)
_store = EventStore()
_projection = PositionsProjection(_store)
_nav = NavService(pricer=_connector.price, store=_store, projection=_projection)
_pipeline = CommandPipeline(connector=_connector, nav_service=_nav, store=_store)
_ledger = LedgerService(nav_service=_nav, store=_store)
_holdings = HoldingsProjection(_store)
_strategies = StrategyService(store=_store)
_attribution = StrategyAttribution(_store)
_orders = OrdersProjection(_store)
_reconciler = Reconciler(connector=_connector, store=_store, projection=_projection)


# --- worker hooks (called by endpoints and the scheduled worker) -----------
def run_settlement() -> dict:
    """Poll in-flight orders to terminal — the async fill tick."""
    return _pipeline.poll_open_orders()


def run_reconcile() -> dict:
    """Event book vs. venue truth."""
    return _reconciler.run()


def run_strike() -> dict:
    """Strike and persist a NAV snapshot."""
    return _nav.strike().to_dict()


# --- reads -----------------------------------------------------------------
@router.get("/fund/nav")
def get_nav():
    """Live (unstruck) valuation plus the last struck snapshot."""
    return {"live": _nav.compute().to_dict(), "last_struck": _nav.latest()}


@router.get("/fund/nav/history")
def get_nav_history(limit: int = Query(90, ge=1, le=365)):
    """Recent struck NAV snapshots, oldest first — for value trend charts."""
    return {"history": _nav.history(limit=limit)}


@router.get("/fund/positions")
def get_positions():
    """The event-sourced book: cash, units outstanding, positions."""
    book = _projection.build()
    return {
        "cash": f(book.cash),
        "units_outstanding": f(book.units_outstanding),
        "positions": {
            s: {"qty": f(p["qty"]), "avg_price": f(p["avg_price"])}
            for s, p in book.positions.items()
        },
    }


@router.get("/fund/lps")
def get_lps():
    """Every LP with units and current value (the manager's LP book)."""
    nav = _nav.compute()
    return {"nav_per_unit": f(nav.nav_per_unit), "lps": _holdings.with_values(nav.nav_per_unit)}


@router.get("/fund/lp/{lp_id}")
def get_lp(lp_id: str):
    """One LP's managed-fund view: units, value, and share of the fund."""
    nav = _nav.compute()
    rec = _holdings.build().get(lp_id)
    if rec is None or abs(rec["units"]) < D("1e-9"):
        raise HTTPException(status_code=404, detail=f"no holdings for {lp_id}")
    units = rec["units"]
    outstanding = nav.units_outstanding if nav.units_outstanding > 0 else units
    return {
        "lp_id": lp_id,
        "name": rec["name"],
        "units": f(units),
        "value_usd": f((units * nav.nav_per_unit).quantize(D("0.01"))),
        "nav_per_unit": f(nav.nav_per_unit),
        "ownership_pct": f((D(100) * units / outstanding).quantize(D("0.0001"))),
    }



@router.get("/fund/events")
def get_events(since_seq: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=1000)):
    """The audit trail — the global event log from ``since_seq`` (exclusive)."""
    return {"events": _store.stream(since_seq=since_seq, limit=limit)}


@router.get("/fund/orders/pending")
def get_pending_orders():
    """The approval queue — orders awaiting a human decision (also where LEAN signals land)."""
    return {"pending": _orders.pending()}


@router.get("/fund/orders/{order_id}")
def get_order(order_id: str):
    events = _store.by_aggregate(order_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"unknown order {order_id}")
    return {"order_id": order_id, "events": events}


# --- order writes ----------------------------------------------------------
@router.post("/fund/orders/propose")
def propose_order(req: ProposeOrderRequest):
    """Propose an order. Passes the risk gate then awaits human approval."""
    order = Order(
        venue=req.venue,
        symbol=req.symbol.upper(),
        side=Side(req.side),
        qty=req.qty,
        limit_price=req.limit_price,
        strategy_id=req.strategy_id,
    )
    return _pipeline.propose_order(order, actor=req.actor)


@router.post("/fund/orders/{order_id}/approve")
def approve_order(order_id: str, req: ApprovalRequest):
    """Human approval gate — approving triggers idempotent execution."""
    try:
        return _pipeline.approve_order(order_id, approver=req.approver)
    except CommandError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/orders/{order_id}/decline")
def decline_order(order_id: str, req: ApprovalRequest):
    try:
        return _pipeline.decline_order(order_id, approver=req.approver)
    except CommandError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/nav/strike")
def strike_nav(req: StrikeNavRequest):
    """Strike and persist a NAV snapshot (the scheduled valuation moment)."""
    return _nav.strike(actor=req.actor).to_dict()


@router.post("/fund/orders/settle")
def settle_orders():
    """Poll in-flight orders and emit any terminal/partial events (async fill tick)."""
    return run_settlement()


@router.post("/fund/reconcile")
def reconcile():
    """Compare the event book against venue truth; emit mismatches."""
    return run_reconcile()


# --- ledger writes (subscribe / redeem) ------------------------------------
@router.post("/fund/lp/subscriptions")
def request_subscription(req: SubscribeRequest):
    """Record an intended deposit (friend says money is coming). Units mint on confirm."""
    try:
        return _ledger.request_subscription(
            lp_id=req.lp_id, usd_amount=req.usd_amount, actor=req.actor, lp_name=req.lp_name
        )
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/lp/subscriptions/{subscription_id}/confirm")
def confirm_subscription(subscription_id: str, req: ActorRequest):
    """Cash landed → mint units at the current NAV-per-unit."""
    try:
        return _ledger.confirm_subscription(subscription_id, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/lp/redemptions")
def request_redemption(req: RedeemRequest):
    """Record an intended redemption; payout is confirmed separately."""
    try:
        return _ledger.request_redemption(lp_id=req.lp_id, units=req.units, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/lp/redemptions/{redemption_id}/confirm")
def confirm_redemption(redemption_id: str, req: ActorRequest):
    """Payout sent → burn units and remove cash at the current NAV-per-unit."""
    try:
        return _ledger.confirm_redemption(redemption_id, actor=req.actor)
    except LedgerError as e:
        raise HTTPException(status_code=409, detail=str(e))


# --- strategies ------------------------------------------------------------
@router.get("/fund/strategies")
def list_strategies():
    """Every strategy with its target allocation and live exposure/P&L, plus any
    discretionary (untagged) book. `actual_pct` is exposure as a share of NAV."""
    nav = _nav.compute()
    total = float(nav.total_nav_usd)
    attr = {a["strategy_id"]: a for a in _attribution.with_values(_connector.price)}

    rows = []
    for s in _strategies.list():
        a = attr.get(s["strategy_id"], {})
        exposure = a.get("exposure_usd", 0.0)
        rows.append({
            **s,
            "exposure_usd": exposure,
            "pnl_usd": a.get("pnl_usd", 0.0),
            "positions": a.get("positions", {}),
            "actual_pct": round(100.0 * exposure / total, 4) if total else 0.0,
        })

    # Layered cake: roll each container strategy up over its descendants.
    by_id = {r["strategy_id"]: r for r in rows}
    children: dict[str, list[str]] = {}
    for r in rows:
        if r.get("parent_id") in by_id:
            children.setdefault(r["parent_id"], []).append(r["strategy_id"])

    def _rollup(sid: str, seen: set | None = None) -> tuple[float, float]:
        seen = seen or set()
        if sid in seen:
            return 0.0, 0.0
        seen.add(sid)
        r = by_id[sid]
        exp, pnl = r["exposure_usd"], r["pnl_usd"]
        for c in children.get(sid, []):
            ce, cp = _rollup(c, seen)
            exp += ce
            pnl += cp
        return exp, pnl

    for r in rows:
        kids = children.get(r["strategy_id"], [])
        r["children"] = kids
        r["is_container"] = bool(kids)
        r["depth"] = 0 if not r.get("parent_id") else 1  # UI indent hint (1 level for now)
        if kids:
            re_, rp_ = _rollup(r["strategy_id"])
            r["rolled_exposure_usd"] = round(re_, 2)
            r["rolled_pnl_usd"] = round(rp_, 2)
            r["rolled_actual_pct"] = round(100.0 * re_ / total, 4) if total else 0.0

    return {"nav_usd": total, "strategies": rows, "discretionary": attr.get("discretionary")}


@router.get("/fund/strategies/{strategy_id}")
def get_strategy(strategy_id: str):
    try:
        s = _strategies.get(strategy_id)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    attr = {a["strategy_id"]: a for a in _attribution.with_values(_connector.price)}
    return {**s, "attribution": attr.get(strategy_id)}


@router.post("/fund/strategies")
def register_strategy(req: StrategyRegisterRequest):
    try:
        return _strategies.register(name=req.name, definition=req.definition,
                                    parent_id=req.parent_id, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/backtest")
def record_backtest(strategy_id: str, req: BacktestResultRequest):
    """Record a backtest result (run in the studio / LEAN) and mark it backtested."""
    try:
        return _strategies.record_backtest(strategy_id, results=req.results, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/backtest/run")
def run_backtest(strategy_id: str, req: BacktestRunRequest):
    """Run a built-in backtest over supplied prices, record the result, mark backtested.

    (Prices are client-supplied for now; wiring Alpaca historical bars is a fast-follow.)
    """
    signals = signals_for(
        req.strategy, req.prices, fast=req.fast, slow=req.slow,
        rsi_period=req.rsi_period, rsi_low=req.rsi_low, rsi_high=req.rsi_high,
        breakout_lookback=req.breakout_lookback, macd_fast=req.macd_fast,
        macd_slow=req.macd_slow, macd_signal=req.macd_signal,
        boll_period=req.boll_period, boll_k=req.boll_k,
        momentum_lookback=req.momentum_lookback, atr_period=req.atr_period, atr_mult=req.atr_mult,
    )
    result = SimpleBacktester().run(req.prices, signals)
    try:
        rec = _strategies.record_backtest(strategy_id, results=result.to_dict(), actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"result": result.to_dict(), "strategy": rec}


@router.get("/fund/marketdata/bars")
def get_bars(symbol: str = Query(..., min_length=1, max_length=6),
             lookback_days: int = Query(180, gt=1, le=2000)):
    """Free daily bars for a symbol (Alpaca if keyed, else Yahoo) — for charts."""
    try:
        bars = fetch_daily_bars(symbol, lookback_days=lookback_days)
    except BarsError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"symbol": bars.symbol, "source": bars.source,
            "closes": bars.closes, "dates": bars.dates,
            "start": bars.start, "end": bars.end}


@router.post("/fund/strategies/{strategy_id}/backtest/by_symbol")
def run_backtest_by_symbol(strategy_id: str, req: BacktestBySymbolRequest):
    """Fetch real free daily bars for a symbol and run the built-in backtest.

    Bars come from Alpaca (free IEX) when ALPACA_API_KEY/SECRET are set, else from
    Stooq (free, no key). Returns the result plus the price series for charting.
    """
    try:
        bars = fetch_daily_bars(req.symbol, lookback_days=req.lookback_days)
    except BarsError as e:
        raise HTTPException(status_code=422, detail=str(e))

    prices = bars.closes
    signals = signals_for(
        req.strategy, prices, fast=req.fast, slow=req.slow,
        rsi_period=req.rsi_period, rsi_low=req.rsi_low, rsi_high=req.rsi_high,
        breakout_lookback=req.breakout_lookback, macd_fast=req.macd_fast,
        macd_slow=req.macd_slow, macd_signal=req.macd_signal,
        boll_period=req.boll_period, boll_k=req.boll_k,
        momentum_lookback=req.momentum_lookback, atr_period=req.atr_period, atr_mult=req.atr_mult,
    )
    result = SimpleBacktester().run(prices, signals)
    try:
        rec = _strategies.record_backtest(strategy_id, results=result.to_dict(), actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {
        "result": result.to_dict(),
        "strategy": rec,
        "source": bars.source,
        "symbol": bars.symbol,
        "bars": {"closes": prices, "dates": bars.dates, "start": bars.start, "end": bars.end},
    }


@router.post("/fund/strategies/{strategy_id}/state")
def set_strategy_state(strategy_id: str, req: StrategyStateRequest):
    """Move a strategy through its lifecycle (deploy, pause, …)."""
    try:
        return _strategies.set_state(strategy_id, state=req.state, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/allocation")
def set_strategy_allocation(strategy_id: str, req: StrategyAllocationRequest):
    """Set a strategy's target allocation (% of NAV)."""
    try:
        return _strategies.set_allocation(strategy_id, target_pct=req.target_pct, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=400, detail=str(e))
