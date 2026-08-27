"""The bar archive — what we knew, not what the vendor says today.

Every property here exists because its absence produces a backtest that looks
fine and is wrong. The subtle one is backfill: a month fetched today is
indistinguishable from a month recorded contemporaneously once it is in the
table, and treating it as known-at-the-time is exactly the lookahead this
archive exists to prevent.
"""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from _testdb import scratch_database

#: Bars archived NOW are only visible to an as-of on or after today. That is
#: the archive being honest rather than convenient: it cannot tell you what you
#: knew last year if it first saw the data tonight. Tests that want everything
#: visible must therefore ask "as of today".
TODAY = datetime.now(timezone.utc).date().isoformat()

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = scratch_database("krypton_fund_test")


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
    from app.fund.barstore import BarStore
    return BarStore(test_dsn), test_dsn


@pytest.fixture
def store():
    s, _ = _store()
    return s


def _sym():
    return f"T{uuid.uuid4().hex[:6].upper()}"


def test_first_observation_is_archived(store):
    sym = _sym()
    out = store.archive(sym, ["2025-01-02", "2025-01-03"], [100.0, 101.0], "yahoo")
    assert out["inserted"] == 2
    got = store.as_of(sym, TODAY)
    assert got["dates"] == ["2025-01-02", "2025-01-03"]
    assert got["closes"] == [100.0, 101.0]


def test_a_restatement_is_recorded_and_the_archive_is_unchanged(store):
    """The archived close is the one the fund ACTED on. Overwriting it would
    erase the only evidence the vendor changed its mind."""
    sym = _sym()
    store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    out = store.archive(sym, ["2025-01-02"], [50.0], "yahoo")   # 2-for-1 split
    assert out["restated"] == 1
    assert out["inserted"] == 0

    assert store.as_of(sym, TODAY)["closes"] == [100.0]   # unchanged

    r = store.restatements(sym)
    assert len(r) == 1
    assert r[0]["old_close"] == 100.0 and r[0]["new_close"] == 50.0
    assert r[0]["drift_pct"] == pytest.approx(-50.0)


def test_rounding_noise_is_not_a_restatement(store):
    sym = _sym()
    store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    out = store.archive(sym, ["2025-01-02"], [100.00001], "yahoo")
    assert out["restated"] == 0
    assert out["unchanged"] == 1


def test_as_of_excludes_bars_from_the_future(store):
    """The bar-date filter, tested on its own.

    The observation is backdated first so that first_seen_at cannot be what
    excludes anything — otherwise this test would pass even if the bar_date
    filter were missing entirely.
    """
    import psycopg
    sym = _sym()
    _, test_dsn = _store()
    store.archive(sym, ["2025-01-02", "2025-06-02", "2025-12-02"],
                  [100.0, 110.0, 120.0], "yahoo")
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("UPDATE fund_bars SET first_seen_at = %s WHERE symbol = %s",
                        (datetime(2025, 1, 1, tzinfo=timezone.utc), sym))
        c.commit()

    got = store.as_of(sym, "2025-06-30")
    assert got["dates"] == ["2025-01-02", "2025-06-02"]
    assert 120.0 not in got["closes"]


def test_as_of_excludes_bars_we_only_learned_later(store, monkeypatch):
    """The subtle one. A month backfilled today is not something a decision
    made last year could have used, however old the bars themselves are."""
    import psycopg
    sym = _sym()
    _, test_dsn = _store()
    store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    # Force this row's first_seen_at into the future relative to the as-of.
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute(
                "UPDATE fund_bars SET first_seen_at = %s WHERE symbol = %s",
                (datetime(2026, 1, 1, tzinfo=timezone.utc), sym))
        c.commit()

    # Bar date is in range, but we did not know it on the as-of date.
    assert store.as_of(sym, "2025-06-30")["dates"] == []
    # Known by 2026 though.
    assert store.as_of(sym, "2026-06-30")["dates"] == ["2025-01-02"]


def test_an_observation_made_during_the_as_of_day_counts(store):
    """Archived at 16:00 on the as-of date WAS available that day. Comparing
    against midnight would throw away the whole day."""
    sym = _sym()
    store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    today = datetime.now(timezone.utc).date().isoformat()
    assert store.as_of(sym, today)["dates"] == ["2025-01-02"]


def test_as_of_can_be_bounded_below(store):
    sym = _sym()
    store.archive(sym, ["2025-01-02", "2025-06-02"], [100.0, 110.0], "yahoo")
    got = store.as_of(sym, TODAY, start="2025-03-01")
    assert got["dates"] == ["2025-06-02"]


def test_coverage_reports_when_the_archive_started(store):
    sym = _sym()
    store.archive(sym, ["2025-01-02", "2025-01-03"], [100.0, 101.0], "yahoo")
    cov = store.coverage(sym)
    assert cov["bars"] == 2
    assert cov["first_bar"] == "2025-01-02"
    assert cov["last_bar"] == "2025-01-03"
    assert cov["archived_from"] is not None
    # The honesty note: bulk-archived bars are today's snapshot, not records.
    assert "snapshot" in cov["caveat"]


def test_an_empty_symbol_reads_as_empty_not_as_an_error(store):
    got = store.as_of(_sym(), TODAY)
    assert got["dates"] == [] and got["closes"] == []
    assert got["point_in_time"] is True


def test_archive_is_idempotent(store):
    sym = _sym()
    store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    out = store.archive(sym, ["2025-01-02"], [100.0], "yahoo")
    assert out["inserted"] == 0 and out["unchanged"] == 1 and out["restated"] == 0
