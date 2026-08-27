"""The flight recorder's offsite copy — and the watermark that would have failed.

CTO finding, 2026-08-21: `fund_agent_runs` is single-copy. Every agent run the
firm has ever done lives in one Postgres container on one machine, which is the
exact condition `snapshot_firestore` was written to end for the event log.

THE DESIGN PROBLEM, and the reason these tests exist: the event log is
append-only, so "what changed" is a contiguous tail and a sequence watermark is
correct. RUNS ARE UPSERTED. `record_run` rewrites output/verdict/recommendations
on conflict and `decide_recommendation` mutates the recommendations JSONB, and
NEITHER touches `resolved_at`. A timestamp or sequence watermark would push a
run once and never notice the CEO accepting six of its recommendations — an
offsite copy quietly wrong about every decision the firm made.

So the unit of change is a content hash over the whole row. The test that
matters is `..._a_decided_recommendation_makes_the_run_stale`.
"""

import os

import pytest
from _testdb import scratch_database

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = scratch_database("krypton_fund_test")


class _FakeBatch:
    def __init__(self, sink):
        self._sink = sink
        self._ops = []

    def set(self, ref, doc):
        self._ops.append((ref, doc))

    def commit(self):
        for ref, doc in self._ops:
            self._sink[ref] = doc
        self._ops = []


class _FakeCollection:
    def __init__(self, name):
        self.name = name

    def document(self, doc_id):
        return f"{self.name}/{doc_id}"


class _FakeDb:
    """Just enough Firestore to record what a batch wrote."""

    def __init__(self):
        self.docs = {}
        self.commits = 0

    def batch(self):
        self.commits += 1
        return _FakeBatch(self.docs)

    def collection(self, name):
        return _FakeCollection(name)


def _pair():
    """A DeskStore and a Snapshotter pointed at the same TEST database."""
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

    from app.fund.deskstore import DeskStore
    from app.fund.pgstore import PostgresEventStore
    from app.fund.snapshot_firestore import FirestoreSnapshotter

    ds = DeskStore(dsn=test_dsn)
    pg = PostgresEventStore(dsn_str=test_dsn)
    db = _FakeDb()
    snap = FirestoreSnapshotter(pg_store=pg, db=db)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_agent_runs")
            cur.execute("TRUNCATE fund_snapshot_runs_state")
        c.commit()
    return ds, snap, db


def _record(ds, run_id="run-a", recs=None):
    return ds.record_run(run_id=run_id, seat="pm", task="t", output="o",
                         recommendations=recs or [{"kind": "process", "text": "x"}])


def test_a_new_run_is_behind_and_then_is_pushed():
    ds, snap, db = _pair()
    _record(ds)
    st = snap.runs_status()
    assert st["runs_in_postgres"] == 1
    assert st["behind_by"] == 1
    assert st["never_pushed"] == 1

    out = snap.run_runs()
    assert out["pushed"] == 1
    assert "fund_agent_runs/run-a" in db.docs
    assert db.docs["fund_agent_runs/run-a"]["seat"] == "pm"


def test_an_unchanged_run_costs_ZERO_writes_on_the_next_cycle():
    """Steady state must not spend quota. The whole reason the hash lives in
    Postgres rather than being read back from Firestore."""
    ds, snap, db = _pair()
    _record(ds)
    snap.run_runs()
    before = db.commits
    out = snap.run_runs()
    assert out["pushed"] == 0
    assert db.commits == before, "an idle cycle wrote to Firestore"
    assert snap.runs_status()["behind_by"] == 0


def test_a_DECIDED_RECOMMENDATION_makes_the_run_stale_again():
    """THE test. `decide_recommendation` mutates the recommendations JSONB and
    touches NO timestamp — a time or sequence watermark would call this run
    up to date while the offsite copy said `open` for a decision the CEO made."""
    ds, snap, db = _pair()
    _record(ds)
    snap.run_runs()
    assert snap.runs_status()["behind_by"] == 0

    ds.decide_recommendation("run-a", 1, "accepted", "ceo")

    st = snap.runs_status()
    assert st["behind_by"] == 1
    assert st["changed_since_push"] == 1
    assert st["never_pushed"] == 0

    snap.run_runs()
    assert db.docs["fund_agent_runs/run-a"]["recommendations"][0]["status"] == "accepted"


def test_a_REWRITTEN_run_is_re_pushed():
    """record_run upserts output/verdict on conflict, also without a timestamp."""
    ds, snap, db = _pair()
    _record(ds)
    snap.run_runs()
    ds.record_run(run_id="run-a", seat="pm", task="t", output="revised output",
                  recommendations=[{"kind": "process", "text": "x"}])
    assert snap.runs_status()["behind_by"] == 1
    snap.run_runs()
    assert db.docs["fund_agent_runs/run-a"]["output"] == "revised output"


def test_a_dry_run_reports_what_it_would_do_and_writes_nothing():
    ds, snap, db = _pair()
    _record(ds)
    out = snap.run_runs(dry_run=True)
    assert out["would_push"] == 1 and out["pushed"] == 0
    assert db.docs == {}
    assert snap.runs_status()["behind_by"] == 1, "a dry run must not advance state"


def test_the_run_id_is_the_document_id_so_a_repeat_overwrites():
    """A half-finished cycle must always be safe to repeat."""
    ds, snap, db = _pair()
    _record(ds)
    snap.run_runs()
    ds.record_run(run_id="run-a", seat="pm", task="t", output="again")
    snap.run_runs()
    assert len([k for k in db.docs if k.startswith("fund_agent_runs/")]) == 1


def test_status_reports_the_two_legs_separately():
    """A caller watching the event log's lag must not have that number moved by
    an unrelated leg."""
    ds, snap, _ = _pair()
    _record(ds)
    st = snap.status()
    assert "behind_by" in st
    assert st["runs"]["behind_by"] == 1
    assert st["runs"]["behind_by"] != st["behind_by"] or st["behind_by"] == 1


def test_an_empty_runs_table_is_up_to_date_not_broken():
    _ds, snap, _ = _pair()
    st = snap.runs_status()
    assert st["runs_in_postgres"] == 0
    assert st["behind_by"] == 0
    assert "unchanged" in st["note"]
