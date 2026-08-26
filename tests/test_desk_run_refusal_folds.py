"""THE D17 CHECKLIST, RUN AGAINST A NEW FOREIGN EVENT ON `desk_run`.

``app/fund/events.py``, directly above ``ORDER_ANNOTATION_EVENTS``, states the
rule this file exists to prove:

    A NEW EVENT TYPE ON AN EXISTING AGGREGATE IS A LIFECYCLE CHANGE UNTIL
    PROVEN OTHERWISE.

It was learned twice, expensively, and both times on an ``order`` aggregate:
``ApprovalRefused`` (guard v1, 2026-08-20) made a live SOFI ticket vanish from
the CEO's pending queue, and ``AutopolicyDeclined`` (PM R41, 2026-08-23) later
made a declined order impossible to approve. Both incidents share one shape —
a fold that switched on ``type`` alone, or that treated "the latest event on
this aggregate" as "the state", absorbed a finding as though it were a
lifecycle step.

A change on this branch appends ``ApprovalRefused`` to a ``desk_run``
aggregate for the first time (the fourth producer of the type overall,
``app/api/v1/fund.py::_refuse_if_redecided``, the narrow re-decision guard
seated 2026-08-24). Measured against the live Postgres log on 2026-08-24: the
``desk_run`` aggregate has carried exactly ONE event type for its entire
life — 678 ``DeskRecommendationDecided`` and zero of anything else — so this
is genuinely the first foreign event on that aggregate, and the D17 rule says
it must be PROVEN not to perturb anything rather than assumed.

THE PROOF SHAPE, copied from ``tests/test_tickets_doors.py``'s
``test_the_requests_fold_is_byte_identical``: fold a stream, fold the same
stream again with the new event type inserted, and assert the two outputs are
equal. Every fold below gets that treatment, plus a POSITIVE CONTROL — proof
that the same fold DOES change when an event it actually reads is inserted,
so the invariance assertion is not passing because the fold reads nothing at
all.

Covered, one class per fold:

  * ``TestTheRequestsFoldIsUnperturbed`` — ``app.fund.desk._requests``
  * ``TestTheDeskViewIsUnperturbed`` — ``app.fund.desk.view``
  * ``TestTheTicketFoldIsUnperturbed`` — ``app.fund.tickets.fold``, plus the
    phantom-vs-ignored distinction: a foreign event on a foreign aggregate
    must be silently ignored, never collected as a phantom (a phantom is an
    event naming an id no adapter has seen — a different, alarming fact).
  * ``TestTheDecisionsSectionIsUnperturbed`` — ``app.fund.metrics``'s
    ``_decisions_section`` (the function whose docstring names
    ``DeskRecommendationDecided``), read through the public
    ``compute_daily``.
  * ``TestTheOrdersProjectionNeverSeesIt`` — ``OrdersProjection``, which drops
    any aggregate that is not ``"order"`` before it ever looks at ``type``.
  * ``TestTheEventLandsOnDeskRunNotOrder`` — driven through the real door
    (``POST /fund/desk/runs/{run_id}/recommendations/{rec_id}``, posted twice
    with the same status), proving the event's own ``aggregate_type`` is
    ``"desk_run"`` and never ``"order"`` — the fact that makes
    ``ORDER_ANNOTATION_EVENTS`` correct to leave untouched.

STORE OWNERSHIP: every store here is private to its own test (or fixture),
per the house rule since D39 — an endpoint test that writes must own its
store and monkeypatch ``fundapi._store``, because two probe events in a
shared store once turned 92 unrelated tests red while each passed alone.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import contextlib
import datetime as _dt
from unittest import mock

from app.fund import desk, tickets as tk, metrics, ticketguard
from app.fund.events import EventType
from app.fund.projections.orders import OrdersProjection


#: A FIXED INSTANT, so a fold's output is a function of its input alone.
#: `desk.view` has no `now` parameter — it reads `datetime.now()` internally —
#: and its `lifecycle.age_hours` is rounded to one decimal, i.e. SIX MINUTES.
#: Two `view()` calls compared for equality therefore disagree whenever they
#: straddle a six-minute boundary: rare, non-reproducible, and it would fail
#: with the message "the refusal changed the desk view", sending the next
#: builder hunting a defect that is not there. Measured with a 4000-second
#: offset: exactly ONE path moves with the clock,
#: `.requests[0].lifecycle.age_hours`.
FROZEN = _dt.datetime(2026, 8, 25, 0, 0, 0, tzinfo=_dt.timezone.utc)


@contextlib.contextmanager
def frozen_clock():
    """Freeze ``datetime.datetime.now`` for code that imports it per-call.

    ``desk.view`` does ``from datetime import datetime`` INSIDE the function,
    so the name resolves against the ``datetime`` MODULE at call time — which
    is why patching the module attribute works here and patching ``desk``'s
    own namespace would not.
    """
    class _Frozen(_dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return FROZEN if tz else FROZEN.replace(tzinfo=None)

    with mock.patch.object(_dt, "datetime", _Frozen):
        yield


# ============================================================================
# SHARED FIXTURES
# ============================================================================

class _Store:
    """The smallest store every fold under test can read: an in-memory list
    with ``append`` and ``stream``, matching ``tests/test_tickets_doors.py``'s
    ``_WritableStore`` and ``tests/test_metrics.py``'s ``FakeStore``. Dicts
    only, since every fold touched here accepts dict-shaped events (checked
    against each fold's own dict/attr dual read before writing this file).
    """

    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):
        self.events.append(e)
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


def _approval_refused_on_desk_run(seq: int, ts: str, run_id: str = "run-hw4-probe",
                                  rec_id: int = 7, actor: str = "ceo") -> dict:
    """One ``ApprovalRefused`` on a ``desk_run`` aggregate.

    THE PAYLOAD IS BUILT BY THE REAL GUARD, not hand-typed. A first draft of
    this helper wrote ``"guard": "legacy-redecision-v1"`` and
    ``"kind": "redecision"`` — neither of which any producer has ever emitted —
    under a docstring claiming it was "shaped like the real payload". The fold
    invariance held either way (these folds never look inside), but a fixture
    that MODELS a payload while claiming to mirror one is how the next reader
    learns a field name that does not exist. Calling ``check_redecision`` makes
    the fixture a CALL rather than a model, and it fails loudly the day the
    refusal's shape changes.
    """
    refusal = ticketguard.check_redecision(
        [{"seq": seq - 1, "status": "accepted", "at": ts, "actor": actor}],
        to="accepted", run_id=run_id, rec_id=rec_id)
    assert refusal is not None, "the fixture must be built from a real refusal"
    return {
        "seq": seq, "ts": ts, "actor": actor,
        "aggregate_id": run_id, "aggregate_type": "desk_run",
        "type": EventType.APPROVAL_REFUSED.value,
        "payload": {
            "kind": refusal["kind"], "target_id": run_id, "approver": actor,
            "guard": refusal["guard"], "reason": refusal["detail"],
            "row_ref": refusal["row_ref"],
            "attempted": refusal["attempted"],
            "recorded_status": refusal["recorded_status"],
            "recorded_at": refusal["recorded_at"],
            "recorded_by": refusal["recorded_by"],
            "prior_same_status": refusal["prior_same_status"],
            "decision_count": refusal["decision_count"], "at": ts,
        },
    }


def _refusals(*, start_seq: int, day: str = "2026-08-21") -> list[dict]:
    """Three refusals on three different desk_run aggregates, so a fold that
    happened to key on one run_id and miss another would still be caught."""
    return [
        _approval_refused_on_desk_run(start_seq, f"{day}T01:00:00Z",
                                      run_id="run-alpha", rec_id=1),
        _approval_refused_on_desk_run(start_seq + 1, f"{day}T12:00:00Z",
                                      run_id="run-beta", rec_id=2),
        _approval_refused_on_desk_run(start_seq + 2, f"{day}T23:00:00Z",
                                      run_id="run-alpha", rec_id=1),
    ]


def _interleave(base: list[dict], foreign: list[dict]) -> list[dict]:
    """Foreign events spread across the front, middle and back of ``base`` —
    never appended only at the end, which would leave "does an early foreign
    event corrupt state read by a later legitimate one" unchecked."""
    if not base:
        return list(foreign)
    mid = len(base) // 2
    return base[:mid] + [foreign[0]] + base[mid:] + foreign[1:]


# ============================================================================
# 1. app.fund.desk._requests
# ============================================================================

class TestTheRequestsFoldIsUnperturbed:
    """``desk._requests`` switches on the four ``DeskRequest*`` values and
    ignores everything else (the D17 checklist comment in events.py cites
    this fold by name and line range). Proven by construction here rather
    than by re-reading the switch statement.
    """

    def _legacy_stream(self) -> list[dict]:
        return [
            {"type": "DeskRequested", "payload": {
                "request_id": "req-open-1", "kind": "build", "serves": "builder",
                "subject": "an ask nobody has decided", "trace_id": "req-open-1",
                "at": "2026-08-20T00:00:00Z", "actor": "cto"}},
            {"type": "DeskRequested", "payload": {
                "request_id": "req-approved-1", "task": "wire the guard",
                "seat": "riskofficer", "trace_id": "req-approved-1",
                "at": "2026-08-19T00:00:00Z", "actor": "ceo"}},
            {"type": "DeskRequestApproved", "payload": {
                "request_id": "req-approved-1", "actor": "ceo",
                "at": "2026-08-19T01:00:00Z"}},
            {"type": "DeskRequested", "payload": {
                "request_id": "req-resolved-1", "task": "measure the drift",
                "seat": "analyst", "trace_id": "req-resolved-1",
                "at": "2026-08-18T00:00:00Z", "actor": "cto"}},
            {"type": "DeskRequestResolved", "payload": {
                "request_id": "req-resolved-1", "at": "2026-08-18T05:00:00Z",
                "resolution": "docs/reviews/the-artifact.md"}},
        ]

    def test_byte_identical_with_desk_run_refusals_interleaved(self):
        without = self._legacy_stream()
        with_refusals = _interleave(without, _refusals(start_seq=100))

        assert len(with_refusals) == len(without) + 3, \
            "the control arm must actually be missing the refusal events"
        assert desk._requests(_Store(without)) == \
               desk._requests(_Store(with_refusals))

    def test_positive_control_a_real_desk_event_DOES_change_the_fold(self):
        """Without this, the invariance test above would pass trivially if
        ``_requests`` ignored its own input stream entirely."""
        without = self._legacy_stream()
        plus_real = without + [{"type": "DeskRequested", "payload": {
            "request_id": "req-brand-new", "task": "a fold this test cares "
            "about", "seat": "quant", "trace_id": "req-brand-new",
            "at": "2026-08-21T00:00:00Z", "actor": "cto"}}]
        assert desk._requests(_Store(without)) != \
               desk._requests(_Store(plus_real))


# ============================================================================
# 2. app.fund.desk.view
# ============================================================================

class TestTheDeskViewIsUnperturbed:
    """The whole desk payload, called exactly as
    ``tests/test_tickets_doors.py`` and ``tests/test_desk.py`` call it:
    ``deskstore=None, pending_orders=None`` so the recommendation leg reads
    as UNKNOWN rather than a silent zero, and the doors' worked-hard mix of
    request species is folded through the same public entry point the API
    layer uses.
    """

    def _busy_stream(self) -> list[dict]:
        return [
            {"type": "DeskRequested", "payload": {
                "request_id": "req-open-2", "task": "a live ask",
                "seat": "pm", "trace_id": "req-open-2",
                "at": "2026-08-20T00:00:00Z", "actor": "ceo"}},
            {"type": "DeskRequestApproved", "payload": {
                "request_id": "req-open-2", "actor": "ceo",
                "at": "2026-08-20T01:00:00Z"}},
            {"type": "DeskDispatched", "payload": {
                "task_id": "chair-born-hw4", "seat": "builder",
                "task": "chair-born work with no backing request",
                "request_id": None, "trace_id": "chair-born-hw4",
                "at": "2026-08-21T00:00:00Z", "actor": "cto"}},
        ]

    def test_the_view_is_byte_identical_with_desk_run_refusals_interleaved(self):
        without = self._busy_stream()
        with_refusals = _interleave(without, _refusals(start_seq=200))

        assert len(with_refusals) == len(without) + 3
        with frozen_clock():
            left = desk.view(_Store(without), deskstore=None,
                             pending_orders=None)
            right = desk.view(_Store(with_refusals), deskstore=None,
                              pending_orders=None)
        assert left == right

    def test_the_frozen_clock_is_ACTUALLY_in_effect(self):
        """THE FREEZE'S OWN POSITIVE CONTROL, and it is not ceremony.

        If ``frozen_clock`` silently stopped patching — a refactor of
        ``desk.view``'s import, say — the equality test above would go back to
        comparing two wall-clock reads and would pass on almost every run
        while carrying the flake it was written to remove. A freeze nobody
        checks is indistinguishable from no freeze at all.

        THE EXPECTED VALUE IS DERIVED FROM THE CODE, NOT FROM THE OUTPUT.
        ``deskcard.lifecycle_rail`` measures from the CURRENT STAGE's
        timestamp, not from filing. ``req-open-2`` is approved and not
        dispatched, so its current stage is ``awaiting_dispatch``, which
        inherits the APPROVAL's stamp — 2026-08-20T01:00:00Z, "because the
        clock the CEO cares about started when he said yes". Against FROZEN
        (2026-08-25T00:00:00Z) that is 119.0 hours, not the 120.0 that filing
        would give. Getting this wrong is how a test ends up asserting
        whatever the code happened to print.
        """
        with frozen_clock():
            v = desk.view(_Store(self._busy_stream()), deskstore=None,
                          pending_orders=None)
        rails = {r["request_id"]: r["lifecycle"] for r in v["requests"]}
        rail = rails["req-open-2"]
        assert rail["current"] == "awaiting_dispatch"
        assert rail["age_hours"] == 119.0

    def test_positive_control_a_real_desk_event_DOES_change_the_view(self):
        without = self._busy_stream()
        plus_real = without + [{"type": "DeskRequested", "payload": {
            "request_id": "req-brand-new-2", "task": "a view this test cares "
            "about", "seat": "coo", "trace_id": "req-brand-new-2",
            "at": "2026-08-21T02:00:00Z", "actor": "cto"}}]
        with frozen_clock():
            left = desk.view(_Store(without), deskstore=None,
                             pending_orders=None)
            right = desk.view(_Store(plus_real), deskstore=None,
                              pending_orders=None)
        assert left != right
        assert right["open_requests"] == left["open_requests"] + 1


# ============================================================================
# 3. app.fund.tickets.fold
# ============================================================================

class TestTheTicketFoldIsUnperturbed:
    """``tickets.fold`` iterates the stream through an if/elif chain keyed on
    ``type`` alone (``app/fund/tickets.py:485-702``); there is no trailing
    ``else`` that catches an unrecognised type, so a type this fold does not
    name — ``ApprovalRefused`` on a ``desk_run`` aggregate — falls through
    every branch untouched. Confirmed here rather than by re-reading the
    chain: the same store folded with and without the refusals must produce
    an identical ticket population, AND the refusal must be absent from
    ``phantom_events`` specifically — collecting it there would misreport a
    silently-ignored foreign event as an id no adapter has ever seen, which
    is a different and alarming claim (see the module's own phantom-cohort
    comment, ``app/fund/tickets.py:453-465``).
    """

    def _busy_ticket_stream(self) -> list[dict]:
        return [
            {"type": "TicketOpened", "payload": {
                "ticket_id": "tkt-hw4-1", "type": "ask", "subject": "a filed ask",
                "filed_for": "chair", "actor": "cto",
                "at": "2026-08-20T00:00:00Z", "trace_id": "tkt-hw4-1",
                "next_actor": "ceo", "due_date": "2026-09-01",
                "money_at_stake": 500.0, "reversibility": "hard",
                "kind": "build"}},
            {"type": "TicketTransitioned", "payload": {
                "ticket_id": "tkt-hw4-1", "to": "in_flight",
                "at": "2026-08-20T01:00:00Z", "actor": "cto",
                "basis": "dispatch"}},
            {"type": "TicketOpened", "payload": {
                "ticket_id": "tkt-hw4-2", "type": "ask",
                "subject": "a second filed ask", "filed_for": "builder",
                "actor": "cto", "at": "2026-08-20T02:00:00Z",
                "trace_id": "tkt-hw4-2"}},
            {"type": "TicketLinked", "payload": {
                "ticket_id": "tkt-hw4-2", "link_kind": "serves",
                "target_id": "tkt-hw4-1", "basis": "the ask it serves",
                "at": "2026-08-20T03:00:00Z", "actor": "cto"}},
        ]

    def _fold(self, store: _Store) -> dict:
        return tk.fold(store, runs=None, now="2026-08-25T00:00:00Z")

    def test_byte_identical_with_desk_run_refusals_interleaved(self):
        without = self._busy_ticket_stream()
        with_refusals = _interleave(without, _refusals(start_seq=300))

        assert len(with_refusals) == len(without) + 3
        left = self._fold(_Store(without))
        right = self._fold(_Store(with_refusals))
        assert left == right

    def test_the_refusal_is_ignored_outright_not_collected_as_a_phantom(self):
        """A phantom is an event naming an id no adapter has seen. This event
        names a ``desk_run`` id (``run-alpha`` / ``run-beta``) — a
        population this fold does not even index — so the honest outcome is
        silence, not a phantom entry that would misdirect a reader hunting
        for corrupted linkage.
        """
        with_refusals = _interleave(self._busy_ticket_stream(),
                                    _refusals(start_seq=400))
        folded = self._fold(_Store(with_refusals))
        assert folded["readable"] is True
        phantom_ids = {p["id"] for p in folded["phantom_events"]}
        assert "run-alpha" not in phantom_ids
        assert "run-beta" not in phantom_ids
        assert "ApprovalRefused" not in {p["event"] for p in folded["phantom_events"]}

    def test_positive_control_a_real_ticket_event_DOES_change_the_fold(self):
        without = self._busy_ticket_stream()
        plus_real = without + [{"type": "TicketOpened", "payload": {
            "ticket_id": "tkt-hw4-brand-new", "type": "ask",
            "subject": "a fold this test cares about", "filed_for": "chair",
            "actor": "cto", "at": "2026-08-25T00:00:00Z",
            "trace_id": "tkt-hw4-brand-new"}}]
        left = self._fold(_Store(without))
        right = self._fold(_Store(plus_real))
        assert left != right
        assert len(right["tickets"]) == len(left["tickets"]) + 1


# ============================================================================
# 4. app.fund.metrics — the decisions section
# ============================================================================

class TestTheDecisionsSectionIsUnperturbed:
    """``_decisions_section`` (``app/fund/metrics.py:234-256``, the function
    whose docstring names ``DeskRecommendationDecided``) filters
    ``day_events`` down to exactly that type before counting by actor and by
    status. It does not read ``aggregate_type`` at all, so an
    ``ApprovalRefused`` on ``desk_run`` — even one that lands inside the same
    UTC day and therefore enters ``day_events`` via ``_events_for_day`` —
    must leave the actor/status tallies untouched. Read through the public
    ``compute_daily`` rather than the private section function, so the
    assertion exercises the same call path a caller actually uses.

    ``compute_daily``'s OTHER sections (``events.total``, ``events.by_type``,
    the digest) are expected to change with a new event on the log — that is
    correct, not a defect, and is why this test scopes its invariance claim
    to ``["decisions"]`` only, exactly as the task that produced this file
    specifies.
    """

    DAY = "2026-08-21"

    def _decisions_stream(self) -> list[dict]:
        return [
            {"seq": 1, "type": "DeskRecommendationDecided",
             "ts": f"{self.DAY}T09:00:00+00:00", "actor": "ceo",
             "payload": {"status": "accepted"}},
            {"seq": 2, "type": "DeskRecommendationDecided",
             "ts": f"{self.DAY}T10:00:00+00:00", "actor": "cto",
             "payload": {"status": "rejected"}},
            {"seq": 3, "type": "DeskRecommendationDecided",
             "ts": f"{self.DAY}T11:00:00+00:00", "actor": "co-cto",
             "payload": {"status": "accepted"}},
        ]

    def test_decisions_byte_identical_with_desk_run_refusals_interleaved(self):
        without = self._decisions_stream()
        # ts inside the same UTC day, so these events DO enter `day_events` —
        # the stronger claim: even present in the fold's own input window,
        # they must not move the decisions tally.
        with_refusals = _interleave(without, _refusals(start_seq=500, day=self.DAY))

        left = metrics.compute_daily(self.DAY, _Store(without))["decisions"]
        right = metrics.compute_daily(self.DAY, _Store(with_refusals))["decisions"]
        assert left == right

    def test_the_refusals_DO_still_show_up_in_the_events_total(self):
        """Named so a reader does not mistake the invariance above for "the
        rollup cannot see this event at all" — it can, and correctly reports
        it in the events section. Only the decisions tally is scoped."""
        without = self._decisions_stream()
        with_refusals = without + _refusals(start_seq=600, day=self.DAY)
        left = metrics.compute_daily(self.DAY, _Store(without))
        right = metrics.compute_daily(self.DAY, _Store(with_refusals))
        assert right["events"]["total"] == left["events"]["total"] + 3
        assert right["events"]["by_type"].get("ApprovalRefused") == 3
        assert right["decisions"] == left["decisions"]

    def test_positive_control_a_real_decision_event_DOES_change_the_section(self):
        without = self._decisions_stream()
        plus_real = without + [
            {"seq": 4, "type": "DeskRecommendationDecided",
             "ts": f"{self.DAY}T12:00:00+00:00", "actor": "ceo",
             "payload": {"status": "done"}}]
        left = metrics.compute_daily(self.DAY, _Store(without))["decisions"]
        right = metrics.compute_daily(self.DAY, _Store(plus_real))["decisions"]
        assert left != right
        assert right["total"] == left["total"] + 1
        assert right["by_actor"]["ceo"] == left["by_actor"]["ceo"] + 1


# ============================================================================
# 5. app.fund.projections.orders.OrdersProjection
# ============================================================================

class TestTheOrdersProjectionNeverSeesIt:
    """``OrdersProjection._apply`` (``app/fund/projections/orders.py:47-49``)
    drops any event whose ``aggregate_type`` is not ``"order"`` as its very
    first line, BEFORE it ever inspects ``type`` — so ``ApprovalRefused`` on
    ``desk_run`` never reaches the annotation-vs-lifecycle branch at all, and
    ``ORDER_ANNOTATION_EVENTS`` genuinely needs no fifth member for it. Two
    layers: a direct call against ``_apply`` (the mechanism), and a
    byte-identical fold through ``pending()``/``history()`` (the outcome).
    """

    def test_apply_is_a_no_op_for_a_desk_run_event(self):
        orders: dict = {}
        refusal = _approval_refused_on_desk_run(1, "2026-08-21T01:00:00Z")
        OrdersProjection._apply(orders, refusal)
        assert orders == {}

    def _order_stream(self) -> list[dict]:
        return [
            {"seq": 1, "aggregate_id": "ORD-hw4-1", "aggregate_type": "order",
             "type": "OrderProposed", "ts": "2026-08-21T00:00:00Z",
             "payload": {"symbol": "TLT", "side": "buy", "qty": 10,
                        "strategy_id": "sleeve_premia"}},
            {"seq": 2, "aggregate_id": "ORD-hw4-1", "aggregate_type": "order",
             "type": "OrderApproved", "ts": "2026-08-21T00:05:00Z",
             "payload": {}},
            {"seq": 3, "aggregate_id": "ORD-hw4-1", "aggregate_type": "order",
             "type": "OrderSubmitted", "ts": "2026-08-21T00:10:00Z",
             "payload": {"venue": "alpaca", "venue_ref": "abc123"}},
        ]

    def test_history_and_pending_byte_identical_with_desk_run_refusals(self):
        without = self._order_stream()
        with_refusals = _interleave(without, _refusals(start_seq=700))
        assert len(with_refusals) == len(without) + 3

        left = OrdersProjection(store=_Store(without))
        right = OrdersProjection(store=_Store(with_refusals))
        assert left.history() == right.history()
        assert left.pending() == right.pending()
        assert left.in_flight() == right.in_flight()

    def test_no_desk_run_event_lands_in_the_folded_order_records(self):
        """The outcome the mechanism-level test above predicts, restated as
        a property of the fold's OWN output rather than of the input: not a
        single folded order record should exist for a ``desk_run`` id."""
        with_refusals = _interleave(self._order_stream(), _refusals(start_seq=800))
        proj = OrdersProjection(store=_Store(with_refusals))
        folded = proj._fold()
        assert "run-alpha" not in folded
        assert "run-beta" not in folded
        assert set(folded.keys()) == {"ORD-hw4-1"}

    def test_positive_control_a_real_order_event_DOES_change_the_fold(self):
        without = self._order_stream()
        plus_real = without + [
            {"seq": 4, "aggregate_id": "ORD-hw4-2", "aggregate_type": "order",
             "type": "OrderProposed", "ts": "2026-08-21T01:00:00Z",
             "payload": {"symbol": "DBC", "side": "buy", "qty": 5,
                        "strategy_id": "sleeve_premia"}}]
        left = OrdersProjection(store=_Store(without)).pending()
        right = OrdersProjection(store=_Store(plus_real)).pending()
        assert left != right
        assert len(right) == len(left) + 1


# ============================================================================
# 6. THE EVENT'S OWN aggregate_type — driven through the real door
# ============================================================================

class _AggStore:
    """Minimal writable store, private to this test class, shaped like
    ``tests/test_legacy_redecision_guard.py``'s ``_AggStore``: it answers
    ``by_aggregate`` (the re-decision guard's read path) and records every
    appended ``Event`` object whole, so the test can inspect the object's own
    ``aggregate_type`` rather than a dict re-derivation of it.
    """

    def __init__(self):
        self.events: list[dict] = []
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


class _Deskstore:
    """Records what was decided; never touches the event log itself."""

    def __init__(self):
        self.decided = []

    def decide_recommendation(self, run_id, rec_id, status, actor, note="",
                              next_actor=None):
        self.decided.append((run_id, rec_id, status))
        return {"rec_id": rec_id, "status": status, "text": "hw4 probe",
                "seat": "pm", "trace_id": None, "next_actor": next_actor}


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
    return c


class TestTheEventLandsOnDeskRunNotOrder:
    """Mirrors ``tests/test_tickets_doors.py``'s
    ``test_no_ticket_event_lands_on_an_order_aggregate``: if this event
    landed on an ``order`` aggregate instead, ``ORDER_ANNOTATION_EVENTS``
    would need a new member (and every order fold would need re-auditing).
    Driven through the real door — the same 409-producing repeat-status
    replay ``tests/test_legacy_redecision_guard.py::TestTheR39Replay``
    exercises — rather than constructed by hand, so this proves what the
    running endpoint actually appends, not what a comment claims it appends.
    """

    RUN_ID = "run-hw4-doorcheck"
    REC_ID = 1

    def _decide(self, client, status="accepted"):
        return client.post(
            f"/api/v1/fund/desk/runs/{self.RUN_ID}/recommendations/{self.REC_ID}",
            json={"status": status, "actor": "ceo", "note": "hw4"})

    def test_the_refusal_event_is_on_desk_run_never_on_order(self, monkeypatch):
        c = _client(monkeypatch, _AggStore(), _Deskstore())

        first = self._decide(c)
        assert first.status_code == 200, first.text

        second = self._decide(c)
        assert second.status_code == 409, second.text

        refusals = [e for e in c.store.appended
                   if getattr(e.type, "value", e.type) == "ApprovalRefused"]
        assert len(refusals) == 1
        ev = refusals[0]
        assert ev.aggregate_type == "desk_run"
        assert ev.aggregate_type != "order"
        assert ev.aggregate_id == self.RUN_ID
        # THE FULL WRITTEN RECORD, restated as the D17 checklist's own check:
        # no event appended by this door landed on an "order" aggregate.
        assert not [e for e in c.store.appended
                   if e.aggregate_type == "order"]

    def test_the_event_type_is_the_one_ORDER_ANNOTATION_EVENTS_already_names(
            self, monkeypatch):
        """Confirms this is genuinely ``EventType.APPROVAL_REFUSED`` — the
        same type already handled (on ``order``) by
        ``ORDER_ANNOTATION_EVENTS`` — rather than a new type this file has
        mis-simulated."""
        c = _client(monkeypatch, _AggStore(), _Deskstore())
        assert self._decide(c).status_code == 200
        assert self._decide(c).status_code == 409
        refusal = c.store.appended[-1]
        assert refusal.type == EventType.APPROVAL_REFUSED
        from app.fund.events import ORDER_ANNOTATION_EVENTS
        assert refusal.type.value in ORDER_ANNOTATION_EVENTS, \
            "sanity: the type itself is the annotation type, even though " \
            "this particular event lands on a different aggregate"
