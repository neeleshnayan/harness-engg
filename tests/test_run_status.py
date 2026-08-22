"""The flight recorder must be able to record work that DIED, and corrections.

TWO DEFECTS, BOTH MEASURED ON 2026-08-22, BOTH GUARDED HERE.

**(1) A dispatch that dies costs zero by construction.** The recorder is
written at RESOLVE, so a run that never returns — host RAM collapse, a hung
suite, a cut session — leaves no row at all. A three-hour builder dispatch
produced zero bytes that morning and the firm's cost meter recorded nothing.
`status` makes the outcome queryable; NULL means `unrecorded` and is never
read as success, because every one of the 52 pre-existing rows would otherwise
fabricate a 100% delivery rate out of an absence.

**(2) THE UPSERT WAS LOSING THE CORRECTIONS IT WAS BEING SENT.** Measured
before the fix, by round trip against Postgres: re-recording a run with a
corrected `tool_uses` kept the OLD number, re-recording with a corrected
`dispatched_at` kept the OLD timestamp, and re-recording WITHOUT `tokens`
blanked the stored count. `tokens` took EXCLUDED unconditionally while
`tool_uses` and `dispatched_at` were not in the DO UPDATE list at all — data
loss in both directions, in the one table the CFO's meter reads.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = "krypton_fund_test"


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
            cur.execute("TRUNCATE fund_agent_runs")
        c.commit()
    return s


def _one(store, run_id="r1"):
    return [r for r in store.runs(limit=50) if r["run_id"] == run_id][0]


# --- recording a failure ----------------------------------------------------

def test_a_dispatch_that_FAILED_is_recordable_and_queryable():
    """Not prose in a verdict — a column, so `what did failed work cost` is a
    query rather than a grep."""
    s = _store()
    s.record_run(run_id="dead", seat="builder", task="D13", output="",
                 tokens=180_000, tool_uses=40, status="failed",
                 dispatched_at="2026-08-22T09:00:00+00:00")
    got = _one(s, "dead")
    assert got["status"] == "failed"
    assert got["tokens"] == 180_000

    from app.fund import metrics
    stats = metrics.summarise_runs(s.all_runs())
    assert stats["runs_failed"] == 1
    assert stats["by_seat"]["builder"]["by_status"] == {"failed": 1}


def test_an_ABORTED_run_is_distinct_from_a_FAILED_one():
    """A decision to stop and a crash carry opposite lessons; a meter that
    merges them cannot tell a discipline from an outage."""
    s = _store()
    s.record_run(run_id="a", seat="quant", task="t", output="", status="aborted")
    s.record_run(run_id="f", seat="quant", task="t", output="", status="failed")
    statuses = sorted(r["status"] for r in s.runs(limit=10))
    assert statuses == ["aborted", "failed"]


def test_a_run_recorded_with_NO_status_reads_unrecorded_not_delivered():
    """Every one of the 52 rows written before this column existed made no
    statement. Defaulting them to `delivered` would invent a success rate."""
    s = _store()
    s.record_run(run_id="old", seat="pm", task="t", output="out")
    assert _one(s, "old")["status"] is None

    from app.fund import metrics
    stats = metrics.summarise_runs(s.all_runs())
    assert stats["by_seat"]["pm"]["by_status"] == {"unrecorded": 1}
    assert stats["runs_failed"] == 0
    assert stats["runs_unrecorded_status"] == 1
    assert "FLOOR" in stats["note"], (
        "a zero failure count beside unrecorded rows must be declared a floor")


def test_a_mistyped_status_is_REFUSED_not_silently_nulled():
    """Nulling it would report a failed run as unrecorded — a quiet loss in
    the one field built to stop quiet losses."""
    s = _store()
    with pytest.raises(ValueError):
        s.record_run(run_id="x", seat="pm", task="t", output="o",
                     status="FAILED_MISERABLY")
    with pytest.raises(ValueError):
        s.record_run(run_id="x", seat="pm", task="t", output="o", status=7)
    assert [r for r in s.runs(limit=10) if r["run_id"] == "x"] == []


def test_status_is_case_insensitive_on_the_way_in_and_normalised_on_the_way_out():
    s = _store()
    s.record_run(run_id="c", seat="pm", task="t", output="o", status=" Failed ")
    assert _one(s, "c")["status"] == "failed"


# --- the upsert must not lose corrections -----------------------------------

def test_re_recording_a_corrected_tool_uses_ACTUALLY_UPDATES_IT():
    """REGRESSION. Before 2026-08-22 the DO UPDATE list omitted `tool_uses`
    entirely, so a chair correcting it got a silent no-op while `tokens` moved
    on the same call."""
    s = _store()
    s.record_run(run_id="r1", seat="builder", task="t", output="o",
                 tokens=10, tool_uses=3)
    s.record_run(run_id="r1", seat="builder", task="t", output="o2",
                 tokens=20, tool_uses=99)
    got = _one(s)
    assert got["tool_uses"] == 99
    assert got["tokens"] == 20


def test_re_recording_a_corrected_dispatched_at_ACTUALLY_UPDATES_IT():
    """REGRESSION, same defect. dispatched_at is the ONLY source of a run's
    wall-clock and it was not in the DO UPDATE list."""
    s = _store()
    s.record_run(run_id="r1", seat="builder", task="t", output="o",
                 dispatched_at="2026-08-21T09:00:00+00:00")
    s.record_run(run_id="r1", seat="builder", task="t", output="o",
                 dispatched_at="2026-08-21T08:00:00+00:00")
    assert _one(s)["dispatched_at"].startswith("2026-08-21T08:00:00")


def test_re_recording_WITHOUT_a_field_does_not_ERASE_the_stored_one():
    """REGRESSION. `tokens = EXCLUDED.tokens` blanked a known count whenever a
    later POST omitted it. A re-record is a CORRECTION, not a replacement."""
    s = _store()
    s.record_run(run_id="r1", seat="builder", task="t", output="o",
                 tokens=10, tool_uses=3, status="delivered",
                 dispatched_at="2026-08-21T09:00:00+00:00")
    s.record_run(run_id="r1", seat="builder", task="t", output="corrected text")
    got = _one(s)
    assert got["tokens"] == 10
    assert got["tool_uses"] == 3
    assert got["status"] == "delivered"
    assert got["dispatched_at"].startswith("2026-08-21T09:00:00")


# --- the uncapped lifetime read ---------------------------------------------

def test_run_stats_reads_EVERY_row_and_proves_it():
    """A cap read as a count is how the firm's first spend meter under-reported
    lifetime runs by more than half."""
    from app.fund import metrics
    s = _store()
    for i in range(30):
        s.record_run(run_id=f"r{i}", seat="builder" if i % 2 else "pm",
                     task="t", output="o", tokens=i, tool_uses=1)
    got = metrics.run_stats(s)
    assert got["row_count"] == 30
    assert got["rows_read"] == 30
    assert got["truncated"] is False
    assert got["complete"] is True
    assert got["total_runs"] == 30
    # The default payload cap is 25: this is the exact gap that was invisible.
    assert len(s.runs(limit=25)) == 25


def test_run_stats_DECLARES_truncation_rather_than_reporting_a_floor_as_a_count():
    from app.fund import metrics

    class Capped:
        def all_runs(self, limit=100_000):
            return [{"seat": "a", "tokens": 1, "tool_uses": 1}] * 5

        def run_count(self):
            return 50

    got = metrics.run_stats(Capped())
    assert got["truncated"] is True
    assert got["complete"] is False
    assert got["note"].startswith("TRUNCATED: 5 of 50")


def test_run_stats_on_an_absent_recorder_is_UNKNOWN_not_zero():
    from app.fund import metrics
    got = metrics.run_stats(None)
    assert metrics.is_unknown(got)
    assert got["reason"] == "RECORDER_UNREACHABLE"


# --- the cap that was a bug -------------------------------------------------

def test_run_by_id_does_NOT_depend_on_the_row_being_in_a_capped_window():
    """REGRESSION, 2026-08-22, AND THE TEST IS BUILT SO THE OLD CODE FAILS IT.

    `run()` used to fetch the newest 1,000 rows with no key and filter in
    Python, so run number 1,001 would 404 while sitting in the table — the
    endpoint saying "no run <id>" about a run that exists. Same defect as the
    25-run payload cap that truncated the firm's first spend meter, one
    row-limit further out.

    Inserting 1,001 rows to prove it would be slow and would still only prove
    it at ONE limit. Instead the unkeyed listing is made to return nothing —
    exactly what a row outside the window looks like — so any implementation
    that SCANS a list fails, and only one that looks the row up by primary key
    passes. The bug cannot hide behind a small fixture."""
    s = _store()
    s.record_run(run_id="r0", seat="pm", task="t", output="body-0")

    real = s.runs
    seen = []

    def only_keyed(*a, **kw):
        seen.append(kw.get("run_id"))
        if not kw.get("run_id"):
            return []          # the row is outside the window
        return real(*a, **kw)

    s.runs = only_keyed
    got = s.run("r0")
    assert got is not None, ("run() scanned an unkeyed list instead of looking "
                            "the row up by primary key")
    assert got["run_id"] == "r0"
    assert got["output"] == "body-0"
    assert seen == ["r0"], f"expected one keyed lookup, got calls {seen}"


def test_run_by_id_returns_None_for_a_run_that_does_not_exist():
    s = _store()
    s.record_run(run_id="r1", seat="pm", task="t", output="o")
    assert s.run("nope") is None


def test_runs_filtered_by_run_id_ignores_the_seat_filter():
    """run_id is a primary key; combining it with seat could only ever return
    the same row or nothing, and silently returning nothing would look like a
    missing run."""
    s = _store()
    s.record_run(run_id="r1", seat="pm", task="t", output="o")
    assert [r["run_id"] for r in s.runs(seat="builder", run_id="r1")] == ["r1"]
