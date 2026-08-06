"""ClarkHarness — the Krypton Fund harness service.

Standalone FastAPI app hosting the fund spine (event store, connectors,
projections, risk, command pipeline). Deliberately independent of the
KryptonPay payments stack: v0 has no wallets, no on-chain rail, and no
money-transmission surface — deposits are recorded off-platform.

See docs/architecture.md for the full design.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.firebase import initialize_firebase

load_dotenv()

# Firebase must init before importing routers that build Firestore clients.
initialize_firebase()

from app.api.v1 import fund as fund_router  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup / shutdown hooks (scheduled NAV strike + reconciliation land here).
    yield


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
