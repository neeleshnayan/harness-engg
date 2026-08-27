"""The trail from a filing sentence to a verdict.

Without it, every judgement about the map's shape is taste: we cannot say
whether a 64% liquidity cluster is the market having one story or the extractor
preferring one kind of sentence. These tests are mostly about keeping the two
kinds of silence apart — nobody looked, versus somebody looked and passed.
"""

import os
import uuid

import pytest
from _testdb import scratch_database

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = scratch_database("krypton_fund_test")
SOURCE = "As of June 30, 2026, we had $81.0 million in cash and cash equivalents."


def _test_dsn():
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


@pytest.fixture
def kit():
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')

    from app.fund.observations import Observations
    from app.fund.provenance import Provenance
    obs, prov = Observations(_test_dsn()), Provenance(_test_dsn())
    with psycopg.connect(_test_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_observations")
            cur.execute("TRUNCATE fund_observation_reviews")
            cur.execute("TRUNCATE fund_candidate_sources")
            cur.execute("CREATE TABLE IF NOT EXISTS fund_candidates ("
                        "candidate_id TEXT PRIMARY KEY, algorithm TEXT, "
                        "grid JSONB, holdout JSONB, state TEXT, passed BOOLEAN, "
                        "failures JSONB, winner JSONB, verdict JSONB, error TEXT, "
                        "started_at TIMESTAMPTZ DEFAULT now(), finished_at TIMESTAMPTZ)")
            cur.execute("TRUNCATE fund_candidates")
        c.commit()
    return obs, prov


def _seed(obs, category="liquidity", n=1):
    import json as _j
    ids = []
    for i in range(n):
        doc = {"ticker": "TEST", "form": "10-Q", "filed": "2026-06-30",
               "accession": f"acc-{uuid.uuid4().hex[:8]}", "url": "https://x",
               "text": SOURCE, "truncated": False}
        obs.extract(doc, model_fn=lambda s, u, c=category: _j.dumps({"observations": [
            {"category": c, "observation": f"obs {i}",
             "quote": "we had $81.0 million in cash and cash equivalents"}]}))
    with __import__("psycopg").connect(_test_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("SELECT observation_id FROM fund_observations "
                        "WHERE category = %s", (category,))
            ids = [r[0] for r in cur.fetchall()]
    return ids


def test_unreviewed_is_not_the_same_as_dismissed(kit):
    """The distinction the whole module exists for. Both are absences in
    behaviour; only one is a decision."""
    obs, prov = kit
    ids = _seed(obs, n=2)
    prov.review(ids[0], "dismissed", note="routine refinancing")
    left = [u["observation_id"] for u in prov.unreviewed()]
    assert ids[0] not in left
    assert ids[1] in left


def test_a_category_nobody_has_looked_at_says_so(kit):
    """'No evidence either way' must not read as 'evidence of nothing'."""
    obs, prov = kit
    _seed(obs, n=2)
    row = prov.yield_by_category()["by_category"][0]
    assert row["reviewed"] == 0
    assert "different from evidence of nothing" in row["verdict"]


def test_a_category_looked_at_and_never_acted_on_is_called_out(kit):
    """The finding that would justify changing the extractor."""
    obs, prov = kit
    for i in _seed(obs, n=3):
        prov.review(i, "dismissed")
    row = prov.yield_by_category()["by_category"][0]
    assert row["acted"] == 0 and row["reviewed"] == 3
    assert "nobody can use them" in row["verdict"]


def test_linking_a_candidate_marks_its_sources_acted(kit):
    """Saying 'this prompted a hypothesis' should not require separately
    saying 'and I read it'."""
    obs, prov = kit
    ids = _seed(obs, n=2)
    prov.link("cand-1", ids)
    row = prov.yield_by_category()["by_category"][0]
    assert row["acted"] == 2 and row["candidates"] == 1
    assert prov.unreviewed() == []


def test_a_passing_candidate_credits_the_category_that_prompted_it(kit):
    """The question that settles the liquidity argument."""
    import psycopg
    obs, prov = kit
    ids = _seed(obs, category="margin", n=1)
    prov.link("cand-9", ids)
    with psycopg.connect(_test_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("INSERT INTO fund_candidates (candidate_id, algorithm, "
                        "grid, state, passed) VALUES ('cand-9','a','{}','done',true)")
        c.commit()
    row = next(r for r in prov.yield_by_category()["by_category"]
               if r["category"] == "margin")
    assert row["passed_gate"] == 1
    assert "cleared the bar" in row["verdict"]


def test_the_trail_runs_backwards_from_a_candidate(kit):
    obs, prov = kit
    prov.link("cand-2", _seed(obs, n=1))
    trail = prov.trail("cand-2")
    assert len(trail) == 1
    assert trail[0]["ticker"] == "TEST"
    assert "81.0 million" in trail[0]["quote"]


def test_re_reviewing_supersedes_rather_than_accumulates(kit):
    """'What does the operator think of this' must have one answer."""
    obs, prov = kit
    oid = _seed(obs, n=1)[0]
    prov.review(oid, "dismissed")
    prov.review(oid, "interesting", note="changed my mind")
    row = prov.yield_by_category()["by_category"][0]
    assert row["reviewed"] == 1


def test_an_unknown_outcome_is_refused(kit):
    obs, prov = kit
    with pytest.raises(ValueError):
        prov.review(_seed(obs, n=1)[0], "maybe-ish")


def test_with_nothing_reviewed_the_report_says_the_map_is_taste(kit):
    obs, prov = kit
    _seed(obs, n=3)
    assert "matter of taste" in prov.yield_by_category()["note"]
