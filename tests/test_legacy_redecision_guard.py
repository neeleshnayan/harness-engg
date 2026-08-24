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
    """Records what was written, so a refused decision can be proven silent."""

    def __init__(self):
        self.decided = []

    def decide_recommendation(self, run_id, rec_id, status, actor, note="",
                              next_actor=None):
        self.decided.append((run_id, rec_id, status))
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
            actor="ceo", note="triage 7"):
    return client.post(
        f"/api/v1/fund/desk/runs/{run_id}/recommendations/{rec_id}",
        json={"status": status, "actor": actor, "note": note})


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
        not a standing licence."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert _decide(c, "accepted").status_code == 200
        assert _decide(c, "done").status_code == 200
        r = _decide(c, "done")
        assert r.status_code == 409
        assert r.json()["detail"]["attempted"] == "done"
        assert r.json()["detail"]["decision_count"] == 2

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
