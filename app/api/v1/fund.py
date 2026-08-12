"""Fund harness API — the spine's HTTP surface.

Order path (venue-agnostic, human-gated): propose → risk gate → approve/decline
→ idempotent execution. Ledger path (LP-facing): subscribe/redeem with a
two-phase confirm, minting/burning units at NAV. Read routes expose NAV,
positions, per-LP holdings, and the audit event log.

The pipeline is wired to the PaperConnector today; swapping in the IBKRConnector
(Step 2) changes only the construction block below.
"""

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

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
from app.fund.memo import MemoError, MemoService
from app.fund.postmortem import PostmortemError, PostmortemService
from app.fund.reconcile import Reconciler
from app.fund.riskanalytics import RiskAnalytics
from app.fund.riskmonitor import RiskControl, RiskMonitor
from app.fund.simulation import CounterfactualSimulator
from app.fund.sentinel import SentinelRadar
from app.fund.strategies import StrategyError, StrategyService
from app.fund.thesis import ThesisError, ThesisService
from app.schemas.fund import (
    ActorRequest,
    ApprovalRequest,
    BacktestBySymbolRequest,
    BacktestResultRequest,
    BacktestRunRequest,
    MemoCreateRequest,
    MemoFinalizeRequest,
    MemoUpdateRequest,
    PostmortemRequest,
    ProposeOrderRequest,
    RedeemRequest,
    RiskHaltRequest,
    RiskLimitsPatchRequest,
    RiskResumeRequest,
    RiskRunRequest,
    RiskShockRequest,
    StrategyAllocationRequest,
    StrategyArchiveRequest,
    StrategyAssetsRequest,
    StrategyParentRequest,
    StrategyRegisterRequest,
    StrategyRenameRequest,
    StrategyStateRequest,
    StrikeNavRequest,
    SubscribeRequest,
    ThesisCreateRequest,
    ThesisStatusRequest,
    ThesisUpdateRequest,
    StrategyOptimizeRequest,
)

from app.fund.optimization import optimize_portfolio

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
_theses = ThesisService(store=_store)
_memos = MemoService(store=_store)
_risk = RiskAnalytics(nav_service=_nav)
_postmortem = PostmortemService(store=_store, pricer=_connector.price)
_attribution = StrategyAttribution(_store)
_orders = OrdersProjection(_store)
_reconciler = Reconciler(connector=_connector, store=_store, projection=_projection)
_control = RiskControl(store=_store)
_monitor = RiskMonitor(nav_service=_nav, store=_store, pricer=_connector.price,
                       attribution=_attribution, strategies=_strategies, control=_control)
from app.fund.pair_arb import PairArbitrageEngine
from app.fund.macro_regime import MacroRegimeClassifier

_pair_arb = PairArbitrageEngine()
_macro_regime = MacroRegimeClassifier()
_simulator = CounterfactualSimulator(nav_service=_nav, positions_projection=_projection, strategy_service=_strategies)
_sentinel = SentinelRadar(thesis_service=_theses, memo_service=_memos, store=_store)


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


@router.post("/fund/nav/strike")
def post_nav_strike(req: ActorRequest | None = None):
    """Manually strike and persist a NAV snapshot into Firestore."""
    actor = req.actor if req else "operator"
    return _nav.strike(actor=actor).to_dict()


# --- reads -----------------------------------------------------------------
@router.get("/fund/venue/account")
def get_venue_account():
    """Live broker account info (Alpaca equity, cash, buying power, positions)."""
    if hasattr(_connector, "account_info"):
        return _connector.account_info()
    return {
        "venue": getattr(_connector, "name", "paper"),
        "configured": False,
        "mode": "paper_mock",
    }


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


@router.get("/fund/orders/history")
def get_order_history(strategy_id: str | None = Query(None), limit: int = Query(200, ge=1, le=1000)):
    """The trade blotter — order lifecycle rows, newest first.

    With ``strategy_id`` on a container strategy, rolls up over its whole subtree
    (the layered cake), so a parent shows its children's trades too.
    """
    subtree: set[str] | None = None
    if strategy_id:
        # collect the strategy + all descendants across many-to-many edges
        kids: dict[str, list[str]] = {}
        for s in _strategies.list():
            for pid in (s.get("parents") or ([s["parent_id"]] if s.get("parent_id") else [])):
                kids.setdefault(pid, []).append(s["strategy_id"])
        subtree, stack = set(), [strategy_id]
        while stack:
            cur = stack.pop()
            if cur in subtree:
                continue
            subtree.add(cur)
            stack.extend(kids.get(cur, []))
    return {"orders": _orders.history(strategy_ids=subtree, limit=limit)}


@router.get("/fund/orders/{order_id}")
def get_order(order_id: str):
    events = _store.by_aggregate(order_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"unknown order {order_id}")
    return {"order_id": order_id, "events": events}


@router.get("/fund/events")
def get_events(limit: int = Query(100, ge=1, le=1000), since_seq: int = Query(0, ge=0)):
    """Immutable fund audit event log, newest first — powers the live audit feed."""
    raw = _store.stream(since_seq=since_seq, limit=limit)
    raw.sort(key=lambda e: e.get("seq") or 0, reverse=True)
    return {"events": raw}


# --- order writes ----------------------------------------------------------
@router.post("/fund/orders/propose")
def propose_order(req: ProposeOrderRequest):
    """Propose an order. Passes the risk gate then awaits human approval.

    Every trade should reference a thesis or be explicitly discretionary — that
    rule is what makes post-mortems meaningful.
    """
    if req.thesis_id:
        try:
            _theses.get(req.thesis_id)  # must reference a real thesis
        except ThesisError:
            raise HTTPException(status_code=404, detail=f"unknown thesis {req.thesis_id}")
    elif not req.discretionary and os.getenv("REQUIRE_THESIS", "false").lower() in ("1", "true", "yes"):
        # Opt-in discipline: every trade references a thesis or is explicitly discretionary.
        raise HTTPException(
            status_code=422,
            detail="order must reference a thesis_id or be marked discretionary=true",
        )
    order = Order(
        venue=req.venue,
        symbol=req.symbol.upper(),
        side=Side(req.side),
        qty=req.qty,
        limit_price=req.limit_price,
        strategy_id=req.strategy_id,
        thesis_id=req.thesis_id,
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


# --- theses (the versioned investment idea a trade references) --------------
@router.post("/fund/theses")
def create_thesis(req: ThesisCreateRequest):
    body = req.model_dump()
    body["owner"] = body.get("owner") or req.actor
    return _theses.create(body, actor=req.actor)


@router.get("/fund/theses")
def list_theses():
    return {"theses": _theses.list()}


@router.get("/fund/theses/{thesis_id}")
def get_thesis(thesis_id: str):
    try:
        return _theses.get(thesis_id)
    except ThesisError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/theses/{thesis_id}")
def update_thesis(thesis_id: str, req: ThesisUpdateRequest):
    try:
        return _theses.update(thesis_id, req.patch, actor=req.actor)
    except ThesisError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/theses/{thesis_id}/status")
def set_thesis_status(thesis_id: str, req: ThesisStatusRequest):
    try:
        return _theses.set_status(thesis_id, status=req.status, actor=req.actor, note=req.note)
    except ThesisError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/fund/theses/{thesis_id}/memos")
def list_thesis_memos(thesis_id: str):
    """Every memo drafted against a thesis (Clark's written case)."""
    return {"memos": _memos.list(thesis_id=thesis_id)}


@router.post("/fund/theses/{thesis_id}/postmortem")
def record_postmortem(thesis_id: str, req: PostmortemRequest):
    """Close the loop: grade the thesis vs. outcome and record realized P&L."""
    try:
        return _postmortem.record(
            thesis_id, verdict=req.verdict, actor=req.actor,
            what_happened=req.what_happened, lessons=req.lessons,
        )
    except ThesisError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PostmortemError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/theses/{thesis_id}/postmortem")
def get_postmortem(thesis_id: str):
    pm = _postmortem.get(thesis_id)
    if pm is None:
        raise HTTPException(status_code=404, detail=f"no post-mortem for thesis {thesis_id}")
    return pm


# --- memos (the written case for a trade, drafted against a thesis) ---------
@router.post("/fund/memos")
def create_memo(req: MemoCreateRequest):
    body = req.model_dump()
    try:
        _theses.get(req.thesis_id)  # a memo must reference a real thesis
    except ThesisError:
        raise HTTPException(status_code=404, detail=f"unknown thesis {req.thesis_id}")
    try:
        return _memos.create(body, actor=req.actor)
    except MemoError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/memos")
def list_memos(thesis_id: str | None = Query(None)):
    return {"memos": _memos.list(thesis_id=thesis_id)}


@router.get("/fund/memos/{memo_id}")
def get_memo(memo_id: str):
    try:
        return _memos.get(memo_id)
    except MemoError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/memos/{memo_id}")
def update_memo(memo_id: str, req: MemoUpdateRequest):
    try:
        return _memos.update(memo_id, req.patch, actor=req.actor)
    except MemoError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/memos/{memo_id}/finalize")
def finalize_memo(memo_id: str, req: MemoFinalizeRequest):
    """Human signs off — the memo becomes the record of decision."""
    try:
        return _memos.finalize(memo_id, actor=req.actor)
    except MemoError as e:
        raise HTTPException(status_code=404, detail=str(e))


# --- risk analytics (concentration + scenario shocks; read-only) ------------
@router.get("/fund/risk/analytics")
def get_risk_analytics():
    """Concentration, cash buffer, HHI, breach flags and default stress scenarios."""
    return _risk.analytics()


@router.post("/fund/risk/shock")
def run_risk_shock(req: RiskShockRequest):
    """Reprice a symbol (or the whole book) by a percent move — a what-if on NAV."""
    return _risk.shock(req.symbol, req.pct)


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

    # Layered cake: roll each container strategy up over its descendants. A
    # strategy can belong to *multiple* parents (many-to-many), so it rolls into
    # each parent it composes into.
    by_id = {r["strategy_id"]: r for r in rows}
    children: dict[str, list[str]] = {}
    for r in rows:
        for pid in (r.get("parents") or ([r["parent_id"]] if r.get("parent_id") else [])):
            if pid in by_id:
                children.setdefault(pid, []).append(r["strategy_id"])

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
def get_bars(symbol: str = Query(..., min_length=1, max_length=12),
             lookback_days: int = Query(180, gt=1, le=2000),
             start_date: str | None = Query(None), end_date: str | None = Query(None)):
    """Free daily bars for a symbol (crypto→CoinGecko, else Alpaca/Yahoo) — for charts."""
    try:
        bars = fetch_daily_bars(symbol, lookback_days=lookback_days, start=start_date, end=end_date)
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
        bars = fetch_daily_bars(req.symbol, lookback_days=req.lookback_days,
                                start=req.start_date, end=req.end_date)
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


@router.post("/fund/strategies/{strategy_id}/optimize")
def optimize_strategy(strategy_id: str, req: StrategyOptimizeRequest):
    try:
        strat = _strategies.get(strategy_id)
        assets = strat.get("assets", [])
        if not assets:
            return {}
        opt_result = optimize_portfolio(assets, lookback_days=req.lookback_days, method=req.method)
        return opt_result
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Optimization failed: {e}")


class SimulationRequest(BaseModel):
    scenario: Optional[str] = None
    crude_oil_price: Optional[float] = None
    yield_10y_bps: Optional[float] = None
    market_shock_pct: Optional[float] = None
    vix_spike_pct: Optional[float] = None
    crypto_shock_pct: Optional[float] = None


@router.post("/fund/risk/simulate")
def simulate_risk(req: SimulationRequest):
    """Run counterfactual macro factor stress test against live fund holdings."""
    return _simulator.simulate(
        scenario=req.scenario,
        crude_oil_price=req.crude_oil_price,
        yield_10y_bps=req.yield_10y_bps,
        market_shock_pct=req.market_shock_pct,
        vix_spike_pct=req.vix_spike_pct,
        crypto_shock_pct=req.crypto_shock_pct,
    )


@router.get("/fund/sentinel/signals")
def get_sentinel_signals():
    """Get active Clark Sentinel Alpha Radar signals."""
    return {"signals": _sentinel.get_signals()}


@router.post("/fund/sentinel/scan")
def scan_sentinel(symbol: Optional[str] = Query(None)):
    """Trigger autonomous Alpha Radar scan across multi-modal feeds."""
    return _sentinel.scan(force_trigger_symbol=symbol)


@router.get("/fund/risk/pairs")
def get_pair_trade_signals():
    """Scan statistical arbitrage pair trade opportunities."""
    return _pair_arb.get_summary()


@router.get("/fund/risk/macro-regime")
def get_macro_regime():
    """Classify current global macro regime and risk conviction modifier."""
    return _macro_regime.get_regime_summary()


@router.post("/fund/strategies/{strategy_id}/rename")
def rename_strategy(strategy_id: str, req: StrategyRenameRequest):
    try:
        return _strategies.rename(strategy_id, name=req.name, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/archive")
def archive_strategy(strategy_id: str, req: StrategyArchiveRequest):
    try:
        return _strategies.archive(strategy_id, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/parents")
def add_strategy_parent(strategy_id: str, req: StrategyParentRequest):
    """Compose this strategy into another parent (many-to-many)."""
    try:
        return _strategies.add_parent(strategy_id, parent_id=req.parent_id, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/strategies/{strategy_id}/parents/remove")
def remove_strategy_parent(strategy_id: str, req: StrategyParentRequest):
    try:
        return _strategies.remove_parent(strategy_id, parent_id=req.parent_id, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


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


@router.post("/fund/strategies/{strategy_id}/assets")
def set_strategy_assets(strategy_id: str, req: StrategyAssetsRequest):
    """Set (replace) the asset universe this strategy scopes."""
    try:
        return _strategies.set_assets(strategy_id, symbols=req.symbols, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/fund/strategies/{strategy_id}/risk")
def get_strategy_risk(strategy_id: str):
    """Per-asset and strategy-level concentration + shock analytics."""
    try:
        s = _strategies.get(strategy_id)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    attr = {a["strategy_id"]: a for a in _attribution.with_values(_connector.price)}
    return _risk.strategy_analytics(s, attr.get(strategy_id), _connector.price)


@router.get("/fund/strategies/{strategy_id}/bars")
def get_strategy_bars(strategy_id: str,
                     lookback_days: int = Query(180, gt=1, le=2000)):
    """Daily bars for every asset scoped into this strategy — powers sparkline charts."""
    try:
        s = _strategies.get(strategy_id)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    assets = s.get("assets") or []
    result = {}
    for sym in assets:
        try:
            bars = fetch_daily_bars(sym, lookback_days=lookback_days)
            result[sym] = {"closes": bars.closes, "dates": bars.dates,
                           "source": bars.source, "start": bars.start, "end": bars.end}
        except BarsError as e:
            result[sym] = {"error": str(e)}
    return {"strategy_id": strategy_id, "assets": assets, "bars": result}


# --- risk engine & monitoring ----------------------------------------------
@router.get("/fund/risk/monitor")
def get_risk_monitor():
    """Pure read of the current full risk picture (observability pane)."""
    return _monitor.assess()


@router.get("/fund/risk/alerts")
def get_risk_alerts():
    """Active (currently open) risk alarms."""
    return {"active": _control.active_alarms()}


@router.get("/fund/risk/alerts/history")
def get_risk_alert_history(limit: int = Query(100, ge=1, le=1000)):
    """Recent alarm events history."""
    return {"history": _control.alarm_history(limit=limit)}


@router.post("/fund/risk/monitor/run")
def run_risk_monitor(req: RiskRunRequest):
    """Periodic worker tick / manual run to evaluate alarms and auto-halt if critical breach."""
    return _monitor.run(actor=req.actor)


@router.get("/fund/risk/limits")
def get_risk_limits():
    """Current risk limits configuration."""
    return _control.limits().to_dict()


@router.post("/fund/risk/limits")
def set_risk_limits(req: RiskLimitsPatchRequest):
    """Patch risk limits configuration."""
    return _control.set_limits(req.patch, actor=req.actor).to_dict()


@router.post("/fund/risk/halt")
def halt_trading(req: RiskHaltRequest):
    """Engage trading kill-switch halt."""
    return _control.halt(reason=req.reason, actor=req.actor)


@router.post("/fund/risk/resume")
def resume_trading(req: RiskResumeRequest):
    """Resume trading after halt (human only)."""
    return _control.resume(actor=req.actor)


def run_risk_monitor_tick(actor: str = "worker") -> dict:
    """Worker tick function to execute the risk monitor."""
    return _monitor.run(actor=actor)

