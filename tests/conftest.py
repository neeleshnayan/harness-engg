"""Pytest wiring: run the spine against an in-memory Firestore fake.

The fake is installed into sys.modules *before* any app module imports
``firebase_admin``. Each test gets a clean store via the ``wire`` fixture.
"""

import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _fake_firestore  # noqa: E402

_DB = _fake_firestore.install()  # injects fake firebase_admin + puts ROOT on sys.path

import pytest  # noqa: E402

from app.fund.connectors.paper import PaperConnector  # noqa: E402
from app.fund.events import EventStore  # noqa: E402
from app.fund.ledger import LedgerService  # noqa: E402
from app.fund.pipeline import CommandPipeline  # noqa: E402
from app.fund.projections.holdings import HoldingsProjection  # noqa: E402
from app.fund.projections.nav import NavService  # noqa: E402
from app.fund.projections.orders import OrdersProjection  # noqa: E402
from app.fund.projections.positions import PositionsProjection  # noqa: E402
from app.fund.projections.strategy import StrategyAttribution  # noqa: E402
from app.fund.memo import MemoService  # noqa: E402
from app.fund.postmortem import PostmortemService  # noqa: E402
from app.fund.riskanalytics import RiskAnalytics  # noqa: E402
from app.fund.risk import RiskGate, RiskLimits  # noqa: E402
from app.fund.strategies import StrategyService  # noqa: E402


@pytest.fixture
def wire():
    """Fresh, isolated spine wiring for one test."""
    _DB._store.clear()
    store = EventStore()
    conn = PaperConnector(prices={"AAPL": 200.0})
    proj = PositionsProjection(store)
    nav = NavService(pricer=conn.price, store=store, projection=proj)
    holdings = HoldingsProjection(store)
    permissive = RiskGate(
        RiskLimits(max_position_pct=10.0, max_order_notional_pct=10.0, min_cash_buffer=0.0)
    )
    return SimpleNamespace(
        store=store,
        conn=conn,
        proj=proj,
        nav=nav,
        holdings=holdings,
        pipe=CommandPipeline(connector=conn, nav_service=nav, store=store),  # default risk
        pipe_open=CommandPipeline(
            connector=conn, nav_service=nav, store=store, risk_gate=permissive
        ),
        ledger=LedgerService(nav_service=nav, store=store),
        strategies=StrategyService(store=store),
        attribution=StrategyAttribution(store),
        orders=OrdersProjection(store),
        memos=MemoService(store=store),
        risk=RiskAnalytics(nav_service=nav),
        postmortem=PostmortemService(store=store, pricer=conn.price),
    )


@pytest.fixture(autouse=True)
def _clear_event_stream_cache():
    """The event store memoises the log per database.

    Tests build a fresh fake db per case, but object ids can be reused once one
    is collected, so a stale entry could otherwise leak from one test into the
    next as phantom events. Cleared around every test rather than trusted to
    isolate itself.
    """
    from app.fund.events import _STREAM_CACHE
    _STREAM_CACHE.clear()
    yield
    _STREAM_CACHE.clear()
