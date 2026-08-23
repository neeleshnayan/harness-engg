"""The store, the endpoint, and the two cross-module agreements.

Everything here needs either Postgres or the spine router, which is why it is
separate from the three pure-function modules beside it.

THE DATABASE TESTS RUN AGAINST THEIR OWN DATABASE, ``krypton_fund_eqtest``,
and the reason is measured rather than cautious: ``krypton_fund_test`` is a
singleton across concurrent pytest processes, ``tests/test_factory.py``
TRUNCATEs shared tables from BACKGROUND THREADS, and a builder dispatch in
2026-08-23 lost three runs to a row another process wrote inside its window.
Any test module that reads a WHOLE table gets its own database; this one reads
the whole of ``fund_execution_quotes`` in almost every assertion.
"""

from __future__ import annotations

import os

import pytest

from app.fund import executionquality as eq

#: Its own database. Created on demand and never shared - see the module
#: docstring for the race this avoids.
EQ_TEST_DB = "krypton_fund_eqtest"


def _dsn() -> str:
    from app.fund.pgstore import dsn as base
    root = base()
    return root.rsplit("/", 1)[0] + "/" + EQ_TEST_DB


def _postgres_or_skip() -> str:
    """The DSN for this module's own database, creating it if need be.

    Skips rather than fails when there is no Postgres: the arithmetic and fold
    modules carry the behaviour that must hold everywhere, and a developer with
    no database should still be able to run those.
    """
    psycopg = pytest.importorskip("psycopg")
    from app.fund.pgstore import dsn as base
    try:
        with psycopg.connect(base(), autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                            (EQ_TEST_DB,))
                if cur.fetchone() is None:
                    cur.execute(f'CREATE DATABASE "{EQ_TEST_DB}"')
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres available for the execution-quote store: {e}")
    return _dsn()


@pytest.fixture
def store():
    """A schema'd, EMPTY store on this module's own database."""
    import psycopg
    dsn = _postgres_or_skip()
    s = eq.QuoteStore(dsn)
    s.ensure_schema()
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE fund_execution_quotes")
        conn.commit()
    # THE FIXTURE VERIFIES WHAT IT BUILT. A confusing count three assertions
    # later is how the cross-process race presented last time.
    assert s.count() == 0
    return s


def _row(**over):
    base = dict(order_id="o1", event_kind="filled", event_seq=100,
                event_ts="2026-08-14T13:30:03.230302+00:00",
                basis=eq.LIVE_BASIS, capture_run="run-test",
                symbol="GLD", side="buy", submitted_venue="alpaca",
                was_submitted=True, bid=402.19, ask=402.25,
                quote_ts="2026-08-14T13:30:03.100000+00:00", feed=eq.LIVE_FEED,
                fill_price=402.18, filled_qty=0.424471)
    base.update(over)
    return base


# --- construction takes no lock -------------------------------------------

def test_constructing_a_quote_store_issues_no_ddl(monkeypatch):
    """CONSTRUCTION MUST NOT TOUCH THE DATABASE.

    The knowledge graph shipped ``_ensure()`` in ``__init__`` and a read-only
    report consequently wedged a live table for about five minutes behind one
    ordinary transaction. This is that defect's regression test: building the
    object may not open a connection at all.
    """
    opened = []

    def explode(*a, **kw):
        opened.append(a)
        raise AssertionError("QuoteStore.__init__ opened a connection")

    monkeypatch.setattr(eq.QuoteStore, "_connect", explode)
    eq.QuoteStore("postgresql://nobody@127.0.0.1:1/nothing")
    assert opened == []


def test_the_module_does_not_declare_itself_a_work_layer_store():
    """The spine SERVES this table, so it must stay importable by the spine.

    ``tests/test_knowledge_isolation.py`` derives the set of modules the spine
    may not import from a ``WORK_LAYER_STORE`` declaration. The episode store
    and the knowledge graph carry it; execution quality is a fact about the
    fund's own money and must not, or ``GET /fund/execution/quality`` becomes
    unimportable the moment somebody runs that guard.
    """
    assert not hasattr(eq, "WORK_LAYER_STORE")


# --- the reader/writer split ----------------------------------------------

def test_reading_a_store_with_no_table_raises_rather_than_returning_empty():
    """SchemaAbsent, not ``[]``.

    "The capture service has never run here" and "it ran and saw nothing" are
    different facts, and only one of them is a reason to go and start it. A
    reader that returns an empty list for both teaches the fund that it has no
    fills to measure.
    """
    dsn = _postgres_or_skip()
    import psycopg
    scratch = dsn.rsplit("/", 1)[0] + "/krypton_fund_eqtest_absent"
    with psycopg.connect(dsn.rsplit("/", 1)[0] + "/postgres",
                         autocommit=True) as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s",
                    ("krypton_fund_eqtest_absent",))
        if cur.fetchone() is None:
            cur.execute('CREATE DATABASE "krypton_fund_eqtest_absent"')
    with psycopg.connect(scratch) as conn, conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS fund_execution_quotes")
        conn.commit()
    s = eq.QuoteStore(scratch)
    with pytest.raises(eq.SchemaAbsent):
        s.rows()
    with pytest.raises(eq.SchemaAbsent):
        s.count()
    with pytest.raises(eq.SchemaAbsent):
        s.max_event_seq()


def test_ensure_schema_is_memoised_per_instance(store):
    """It returns True the time it ran and False after, so a poll loop issues
    the DDL once rather than once a tick."""
    fresh = eq.QuoteStore(_dsn())
    assert fresh.ensure_schema() is True
    assert fresh.ensure_schema() is False


# --- the database enforces absence ----------------------------------------

def test_a_midpoint_cannot_be_stored_without_both_sides(store):
    """THE ROW THE WHOLE INSTRUMENT EXISTS TO PREVENT: a mid with no quote.

    Enforced in the DATABASE rather than by whoever writes the next caller,
    because a convention only its author honours is the unwired-kill-switch
    pattern. Written with raw SQL deliberately: ``record`` cannot produce this
    row, and a constraint that only the happy path respects is not a
    constraint.
    """
    import psycopg
    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO fund_execution_quotes (order_id, event_kind,"
                " event_seq, event_ts, mid, basis, capture_run)"
                " VALUES ('o9','filled',9,'t',402.22,%s,'r')",
                (eq.LIVE_BASIS,))


def test_an_absent_mid_must_carry_a_stated_reason(store):
    """No mid and no reason is a row that says nothing and looks like data."""
    import psycopg
    for reason in (None, "", "   "):
        with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(
                    "INSERT INTO fund_execution_quotes (order_id, event_kind,"
                    " event_seq, event_ts, quote_absent_reason, basis,"
                    " capture_run) VALUES ('o9','filled',9,'t',%s,%s,'r')",
                    (reason, eq.LIVE_BASIS))


def test_a_basis_point_figure_cannot_be_stored_without_a_midpoint(store):
    """An effective spread with no mid under it is a fabricated cost."""
    import psycopg
    for col in ("effective_spread_bps", "signed_effective_spread_bps"):
        with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
            with pytest.raises(psycopg.errors.CheckViolation):
                cur.execute(
                    f"INSERT INTO fund_execution_quotes (order_id, event_kind,"
                    f" event_seq, event_ts, quote_absent_reason, {col},"
                    f" basis, capture_run)"
                    f" VALUES ('o9','filled',9,'t','no_quote',1.5,%s,'r')",
                    (eq.LIVE_BASIS,))


@pytest.mark.parametrize("field, bad", [
    ("event_kind", "cancelled"),
    ("basis", "whatever-i-fancied"),
    ("feed", "bloomberg"),
])
def test_the_vocabularies_are_closed_in_the_database(store, field, bad):
    """A value outside the vocabulary is refused by the table, not just by
    Python. Python's check can be bypassed by the next caller with a cursor;
    the constraint cannot."""
    import psycopg
    cols = dict(order_id="o9", event_kind="filled", event_seq=9, event_ts="t",
                basis=eq.LIVE_BASIS, capture_run="r")
    cols[field] = bad
    if field == "feed":
        cols["feed"] = bad
        cols["quote_absent_reason"] = "no_quote"
    else:
        cols["quote_absent_reason"] = "no_quote"
    names = ", ".join(cols)
    marks = ", ".join(["%s"] * len(cols))
    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(f"INSERT INTO fund_execution_quotes ({names}) "
                        f"VALUES ({marks})", tuple(cols.values()))


def test_a_blank_capture_run_is_refused(store):
    """Every row names the process that wrote it, so a bad capture can be
    fenced off later. NOT NULL happily accepts the empty string, which is why
    there is a CHECK beside it and a Python guard in front of it."""
    with pytest.raises(ValueError):
        store.record(**_row(capture_run="   "))
    import psycopg
    with psycopg.connect(_dsn()) as conn, conn.cursor() as cur:
        with pytest.raises(psycopg.errors.CheckViolation):
            cur.execute(
                "INSERT INTO fund_execution_quotes (order_id, event_kind,"
                " event_seq, event_ts, quote_absent_reason, basis,"
                " capture_run) VALUES ('o9','filled',9,'t','no_quote',%s,' ')",
                (eq.LIVE_BASIS,))


# --- record() -------------------------------------------------------------

def test_record_derives_every_figure_and_stores_the_derivation(store):
    """The caller hands over observations; the arithmetic happens ONCE, here.

    Catches a second caller shipping a second convention: if ``record`` ever
    accepted a pre-computed spread, two writers could disagree about what a
    basis point means and the table would hold both.
    """
    got = store.record(**_row())
    assert got["created"] is True
    rows, truncated = store.rows()
    assert truncated is False and len(rows) == 1
    r = rows[0]
    assert r["mid"] == pytest.approx((402.19 + 402.25) / 2)
    assert r["spread_bps"] == pytest.approx(eq.spread_bps_of(402.19, 402.25))
    assert r["effective_spread_bps"] == pytest.approx(
        eq.effective_spread_bps(402.18, r["mid"]))
    assert r["signed_effective_spread_bps"] == pytest.approx(
        eq.signed_effective_spread_bps(402.18, r["mid"], "buy"))
    assert r["quote_absent_reason"] is None


def test_a_one_sided_quote_stores_the_side_it_saw_and_no_midpoint(store):
    """The live DBA observation: bid 27.49, ask 0.0.

    ``(27.49 + 0.0) / 2`` is a fabricated price for a real fund holding. The
    row must keep the bid it genuinely saw AND refuse the mid, because
    discarding the bid would lose an observation and keeping the mid would
    invent one.
    """
    store.record(**_row(symbol="DBA", bid=27.49, ask=0.0, fill_price=28.38))
    r = store.rows()[0][0]
    assert r["bid"] == pytest.approx(27.49)
    assert r["ask"] == pytest.approx(0.0)
    assert r["mid"] is None
    assert r["effective_spread_bps"] is None
    assert r["quote_absent_reason"] == "one_sided_quote:ask_absent"


def test_a_caller_supplied_reason_drops_the_midpoint_it_disowns(store):
    """When the caller says the quote is unusable, believe the caller.

    A vendor timeout beside a stale cached bid/ask would otherwise store a
    perfectly-shaped mid computed from numbers the caller already declared
    untrustworthy.
    """
    store.record(**_row(quote_absent_reason="quote_fetch_failed:Timeout"))
    r = store.rows()[0][0]
    assert r["mid"] is None
    assert r["effective_spread_bps"] is None
    assert r["quote_absent_reason"] == "quote_fetch_failed:Timeout"
    # The observation itself is still kept.
    assert r["bid"] == pytest.approx(402.19)


def test_the_natural_key_makes_a_re_run_write_nothing(store):
    """APPEND-ONLY BY KEY. A capture restarted from an old checkpoint must not
    double the denominator of every coverage figure."""
    first = store.record(**_row())
    second = store.record(**_row())
    assert first["created"] is True
    assert second["created"] is False and second["quote_row_id"] is None
    assert store.count() == 1


def test_a_better_measurement_of_the_same_event_is_a_second_row(store):
    """The live pass sees IEX; the consolidated quote for the same instant
    arrives fifteen minutes later. Two bases, two rows, neither overwriting
    the other — a reader filters on basis rather than trusting that somebody
    replaced the worse one."""
    store.record(**_row(basis=eq.LIVE_BASIS, feed=eq.LIVE_FEED))
    store.record(**_row(basis=eq.RETRO_BASIS, feed=eq.RETRO_FEED))
    assert store.count() == 2
    assert store.count(basis=eq.LIVE_BASIS) == 1
    assert store.count(basis=eq.RETRO_BASIS) == 1
    live, _ = store.rows(basis=eq.LIVE_BASIS)
    assert [r["feed"] for r in live] == [eq.LIVE_FEED]


@pytest.mark.parametrize("bad", [
    dict(event_kind="proposed"), dict(basis="mark"), dict(feed="polygon"),
])
def test_record_refuses_an_out_of_vocabulary_value_before_the_database_does(
        store, bad):
    """Python refuses first with a message naming the vocabulary. The database
    refuses too (tested above); both exist because only one of them survives
    the next caller who reaches for a cursor."""
    with pytest.raises(ValueError):
        store.record(**_row(**bad))


# --- paging and the checkpoint read ---------------------------------------

def test_truncation_is_measured_not_inferred(store):
    """Fetch limit+1. ``len(rows) == limit`` cannot tell a full page from a
    cut one, and ``>=`` cries outage on a merely-full table."""
    for i in range(5):
        store.record(**_row(order_id=f"o{i}", event_seq=100 + i))
    rows, truncated = store.rows(limit=5)
    assert len(rows) == 5 and truncated is False
    rows, truncated = store.rows(limit=4)
    assert len(rows) == 4 and truncated is True
    assert store.count() == 5


def test_rows_come_back_newest_event_first(store):
    """The order the desk reads them in. Asserted rather than assumed: the
    ORDER BY is the only thing making 'newest first' true."""
    for seq in (100, 300, 200):
        store.record(**_row(order_id=f"o{seq}", event_seq=seq))
    rows, _ = store.rows()
    assert [r["event_seq"] for r in rows] == [300, 200, 100]


def test_max_event_seq_is_none_on_an_empty_store_not_zero(store):
    """None means 'nothing captured'. Zero would mean 'start from the
    beginning of the log', which is a different and much worse instruction."""
    assert store.max_event_seq() is None
    store.record(**_row(event_seq=742))
    assert store.max_event_seq() == 742
    assert store.max_event_seq(basis=eq.RETRO_BASIS) is None


def test_the_selected_columns_and_the_dict_keys_cannot_drift(store):
    """ROW_COLUMNS drives both the SELECT and the dict, so they are one
    structure rather than two that must be kept in step by hand."""
    store.record(**_row())
    r = store.rows()[0][0]
    assert tuple(r) == eq.ROW_COLUMNS


# --- the two cross-module agreements --------------------------------------

def test_this_module_and_tca_agree_on_which_venue_is_uninformative():
    """TWO COPIES OF ONE JUDGEMENT, PINNED BEHAVIOURALLY.

    ``app/fund/tca.py`` decides informativeness with its own string literal
    (``(self.venue or "") != "paper"``) inside a property, so the list cannot
    be derived from here. This test drives the REAL ``OrderCost`` on each venue
    and fails on whoever changes either module without the other — which is
    the only guard available when the second copy is a literal in a method.
    """
    from app.fund.tca import OrderCost
    def cost(venue):
        return OrderCost(
            order_id="o", symbol="SPY", side="buy", strategy_id=None, qty=1.0,
            decision_price=1.0, arrival_price=1.0, fill_price=1.0,
            notional_usd=1.0, fees_usd=0.0, approval_latency_s=None,
            submit_to_fill_s=None, total_bps=0.0, delay_bps=0.0,
            execution_bps=0.0, fees_bps=None, total_usd=0.0, has_split=True,
            proposed_ts=None, filled_ts=None, venue=venue,
            venue_declared=venue, venue_disputed=False)
    for venue in eq.SIMULATED_VENUES:
        assert cost(venue).informative is False, (
            f"tca calls {venue!r} informative; executionquality calls it "
            f"simulated. One of the two modules moved.")
        assert eq.execution_class(venue, True) == "simulated"
    assert cost("alpaca").informative is True
    assert eq.execution_class("alpaca", True) == "executed"


def test_the_capture_page_size_matches_the_endpoint_it_reads():
    """EVENTS_PAGE is a claim about somebody else's route.

    ``gap_below``'s whole arithmetic rests on knowing when a page came back
    FULL, and the page size is set by ``GET /fund/events``' own ``le``. Read it
    off the live route signature rather than restating it, so raising the cap
    there cannot leave a gap detector that never fires.
    """
    import inspect
    from execution import nbbo_capture
    from app.api.v1.fund import get_events
    limit = inspect.signature(get_events).parameters["limit"].default
    # fastapi 0.1xx keeps the bound in annotated-types metadata, not as an
    # attribute - measured, because `limit.le` is silently None on this
    # version and an assertion against None would have passed vacuously.
    caps = [m.le for m in getattr(limit, "metadata", []) if hasattr(m, "le")]
    assert len(caps) == 1, f"expected one upper bound on /fund/events, got {caps}"
    assert nbbo_capture.EVENTS_PAGE == caps[0], (
        f"the events endpoint caps at {caps[0]}; the capture loop requests "
        f"{nbbo_capture.EVENTS_PAGE}")


# --- the endpoint ---------------------------------------------------------

def test_the_endpoint_reports_an_unreadable_store_as_unreadable(monkeypatch):
    """Absence, never zero, and the three absences stay apart.

    With no quote store the endpoint must say ``readable: false`` with a
    reason, serve ``rows: null``, and STILL report the real fill count folded
    from the log — because "we cannot read the quotes" and "we have no fills"
    are different, and the second one is false.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.v1.fund as fundmod

    monkeypatch.setattr(fundmod, "_execution_quotes", lambda: None)
    body = TestClient(app).get("/api/v1/fund/execution/quality").json()
    assert body["readable"] is False
    assert body["rows"] is None
    assert body["summary"] is None
    assert isinstance(body["reason"], str) and body["reason"].strip()
    cov = body["coverage"]
    assert cov["readable"] is False
    assert cov["measured"] is None
    assert isinstance(cov["fill_events_total"], int)


def test_the_endpoint_serves_the_mark_table_beside_the_quote_table(monkeypatch):
    """Two bases, never merged. The mark table is computed from the log on
    every request and stored nowhere, so no reader can pick it up believing a
    quote was behind it."""
    from fastapi.testclient import TestClient
    from app.main import app
    import app.api.v1.fund as fundmod

    monkeypatch.setattr(fundmod, "_execution_quotes", lambda: None)
    body = TestClient(app).get("/api/v1/fund/execution/quality").json()
    retro = body["retro_mark_basis"]
    assert retro["basis"] == eq.MARK_BASIS
    assert retro["basis"] not in eq.BASES, (
        "the mark basis must not be a value the quote table can hold")
    for row in retro["rows"]:
        assert row["basis"] == eq.MARK_BASIS


def test_the_endpoint_route_is_registered_and_is_read_only():
    """The route exists at the path the desk will call, and it is GET only.

    Asserted against the SERVED OpenAPI document rather than ``app.routes``:
    the fund router is mounted, so ``app.routes`` holds nine top-level entries
    and none of the fund paths — a membership test there would have been
    vacuously false in one direction and is unable to be true in the other.

    A capture-only dispatch may add a read and nothing else, and this is what
    pins that: the new path serves GET and no verb that writes.
    """
    from app.main import app
    paths = app.openapi()["paths"]
    path = "/api/v1/fund/execution/quality"
    assert path in paths, f"route missing; nearest: {[p for p in paths if 'execution' in p]}"
    assert set(paths[path]) == {"get"}
