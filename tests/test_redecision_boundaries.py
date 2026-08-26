"""Boundary table for the legacy re-decision guard's pure layer.

Covers ``app.fund.ticketguard.decisions_for``, ``redecision_lineage`` and
``check_redecision`` (the LEGACY door's narrow rule — see the module docstring
of ``app/fund/ticketguard.py``, "THE LEGACY DOOR" section), plus
``scripts/desk_sweep.classify`` — the sweep script's own reading of the same
guard's 409 shape.

``tests/test_legacy_redecision_guard.py`` already pins the guard's BEHAVIOUR
end to end through the FastAPI door (R39's eight-event replay, the
progression cases, the fail-open discipline). This file does not repeat that
— it drives the three pure functions directly at their INPUT BOUNDARIES:
type coercion in ``decisions_for``'s filters, the sort key for malformed
``seq``, the reopen arithmetic in ``redecision_lineage``, and every branch of
``check_redecision``'s ``to`` guard and status matrix. Nothing here starts a
FastAPI app or touches a store double.

Two real facts are cited in comments below rather than restated as prose:
exactly ONE row in the live record is ``A -> B -> A``
(``run-pm-sleeve-v2#15``: accepted, done, open, accepted, staged), and R39's
row ``run-triage7-decisions#1`` is 8x accepted at seqs 1122, 1123, 1195, 1201,
1202, 1203, 1253, 1281. No live population TOTAL (event counts, row counts) is
asserted anywhere here — the log is append-only and those move.
"""

from __future__ import annotations

import contextlib
import http.server
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import threading

import pytest

from app.fund import ticketguard


SWEEP_PATH = (pathlib.Path(__file__).resolve().parents[1]
              / "scripts" / "desk_sweep.py")


def _sweep():
    spec = importlib.util.spec_from_file_location("hw4_desk_sweep", SWEEP_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- helpers --

def _raw_event(seq, rec_id, status, *, actor="ceo", run_id=None, at="t",
               event_type=ticketguard.LEGACY_DECISION_EVENT, payload=...):
    """One raw event dict, shaped like ``EventStore.by_aggregate`` returns.

    ``payload=...`` (the sentinel) builds the ordinary
    ``{rec_id, status, at[, run_id]}`` shape; pass an explicit ``payload=``
    (including ``None`` or a non-dict) to exercise the malformed-payload
    paths ``decisions_for`` must survive.
    """
    if payload is ...:
        payload = {"rec_id": rec_id, "status": status, "at": at}
        if run_id is not None:
            payload["run_id"] = run_id
    return {"seq": seq, "type": event_type, "payload": payload, "actor": actor}


def _decision(status, at, *, actor="a", seq=None):
    """One already-narrowed decision dict — ``decisions_for``'s own output
    shape — for feeding ``redecision_lineage`` / ``check_redecision``
    directly without going through the event filter."""
    return {"seq": seq, "status": status, "at": at, "actor": actor}


# ============================================================================
# A. decisions_for — filter robustness
# ============================================================================

class TestDecisionsForFilterRobustness:
    """Each row is a way the filter could silently match the wrong thing (or
    nothing) if a comparison were changed from stringified to typed, or if a
    malformed payload were allowed to propagate instead of being read as
    ``{}``. The R39 module's own docstring names the ``54 of 56`` linkage
    shape this defends against: an ``==`` on mixed types reads "never
    decided" on every row and fails open forever with a green suite."""

    @pytest.mark.parametrize("events,run_id,rec_id,expected_seqs", [
        # int rec_id argument, str rec_id in the payload
        pytest.param(
            [_raw_event(1, "1", "accepted", run_id="r1")],
            "r1", 1, [1], id="rec_id-int-arg-str-payload"),
        # str rec_id argument, int rec_id in the payload
        pytest.param(
            [_raw_event(1, 1, "accepted", run_id="r1")],
            "r1", "1", [1], id="rec_id-str-arg-int-payload"),
        # payload carries no run_id at all -> kept regardless of the call's run_id
        pytest.param(
            [_raw_event(1, 1, "accepted")],
            "whatever-run", 1, [1], id="payload-missing-run_id-kept"),
        # payload's run_id disagrees with the one asked for -> excluded
        pytest.param(
            [_raw_event(1, 1, "accepted", run_id="other-run")],
            "r1", 1, [], id="payload-mismatched-run_id-excluded"),
        # a non-dict entry in the list is skipped, not fatal
        pytest.param(
            ["not-an-event", _raw_event(1, 1, "accepted", run_id="r1")],
            "r1", 1, [1], id="non-dict-event-skipped"),
        # payload=None reads as {}; rec_id becomes None, so it matches a
        # rec_id=None request and nothing else
        pytest.param(
            [_raw_event(1, None, None, payload=None)],
            "r", None, [1], id="payload-None-matches-rec_id-None"),
        pytest.param(
            [_raw_event(1, None, None, payload=None)],
            "r", "7", [], id="payload-None-excluded-from-other-rec_id"),
        # payload is a list, not a dict: same {} treatment as payload=None
        pytest.param(
            [_raw_event(1, None, None, payload=[1, 2, 3])],
            "r", None, [1], id="payload-list-matches-rec_id-None"),
        pytest.param(
            [_raw_event(1, None, None, payload=[1, 2, 3])],
            "r", "7", [], id="payload-list-excluded-from-other-rec_id"),
        # a foreign event type on the same aggregate is excluded even though
        # rec_id and run_id both match
        pytest.param(
            [_raw_event(1, 1, "accepted", run_id="r1",
                        event_type="ApprovalRefused")],
            "r1", 1, [], id="foreign-event-type-excluded"),
        # rec_id=0 vs rec_id=None: str(0) == "0", str(None) == "None" — the
        # two must not be treated as interchangeable "falsy" rec_ids
        pytest.param(
            [_raw_event(1, 0, "s0")], "r", 0, [1], id="rec_id-0-matches-0"),
        pytest.param(
            [_raw_event(1, 0, "s0")], "r", None, [],
            id="rec_id-0-does-not-match-None"),
        pytest.param(
            [_raw_event(1, None, "sN")], "r", None, [1],
            id="rec_id-None-matches-None"),
        pytest.param(
            [_raw_event(1, None, "sN")], "r", 0, [],
            id="rec_id-None-does-not-match-0"),
    ])
    def test_filter_keeps_or_excludes_by_the_stated_rule(
            self, events, run_id, rec_id, expected_seqs):
        out = ticketguard.decisions_for(events, run_id, rec_id)
        assert [d["seq"] for d in out] == expected_seqs

    def test_kept_dict_has_exactly_the_six_published_keys(self):
        """A seventh key (the sort scratch field, or a leaked payload key)
        would silently widen every consumer's view of a decision row.

        SIX SINCE 2026-08-26, not four: ``note`` and ``next_actor`` are
        carried because the guard's comparison is no longer status-only. The
        count is asserted rather than a subset checked — dropping either of
        the two new keys would make ``redecision_lineage`` read every row's
        note as absent and every re-record as a no-op, which is the shape of
        the defect this repair exists to remove."""
        events = [_raw_event(1, 1, "accepted", run_id="r1", actor="ceo")]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert len(out) == 1
        assert set(out[0].keys()) == {"seq", "status", "at", "actor", "note",
                                      "next_actor"}

    def test_the_two_new_keys_carry_the_payloads_own_values(self):
        """The regression this guards: a fold that returns the KEY without
        the VALUE passes a set-of-keys assertion and reads None forever."""
        events = [_raw_event(
            1, 1, "done", run_id="r1", actor="cto",
            payload={"rec_id": 1, "status": "done", "at": "t", "run_id": "r1",
                     "note": "closed on the record", "next_actor": "ceo"})]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert out[0]["note"] == "closed on the record"
        assert out[0]["next_actor"] == "ceo"

    def test_a_payload_with_neither_field_reads_them_as_None(self):
        """Every decision event older than those payload fields. Absent is
        reported absent — never "" for the note, which would be a claim that
        the row's note was deliberately cleared."""
        events = [_raw_event(1, 1, "accepted", run_id="r1")]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert out[0]["note"] is None
        assert out[0]["next_actor"] is None

    def test_actor_comes_from_the_event_not_the_payload(self):
        """The payload has no actor field of its own on the real door; a
        payload that happens to carry one (a replay artifact, a forged
        field) must never leak into the decider's identity."""
        events = [_raw_event(
            1, 1, "accepted", run_id="r1", actor="real-decider",
            payload={"rec_id": 1, "status": "accepted", "at": "t",
                     "run_id": "r1", "actor": "impostor"})]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert out[0]["actor"] == "real-decider"


class TestDecisionsForOrdering:
    """Order comes from ``seq``, the store's total order — never from
    ``payload["at"]`` (two doors on two hosts can disagree) and never from
    list position for a well-sequenced event. Only an event with a
    non-int ``seq`` falls back to arrival order, and only among its own kind."""

    def test_out_of_order_seqs_come_back_ascending(self):
        events = [
            _raw_event(5, 1, "c", run_id="r1"),
            _raw_event(1, 1, "a", run_id="r1"),
            _raw_event(3, 1, "b", run_id="r1"),
        ]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert [d["seq"] for d in out] == [1, 3, 5]

    def test_a_seq_of_None_sorts_after_every_int_seq(self):
        events = [
            _raw_event(2, 1, "b", run_id="r1"),
            _raw_event(None, 1, "none-first-in-arrival", run_id="r1"),
            _raw_event(1, 1, "a", run_id="r1"),
        ]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert [d["seq"] for d in out] == [1, 2, None]

    def test_two_None_seq_events_keep_their_arrival_order(self):
        """Both sort into the same "after everything" bucket; the tie is
        broken by original list position, not dropped or reversed."""
        events = [
            _raw_event(None, 1, "first-arrival", run_id="r1", at="t-first"),
            _raw_event(1, 1, "has-a-seq", run_id="r1"),
            _raw_event(None, 1, "second-arrival", run_id="r1", at="t-second"),
        ]
        out = ticketguard.decisions_for(events, "r1", 1)
        assert [d["seq"] for d in out] == [1, None, None]
        none_seq_ats = [d["at"] for d in out if d["seq"] is None]
        assert none_seq_ats == ["t-first", "t-second"]


# ============================================================================
# B. redecision_lineage
# ============================================================================

class TestRedecisionLineage:
    """``same_status_run`` is the CURRENT unbroken run ending at the last
    element, not every occurrence ever — the distinction that matters on a
    reopen. ``recorded_at``/``recorded_by`` describe the start of that run;
    ``first_ever_at`` describes the earliest occurrence anywhere, and the two
    differ only when a reopen has happened."""

    def test_empty_input_returns_the_exact_no_decision_shape(self):
        """Asserted as an EQUALITY, not a subset: the no-decision branch and
        the decided branch must publish the same key set, or a consumer that
        reads `recorded_note` off a never-decided row gets a KeyError on the
        one path nobody exercises. `recorded_note` is "" and
        `recorded_next_actor` is None on this branch because a row with no
        decisions has had neither written."""
        assert ticketguard.redecision_lineage([]) == {
            "decided": False, "decision_count": 0, "recorded_status": None,
            "recorded_at": None, "recorded_by": None, "same_status_run": 0,
            "first_ever_at": None, "recorded_note": "",
            "recorded_next_actor": None, "basis": "no_decision_events",
        }

    def test_one_element(self):
        lin = ticketguard.redecision_lineage(
            [_decision("accepted", "t1", actor="ceo", seq=1)])
        assert lin["decided"] is True
        assert lin["decision_count"] == 1
        assert lin["recorded_status"] == "accepted"
        assert lin["same_status_run"] == 1
        assert lin["recorded_at"] == "t1"
        assert lin["recorded_by"] == "ceo"
        assert lin["first_ever_at"] == "t1"
        assert lin["basis"] == "decision_events"
        assert lin["seqs"] == [1]

    def test_a_run_of_three_identical(self):
        decisions = [_decision("accepted", f"t{i}", seq=i) for i in (1, 2, 3)]
        lin = ticketguard.redecision_lineage(decisions)
        assert lin["decision_count"] == 3
        assert lin["same_status_run"] == 3
        assert lin["recorded_at"] == "t1"
        assert lin["first_ever_at"] == "t1"

    def test_A_then_B_the_run_covers_only_the_last_status(self):
        decisions = [_decision("accepted", "t1", seq=1),
                    _decision("done", "t2", actor="pm", seq=2)]
        lin = ticketguard.redecision_lineage(decisions)
        assert lin["recorded_status"] == "done"
        assert lin["same_status_run"] == 1
        assert lin["recorded_at"] == "t2"
        assert lin["recorded_by"] == "pm"
        assert lin["first_ever_at"] == "t2"
        assert lin["decision_count"] == 2

    def test_A_A_then_B_the_pre_progression_repeat_does_not_leak_into_B(self):
        decisions = [_decision("accepted", "t1", seq=1),
                    _decision("accepted", "t2", seq=2),
                    _decision("done", "t3", actor="pm", seq=3)]
        lin = ticketguard.redecision_lineage(decisions)
        assert lin["recorded_status"] == "done"
        assert lin["same_status_run"] == 1
        assert lin["recorded_at"] == "t3"
        assert lin["first_ever_at"] == "t3"
        assert lin["decision_count"] == 3

    def test_A_B_A_the_reopen_shape(self):
        """The one row in the live record shaped like this is
        ``run-pm-sleeve-v2#15`` (accepted, done, open, accepted, staged) —
        this is the minimal 3-element instance of the same defect class.
        The run must reset at the reopen: ``same_status_run`` counts only the
        SECOND acceptance, ``recorded_at`` names the second acceptance's
        time, and ``first_ever_at`` still points at the first one — reading
        ``recorded_at`` as "when this was decided" must never point a reader
        at a decision the reopen already undid."""
        decisions = [_decision("accepted", "t1-first-accept", actor="ceo", seq=1),
                    _decision("done", "t2-done", actor="pm", seq=2),
                    _decision("accepted", "t3-second-accept", actor="coo", seq=3)]
        lin = ticketguard.redecision_lineage(decisions)
        assert lin["recorded_status"] == "accepted"
        assert lin["same_status_run"] == 1
        assert lin["recorded_at"] == "t3-second-accept"
        assert lin["recorded_by"] == "coo"
        assert lin["first_ever_at"] == "t1-first-accept"
        assert lin["decision_count"] == 3

    def test_A_B_A_A_the_run_after_reopen_grows_again(self):
        decisions = [_decision("accepted", "t1", seq=1),
                    _decision("done", "t2", seq=2),
                    _decision("accepted", "t3-run-start", actor="coo", seq=3),
                    _decision("accepted", "t4", seq=4)]
        lin = ticketguard.redecision_lineage(decisions)
        assert lin["recorded_status"] == "accepted"
        assert lin["same_status_run"] == 2
        assert lin["recorded_at"] == "t3-run-start"
        assert lin["recorded_by"] == "coo"
        assert lin["first_ever_at"] == "t1"
        assert lin["decision_count"] == 4


# ============================================================================
# C. check_redecision
# ============================================================================

class TestCheckRedecisionToBoundary:
    """``to`` must be a non-empty ``str`` before the guard looks at anything.

    **THE ROW MUST HOLD THE DEGENERATE VALUE, or this class proves nothing.**
    The first draft of these cases ran every ``to`` against a row recorded
    ``accepted``, and every one of them passed for the wrong reason: ``None``,
    ``0`` and ``123`` are all ``!= "accepted"``, so the ordinary
    status comparison allows them whether or not the type check exists.
    Deleting the guarded branch left the whole class green — a test that
    cannot fail for the defect it names.

    The case that makes the branch load-bearing is a row whose OWN recorded
    status is the degenerate value: a malformed payload leaves
    ``status=None``, and without the type check ``None == None`` would refuse
    — the door would start rejecting decisions because an earlier event was
    unreadable. That is the defect, and these cases are pointed at it.
    """

    @pytest.mark.parametrize("to", [None, "", 0, False],
                             ids=["None", "empty-str", "int-0", "bool-False"])
    def test_a_degenerate_to_allows_even_when_the_ROW_HOLDS_THE_SAME_VALUE(
            self, to):
        # The row's last decision records exactly what is being asked for, so
        # only the type check can produce the allow.
        row = [_decision(to, "t1", actor="ceo", seq=1)]
        assert ticketguard.redecision_lineage(row)["recorded_status"] == to
        assert ticketguard.check_redecision(
            row, to=to, run_id="run-x", rec_id=1) is None

    @pytest.mark.parametrize("to", [123, True],
                             ids=["int-123", "bool-True"])
    def test_a_non_string_to_allows_against_a_row_holding_it(self, to):
        """``True == 1`` in Python, so a row recorded ``1`` and a ``to`` of
        ``True`` compare equal. Only ``isinstance(to, str)`` separates them."""
        row = [_decision(to, "t1", actor="ceo", seq=1)]
        assert ticketguard.check_redecision(
            row, to=to, run_id="run-x", rec_id=1) is None

    def test_the_control_positive_a_real_matching_string_does_refuse(self):
        """Without this, every case above could be passing because the guard
        never refuses anything, not because the ``to`` check works."""
        result = ticketguard.check_redecision(
            [_decision("accepted", "t1", actor="ceo", seq=1)],
            to="accepted", run_id="run-x", rec_id=1)
        assert result is not None
        assert result["refused"] is True

    def test_a_row_whose_last_status_is_unreadable_does_not_lock_the_row(self):
        """THE DEFECT IN ONE SENTENCE: an unreadable earlier event must not
        make a later, legitimate decision impossible. Absence is not a state
        the row holds."""
        row = [_decision("accepted", "t1", actor="ceo", seq=1),
               _decision(None, "t2", actor="ceo", seq=2)]
        for status in ("accepted", "done", "rejected"):
            assert ticketguard.check_redecision(
                row, to=status, run_id="run-x", rec_id=1) is None


#: The six status strings named in the contract, each exercised both as
#: "the row already holds it" (refuse) and "the row holds something else"
#: (allow). Paired with a fixed different status so the allow case never
#: coincides with the refuse case.
_STATUS_PAIRS = [
    ("open", "accepted"),
    ("accepted", "done"),
    ("rejected", "staged"),
    ("staged", "done"),
    ("done", "noted"),
    ("noted", "open"),
]


class TestCheckRedecisionStatusMatrix:
    """Every status the legacy door's vocabulary carries, both directions.
    A guard that refused on the wrong branch (e.g. always refusing, or
    comparing against ``decided_state`` instead of the CURRENT status) would
    pass a partial table; this one exercises all six symmetrically."""

    @pytest.mark.parametrize("status,_other", _STATUS_PAIRS,
                             ids=[s for s, _ in _STATUS_PAIRS])
    def test_refuses_when_the_row_already_holds_this_status(self, status, _other):
        decisions = [_decision(status, "t1", actor="ceo", seq=1)]
        result = ticketguard.check_redecision(
            decisions, to=status, run_id="run-x", rec_id=9)
        assert result is not None
        assert result["refused"] is True
        assert result["hint"] == "already_at_this_status"
        assert result["attempted"] == status
        assert result["recorded_status"] == status

    @pytest.mark.parametrize("status,other", _STATUS_PAIRS,
                             ids=[s for s, _ in _STATUS_PAIRS])
    def test_allows_when_the_row_holds_a_different_status(self, status, other):
        decisions = [_decision(status, "t1", actor="ceo", seq=1)]
        result = ticketguard.check_redecision(
            decisions, to=other, run_id="run-x", rec_id=9)
        assert result is None


class TestCheckRedecisionRefusalShape:
    """The refusal dict's published contract fields, asserted by NAME —
    never by a substring of ``detail``, which is prose written for a human
    and free to be reworded without changing what the guard actually did."""

    def test_every_published_field_is_present_and_correct(self):
        decisions = [_decision("accepted", "t1", actor="ceo", seq=1122),
                    _decision("accepted", "t2", actor="coo", seq=1123)]
        result = ticketguard.check_redecision(
            decisions, to="accepted", run_id="run-triage7-decisions", rec_id=1)
        assert result["refused"] is True
        assert result["hint"] == "already_at_this_status"
        assert result["guard"] == ticketguard.LEGACY_REDECISION_GUARD_VERSION
        assert result["attempted"] == "accepted"
        assert result["row_ref"] == "run-triage7-decisions#1"
        assert result["prior_same_status"] == 2
        assert result["decision_count"] == 2
        assert result["recorded_at"] == "t1"
        assert result["recorded_by"] == "ceo"
        assert result["recorded_status"] == "accepted"
        assert result["kind"] == "desk_recommendation"
        assert isinstance(result["detail"], str) and result["detail"]


class TestCheckRedecisionPriorSameStatusCount:
    """``prior_same_status`` is the run length, asserted at three sizes —
    including R39's own eight, replayed at its real seqs (1122, 1123, 1195,
    1201, 1202, 1203, 1253, 1281) rather than a synthetic count, so this test
    is pinned to the actual incident and not just a round number."""

    def test_run_of_one(self):
        decisions = [_decision("accepted", "t1", actor="ceo", seq=1122)]
        result = ticketguard.check_redecision(
            decisions, to="accepted", run_id="run-triage7-decisions", rec_id=1)
        assert result["prior_same_status"] == 1

    def test_run_of_two(self):
        decisions = [_decision("accepted", "t1", actor="ceo", seq=1122),
                    _decision("accepted", "t2", actor="coo", seq=1123)]
        result = ticketguard.check_redecision(
            decisions, to="accepted", run_id="run-triage7-decisions", rec_id=1)
        assert result["prior_same_status"] == 2

    def test_run_of_eight_R39s_own_seqs(self):
        r39_seqs = (1122, 1123, 1195, 1201, 1202, 1203, 1253, 1281)
        decisions = [_decision("accepted", f"t{seq}", actor="ceo", seq=seq)
                    for seq in r39_seqs]
        result = ticketguard.check_redecision(
            decisions, to="accepted", run_id="run-triage7-decisions", rec_id=1)
        assert result["prior_same_status"] == 8
        assert result["decision_count"] == 8


# ============================================================================
# D. desk_sweep.classify
# ============================================================================

class TestClassify:
    """``classify`` decides FAIL vs ALREADY purely from a machine-readable
    ``hint`` — never from prose — because ``desk_sweep`` counts a batch's
    ``already`` outcomes as "nothing needed doing" and its exit status is
    non-zero only on a real ``fail``. A classifier that guessed from shape
    (any 409 with a "detail" dict, say) would silently promote the
    supersession brake's genuine refusals into no-ops."""

    def setup_method(self):
        self.m = _sweep()

    def _already_body(self):
        return json.dumps({"detail": {
            "hint": "already_at_this_status",
            "recorded_status": "accepted", "recorded_at": "t"}}).encode()

    def _superseded_body(self):
        # A DIFFERENT guard's refusal shape — a real 409, but not this one's
        # hint. Must classify as fail, not already: a supersession brake
        # firing is a genuine refusal to act, never a no-op.
        return json.dumps({"detail": {
            "mode": "superseded", "superseder_ref": "run-x#2"}}).encode()

    @pytest.mark.parametrize("code,body,expected", [
        pytest.param(200, b"", "ok", id="200-empty-body"),
        pytest.param(200, b"not json", "ok", id="200-body-ignored-even-if-junk"),
        pytest.param(422, b"whatever", "fail", id="422-fail"),
        pytest.param(500, b"whatever", "fail", id="500-fail"),
        pytest.param(503, b"whatever", "fail", id="503-fail"),
        pytest.param(409, b"<html>", "fail", id="409-unparseable-html"),
        pytest.param(409, b"{}", "fail", id="409-empty-object-no-detail"),
        pytest.param(409, b'{"detail": "a string"}', "fail",
                     id="409-detail-is-a-string-not-a-dict"),
        pytest.param(409, b'{"detail": {"hint": "something_else"}}', "fail",
                     id="409-detail-dict-wrong-hint"),
    ])
    def test_code_and_body_boundary_table(self, code, body, expected):
        assert self.m.classify(code, body) == expected

    def test_409_with_the_already_hint_classifies_already(self):
        assert self.m.classify(409, self._already_body()) == "already"

    def test_409_supersession_shaped_body_is_fail_not_already(self):
        """A dict ``detail`` with a plausible-looking refusal shape, but no
        matching hint, must NOT be mistaken for this guard's own 409."""
        assert self.m.classify(409, self._superseded_body()) == "fail"

    def test_bytes_and_str_bodies_classify_the_same(self):
        """``_post`` always hands ``classify`` bytes (``HTTPError.read()``),
        but the function's own contract accepts either — a caller change to
        a str body (a different transport, a test double) must not silently
        change the verdict."""
        as_bytes = self._already_body()
        as_str = as_bytes.decode()
        assert self.m.classify(409, as_bytes) == "already"
        assert self.m.classify(409, as_str) == "already"

    def test_a_body_that_is_not_str_or_bytes_at_all_fails_rather_than_crashes(self):
        """``json.loads(None)`` raises ``TypeError``, not ``ValueError`` —
        the classifier must catch both, not just the JSON-decode error."""
        assert self.m.classify(409, None) == "fail"


# ============================================================================
# THE SWEEP'S EXIT CODE — the part a caller reads, run as a real process
# ============================================================================

class TestTheSweepExitCode:
    """THE SIGNAL A CALLER ACTUALLY SEES, and until 2026-08-24 there was none.

    ``desk_sweep.py`` exited 0 whatever happened, so a sweep of 40 rows that
    failed all 40 was indistinguishable from one that closed all 40. Found by
    mutation (M37): deleting the ``sys.exit`` left every test green, because
    every test called the functions in-process and none ran the script.

    These run the REAL script as a subprocess against a stub HTTP server, so
    the ``__main__`` block — the only place the exit code is decided — is
    executed rather than source-inspected.
    """

    @staticmethod
    @contextlib.contextmanager
    def _server(code, body=b"{}"):
        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        srv = http.server.HTTPServer(("127.0.0.1", 0), H)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            yield f"http://127.0.0.1:{srv.server_address[1]}/api/v1"
        finally:
            srv.shutdown()

    def _run(self, base, rows, tmp_path):
        p = tmp_path / "sweep.json"
        p.write_text(json.dumps(rows), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(SWEEP_PATH), "decide", str(p)],
            capture_output=True, text=True,
            env={**os.environ, "DESK_SWEEP_BASE": base})

    _ROWS = [{"run_id": "run-x", "rec_id": 1, "status": "done", "note": "why"}]

    def test_a_clean_sweep_exits_zero(self, tmp_path):
        with self._server(200) as base:
            r = self._run(base, self._ROWS, tmp_path)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "decided 1, already 0, failed 0" in r.stdout

    def test_a_REAL_failure_exits_one(self, tmp_path):
        with self._server(422, b'{"detail": "no such run"}') as base:
            r = self._run(base, self._ROWS, tmp_path)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "failed 1" in r.stdout

    def test_ALREADY_exits_ZERO_because_nothing_went_wrong(self, tmp_path):
        """THE POINT OF THE THIRD OUTCOME. 237 rows in the record have already
        recorded ``done``; if re-sweeping them exited non-zero, the guard
        would look like a breakage every time the chair re-ran a sweep, and
        the chair would stop reading the word."""
        body = json.dumps({"detail": {
            "refused": True, "hint": "already_at_this_status",
            "recorded_status": "done",
            "recorded_at": "2026-08-23T14:06:30Z"}}).encode()
        with self._server(409, body) as base:
            r = self._run(base, self._ROWS, tmp_path)
        assert r.returncode == 0, r.stdout + r.stderr
        assert "already 1" in r.stdout
        assert "failed 0" in r.stdout
        assert "ALREADY run-x#1" in r.stdout

    def test_a_supersession_409_still_exits_ONE(self, tmp_path):
        """A different guard's 409 is a refusal to act, not a no-op, and the
        sweep must not launder it into silence."""
        body = json.dumps({"detail": {
            "refused": True, "mode": "superseded",
            "superseder_ref": "rec:run-y#3"}}).encode()
        with self._server(409, body) as base:
            r = self._run(base, self._ROWS, tmp_path)
        assert r.returncode == 1, r.stdout + r.stderr
        assert "failed 1" in r.stdout
