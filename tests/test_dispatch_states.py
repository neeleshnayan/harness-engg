"""A dispatch has THREE states, and the middle one is an obligation on the chair.

THE CONSTITUTION, quoting the CEO on desk request 907ecc74: *"no it should nto
close automatically since the cto needs to review the work be satisified and
then log or do what needs to be done and then close it"* — and, in the same
section: *"Build the third state; never build the auto-close."*

THE MEASUREMENT that made this operational rather than cosmetic (live spine,
2026-08-22): the builder's desk read `working` for 21 hours and the analyst's
for 19, both after their dispatches had returned. Two agents in parallel are
permitted as of the same week, so the chair reading that payload could not tell
whether a slot was free. The UI half of this had already shipped and was reading
keys the spine never sent.

Every test below fails if one of the four ways to get this wrong comes back:

  1. auto-closing on a returned run (a completion nobody performed);
  2. rendering a returned dispatch as a working seat (the incident);
  3. matching a run to a dispatch on anything but an exact identifier (an
     obligation invented out of a near-miss);
  4. reporting "we could not look" as "nothing came back".
"""

from __future__ import annotations

from app.fund import desk
from app.fund.events import Event, EventType


class MemStore:
    def __init__(self, events=None):
        self.events = list(events or [])

    def append(self, e):
        self.events.append(e)
        return e

    def stream(self, since_seq=0, limit=100_000):
        return [{"type": e.type.value, "payload": e.payload} for e in self.events]


def _dispatch(seat, task_id, trace_id=None, at="2026-08-22T09:00:00+00:00"):
    p = {"task_id": task_id, "seat": seat, "task": f"{seat} work", "at": at}
    if trace_id:
        p["trace_id"] = trace_id
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_DISPATCHED, payload=p, actor="cto")


def _resolved(task_id, at="2026-08-22T12:00:00+00:00"):
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_REQUEST_RESOLVED,
                 payload={"request_id": task_id, "at": at,
                          "resolution": "docs/thing.md"}, actor="cto")


def _run(run_id, trace_id=None, resolved_at="2026-08-22T10:00:00+00:00"):
    return {"run_id": run_id, "trace_id": trace_id, "seat": "builder",
            "resolved_at": resolved_at}


# ---------------------------------------------------------- the three -------

def test_a_dispatch_with_nothing_back_is_working():
    a = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                       runs=[_run("run-other", "run-other-trace")])
    assert a["builder"]["status"] == "working"
    assert a["builder"]["returned_run_id"] is None
    # The recorder was read and held no matching run: that is a MEASURED
    # negative, not an unknown.
    assert a["builder"]["review_detectable"] is True


def test_a_returned_dispatch_is_awaiting_review_not_working():
    """THE INCIDENT. The seat came back, the run was recorded, and the desk
    still said `working` — for 21 hours, while a parallel slot sat unusable."""
    a = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                       runs=[_run("run-b-1", "run-b-1")])
    assert a["builder"]["status"] == "awaiting_review"
    assert a["builder"]["returned_run_id"] == "run-b-1"
    assert a["builder"]["task_id"] == "t1"
    assert a["builder"]["review_detectable"] is True


def test_a_returned_dispatch_does_NOT_close_itself():
    """The instruction, as an assertion. A run coming back is not a
    resolution: the dispatch stays open, `last_delivered` stays empty, and
    only a recorded resolution moves the seat to idle.

    If this ever fails, the board is reporting a completion nobody performed —
    the unwired-kill-switch pattern wearing a progress bar."""
    back = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                          runs=[_run("run-b-1", "run-b-1")])["builder"]
    assert back["status"] != "idle"
    assert back["status"] != "closed"
    assert back["last_delivered"] is None

    closed = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1"), _resolved("t1")]),
        runs=[_run("run-b-1", "run-b-1")])["builder"]
    assert closed["status"] == "idle"
    assert closed["last_delivered"]["artifact"] == "docs/thing.md"
    assert closed["review_detectable"] is None      # nothing left to detect


def test_an_idle_seat_is_idle_and_carries_no_dispatch():
    a = desk._activity(MemStore([]), runs=[_run("run-b-1", "run-b-1")])
    assert a["pm"]["status"] == "idle"
    assert a["pm"]["task_id"] is None
    assert a["pm"]["returned_run_id"] is None
    assert a["pm"]["review_detectable"] is None


# ------------------------------------------------------- exact matching -----

def test_matching_is_on_exact_identifiers_only():
    """Nothing is matched on seat plus a timestamp. A near-miss there would
    mark an unrelated run as this dispatch's return and invent an obligation
    the chair does not have — which is worse than the gap it would close."""
    # Same seat, a run resolved AFTER the dispatch, no shared identifier.
    a = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-2")]),
        runs=[_run("run-b-1", "run-b-1", resolved_at="2026-08-22T11:00:00+00:00")])
    assert a["builder"]["status"] == "working"
    assert a["builder"]["returned_run_id"] is None


def test_a_run_id_or_a_task_id_matches_too():
    """Both older conventions live in the log: 8 of 24 dispatches carry a
    task_id that IS the run's trace, and a run may be found by its own id."""
    by_task = desk._activity(MemStore([_dispatch("builder", "run-b-1")]),
                             runs=[_run("run-b-1", "run-b-1")])
    assert by_task["builder"]["status"] == "awaiting_review"

    by_run_id = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1")]),
        runs=[_run("run-b-1", trace_id=None)])
    assert by_run_id["builder"]["status"] == "awaiting_review"


def test_a_dispatch_with_no_identifier_reports_undetectable_not_working():
    """4 of 24 dispatches in the live log carry no trace_id at all. They can
    never be matched, so `working` is an honest FLOOR — and the payload has to
    say so, or "we never looked" renders as "nothing came back"."""
    a = desk._activity(MemStore([_dispatch("builder", None, None)]),
                       runs=[_run("run-b-1", "run-b-1")])
    # No task_id and no trace: the fold cannot even open the dispatch.
    assert a["builder"]["status"] == "idle"

    # With a task_id but no trace, the dispatch IS open and IS matchable.
    b = desk._activity(MemStore([_dispatch("builder", "t1", None)]),
                       runs=[_run("run-b-1", "run-b-1")])
    assert b["builder"]["status"] == "working"
    assert b["builder"]["review_detectable"] is True


def test_an_unreadable_recorder_is_not_a_quiet_bench():
    """`runs=None` means the flight recorder could not be read. Every open
    dispatch stays WORKING and every one says detection was unavailable —
    "still running" and "we cannot see" must not render as the same word."""
    a = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                       runs=None)
    assert a["builder"]["status"] == "working"
    assert a["builder"]["review_detectable"] is False


def test_an_empty_but_readable_recorder_is_a_measured_negative():
    """Read and empty is a different fact from unreadable: with zero runs in
    existence, "nothing came back" is measured, not assumed."""
    a = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                       runs=[])
    assert a["builder"]["status"] == "working"
    assert a["builder"]["review_detectable"] is True


def test_a_dispatch_older_than_a_TRUNCATED_run_window_cannot_be_judged():
    """`runs` is the newest N by resolved_at. When that list is FULL it may be
    truncated, so a dispatch made before its oldest row may have a return that
    resolved outside it — a miss proves nothing, and claiming otherwise would
    be a confident answer built on a truncated list."""
    old = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1",
                            at="2026-08-01T09:00:00+00:00")]),
        runs=[_run("run-x", "run-x", resolved_at="2026-08-22T10:00:00+00:00")],
        runs_limit=1)
    assert old["builder"]["status"] == "working"
    assert old["builder"]["review_detectable"] is False

    recent = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1",
                            at="2026-08-22T09:00:00+00:00")]),
        runs=[_run("run-x", "run-x", resolved_at="2026-08-22T08:00:00+00:00")],
        runs_limit=1)
    assert recent["builder"]["review_detectable"] is True


def test_a_COMPLETE_run_list_has_no_outside_to_fall_into():
    """The rule must be exact, not merely careful. A list shorter than the cap
    it was fetched under IS the whole table — so an old dispatch with no match
    in it is a measured negative, and reporting UNKNOWN there would be an
    honest-looking answer to a question we can actually answer."""
    a = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1",
                            at="2026-08-01T09:00:00+00:00")]),
        runs=[_run("run-x", "run-x", resolved_at="2026-08-22T10:00:00+00:00")],
        runs_limit=25)
    assert a["builder"]["status"] == "working"
    assert a["builder"]["review_detectable"] is True


def test_timestamps_are_compared_as_instants_not_strings():
    """The log writes `+00:00` and hand-written fixtures write `Z`.
    Lexicographically "2026-08-22T09:00:00Z" > "2026-08-22T09:00:00+00:00",
    which is the wrong answer for two identical instants."""
    a = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1",
                            at="2026-08-22T09:00:00Z")]),
        runs=[_run("run-x", "run-x", resolved_at="2026-08-22T09:00:00+00:00")],
        runs_limit=1)
    assert a["builder"]["review_detectable"] is True
    # An unreadable timestamp cannot be compared, so it cannot report a clean
    # look either.
    b = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1", at="yesterday-ish")]),
        runs=[_run("run-x", "run-x", resolved_at="2026-08-22T09:00:00+00:00")],
        runs_limit=1)
    assert b["builder"]["review_detectable"] is False


def test_a_positive_match_proves_detection_regardless_of_the_window():
    """Finding the run IS the proof. A window rule that could turn a matched
    return into `review_detectable: false` would contradict the payload it
    sits beside."""
    a = desk._activity(
        MemStore([_dispatch("builder", "t1", "run-b-1",
                            at="2026-08-01T09:00:00+00:00")]),
        runs=[_run("run-b-1", "run-b-1",
                   resolved_at="2026-08-22T10:00:00+00:00")],
        runs_limit=1)
    assert a["builder"]["status"] == "awaiting_review"
    assert a["builder"]["review_detectable"] is True


# ---------------------------------------------------------- telemetry -------

def test_a_returned_seat_is_not_running_now():
    """The COO watched `seat_telemetry` report `running_now: true` for two
    seats that had both returned and been recorded. It fired live, twice,
    during its own triage."""
    act = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                         runs=[_run("run-b-1", "run-b-1")])
    t = desk.seat_telemetry([], act, "2026-08-22")["seats"]["builder"]
    assert t["running_now"] is False
    assert t["awaiting_review"] is True
    assert t["returned_run_id"] == "run-b-1"
    # The dispatch is still open, so its task and clock survive the return.
    assert t["running_task"] == "builder work"
    assert t["running_since"] == "2026-08-22T09:00:00+00:00"


def test_a_working_seat_is_running_and_not_awaiting():
    act = desk._activity(MemStore([_dispatch("builder", "t1", "run-b-1")]),
                         runs=[])
    t = desk.seat_telemetry([], act, "2026-08-22")["seats"]["builder"]
    assert t["running_now"] is True
    assert t["awaiting_review"] is False
    assert t["returned_run_id"] is None


def test_an_idle_seat_is_neither():
    t = desk.seat_telemetry([], desk._activity(MemStore([]), runs=[]),
                            "2026-08-22")["seats"]["pm"]
    assert t["running_now"] is False
    assert t["awaiting_review"] is False
    assert t["running_task"] is None


# --------------------------------------------------------- through view -----

def test_the_view_wires_the_recorder_into_the_state_and_degrades_honestly():
    """The whole point of the plumbing: `_activity` must be called AFTER the
    runs are loaded, and with None when they could not be."""
    dispatched = [_dispatch("builder", "t1", "run-b-1")]

    class Store:
        def runs(self, limit=25):
            return [{**_run("run-b-1", "run-b-1"), "recommendations": [],
                     "task": "t", "artifact_path": None, "verdict": None}]

        def open_recommendations(self):
            return []

    v = desk.view(MemStore(dispatched), Store())
    row = next(r for r in v["roster"] if r["agent"] == "builder")
    assert row["activity"]["status"] == "awaiting_review"
    assert row["activity"]["returned_run_id"] == "run-b-1"
    assert v["seat_telemetry"]["seats"]["builder"]["running_now"] is False

    class BrokenStore(Store):
        def runs(self, limit=25):
            raise RuntimeError("recorder down")

    v2 = desk.view(MemStore(dispatched), BrokenStore())
    row2 = next(r for r in v2["roster"] if r["agent"] == "builder")
    assert row2["activity"]["status"] == "working"
    assert row2["activity"]["review_detectable"] is False


def test_no_store_at_all_still_renders_the_bench():
    """The desk must not need a flight recorder to say who was dispatched."""
    v = desk.view(MemStore([_dispatch("builder", "t1", "run-b-1")]))
    row = next(r for r in v["roster"] if r["agent"] == "builder")
    assert row["activity"]["status"] == "working"
    assert row["activity"]["review_detectable"] is False
