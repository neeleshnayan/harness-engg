"""Fund harness API — the spine's HTTP surface.

Order path (venue-agnostic, human-gated): propose → risk gate → approve/decline
→ idempotent execution. Ledger path (LP-facing): subscribe/redeem with a
two-phase confirm, minting/burning units at NAV. Read routes expose NAV,
positions, per-LP holdings, and the audit event log.

The venue and the ledger are chosen by the fund's MODE (app/fund/mode.py):
``test`` runs a simulated venue against an isolated store, ``alpaca-paper``
runs the real broker's paper account against the fund's book, ``alpaca-prod``
is built and structurally locked. Neither dimension has a default.
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

from app.fund import mode as fundmode
from app.fund.connectors.base import Order, Side
from app.fund.venue import build_connector
from app.fund import tearsheet
from app.fund.backtest import CostModel, SimpleBacktester, signals_for
from app.fund.execution import ExecutionHistory, summarise
_log = logging.getLogger(__name__)

from app.fund.custody import CustodyIngest
from app.fund.signals import SignalRunner
from app.fund.marketdata import BarsError, fetch_daily_bars
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
    DrawdownRebaseRequest,
    HaltAcknowledgeRequest,
    LossRebaseRequest,
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
    StrategyOptimizeRequest,
    StrategyMemberRequest,
    StrategyMemberWeightsRequest,
    StrategyComposeWeightsRequest,
)
from app.fund.thesis_generator.service import ThesisGeneratorService

from app.fund.optimization import optimize_portfolio, optimize_return_streams

logger = logging.getLogger(__name__)

router = APIRouter()

# --- spine wiring: ONE mode, TWO dimensions --------------------------------
# A mode is (where orders go) x (where events land). See app/fund/mode.py for
# why those are two decisions and why neither has a default.
def _live_price_fn():
    """Live marks unconditionally, for READ views that want market levels.

    Not part of the order path — see ``_paper_live_pricer`` for that.
    """
    from app.fund.marketdata import live_price
    return live_price


def _paper_live_pricer():
    """Live free marks for the simulated venue when FUND_LIVE_MARKS is truthy.

    Read from the flag ALONE as of 2026-08-22. The old mock branch was
    ``_paper_live_pricer() or _live_price_fn()`` — live marks unconditionally,
    with the flag able only to turn them on, never off. One switch, one
    meaning; ``.env`` carries FUND_LIVE_MARKS=true, so the live spine's
    behaviour is unchanged and the hidden ``or`` is gone.
    """
    if os.getenv("FUND_LIVE_MARKS", "false").lower() in ("1", "true", "yes"):
        from app.fund.marketdata import live_price
        return live_price
    return None


# --- the wiring, as ONE function of the mode --------------------------------
# Everything below depends on the mode through exactly two things: which
# connector executes orders, and which store the events land in. Building it in
# a function rather than as twenty top-level statements is what makes the mode
# SWITCHABLE at all — and, more importantly, what makes the switch ATOMIC:
# every object is constructed into a local first, and the module globals are
# rebound only once all of them exist. A half-rewired spine — new store, old
# connector — is the exact shape of the incident this whole module exists to
# prevent.
_mode_spec: fundmode.ModeSpec
_snapshots = None


def _wire(spec: fundmode.ModeSpec) -> fundmode.ModeSpec:
    """(Re)build every object whose identity depends on the fund's mode."""
    global _mode_spec, _connector, _store, _snapshots, _projection, _nav
    global _pipeline, _ledger, _holdings, _strategies, _theses, _memos
    global _thesis_generator, _risk, _postmortem, _attribution, _orders
    global _reconciler, _control, _monitor, _riskengine, _factor_model
    global _intraday, _rebalance, _simulator

    connector = build_connector(spec, live_pricer=_paper_live_pricer())
    store = EventStore()

    # Snapshotted on Firestore: without it every read folds the entire event
    # log, which is O(all history) per request and exhausted the read quota
    # (429).
    #
    # NOT snapshotted on Postgres, deliberately. The snapshot store is a cache
    # whose only justification was that reading the log was expensive; folding
    # 155 events out of Postgres takes 40 milliseconds, so the cache buys
    # nothing and costs a write every fifty events. Worse, it kept the read
    # path anchored to Firestore after the ledger had left: with the quota
    # exhausted, every snapshot read failed through gRPC retries and a single
    # NAV request took FIFTY-SEVEN SECONDS — long enough that Clark's own tools
    # timed out and reported the fund unreachable while Postgres sat there
    # answering in milliseconds.
    from app.fund.events import store_backend
    if store_backend() == "postgres":
        snapshots = None
    else:
        from app.fund.snapshots import SnapshotStore
        snapshots = SnapshotStore()

    projection = PositionsProjection(store, snapshots=snapshots)
    nav = NavService(pricer=connector.price, store=store, projection=projection)
    pipeline = CommandPipeline(connector=connector, nav_service=nav, store=store)
    ledger = LedgerService(nav_service=nav, store=store)
    holdings = HoldingsProjection(store, snapshots=snapshots)
    strategies = StrategyService(store=store)
    theses = ThesisService(store=store)
    memos = MemoService(store=store)
    thesis_generator = ThesisGeneratorService(store=store, thesis_service=theses,
                                              memo_service=memos)
    risk = RiskAnalytics(nav_service=nav)
    postmortem = PostmortemService(store=store, pricer=connector.price)
    attribution = StrategyAttribution(store, snapshots=snapshots)
    orders = OrdersProjection(store, snapshots=snapshots)
    reconciler = Reconciler(connector=connector, store=store,
                            projection=projection, nav_service=nav)
    control = RiskControl(store=store)
    monitor = RiskMonitor(nav_service=nav, store=store, pricer=connector.price,
                          attribution=attribution, strategies=strategies,
                          control=control)
    riskengine = AdvancedRiskEngine(nav_service=nav, pricer=connector.price,
                                    attribution=attribution, strategies=strategies)
    factor_model = FactorModel()
    intraday = IntradayNav()
    rebalance = RebalanceService(nav_service=nav, pricer=connector.price,
                                 attribution=attribution, strategies=strategies,
                                 pipeline=pipeline, control=control,
                                 risk_engine=riskengine, store=store)
    simulator = CounterfactualSimulator(nav_service=nav,
                                        positions_projection=projection,
                                        strategy_service=strategies)

    # Everything constructed. Rebind in one pass.
    _mode_spec = spec
    _connector, _store, _snapshots = connector, store, snapshots
    _projection, _nav, _pipeline, _ledger = projection, nav, pipeline, ledger
    _holdings, _strategies, _theses, _memos = holdings, strategies, theses, memos
    _thesis_generator, _risk, _postmortem = thesis_generator, risk, postmortem
    _attribution, _orders, _reconciler = attribution, orders, reconciler
    _control, _monitor, _riskengine = control, monitor, riskengine
    _factor_model, _intraday = factor_model, intraday
    _rebalance, _simulator = rebalance, simulator
    return spec


#: Resolved and wired at IMPORT — a fund that cannot determine its own mode
#: must refuse to construct an order path at all, which for a module whose
#: import IS the construction means failing right here, loudly, before a single
#: endpoint exists to accept an order.
_wire(fundmode.activate(fundmode.resolve()))


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
    if not _mode_spec.real_broker:
        _log.warning("trade stream: mode is %r, which has no broker socket to "
                     "listen to — polling only", _mode_spec.mode.value)
        return None
    if _connector.name != "alpaca":
        _log.warning("trade stream: venue is %r, not alpaca — polling only", _connector.name)
        return None

    from app.fund.tradestream import TradeStream

    # paper vs live from the MODE, like everything else. ALPACA_PAPER decided
    # which ACCOUNT this socket subscribed to while being tied to nothing the
    # rest of the fund could see.
    paper = _mode_spec.venue_kind is fundmode.VenueKind.ALPACA_PAPER
    _trade_stream = TradeStream(_pipeline, key, secret, paper=paper)
    return asyncio.create_task(_trade_stream.run())


def stop_trade_stream() -> None:
    """Stop the stream AND drop the handle.

    The handle is cleared as of 2026-08-22. Without it a stopped stream stayed
    in ``_trade_stream`` and ``trade_stream_state()`` kept describing a socket
    that had been told to stop — a control reporting a state it is no longer
    in, which is the pattern this codebase names most often. It also matters to
    the mode switch, which stops the stream precisely so that nothing holds the
    pipeline of the store being left.
    """
    global _trade_stream
    if _trade_stream is not None:
        _trade_stream.stop()
        _trade_stream = None


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
        # TWO LEGS, EACH CHECKED SEPARATELY (2026-08-21).
        #
        # This block used to `return` the moment the event log was current —
        # which is most of the time. Adding the agent-runs mirror underneath
        # that early exit would have produced a mirror that essentially never
        # ran: the unwired-kill-switch pattern, in the one module written to
        # end it. The two legs are behind for unrelated reasons and each gets
        # its own test.
        events_behind = st.get("behind_by") or 0
        runs_behind = (st.get("runs") or {}).get("behind_by") or 0
        if not events_behind and not runs_behind:
            return {"skipped": "nothing new to snapshot", **st}

        out: dict[str, Any] = {}
        if events_behind:
            logger.info("snapshot starting — %s events behind", events_behind)
            out = snap.run()
            logger.info("snapshot pushed: %s", out)
        else:
            out = {"pushed": 0, "note": "the event log was already current"}
        if runs_behind:
            try:
                out["runs"] = snap.run_runs()
                logger.info("agent-run snapshot pushed: %s", out["runs"])
            except Exception as e:  # noqa: BLE001
                # A runs failure must never fail the event leg — the ledger's
                # durability is the older and larger promise.
                logger.warning("agent-run snapshot failed: %s", e)
                out["runs"] = {"pushed": 0,
                               "error": f"{type(e).__name__}: {e}"[:200]}
        else:
            out["runs"] = {"pushed": 0,
                           "note": "every run was already offsite and unchanged"}
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

    Copies events AND agent runs; writes nothing to the ledger and moves no
    money. The runs leg is reported separately rather than summed in — a caller
    watching the event log's durability must not have that number moved by an
    unrelated leg, and a runs failure must not read as an events failure.
    """
    if store_backend() != "postgres":
        raise HTTPException(status_code=503,
                            detail="the snapshot copies FROM postgres")
    from app.fund.snapshot_firestore import FirestoreSnapshotter
    try:
        snap = FirestoreSnapshotter(pg_store=_store)
        out = snap.run(dry_run=dry_run)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}"[:300])
    try:
        out["runs"] = snap.run_runs(dry_run=dry_run)
    except Exception as e:  # noqa: BLE001
        # Best effort and SAID so: losing the runs mirror must not fail the
        # event push, and a silent skip would leave the flight recorder
        # single-copy while the response read as a success.
        logger.warning("agent-run snapshot failed: %s", e)
        out["runs"] = {"pushed": 0, "error": f"{type(e).__name__}: {e}"[:300],
                       "note": "the runs leg failed; the event leg above is "
                               "unaffected and its result stands"}
    return out


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
    # WHICH store this durability figure describes. Three modes, three stores:
    # "behind by 0 events" is a different promise depending on which log it is
    # about, and an unlabelled watermark is the same class of statement as the
    # in-memory ledger that reported successful mirroring hourly.
    st["mode"] = _mode_spec.mode.value
    st["ledger_database"] = getattr(_store, "database", None)
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
        # Per-instrument and per-venue cuts. The venue cut exists because one
        # venue in this fund cannot measure execution cost at all, and averaging
        # it in is how "cheaper than modelled" got onto a panel.
        "by_symbol": tca.by_symbol(limit=limit),
        "by_venue": tca.by_venue(limit=limit),
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


# --- the fund's mode: read it, and switch it --------------------------------
class ModeSwitchRequest(BaseModel):
    mode: str
    approver: str
    #: The approval-channel echo. For a mode switch the id being approved IS
    #: the mode, so the echo is its first 8 characters — "nothing can approve
    #: what it has not read" applies to a mode exactly as it does to an order.
    confirm: str | None = None
    instruction: str | None = None
    reason: str = ""


@router.get("/fund/mode")
def get_fund_mode():
    """Which mode this spine is in, which modes exist, and why prod is locked.

    The read side of the CEO's toggle. Deliberately verbose: the failure this
    surface prevents is a human reading a test number as real, so it reports
    the active mode, both of its dimensions, where the declaration came from,
    and the full alpaca-prod precondition list with each item's status.
    """
    return fundmode.report(store=_store)


@router.post("/fund/mode")
def switch_fund_mode(req: ModeSwitchRequest):
    """Switch the fund's mode. A CONTROL, not a preference.

    Four things have to be true, and each of them is a lesson rather than a
    formality:

      1. THE CEO'S CLICK. Same allowlist and same echo as an order approval —
         switching modes changes where real money-shaped orders go, which is a
         larger decision than any single order, so it cannot be a smaller one
         procedurally.
      2. NOTHING IN FLIGHT. An order proposed against one venue and approved
         against another is the phantom-fill shape with a switch on the front.
         Pending AND unresolved-in-flight both block; the check names the
         orders rather than just refusing, so the operator can clear them.
      3. THE DEPARTURE AND THE ARRIVAL ARE BOTH RECORDED. The event goes into
         the store being LEFT and the store being ENTERED. Neither log gets a
         silent gap. The two are never joined — each holds its own half.
      4. THE CHOICE IS DURABLE. Written to the mode file, so a restart does
         not quietly revert the switch. A toggle a restart undoes is the same
         trapdoor as a defaulting ledger flag.
    """
    from app.fund.events import Event, EventType

    try:
        target = fundmode.parse_mode(req.mode)
    except fundmode.ModeError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if target is _mode_spec.mode:
        return {"switched": False, "mode": target.value,
                "note": f"already in {target.value}"}

    # (1) the approval channel, echoing the MODE being switched to.
    approver = _guard_approval("fund_mode", target.value, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)

    # alpaca-prod: the code lock and the precondition list, both.
    if target is fundmode.FundMode.ALPACA_PROD:
        gate = fundmode.prod_gate_report(store=_store)
        raise HTTPException(
            status_code=403,
            detail={"refused": "alpaca-prod is structurally unreachable",
                    "prod_gate": gate})

    # (2) nothing may be in flight across the switch.
    blocking = []
    try:
        blocking = ([{"order_id": r["order_id"], "state": "pending_approval"}
                     for r in _orders.pending()]
                    + [{"order_id": r["order_id"], "state": "in_flight"}
                       for r in _orders.in_flight()])
    except Exception as e:  # noqa: BLE001 — unreadable is NOT "nothing pending"
        raise HTTPException(
            status_code=503,
            detail=f"cannot read the order queue ({type(e).__name__}: {e}), so "
                   "it cannot be shown to be empty. Refusing to switch modes "
                   "against an unknown queue — unreadable is not unchanged.")
    if blocking:
        raise HTTPException(
            status_code=409,
            detail={"refused": "orders are open across the switch",
                    "orders": blocking,
                    "why": "an order proposed against one venue and resolved "
                           "against another is the phantom-fill shape with a "
                           "switch on the front"})

    # (2b) THE FILL STREAM MUST STOP BEFORE THE STORE MOVES.
    #
    # TradeStream captures the pipeline it was constructed with, so a stream
    # started in alpaca-paper holds the OLD pipeline — old connector, old
    # store — for as long as it lives. Rewiring underneath it would leave a
    # socket subscribed to the Alpaca account writing fills into the store we
    # just left, which is the two-books-in-one-process failure this whole
    # module exists to make impossible, arriving through the one object that
    # does not go through `_wire`.
    #
    # Found by reading the diff, not by a test: nothing in the suite starts a
    # real stream.
    stream_was_live = _trade_stream is not None
    if stream_was_live:
        stop_trade_stream()

    previous = _mode_spec
    at = datetime.now(timezone.utc).isoformat()
    payload = {"from": previous.mode.value, "to": target.value,
               "from_ledger": previous.pg_database,
               "to_ledger": fundmode.MODES[target].pg_database,
               "approver": approver, "reason": req.reason, "at": at}

    # (3a) the DEPARTURE, into the store being left, before anything moves.
    _store.append(Event(aggregate_id="fund", aggregate_type="fund",
                        type=EventType.FUND_MODE_SWITCHED,
                        payload={**payload, "leg": "departure"},
                        actor=approver))

    # (4) durable, then rewire.
    record = fundmode.write_mode_file(target, actor=approver,
                                      reason=req.reason or "(no reason given)")
    try:
        _wire(fundmode.activate(fundmode.MODES[target], force=True))
    except Exception as e:  # noqa: BLE001
        # Put the process back where it was AND the file with it, so a failed
        # switch does not leave a spine and a file disagreeing — which
        # ``resolve()`` would refuse to start on next boot.
        fundmode.write_mode_file(previous.mode, actor=approver,
                                 reason=f"rolled back: switch to "
                                        f"{target.value} failed ({e})")
        _wire(fundmode.activate(previous, force=True))
        raise HTTPException(
            status_code=500,
            detail=f"switch to {target.value} failed and was rolled back to "
                   f"{previous.mode.value}: {type(e).__name__}: {e}")

    # (3b) the ARRIVAL, into the store now in force. _store is the new one.
    _store.append(Event(aggregate_id="fund", aggregate_type="fund",
                        type=EventType.FUND_MODE_SWITCHED,
                        payload={**payload, "leg": "arrival"},
                        actor=approver))
    _riskengine.invalidate()

    # The stream is NOT auto-restarted, and that is stated rather than silent.
    # Restarting it needs the running event loop's `create_task`, and a fill
    # observer that comes back up by itself after a mode change is exactly the
    # kind of thing that should be a deliberate act. The poller underneath it
    # keeps working — it is the backstop and it reads the new wiring — so this
    # degrades to slower, never to blind, and the response says which.
    return {"switched": True, "from": previous.mode.value, "to": target.value,
            "persisted": record,
            "fill_stream": ("stopped — restart the spine to re-subscribe; the "
                            "settlement poller is still running underneath"
                            if stream_was_live else "was not running"),
            "mode": fundmode.report(store=_store)}


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
    # Where state lives and where ORDERS go are separate facts, and a test mode
    # must never hide that real orders are leaving the building. Report both,
    # from the MODE rather than from a pair of environment flags.
    venue = getattr(_connector, "name", "unknown")
    return {**info,
            "is_production": info.get("env") == "production",
            "venue": venue,
            "mode": _mode_spec.mode.value,
            "ledger_database": _mode_spec.pg_database,
            # "Real" here has always meant "leaving the building for a broker",
            # which is true of the Alpaca PAPER account too — a queued order at
            # a real venue is not a simulation. Whether real MONEY can move is
            # the separate, sharper question beside it.
            "orders_are_real": _mode_spec.real_broker,
            "real_money": _mode_spec.real_money,
            "seeder_may_run": not _mode_spec.real_broker,
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
    """One candidate, with the ANALYTICS the verdict was computed from.

    Additive since 2026-08-21: `analytics` carries the verification run's equity
    curve, benchmark curve and fills, the cost sweep's grid, and the per-fold
    walk-forward rows. Every pre-existing field is unchanged — the Lab's belt
    table and the mechanics view both read this shape.

    `analytics.available` is false for the four typed absences (never captured /
    pruned / unavailable / not testable) and carries the sentence that says
    which. A candidate judged before the belt kept its evidence renders as
    NOT CAPTURED, never as an empty panel — see app/fund/runanalytics.py.
    """
    f = _factory()
    if f is None:
        raise HTTPException(status_code=503, detail="the factory needs FUND_STORE=postgres")
    out = f.get(candidate_id)
    if out is None:
        raise HTTPException(status_code=404, detail=f"unknown candidate {candidate_id!r}")
    return out


@router.get("/fund/factory/candidates")
def factory_history(algorithm: str | None = Query(None), limit: int = Query(50, ge=1, le=500)):
    """What has already been tried, and why it died.

    The INDEX read: every row carries `walkforward.folds` (requested dates, the
    window the engine covered, `dates_honoured`, and each fold's own reason for
    being measurable or not) and `analytics_available`, but NOT the equity curves
    or the fills — those are ~80 KB each and have one reader, the panel for the
    run you opened. GET the individual candidate for those.
    """
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


@router.post("/fund/factory/reconcile")
def factory_reconcile(max_age_hours: float | None = Query(None, gt=0)):
    """Close out candidates whose runner died, without inventing a verdict.

    A candidate row lives in Postgres; the thread that finishes it does not. Every
    spine restart therefore left any in-flight candidate stuck in `running`
    forever, silently subtracting from the judged count. They become `orphaned`,
    which is neither passed nor failed - an interrupted run produced no evidence.
    """
    f = _factory()
    if f is None:
        raise HTTPException(status_code=503,
                            detail="the factory needs FUND_STORE=postgres")
    return f.reconcile_orphans(max_age_hours)


class DeskRequest(BaseModel):
    """The operator asking the bench for work. Human-initiated, always."""
    kind: str            # proposal | attack | audit
    subject: str         # what to propose on / attack / audit
    note: str = ""
    actor: str = "operator"
    # The chatter thread. Usually absent here — a request BIRTHS a trace and
    # the trace_id defaults to the request_id. Passed explicitly only when
    # this request continues an existing chain (e.g. an adversary attack on
    # a thesis keeps the thesis's trace).
    trace_id: Optional[str] = None


@router.get("/fund/desk")
def research_desk():
    """The firm's bench, its artifact chain, and its open requests.

    The spine records requests and reads artifacts from docs/; it does not run
    agents. That honesty line is carried in the payload so the UI renders it.
    """
    from app.fund import desk
    # Pending orders are part of the CEO's open-item count (the COO triage
    # trigger), and unreadable pending orders make the count INCOMPLETE rather
    # than smaller — desk_load says which component it could not read.
    pending = None
    try:
        pending = _orders.pending()
    except Exception as e:  # noqa: BLE001
        logger.info("desk load: pending orders unreadable: %s", e)
    return desk.view(_store, deskstore=_deskstore(), pending_orders=pending)


@router.post("/fund/desk/requests")
def desk_request(req: DeskRequest):
    """Record a work request for the bench. Writes an event and moves no money."""
    from app.fund import desk as desk_mod
    from app.fund.events import Event, EventType
    kind = (req.kind or "").strip().lower()
    if kind not in desk_mod.REQUEST_KINDS:
        raise HTTPException(status_code=422,
                            detail=f"kind must be one of "
                                   f"{sorted(desk_mod.REQUEST_KINDS)}")
    if not (req.subject or "").strip():
        raise HTTPException(status_code=422,
                            detail="a request needs a subject - 'do research' is "
                                   "not an ask the bench can act on")
    import uuid
    rid = str(uuid.uuid4())
    payload = {"request_id": rid, "kind": kind,
               "serves": desk_mod.REQUEST_KINDS[kind],
               "subject": req.subject.strip(), "note": req.note or "",
               "trace_id": (req.trace_id or "").strip() or rid,
               "at": datetime.now(timezone.utc).isoformat(),
               "actor": req.actor}
    _store.append(Event(aggregate_id=payload["request_id"],
                        aggregate_type="desk_request",
                        type=EventType.DESK_REQUESTED,
                        payload=payload, actor=req.actor))
    return payload


class DeskDispatch(BaseModel):
    """The CTO recording that a seat has been put to work. CTO-only by protocol."""
    seat: str
    task: str
    request_id: Optional[str] = None
    actor: str = "cto"
    trace_id: Optional[str] = None


@router.post("/fund/desk/dispatch")
def desk_dispatch(req: DeskDispatch):
    """Record a dispatch so the desk can show what each seat is doing.

    The spine cannot watch an agent think; this records the truthful envelope -
    dispatched at T, delivered at T2 - and the UI renders exactly that.
    """
    from app.fund import desk as desk_mod
    from app.fund.events import Event, EventType
    seats = set(desk_mod.REQUEST_KINDS.values())
    if req.seat not in seats:
        raise HTTPException(status_code=422,
                            detail=f"seat must be one of {sorted(seats)}")
    if not (req.task or "").strip():
        raise HTTPException(status_code=422, detail="name the task")
    import uuid
    tid = req.request_id or str(uuid.uuid4())
    payload = {"task_id": tid,
               "seat": req.seat, "task": req.task.strip(),
               "request_id": req.request_id,
               # A dispatch continues the request's trace when there is one;
               # a CTO-initiated dispatch with no request births its own.
               "trace_id": (req.trace_id or "").strip() or tid,
               "at": datetime.now(timezone.utc).isoformat(), "actor": req.actor}
    _store.append(Event(aggregate_id=payload["task_id"],
                        aggregate_type="desk_request",
                        type=EventType.DESK_DISPATCHED,
                        payload=payload, actor=req.actor))
    return payload


class DeskApprove(BaseModel):
    """The CEO endorsing a queued request for dispatch. Approval is not a
    trigger — the CTO still fires the dispatch; this records that the ask has
    the CEO's blessing, which is what a seat-filed request waits for."""
    actor: str = "ceo"
    note: str = ""
    confirm: Optional[str] = None      # approval-channel guard v1: echo of id[:8]
    instruction: Optional[str] = None  # via-cto: the CEO's quoted instruction


@router.post("/fund/desk/requests/{request_id}/approve")
def desk_approve(request_id: str, req: DeskApprove):
    from app.fund.events import Event, EventType
    actor = _guard_approval("desk_request", request_id, req.actor, req.confirm,
                            req.instruction, DESK_APPROVAL_ALLOWLIST)
    payload = {"request_id": request_id, "actor": actor,
               "note": req.note or "",
               "at": datetime.now(timezone.utc).isoformat()}
    _store.append(Event(aggregate_id=request_id, aggregate_type="desk_request",
                        type=EventType.DESK_REQUEST_APPROVED,
                        payload=payload, actor=req.actor))
    return payload


class DeskDecline(BaseModel):
    """The CEO rejecting a queued request. Like order declines, deliberately
    OUTSIDE the approval guard: a decline is reversible (the ask can be
    re-filed) and closing a door must never be harder than opening one. The
    reason is mandatory — a silent rejection reads identically to an unseen
    ask."""
    reason: str
    actor: str = "ceo"


@router.post("/fund/desk/requests/{request_id}/decline")
def desk_decline(request_id: str, req: DeskDecline):
    """Reject a request — allowed while open OR approved-but-untriggered
    (withdrawing a blessing before the CTO fires it is a real decision and
    deserves a real record). A resolved request is history and stays."""
    from app.fund.events import Event, EventType
    if not (req.reason or "").strip():
        raise HTTPException(status_code=422,
                            detail="a rejection needs its written reason")
    from app.fund.desk import _requests
    row = next((r for r in _requests(_store)
                if r.get("request_id") == request_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="no such request")
    if row.get("status") in ("resolved", "declined"):
        raise HTTPException(
            status_code=409,
            detail=f"request is already {row['status']} — history stays")
    payload = {"request_id": request_id, "reason": req.reason.strip(),
               "at": datetime.now(timezone.utc).isoformat(),
               "actor": req.actor}
    _store.append(Event(aggregate_id=request_id, aggregate_type="desk_request",
                        type=EventType.DESK_REQUEST_DECLINED,
                        payload=payload, actor=req.actor))
    return payload


class DeskResolve(BaseModel):
    resolution: str
    actor: str = "cto"
    trace_id: Optional[str] = None


@router.post("/fund/desk/requests/{request_id}/resolve")
def desk_resolve(request_id: str, req: DeskResolve):
    """Mark a request served, with the artifact that served it named."""
    from app.fund.events import Event, EventType
    if not (req.resolution or "").strip():
        raise HTTPException(status_code=422,
                            detail="name the artifact that served this request")
    payload = {"request_id": request_id, "resolution": req.resolution.strip(),
               "trace_id": (req.trace_id or "").strip() or request_id,
               "at": datetime.now(timezone.utc).isoformat(), "actor": req.actor}
    _store.append(Event(aggregate_id=request_id, aggregate_type="desk_request",
                        type=EventType.DESK_REQUEST_RESOLVED,
                        payload=payload, actor=req.actor))
    return payload


_deskstore_cache = None


def _deskstore():
    global _deskstore_cache
    if _deskstore_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.deskstore import DeskStore
        _deskstore_cache = DeskStore()
    return _deskstore_cache


class AgentRunRecord(BaseModel):
    """One agent dispatch, recorded whole. CTO writes this at resolve time."""
    run_id: str
    seat: str
    task: str
    output: str
    model: Optional[str] = None
    tokens: Optional[int] = None
    tool_uses: Optional[int] = None
    # THE CHAIR PASSES THIS AT RECORD TIME and nothing else can: the recorder
    # is written at RESOLVE, so without it the row knows when the work
    # finished and not when it started, and the run has no wall-clock at all.
    # Measured 2026-08-22: 7 of 52 rows carry it, so 45 runs report an UNKNOWN
    # duration — which is the honest reading, and the reason to start passing
    # it. ISO-8601 UTC.
    dispatched_at: Optional[str] = None
    # WHAT BECAME OF THE DISPATCH: delivered | failed | aborted. Absent means
    # the chair stated no outcome and reads as `unrecorded` — never as success.
    # A failed run is recordable precisely so that work which DIES stops
    # costing zero: today's meter records at resolve, so a dispatch that
    # collapses with the host leaves no row and no cost. An unrecognised value
    # is REFUSED (422) rather than nulled.
    status: Optional[str] = None
    artifact_path: Optional[str] = None
    verdict: Optional[str] = None
    # The distilled why: 3-6 bullets, written at resolve, rendered on the desk.
    reasoning: Optional[str] = None
    # The chatter thread this run belongs to — the desk request's trace_id,
    # carried verbatim so the whole chain replays from one id.
    trace_id: Optional[str] = None
    # Each recommendation is {kind, text, money_at_stake?, next_actor?,
    # due_date?}.
    # `money_at_stake` is an OPTIONAL float: the dollars this recommendation
    # moves, stated by the seat. Absent means the seat did not state one —
    # never zero — and the desk ranks absent-last and prints the gap.
    # `next_actor` is an OPTIONAL string (ceo | chair | seat | nobody): whose
    # move it is. Absent means the desk INFERS it from lifecycle and kind, and
    # `desk_load.explicit_next_actor` reports how many rows declared it, so a
    # reader can tell a count built on declaration from one built on inference.
    # `due_date` is an OPTIONAL YYYY-MM-DD dated commitment — the day something
    # happens whether or not anybody clicks. It is the CEO desk's TOP ranking
    # key, so a seat filing a time exit or an auto-close should state it here;
    # it is never read out of the recommendation's prose.
    recommendations: Optional[list[dict]] = None
    meta: Optional[dict] = None


@router.post("/fund/desk/runs")
def record_agent_run(req: AgentRunRecord):
    """Store an agent run whole - the desk's flight recorder.

    TWO FIELDS THE CHAIR MUST PASS AND HISTORICALLY HAS NOT:

    * ``dispatched_at`` — the only source of a run's wall-clock, because this
      endpoint is called at RESOLVE. 7 of 52 live rows carry it.
    * ``status`` — ``delivered`` / ``failed`` / ``aborted``. A dispatch that
      dies is recorded with ``status="failed"`` and whatever tokens it burned;
      without it, failed work costs zero by construction and the firm's
      self-knowledge is biased by exactly the amount of work that failed.

    RE-POSTING THE SAME ``run_id`` IS A CORRECTION, NOT A REPLACEMENT: every
    nullable field upserts through COALESCE, so omitting one leaves the stored
    value alone.
    """
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    try:
        return ds.record_run(**req.model_dump())
    except ValueError as e:
        # A mistyped `status` is a 422, not a 500 and not a silent null — the
        # caller is the chair or a script, and it should see which value was
        # refused rather than discover later that an outcome went unrecorded.
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/desk/runs")
def list_agent_runs(seat: str | None = Query(None),
                    limit: int = Query(50, ge=1, le=500)):
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    return {"runs": ds.runs(seat=seat, limit=limit)}


@router.get("/fund/desk/runs/stats")
def agent_run_stats():
    """LIFETIME per-seat run aggregates — UNCAPPED, with a truncation proof.

    **DECLARED BEFORE ``/fund/desk/runs/{run_id}`` ON PURPOSE.** FastAPI matches
    routes in declaration order, so a literal path registered after a path
    parameter on the same prefix is unreachable — this endpoint would return
    404 "no run stats" instead of the stats. A test pins the order.

    Exists because the firm's first spend meter was hand-assembled from
    ``GET /fund/desk/runs``'s default payload, whose 25-run cap ``deskstore``
    itself documents as "a FLOOR wearing the costume of a count", while
    lifetime runs were 49+. Nobody noticed until someone queried with limit=500.

    So this reports ``row_count`` (from ``SELECT count(*)``) beside
    ``rows_read`` and sets ``truncated``: the answer says whether it is
    complete, rather than leaving the reader to assume.

    Per seat: runs, tokens, tool uses, first/last resolution, median wall-clock
    where ``dispatched_at`` was recorded, and the outcome split. Absences are
    named, never zeroed — a seat with no token counts reports ``tokens: null``
    with ``runs_missing_tokens``, and a run with no ``status`` is
    ``unrecorded``, which is not ``delivered``.
    """
    from app.fund import metrics
    return metrics.run_stats(_deskstore())


@router.get("/fund/desk/runs/{run_id}")
def get_agent_run(run_id: str):
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    got = ds.run(run_id)
    if got is None:
        raise HTTPException(status_code=404, detail=f"no run {run_id}")
    return got


class TranscriptRecord(BaseModel):
    #: brief | report | transcript — a closed set, so "did we keep the brief"
    #: is answerable by query rather than by grepping a free-text column.
    kind: str
    content: str
    meta: Optional[dict] = None


@router.post("/fund/desk/runs/{run_id}/transcript")
def add_run_transcript(run_id: str, req: TranscriptRecord):
    """Store the INTERACTION behind a run — the brief, the verbatim report, or
    the turn log (CEO decision, 2026-08-21).

    `fund_agent_runs.output` holds what a seat CONCLUDED. It does not hold what
    we asked, nor how the seat got there, and both currently live only in a
    session that ends. This is the durable copy.

    APPEND-ONLY: a second `brief` for the same run is a second row, not an
    overwrite — a dispatch that gained a mid-flight course correction had two
    briefs, and collapsing them would erase that the scope moved.

    There is NO retention policy, deliberately (the CEO said so explicitly).
    Cleanup is a later versioned decision with a written reason.
    """
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    try:
        return ds.add_transcript(run_id=run_id, kind=req.kind,
                                 content=req.content, meta=req.meta)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/desk/runs/{run_id}/transcript")
def get_run_transcript(run_id: str, kind: str | None = Query(None),
                       with_content: bool = Query(True)):
    """The interaction behind a run, OLDEST FIRST — it is a chronology.

    Reports `kinds_missing` as well as what is present: "no brief was captured
    for this run" is the answer a reader most often wants and the easiest one to
    mistake for "this run had no brief".
    """
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    return ds.transcripts(run_id, kind=kind, with_content=with_content)


@router.get("/fund/desk/archives")
def desk_archives():
    """Every Daily the secretary has filed, newest first.

    Exists so the Studio never reads the filesystem: the spine owns what is on
    disk, the browser owns what is on screen, and a page that stats files breaks
    the moment it is served from anywhere but this machine.

    Distinguishes three absences — the directory missing, present-and-empty, and
    unreadable — because a caller that cannot tell them apart reports "no
    dailies" for a permissions error.
    """
    from app.fund import desk as desk_mod
    return desk_mod.archives()


@router.get("/fund/desk/archives/memo")
def desk_archive_memo(date: Optional[str] = None):
    """The secretary's Daily, parsed for the memo card on the CEO's desk.

    THE CEO SAW THE ABSENCE AND ASKED ABOUT IT. The card, the TypeScript type
    and its five-way absence vocabulary all merged; this route did not exist,
    so the card has rendered a permanent "no memo" caused entirely by its own
    missing endpoint. A control reporting an absence it manufactures is the
    unwired-kill-switch pattern with a friendly face.

    Without `date`, the newest DATED archive. With one, that day exactly. The
    parameter is never joined into a path — it is matched against the index
    `archives()` builds by globbing `docs/archives/*.md`, so this route can
    only ever read a file that directory listed — and it is additionally
    validated against YYYY-MM-DD so a malformed parameter can be told apart
    from a day nobody documented.

    Always 200. The five absences are DATA (`available` + `reason`), not
    statuses: the client must be able to tell "she has never run" from "no
    session was live that day" from "the file is unreadable", and an HTTP code
    can only say "no". That is the same reason `/fund/desk/archives` returns
    its three absences in the body.
    """
    from app.fund import desk as desk_mod
    return desk_mod.archive_memo(date)


class RecDecision(BaseModel):
    status: str          # accepted | rejected | staged | done | noted
    actor: str = "ceo"
    note: str = ""
    # OPTIONAL: whose move it is NEXT, which is a different question from what
    # the decision was. One of ceo / chair / seat / nobody. Its indispensable
    # case is an `accepted` row whose EXECUTION is still the CEO's own act —
    # the desk's counter otherwise infers every accepted row onto the chair,
    # which is the COO's standing objection of 2026-08-21. Refused on a
    # terminal status; absent means the desk infers.
    next_actor: Optional[str] = None


@router.post("/fund/desk/runs/{run_id}/recommendations/{rec_id}")
def decide_recommendation(run_id: str, rec_id: int, req: RecDecision):
    """A decision on an agent's recommendation - state in the table, the
    decision itself on the event log. Both, and they must agree."""
    ds = _deskstore()
    if ds is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    from app.fund.events import Event, EventType
    try:
        hit = ds.decide_recommendation(run_id, rec_id, req.status, req.actor,
                                       req.note, next_actor=req.next_actor)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    _store.append(Event(aggregate_id=run_id, aggregate_type="desk_run",
                        type=EventType.DESK_RECOMMENDATION_DECIDED,
                        payload={"run_id": run_id, "rec_id": rec_id,
                                 "status": req.status, "note": req.note,
                                 "text": hit.get("text"),
                                 "seat": hit.get("seat"),
                                 # On the event too, not just the table: the
                                 # log is where "who owed what, when" is
                                 # reconstructed, and a routing decision that
                                 # existed only in current state would be
                                 # unrecoverable the moment it changed.
                                 "next_actor": hit.get("next_actor"),
                                 "trace_id": hit.get("trace_id"),
                                 "at": datetime.now(timezone.utc).isoformat()},
                        actor=req.actor))
    return hit


@router.get("/fund/mechanics")
def fund_mechanics():
    """How a hunch becomes a position, what dies on the way, and when.

    Read as selection, because that is what the machinery does: a candidate is a
    GRID (variation), the gate kills (selection), strategies carry parent/child
    and member weights (composition), and the gate ITSELF has four generations.

    Facts are resolved here and passed in, on the same reasoning as the digest:
    the view is a reading over the machinery, never a second place that knows how
    to run it. Every block degrades to a stated absence.
    """
    from app.fund import mechanics
    from app.fund.gate import GATE_VERSION

    def _try(fn, label):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            logger.info("mechanics: %s unavailable: %s", label, e)
            return None

    obs = None
    o = _observations()
    if o is not None:
        obs = _try(lambda: o.coverage(), "observations")

    return mechanics.build(
        candidates=_try(lambda: factory_history(None, 500), "candidates"),
        strategies=_try(lambda: list_strategies(), "strategies"),
        observations=obs,
        approvals=_try(lambda: {"pending": _orders.pending() or []}, "approvals"),
        exits=_try(lambda: check_exit_rules(None), "exits"),
        # Newest-first from the tail, which is what /fund/events returns. The
        # timeline sorts ascending itself rather than trusting the order.
        events=_try(lambda: get_events(since_seq=0, limit=1000), "events"),
        gate_version=GATE_VERSION,
    )


@router.get("/fund/doctrine")
def operating_doctrine():
    """The seven-stage workflow, with each stage's status read LIVE where possible.

    docs/FUND_GENESIS.md is canonical. This endpoint exists so the workflow can be
    a surface rather than a page, and status is READ rather than restated - a
    doctrine view that hardcoded "stage 02: HOLDS" would reproduce the exact
    failure stage 02 exists because of.
    """
    from app.fund import doctrine, judgement
    judgement.use_control(_control)
    return doctrine.review()


@router.get("/fund/liveness")
def scheduled_job_liveness():
    """Which periodic jobs have actually run, and which are overdue.

    Exists because the harness could not previously tell a control that reported
    nothing from a control that never ran. The risk monitor - the only code that
    trips the drawdown and daily-loss halts - had zero callers, and its silence
    was indistinguishable from a calm book.
    """
    from app.fund import heartbeat
    return heartbeat.report()


@router.get("/fund/judgement")
def judgement_register(today: str | None = Query(None)):
    """The thresholds we chose ourselves, and what would show we chose wrong.

    Every number here decides verdicts. Six of them are judged rather than
    measured, which is defensible only while it is visible — so the register reads
    each value from the running fund rather than restating it, and reports drift
    between the number in force and the reason on file.
    """
    from app.fund import judgement
    judgement.use_control(_control)
    judgement.use_metrics(_judgement_metrics)
    return judgement.review(today)


def _judgement_metrics() -> dict[str, Any]:
    """The live metric namespace machine-checkable review triggers read.

    Deliberately small and deliberately CHEAP relative to the alternative: one
    `assess()` per register read, not one per entry. `risk_advanced.*` is NOT
    in here — that view computes a covariance matrix over 174 observations, and
    a register that recomputes it on every poll would be switched off. Entries
    wanting an advanced-risk trigger keep prose until there is a cached view to
    read; that is a stated gap, not an oversight.

    An unreadable metric is ABSENT from this dict, never zero — TriggerSpec
    reports a missing key as UNCHECKED, which is the honest reading.
    """
    out: dict[str, Any] = {}
    try:
        a = _monitor.assess()
    except Exception as e:  # noqa: BLE001
        logger.info("judgement metrics: risk monitor unreadable: %s", e)
        return out
    dd = a.get("drawdown") or {}
    for src, dst in (("drawdown_pct", "risk_monitor.drawdown_pct"),
                     ("max_drawdown_pct", "risk_monitor.max_drawdown_pct"),
                     ("peak_nav", "risk_monitor.peak_nav")):
        if dd.get(src) is not None:
            out[dst] = dd[src]
    if dd.get("utilization") is not None:
        out["risk_monitor.drawdown_utilization_pct"] = dd["utilization"] * 100.0
    for src, dst in (("nav_usd", "risk_monitor.nav_usd"),
                     ("cash_pct", "risk_monitor.cash_pct"),
                     ("gross_exposure_pct", "risk_monitor.gross_exposure_pct")):
        if a.get(src) is not None:
            out[dst] = a[src]
    out["risk_monitor.open_alarms"] = len(a.get("alarms") or [])
    out["risk_monitor.halted"] = 1.0 if a.get("halted") else 0.0
    return out


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

    # Our own thresholds, resolved here for the same reason NAV is: the digest
    # reads facts, it does not go and find them.
    knobs = None
    try:
        from app.fund import judgement
        judgement.use_control(_control)
        knobs = judgement.review()
    except Exception as e:  # noqa: BLE001
        logger.info("digest: judgement register unavailable: %s", e)

    from app.fund.digest import build as build_digest
    return build_digest(store=_store, observations=o, factory=f,
                        universe=_universe(), nav=nav_block,
                        approvals=approvals, adv_band=adv_band,
                        deployed=deployed, since_hours=since_hours,
                        knobs=knobs)


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


# --- approval-channel guard v1 (2026-08-20, CEO decision) --------------------
# Written reason: the approver field was free text accepted from anything on
# localhost — exactly as forgeable as the exit-rule marker string autopolicy v1
# trusted. On a one-box deployment identity cannot be proven cryptographically,
# so v1 closes the two risks that are closable: approval by ACCIDENT (a stray
# script, a replayed command, a probing seat) and approval without
# ATTRIBUTION. Three checks, all fail-closed, approvals only (declines are
# reversible and stay open):
#   1. allowlist — only "neelesh" (the CEO's own click) and "neelesh-via-cto"
#      (the CTO executing an EXPLICIT CEO instruction) may approve;
#   2. echo — the request must repeat the first 8 chars of the id it
#      approves: nothing can approve what it has not read;
#   3. citation — a via-cto approval must quote the CEO's instruction
#      verbatim; the quote lands in the approval event for the riskofficer.
# A refused approval is RECORDED as an ApprovalRefused event: a probe becomes
# a finding, not a fill. Widening this allowlist is a versioned change.
# v1.1 (2026-08-20, CEO instruction "rushi is out of the picture; your ceo is
# neelesh"): the approval identity migrated rushi -> neelesh. Historical
# events keep the rushi actor they were recorded with; the name can no longer
# approve anything.
# v1.2 (2026-08-21, CEO decision — the co-CTO chair): "neelesh-via-co-cto"
# added to both allowlists. Same rules as via-cto (echo + verbatim CEO
# instruction), distinct identity so the record shows WHICH chair staged
# every approval — the co-CTO's actions are auditable as a set, by Fable
# and by the riskofficer, without reading a single diff. The co-CTO's
# charter (what it may and may not do) lives in the firm constitution;
# this guard only makes its footprint attributable.
APPROVAL_ALLOWLIST = {"neelesh", "neelesh-via-cto", "neelesh-via-co-cto"}
DESK_APPROVAL_ALLOWLIST = {"ceo", "neelesh", "neelesh-via-cto",
                           "neelesh-via-co-cto"}


def _guard_approval(kind: str, target_id: str, approver: str,
                    confirm: str | None, instruction: str | None,
                    allowlist: set[str]) -> str:
    """Refuse-and-record, or return the attribution string to pass downstream."""
    from app.fund.events import Event, EventType
    who = (approver or "").strip().lower()
    want = (target_id or "")[:8]
    reason = None
    if who not in allowlist:
        reason = (f"approver '{approver}' is not on the approval allowlist "
                  f"{sorted(allowlist)} — approval-channel guard v1")
    elif (confirm or "").strip() != want:
        reason = (f"confirm echo missing or wrong: approving this {kind} "
                  f"requires confirm='{want}' (the first 8 chars of its id)")
    elif (who in ("neelesh-via-cto", "neelesh-via-co-cto")
          and not (instruction or "").strip()):
        reason = (f"a {who.split('neelesh-')[1]} approval must quote the "
                  "CEO's explicit instruction verbatim in 'instruction'")
    if reason:
        _store.append(Event(
            aggregate_id=target_id or "unknown", aggregate_type=kind,
            type=EventType.APPROVAL_REFUSED,
            payload={"kind": kind, "target_id": target_id,
                     "approver": approver or "", "reason": reason,
                     "at": datetime.now(timezone.utc).isoformat()},
            actor=approver or "unknown"))
        raise HTTPException(status_code=403, detail=f"approval refused: {reason}")
    if who in ("neelesh-via-cto", "neelesh-via-co-cto"):
        return f"{who} [{(instruction or '').strip()}]"
    return approver


@router.post("/fund/orders/{order_id}/approve")
def approve_order(order_id: str, req: ApprovalRequest):
    """Human approval gate — approving triggers idempotent execution.

    Two guards, in order, both fail-closed and both recording an
    ApprovalRefused event so a refused click is a finding rather than silence:

      1. the approval-channel guard (who, echo, citation) — v1, above;
      2. MARK SANITY — v1, 2026-08-21. The price the order was RAISED at must
         agree with the fund's own last struck mark within the SAME versioned
         bound the auto-policy uses. This is the check whose absence cost
         $128.26: the GLD sell at $100.00 against a $415.04 strike took exactly
         this path, and the machine had been refusing that shape since
         autopolicy v2 while the human had no check at all. See
         app/fund/marksanity.py for the three cases and the one judgement.
    """
    approver = _guard_approval("order", order_id, req.approver, req.confirm,
                               req.instruction, APPROVAL_ALLOWLIST)
    _guard_mark_sanity(order_id, approver)
    try:
        return _pipeline.approve_order(order_id, approver=approver)
    except CommandError as e:
        raise HTTPException(status_code=409, detail=str(e))


def _guard_mark_sanity(order_id: str, approver: str) -> dict:
    """Refuse-and-record an approval whose price the fund's own marks contradict.

    Returns the verdict on a pass, so the caller could attach it to the approval
    if that is ever wanted; raises 409 on a refusal. 409, not 403: the channel
    guard's 403 means "you may not approve", and this means "this order is not
    in a state to be approved" — a different fact, and one a re-strike or a
    re-proposal clears.
    """
    from app.fund.events import Event, EventType
    from app.fund import marksanity

    verdict = marksanity.check(_store, order_id)
    if not verdict.get("refuse"):
        return verdict
    _store.append(Event(
        aggregate_id=order_id, aggregate_type="order",
        type=EventType.APPROVAL_REFUSED,
        payload={"kind": "order", "target_id": order_id,
                 "approver": approver or "", "guard": "mark_sanity_v1",
                 "reason": verdict["reason"],
                 # Both numbers on the record, always. A refusal whose numbers
                 # live only in an HTTP response is a refusal nobody can audit.
                 "quote_price": verdict.get("quote_price"),
                 "reference_mark": verdict.get("reference_mark"),
                 "move_pct": verdict.get("move_pct"),
                 "bound_pct": verdict.get("bound_pct"),
                 "basis": verdict.get("basis"),
                 "at": datetime.now(timezone.utc).isoformat()},
        actor=approver or "unknown"))
    raise HTTPException(status_code=409,
                        detail=f"approval refused: {verdict['reason']}")


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
    actor: str = "neelesh"
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


# --- book <-> venue reconciliation (CEO decision, 2026-08-21) ---------------
class VenueSyncApplyRequest(BaseModel):
    approver: str
    #: The approval-channel echo — the first 8 characters of the PLAN's run_id.
    #: Nothing can approve what it has not read, and here that means the
    #: operator has fetched the plan and is approving THAT plan, not a
    #: reconciliation in the abstract against a broker reading that has since
    #: moved (broker equity moved $0.03 between two readings four hours apart
    #: on 2026-08-22 — it is a live number, and approving "a sync" rather than
    #: "this sync" would apply whatever the broker happens to say at click
    #: time).
    confirm: str | None = None
    instruction: str | None = None
    run_id: str
    reason: str


def _venue_sync_plan():
    from app.fund import venuesync

    return venuesync.plan(connector=_connector, store=_store,
                          nav_service=_nav, attribution=_attribution,
                          pricer=_connector.price)


@router.get("/fund/venue/sync/plan")
def get_venue_sync_plan():
    """DRY RUN: exactly what reconciling the book to the venue would write.

    Reads both sides and writes nothing. Refuses rather than guessing on any
    absence — an unreadable broker, a missing cash figure, or a symbol with no
    mark all raise, because a reconciliation computed against a partial
    reading moves NAV by a number nobody measured.
    """
    from app.fund import venuesync

    if not _mode_spec.real_broker:
        raise HTTPException(
            status_code=400,
            detail=f"mode {_mode_spec.mode.value!r} runs on a simulated venue "
                   "— there is no second opinion to reconcile against")
    try:
        return _venue_sync_plan().to_dict()
    except venuesync.VenueSyncError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502,
                            detail=f"venue unreadable: {type(e).__name__}: {e}")


@router.post("/fund/venue/sync/apply")
def apply_venue_sync(req: VenueSyncApplyRequest):
    """Append the reconciling event. THE CEO'S CLICK, and nothing less.

    NAV steps for a NON-MARKET reason here, so every clean-field guard rail is
    on this path: the magnitude is measured from two readings (never a plug),
    the pre-sync values are preserved in the payload beside the new ones, the
    approval channel records who and the request carries why, and the P&L
    reader reports the step separately from performance forever after.

    It does NOT read broker equity as NAV. It appends, and the FOLD produces
    the matching answer.
    """
    from app.fund import venuesync

    if not _mode_spec.real_broker:
        raise HTTPException(
            status_code=400,
            detail=f"mode {_mode_spec.mode.value!r} runs on a simulated venue")

    approver = _guard_approval("venue_sync", req.run_id, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)
    try:
        plan = _venue_sync_plan()
    except venuesync.VenueSyncError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # The plan is re-read here rather than trusted from the client, so the
    # numbers written are ones this process just measured. The run_id the
    # operator echoed is carried onto it, which is what makes the approval
    # attach to the plan they SAW: if the venue has moved materially since,
    # the diff between the two is visible in the response.
    reviewed = plan.to_payload()
    plan.run_id = req.run_id
    try:
        result = venuesync.apply(_store, plan, actor=approver, reason=req.reason)
    except venuesync.VenueSyncError as e:
        raise HTTPException(status_code=422, detail=str(e))

    _riskengine.invalidate()
    _store.invalidate_cache()
    after = _nav.compute()
    return {
        **result,
        "reviewed_plan": reviewed,
        "nav_after": {
            "total_nav_usd": f(after.total_nav_usd),
            "breakdown": {k: f(v) for k, v in after.breakdown.items()},
        },
        "since_inception": _nav.since_inception(after),
        "reminder": "the NAV step is a RECONCILIATION, not a return — read "
                    "since_inception.return_pct_ex_reconciliation for "
                    "performance",
    }


class BackfillApplyRequest(BaseModel):
    actor: str = "reconciliation"
    confirm: bool = False


@router.get("/fund/venue/backfill/plan")
def plan_venue_backfill():
    """DRY RUN: which venue fills are missing from our log, and what adopting
    them would do. Reads both sides, writes nothing."""
    if not _mode_spec.real_broker:
        raise HTTPException(
            status_code=400,
            detail=f"mode {_mode_spec.mode.value!r} runs on a simulated venue — "
                   "there is no broker to back-fill from")
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
    if not _mode_spec.real_broker:
        raise HTTPException(
            status_code=400,
            detail=f"mode {_mode_spec.mode.value!r} runs on a simulated venue")
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
    confirm: str | None = None      # approval-channel guard v1: echo of id[:8]
    instruction: str | None = None  # via-cto: the CEO's quoted instruction


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
    approver = _guard_approval("rebalance_plan", plan_id, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)
    try:
        return _rebalance.approve(plan_id, approver=approver,
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
    from app.fund.riskmonitor import HALT_MANUAL
    return _control.halt(reason=req.reason, actor=req.actor,
                         halt_class=req.halt_class or HALT_MANUAL)


@router.post("/fund/risk/drawdown-reference/rebase")
def rebase_drawdown_reference(req: DrawdownRebaseRequest):
    """Lower the peak the drawdown rule measures from (CEO-accepted PM R1).

    The defect: `assess()` takes the trailing-365d MAX of NAV history as the
    peak, and the fund's $2,036.35 high includes the phantom-fill era — so a
    bad mark caps risk capacity for a YEAR. This moves the reference, once, in
    the log, with a mandatory reason. It moves no threshold.

    On the approval channel, and REFUSED during an integrity halt, exactly like
    the loss rebase. The direction is enforced in RiskControl: a rebase may
    only LOWER the reference, and `effective_peak` floors the live peak at any
    genuine high observed since — so it can shorten a phantom's shadow and can
    never hide a real peak.
    """
    assessment = _monitor.assess()
    dd = assessment.get("drawdown") or {}
    current_peak = dd.get("unrebased_peak_nav", dd.get("peak_nav"))
    token = _control.drawdown_rebase_token(current_peak)
    approver = _guard_approval("drawdown_reference_rebase", token, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)
    nav_now = float(assessment.get("nav_usd") or 0.0)
    if req.nav_usd < nav_now:
        raise HTTPException(
            status_code=409,
            detail=(f"refusing to rebase the drawdown peak to "
                    f"${req.nav_usd:,.2f}: that is below current NAV of "
                    f"${nav_now:,.2f}, so the effective peak would be floored "
                    f"at NAV and the rebase would be recorded having changed "
                    f"nothing. Did you mean a figure at or above current NAV?"))
    try:
        return _control.rebase_drawdown_reference(
            new_peak=req.nav_usd, current_peak=float(current_peak or 0.0),
            reason=req.reason, actor=approver)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/risk/halt/acknowledge")
def acknowledge_halt(req: HaltAcknowledgeRequest):
    """Record that the CEO has SEEN the open halt. Reopens nothing by itself.

    On the approval channel (allowlist, confirm echo, via-cto citation) because
    it is a precondition for an execution path reopening — condition (1) of the
    four the loss-halt auto-resume policy evaluates on the monitor tick. It is
    NOT a resume and NOT a rebase: it moves no number and re-arms no path, and
    a halt whose other three conditions never hold stays shut forever with this
    acknowledgement sitting harmlessly in the log.

    Any class may be acknowledged — seeing an integrity halt is worth
    recording. Only a LOSS halt's acknowledgement feeds the auto-resume policy.
    """
    token = _control.halt_ack_token()
    approver = _guard_approval("halt_acknowledge", token, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)
    try:
        return _control.acknowledge_halt(actor=approver, note=req.note)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/risk/loss-reference/rebase")
def rebase_loss_reference(req: LossRebaseRequest):
    """Acknowledge a loss and move the daily-loss reference to current NAV.

    The reopening procedure for a LOSS-class halt (CEO-blessed 2026-08-20).
    Moves no threshold — the limit stays where the register says it is; this
    moves the point it is measured from, once, in the log, with a reason.

    On the approval channel exactly like an order approval, because it is an
    approval: it re-arms an execution path the fund deliberately closed.
    Refused while an INTEGRITY halt is open — rebasing onto a NAV we do not
    trust would launder a bad mark into the fund's own reference.
    """
    token = _monitor.rebase_token()
    approver = _guard_approval("loss_reference_rebase", token, req.approver,
                               req.confirm, req.instruction, APPROVAL_ALLOWLIST)
    nav_usd = float(_nav.compute(stale_ok=True).total_nav_usd)
    try:
        return _control.rebase_loss_reference(nav_usd=nav_usd, reason=req.reason,
                                              actor=approver)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/fund/risk/resume")
def resume_trading(req: RiskResumeRequest):
    """Resume trading after halt (human only)."""
    return _control.resume(actor=req.actor)


# --- derived metrics (2026-08-22) -------------------------------------------
#
# READ-SIDE ONLY, AND DERIVED. Nothing here is a source of truth: NAV folds
# from the event log, the desk folds from the desk, and these endpoints exist
# so a seat can ask a question in ONE call instead of re-deriving it from 965
# raw events by hand. See app/fund/metrics.py for the guard rails.

_metricsstore_cache = None


def _metricsstore():
    """The rollup table, or None when the fund is not on Postgres.

    None is a real answer and every caller renders it as such: the derived
    table does not exist on the Firestore backend, and a refresh that silently
    did nothing would be worse than one that says it cannot run.
    """
    global _metricsstore_cache
    if _metricsstore_cache is None:
        from app.fund.events import store_backend
        if store_backend() != "postgres":
            return None
        from app.fund.metrics import MetricsStore
        _metricsstore_cache = MetricsStore()
    return _metricsstore_cache


@router.get("/fund/metrics/daily")
def metrics_daily(date: Optional[str] = Query(
        None, description="UTC day as YYYY-MM-DD; defaults to today (UTC)")):
    """One UTC day, folded once — the call that replaces a seat's hand fold.

    Events by type, decisions by actor and status, NAV open/close/strike count,
    fills with notional and venue split, ReconciliationMismatch, the desk
    request lifecycle, and per-seat runs from the UNCAPPED window.

    COMPUTED LIVE ON EVERY CALL. The stored rollup is reported BESIDE the fresh
    computation under ``stored``, with ``agrees`` comparing digests — so a
    stale row is visible and never authoritative. That ordering is the whole
    safety property: a cache that can silently disagree with the log would be
    the write-only verdict column in a new costume.

    ``complete_day`` is False while the day is still running. Sections that
    cannot be computed carry ``state: "UNKNOWN"`` with a reason; they are
    listed in ``unknown_sections`` and they are never zero.
    """
    from app.fund import metrics
    day = date or datetime.now(timezone.utc).date().isoformat()
    try:
        body = metrics.compute_daily(day, _store, deskstore=_deskstore())
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    ms = _metricsstore()
    stored = None
    if ms is not None:
        try:
            row = ms.stored(body["day"])
        except Exception as e:  # noqa: BLE001
            logger.warning("metrics: stored row unreadable: %s", e)
            row = None
            stored = {"present": None, "note": f"the rollup table could not be "
                                               f"read: {e}"}
        if stored is None:
            stored = {
                "present": row is not None,
                "computed_at": (row or {}).get("computed_at"),
                "digest": (row or {}).get("digest"),
                "metrics_version": (row or {}).get("metrics_version"),
                # None, not False: with no stored row there is nothing to agree
                # or disagree with, and False would read as "the cache is
                # wrong" when the truth is "there is no cache".
                "agrees": (None if row is None
                           else row.get("digest") == body["digest"]),
                "note": ("no rollup has been recorded for this day; the figures "
                         "above were computed live from the log"
                         if row is None else
                         "the recorded rollup " +
                         ("MATCHES" if row.get("digest") == body["digest"]
                          else "DISAGREES WITH") +
                         " a fresh fold of the log"),
            }
    else:
        stored = {"present": None,
                  "note": "the rollup table exists only under "
                          "FUND_STORE=postgres; nothing was recorded and "
                          "nothing was compared"}
    return {**body, "stored": stored}


class MetricsRefresh(BaseModel):
    #: UTC day to (re)compute. Absent means today.
    date: Optional[str] = None
    actor: str = "cto"


@router.post("/fund/metrics/refresh")
def metrics_refresh(req: MetricsRefresh):
    """Recompute a day and RECORD it. Idempotent, chair-triggered.

    NO SCHEDULER AND NO SELF-STARTING ANYTHING — the constitution's ignition
    rule applies to derived tables exactly as it applies to seats. A day that
    nobody refreshes simply has no stored row, and ``GET /fund/metrics/daily``
    still answers correctly because it computes live.

    ``changed`` says whether the content actually moved since the last record.
    On a CLOSED day that is a signal worth reading: it means the log gained
    events after the day ended — a backfill or a late correction — and a chair
    should see that rather than have the row silently replaced.

    A computation that raises writes NOTHING; the previous row stands. There is
    no except clause in ``MetricsStore.refresh`` to get that wrong.
    """
    ms = _metricsstore()
    if ms is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    day = req.date or datetime.now(timezone.utc).date().isoformat()
    try:
        return {**ms.refresh(day, _store, deskstore=_deskstore()),
                "actor": req.actor}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/fund/metrics/days")
def metrics_days(limit: int = Query(90, ge=1, le=365)):
    """Which days have a recorded rollup — headers only, never whole bodies."""
    ms = _metricsstore()
    if ms is None:
        raise HTTPException(status_code=503, detail="needs FUND_STORE=postgres")
    rows = ms.days(limit=limit)
    return {"days": rows, "count": len(rows)}


@router.get("/fund/metrics/friction")
def metrics_friction(open_only: bool = Query(
        False, description="drop resolved and declined rows")):
    """Every desk request, folded forward, AGED, oldest first.

    The secretary's friction ledger as one call. Its first hand-built run found
    28 requests approved and undispatched at midnight on 2026-08-21, all
    waiting on the chair, the oldest 14h34m, and only 3 of the 28 answered the
    next day.

    ``approved_undispatched`` is a first-class state, and the payload declares
    it an UPPER BOUND: 14 of 24 ``DeskDispatched`` events carry no
    ``request_id``, so a dispatched request can look undispatched here. See
    ``dispatch_link_coverage``. Reporting the number without that caveat would
    be a confident figure resting on an instrument that cannot see half its own
    input.
    """
    from app.fund import metrics
    got = metrics.friction(_store)
    if open_only:
        got = {**got,
               "requests": [r for r in got["requests"] if not r["terminal"]],
               "filtered": "open_only"}
    return got


def run_risk_monitor_tick(actor: str = "worker") -> dict:
    """Worker tick function to execute the risk monitor."""
    return _monitor.run(actor=actor)


def run_results_prune_tick() -> dict:
    """Worker tick: delete engine output that is neither recent nor in use.

    Every backtest writes a results directory and nothing ever removed one, so 501
    had accumulated to 188 MB on a machine already short of disk and RAM. The
    parsed result is mirrored to Postgres, so a settled job's directory is debug
    material rather than the record.

    ALSO ages out captured candidate analytics, on the same tick and deliberately
    NOT on the same schedule: engine directories are debug material with a
    one-day life, while a candidate's captured evidence is what a deployment
    decision rested on and keeps for a quarter. One tick, two policies, each
    sized from what it holds.

    The candidate leg is best-effort and reported separately rather than folded
    in: it needs Postgres, and a tick that failed silently because the factory
    was unavailable would look exactly like a tick with nothing to do.
    """
    out = _lean().prune_results()
    f = _factory()
    if f is None:
        out["analytics"] = {
            "count": 0,
            "note": "candidate analytics are stored only under FUND_STORE=postgres; "
                    "nothing was examined, which is not the same as nothing being due",
        }
        return out
    try:
        out["analytics"] = f.prune_analytics()
    except Exception as e:  # noqa: BLE001
        logger.warning("candidate analytics prune failed: %s", e)
        out["analytics"] = {"count": 0, "error": f"{type(e).__name__}: {e}"[:200],
                            "note": "the prune could not run — nothing was removed"}
    return out


def run_autopolicy_tick() -> dict:
    """Worker tick: auto-approve what the deterministic envelope covers.

    v4 envelope: exit-rule-triggered SELLs only, fresh, liveness proven, the
    trigger event naming the exact order, the rule predating the position, the
    mark corroborated, the notional capped — and (v4) the quantity held on the
    same side by the rule's own strategy, by the fund's book AND by the BROKER,
    with book and broker agreeing. Everything else waits for the CEO exactly as
    before. See app/fund/autopolicy.py for the amendment this implements, its
    reasoning, and the dated note on what v4 corrects.
    """
    from app.fund import autopolicy, heartbeat
    try:
        pending = _orders.pending() or []
    except Exception as e:  # noqa: BLE001
        logger.info("autopolicy tick: queue unreadable: %s", e)
        return {"approved": [], "skipped": [], "failed": [],
                "note": f"queue unreadable: {e}"}
    if not pending:
        return {"approved": [], "skipped": [], "failed": [],
                "policy_version": autopolicy.AUTOPOLICY_VERSION,
                "note": "queue empty"}
    hb = {j["job"]: j for j in heartbeat.report()["jobs"]}
    # v4: ONE broker round trip per TICK, not per order — the policy's cost must
    # not be a function of the queue length. Taken here, AFTER the empty-queue
    # return above, so an idle queue costs the venue nothing.
    #
    # `readable` rides separately from the dict on purpose: an empty dict is
    # what a flat account and an unreachable broker both return, and reading
    # the second as the first is how the fund would conclude "everything is
    # flat" from a network error.
    venue_readable, venue_positions = autopolicy.venue_snapshot(_connector)
    # v2: each candidate order gets its context gathered from the event log
    # (trigger linkage, rule pre-commitment, mark corroboration vs the last
    # strike, notional vs struck NAV). A failing gatherer yields an absent
    # context, which evaluate() fails closed on.
    return autopolicy.run(
        _pipeline, pending, halted=_control.is_halted(), heartbeats=hb,
        context_fn=lambda row: autopolicy.context_for(
            _store, row, _connector.price,
            venue_positions=venue_positions, venue_readable=venue_readable))


def run_proposal_expiry_tick() -> dict:
    """Worker tick: decline proposals past the staleness limit, reason on record.

    The approve path already refuses stale proposals; this keeps the QUEUE honest
    between refusals, so the operator never faces a button whose only outcome is
    an error.

    CORRECTED 2026-08-21 (riskofficer R19). This docstring used to end "Exit-
    sourced proposals re-raise themselves from fresh marks on the exit tick if
    their condition still holds." THAT IS FALSE, and it is false in the
    dangerous direction: ExitRules.enforce() stamps `triggered_at` on the rule
    (exitrule.py:183-194) and SKIPS any rule carrying it (exitrule.py:275), so
    a fired exit fires exactly once. Only a fresh EXIT_RULE_SET clears the
    stamp. Seq 195 is the live proof — its own note records a human
    re-committing the rule by hand. So an expired exit proposal is GONE until
    someone notices, which is why autopolicy.run() now logs every decline.
    """
    try:
        pending = _orders.pending() or []
    except Exception as e:  # noqa: BLE001
        logger.info("proposal expiry tick: queue unreadable: %s", e)
        return {"expired": [], "count": 0, "note": f"queue unreadable: {e}"}
    return _pipeline.expire_stale_proposals(pending)


def run_factory_reconcile_tick() -> dict:
    """Worker tick: orphan candidates whose runner died.

    Cheap (one indexed UPDATE) and self-throttling by the age ceiling, so it can
    ride the ordinary scheduler tick rather than needing its own schedule.
    """
    f = _factory()
    if f is None:
        return {"orphaned": [], "count": 0, "note": "factory unavailable"}
    return f.reconcile_orphans()


def run_exit_check_tick(actor: str = "worker") -> dict:
    """Worker tick: evaluate pre-committed exits and raise closing proposals.

    The missing link. Every piece of the exit mechanism existed - the commitment
    event, the evaluation, the three event types - and nothing joined them, so
    EXIT_RULE_TRIGGERED was emitted by no code anywhere and a fired rule produced
    nothing at all. Called from the scheduler so a rule fires whether or not
    anybody is looking, which is the entire point of having committed to it early.

    Raises SELL proposals through the ordinary pipeline. The pre-trade gate still
    runs; a human still clicks. Nothing here closes a position.
    """
    from app.fund.exitrule import ExitRules
    try:
        positions = (_monitor.assess() or {}).get("positions") or []
    except Exception as e:  # noqa: BLE001
        # Marks unavailable is NOT "no exits fired". Reported as such, because a
        # tick that silently sees zero positions would look identical to a calm
        # book and would let every committed stop go unevaluated in silence.
        logger.warning("exit check tick: marks unavailable, exits UNEVALUATED: %s", e)
        return {"raised": [], "skipped": [], "failed": [],
                "note": f"marks unavailable, so no exit rule was checked: {e}"}
    return ExitRules(_store).enforce(positions, pipeline=_pipeline, actor=actor)

