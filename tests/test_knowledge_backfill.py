"""The backfill — best effort, and honest about every edge of that effort.

Runs against a FIXTURE, never the live store. The fixture's source tables are
created by executing the OWNING MODULES' own SCHEMA strings rather than a
second copy of the DDL: two structures that must agree should be derived, not
maintained in parallel, and a copy here would silently pass after the real
table changed shape.

**ITS OWN DATABASE, AND THAT IS NOT FASTIDIOUSNESS — IT IS A MEASURED FLAKE.**
This module needs to read ALL of ``fund_candidates``, because that is what the
backfill does. In ``krypton_fund_test`` that table is TRUNCATEd by
``test_factory.py`` and ``test_provenance.py``, and ``test_factory.py`` submits
candidates on BACKGROUND THREADS — so the rows are not exclusively any one
module's even inside a single pytest process. Measured 2026-08-23: a DIFFERENT
test in this module failed on each of three consecutive runs, and the row left
behind was ``algorithm='algo'`` (test_factory's) stamped inside this module's
run window, written by a SECOND pytest process running concurrently under the
two-builders arrangement.

``krypton_fund_kgtest`` is not any fund mode's ledger (``tests/
test_fund_mode.py`` K1 asserts that property for the mode databases, and this
name is none of them).

What each test pins is a way the ingestion could quietly lie:

  * an interrupted candidate scored as a verdict
  * a shared container window divided between siblings
  * the fence catching a different set than the six it names
  * a re-run duplicating the graph
  * a missing source table reading as zero rows
  * a partial header filled in with a plausible guess
"""

import os

import pytest
from _testdb import scratch_database

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

#: THIS MODULE'S OWN SCRATCH DATABASE. See the module docstring for the
#: measured reason; the short version is that this module reads the WHOLE of
#: fund_candidates and two other modules own rows in it.
TEST_DB = scratch_database("krypton_fund_kgtest")

#: The fixture's own dates. The fence's real cohort is 2026-08-20/21; the
#: fixture puts exactly ONE candidate on 2026-08-20, so a run with
#: ``expect_fenced=1`` exercises the fencing path and a run at the live default
#: of 6 must REFUSE.
FENCE_DAY = "2026-08-20"
OTHER_DAY = "2026-08-16"


def _dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


def _connect():
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
    return psycopg.connect(_dsn())


def _source_schema(cur, with_jobs=True, with_runs=True) -> None:
    """Create the source tables from their owning modules' own DDL."""
    from app.fund.factory import SCHEMA as CANDIDATE_SCHEMA
    cur.execute(CANDIDATE_SCHEMA)
    if with_jobs:
        from app.fund.leanstore import SCHEMA as LEAN_SCHEMA
        cur.execute(LEAN_SCHEMA)
    if with_runs:
        from app.fund.deskstore import SCHEMA as DESK_SCHEMA
        cur.execute(DESK_SCHEMA)


def _fixture(with_jobs=True, with_runs=True):
    """Six candidates covering every interpretation branch, and their jobs."""
    import json
    # EXPLICIT since the reader/writer split: constructing a graph no longer
    # issues DDL, so the fixture has to ask. Without this the TRUNCATE below
    # fails on a first run against a fresh krypton_fund_kgtest — and it passed
    # only because the tables happened to survive from an earlier run.
    _graph().ensure_schema()
    conn = _connect()
    with conn:
        with conn.cursor() as cur:
            _source_schema(cur, with_jobs, with_runs)
            cur.execute("TRUNCATE kg_edge, kg_outcome, kg_hypothesis")
            cur.execute("TRUNCATE fund_candidates")
            if with_jobs:
                cur.execute("TRUNCATE fund_lean_jobs")
            if with_runs:
                cur.execute("TRUNCATE fund_agent_runs")

            def cand(cid, algo, day, hh, state, passed, failures, gv="v4.1",
                     checks=None, minutes=10):
                verdict = None
                if state == "done":
                    verdict = json.dumps({"gate_version": gv, "passed": passed,
                                          "failures": failures,
                                          "checks": checks or {}})
                cur.execute(
                    "INSERT INTO fund_candidates (candidate_id, algorithm, "
                    "grid, state, passed, failures, verdict, started_at, "
                    "finished_at) VALUES (%s,%s,'{}'::jsonb,%s,%s,%s,%s,%s,%s)",
                    (cid, algo, state, passed, json.dumps(failures), verdict,
                     f"{day}T{hh}:00:00+00:00",
                     f"{day}T{hh}:{minutes:02d}:00+00:00"))

            # 1. exclusive window, one kill reason, named by a run
            cand("aaaa00000001", "solo_algo", OTHER_DAY, "01", "done", False,
                 ["no held-out test - choosing the best of N settings"],
                 checks={"psr_pct": 12.0})
            # 2. exclusive window, PASSED
            cand("aaaa00000002", "pass_algo", OTHER_DAY, "02", "done", True, [])
            # 3+4. TWO candidates of the same algorithm, overlapping windows
            cand("aaaa00000003", "twin_algo", OTHER_DAY, "03", "done", False,
                 ["probabilistic Sharpe 1% is below 65.0% - luck"])
            cand("aaaa00000004", "twin_algo", OTHER_DAY, "03", "done", False,
                 ["probabilistic Sharpe 2% is below 65.0% - luck"])
            # 5. ORPHANED: no verdict was ever reached
            cand("aaaa00000005", "orphan_algo", OTHER_DAY, "05", "orphaned",
                 None, [])
            # 6. on a FENCED date
            cand("aaaa00000006", "fenced_algo", FENCE_DAY, "06", "done", False,
                 ["cost robustness was never measured (none run) - x"])

            if with_jobs:
                for jid, algo, day, hh, mm, secs in [
                        ("j1", "solo_algo", OTHER_DAY, "01", "05", 100.0),
                        ("j2", "solo_algo", OTHER_DAY, "01", "06", 40.0),
                        ("j3", "pass_algo", OTHER_DAY, "02", "05", 7.0),
                        ("j4", "twin_algo", OTHER_DAY, "03", "05", 999.0),
                        ("j5", "fenced_algo", FENCE_DAY, "06", "05", 55.0)]:
                    cur.execute(
                        "INSERT INTO fund_lean_jobs (job_id, algorithm, state, "
                        "wall_seconds, submitted_at) VALUES (%s,%s,'done',%s,%s)",
                        (jid, algo, secs, f"{day}T{hh}:{mm}:00+00:00"))

            if with_runs:
                cur.execute(
                    "INSERT INTO fund_agent_runs (run_id, seat, task, output) "
                    "VALUES ('run-quant-fixture','quant','belt run',"
                    "'ran candidate aaaa00000001 end to end')")
                cur.execute(
                    "INSERT INTO fund_agent_runs (run_id, seat, task, output) "
                    "VALUES ('run-noise','pm','unrelated','no ids here')")
        conn.commit()

    # THE FIXTURE VERIFIES ITSELF, out loud. A fixture that quietly built a
    # different world would surface three lines later as a confusing count
    # mismatch in whichever test happened to run — which is exactly how the
    # shared-database race presented before this module got its own store.
    with _connect() as c2:
        with c2.cursor() as cur:
            cur.execute("SELECT count(*), count(*) FILTER (WHERE "
                        "started_at::date = %s) FROM fund_candidates",
                        (FENCE_DAY,))
            total, fenced = cur.fetchone()
    assert (total, fenced) == (6, 1), (
        f"the fixture built {total} candidates with {fenced} on the fenced "
        f"date, not 6 and 1 — something else is writing to {TEST_DB}")


def _ingest(expect_fenced=1, **kw):
    import scripts.kg.backfill as bf  # noqa: F401  (import for coverage)
    from scripts.kg.backfill import ingest
    return ingest(_dsn(), "run-fixture", expect_fenced=expect_fenced, **kw)


def _graph():
    from app.fund.knowledge import KnowledgeGraph
    return KnowledgeGraph(dsn=_dsn())


@pytest.fixture(autouse=True)
def _sys_path():
    """``scripts/`` is already on sys.path via tests/conftest.py; the package
    directory needs an entry too so ``scripts.kg.backfill`` imports."""
    import pathlib
    import sys
    root = pathlib.Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))


def test_the_fixture_ingests_and_counts_every_source():
    _fixture()
    rep = _ingest()
    s = rep["sources"]["fund_candidates"]
    assert s["rows_read"] == 6
    assert s["hypotheses_written"] == 6
    assert s["outcomes_written"] == 5, "the orphaned candidate has no verdict"
    assert s["judged"] == 5
    assert s["uninterpretable_no_verdict"] == 1
    assert rep["sources"]["fund_agent_runs"]["outcomes_written"] == 0
    assert rep["sources"]["fund_agent_runs"]["uninterpretable_as_outcomes"] == 2
    assert rep["sources"]["fund_lean_jobs"]["outcomes_written"] == 0
    assert rep["edges_written"] == 0


def test_an_ORPHANED_candidate_gets_a_hypothesis_and_NO_outcome():
    """An interrupted run produced no evidence.

    Scoring it as a kill would credit the gate with a decision it never made;
    scoring it as a survivor would be worse. It reads "not yet judged".
    """
    _fixture()
    _ingest()
    kg = _graph()
    d = kg.family_ledger("orphan_algo")
    # RECORDED, NOT TESTED. The candidate is in the graph and has no verdict,
    # and since 2026-08-23 the ledger has a status that can say exactly that —
    # v1 called this family TESTED, which is the sentence the validator's
    # spot-audit caught reading "tested: 6, not yet judged: 6".
    assert d["status"] == "RECORDED_UNJUDGED"
    assert d["recorded"] == 1 and d["judged"] == 0
    assert d["killed"] == 0 and d["survivors"] == []
    assert d["unjudged"] == ["cand-aaaa00000005"]


def test_a_SHARED_container_window_reports_ABSENT_rather_than_dividing():
    """Two twin_algo candidates ran in the same window over one 999s job.

    Attributing 999s to each would double the bill; halving it would invent an
    allocation nobody measured. Both report ABSENT with basis ``ambiguous``.
    """
    _fixture()
    rep = _ingest()
    # The WHOLE distribution, not just the interesting cell: three bases are
    # three different absences and a test that pinned one of them would go
    # green while the other two collapsed into each other.
    #   exclusive 3 = solo_algo, pass_algo, fenced_algo
    #   ambiguous 2 = the twin_algo pair
    #   no_jobs   1 = orphan_algo, whose window holds no container at all
    assert rep["cost_basis"] == {"exclusive": 3, "ambiguous": 2, "no_jobs": 1}
    kg = _graph()
    twins = kg._out_rows("WHERE hypothesis_id = ANY(%s)",
                         (["cand-aaaa00000003", "cand-aaaa00000004"],))
    assert len(twins) == 2
    for t in twins:
        assert t["container_seconds"] is None
        assert t["container_cost_basis"] == "ambiguous"
    solo = kg._out_rows("WHERE hypothesis_id = 'cand-aaaa00000001'")[0]
    assert solo["container_seconds"] == pytest.approx(140.0)
    assert solo["container_cost_basis"] == "exclusive"


def test_a_REAL_citing_run_beats_the_ingestion_run():
    _fixture()
    rep = _ingest()
    assert rep["sources"]["fund_candidates"]["with_real_citing_run"] == 1
    assert rep["sources"]["fund_candidates"]["citing_the_ingestion_run"] == 5
    kg = _graph()
    named = kg._hyp_rows("WHERE id = 'cand-aaaa00000001'")[0]
    assert named["run_id"] == "run-quant-fixture"
    other = kg._hyp_rows("WHERE id = 'cand-aaaa00000002'")[0]
    assert other["run_id"] == "run-fixture", (
        "a candidate no run names cites the ingestion, which is honest about "
        "being an ingestion rather than borrowing somebody else's run")


def test_the_FENCED_cohort_is_voided_and_leaves_every_comparison():
    _fixture()
    rep = _ingest()
    assert rep["voided_by_fence"] == 1
    assert rep["fenced"] == ["aaaa00000006"]
    kg = _graph()
    row = kg._out_rows("WHERE hypothesis_id = 'cand-aaaa00000006'")[0]
    assert row["verdict"] == "voided"
    assert row["voided_from"] == "fail"
    assert "clean-field amendment" in row["void_reason"]
    d = kg.family_ledger("fenced_algo")
    assert d["killed"] == 0 and d["survivors"] == []
    assert d["unjudged_because_voided"] == ["cand-aaaa00000006"]
    assert "cost_robustness_unmeasured" not in [
        c["slug"] for c in kg.kill_taxonomy()["causes"]], (
        "a fenced kill must not appear in the taxonomy")


def test_the_fence_REFUSES_when_the_derivation_finds_the_wrong_count():
    """Fencing the wrong rows is worse than fencing none.

    The live cohort is exactly six; a store where the derivation returns any
    other number is a store where the fence would be pointed at something else.
    """
    _fixture()
    with pytest.raises(SystemExit, match="REFUSING"):
        _ingest(expect_fenced=6)


def test_the_backfill_is_IDEMPOTENT():
    _fixture()
    first = _ingest()
    second = _ingest()
    assert first["sources"]["fund_candidates"]["hypotheses_written"] == 6
    assert second["sources"]["fund_candidates"]["hypotheses_written"] == 0
    assert second["sources"]["fund_candidates"]["outcomes_written"] == 0
    assert second["voided_by_fence"] == 0, (
        "a second void on the same row would raise; the dedupe key must stop "
        "the row being written twice in the first place")
    kg = _graph()
    assert len(kg._hyp_rows()) == 6
    assert len(kg._out_rows()) == 5


def test_backfilled_headers_are_NULL_rather_than_RECONSTRUCTED():
    """Pre-grammar proposals get partial headers, never plausible guesses.

    A mechanism sentence invented for a 2026-08-16 candidate would read exactly
    like one a seat wrote, and the graph would become a second record instead
    of an index over the first.
    """
    _fixture()
    _ingest()
    h = _graph()._hyp_rows("WHERE id = 'cand-aaaa00000001'")[0]
    assert h["provenance"] == "backfill"
    assert h["source"] is None, "the source is unknown, and NULL says so"
    assert h["source_ref"] == "fund_candidates:aaaa00000001"
    for field in ("mechanism", "counterparty", "claim_type", "entities",
                  "observable", "horizon", "predictions", "falsifier"):
        assert h[field] is None, f"{field} was reconstructed rather than left NULL"


def test_a_MISSING_source_table_reads_UNREADABLE_rather_than_zero():
    """Unreadable is not unchanged, and an absent table is not an empty one.

    An earlier draft simply crashed here, which is the same defect louder.
    """
    import psycopg
    _fixture(with_jobs=False, with_runs=False)
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS fund_lean_jobs")
            cur.execute("DROP TABLE IF EXISTS fund_agent_transcripts")
            cur.execute("DROP TABLE IF EXISTS fund_agent_runs")
        c.commit()
    rep = _ingest()
    jobs = rep["sources"]["fund_lean_jobs"]
    runs = rep["sources"]["fund_agent_runs"]
    assert jobs["present"] is False and jobs["rows_read"] is None
    assert runs["present"] is False and runs["rows_read"] is None
    assert "TABLE ABSENT" in jobs["why"] and "TABLE ABSENT" in runs["why"]
    assert rep["cost_basis"] == {"unmeasured": 6}, (
        "with no jobs table every cost is `unmeasured` — NOT `no_jobs`, which "
        "would claim we looked and found none")
    assert rep["sources"]["fund_candidates"]["with_real_citing_run"] == 0
    from scripts.kg.backfill import render
    text = render(rep)
    assert "UNREADABLE" in text and "TABLE ABSENT" in text


def test_the_dry_run_writes_nothing_but_still_counts():
    _fixture()
    rep = _ingest(dry_run=True)
    assert rep["dry_run"] is True
    assert rep["sources"]["fund_candidates"]["rows_read"] == 6
    assert rep["kill_reason_slugs"]  # classification still happens
    assert rep["voided_by_fence"] == 0
    kg = _graph()
    assert kg._hyp_rows() == [] and kg._out_rows() == []


def test_every_fixture_kill_sentence_classifies():
    _fixture()
    rep = _ingest()
    assert rep["unclassified_kill_reasons"] == []
    assert rep["kill_reason_slugs"] == {
        "psr_below_floor": 2, "cost_robustness_unmeasured": 1,
        "holdout_absent": 1}
