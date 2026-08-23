"""The desk engine's durable records — the rules the DATABASE has to hold.

These are the invariants a Python helper cannot guarantee, so they are
exercised against a real Postgres: at most ONE live supersession edge per
target (a partial unique index, not a check-then-insert race), a strike that
cannot be silent, a correction that cannot be empty.

**OWN DATABASE, AND THE REASON IS MEASURED.** ``krypton_fund_test`` is a
SINGLETON across concurrent pytest processes, and two builders may now run in
parallel by CEO decision. On 2026-08-23 (builder D21) a test failed on each of
three consecutive runs because ``tests/test_factory.py`` TRUNCATEs
``fund_candidates`` from BACKGROUND THREADS while another module reads it.
Every module here reads a WHOLE table (``edges()``, ``items()``,
``state()``), which is exactly the shape that loses that race — so it gets
``krypton_fund_deskenginetest`` and no other module touches it.

Skipped unless a Postgres is reachable, like every other store test here.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = "krypton_fund_deskenginetest"


def _dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


def _clean(cls):
    """A fresh table set per test, in this module's OWN database."""
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
    store = cls(dsn=_dsn())
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_desk_intray, fund_desk_intray_log, "
                        "fund_desk_supersession, fund_desk_briefing_review")
        c.commit()
    return store


@pytest.fixture
def tray():
    from app.fund.deskengine import InTray
    return _clean(InTray)


@pytest.fixture
def edges():
    from app.fund.deskengine import Supersessions
    return _clean(Supersessions)


@pytest.fixture
def shelf():
    from app.fund.deskengine import BriefingLedger
    return _clean(BriefingLedger)


# ---------------------------------------------------------------- in-tray --

def test_a_posted_ask_waits_in_the_tray_and_fires_nothing(tray):
    """IGNITION IS UNCHANGED. Filling a tray is an ASK; a human still dispatches."""
    tray.post(to_seat="quant", from_seat="pm", task="implement the survivor",
              why="R39 needs it before Monday")
    items = tray.items(seat="quant")
    assert len(items) == 1
    assert items[0]["status"] == "posted"
    assert items[0]["from_seat"] == "pm"
    assert tray.items(seat="builder") == []


def test_the_chair_blesses_the_tray_and_strikes_with_a_reason(tray):
    """The BINDS pattern applied to tasks: everything not struck is blessed."""
    a = tray.post(to_seat="quant", from_seat="pm", task="A")
    b = tray.post(to_seat="quant", from_seat="coo", task="B")
    out = tray.drain("quant", "cto", strike={b["item_id"]: "duplicates A"})
    assert [i["item_id"] for i in out["blessed"]] == [a["item_id"]]
    assert out["struck"][0]["reason"] == "duplicates A"
    assert {i["status"] for i in tray.items(seat="quant")} == {"blessed", "struck"}


def test_a_silent_strike_is_refused(tray):
    """To the sending seat, a strike with no reason reads exactly like an
    unread ask — which is the thing the in-tray exists to stop."""
    b = tray.post(to_seat="quant", from_seat="pm", task="B")
    with pytest.raises(ValueError, match="written reason"):
        tray.drain("quant", "cto", strike={b["item_id"]: "   "})
    assert tray.items(seat="quant")[0]["status"] == "posted"


def test_a_mistyped_strike_id_refuses_the_whole_drain(tray):
    """FAILURE DIRECTION. Ignoring an unknown id would BLESS the item the
    chair meant to remove, and the chair would never know."""
    tray.post(to_seat="quant", from_seat="pm", task="A")
    with pytest.raises(ValueError, match="cannot strike"):
        tray.drain("quant", "cto", strike={"not-an-id": "no"})
    assert tray.items(seat="quant")[0]["status"] == "posted"


def test_a_struck_item_returns_to_its_sender_exactly_once(tray):
    b = tray.post(to_seat="quant", from_seat="pm", task="B")
    tray.drain("quant", "cto", strike={b["item_id"]: "out of scope"})
    owed = tray.returns_for("pm")
    assert [i["item_id"] for i in owed] == [b["item_id"]]
    assert tray.acknowledge([b["item_id"]], "cto") == 1
    assert tray.returns_for("pm") == [], "a return must not repeat forever"


def test_a_blessed_item_is_never_owed_back(tray):
    a = tray.post(to_seat="quant", from_seat="pm", task="A")
    tray.drain("quant", "cto")
    assert tray.returns_for("pm") == []
    assert tray.acknowledge([a["item_id"]], "cto") == 0


def test_a_self_post_is_refused(tray):
    with pytest.raises(ValueError, match="self-post"):
        tray.post(to_seat="pm", from_seat="pm", task="think about it")


def test_a_blank_ask_is_refused(tray):
    with pytest.raises(ValueError, match="needs a task"):
        tray.post(to_seat="quant", from_seat="pm", task="   ")


def test_every_transition_is_logged_with_its_actor(tray):
    """The riskofficer audits the engine's writes; a current-state row cannot
    answer 'who struck this and when'."""
    b = tray.post(to_seat="quant", from_seat="pm", task="B")
    tray.drain("quant", "cto", strike={b["item_id"]: "no"})
    tray.acknowledge([b["item_id"]], "cto")
    log = tray.history(b["item_id"])
    assert [r["action"] for r in log] == ["posted", "struck", "returned"]
    assert log[1]["actor"] == "cto" and log[1]["reason"] == "no"


def test_an_unrecognised_status_filter_is_refused_by_the_store(tray):
    """The guard lives in the store, not only in the route, because a script
    reading the tray directly deserves the same refusal."""
    tray.post(to_seat="quant", from_seat="pm", task="A")
    assert len(tray.items(seat="quant", status="posted")) == 1
    with pytest.raises(ValueError, match="status must be one of"):
        tray.items(seat="quant", status="pending")


def test_draining_an_empty_tray_says_so_rather_than_reporting_nothing(tray):
    out = tray.drain("quant", "cto")
    assert out["blessed"] == [] and out["struck"] == []
    assert "empty" in out["note"] and "measured fact" in out["note"]


# ----------------------------------------------------------- supersession --

R37 = "rec:run-pm-0908#1"
R39 = "rec:run-pm-r39#1"


def test_the_r37_specimen_needs_its_named_event_and_its_revival_branch(edges):
    """docs/coo/TRIAGE7_2026-08-23.md decision 2, verbatim disposition:
    'Retire, don't clear: if Monday stops at the probe, R37's premise revives
    intact.' An edge recording only 'pending' loses BOTH halves."""
    with pytest.raises(ValueError, match="dies_at_event"):
        edges.add(target_ref=R37, superseder_ref=R39,
                  mode="superseded_pending", reason="premise dies Monday",
                  actor="cto", revives_if="R39 stops at the probe")
    with pytest.raises(ValueError, match="revives_if"):
        edges.add(target_ref=R37, superseder_ref=R39,
                  mode="superseded_pending", reason="premise dies Monday",
                  actor="cto", dies_at_event="R39 step 4 rebuy")
    got = edges.add(target_ref=R37, superseder_ref=R39,
                    mode="superseded_pending",
                    reason="broker-holds-zero premise dies at the rebuy",
                    actor="cto", dies_at_event="R39 step 4 rebuy TLT/DBC",
                    revives_if="R39 stops at the probe")
    assert got["mode"] == "superseded_pending"
    assert got["dies_at_event"] == "R39 step 4 rebuy TLT/DBC"


def test_at_most_one_live_edge_per_target(edges):
    """A partial unique index, not a check-then-insert: two chairs applying an
    edge in the same second is exactly the case a Python check loses, and two
    live edges would make the chip depend on read order."""
    edges.add(target_ref=R37, superseder_ref=R39, mode="superseded",
              reason="replaced", actor="cto")
    with pytest.raises(ValueError, match="already carries a live"):
        edges.add(target_ref=R37, superseder_ref="rec:run-z#1",
                  mode="killed", reason="also dead", actor="cto")


def test_retracting_restores_the_row_and_keeps_the_history(edges):
    """Recorded, never deleted. A row that silently reappears with no history
    is how the R37 pattern started."""
    e = edges.add(target_ref=R37, superseder_ref=R39, mode="superseded_pending",
                  reason="premise dies Monday", actor="cto",
                  dies_at_event="R39 step 4", revives_if="R39 stops at probe")
    with pytest.raises(ValueError, match="written reason"):
        edges.retract(e["edge_id"], "cto", "  ")
    back = edges.retract(e["edge_id"], "cto", "R39 stopped at the probe")
    assert back["retracted_at"] and back["retract_reason"]
    assert edges.by_target() == {}, "a retracted edge no longer blocks"
    assert len(edges.edges(include_retracted=True)) == 1
    # And the target can be superseded again later.
    edges.add(target_ref=R37, superseder_ref=R39, mode="superseded",
              reason="second time, for real", actor="cto")


def test_confirming_a_pending_edge_makes_it_a_plain_supersession(edges):
    e = edges.add(target_ref=R37, superseder_ref=R39, mode="superseded_pending",
                  reason="premise dies Monday", actor="cto",
                  dies_at_event="R39 step 4", revives_if="R39 stops at probe")
    done = edges.confirm(e["edge_id"], "cto", "rebuy filled 15:02Z")
    assert done["mode"] == "superseded"
    assert done["confirmed_by"] == "cto"
    with pytest.raises(ValueError, match="no future event left"):
        edges.confirm(e["edge_id"], "cto")


def test_confirming_a_retracted_edge_is_a_404_not_a_noop(edges):
    """'Confirm' on a dead row would read in the record as an event that
    occurred."""
    e = edges.add(target_ref=R37, superseder_ref=R39, mode="superseded",
                  reason="dead", actor="cto")
    edges.retract(e["edge_id"], "cto", "wrong row")
    with pytest.raises(KeyError):
        edges.confirm(e["edge_id"], "cto")


def test_a_killed_row_needs_no_superseder_and_everything_else_does(edges):
    """A row killed on its merits is not replaced by anything, and inventing a
    superseder to fill the column would fabricate a lineage."""
    edges.add(target_ref="rec:run-a#1", mode="killed",
              reason="killed by the adversary", actor="cto")
    with pytest.raises(ValueError, match="needs the row that supersedes"):
        edges.add(target_ref="rec:run-b#1", mode="superseded",
                  reason="replaced by something", actor="cto")


@pytest.mark.parametrize("bad", ["run-x#1", "rec:run-x", "", "nonsense"])
def test_an_unparseable_target_is_refused(edges, bad):
    """An edge against a target that cannot exist protects nothing while
    looking like it does."""
    with pytest.raises(ValueError, match="not a desk row reference"):
        edges.add(target_ref=bad, superseder_ref=R39, mode="superseded",
                  reason="r", actor="cto")


def test_a_row_cannot_supersede_itself(edges):
    with pytest.raises(ValueError, match="cannot supersede itself"):
        edges.add(target_ref=R37, superseder_ref=R37, mode="superseded",
                  reason="r", actor="cto")


def test_a_supersession_needs_its_written_reason(edges):
    with pytest.raises(ValueError, match="written reason"):
        edges.add(target_ref=R37, superseder_ref=R39, mode="superseded",
                  reason="   ", actor="cto")


# ------------------------------------- D24: the D22 kill repairs, at the DB --

@pytest.mark.parametrize("filed", [" req:{u}", "req:{u} ", "req:{u}\n",
                                   "req:{U}", "\treq:{u}"])
def test_an_edge_filed_WHITESPACED_OR_MISCASED_still_brakes_the_row(edges, filed):
    """ADVERSARY D22, attack E: validate-stripped / store-raw.

    `parse_ref` strips before matching, so every spelling here was ACCEPTED,
    listed on the page, and blocked nothing — the reader looks the row up as
    `req_ref(request_id)` and never matched the raw string. An edge that is
    visible and inert is worse than a refused one: everybody looking at the
    desk believes there is a brake.

    The case rows are UUIDs on purpose: RFC 4122 says a UUID's hex is
    case-insensitive, so `REQ-…` and `req-…` are the SAME request and storing
    them as two rows is the defect. A non-UUID id keeps its bytes — see the
    test below.
    """
    from app.fund.deskengine import approval_refusal, req_ref
    uid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    edges.add(target_ref=filed.format(u=uid, U=uid.upper()),
              superseder_ref=R39, mode="superseded",
              reason="R37's premise died at the rebuy", actor="cto")
    stored = edges.edges()[0]["target_ref"]
    assert stored == req_ref(uid), "the stored ref is the canonical one"
    assert approval_refusal(req_ref(uid), edges.by_target())


def test_a_NON_UUID_id_keeps_its_bytes_because_case_may_be_significant(edges):
    """The other direction, and the reason case is not lowercased blindly.

    A run id is a free-form string: `rec:Run-X#1` and `rec:run-x#1` may be two
    different runs, and merging them would make an edge brake the WRONG row —
    the one failure this table cannot afford. So canonicalisation normalises
    only what the identifier's own spec says is insignificant.
    """
    from app.fund.deskengine import approval_refusal, rec_ref
    edges.add(target_ref=" rec:Run-X#007 ", superseder_ref=R39,
              mode="superseded", reason="r", actor="cto")
    stored = edges.edges()[0]["target_ref"]
    assert stored == "rec:Run-X#7", "stripped and re-numbered, never re-cased"
    assert approval_refusal(rec_ref("Run-X", 7), edges.by_target())
    assert approval_refusal(rec_ref("run-x", 7), edges.by_target()) is None


def test_two_spellings_of_one_uuid_row_COLLIDE_on_the_live_index(edges):
    """Canonicalising on write is what makes the at-most-one-live-edge index
    mean anything: before it, `req:x` and ` req:x` were two rows, and the chip
    the desk rendered depended on read order."""
    uid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    edges.add(target_ref=f"req:{uid}", superseder_ref=R39, mode="superseded",
              reason="first", actor="cto")
    with pytest.raises(ValueError, match="already carries a live"):
        edges.add(target_ref=f"  req:{uid.upper()}\n", superseder_ref=R39,
                  mode="killed", reason="second", actor="cto")


def test_a_self_supersession_cannot_hide_behind_a_spelling(edges):
    """The identity check compares CANONICAL refs, so ` rec:run-a#1 ` cannot
    supersede `rec:run-a#1`. A row superseding itself is unapprovable for
    ever with no lineage to retract against."""
    with pytest.raises(ValueError, match="cannot supersede itself"):
        edges.add(target_ref="rec:run-a#1", superseder_ref=" rec:run-a#01 ",
                  mode="superseded", reason="r", actor="cto")


def test_rows_written_BEFORE_the_repair_are_migrated_on_construction(edges):
    """The other half of a canonicalisation fix, and shipping without it would
    leave whatever the table already holds inert for ever.

    Written through raw SQL because that is the only way a pre-repair row
    exists now: the writer refuses to make one.
    """
    import psycopg
    from app.fund.deskengine import Supersessions, approval_refusal, req_ref
    uid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO fund_desk_supersession "
                "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
                "VALUES (%s,%s,%s,'superseded','legacy row','cto')",
                ("legacy-1", f" req:{uid.upper()}\n", " rec:run-y#01 "))
            cur.execute(
                "INSERT INTO fund_desk_supersession "
                "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
                "VALUES (%s,%s,NULL,'killed','not a ref at all','cto')",
                ("legacy-2", "not-a-ref"))
        c.commit()
    assert approval_refusal(req_ref(uid), edges.by_target()) is None, (
        "precondition: the legacy row brakes nothing before the migration")

    # ON CONSTRUCTION, not by a script somebody remembers to run: the report
    # is what that construction did.
    report = Supersessions(dsn=_dsn()).migration_report
    assert report["rewritten"] == 1
    assert report["unparseable"] == ["legacy-2"], (
        "a ref that cannot be parsed is REPORTED, never guessed at")
    assert report["conflicts"] == []
    fixed = {e["edge_id"]: e for e in edges.edges()}
    assert fixed["legacy-1"]["target_ref"] == req_ref(uid)
    assert fixed["legacy-1"]["superseder_ref"] == "rec:run-y#1"
    assert fixed["legacy-2"]["target_ref"] == "not-a-ref", "left exactly as filed"
    assert approval_refusal(req_ref(uid), edges.by_target())
    # Idempotent: a second construction finds nothing left to do.
    assert Supersessions(dsn=_dsn()).migration_report["rewritten"] == 0


def test_a_migration_that_could_not_read_the_whole_table_SAYS_SO(edges, monkeypatch):
    """A partial migration that reports success is the silent-cap defect in a
    second costume. The scan is bounded because it runs inside a
    request-serving process; the bound is disclosed, not hidden."""
    from app.fund import deskengine as DE
    for i in range(3):
        edges.add(target_ref=f"req:row-{i}", superseder_ref=R39,
                  mode="superseded", reason="r", actor="cto")
    monkeypatch.setattr(DE, "MIGRATION_SCAN_LIMIT", 2)
    report = DE.Supersessions(dsn=_dsn()).migration_report
    assert report["truncated"] is True and report["scanned"] == 2


def test_a_migration_collision_is_REPORTED_and_neither_row_is_lost(edges):
    """Two spellings of one row cannot be merged by a migration: which edge
    survives is a decision with a written reason. So the collision is counted
    and both rows stay."""
    import psycopg
    from app.fund.deskengine import Supersessions
    uid = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
    edges.add(target_ref=f"req:{uid}", superseder_ref=R39, mode="superseded",
              reason="the canonical one", actor="cto")
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute(
                "INSERT INTO fund_desk_supersession "
                "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
                "VALUES (%s,%s,%s,'killed','the raw one','cto')",
                ("legacy-dup", f" req:{uid.upper()} ", None))
        c.commit()
    report = Supersessions(dsn=_dsn()).migration_report
    assert report["rewritten"] == 0
    assert [c["edge_id"] for c in report["conflicts"]] == ["legacy-dup"]
    assert len(edges.edges()) == 2, "nothing is deleted by a migration"


def test_a_FLOOD_makes_the_brake_UNREADABLE_and_never_absent(edges):
    """ADVERSARY D22, attack A, executed: at 1,001 edges the R37 specimen's
    brake vanished from `by_target()` while the store reported healthy, and
    the row it protected became approvable.

    A control's backing query may not silently cap. Past the limit this raises
    — and `_edges_by_target` reads any exception as UNREADABLE, which is the
    disclosed fail-open leg, not a silent one.
    """
    import psycopg
    import uuid as _uuid
    from app.fund.deskengine import (EDGE_QUERY_LIMIT, SupersessionsTruncated,
                                     approval_refusal)
    edges.add(target_ref=R37, superseder_ref=R39, mode="superseded_pending",
              reason="premise dies at the rebuy", actor="cto",
              dies_at_event="R39 step 4", revives_if="the probe stops")
    assert approval_refusal(R37, edges.by_target()), "the brake exists"
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.executemany(
                "INSERT INTO fund_desk_supersession "
                "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
                "VALUES (%s,%s,NULL,'killed','noise','anyone')",
                [(str(_uuid.uuid4()), f"req:noise-{i}")
                 for i in range(EDGE_QUERY_LIMIT)])
        c.commit()
    with pytest.raises(SupersessionsTruncated):
        edges.by_target()
    # The DISPLAY path still answers, and says what it is missing — with the
    # true total beside the page, measured rather than implied.
    rows, truncated = edges.page()
    assert truncated is True and len(rows) == EDGE_QUERY_LIMIT
    assert edges.count() == EDGE_QUERY_LIMIT + 1


def test_EXACTLY_the_limit_is_a_complete_answer_not_a_truncated_one(edges):
    """Fetching limit+1 is what makes this distinguishable. A store that
    counted `len(rows) == limit` as truncation would cry outage on a table
    that is merely full, and the disclosed fail-open would fire for ever."""
    import psycopg
    import uuid as _uuid
    from app.fund.deskengine import EDGE_QUERY_LIMIT
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.executemany(
                "INSERT INTO fund_desk_supersession "
                "(edge_id,target_ref,superseder_ref,mode,reason,applied_by) "
                "VALUES (%s,%s,NULL,'killed','noise','anyone')",
                [(str(_uuid.uuid4()), f"req:noise-{i}")
                 for i in range(EDGE_QUERY_LIMIT)])
        c.commit()
    rows, truncated = edges.page()
    assert len(rows) == EDGE_QUERY_LIMIT and truncated is False
    assert len(edges.by_target()) == EDGE_QUERY_LIMIT


def test_the_limit_is_READ_rather_than_hardcoded_in_the_query(edges, monkeypatch):
    """MOVE it (D16/D21): with the limit moved to 3, four edges must truncate.
    An assertion at 1,000 cannot tell a read from a literal in the SQL."""
    from app.fund import deskengine as DE
    for i in range(4):
        edges.add(target_ref=f"req:row-{i}", superseder_ref=R39,
                  mode="superseded", reason="r", actor="cto")
    monkeypatch.setattr(DE, "EDGE_QUERY_LIMIT", 3)
    with pytest.raises(DE.SupersessionsTruncated):
        edges.by_target()
    monkeypatch.setattr(DE, "EDGE_QUERY_LIMIT", 4)
    assert len(edges.by_target()) == 4


def test_the_live_edge_map_feeds_the_refusal(edges):
    """End to end: the stored edge is what `approval_refusal` reads."""
    from app.fund.deskengine import approval_refusal
    edges.add(target_ref=R37, superseder_ref=R39, mode="superseded_pending",
              reason="broker-holds-zero premise dies at the rebuy", actor="cto",
              dies_at_event="R39 step 4 rebuy TLT/DBC",
              revives_if="R39 stops at the probe")
    refusal = approval_refusal(R37, edges.by_target())
    assert refusal["refused"] is True
    assert "R39 step 4 rebuy TLT/DBC" in refusal["detail"]
    assert approval_refusal(R39, edges.by_target()) is None


# ------------------------------------------------------- briefing ledger ---

def test_verifying_flips_the_badge_and_a_correction_is_a_new_row(shelf):
    """Findings-doc rules apply to the shelf: a memo is never edited."""
    p = "docs/coo/TRIAGE7_2026-08-23.md"
    assert shelf.state() == {}
    shelf.record(path=p, action="verified", actor="cto", note="spot-checked 3 figures")
    shelf.record(path=p, action="correction", actor="cto",
                 note="the $501.58 figure predates the 08-23 mark")
    st = shelf.state()
    assert st[p]["verified_by"] == "cto"
    assert st[p]["verification_note"] == "spot-checked 3 figures"
    assert len(st[p]["corrections"]) == 1


def test_an_empty_correction_is_refused(shelf):
    """A blank chip warns a reader about nothing and trains them to ignore
    the next one."""
    with pytest.raises(ValueError, match="needs its text"):
        shelf.record(path="docs/x.md", action="correction", actor="cto")


def test_an_unknown_review_action_is_refused(shelf):
    with pytest.raises(ValueError, match="action must be one of"):
        shelf.record(path="docs/x.md", action="approved", actor="cto")


def test_windows_paths_are_normalised_so_the_badge_finds_its_memo(shelf):
    """The shelf keys on the path the fold produces, which uses forward
    slashes on every platform. A badge stored under a backslash path would
    silently never match."""
    shelf.record(path="docs\\coo\\TRIAGE7_2026-08-23.md", action="verified",
                 actor="cto")
    assert "docs/coo/TRIAGE7_2026-08-23.md" in shelf.state()
