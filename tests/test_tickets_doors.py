"""THE TICKET HIGHWAY'S DOORS — slice 2 of docs/design/TICKET_HIGHWAY_V1.

WHAT EACH CLASS DEFENDS, named so a reader can tell a guard from a decoration.
Every one of these is a defect this fund has already paid for once:

  * **The phantom guard** (``TestThePhantomGuard``). ``desk_resolve`` and
    ``desk_approve`` appended without ever looking the row up, so a POST
    against the 8-character shorthand the desk prints returned **200** and
    wrote an event against an aggregate no fold reads — bare ids like
    ``1c53589f`` are in Postgres today. Failure #5 of the design's own table:
    *any 200 lands against a fold-unknown id.*
  * **The lamp-close gap** (``TestAChairBornDispatchCanBeClosed``, ticket
    d03c09b6). Eight chair-born dispatches were open with no legitimate event
    that could close them. Slice 2's stated acceptance is that one reaches
    ``done``.
  * **The approval guard is REUSED, not rewritten** (``TestTheApprovalGuard``).
    A threshold or identity that exists twice has already drifted once, so the
    allowlist is MOVED in a test rather than compared — an assertion that the
    door's answer equals the constant cannot tell a read from a hardcoded
    duplicate that happens to agree today.
  * **Terminal is terminal** (``TestLegality``). No reopen transition exists;
    history is never unwound. The table is READ from ``tickets.ALLOWED_FROM``
    and a test moves it to prove that.
  * **No citation, no close** (``TestTerminalRequirements``). §1.2's terminal
    table made mechanical, plus the fact that expiry is SHUT while no aging
    policy is ratified.
  * **The legacy folds are untouched** (``TestTheLegacyFoldsAreUntouched``).
    The D17 rule — a new event type is a lifecycle change until proven
    otherwise — asserted by construction: the same store folded with and
    without ticket events must produce identical desk views.

THE STORE IS THIS FILE'S OWN. The house rule since D39: an endpoint test that
WRITES must own a ``MemStore`` and monkeypatch ``fundapi._store``, because two
probe events once turned 92 unrelated tests red while every one of them passed
in isolation.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.fund import desk, tickets as tk
from app.fund.deskengine import MIN_ID_PREFIX


# ---------------------------------------------------------------- fixtures --

class _WritableStore:
    """An event store for THIS test only. Accepts appends; yields both shapes.

    ``stream`` yields the ``Event`` OBJECTS the doors appended, not dicts,
    because that is what the in-memory store does in production and a fold
    tested only against dicts would be green in tests and blind on firestore.
    Pre-seeded legacy rows are dicts, so one store exercises both.
    """

    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):
        self.events.append(e)
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


def _ev(t: str, payload: dict) -> dict:
    return {"type": t, "payload": payload}


#: A chair-born dispatch: no ``request_id``, so it exists only in
#: ``desk._activity``. Twenty-four of these are on the live record and eight of
#: them were open with no way to close them.
D_CHAIR_BORN = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
#: A filed, undecided ask.
R_OPEN = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _legacy_events():
    return [
        _ev("DeskRequested",
            {"request_id": R_OPEN, "kind": "build", "serves": "builder",
             "subject": "an ask nobody has decided", "trace_id": R_OPEN,
             "at": "2026-08-20T00:00:00Z", "actor": "cto"}),
        _ev("DeskDispatched",
            {"task_id": D_CHAIR_BORN, "seat": "builder",
             "task": "chair-born work with no backing request",
             "request_id": None, "trace_id": D_CHAIR_BORN,
             "at": "2026-08-21T00:00:00Z", "actor": "cto"}),
    ]


@pytest.fixture()
def store():
    return _WritableStore(_legacy_events())


@pytest.fixture()
def client(monkeypatch, store):
    """A client whose store is this test's, with no deskstore.

    ``_deskstore`` returns None so the recommendation leg is UNKNOWN rather
    than zero — the doors do not need it and a test that quietly supplied an
    empty run list would be asserting against a leg the fold marks unread.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


def _open(client, **kw):
    body = {"type": "ask", "subject": "a ticket filed at the door"}
    body.update(kw)
    return client.post("/api/v1/fund/tickets", json=body)


def _opened_id(client, **kw) -> str:
    r = _open(client, **kw)
    assert r.status_code == 200, r.text
    return r.json()["ticket_id"]


def _transition(client, tid, to, **kw):
    body = {"to": to, "actor": "ceo", "confirm": tid[:8]}
    body.update(kw)
    return client.post(f"/api/v1/fund/tickets/{tid}/transition", json=body)


def _fold(store):
    return tk.fold(store, runs=None, now="2026-08-25T00:00:00Z")


def _by_id(store):
    return {t["ticket_id"]: t for t in _fold(store)["tickets"]}


def _types(store):
    from app.fund.events import EventType
    out = []
    for e in store.events:
        t = e.get("type") if isinstance(e, dict) else getattr(e, "type", None)
        out.append(getattr(t, "value", t))
    return out


# ============================================================================
# THE ROUND TRIP: what a door appends is what the fold reads
# ============================================================================

class TestTheOpenDoor:
    def test_a_filed_ticket_appears_in_the_fold_exactly_once(self, client, store):
        tid = _opened_id(client, subject="the round trip")
        rows = [t for t in _fold(store)["tickets"] if t["ticket_id"] == tid]
        assert len(rows) == 1
        assert rows[0]["state"] == "filed"
        assert rows[0]["type"] == "ask"
        assert rows[0]["subject"] == "the round trip"
        assert rows[0]["source"] == "TicketOpened"

    def test_the_id_is_a_full_uuid4_never_a_prefix(self, client):
        import uuid
        tid = _opened_id(client)
        # §1.1: ids are full uuid4, ALWAYS. The 8-char-prefix habit is what
        # rotted 54 of 56 linkages, so this asserts the shape rather than the
        # length — a 36-character non-uuid would pass a length check.
        assert uuid.UUID(tid).version == 4

    def test_two_tickets_never_share_an_id(self, client):
        assert _opened_id(client) != _opened_id(client)

    @pytest.mark.parametrize("field,value", [
        ("due_date", "2026-12-31"),
        ("reversibility", "irreversible"),
        ("money_at_stake", 128.26),
    ])
    def test_the_routing_fields_survive_the_round_trip(self, client, store,
                                                       field, value):
        """The three fields the builder's D9 finding said NOTHING writes.

        ``due_date`` is the desk's top ranking key and separated ZERO rows
        because no producer ever wrote it. A door that accepted them and did
        not fold them would reproduce that finding with extra steps.
        """
        tid = _opened_id(client, **{field: value})
        assert _by_id(store)[tid][field] == value

    def test_the_declared_next_actor_is_READ_not_inferred(self, client, store):
        tid = _opened_id(client, next_actor="ceo")
        row = _by_id(store)[tid]
        assert row["next_actor"] == "ceo"
        assert row["next_actor_basis"] == "explicit"

    def test_an_undeclared_actor_follows_desk_UNDECIDED_ROUTES_TO(
            self, client, store, monkeypatch):
        """MOVED, not compared. An assertion that the fold's answer equals
        ``desk.UNDECIDED_ROUTES_TO`` cannot distinguish a read from a hardcoded
        ``"chair"`` that happens to agree today."""
        tid = _opened_id(client)
        assert _by_id(store)[tid]["next_actor"] == desk.UNDECIDED_ROUTES_TO
        monkeypatch.setattr(desk, "UNDECIDED_ROUTES_TO", "seat")
        moved = _by_id(store)[tid]
        assert moved["next_actor"] == "seat"
        assert moved["next_actor_basis"] == "undecided_default"

    def test_a_parent_is_recorded_at_birth(self, client, store):
        parent = _opened_id(client, subject="the parent")
        child = _opened_id(client, subject="the child", parent_id=parent)
        row = _by_id(store)[child]
        assert row["parent_id"] == parent
        assert row["parent_basis"] == "declared_at_birth"

    def test_a_parent_that_does_not_exist_is_refused(self, client, store):
        """A ticket born linked to nothing is the 54-of-56 rot, freshly made."""
        before = len(store.events)
        r = _open(client, parent_id="ffffffff-ffff-4fff-8fff-ffffffffffff")
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "no such ticket"
        assert len(store.events) == before, "a refused open must append nothing"


class TestTheOpenDoorValidates:
    @pytest.mark.parametrize("body,where", [
        ({"type": "lesson"}, "type"),
        ({"type": "asks"}, "type"),
        ({"type": ""}, "type"),
        ({"subject": "   "}, "subject"),
        ({"next_actor": "unknown"}, "next_actor"),
        ({"next_actor": "builder"}, "next_actor"),
        ({"reversibility": "maybe"}, "reversibility"),
        ({"due_date": "31-12-2026"}, "due_date"),
        ({"due_date": "2026-02-31"}, "due_date"),
        ({"due_date": "tomorrow"}, "due_date"),
        ({"money_at_stake": -1.0}, "money_at_stake"),
    ])
    def test_bad_input_is_refused_and_appends_nothing(self, client, store,
                                                      body, where):
        before = len(store.events)
        r = _open(client, **body)
        assert r.status_code == 422, r.text
        assert where in str(r.json()["detail"]), \
            "the refusal must name the field it refused on"
        assert len(store.events) == before

    def test_unknown_is_refused_because_it_is_the_spines_conclusion(self, client):
        """``unknown`` is in ``desk.NEXT_ACTORS`` and NOT in
        ``FILEABLE_NEXT_ACTORS``: it is what the spine concludes when it cannot
        tell, never something a filer may claim. A door validating against the
        wider vocabulary would let a filer assert the spine's own uncertainty.
        """
        assert "unknown" in desk.NEXT_ACTORS
        assert "unknown" not in desk.FILEABLE_NEXT_ACTORS
        assert _open(client, next_actor="unknown").status_code == 422

    def test_the_fileable_vocabulary_is_READ_not_restated(self, client,
                                                          monkeypatch):
        monkeypatch.setattr(desk, "FILEABLE_NEXT_ACTORS", ("ceo",))
        assert _open(client, next_actor="ceo").status_code == 200
        assert _open(client, next_actor="chair").status_code == 422

    def test_the_openable_types_are_READ_not_restated(self, client,
                                                      monkeypatch):
        monkeypatch.setattr(tk, "OPENABLE_TYPES", ("challenge",))
        assert _open(client, type="challenge").status_code == 200
        assert _open(client, type="ask").status_code == 422

    def test_a_challenge_can_be_filed_so_terminal_is_not_a_dead_end(
            self, client, store):
        """§1.2 says a dispute with a terminal ticket is a NEW ``challenge``
        ticket. Enforcing terminal-is-terminal while that type could not be
        filed would be a rule pointing at a door that does not exist."""
        tid = _opened_id(client, type="challenge", subject="I dispute the close")
        assert _by_id(store)[tid]["type"] == "challenge"


# ============================================================================
# THE PHANTOM GUARD — failure #5: any 200 lands against a fold-unknown id
# ============================================================================

class TestThePhantomGuard:
    UNKNOWN = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

    def test_a_transition_against_an_unknown_id_is_404_not_200(self, client,
                                                               store):
        before = len(store.events)
        r = _transition(client, self.UNKNOWN, "in_flight")
        assert r.status_code == 404
        d = r.json()["detail"]
        assert d["error"] == "no such ticket"
        assert d["folds_consulted"] == ["tickets"]
        assert d["did_you_mean"] == []
        assert len(store.events) == before

    def test_a_link_against_an_unknown_id_is_404(self, client):
        tid = _opened_id(client)
        r = client.post(f"/api/v1/fund/tickets/{self.UNKNOWN}/link",
                        json={"link_kind": "serves", "target_id": tid})
        assert r.status_code == 404

    def test_the_link_doors_TARGET_is_guarded_too(self, client, store):
        """BOTH ENDS. A link whose target does not exist is exactly the rot
        this door was built to prevent, manufactured at the door itself."""
        tid = _opened_id(client)
        before = len(store.events)
        r = client.post(f"/api/v1/fund/tickets/{tid}/link",
                        json={"link_kind": "serves", "target_id": self.UNKNOWN})
        assert r.status_code == 404
        assert r.json()["detail"]["ticket_id"] == self.UNKNOWN, \
            "the refusal must name the END that was unknown"
        assert len(store.events) == before

    def test_an_eight_char_shorthand_is_refused_WITH_the_expansion(self, client):
        """The shorthand is what the desk prints, so the caller is almost
        always one expansion away. This is the id shape that returned 200 and
        wrote a phantom aggregate."""
        tid = _opened_id(client)
        r = _transition(client, tid[:MIN_ID_PREFIX], "in_flight")
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == [tid]

    def test_a_prefix_shorter_than_the_minimum_offers_no_expansion(self, client):
        """Below ``MIN_ID_PREFIX`` an expansion is a guess, not help — a
        3-character prefix could match anything. The refusal stands; the pool
        is empty."""
        tid = _opened_id(client)
        r = _transition(client, tid[:MIN_ID_PREFIX - 1], "in_flight")
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == []

    def test_MIN_ID_PREFIX_is_READ_not_restated(self, client, monkeypatch):
        from app.fund import deskengine
        tid = _opened_id(client)
        monkeypatch.setattr(deskengine, "MIN_ID_PREFIX", 4)
        r = _transition(client, tid[:4], "in_flight")
        assert r.json()["detail"]["did_you_mean"] == [tid]

    def test_a_legacy_dispatch_id_is_KNOWN_to_this_guard(self, client):
        """THE FLAG THAT IS NOT HERE. The desk guard needed ``allow_dispatch``
        because it read one fold of two. The ticket fold holds asks,
        dispatches and recommendations in one population, so a chair-born
        dispatch is simply a known id and there is no flag to widen."""
        r = _transition(client, D_CHAIR_BORN, "returned", actor="cto",
                        confirm=None)
        assert r.status_code == 200, r.text

    def test_it_FAILS_OPEN_when_the_fold_is_unreadable(self, client, store,
                                                       monkeypatch):
        """DELIBERATE, AND INHERITED FROM ``_refuse_unknown_request``
        UNCHANGED. The guard cannot tell "no such ticket" from "cannot tell",
        and refusing every call because a READ failed would turn a rendering
        guard into an outage on the approval path.

        Measured through the LINK door, which is the one that continues after
        the guard: an unreadable fold must not 404, and the record must say the
        cycle check did not run.
        """
        from app.api.v1 import fund as fundapi
        tid = _opened_id(client)
        target = _opened_id(client)
        monkeypatch.setattr(fundapi, "_ticket_index", lambda: None)
        r = client.post(f"/api/v1/fund/tickets/{tid}/link",
                        json={"link_kind": "parent", "target_id": target})
        assert r.status_code == 200, "the phantom guard must fail OPEN"
        assert r.json()["cycle_checked"] is False, \
            "a link recorded without the cycle check must not read as checked"

    def test_the_TRANSITION_door_503s_rather_than_guessing_legality(
            self, client, store, monkeypatch):
        """IDENTITY AND LEGALITY ARE DIFFERENT QUESTIONS, and only the first
        one fails open. Without the ticket's current state this door would
        append a transition the fold REFUSES at replay — a 200 for something
        that never happened, which is the shape the phantom guard exists to
        end.
        """
        from app.api.v1 import fund as fundapi
        tid = _opened_id(client)
        before = len(store.events)
        monkeypatch.setattr(fundapi, "_ticket_index", lambda: None)
        r = _transition(client, tid, "in_flight")
        assert r.status_code == 503
        assert len(store.events) == before


# ============================================================================
# THE APPROVAL GUARD — reused, never rewritten
# ============================================================================

class TestTheApprovalGuard:
    def test_a_decision_transition_refuses_an_actor_off_the_allowlist(
            self, client, store):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", actor="builder")
        assert r.status_code == 403
        assert "allowlist" in r.json()["detail"]
        assert "ApprovalRefused" in _types(store), \
            "a refused approval is a FINDING and findings are events — a " \
            "refusal whose only trace is an HTTP response is invisible to " \
            "the riskofficer, who audits from /fund/events"
        assert _by_id(store)[tid]["state"] == "filed"

    def test_a_missing_echo_is_refused(self, client):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", confirm=None)
        assert r.status_code == 403
        assert "confirm echo" in r.json()["detail"]

    def test_an_echo_from_a_DIFFERENT_ticket_is_refused(self, client):
        tid, other = _opened_id(client), _opened_id(client)
        r = _transition(client, tid, "accepted", confirm=other[:8])
        assert r.status_code == 403

    def test_via_cto_must_quote_the_ceo(self, client):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", actor="neelesh-via-cto")
        assert r.status_code == 403
        assert "verbatim" in r.json()["detail"]

    def test_via_cto_attribution_reaches_the_event(self, client, store):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", actor="neelesh-via-cto",
                        instruction="keep belting")
        assert r.status_code == 200, r.text
        assert r.json()["actor"] == "neelesh-via-cto [keep belting]"
        assert _by_id(store)[tid]["transitions"][-1]["actor"] == \
            "neelesh-via-cto [keep belting]"

    def test_the_allowlist_is_READ_not_copied(self, client, monkeypatch):
        """MOVED, not compared. An assertion that ``ceo`` is admitted and
        ``builder`` is not agrees with a hardcoded duplicate of the set."""
        from app.api.v1 import fund as fundapi
        tid = _opened_id(client)
        monkeypatch.setattr(fundapi, "DESK_APPROVAL_ALLOWLIST", {"builder"})
        assert _transition(client, tid, "accepted", actor="ceo").status_code == 403
        assert _transition(client, tid, "accepted",
                           actor="builder").status_code == 200

    @pytest.mark.parametrize("to", ["in_flight", "returned"])
    def test_a_NON_decision_transition_takes_no_echo(self, client, store, to):
        """The pair that makes the guard test mean something. If every
        transition were guarded, "decision transitions are guarded" would be
        true and empty. ``in_flight`` and ``returned`` are the chair recording
        what it DID, not a permission it granted itself."""
        tid = _opened_id(client)
        assert _transition(client, tid, "in_flight", actor="cto",
                           confirm=None).status_code == 200
        if to == "returned":
            assert _transition(client, tid, "returned", actor="cto",
                               confirm=None).status_code == 200

    def test_DECISION_TRANSITIONS_is_READ_not_restated(self, client,
                                                       monkeypatch):
        """Move the classification and the guard must follow it. ``in_flight``
        is unguarded today; declaring it a decision must make it demand an
        echo, and that can only happen if the door reads the constant."""
        tid = _opened_id(client)
        monkeypatch.setattr(tk, "DECISION_TRANSITIONS", ("in_flight",))
        r = _transition(client, tid, "in_flight", actor="cto", confirm=None)
        assert r.status_code == 403

    def test_the_guard_runs_BEFORE_the_lineage_is_handed_out(self, client):
        """``desk_approve`` moved this order for a reason: v1 handed the
        supersession lineage to ANY caller, including one the allowlist was
        about to refuse. Identity is established first. An unknown id with a
        bad actor must answer 403, never 404 — the 404 carries
        ``did_you_mean``, which is information a refused caller has not earned.
        """
        r = _transition(client, TestThePhantomGuard.UNKNOWN, "accepted",
                        actor="builder")
        assert r.status_code == 403


# ============================================================================
# LEGALITY — terminal is terminal
# ============================================================================

class TestLegality:
    def test_an_unknown_target_state_is_refused_with_the_vocabulary(self,
                                                                    client):
        tid = _opened_id(client)
        r = _transition(client, tid, "dine")
        assert r.status_code == 422
        assert set(r.json()["detail"]["allowed"]) == set(tk.TICKET_STATES)

    def test_filed_does_not_jump_to_returned(self, client, store):
        tid = _opened_id(client)
        before = len(store.events)
        r = _transition(client, tid, "returned", actor="cto", confirm=None)
        assert r.status_code == 409
        assert r.json()["detail"]["from"] == "filed"
        assert r.json()["detail"]["allowed_from"] == ["in_flight"]
        assert len(store.events) == before

    def test_a_terminal_ticket_cannot_be_REOPENED(self, client, store):
        """HISTORY IS NEVER UNWOUND. No ``ALLOWED_FROM`` entry admits a
        terminal source, so there is no reopen transition to find."""
        tid = _opened_id(client)
        assert _transition(client, tid, "declined",
                           reason="not this quarter").status_code == 200
        r = _transition(client, tid, "in_flight", actor="cto", confirm=None)
        assert r.status_code == 409
        assert r.json()["detail"]["terminal"] is True
        assert "challenge" in r.json()["detail"]["note"]

    @pytest.mark.parametrize("terminal", tk.TERMINAL_STATES)
    def test_NO_terminal_state_is_a_legal_SOURCE(self, terminal):
        """The table itself, not one path through it. A single reopen entry
        added by a future edit would fail here before any door was written."""
        for to, sources in tk.ALLOWED_FROM.items():
            assert terminal not in sources, \
                f"{terminal!r} -> {to!r} would be a reopen transition"

    def test_ALLOWED_FROM_is_READ_not_restated(self, client, monkeypatch):
        """MOVED. The door and the fold must consult one table; two copies of
        a state machine is how a door admits what a fold then refuses."""
        tid = _opened_id(client)
        monkeypatch.setitem(tk.ALLOWED_FROM, "in_flight", ())
        assert _transition(client, tid, "in_flight", actor="cto",
                           confirm=None).status_code == 409

    def test_the_fold_refuses_at_replay_what_two_racing_doors_admit(
            self, client, store):
        """THE DOOR IS A CONVENIENCE; THE FOLD IS THE AUTHORITY. Two callers
        can both read ``filed`` and both pass the door. Only one may land, and
        the loser is RECORDED as refused rather than dropped — "this never
        happened" and "this was attempted and correctly refused" are different
        facts, and only the second says the guard did its job.
        """
        from app.fund.events import Event, EventType
        tid = _opened_id(client)
        assert _transition(client, tid, "approved").status_code == 200
        # The second event, appended directly: the race the door cannot see.
        store.append(Event(
            aggregate_id=tid, aggregate_type="ticket",
            type=EventType.TICKET_TRANSITIONED,
            payload={"ticket_id": tid, "from": "filed", "to": "approved",
                     "actor": "ceo", "basis": "decision",
                     "at": "2026-08-24T23:59:00Z"},
            actor="ceo"))
        row = _by_id(store)[tid]
        assert row["state"] == "approved"
        assert [r["to"] for r in row["refused_transitions"]] == ["approved"]


# ============================================================================
# TERMINAL REQUIREMENTS — no citation, no close
# ============================================================================

class TestTerminalRequirements:
    @pytest.mark.parametrize("to,field", [
        ("done", "citation"),
        ("declined", "reason"),
        ("superseded", "superseder_ref"),
        ("merged", "decision_ref"),
    ])
    def test_a_terminal_without_its_record_is_refused(self, client, store,
                                                      to, field):
        tid = _opened_id(client)
        before = len(store.events)
        r = _transition(client, tid, to)
        assert r.status_code == 422
        assert r.json()["detail"]["required"] == field
        assert len(store.events) == before
        assert _transition(client, tid, to, **{field: "the record"}
                           ).status_code == 200

    def test_a_blank_record_is_not_a_record(self, client):
        tid = _opened_id(client)
        assert _transition(client, tid, "done", citation="   ").status_code == 422

    def test_TERMINAL_REQUIREMENTS_is_READ_not_restated(self, client,
                                                        monkeypatch):
        tid = _opened_id(client)
        monkeypatch.setitem(tk.TERMINAL_REQUIREMENTS, "approved",
                            ("citation", "moved for the test"))
        assert _transition(client, tid, "approved").status_code == 422

    def test_EXPIRY_IS_SHUT_while_no_aging_policy_is_ratified(self, client,
                                                              store):
        """§1.2 makes the aging policy CEO-ratified and none exists. A door
        that closes aged work under no stated rule is how a queue gets quietly
        emptied instead of quietly worked."""
        assert tk.AGING_POLICY_VERSION is None
        tid = _opened_id(client)
        before = len(store.events)
        r = _transition(client, tid, "expired")
        assert r.status_code == 422
        assert "AGING_POLICY_VERSION" in r.json()["detail"]["note"]
        assert len(store.events) == before

    def test_when_a_policy_IS_ratified_the_sweep_must_NAME_it(self, client,
                                                              monkeypatch):
        monkeypatch.setattr(tk, "AGING_POLICY_VERSION", "aging-v1")
        tid = _opened_id(client)
        assert _transition(client, tid, "expired").status_code == 422
        assert _transition(client, tid, "expired",
                           policy_version="aging-v2").status_code == 422
        assert _transition(client, tid, "expired",
                           policy_version="aging-v1").status_code == 200


# ============================================================================
# THE SUPERSESSION REFUSAL, generalized
# ============================================================================

class _Edges:
    """A readable edge store with one live edge on ``ref``."""

    def __init__(self, ref):
        self.ref = ref

    def __call__(self):
        return {self.ref: {"edge_id": "e1", "mode": "superseded",
                           "superseder_ref": "req:the-newer-one",
                           "reason": "a newer ask replaces it",
                           "retracted_at": None}}


class TestTheSupersessionRefusal:
    def test_an_advancing_transition_on_a_superseded_ask_is_409(
            self, client, store, monkeypatch):
        from app.api.v1 import fund as fundapi
        from app.fund.deskengine import req_ref
        monkeypatch.setattr(fundapi, "_edges_by_target", _Edges(req_ref(R_OPEN)))
        r = _transition(client, R_OPEN, "approved")
        assert r.status_code == 409
        assert r.json()["detail"]["refused"] is True
        assert "ApprovalRefused" in _types(store), \
            "the D22 finding: a refusal whose only trace is an HTTP response " \
            "is the fund's first SILENT approval refusal"
        assert _by_id(store)[R_OPEN]["state"] == "filed"

    def test_CLOSING_a_superseded_row_stays_easy(self, client, monkeypatch):
        """The legacy constant lists only the ADVANCING statuses for exactly
        this reason: refusing to close a superseded row would strand it open
        forever."""
        from app.api.v1 import fund as fundapi
        from app.fund.deskengine import req_ref
        monkeypatch.setattr(fundapi, "_edges_by_target", _Edges(req_ref(R_OPEN)))
        assert _transition(client, R_OPEN, "declined",
                           reason="superseded, closing it").status_code == 200

    def test_RETURNED_is_not_advancing_so_a_seats_work_is_never_lost(
            self, client, monkeypatch):
        """Recording that a seat came back is a statement about something that
        ALREADY HAPPENED. Refusing it would leave a superseded in-flight ticket
        with no way to record what the seat produced — the work would vanish
        from the record rather than from the queue."""
        from app.api.v1 import fund as fundapi
        from app.fund.deskengine import req_ref
        assert _transition(client, R_OPEN, "in_flight", actor="cto",
                           confirm=None).status_code == 200
        monkeypatch.setattr(fundapi, "_edges_by_target", _Edges(req_ref(R_OPEN)))
        assert _transition(client, R_OPEN, "returned", actor="cto",
                           confirm=None).status_code == 200
        # and the step AFTER it is advancing, so nothing advances past the edge
        assert _transition(client, R_OPEN, "done",
                           citation="an artifact").status_code == 409

    def test_a_ticket_with_NO_key_in_the_edge_store_says_so(self, client,
                                                            monkeypatch):
        """THREE ANSWERS, NOT TWO. The edge store's vocabulary predates
        tickets: a dispatch has no ``req:``/``rec:`` key at all. Reporting that
        as ``supersession_readable: true`` would let an UNRUN check read as a
        passed one, which is precisely what the D22 review found missing."""
        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
        r = _transition(client, D_CHAIR_BORN, "returned", actor="cto",
                        confirm=None)
        assert r.status_code == 200
        assert r.json()["supersession_checked"] is False
        assert r.json()["supersession_readable"] is None

    def test_an_unreadable_edge_store_is_DISCLOSED_not_hidden(self, client,
                                                              monkeypatch):
        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_edges_by_target", lambda: None)
        r = _transition(client, R_OPEN, "approved")
        assert r.status_code == 200
        assert r.json()["supersession_readable"] is False, \
            "False means the check did not run and this went through anyway"
        assert r.json()["supersession_checked"] is True

    def test_ADVANCING_TICKET_STATES_is_READ_not_restated(self, client,
                                                          monkeypatch):
        from app.api.v1 import fund as fundapi
        from app.fund.deskengine import req_ref
        monkeypatch.setattr(fundapi, "_edges_by_target", _Edges(req_ref(R_OPEN)))
        monkeypatch.setattr(tk, "ADVANCING_TICKET_STATES", ())
        assert _transition(client, R_OPEN, "approved").status_code == 200


# ============================================================================
# THE LINK DOOR
# ============================================================================

class TestTheLinkDoor:
    def test_a_parent_link_lands_in_the_fold(self, client, store):
        a, b = _opened_id(client), _opened_id(client)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "parent", "target_id": b,
                              "basis": "the run that serves it"})
        assert r.status_code == 200, r.text
        row = _by_id(store)[a]
        assert row["parent_id"] == b
        assert row["parent_basis"] == "ticket_linked"
        assert row["links"][0]["basis"] == "the run that serves it"

    def test_a_decision_ref_is_RECORDED_here_and_ENFORCED_in_slice_3(
            self, client, store):
        a, b = _opened_id(client), _opened_id(client)
        client.post(f"/api/v1/fund/tickets/{a}/link",
                    json={"link_kind": "decision_ref", "target_id": b})
        assert _by_id(store)[a]["decision_ref"] == b

    def test_serves_links_accumulate(self, client, store):
        a, b, c = (_opened_id(client) for _ in range(3))
        for t in (b, c):
            client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "serves", "target_id": t})
        assert _by_id(store)[a]["serves"] == [b, c]

    def test_an_unknown_link_kind_is_refused_with_the_vocabulary(self, client,
                                                                 store):
        a, b = _opened_id(client), _opened_id(client)
        before = len(store.events)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "blocks", "target_id": b})
        assert r.status_code == 422
        assert r.json()["detail"]["allowed"] == list(tk.LINK_KINDS)
        assert len(store.events) == before

    def test_LINK_KINDS_is_READ_not_restated(self, client, monkeypatch):
        a, b = _opened_id(client), _opened_id(client)
        monkeypatch.setattr(tk, "LINK_KINDS", ("serves",))
        assert client.post(f"/api/v1/fund/tickets/{a}/link",
                           json={"link_kind": "parent",
                                 "target_id": b}).status_code == 422

    @pytest.mark.parametrize("kind", list(tk.LINK_KINDS))
    def test_a_ticket_cannot_link_to_itself(self, client, store, kind):
        """EVERY KIND, and the assertion is on the SPECIFIC refusal.

        Mutation survivor M47 is why both halves of that sentence are here. A
        self-``parent`` link is ALSO caught by the cycle check one branch
        further down, so a test that only used ``parent`` and only asserted
        ``422`` passed with the self-link check deleted — two different guards
        producing one status code, and the test could not tell them apart.
        ``serves`` and ``decision_ref`` run no cycle check at all, so they are
        the arms that actually pin this guard.
        """
        a = _opened_id(client)
        before = len(store.events)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": kind, "target_id": a})
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "a ticket cannot link to itself"
        assert len(store.events) == before

    def test_a_parent_cycle_is_refused(self, client, store):
        """``parent_id`` is a TREE. A cycle in it makes every consumer that
        walks the ancestry loop forever, and the walk is what the design's
        in-tray queries are built on."""
        a, b, c = (_opened_id(client) for _ in range(3))
        for child, parent in ((a, b), (b, c)):
            assert client.post(f"/api/v1/fund/tickets/{child}/link",
                               json={"link_kind": "parent",
                                     "target_id": parent}).status_code == 200
        before = len(store.events)
        r = client.post(f"/api/v1/fund/tickets/{c}/link",
                        json={"link_kind": "parent", "target_id": a})
        assert r.status_code == 422
        assert "cycle" in r.json()["detail"]["error"]
        assert len(store.events) == before

    def test_a_NON_parent_link_may_point_back_up_the_tree(self, client):
        """Only ``parent`` is a tree. ``serves`` and ``decision_ref`` are
        allowed to point anywhere, and refusing them on the parent chain would
        forbid a child from citing the ask it serves."""
        a, b = _opened_id(client), _opened_id(client)
        client.post(f"/api/v1/fund/tickets/{a}/link",
                    json={"link_kind": "parent", "target_id": b})
        assert client.post(f"/api/v1/fund/tickets/{b}/link",
                           json={"link_kind": "serves",
                                 "target_id": a}).status_code == 200


# ============================================================================
# THE MUTATION SURVIVORS — every test below exists because a mutant lived
#
# The first pass over this slice killed 42 of 54 and 12 lived. NONE of them
# was equivalent or no-op: each named a branch the suite could not see. They
# are gathered here rather than scattered so the reason survives the diff —
# a test written to kill a specific mutant is worth more when the mutant is
# named beside it.
# ============================================================================

class TestTheApprovalGuardCoversEveryDecision:
    """M19 and M20 — THE TWO THAT MATTERED, both on the approval path.

    The guard was exercised for ``accepted`` alone. Removing ``declined`` from
    ``DECISION_TRANSITIONS`` (M19) and removing the whole ``+ TERMINAL_STATES``
    half (M20) both left the suite GREEN — which is to say the tests asserted
    "one decision transition is guarded" while the docstring claimed "every
    decision transition is guarded". Parametrizing over the constant is what
    makes the two sentences the same sentence.
    """

    #: THE LIST IS THE DESIGN'S, TRANSCRIBED, NOT THE CODE'S — and the second
    #: mutation pass is why. Parametrizing over ``tk.DECISION_TRANSITIONS``
    #: killed neither M19 nor M20, because the mutant SHRINKS that constant and
    #: the test's own domain shrank with it: the states the mutant removed were
    #: never asked about. A test whose parameter list is read from the value
    #: under test has asserted self-consistency and can prove nothing.
    #:
    #: So this is memo §2.3 in longhand — *"decision transitions (``approved``,
    #: ``accepted``, ``declined``, all terminals)"* — expanded against §1.2's
    #: five terminals, and ``test_the_constant_matches_the_design`` below is
    #: what stops the transcription and the constant from drifting apart.
    #:
    #: ``expired`` is absent, and that is not a hole: it is refused outright
    #: while ``AGING_POLICY_VERSION`` is None, by a check that runs BEFORE the
    #: guard, so there is no admitted path through the guard to test.
    #: ``TestTerminalRequirements`` pins that refusal instead.
    _GUARDED = ("approved", "accepted", "declined", "done", "superseded",
                "merged")

    #: The record each terminal must carry, so the door reaches the guard
    #: rather than stopping at the 422 in front of it. Transitions with no
    #: requirement pass an empty dict.
    _RECORD = {"done": {"citation": "an artifact"},
               "declined": {"reason": "not this quarter"},
               "superseded": {"superseder_ref": "req:the-newer-one"},
               "merged": {"decision_ref": "the-canonical-row"}}

    def test_the_constant_matches_the_design(self):
        """The transcription above against the code, in one place. If §2.3's
        list and ``DECISION_TRANSITIONS`` ever diverge, this says so — and it
        is the only test here that may read the constant, precisely because
        checking the constant is its whole job."""
        assert set(tk.DECISION_TRANSITIONS) == set(self._GUARDED) | {"expired"}

    @pytest.mark.parametrize("to", _GUARDED)
    def test_EVERY_decision_transition_refuses_an_actor_off_the_allowlist(
            self, client, store, to):
        tid = _opened_id(client)
        r = _transition(client, tid, to, actor="builder",
                        **self._RECORD.get(to, {}))
        assert r.status_code == 403, \
            f"a {to!r} transition reached the record without the guard"
        assert "allowlist" in r.json()["detail"]
        assert _by_id(store)[tid]["state"] == "filed"

    @pytest.mark.parametrize("to", _GUARDED)
    def test_EVERY_decision_transition_demands_the_echo(self, client, to):
        tid = _opened_id(client)
        r = _transition(client, tid, to, confirm=None, **self._RECORD.get(to, {}))
        assert r.status_code == 403
        assert "confirm echo" in r.json()["detail"]


class TestSupersessionOnATicketWithNoKey:
    """M45 and M53 — an UNRUN check reading as a passed one.

    The existing coverage used ``returned``, which is not an advancing
    transition, so the supersession block was skipped whatever
    ``_ticket_supersession_ref`` returned. Both mutants lived in that shadow:
    one dropped the ``and ref`` condition, the other fabricated a ``req:`` key
    for a ticket type the edge store has never held. Only an ADVANCING
    transition on a ticket with no key can see either.
    """

    def test_an_advancing_transition_with_no_key_reports_the_check_UNRUN(
            self, client, monkeypatch):
        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
        assert _transition(client, D_CHAIR_BORN, "returned", actor="cto",
                           confirm=None).status_code == 200
        r = _transition(client, D_CHAIR_BORN, "done", citation="an artifact")
        assert r.status_code == 200, r.text
        assert r.json()["supersession_checked"] is False
        assert r.json()["supersession_readable"] is None, \
            "a dispatch has no req:/rec: key, so the check did not run — " \
            "reporting it as readable would let an unrun check read as passed"

    def test_a_door_born_ticket_has_no_key_either(self, client, monkeypatch):
        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
        tid = _opened_id(client)
        r = _transition(client, tid, "approved")
        assert r.status_code == 200, r.text
        assert r.json()["supersession_checked"] is False


class TestTheFoldItselfIsUnreadable:
    """M54 — the fail-open tests monkeypatched the very function under test.

    ``test_it_FAILS_OPEN_when_the_fold_is_unreadable`` replaced
    ``_ticket_index`` wholesale, so ``_ticket_index``'s OWN guard (``rows is
    None`` -> None) was never executed by anything. Deleting it left the suite
    green and the real path raising ``TypeError`` on a None row list — a 500
    where the design promises a disclosed fail-open. This drives the REAL path
    by breaking the store underneath it.
    """

    @pytest.fixture()
    def blind_client(self, monkeypatch, store):
        class _Blind:
            def append(self, e):
                store.append(e)
                return e

            def stream(self, since_seq=0, limit=100_000):
                raise OSError("the event stream is unreadable")

        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_store", _Blind())
        monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        return TestClient(app)

    def test_the_link_door_fails_OPEN_through_the_real_index(self, blind_client):
        r = blind_client.post("/api/v1/fund/tickets/any-id/link",
                              json={"link_kind": "serves",
                                    "target_id": "another-id"})
        assert r.status_code == 200, \
            "an unreadable fold must not turn a rendering guard into an outage"
        assert r.json()["cycle_checked"] is False

    def test_the_open_doors_parent_guard_fails_OPEN_too(self, blind_client):
        r = blind_client.post("/api/v1/fund/tickets",
                              json={"type": "ask", "subject": "filed blind",
                                    "parent_id": "a-parent-nobody-can-check"})
        assert r.status_code == 200, r.text

    def test_the_transition_door_503s_through_the_real_index(self, blind_client):
        r = blind_client.post("/api/v1/fund/tickets/any-id/transition",
                              json={"to": "in_flight", "actor": "cto"})
        assert r.status_code == 503


class TestDidYouMeanIsAPrefixNotASubstring:
    """M27 — ``startswith`` swapped for ``in`` and every test still passed,
    because every test asked with a prefix.

    A ``did_you_mean`` that matches a substring ANYWHERE is a wrong
    suggestion, not a loose one: it would answer a mistyped middle-of-the-id
    fragment with a confident expansion to an unrelated ticket, and the whole
    point of the help is that the caller is one expansion away from the right
    row.
    """

    def test_a_middle_fragment_gets_no_expansion(self, client):
        tid = _opened_id(client)
        middle = tid[4:4 + MIN_ID_PREFIX + 4]
        assert middle in tid and not tid.startswith(middle)
        r = _transition(client, middle, "in_flight")
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == []


class TestTheFoldDefendsItselfAgainstABadProducer:
    """M2, M3, M5, M6, M10 — the fold's own guards, which no door can reach.

    The doors validate, so a malformed ticket event cannot arrive through
    them TODAY. Slice 4's staging pipeline and slice 5's resolve pipeline will
    be new producers, and the fold's guards are what stands between a producer
    bug and a corrupted population. Every one of these was invisible until an
    event was hand-crafted, which is the only way to test them.
    """

    def _append(self, store, etype, payload):
        from app.fund.events import Event
        store.append(Event(aggregate_id=str(payload.get("ticket_id") or "?"),
                           aggregate_type="ticket", type=etype,
                           payload=payload, actor="a-producer"))

    def test_an_opened_event_with_no_ticket_id_mints_nothing(self, client,
                                                             store):
        """M2. Without the guard this mints a ticket keyed on the empty
        string — a row with no identity, which every later event would then
        resolve against by accident."""
        from app.fund.events import EventType
        before = {t["ticket_id"] for t in _fold(store)["tickets"]}
        self._append(store, EventType.TICKET_OPENED,
                     {"ticket_id": "", "type": "ask", "subject": "no id",
                      "at": "2026-08-25T00:00:00Z", "actor": "cto"})
        assert {t["ticket_id"] for t in _fold(store)["tickets"]} == before

    @pytest.mark.parametrize("etype_name,extra", [
        ("TICKET_TRANSITIONED", {"to": "approved"}),
        ("TICKET_LINKED", {"link_kind": "parent", "target_id": "x"}),
    ])
    def test_an_event_against_an_unknown_id_is_counted_as_a_PHANTOM(
            self, store, etype_name, extra):
        """M3. Silently skipping it and recording it as a phantom look
        identical from the outside and are opposite facts: one says nothing
        happened, the other says something was attempted against an id no
        adapter has ever seen. The phantom cohort is failure #5's meter."""
        from app.fund.events import EventType
        self._append(store, getattr(EventType, etype_name),
                     {"ticket_id": "an-id-no-fold-has-seen",
                      "at": "2026-08-25T00:00:00Z", **extra})
        folded = _fold(store)
        assert [p["id"] for p in folded["phantom_events"]] == \
            ["an-id-no-fold-has-seen"]
        assert "an-id-no-fold-has-seen" not in \
            {t["ticket_id"] for t in folded["tickets"]}

    def test_a_REFUSED_returned_transition_does_not_stamp_returned_at(
            self, client, store):
        """M5. ``filed -> returned`` is illegal, so ``_advance`` refuses it.
        Stamping ``returned_at`` anyway would report a seat as having come
        back from work it was never sent on — a fabricated timestamp, which is
        this fund's oldest forbidden move."""
        from app.fund.events import EventType
        tid = _opened_id(client)
        self._append(store, EventType.TICKET_TRANSITIONED,
                     {"ticket_id": tid, "to": "returned", "actor": "cto",
                      "at": "2026-08-25T00:00:00Z"})
        row = _by_id(store)[tid]
        assert row["state"] == "filed"
        assert row.get("returned_at") is None
        assert [r["to"] for r in row["refused_transitions"]] == ["returned"]

    def test_a_link_event_with_an_unrecognised_kind_is_IGNORED(self, client,
                                                               store):
        """M6. The door refuses an unknown ``link_kind``; the fold must too,
        or a future producer's typo becomes a ``serves`` edge by falling
        through the else."""
        from app.fund.events import EventType
        a, b = _opened_id(client), _opened_id(client)
        self._append(store, EventType.TICKET_LINKED,
                     {"ticket_id": a, "link_kind": "blocks", "target_id": b,
                      "at": "2026-08-25T00:00:00Z"})
        row = _by_id(store)[a]
        assert row["parent_id"] is None
        assert "serves" not in row
        assert "links" not in row

    def test_a_TERMINAL_door_born_ticket_routes_to_NOBODY(self, client, store):
        """M10, and it is failure #3 wearing a new costume. A ticket that
        DECLARED ``next_actor: ceo`` and has since been declined must stop
        being the CEO's move — "executed, shown open" is the 16-row regression
        the CEO called out by name, and a terminal row still routing to him is
        exactly how it renders a decision control on a closed decision."""
        tid = _opened_id(client, next_actor="ceo")
        assert _by_id(store)[tid]["next_actor"] == "ceo"
        assert _transition(client, tid, "declined",
                           reason="not this quarter").status_code == 200
        row = _by_id(store)[tid]
        assert row["terminal"] is True
        assert row["next_actor"] == "nobody"
        assert row["next_actor_basis"] == "lifecycle"


# ============================================================================
# THE LAMP-CLOSE GAP — slice 2's stated acceptance (ticket d03c09b6)
# ============================================================================

class TestAChairBornDispatchCanBeClosed:
    def test_it_walks_in_flight_to_returned_to_done(self, client, store):
        """FAILURE #4 OF THE DESIGN'S OWN TABLE: *any dispatch exists that no
        legitimate event can close.* Eight chair-born dispatches were open with
        no close path at all. The ticket door is that path, and this is the
        test that fails if it disappears."""
        row = _by_id(store)[D_CHAIR_BORN]
        assert row["type"] == "dispatch" and row["state"] == "in_flight"

        assert _transition(client, D_CHAIR_BORN, "returned", actor="cto",
                           confirm=None).status_code == 200
        returned = _by_id(store)[D_CHAIR_BORN]
        assert returned["state"] == "returned"
        # THE CONSTITUTION'S MISSING MIDDLE STATE, with a real timestamp. The
        # legacy resolve path reports `returned_at: UNKNOWN` because no legacy
        # event carries it; this one does, and the basis says which.
        assert returned["returned_at"] is not None
        assert returned["returned_basis"] == "ticket_transition"

        r = _transition(client, D_CHAIR_BORN, "done",
                        citation="docs/reviews/the-artifact.md")
        assert r.status_code == 200, r.text
        done = _by_id(store)[D_CHAIR_BORN]
        assert done["state"] == "done" and done["terminal"] is True
        assert done["citation"] == "docs/reviews/the-artifact.md"
        assert done["next_actor"] == "nobody"

    def test_the_close_is_NOT_available_without_a_citation(self, client):
        _transition(client, D_CHAIR_BORN, "returned", actor="cto", confirm=None)
        assert _transition(client, D_CHAIR_BORN, "done").status_code == 422


# ============================================================================
# THE LEGACY FOLDS ARE UNTOUCHED — the D17 checklist, run not remembered
# ============================================================================

class TestTheLegacyFoldsAreUntouched:
    """A new event type is a lifecycle change until proven otherwise.

    Proven by CONSTRUCTION rather than by reading the switch statements: the
    same store folded with and without the highway's events must produce
    identical answers everywhere the desk reads.
    """

    @pytest.fixture()
    def busy(self, client, store):
        """One store, worked hard through every ticket door."""
        tid = _opened_id(client, next_actor="ceo", due_date="2026-09-01",
                         money_at_stake=500.0, reversibility="hard")
        _transition(client, tid, "approved")
        _transition(client, D_CHAIR_BORN, "returned", actor="cto", confirm=None)
        _transition(client, D_CHAIR_BORN, "done", citation="an artifact")
        client.post(f"/api/v1/fund/tickets/{tid}/link",
                    json={"link_kind": "serves", "target_id": D_CHAIR_BORN})
        return store

    def test_the_desk_view_is_byte_identical(self, busy):
        from app.fund.events import EventType
        ticket_types = {EventType.TICKET_OPENED.value,
                        EventType.TICKET_TRANSITIONED.value,
                        EventType.TICKET_LINKED.value,
                        EventType.TICKET_CONSUMED.value}
        without = _WritableStore(
            [e for e in busy.events
             if (getattr(getattr(e, "type", None), "value", None)
                 or (e.get("type") if isinstance(e, dict) else None))
             not in ticket_types])
        assert len(without.events) < len(busy.events), \
            "the control arm must actually be missing the ticket events"
        assert (desk.view(busy, deskstore=None, pending_orders=None)
                == desk.view(without, deskstore=None, pending_orders=None))

    def test_the_requests_fold_is_byte_identical(self, busy):
        assert desk._requests(busy) == desk._requests(_WritableStore(
            _legacy_events()))

    def test_no_ticket_event_lands_on_an_order_aggregate(self, busy):
        """``ORDER_ANNOTATION_EVENTS`` needs no fifth member — and this is the
        check that proves it rather than the comment that claims it."""
        assert not [e for e in busy.events
                    if getattr(e, "aggregate_type", None) == "order"]

    def test_every_ticket_event_lands_on_the_ticket_aggregate(self, busy):
        from app.fund.events import EventType
        ticket_types = {EventType.TICKET_OPENED.value,
                        EventType.TICKET_TRANSITIONED.value,
                        EventType.TICKET_LINKED.value}
        mine = [e for e in busy.events
                if getattr(getattr(e, "type", None), "value", None)
                in ticket_types]
        assert len(mine) == 5
        assert {e.aggregate_type for e in mine} == {"ticket"}


# ============================================================================
# THE CONSUMPTION RECEIPT — an event type with no producer, said out loud
# ============================================================================

class TestTicketConsumed:
    def test_it_is_a_RECEIPT_and_never_a_transition(self, client, store):
        """Folding consumption as a state change would close the loop
        automatically, and "the system stages, never appends" is the one rule
        this highway does not bend."""
        from app.fund.events import Event, EventType
        tid = _opened_id(client)
        store.append(Event(
            aggregate_id=tid, aggregate_type="ticket",
            type=EventType.TICKET_CONSUMED,
            # THE ACTOR GOES IN THE PAYLOAD, and this line is the specification
            # slice 5's producer must meet. Every adapter in this fold reads
            # `payload["actor"]`, never `Event.actor` — the legacy desk doors
            # write it to both and the fold has only ever read one. A producer
            # that set the Event field alone would fold as `actor: None` and
            # the receipt would say a lesson was consumed by nobody.
            payload={"ticket_id": tid, "consumed_by_dispatch": "run-builder-hw3",
                     "seat": "builder", "at": "2026-08-25T00:00:00Z",
                     "actor": "cto"},
            actor="cto"))
        row = _by_id(store)[tid]
        assert row["state"] == "filed"
        assert row["consumptions"] == [
            {"consumed_by_dispatch": "run-builder-hw3", "seat": "builder",
             "at": "2026-08-25T00:00:00Z", "actor": "cto"}]

    def test_the_fold_reads_the_PAYLOAD_actor_not_the_event_field(self, client,
                                                                  store):
        """The convention above, pinned so slice 5 cannot get it wrong quietly.
        This test exists because writing it caught the author out first."""
        from app.fund.events import Event, EventType
        tid = _opened_id(client)
        store.append(Event(
            aggregate_id=tid, aggregate_type="ticket",
            type=EventType.TICKET_CONSUMED,
            payload={"ticket_id": tid, "at": "2026-08-25T00:00:00Z"},
            actor="an-actor-only-on-the-event"))
        assert _by_id(store)[tid]["consumptions"][0]["actor"] is None

    def test_it_has_NO_door_in_this_slice(self):
        """Stated as a test rather than a comment so that adding one is a
        deliberate act. Slice 5's chair resolve pipeline is its producer; an
        unwired control is reported unwired, never implied done."""
        from app.api.v1 import fund as fundapi
        paths = {r.path for r in fundapi.router.routes}
        assert not [p for p in paths if "consum" in p]

    def test_a_receipt_against_an_unknown_id_is_a_PHANTOM_not_a_ticket(
            self, store):
        """The fold counts it and never mints a row from it — a ticket born
        from a phantom would launder the defect into a row."""
        from app.fund.events import Event, EventType
        store.append(Event(
            aggregate_id="nope", aggregate_type="ticket",
            type=EventType.TICKET_CONSUMED,
            payload={"ticket_id": "nope", "at": "2026-08-25T00:00:00Z"},
            actor="cto"))
        folded = _fold(store)
        assert [p["event"] for p in folded["phantom_events"]] == ["TicketConsumed"]
        assert "nope" not in {t["ticket_id"] for t in folded["tickets"]}


# ============================================================================
# THE OPEN DOOR DOES NOT OVERWRITE
# ============================================================================

class TestADuplicateOpenNeverOverwrites:
    def test_a_second_birth_on_one_id_is_recorded_and_refused(self, client,
                                                              store):
        """The door mints a fresh uuid4 so this cannot arrive from it. It is
        recorded rather than dropped because a second birth on one id is a fact
        about the record, and a silent overwrite would let a later event
        rewrite an earlier ticket's subject and filer."""
        from app.fund.events import Event, EventType
        tid = _opened_id(client, subject="the original")
        store.append(Event(
            aggregate_id=tid, aggregate_type="ticket",
            type=EventType.TICKET_OPENED,
            payload={"ticket_id": tid, "type": "ask", "subject": "the impostor",
                     "at": "2026-08-25T00:00:00Z", "actor": "someone else"},
            actor="someone else"))
        row = _by_id(store)[tid]
        assert row["subject"] == "the original"
        assert [r["basis"] for r in row["refused_transitions"]] == \
            ["duplicate-open"]


# ============================================================================
# BOUNDARY TABLES — a mechanical breadth pass. Every inequality and every
# closed vocabulary in the doors, probed AT its edge rather than well inside
# or well outside it. Each parametrized case states in a comment which side
# of the boundary it sits on, because a boundary test that does not say so is
# indistinguishable from an arbitrary one six months later.
#
# A SHARED-WORD HAZARD FOUND WHILE WRITING THESE, reported rather than
# silently worked around (both are reproducible on this file's own doors):
#
#   1. ``"challenge"`` is live in TWO unrelated refusals. It is a member of
#      ``OPENABLE_TYPES``, so it appears in the open door's 422 ``allowed``
#      list whenever an unknown ``type`` is refused (e.g. filing
#      ``type="lesson"``) — see ``TestTheOpenDoorValidates`` above. It is
#      ALSO the word the transition door's 409 ``note`` uses to point a
#      terminal-reopen refusal at its escape hatch (``TestLegality
#      .test_a_terminal_ticket_cannot_be_REOPENED``). A bare
#      ``"challenge" in str(response.json())`` cannot tell "you named a type
#      this fold does not open" from "this ticket is terminal, file a
#      challenge instead" — the two are different doors, different status
#      codes (422 vs 409), and different reasons. Every existing assertion on
#      this word already keys on the specific field (``detail["note"]``
#      vs ``detail["allowed"]``), which is what keeps it safe; a future test
#      that loosens that to a whole-body substring check would not be.
#   2. ``"decision_ref"`` is live in TWO unrelated vocabularies. It is a
#      ``TERMINAL_REQUIREMENTS`` field name (the ``merged`` terminal's
#      required record) and, separately, a ``LINK_KINDS`` value (what
#      ``POST .../link`` may be asked to record). A refusal naming the first
#      ("a 'merged' transition must carry 'decision_ref'") and a link body
#      naming the second (``{"link_kind": "decision_ref", ...}``) share the
#      token even though one is "you forgot to cite the canonical row" and
#      the other is "here is the edge to record" — different endpoints,
#      different meanings, same eight characters.
#   3. THE MILDER, STRUCTURAL VERSION: the word ``"unknown"`` leads FIVE
#      distinct 422 refusals in these doors (``unknown ticket type``,
#      ``unknown next_actor``, ``unknown reversibility``, ``unknown ticket
#      state``, ``unknown link_kind``). None of the tests in this file key on
#      that word alone — every one asserts the specific field name instead
#      (``where in str(detail)`` with ``where`` set to ``"type"``,
#      ``"reversibility"``, and so on) — which is exactly the discipline that
#      keeps five refusals that share a leading word from being confused with
#      one another. Named here so the next test written against these doors
#      inherits the reason rather than rediscovering it.
# ============================================================================

class TestMoneyAtStakeBoundary:
    """The door's one inequality: ``money_at_stake < 0`` refuses, so the
    boundary is zero itself, not some small positive epsilon."""

    @pytest.mark.parametrize("value,accepted", [
        (0.0, True),     # the boundary itself: `0.0 < 0` is False -> ACCEPTED
        (-0.0, True),    # IEEE negative zero: `-0.0 < 0` is ALSO False -> ACCEPTED
        (-0.01, False),  # one cent on the negative side -> REFUSED
        (1e9, True),     # a large positive value, far from the boundary -> ACCEPTED
    ])
    def test_the_negative_boundary(self, client, store, value, accepted):
        r = _open(client, money_at_stake=value)
        if accepted:
            assert r.status_code == 200, r.text
            tid = r.json()["ticket_id"]
            assert _by_id(store)[tid]["money_at_stake"] == value
        else:
            assert r.status_code == 422
            # Structured field, not prose — `money_at_stake` is the one
            # numeric key this refusal echoes back, so it cannot be
            # satisfied by a different validation's message.
            assert r.json()["detail"]["money_at_stake"] == value


class TestDueDateBoundary:
    """``due_date`` takes exactly one check — ``strptime`` on the STRIPPED
    string against ``%Y-%m-%d`` — and nothing here says a due date must be in
    the future, so a past date is on the ACCEPTED side same as a future one."""

    @pytest.mark.parametrize("value", [
        "0001-01-01",  # datetime.MINYEAR — the shortest representable calendar year
        "9999-12-31",  # datetime.MAXYEAR — the longest representable calendar year
        "2028-02-29",  # a leap day that EXISTS: 2028 % 4 == 0
        "2020-01-01",  # a date already in the past -> still ACCEPTED
    ])
    def test_accepted_at_the_edge(self, client, store, value):
        tid = _opened_id(client, due_date=value)
        assert _by_id(store)[tid]["due_date"] == value

    def test_a_leap_day_that_does_not_exist_is_refused(self, client, store):
        """2027 is not divisible by 4 — Feb 29 2027 never happens on any
        calendar, so `strptime` refuses it the same way it refuses
        `2026-02-31` above."""
        before = len(store.events)
        r = _open(client, due_date="2027-02-29")
        assert r.status_code == 422
        assert r.json()["detail"]["due_date"] == "2027-02-29"
        assert len(store.events) == before

    def test_a_trailing_space_is_STRIPPED_not_refused(self, client, store):
        """The door validates ``req.due_date.strip()`` (fund.py) and then
        stores ``(req.due_date or "").strip() or None`` — both reads strip,
        so a trailing space is accepted AND the fold holds the trimmed date,
        never the raw string with the space still on it."""
        tid = _opened_id(client, due_date="2026-12-31 ")
        assert _by_id(store)[tid]["due_date"] == "2026-12-31"


class TestMinIdPrefixBoundary:
    """``_refuse_unknown_ticket`` expands a prefix into ``did_you_mean`` only
    at or above ``deskengine.MIN_ID_PREFIX`` (read here, never restated). The
    two existing phantom-guard tests each pin one side of this line
    (``test_an_eight_char_shorthand_is_refused_WITH_the_expansion`` and
    ``test_a_prefix_shorter_than_the_minimum_offers_no_expansion``); this
    parametrizes all three lengths so the transition is one table rather than
    two separate tests a reader has to align by hand."""

    @pytest.mark.parametrize("delta,expect_expansion", [
        (-1, False),  # MIN_ID_PREFIX - 1: one below the floor -> no expansion
        (0, True),    # MIN_ID_PREFIX exactly: the floor itself -> expansion offered
        (1, True),    # MIN_ID_PREFIX + 1: one above the floor -> expansion offered
    ])
    def test_the_expansion_floor(self, client, delta, expect_expansion):
        tid = _opened_id(client)
        prefix = tid[:MIN_ID_PREFIX + delta]
        r = _transition(client, prefix, "in_flight")
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == ([tid] if expect_expansion
                                                       else [])


class TestSubjectBoundary:
    """``subject`` takes one check — ``.strip()`` must be non-empty — and no
    upper bound anywhere in this door. Empty and whitespace-only both land on
    the refused side of that one check; a single character and a very long
    string both clear it because nothing here rejects on length."""

    @pytest.mark.parametrize("subject", ["", "\t\n "])
    def test_empty_or_whitespace_only_is_refused(self, client, store, subject):
        before = len(store.events)
        r = _open(client, subject=subject)
        assert r.status_code == 422
        # Structured field: the door's own `error` string, not a substring
        # search over the whole body.
        assert r.json()["detail"]["error"] == "a ticket needs a subject"
        assert len(store.events) == before

    def test_a_single_character_is_accepted(self, client, store):
        tid = _opened_id(client, subject="x")
        assert _by_id(store)[tid]["subject"] == "x"

    def test_a_very_long_subject_is_accepted(self, client, store):
        """No max length is enforced anywhere in ``TicketOpen`` or the door —
        a 10,000-character subject is exactly as legal as a one-character
        one, because nothing here checks."""
        subject = "x" * 10_000
        tid = _opened_id(client, subject=subject)
        assert _by_id(store)[tid]["subject"] == subject


class TestConfirmEchoBoundary:
    """The approval guard compares ``confirm`` against ``target_id[:8]`` by
    EXACT string equality (``_guard_approval``, fund.py) — not a prefix or
    ``startswith`` check. That distinction is the whole point of this table:
    ``target_id[:8]`` is itself a PREFIX of ``target_id[:9]``, so a guard
    written as a prefix comparison would wrongly accept nine characters. This
    one does not, because it compares for equality, not containment."""

    def test_seven_chars_is_refused(self, client):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", confirm=tid[:7])
        assert r.status_code == 403

    def test_eight_chars_is_accepted(self, client):
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", confirm=tid[:8])
        assert r.status_code == 200, r.text

    def test_nine_chars_is_refused(self, client):
        """THE NEAR MISS: ``tid[:8]`` is a PREFIX of ``tid[:9]``. Refused
        here proves the guard is doing exact-equality (``!=``) rather than
        `str.startswith`, which would have let this one slip through."""
        tid = _opened_id(client)
        r = _transition(client, tid, "accepted", confirm=tid[:9])
        assert r.status_code == 403
