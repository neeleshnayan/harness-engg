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

    def test_a_ticket_cannot_link_to_itself(self, client, store):
        a = _opened_id(client)
        before = len(store.events)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "parent", "target_id": a})
        assert r.status_code == 422
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
