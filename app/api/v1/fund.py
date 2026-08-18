"""Fund harness API — the spine's HTTP surface.

Order path (venue-agnostic, human-gated): propose → risk gate → approve/decline
→ idempotent execution. Ledger path (LP-facing): subscribe/redeem with a
two-phase confirm, minting/burning units at NAV. Read routes expose NAV,
positions, per-LP holdings, and the audit event log.

The pipeline is wired to the PaperConnector today; swapping in the IBKRConnector
(Step 2) changes only the construction block below.
"""

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel

from app.fund.connectors.alpaca import AlpacaConnector
from app.fund.connectors.base import Order, Side
from app.fund import tearsheet
from app.fund.backtest import CostModel, SimpleBacktester, signals_for
from app.fund.execution import ExecutionHistory, summarise
_log = logging.getLogger(__name__)

from app.fund.custody import CustodyIngest
from app.fund.signals import SignalRunner
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
from app.core.firebase import active_book as _active_book
from app.core.firebase import is_production
from app.fund.backfill import BrokerBackfill
from app.fund.intraday import IntradayNav
from app.fund.rebalance import RebalanceError, RebalanceService
from app.fund.factors import FactorModel
from app.fund.riskengine import AdvancedRiskEngine
from app.fund.riskmonitor import RiskControl, RiskMonitor
from app.fund.simulation import CounterfactualSimulator
from app.fund.strategies import StrategyError, StrategyService
from app.fund.thesis import ThesisError, ThesisService
from app.schemas.fund import (
    ActorRequest,
    ApprovalRequest,
    BacktestBySymbolRequest,
    CustodyApplyRequest,
    SignalRunRequest,
    BacktestResultRequest,
    BacktestRunRequest,
    MemoCreateRequest,
    MemoFinalizeRequest,
    MemoUpdateRequest,
    PostmortemRequest,
    ExternalSignalRequest,
    LeanAlgorithmRequest,
    LeanBacktestRequest,
    LeanLiveRequest,
    LeanSweepRequest,
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
    ThesisGenerateRequest,
    ThesisPromoteRequest,
    ThesisRecommendationRequest,
    StrategyOptimizeRequest,
    StrategyMemberRequest,
    StrategyMemberWeightsRequest,
    StrategyComposeWeightsRequest,
)
from app.fund.thesis_generator.service import ThesisGeneratorService
from app.fund.recommendation import RecommendationError, build_thesis_trade_recommendation

from app.fund.optimization import optimize_portfolio, optimize_return_streams

logger = logging.getLogger(__name__)

router = APIRouter()

# --- spine wiring (single place to swap the venue) -------------------------
# Alpaca when configured, else the in-Firestore paper venue. Same protocol.
def _live_price_fn():
    """Live marks unconditionally — mock mode wants real prices behind fake fills."""
    from app.fund.marketdata import live_price
    return live_price


def _paper_live_pricer():
    """Live free marks for the paper venue when FUND_LIVE_MARKS is truthy."""
    if os.getenv("FUND_LIVE_MARKS", "false").lower() in ("1", "true", "yes"):
        from app.fund.marketdata import live_price
        return live_price
    return None


def _mock_mode() -> bool:
    return os.getenv("USE_FAKE_FIRESTORE", "").lower() in ("1", "true", "yes")


def _real_broker() -> bool:
    """Route orders to the real venue even while the ledger is local.

    The two decisions — where state lives, and where orders go — are separate,
    and conflating them meant you could not do the one thing that actually
    proves the system works: place real orders and watch them fill, without
    writing to the production ledger. This flag splits them.
    """
    return (os.getenv("FUND_REAL_BROKER", "").lower() in ("1", "true", "yes")
            and bool(os.getenv("ALPACA_API_KEY")))


# Mock mode normally uses the paper venue even when Alpaca credentials exist:
# routing mock fills to the real broker leaves them queued until the market
# opens, so the book never moves and the point of the mock is lost. Fills are
# simulated; the prices they fill at are real (live_pricer).
#
# FUND_REAL_BROKER=1 overrides that for live-flow testing: orders go to Alpaca
# for real, the ledger stays local.
_connector = (
    AlpacaConnector()
    if _real_broker()
    else (
        PaperConnector(live_pricer=_paper_live_pricer() or _live_price_fn())
        if _mock_mode()
        else (
            AlpacaConnector()
            if os.getenv("ALPACA_API_KEY")
            else PaperConnector(live_pricer=_paper_live_pricer())
        )
    )
)
_store = EventStore()
# Snapshotted on Firestore: without it every read folds the entire event log,
# which is O(all history) per request and exhausted the read quota (429).
#
# NOT snapshotted on Postgres, deliberately. The snapshot store is a cache
# whose only justification was that reading the log was expensive; folding 155
# events out of Postgres takes 40 milliseconds, so the cache buys nothing and
# costs a write every fifty events. Worse, it kept the read path anchored to
# Firestore after the ledger had left: with the quota exhausted, every snapshot
# read failed through gRPC retries and a single NAV request took FIFTY-SEVEN
# SECONDS — long enough that Clark's own tools timed out and reported the fund
# unreachable while Postgres sat there answering in milliseconds.
from app.fund.events import store_backend
if store_backend() == "postgres":
    _snapshots = None
else:
    from app.fund.snapshots import SnapshotStore
    _snapshots = SnapshotStore()
_projection = PositionsProjection(_store, snapshots=_snapshots)
_nav = NavService(pricer=_connector.price, store=_store, projection=_projection)
_pipeline = CommandPipeline(connector=_connector, nav_service=_nav, store=_store)
_ledger = LedgerService(nav_service=_nav, store=_store)
_holdings = HoldingsProjection(_store, snapshots=_snapshots)
_strategies = StrategyService(store=_store)
_theses = ThesisService(store=_store)
_memos = MemoService(store=_store)
_thesis_generator = ThesisGeneratorService(store=_store, thesis_service=_theses, memo_service=_memos)
_risk = RiskAnalytics(nav_service=_nav)
_postmortem = PostmortemService(store=_store, pricer=_connector.price)
_attribution = StrategyAttribution(_store, snapshots=_snapshots)
_orders = OrdersProjection(_store, snapshots=_snapshots)
_reconciler = Reconciler(connector=_connector, store=_store, projection=_projection,
                         nav_service=_nav)
_control = RiskControl(store=_store)
_monitor = RiskMonitor(nav_service=_nav, store=_store, pricer=_connector.price,
                       attribution=_attribution, strategies=_strategies, control=_control)
_riskengine = AdvancedRiskEngine(nav_service=_nav, pricer=_connector.price,
                                 attribution=_attribution, strategies=_strategies)
_factor_model = FactorModel()
_intraday = IntradayNav()
_rebalance = RebalanceService(nav_service=_nav, pricer=_connector.price,
                              attribution=_attribution, strategies=_strategies,
                              pipeline=_pipeline, control=_control,
                              risk_engine=_riskengine, store=_store)
_simulator = CounterfactualSimulator(nav_service=_nav, positions_projection=_projection, strategy_service=_strategies)


# --- worker hooks (called by endpoints and the scheduled worker) -----------
def sample_intraday_nav() -> dict:
    """Record one intraday NAV point. Cheap, in-memory, never an event."""
    snap = _nav.compute()
    took = _intraday.sample(
        nav_usd=float(snap.total_nav_usd),
        nav_per_unit=float(snap.nav_per_unit) if snap.nav_per_unit is not None else None,
        cash_usd=float(snap.breakdown.get("cash", 0)),
    )
    return {"sampled": took, "n": len(_intraday)}


def run_settlement() -> dict:
    """Poll in-flight orders to terminal — the async fill tick."""
    return _pipeline.poll_open_orders()


# --- live fill stream ------------------------------------------------------
# Kept beside the poller it complements, not hidden in main.py: whether fills
# arrive by push or by poll is a property of the fund's write path.
_trade_stream: "TradeStream | None" = None


def start_trade_stream():
    """Subscribe to venue trade updates. Returns the task, or None.

    Refuses on anything but a real, keyed Alpaca connector: the paper/mock
    connector has no socket to listen to, and pretending otherwise would report
    a healthy stream that can never deliver anything.
    """
    global _trade_stream
    import asyncio

    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        _log.warning("trade stream: no Alpaca credentials — polling only")
        return None
    if _connector.name != "alpaca":
        _log.warning("trade stream: venue is %r, not alpaca — polling only", _connector.name)
        return None

    from app.fund.tradestream import TradeStream

    paper = os.getenv("ALPACA_PAPER", "true").lower() not in ("0", "false", "no")
    _trade_stream = TradeStream(_pipeline, key, secret, paper=paper)
    return asyncio.create_task(_trade_stream.run())


def stop_trade_stream() -> None:
    if _trade_stream is not None:
        _trade_stream.stop()


def trade_stream_state() -> dict:
    """What the live stream is doing, for anyone reporting whether it works."""
    if _trade_stream is None:
        return {"enabled": False,
                "reason": "ENABLE_TRADE_STREAM is off — fills arrive by polling"}
    return _trade_stream.state()


def run_reconcile() -> dict:
    """Event book vs. venue truth."""
    return _reconciler.run()


def run_strike() -> dict:
    """Strike and persist a NAV snapshot."""
    return _nav.strike().to_dict()


def run_universe_refresh() -> dict:
    """Re-measure the tradable universe if it has gone stale.

    Cheap to call and mostly a no-op: it checks the age first and only spends
    the 50 seconds when the screen is actually due. That matters because the
    scheduler ticks every thirty seconds and this must not become a minute of
    work per tick.

    Touches no event log and holds no fund state — the universe is a
    measurement of the market, not a fact about the fund — so a failure here
    is logged and dropped rather than allowed near the ledger.
    """
    u = _universe()
    if u is None:
        return {"skipped": "universe needs FUND_STORE=postgres"}
    from app.fund.universe import needs_refresh
    fresh = u.freshness()
    if not needs_refresh(fresh.get("age_hours")):
        return {"skipped": "still fresh", **fresh}
    logger.info("universe refresh starting (age %sh)", fresh.get("age_hours"))
    out = u.refresh()
    logger.info("universe refreshed: %s", out)
    return out


#: How often durability is pushed to Firestore. Hourly: the snapshot exists so
#: that losing this machine costs at most an hour of events, and pushing more
#: often buys little while pushing less often quietly widens that window.
SNAPSHOT_EVERY_MINUTES = float(os.getenv("FUND_SNAPSHOT_EVERY_MINUTES", "60"))


def run_snapshot() -> dict:
    """Push new events to Firestore if the last push has aged out.

    The snapshot was BUILT and never SCHEDULED, which is the worst of the three
    possible states: an unscheduled backup still answers when you ask it, still
    reports a watermark, and is quietly describing a durability guarantee the
    fund does not have. A backup nobody runs is a story about a backup.

    Same shape as the universe tick — checks the clock first and is almost
    always a no-op, because this runs every thirty seconds. Failures are logged
    and dropped: the snapshot is a copy, and a copy that cannot be written must
    never be able to disturb the ledger it is copying.
    """
    if store_backend() != "postgres":
        return {"skipped": "the snapshot copies FROM postgres"}
    try:
        from app.fund.snapshot_firestore import FirestoreSnapshotter
        snap = FirestoreSnapshotter(pg_store=_store)
        st = snap.status()
        last = st.get("last_run_at")
        if last:
            age_min = (datetime.now(timezone.utc)
                       - datetime.fromisoformat(last)).total_seconds() / 60.0
            if age_min < SNAPSHOT_EVERY_MINUTES:
                return {"skipped": "recent", "age_minutes": round(age_min, 1),
                        **st}
        if not st.get("behind_by"):
            return {"skipped": "nothing new to snapshot", **st}
        logger.info("snapshot starting — %s events behind", st.get("behind_by"))
        out = snap.run()
        logger.info("snapshot pushed: %s", out)
        return out
    except Exception as e:  # noqa: BLE001
        logger.warning("snapshot skipped: %s", e)
        return {"skipped": f"{type(e).__name__}: {e}"[:200]}


@router.post("/fund/snapshot/run")
def snapshot_run(dry_run: bool = Query(False)):
    """Push durability now, ignoring the hourly clock.

    Exists because the snapshot can only be exercised in-process: opening a real
    Firestore client from a script is refused while the fake store is installed,
    and rightly so. Without a trigger the only way to check that durability
    works was to wait for the interval — which is how it went unnoticed that it
    did not work at all.

    Copies events; writes nothing to the ledger and moves no money.
    """
    if store_backend() != "postgres":
        raise HTTPException(status_code=503,
                            detail="the snapshot copies FROM postgres")
    from app.fund.snapshot_firestore import FirestoreSnapshotter
    try:
        return FirestoreSnapshotter(pg_store=_store).run(dry_run=dry_run)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}"[:300])


@router.get("/fund/snapshot/status")
def snapshot_status():
    """How far behind durability is, and when it last succeeded.

    Surfaced because "behind by N events" is the actual recovery-point objective,
    and a number nobody can read is a number nobody checks.
    """
    if store_backend() != "postgres":
        raise HTTPException(status_code=503,
                            detail="the snapshot copies FROM postgres")
    from app.fund.snapshot_firestore import FirestoreSnapshotter
    try:
        st = FirestoreSnapshotter(pg_store=_store).status()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"{type(e).__name__}: {e}")
    st["every_minutes"] = SNAPSHOT_EVERY_MINUTES
    return st


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


@router.get("/fund/fees")
def get_fees():
    """The mandate's fee terms and what is currently accrued against them.

    ``terms_recorded: false`` is the important one — it means nobody has
    decided, which reads identically to "we charge nothing" on every screen
    until someone asks.
    """
    from app.fund.fees import FeeLedger

    return FeeLedger(_store).state()


class FeeTermsRequest(BaseModel):
    management_annual_pct: float = 0.0
    performance_pct: float = 0.0
    initial_high_water: float = 1.0
    note: str = ""
    actor: str = "operator"


@router.post("/fund/fees/terms")
def set_fee_terms(req: FeeTermsRequest):
    """Record the fee schedule. A zero is a decision and belongs in the log."""
    from app.fund.fees import FeeLedger, FeeTerms

    terms = FeeTerms(
        management_annual_pct=req.management_annual_pct,
        performance_pct=req.performance_pct,
        initial_high_water=req.initial_high_water,
        note=req.note,
    )
    return FeeLedger(_store).set_terms(terms, actor=req.actor)


@router.post("/fund/fees/accrue")
def accrue_fees(req: ActorRequest | None = None):
    """Book fees earned since the last accrual. No-op when the terms are zero."""
    from app.fund.fees import FeeLedger

    nav = _nav.compute()
    # The gross book, before the liability this call is about to add to.
    gross = nav.total_nav_usd + FeeLedger(_store).outstanding()
    return FeeLedger(_store).accrue(
        gross_nav=gross, units_outstanding=nav.units_outstanding,
        actor=(req.actor if req else "system"),
    )


@router.get("/fund/ledger/verify")
def verify_ledger_chain(limit: int = Query(100_000, ge=1)):
    """Walk the hash chain and report the first link that does not hold.

    Append-only is a description of how we write, not a property an auditor can
    check. This is the check. A break means an event was altered, inserted or
    removed after it was written — or, less dramatically, that two processes
    appended at once (see the scheduler-lease task).
    """
    return _store.verify_chain(limit=limit)


@router.get("/fund/tca")
def get_transaction_costs(limit: int = Query(500, ge=1, le=5000)):
    """What trading actually cost, against what the backtests assumed.

    Folded from the order lifecycle already in the log, so it applies
    retroactively to every order the fund has placed. Until this is measured,
    every Sharpe ratio in the system describes an assumption rather than a
    strategy.
    """
    from app.fund.tca import TransactionCosts

    tca = TransactionCosts(_store)
    rows = tca.costs(limit=limit)
    from app.fund.tca import summarise
    return {
        "summary": summarise(rows),
        "by_strategy": tca.by_strategy(limit=limit),
        "orders": [r.to_dict() for r in rows],
    }


@router.get("/fund/session")
def get_market_session():
    """The venue's session — state, phase, and the countdown to the next change.

    Polled by the UI, so it carries a short cache. The connector's
    ``market_open()`` stays deliberately uncached for the trade path, where
    being a few seconds stale at the bell is a real error; a countdown that is
    ten seconds behind is not.
    """
    from app.fund.session import unknown

    probe = getattr(_connector, "session", None)
    if probe is None:
        # A simulated venue has no session. Saying so beats inventing one.
        return {
            **unknown("simulated venue — no exchange session").to_dict(),
            "simulated": True,
        }
    return {**_session_cache(probe).to_dict(), "simulated": False}


_SESSION_TTL_SECONDS = 10.0
_session_hit: dict[str, Any] = {"at": 0.0, "value": None}


def _session_cache(probe):
    """Ten-second memo, so UI polling does not become a clock-fetch per client."""
    import time as _time

    now = _time.time()
    if _session_hit["value"] is not None and now - _session_hit["at"] < _SESSION_TTL_SECONDS:
        return _session_hit["value"]
    value = probe()
    _session_hit.update({"at": now, "value": value})
    return value


@router.get("/fund/compliance")
def get_compliance_status():
    """The externally-imposed constraints the fund is currently operating under.

    Separate from /fund/risk because these are not the mandate's choices. The
    day-trade budget in particular is a cliff rather than a slope: the fourth
    day trade in five sessions restricts a sub-$25k account to closing-only for
    ninety days, so the number that matters is how many are left, and it has to
    be visible before an order is proposed rather than at the rejection.
    """
    from app.fund.compliance import (
        PDT_EQUITY_THRESHOLD,
        PDT_MAX_DAY_TRADES,
        AccountState,
        DayTradeLedger,
    )

    if hasattr(_connector, "account_state"):
        try:
            account = _connector.account_state()
        except Exception as e:  # noqa: BLE001
            account = AccountState.unknown(str(e))
    else:
        account = AccountState.unknown("simulated venue — no brokerage account")

    own = DayTradeLedger(_store).count()
    broker = account.daytrade_count
    used = broker if broker is not None else own
    equity = account.equity
    # The rule only restricts accounts below the threshold. Unknown equity is
    # not known to be above it.
    applies = equity is None or equity < PDT_EQUITY_THRESHOLD

    return {
        "account": account.to_dict(),
        "pdt": {
            "applies": applies,
            "equity_threshold": PDT_EQUITY_THRESHOLD,
            "max_day_trades": PDT_MAX_DAY_TRADES,
            "used": used,
            "remaining": max(PDT_MAX_DAY_TRADES - 1 - used, 0) if applies else None,
            "broker_count": broker,
            "our_count": own,
            "source": "broker" if broker is not None else "our event log",
            "diverges": broker is not None and broker != own,
        },
    }


@router.get("/fund/book")
def get_book_identity():
    """Which Firestore project this process is reading and writing.

    The ledger is append-only, so operating against the wrong book is a
    permanent mistake. This makes the active book checkable from outside.
    """
    try:
        from app.core.firebase import active_book
        info = active_book()
    except Exception:
        info = {"project_id": "unknown", "env": "unknown"}
    # Where state lives and where ORDERS go are separate facts, and "mock" must
    # never hide that real orders are leaving the building. Report both.
    venue = getattr(_connector, "name", "unknown")
    return {**info,
            "is_production": info.get("env") == "production",
            "venue": venue,
            "orders_are_real": bool(_real_broker()),
            "seeder_may_run": bool(_mock_mode() and not _real_broker()),
            # How fills reach the ledger. A silently dead stream looks exactly
            # like a quiet market, so its state is reported rather than assumed.
            "fill_stream": trade_stream_state()}


@router.get("/fund/market/quotes")
def get_market_quotes(symbols: str | None = Query(None, description="Comma-separated override")):
    """Live quotes for the fund's universe — everything held, plus assets scoped
    to a live strategy.

    Prices come from market data, not the ledger, so an explicit ``symbols`` list
    is answerable even when the event log is unavailable — that is what keeps the
    research loop and the ticker alive during a datastore outage. Without it we
    must read the book to know what the fund cares about; if that read fails we
    say the universe is unknown rather than implying the fund holds nothing.
    """
    from app.fund import quotes as _quotes

    if symbols:
        wanted = [s.strip().upper() for s in symbols.split(",") if s.strip()][:24]
        return _quotes.build([], [{"assets": wanted, "archived": False}])

    try:
        nav = _nav.compute()
        positions = [
            {"symbol": p["symbol"], "qty": f(p["qty"]), "value_usd": f(p["usd_value"]),
             "weight_pct": round(100.0 * float(p["usd_value"]) / float(nav.total_nav_usd), 4)
                           if float(nav.total_nav_usd) else 0.0}
            for p in (nav.positions or [])
        ]
        strategies = _strategies.list()
    except Exception as e:
        return {"quotes": [], "held_count": 0, "watch_count": 0, "unpriced": [],
                "universe_known": False,
                "reason": f"cannot read the fund's universe: {type(e).__name__}"}

    out = _quotes.build(positions, strategies)
    out["universe_known"] = True
    return out


@router.get("/fund/nav")
def get_nav():
    """Live (unstruck) valuation, the last struck snapshot, and the
    since-inception score — NAV against net external cash, and the
    flow-proof per-unit return. NAV alone answers "what is it worth";
    this answers "has it made anything", which is the first question
    every operator and LP actually asks."""
    snap = _nav.compute()
    return {
        "live": snap.to_dict(),
        "last_struck": _nav.latest(),
        "since_inception": _nav.since_inception(snap),
    }


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
    """The audit trail, newest first — the TAIL of the log, not its head.

    This route used to be declared twice in this file, and FastAPI keeps the
    first: a dead twin below promised "newest first" while callers actually
    received the oldest ``limit`` events in ascending order. Every live feed
    therefore rendered the bootstrap sequence and computed staleness from a
    two-day-old event while fresh ones went unshown. One route now, doing
    what the dead one said.
    """
    raw = _store.stream(since_seq=since_seq, limit=100_000)
    return {"events": list(reversed(raw[-limit:]))}


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


@router.get("/fund/executions")
def get_executions(strategy_id: str | None = Query(None),
                   limit: int = Query(500, ge=1, le=2000)):
    """Fills and closed round-trips, folded from the event log.

    The blotter above shows order *lifecycle* rows. This shows what those fills
    did: each sale matched against the running average cost, with the P&L it
    realized, so an operator can see when a strategy sold and whether it was
    right — and see the distribution rather than one pooled number.

    Read-only and derived; it writes nothing and adds no state.
    """
    hist = ExecutionHistory(_store)
    if strategy_id:
        return hist.for_strategy(strategy_id, limit=limit)
    rows = hist.all(limit=limit)
    return {
        "strategies": rows,
        "totals": summarise([t for r in rows for t in r.get("round_trips", [])]),
    }


def _signal_runner() -> SignalRunner:
    conn = _connector
    return SignalRunner(
        strategies=_strategies, nav=_nav, pipeline=_pipeline,
        pricer=conn.price,
        pending_lookup=lambda: _orders.history(limit=200),
        market_open=getattr(conn, "market_open", None),
        # Shares the endpoint's ten-second memo, so a signal run and the UI's
        # session poll do not each cost a clock fetch.
        session=(lambda: _session_cache(conn.session)) if hasattr(conn, "session") else None,
    )


@router.get("/fund/custody/plan")
def plan_custody(after: str | None = Query(None, description="ISO date; only activities after it")):
    """What the broker did to the book that our ledger has not recorded.

    Dividends and interest arrive without an order, so nothing in the order path
    can ever account for them. Left uningested they show up only as NAV drift
    against broker equity that never resolves.

    Read-only.
    """
    try:
        return CustodyIngest(_connector, _store).plan(after=after)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/fund/custody/apply")
def apply_custody(req: CustodyApplyRequest):
    """Append the missing custody events. Idempotent by the venue's activity id.

    Writes to the append-only ledger, so it requires ``confirm=true`` and refuses
    outright against production — the same guard the venue backfill carries.
    """
    if is_production():
        raise HTTPException(
            status_code=403,
            detail="refusing to write custody events against the production book",
        )
    if not req.confirm:
        raise HTTPException(status_code=422, detail="pass confirm=true to write events")
    try:
        return CustodyIngest(_connector, _store).apply(after=req.after, actor=req.actor)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/fund/signals")
def get_signals():
    """What every live strategy currently wants. Writes nothing, proposes nothing.

    This is the read that was missing: strategies had allocations and universes
    but no mechanism ever evaluated them, so 'what does the book want to do
    right now' had no answer.
    """
    return {"decisions": [d.to_dict() for d in _signal_runner().evaluate()]}


@router.post("/fund/signals/run")
def run_signals(req: SignalRunRequest):
    """Evaluate the live strategies and PROPOSE the orders their signals imply.

    Proposals only. Each one passes the venue check and the risk gate and then
    waits for a human to approve it — there is no path from here to execution,
    by construction. ``dry_run`` defaults to true, so calling this without
    arguments shows what would be proposed and touches nothing.
    """
    return _signal_runner().run(actor=req.actor, dry_run=req.dry_run)


@router.get("/fund/executions/chart")
def get_execution_chart(symbol: str = Query(..., min_length=1, max_length=12),
                        strategy_id: str | None = Query(None),
                        lookback_days: int = Query(180, ge=5, le=2000)):
    """OHLC bars for a symbol with our own fills placed on them.

    The chart an operator wants when asking "why did it sell there": the candles
    the decision was made against, and the buy/sell marks that actually
    happened. Marks come from the event log, never from signals — a signal that
    did not become a fill is not a trade.

    Fills are snapped to the trading DAY, because the bars are daily. An
    intraday fill sits on the bar containing it rather than being interpolated
    between bars.
    """
    try:
        bars = fetch_daily_bars(symbol, lookback_days=lookback_days)
    except BarsError as e:
        raise HTTPException(status_code=422, detail=str(e))

    sym = symbol.strip().upper()
    hist = ExecutionHistory(_store)
    rows = [hist.for_strategy(strategy_id)] if strategy_id else hist.all()

    dates = bars.dates or []
    first, last = (dates[0] if dates else None), (dates[-1] if dates else None)

    marks, trips = [], []
    for r in rows:
        for f in r.get("fills", []):
            if (f.get("symbol") or "").upper() != sym:
                continue
            day = (f.get("ts") or "")[:10] or None
            marks.append({
                "date": day,
                # An honest flag: a fill outside the fetched window has no bar to
                # sit on, and silently dropping it would understate the activity.
                "in_window": bool(day and first and last and first <= day <= last),
                "side": f.get("side"), "qty": f.get("qty"), "price": f.get("price"),
                "strategy_id": r.get("strategy_id"), "ts": f.get("ts"),
            })
        for t in r.get("round_trips", []):
            if (t.get("symbol") or "").upper() == sym:
                trips.append({**t, "strategy_id": r.get("strategy_id")})

    marks.sort(key=lambda m: m.get("ts") or "")
    return {
        "symbol": bars.symbol,
        "source": bars.source,
        "adjusted": bars.adjusted,
        "adjustment": bars.adjustment,
        "bars": {
            "dates": dates, "open": bars.opens, "high": bars.highs,
            "low": bars.lows, "close": bars.closes, "volume": bars.volumes,
            # Close-only sources exist; say so rather than faking flat candles.
            "has_ohlc": bars.opens is not None,
            "start": bars.start, "end": bars.end,
        },
        "fills": marks,
        "n_fills_outside_window": sum(1 for m in marks if not m["in_window"]),
        "round_trips": trips,
    }


@router.get("/fund/orders/{order_id}")
def get_order(order_id: str):
    events = _store.by_aggregate(order_id)
    if not events:
        raise HTTPException(status_code=404, detail=f"unknown order {order_id}")
    return {"order_id": order_id, "events": events}


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
        rationale=req.rationale,
        critique=req.critique,
    )
    return _pipeline.propose_order(order, actor=req.actor)


# --- LEAN orchestration ------------------------------------------------------
# The engine as a harness service: algorithms live in the workspace, backtests
# run as async Docker jobs, results come back in the fund's vocabulary. Lazy
# singleton — the workspace dir is created on first use, not at import.
_bars_archive = None


def _barstore():
    """The point-in-time bar archive, or None when there is nowhere to put it.

    Postgres-only by design: the archive's value is that a first observation is
    never overwritten, which needs a real primary key and a transaction. There
    is no Firestore fallback because a half-kept archive is worse than none —
    it would answer as_of queries with gaps it could not describe.
    """
    global _bars_archive
    if _bars_archive is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.barstore import BarStore
        _bars_archive = BarStore()
    return _bars_archive


_leanrunner = None


def _lean():
    global _leanrunner
    if _leanrunner is None:
        from app.fund.leanrunner import LeanRunner
        _leanrunner = LeanRunner()
    return _leanrunner


@router.post("/fund/lean/algorithms")
def lean_save_algorithm(req: LeanAlgorithmRequest):
    """Save (or overwrite) a LEAN algorithm — the Lab IDE's save button."""
    from app.fund.leanrunner import LeanError
    try:
        return _lean().save_algorithm(req.name, req.code)
    except LeanError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/lean/algorithms")
def lean_list_algorithms():
    return {"algorithms": _lean().list_algorithms()}


@router.get("/fund/lean/algorithms/{name}")
def lean_get_algorithm(name: str):
    from app.fund.leanrunner import LeanError
    try:
        return _lean().get_algorithm(name)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/lean/backtests")
def lean_submit_backtest(req: LeanBacktestRequest):
    """Run a saved algorithm through the engine. Async: poll the job."""
    from app.fund.leanrunner import LeanError
    try:
        return _lean().submit_backtest(req.algorithm, req.parameters)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/lean/sweeps")
def lean_submit_sweep(req: LeanSweepRequest):
    """Run an algorithm across a parameter grid. Async: poll the sweep.

    Answers the question a single backtest cannot: is the good result a
    plateau or an island?
    """
    from app.fund.leanrunner import LeanError
    try:
        return _lean().submit_sweep(req.algorithm, req.grid, req.holdout)
    except LeanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/lean/live")
def lean_start_live(req: LeanLiveRequest):
    """Start a supervised live LEAN session.

    The signal token is read from the environment here and never crosses this
    API in either direction — the caller names a strategy, not a credential.
    """
    from app.fund.leanrunner import LeanError
    token = os.getenv("EXTERNAL_SIGNAL_TOKEN", "")
    try:
        return _lean().start_live(req.algorithm, req.strategy_id or "",
                                  token, req.qty)
    except LeanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund/lean/live")
def lean_list_live():
    return {"sessions": _lean().live_sessions()}


@router.delete("/fund/lean/live/{session_id}")
def lean_stop_live(session_id: str):
    from app.fund.leanrunner import LeanError
    try:
        return _lean().stop_live(session_id)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))


_universe_cache = None


def _universe():
    global _universe_cache
    if _universe_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.universe import Universe
        _universe_cache = Universe()
    return _universe_cache


_factory_cache = None


def _factory():
    global _factory_cache
    if _factory_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.factory import CandidateFactory
        _factory_cache = CandidateFactory(runner=_lean())
    return _factory_cache


class CandidateRequest(BaseModel):
    algorithm: str
    grid: Dict[str, List[str]]
    holdout: Optional[Dict[str, str]] = None
    #: Observations that prompted this hypothesis. Recorded now because the
    #: link exists only at the moment someone decides to test something.
    observation_ids: Optional[List[str]] = None


@router.post("/fund/factory/candidates")
def factory_submit(req: CandidateRequest):
    """Send a candidate down the belt: sweep, hold out, verify, judge.

    Returns immediately with an id. The belt ends at a VERDICT and goes no
    further — what happens to something that clears the bar stays a human
    decision, because a factory that could deploy its own output would be a
    fund with nobody accountable for its positions.
    """
    f = _factory()
    if f is None:
        raise HTTPException(status_code=503, detail="the factory needs FUND_STORE=postgres")
    from app.fund.leanrunner import LeanError
    try:
        return f.submit(req.algorithm, req.grid, req.holdout, req.observation_ids)
    except LeanError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund/factory/candidates/{candidate_id}")
def factory_get(candidate_id: str):
    f = _factory()
    if f is None:
        raise HTTPException(status_code=503, detail="the factory needs FUND_STORE=postgres")
    out = f.get(candidate_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate {candidate_id!r}")
    return out


@router.get("/fund/factory/candidates")
def factory_history(algorithm: str | None = Query(None), limit: int = Query(50, ge=1, le=500)):
    """What has already been tried, and why it died."""
    f = _factory()
    if f is None:
        raise HTTPException(status_code=503, detail="the factory needs FUND_STORE=postgres")
    return {"scoreboard": f.scoreboard(), "candidates": f.history(algorithm, limit)}


_observations_cache = None


def _observations():
    global _observations_cache
    if _observations_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.observations import Observations
        _observations_cache = Observations()
    return _observations_cache


class ObservationSweepRequest(BaseModel):
    tickers: List[str]
    forms: List[str] = ["10-Q", "8-K"]
    since: Optional[str] = None
    per_ticker: int = 2


@router.post("/fund/research/read")
def research_read(req: ObservationSweepRequest):
    """Read filings across names and store what survives verification.

    Returns OBSERVATIONS, not trade ideas: checkable statements each carrying a
    verbatim quote that was matched against the filing before storage. Turning
    one into a position is a separate step a person takes, in the open.
    """
    o = _observations()
    if o is None:
        raise HTTPException(status_code=503, detail="research needs FUND_STORE=postgres")
    from app.fund.observations import sweep
    return sweep([t.upper() for t in req.tickers], forms=tuple(req.forms),
                 since=req.since, per_ticker=req.per_ticker, store=o)


_provenance_cache = None


def _provenance():
    global _provenance_cache
    if _provenance_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.provenance import Provenance
        _provenance_cache = Provenance()
    return _provenance_cache


class ReviewRequest(BaseModel):
    outcome: str
    note: Optional[str] = None
    actor: str = "operator"


@router.post("/fund/research/observations/{observation_id}/review")
def research_review(observation_id: str, req: ReviewRequest):
    """Record that a human saw this and decided something.

    A dismissal and an unread look identical in behaviour, so a dismissal has
    to be declared. An inferred exclusion hardens silently into a blind spot; a
    declared one can be revisited.
    """
    p = _provenance()
    if p is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    try:
        return p.review(observation_id, req.outcome, req.note, req.actor)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund/research/yield")
def research_yield():
    """Which kinds of observation actually lead anywhere.

    The report that settles whether a big category is signal or an artifact of
    how we extract — a question no amount of arranging the map can answer.
    """
    p = _provenance()
    if p is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    return {**p.yield_by_category(), "unreviewed": p.unreviewed(limit=25)}


@router.get("/fund/factory/candidates/{candidate_id}/trail")
def factory_trail(candidate_id: str):
    """What prompted this candidate — the audit trail, backwards."""
    p = _provenance()
    if p is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    return {"candidate_id": candidate_id, "sources": p.trail(candidate_id)}


@router.get("/fund/research/map")
def research_map(turnover_pct: float = Query(1.0, gt=0, le=100)):
    """The terrain: what has been read, what it said, and where nothing is.

    The default view, deliberately. A ranked list would answer "what should I
    look at" while quietly hiding what it flattened; this answers "what does
    the ground look like", including the regions holding nothing — which is the
    one thing a list can never say.
    """
    o = _observations()
    if o is None:
        raise HTTPException(status_code=503, detail="research needs FUND_STORE=postgres")
    from app.fund.researchmap import build
    u = _universe()
    size = None
    if u is not None:
        try:
            # The TRUE count, not the length of a limited page — using the page
            # size would have reported "3 of 2,000" for a band holding 5,557,
            # flattering our coverage on the one view built to be honest.
            size = u.hunting_ground_count(turnover_pct=turnover_pct)
        except Exception as e:  # noqa: BLE001
            logger.info("hunting ground size unavailable for the map: %s", e)
    # The band the screen itself uses, derived the same way rather than restated:
    # capacity = participation * adv / turnover, inverted to bound ADV. Two
    # copies of this arithmetic would drift, and the map would then report
    # coverage of a band nobody screens.
    t = turnover_pct / 100.0
    adv_band = (BAND_MIN_CAPACITY * t / BAND_PARTICIPATION,
                BAND_MAX_CAPACITY * t / BAND_PARTICIPATION)
    return build(o, universe=u, hunting_ground_size=size, adv_band=adv_band)


@router.get("/fund/digest")
def morning_digest(since_hours: float = Query(24.0, gt=0, le=168)):
    """The morning read: what was read, what was judged, what needs a click.

    Exists because the loop was built and not lived in — 376 observations carried
    exactly one review, made by the person testing the review button. The missing
    piece was never another surface; it was a reason to come back tomorrow.

    Assembled from resolved facts rather than subsystem handles: NAV and the
    approval count are computed here and passed in, so the digest cannot become a
    second place that knows how to value the book or where approvals live.
    """
    o = _observations()
    f = _factory()
    nav_block = None
    try:
        nav_block = _nav.compute().to_dict()
    except Exception as e:  # noqa: BLE001
        logger.info("digest: NAV unavailable: %s", e)
    approvals = None
    try:
        approvals = {"pending_count": len(_orders.pending() or [])}
    except Exception as e:  # noqa: BLE001
        logger.info("digest: approval queue unavailable: %s", e)

    # The same band arithmetic as the screen and the map, from the same
    # constants — three copies would drift and each surface would then be honest
    # about a different market.
    t = 1.0 / 100.0
    adv_band = (BAND_MIN_CAPACITY * t / BAND_PARTICIPATION,
                BAND_MAX_CAPACITY * t / BAND_PARTICIPATION)

    # Which algorithms the fund is actually holding, so a failing DEPLOYED
    # strategy can be told apart from a failing research candidate. Slugged from
    # the strategy name because that is the convention the workspace already
    # follows ("Momentum · Large Cap Tech" -> momentum_large_cap_tech); a missed
    # match costs a digest line, never a wrong one.
    deployed: set[str] = set()
    try:
        for st in _strategies.list():
            if str(st.get("state") or "").lower() != "deployed":
                continue
            slug = re.sub(r"[^a-z0-9]+", "_",
                          str(st.get("name") or "").lower()).strip("_")
            if slug:
                deployed.add(slug)
    except Exception as e:  # noqa: BLE001
        logger.info("digest: deployed strategies unavailable: %s", e)

    from app.fund.digest import build as build_digest
    return build_digest(store=_store, observations=o, factory=f,
                        universe=_universe(), nav=nav_block,
                        approvals=approvals, adv_band=adv_band,
                        deployed=deployed, since_hours=since_hours)


@router.get("/fund/research/observations")
def research_observations(ticker: str | None = Query(None),
                          category: str | None = Query(None),
                          limit: int = Query(50, ge=1, le=500)):
    """What the filings said, with the quote that proves it."""
    o = _observations()
    if o is None:
        raise HTTPException(status_code=503, detail="research needs FUND_STORE=postgres")
    return {"coverage": o.coverage(),
            "observations": o.recent(ticker=ticker, category=category,
                                     limit=limit)}


class ExitRuleRequest(BaseModel):
    """One pre-committed exit. Submitted BEFORE the position exists."""
    strategy_id: str
    kind: str
    symbol: Optional[str] = None
    threshold_pct: Optional[float] = None
    on_date: Optional[str] = None
    note: str = ""
    actor: str = "operator"


class ExitOverrideRequest(BaseModel):
    strategy_id: str
    kind: str
    symbol: Optional[str] = None
    reason: str
    actor: str = "operator"


@router.post("/fund/exits")
def set_exit_rule(req: ExitRuleRequest):
    """Commit an exit rule to the event log.

    Recorded as an event rather than stored as config for one reason: a rule in a
    table can be edited by the person it constrains and nobody would know. In the
    append-only log it can only be superseded, and the supersession is visible.

    Writes an event and moves no money.
    """
    from app.fund.events import Event, EventType
    from app.fund.exitrule import ExitRuleError, build as build_rule
    try:
        rule = build_rule(req.strategy_id, req.kind,
                          threshold_pct=req.threshold_pct, on_date=req.on_date,
                          note=req.note, symbol=req.symbol)
    except ExitRuleError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Keyed on the strategy so the commitment, any supersession and any override
    # all land on the same aggregate and read as one history.
    _store.append(Event(req.strategy_id, "strategy", EventType.EXIT_RULE_SET,
                        rule, req.actor))
    return rule


@router.get("/fund/exits")
def list_exit_rules(strategy_id: str | None = Query(None)):
    """Active exit commitments, folded from the log."""
    from app.fund.exitrule import ExitRules
    return {"rules": ExitRules(_store).active(strategy_id)}


@router.get("/fund/exits/check")
def check_exit_rules(strategy_id: str | None = Query(None)):
    """Evaluate every committed exit against current marks.

    Reports fired, holding and unevaluable SEPARATELY. "Could not check" is not
    "fine", and a digest that merged them would let an unmarked position read as
    being in good standing.
    """
    from app.fund.exitrule import ExitRules
    try:
        positions = (_monitor.assess() or {}).get("positions") or []
    except Exception as e:  # noqa: BLE001
        logger.info("exit check: marks unavailable: %s", e)
        positions = []
    return ExitRules(_store).check(positions, strategy_id)


@router.post("/fund/exits/override")
def override_exit_rule(req: ExitOverrideRequest):
    """Record that a fired exit was deliberately not taken.

    Overrides are allowed; silent ones are not. An exit that can be ignored
    without a trace is not an exit, it is a story about why this time is
    different — and the reason this is a required field is to make that story
    expensive to tell.
    """
    from app.fund.events import Event, EventType
    if not (req.reason or "").strip():
        raise HTTPException(
            status_code=422,
            detail="an override needs a reason — that is the entire point of "
                   "recording it")
    payload = {"strategy_id": req.strategy_id, "kind": req.kind,
               "symbol": req.symbol, "reason": req.reason,
               "at": datetime.now(timezone.utc).isoformat(), "actor": req.actor}
    _store.append(Event(req.strategy_id, "strategy",
                        EventType.EXIT_RULE_OVERRIDDEN, payload, req.actor))
    return payload


@router.get("/fund/risk/throttle")
def risk_throttle():
    """How much of normal gross the regime justifies right now.

    Reduction only: this can lower gross and never raise it. Coming back up is
    a human decision, because an all-clear from a model is not the same thing
    as an opportunity.
    """
    from app.fund.throttle import target_gross
    try:
        from app.fund.regime import RegimeAnalytics
        regime = RegimeAnalytics().market()
    except Exception as e:  # noqa: BLE001
        # An unreachable regime must NOT read as a fragile one: target_gross
        # treats unmeasurable as full gross, so a data outage cannot quietly
        # become a trading decision.
        logger.warning("regime unavailable for throttle: %s", e)
        regime = {}
    return target_gross(regime)


@router.get("/fund/health")
def fund_health():
    """Is the system well — not merely up.

    Every check does the REAL operation and times it, because a liveness ping
    returned 200 through every outage this fund has had: the sixty-second NAV,
    the exhausted Firestore quota, the allocation that 500'd without reaching
    the log. The service was up throughout all of them.
    """
    from app.fund.health import report
    out = report(nav_service=_nav, connector=_connector, runner=_lean())
    # 200 even when degraded: this endpoint's job is to be READ, and a
    # monitoring tool that cannot parse the body because the status code made
    # it give up has learned nothing.
    return out


#: The capacity band the fund screens, in ONE place. The hunting ground, the
#: map's coverage denominator and any as-of rebuild all have to mean the same
#: band — three copies of this arithmetic would drift apart and each surface
#: would then be honest about a different market.
BAND_PARTICIPATION = 0.01
BAND_MIN_CAPACITY = 400_000.0
BAND_MAX_CAPACITY = 5_000_000.0


@router.get("/fund/universe/hunting-ground")
def universe_hunting_ground(
    turnover_pct: float = Query(5.0, gt=0, le=100),
    participation: float = Query(0.01, gt=0, le=1),
    min_capacity: float = Query(100_000.0, ge=0),
    max_capacity: float = Query(50_000_000.0, gt=0),
    limit: int = Query(200, ge=1, le=2000),
    operating_only: bool = Query(True),
):
    """Names inside the band where being small is an advantage.

    The upper bound is the interesting one: names above it are excluded not for
    being bad but for being available to everyone, which is a different and far
    more useful reason to pass on something.
    """
    u = _universe()
    if u is None:
        raise HTTPException(status_code=503,
                            detail="the universe lives in Postgres; run with FUND_STORE=postgres")
    return u.hunting_ground(turnover_pct=turnover_pct, participation=participation,
                            min_capacity=min_capacity, max_capacity=max_capacity,
                            limit=limit, operating_only=operating_only)


@router.get("/fund/universe/stats")
def universe_stats():
    u = _universe()
    if u is None:
        raise HTTPException(status_code=503, detail="universe needs FUND_STORE=postgres")
    return u.stats()


@router.get("/fund/lean/gate")
def lean_gate_criteria():
    """The bar a candidate must clear, published so it can be argued with.

    Served separately from any result on purpose: a threshold you can only see
    next to a number you already like is not a threshold.
    """
    from app.fund.gate import CRITERIA, GATE_VERSION
    return {"gate_version": GATE_VERSION, "criteria": CRITERIA}


@router.post("/fund/lean/gate/{sweep_id}")
def lean_gate_sweep(sweep_id: str):
    """Judge a finished sweep against the bar.

    Takes a SWEEP rather than a single backtest because most of the bar is
    about evidence a single run cannot provide: whether the winner survived
    data it was not chosen on, and how wrong we can be about costs. Judging
    one backtest would mean waiving exactly the criteria that matter.
    """
    from app.fund.gate import evaluate
    from app.fund.leanrunner import LeanError
    try:
        sweep = _lean().sweep(sweep_id)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if sweep.get("state") != "done":
        raise HTTPException(status_code=409,
                            detail=f"sweep is {sweep.get('state')} — judge it when it finishes")

    holdout = sweep.get("holdout_result")
    best = (sweep.get("summary") or {}).get("best") or {}
    params = best.get("parameters") or {}
    # Re-run the winner so the verdict is judged on a full result — the sweep's
    # own rows are trimmed to what a comparison needs and carry no costs
    # disclosure, benchmark or capacity.
    job = _lean().submit_backtest(sweep["algorithm"], params)
    return {"sweep_id": sweep_id, "algorithm": sweep["algorithm"],
            "winner": params, "verify_job_id": job["job_id"],
            "note": "poll the job, then POST /fund/lean/gate/judge with it",
            "holdout_available": bool(holdout)}


@router.post("/fund/lean/gate/judge/{job_id}")
def lean_gate_judge(job_id: str, sweep_id: str = Query(...)):
    """Apply the bar to a finished verification run plus its sweep."""
    from app.fund.gate import evaluate
    from app.fund.leanrunner import LeanError
    try:
        job = _lean().job(job_id)
        sweep = _lean().sweep(sweep_id)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if job.get("state") != "done":
        raise HTTPException(status_code=409, detail=f"job is {job.get('state')}")
    return {
        "algorithm": job.get("algorithm"),
        "parameters": job.get("parameters"),
        **evaluate(job.get("result") or {},
                   sweep.get("holdout_result"),
                   sweep.get("summary")),
    }


@router.get("/fund/lean/sweeps")
def lean_list_sweeps():
    """Sweep history, including runs from before the last restart."""
    return {"sweeps": _lean().sweeps()}


@router.get("/fund/lean/sweeps/{sweep_id}")
def lean_get_sweep(sweep_id: str):
    from app.fund.leanrunner import LeanError
    try:
        return _lean().sweep(sweep_id)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/fund/lean/backtests")
def lean_list_backtests():
    return {"jobs": _lean().jobs()}


@router.get("/fund/lean/backtests/{job_id}")
def lean_get_backtest(job_id: str):
    from app.fund.leanrunner import LeanError
    try:
        return _lean().job(job_id)
    except LeanError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/signals/external")
def external_signal(req: ExternalSignalRequest):
    """Signal intake for external engines (LEAN in Docker, later EC2).

    Propose-only by construction: whatever the engine wants, it lands in the
    approval queue behind the same risk and compliance gates as every other
    proposal, and a human click remains the only path to the venue. An engine
    with a brokerage attached would bypass all of that — so no engine gets
    one; it gets this endpoint instead.

    Token-gated (EXTERNAL_SIGNAL_TOKEN): 503 when unset — absent config reads
    as OFF, never as open. The strategy must already be registered, because an
    engine signal nobody can attribute is a trade nobody can post-mortem.
    """
    import hmac

    expected = os.getenv("EXTERNAL_SIGNAL_TOKEN", "").strip()
    if not expected:
        raise HTTPException(status_code=503,
                            detail="external signals disabled (EXTERNAL_SIGNAL_TOKEN unset)")
    if not hmac.compare_digest(req.token.strip(), expected):
        raise HTTPException(status_code=403, detail="bad signal token")
    try:
        _strategies.get(req.strategy_id)
    except StrategyError:
        raise HTTPException(
            status_code=404,
            detail=f"unknown strategy {req.strategy_id!r} — register the engine's "
                   "algorithm as a strategy first, so its trades are attributable",
        )
    order = Order(
        venue="paper",
        symbol=req.symbol.upper().strip(),
        side=Side(req.side),
        qty=req.qty,
        limit_price=req.limit_price,
        strategy_id=req.strategy_id,
        rationale=f"[{req.source}:{req.algo_id or 'algo'}] {req.reason}",
    )
    return _pipeline.propose_order(order, actor=f"external:{req.source}")


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


@router.get("/fund/venue/reconcile")
def venue_reconcile():
    """Broker-vs-book drift SIGNAL (read-only — writes no events).

    NAV stays folded from the event log; broker equity is only ever a comparison.
    A large delta means investigate before trading.
    """
    return _reconciler.drift()


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
# --- Automatic Theme Discovery & Thesis Generator (MVP #2) (must precede {thesis_id}) ---
@router.post("/fund/theses/generate")
def generate_thesis(req: ThesisGenerateRequest):
    """Automatically discover key themes, narratives, and generate an investment thesis."""
    try:
        res = _thesis_generator.generate_thesis(req.query, direction_override=req.direction)
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.post("/fund/theses/from-generation")
def promote_generated_thesis(req: ThesisPromoteRequest):
    """Promotes a generated thesis into the fund spine (creating Thesis + initial Memo)."""
    try:
        from app.fund.thesis_generator.models import GeneratedThesisResult
        parsed_res = GeneratedThesisResult(**req.generated_thesis)
        return _thesis_generator.promote_to_fund(
            parsed_res,
            actor=req.actor,
            target_exposure_pct=req.target_exposure_pct,
            horizon=req.horizon,
            backtest=req.backtest,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/theses/sources/status")
def get_thesis_sources_status():
    """Reports real-time connectivity and health of integrated research data sources."""
    try:
        statuses = _thesis_generator.get_data_sources_status()
        return {"sources": [s.model_dump() for s in statuses]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fund/theses/{thesis_id}/recommendation")
def recommend_thesis_trade(thesis_id: str, req: ThesisRecommendationRequest):
    """Consume a thesis plus its backtest into a sized trade recommendation.

    This is the missing hand-off between research and the approval desk.  It
    never executes: the default response is read-only, and an explicitly
    requested proposal is still passed through the normal risk gate and waits
    for a human approval.
    """
    try:
        thesis = _theses.get(thesis_id)
    except ThesisError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Validate the stored research before touching a price source.  A missing
    # backtest is a clear 422, not an incidental market-data outage.
    try:
        build_thesis_trade_recommendation(thesis_id, thesis, mark=1.0, nav_usd=1.0)
    except RecommendationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    symbol = str(thesis["assets"][0]).upper()
    try:
        price = float(_connector.price(symbol))
        nav = float(_nav.compute().total_nav_usd)
    except Exception as e:  # price and NAV are prerequisites for sizing
        raise HTTPException(status_code=503, detail=f"cannot size recommendation: {e}")
    try:
        recommendation = build_thesis_trade_recommendation(thesis_id, thesis, mark=price, nav_usd=nav)
    except RecommendationError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not req.create_proposal:
        return {"recommendation": recommendation, "proposal": None}

    order = Order(venue="paper", symbol=recommendation["symbol"],
                  side=Side(recommendation["side"]), qty=recommendation["qty"],
                  thesis_id=thesis_id, rationale=recommendation["rationale"])
    proposal = _pipeline.propose_order(order, actor=req.actor)
    return {"recommendation": recommendation, "proposal": proposal}


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


@router.delete("/fund/theses/{thesis_id}")
def delete_thesis(thesis_id: str, req: ActorRequest):
    """Archive an unused thesis from the Studio while retaining the audit log."""
    try:
        return _theses.archive(thesis_id, actor=req.actor)
    except ThesisError as e:
        raise HTTPException(status_code=409, detail=str(e))


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
            # realized vs unrealized matter for tax and attribution; None (not 0)
            # when there is no attribution, so the UI shows "—" not a fake zero
            "realized_pnl_usd": a.get("realized_pnl_usd"),
            "unrealized_pnl_usd": a.get("unrealized_pnl_usd"),
            "cost_basis_usd": a.get("cost_basis_usd"),
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


@router.get("/fund/strategies/divergence")
def get_strategy_divergence():
    """Live performance vs the backtest each strategy was deployed on.

    The number the watcher's brief always promised: "a strategy that has not
    resembled its backtest for a fortnight". Rows under 14 live days say so
    rather than annualising two days of noise into a verdict.
    """
    from app.fund.divergence import compare

    return compare(
        _store,
        _strategies.list(),
        _attribution.with_values(_live_price_fn()),
    )


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
             start_date: str | None = Query(None), end_date: str | None = Query(None),
             as_of: str | None = Query(
                 None, pattern=r"^\d{4}-\d{2}-\d{2}$",
                 description="Serve the series as it was KNOWN on this date, "
                             "from the point-in-time archive"),
             format: str = Query("json", pattern="^(json|csv)$")):
    """Free daily bars for a symbol (crypto→CoinGecko, else Alpaca/Yahoo).

    ``format=csv`` streams one ``date,close`` line per bar — the shape LEAN's
    remote-file reader expects: it iterates LINES as data points, so a JSON
    blob reads as exactly one bar (the smoke test processed 1 data point of a
    155-bar history before this existed).
    """
    # Point-in-time: serve what was KNOWN on as_of, from the archive, rather
    # than what the vendor says today. A backtest handed today's view of 2025
    # is not a simulation of a decision — the closes are adjusted for splits
    # that had not happened, and any correction the vendor has since made is
    # baked in.
    if as_of:
        store = _barstore()
        if store is None:
            raise HTTPException(
                status_code=503,
                detail="point-in-time bars need the Postgres archive; "
                       "run with FUND_STORE=postgres")
        pit = store.as_of(symbol, as_of, start=start_date)
        if not pit["dates"]:
            raise HTTPException(
                status_code=404,
                detail=f"nothing archived for {symbol} on or before {as_of} — "
                       f"the archive only knows what it has seen, and it had "
                       f"not seen this. Fetch it live first.")
        if format == "csv":
            lines = "\n".join(f"{d},{c}" for d, c in zip(pit["dates"], pit["closes"]))
            return Response(content=lines, media_type="text/csv")
        return pit

    try:
        bars = fetch_daily_bars(symbol, lookback_days=lookback_days, start=start_date, end=end_date)
    except BarsError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Every live fetch feeds the archive. First observation wins; a vendor
    # disagreeing with what it served before is logged as a restatement, never
    # applied. Best effort — a failing archive must not take down market data.
    store = _barstore()
    if store is not None:
        try:
            store.archive(bars.symbol, bars.dates or [], bars.closes or [],
                          bars.source or "unknown")
        except Exception as e:  # noqa: BLE001
            logger.warning("bar archive write failed for %s: %s", symbol, e)

    if format == "csv":
        dates = bars.dates or []
        lines = "\n".join(f"{d},{c}" for d, c in zip(dates, bars.closes))
        return Response(content=lines, media_type="text/csv")
    return {"symbol": bars.symbol, "source": bars.source,
            "closes": bars.closes, "dates": bars.dates,
            "start": bars.start, "end": bars.end}


@router.post("/fund/research/backtest")
def research_backtest(req: BacktestBySymbolRequest):
    """Stateless backtest — the research loop, with no strategy registered.

    A tester you must first register a strategy to use is not a tester. Here you
    pick a symbol, a template and parameters, and get the full result back:
    equity curve, trade list and statistics, alongside the price series so the
    two can be drawn on the same axis.

    Touches no event log: research is not fund state. Nothing is persisted until
    someone decides the idea is worth registering.
    """
    try:
        bars = fetch_daily_bars(req.symbol, lookback_days=req.lookback_days,
                                start=req.start_date, end=req.end_date)
    except BarsError as e:
        raise HTTPException(status_code=422, detail=str(e))

    prices = bars.closes
    signals = signals_for(
        req.strategy, prices,
        fast=req.fast, slow=req.slow,
        rsi_period=req.rsi_period, rsi_low=req.rsi_low, rsi_high=req.rsi_high,
        breakout_lookback=req.breakout_lookback,
        macd_fast=req.macd_fast, macd_slow=req.macd_slow, macd_signal=req.macd_signal,
        boll_period=req.boll_period, boll_k=req.boll_k,
        momentum_lookback=req.momentum_lookback,
        atr_period=req.atr_period, atr_mult=req.atr_mult,
    )
    # The SAME cost model runs over both the strategy and its benchmark. Costing
    # a strategy that trades weekly against a frictionless buy-and-hold would
    # flatter the benchmark; costing neither flatters the strategy.
    costs = CostModel(slippage_bps=req.slippage_bps, commission_bps=req.commission_bps)
    result = SimpleBacktester(costs).run(prices, signals)

    # buy-and-hold over the same window — a strategy that cannot beat simply
    # owning the thing is not interesting, and that comparison should be
    # impossible to avoid seeing
    bh = SimpleBacktester(costs).run(prices, [1.0] * len(prices))

    return {
        "symbol": bars.symbol,
        "source": bars.source,
        "strategy": req.strategy,
        "params": req.model_dump(exclude_none=True),
        "result": result.to_dict(),
        "benchmark": {
            "label": "buy & hold",
            "total_return": round(bh.total_return, 6),
            "sharpe": round(bh.sharpe, 4),
            "max_drawdown": round(bh.max_drawdown, 6),
            "equity_curve": [round(e, 6) for e in bh.equity_curve],
        },
        # The full research picture: risk-adjusted ratios, drawdown recovery,
        # benchmark-relative alpha/beta, and the inference block that says
        # whether any of it is distinguishable from luck.
        "tearsheet": tearsheet.build(
            result.equity_curve,
            benchmark_curve=bh.equity_curve,
            benchmark_label="buy & hold",
            trades=result.trades,
            signals=signals,
            n_trials=max(1, int(req.n_trials or 1)),
        ),
        "data_quality": {
            "adjusted": bars.adjusted,
            "adjustment": bars.adjustment,
            # Backtesting signals on an unadjusted series measures corporate
            # actions, not the strategy — so this is a caveat on the result,
            # not a footnote about the feed.
            "warning": None if bars.adjusted else (
                f"{bars.source} returned an UNADJUSTED price series — splits and "
                "dividends appear as price jumps, and any signal or drawdown "
                "computed across one is unreliable"
            ),
        },
        "bars": {"closes": prices, "dates": bars.dates,
                 "start": bars.start, "end": bars.end},
        "signals": signals,
    }


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


@router.post("/fund/strategies/{parent_id}/members")
def set_strategy_member(parent_id: str, req: StrategyMemberRequest):
    """Set target weight for a child strategy member under parent_id (S1)."""
    try:
        return _strategies.set_member_weight(parent_id, child_id=req.child_id, weight=req.weight, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/strategies/{parent_id}/members/weights")
def set_strategy_member_weights(parent_id: str, req: StrategyMemberWeightsRequest):
    """Bulk set target weights for child strategy members under parent_id (S1)."""
    try:
        return _strategies.set_member_weights(parent_id, weights=req.weights, actor=req.actor)
    except StrategyError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/strategies/{parent_id}/compose/weights")
def compose_strategy_weights(parent_id: str, req: StrategyComposeWeightsRequest):
    """Suggest optimal weights for member child strategies (S2). Does not persist."""
    try:
        parent = _strategies.get(parent_id)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    members = parent.get("members", [])
    if not members:
        all_strats = _strategies.list()
        members = [{"child_id": s["strategy_id"], "name": s["name"], "weight": 0.0}
                   for s in all_strats if s["strategy_id"] != parent_id and not s.get("archived")]

    streams = {}
    skipped = []
    for m in members:
        cid = m["child_id"]
        c_rec = _strategies.get(cid)
        c_assets = c_rec.get("assets") or []
        series = None
        if c_assets:
            closes_list = []
            for sym in c_assets:
                try:
                    bars = fetch_daily_bars(sym, lookback_days=req.lookback_days)
                    if bars and bars.closes:
                        s = pd.Series(bars.closes, index=pd.to_datetime(bars.dates))
                        norm_s = s / (s.iloc[0] if s.iloc[0] != 0 else 1.0)
                        closes_list.append(norm_s)
                except BarsError:
                    pass
            if closes_list:
                series = pd.DataFrame(closes_list).T.mean(axis=1)

        if series is None or len(series) < 5:
            skipped.append(cid)
        else:
            streams[cid] = series

    if not streams:
        return {
            "weights": {m["child_id"]: round(1.0 / len(members), 4) for m in members} if members else {},
            "method": req.method,
            "expected": {"sharpe": None, "vol": 0.0, "ret": 0.0},
            "cv": {"pbo": 0.0, "oos_sharpe": None},
            "skipped_members": skipped,
        }

    df_streams = pd.DataFrame(streams)
    res = optimize_return_streams(df_streams, method=req.method)
    res["skipped_members"] = skipped
    return res


@router.get("/fund/strategies/{parent_id}/composite")
def get_composite_strategy(parent_id: str):
    """Return composite assessment: members, blended equity curve, metrics, and risk (S3)."""
    try:
        parent = _strategies.get(parent_id)
    except StrategyError as e:
        raise HTTPException(status_code=404, detail=str(e))

    members = parent.get("members", [])
    attr_map = {a["strategy_id"]: a for a in _attribution.with_values(_connector.price)}

    enriched_members = []
    weights_sum = 0.0
    for m in members:
        cid = m["child_id"]
        w = float(m.get("weight", 0.0))
        weights_sum += w
        c_attr = attr_map.get(cid, {})
        enriched_members.append({
            "child_id": cid,
            "name": m.get("name"),
            "weight": round(w, 4),
            "exposure_usd": c_attr.get("exposure_usd", 0.0),
            "pnl_usd": c_attr.get("pnl_usd", 0.0),
        })

    curves = {}
    flags = []
    for m in members:
        cid = m["child_id"]
        c_rec = _strategies.get(cid)
        c_assets = c_rec.get("assets") or []
        series = None
        if c_assets:
            closes_list = []
            for sym in c_assets:
                try:
                    bars = fetch_daily_bars(sym, lookback_days=180)
                    if bars and bars.closes:
                        s = pd.Series(bars.closes, index=pd.to_datetime(bars.dates))
                        norm_s = s / (s.iloc[0] if s.iloc[0] != 0 else 1.0)
                        closes_list.append(norm_s)
                except BarsError:
                    pass
            if closes_list:
                series = pd.DataFrame(closes_list).T.mean(axis=1)

        if series is None or len(series) < 5:
            flags.append(f"Child strategy '{m.get('name')}' has no backtest curve — excluded from rollup")
        else:
            norm_series = series / (series.iloc[0] if series.iloc[0] != 0 else 1.0)
            curves[cid] = norm_series

    blended_points = []
    metrics = None
    drawdown_pct = 0.0
    if curves:
        df_curves = pd.DataFrame(curves).dropna(how="all").ffill().bfill()
        if not df_curves.empty:
            cash_w = max(0.0, 1.0 - weights_sum)
            blend_vals = pd.Series(cash_w, index=df_curves.index)
            for cid, s in df_curves.items():
                w = next((m["weight"] for m in members if m["child_id"] == cid), 0.0)
                blend_vals += w * s

            for idx, val in blend_vals.items():
                date_str = str(idx)[:10]
                blended_points.append({"t": date_str, "v": round(float(val), 4)})

            total_ret = float(blend_vals.iloc[-1] / blend_vals.iloc[0] - 1.0) if blend_vals.iloc[0] != 0 else 0.0
            pct_changes = blend_vals.pct_change().dropna()
            sharpe = None
            if len(pct_changes) >= 20:
                std_val = float(pct_changes.std())
                if std_val > 1e-9:
                    sharpe = round(float((pct_changes.mean() / std_val) * (252 ** 0.5)), 2)

            cum = blend_vals.values
            peaks = np.maximum.accumulate(cum)
            dds = (cum - peaks) / np.maximum(peaks, 1e-8)
            max_dd = float(np.min(dds)) if len(dds) > 0 else 0.0
            drawdown_pct = abs(max_dd)

            metrics = {
                "total_return": round(total_ret * 100, 2),
                "sharpe": sharpe,
                "max_drawdown": round(max_dd, 4),
            }

    hhi = 0.0
    if weights_sum > 0:
        hhi = float(sum((m["weight"] / weights_sum) ** 2 for m in enriched_members))
        if hhi > 0.4:
            flags.append("High portfolio concentration (HHI > 0.40)")

    if weights_sum < 0.999:
        flags.append(f"Weights sum to {round(weights_sum * 100, 1)}% (< 100%, remainder cash)")
    elif weights_sum > 1.001:
        flags.append(f"Weights sum to {round(weights_sum * 100, 1)}% (> 100%, leverage)")

    return {
        "strategy_id": parent_id,
        "members": enriched_members,
        "blended_equity": blended_points,
        "metrics": metrics,
        "risk": {
            "concentration_hhi": round(hhi, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "flags": flags,
        },
        "weights_sum": round(weights_sum, 4),
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


@router.get("/fund/risk/advanced")
def get_risk_advanced(
    lookback_days: int = Query(250, ge=60, le=1500),
    include_regime: bool = Query(True),
    include_historical: bool = Query(True),
    force: bool = Query(False, description="bypass the 30-minute cache and recompute"),
):
    """Correlation, risk contribution, Expected Shortfall, market regime,
    reverse stress and historical replay — the structural risk view.

    Slower than /risk/monitor because it reads market history; each block
    degrades independently and reports why rather than returning zeros.
    """
    peak = None
    try:
        hist = _nav.history(365)
        vals = [float(h.get("total_nav_usd", 0)) for h in hist if h.get("total_nav_usd")]
        vals.append(float(_nav.compute().total_nav_usd))
        peak = max(vals) if vals else None
    except Exception:  # noqa: BLE001 — peak is an input to reverse stress, not a gate
        peak = None
    return _riskengine.view(
        lookback_days=lookback_days,
        limits=_control.limits(),
        peak_nav=peak,
        include_regime=include_regime,
        include_historical=include_historical,
        force=force,
    )


@router.get("/fund/risk/history")
def get_risk_history(limit: int = Query(180, ge=2, le=1000)):
    """The risk view's time dimension: one compact point per fresh engine
    compute (book vol, effective bets, ES, move-to-halt), oldest first.
    Sparse by design — points accrue when the book changes or the cache
    expires, not on a clock. Telemetry, never the event log."""
    from app.fund.riskhistory import RiskHistory

    return {"points": RiskHistory().recent(limit=limit)}


class RiskWhatIfRequest(BaseModel):
    """Proposed strategy weights as percentages of NAV, keyed by strategy_id."""
    targets: dict[str, float]
    lookback_days: int = 250


@router.post("/fund/risk/whatif")
def risk_what_if(req: RiskWhatIfRequest):
    """Risk mechanics of a proposed allocation vs the current one.

    Read-only: computes what the book WOULD look like. Nothing is written and no
    order is placed — rebalancing still goes through propose/approve.
    """
    return _riskengine.what_if(req.targets, lookback_days=req.lookback_days)


class ResearchEvaluateRequest(BaseModel):
    """A candidate strategy's daily returns (or an equity curve) plus the dates
    they fall on."""
    returns: list[float] | None = None
    equity_curve: list[float] | None = None
    dates: list[str]
    allocation_pct: float = 10.0


@router.post("/fund/research/evaluate")
def evaluate_candidate(req: ResearchEvaluateRequest):
    """The two questions a backtest cannot answer.

    1. Is this alpha, or factor exposure you could buy for nine basis points?
    2. Does adding it make the FUND better, or is it a duplicate of something
       already deployed?

    Stateless and read-only — nothing is registered or persisted.
    """
    rets = req.returns
    if rets is None and req.equity_curve:
        eq = req.equity_curve
        rets = [(eq[i] / eq[i - 1] - 1.0) if eq[i - 1] else 0.0
                for i in range(1, len(eq))]
    if not rets:
        raise HTTPException(status_code=422,
                            detail="supply either returns or an equity_curve")

    # An equity curve of N points yields N-1 returns; align the dates to match
    # rather than silently zipping mismatched series.
    dates = req.dates
    if len(dates) == len(rets) + 1:
        dates = dates[1:]
    if len(dates) != len(rets):
        raise HTTPException(
            status_code=422,
            detail=f"{len(rets)} returns but {len(req.dates)} dates — cannot align",
        )

    out: dict = {"n_obs": len(rets)}
    try:
        out["factors"] = _factor_model.analyse(rets, dates)
    except Exception as e:  # noqa: BLE001
        out["factors"] = {"measurable": False,
                          "reason": f"factor data unavailable ({type(e).__name__})"}
    try:
        out["fit"] = _riskengine.candidate_fit(rets, dates, req.allocation_pct)
    except Exception as e:  # noqa: BLE001
        out["fit"] = {"measurable": False,
                      "reason": f"portfolio fit unavailable ({type(e).__name__})"}
    return out


class ResearchPromoteRequest(BaseModel):
    """Turn a Lab run into a real strategy and queue it for review."""
    name: str
    symbols: list[str]
    definition: dict
    backtest: dict | None = None
    allocation_pct: float = 10.0
    actor: str = "rushi"
    note: str | None = None


@router.post("/fund/research/promote")
def promote_candidate(req: ResearchPromoteRequest):
    """Research -> strategy -> rebalance queue, in one step.

    This is the seam that was missing. Previously a strategy was created as an
    empty named shell and filled in somewhere else, so the evidence that
    justified it was never attached to it. Here the definition, the universe and
    the backtest that earned it arrive together, and the sizing decision goes
    into the review queue rather than straight to the venue.

    Registers the strategy but does NOT deploy or trade it: a human still
    approves the rebalance plan.
    """
    if not req.symbols:
        raise HTTPException(status_code=422, detail="a strategy needs at least one symbol")

    st = _strategies.register(req.name, actor=req.actor, definition=req.definition)
    sid = st["strategy_id"]
    _strategies.set_assets(sid, [s.upper() for s in req.symbols], actor=req.actor)
    if req.backtest:
        _strategies.record_backtest(sid, req.backtest, actor=req.actor)
        _strategies.set_state(sid, "backtested", actor=req.actor)

    # Keep every existing deployed strategy where it is; add the newcomer.
    targets: dict[str, float] = {}
    for s in _strategies.list():
        if s.get("state") == "deployed" and not s.get("archived"):
            targets[s["strategy_id"]] = float(s.get("allocation_pct") or 0.0)
    targets[sid] = float(req.allocation_pct)

    try:
        plan = _rebalance.propose(
            targets, actor=req.actor,
            note=req.note or f"promote '{req.name}' from the Lab at {req.allocation_pct:.0f}%",
        )
    except RebalanceError as e:
        # The strategy is still registered — research is not lost because the
        # sizing could not be queued. Say exactly that rather than pretending.
        return {"strategy_id": sid, "queued": False, "reason": str(e)}
    return {"strategy_id": sid, "queued": True, "plan": plan}


@router.get("/fund/nav/intraday")
def get_intraday_nav(minutes: int = Query(180, ge=5, le=1440)):
    """Intraday NAV samples for the P&L trace.

    These are NOT struck NAV: they live in memory, vanish on restart and carry
    ``struck: false``. Use them to watch a session, never to reconcile or report.
    """
    # Sample on read too, so a freshly-opened chart has a current point even if
    # the scheduler tick has not landed yet.
    sample_intraday_nav()
    return _intraday.series(minutes=minutes)


# --- venue backfill (adopt fills the platform did not originate) ------------
def _broker_fills_for_backfill() -> list[dict]:
    """Real filled orders at the venue, in the shape BrokerBackfill expects."""
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    client = _connector._trading()  # noqa: SLF001 — same package, deliberate
    rows = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))
    out = []
    for o in rows:
        if getattr(o, "status", None) is None or o.status.value != "filled":
            continue
        out.append({
            "client_order_id": str(o.client_order_id),
            "symbol": o.symbol,
            "side": o.side.value,
            "qty": float(o.filled_qty or 0),
            "price": float(o.filled_avg_price or 0),
        })
    return out


def _symbol_to_strategy() -> dict[str, str]:
    """Map each symbol to the deployed strategy that DECLARES it.

    Read from the strategies' own universes rather than a hardcoded table, so it
    cannot drift out of step with the book. A symbol claimed by two strategies is
    genuinely ambiguous and is left unmapped — guessing would put P&L against a
    thesis that did not ask for it.
    """
    owners: dict[str, list[str]] = {}
    try:
        for st in _strategies.list():
            if st.get("archived") or st.get("state") != "deployed":
                continue
            for sym in (st.get("assets") or []):
                owners.setdefault(str(sym).upper(), []).append(st["strategy_id"])
    except Exception:  # noqa: BLE001
        return {}
    return {sym: ids[0] for sym, ids in owners.items() if len(ids) == 1}


def _attribute_plan(plan) -> dict:
    """Stamp each planned fill with its owning strategy, and report coverage."""
    mapping = _symbol_to_strategy()
    mapped, unmapped = {}, []
    for pf in plan.all_events:
        sid = mapping.get(str(pf.symbol).upper())
        if sid:
            pf.strategy_id = sid
            mapped[pf.symbol] = sid
        else:
            unmapped.append(pf.symbol)
    return {
        "mapped": mapped,
        "unmapped": sorted(set(unmapped)),
        "note": "attribution is inferred from declared universes; these fills were "
                "not placed by the platform, so no strategy actually chose them",
    }


class BackfillApplyRequest(BaseModel):
    actor: str = "reconciliation"
    confirm: bool = False


@router.get("/fund/venue/backfill/plan")
def plan_venue_backfill():
    """DRY RUN: which venue fills are missing from our log, and what adopting
    them would do. Reads both sides, writes nothing."""
    if not _real_broker():
        raise HTTPException(status_code=400,
                            detail="no real broker configured — nothing to back-fill")
    try:
        fills = _broker_fills_for_backfill()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"venue unreadable: {type(e).__name__}: {e}")
    plan = BrokerBackfill(store=_store).plan(fills)
    mapping = _attribute_plan(plan)
    return {"venue_filled_orders": len(fills), "plan": plan.to_dict(),
            "attribution": mapping,
            "is_production": bool(_active_book().get("env") == "production")}


@router.post("/fund/venue/backfill/apply")
def apply_venue_backfill(req: BackfillApplyRequest):
    """Write the missing venue fills into the ledger.

    This is a permanent append to an append-only log, so it is guarded twice:
    never against the production book from this endpoint, and never without an
    explicit confirm. Adopted fills carry no strategy_id — nobody's strategy
    chose them, and pretending otherwise would corrupt attribution.
    """
    if _active_book().get("env") == "production":
        raise HTTPException(
            status_code=403,
            detail="refusing to back-fill the PRODUCTION ledger from the API; "
                   "use scripts/reconcile_broker.py with a dry run first")
    if not req.confirm:
        raise HTTPException(status_code=400, detail="pass confirm=true to write")
    if not _real_broker():
        raise HTTPException(status_code=400, detail="no real broker configured")
    fills = _broker_fills_for_backfill()
    bf = BrokerBackfill(store=_store)
    plan = bf.plan(fills)
    mapping = _attribute_plan(plan)
    result = bf.apply(plan, actor=req.actor)
    _riskengine.invalidate()
    return {"applied": result, "attribution": mapping, "plan": plan.to_dict()}


# --- rebalance (a reviewable batch, not a button) ---------------------------
class RebalanceBuildRequest(BaseModel):
    targets: dict[str, float]


class RebalanceProposeRequest(BaseModel):
    targets: dict[str, float]
    actor: str
    note: str | None = None


class RebalanceApproveRequest(BaseModel):
    approver: str
    allow_self_approval: bool = True


class RebalanceDeclineRequest(BaseModel):
    actor: str
    reason: str | None = None


@router.post("/fund/rebalance/preview")
def preview_rebalance(req: RebalanceBuildRequest):
    """The order list a set of targets implies. Writes nothing."""
    try:
        return _rebalance.build(req.targets)
    except RebalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/rebalance/propose")
def propose_rebalance(req: RebalanceProposeRequest):
    """Queue a plan for review. Places no orders."""
    try:
        return _rebalance.propose(req.targets, actor=req.actor, note=req.note)
    except RebalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/fund/rebalance/pending")
def list_pending_rebalances():
    """Plans awaiting a human, each decorated with what has changed since it
    was written (price drift, age, halt state)."""
    return {"pending": _rebalance.pending()}


@router.get("/fund/rebalance/history")
def list_rebalance_history(limit: int = Query(20, ge=1, le=200)):
    return {"history": _rebalance.history(limit)}


@router.get("/fund/rebalance/{plan_id}")
def get_rebalance(plan_id: str):
    try:
        return _rebalance.get(plan_id)
    except RebalanceError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/fund/rebalance/{plan_id}/approve")
def approve_rebalance(plan_id: str, req: RebalanceApproveRequest):
    """Push the plan: re-prices, re-gates every order, reports what happened."""
    try:
        return _rebalance.approve(plan_id, approver=req.approver,
                                  allow_self_approval=req.allow_self_approval)
    except RebalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/fund/rebalance/{plan_id}/decline")
def decline_rebalance(plan_id: str, req: RebalanceDeclineRequest):
    try:
        return _rebalance.decline(plan_id, actor=req.actor, reason=req.reason)
    except RebalanceError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
