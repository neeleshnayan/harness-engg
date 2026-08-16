"""The hunting ground — names a large fund structurally cannot trade.

The filters here are about US, not about the market, and both tests below
exist because ignoring either produces a screen full of names we cannot hold.
"""

import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = "krypton_fund_test"


def _uni():
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
    from app.fund.universe import Universe
    u = Universe(test_dsn)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_universe")
        c.commit()
    return u


@pytest.fixture
def uni():
    return _uni()


def _seed(uni, rows):
    uni._upsert([(s, "NASDAQ", True, adv, px, 60) for s, adv, px in rows])


def test_the_band_excludes_names_everyone_can_trade(uni):
    """The upper bound is the point. SPY is not rejected for being bad, it is
    rejected for being available to everyone."""
    _seed(uni, [("SPY", 35_000_000_000.0, 500.0),
                ("SMALL", 10_000_000.0, 20.0)])
    hg = uni.hunting_ground(turnover_pct=5.0)
    syms = [n["symbol"] for n in hg["names"]]
    assert "SMALL" in syms
    assert "SPY" not in syms


def test_the_band_excludes_names_too_small_to_bother(uni):
    _seed(uni, [("TINY", 50_000.0, 2.0), ("OK", 10_000_000.0, 20.0)])
    syms = [n["symbol"] for n in uni.hunting_ground(turnover_pct=5.0)["names"]]
    assert "TINY" not in syms and "OK" in syms


def test_capacity_is_computed_at_the_asked_turnover_not_stored(uni):
    """Capacity is a property of a strategy-on-a-name, not of a ticker: the
    same symbol supports ten times the money at a tenth the turnover. Storing
    one number would turn an assumption into a fact."""
    _seed(uni, [("X", 10_000_000.0, 20.0)])
    slow = uni.hunting_ground(turnover_pct=1.0)["names"][0]["capacity_usd"]
    fast = uni.hunting_ground(turnover_pct=10.0)["names"][0]["capacity_usd"]
    assert slow == pytest.approx(fast * 10)


def test_a_lower_participation_assumption_shrinks_the_band(uni):
    _seed(uni, [("X", 10_000_000.0, 20.0)])
    a = uni.hunting_ground(participation=0.01)["names"][0]["capacity_usd"]
    b = uni.hunting_ground(participation=0.005)["names"][0]["capacity_usd"]
    assert b == pytest.approx(a / 2)


def test_refresh_is_idempotent_per_symbol(uni):
    _seed(uni, [("X", 10_000_000.0, 20.0)])
    _seed(uni, [("X", 20_000_000.0, 21.0)])
    assert uni.stats()["symbols"] == 1
    assert uni.stats()["adv_max_usd"] == pytest.approx(20_000_000.0)


def test_zero_turnover_is_refused_rather_than_dividing_by_zero(uni):
    with pytest.raises(ValueError):
        uni.hunting_ground(turnover_pct=0)


def test_stats_on_an_empty_universe_do_not_explode(uni):
    s = uni.stats()
    assert s["symbols"] == 0 and s["adv_median_usd"] is None
