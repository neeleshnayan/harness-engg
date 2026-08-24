"""LESSONS WITH RECEIPTS — slice 5 of the ticket highway.

Failure #8 in the design's own table: *"BINDS carried by hand"*. The
constitution has specified the CONTENT of a ``## BINDS`` entry since
2026-08-21 — *"named seats, and for each one the lesson written as an
instruction to THAT seat"* — and specified nothing about the carrier, because
the carrier was a chair reading a report and remembering. The measured
consequence is in the constitution's own text: the quant's least-capacious-leg
finding *"sat in quant.md, a file the mechanism never reads, until a chair
noticed and carried it across by hand"*.

THE FALSIFIER, WRITTEN BY THE DESIGN AND EXECUTED HERE: *"a filed lesson
reaches the receiving seat's dispatch without a receipt, or a lesson silently
vanishes"*. Both halves have tests. The second is the one worth naming:
``TestAnUnconsumedLessonAges`` asserts that a never-consumed lesson is never
filtered out, sorts to the TOP of the board, and reports its lag as null with
a stated basis — never as zero, which would read as instant delivery.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.fund import ticketstaging


BINDS = """## BINDS

- **quant** — capacity is bounded by your least capacious leg, so name the leg
  you believe binds.
- **mechanism, analyst**: before presenting a derived constant as read from the
  world, substitute two inputs and confirm the output can move.

## EVOLVE
- **pm** — this one is in a different section and must not be read.
"""


class _WriteStore:
    def __init__(self):
        self.events, self.appended = [], []

    def append(self, e):
        self.appended.append(e)
        self.events.append({"type": e.type, "payload": e.payload})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


# ============================================================================
# THE GRAMMAR
# ============================================================================

class TestTheBindsGrammar:
    def test_one_lesson_per_receiving_seat_not_per_entry(self):
        """An entry naming two seats is TWO obligations.

        The analyst consuming it says nothing about whether the mechanism ever
        did, and one row would go ``done`` on the first receipt and take the
        second seat's lesson with it.
        """
        p = ticketstaging.parse_binds_block(BINDS)
        assert p["block_present"] is True
        assert sorted(x["seat"] for x in p["lessons"]) == [
            "analyst", "mechanism", "quant"]

    def test_the_lesson_text_survives_its_own_punctuation(self):
        """Split on the FIRST separator only. A lesson routinely contains
        colons and dashes; splitting on all of them would truncate every
        instruction after its first clause."""
        p = ticketstaging.parse_binds_block(
            "## BINDS\n- quant — name the leg: the one that binds — and say so\n")
        assert p["lessons"][0]["lesson"] == "name the leg: the one that binds — and say so"

    @pytest.mark.parametrize("sep", ["—", "–", ":", " - "])
    def test_all_four_separators_the_firm_already_writes(self, sep):
        p = ticketstaging.parse_binds_block(f"## BINDS\n- quant{sep}do the thing\n")
        assert p["lessons"] == [{"seat": "quant", "lesson": "do the thing",
                                 "raw": p["lessons"][0]["raw"]}]

    def test_the_block_ends_at_the_next_heading(self):
        p = ticketstaging.parse_binds_block(BINDS)
        assert "pm" not in {x["seat"] for x in p["lessons"]}

    def test_an_absent_block_is_not_zero_lessons(self):
        p = ticketstaging.parse_binds_block("## STATE\nprose\n")
        assert p["block_present"] is False and p["lessons"] == []

    def test_no_text_at_all_is_UNKNOWN(self):
        p = ticketstaging.parse_binds_block(None)
        assert "UNKNOWN" in p["note"]

    def test_an_unrecognised_seat_is_reported_never_silently_addressed(self):
        """A lesson filed for ``buidler`` is a lesson nobody receives."""
        p = ticketstaging.parse_binds_block("## BINDS\n- buidler — a lesson\n")
        assert p["lessons"] == []
        assert "unrecognised seat name" in p["unparsed"][0]["why"]

    def test_an_entry_with_no_separator_is_reported_not_dropped(self):
        p = ticketstaging.parse_binds_block("## BINDS\n- quant does things\n")
        assert p["lessons"] == []
        assert "no separator" in p["unparsed"][0]["why"]

    def test_a_mixed_entry_files_the_known_seat_and_reports_the_other(self):
        p = ticketstaging.parse_binds_block("## BINDS\n- quant, buidler — x\n")
        assert [x["seat"] for x in p["lessons"]] == ["quant"]
        assert len(p["unparsed"]) == 1

    def test_the_roster_is_READ_from_desk_not_copied(self, monkeypatch):
        """MOVE THE VALUE. A seat removed from the bench must stop being
        addressable — a second list here would let this parser file for a seat
        that no longer exists."""
        assert ticketstaging.parse_binds_block(
            "## BINDS\n- quant — x\n")["lessons"]
        from app.fund import desk
        monkeypatch.setattr(desk, "ROSTER",
                            [r for r in desk.ROSTER if r["agent"] != "quant"])
        p = ticketstaging.parse_binds_block("## BINDS\n- quant — x\n")
        assert p["lessons"] == [] and len(p["unparsed"]) == 1


class TestLessonsBecomeOrdinaryProposals:
    def test_no_second_write_path(self):
        """A lesson becomes a ticket exactly the way every other proposal does.

        A BINDS endpoint that minted lesson tickets directly would be a door
        with its own copy of the type check, the subject check and the routing
        vocabulary.
        """
        p = ticketstaging.parse_binds_block("## BINDS\n- quant — name the leg\n")
        props = ticketstaging.lessons_as_proposals(p["lessons"],
                                                   from_seat="builder")
        assert props[0]["kind"] == "open"
        assert props[0]["fields"]["type"] == "lesson"
        assert props[0]["fields"]["for"] == "quant"
        assert props[0]["fields"]["subject"] == "name the leg"
        assert props[0]["fields"]["from_seat"] == "builder"

    def test_a_lesson_is_the_receiving_seats_move_declared_not_inferred(self):
        p = ticketstaging.parse_binds_block("## BINDS\n- quant — x\n")
        props = ticketstaging.lessons_as_proposals(p["lessons"])
        assert props[0]["fields"]["next_actor"] == "seat"


# ============================================================================
# THE RECEIPTS
# ============================================================================

@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    store = _WriteStore()
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
    monkeypatch.setattr(fundapi, "_stagedstore", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store = store
    return c


def _lesson(client, seat="quant", subject="name the leg you believe binds"):
    r = client.post("/api/v1/fund/tickets",
                    json={"type": "lesson", "subject": subject,
                          "filed_for": seat, "next_actor": "seat"})
    assert r.status_code == 200, r.text
    return r.json()["ticket_id"]


class TestTheConsumptionReceipt:
    def test_it_names_the_dispatch_that_carried_the_lesson(self, client):
        tid = _lesson(client)
        r = client.post(f"/api/v1/fund/tickets/{tid}/consumed",
                        json={"consumed_by_dispatch": "run-quant-d5"})
        assert r.status_code == 200, r.text
        assert r.json()["consumed_by_dispatch"] == "run-quant-d5"
        # The seat is inherited from the ticket when the caller omits it.
        assert r.json()["seat"] == "quant"

    def test_a_receipt_that_names_no_dispatch_is_refused(self, client):
        tid = _lesson(client)
        r = client.post(f"/api/v1/fund/tickets/{tid}/consumed",
                        json={"consumed_by_dispatch": "  "})
        assert r.status_code == 422
        assert "which brief carried it" in r.json()["detail"]

    def test_an_unknown_ticket_is_404(self, client):
        r = client.post("/api/v1/fund/tickets/nope/consumed",
                        json={"consumed_by_dispatch": "run-x"})
        assert r.status_code == 404

    def test_a_receipt_on_a_non_lesson_is_refused(self, client):
        """Consumption lag must keep meaning what its name says."""
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "ask", "subject": "an ask"})
        tid = r.json()["ticket_id"]
        bad = client.post(f"/api/v1/fund/tickets/{tid}/consumed",
                          json={"consumed_by_dispatch": "run-x"})
        assert bad.status_code == 422
        assert bad.json()["detail"]["type"] == "ask"

    def test_a_receipt_is_NOT_a_transition(self, client):
        """The design's separation (§1.5): consumption records that a lesson
        reached a brief; whether it is DONE is the chair's judgement and takes
        a transition of its own. Folding the receipt as a state change would
        close the loop automatically."""
        tid = _lesson(client)
        client.post(f"/api/v1/fund/tickets/{tid}/consumed",
                    json={"consumed_by_dispatch": "run-quant-d5"})
        rows = client.get("/api/v1/fund/tickets?limit=5000").json()["tickets"]
        row = next(r for r in rows if r["ticket_id"] == tid)
        assert row["state"] == "filed"
        assert row["terminal"] is False
        assert len(row["consumptions"]) == 1

    def test_two_dispatches_carrying_one_lesson_leave_two_receipts(self, client):
        tid = _lesson(client)
        for d in ("run-quant-d5", "run-quant-d6"):
            client.post(f"/api/v1/fund/tickets/{tid}/consumed",
                        json={"consumed_by_dispatch": d})
        b = client.get("/api/v1/fund/tickets/lessons").json()
        row = next(x for x in b["lessons"] if x["ticket_id"] == tid)
        assert len(row["consumptions"]) == 2
        # THE FIRST receipt sets the lag. A later re-carry does not make the
        # original wait shorter or longer.
        assert row["consumed_by_dispatch"] == "run-quant-d5"


# ============================================================================
# THE BOARD
# ============================================================================

class TestAnUnconsumedLessonAges:
    """Slice 5's acceptance: a never-consumed lesson AGES rather than vanishes."""

    def test_it_is_never_filtered_out(self, client):
        tid = _lesson(client)
        b = client.get("/api/v1/fund/tickets/lessons").json()
        assert [x["ticket_id"] for x in b["lessons"]] == [tid]
        assert b["counts"] == {"lessons": 1, "consumed": 0, "unconsumed": 1,
                               "terminal": 0}

    def test_its_lag_is_null_with_a_stated_basis_never_zero(self, client):
        """A lag of 0 for a lesson nobody carried reads as instant delivery."""
        _lesson(client)
        row = client.get("/api/v1/fund/tickets/lessons").json()["lessons"][0]
        assert row["consumption_lag_hours"] is None
        assert row["lag_basis"] == "unconsumed"
        assert row["age_basis"] == "event_timestamps"
        assert row["age_hours"] is not None

    def test_unconsumed_sorts_above_consumed(self, client):
        carried = _lesson(client, subject="this one was carried")
        client.post(f"/api/v1/fund/tickets/{carried}/consumed",
                    json={"consumed_by_dispatch": "run-quant-d5"})
        waiting = _lesson(client, subject="this one is still waiting")
        b = client.get("/api/v1/fund/tickets/lessons").json()
        assert b["lessons"][0]["ticket_id"] == waiting
        assert b["lessons"][0]["consumed"] is False

    def test_the_median_reports_the_denominator_it_was_taken_over(self, client):
        """A median over the consumed minority, read as the population, is a
        number meaning something other than its label."""
        _lesson(client)
        b = client.get("/api/v1/fund/tickets/lessons").json()
        assert b["median_lag_hours"] is None
        assert "UNKNOWN over 1 row(s) — never zero" in b["median_lag_basis"]

    def test_the_median_names_the_rows_it_excludes(self, client):
        carried = _lesson(client)
        client.post(f"/api/v1/fund/tickets/{carried}/consumed",
                    json={"consumed_by_dispatch": "run-quant-d5"})
        _lesson(client, subject="waiting")
        b = client.get("/api/v1/fund/tickets/lessons").json()
        assert b["median_lag_hours"] is not None
        assert "1 row(s) are NOT in this figure" in b["median_lag_basis"]

    def test_the_seat_filter_narrows_the_list(self, client):
        _lesson(client, seat="quant")
        _lesson(client, seat="analyst")
        b = client.get("/api/v1/fund/tickets/lessons?seat=analyst").json()
        assert [x["seat"] for x in b["lessons"]] == ["analyst"]

    def test_an_unreadable_fold_reports_UNKNOWN_not_an_empty_board(
            self, client, monkeypatch):
        from app.api.v1 import fund as fundapi

        class _Dead:
            def stream(self, **kw):
                raise OSError("no store")

        monkeypatch.setattr(fundapi, "_store", _Dead())
        b = client.get("/api/v1/fund/tickets/lessons").json()
        assert b["readable"] is False and b["lessons"] is None


class TestTheBindsEndpoint:
    def test_it_parses_and_stages_and_appends_nothing(self, client):
        """Off Postgres there is no staging table, so this proves the parse and
        the absence of any append in one call — `stored` false, `staged` null,
        and the event log untouched."""
        r = client.post("/api/v1/fund/tickets/binds",
                        json={"text": BINDS, "from_seat": "builder"})
        assert r.status_code == 200, r.text
        b = r.json()
        assert len(b["lessons"]) == 3
        assert b["stored"] is False and b["staged"] is None
        assert client.store.appended == []

    def test_a_dry_run_stores_nothing_even_with_a_table(self, client):
        r = client.post("/api/v1/fund/tickets/binds",
                        json={"text": BINDS, "dry_run": True})
        assert r.json()["stored"] is False
        assert client.store.appended == []

    def test_no_binds_block_is_reported_as_such(self, client):
        b = client.post("/api/v1/fund/tickets/binds",
                        json={"text": "## STATE\nprose\n"}).json()
        assert b["block_present"] is False and b["lessons"] == []


# ============================================================================
# END TO END, through the ordinary console
# ============================================================================

pgmark = pytest.mark.skipif(os.getenv("SKIP_PG_TESTS") == "1",
                            reason="Postgres tests disabled")
TEST_DB = "krypton_fund_ticketstagingtest"


@pytest.fixture()
def table():
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    head, _, _ = dsn().rpartition("/")
    target = f"{head}/{TEST_DB}"
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    st = ticketstaging.StagedTickets(dsn=target)
    with psycopg.connect(target) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_ticket_staged")
        c.commit()
    return st


@pgmark
class TestTheWholeHop:
    """A BINDS entry -> staged -> chair resolves -> lesson ticket -> receipt.

    THE ONE TEST THAT WOULD CATCH A BROKEN JOINT BETWEEN SLICES 4 AND 5. Every
    other test in this file exercises one half; this one is the reason the
    halves have to agree.
    """

    def test_binds_to_receipt(self, monkeypatch, table):
        from fastapi import FastAPI

        from app.api.v1 import fund as fundapi
        store = _WriteStore()
        monkeypatch.setattr(fundapi, "_store", store)
        monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
        monkeypatch.setattr(fundapi, "_stagedstore", lambda: table)
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        c = TestClient(app)

        staged = c.post("/api/v1/fund/tickets/binds",
                        json={"text": BINDS, "from_seat": "builder",
                              "run_id": "run-builder-hw3"}).json()
        assert staged["stored"] is True and len(staged["staged"]) == 3
        # NOTHING ON THE LOG YET. The seat has proposed; the chair has not
        # clicked.
        assert store.appended == []

        ids = [s["staged_id"] for s in staged["staged"]]
        r = c.post("/api/v1/fund/tickets/staged/resolve",
                   json={"decisions": [
                       {"staged_id": ids[0], "verdict": "accept"},
                       {"staged_id": ids[1], "verdict": "accept"},
                       {"staged_id": ids[2], "verdict": "strike",
                        "reason": "already in that seat's memory"}]})
        b = r.json()
        assert len(b["applied"]) == 2 and len(b["struck"]) == 1

        board = c.get("/api/v1/fund/tickets/lessons").json()
        assert board["counts"] == {"lessons": 2, "consumed": 0,
                                   "unconsumed": 2, "terminal": 0}
        tid = board["lessons"][0]["ticket_id"]
        c.post(f"/api/v1/fund/tickets/{tid}/consumed",
               json={"consumed_by_dispatch": "run-quant-d6"})
        board = c.get("/api/v1/fund/tickets/lessons").json()
        assert board["counts"]["consumed"] == 1
        assert board["counts"]["unconsumed"] == 1
        # THE STRUCK LESSON DID NOT VANISH — it is a struck ROW, on the record
        # with its reason, and it is not a ticket.
        assert table.get(ids[2])["status"] == "struck"
        assert table.get(ids[2])["resolution_reason"]
