"""THE NARROW DECISION GUARD on the legacy door — R39's own shape, replayed.

THE INCIDENT. On the live record, the R39 approval decision was recorded
**eight times on one identity**: eight ``DeskRecommendationDecided`` events at
seq 1122, 1123, 1195, 1201, 1202, 1203, 1253 and 1281, every one naming
``run-triage7-decisions#1`` with status ``accepted``. They landed on
``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}`` — the LEGACY door,
which the ticket highway's slice 3 deliberately did not touch. On 2026-08-24
the CEO decided to wire it, with the census in front of him.

THE TWO THINGS THIS FILE PINS, and they are the two halves of the same rule:

  * the 2nd through 8th presentations of ``accepted`` are REFUSED and the 1st
    stands (``TestTheR39Replay``);
  * an ``accepted -> done`` progression is NOT refused
    (``TestAProgressionIsNotARepeat``) — because 136 rows in the record carry
    one, and a guard that broke them would be a control refusing correct work.

WHAT IS PINNED AND WHAT IS NOT. The eight seqs are fixed history and are quoted
as the shape being replayed. **The population totals are NOT asserted anywhere
in this file and must not be**: the log is append-only and live, so 678 events
over 491 rows was true at one instant and will never be true again. Two
readings during this dispatch already differed from the brief's own figures.
What is asserted is the INVARIANT — same status refused, changed status
allowed — which is true at every population size.

Reproduce the census with
``python scripts/instruments/hw4/redecision_census.py``; it reads Postgres end
to end rather than the 1000-capped event feed, and refuses on an empty
population.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.fund import ticketguard


# ---------------------------------------------------------------- fixtures --

class _AggStore:
    """An event store this test OWNS, and which can answer ``by_aggregate``.

    THE ``by_aggregate`` METHOD IS NOT DECORATION HERE — it is the whole reason
    the guard can see the row's history, and 18 of the suite's 23 event-store
    doubles do not have it (``scripts/instruments/hw4/store_double_census.py``).
    Against one of those the guard fails OPEN, so a test written on a double
    without it would assert a refusal that never happened and pass by never
    reaching the control. Every test here asserts ``redecision_basis ==
    "decision_events"`` on the allowed path for exactly that reason.

    The house rule since D39: an endpoint test that WRITES must own its store
    and monkeypatch ``fundapi._store``; two probe events in the process-wide
    store once turned 92 unrelated tests red while each passed in isolation.
    """

    def __init__(self, events=None):
        self.events = list(events or [])
        self.appended = []

    def append(self, e):
        self.appended.append(e)
        self.events.append({
            "seq": len(self.events) + 1,
            "type": getattr(e.type, "value", e.type),
            "payload": e.payload, "actor": e.actor,
            "aggregate_type": e.aggregate_type, "aggregate_id": e.aggregate_id})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]

    def by_aggregate(self, aggregate_id):
        return [e for e in self.events
                if e.get("aggregate_id") == str(aggregate_id)]

    def of_type(self, name):
        return [e for e in self.appended
                if getattr(e.type, "value", e.type) == name]


class _BlindStore(_AggStore):
    """A store with no ``by_aggregate`` at all — 18 of the suite's 23 doubles."""

    by_aggregate = None


class _AngryStore(_AggStore):
    """A store whose ``by_aggregate`` raises — the outage, not the wiring."""

    def by_aggregate(self, aggregate_id):
        raise RuntimeError("postgres went away")


class _Deskstore:
    """Records what was written, so a refused decision can be proven silent.

    IT RECORDS THE ARGUMENTS AND MODELS NOTHING. An earlier version kept only
    ``(run_id, rec_id, status)``, which made "the write reached the writer"
    assertable and "the NOTE reached the writer" not — and that gap is exactly
    why the suite could not see the 2026-08-26 defect. ``writes`` carries the
    note and the routing owner too. It deliberately does NOT reproduce the
    real writer's ``if note:`` / pop-on-terminal branches: a double that
    re-implements the code under test can agree with a bug.
    """

    def __init__(self):
        self.decided = []
        self.writes = []

    def decide_recommendation(self, run_id, rec_id, status, actor, note="",
                              next_actor=None):
        self.decided.append((run_id, rec_id, status))
        self.writes.append({"run_id": run_id, "rec_id": rec_id,
                            "status": status, "actor": actor, "note": note,
                            "next_actor": next_actor})
        return {"rec_id": rec_id, "status": status, "text": "R39",
                "seat": "coo", "trace_id": None, "next_actor": next_actor}


def _client(monkeypatch, store, deskstore):
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: deskstore)
    monkeypatch.setattr(fundapi, "_edges_by_target", lambda: None)
    monkeypatch.setattr(fundapi, "_intray", lambda: None)
    monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store = store
    c.deskstore = deskstore
    return c


#: R39's row, by name. Quoted from the record rather than invented, so that a
#: reader can put this file beside `scripts/instruments/hw4/redecision_census.py`
#: and see the same identity.
R39_RUN = "run-triage7-decisions"
R39_REC = 1

#: The eight seqs the incident actually occupies. Used as the REPETITION COUNT
#: this replay drives, not asserted as a live population.
R39_SEQS = (1122, 1123, 1195, 1201, 1202, 1203, 1253, 1281)


def _decide(client, status="accepted", run_id=R39_RUN, rec_id=R39_REC,
            actor="ceo", note="triage 7", next_actor=None):
    body = {"status": status, "actor": actor, "note": note}
    if next_actor is not None:
        body["next_actor"] = next_actor
    return client.post(
        f"/api/v1/fund/desk/runs/{run_id}/recommendations/{rec_id}",
        json=body)


# ============================================================================
# THE ACCEPTANCE CRITERION — R39's eight, replayed through the legacy door
# ============================================================================

class TestTheR39Replay:
    def test_the_first_accepted_stands_and_the_next_seven_are_refused(
            self, monkeypatch):
        """R39, seq 1122-1281: eight acceptances of one decision.

        THE DEFECT THIS PINS. Before this guard, nothing on this door held
        "this row already records that" as a fact, so the second through
        eighth presentations were indistinguishable from the first — and eight
        events made one decision look like eight on every surface that counts
        them. The ticket highway's slice 3 built the rule and abstained from
        this door; the CEO decided to wire it on 2026-08-24.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)

        first = _decide(c)
        assert first.status_code == 200, first.text
        # THE GUARD RAN. Without this the whole class could pass against a
        # store that cannot answer, having never reached the control.
        assert first.json()["redecision_basis"] == "decision_events"
        assert first.json()["redecision_readable"] is True

        rest = [_decide(c) for _ in range(len(R39_SEQS) - 1)]
        assert [r.status_code for r in rest] == [409] * 7

        # ONE decision written, not eight. The store is the authority on what
        # actually landed; the HTTP codes alone would not prove the refusal
        # stopped the write.
        assert ds.decided == [(R39_RUN, R39_REC, "accepted")]

        # ONE DeskRecommendationDecided event, seven ApprovalRefused.
        assert len(c.store.of_type("DeskRecommendationDecided")) == 1
        assert len(c.store.of_type("ApprovalRefused")) == 7

    def test_each_refusal_carries_the_lineage_and_a_refusal_never_counts(
            self, monkeypatch):
        """A refusal that does not say WHY is a puzzle, not a control."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c).status_code == 200

        priors = []
        for _ in range(len(R39_SEQS) - 1):
            r = _decide(c)
            assert r.status_code == 409
            d = r.json()["detail"]
            assert d["refused"] is True
            assert d["hint"] == "already_at_this_status"
            assert d["row_ref"] == f"{R39_RUN}#{R39_REC}"
            assert d["attempted"] == "accepted"
            assert d["recorded_status"] == "accepted"
            assert d["recorded_by"] == "ceo"
            assert d["recorded_at"], "the refusal must say WHEN, not just no"
            assert d["guard"] == ticketguard.LEGACY_REDECISION_GUARD_VERSION
            priors.append(d["prior_same_status"])

        # THE FIRST REFUSAL SEES ONE PRIOR, THE SEVENTH SEES ONE. A refused
        # attempt is not a decision and must never count as one — otherwise
        # the count would read 1..7 and a rejected event would be able to lock
        # a row by inflating its own history.
        assert priors == [1] * 7
        assert all(p == 1 for p in priors)

    def test_the_refusal_is_AUDIBLE_in_the_event_log(self, monkeypatch):
        """"Audible" means IN THE EVENT LOG, never a log line.

        The riskofficer audits refusals from ``/fund/events``, not from
        anybody's terminal — so a refusal whose only trace is an HTTP response
        is invisible to the seat whose job is auditing this path.
        """
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c).status_code == 200
        assert _decide(c).status_code == 409

        refusals = c.store.of_type("ApprovalRefused")
        assert len(refusals) == 1
        ev = refusals[0]
        assert ev.aggregate_type == "desk_run"
        assert ev.aggregate_id == R39_RUN
        p = ev.payload
        assert p["guard"] == ticketguard.LEGACY_REDECISION_GUARD_VERSION
        assert p["approver"] == "ceo"
        assert p["attempted"] == "accepted"
        assert p["recorded_status"] == "accepted"
        assert p["recorded_by"] == "ceo"
        assert p["recorded_at"]
        assert p["prior_same_status"] == 1
        assert p["decision_count"] == 1
        assert p["row_ref"] == f"{R39_RUN}#{R39_REC}"
        assert "ONE DECISION, ONE ROW" in p["reason"]

    def test_a_refusal_event_does_not_feed_the_next_refusal(self, monkeypatch):
        """The guard reads the aggregate it also WRITES to.

        ``ApprovalRefused`` lands on the same ``desk_run`` aggregate the
        decisions do, so a guard that folded every event on that aggregate
        would count its own refusals as decisions and the numbers would climb
        by two. ``decisions_for`` filters on type; this proves it does.
        """
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c).status_code == 200
        for _ in range(4):
            assert _decide(c).status_code == 409

        last = c.store.of_type("ApprovalRefused")[-1].payload
        # Four refusals later, the row still holds exactly ONE decision.
        assert last["decision_count"] == 1
        assert last["prior_same_status"] == 1


# ============================================================================
# THE SCOPE REPAIR — a CORRECTION is not a DUPLICATE (2026-08-26)
#
# THE DEFECT, MEASURED. The v1 guard compared `status` alone while
# `deskstore.decide_recommendation` wrote five fields, and its 409 told the
# caller the write "changes nothing". Replayed over the whole record
# (`scripts/instruments/hw5/redecision_scope.py`), **17 of v1's 37 refusals
# carried a real table write** — 13 note-only, 4 note + `next_actor`, 7 of
# them from one chair sweep. `note` is parsed into the supersession marker on
# the CEO's desk card (`deskcard.superseded_by`), and this endpoint is the
# writer's only caller repo-wide, so those corrections had no door at all.
#
# NO TEST ASSERTED THE LOSS, which is why the repair fought nothing: every
# test above drives the door with the SAME note on every call, so a
# status-only comparison and a whole-write-set comparison give identical
# answers to all of them. These are the tests that fail if v1 returns.
# ============================================================================

class TestACorrectionIsNotADuplicate:

    def test_a_note_differing_re_record_PASSES_and_the_note_LANDS(
            self, monkeypatch):
        """13 of the 17. The row is already ``done``; only the citation
        changed. Both halves are asserted — a 200 alone would pass if the
        door accepted the request and dropped the note on the way through."""
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)

        assert _decide(c, "done", note="closed, cited X").status_code == 200
        second = _decide(c, "done", note="closed, cited Y — X was wrong")
        assert second.status_code == 200, second.text
        assert second.json()["redecision_basis"] == "decision_events"
        assert ds.writes[-1]["note"] == "closed, cited Y — X was wrong"
        assert c.store.of_type("ApprovalRefused") == []

    def test_the_corrected_note_is_on_the_EVENT_too(self, monkeypatch):
        """The table is current state; the log is the record. A correction
        that reached only one of them is unrecoverable the moment the row
        moves again — and the log is what this guard itself reads."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        _decide(c, "done", note="first")
        _decide(c, "done", note="second")
        notes = [e.payload["note"]
                 for e in c.store.of_type("DeskRecommendationDecided")]
        assert notes == ["first", "second"]

    def test_a_next_actor_differing_re_record_PASSES_and_ROUTING_LANDS(
            self, monkeypatch):
        """4 of the 17. The status was already right; what changed is whose
        move it is. A non-terminal status throughout, because the writer
        refuses ``next_actor`` on a terminal one with a 422 by design."""
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)

        assert _decide(c, "accepted", note="n").status_code == 200
        routed = _decide(c, "accepted", note="n", next_actor="ceo")
        assert routed.status_code == 200, routed.text
        assert ds.writes[-1]["next_actor"] == "ceo"
        assert routed.json()["next_actor"] == "ceo"
        assert c.store.of_type("ApprovalRefused") == []

    def test_an_all_fields_identical_re_record_is_STILL_REFUSED(
            self, monkeypatch):
        """THE CONTROL POSITIVE, and the reason the repair is a scope fix
        rather than a removal. Same status, same note, same owner: nothing
        to write, so the door refuses exactly as it did before."""
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)

        assert _decide(c, "accepted", note="n", next_actor="ceo").status_code \
            == 200
        again = _decide(c, "accepted", note="n", next_actor="ceo")
        assert again.status_code == 409, again.text
        assert len(ds.writes) == 1
        assert [e.payload["kind"]
                for e in c.store.of_type("ApprovalRefused")] == [
                    "desk_recommendation"]

    def test_the_refusal_NAMES_the_fields_it_compared(self, monkeypatch):
        """A 409 that asserts "changes nothing" without saying what it
        compared is how a control gets believed past its scope — which is
        the whole v1 story. The list is published on the response AND on the
        event, so an auditor reading the log later can tell a v1.1 refusal
        (three fields) from a v1 one (status alone)."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        _decide(c, "done", note="n")
        refused = _decide(c, "done", note="n")
        detail = refused.json()["detail"]
        assert detail["unchanged_fields"] == ["status", "note", "next_actor"]
        assert detail["not_written_fields"] == []
        event = c.store.of_type("ApprovalRefused")[0]
        assert event.payload["unchanged_fields"] == detail["unchanged_fields"]
        assert event.payload["not_written_fields"] == []

    def test_the_refusal_no_longer_claims_the_write_changes_NOTHING_blindly(
            self, monkeypatch):
        """The v1 sentence was FALSE for 17 refusals. The replacement names
        what it actually rewrote, so the claim is checkable.

        ASSERTED AS A CONTRAST, not as a substring hit. "writes no note"
        appears in one refusal and must be ABSENT from the other — a bare
        ``in`` check on a sentence this guard emits on every 409 would be
        satisfied by the wrong branch and would pin nothing at all."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        _decide(c, "done", note="")
        no_note = _decide(c, "done", note="")
        assert "writes no note" in no_note.json()["detail"]["detail"]

        c2 = _client(monkeypatch, _AggStore(), _Deskstore())
        _decide(c2, "done", note="cited")
        with_note = _decide(c2, "done", note="cited")
        text = with_note.json()["detail"]["detail"]
        assert "writes no note" not in text
        assert "status, note, next_actor with the value(s) already stored" \
            in text

    def test_a_NOTELESS_decision_does_not_erase_the_standing_note(
            self, monkeypatch):
        """MUTATION SURVIVOR M22, and the sharpest of the six.

        The writer's ``if note:`` means an empty note LEAVES the previous one
        in place. So a row that went ``accepted`` with a citation and was then
        closed with no citation still HOLDS that citation — and re-sending it
        is a true duplicate that must refuse.

        A fold that took the last note FIELD rather than the last non-empty
        one would read the row's note as erased, call the resend a change, and
        let the duplicate through. Nothing else in this file can see that: it
        needs three decisions with an empty note in the MIDDLE.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        assert _decide(c, "accepted", note="cited: memo 3").status_code == 200
        assert _decide(c, "done", note="").status_code == 200
        resend = _decide(c, "done", note="cited: memo 3")
        assert resend.status_code == 409, resend.text
        assert len(ds.writes) == 2

    def test_the_STANDING_owner_is_the_latest_one_not_the_first(
            self, monkeypatch):
        """MUTATION SURVIVOR M23. A row re-routed chair -> ceo holds ``ceo``;
        re-sending ``ceo`` is a duplicate. A fold reading the FIRST decision's
        owner would compare against ``chair``, call it a change, and let a
        third identical write through — one decision looking like three."""
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        assert _decide(c, "accepted", note="n",
                       next_actor="chair").status_code == 200
        assert _decide(c, "accepted", note="n",
                       next_actor="ceo").status_code == 200
        third = _decide(c, "accepted", note="n", next_actor="ceo")
        assert third.status_code == 409, third.text
        assert len(ds.writes) == 2

    def test_a_row_walks_correct_note_wrong_note_correct_note(
            self, monkeypatch):
        """THE PIVOT AS ONE WALK. Each 409 sits between two 200s that differ
        from it in exactly one field, so a reader can see that the guard is
        refusing the repeat and nothing else. Under v1 this walk is four
        200s and three 409s in the wrong places."""
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        codes = [
            _decide(c, "done", note="A").status_code,   # first closure
            _decide(c, "done", note="A").status_code,   # true duplicate
            _decide(c, "done", note="B").status_code,   # correction
            _decide(c, "done", note="B").status_code,   # duplicate again
            _decide(c, "open", note="B").status_code,   # reopen
        ]
        assert codes == [200, 409, 200, 409, 200]
        assert [w["note"] for w in ds.writes] == ["A", "B", "B"]


class TestR39IsUNTOUCHEDByTheRepair:
    """THE SAFETY ARGUMENT, and it is the only one that matters: a repair
    that loosened the guard past its motivating incident would have thrown
    away what it was built for.

    R39's eight real events at seqs 1122, 1123, 1195, 1201, 1202, 1203, 1253
    and 1281 all carry ``status="accepted"``, an EMPTY note and the same
    ``next_actor`` — verified against ``fund_events`` 2026-08-26. So every one
    of the seven repeats is a true no-op under the repaired scope too, and the
    whole-record replay reports ``freed_by_the_repair`` for this row as zero.
    """

    def test_eight_presentations_with_EMPTY_notes_still_refuse_seven(
            self, monkeypatch):
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        codes = [_decide(c, "accepted", note="", next_actor="ceo").status_code
                 for _ in R39_SEQS]
        assert codes == [200] + [409] * 7
        assert len(ds.writes) == 1
        assert len(c.store.of_type("ApprovalRefused")) == 7

    def test_the_seven_refusals_name_an_UNWRITTEN_note(self, monkeypatch):
        """The distinction the repair rests on: R39's repeats did not carry a
        correction that was being dropped — they carried no note at all. That
        is visible in the refusal, so nobody has to take it on trust."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        _decide(c, "accepted", note="", next_actor="ceo")
        refused = _decide(c, "accepted", note="", next_actor="ceo")
        assert refused.status_code == 409
        detail = refused.json()["detail"]
        assert detail["not_written_fields"] == ["note"]
        assert detail["unchanged_fields"] == ["status", "next_actor"]


class TestTheScopeInstrument:
    """``scripts/instruments/hw5/redecision_scope.py`` — the measurement the
    two docstrings cite (v1 refused 37, v1.1 refuses 20, 17 freed, 0 newly
    refused, over the whole log at seq 1..1547 on 2026-08-26).

    Tested on SYNTHETIC populations, never on the live one: the log is
    append-only and those totals move, so asserting them here would pin a
    number that is already stale. What is asserted is the instrument's own
    arithmetic — which is what makes the live reading trustworthy."""

    def _mod(self):
        import importlib.util
        import pathlib
        p = (pathlib.Path(__file__).resolve().parents[1]
             / "scripts" / "instruments" / "hw5" / "redecision_scope.py")
        spec = importlib.util.spec_from_file_location("hw5_scope", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _ev(self, seq, status, note="", next_actor=None, rec=1,
            run="run-x", actor="cto"):
        return {"seq": seq, "type": "DeskRecommendationDecided",
                "actor": actor, "aggregate_id": run,
                "payload": {"run_id": run, "rec_id": rec, "status": status,
                            "at": f"t{seq}", "note": note,
                            "next_actor": next_actor}}

    def test_a_note_correction_is_counted_as_FREED(self):
        """The 13-shape. v1 refuses the second event, v1.1 allows it, and the
        instrument must attribute the difference to ``note``."""
        m = self._mod()
        out = m.replay([self._ev(1, "done", note="A"),
                        self._ev(2, "done", note="B")])
        assert out["v1_refusals"] == 1
        assert out["v11_refusals"] == 0
        assert out["freed_by_the_repair"] == 1
        assert out["freed_shapes"] == {"note": 1}

    def test_a_re_routing_is_counted_with_its_own_shape(self):
        """The 4-shape: note AND next_actor both move."""
        m = self._mod()
        out = m.replay([self._ev(1, "staged", note="A", next_actor="chair"),
                        self._ev(2, "staged", note="B", next_actor="ceo")])
        assert out["freed_shapes"] == {"note+next_actor": 1}

    def test_a_TRUE_duplicate_is_freed_by_neither_form(self):
        """R39's shape. Both forms refuse it, so it lands in neither the
        freed list nor the newly-refused one — the positive control without
        which "17 freed" could just mean "the replay allows everything"."""
        m = self._mod()
        out = m.replay([self._ev(i, "accepted", note="", next_actor="ceo")
                        for i in range(1, 9)])
        assert out["v1_refusals"] == 7
        assert out["v11_refusals"] == 7
        assert out["freed_by_the_repair"] == 0
        assert out["newly_refused_by_the_repair"] == 0

    def test_the_repair_NEVER_adds_a_refusal(self):
        """THE DIRECTION CLAIM, MADE FALSIFIABLE. v1.1 is strictly weaker than
        v1 — so over any population, ``newly_refused_by_the_repair`` is zero.
        The live run reports zero over 678 events; this pins the property on a
        population that mixes every shape."""
        m = self._mod()
        evs = []
        for i, (st, note, na) in enumerate([
                ("open", "", None), ("accepted", "a", "ceo"),
                ("accepted", "a", "ceo"), ("accepted", "b", "ceo"),
                ("done", "b", None), ("done", "b", None),
                ("open", "", None), ("open", "c", None)], start=1):
            evs.append(self._ev(i, st, note=note, next_actor=na))
        out = m.replay(evs)
        assert out["newly_refused_by_the_repair"] == 0
        assert out["v11_refusals"] <= out["v1_refusals"]

    def test_it_separates_rows_CURRENTLY_holding_a_status_from_rows_that_EVER_did(
            self):
        """THE TWO POPULATIONS THAT PRODUCED A WRONG SENTENCE. "237 rows have
        already recorded ``done``" and "236 rows currently hold ``done``" are
        both true of the live record; only the second is the population this
        guard can refuse, and the difference is the reopened rows.

        The fixture IS a reopen — accepted, done, open — so the two counts must
        disagree here or the separation proves nothing. Nothing else in the
        suite distinguishes them, which is exactly how the wrong one shipped.
        """
        m = self._mod()
        out = m.replay([self._ev(1, "accepted", note="a"),
                        self._ev(2, "done", note="b"),
                        self._ev(3, "open", note="c")])
        assert out["rows_currently_holding"] == {"open": 1}
        assert out["rows_ever_recording"] == {"accepted": 1, "done": 1,
                                              "open": 1}

    def test_the_currently_holding_counts_sum_to_the_row_count(self):
        """The invariant that makes the live reading checkable without a
        second query: every row holds exactly one status, so the buckets
        partition ``distinct_rows``. On the live log that is 236 + 4 + 154 +
        37 + 60 = 491."""
        m = self._mod()
        out = m.replay([self._ev(1, "done", rec=1), self._ev(2, "done", rec=1),
                        self._ev(3, "open", rec=2),
                        self._ev(4, "accepted", rec=3)])
        assert sum(out["rows_currently_holding"].values()) \
            == out["distinct_rows"] == 3

    def test_two_rows_do_not_see_each_others_history(self):
        m = self._mod()
        out = m.replay([self._ev(1, "done", note="A", rec=1),
                        self._ev(2, "done", note="A", rec=2)])
        assert out["distinct_rows"] == 2
        assert out["v1_refusals"] == 0

    def test_it_REFUSES_an_empty_population(self, monkeypatch, capsys):
        m = self._mod()
        monkeypatch.setattr(m, "pull", lambda dsn=None: (
            [], {"log_events": 0, "seq_min": None, "seq_max": None,
                 "covers_whole_log": True}))
        assert m.main([]) == 2
        assert "REFUSED" in capsys.readouterr().err

    def test_the_null_arm_states_its_domain_size(self, capsys):
        """A --null that compared nothing prints the same clean line as one
        that compared R39's eight. The domain size is in the sentence."""
        m = self._mod()
        assert m.main(["--null"]) == 0
        out = capsys.readouterr().out
        assert "8 events over 1 row(s) compared" in out
        assert "freed 0" in out

    def test_the_null_arm_CAN_FAIL_when_the_guard_stops_refusing(
            self, monkeypatch, capsys):
        """MUTATION SURVIVORS M34/M35: a null arm whose exit code is a
        constant is a check that cannot fire, which is this firm's named
        worst defect wearing a green tick. Break the guard underneath it and
        the arm must return 1.

        Patched at ``ticketguard.check_redecision`` — the real dependency —
        rather than at the instrument's own function, so what is proven is
        that the arm is actually consulting the control."""
        from app.fund import ticketguard as tg
        m = self._mod()
        monkeypatch.setattr(tg, "check_redecision",
                            lambda *a, **k: None)
        assert m.main(["--null"]) == 1
        assert "freed 7" in capsys.readouterr().out

    def test_the_null_arms_DOMAIN_assertion_can_fire(self, monkeypatch):
        """The other half. If the arm's own fixture stopped producing the
        eight-event shape it claims to replay, its zero would be measured
        over the wrong population — so the domain size is asserted, and the
        assertion is proven reachable rather than assumed."""
        m = self._mod()
        monkeypatch.setattr(m, "v1_refuses", lambda lineage, to: False)
        with pytest.raises(AssertionError):
            m.main(["--null"])


# ============================================================================
# THE OTHER HALF — 136 rows in the record carry a genuine progression
# ============================================================================

class TestAProgressionIsNotARepeat:
    def test_accepted_then_done_is_NOT_refused(self, monkeypatch):
        """THE TEST THAT FAILS IF THE BROAD FORM EVER RETURNS.

        An earlier draft of this guard's sibling refused any guarded
        transition on a ticket that had EVER been decided, and it passed 57
        tests because not one walked a whole lifecycle. Here the equivalent
        mistake would refuse ``done`` on every row a human had accepted —
        136 rows in the record, and every future closure.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)

        assert _decide(c, "accepted").status_code == 200
        done = _decide(c, "done")
        assert done.status_code == 200, done.text
        assert done.json()["redecision_basis"] == "decision_events"
        assert ds.decided == [(R39_RUN, R39_REC, "accepted"),
                              (R39_RUN, R39_REC, "done")]
        assert c.store.of_type("ApprovalRefused") == []

    def test_the_SECOND_done_is_refused_once_the_row_holds_it(self, monkeypatch):
        """Closing twice is still a repeat. The progression bought one ``done``,
        not a standing licence.

        THE TWO COUNTS MUST BE ASSERTED TOGETHER AND THEY MUST DIFFER HERE.
        This row has TWO decisions (``accepted``, ``done``) but a same-status
        run of ONE, and that gap is the entire difference between the defect
        and an ordinary lifecycle: ``prior_same_status`` is what says "you
        have recorded this before", ``decision_count`` is only "this row has
        been decided". A refusal reporting 2-of-2 here would tell the reader
        the row had been closed twice when it had been closed once. Found by
        mutation (M18): swapping the two left every test green because no
        case had yet been built where they disagree.
        """
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c, "accepted").status_code == 200
        assert _decide(c, "done").status_code == 200
        r = _decide(c, "done")
        assert r.status_code == 409
        d = r.json()["detail"]
        assert d["attempted"] == "done"
        assert d["decision_count"] == 2
        assert d["prior_same_status"] == 1
        assert d["recorded_by"] == "ceo"

        # And on the EVENT too, not only in the response — the audit reads the
        # log, and the log is where the two numbers must not have been swapped.
        p = c.store.of_type("ApprovalRefused")[-1].payload
        assert (p["prior_same_status"], p["decision_count"]) == (1, 2)

    @pytest.mark.parametrize("chain", [
        ("open", "accepted", "staged", "done"),
        ("accepted", "rejected"),
        ("staged", "done"),
        ("accepted", "done", "open", "accepted", "staged"),
    ])
    def test_a_whole_lifecycle_walks_without_a_single_refusal(
            self, monkeypatch, chain):
        """FOUR LIFECYCLES, WALKED END TO END, and the last one is real.

        ``accepted -> done -> open -> accepted -> staged`` is
        ``run-pm-sleeve-v2#15`` on the live record — the ONLY A->B->A row in
        the whole log, and the reason this guard compares against the status
        the row CURRENTLY holds rather than every status it has ever held. A
        rule reading "has this row ever recorded accepted" refuses that fourth
        step: a genuine re-acceptance after a genuine reopen.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        for status in chain:
            r = _decide(c, status)
            assert r.status_code == 200, f"{status!r} refused in {chain}: {r.text}"
        assert [s for _, _, s in ds.decided] == list(chain)
        assert c.store.of_type("ApprovalRefused") == []

    def test_two_different_rows_do_not_see_each_others_decisions(
            self, monkeypatch):
        """The identity is (run_id, rec_id), not the run.

        Every recommendation on a run shares one aggregate, so a guard keyed
        on the run alone would refuse rec 2's first acceptance because rec 1
        had already been accepted.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _AggStore(), ds)
        assert _decide(c, "accepted", rec_id=1).status_code == 200
        assert _decide(c, "accepted", rec_id=2).status_code == 200
        assert _decide(c, "accepted", rec_id=2).status_code == 409
        assert _decide(c, "accepted", rec_id=1).status_code == 409
        assert ds.decided == [(R39_RUN, 1, "accepted"), (R39_RUN, 2, "accepted")]

    def test_two_different_runs_do_not_see_each_others_decisions(
            self, monkeypatch):
        """A re-PRESENTATION on a fresh identity is invisible here, and that is
        the honest limit of this control rather than a gap in it.

        Nothing about a new ``(run_id, rec_id)`` is derivable from an old row's
        history. The other half of R39 — one subject across a dozen-odd
        identities — lives on the ticket highway, not here.
        """
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c, "accepted", run_id="run-a").status_code == 200
        assert _decide(c, "accepted", run_id="run-b").status_code == 200


# ============================================================================
# ABSENCE DISCIPLINE — a guard that could not look never says "allowed"
# ============================================================================

class TestTheGuardSaysWhenItCouldNotLook:
    def test_a_store_without_by_aggregate_fails_OPEN_and_names_the_reason(
            self, monkeypatch):
        """Failing CLOSED here would take the CEO's decide door dark whenever
        the event store hiccups, to prevent 37 no-op events in five months.
        That is the wrong trade — but silence about it is not allowed either.
        """
        ds = _Deskstore()
        c = _client(monkeypatch, _BlindStore(), ds)
        r = _decide(c)
        assert r.status_code == 200
        assert r.json()["redecision_readable"] is False
        assert r.json()["redecision_basis"] == "store_cannot_answer"
        # It really did go through, twice, unrefused — the guard was not
        # consulted rather than consulted-and-satisfied.
        assert _decide(c).status_code == 200
        assert len(ds.decided) == 2

    def test_a_store_that_RAISES_is_told_apart_from_one_that_cannot_answer(
            self, monkeypatch):
        """Two different facts, two different words. An outage is not a wiring
        gap, and a reader who cannot tell them apart cannot fix either."""
        c = _client(monkeypatch, _AngryStore(), _Deskstore())
        r = _decide(c)
        assert r.status_code == 200
        assert r.json()["redecision_readable"] is False
        assert r.json()["redecision_basis"] == "store_error"

    def test_the_degradation_reaches_the_EVENT_not_only_the_response(
            self, monkeypatch):
        """The response is gone the moment the caller closes its terminal.

        A decision taken while the guard was blind is a fact about the record
        and belongs ON the record — otherwise a later audit sees an ordinary
        decision and has no way to know the control was not consulted.
        """
        c = _client(monkeypatch, _BlindStore(), _Deskstore())
        assert _decide(c).status_code == 200
        decided = c.store.of_type("DeskRecommendationDecided")
        assert len(decided) == 1
        assert decided[0].payload["redecision_readable"] is False
        assert decided[0].payload["redecision_basis"] == "store_cannot_answer"

    def test_a_normal_decision_records_that_the_guard_DID_look(self, monkeypatch):
        """The positive control. Without it the test above passes just as well
        against a door that never sets the field at all."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c).status_code == 200
        p = c.store.of_type("DeskRecommendationDecided")[0].payload
        assert p["redecision_readable"] is True
        assert p["redecision_basis"] == "decision_events"

    def test_the_three_bases_are_distinct_words(self):
        """A vocabulary whose members collide says nothing. Cheap, and it is
        the check that would have caught two constants set to one string."""
        from app.api.v1 import fund as fundapi
        bases = {fundapi.REDECISION_BASIS_READ,
                 fundapi.REDECISION_BASIS_NO_METHOD,
                 fundapi.REDECISION_BASIS_ERROR}
        assert len(bases) == 3


# ============================================================================
# THE STORE-DOUBLE CENSUS — the number cited in fund.py has a command
# ============================================================================

class TestTheStoreDoubleCensus:
    def _census(self):
        import importlib.util
        import pathlib
        p = (pathlib.Path(__file__).resolve().parents[1]
             / "scripts" / "instruments" / "hw4" / "store_double_census.py")
        spec = importlib.util.spec_from_file_location("hw4_store_census", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_the_fail_open_path_is_reachable_from_inside_this_suite(self):
        """THE INVARIANT, NOT THE TOTAL. The counts move as the suite grows;
        what must stay true for `redecision_basis` to earn its place is that
        some double in here cannot answer `by_aggregate`."""
        m = self._census()
        import pathlib
        out = m.census(str(pathlib.Path(__file__).resolve().parent))
        assert out["doubles"] > 0, "the census looked in the wrong place"
        assert out["without_by_aggregate"] > 0
        assert out["unparseable"] == []

    def test_it_counts_DOUBLES_and_not_files_that_mention_the_name(self, tmp_path):
        """The defect the AST version exists to fix: `grep -l` counts a file
        with two doubles once, and a module-level helper named `by_aggregate`
        as a store that has one."""
        m = self._census()
        (tmp_path / "test_two.py").write_text(
            "def by_aggregate(x):\n    return []\n\n"
            "class A:\n    def append(self, e): pass\n"
            "    def stream(self, **k): return []\n\n"
            "class B:\n    def append(self, e): pass\n"
            "    def stream(self, **k): return []\n"
            "    def by_aggregate(self, a): return []\n",
            encoding="utf-8")
        out = m.census(str(tmp_path))
        assert out["doubles"] == 2          # grep -l would have said 1 file
        assert out["with_by_aggregate"] == 1  # the loose function is not a store
        assert out["without_by_aggregate"] == 1

    def test_it_refuses_an_empty_domain_rather_than_printing_a_zero(
            self, tmp_path, capsys):
        """A zero without its domain is not a result. An empty directory and a
        suite with no doubles must not print the same clean table."""
        m = self._census()
        assert m.main(["--tests", str(tmp_path)]) == 2
        assert "REFUSED" in capsys.readouterr().err

    def test_a_class_with_only_ONE_half_of_the_shape_is_not_a_store(
            self, tmp_path):
        """A recorder is not a store and a feed is not a store.

        Found by mutation (M40): relaxing ``all`` to ``any`` survived, because
        every class in the earlier fixture had both methods. With ``any``, a
        bare recorder counts as an event store and the "can it answer
        by_aggregate" denominator quietly inflates.
        """
        m = self._census()
        (tmp_path / "test_halves.py").write_text(
            "class OnlyAppend:\n    def append(self, e): pass\n\n"
            "class OnlyStream:\n    def stream(self, **k): return []\n\n"
            "class Both:\n    def append(self, e): pass\n"
            "    def stream(self, **k): return []\n",
            encoding="utf-8")
        out = m.census(str(tmp_path))
        assert out["doubles"] == 1


# ============================================================================
# THE RE-DECISION CENSUS — the instrument the refusal counts are quoted from
# ============================================================================

class TestTheRedecisionCensus:
    """The numbers in ``_refuse_if_redecided``'s direction table come from
    here, so its two legs must be told apart and its refusal must fire."""

    def _census(self):
        import importlib.util
        import pathlib
        p = (pathlib.Path(__file__).resolve().parents[1]
             / "scripts" / "instruments" / "hw4" / "redecision_census.py")
        spec = importlib.util.spec_from_file_location("hw4_redec_census", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    #: The one A->B->A row in the live record, by shape:
    #: ``run-pm-sleeve-v2#15`` went accepted -> done -> open -> accepted ->
    #: staged. It is the ONLY population on which the census's two legs
    #: disagree, which is exactly why it is the fixture.
    _REOPEN = ["accepted", "done", "open", "accepted", "staged"]

    def _events(self, statuses, run="run-pm-sleeve-v2", rec=15):
        return [{"seq": i + 1, "run_id": run, "rec_id": rec, "status": s,
                 "actor": "ceo", "at": f"2026-08-2{i}T00:00:00Z"}
                for i, s in enumerate(statuses)]

    def test_the_reopen_separates_the_CONSECUTIVE_leg_from_the_EVER_leg(self):
        """THE WHOLE DESIGN ARGUMENT, AS A NUMBER.

        On this row the ever-repeat leg counts ONE (the second ``accepted``)
        and the consecutive leg counts ZERO — because that second acceptance
        followed a reopen and is a genuine decision, not a repeat. If the two
        legs agreed here, the guard's choice between them would be arbitrary.
        Found by mutation (M38): the two legs were computed by different
        expressions and nothing compared them.
        """
        out = self._census().census(self._events(self._REOPEN))
        assert out["ever_repeat_events_total"] == 1
        assert out["consecutive_repeat_events_total"] == 0
        assert len(out["aba_rows"]) == 1
        assert out["progression_rows"] == 1

    def test_a_true_repeat_is_counted_by_BOTH_legs(self):
        """The positive control for the test above: where there is no reopen
        the two legs must agree, or the separation proves nothing."""
        out = self._census().census(
            self._events(["accepted"] * 3, run="run-triage7-decisions", rec=1))
        assert out["ever_repeat_events_total"] == 2
        assert out["consecutive_repeat_events_total"] == 2
        assert out["aba_rows"] == []

    def test_it_REFUSES_an_empty_population_rather_than_printing_a_table(
            self, monkeypatch, capsys):
        """An unreachable database and a database with no matching events
        produce the same clean table otherwise. Found by mutation (M39): the
        refusal branch had no test at all, because reaching it needs a store.
        """
        m = self._census()
        monkeypatch.setattr(m, "pull", lambda dsn=None: (
            [], {"log_events": 0, "seq_min": None, "seq_max": None,
                 "covers_whole_log": True}))
        assert m.main([]) == 2
        assert "REFUSED" in capsys.readouterr().err

    def test_the_null_arm_states_its_domain_size(self, capsys):
        """A --null that silently compared nothing prints the same zero as one
        that compared a clean corpus."""
        m = self._census()
        assert m.main(["--null"]) == 0
        out = capsys.readouterr().out
        assert "7 events over 7 distinct rows compared" in out
