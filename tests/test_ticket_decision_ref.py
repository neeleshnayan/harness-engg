"""ONE DECISION, ONE ROW — slice 3 of the ticket highway.

THE INCIDENT THESE TESTS ARE NAMED FOR. On the live record, 2026-08-24, the R39
approval decision was decided **eight times on one identity** — eight
``DeskRecommendationDecided`` events at seq 1122, 1123, 1195, 1201, 1202, 1203,
1253, 1281, every one naming ``run-triage7-decisions#1`` with status
``accepted`` — while the same subject was separately re-presented across a
dozen-odd distinct identities. Measured with ``scripts/instruments/hw3/
r39_census.py --subject R39``; the instrument REFUSES on an empty population,
and its ``--null`` arm reports zero over a stated window of 1,000 events with
``covers_whole_log: false`` beside it.

THE EIGHT SEQS ARE FIXED HISTORY AND ARE SAFE TO QUOTE. The re-presentation
totals are NOT: two readings an hour apart the same day gave 23-over-12 and
then 24-over-13. Nothing in this file asserts either, and nothing should — a
test that pinned a growing population would be measuring the desk's traffic.

``TestTheR39Replay`` is the slice's stated acceptance criterion executed: the
same eight presentations through the ticket door produce ONE canonical row and
seven refusals, each carrying its lineage and each appending an
``ApprovalRefused`` event so the riskofficer can see it in ``/fund/events``
rather than in somebody's terminal.

WHAT THESE TESTS COVER, AND WHERE THE REST LIVES. This file is the TICKET
door's rule (``check_representation``). The legacy ``decide_recommendation``
door — where all eight of those events actually landed — was wired on
2026-08-24 on the CEO's decision, with the NARROWER rule
(``check_redecision``): it refuses only a status the row already holds, so
every progression passes. Its acceptance tests are in
``tests/test_legacy_redecision_guard.py``; ``TestTheLegacyDoorIsWired`` below
pins that the two doors keep two rules and do not get tidied into one.
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
        Taking ``approved`` OUT of the guarded set must change the answer for
        a ticket whose prior decision WAS ``approved``.
        """
        already_approved = _ticket("approved")
        assert ticketguard.check_representation(already_approved,
                                                to="approved") is not None
        monkeypatch.setattr(ticketguard, "REDECISION_GUARDED", ("accepted",))
        assert ticketguard.check_representation(already_approved,
                                                to="approved") is None

    def test_the_ORDINARY_LIFECYCLE_IS_NOT_REFUSED(self):
        """THE DEFECT I WROTE AND CAUGHT IN THE READ-THROUGH, pinned.

        ``filed -> approved -> in_flight -> returned -> accepted`` carries TWO
        legitimate decisions: the CEO blessing the ask, and a human deciding
        yes on the output. My first version refused any guarded transition on a
        ticket that had ever been decided, which would have refused the
        ``accepted`` at the end of every ticket the CEO ever approved. It
        passed 57 tests, because not one of them walked the whole lifecycle.
        """
        t = _ticket("returned", transitions=[
            {"from": None, "to": "filed", "at": "a", "actor": "cto",
             "basis": "birth"},
            {"from": "filed", "to": "approved", "at": "b", "actor": "ceo",
             "basis": "decision"},
            {"from": "approved", "to": "in_flight", "at": "c", "actor": "cto",
             "basis": "dispatch"},
            {"from": "in_flight", "to": "returned", "at": "d", "actor": "cto",
             "basis": "transition"}])
        assert ticketguard.lineage(t)["decided"] is True
        assert ticketguard.check_representation(t, to="accepted") is None
        # And the thing it DOES catch on the same ticket: a second `approved`.
        r = ticketguard.check_representation(t, to="approved")
        assert r is not None and r["prior_same_state"] == 1

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

class TestTheTerminalRequirementsMovedOut:
    """SIX TESTS DELETED HERE, and the deletion is the point.

    They exercised ``ticketguard.terminal_requirement`` — a pure
    re-implementation of §1.2's terminal table that NOTHING CALLED. Slice 2's
    ``ticket_transition`` had landed its own inline version reading the same
    two constants, and my own door (which would have called mine) was deleted
    when the two slices merged. A green test class over an uncalled control is
    worse than no class at all: it reads, from the outside, exactly like a door
    that is guarded.

    ``tests/test_tickets_doors.py::TestTerminalRequirements`` is where that
    rule is tested, against the door that enforces it. This class exists only
    so the removal is a written act rather than a silent shrink in the count.
    """

    def test_the_rule_is_tested_where_it_is_ENFORCED(self):
        from app.fund import ticketguard
        assert not hasattr(ticketguard, "terminal_requirement"),             ("if this function comes back, wire it to a door in the same "
             "commit — an uncalled control is the thing this class records")



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
# WHAT THIS FILE DELIBERATELY DOES NOT RE-TEST
# ============================================================================
#
# The transition, open and link doors are SLICE 2's, and `tests/
# test_tickets_doors.py` covers them in 87 tests: the phantom guard and its
# `did_you_mean`, the approval channel and its per-target echo, legality and
# terminal precedence, terminal requirements, expiry being shut, the
# supersession refusal and its three-valued disclosure.
#
# I WROTE 24 OF MY OWN AGAINST THOSE DOORS BEFORE DISCOVERING SLICE 2 HAD
# LANDED THEM, AND DELETED ALL 24 RATHER THAN KEEPING BOTH. Two suites
# asserting one door is not twice the confidence; it is two places for the
# rule to be stated and one of them to go stale. What remains here is only
# what slice 3 ADDS: the decision-lineage rule, its refusal event, and the
# two escapes.


# ============================================================================
# WHAT THIS SLICE DOES NOT CHANGE
# ============================================================================

class TestTheMergeTargetAtTheDoor:
    """MUTANT M41 SURVIVED WITHOUT THIS, and the reason is instructive.

    The door test that covered ``merge_target_error`` lived in the block of 24
    I deleted when slice 2's doors landed — it was one of the few in that block
    that tested MY code rather than slice 2's, and it went out with the rest.
    The pure-function tests in ``TestTheMergeTarget`` kept passing, which is
    exactly how an uncalled check looks from the inside.
    """

    def test_a_merge_into_a_ghost_is_refused_AT_THE_DOOR(self, client):
        ghost = "99999999-9999-4999-8999-999999999999"
        tid = _open(client)
        before = len(client.store.appended)
        r = _transition(client, tid, "merged", decision_ref=ghost)
        assert r.status_code == 422
        # SHARED-WORD AUDIT: this sentence is reachable only from
        # `merge_target_error`'s unknown-target branch. "refused" and "merged"
        # both appear in the terminal-requirement refusal too.
        assert "names no ticket this fold has ever seen" in str(r.json()["detail"])
        assert len(client.store.appended) == before, \
            "a refused merge must append nothing"

    def test_a_merge_into_ITSELF_is_refused_at_the_door(self, client):
        tid = _open(client)
        r = _transition(client, tid, "merged", decision_ref=tid)
        assert r.status_code == 422
        assert "cannot be merged into itself" in str(r.json()["detail"])

    def test_a_merge_into_a_REAL_row_still_lands(self, client):
        """The check can only REFUSE — the ordinary path is untouched."""
        canonical, dup = _open(client), _open(client)
        assert _transition(client, dup, "merged",
                           decision_ref=canonical).status_code == 200


class TestTheCensusInstrument:
    """The measurement behind this file's own claims, under test.

    An instrument whose numbers appear in a docstring and which nothing
    exercises is a claim with no check — and this one already told a
    half-truth: it reported ``events_scanned`` as though it were the domain
    when ``GET /fund/events`` caps at 1000 and serves the NEWEST 1000. The
    Gauntlet's null-test pass found it; these tests keep it found.
    """

    @staticmethod
    def _census(*args, **kw):
        import importlib.util
        import pathlib
        p = (pathlib.Path(__file__).resolve().parents[1]
             / "scripts" / "instruments" / "hw3" / "r39_census.py")
        spec = importlib.util.spec_from_file_location("r39_census", p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m

    def test_a_window_pinned_against_the_cap_says_it_is_a_window(self):
        m = self._census()
        events = [{"seq": 543 + i, "type": "X", "payload": {}}
                  for i in range(m.FEED_CAP)]
        out = m.census(events, "R39")
        assert out["events_scanned"] == m.FEED_CAP
        assert out["window_min_seq"] == 543
        # FALSE, not None and not True: we are pinned against the cap and the
        # window does not start at seq 1, so older events certainly exist.
        assert out["covers_whole_log"] is False

    def test_a_window_shorter_than_the_cap_covers_the_log(self):
        m = self._census()
        events = [{"seq": i + 1, "type": "X", "payload": {}} for i in range(10)]
        assert m.census(events, "R39")["covers_whole_log"] is True

    def test_a_full_window_that_starts_at_seq_1_also_covers_it(self):
        """The boundary the naive `len < cap` test would get wrong."""
        m = self._census()
        events = [{"seq": i + 1, "type": "X", "payload": {}}
                  for i in range(m.FEED_CAP)]
        assert m.census(events, "R39")["covers_whole_log"] is True

    def test_events_without_seqs_report_UNKNOWN_coverage_not_full(self):
        m = self._census()
        out = m.census([{"type": "X", "payload": {}}], "R39")
        assert out["covers_whole_log"] is None
        assert out["window_min_seq"] is None

    def test_it_separates_re_decision_from_re_presentation(self):
        """The two shapes the phrase 'one decision, eight rows' collapses."""
        m = self._census()
        events = (
            [{"seq": i, "type": "DeskRecommendationDecided",
              "payload": {"run_id": "run-a", "rec_id": 1, "text": "R39"}}
             for i in range(1, 9)]
            + [{"seq": 9, "type": "DeskRecommendationDecided",
                "payload": {"run_id": "run-b", "rec_id": 2, "text": "R39"}}])
        out = m.census(events, "R39")
        assert out["decision_events"] == 9          # nine decisions...
        assert out["distinct_identities"] == 2      # ...over two rows
        assert out["worst_identity"] == ["run-a", 1]
        assert out["worst_identity_decisions"] == 8
        assert out["worst_identity_seqs"] == list(range(1, 9))

    def test_the_null_arm_finds_nothing_over_a_NON_empty_domain(self):
        """A zero without its domain is not a result."""
        m = self._census()
        events = [{"seq": i + 1, "type": "X", "payload": {"text": "R39"}}
                  for i in range(5)]
        out = m.census(events, "__NO_SUCH_SUBJECT_ZZZQ__")
        assert out["events_mentioning_subject"] == 0
        assert out["events_scanned"] == 5


class TestTheLegacyDoorIsWired:
    """THE ABSTENTION ENDED ON 2026-08-24, and this class is what said so.

    Its predecessor was ``TestTheLegacyDoorIsUntouched``, whose docstring read:
    *"the day somebody does wire it, this test is the thing that says so out
    loud"*. That day came — the CEO decided it with the census in front of him
    — so the assertion is inverted rather than deleted, because a door that
    silently stopped being guarded and a door that was never guarded look
    identical to a suite with no test at all.

    THE TWO DOORS TAKE DIFFERENT RULES, and this class pins that too. The
    ticket door gets ``check_representation`` (the broader rule, with the
    ``merged``/``superseded`` escapes); the legacy door gets
    ``check_redecision`` (the narrow one — refuse only a status the row
    already holds). Porting the broad rule here would refuse every
    ``accepted -> done`` closure in the record.
    """

    def _legacy_src(self):
        import inspect

        from app.api.v1 import fund as fundapi
        return inspect.getsource(fundapi.decide_recommendation)

    def test_decide_recommendation_now_consults_the_narrow_guard(self):
        assert "_refuse_if_redecided" in self._legacy_src()

    def test_the_narrow_guard_reaches_ticketguard(self):
        """Named through the door helper, so the rule has ONE home.

        A second copy of "has this row already recorded that" is exactly the
        shape that let one client read 11 where the spine read 6.
        """
        import inspect

        from app.api.v1 import fund as fundapi
        src = inspect.getsource(fundapi._refuse_if_redecided)
        assert "ticketguard.check_redecision" in src
        assert "ticketguard.decisions_for" in src

    def test_the_BROAD_ticket_rule_is_NOT_ported_to_the_legacy_door(self):
        """THE TEST THAT FAILS IF SOMEBODY TIDIES THE TWO RULES INTO ONE.

        ``check_representation`` refuses a bare re-presentation of a decision
        the ticket has EVER recorded. On the legacy door that reading refuses
        the second decision of every ordinary lifecycle — 136 rows in the
        record carry one — which is a control refusing correct work.
        """
        import inspect

        from app.api.v1 import fund as fundapi
        both = (self._legacy_src()
                + inspect.getsource(fundapi._refuse_if_redecided))
        assert "check_representation" not in both

    def test_the_two_doors_publish_DIFFERENT_guard_versions(self):
        """An auditor reading an ApprovalRefused off /fund/events must be able
        to tell which rule refused without inspecting the aggregate type."""
        assert (ticketguard.DECISION_REF_GUARD_VERSION
                != ticketguard.LEGACY_REDECISION_GUARD_VERSION)
