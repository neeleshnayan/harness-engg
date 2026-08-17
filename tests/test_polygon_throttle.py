"""The vendor budget belongs to the API key, not to a process.

The property under test: two processes each obeying four-a-minute must not
together ask for eight. This is not hypothetical tuning — an in-process throttle
let a second script burst into a window the vendor was still counting, and the
429s that came back were written into a research sample as "this company has no
history". A rate limit must never be able to enter a dataset as absence.
"""

import time

import pytest

from app.fund.polygon import RateLimited, PolygonError, _Throttle


def test_rate_limited_is_distinguishable_from_a_missing_symbol():
    """A caller building a dataset has to tell "the vendor was busy" from "this
    name has no history". One exception type for both forces it to guess, and a
    guess here becomes a fabricated fact about a company."""
    assert issubclass(RateLimited, PolygonError)
    # ...but catching the generic error must not silently swallow a rate limit
    # as though it were missing data.
    assert RateLimited is not PolygonError


def test_the_window_is_shared_across_throttle_instances(monkeypatch):
    """Two _Throttle objects stand in for two processes: separate memory, one
    database. The second must be made to wait by the first's calls."""
    pytest.importorskip("psycopg")
    try:
        a = _Throttle(calls=2, window_s=60.0)
        if not a._ensure_pg():
            pytest.skip("no Postgres available for the shared-window test")
    except Exception:
        pytest.skip("no Postgres available for the shared-window test")

    import psycopg
    from app.fund.pgstore import dsn
    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE fund_rate_limit SET calls_at = '{}' "
                        "WHERE bucket = 'polygon'")
        conn.commit()

    b = _Throttle(calls=2, window_s=60.0)
    assert b._ensure_pg()

    # `a` spends the whole budget of two.
    assert a.wait() == 0.0
    assert a.wait() == 0.0
    # `b` has its own empty in-memory list, so only a shared window can stop it.
    waited = b._claim_pg()
    assert waited is not None and waited > 1, (
        "a second process was handed a slot the budget had already spent")

    with psycopg.connect(dsn()) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE fund_rate_limit SET calls_at = '{}' "
                        "WHERE bucket = 'polygon'")
        conn.commit()


def test_an_unavailable_database_still_throttles():
    """A missing database must degrade to in-process throttling, never to an
    unthrottled client — the failure mode there is a rate-limit storm."""
    t = _Throttle(calls=1, window_s=0.3)
    t._pg_broken = True          # as if Postgres were unreachable
    assert t.wait() == 0.0
    t0 = time.monotonic()
    t.wait()
    assert time.monotonic() - t0 >= 0.2, "second call was not made to wait"
