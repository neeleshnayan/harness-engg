"""ClarkHarness — the Krypton Fund harness service.

Standalone FastAPI app hosting the fund spine (event store, connectors,
projections, risk, command pipeline). Deliberately independent of the
KryptonPay payments stack: v0 has no wallets, no on-chain rail, and no
money-transmission surface — deposits are recorded off-platform.

See docs/architecture.md for the full design.
"""

import asyncio
import logging
import os
import pathlib
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.firebase import initialize_firebase

# Without this there is no handler on the root logger and no level set, so
# Python's default of WARNING applies and every _log.info() in the service is
# silently discarded. That is how "no strike — market closed", "scheduler lease
# ACQUIRED" and every settlement warning came to be written, shipped, and never
# once seen. The scheduler's decisions are the main window into what the
# deterministic worker is doing between ticks; dropping them leaves the
# operator inferring behaviour from side effects.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s:     %(name)s | %(message)s",
)

_log = logging.getLogger("clarkharness")

_WEB_DIR = pathlib.Path(__file__).resolve().parents[1] / "web"

load_dotenv()

# Firebase must be ready before importing routers that build Firestore clients.
# Dev escape hatch: USE_FAKE_FIRESTORE=1 runs with an in-memory Firestore (no
# creds, ephemeral) so you can test locally without a service account.
use_fake = os.getenv("USE_FAKE_FIRESTORE", "").lower() in ("1", "true", "yes")

if use_fake:
    _log.warning("MOCK MODE — in-memory ledger, real market prices. NOT the fund.")
    from app.core.dev_firestore import install_fake
    install_fake()
    from app.core import firebase as _fb
    _fb._active.update({"project_id": "in-memory", "env": "mock",
                        "service_account": "(none)", "database_id": "(memory)"})
else:
    try:
        initialize_firebase()
    except Exception as e:
        # Falling back to a local file is a reasonable thing to do while
        # developing and a catastrophic thing to do on the real book: the fund
        # would come up looking healthy, accept orders, and write fills into a
        # JSON file that no reconciliation, backup or audit trail knows about.
        # Every event written during the outage would be invisible to the
        # ledger it is supposed to live in, and the hash chain — whose whole
        # purpose is to make missing events loud — would be perfectly intact,
        # because the events were never in that chain to begin with.
        #
        # So production refuses to start. An outage that stops the fund is a
        # problem you find out about immediately; one that silently relocates
        # the ledger is a problem you find out about at the audit.
        if os.getenv("FUND_ENV", "").lower() == "production":
            _log.error("Firebase init failed (%s) and FUND_ENV=production — "
                       "refusing to start on a local ledger.", e)
            raise RuntimeError(
                f"cannot reach the production ledger ({e}). Refusing to fall "
                f"back to a local file: fills written there would be invisible "
                f"to reconciliation and to the audit trail. Fix connectivity, "
                f"or set USE_FAKE_FIRESTORE=1 deliberately to work offline."
            ) from e
        _log.warning("Firebase init failed (%s) — falling back to local dev Firestore.", e)
        from app.core.dev_firestore import install_fake
        install_fake()

from app.api.v1 import fund as fund_router  # noqa: E402
from app.fund import heartbeat
from app.fund.demo_seed import seed_if_empty  # noqa: E402
from app.fund.lease import SchedulerLease  # noqa: E402
from app.fund.schedule import StrikeWindow  # noqa: E402


def _venue_session():
    """The venue's session, or a simulated stand-in.

    A connector with no clock is a simulated venue, which has no exchange
    session and trades whenever asked — reporting it open keeps mock mode
    behaving the way it always has rather than silently freezing NAV history.
    """
    from app.fund.session import PHASE_REGULAR, MarketSession, STATE_OPEN, unknown

    probe = getattr(fund_router._connector, "session", None)
    if probe is None:
        return MarketSession(state=STATE_OPEN, phase=PHASE_REGULAR,
                             note="simulated venue — always open")
    try:
        return probe()
    except Exception as e:  # noqa: BLE001
        return unknown(str(e))


#: The running scheduler's lease, so shutdown can hand it back rather than
#: leaving the next process to wait out the TTL.
_lease: SchedulerLease | None = None


async def _scheduler():
    """Deterministic worker: settle fills often; strike NAV + reconcile on the session.

    Runs only while holding the scheduler lease. Losing it is not a failure —
    it means another process is doing this work, which is the point — so the
    loser goes quiet and keeps asking rather than exiting, and picks the work
    back up if that process dies.
    """
    settle_every = int(os.getenv("SETTLE_INTERVAL_SECONDS", "30"))
    strike_every = int(os.getenv("STRIKE_INTERVAL_SECONDS", "1800"))
    # The lease must outlive several ticks. One that expires between two ticks
    # of its own holder hands the work back and forth and produces exactly the
    # double-execution it exists to prevent.
    global _lease
    lease = _lease = SchedulerLease(ttl_seconds=max(180, settle_every * 4))
    _log.info("scheduler identity: %s", lease.owner)
    since_strike = 0
    window = StrikeWindow()
    was_held = None
    while True:
        await asyncio.sleep(settle_every)

        state = lease.acquire()
        if state.held != was_held:
            # Log only on change: at a 20s tick, saying this every time would
            # bury everything else in the log.
            _log.info("scheduler lease %s — %s",
                      "ACQUIRED" if state.held else "NOT HELD", state.reason)
            was_held = state.held
        if not state.held:
            continue

        since_strike += settle_every
        # Settlement stays unconditional. It is read-mostly, idempotent, and an
        # order submitted near the bell can fill after it — refusing to poll
        # while closed would leave that fill unrecorded until the next open.
        try:
            fund_router.run_settlement()
            heartbeat.beat("settlement")
        except Exception as e:  # noqa: BLE001
            _log.warning("settlement tick failed: %s", e)
        # Intraday NAV telemetry. Self-throttling and in-memory, so a fast
        # settle interval cannot flood it and it never touches the event log.
        try:
            fund_router.sample_intraday_nav()
        except Exception as e:  # noqa: BLE001
            _log.debug("intraday sample skipped: %s", e)
        # The universe screen, re-measured when it goes stale. Almost always a
        # no-op — it checks the age first and only spends the 50 seconds when
        # actually due, which it has to, because this tick runs every 30s.
        #
        # Under the lease with everything else, so one process measures rather
        # than three racing. And it writes no event: the universe is a
        # measurement of the market, not a fact about the fund.
        try:
            fund_router.run_universe_refresh()
        except Exception as e:  # noqa: BLE001
            _log.warning("universe refresh skipped: %s", e)
        # Durability. Built long before it was scheduled, which meant the fund
        # had a backup in the same sense that an unplugged smoke alarm is a
        # smoke alarm. Self-throttling like the universe tick, and it writes no
        # event: a copy must never be able to disturb what it is copying.
        try:
            fund_router.run_snapshot()
            heartbeat.beat("snapshot")
        except Exception as e:  # noqa: BLE001
            _log.warning("snapshot skipped: %s", e)
        # The kill switches. RiskMonitor.run() is the ONLY code that raises
        # alarms and trips the drawdown and daily-loss halts, and until now it
        # had ZERO callers — reachable from an endpoint nothing hit and from one
        # post-fill path swallowing its own exceptions. So the documented
        # "kill switches that will act without asking" would not have acted: a
        # position could have held for 21 days with the -10% halt never once
        # evaluated. Same class of bug as the snapshot two blocks up, which is
        # why that comment about the unplugged smoke alarm is still there.
        try:
            fund_router.run_risk_monitor_tick(actor="worker")
            heartbeat.beat("risk_monitor")
        except Exception as e:  # noqa: BLE001
            _log.warning("risk monitor tick failed: %s", e)
        # The pre-committed exits. Evaluates every committed rule against current
        # marks and, for one that fires, appends EXIT_RULE_TRIGGERED and raises a
        # closing SELL into the approval queue with the rule quoted. It never
        # closes anything: the pre-trade gate still runs and a human still clicks.
        try:
            fund_router.run_exit_check_tick(actor="worker")
            heartbeat.beat("exit_check")
        except Exception as e:  # noqa: BLE001
            _log.warning("exit check tick failed: %s", e)
        # Candidates whose runner died with a previous process. Their rows say
        # `running` and nothing will ever finish them, so they sat in the
        # scoreboard as neither judged nor failed and quietly made the survival
        # rate wrong. Marked `orphaned` — an absence, never a verdict.
        try:
            fund_router.run_factory_reconcile_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("factory reconcile tick failed: %s", e)
        # Stale proposals. Approval already refuses them; this keeps the queue
        # honest BETWEEN refusals. The one time it mattered, the stale proposal
        # was a take-profit on a position that had since fallen 8% - the guard
        # protected the trade, and this tick protects the operator from a queue
        # of buttons that can only error.
        try:
            fund_router.run_proposal_expiry_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("proposal expiry tick failed: %s", e)
        # Engine output older than the retention window. Cheap: it lists one
        # directory and returns immediately when nothing is due. Unbounded growth
        # on disk is the same class of problem as the unbounded `running` rows
        # above — nothing was wrong with any single write, and nothing removed them.
        try:
            fund_router.run_results_prune_tick()
        except Exception as e:  # noqa: BLE001
            _log.warning("results prune tick failed: %s", e)
        if since_strike >= strike_every:
            since_strike = 0
            # Both of these WRITE to the permanent log — a NAV_STRUCK snapshot
            # and any RECONCILIATION_MISMATCH — and both read prices to do it.
            # Off-session those prices are the previous close, so an unguarded
            # tick writes an invented mark and reports a divergence that only
            # exists because the book was valued twice at the same stale price.
            session = _venue_session()
            decision = window.evaluate(session.is_open)
            if not decision.strike:
                # Named rather than silent: an operator looking at a NAV series
                # that stopped advancing needs to see that it was a decision.
                _log.info("no strike — %s (%s)", decision.reason, session.phase)
                # Beat anyway, with the reason. A deliberate no-strike is the job
                # WORKING; leaving it silent would make "market closed" read
                # identical to "the strike loop died", which is the exact
                # ambiguity this heartbeat exists to remove.
                heartbeat.beat("nav_strike", note=f"no strike — {decision.reason}")
                continue
            _log.info("strike/reconcile: %s (%s)", decision.reason, session.phase)
            for fn in (fund_router.run_strike, fund_router.run_reconcile):
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    _log.warning("%s failed: %s", fn.__name__, e)
            heartbeat.beat("nav_strike", note=decision.reason)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-seed demo state if empty on server start.
    # DISABLE_DEMO_SEED=1 leaves the book empty so it can be built deliberately
    # — mock mode is more useful mirroring the real fund than showing invented
    # strategies with fabricated backtest numbers.
    if os.getenv("DISABLE_DEMO_SEED", "").lower() in ("1", "true", "yes"):
        _log.warning("DISABLE_DEMO_SEED set — starting with an empty book.")
    else:
        try:
            seed_if_empty(fund_router._store, fund_router._nav._db)
        except Exception as e:
            _log.warning("Auto-seed error (%s) — proceeding with existing state.", e)

    task = None
    if os.getenv("ENABLE_SCHEDULER", "true").lower() != "false":
        task = asyncio.create_task(_scheduler())

    # Live fill events. OFF by default: the settlement poller is what the fund
    # has always run on, and this only removes the delay — it is not load-bearing
    # until it has proved itself against a real session. Turning it on adds a
    # second, faster observer; every path it takes is idempotent, so the poller
    # keeps running underneath as the backstop.
    stream_task = None
    if os.getenv("ENABLE_TRADE_STREAM", "false").lower() in ("1", "true", "yes"):
        stream_task = fund_router.start_trade_stream()

    yield

    for t in (stream_task, task):
        if not t:
            continue
        t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
    fund_router.stop_trade_stream()

    # Hand the lease back rather than leaving the next process to wait out the
    # TTL. On a redeploy that is the difference between the new container
    # working immediately and the fund having no scheduler for three minutes.
    if _lease is not None:
        try:
            _lease.release()
            _log.info("scheduler lease released")
        except Exception as e:  # noqa: BLE001
            _log.warning("could not release the scheduler lease (%s) — "
                         "it will expire on its own", e)


app = FastAPI(
    title="ClarkHarness — Krypton Fund",
    description="Agentic operator + LP interface for the Krypton Fund: "
    "event-sourced command spine, unit ledger, NAV, risk, and audit.",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "fund",
            "description": "Fund spine: propose/approve orders, NAV, positions, and the audit event log.",
        }
    ],
)

# localhost and 127.0.0.1 are the same machine and a different ORIGIN, and the
# browser does not care that they resolve identically. Allowing only one means
# the cockpit works or silently fails depending on which the operator typed —
# every panel reporting "spine unreachable" while curl against the same port
# answers instantly. Both are listed so that choice stops mattering.
_DEFAULT_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://.*\.kryptonfund\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def _database_error_handler(request: Request, exc: Exception):
    """Say what actually went wrong.

    A bare 500 sent the UI to "is ClarkHarness running?" — which sends the
    operator to check a service that is running and a config that is correct,
    while the real cause (the datastore refusing reads) goes unnamed. These are
    infrastructure faults, not bugs in the request, so they answer 503 with a
    cause the interface can show verbatim.
    """
    from fastapi.responses import JSONResponse

    name = type(exc).__name__
    if name in ("ResourceExhausted", "PermissionDenied", "ServiceUnavailable",
                "DeadlineExceeded", "Unauthenticated"):
        cause = {
            "ResourceExhausted": "The fund database is over its read/write quota. "
                                 "Free-tier quota resets daily; upgrading the plan lifts it.",
            "PermissionDenied": "The fund database refused access — check the service "
                                "account's permissions and that Firestore is enabled.",
            "Unauthenticated": "The fund database rejected our credentials.",
            "ServiceUnavailable": "The fund database is unreachable.",
            "DeadlineExceeded": "The fund database did not respond in time.",
        }[name]
        _log.error("datastore fault (%s): %s", name, exc)
        return JSONResponse(
            status_code=503,
            content={"detail": cause, "cause": name, "retryable": True},
        )
    _log.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": f"{name}: {exc}"})


app.include_router(fund_router.router, prefix="/api/v1", tags=["fund"])


@app.get("/health")
def health():
    return {"status": "healthy", "service": "clarkharness", "version": "0.1.0"}


@app.get("/lp", include_in_schema=False)
def lp_view():
    """Serve the LP-facing managed-fund view (reads /api/v1/fund/* client-side)."""
    return FileResponse(_WEB_DIR / "lp.html")


@app.get("/ops", include_in_schema=False)
def ops_view():
    """Serve the operator cockpit (reads /api/v1/fund/* client-side)."""
    return FileResponse(_WEB_DIR / "ops.html")


@app.get("/strategies", include_in_schema=False)
def strategies_view():
    """Serve the strategies workbench (reads /api/v1/fund/strategies/* client-side)."""
    return FileResponse(_WEB_DIR / "strategies.html")
