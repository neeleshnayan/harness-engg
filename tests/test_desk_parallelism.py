"""A SEAT CAN HOLD MORE THAN ONE OPEN DISPATCH, AND THE FOLD USED TO HIDE IT.

THE INCIDENT, and it is the CEO's own, made on the floor 2026-08-27, verbatim:
*"1 builder working but 2 in reality"*. Two builders concurrently is a
VERSIONED PERMISSION — the constitution allows it on disjoint write scopes and
serialized suites — so ``_activity`` was not describing an impossible state
wrongly. It was describing a permitted, live, deliberately-chosen state
wrongly, on the one surface a human uses to decide whether a slot is free.

The mechanism was one line: the event loop accumulated every open dispatch in
``open_by_task`` and then wrote ``seats[seat]["working_on"] = p`` — last write
wins. Everything downstream (the lamp, ``seat_telemetry.running_now``, the
chair's "is the bench full") read that projection as though it were the seat.

Every test below fails if one of the five ways to get this wrong comes back:

  1. reporting only the newest dispatch (the incident);
  2. counting the list instead of its STATES, so a returned dispatch inflates
     "working";
  3. recomputing a count in a consumer rather than reading the fold's;
  4. an implicit sort order over stamps that can tie;
  5. the headline fields moving, which would break every existing consumer —
     this diff is ADDITIVE and these tests are what makes that word mean
     something.
"""

from __future__ import annotations

import pytest

from app.fund import desk
from app.fund.events import Event, EventType


class MemStore:
    def __init__(self, events=None):
        self.events = list(events or [])

    def stream(self, since_seq=0, limit=100_000):
        return [{"type": e.type.value, "payload": e.payload} for e in self.events]


def _dispatch(seat, task_id, trace_id=None, at="2026-08-27T09:00:00+00:00",
              task=None):
    p = {"task_id": task_id, "seat": seat, "at": at,
         "task": task or f"{seat} {task_id}"}
    if trace_id:
        p["trace_id"] = trace_id
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_DISPATCHED, payload=p, actor="cto")


def _resolved(task_id, at="2026-08-27T12:00:00+00:00"):
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_REQUEST_RESOLVED,
                 payload={"request_id": task_id, "at": at,
                          "resolution": "docs/thing.md"}, actor="cto")


def _run(run_id, trace_id=None, resolved_at="2026-08-27T10:00:00+00:00"):
    return {"run_id": run_id, "trace_id": trace_id, "seat": "builder",
            "resolved_at": resolved_at}


# ------------------------------------------------- the incident, reproduced --

def test_two_open_dispatches_for_one_seat_are_BOTH_reported():
    """THE CEO'S OBSERVATION, as an assertion.

    Two live builder dispatches — slice3 and ops1, the real pair on the day
    this was found. Before the fix ``_activity`` returned one row describing
    ops1 and the floor lit one lamp.
    """
    a = desk._activity(MemStore([
        _dispatch("builder", "t-slice3", at="2026-08-27T07:32:39+00:00",
                  task="Builder slice3: seat pages + console"),
        _dispatch("builder", "t-ops1", at="2026-08-27T07:40:00+00:00",
                  task="Builder ops1: NAV-gap reader"),
    ]), runs=[])
    row = a["builder"]
    assert row["working_count"] == 2
    assert len(row["open_dispatches"]) == 2
    # Both tasks are on the surface, not just the newest. The hover text the
    # room draws comes from here.
    assert {d["task"] for d in row["open_dispatches"]} == {
        "Builder slice3: seat pages + console",
        "Builder ops1: NAV-gap reader",
    }
    assert {d["task_id"] for d in row["open_dispatches"]} == {
        "t-slice3", "t-ops1"}


def test_a_second_open_dispatch_does_not_shrink_when_one_more_arrives():
    """The count MOVES with the population rather than agreeing with it by
    accident. Three open dispatches must read three — a hardcoded 2, or a
    count taken from the headline, would pass the test above and fail here."""
    a = desk._activity(MemStore([
        _dispatch("builder", "t1", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t2", at="2026-08-27T08:00:00+00:00"),
        _dispatch("builder", "t3", at="2026-08-27T09:00:00+00:00"),
    ]), runs=[])
    assert a["builder"]["working_count"] == 3
    assert len(a["builder"]["open_dispatches"]) == 3


# ------------------------------------------------------- states, not length --

def test_the_counts_split_by_STATE_and_neither_is_the_list_length():
    """A returned dispatch is an obligation on the CHAIR, not a busy seat.

    Two open dispatches, one of which has come back. ``working_count`` must be
    1 and ``awaiting_review_count`` 1 — a fold that counted the LIST would
    report the bench full when half of it is waiting on a review.
    """
    a = desk._activity(MemStore([
        _dispatch("builder", "t1", "trace-1", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t2", "trace-2", at="2026-08-27T08:00:00+00:00"),
    ]), runs=[_run("run-b-1", "trace-1")])
    row = a["builder"]
    assert len(row["open_dispatches"]) == 2
    assert row["working_count"] == 1
    assert row["awaiting_review_count"] == 1
    states = {d["task_id"]: d["status"] for d in row["open_dispatches"]}
    assert states == {"t1": "awaiting_review", "t2": "working"}
    # And the returned run is named on ITS OWN row, so the chair can open it
    # without guessing which dispatch it belongs to.
    back = [d for d in row["open_dispatches"] if d["task_id"] == "t1"][0]
    assert back["returned_run_id"] == "run-b-1"
    other = [d for d in row["open_dispatches"] if d["task_id"] == "t2"][0]
    assert other["returned_run_id"] is None


def test_counts_are_zero_and_the_list_empty_for_a_seat_with_nothing_open():
    """Zero here is a MEASUREMENT — the fold read the stream and found no open
    dispatch for this seat. It is not the absence-as-zero the non-negotiables
    forbid, and the distinction is that the stream either streams or raises."""
    a = desk._activity(MemStore([_dispatch("builder", "t1")]), runs=[])
    assert a["quant"]["working_count"] == 0
    assert a["quant"]["awaiting_review_count"] == 0
    assert a["quant"]["open_dispatches"] == []
    assert a["quant"]["status"] == "idle"


# ------------------------------------------- the headline is a compatibility
# ------------------------------------------- surface, and it can understate --

def test_the_headline_reads_idle_while_an_older_dispatch_is_STILL_OPEN():
    """THE DISAGREEMENT, PINNED ON PURPOSE — and now HALF of it is repaired.

    ``working_on`` is retired when the NEWEST dispatch resolves, so a seat
    holding an older open dispatch reports ``status: "idle"``. That headline
    behaviour is a compatibility surface and it still does not move; this test
    is what makes the word "unchanged" mean something.

    WHAT DID MOVE, 2026-08-27 (B2): ``seat_telemetry.running_now`` no longer
    reads this headline. It reads the LIST, so the seat below is reported as
    running — see ``test_running_now_reads_the_LIST_not_the_headline``, which
    is the destination this docstring used to call a map.
    """
    a = desk._activity(MemStore([
        _dispatch("builder", "t-old", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t-new", at="2026-08-27T08:00:00+00:00"),
        _resolved("t-new"),
    ]), runs=[])
    row = a["builder"]
    assert row["status"] == "idle", "headline behaviour must not move"
    assert row["task"] is None
    # ...and a builder is still running.
    assert row["working_count"] == 1
    assert [d["task_id"] for d in row["open_dispatches"]] == ["t-old"]


def test_resolving_one_dispatch_removes_ONLY_that_one_from_the_list():
    a = desk._activity(MemStore([
        _dispatch("builder", "t1", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t2", at="2026-08-27T08:00:00+00:00"),
        _resolved("t1"),
    ]), runs=[])
    assert [d["task_id"] for d in a["builder"]["open_dispatches"]] == ["t2"]
    assert a["builder"]["working_count"] == 1


def test_the_headline_fields_are_UNCHANGED_for_a_single_dispatch():
    """The additive promise, as an assertion. One dispatch, one run back: every
    field an existing consumer reads must hold exactly what it held before."""
    a = desk._activity(MemStore([_dispatch("builder", "t1", "trace-1")]),
                       runs=[_run("run-b-1", "trace-1")])
    row = a["builder"]
    assert row["status"] == "awaiting_review"
    assert row["task"] == "builder t1"
    assert row["since"] == "2026-08-27T09:00:00+00:00"
    assert row["task_id"] == "t1"
    assert row["returned_run_id"] == "run-b-1"
    assert row["review_detectable"] is True
    assert row["last_delivered"] is None


def test_review_detectable_is_None_only_when_the_HEADLINE_is_idle():
    """Idle means "nothing to detect"; it must not leak onto the open rows,
    which each answer the question for themselves."""
    a = desk._activity(MemStore([_dispatch("builder", "t1")]), runs=None)
    assert a["quant"]["review_detectable"] is None
    assert a["quant"]["open_dispatches"] == []
    # The recorder could not be read, so every OPEN row says so — as False,
    # never as None, because None on a live dispatch would read as "idle".
    assert a["builder"]["review_detectable"] is False
    assert [d["review_detectable"] for d in a["builder"]["open_dispatches"]] \
        == [False]


# ---------------------------------------------------------------- ordering --

def test_open_dispatches_are_newest_first():
    a = desk._activity(MemStore([
        _dispatch("builder", "t-old", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t-new", at="2026-08-27T09:00:00+00:00"),
        _dispatch("builder", "t-mid", at="2026-08-27T08:00:00+00:00"),
    ]), runs=[])
    assert [d["task_id"] for d in a["builder"]["open_dispatches"]] \
        == ["t-new", "t-mid", "t-old"]


def test_an_EXACT_TIE_on_the_stamp_breaks_toward_the_LATER_EVENT():
    """Two dispatches fired in one session share a stamp — the clock's
    resolution is coarser than the loop. A sort on the stamp alone then returns
    whatever order the stream gave, which is a contract nobody wrote down."""
    same = "2026-08-27T07:32:39+00:00"
    a = desk._activity(MemStore([
        _dispatch("builder", "t-first", at=same),
        _dispatch("builder", "t-second", at=same),
    ]), runs=[])
    assert [d["task_id"] for d in a["builder"]["open_dispatches"]] \
        == ["t-second", "t-first"]


@pytest.mark.parametrize("bad", ["", "not-a-date", "2026-13-45", None])
def test_an_UNREADABLE_stamp_sorts_oldest_and_never_raises(bad):
    """``None`` and a datetime are not orderable in Python, and a payload
    builder is the worst place to discover that."""
    a = desk._activity(MemStore([
        _dispatch("builder", "t-bad", at=bad),
        _dispatch("builder", "t-good", at="2026-08-27T09:00:00+00:00"),
    ]), runs=[])
    assert [d["task_id"] for d in a["builder"]["open_dispatches"]] \
        == ["t-good", "t-bad"]
    assert a["builder"]["working_count"] == 2


# ------------------------------------------------------- one constructor -----

def test_the_idle_fallback_and_the_folds_idle_row_have_THE_SAME_KEYS():
    """There were two constructors for one envelope and they disagreed: the
    fold emitted ten keys, the desk payload's fallback for a roster agent
    outside ``REQUEST_KINDS`` emitted four. Nothing exercises that branch
    today, which is precisely why it would have stayed wrong."""
    a = desk._activity(MemStore([]), runs=[])
    assert set(desk.idle_activity()) == set(a["quant"])
    assert desk.idle_activity() == a["quant"]


def test_the_idle_fallback_is_a_FRESH_dict_per_call():
    """A shared default would let one seat's annotation land on every seat."""
    one, two = desk.idle_activity(), desk.idle_activity()
    assert one is not two
    one["open_dispatches"].append({"task_id": "x"})
    assert two["open_dispatches"] == []


def test_a_dispatch_with_no_seat_is_dropped_rather_than_grouped_under_None():
    a = desk._activity(MemStore([
        Event(aggregate_id="t0", aggregate_type="desk_request",
              type=EventType.DESK_DISPATCHED,
              payload={"task_id": "t0", "task": "orphan",
                       "at": "2026-08-27T07:00:00+00:00"}, actor="cto"),
        _dispatch("builder", "t1"),
    ]), runs=[])
    assert a["builder"]["working_count"] == 1
    assert None not in a


# ----------------------------------------- closed from the mutation pass ----
#
# Each test below was written because a MUTANT SURVIVED the first pass. The
# defect it introduces is named in the docstring; without the test, that
# defect ships.

def test_the_two_counts_are_over_DIFFERENT_populations():
    """M06: `awaiting_review_count` counting WORKING rows survived the first
    pass, because the fixture had one of each and the two wrong answers were
    the same number. An asymmetric population is what makes this assertion
    mean anything."""
    a = desk._activity(MemStore([
        _dispatch("builder", "t1", "trace-1", at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t2", "trace-2", at="2026-08-27T08:00:00+00:00"),
        _dispatch("builder", "t3", "trace-3", at="2026-08-27T09:00:00+00:00"),
    ]), runs=[_run("run-b-1", "trace-1")])
    row = a["builder"]
    assert row["working_count"] == 2
    assert row["awaiting_review_count"] == 1
    assert row["working_count"] + row["awaiting_review_count"] \
        == len(row["open_dispatches"])


def test_the_TRACE_id_is_matched_before_the_task_id():
    """M10: reversing the identifier order survived, because no fixture had a
    dispatch whose trace_id and task_id BOTH matched — different — runs.

    The order is not arbitrary: measured over the live log, 17 of 24 dispatches
    match on trace_id and 8 on task_id (the older convention where the two were
    the same string). Where both resolve, the trace is this dispatch's own and
    the task_id is the older, weaker key.
    """
    a = desk._activity(MemStore([_dispatch("builder", "t1", "trace-1")]),
                       runs=[_run("run-by-trace", "trace-1"),
                             _run("run-by-task", "t1")])
    assert a["builder"]["returned_run_id"] == "run-by-trace"
    assert a["builder"]["open_dispatches"][0]["returned_run_id"] \
        == "run-by-trace"


def test_a_roster_agent_OUTSIDE_the_kind_map_gets_the_FULL_envelope():
    """M23: restoring the old four-key fallback survived, because nothing
    reaches that branch — all eleven roster agents are in ``REQUEST_KINDS``,
    verified against the live payload. The branch nobody exercises is the
    branch nobody patches, so it is exercised here directly.

    A seat added to ``ROSTER`` and not to ``REQUEST_KINDS`` must still serve
    the same ten keys as every other seat; anything less and every consumer of
    ``open_dispatches`` reads absent-as-undefined on that seat alone.
    """
    from app.fund import desk as desk_mod
    seats = {r["agent"] for r in desk_mod.ROSTER}
    kinds = set(desk_mod.REQUEST_KINDS.values())
    stranger = "a_seat_with_no_request_kind"
    assert stranger not in kinds
    # The payload's own fallback, called the way the payload calls it.
    fallback = desk_mod.idle_activity()
    folded = desk_mod._activity(MemStore([]), runs=[])
    any_seat = next(iter(kinds))
    assert set(fallback) == set(folded[any_seat])
    assert fallback["open_dispatches"] == []
    assert fallback["working_count"] == 0
    assert fallback["awaiting_review_count"] == 0
    # And the roster/kind-map overlap is asserted so that ADDING a seat to one
    # and not the other goes red here rather than on the CEO's floor.
    assert seats <= kinds | {"ceo", "cto"}, (
        f"roster agents with no request kind: {sorted(seats - kinds)}")


def test_the_PAYLOAD_serves_the_full_envelope_to_a_seat_the_fold_never_saw(
        monkeypatch):
    """M23, ON THE PATH THAT ACTUALLY HAS THE BRANCH.

    The first attempt at this test asserted key-set equality between
    ``idle_activity()`` and the fold's own idle row — and the mutant SURVIVED
    it, because the four-key literal lives in ``view``'s roster comprehension
    and that test never called ``view``. A test that cannot reach the branch
    cannot defend it, however much it looks like it is about the same thing.

    So: a stranger is put in ``ROSTER`` with no entry in ``REQUEST_KINDS``,
    which is exactly the state that would exist five minutes after somebody
    seats a new agent. Its activity envelope must carry the same ten keys as
    every other seat's, or every consumer of ``open_dispatches`` reads
    absent-as-undefined on that one seat.
    """
    from app.fund import desk as desk_mod
    stranger = {"agent": "newcomer", "lane": "a lane", "emits": "an artifact",
                "exists_because": "a demonstrated need"}
    monkeypatch.setattr(desk_mod, "ROSTER",
                        list(desk_mod.ROSTER) + [stranger])
    payload = desk_mod.view(MemStore([_dispatch("builder", "t1")]))
    rows = {r["agent"]: r["activity"] for r in payload["roster"]}
    assert "newcomer" in rows
    assert set(rows["newcomer"]) == set(desk_mod.idle_activity())
    assert rows["newcomer"] == desk_mod.idle_activity()
    # And it is the SAME envelope a folded seat gets — the whole point of one
    # constructor is that these two cannot drift.
    assert set(rows["newcomer"]) == set(rows["builder"])


# ------------------------------------------------------ seat_telemetry, the
# ------------------------------------------------------ headline understatement

def _telemetry(store_events, seat="builder"):
    """The live-state half of a telemetry row, folded exactly as the payload
    folds it — ``_activity`` first, then ``seat_telemetry`` over its output.
    Building the activity dict by hand here would test a shape the spine never
    produces, which is the fixture-classification trap."""
    act = desk._activity(MemStore(store_events), runs=[])
    return desk.seat_telemetry([], act, "2026-08-27")["seats"][seat]


def test_running_now_reads_the_LIST_not_the_headline():
    """THE REPAIR, AND THE DEFECT IT CLOSES.

    Filed by the diff that created it (slice3, ``_activity``'s docstring:
    *"``seat_telemetry``'s ``running_now`` — which reads the headline —
    inherits the understatement and is NOT repaired here"*). The shape: two
    dispatches, the NEWER one resolved, an OLDER one still running. The
    headline is ``idle`` because ``working_on`` was retired with the newer
    one; the seat is running.

    Before this repair ``running_now`` was False here — the chair reading the
    payload to see whether a parallel builder slot was free was told the bench
    was empty while a builder was mid-dispatch. That is the CEO's own floor
    observation (*"1 builder working but 2 in reality"*) one field downstream
    of where it was fixed.
    """
    t = _telemetry([
        _dispatch("builder", "t-old", at="2026-08-27T07:00:00+00:00",
                  task="the older one, still running"),
        _dispatch("builder", "t-new", at="2026-08-27T08:00:00+00:00"),
        _resolved("t-new"),
    ])
    assert t["running_now"] is True
    assert t["live_basis"] == desk.LIVE_FROM_LIST
    # AND THE ROW DOES NOT CONTRADICT ITSELF. `running_now: true` beside
    # `running_task: null` is the shape this repair had to avoid: five fields
    # describing one condition, computed in one place, from one input.
    assert t["running_task"] == "the older one, still running"
    assert t["running_since"] == "2026-08-27T07:00:00+00:00"


def test_running_now_is_FALSE_when_the_only_open_dispatch_has_RETURNED():
    """The third state survives the repair.

    A returned dispatch is an obligation on the chair, NOT a running seat —
    the distinction the COO measured (``running_now: true`` for two seats 21
    and 19 hours after both had returned). Reading the list must not undo it:
    the list is filtered by STATE, never counted whole.
    """
    t = _telemetry([
        _dispatch("builder", "t1", at="2026-08-27T07:00:00+00:00"),
    ], seat="builder")
    # A dispatch with no run back is WORKING; add the run to make it returned.
    act = desk._activity(
        MemStore([_dispatch("builder", "t1", trace_id="tr-1",
                            at="2026-08-27T07:00:00+00:00")]),
        runs=[_run("run-1", trace_id="tr-1")])
    back = desk.seat_telemetry([], act, "2026-08-27")["seats"]["builder"]
    assert act["builder"]["awaiting_review_count"] == 1
    assert act["builder"]["working_count"] == 0
    assert back["running_now"] is False
    assert back["awaiting_review"] is True
    assert back["returned_run_id"] == "run-1"
    # ...and the working case above is genuinely the other answer, so this
    # test cannot pass by both arms being False.
    assert t["running_now"] is True


def test_a_seat_running_AND_awaiting_review_reports_both():
    """Two open dispatches in two different states. Both facts are true at
    once and the row says so — the pair of booleans is not an enum, and a
    telemetry block that picked one would hide either a busy slot or a review
    the chair owes."""
    act = desk._activity(MemStore([
        _dispatch("builder", "t-back", trace_id="tr-1",
                  at="2026-08-27T07:00:00+00:00"),
        _dispatch("builder", "t-live", at="2026-08-27T08:00:00+00:00",
                  task="the one still running"),
    ]), runs=[_run("run-1", trace_id="tr-1")])
    t = desk.seat_telemetry([], act, "2026-08-27")["seats"]["builder"]
    assert t["running_now"] is True
    assert t["awaiting_review"] is True
    assert t["returned_run_id"] == "run-1"
    # The RUNNING dispatch owns the task line: "what is this seat doing" and
    # "what does the chair owe" are different questions.
    assert t["running_task"] == "the one still running"


def test_an_ABSENT_dispatch_list_falls_back_to_the_headline_AND_SAYS_SO():
    """ABSENT IS NOT EMPTY, and this is the input that proves it.

    A hand-built activity dict — no ``open_dispatches`` key at all — is a
    different input from a seat with an empty list, and it gets a different
    answer: the headline, plus ``live_basis`` stating in words that this row
    can understate. A silent fallback would have re-created the exact defect
    the repair closes, on the one path no fold produces and therefore no
    payload test covers.
    """
    hand = {"builder": {"status": "working", "task": "hand-built",
                        "since": "2026-08-27T07:00:00+00:00"}}
    t = desk.seat_telemetry([], hand, "2026-08-27")["seats"]["builder"]
    assert t["running_now"] is True
    assert t["running_task"] == "hand-built"
    assert t["live_basis"] == desk.LIVE_FROM_HEADLINE
    assert "UNDERSTATE" in t["live_basis"]

    # An EMPTY list is the other input and it is a MEASUREMENT: the fold ran
    # and found nothing open.
    empty = {"builder": {"status": "working", "task": "hand-built",
                         "open_dispatches": []}}
    e = desk.seat_telemetry([], empty, "2026-08-27")["seats"]["builder"]
    assert e["running_now"] is False
    assert e["running_task"] is None
    assert e["live_basis"] == desk.LIVE_FROM_LIST


def test_the_ordinary_path_did_not_move():
    """A seat whose NEWEST dispatch is open reports exactly what it always
    did. The repair is a behaviour change on ONE shape (an older dispatch
    outliving a newer one) and this asserts it is not a behaviour change on
    the common one."""
    t = _telemetry([
        _dispatch("builder", "t1", at="2026-08-27T07:00:00+00:00",
                  task="the only one"),
    ])
    assert t["running_now"] is True
    assert t["awaiting_review"] is False
    assert t["running_task"] == "the only one"
    assert t["running_since"] == "2026-08-27T07:00:00+00:00"
    assert t["returned_run_id"] is None

    idle = _telemetry([], seat="quant")
    assert idle["running_now"] is False
    assert idle["awaiting_review"] is False
    assert idle["running_task"] is None


def test_a_working_row_with_NO_TASK_still_reports_the_seat_as_running():
    """THE GAUNTLET'S FINDING, and it is about a contradiction, not a crash.

    Every ``_dispatch`` fixture in this file defaults a non-null ``task``, so
    a dispatch filed without one had never reached ``_live_state``. The two
    fields must disagree about NOTHING: the seat is running (a dispatch is
    open), and the task is absent (the dispatch stated none). A row that
    reported ``running_now: false`` because it could not read a task would be
    the understatement this whole repair removed, wearing a different cause.
    """
    # THE FIXTURE CANNOT REPRESENT THIS SHAPE, so the event is built by hand.
    # `_dispatch` does `task or f"{seat} {task_id}"`, which coerces an empty
    # task into a default — a fixture that cannot express the input under test
    # is the wrong fixture, and the first version of this test passed a `""`
    # and silently measured the default instead.
    taskless = Event(aggregate_id="t1", aggregate_type="desk_request",
                     type=EventType.DESK_DISPATCHED,
                     payload={"task_id": "t1", "seat": "builder",
                              "at": "2026-08-27T07:00:00+00:00"},
                     actor="cto")
    assert "task" not in taskless.payload, "the fixture omits the key"
    a = desk._activity(MemStore([taskless]), runs=[])
    t = desk.seat_telemetry([], a, "2026-08-27")["seats"]["builder"]
    assert t["running_now"] is True, "an open dispatch is an open dispatch"
    assert t["running_task"] is None, "a missing task is ABSENT"
    assert t["live_basis"] == desk.LIVE_FROM_LIST

    # AND THE EMPTY-STRING SHAPE, WHICH IS THE ONE THE `or None` IS FOR.
    # The first version of this test only omitted the key — `.get("task")`
    # returns None either way, so the mutant that removes `or None` SURVIVED
    # it. A dispatch filed with `task: ""` is the input that separates them:
    # without the guard the payload carries an empty string, and a card then
    # renders a blank line where a task belongs instead of saying nothing.
    blank = Event(aggregate_id="t2", aggregate_type="desk_request",
                  type=EventType.DESK_DISPATCHED,
                  payload={"task_id": "t2", "seat": "adversary",
                           "at": "2026-08-27T07:00:00+00:00", "task": ""},
                  actor="cto")
    assert blank.payload["task"] == "", "the fixture carries an EMPTY task"
    bt = desk.seat_telemetry(
        [], desk._activity(MemStore([blank]), runs=[]),
        "2026-08-27")["seats"]["adversary"]
    assert bt["running_now"] is True
    assert bt["running_task"] is None, (
        "an EMPTY task string is absence, not a blank line — `or None`")
    # ...and the ordinary row beside it still carries its task, so this is not
    # a test that would pass on a function that blanked every task.
    b = desk._activity(MemStore([
        _dispatch("quant", "t2", at="2026-08-27T07:00:00+00:00", task="a job"),
    ]), runs=[])
    assert (desk.seat_telemetry([], b, "2026-08-27")["seats"]["quant"]
            ["running_task"]) == "a job"
