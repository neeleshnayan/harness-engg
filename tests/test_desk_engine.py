"""The desk engine v1 — the four things it must never do.

Every test here names the defect it exists to catch, because this engine sits
one field away from the CEO's approval surface and the failure modes are all
QUIET ones:

  1. **Routing must never send an undecided row to the CEO.** The whole flood
     was 54 of 91 rows arriving on his desk by default (COO triage #7). A
     regression here looks like a slightly busier desk, which is invisible.
  2. **Auto-hygiene must never write anything but bookkeeping.** Two tests
     once ASSERTED a gate loosening; a rules table that can be read but not
     violated is the only kind worth shipping. `test_no_rule_can_ever_write_*`
     walks the shipped table rather than a fixture of it.
  3. **A superseded row must be unapprovable, and a superseded row must stay
     WITHDRAWABLE.** The R37 specimen (docs/coo/TRIAGE7_2026-08-23.md
     decision 2) fails in both directions: approving it after Monday strips
     dated exit coverage from $501.58, and blocking its withdrawal wedges it
     on the desk forever.
  4. **An absence must never render as a value.** A run with no recorded
     status is not a delivered run; an unreadable verification ledger is not
     an unverified memo; a rule that did not run found no flags.

Hermetic: no Postgres, no network, no git. The store-backed half lives in
tests/test_desk_engine_store.py.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.fund import desk, deskengine, deskhygiene


# --------------------------------------------------------------- fixtures --

class MemStore:
    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):
        # aggregate_type/_id are captured because a refusal event's AGGREGATE
        # is what decides which folds see it — the D17 lesson, and the reason
        # the supersession refusal had to be checked against every fold that
        # keys on it.
        self.events.append({"type": e.type.value, "payload": e.payload,
                            "actor": e.actor,
                            "aggregate_type": e.aggregate_type,
                            "aggregate_id": e.aggregate_id})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)[:limit]


def requested(rid, kind="attack", serves="adversary", at="2026-08-22T00:00:00+00:00",
              trace=None, subject="attack the thing"):
    return {"type": "DeskRequested",
            "payload": {"request_id": rid, "kind": kind, "serves": serves,
                        "subject": subject, "trace_id": trace or rid, "at": at,
                        "actor": "cto"}}


def approved(rid, at="2026-08-22T01:00:00+00:00"):
    return {"type": "DeskRequestApproved",
            "payload": {"request_id": rid, "actor": "ceo", "at": at}}


def dispatched(rid, seat="adversary", trace=None, at="2026-08-22T02:00:00+00:00"):
    return {"type": "DeskDispatched",
            "payload": {"task_id": rid, "seat": seat, "request_id": rid,
                        "trace_id": trace or rid, "at": at, "actor": "cto"}}


def run(run_id, *, seat="adversary", status="delivered", verdict="KILL",
        trace=None, resolved="2026-08-22T03:00:00+00:00", serves=None,
        recommendations=None):
    return {"run_id": run_id, "seat": seat, "task": "t", "status": status,
            "verdict": verdict, "trace_id": trace, "resolved_at": resolved,
            "recommendations": recommendations or [],
            "meta": {"serves_requests": serves} if serves else {}}


class FakeDeskStore:
    """Enough of the flight recorder for the read paths."""

    def __init__(self, runs=None, recs=None):
        self._runs = list(runs or [])
        self._recs = list(recs or [])
        self.decided = []

    def runs(self, seat=None, limit=50, with_output=False, run_id=None):
        return list(self._runs)[:limit]

    def all_runs(self, limit=100_000):
        return list(self._runs)[:limit]

    def open_recommendations(self):
        return list(self._recs)

    def record_run(self, **kw):
        self._runs.append(kw)
        return {"run_id": kw["run_id"],
                "recommendations": len(kw.get("recommendations") or []),
                "stored": kw.get("recommendations")}

    def decide_recommendation(self, run_id, rec_id, status, actor, note="",
                              next_actor=None):
        self.decided.append((run_id, rec_id, status))
        return {"rec_id": rec_id, "status": status, "text": "t",
                "seat": "pm", "trace_id": None, "next_actor": next_actor}


def client(monkeypatch, store, deskstore=None, edges=None, intray=None):
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_store", store)
    monkeypatch.setattr(fundapi, "_deskstore", lambda: deskstore)
    monkeypatch.setattr(fundapi, "_edges_by_target", lambda: edges)
    monkeypatch.setattr(fundapi, "_intray", lambda: intray)
    monkeypatch.setattr(fundapi, "_briefing_ledger", lambda: None)
    monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


GOOD_REC = {"kind": "build", "text": "do the thing", "next_actor": "chair",
            "due_date": None, "reversibility": "reversible",
            "money_at_stake": None}


# ================================================== 1. routing at birth =====

def test_a_filing_with_no_routing_is_refused_and_names_every_missing_field():
    """THE FLOOD: 54 of 91 CEO-routed rows arrived by default (COO triage #7).

    All four errors at once, not one per round trip — a seat re-posting to
    discover the second missing field is a seat spending four calls on a form.
    """
    errors = desk.routing_errors({"text": "x", "kind": "build"}, 0)
    assert len(errors) == 1
    for field in desk.ROUTING_REQUIRED_FIELDS:
        assert field in errors[0]
    assert "recommendations[0]" in errors[0]


def test_the_routing_rule_READS_the_required_set_rather_than_repeating_it(monkeypatch):
    """MOVE the value, do not match it (D16/D21 standard).

    Asserting `errors mention next_actor` cannot tell a read from a hardcoded
    list that happens to agree. So the required set is MOVED to something the
    module has never seen, and the refusal must follow it.
    """
    monkeypatch.setattr(desk, "ROUTING_REQUIRED_FIELDS", ("blast_radius",))
    errors = desk.routing_errors(dict(GOOD_REC), 0)
    assert len(errors) == 1 and "blast_radius" in errors[0]
    # And the four real fields are now IRRELEVANT — proof nothing else pins them.
    assert desk.routing_errors({"blast_radius": 1}, 0) == []


def test_undecided_routes_to_the_chair_and_never_to_the_ceo():
    """The default flips. This is the single assertion the flood turns on."""
    routed = desk.route_at_birth({"text": "x", "next_actor": "undecided"})
    assert routed["next_actor"] == desk.UNDECIDED_ROUTES_TO == "chair"
    assert routed["next_actor"] != "ceo"
    # The seat's own word is preserved beside the resolution: a chair queue
    # full of `routed_from: undecided` is a bench that stopped thinking about
    # ownership, and overwriting it would delete that measurement.
    assert routed["routed_from"] == "undecided"


def test_unknown_is_not_a_word_a_seat_may_file():
    """`unknown` is a READING the desk produces, never a claim a filer makes.

    Allowing it would let a seat opt out of routing while looking compliant,
    and `desk_load` counts unknown toward the CEO — so the flood would come
    back through the one word that was supposed to be unwritable.
    """
    assert "unknown" not in desk.FILEABLE_NEXT_ACTORS
    errors = desk.routing_errors({**GOOD_REC, "next_actor": "unknown"}, 0)
    assert len(errors) == 1 and "unknown" in errors[0]


@pytest.mark.parametrize("value", ["2026-8-1", "next Monday", "20260801", ""])
def test_a_malformed_due_date_is_refused_not_nulled(value):
    """It used to sort lexicographically against real dates and lose the row."""
    errors = desk.routing_errors({**GOOD_REC, "due_date": value}, 0)
    assert len(errors) == 1 and "due_date" in errors[0]


def test_an_honest_absence_is_accepted_on_both_ranking_keys():
    """Required means the KEY is present, not that a figure was invented.

    The opposite failure is worse than the flood: a seat forced to state a
    dollar figure states one, and the desk then ranks on fabricated money.
    """
    assert desk.routing_errors({**GOOD_REC, "due_date": None,
                                  "money_at_stake": None}, 0) == []


@pytest.mark.parametrize("value", ["free", float("nan"), float("inf"), "12"])
def test_money_at_stake_must_be_a_finite_number_or_null(value):
    assert desk.routing_errors({**GOOD_REC, "money_at_stake": value}, 0)


def test_the_endpoint_refuses_an_unrouted_filing_with_422_WHEN_ENFORCED(monkeypatch):
    """The rule at full strength — behind the flag the chair flips."""
    monkeypatch.setattr(desk, "DESK_ROUTING_ENFORCE", True)
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "recommendations": [{"kind": "build", "text": "x"}]})
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["routing_rules_version"] == desk.ROUTING_RULES_VERSION
    assert sorted(body["required"]) == sorted(desk.ROUTING_REQUIRED_FIELDS)
    assert body["enforced"] is True
    assert ds._runs == [], "a refused filing must not be stored"


# --------------------------------------------- the enforcement flag (D24) ---
#
# THE HALF-SHIPPED CONTRACT (adversary D22, ground 2 of the bundle kill). The
# 422 was measured over the last day of live traffic and would have rejected
# 16 of 17 runs across eight seats: the schema half of a contract whose other
# half — the seat protocols that teach seats the four fields — is outside this
# repo's write scope. Enforced alone it does not tighten routing; it stops the
# record being written.

def test_the_enforcement_flag_SHIPS_OFF_and_the_reason_is_on_the_record():
    """Traceability half of the pin (D21 standard): the shipped value, and the
    written basis it came from, checked separately from the behaviour.

    Hardcoded True/False on purpose — a test that reads the constant it guards
    moves with it and pins nothing.
    """
    import inspect
    assert desk.DESK_ROUTING_ENFORCE is False
    assert desk.ROUTING_ENFORCED_FROM_VERSION == 1
    src = inspect.getsource(desk)
    assert "16 of the 17 runs" in src, (
        "the measured cost of flipping the flag must stay beside the flag")


def test_with_the_flag_off_an_unrouted_filing_is_STORED_and_the_finding_returned(monkeypatch):
    """Behavioural half: today's traffic is recorded, and told what it owes.

    An advisory is not a shrug. The whole reason the flip is cheap later is
    that the errors are computed and returned NOW, so nobody has to guess at
    the cost of turning the rule on.
    """
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "recommendations": [{"kind": "build", "text": "x"}]})
    assert r.status_code == 200
    assert len(ds._runs) == 1, "an unenforced filing is recorded, not dropped"
    adv = r.json()["routing_advisory"]
    assert adv["enforced"] is False
    assert len(adv["errors"]) == 1
    for field in desk.ROUTING_REQUIRED_FIELDS:
        assert field in adv["errors"][0]


def test_a_compliant_filing_carries_no_advisory_at_all(monkeypatch):
    """The advisory must not become furniture on every response — a warning
    that is always there is a warning nobody reads."""
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "recommendations": [dict(GOOD_REC)]})
    assert r.status_code == 200
    assert "routing_advisory" not in r.json()


def test_a_run_may_OPT_IN_to_the_refusal_ahead_of_the_fleet(monkeypatch):
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "routing_version": 1,
                     "recommendations": [{"kind": "build", "text": "x"}]})
    assert r.status_code == 422
    assert r.json()["detail"]["enforced"] is True
    assert ds._runs == []


@pytest.mark.parametrize("declared,expect", [
    (0, "stored"),          # a version below the threshold is not an opt-in
    (None, "stored"),       # absent is absent
    (1, "enforced"),        # the only shape that opts in
    (True, "rejected"),     # StrictInt: a typo'd flag is not version 1
    ("1", "rejected"),      # StrictInt: a quoted version is not a version
    (0.9, "rejected"),      # StrictInt: and 0.9 is not a version either
])
def test_what_counts_as_a_version_DECLARATION_measured_at_the_door(
        monkeypatch, declared, expect):
    """The opt-in must not fire on a value nobody meant as a version — that
    direction stops a run being recorded at all.

    THE TYPE BOUNDARY IS PYDANTIC'S, AND IT HAD TO BE MADE STRICT TO BE ONE.
    Measured on pydantic 2.13.4: a plain `Optional[int]` turns JSON `true`
    into the integer 1 and the string `"1"` into 1 — both would have opted a
    caller into a refusal it never asked for, and no handler-side type guard
    can see it, because the coercion already happened upstream. `StrictInt`
    is what makes the four rejections below true, and the `true` row is its
    only witness. (I first wrote the handler's bool guard off as unreachable,
    then measured that pydantic normalises `true` to a real `int` and the
    guard could never have fired: the guard is gone and the model is strict.)
    """
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "routing_version": declared,
                     "recommendations": [{"kind": "build", "text": "x"}]})
    if expect == "stored":
        assert r.status_code == 200 and len(ds._runs) == 1
        assert r.json()["routing_advisory"]["enforced"] is False
    elif expect == "enforced":
        assert r.status_code == 422 and ds._runs == []
        assert r.json()["detail"]["enforced"] is True
    else:
        assert r.status_code == 422 and ds._runs == []
        # pydantic's shape, not the routing rule's: a list of field errors.
        assert isinstance(r.json()["detail"], list)


def test_the_declared_version_is_stored_so_the_flip_can_be_audited(monkeypatch):
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "routing_version": 1,
                     "recommendations": [dict(GOOD_REC)]})
    assert r.status_code == 200
    assert ds._runs[0]["meta"]["routing_version"] == 1


def test_the_gate_and_the_rule_are_ONE_predicate_not_two(monkeypatch):
    """MOVE the rule and the gated wrapper must follow it (D18: a rule and the
    guard deciding whether the rule ran must not each carry the question)."""
    monkeypatch.setattr(desk, "ROUTING_REQUIRED_FIELDS", ("blast_radius",))
    assert desk.validate_routing(dict(GOOD_REC), 0, enforce=True)
    assert desk.validate_routing({"blast_radius": 1}, 0, enforce=True) == []
    # ...and with enforcement off the SAME row produces nothing to refuse.
    assert desk.validate_routing(dict(GOOD_REC), 0, enforce=False) == []


def test_the_endpoint_normalises_undecided_before_storing(monkeypatch):
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "recommendations": [{**GOOD_REC, "next_actor": "undecided"}]})
    assert r.status_code == 200
    stored = ds._runs[0]["recommendations"][0]
    assert stored["next_actor"] == "chair"
    assert stored["routed_from"] == "undecided"


def test_serves_requests_lands_in_meta_as_ids(monkeypatch):
    """THE ENGINE'S MISSING EDGE, measured: 66 of 66 open/approved requests on
    2026-08-23 could be joined to no run at all. This field is the fix, and it
    must arrive as identifiers — the hygiene join reads no prose."""
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "adversary", "task": "t",
                     "output": "o", "serves_requests": ["req-a", " req-b "],
                     "recommendations": []})
    assert r.status_code == 200
    assert ds._runs[0]["meta"]["serves_requests"] == ["req-a", "req-b"]


def test_a_run_with_no_recommendations_still_files(monkeypatch):
    """Routing binds ROWS, not runs. A verdict-only dispatch has none."""
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "adversary", "task": "t",
                     "output": "o"})
    assert r.status_code == 200


# ======================================================== 2. the matrix =====

def item(**kw):
    base = {"source": "recommendation", "seat": "pm", "status": "open",
            "next_actor_resolved": "ceo", "supersession": None}
    return {**base, **kw}


def test_every_item_lands_in_exactly_one_column():
    """A PARTITION, not four filters. Overlapping tallies are how '26
    elsewhere' ended up beside '6 with the chair', both true, one label apart."""
    items = [item(status=s) for s in ("open", "accepted", "staged", "done",
                                      "rejected", "noted")]
    items += [item(source="request", status=s)
              for s in ("open", "approved", "resolved", "declined")]
    items += [item(source="intray", status=s)
              for s in ("posted", "blessed", "struck")]
    m = desk.desk_matrix(items)
    assert sum(m["totals"].values()) == len(items) == m["items_classified"]


def test_a_terminal_row_carrying_a_live_edge_is_closed_not_blocking():
    """PRECEDENCE. A rejected row that is also superseded must not reappear
    under BLOCKING — it is finished, and a desk that resurrects finished work
    is the complaint this engine answers."""
    v = desk.classify_item(item(status="rejected",
                                supersession={"mode": "superseded"}))
    assert v["category"] == "closed"


def test_the_r37_shape_is_blocking_not_ticking():
    """THE TYPE SPECIMEN (docs/coo/TRIAGE7_2026-08-23.md decision 2).

    R37 is formally `staged`. Reading a staged row as 'in motion' is exactly
    the reading that lets it be clicked after the event that made it wrong —
    stripping the only dated exit coverage on $501.58.
    """
    v = desk.classify_item(item(
        status="staged",
        supersession={"mode": "superseded_pending",
                      "dies_at_event": "R39 step 4 rebuy"}))
    assert v["category"] == "blocking"
    assert "superseded_pending" in v["why"]


def test_a_row_whose_owner_cannot_be_read_blocks_rather_than_looking_open():
    v = desk.classify_item(item(next_actor_resolved="unknown"))
    assert v["category"] == "blocking"


def test_an_approved_request_nobody_dispatched_is_blocking_and_a_dispatched_one_ticks():
    """The chair backlog is a real blockage, measured at 30+ rows. It is not
    'in motion' and it is not the CEO's — it is waiting on one act."""
    assert desk.classify_item(
        item(source="request", status="approved",
             dispatched=False))["category"] == "blocking"
    assert desk.classify_item(
        item(source="request", status="approved",
             dispatched=True))["category"] == "ticking"


def test_the_closed_column_declares_that_it_understates_itself():
    """A COLUMN THAT CANNOT SEE ALL ITS ROWS MUST SAY SO.

    `DeskStore.open_recommendations` returns only open / accepted / staged, so
    a rejected or done recommendation never reaches this fold. The number is
    therefore a floor for recommendations and exact for everything else — and
    a reader taking it for the firm's closure rate would be reading an
    absence as a value, which is the one thing this desk is not allowed to do.
    """
    d = desk.CATEGORY_DEFINITIONS["closed"]
    assert "INCOMPLETE" in d and "recommendation" in d.lower()


def test_a_status_outside_the_vocabulary_blocks_rather_than_defaulting_open():
    v = desk.classify_item(item(status="halfway"))
    assert v["category"] == "blocking" and "vocabulary" in v["why"]


def test_a_cell_is_bounded_and_says_so():
    """NOTHING RENDERS UNBOUNDED — the CEO's own words were 'this feels like
    an infine scroll'. The cap must be visible as a cap, never read as a count:
    the last cap this desk shipped (25 runs) truncated the firm's first spend
    meter and nobody knew."""
    m = desk.desk_matrix([item() for _ in range(7)], cell_limit=3)
    cell = m["cells"]["pm"]["open"]
    assert cell["count"] == 7 and cell["shown"] == 3 and cell["truncated"] is True
    assert len(cell["items"]) == 3


def test_seat_to_seat_traffic_is_attributed_to_the_receiving_seat_and_never_to_the_ceo():
    """The spec: 'the CEO's desk never sees seat-to-seat traffic'."""
    items = desk.desk_items([], [], intray_items=[
        {"item_id": "i1", "to_seat": "quant", "from_seat": "pm",
         "task": "implement", "status": "posted"}])
    assert items[0]["seat"] == "quant"
    assert items[0]["next_actor_resolved"] == "seat"


def test_an_unattributable_row_is_kept_so_the_matrix_totals_to_the_desk():
    m = desk.desk_matrix([item(seat=None), item(seat="")])
    assert m["cells"]["unattributed"]["open"]["count"] == 2


# ================================================== 3. the CEO's surface ====

def rec(rec_id, **kw):
    base = {"rec_id": rec_id, "seat": "pm", "status": "open", "text": f"r{rec_id}",
            "kind": "awaits-ceo", "run_id": "run-x", "due_date": None,
            "money_at_stake": None, "resolved_at": "2026-08-22T00:00:00+00:00"}
    return {**base, **kw}


def _ceo(recs=(), requests=(), **kw):
    annotated = [desk._annotated(r) for r in recs]
    return desk.ceo_desk(open_recommendations=annotated, requests=list(requests),
                         now="2026-08-23T12:00:00+00:00", **kw)


def test_the_ceo_desk_and_the_counter_report_THE_SAME_NUMBER():
    """THE INVARIANT THIS PAGE EXISTS FOR, and the defect that earned it.

    The first cut of `ceo_desk` filtered its decision list to the `open` and
    `blocking` columns, which silently dropped every `accepted` row whose
    EXECUTION is still the CEO's own act — the COO's standing objection of
    2026-08-21, and the exact case the explicit `next_actor` field was added
    for. On the live corpus that was eight rows, and it put a FOURTH number on
    a page that already carried three claiming to be the same thing.

    Found by looking at the rendered page, not by any test. So this is the
    test: over a corpus containing every shape that matters — an accepted row
    routed explicitly to the CEO, a staged row routed to the chair, an open
    request, an approved request, an in-tray posting, a pending order and a
    terminal row — `decisions.total` and `desk_load.total` must agree exactly.
    """
    recs = [
        rec(1),                                             # open -> ceo
        rec(2, status="accepted", next_actor="ceo"),        # HIS to execute
        rec(3, status="staged"),                            # -> chair
        rec(4, kind="build"),                               # -> chair by kind
        rec(5, status="done"),                              # terminal
        rec(6, kind="nothing-anyone-has-seen"),             # -> ceo by default
    ]
    annotated = [desk._annotated(r) for r in recs]
    requests = [
        {"request_id": "q1", "kind": "attack", "status": "open", "at": "t"},
        {"request_id": "q2", "kind": "build", "status": "approved", "at": "t"},
        {"request_id": "q3", "kind": "build", "status": "resolved", "at": "t"},
    ]
    orders = [{"order_id": "o1", "symbol": "SPY", "side": "buy", "qty": 1,
               "impact_preview": {"notional_usd": 640.0}}]
    tray = [{"item_id": "i1", "to_seat": "quant", "from_seat": "pm",
             "task": "x", "status": "posted"}]

    out = desk.ceo_desk(open_recommendations=annotated, requests=requests,
                        intray_items=tray, pending_orders=orders,
                        now="2026-08-23T12:00:00+00:00")
    load = desk.desk_load(annotated, orders,
                          [r for r in requests if r["status"] == "open"])
    assert out["decisions"]["total"] == load["total"], (
        f"the CEO's page says {out['decisions']['total']} and the counter says "
        f"{load['total']} — two numbers for one question is the defect this "
        f"engine was built to end")
    # And the accepted-but-his row is genuinely in the list, not merely counted.
    assert 2 in [i.get("rec_id") for i in out["decisions"]["items"]]


def test_only_a_server_refusal_may_remove_a_row_from_the_ceos_count():
    """The ONE documented reason the two numbers may differ, pinned.

    A superseded row leaves the decision list because the spine refuses the
    click; it stays on the counter because it is still work owed. Any OTHER
    divergence is a bug, so the size of this one is asserted exactly.
    """
    annotated = [desk._annotated(r) for r in [rec(1), rec(2)]]
    ref = deskengine.rec_ref("run-x", 1)
    edges = {ref: {"target_ref": ref, "superseder_ref": "rec:run-y#1",
                   "mode": "superseded", "reason": "r", "retracted_at": None,
                   "edge_id": "e1"}}
    out = desk.ceo_desk(open_recommendations=annotated, requests=[],
                        supersessions=edges, now="2026-08-23T12:00:00+00:00")
    load = desk.desk_load(annotated, [], [])
    assert load["total"] - out["decisions"]["total"] == 1
    assert out["blocked"]["total"] == 1


def test_a_pending_order_is_on_the_board_and_belongs_to_nobody_on_the_bench():
    orders = [{"order_id": "o1", "symbol": "TLT", "side": "sell", "qty": 3,
               "impact_preview": {"notional_usd": 246.0}}]
    items = desk.desk_items([], [], pending_orders=orders)
    assert len(items) == 1
    o = items[0]
    assert o["seat"] == "execution", (
        "filing an order under the strategy that proposed it would put "
        "execution rows in a seat's ticket count")
    assert o["next_actor_resolved"] == "ceo"
    assert o["money_at_stake"] == 246.0
    assert o["reversibility"] == "irreversible"
    assert desk.classify_item(o)["category"] == "open"


def test_an_order_with_no_impact_preview_states_no_figure_rather_than_zero():
    items = desk.desk_items([], [], pending_orders=[{"order_id": "o", "qty": 1}])
    assert items[0]["money_at_stake"] is None


def test_the_decision_list_ranks_dates_first_then_money_with_absent_last():
    """Both ranking keys were empty on 47 of 47 rows. Now that they exist, an
    absence must not sort as an epoch date or as $0."""
    out = _ceo([rec(1, money_at_stake=10.0),
                rec(2, due_date="2026-09-08"),
                rec(3),
                rec(4, due_date="2026-08-30", money_at_stake=1.0),
                rec(5, money_at_stake=900.0)])
    order = [i["rec_id"] for i in out["decisions"]["items"]]
    assert order == [4, 2, 5, 1, 3]
    assert out["decisions"]["ranked_on_nothing"] == 1


def test_a_stated_negative_stake_still_outranks_a_stated_nothing():
    """Found by mutation: dropping the absence FLAG from the money key
    SURVIVED, because every fixture stated a positive figure and a positive
    figure sorts ahead of the 0.0 an absence contributes.

    A NEGATIVE stake exposes it — magnitude alone puts `-5` behind a row that
    said nothing at all, which is an absence beating a number, hiding in a
    sign. It is the exact case the comment on `_rank_key` claims to handle,
    and until this test the claim was unchecked.
    """
    out = _ceo([rec(1, money_at_stake=-5.0), rec(2)])
    assert [i["rec_id"] for i in out["decisions"]["items"]] == [1, 2]


def test_a_superseded_row_is_not_offered_as_a_decision():
    """The server refuses the approval, so listing it would offer a button
    that fails. It is on the kill shelf with its lineage instead."""
    edges = {deskengine.rec_ref("run-x", 1):
             {"target_ref": deskengine.rec_ref("run-x", 1),
              "superseder_ref": deskengine.rec_ref("run-y", 1),
              "mode": "superseded", "reason": "replaced by R39",
              "retracted_at": None, "edge_id": "e1"}}
    out = _ceo([rec(1), rec(2)], supersessions=edges)
    assert [i["rec_id"] for i in out["decisions"]["items"]] == [2]
    assert out["kill_shelf"]["total"] == 1


def test_a_pending_edge_keeps_the_row_off_the_decision_list_but_on_the_desk():
    """Its premise may revive. A row hidden from the desk cannot be revived by
    anyone who cannot see it — so pending stays out of the kill shelf."""
    ref = deskengine.rec_ref("run-x", 1)
    edges = {ref: {"target_ref": ref, "superseder_ref": deskengine.rec_ref("run-y", 1),
                   "mode": "superseded_pending", "reason": "premise dies Monday",
                   "dies_at_event": "R39 step 4", "revives_if": "R39 stops at the probe",
                   "retracted_at": None, "edge_id": "e1"}}
    out = _ceo([rec(1)], supersessions=edges)
    assert out["decisions"]["total"] == 0
    assert out["kill_shelf"]["total"] == 0
    assert out["matrix"]["totals"]["blocking"] == 1


def test_on_fire_is_dated_and_overdue_and_nothing_else():
    """'On fire means dated or losing money; nothing else goes there.'"""
    out = _ceo([rec(1, due_date="2026-08-23"),      # today — on fire
                rec(2, due_date="2026-08-22"),      # yesterday — on fire
                rec(3, due_date="2026-09-08"),      # future — not
                rec(4, money_at_stake=100000.0)])   # big, undated — not
    assert sorted(i["rec_id"] for i in out["on_fire"]["items"]) == [1, 2]


def test_an_unreachable_risk_control_renders_unknown_not_calm():
    out = _ceo([rec(1)], halted=None)
    assert out["on_fire"]["risk_halted"] is None
    out2 = _ceo([rec(1)], halted=False)
    assert out2["on_fire"]["risk_halted"] is False


def test_the_greeting_says_it_has_no_previous_visit_rather_than_no_change():
    """'Nothing has changed since your last visit' and 'we do not know when
    your last visit was' are different sentences; only one is a fact."""
    g = _ceo([rec(1)])["greeting"]
    assert "No previous visit" in g["changed"]
    assert "nothing" not in g["changed"].lower().split("marked new")[0][:40]

    g2 = _ceo([rec(1)], since="2026-08-22T00:00:00+00:00",
              changed={"new_requests": 0})["greeting"]
    assert "Nothing has been recorded since" in g2["changed"]

    g3 = _ceo([rec(1)], since="2026-08-22T00:00:00+00:00",
              changed={"new_requests": 3})["greeting"]
    assert "3 new requests" in g3["changed"]


def test_the_greeting_counts_agree_with_the_lists_beside_them():
    """If the greeting and the list disagree, one of them reads a different
    fold — the 11-vs-6 defect, which shipped twice."""
    out = _ceo([rec(1, due_date="2026-08-01"), rec(2), rec(3)])
    assert f"{out['decisions']['total']} item(s) need you" in out["greeting"]["needs_you"]
    assert str(len(out["on_fire"]["items"])) in out["greeting"]["on_fire"]


def test_everything_the_ceo_sees_carries_shown_total_and_a_cap():
    out = _ceo([rec(i) for i in range(1, 40)], decisions_limit=5)
    d = out["decisions"]
    assert d["shown"] == 5 and d["total"] == 39 and d["truncated"] is True


# ======================================================== 4. the shelf ======

def test_an_unreadable_ledger_makes_every_badge_unknown_not_unverified():
    """A memo the chair HAS checked must not be shown as unchecked by a
    database outage. Absence is not a value, including here."""
    s = desk.briefings(review_state=None)
    assert s["ledger_readable"] is False
    assert all(m["badge"] == "unknown" for m in s["memos"])
    assert "UNKNOWN" in s["note"]


def test_a_memo_is_unverified_until_the_chair_says_otherwise():
    s = desk.briefings(review_state={})
    assert s["memos"], "the shelf must find the real docs/ tree"
    assert all(m["badge"] == "chair-unverified" for m in s["memos"])
    path = s["memos"][0]["path"]
    s2 = desk.briefings(review_state={
        path: {"verified_by": "cto", "verified_at": "2026-08-23T00:00:00+00:00",
               "corrections": [{"actor": "cto", "note": "figure restated"}]}})
    hit = next(m for m in s2["memos"] if m["path"] == path)
    assert hit["badge"] == "chair-verified"
    assert hit["corrections"] and hit["corrections"][0]["note"] == "figure restated"


def test_the_shelf_carries_only_the_three_named_seats():
    """docs/reviews already renders in `artifacts` paired with what it
    attacked; docs/pm reaches the desk as recommendations with money and dates
    on them. One artifact in two places disagrees with itself eventually."""
    dirs = {s["dir"] for s in desk.BRIEFING_SOURCES}
    assert dirs == {"archives", "coo", "cfo"}
    s = desk.briefings(review_state={})
    assert not any("/reviews/" in m["path"] or "/pm/" in m["path"]
                   for m in s["memos"])


def test_the_shelf_is_newest_first_and_undated_memos_sort_last():
    dated = [m for m in desk.briefings(review_state={})["memos"] if m["date"]]
    assert dated == sorted(dated, key=lambda m: m["date"], reverse=True)


# ================================================== 5. the hygiene guard ====

def test_no_shipped_rule_can_write_anything_but_bookkeeping():
    """THE TEST THAT CANNOT BLESS A LOOSENING.

    It walks the SHIPPED table, not a fixture of it, so a rule added later
    with an approving action fails here rather than at review. Two tests once
    asserted a gate loosening; this is the shape that could not.
    """
    for rule in deskhygiene.HYGIENE_RULES:
        assert rule.action in deskhygiene.RULE_ACTIONS
        deskhygiene.assert_bookkeeping_only(rule.action, rule.produces)
        if rule.action in deskhygiene.CLOSING_ACTIONS:
            assert rule.produces in deskhygiene.BOOKKEEPING_STATUSES
        else:
            assert rule.produces is None


def test_the_allowlist_holds_exactly_one_status_and_it_is_resolved():
    """PINNED, HARDCODED, FROM BOTH SIDES (D21 standard).

    Found by mutation: widening ``BOOKKEEPING_STATUSES`` to include
    `accepted` SURVIVED the whole suite, because `assert_bookkeeping_only`
    also checks the action->status mapping and refused on that second test
    instead. Defence in depth is good; a test that cannot tell WHICH layer
    refused is not, because the day someone simplifies the second check the
    allowlist becomes the only guard and nothing here would notice.

    So this pins the constant itself. Widening it is then a visible red test
    with this docstring attached, which is exactly the conversation a
    loosening should have to have.
    """
    assert deskhygiene.BOOKKEEPING_STATUSES == ("resolved",)
    assert deskhygiene.ACTION_STATUS == {"close_request": "resolved"}
    assert deskhygiene.CLOSING_ACTIONS == ("close_request",)
    for forbidden in ("accepted", "staged", "approved", "rejected", "declined",
                      "done", "noted"):
        assert forbidden not in deskhygiene.BOOKKEEPING_STATUSES


def test_every_rule_carries_its_id_version_reason_and_authority():
    """An auditor reads the rule, never a diff."""
    for rule in deskhygiene.HYGIENE_RULES:
        d = rule.as_dict()
        for field in ("rule_id", "since", "title", "evidence",
                      "written_reason", "authority"):
            assert d[field] and isinstance(d[field], str), field
    assert len({r.rule_id for r in deskhygiene.HYGIENE_RULES}) == \
        len(deskhygiene.HYGIENE_RULES)


@pytest.mark.parametrize("status", ["accepted", "staged", "approved",
                                    "rejected", "declined", "noted", "done",
                                    "open", None, ""])
def test_the_guard_refuses_every_status_that_is_not_bookkeeping(status):
    """Hardcoded, from BOTH sides of the boundary (D21 standard): a test
    parametrised by the constant it guards moves with the constant and pins
    nothing."""
    if status in ("resolved",):
        return
    with pytest.raises(ValueError):
        deskhygiene.assert_bookkeeping_only("close_request", status)


def test_the_guard_reads_the_allowlist_rather_than_repeating_it(monkeypatch):
    """MOVE it. `resolved` is refused once the allowlist no longer holds it —
    which a test asserting `== "resolved"` could never distinguish from a
    hardcoded copy."""
    monkeypatch.setattr(deskhygiene, "BOOKKEEPING_STATUSES", ("filed_away",))
    monkeypatch.setattr(deskhygiene, "ACTION_STATUS", {"close_request": "filed_away"})
    with pytest.raises(ValueError):
        deskhygiene.assert_bookkeeping_only("close_request", "resolved")
    deskhygiene.assert_bookkeeping_only("close_request", "filed_away")


def test_the_allowlist_is_INDEPENDENT_of_the_action_mapping(monkeypatch):
    """THE BOUNDARY MUST NOT DERIVE FROM THE MECHANISM.

    Found by mutation: deleting the allowlist check entirely SURVIVED, because
    the action->status mapping refused the same inputs. That agreement holds
    only while there is one action and one status — and it means a future
    loosening could be shipped by widening the MECHANISM alone, with the
    boundary quietly following it.

    So this pins the case where the two disagree: the mechanism is moved to
    produce `accepted`, and the guard must still refuse, because `accepted` is
    not a state this policy is allowed to write no matter what any action map
    says. Deriving `BOOKKEEPING_STATUSES` from `ACTION_STATUS.values()` would
    make this test impossible to write, which is the reason the duplication
    stays.
    """
    monkeypatch.setattr(deskhygiene, "ACTION_STATUS",
                        {"close_request": "accepted"})
    with pytest.raises(ValueError, match="may only write"):
        deskhygiene.assert_bookkeeping_only("close_request", "accepted")


def test_the_applier_calls_the_guard_and_not_only_its_own_checks():
    """Found by mutation: removing `assert_bookkeeping_only` from
    `apply_proposal` SURVIVED — every fixture went through `evaluate`, which
    never builds a mismatched proposal. A guard is only wired if something
    reaches it that nothing else would catch, so here is that something: a
    well-formed close carrying a status the policy may not write.
    """
    called = []
    with pytest.raises(ValueError, match="may only write"):
        deskhygiene.apply_proposal(
            {"action": "close_request", "status": "accepted", "rule_id": "H1",
             "citation": "a real-looking citation",
             "target": {"request_id": "q1"}},
            close_request=lambda *a: called.append(a))
    assert called == [], "the write must not happen before the guard"


def test_an_unrecognised_action_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        deskhygiene.assert_bookkeeping_only("approve_order", "resolved")


def test_a_flag_may_not_carry_a_status():
    with pytest.raises(ValueError):
        deskhygiene.assert_bookkeeping_only("flag", "resolved")
    deskhygiene.assert_bookkeeping_only("flag", None)


def test_applying_a_flag_is_refused():
    """A flag is a proposal for a human's click. Applying one would be the
    policy claiming a confirmation nobody gave."""
    with pytest.raises(ValueError):
        deskhygiene.apply_proposal(
            {"action": "flag", "status": None, "rule_id": "H3",
             "citation": "x", "target": {}},
            close_request=lambda *a: None)


def test_a_close_with_no_citation_is_refused():
    """The riskofficer audits this policy FROM its citations. An unexplained
    auto-close is indistinguishable from a bug."""
    with pytest.raises(ValueError):
        deskhygiene.apply_proposal(
            {"action": "close_request", "status": "resolved", "rule_id": "H1",
             "citation": "  ", "target": {"request_id": "r"}},
            close_request=lambda *a: None)


def test_a_proposal_naming_an_unknown_rule_is_refused():
    with pytest.raises(ValueError):
        deskhygiene.apply_proposal(
            {"action": "close_request", "status": "resolved", "rule_id": "H9",
             "citation": "c", "target": {"request_id": "r"}},
            close_request=lambda *a: None)


# ================================================ 6. the evidence joins =====

def test_h1_closes_a_blind_review_on_a_delivered_verdict():
    """MEASURED LEAK: requests 1c53589f and b6f4a407 were still `open` on the
    live spine while run-adversary-batch2 had delivered both verdicts."""
    reqs = [{"request_id": "q1", "kind": "attack", "status": "open",
             "trace_id": "t1"}]
    out = deskhygiene.evaluate(requests=reqs,
                               runs=[run("run-a", trace="t1")])
    assert [p["rule_id"] for p in out["proposals"]] == ["H1"]
    p = out["proposals"][0]
    assert p["status"] == "resolved" and p["join"] == "trace_id"
    assert "run-a" in p["citation"] and "KILL" in p["citation"]


@pytest.mark.parametrize("status", [None, "failed", "aborted", "", "DELIVERED?"])
def test_a_run_that_did_not_deliver_closes_nothing(status):
    """ABSENCE IS NOT DELIVERY. A NULL status means the chair recorded no
    outcome; reading it as success would close a desk request on a dispatch
    that may have died with the host — which happened, for three hours, on
    2026-08-22."""
    reqs = [{"request_id": "q1", "kind": "attack", "status": "open",
             "trace_id": "t1"}]
    out = deskhygiene.evaluate(requests=reqs,
                               runs=[run("run-a", trace="t1", status=status)])
    assert out["proposals"] == []
    assert out["counts"]["linked_but_undelivered"] == 1


def test_a_blind_review_with_no_recorded_verdict_is_not_closed():
    """'The seat returned' and 'the question was answered' come apart exactly
    here, and a blind review closes on its verdict."""
    reqs = [{"request_id": "q1", "kind": "attack", "status": "open",
             "trace_id": "t1"}]
    out = deskhygiene.evaluate(requests=reqs,
                               runs=[run("run-a", trace="t1", verdict="")])
    assert out["proposals"] == []
    assert out["counts"]["linked_but_undelivered"] == 1


def test_a_verdict_from_a_seat_that_is_not_the_adversary_does_not_close_a_blind_review():
    """Blind review is the adversary's boundary. A 'verdict' from any other
    seat closing an attack request would let the reviewed party close its own
    review."""
    reqs = [{"request_id": "q1", "kind": "attack", "status": "open",
             "trace_id": "t1"}]
    out = deskhygiene.evaluate(
        requests=reqs, runs=[run("run-a", seat="builder", trace="t1")])
    assert out["proposals"] == []


def test_h2_closes_an_approved_request_on_a_declared_join():
    """The `declared` edge is `meta.serves_requests` — IDs the chair states at
    record time. It is the only join that works today: zero runs carry a
    request's trace and DeskDispatched stopped being written 2026-08-21."""
    reqs = [{"request_id": "q2", "kind": "build", "status": "approved",
             "trace_id": "t2"}]
    out = deskhygiene.evaluate(
        requests=reqs,
        runs=[run("run-b", seat="builder", verdict=None, serves=["q2"])])
    assert [p["rule_id"] for p in out["proposals"]] == ["H2"]
    assert out["proposals"][0]["join"] == "declared"


def test_a_dispatch_event_naming_the_request_is_the_strongest_join():
    reqs = [{"request_id": "q3", "kind": "build", "status": "approved",
             "trace_id": "nothing-matches-this"}]
    out = deskhygiene.evaluate(
        requests=reqs, runs=[run("run-c", seat="builder", trace="q3")],
        dispatches=[dispatched("q3", seat="builder")["payload"]])
    assert out["proposals"][0]["join"] == "dispatch_request_id"


def test_a_request_with_no_evidence_edge_is_reported_not_left_silent():
    """MEASURED 2026-08-23: 66 of 66. A hygiene engine that answered '0
    closes' against a desk of 92 rows would be reporting a clean desk when
    what it means is a missing edge."""
    reqs = [{"request_id": "q4", "kind": "build", "status": "approved",
             "trace_id": "t4", "task": "build the thing", "seat": "builder"}]
    out = deskhygiene.evaluate(requests=reqs, runs=[run("run-d", trace="other")])
    assert out["proposals"] == []
    assert out["counts"]["unlinkable"] == 1
    assert out["unlinkable"][0]["request_id"] == "q4"
    assert "NOT the same as no work" in out["unlinkable"][0]["why"]
    assert "NO evidence edge" in out["note"]


@pytest.mark.parametrize("status", ["resolved", "declined"])
def test_a_terminal_request_is_never_a_hygiene_candidate(status):
    reqs = [{"request_id": "q5", "kind": "attack", "status": status,
             "trace_id": "t5"}]
    out = deskhygiene.evaluate(requests=reqs, runs=[run("run-e", trace="t5")])
    assert out["proposals"] == [] and out["counts"]["candidate_requests"] == 0


def test_a_prose_match_can_only_ever_flag():
    reqs = []
    recs = [{"run_id": "r", "rec_id": 1, "status": "open",
             "text": "shipped in abc1234, see the diff"}]
    out = deskhygiene.evaluate(requests=reqs, runs=[], recommendations=recs,
                               is_ancestor=lambda s: True)
    assert out["proposals"] == []
    assert out["flags"][0]["flag"] == "probably_discharged"
    assert out["flags"][0]["status"] is None
    assert "never auto-closed" in out["flags"][0]["requires"]


def test_a_citation_git_could_not_resolve_is_unchecked_not_clean():
    recs = [{"run_id": "r", "rec_id": 1, "status": "open",
             "text": "shipped in abc1234"}]
    out = deskhygiene.evaluate(requests=[], runs=[], recommendations=recs,
                               is_ancestor=lambda s: None)
    assert out["flags"][0]["flag"] == "unresolvable_citation"
    assert "UNCHECKED" in out["flags"][0]["requires"]


def test_a_commit_not_in_head_raises_nothing():
    recs = [{"run_id": "r", "rec_id": 1, "status": "open",
             "text": "proposed in abc1234"}]
    out = deskhygiene.evaluate(requests=[], runs=[], recommendations=recs,
                               is_ancestor=lambda s: False)
    assert out["flags"] == []


def test_a_rule_that_did_not_run_says_so_instead_of_finding_nothing():
    """H3 needs a git oracle. The desk read supplies none — and a payload
    reporting zero flags would be a rule that never ran wearing the costume of
    a clean result."""
    out = deskhygiene.evaluate(requests=[], runs=[], recommendations=[],
                               is_ancestor=None)
    assert [x["rule_id"] for x in out["rules_not_evaluated"]] == ["H3"]
    assert "H3" not in out["rules_evaluated"]
    assert "UNCHECKED" in out["note"]
    out2 = deskhygiene.evaluate(requests=[], runs=[], recommendations=[],
                                is_ancestor=lambda s: False)
    assert out2["rules_not_evaluated"] == []
    assert set(out2["rules_evaluated"]) == {r.rule_id for r in deskhygiene.HYGIENE_RULES}


@pytest.mark.parametrize("token,found", [
    ("abc1234", True),        # has a letter
    ("2026080", False),       # a date fragment: hex-legal, all digits
    ("1885", False),          # too short
    ("deadbeef", True),
    ("739b5ac9", True),       # a desk TICKET id — git is the arbiter, not us
])
def test_the_sha_reader_needs_a_letter_because_this_desk_is_made_of_numbers(token, found):
    assert (token in deskhygiene.cited_commits(f"see {token} here")) is found


def test_cited_commits_dedupes_and_keeps_order():
    assert deskhygiene.cited_commits("abc1234 then def5678 then abc1234") == \
        ["abc1234", "def5678"]


# ============================================ 7. the supersession refusal ===

REF = "rec:run-x#1"


def _edge(mode="superseded", **kw):
    base = {"edge_id": "e1", "target_ref": REF, "superseder_ref": "rec:run-y#1",
            "mode": mode, "reason": "R39 buys the exits back",
            "dies_at_event": None, "revives_if": None, "retracted_at": None}
    return {**base, **kw}


@pytest.mark.parametrize("mode", deskengine.UNAPPROVABLE_MODES)
def test_every_unapprovable_mode_refuses(mode):
    r = deskengine.approval_refusal(REF, {REF: _edge(mode)})
    assert r and r["refused"] is True and r["mode"] == mode
    assert "rec:run-y#1" in r["detail"]


def test_the_refusal_reads_the_mode_set_rather_than_listing_modes(monkeypatch):
    """MOVE it: with `superseded` off the unapprovable list the refusal must
    disappear. An assertion that the three known modes refuse cannot tell a
    read from three hardcoded branches."""
    monkeypatch.setattr(deskengine, "UNAPPROVABLE_MODES", ("killed",))
    assert deskengine.approval_refusal(REF, {REF: _edge("superseded")}) is None
    assert deskengine.approval_refusal(REF, {REF: _edge("killed")})


def test_a_retracted_edge_stops_refusing():
    """The revival branch. 'If Monday stops at the probe, R37's premise
    revives intact.'"""
    assert deskengine.approval_refusal(
        REF, {REF: _edge(retracted_at="2026-08-24T00:00:00+00:00")}) is None


def test_a_pending_refusal_carries_both_halves_of_its_own_story():
    r = deskengine.approval_refusal(REF, {REF: _edge(
        "superseded_pending", dies_at_event="R39 step 4 rebuy",
        revives_if="R39 stops at the probe")})
    assert "R39 step 4 rebuy" in r["detail"]
    assert "R39 stops at the probe" in r["detail"]
    assert "retract the edge first" in r["detail"]


def test_an_unreadable_edge_store_does_not_take_the_approval_path_down():
    """The one place in this engine where an absence fails PERMISSIVE, and it
    is deliberate: refusing every approval whenever Postgres hiccups would
    stop the CEO's whole desk for a bookkeeping table. The degradation is
    reported in the payload (`readable.supersessions`) so a click during an
    outage is visible in the record."""
    assert deskengine.approval_refusal(REF, None) is None


def test_a_row_with_no_edge_is_untouched():
    assert deskengine.approval_refusal(REF, {}) is None
    assert deskengine.approval_refusal(None, {REF: _edge()}) is None


@pytest.mark.parametrize("ref,ok", [
    ("rec:run-x#1", True), ("req:abc-123", True),
    ("rec:run-x", False), ("rec:run-x#a", False), ("", False),
    ("run-x#1", False), (None, False), (7, False),
])
def test_a_row_reference_parses_or_is_refused_never_silently_matches_nothing(ref, ok):
    assert (deskengine.parse_ref(ref) is not None) is ok


# ============================================== 8. the refusal at the API ===

def test_approving_a_superseded_recommendation_is_refused_by_the_server(monkeypatch):
    """A DISABLED BUTTON IS A HINT. R37 must be impossible through the API,
    not merely awkward through the UI."""
    ds = FakeDeskStore()
    edges = {deskengine.rec_ref("run-x", 1): _edge(target_ref=deskengine.rec_ref("run-x", 1))}
    c = client(monkeypatch, MemStore(), deskstore=ds, edges=edges)
    r = c.post("/api/v1/fund/desk/runs/run-x/recommendations/1",
               json={"status": "accepted", "actor": "ceo"})
    assert r.status_code == 409
    assert r.json()["detail"]["mode"] == "superseded"
    assert ds.decided == [], "nothing may be written on a refused decision"


def test_withdrawing_a_superseded_recommendation_stays_easy(monkeypatch):
    """THE OTHER DIRECTION, and it is the one an over-eager guard breaks. The
    R37 disposition is *withdraw it*; an engine that blocked the withdrawal
    along with the approval would wedge the row on the desk forever."""
    ds = FakeDeskStore()
    edges = {deskengine.rec_ref("run-x", 1): _edge(target_ref=deskengine.rec_ref("run-x", 1))}
    c = client(monkeypatch, MemStore(), deskstore=ds, edges=edges)
    r = c.post("/api/v1/fund/desk/runs/run-x/recommendations/1",
               json={"status": "rejected", "actor": "ceo",
                     "note": "withdrawn per triage 7"})
    assert r.status_code == 200
    assert ds.decided == [("run-x", 1, "rejected")]


def test_approving_a_superseded_request_is_refused_AFTER_the_guard_admits_the_caller(monkeypatch):
    """ORDER CORRECTED (adversary D22): identity first, lineage second.

    v1 ran the supersession check first and handed the edge, its superseder
    and its named future event to ANY caller — including one the allowlist was
    about to refuse. The refusal itself is unchanged and still cannot admit
    anything; only who gets to read the lineage moved.
    """
    from app.api.v1 import fund as fundapi
    calls = []
    monkeypatch.setattr(fundapi, "_guard_approval",
                        lambda *a, **k: calls.append(a) or "ceo")
    store = MemStore()
    edges = {deskengine.req_ref("q1"): _edge(target_ref=deskengine.req_ref("q1"),
                                             mode="killed", superseder_ref=None)}
    c = client(monkeypatch, store, edges=edges)
    r = c.post("/api/v1/fund/desk/requests/q1/approve",
               json={"actor": "ceo", "confirm": "q1"})
    assert r.status_code == 409
    assert len(calls) == 1, "the approval guard runs FIRST now"
    assert [e["type"] for e in store.events] == ["ApprovalRefused"]
    assert store.events[0]["payload"]["guard"] == "supersession_v1"
    assert "DeskRequestApproved" not in [e["type"] for e in store.events]


def test_a_caller_the_allowlist_refuses_never_sees_the_lineage(monkeypatch):
    """THE REASON THE ORDER MOVED, stated as its own test. A row's supersession
    lineage names the superseder and the future event that kills its premise;
    a caller who cannot approve anything has no business reading it.

    The real guard runs here — not a stub — because the fact under test is
    which refusal arrives first, and a stubbed guard cannot refuse.
    """
    store = MemStore()
    edges = {deskengine.req_ref("q1"): _edge(target_ref=deskengine.req_ref("q1"),
                                             mode="superseded_pending",
                                             dies_at_event="R39 step 4",
                                             revives_if="the probe stops")}
    c = client(monkeypatch, store, edges=edges)
    r = c.post("/api/v1/fund/desk/requests/q1/approve",
               json={"actor": "mallory", "confirm": "q1"})
    assert r.status_code == 403
    body = r.json()
    for leak in ("R39 step 4", "the probe stops", "superseded_pending",
                 "rec:run-y#1"):
        assert leak not in str(body), f"the 403 leaked {leak!r}"
    # The channel guard's own refusal is still recorded, as it always was.
    assert [e["type"] for e in store.events] == ["ApprovalRefused"]
    assert store.events[0]["payload"]["reason"].startswith("approver 'mallory'")


def test_the_supersession_refusal_is_RECORDED_not_only_returned(monkeypatch):
    """THE FUND'S FIRST SILENT APPROVAL REFUSAL (adversary D22), closed.

    Every other refusal on this path appends `ApprovalRefused` — the channel
    guard since v1, `_guard_mark_sanity` since 2026-08-21. The riskofficer
    audits refusals from /fund/events and nowhere else, so a 409 that exists
    only in an HTTP response is a refusal nobody can audit.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    store = MemStore()
    edges = {deskengine.req_ref("q1"): _edge(target_ref=deskengine.req_ref("q1"),
                                             mode="superseded_pending",
                                             dies_at_event="R39 step 4",
                                             revives_if="the probe stops")}
    c = client(monkeypatch, store, edges=edges)
    r = c.post("/api/v1/fund/desk/requests/q1/approve",
               json={"actor": "ceo", "confirm": "q1"})
    assert r.status_code == 409
    assert len(store.events) == 1
    ev = store.events[0]
    assert ev["type"] == "ApprovalRefused"
    assert ev["aggregate_type"] == "desk_request" and ev["aggregate_id"] == "q1"
    p = ev["payload"]
    assert p["guard"] == "supersession_v1"
    assert p["edge_id"] == "e1" and p["mode"] == "superseded_pending"
    assert p["row_ref"] == deskengine.req_ref("q1")
    assert "R39 step 4" in p["reason"]


def test_the_refusal_on_a_RECOMMENDATION_is_recorded_too(monkeypatch):
    """Same control, same silence, same fix — the D17 corollary: a fix applied
    to one file in a family is not applied to its siblings."""
    ds = FakeDeskStore()
    ref = deskengine.rec_ref("run-x", 1)
    store = MemStore()
    c = client(monkeypatch, store, deskstore=ds,
               edges={ref: _edge(target_ref=ref)})
    r = c.post("/api/v1/fund/desk/runs/run-x/recommendations/1",
               json={"status": "accepted", "actor": "ceo"})
    assert r.status_code == 409
    assert [e["type"] for e in store.events] == ["ApprovalRefused"]
    assert store.events[0]["payload"]["row_ref"] == ref
    assert ds.decided == []


def test_an_approval_taken_during_an_outage_SAYS_SO_in_the_record(monkeypatch):
    """THE DISCLOSURE THAT JUSTIFIES FAILING OPEN (adversary D22, ground 1).

    The fail-open is accepted policy; what was missing is the sentence in the
    record saying the check did not run. Without it an approval taken during a
    Postgres outage is indistinguishable from a verified one, which is the
    whole cost of failing open, unpaid.
    """
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    store = MemStore()
    c = client(monkeypatch, store, edges=None)     # unreadable, not empty
    r = c.post("/api/v1/fund/desk/requests/q1/approve", json={"actor": "ceo"})
    assert r.status_code == 200
    assert r.json()["supersession_readable"] is False
    assert store.events[0]["payload"]["supersession_readable"] is False


def test_a_verified_approval_says_the_check_RAN(monkeypatch):
    """The other half, and the one that makes the first half mean anything: a
    field that is only ever False is a field nobody can read a claim from."""
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    store = MemStore()
    c = client(monkeypatch, store, edges={})       # readable, and empty
    r = c.post("/api/v1/fund/desk/requests/q1/approve", json={"actor": "ceo"})
    assert r.status_code == 200
    assert r.json()["supersession_readable"] is True
    assert store.events[0]["payload"]["supersession_readable"] is True


def test_a_non_advancing_decision_reports_the_check_as_NOT_RUN_never_as_clean(monkeypatch):
    """None is not False and neither is True. Rejecting a row does not consult
    the brake, and the record must not imply that it did."""
    ds = FakeDeskStore()
    store = MemStore()
    c = client(monkeypatch, store, deskstore=ds, edges={})
    r = c.post("/api/v1/fund/desk/runs/run-x/recommendations/1",
               json={"status": "rejected", "actor": "ceo"})
    assert r.status_code == 200
    assert r.json()["supersession_readable"] is None
    decided = [e for e in store.events if e["type"] == "DeskRecommendationDecided"]
    assert decided[0]["payload"]["supersession_readable"] is None


def test_an_ordinary_request_still_approves(monkeypatch):
    """The tightening must be invisible to every row without an edge."""
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    store = MemStore()
    c = client(monkeypatch, store, edges={})
    r = c.post("/api/v1/fund/desk/requests/q1/approve", json={"actor": "ceo"})
    assert r.status_code == 200
    assert [e["type"] for e in store.events] == ["DeskRequestApproved"]


# ================================================ 9. applying the policy ====

def test_hygiene_apply_writes_a_resolution_carrying_its_rule_and_citation(monkeypatch):
    """Every auto-close is auditable from /fund/events, like any other write:
    the actor NAMES the policy version and the payload carries the rule id,
    the join and the evidence."""
    store = MemStore([requested("q1"), approved("q1")])
    ds = FakeDeskStore(runs=[run("run-a", serves=["q1"])])
    c = client(monkeypatch, store, deskstore=ds)
    proposed = c.get("/api/v1/fund/desk/hygiene?git=false").json()
    assert [p["rule_id"] for p in proposed["proposals"]] == ["H1"]

    r = c.post("/api/v1/fund/desk/hygiene/apply",
               json={"proposals": [{"rule_id": "H1", "request_id": "q1"}],
                     "actor": "cto"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["applied"]) == 1 and body["refused"] == []
    written = [e for e in store.events if e["type"] == "DeskRequestResolved"]
    assert len(written) == 1
    assert written[0]["actor"].startswith("desk-hygiene/")
    hyg = written[0]["payload"]["hygiene"]
    assert hyg["rule_id"] == "H1" and hyg["join"] == "declared"
    assert deskhygiene.POLICY_VERSION in written[0]["payload"]["resolution"]


def test_hygiene_apply_refuses_a_proposal_the_engine_does_not_currently_make(monkeypatch):
    """Otherwise this endpoint is 'close any request you name' wearing a
    hygiene label. The state can move between the read and the write."""
    store = MemStore([requested("q1"), approved("q1")])
    c = client(monkeypatch, store, deskstore=FakeDeskStore())
    r = c.post("/api/v1/fund/desk/hygiene/apply",
               json={"proposals": [{"rule_id": "H1", "request_id": "q1"}]})
    assert r.status_code == 200
    assert r.json()["applied"] == []
    assert "does not currently propose" in r.json()["refused"][0]["why"]
    assert [e for e in store.events if e["type"] == "DeskRequestResolved"] == []


def test_hygiene_apply_cannot_be_talked_into_approving(monkeypatch):
    """A caller naming a rule whose action approves gets nothing: the applier
    matches against the live evaluation, and the guard refuses anything the
    allowlist does not hold."""
    store = MemStore([requested("q1")])
    c = client(monkeypatch, store, deskstore=FakeDeskStore())
    r = c.post("/api/v1/fund/desk/hygiene/apply",
               json={"proposals": [{"rule_id": "H1", "request_id": "q1",
                                    "action": "approve", "status": "approved"}]})
    assert r.json()["applied"] == []
    assert [e for e in store.events
            if e["type"] in ("DeskRequestApproved", "OrderApproved")] == []


def test_the_desk_read_does_not_evaluate_the_git_rule(monkeypatch):
    """Shelling out to git once per cited commit on the page the CEO opens is
    a cost his desk should not carry — and the payload must say H3 did not run
    rather than report no flags."""
    store = MemStore([requested("q1")])
    c = client(monkeypatch, store, deskstore=FakeDeskStore())
    body = c.get("/api/v1/fund/desk/ceo").json()
    assert [x["rule_id"] for x in body["hygiene"]["rules_not_evaluated"]] == ["H3"]


def test_the_intray_history_route_is_declared_before_the_seat_parameter():
    """FastAPI matches in DECLARATION order. A literal path registered after a
    path parameter on the same prefix is unreachable and 404s plausibly — this
    codebase has already shipped that once (`/fund/desk/runs/stats`), and
    reading the file top to bottom is exactly how it gets reintroduced by the
    next person appending a route at the end."""
    from fastapi.routing import APIRoute
    from app.api.v1 import fund as fundapi
    # PER METHOD. `/fund/desk/intray/{seat}` is registered for BOTH POST and
    # GET, and a naive `paths.index(...)` finds the POST — which is declared
    # first and shadows nothing, because a POST route cannot swallow a GET.
    # The first cut of this test did exactly that and failed on a correct
    # ordering, which is a test that would have been "fixed" by moving working
    # code.
    gets = [r.path for r in fundapi.router.routes
            if isinstance(r, APIRoute) and "GET" in (r.methods or set())]
    assert gets.index("/fund/desk/intray/item/{item_id}/history") \
        < gets.index("/fund/desk/intray/{seat}")


def test_a_mistyped_intray_filter_is_refused_not_answered_with_an_empty_tray(monkeypatch):
    """An unmatched filter returns no rows, and no rows reads as 'this seat has
    nothing waiting'. The caller would be told a fact about the world by a fact
    about its own spelling."""
    class Tray:
        def items(self, seat=None, status=None, limit=500):
            from app.fund.deskengine import INTRAY_STATUSES
            if status is not None and status not in INTRAY_STATUSES:
                raise ValueError("status must be one of ...")
            return []
        def returns_for(self, seat, limit=200):
            return []
    c = client(monkeypatch, MemStore(), intray=Tray())
    assert c.get("/api/v1/fund/desk/intray/quant?status=pending").status_code == 422
    assert c.get("/api/v1/fund/desk/intray/quant?status=posted").status_code == 200


def test_the_hygiene_module_ships_no_constant_nothing_reads():
    """Deleted before shipping: a `JOIN_KINDS` tuple no code consulted. A
    constant with no reader is a label, and this fund has a rule about those.
    Pinned so it does not come back as documentation-shaped dead weight."""
    assert not hasattr(deskhygiene, "JOIN_KINDS")


def test_the_ceo_endpoint_reports_which_stores_it_could_read(monkeypatch):
    """A page that could not read the supersession table must render 'lineage
    unknown', never 'no lineage'. The second is a claim."""
    c = client(monkeypatch, MemStore(), deskstore=None, edges=None, intray=None)
    body = c.get("/api/v1/fund/desk/ceo").json()
    assert body["readable"]["recommendations"] is False
    assert body["readable"]["supersessions"] is False
    assert body["readable"]["intray"] is False


# ============================ 12. the edge reader itself (D24 repairs) ======

def test_a_cold_cache_outage_and_a_warm_one_get_THE_SAME_policy(monkeypatch):
    """ADVERSARY D22, probe F1: the fail-open was decided by CACHE WARMTH.

    Store CONSTRUCTION sat outside the try, so the first approval after a
    restart with Postgres down raised OSError and 500'd the approval path —
    the exact outcome failing open exists to prevent — while a warm process
    degraded silently to permissive. One outage must produce one policy.
    """
    from app.api.v1 import fund as fundapi

    def cold():                     # construction fails, as on a restart
        raise OSError("connection to server at 127.0.0.1 port 5433 failed")

    class WarmButUnreadable:        # construction fine, query fails
        def by_target(self):
            raise RuntimeError("postgres went away mid-check")

    monkeypatch.setattr(fundapi, "_supersessions", cold)
    assert fundapi._edges_by_target() is None
    monkeypatch.setattr(fundapi, "_supersessions", lambda: WarmButUnreadable())
    assert fundapi._edges_by_target() is None


def test_a_TRUNCATED_edge_map_is_unreadable_not_short(monkeypatch):
    """The two repairs meeting: the store raises past its limit, and this
    reader turns that into UNREADABLE — which is the disclosed fail-open, not
    a map with the brakes quietly missing from it."""
    from app.api.v1 import fund as fundapi
    from app.fund.deskengine import SupersessionsTruncated

    class Flooded:
        def by_target(self):
            raise SupersessionsTruncated(1000, "WHERE retracted_at IS NULL")

    monkeypatch.setattr(fundapi, "_supersessions", lambda: Flooded())
    assert fundapi._edges_by_target() is None


def test_a_failure_ABOVE_the_store_is_the_same_policy_not_a_500(monkeypatch):
    """The last uncaught path (adversary D22, probe D's final case). If the
    reader itself is broken or replaced, the approval path must still take the
    disclosed fail-open — a 500 here is the CEO unable to approve anything
    because a bookkeeping helper threw."""
    from app.api.v1 import fund as fundapi

    def boom():
        raise RuntimeError("postgres went away mid-check")

    monkeypatch.setattr(fundapi, "_edges_by_target", boom)
    monkeypatch.setattr(fundapi, "_guard_approval", lambda *a, **k: "ceo")
    store = MemStore()
    monkeypatch.setattr(fundapi, "_store", store)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    r = TestClient(app).post("/api/v1/fund/desk/requests/q1/approve",
                             json={"actor": "ceo"})
    assert r.status_code == 200
    assert r.json()["supersession_readable"] is False


def test_off_postgres_the_edge_reader_says_unreadable_rather_than_empty(monkeypatch):
    """None, never {}. An empty map is a measured 'no edges exist' and would
    let the approve path claim a clean check it never made."""
    from app.api.v1 import fund as fundapi
    monkeypatch.setattr(fundapi, "_supersessions", lambda: None)
    assert fundapi._edges_by_target() is None


def test_the_edge_LIST_endpoint_shows_its_rows_and_declares_the_cap(monkeypatch):
    """The display path's half of the truncation repair: a human gets the rows
    AND the word, where the control gets an exception."""
    from app.api.v1 import fund as fundapi
    from app.fund.deskengine import EDGE_QUERY_LIMIT

    class Paged:
        def page(self, include_retracted=False, limit=None):
            return [{"edge_id": "e1"}], True

    monkeypatch.setattr(fundapi, "_supersessions", lambda: Paged())
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    body = TestClient(app).get("/api/v1/fund/desk/supersessions").json()
    assert body["truncated"] is True
    assert body["limit"] == EDGE_QUERY_LIMIT
    assert body["count"] == 1
