"""The rollup TABLE — and the one rule it must never break.

**A FAILED REFRESH MUST NEVER RENDER AS A QUIET ZERO ROW.** That sentence is
the first thing in `metrics.py`'s docstring and it is the whole reason a
derived table is allowed to exist here at all. A rollup that wrote `0 events,
$0 NAV` because the log was briefly unreadable would put a fabricated day in
front of every reader who trusted the table — and the fabrication would be
indistinguishable from a genuinely quiet day.

The second rule: **a rollup is never authoritative over the log.** The stored
digest exists so a stale row can be DETECTED, not so it can be believed.
"""

import os

import pytest
from _testdb import scratch_database

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = scratch_database("krypton_fund_test")


class FakeStore:
    def __init__(self, events=None):
        self._events = list(events or [])

    def stream(self, since_seq=0, limit=200):
        return [e for e in self._events if e.get("seq", 0) > since_seq][:limit]


def ev(seq, type_, ts, payload=None):
    return {"seq": seq, "type": type_, "ts": ts, "actor": "system",
            "payload": payload or {}}


def _store():
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    test_dsn = f"{head}/{TEST_DB}"
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    from app.fund.metrics import MetricsStore
    ms = MetricsStore(dsn=test_dsn)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_metrics_daily")
        c.commit()
    return ms


DAY = "2026-08-21"
EVENTS = [ev(1, "NavStruck", "2026-08-21T09:00:00+00:00",
             {"total_nav_usd": 2000})]


def test_a_refresh_that_RAISES_writes_no_row_at_all():
    """THE MODULE'S FOUNDING RULE. A day that could not be computed must be
    ABSENT from the table, never present and empty — an empty row reads as a
    measured quiet day and there is no way for a reader to tell."""
    ms = _store()

    class Boom:
        def stream(self, *a, **k):
            raise RuntimeError("log unreadable")

    with pytest.raises(RuntimeError):
        ms.refresh(DAY, Boom())
    assert ms.stored(DAY) is None
    assert ms.days() == []


def test_a_failed_refresh_leaves_a_GOOD_previous_row_standing():
    ms = _store()
    ms.refresh(DAY, FakeStore(EVENTS))
    good = ms.stored(DAY)

    class Boom:
        def stream(self, *a, **k):
            raise RuntimeError("log unreadable")

    with pytest.raises(RuntimeError):
        ms.refresh(DAY, Boom())
    assert ms.stored(DAY)["digest"] == good["digest"]
    assert ms.stored(DAY)["payload"]["nav"]["close_usd"] == 2000.0


def test_refresh_is_IDEMPOTENT_over_an_unchanged_log():
    ms = _store()
    store = FakeStore(EVENTS)
    a = ms.refresh(DAY, store)
    b = ms.refresh(DAY, store)
    assert a["digest"] == b["digest"]
    assert a["first_write"] is True and a["changed"] is False
    assert b["first_write"] is False and b["changed"] is False
    assert [d["day"] for d in ms.days()] == [DAY]


def test_refresh_REPORTS_when_a_closed_day_gains_events_after_the_fact():
    """A backfill or a late correction moves a closed day's content. The chair
    should SEE that rather than have the row silently replaced."""
    ms = _store()
    first = ms.refresh(DAY, FakeStore(EVENTS))
    later = ms.refresh(DAY, FakeStore(EVENTS + [
        ev(2, "OrderFilled", "2026-08-21T10:00:00+00:00",
           {"avg_price": "5", "filled_qty": "2"})]))
    assert later["changed"] is True
    assert later["previous_digest"] == first["digest"]
    assert later["digest"] != first["digest"]


def test_a_day_with_no_recorded_rollup_reads_None_not_an_empty_body():
    ms = _store()
    assert ms.stored("2026-08-19") is None


def test_the_stored_payload_carries_its_own_version_and_completeness():
    ms = _store()
    from app.fund import metrics
    ms.refresh(DAY, FakeStore(EVENTS))
    row = ms.stored(DAY)
    assert row["metrics_version"] == metrics.METRICS_VERSION
    assert row["complete_day"] is True
    assert row["payload"]["day"] == DAY


def test_days_returns_HEADERS_not_whole_bodies():
    """The payload is tens of kilobytes; shipping every one to answer "which
    days do we have" is how a convenience endpoint becomes the slow thing it
    was built to replace."""
    ms = _store()
    ms.refresh(DAY, FakeStore(EVENTS))
    header = ms.days()[0]
    assert "payload" not in header
    assert set(header) == {"day", "metrics_version", "digest", "complete_day",
                           "computed_at"}
