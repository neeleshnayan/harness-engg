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
    _log.warning("USE_FAKE_FIRESTORE set — using in-memory Firestore.")
    from app.core.dev_firestore import install_fake
    install_fake()
else:
    try:
        initialize_firebase()
    except Exception as e:
        _log.warning("Firebase init failed (%s) — falling back to local dev Firestore.", e)
        from app.core.dev_firestore import install_fake
        install_fake()

from app.api.v1 import fund as fund_router  # noqa: E402
from app.fund.demo_seed import seed_if_empty  # noqa: E402


async def _scheduler():
    """24×7 deterministic worker: settle fills often; strike NAV + reconcile on the slow cycle."""
    settle_every = int(os.getenv("SETTLE_INTERVAL_SECONDS", "30"))
    strike_every = int(os.getenv("STRIKE_INTERVAL_SECONDS", "1800"))
    since_strike = 0
    while True:
        await asyncio.sleep(settle_every)
        since_strike += settle_every
        try:
            fund_router.run_settlement()
        except Exception as e:  # noqa: BLE001
            _log.warning("settlement tick failed: %s", e)
        if since_strike >= strike_every:
            since_strike = 0
            for fn in (fund_router.run_strike, fund_router.run_reconcile):
                try:
                    fn()
                except Exception as e:  # noqa: BLE001
                    _log.warning("%s failed: %s", fn.__name__, e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-seed demo state if empty on server start
    try:
        seed_if_empty(fund_router._store, fund_router._nav._db)
    except Exception as e:
        _log.warning("Auto-seed error (%s) — proceeding with existing state.", e)

    task = None
    if os.getenv("ENABLE_SCHEDULER", "true").lower() != "false":
        task = asyncio.create_task(_scheduler())
    yield
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


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

_origins = [o for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o]
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
