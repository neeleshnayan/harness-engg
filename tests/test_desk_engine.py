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
        self.events.append({"type": e.type.value, "payload": e.payload,
                            "actor": e.actor})
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
    errors = desk.validate_routing({"text": "x", "kind": "build"}, 0)
    assert len(errors) == 1
    for field in desk.ROUTING_REQUIRED_FIELDS:
        assert field in errors[0]
    assert "recommendations[0]" in errors[0]


def test_validate_routing_READS_the_required_set_rather_than_repeating_it(monkeypatch):
    """MOVE the value, do not match it (D16/D21 standard).

    Asserting `errors mention next_actor` cannot tell a read from a hardcoded
    list that happens to agree. So the required set is MOVED to something the
    module has never seen, and the refusal must follow it.
    """
    monkeypatch.setattr(desk, "ROUTING_REQUIRED_FIELDS", ("blast_radius",))
    errors = desk.validate_routing(dict(GOOD_REC), 0)
    assert len(errors) == 1 and "blast_radius" in errors[0]
    # And the four real fields are now IRRELEVANT — proof nothing else pins them.
    assert desk.validate_routing({"blast_radius": 1}, 0) == []


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
    errors = desk.validate_routing({**GOOD_REC, "next_actor": "unknown"}, 0)
    assert len(errors) == 1 and "unknown" in errors[0]


@pytest.mark.parametrize("value", ["2026-8-1", "next Monday", "20260801", ""])
def test_a_malformed_due_date_is_refused_not_nulled(value):
    """It used to sort lexicographically against real dates and lose the row."""
    errors = desk.validate_routing({**GOOD_REC, "due_date": value}, 0)
    assert len(errors) == 1 and "due_date" in errors[0]


def test_an_honest_absence_is_accepted_on_both_ranking_keys():
    """Required means the KEY is present, not that a figure was invented.

    The opposite failure is worse than the flood: a seat forced to state a
    dollar figure states one, and the desk then ranks on fabricated money.
    """
    assert desk.validate_routing({**GOOD_REC, "due_date": None,
                                  "money_at_stake": None}, 0) == []


@pytest.mark.parametrize("value", ["free", float("nan"), float("inf"), "12"])
def test_money_at_stake_must_be_a_finite_number_or_null(value):
    assert desk.validate_routing({**GOOD_REC, "money_at_stake": value}, 0)


def test_the_endpoint_refuses_an_unrouted_filing_with_422(monkeypatch):
    ds = FakeDeskStore()
    c = client(monkeypatch, MemStore(), deskstore=ds)
    r = c.post("/api/v1/fund/desk/runs",
               json={"run_id": "r1", "seat": "pm", "task": "t", "output": "o",
                     "recommendations": [{"kind": "build", "text": "x"}]})
    assert r.status_code == 422
    body = r.json()["detail"]
    assert body["routing_rules_version"] == desk.ROUTING_RULES_VERSION
    assert sorted(body["required"]) == sorted(desk.ROUTING_REQUIRED_FIELDS)
    assert ds._runs == [], "a refused filing must not be stored"


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


def test_approving_a_superseded_request_is_refused_before_the_guard_runs(monkeypatch):
    """FIRST, not last: the caller gets the lineage instead of a confirm-echo
    error about a row it should not be approving at all. And the guard is
    proven untouched — it is never reached."""
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
    assert calls == [], "the approval guard must not even be reached"
    assert store.events == []


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


def test_the_ceo_endpoint_reports_which_stores_it_could_read(monkeypatch):
    """A page that could not read the supersession table must render 'lineage
    unknown', never 'no lineage'. The second is a claim."""
    c = client(monkeypatch, MemStore(), deskstore=None, edges=None, intray=None)
    body = c.get("/api/v1/fund/desk/ceo").json()
    assert body["readable"]["recommendations"] is False
    assert body["readable"]["supersessions"] is False
    assert body["readable"]["intray"] is False
