"""The ticket fold — slice 1 of the ticket highway.

WHAT THESE TESTS DEFEND, named so a future reader can tell a guard from a
decoration. Each class heads the defect it exists to catch:

  * **The reconciliation.** Slice 1's stated acceptance is that the fold's
    counts reconcile with ``desk_load``'s partition. The tests compute
    ``desk_load`` INDEPENDENTLY from the same fixture and assert every leg —
    if the two instruments ever disagree, the suite names which leg.
  * **Terminal precedence.** ``desk._requests`` is order-honest, not
    last-write-wins (desk.py:655-677): a resolution must never overwrite a
    decline, because executing a declined ask is the chair overriding the
    CEO's no. The fold inherits that rule and a test breaks if it drifts to
    last-write-wins.
  * **Absence is never zero.** ``DeskStore.all_runs`` does not SELECT the
    ``recommendations`` column, so a fold built on it reports 0
    recommendation tickets against a live record holding 550 — a stable,
    plausible, entirely false number. Two tests pin the distinction between
    "not read" and "none".
  * **Zero write paths.** Slice 1's third acceptance criterion, asserted by
    AST rather than by reading the diff.

THE FIXTURE IS A MINIATURE OF THE LIVE RECORD, not an invented shape. Every
species in it was measured on the live event log 2026-08-24 before it was
written down: a request dispatched while still ``open`` (1 live), a chair-born
dispatch whose ``trace_id`` differs from its ``task_id`` (10 of 24 live), a
duplicate resolution (24 live), and a run whose trace lands on no ticket (127
of 145 live).
"""

from __future__ import annotations

import ast
import pathlib

import pytest
from fastapi.testclient import TestClient

from app.fund import desk, tickets
from app.fund.deskstore import DeskStore


# ---------------------------------------------------------------- fixtures --

class _MemStore:
    """An event store for THIS test only.

    The house rule since D39: an endpoint test must own its store, because the
    process-wide one is shared and two probe events once turned 92 unrelated
    tests red while every one of them passed in isolation.
    """

    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):        # pragma: no cover - the fold never writes
        raise AssertionError("the ticket fold must not append")

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


def _ev(t: str, payload: dict) -> dict:
    return {"type": t, "payload": payload}


R_OPEN = "11111111-1111-4111-8111-111111111111"
R_DISPATCHED = "22222222-2222-4222-8222-222222222222"
R_APPROVED = "33333333-3333-4333-8333-333333333333"
R_RESOLVED = "44444444-4444-4444-8444-444444444444"
R_DECLINED = "55555555-5555-4555-8555-555555555555"
#: An approved request whose DISPATCH carries a different ``trace_id`` from the
#: request's own. This is the case that distinguishes "transition the request"
#: from "mint a second ticket", and a fixture without it cannot see the
#: difference — 11 of the 12 live dispatches-with-a-request share the trace, so
#: the majority case hides the fork.
R_TRACE_DIFFERS = "88888888-8888-4888-8888-888888888888"
D_OTHER_TRACE = "a-trace-the-dispatch-minted-for-itself"
#: A chair-born dispatch whose trace differs from its task_id. Ten of the 24
#: live chair-born dispatches are shaped this way, which is why the fold keeps
#: an alias index instead of keying on the trace alone.
D_STRANDED = "66666666-6666-4666-8666-666666666666"
D_CLOSED_TASK = "77777777-7777-4777-8777-777777777777"
D_CLOSED_TRACE = "trace-for-the-closed-dispatch"


def _requested(rid, subject="an ask", seat="builder", at="2026-08-20T00:00:00Z"):
    return _ev("DeskRequested",
               {"request_id": rid, "kind": "build", "serves": seat,
                "subject": subject, "trace_id": rid, "at": at, "actor": "cto"})


def _events():
    return [
        _requested(R_OPEN, "an ask nobody has touched"),
        _requested(R_DISPATCHED, "an ask already being worked"),
        _requested(R_APPROVED, "an ask the CEO blessed"),
        _requested(R_RESOLVED, "an ask that was served"),
        _requested(R_DECLINED, "an ask the CEO refused"),
        _requested(R_TRACE_DIFFERS, "an ask dispatched on a fresh trace"),
        _ev("DeskRequestApproved",
            {"request_id": R_TRACE_DIFFERS, "actor": "ceo",
             "at": "2026-08-21T00:30:00Z"}),
        _ev("DeskDispatched",
            {"task_id": R_TRACE_DIFFERS, "request_id": R_TRACE_DIFFERS,
             "seat": "analyst", "task": "an ask dispatched on a fresh trace",
             "trace_id": D_OTHER_TRACE, "at": "2026-08-21T00:45:00Z",
             "actor": "cto"}),
        # THE DIVERGENCE CASE, measured live: dispatched while still `open`.
        _ev("DeskDispatched",
            {"task_id": R_DISPATCHED, "request_id": R_DISPATCHED,
             "seat": "builder", "task": "an ask already being worked",
             "trace_id": R_DISPATCHED, "at": "2026-08-21T00:00:00Z",
             "actor": "cto"}),
        _ev("DeskRequestApproved",
            {"request_id": R_APPROVED, "actor": "ceo",
             "at": "2026-08-21T01:00:00Z"}),
        _ev("DeskRequestApproved",
            {"request_id": R_RESOLVED, "actor": "ceo",
             "at": "2026-08-21T02:00:00Z"}),
        _ev("DeskRequestResolved",
            {"request_id": R_RESOLVED, "resolution": "docs/served.md",
             "at": "2026-08-21T03:00:00Z", "actor": "cto"}),
        # A DUPLICATE RESOLUTION. 24 live on the record; the fold must refuse
        # it and SAY it refused it.
        _ev("DeskRequestResolved",
            {"request_id": R_RESOLVED, "resolution": "docs/served-again.md",
             "at": "2026-08-21T04:00:00Z", "actor": "cto"}),
        _ev("DeskRequestDeclined",
            {"request_id": R_DECLINED, "reason": "not now",
             "at": "2026-08-21T05:00:00Z", "actor": "ceo"}),
        # AND A RESOLUTION AGAINST THE DECLINED ROW. This is the one that must
        # never apply: it would be the chair executing what the CEO refused.
        _ev("DeskRequestResolved",
            {"request_id": R_DECLINED, "resolution": "docs/did-it-anyway.md",
             "at": "2026-08-21T06:00:00Z", "actor": "cto"}),
        # A chair-born dispatch that nothing ever closed — the lamp.
        _ev("DeskDispatched",
            {"task_id": D_STRANDED, "seat": "adversary", "task": "a review",
             "trace_id": D_STRANDED, "at": "2026-08-22T00:00:00Z",
             "actor": "cto"}),
        # A chair-born dispatch whose trace differs from its task_id, closed
        # by a resolve naming the TASK id. The alias index is what makes that
        # land; keyed on the trace alone it would be a phantom.
        _ev("DeskDispatched",
            {"task_id": D_CLOSED_TASK, "seat": "quant", "task": "a belt run",
             "trace_id": D_CLOSED_TRACE, "at": "2026-08-22T01:00:00Z",
             "actor": "cto"}),
        _ev("DeskRequestResolved",
            {"request_id": D_CLOSED_TASK, "resolution": "docs/belt.md",
             "at": "2026-08-22T02:00:00Z", "actor": "cto"}),
        # A phantom: an 8-character shorthand no fold has ever seen.
        _ev("DeskRequestResolved",
            {"request_id": "1c53589f", "resolution": "docs/nowhere.md",
             "at": "2026-08-22T03:00:00Z", "actor": "cto"}),
    ]


def _rec(rec_id, status, **kw):
    return {"rec_id": rec_id, "seat": "builder", "status": status,
            "text": f"recommendation {rec_id}", "kind": kw.pop("kind", None),
            "trace_id": kw.pop("trace_id", None),
            "money_at_stake": None, "due_date": None, "reversibility": None,
            **kw}


def _runs():
    return [
        {"run_id": "run-linked", "seat": "builder", "task": "the linked run",
         "trace_id": R_OPEN, "resolved_at": "2026-08-23T00:00:00Z",
         "artifact_path": "docs/a.md",
         "recommendations": [
             _rec(1, "open"),                       # -> ceo (default)
             _rec(2, "open", kind="build"),         # -> chair (kind)
             _rec(3, "accepted"),                   # -> chair (lifecycle)
             _rec(4, "staged"),                     # -> chair (lifecycle)
             _rec(5, "open", kind="note_to_riskofficer"),   # -> seat
             _rec(6, "open", next_actor="nobody"),  # -> nobody (explicit)
             _rec(7, "open", status_note="x", kind="no_action"),  # -> nobody
             _rec(8, "done", decided_by="ceo",
                  decided_at="2026-08-23T01:00:00Z"),
             _rec(9, "rejected", decided_by="ceo",
                  decided_at="2026-08-23T02:00:00Z"),
             _rec(10, "noted", decided_by="cto",
                  decided_at="2026-08-23T03:00:00Z"),
             # AN UNREADABLE ROUTING CLAIM -> actor `unknown`. Three live on
             # 2026-08-24, and it is the row that makes the CEO leg's
             # `ceo OR unknown` branch reachable: `desk_load` counts an
             # undeterminable actor toward the CEO because it is work he may
             # still owe (desk.py:1304-1307), and a fixture without one lets
             # a fold that counted only `ceo` reconcile perfectly.
             _rec(11, "open", next_actor="legal"),
         ]},
        # A run whose trace lands on NO ticket — 117 of the 135 runs that carry
        # recommendations, live 2026-08-24 (hw1_recount.py). Its children
        # are fenced as pre-highway, never guessed a parent.
        {"run_id": "run-unlinked", "seat": "quant", "task": "the orphan run",
         "trace_id": "a-trace-nothing-else-carries",
         "resolved_at": "2026-08-23T04:00:00Z", "artifact_path": None,
         "recommendations": [_rec(1, "open")]},
    ]


class _FakeDeskStore:
    """Duck-typed run source that REUSES the real ``open_recommendations``.

    The method is bound off ``DeskStore`` rather than re-implemented, so the
    "which statuses are still open" rule the reconciliation rests on is read
    from production code. A test that re-stated that filter could agree with a
    fold that had drifted from the store.
    """

    def __init__(self, runs):
        self._runs = list(runs)

    def runs(self, limit=50, **kw):
        return list(self._runs)[:limit]

    open_recommendations = DeskStore.open_recommendations


@pytest.fixture()
def folded():
    return tickets.fold(_MemStore(_events()), runs=_runs(), runs_limit=1000,
                        now="2026-08-24T00:00:00Z")


def _by_id(folded):
    return {t["ticket_id"]: t for t in folded["tickets"]}


# ============================================================================
# THE ACCEPTANCE: every species appears exactly once
# ============================================================================

class TestEverythingAppearsExactlyOnce:
    def test_ticket_ids_are_unique(self, folded):
        ids = [t["ticket_id"] for t in folded["tickets"]]
        assert len(ids) == len(set(ids))

    def test_every_request_becomes_exactly_one_ask_ticket(self, folded):
        rows = desk._requests(_MemStore(_events()))
        asks = [t for t in folded["tickets"] if t["type"] == "ask"]
        assert len(asks) == len(rows) == 6
        assert {t["request_id"] for t in asks} == {r["request_id"] for r in rows}

    def test_a_chair_born_dispatch_is_a_ticket_born_in_flight(self, folded):
        d = _by_id(folded)[D_STRANDED]
        assert d["type"] == "dispatch" and d["state"] == "in_flight"
        assert d["transitions"] == [
            {"from": None, "to": "in_flight", "at": "2026-08-22T00:00:00Z",
             "actor": "cto", "basis": "birth"}]

    def test_a_dispatch_naming_a_request_transitions_it_rather_than_forking(
            self, folded):
        """One piece of work keeps one id. A dispatch that named its request
        must NOT mint a second ticket — that is failure #1 (linkage rot) in
        the design's own table.

        THE FIXTURE HERE IS THE WHOLE TEST, and the first version of it was
        VACUOUS: it asserted that a made-up id shape (``dispatch:<uuid>``) was
        absent, which the code could never have produced either way, and the
        mutant that removed the transition branch SURVIVED. The distinguishing
        case is a dispatch whose ``trace_id`` differs from its request's — 11
        of the 12 live ones share the trace, so on the common shape a forking
        fold reaches the identical answer by a different road.
        """
        t = _by_id(folded)[R_TRACE_DIFFERS]
        assert t["type"] == "ask" and t["state"] == "in_flight"
        assert [x["to"] for x in t["transitions"]] \
            == ["filed", "approved", "in_flight"]
        assert D_OTHER_TRACE not in _by_id(folded), \
            "the dispatch's own trace must not become a second ticket"
        assert folded["counts"]["by_type"]["dispatch"] == 2, \
            "only the two CHAIR-BORN dispatches are dispatch tickets"

    def test_the_common_shape_transitions_too(self, folded):
        """The same rule where the dispatch shares its request's trace."""
        t = _by_id(folded)[R_DISPATCHED]
        assert t["type"] == "ask" and t["state"] == "in_flight"
        assert [x["to"] for x in t["transitions"]] == ["filed", "in_flight"]

    def test_every_stored_recommendation_becomes_exactly_one_child(self,
                                                                   folded):
        recs = [r for run in _runs() for r in run["recommendations"]]
        children = [t for t in folded["tickets"]
                    if t["type"] == "recommendation"]
        assert len(children) == len(recs) == 12

    def test_a_child_of_a_linked_run_carries_its_parent(self, folded):
        t = _by_id(folded)["rec:run-linked#1"]
        assert t["parent_id"] == R_OPEN
        assert t["parent_basis"] == "run_trace_id"

    def test_a_child_of_an_unlinkable_run_is_fenced_not_guessed(self, folded):
        t = _by_id(folded)["rec:run-unlinked#1"]
        assert t["parent_id"] is None
        assert t["parent_basis"] == "unlinkable_pre_highway"
        assert folded["counts"]["unlinked_children"] == 1

    def test_the_type_partition_sums_to_the_population(self, folded):
        c = folded["counts"]
        assert sum(c["by_type"].values()) == c["total"] == len(folded["tickets"])
        assert sum(c["by_state"].values()) == c["total"]
        assert sum(c["by_next_actor"].values()) == c["total"]
        assert c["working"] + c["terminal"] == c["total"]

    def test_every_actor_renders_even_at_zero(self, folded):
        """A key that disappears when its count reaches zero is absence-as-
        silence: a client reading ``by_next_actor["seat"]`` would raise on the
        good news. Seeded from ``desk.NEXT_ACTORS`` so the two vocabularies
        cannot drift.

        THE SECOND FOLD IS THE TEST. The main fixture happens to populate all
        five actors, so asserting over it would pass on a dict that seeds
        nothing — the assertion needs a population where an actor is genuinely
        absent, and a single open ask is one."""
        assert set(folded["counts"]["by_next_actor"]) == set(desk.NEXT_ACTORS)
        lone = tickets.fold(_MemStore([_requested(R_OPEN)]), runs=[],
                            now="2026-08-24T00:00:00Z")
        actors = lone["counts"]["by_next_actor"]
        assert set(actors) == set(desk.NEXT_ACTORS)
        # Routing v2 (2026-08-27, CEO "4. Yes"): an OPEN ask is the CHAIR's
        # move now, not the CEO's. v1 pinned ceo == 1 here.
        assert actors["chair"] == 1
        assert actors["seat"] == 0 and actors["nobody"] == 0 \
            and actors["ceo"] == 0 and actors["unknown"] == 0


# ============================================================================
# THE ACCEPTANCE: the counts reconcile with desk_load's partition
# ============================================================================

class TestReconciliationWithDeskLoad:
    """Slice 1's falsifiable acceptance, with the arithmetic stated.

    ``desk_load`` is computed here from the SAME fixture through the real
    ``desk`` module, so this is two instruments over one record rather than a
    fold compared with a number somebody typed.
    """

    @pytest.fixture()
    def load(self):
        store = _MemStore(_events())
        reqs = desk._requests(store)
        open_reqs = [r for r in reqs if r["status"] == "open"]
        ds = _FakeDeskStore(_runs())
        return desk.desk_load(ds.open_recommendations(), [], open_reqs,
                              chair_backlog=None)

    def test_the_ceo_recommendation_leg_agrees(self, folded, load):
        assert folded["reconciliation"]["recommendation_ceo"] \
            == load["components"]["open_recommendations"]

    def test_the_open_request_leg_agrees(self, folded, load):
        # ROUTING v2 (2026-08-27, CEO decision): open asks are the CHAIR's
        # move, so the fold's open-ask count agrees with the CHAIR leg of the
        # census and the CEO component reads zero. The AGREEMENT between the
        # two instruments is the invariant; the addressee moved.
        assert folded["reconciliation"]["ask_legacy_open"] \
            == load["requests_by_actor"]["chair"]
        assert load["components"]["requests_awaiting_approval"] == 0

    def test_the_decided_and_elsewhere_legs_agree(self, folded, load):
        r = folded["reconciliation"]
        assert r["recommendation_decided_awaiting_execution"] \
            == load["decided_awaiting_execution"]
        assert r["recommendation_open_elsewhere"] == load["open_elsewhere"]

    def test_the_working_recommendation_population_agrees(self, folded):
        # 9 = run-linked's six `open` (1, 2, 5, 6, 7, 11) + `accepted` 3 +
        # `staged` 4, plus run-unlinked's single `open`. Re-derived from the
        # fixture rather than copied from a previous run of this test.
        assert folded["reconciliation"]["recommendation_working"] \
            == len(_FakeDeskStore(_runs()).open_recommendations()) == 9

    def test_desk_load_total_is_derivable_from_the_fold(self, folded, load):
        """THE HEADLINE IDENTITY. Reproduced on the live record 2026-08-24:
        38 + 0 + 16 = 54, all seven legs exact
        (``scratchpad/hw1_reconcile.py``)."""
        r = folded["reconciliation"]
        pending = load["components"]["pending_orders"]
        # ROUTING v2: open asks left the CEO's figure for the chair's, so the
        # identity is recommendations + pending. The asks are still counted —
        # requests_by_actor.chair carries them — they are just not HIS.
        assert r["recommendation_ceo"] + pending == load["total"]
        assert r["ask_legacy_open"] == load["requests_by_actor"]["chair"]
        assert r["total_less_pending_orders"] == load["total"] - pending

    def test_the_recommendation_partition_is_exhaustive(self, folded):
        """THREE INDEPENDENT TALLIES THAT MUST SUM. This was a tautology while
        ``elsewhere`` was ``working - ceo - decided``: a remainder absorbs
        every misclassification by construction, so the assertion could not
        fail however badly the other two legs classified. All three are counted
        directly now, and this line is a check rather than a restatement."""
        r = folded["reconciliation"]
        assert (r["recommendation_ceo"]
                + r["recommendation_decided_awaiting_execution"]
                + r["recommendation_open_elsewhere"]) \
            == r["recommendation_working"]
        assert r["recommendation_open_elsewhere"] > 0, \
            "and the fixture must actually populate the third leg, or the " \
            "sum above holds trivially at zero"

    def test_the_run_cap_divergence_is_published(self):
        """THE GAUNTLET'S SHARPEST FIND, made a first-class field.
        ``open_recommendations`` scans the newest ``OPEN_RECS_RUN_CAP`` runs;
        this fold takes the caller's larger cap. Past the cap ``desk_load``
        reads a strict SUBSET and every reconciliation leg drifts with nothing
        on either surface to point at. A matter of WHEN, not if: 145 runs
        against a cap of 200 on 2026-08-24."""
        from app.fund.deskstore import OPEN_RECS_RUN_CAP
        under = [{"run_id": f"r{i}", "seat": "s", "task": "t",
                  "trace_id": None, "resolved_at": None,
                  "recommendations": []}
                 for i in range(OPEN_RECS_RUN_CAP)]
        f = tickets.fold(_MemStore([]), runs=under, runs_limit=5000,
                         now="2026-08-24T00:00:00Z")
        assert f["counts"]["reconciles_with_desk_load"] is True
        assert f["counts"]["desk_load_runs_cap"] == OPEN_RECS_RUN_CAP
        over = under + [{"run_id": "r-over", "seat": "s", "task": "t",
                         "trace_id": None, "resolved_at": None,
                         "recommendations": []}]
        g = tickets.fold(_MemStore([]), runs=over, runs_limit=5000,
                         now="2026-08-24T00:00:00Z")
        assert g["counts"]["reconciles_with_desk_load"] is False

    def test_the_cap_is_READ_from_deskstore_not_copied(self, monkeypatch):
        """MOVE IT TO PROVE IT. An assertion that the fold's cap equals
        deskstore's cannot tell a read from a duplicate that happens to agree,
        so this moves the source and requires the fold to move with it."""
        import app.fund.deskstore as ds_mod
        monkeypatch.setattr(ds_mod, "OPEN_RECS_RUN_CAP", 3)
        rows = [{"run_id": f"r{i}", "seat": "s", "task": "t", "trace_id": None,
                 "resolved_at": None, "recommendations": []}
                for i in range(4)]
        f = tickets.fold(_MemStore([]), runs=rows, runs_limit=5000,
                         now="2026-08-24T00:00:00Z")
        assert f["counts"]["desk_load_runs_cap"] == 3
        assert f["counts"]["reconciles_with_desk_load"] is False

    def test_open_recommendations_actually_uses_the_named_cap(self,
                                                              monkeypatch):
        """MUTATION SURVIVOR M43: naming the constant is not the same as using
        it. Changing ``open_recommendations`` to scan 201 runs while the
        constant still read 200 killed no test — the fold would then publish a
        cap that is not the one the other instrument obeys, which is a
        confident wrong answer with a citation attached. This drives the REAL
        ``DeskStore.open_recommendations`` (bound onto the fake), so the
        constant and its one use are pinned together."""
        import app.fund.deskstore as ds_mod
        monkeypatch.setattr(ds_mod, "OPEN_RECS_RUN_CAP", 1)
        two = [{"run_id": "r1", "seat": "s", "task": "t", "trace_id": None,
                "resolved_at": None, "artifact_path": None,
                "recommendations": [_rec(1, "open")]},
               {"run_id": "r2", "seat": "s", "task": "t", "trace_id": None,
                "resolved_at": None, "artifact_path": None,
                "recommendations": [_rec(1, "open")]}]
        assert len(_FakeDeskStore(two).open_recommendations()) == 1
        monkeypatch.setattr(ds_mod, "OPEN_RECS_RUN_CAP", 2)
        assert len(_FakeDeskStore(two).open_recommendations()) == 2

    def test_an_unknown_run_count_is_not_reported_as_agreement(self):
        """None, never True: "we did not look" must not render as "the two
        instruments agree"."""
        f = tickets.fold(_MemStore([]), runs=None,
                         now="2026-08-24T00:00:00Z")
        assert f["counts"]["reconciles_with_desk_load"] is None

    def test_the_ask_identity_names_the_dispatched_while_open_gap(self, folded):
        """THE MEASURED DIVERGENCE, made an invariant rather than an
        off-by-one. ``desk._requests`` has no ``in_flight`` state, so a
        request already being worked still reads ``open`` and still counts as
        a decision awaiting the CEO — one live row on 2026-08-24. The two
        legs are counted independently, so this identity can fail."""
        r = folded["reconciliation"]
        assert r["ask_dispatched_while_open"] == 1
        assert r["ask_legacy_open"] == r["ask_filed"] \
            + r["ask_dispatched_while_open"]

    def test_a_dispatched_ask_is_not_silently_dropped_from_the_ceo_leg(
            self, folded, load):
        """The direction guard on the finding above. Routing the asks off the
        CEO's figure (routing v2) must not become HIDING them: the fold's
        count still equals what ``desk_load`` publishes on the chair leg,
        gap and all. A dispatched ask that vanished from BOTH legs would
        fail here."""
        assert folded["reconciliation"]["ask_legacy_open"] == 2
        assert load["requests_by_actor"]["chair"] == 2
        assert load["components"]["requests_awaiting_approval"] == 0


# ============================================================================
# TERMINAL PRECEDENCE — order-honest, never last-write-wins
# ============================================================================

class TestTerminalPrecedence:
    def test_a_resolution_never_overwrites_a_decline(self, folded):
        """desk.py:669-674's rule, inherited. Executing a declined ask would
        be the chair overriding the CEO's no, and a fold that let the later
        event win would report it as done."""
        t = _by_id(folded)[R_DECLINED]
        assert t["state"] == "declined"
        # The refused resolution must not have written its artifact either. The
        # first version of this line was `assert t["citation"] is None if
        # "citation" in t else True` — a conditional EXPRESSION that evaluates
        # to True whenever the key is absent, which is always. A vacuous
        # assertion that reads like a check is worse than no line at all.
        assert "citation" not in t
        assert "resolved_at" not in t
        assert [(x["from"], x["to"]) for x in t["refused_transitions"]] \
            == [("declined", "done")]

    def test_a_duplicate_resolution_is_refused_and_recorded(self, folded):
        t = _by_id(folded)[R_RESOLVED]
        assert t["state"] == "done"
        assert t["citation"] == "docs/served.md", \
            "the FIRST resolution's artifact stands; the second is not a fact"
        assert len(t["refused_transitions"]) == 1

    def test_an_approval_only_moves_an_open_request(self):
        """desk.py:656. An approval landing after a resolve must not revive
        the row."""
        f = tickets.fold(_MemStore([
            _requested(R_OPEN),
            _ev("DeskRequestResolved", {"request_id": R_OPEN,
                                        "resolution": "docs/x.md",
                                        "at": "2026-08-21T00:00:00Z"}),
            _ev("DeskRequestApproved", {"request_id": R_OPEN, "actor": "ceo",
                                        "at": "2026-08-22T00:00:00Z"}),
        ]), runs=[], now="2026-08-24T00:00:00Z")
        t = _by_id(f)[R_OPEN]
        assert t["state"] == "done" and t["legacy_status"] == "resolved"
        assert [(x["from"], x["to"]) for x in t["refused_transitions"]] \
            == [("done", "approved")]

    def test_a_declined_request_cannot_be_dispatched(self):
        f = tickets.fold(_MemStore([
            _requested(R_DECLINED),
            _ev("DeskRequestDeclined", {"request_id": R_DECLINED,
                                        "reason": "no",
                                        "at": "2026-08-21T00:00:00Z"}),
            _ev("DeskDispatched", {"task_id": R_DECLINED,
                                   "request_id": R_DECLINED, "seat": "builder",
                                   "task": "t", "trace_id": R_DECLINED,
                                   "at": "2026-08-22T00:00:00Z"}),
        ]), runs=[], now="2026-08-24T00:00:00Z")
        assert _by_id(f)[R_DECLINED]["state"] == "declined"

    def test_the_fold_agrees_with_desk_requests_on_every_terminal(self, folded):
        """The two instruments over one record, row by row. ``desk._requests``
        is the incumbent and the fold must not quietly disagree with it about
        which rows are closed."""
        legacy = {r["request_id"]: r["status"]
                  for r in desk._requests(_MemStore(_events()))}
        for t in folded["tickets"]:
            if t["type"] == "ask":
                assert t["legacy_status"] == legacy[t["request_id"]]


# ============================================================================
# THE LAMP: a chair-born dispatch has a legitimate close
# ============================================================================

class TestTheDispatchLifecycle:
    def test_a_resolve_naming_a_task_id_closes_the_dispatch_ticket(self,
                                                                   folded):
        """Ticket d03c09b6, the structural half. The activity fold already
        closes on this event (desk.py:781-790); before the ticket fold there
        was no ENTITY it closed."""
        t = _by_id(folded)[D_CLOSED_TRACE]
        assert t["type"] == "dispatch" and t["state"] == "done"
        assert t["citation"] == "docs/belt.md"

    def test_a_stranded_lamp_is_still_in_flight_and_owed_to_the_chair(self,
                                                                      folded):
        t = _by_id(folded)[D_STRANDED]
        assert t["state"] == "in_flight" and t["next_actor"] == "chair"
        assert t["next_actor_basis"] == "dispatch_lifecycle"

    def test_returned_is_reported_unknown_never_fabricated(self, folded):
        """Legacy resolves carry no separate returned stage (memo §1.4). The
        fold must say UNKNOWN rather than invent the instant the seat came
        back."""
        t = _by_id(folded)[D_CLOSED_TRACE]
        assert t["returned_at"] is None
        assert t["returned_basis"] == "unknown"

    def test_an_event_naming_an_unknown_id_is_listed_not_ticketed(self,
                                                                  folded):
        """A ticket born from a phantom would launder the defect into a row.
        17 such events on the live record."""
        assert folded["phantom_events"] == [
            {"event": "DeskRequestResolved", "id": "1c53589f",
             "at": "2026-08-22T03:00:00Z"}]
        assert "1c53589f" not in _by_id(folded)


# ============================================================================
# ABSENCE IS NEVER ZERO
# ============================================================================

class TestAbsenceDiscipline:
    def test_runs_none_reports_the_leg_unread_not_empty(self):
        f = tickets.fold(_MemStore(_events()), runs=None,
                         now="2026-08-24T00:00:00Z")
        assert f["counts"]["recommendations_read"] is False
        assert f["counts"]["by_type"]["recommendation"] == 0
        assert "UNKNOWN rather than zero" in f["note"]

    def test_a_run_row_without_the_column_is_unreadable_not_empty(self):
        """THE all_runs TRAP. ``DeskStore.all_runs`` omits the
        ``recommendations`` column (deskstore.py:563-575), so every row it
        returns would otherwise contribute a silent zero — 0 against a live
        550."""
        rows = [{"run_id": "r1", "seat": "builder", "task": "t",
                 "trace_id": None, "resolved_at": None}]
        f = tickets.fold(_MemStore([]), runs=rows, runs_limit=10,
                         now="2026-08-24T00:00:00Z")
        c = f["counts"]
        assert c["recommendations_read"] is True
        assert c["recommendations_complete"] is False
        assert c["recommendations_unreadable_runs"] == 1

    def test_a_complete_run_list_says_so(self, folded):
        c = folded["counts"]
        assert c["recommendations_complete"] is True
        assert c["recommendations_unreadable_runs"] == 0

    def test_an_unparseable_timestamp_gives_a_null_age_not_a_zero(self):
        f = tickets.fold(_MemStore([
            _requested(R_OPEN, at="whenever")]), runs=[],
            now="2026-08-24T00:00:00Z")
        t = _by_id(f)[R_OPEN]
        assert t["age_hours"] is None and t["age_basis"] == "unknown"
        assert t["age_in_state_hours"] is None

    def test_a_readable_age_is_computed_from_the_event_timestamps(self, folded):
        t = _by_id(folded)[D_STRANDED]
        assert t["age_hours"] == 48.0 and t["age_basis"] == "event_timestamps"

    def test_an_unreadable_stream_reports_unknown_not_empty(self):
        class _Broken(_MemStore):
            def stream(self, since_seq=0, limit=100_000):
                raise RuntimeError("the store is down")

        f = tickets.fold(_Broken(), runs=_runs())
        assert f["readable"] is False
        assert f["tickets"] is None and f["counts"] is None
        assert "UNKNOWN" in f["note"]

    def test_a_generator_of_runs_is_not_counted_as_zero_runs(self):
        """MEASURED BEFORE THE FIX: passing a generator folded 550
        recommendations and reported ``runs_seen: 0``, because the census
        re-listed an iterator the child loop had already drained. A coverage
        count of zero beside rows read from those same runs is the silent-zero
        shape pointed at the instrument's own reach."""
        f = tickets.fold(_MemStore([]), runs=(r for r in _runs()),
                         runs_limit=1000, now="2026-08-24T00:00:00Z")
        assert f["counts"]["runs_seen"] == 2
        assert f["counts"]["by_type"]["recommendation"] == 12

    def test_a_truncated_run_list_says_it_may_be_truncated(self):
        f = tickets.fold(_MemStore([]), runs=_runs()[:1], runs_limit=1,
                         now="2026-08-24T00:00:00Z")
        assert f["counts"]["runs_truncated"] is True
        f2 = tickets.fold(_MemStore([]), runs=_runs(), runs_limit=1000,
                          now="2026-08-24T00:00:00Z")
        assert f2["counts"]["runs_truncated"] is False


# ============================================================================
# ROUTING IS READ FROM desk, NOT COPIED INTO THIS MODULE
# ============================================================================

class TestRoutingIsReusedNotReimplemented:
    """An assertion that the fold's answer EQUALS desk's cannot tell a read
    from a hardcoded duplicate that happens to agree today. So these tests
    MOVE desk's rules and require the fold to move with them."""

    def test_moving_a_kind_in_desks_table_moves_the_folds_answer(self,
                                                                 monkeypatch):
        monkeypatch.setitem(desk.KIND_ACTORS, "build", "seat")
        f = tickets.fold(_MemStore(_events()), runs=_runs(),
                         now="2026-08-24T00:00:00Z")
        assert _by_id(f)["rec:run-linked#2"]["next_actor"] == "seat"

    def test_moving_open_request_actor_moves_every_ask(self, monkeypatch):
        monkeypatch.setattr(desk, "OPEN_REQUEST_ACTOR", "chair")
        f = tickets.fold(_MemStore(_events()), runs=[],
                         now="2026-08-24T00:00:00Z")
        assert _by_id(f)[R_OPEN]["next_actor"] == "chair"

    def test_a_terminal_recommendation_is_nobodys_move(self, folded):
        for rid in ("rec:run-linked#8", "rec:run-linked#9",
                    "rec:run-linked#10"):
            assert _by_id(folded)[rid]["next_actor"] == "nobody"

    def test_an_explicit_next_actor_is_honoured(self, folded):
        t = _by_id(folded)["rec:run-linked#6"]
        assert t["next_actor"] == "nobody"
        assert t["next_actor_basis"] == "explicit"


# ============================================================================
# THE LEGACY STATUS MAP
# ============================================================================

class TestLegacyStatusAdapters:
    @pytest.mark.parametrize("rec_id,legacy,state", [
        ("rec:run-linked#1", "open", "filed"),
        ("rec:run-linked#3", "accepted", "accepted"),
        ("rec:run-linked#4", "staged", "accepted"),
        ("rec:run-linked#8", "done", "done"),
        ("rec:run-linked#9", "rejected", "declined"),
        ("rec:run-linked#10", "noted", "done"),
    ])
    def test_each_legacy_status_maps_to_its_stated_state(self, folded, rec_id,
                                                         legacy, state):
        t = _by_id(folded)[rec_id]
        assert (t["legacy_status"], t["state"]) == (legacy, state)

    def test_the_legacy_word_survives_the_collapse(self, folded):
        """``staged`` and ``accepted`` both fold to ``accepted``. The original
        word must stay on the row or the collapse would be a deletion."""
        assert _by_id(folded)["rec:run-linked#4"]["legacy_status"] == "staged"

    def test_the_terminal_rec_statuses_agree_with_desks_list(self):
        """One definition with a guard beats two that drift — the reason
        ``desk.TERMINAL_STATUSES`` exists at all (desk.py:978-982)."""
        terminal = {s for s, st in tickets.LEGACY_REC_STATE.items()
                    if st in tickets.TERMINAL_STATES}
        assert terminal == set(desk.TERMINAL_STATUSES)

    def test_an_unrecognised_status_is_flagged_not_guessed(self):
        rows = [{"run_id": "r", "seat": "s", "task": "t", "trace_id": None,
                 "resolved_at": None,
                 "recommendations": [_rec(1, "sideways")]}]
        f = tickets.fold(_MemStore([]), runs=rows, now="2026-08-24T00:00:00Z")
        t = _by_id(f)["rec:r#1"]
        assert t["legacy_state_recognised"] is False
        assert t["legacy_status"] == "sideways"
        assert t["state"] == "filed", \
            "it lands WORKING, where the row stays visible and owed — a " \
            "terminal guess would delete it from every queue"

    def test_an_unrecognised_status_is_published_as_the_divergence_leg(self):
        """THE ONE WAY THE RECONCILIATION CAN SILENTLY BREAK, made a number.
        ``open_recommendations`` selects three known statuses, so a row outside
        the vocabulary is invisible to ``desk_load`` and counted here. Zero on
        the live record — which is why it had to be written down before it
        stops being zero."""
        rows = [{"run_id": "r", "seat": "s", "task": "t", "trace_id": None,
                 "resolved_at": None,
                 "recommendations": [_rec(1, "sideways"), _rec(2, "open")]}]
        f = tickets.fold(_MemStore([]), runs=rows, now="2026-08-24T00:00:00Z")
        assert f["reconciliation"]["recommendation_unrecognised_status"] == 1

    def test_the_divergence_leg_is_zero_on_a_clean_population(self, folded):
        """NULL TEST, with its domain size stated: 12 recommendation tickets
        compared, every one of them carrying a recognised status."""
        assert folded["counts"]["by_type"]["recommendation"] == 12
        assert folded["reconciliation"]["recommendation_unrecognised_status"] \
            == 0


# ============================================================================
# ZERO WRITE PATHS — slice 1's third acceptance criterion
# ============================================================================

class TestTheFoldCannotWrite:
    def test_the_module_contains_no_append_and_no_event_construction(self):
        """Asserted by AST rather than by reading the diff. ``tickets.py`` is
        a rendering; the day it grows a door is the day this test fails and
        somebody has to say so in a commit message."""
        src = pathlib.Path(tickets.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        bad = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = (fn.attr if isinstance(fn, ast.Attribute)
                        else getattr(fn, "id", ""))
                if name in ("append", "Event", "execute", "commit", "insert"):
                    # `list.append` on a local is fine; a call on `store`,
                    # `conn` or `cur` is not.
                    target = (getattr(fn.value, "id", "")
                              if isinstance(fn, ast.Attribute) else "")
                    if name != "append" or target in ("store", "conn", "cur",
                                                      "_store"):
                        bad.append(f"{name} on {target or '<bare>'}")
        assert bad == [], f"the ticket fold must not write: {bad}"

    def test_the_module_imports_no_event_writer(self):
        """BY AST, NOT BY SUBSTRING. The first draft of this test asserted
        ``"import Event" not in src`` and failed on ``import EventType`` — a
        check satisfiable by a different name is the shared-word defect, and
        it would equally have PASSED on ``import Event as E``."""
        src = pathlib.Path(tickets.__file__).read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(src)):
            if isinstance(node, ast.ImportFrom):
                imported |= {a.name for a in node.names}
            elif isinstance(node, ast.Import):
                imported |= {a.name for a in node.names}
        assert "Event" not in imported, \
            "the fold imports the event constructor; it can only read"
        assert "EventType" in imported, \
            "and this is the guard against the guard: the fold DOES read the " \
            "enum, so an empty import set would make the line above vacuous"

    def test_the_fold_never_calls_append_on_the_store(self, folded):
        """The AST guard is static; this is the dynamic half — ``_MemStore``
        raises on append, so any write path would fail every test above."""
        with pytest.raises(AssertionError):
            _MemStore().append(object())


# ============================================================================
# THE ENDPOINT
# ============================================================================

@pytest.fixture()
def client(monkeypatch):
    from fastapi import FastAPI

    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_store", _MemStore(_events()))
    monkeypatch.setattr(fundapi, "_deskstore",
                        lambda: _FakeDeskStore(_runs()))
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


class TestTheEndpoint:
    def test_it_serves_the_whole_population_with_its_counts(self, client):
        r = client.get("/api/v1/fund/tickets?limit=5000")
        assert r.status_code == 200
        b = r.json()
        assert b["readable"] is True
        assert b["counts"]["total"] == len(b["tickets"]) == b["total"]
        # `challenge` is 0 and PRESENT, which is the point of seeding the
        # census from the vocabulary: a type with no rows renders zero rather
        # than vanishing from the dict. It gained a key in slice 2 (a
        # door-born-only species, §1.2's escape hatch from a terminal row) and
        # this fixture has no legacy carrier that could produce one.
        # `lesson` joined the vocabulary in slice 5 (it arrived WITH its
        # consumption receipt, which was the condition slice 2 stated for
        # admitting it). Like `challenge` it has no legacy carrier, so this
        # fixture produces zero of them — and zero-and-PRESENT is the assertion.
        assert b["counts"]["by_type"] == {"ask": 6, "dispatch": 2,
                                          "recommendation": 12, "challenge": 0,
                                          "lesson": 0}

    def test_a_filter_narrows_the_list_and_not_the_census(self, client):
        b = client.get("/api/v1/fund/tickets?type=ask").json()
        assert {t["type"] for t in b["tickets"]} == {"ask"}
        assert b["total"] == 6
        assert b["counts"]["total"] == 20, \
            "the census is the population, never the page"

    def test_the_state_filter_works_and_is_echoed(self, client):
        b = client.get("/api/v1/fund/tickets?state=in_flight").json()
        assert {t["state"] for t in b["tickets"]} == {"in_flight"}
        assert b["filters"] == {"type": None, "state": "in_flight"}

    @pytest.mark.parametrize("q", ["type=dispach", "state=dine",
                                   "type=lesson", "state=returned&type=ask"])
    def test_an_unrecognised_filter_is_refused_not_answered_with_zero(
            self, client, q):
        """``?state=dine`` would otherwise return ``total: 0`` — which reads
        exactly like "no ticket is in that state". Absence-as-zero at the query
        layer. ``returned`` is a real state no legacy adapter can produce, and
        asking for it must say the state is empty, which it does through a 200
        with total 0.

        ``type=lesson`` CHANGED SIDES IN SLICE 5, and the case is kept rather
        than deleted because the move is the interesting part: it was a live
        example of a REFUSED filter (in the design's type table, not in the
        fold's) and it is now a live example of a RECOGNISED one with no rows.
        The distinction the test defends — 422 for a word the vocabulary does
        not contain, 200-with-zero for one it does — is unchanged; only which
        side ``lesson`` sits on moved.
        """
        recognised = ("state=returned&type=ask", "type=lesson")
        r = client.get(f"/api/v1/fund/tickets?{q}")
        if q in recognised:
            assert r.status_code == 200 and r.json()["total"] == 0, \
                "a RECOGNISED filter with no rows is an honest empty answer"
            return
        assert r.status_code == 422
        assert "allowed" in r.json()["detail"]

    def test_a_page_cap_reports_itself_truncated(self, client):
        b = client.get("/api/v1/fund/tickets?limit=3").json()
        assert len(b["tickets"]) == 3 and b["shown"] == 3
        assert b["total"] == 20 and b["truncated"] is True

    def test_an_uncapped_page_is_not_truncated(self, client):
        b = client.get("/api/v1/fund/tickets?limit=5000").json()
        assert b["truncated"] is False

    @pytest.mark.parametrize("limit,truncated", [(19, True), (20, False),
                                                 (21, False)])
    def test_the_truncation_boundary(self, client, limit, truncated):
        """BOUNDARY TABLE on the one inequality this endpoint owns. 20 tickets
        in the fixture: at limit 20 the page holds all of them and
        ``truncated`` must be FALSE — ``>=`` there would tell a reader rows
        were hidden when none were, which is the honest-unknown firing on a
        knowable case."""
        b = client.get(f"/api/v1/fund/tickets?limit={limit}").json()
        assert b["total"] == 20
        assert b["truncated"] is truncated

    def test_it_degrades_rather_than_refuses_without_a_deskstore(
            self, client, monkeypatch):
        """A spine without Postgres can still read the event log. Two thirds
        of a readable answer beats a 503, and zero recommendations would be a
        lie."""
        from app.api.v1 import fund as fundapi
        monkeypatch.setattr(fundapi, "_deskstore", lambda: None)
        b = client.get("/api/v1/fund/tickets").json()
        assert b["counts"]["recommendations_read"] is False
        assert b["counts"]["by_type"]["ask"] == 6

    def test_an_unreadable_recorder_does_not_become_zero_recommendations(
            self, client, monkeypatch):
        from app.api.v1 import fund as fundapi

        class _Broken:
            def runs(self, limit=50, **kw):
                raise RuntimeError("recorder down")

        monkeypatch.setattr(fundapi, "_deskstore", lambda: _Broken())
        b = client.get("/api/v1/fund/tickets").json()
        assert b["counts"]["recommendations_read"] is False

    def test_the_endpoint_publishes_the_reconciliation_and_its_arithmetic(
            self, client):
        b = client.get("/api/v1/fund/tickets").json()
        assert "desk_load.total" in b["reconciliation"]["arithmetic"]
        assert b["fold_version"] == tickets.TICKET_FOLD_VERSION
