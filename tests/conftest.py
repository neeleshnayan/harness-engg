"""Pytest wiring: run the spine against an in-memory Firestore fake.

The fake is installed into sys.modules *before* any app module imports
``firebase_admin``. Each test gets a clean store via the ``wire`` fixture.
"""

import os
import pathlib
import sys
from types import SimpleNamespace

# DECLARED, not defaulted — ``events.store_backend()`` has no default as of
# 2026-08-22 and raises when nothing says which store this process uses. The
# suite runs against the in-memory Firestore fake installed two lines below, so
# it says so here. This line is the point of that change working as intended:
# every process now states its ledger, including this one.
os.environ.setdefault("FUND_STORE", "firestore")
# The suite is a test-mode process and says so, because importing
# ``app.api.v1.fund`` now RESOLVES the mode and refuses when nothing declared
# one. That refusal is the feature.
#
# The mode file must not be consulted: a developer's own `.fund_mode`, left
# pointing at alpaca-paper, would otherwise make `resolve()` raise a conflict
# and take the whole suite down for a reason that has nothing to do with the
# code under test. Pointed at a path inside the pytest tree that never exists.
os.environ.setdefault("FUND_MODE", "test")
os.environ.setdefault(
    "FUND_MODE_FILE",
    str(pathlib.Path(__file__).resolve().parent / ".fund_mode.absent"))
# NOTE the autouse fixture below DEACTIVATES the process mode around every
# test. Importing the router activates it once; a unit test that hand-builds a
# pipeline has genuinely not declared a mode, and the honest stamp for that is
# no stamp at all. Tests that care activate one explicitly.

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
    # Deterministic test prices live HERE, explicitly — the module-level equity
    # seeds were removed 2026-08-20 (riskofficer F1: a stale seed is a
    # fabricated mark; SPY served at 560 vs a true 769 during the incident).
    conn = PaperConnector(prices={"AAPL": 200.0, "MSFT": 430.0})
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


@pytest.fixture(autouse=True)
def _benchmark_population_register_absent(monkeypatch):
    """The benchmark's as-of register is OFF by default in the suite.

    ``_add_benchmark`` consults ``fund_universe_asof`` to strip names that were
    not listed on the window's first date. That read is SELECT-only and points
    at whatever database ``pgstore.dsn()`` resolves to — which in a unit-test
    process is the developer's live one. Two problems, and the second is the
    real one: the read is I/O in a pure unit test, and a benchmark test's
    outcome would then depend on which snapshots someone happened to capture.
    A future capture at a date a fixture uses would fail the seven
    ``_add_benchmark`` call sites in tests/test_benchmark_truncation.py for a
    reason that has nothing to do with truncation.

    So the default is "no register", which is the honest state of this fund on
    every date but one, and tests that care pass a ``population=`` report in.
    ``tests/test_benchmark_population.py`` drives the real reader explicitly.
    """
    from app.fund import asof, leanrunner
    monkeypatch.setattr(
        leanrunner, "_population_report",
        lambda wanted, as_of: asof.population_report(
            wanted, as_of, listed=None, priced_delisted=None,
            read_error="the as-of register is not consulted in the test suite"))
    yield


@pytest.fixture(autouse=True)
def _clear_active_mode():
    """The active fund mode is process state; a test must not leak it.

    ``mode.activate()`` is deliberately global — one process folds one store —
    which makes it exactly the kind of thing that leaks between tests and turns
    a later assertion about an absent stamp into a mystery.
    """
    from app.fund import mode as _mode
    _mode.deactivate()
    yield
    _mode.deactivate()
