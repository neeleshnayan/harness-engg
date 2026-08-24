"""ONE DECISION, ONE ROW — slice 3 of the ticket highway.

THE INCIDENT THESE TESTS ARE NAMED FOR. On the live record, 2026-08-24, the R39
approval decision was decided **eight times on one identity** — eight
``DeskRecommendationDecided`` events at seq 1122, 1123, 1195, 1201, 1202, 1203,
1253, 1281, every one naming ``run-triage7-decisions#1`` with status
``accepted`` — while the same subject was separately re-presented across twelve
distinct identities carrying 23 decision events between them. Measured with
``scripts/instruments/hw3/r39_census.py --subject R39``; the instrument REFUSES
on an empty population, and its ``--null`` arm reports zero over a stated
domain of 1,000 events.

``TestTheR39Replay`` is the slice's stated acceptance criterion executed: the
same eight presentations through the ticket door produce ONE canonical row and
seven refusals, each carrying its lineage and each appending an
``ApprovalRefused`` event so the riskofficer can see it in ``/fund/events``
rather than in somebody's terminal.

WHAT THESE TESTS DELIBERATELY DO NOT CLAIM. The guard is wired to the TICKET
door only. The legacy ``decide_recommendation`` door — where all eight of those
events actually landed — is untouched, and ``TestTheLegacyDoorIsUntouched``
pins that rather than leaving it to be assumed: this slice does not change the
behaviour of any path the CEO's desk posts to today.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.fund import ticketguard, tickets


# ---------------------------------------------------------------- fixtures --

class _WriteStore:
    """An event store this test OWNS, and which records what was appended.

    The house rule since D39: an endpoint test that WRITES must own a store and
    monkeypatch ``fundapi._store``. Two probe events written into the
    process-wide store once turned 92 unrelated tests red while every one of
    them passed in isolation.
    """

    def __init__(self, events=None):
        self.events = list(events or [])
        self.appended = []

    def append(self, e):
        self.appended.append(e)
        self.events.append({"type": e.type, "payload": e.payload,
                            "actor": e.actor})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]

    def of_type(self, name):
        return [e for e in self.appended
                if getattr(e.type, "value", e.type) == name]


@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    store = _WriteStore()
    monkeypatch.setattr(fundapi, "_store", store)
    # No Postgres: the recommendation leg is UNKNOWN and the ask/dispatch legs
    # are real, which is the degradation `tickets_view` already documents. The
    # door tests are about ticket-native rows, so nothing here needs a run.
    monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store = store
    return c


def _open(client, **kw):
    body = {"type": "ask", "subject": "approve R39 as one sequence",
            "filed_for": "pm", "actor": "cto"}
    body.update(kw)
    r = client.post("/api/v1/fund/tickets", json=body)
    assert r.status_code == 200, r.text
    return r.json()["ticket_id"]


def _transition(client, tid, to, **kw):
    body = {"to": to, "actor": "ceo", "confirm": tid[:8]}
    body.update(kw)
    return client.post(f"/api/v1/fund/tickets/{tid}/transition", json=body)


def _ticket(state="accepted", *, transitions=None, ticket_id="T-1", **extra):
    """A fold-shaped ticket row, hand-built, for the pure-guard tests."""
    t = {"ticket_id": ticket_id, "state": state,
         "transitions": transitions if transitions is not None else
         [{"from": None, "to": "filed", "at": "2026-08-24T00:00:00Z",
           "actor": "cto", "basis": "birth"},
          {"from": "filed", "to": state, "at": "2026-08-24T01:00:00Z",
           "actor": "ceo", "basis": "decision"}]}
    t.update(extra)
    return t


# ============================================================================
# THE ACCEPTANCE CRITERION
# ============================================================================

class TestTheR39Replay:
    """Slice 3's stated acceptance, executed against the real cardinality."""

    def test_eight_presentations_produce_one_row_and_seven_refusals(self, client):
        """R39, seq 1122-1281: eight acceptances of one decision.

        The defect this pins: before slice 3 nothing anywhere held "this has
        already been decided" as a fact, so the second through eighth
        presentations were indistinguishable from the first at every door.
        """
        tid = _open(client)
        first = _transition(client, tid, "accepted")
        assert first.status_code == 200, first.text

        refusals = [_transition(client, tid, "accepted") for _ in range(7)]
        assert [r.status_code for r in refusals] == [409] * 7

        # ONE canonical row, not eight.
        rows = client.get("/api/v1/fund/tickets?limit=5000").json()["tickets"]
        mine = [r for r in rows if r["ticket_id"] == tid]
        assert len(mine) == 1
        assert mine[0]["state"] == "accepted"
        assert mine[0]["decided"] is True
        # ONE applied decision, however many times it was asked for. The
        # refused attempts are NOT counted as decisions — a rejected event
        # locking a row would be the guard eating its own tail.
        assert mine[0]["decision_count"] == 1

    def test_every_refusal_carries_the_lineage_and_the_two_legal_moves(self, client):
        tid = _open(client)
        assert _transition(client, tid, "accepted").status_code == 200
        d = _transition(client, tid, "accepted").json()["detail"]
        assert d["hint"] == "bare_representation"
        assert d["canonical_ticket_id"] == tid
        assert d["decided_state"] == "accepted"
        assert d["decided_at"]
        # The two escapes are NAMED on the refusal, because a refusal that does
        # not say what to do instead is a puzzle.
        assert "merged" in d["detail"] and "superseded" in d["detail"]

    def test_each_refusal_is_audible_in_the_event_log(self, client):
        """'Audible' means IN THE EVENT LOG, never logger.warning.

        The riskofficer audits refusals from ``/fund/events``. Seven silent
        409s would be seven refusals nobody whose job is auditing them can see.
        """
        tid = _open(client)
        _transition(client, tid, "accepted")
        before = len(client.store.of_type("ApprovalRefused"))
        for _ in range(7):
            _transition(client, tid, "accepted")
        after = client.store.of_type("ApprovalRefused")
        assert len(after) - before == 7
        p = after[-1].payload
        assert p["kind"] == "ticket" and p["target_id"] == tid
        assert p["canonical_ticket_id"] == tid
        assert p["attempted"] == "accepted"
        assert "decision_ref_v1" in p["guard"]

    def test_the_canonical_row_can_still_be_closed(self, client):
        """CLOSING MUST NEVER BE HARDER THAN OPENING.

        A guard that refused every transition on a decided ticket would strand
        the whole population open — the failure ``ADVANCING_REC_STATUSES``
        excludes its four terminals to avoid.
        """
        tid = _open(client)
        _transition(client, tid, "accepted")
        r = _transition(client, tid, "done", citation="docs/pm/PM_R39_PLAN.md")
        assert r.status_code == 200, r.text
        rows = client.get("/api/v1/fund/tickets?limit=5000").json()["tickets"]
        row = next(r for r in rows if r["ticket_id"] == tid)
        assert row["state"] == "done"
        # THE DECISION SURVIVES THE STATE MOVING ON (§1.5). `state` is `done`;
        # `decided` is still true and still names what was decided.
        assert row["decided"] is True and row["decided_state"] == "done"

    def test_a_re_presentation_may_be_merged_into_the_canonical_row(self, client):
        """The first legal escape: same decision, cite it."""
        canonical = _open(client)
        _transition(client, canonical, "accepted")
        dup = _open(client, subject="approve R39 (re-filed by triage7)")
        _transition(client, dup, "accepted")
        r = _transition(client, dup, "merged", decision_ref=canonical)
        assert r.status_code == 200, r.text
        rows = client.get("/api/v1/fund/tickets?limit=5000").json()["tickets"]
        row = next(x for x in rows if x["ticket_id"] == dup)
        assert row["state"] == "merged"
        assert row["canonical_ticket_id"] == canonical


# ============================================================================
# THE RULE ITSELF — pure, no door
# ============================================================================

class TestTheDecisionRefRule:
    def test_an_undecided_ticket_is_not_refused(self):
        t = _ticket("filed", transitions=[
            {"from": None, "to": "filed", "at": "x", "actor": "cto",
             "basis": "birth"}])
        assert ticketguard.check_representation(t, to="accepted") is None

    def test_a_decided_ticket_presented_bare_is_refused(self):
        r = ticketguard.check_representation(_ticket("accepted"), to="accepted")
        assert r is not None and r["hint"] == "bare_representation"

    def test_a_reference_that_does_not_match_its_terminal_is_refused(self):
        """The worst available shape: it LOOKS like compliance.

        Supplying ``decision_ref`` while asking for a second ``accepted``
        produces a second live row holding the same decision — the exact
        outcome the reference was supposed to prevent.
        """
        r = ticketguard.check_representation(_ticket("accepted"), to="accepted",
                                             decision_ref="T-9")
        assert r is not None and r["hint"] == "wrong_terminal_for_reference"

    @pytest.mark.parametrize("to,kw", [
        ("merged", {"decision_ref": "T-9"}),
        ("superseded", {"superseder_ref": "T-9"}),
        ("done", {}),
        ("declined", {}),
        ("in_flight", {}),
        ("returned", {}),
    ])
    def test_the_transitions_this_guard_does_not_touch(self, to, kw):
        """Everything except a second `approved`/`accepted` passes.

        Named one by one rather than asserted as a set difference: a set
        difference recomputes the production constant and would agree with it
        however wrong it became.
        """
        assert ticketguard.check_representation(_ticket("accepted"), to=to,
                                                **kw) is None

    def test_a_decline_after_an_acceptance_is_a_reversal_not_a_re_presentation(self):
        """§1.2's ``accepted --> declined : human reverses before execution``.

        Refusing it bare would make a wrongly-accepted ticket harder to
        withdraw than it was to accept.
        """
        assert ticketguard.check_representation(_ticket("accepted"),
                                                to="declined") is None

    def test_a_refused_attempt_is_not_a_prior_decision(self):
        """A rejected event must not be able to lock a row.

        ``refused_transitions`` records that something was ATTEMPTED and
        correctly stopped; counting it as a decision would let a caller freeze
        a ticket by aiming an illegal transition at it.
        """
        t = _ticket("filed", transitions=[
            {"from": None, "to": "filed", "at": "x", "actor": "cto",
             "basis": "birth"}])
        t["refused_transitions"] = [
            {"from": "filed", "to": "accepted", "at": "y", "actor": "someone",
             "basis": "decision", "why": "..."}]
        assert ticketguard.check_representation(t, to="accepted") is None

    def test_the_birth_row_of_a_ticket_born_decided_is_not_a_decision(self):
        """A legacy recommendation folded straight into ``accepted``.

        Its birth transition writes ``basis: "birth"``. Reading that as a prior
        decision would refuse the FIRST real decision on every legacy row.
        """
        t = _ticket("accepted", transitions=[
            {"from": None, "to": "accepted", "at": "x", "actor": "pm",
             "basis": "birth"}])
        assert ticketguard.lineage(t)["decided"] is False
        assert ticketguard.check_representation(t, to="accepted") is None

    def test_the_guarded_set_is_read_from_the_module_not_restated(self,
                                                                 monkeypatch):
        """MOVE THE VALUE, do not compare to it.

        An assertion that the guard equals ``REDECISION_GUARDED`` cannot
        distinguish a read from a hardcoded duplicate that happens to agree.
        Moving ``declined`` INTO the guarded set must change the answer.
        """
        assert ticketguard.check_representation(_ticket("accepted"),
                                                to="declined") is None
        monkeypatch.setattr(ticketguard, "REDECISION_GUARDED",
                            ("approved", "accepted", "declined"))
        assert ticketguard.check_representation(_ticket("accepted"),
                                                to="declined") is not None

    def test_decision_transitions_is_read_from_tickets_not_copied(self,
                                                                 monkeypatch):
        """The same move, one layer down: ``tickets.DECISION_TRANSITIONS``."""
        t = _ticket("in_flight", transitions=[
            {"from": None, "to": "filed", "at": "x", "actor": "c",
             "basis": "birth"},
            {"from": "filed", "to": "in_flight", "at": "y", "actor": "c",
             "basis": "dispatch"}])
        assert ticketguard.lineage(t)["decided"] is False
        monkeypatch.setattr(tickets, "DECISION_TRANSITIONS",
                            ("in_flight",) + tickets.DECISION_TRANSITIONS)
        assert ticketguard.lineage(t)["decided"] is True


class TestTheLineage:
    def test_it_reports_its_basis_when_there_is_no_transition_list(self):
        """Absence is never zero and never silent."""
        assert ticketguard.lineage({"ticket_id": "T"})["basis"] == "unknown"

    def test_canonical_is_the_decision_ref_when_the_row_was_merged(self):
        t = _ticket("merged", decision_ref="CANON")
        assert ticketguard.lineage(t)["canonical_ticket_id"] == "CANON"

    def test_canonical_is_itself_when_it_was_not(self):
        assert ticketguard.lineage(_ticket())["canonical_ticket_id"] == "T-1"

    def test_the_last_decision_wins_the_summary_fields(self):
        t = _ticket("done", transitions=[
            {"from": None, "to": "filed", "at": "a", "actor": "c",
             "basis": "birth"},
            {"from": "filed", "to": "accepted", "at": "b", "actor": "ceo",
             "basis": "decision"},
            {"from": "accepted", "to": "done", "at": "c", "actor": "cto",
             "basis": "review-close"}])
        lin = ticketguard.lineage(t)
        assert lin["decision_count"] == 2
        assert lin["decided_state"] == "done" and lin["decided_by"] == "cto"


# ============================================================================
# THE TERMINALS
# ============================================================================

class TestTheTerminalRequirements:
    @pytest.mark.parametrize("to,field", [
        ("done", "citation"), ("declined", "reason"),
        ("superseded", "superseder_ref"), ("merged", "decision_ref")])
    def test_each_terminal_refuses_without_its_own_field(self, to, field):
        assert ticketguard.terminal_requirement(to, {}) is not None
        assert ticketguard.terminal_requirement(to, {field: "x"}) is None

    def test_whitespace_is_not_a_citation(self):
        assert ticketguard.terminal_requirement("done", {"citation": "   "})

    def test_a_working_state_needs_nothing(self):
        for s in tickets.WORKING_STATES:
            assert ticketguard.terminal_requirement(s, {}) is None

    def test_expired_is_refused_while_no_aging_policy_exists(self):
        assert tickets.AGING_POLICY_VERSION is None
        why = ticketguard.terminal_requirement("expired", {})
        assert why is not None and "AGING_POLICY_VERSION" in why

    def test_expired_is_admitted_the_moment_a_policy_is_ratified(self,
                                                                monkeypatch):
        """MOVE THE VALUE. The refusal must be READ from the constant.

        A test that only asserts ``expired`` is refused today cannot tell a
        policy check from an unconditional ``return "no"``.
        """
        monkeypatch.setattr(tickets, "AGING_POLICY_VERSION", "aging-v1")
        assert ticketguard.terminal_requirement("expired", {}) is None

    def test_the_requirements_table_is_read_from_tickets(self, monkeypatch):
        monkeypatch.setitem(tickets.TERMINAL_REQUIREMENTS, "done",
                            ("reason", "something else entirely"))
        assert ticketguard.terminal_requirement("done", {"citation": "x"})
        assert ticketguard.terminal_requirement("done", {"reason": "x"}) is None


class TestTheMergeTarget:
    def test_a_row_cannot_merge_into_itself(self):
        assert ticketguard.merge_target_error("T", "T", {"T"}) is not None

    def test_a_reference_to_a_ticket_nobody_has_seen_is_refused(self):
        why = ticketguard.merge_target_error("T", "GHOST", {"T", "U"})
        assert why is not None and "GHOST" in why

    def test_a_real_reference_passes(self):
        assert ticketguard.merge_target_error("T", "U", {"T", "U"}) is None

    def test_an_absent_reference_is_left_to_the_terminal_requirement(self):
        """Two guards, one message. Returning an error here as well would give
        the caller two different sentences for one missing field."""
        assert ticketguard.merge_target_error("T", None, {"T"}) is None


# ============================================================================
# THE DOOR
# ============================================================================

class TestTheTransitionDoor:
    def test_an_unknown_ticket_is_404_with_did_you_mean(self, client):
        tid = _open(client)
        r = _transition(client, tid[:8], "accepted")
        assert r.status_code == 404
        d = r.json()["detail"]
        assert d["did_you_mean"] == [tid]
        assert d["folds_consulted"] == ["tickets"]

    def test_a_decision_transition_takes_the_approval_channel_guard(self, client):
        tid = _open(client)
        r = client.post(f"/api/v1/fund/tickets/{tid}/transition",
                        json={"to": "accepted", "actor": "ceo"})
        assert r.status_code == 403
        assert "confirm echo" in r.json()["detail"]

    def test_a_non_decision_transition_does_not(self, client):
        """Firing a dispatch and recording a return are things the chair DOES
        and then writes down, not permissions it grants itself."""
        tid = _open(client)
        r = client.post(f"/api/v1/fund/tickets/{tid}/transition",
                        json={"to": "in_flight", "actor": "cto"})
        assert r.status_code == 200, r.text

    def test_an_unknown_target_state_is_422_not_a_silent_no_op(self, client):
        tid = _open(client)
        r = _transition(client, tid, "dine")
        assert r.status_code == 422
        assert r.json()["detail"]["allowed"] == list(tickets.TICKET_STATES)

    def test_an_illegal_transition_is_refused_at_the_door(self, client):
        """``filed`` does not go straight to ``returned``.

        Refused here rather than accepted-and-silently-not-applied: a 200
        followed by a transition the fold records as refused is the shape where
        the caller believes it acted.
        """
        tid = _open(client)
        r = client.post(f"/api/v1/fund/tickets/{tid}/transition",
                        json={"to": "returned", "actor": "cto"})
        assert r.status_code == 409
        assert r.json()["detail"]["allowed_from"] == ["in_flight"]

    def test_a_terminal_without_its_field_is_422(self, client):
        tid = _open(client)
        assert _transition(client, tid, "done").status_code == 422

    def test_expired_is_refused_at_the_door(self, client):
        tid = _open(client)
        r = _transition(client, tid, "expired")
        assert r.status_code == 422
        assert "AGING_POLICY_VERSION" in r.json()["detail"]

    def test_a_merge_into_a_ghost_is_refused(self, client):
        tid = _open(client)
        ghost = "99999999-9999-4999-8999-999999999999"
        r = _transition(client, tid, "merged", decision_ref=ghost)
        assert r.status_code == 422
        # SHARED-WORD AUDIT: the phrase must be reachable ONLY by this branch.
        # "refused" and "merged" appear in the terminal-requirement message
        # too, so matching on either would pass for the wrong reason.
        detail = r.json()["detail"]
        assert "names no ticket this fold has ever seen" in detail
        assert ghost in detail

    def test_the_transition_records_whether_each_check_ran(self, client):
        """`false` means the check was SKIPPED, never 'nothing was found'."""
        tid = _open(client)
        b = _transition(client, tid, "accepted").json()
        assert b["fold_readable"] is True
        assert b["supersession_readable"] is None
        assert "no legacy ref" in b["supersession_basis"]

    def test_the_door_appends_exactly_one_event_per_accepted_transition(self,
                                                                       client):
        tid = _open(client)
        before = len(client.store.of_type("TicketTransitioned"))
        _transition(client, tid, "accepted")
        assert len(client.store.of_type("TicketTransitioned")) - before == 1

    def test_a_refused_transition_appends_no_TicketTransitioned(self, client):
        tid = _open(client)
        _transition(client, tid, "accepted")
        before = len(client.store.of_type("TicketTransitioned"))
        _transition(client, tid, "accepted")
        assert len(client.store.of_type("TicketTransitioned")) == before


class TestTheOpenDoor:
    def test_it_mints_a_full_uuid_and_never_takes_one(self, client):
        import uuid as _uuid
        tid = _open(client)
        assert _uuid.UUID(tid).version == 4
        # An id supplied by the caller is IGNORED, not honoured: the 8-char
        # prefix habit is what rotted 54 of 56 linkages.
        other = _open(client, ticket_id="1c53589f")
        assert other != "1c53589f"

    def test_an_unopenable_type_is_refused(self, client):
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "sandwich", "subject": "x"})
        assert r.status_code == 422
        assert r.json()["detail"]["allowed"] == list(tickets.OPENABLE_TYPES)

    def test_a_blank_subject_is_refused(self, client):
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "ask", "subject": "   "})
        assert r.status_code == 422

    def test_an_unknown_reversibility_is_refused(self, client):
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "ask", "subject": "s",
                              "reversibility": "maybe"})
        assert r.status_code == 422

    def test_an_unknown_next_actor_is_refused_from_desks_own_vocabulary(
            self, client, monkeypatch):
        """READ from ``desk.NEXT_ACTORS``. Moving the vocabulary must move the
        door — two answers to 'whose move is it' is the defect the highway
        exists to stop multiplying."""
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "ask", "subject": "s",
                              "next_actor": "the-cat"})
        assert r.status_code == 422
        from app.fund import desk
        monkeypatch.setattr(desk, "NEXT_ACTORS", desk.NEXT_ACTORS + ("the-cat",))
        r = client.post("/api/v1/fund/tickets",
                        json={"type": "ask", "subject": "s",
                              "next_actor": "the-cat"})
        assert r.status_code == 200, r.text


class TestTheLinkDoor:
    def test_both_ends_are_guarded(self, client):
        a = _open(client)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "parent",
                              "target_id": "99999999-9999-4999-8999-999999999999"})
        assert r.status_code == 404

    def test_a_self_link_is_refused(self, client):
        a = _open(client)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "parent", "target_id": a})
        assert r.status_code == 422

    def test_an_unknown_link_kind_is_refused(self, client):
        a, b = _open(client), _open(client)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "vibes", "target_id": b})
        assert r.status_code == 422

    def test_a_decision_ref_link_lands_on_the_fold(self, client):
        a, b = _open(client), _open(client)
        r = client.post(f"/api/v1/fund/tickets/{a}/link",
                        json={"link_kind": "decision_ref", "target_id": b})
        assert r.status_code == 200, r.text
        rows = client.get("/api/v1/fund/tickets?limit=5000").json()["tickets"]
        row = next(x for x in rows if x["ticket_id"] == a)
        assert row["canonical_ticket_id"] == b


# ============================================================================
# WHAT THIS SLICE DOES NOT CHANGE
# ============================================================================

class TestTheLegacyDoorIsUntouched:
    def test_decide_recommendation_does_not_consult_this_guard(self):
        """The eight R39 events landed HERE, and this slice does not touch it.

        Wiring the guard into a live approval-adjacent path the CEO's desk
        posts to today is a human decision with the numbers in front of it, not
        a slice's side effect. Asserted rather than assumed, so that the day
        somebody does wire it, this test is the thing that says so out loud.
        """
        import inspect

        from app.api.v1 import fund as fundapi
        src = inspect.getsource(fundapi.decide_recommendation)
        assert "ticketguard" not in src
        assert "check_representation" not in src
