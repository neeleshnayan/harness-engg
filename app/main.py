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
from app.fund.demo_seed import seed_if_empty  # noqa: E402
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


async def _scheduler():
    """Deterministic worker: settle fills often; strike NAV + reconcile on the session."""
    settle_every = int(os.getenv("SETTLE_INTERVAL_SECONDS", "30"))
    strike_every = int(os.getenv("STRIKE_INTERVAL_SECONDS", "1800"))
    since_strike = 0
    window = StrikeWindow()
    while True:
        await asyncio.sleep(settle_every)
        since_strike += settle_every
        # Settlement stays unconditional. It is read-mostly, idempotent, and an
        # order submitted near the bell can fill after it — refusing to poll
        # while closed would leave that fill unrecorded until the next open.
        try:
            fund_router.run_settlement()
        except Exception as e:  # noqa: BLE001
            _log.warning("settlement tick failed: %s", e)
        # Intraday NAV telemetry. Self-throttling and in-memory, so a fast
        # settle interval cannot flood it and it never touches the event log.
        try:
            fund_router.sample_intraday_nav()
        except Exception as e:  # noqa: BLE001
            _log.debug("intraday sample skipped: %s", e)
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
                continue
            _log.info("strike/reconcile: %s (%s)", decision.reason, session.phase)
            for fn in (fund_router.run_strike, fund_router.run_reconcile):
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    _log.warning("%s failed: %s", fn.__name__, e)


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
