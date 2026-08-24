"""THE AGENT->CTO->AGENT HOP — slice 4 of the ticket highway.

THE ONE INVARIANT THIS FILE EXISTS FOR: **staging appends nothing.** Seats have
never had a pen and this slice must not hand them one by accident. Two tests
assert it by AST rather than by reading the diff — ``ticketstaging`` must not
import the event store, and no function in it may call ``append``.

The rest defends the grammar and the console:

  * **An absent block is not zero proposals.** ``block_present`` false means
    the producer has not adopted the format; true with no proposals means it
    had nothing to file. Failure #6 in the design's table is that structured
    filing sits at 0 of 116, and collapsing these two makes that number
    unreadable.
  * **Nothing the parser cannot read is dropped.** A silently discarded line
    converts a producer's mistake into a fact nobody can find.
  * **A strike is a record, not a removal.**
  * **The console is not a back door.** An accepted row takes the ordinary
    door with every guard on it — including the per-target approval echo.

Postgres tests live in their OWN database (``krypton_fund_ticketstagingtest``)
for the reason ``test_desk_engine_store.py`` states: ``krypton_fund_test`` is a
singleton across concurrent pytest processes and two builders may run in
parallel.
"""

from __future__ import annotations

import ast
import os
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.fund import ticketstaging


# ============================================================================
# THE BOUNDARY
# ============================================================================

SRC = pathlib.Path(ticketstaging.__file__)


class TestStagingAppendsNothing:
    """The structural half of 'seats gain no pen'."""

    def test_the_module_does_not_import_the_event_store(self):
        """AST, with an EXACT name set and a positive control.

        A substring check would be vacuous in both directions: ``"import
        Event" in src`` matches ``import EventType``, and a name set that is
        empty by accident passes everything. The control below proves the
        walker actually finds imports.
        """
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add(node.module or "")
                imported |= {f"{node.module}.{a.name}" for a in node.names}
        assert "app.fund.events" not in imported
        assert not any(n.startswith("app.fund.events") for n in imported)
        # POSITIVE CONTROL: the walker sees SOMETHING, so an empty set cannot
        # make this guard pass by finding nothing at all.
        assert "app.fund.pgstore.dsn" in imported or "app.fund.pgstore" in imported

    def test_the_module_never_names_an_event_or_a_store(self):
        """The sharper form, and the first one I wrote was WRONG.

        ``"append" not in calls`` failed on ``out.append(...)`` — a Python
        list. Banning the word ``append`` bans list-building, which is not the
        invariant; the invariant is that this module cannot reach the log. You
        cannot append to the event log without naming ``Event`` and a store, so
        those are what is banned, with a positive control so an empty walk
        cannot pass.
        """
        tree = ast.parse(SRC.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree)
                  if isinstance(n, ast.Attribute)}
        for banned in ("Event", "EventType", "EventStore", "_store", "store"):
            assert banned not in names, f"{banned} is named in {SRC.name}"
        # POSITIVE CONTROL: the walker sees the names that ARE there.
        assert {"execute", "cursor", "commit"} <= names

    def test_only_the_sql_verbs_this_table_is_allowed_are_present(self):
        """NOTHING HERE EVER DELETEs. A struck proposal that leaves no row is
        indistinguishable from one nobody read."""
        src = SRC.read_text(encoding="utf-8").upper()
        assert "DELETE FROM" not in src
        assert "DROP TABLE" not in src


# ============================================================================
# THE GRAMMAR
# ============================================================================

class TestTheBlockIsFoundOrHonestlyAbsent:
    def test_no_block_is_not_zero_proposals(self):
        p = ticketstaging.parse_tickets_block("## STATE\nsome prose\n")
        assert p["block_present"] is False and p["proposals"] == []

    def test_an_empty_block_is_present_and_empty(self):
        p = ticketstaging.parse_tickets_block("## TICKETS\n\n## STATE\nx\n")
        assert p["block_present"] is True and p["proposals"] == []

    def test_no_text_at_all_is_UNKNOWN_not_absent(self):
        """None means we could not look. Absence is never zero and 'we did not
        read the run' is not 'the seat filed nothing'."""
        p = ticketstaging.parse_tickets_block(None)
        assert p["block_present"] is False
        assert "UNKNOWN" in p["note"]

    @pytest.mark.parametrize("heading", ["## TICKETS", "### Tickets",
                                         "#tickets", "##   tickets   "])
    def test_the_heading_is_read_forgivingly(self, heading):
        """A producer who typed '### Tickets' has done the thing we asked."""
        p = ticketstaging.parse_tickets_block(f"{heading}\n- close: abc | citation: x\n")
        assert p["block_present"] is True and len(p["proposals"]) == 1

    def test_the_block_ends_at_the_next_heading(self):
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- close: abc | citation: x\n\n"
            "## STATE\n- close: def | citation: y\n")
        assert [x["ticket_id"] for x in p["proposals"]] == ["abc"]


class TestTheProposals:
    def test_a_transition_with_an_arrow(self):
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- transition: a4f2 -> done | citation: docs/x.md\n")
        got = p["proposals"][0]
        assert got["kind"] == "transition"
        assert got["ticket_id"] == "a4f2" and got["to_state"] == "done"
        assert got["fields"]["citation"] == "docs/x.md"

    @pytest.mark.parametrize("verb,state", [("close", "done"),
                                            ("decline", "declined"),
                                            ("merge", "merged")])
    def test_the_three_aliases(self, verb, state):
        p = ticketstaging.parse_tickets_block(
            f"## TICKETS\n- {verb}: a4f2 | reason: r | citation: c "
            "| decision_ref: d\n")
        assert p["proposals"][0]["to_state"] == state

    def test_the_alias_table_is_read_not_restated(self, monkeypatch):
        """MOVE THE VALUE. Adding an alias must change the parse."""
        assert ticketstaging.parse_tickets_block(
            "## TICKETS\n- bury: a4f2\n")["proposals"] == []
        monkeypatch.setitem(ticketstaging._ALIASES, "bury", "expired")
        p = ticketstaging.parse_tickets_block("## TICKETS\n- bury: a4f2\n")
        assert p["proposals"][0]["to_state"] == "expired"

    def test_an_open_proposal(self):
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- open: ask | for: quant | subject: implement the "
            "survivor | next_actor: chair | due: 2026-08-25\n")
        got = p["proposals"][0]
        assert got["kind"] == "open" and got["ticket_id"] is None
        assert got["fields"]["type"] == "ask"
        assert got["fields"]["for"] == "quant"
        assert got["fields"]["subject"] == "implement the survivor"
        assert got["fields"]["due"] == "2026-08-25"

    def test_a_proposal_may_wrap(self):
        """A grammar that punished wrapping would be a grammar nobody uses."""
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- open: ask | for: quant\n  | subject: the survivor\n")
        assert p["proposals"][0]["fields"]["subject"] == "the survivor"

    def test_the_raw_line_is_kept_on_every_proposal(self):
        p = ticketstaging.parse_tickets_block("## TICKETS\n- close: a4f2\n")
        assert "close: a4f2" in p["proposals"][0]["raw"]


class TestNothingIsSilentlyDropped:
    @pytest.mark.parametrize("line,why_fragment", [
        ("- sandwich: a4f2", "unknown verb"),
        ("- transition: a4f2", "needs '<ticket_id> -> <state>'"),
        ("- open:", "needs a ticket type"),
    ])
    def test_an_unreadable_line_is_returned_not_dropped(self, line,
                                                        why_fragment):
        p = ticketstaging.parse_tickets_block(f"## TICKETS\n{line}\n")
        assert p["proposals"] == []
        assert len(p["unparsed"]) == 1
        # SHARED-WORD AUDIT: each fragment is reachable only by its own branch.
        assert why_fragment in p["unparsed"][0]["why"]

    def test_a_fragment_with_no_key_is_kept_not_discarded(self):
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- close: a4f2 | this has no colon | citation: c\n")
        got = p["proposals"][0]
        assert got["fields"]["_extra"] == ["this has no colon"]
        assert got["fields"]["citation"] == "c"

    def test_good_and_bad_lines_coexist(self):
        p = ticketstaging.parse_tickets_block(
            "## TICKETS\n- close: a4f2 | citation: c\n- sandwich: b\n")
        assert len(p["proposals"]) == 1 and len(p["unparsed"]) == 1


# ============================================================================
# THE TABLE (Postgres)
# ============================================================================

pgmark = pytest.mark.skipif(os.getenv("SKIP_PG_TESTS") == "1",
                            reason="Postgres tests disabled")

TEST_DB = "krypton_fund_ticketstagingtest"


def _dsn() -> str:
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    return f"{head}/{TEST_DB}"


@pytest.fixture()
def table():
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
    st = ticketstaging.StagedTickets(dsn=_dsn())
    with psycopg.connect(_dsn()) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_ticket_staged")
        c.commit()
    return st


def _one(kind="transition", **kw):
    base = {"kind": kind, "ticket_id": "a4f2", "to_state": "done",
            "fields": {"citation": "docs/x.md"}, "raw": "- close: a4f2"}
    base.update(kw)
    return base


@pgmark
class TestTheStagingTable:
    def test_a_staged_row_round_trips(self, table):
        rows = table.stage([_one()], run_id="run-x", seat="builder")
        got = table.get(rows[0]["staged_id"])
        assert got["status"] == "staged" and got["ticket_id"] == "a4f2"
        assert got["fields"]["citation"] == "docs/x.md"

    def test_an_unknown_kind_is_refused_not_stored(self, table):
        with pytest.raises(ValueError):
            table.stage([_one(kind="sandwich")], run_id=None, seat=None)
        assert table.counts()["staged"] == 0

    def test_a_strike_is_recorded_never_removed(self, table):
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        table.resolve(sid, verdict="struck", actor="cto", reason="disagree")
        got = table.get(sid)
        assert got is not None
        assert got["status"] == "struck"
        assert got["resolution_reason"] == "disagree"

    def test_a_strike_needs_its_written_reason(self, table):
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        with pytest.raises(ValueError):
            table.resolve(sid, verdict="struck", actor="cto")

    def test_an_acceptance_does_not(self, table):
        """Asymmetric ON PURPOSE: agreeing with a proposal adds nothing that
        the proposal does not already say. Disagreeing does."""
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        assert table.resolve(sid, verdict="accepted", actor="cto") is not None

    def test_a_second_resolve_is_refused_in_the_database(self, table):
        """Not in a check-then-write. Two chair sessions clicking the same
        batch would otherwise both append an event."""
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        assert table.resolve(sid, verdict="accepted", actor="cto") is not None
        assert table.resolve(sid, verdict="accepted", actor="cto") is None

    def test_an_unknown_staged_id_returns_None_not_an_empty_dict(self, table):
        assert table.resolve("nope", verdict="accepted", actor="cto") is None

    def test_counts_seed_every_status(self, table):
        assert set(table.counts()) == set(ticketstaging.STAGED_STATUSES)
        assert table.counts()["struck"] == 0

    def test_attach_event_records_what_the_append_produced(self, table):
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        table.resolve(sid, verdict="accepted", actor="cto")
        table.attach_event(sid, event_ref="T-1")
        assert table.get(sid)["event_ref"] == "T-1"

    def test_a_bad_verdict_is_refused(self, table):
        sid = table.stage([_one()], run_id=None, seat=None)[0]["staged_id"]
        with pytest.raises(ValueError):
            table.resolve(sid, verdict="maybe", actor="cto")


# ============================================================================
# THE CONSOLE
# ============================================================================

class _WriteStore:
    def __init__(self):
        self.events, self.appended = [], []

    def append(self, e):
        self.appended.append(e)
        self.events.append({"type": e.type, "payload": e.payload})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


@pytest.fixture()
def console(monkeypatch, table):
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    store = _WriteStore()
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
    monkeypatch.setattr(fundapi, "_stagedstore", lambda: table)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store, c.table = store, table
    return c


@pgmark
class TestTheConsole:
    def test_staging_a_block_writes_rows_and_no_events(self, console):
        r = console.post("/api/v1/fund/tickets/staged",
                         json={"text": "## TICKETS\n- open: ask | for: quant "
                                       "| subject: implement the survivor\n",
                               "run_id": "run-pm-1", "seat": "pm"})
        assert r.status_code == 200, r.text
        assert r.json()["stored"] is True and len(r.json()["staged"]) == 1
        # THE WHOLE POINT: nothing reached the log.
        assert console.store.appended == []

    def test_a_dry_run_writes_nothing_at_all(self, console):
        r = console.post("/api/v1/fund/tickets/staged",
                         json={"text": "## TICKETS\n- open: ask | subject: s\n",
                               "dry_run": True})
        assert r.json()["stored"] is False
        assert console.table.counts()["staged"] == 0

    def test_an_accepted_open_becomes_exactly_one_TicketOpened(self, console):
        sid = console.post("/api/v1/fund/tickets/staged",
                           json={"text": "## TICKETS\n- open: ask | for: quant"
                                         " | subject: implement the survivor\n",
                                 "seat": "pm"}).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": sid,
                                              "verdict": "accept"}]})
        assert r.status_code == 200, r.text
        assert len(r.json()["applied"]) == 1
        opened = [e for e in console.store.appended
                  if getattr(e.type, "value", e.type) == "TicketOpened"]
        assert len(opened) == 1
        assert opened[0].payload["subject"] == "implement the survivor"
        assert opened[0].payload["filed_for"] == "quant"

    def test_a_struck_proposal_leaves_a_struck_record_and_no_event(self, console):
        sid = console.post("/api/v1/fund/tickets/staged",
                           json={"text": "## TICKETS\n- open: ask | subject: s\n"}
                           ).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": sid,
                                              "verdict": "strike",
                                              "reason": "the chair disagrees"}]})
        assert r.json()["struck"] == [{"staged_id": sid,
                                       "reason": "the chair disagrees"}]
        assert console.table.get(sid)["status"] == "struck"
        assert console.store.appended == []

    def test_a_strike_without_a_reason_is_refused(self, console):
        sid = console.post("/api/v1/fund/tickets/staged",
                           json={"text": "## TICKETS\n- open: ask | subject: s\n"}
                           ).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": sid,
                                              "verdict": "strike"}]})
        assert r.status_code == 422

    def test_the_console_is_not_a_back_door_around_the_approval_echo(self,
                                                                    console):
        """A DECISION transition staged by a seat still takes the per-target
        echo. Without it the row is REFUSED — by the ordinary door, not by a
        second copy of the guard living here."""
        opened = console.post("/api/v1/fund/tickets",
                              json={"type": "ask", "subject": "s"}).json()
        tid = opened["ticket_id"]
        sid = console.post(
            "/api/v1/fund/tickets/staged",
            json={"text": f"## TICKETS\n- transition: {tid} -> accepted\n"}
        ).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": sid,
                                              "verdict": "accept"}],
                               "actor": "ceo"})
        refused = r.json()["refused"]
        assert len(refused) == 1 and refused[0]["status"] == 403
        assert "accepted_without_event" in refused[0]["state"]
        assert console.table.get(sid)["event_ref"] is None

    def test_a_decision_row_with_its_echo_lands(self, console):
        tid = console.post("/api/v1/fund/tickets",
                           json={"type": "ask", "subject": "s"}
                           ).json()["ticket_id"]
        sid = console.post(
            "/api/v1/fund/tickets/staged",
            json={"text": f"## TICKETS\n- transition: {tid} -> accepted\n"}
        ).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": sid,
                                              "verdict": "accept",
                                              "confirm": tid[:8]}],
                               "actor": "ceo"})
        assert r.json()["applied"], r.text
        assert console.table.get(sid)["event_ref"] == tid

    def test_a_missing_staged_id_is_its_own_outcome(self, console):
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [{"staged_id": "nope",
                                              "verdict": "accept"}]})
        assert r.json()["missing"] and not r.json()["applied"]

    def test_partial_failure_is_reported_per_row(self, console):
        good = console.post("/api/v1/fund/tickets/staged",
                            json={"text": "## TICKETS\n- open: ask | subject: g\n"}
                            ).json()["staged"][0]["staged_id"]
        r = console.post("/api/v1/fund/tickets/staged/resolve",
                         json={"decisions": [
                             {"staged_id": good, "verdict": "accept"},
                             {"staged_id": "nope", "verdict": "accept"}]})
        b = r.json()
        assert len(b["applied"]) == 1 and len(b["missing"]) == 1

    def test_the_staged_view_refuses_an_unknown_status_filter(self, console):
        r = console.get("/api/v1/fund/tickets/staged?status=dine")
        assert r.status_code == 422
        assert r.json()["detail"]["allowed"] == list(
            ticketstaging.STAGED_STATUSES)

    @pytest.mark.parametrize("limit,ok", [
        (0, False),      # below `ge=1` — REFUSED by FastAPI's own validation
        (1, True),       # the floor itself — ACCEPTED
        (5000, True),    # the ceiling itself — ACCEPTED
        (5001, False),   # one above `le=5000` — REFUSED
    ])
    def test_the_limit_boundary(self, console, limit, ok):
        """THE GAUNTLET'S 5e: `Query(500, ge=1, le=5000)` was entirely
        unexercised on this endpoint. Probed AT both edges."""
        r = console.get(f"/api/v1/fund/tickets/staged?limit={limit}")
        assert r.status_code == (200 if ok else 422)

    def test_a_page_cap_does_not_shrink_the_counts(self, console):
        """The counts are a census over the whole table; the list is a page."""
        for _ in range(3):
            console.post("/api/v1/fund/tickets/staged",
                         json={"text": "## TICKETS\n- open: ask | subject: s\n"})
        b = console.get("/api/v1/fund/tickets/staged?limit=1").json()
        assert b["shown"] == 1
        assert b["counts"]["staged"] == 3

    def test_the_staged_view_serves_the_queue_with_its_counts(self, console):
        console.post("/api/v1/fund/tickets/staged",
                     json={"text": "## TICKETS\n- open: ask | subject: s\n"})
        b = console.get("/api/v1/fund/tickets/staged").json()
        assert b["readable"] is True and b["counts"]["staged"] == 1


class TestTheConsoleOffPostgres:
    """`null` is not `[]`. A process with no staging table must say so."""

    @pytest.fixture()
    def dead(self, monkeypatch):
        from fastapi import FastAPI

        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_store", _WriteStore())
        monkeypatch.setattr(fundapi, "_stagedstore", lambda: None)
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        return TestClient(app)

    def test_the_queue_is_UNKNOWN_not_empty(self, dead):
        b = dead.get("/api/v1/fund/tickets/staged").json()
        assert b["readable"] is False and b["staged"] is None

    def test_staging_parses_and_says_it_did_not_store(self, dead):
        b = dead.post("/api/v1/fund/tickets/staged",
                      json={"text": "## TICKETS\n- open: ask | subject: s\n"}).json()
        assert b["stored"] is False and b["staged"] is None
        assert len(b["proposals"]) == 1

    def test_resolving_is_503_not_a_200_reporting_success(self, dead):
        r = dead.post("/api/v1/fund/tickets/staged/resolve",
                      json={"decisions": []})
        assert r.status_code == 503
