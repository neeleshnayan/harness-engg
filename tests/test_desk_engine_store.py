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
