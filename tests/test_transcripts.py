"""The interaction behind a run — brief, report, transcript (CEO, 2026-08-21).

`fund_agent_runs.output` holds what a seat CONCLUDED. It does not hold what we
asked, nor how the seat got there, and both lived only in a session that ends.

Two properties carry the design and both are tested here:

  * APPEND-ONLY. A dispatch that gained a mid-flight course correction had TWO
    briefs, and an upsert on (run_id, kind) would erase that the scope moved —
    which is exactly the thing a later reader needs to see.
  * ABSENCE IS NAMED. "no brief was captured for this run" is the answer a
    reader most often wants and the easiest to mistake for "this run had no
    brief", so the reader is told which kinds are missing rather than left to
    infer it from a short list.
"""

import os

import pytest
from _testdb import scratch_database

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
    from app.fund.deskstore import DeskStore
    s = DeskStore(dsn=test_dsn)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_agent_transcripts")
        c.commit()
    return s


def test_a_brief_and_a_report_are_stored_and_read_back():
    s = _store()
    s.add_transcript(run_id="run-1", kind="brief", content="Do the thing.")
    s.add_transcript(run_id="run-1", kind="report", content="Did the thing.")
    got = s.transcripts("run-1")
    assert got["count"] == 2
    assert [t["kind"] for t in got["transcripts"]] == ["brief", "report"]
    assert got["transcripts"][0]["content"] == "Do the thing."


def test_the_chronology_is_OLDEST_first():
    """This is a conversation, not a list of runs. Reading it newest-first puts
    the answer above the question."""
    s = _store()
    s.add_transcript(run_id="run-2", kind="brief", content="first")
    s.add_transcript(run_id="run-2", kind="transcript", content="second")
    s.add_transcript(run_id="run-2", kind="report", content="third")
    assert [t["content"] for t in s.transcripts("run-2")["transcripts"]] == [
        "first", "second", "third"]


def test_a_SECOND_brief_is_a_second_row_not_an_overwrite():
    """THE append-only property. A mid-flight course correction is a real event
    in a dispatch's life; collapsing it onto one row erases that the scope
    moved."""
    s = _store()
    s.add_transcript(run_id="run-3", kind="brief", content="original scope")
    s.add_transcript(run_id="run-3", kind="brief", content="course correction")
    got = s.transcripts("run-3", kind="brief")
    assert got["count"] == 2
    assert [t["content"] for t in got["transcripts"]] == [
        "original scope", "course correction"]


def test_missing_kinds_are_NAMED_rather_than_left_to_inference():
    s = _store()
    s.add_transcript(run_id="run-4", kind="report", content="only the report")
    got = s.transcripts("run-4")
    assert got["kinds_present"] == ["report"]
    assert sorted(got["kinds_missing"]) == ["brief", "transcript"]
    assert "NOT captured" in got["note"]
    assert "not the same as the run not having had one" in got["note"]


def test_a_run_with_nothing_captured_says_the_interaction_is_GONE():
    s = _store()
    got = s.transcripts("run-never")
    assert got["count"] == 0
    assert got["transcripts"] == []
    assert "gone, not empty" in got["note"]


def test_an_unknown_kind_is_refused_rather_than_stored():
    """A free-text kind makes 'did we keep the brief' unanswerable by query."""
    s = _store()
    with pytest.raises(ValueError) as e:
        s.add_transcript(run_id="run-5", kind="musings", content="x")
    assert "must be one of" in str(e.value)


def test_an_EMPTY_transcript_is_refused():
    """An empty row reads as 'we captured this' when nothing was captured."""
    s = _store()
    for blank in ("", "   ", "\n"):
        with pytest.raises(ValueError) as e:
            s.add_transcript(run_id="run-6", kind="brief", content=blank)
        assert "empty" in str(e.value)


def test_the_kind_is_normalised_so_case_does_not_fork_the_record():
    s = _store()
    s.add_transcript(run_id="run-7", kind="BRIEF", content="x")
    assert s.transcripts("run-7")["kinds_present"] == ["brief"]


def test_a_transcript_may_be_stored_BEFORE_its_run_exists():
    """A brief is written before a run resolves. Requiring the run row first
    would mean the one artifact written earliest is the one that cannot be
    stored."""
    s = _store()
    out = s.add_transcript(run_id="run-not-yet", kind="brief", content="ahead of time")
    assert out["transcript_id"] > 0
    assert s.transcripts("run-not-yet")["count"] == 1


def test_content_can_be_omitted_from_the_read_for_an_index():
    s = _store()
    s.add_transcript(run_id="run-8", kind="transcript", content="x" * 5000)
    got = s.transcripts("run-8", with_content=False)
    assert got["transcripts"][0]["content"] is None
    # The SIZE still comes back, so an index can say how much is there without
    # shipping it.
    assert got["transcripts"][0]["chars"] == 5000
