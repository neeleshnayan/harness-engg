"""Request ids, as seats write them and as doors must read them.

THE INCIDENT (COO triage #8, finding J1, chair-verified; re-measured by this
seat on 2026-08-24 over the live spine — 136 runs, 109 requests):

  * ``meta.serves_requests`` has carried **13 declarations**: 5 full uuids,
    **6 unambiguous 8-character prefixes**, 2 prose strings, 0 ambiguous.
  * ``deskhygiene`` — the only instrument that closes a request without chair
    attention — joins on the FULL id. Those six matched nothing, and it
    proposed **1 close over 73 candidates**.
  * The chair's own resolve script then hit the same trap from the other side:
    ``POST /fund/desk/requests/{8-char}/resolve`` returned **200** and wrote
    the resolution against a PHANTOM aggregate, while the real request stayed
    ``approved``. Postgres shows bare ids like ``1c53589f`` sitting there as
    aggregate ids.

Reproduce the first two: ``GET /api/v1/fund/desk/runs?limit=500``, collect
``meta.serves_requests``, and set-compare against ``GET /api/v1/fund/desk``'s
``requests[].request_id``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.fund import deskengine


# ============================================================================
# The normaliser
# ============================================================================

#: The live pool, trimmed to the ids the declarations actually reach.
KNOWN = [
    "3eeb42d4-1111-4111-8111-111111111111",
    "b6f4a407-2222-4222-8222-222222222222",
    "1c53589f-3333-4333-8333-333333333333",
    "788caa72-4444-4444-8444-444444444444",
    "a26debb9-827a-47e9-9cac-c5ca1ba2213f",
]


class TestResolveRequestIds:
    def test_the_six_live_prefixes_resolve_to_full_ids(self):
        """The measured heart of J1. Six shorthand ids matched nothing in the
        hygiene join; each is an unambiguous head of exactly one request."""
        out = deskengine.resolve_request_ids(
            ["3eeb42d4", "b6f4a407", "1c53589f", "788caa72"], KNOWN)
        assert out["ids"] == [
            "3eeb42d4-1111-4111-8111-111111111111",
            "b6f4a407-2222-4222-8222-222222222222",
            "1c53589f-3333-4333-8333-333333333333",
            "788caa72-4444-4444-8444-444444444444"]
        assert len(out["normalised"]) == 4
        assert out["ambiguous"] == [] and out["unresolved"] == []

    def test_a_full_id_passes_through_untouched_and_unreported(self):
        out = deskengine.resolve_request_ids(
            ["a26debb9-827a-47e9-9cac-c5ca1ba2213f"], KNOWN)
        assert out["ids"] == ["a26debb9-827a-47e9-9cac-c5ca1ba2213f"]
        assert out["normalised"] == []

    def test_prose_is_kept_verbatim_and_reported_unresolved(self):
        """Two live declarations are sentences ("THE DESK, REDESIGNED"). The
        record of what a run CLAIMED to serve is a fact about the filing even
        when the claim points nowhere, so it is never dropped."""
        out = deskengine.resolve_request_ids(
            ["THE DESK, REDESIGNED", "DESK GREETINGS + STEERING"], KNOWN)
        assert out["ids"] == ["THE DESK, REDESIGNED", "DESK GREETINGS + STEERING"]
        assert out["unresolved"] == out["ids"]

    def test_an_ambiguous_prefix_is_never_guessed(self):
        """Two candidates means the shorthand does not identify a request.
        Picking the first would CLOSE SOMEBODY ELSE'S TICKET — and a wrong
        close is strictly worse than an unclosed one, because the unclosed one
        is visible."""
        pool = ["abcd1234-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "abcd1234-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]
        out = deskengine.resolve_request_ids(["abcd1234"], pool)
        assert out["ids"] == ["abcd1234"], "left exactly as written"
        assert out["ambiguous"] == [{"declared": "abcd1234",
                                     "matches": sorted(pool)}]
        assert out["normalised"] == []

    @pytest.mark.parametrize("n,resolves", [
        (7, False), (8, True), (9, True), (36, True)])
    def test_the_minimum_prefix_length_is_a_boundary(self, n, resolves):
        """BOUNDARY TABLE for `MIN_ID_PREFIX = 8`. Every abbreviated id in the
        live corpus is exactly eight — the uuid head the desk prints. Seven is
        a typo, not a shorthand, and matching it would let a slip address a
        real request."""
        assert deskengine.MIN_ID_PREFIX == 8
        full = KNOWN[0]
        out = deskengine.resolve_request_ids([full[:n]], KNOWN)
        assert (out["ids"] == [full]) is resolves
        assert (out["normalised"] != []) is (resolves and n < len(full))

    def test_an_empty_pool_resolves_nothing_and_invents_nothing(self):
        """NULL TEST. With no known requests every declaration is unresolved —
        never silently normalised to itself and called clean."""
        out = deskengine.resolve_request_ids(["3eeb42d4"], [])
        assert out["ids"] == ["3eeb42d4"]
        assert out["unresolved"] == ["3eeb42d4"]
        assert out["normalised"] == []

    def test_nothing_declared_is_nothing_reported(self):
        """NULL TEST. The common case: a run that serves no request must
        produce an entirely empty account, not an advisory."""
        for empty in ([], None, "", 0):
            out = deskengine.resolve_request_ids(empty, KNOWN)
            assert out == {"ids": [], "normalised": [], "ambiguous": [],
                           "unresolved": []}

    def test_blank_declarations_are_skipped_not_stored(self):
        out = deskengine.resolve_request_ids(["", "   ", None], KNOWN)
        assert out["ids"] == []

    def test_whitespace_around_a_shorthand_still_resolves(self):
        """The validate-stripped/store-raw defect (adversary D22) in a new
        place: a trailing newline from a shell must not turn a good id into an
        unresolved one."""
        out = deskengine.resolve_request_ids(["  3eeb42d4\n"], KNOWN)
        assert out["ids"] == [KNOWN[0]]

    def test_an_unreadable_pool_does_not_crash_the_normaliser(self):
        assert deskengine.resolve_request_ids(["3eeb42d4"], None)["unresolved"] \
            == ["3eeb42d4"]


# ============================================================================
# The doors
# ============================================================================

class _MemStore:
    """An event store for THIS test only.

    THE REASON IS A DEFECT THIS FILE ALREADY CAUSED. The first draft drove
    these doors through `app.main`'s TestClient, which writes to the process-
    wide store the whole session shares — so two probe requests leaked into
    every later test that folds the event log, and **92 tests in 17 files went
    red while every one of them passed in isolation**. The full suite was clean
    on the base commit, so the pollution was unambiguously mine.

    That is the shape of a test that would be dismissed as flaky. An endpoint
    test that writes must own its store.
    """

    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):
        self.events.append({"type": e.type.value, "payload": e.payload,
                            "actor": e.actor,
                            "aggregate_type": e.aggregate_type,
                            "aggregate_id": e.aggregate_id})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


def _requested(rid: str, subject: str = "a probe request") -> dict:
    return {"type": "DeskRequested",
            "payload": {"request_id": rid, "kind": "build", "serves": "builder",
                        "subject": subject, "trace_id": rid,
                        "at": "2026-08-24T00:00:00+00:00", "actor": "cto"}}


#: The one real request these tests approve, resolve and decline against.
LIVE_ID = "1c53589f-3333-4333-8333-333333333333"


@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    store = _MemStore([_requested(LIVE_ID)])
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
    monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store = store        # type: ignore[attr-defined]
    return c


class TestAPhantomAggregateIsRefused:
    """A 200 against an id no fold has seen is the worst available shape: the
    caller believes it acted, the record says something happened, and the real
    request is untouched. Three doors; ``decline`` already looked the row up.
    """

    def test_resolve_refuses_an_unknown_id(self, client):
        r = client.post("/api/v1/fund/desk/requests/1c53589f/resolve",
                        json={"resolution": "SERVED by builder D39",
                              "actor": "cto"})
        assert r.status_code == 404, (
            "this returned 200 before 2026-08-24 and wrote a phantom "
            "aggregate")
        assert r.json()["detail"]["error"] == "no such desk request"

    def test_approve_refuses_an_unknown_id(self, client):
        r = client.post("/api/v1/fund/desk/requests/nosuchid-0000/approve",
                        json={"actor": "ceo", "confirm": "nosuchid"})
        assert r.status_code == 404
        assert r.json()["detail"]["error"] == "no such desk request"

    def test_decline_already_refused_and_still_does(self, client):
        """Named so a future refactor that unified the three doors cannot
        quietly lose the one that was already right."""
        r = client.post("/api/v1/fund/desk/requests/nosuchid-0000/decline",
                        json={"reason": "not needed", "actor": "ceo"})
        assert r.status_code == 404

    def test_the_refusal_names_the_full_id_it_could_have_meant(self, client):
        """The shorthand is what the desk PRINTS, so the caller is almost
        always one expansion away. Naming it turns the refusal into a fix
        rather than a puzzle — the chair's own resolve script is the caller
        that walked into this."""
        r = client.post(f"/api/v1/fund/desk/requests/{LIVE_ID[:8]}/resolve",
                        json={"resolution": "x", "actor": "cto"})
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == [LIVE_ID]

    def test_did_you_mean_is_EMPTY_when_nothing_matches(self, client):
        """NULL TEST (Gauntlet finding): the suggestion list was only ever
        exercised where a match existed.

        The live case that made this matter is not the shorthand one. On
        2026-08-24 at 09:03Z the chair resolved the Gold dossier against
        ``96390291-…`` — a full uuid that is a DISPATCH task_id, not a request
        id, with no ``DeskRequested`` behind it. Nothing prefix-matches it, and
        the refusal must say so with an empty list rather than reaching for the
        nearest id.

        THAT LIVE CASE IS NOW A 200 AND THIS TEST IS STILL RIGHT, which is
        worth stating so nobody reads the two as contradicting each other.
        Ticket d03c09b6 gave the resolve door the dispatch fold, so a real
        dispatch task_id resolves — see ``TestADispatchBornLampCanBeClosed``.
        THIS store holds no ``DeskDispatched`` event at all, so the id is
        genuinely unknown here and the empty suggestion list is the whole
        point: the null test survives the widening because its fixture
        contains nothing to widen INTO.
        """
        r = client.post(
            "/api/v1/fund/desk/requests/96390291-82ab-4876-904f-f18ebaaa7aac"
            "/resolve", json={"resolution": "x", "actor": "cto"})
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == []

    def test_a_short_typo_gets_no_suggestions_either(self, client):
        """Below `MIN_ID_PREFIX` nothing is matched, so nothing is suggested —
        the same bound the normaliser uses, asked at the other door."""
        r = client.post("/api/v1/fund/desk/requests/1c5358/resolve",
                        json={"resolution": "x", "actor": "cto"})
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == []

    def test_a_real_request_still_resolves(self, client):
        """THE TIGHTENING MUST ONLY REFUSE. A row that exists takes exactly the
        path it took yesterday — a guard that also blocked the good case would
        be an outage wearing a control's clothes."""
        r = client.post(f"/api/v1/fund/desk/requests/{LIVE_ID}/resolve",
                        json={"resolution": "SERVED by the probe",
                              "actor": "cto"})
        assert r.status_code == 200
        assert r.json()["request_id"] == LIVE_ID
        assert [e["type"] for e in client.store.events] == [
            "DeskRequested", "DeskRequestResolved"]

    def test_a_real_request_still_approves(self, client):
        r = client.post(f"/api/v1/fund/desk/requests/{LIVE_ID}/approve",
                        json={"actor": "ceo", "confirm": LIVE_ID[:8]})
        assert r.status_code == 200
        assert [e["type"] for e in client.store.events] == [
            "DeskRequested", "DeskRequestApproved"]

    def test_an_unreadable_fold_does_not_gate_the_approval_path(self,
                                                               monkeypatch):
        """FAILS OPEN ON A READ FAILURE, DELIBERATELY, AND SAYS SO IN THE LOG.

        This guard catches a typo; it is not one of the approval channel's
        controls. If the event store cannot be read it cannot tell "no such
        request" from "cannot tell" — and refusing every approval because a
        READ failed would turn a rendering guard into an outage on the one
        path the CEO uses. The allowlist, the echo and the supersession check
        are untouched either way.
        """
        from fastapi import FastAPI

        from app.api.v1 import fund as fundapi

        class _Broken(_MemStore):
            def stream(self, since_seq=0, limit=100_000):
                raise RuntimeError("the store is down")

        store = _Broken()
        monkeypatch.setattr(fundapi, "_store", store)
        monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
        monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
        monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
        app = FastAPI()
        app.include_router(fundapi.router, prefix="/api/v1")
        r = TestClient(app).post(
            f"/api/v1/fund/desk/requests/{LIVE_ID}/approve",
            json={"actor": "ceo", "confirm": LIVE_ID[:8]})
        assert r.status_code == 200, "a read failure must not gate approvals"


# ============================================================================
# THE LAMP-CLOSE DOOR (ticket d03c09b6)
# ============================================================================

#: The two chair-born dispatches the chair named as the live stranded lamps on
#: 2026-08-24. Both are real ``DeskDispatched.task_id`` values with no backing
#: ``DeskRequested``; both were still in flight when this was written and
#: neither is resolved here — the fixture proves the DOOR opens, and walking
#: through it is the chair's act, not a test's.
LIVE_LAMPS = ("ff8c4270-ecbc-4d6e-a8a8-64786a86c953",
              "a6976a45-c227-4262-8750-ea8372dc8b67")

#: A chair-born dispatch whose trace differs from its task_id. Ten of the 24
#: live chair-born dispatches are shaped this way, so the door must admit the
#: TASK id — which is the one a resolve names — and not only the trace.
LAMP_WITH_OTHER_TRACE = "13b1705b-577a-437d-a933-972effe6b901"


def _dispatched(task_id: str, trace_id: str = None, seat: str = "builder"):
    return {"type": "DeskDispatched",
            "payload": {"task_id": task_id, "seat": seat,
                        "task": "a chair-born dispatch", "request_id": None,
                        "trace_id": trace_id or task_id,
                        "at": "2026-08-24T00:00:00+00:00", "actor": "cto"}}


@pytest.fixture()
def lamp_client(monkeypatch):
    """A store holding one real request AND three chair-born dispatches."""
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    store = _MemStore([_requested(LIVE_ID),
                       _dispatched(LIVE_LAMPS[0], seat="adversary"),
                       _dispatched(LIVE_LAMPS[1], seat="quant"),
                       _dispatched(LAMP_WITH_OTHER_TRACE,
                                   trace_id="trace-not-the-task-id")])
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_edges_by_target", lambda: {})
    monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.store = store        # type: ignore[attr-defined]
    return c


class TestADispatchBornLampCanBeClosed:
    """THE DEFECT: since the phantom guard landed (2026-08-24) a CTO-born
    dispatch — ``DeskDispatched`` with no backing ``DeskRequested`` — has had
    NO legitimate close path. The guard reads ``desk._requests``, which folds
    ``DeskRequested`` and has never heard of a chair-born dispatch, while
    ``desk._activity`` closes exactly that lamp on a ``DeskRequestResolved``
    naming its ``task_id`` (desk.py:781-790). Measured on the live record the
    day of the fix: 24 chair-born dispatches, 30 resolutions that had already
    landed against them historically, and 8 lamps burning with no way out.

    That is failure #4 in the ticket-highway design's own table, stated as its
    own falsifier: *any dispatch exists that no legitimate event can close*.
    """

    def test_a_dispatch_born_id_resolves(self, lamp_client):
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[0]}/resolve",
            json={"resolution": "docs/reviews/ADVERSARY.md", "actor": "cto"})
        assert r.status_code == 200, (
            "this returned 404 between the phantom guard landing and "
            "d03c09b6 — a lamp with no door")
        assert [e["type"] for e in lamp_client.store.events][-1] \
            == "DeskRequestResolved"

    def test_the_activity_fold_then_retires_the_lamp(self, lamp_client):
        """THE CLOSE IS ONLY REAL IF THE SURFACE MOVES. A 200 that left the
        seat's lamp lit would be the same phantom shape pointing the other
        way, so this asserts the fold, not the status code."""
        from app.fund import desk
        before = desk._activity(lamp_client.store, runs=[])
        assert before["adversary"]["status"] == "working"
        lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[0]}/resolve",
            json={"resolution": "docs/reviews/ADVERSARY.md", "actor": "cto"})
        after = desk._activity(lamp_client.store, runs=[])
        assert after["adversary"]["status"] == "idle"
        assert after["adversary"]["last_delivered"]["artifact"] \
            == "docs/reviews/ADVERSARY.md"

    def test_the_second_live_lamp_closes_too(self, lamp_client):
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[1]}/resolve",
            json={"resolution": "docs/belt/QUANT.md", "actor": "cto"})
        assert r.status_code == 200

    def test_a_lamp_whose_trace_differs_from_its_task_id_closes(self,
                                                                lamp_client):
        """The door is addressed by ``task_id``. Ten of the 24 live chair-born
        dispatches carry a different ``trace_id``, so a guard that admitted the
        trace instead would have fixed the minority case and looked correct."""
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LAMP_WITH_OTHER_TRACE}/resolve",
            json={"resolution": "docs/x.md", "actor": "cto"})
        assert r.status_code == 200

    def test_the_trace_id_itself_is_NOT_a_door(self, lamp_client):
        """The other direction of the same fact, and the reason the widening
        is bounded: the admitted set is exactly what ``DeskDispatched.task_id``
        named. A trace string is not an address."""
        r = lamp_client.post(
            "/api/v1/fund/desk/requests/trace-not-the-task-id/resolve",
            json={"resolution": "docs/x.md", "actor": "cto"})
        assert r.status_code == 404

    def test_a_never_seen_id_is_still_refused(self, lamp_client):
        """THE TEST THAT MUST NOT BE ABLE TO BLESS THE BUG. The widening is
        real, so the guard's whole purpose has to be re-proven beside it: the
        8-character shorthands sitting in Postgres as aggregate ids are in
        NEITHER fold and still 404."""
        for phantom in ("1c53589f", "nosuchid-0000",
                        "00000000-0000-4000-8000-000000000000"):
            r = lamp_client.post(
                f"/api/v1/fund/desk/requests/{phantom}/resolve",
                json={"resolution": "docs/nowhere.md", "actor": "cto"})
            assert r.status_code == 404, phantom
            assert r.json()["detail"]["error"] == "no such desk request"
        assert [e["type"] for e in lamp_client.store.events] == [
            "DeskRequested", "DeskDispatched", "DeskDispatched",
            "DeskDispatched"], "no phantom wrote anything"

    def test_the_refusal_says_which_folds_it_consulted(self, lamp_client):
        r = lamp_client.post("/api/v1/fund/desk/requests/1c53589f/resolve",
                             json={"resolution": "x", "actor": "cto"})
        assert r.json()["detail"]["folds_consulted"] == ["requests",
                                                         "dispatches"]

    def test_a_dispatch_shorthand_is_expanded_by_did_you_mean(self,
                                                              lamp_client):
        """``did_you_mean`` draws from whatever set the door accepts, so the
        help follows the door rather than lagging one fold behind it."""
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[0][:8]}/resolve",
            json={"resolution": "x", "actor": "cto"})
        assert r.status_code == 404
        assert r.json()["detail"]["did_you_mean"] == [LIVE_LAMPS[0]]


class TestTheApprovalDoorIsUnchanged:
    """THE WIDENING IS BOUNDED TO ONE DOOR, and this class is the boundary.

    Approving a chair-born dispatch is meaningless — there is no request to
    bless — and it would write a ``DeskRequestApproved`` against an aggregate
    ``desk._requests`` ignores, which is precisely the phantom shape the guard
    exists to stop. Measured before the choice was made: of the 7 live
    ``DeskRequestApproved`` events naming an id outside the requests fold,
    ZERO name a dispatch task_id. Nothing historical is served by widening it.
    """

    def test_approve_still_refuses_a_dispatch_born_id(self, lamp_client):
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[0]}/approve",
            json={"actor": "ceo", "confirm": LIVE_LAMPS[0][:8]})
        assert r.status_code == 404
        assert r.json()["detail"]["folds_consulted"] == ["requests"]

    def test_decline_still_refuses_a_dispatch_born_id(self, lamp_client):
        """``desk_decline`` looks the row up in ``_requests`` directly and was
        never routed through this guard; named here so a future unification of
        the three doors cannot widen it by accident."""
        r = lamp_client.post(
            f"/api/v1/fund/desk/requests/{LIVE_LAMPS[0]}/decline",
            json={"reason": "no", "actor": "ceo"})
        assert r.status_code == 404


class TestTheDispatchFold:
    def test_it_names_every_dispatched_task_id(self, lamp_client):
        from app.fund import desk
        assert desk.dispatched_task_ids(lamp_client.store) == {
            LIVE_LAMPS[0], LIVE_LAMPS[1], LAMP_WITH_OTHER_TRACE}

    def test_it_is_a_different_question_from_dispatched_request_ids(
            self, lamp_client):
        """Chair-born dispatches carry no ``request_id``, so the older fold
        sees NONE of them. Two folds, two questions — and only one of them
        contains a lamp's id."""
        from app.fund import desk
        assert desk.dispatched_request_ids(lamp_client.store) == set()
        assert len(desk.dispatched_task_ids(lamp_client.store)) == 3

    def test_an_unreadable_store_narrows_the_door_rather_than_opening_it(self):
        """FAILS CLOSED, and that is deliberately the opposite direction from
        the requests read: this fold can only ADD ids, so losing it can only
        refuse. An empty set is the safe answer; a raise would take the door
        down and a fabricated set would admit anything."""
        from app.fund import desk

        class _Broken(_MemStore):
            def stream(self, since_seq=0, limit=100_000):
                raise RuntimeError("the store is down")

        assert desk.dispatched_task_ids(_Broken()) == set()
