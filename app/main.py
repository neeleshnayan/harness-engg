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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.core.firebase import initialize_firebase

_log = logging.getLogger("clarkharness")

_WEB_DIR = pathlib.Path(__file__).resolve().parents[1] / "web"

load_dotenv()

# Firebase must be ready before importing routers that build Firestore clients.
# Dev escape hatch: USE_FAKE_FIRESTORE=1 runs with an in-memory Firestore (no
# creds, ephemeral) so you can test locally without a service account.
if os.getenv("USE_FAKE_FIRESTORE", "").lower() in ("1", "true", "yes"):
    _log.warning("USE_FAKE_FIRESTORE set — using in-memory Firestore (DEV ONLY, data is ephemeral).")
    from app.core.dev_firestore import install_fake

    install_fake()
else:
    initialize_firebase()

from app.api.v1 import fund as fund_router  # noqa: E402


async def _scheduler():
    """24×7 deterministic worker: settle fills often; strike NAV + reconcile on the slow cycle.

    Every tick is guarded so a transient failure never takes the loop (or the app) down.
    Intervals and on/off are env-configurable.
    """
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
