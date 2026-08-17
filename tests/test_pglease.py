"""The scheduler lease on Postgres — two spines must never both hold it.

The lease decides which process strikes NAV and settles orders. If two hold it
at once the fund double-writes; if none can hold it the fund silently stops
marking its own book. Both failures are quiet, which is why they are tested.
"""

import os
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")


def _lease(owner: str, ttl: int = 30, name: str | None = None):
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    try:
        psycopg.connect(dsn(), connect_timeout=3).close()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    from app.fund.pglease import PostgresSchedulerLease
    return PostgresSchedulerLease(ttl_seconds=ttl, owner=owner,
                                  doc=name or f"test-{uuid.uuid4().hex[:8]}")


def test_the_second_process_is_refused():
    name = f"test-{uuid.uuid4().hex[:8]}"
    a, b = _lease("A", name=name), _lease("B", name=name)
    assert a.acquire().held is True
    state = b.acquire()
    assert state.held is False
    assert "held by A" in state.reason
    a.release()


def test_the_holder_renews_without_losing_it():
    name = f"test-{uuid.uuid4().hex[:8]}"
    a = _lease("A", name=name)
    a.acquire()
    again = a.acquire()
    assert again.held is True
    assert again.reason == "renewed"
    a.release()


def test_an_expired_lease_is_taken_over():
    """A process that dies holding the lease must not lock the fund out."""
    name = f"test-{uuid.uuid4().hex[:8]}"
    dead = _lease("dead", ttl=1, name=name)
    dead.acquire()
    time.sleep(1.2)
    taker = _lease("taker", name=name)
    state = taker.acquire()
    assert state.held is True
    assert "expired" in state.reason
    taker.release()


def test_release_only_clears_our_own_ownership():
    """A loser releasing on its way out must not evict the winner."""
    name = f"test-{uuid.uuid4().hex[:8]}"
    a, b = _lease("A", name=name), _lease("B", name=name)
    a.acquire()
    b.acquire()          # refused
    b.release()          # must be a no-op against A's ownership
    assert a.state().reason == "ours"
    assert b.acquire().held is False
    a.release()


def test_released_lease_is_free_immediately():
    name = f"test-{uuid.uuid4().hex[:8]}"
    a, b = _lease("A", name=name), _lease("B", name=name)
    a.acquire()
    a.release()
    state = b.acquire()
    assert state.held is True
    assert "free" in state.reason
    b.release()


def test_state_does_not_take_the_lease():
    name = f"test-{uuid.uuid4().hex[:8]}"
    a, b = _lease("A", name=name), _lease("B", name=name)
    a.acquire()
    assert b.state().held is False
    assert a.state().held is True
    # b only looked; a still has it
    assert a.acquire().reason == "renewed"
    a.release()


def test_unreachable_postgres_refuses_rather_than_assuming_solitude():
    """The safety property: not knowing whether we are alone means not running."""
    from app.fund.pglease import PostgresSchedulerLease
    pytest.importorskip("psycopg")
    try:
        lease = PostgresSchedulerLease(
            dsn_str="postgresql://nobody:nope@127.0.0.1:59999/nothing",
            owner="A", doc="x")
    except Exception:
        return          # refused at construction, which is also correct
    state = lease.acquire()
    assert state.held is False
    assert "unreadable" in state.reason


def test_dispatch_selects_postgres_when_configured(monkeypatch):
    """Guarded like its siblings: constructing the lease OPENS a connection, so
    without the skip this hangs for the connect timeout and then fails on a
    machine with no Postgres — reporting a dispatch bug that is really a
    missing container."""
    _lease("guard-check")          # skips cleanly when Postgres is unreachable
    monkeypatch.setenv("FUND_STORE", "postgres")
    from app.fund.lease import SchedulerLease
    from app.fund.pglease import PostgresSchedulerLease
    assert isinstance(SchedulerLease(), PostgresSchedulerLease)
