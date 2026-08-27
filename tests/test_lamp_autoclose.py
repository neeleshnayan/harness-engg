"""THE LAMP AUTO-CLOSE, pinned at the two functions the recorder consumes.

History, so the next reader knows why this file is strict: `lamp_on.py`'s
docstring promised auto-close-on-run-record from the day the hook shipped
(2026-08-27 morning), and nothing implemented it — 15 lamps burned stale in
ONE DAY and the CEO caught it on the floor, twice. A docstring is not a
mechanism. These tests pin the mechanism that now exists:
`desk.open_dispatch_task_ids` (what "open" means — the same
enter-on-DESK_DISPATCHED / pop-on-DESK_REQUEST_RESOLVED pair the floor's
`_activity` fold runs) and `desk.plan_lamp_close` (which lamps one run
record retires). The handler in `app/api/v1/fund.py::record_agent_run`
composes exactly these two and appends the same `DeskRequestResolved` the
manual resolve door appends, so floor and recorder cannot disagree.
"""
from app.fund.desk import open_dispatch_task_ids, plan_lamp_close
from app.fund.events import Event, EventType


class MemStore:
    def __init__(self, events=None):
        self._events = list(events or [])

    def stream(self, since_seq=0, limit=100_000):
        return list(self._events)


def _dispatch(seat, task_id):
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_DISPATCHED,
                 payload={"seat": seat, "task_id": task_id,
                          "task": f"work for {seat}",
                          "at": "2026-08-27T09:00:00+00:00"},
                 actor="cto")


def _resolved(task_id):
    return Event(aggregate_id=task_id, aggregate_type="desk_request",
                 type=EventType.DESK_REQUEST_RESOLVED,
                 payload={"request_id": task_id, "resolution": "done",
                          "at": "2026-08-27T12:00:00+00:00"},
                 actor="cto")


class TestOpenDispatchTaskIds:
    def test_an_unresolved_dispatch_is_open(self):
        store = MemStore([_dispatch("builder", "t1")])
        assert open_dispatch_task_ids(store, "builder") == ["t1"]

    def test_a_resolved_dispatch_is_not(self):
        store = MemStore([_dispatch("builder", "t1"), _resolved("t1")])
        assert open_dispatch_task_ids(store, "builder") == []

    def test_seats_do_not_leak_into_each_other(self):
        """The 15-lamp sweep closed OTHER seats' dispatches with the builder's
        two crews still out — the seat filter is what made that safe."""
        store = MemStore([_dispatch("builder", "b1"),
                          _dispatch("validator", "v1")])
        assert open_dispatch_task_ids(store, "builder") == ["b1"]
        assert open_dispatch_task_ids(store, "validator") == ["v1"]

    def test_oldest_first_because_single_close_takes_the_oldest(self):
        store = MemStore([_dispatch("builder", "old"),
                          _dispatch("builder", "new")])
        assert open_dispatch_task_ids(store, "builder") == ["old", "new"]

    def test_a_foreign_resolution_does_not_pop_a_dispatch(self):
        """DeskRequestResolved rows for ordinary desk REQUESTS share the event
        type; one naming a request_id that is not a dispatch must not close
        anything (the D39 phantom class, seen from the other side)."""
        store = MemStore([_dispatch("builder", "t1"), _resolved("other-id")])
        assert open_dispatch_task_ids(store, "builder") == ["t1"]

    def test_an_unreadable_store_raises_rather_than_reading_empty(self):
        """Absence is never zero: a fold that cannot read must not report
        'no dispatches' — the handler catches and says so."""
        class Broken:
            def stream(self, since_seq=0, limit=100_000):
                raise RuntimeError("pg down")
        try:
            open_dispatch_task_ids(Broken(), "builder")
        except RuntimeError:
            pass
        else:  # pragma: no cover - the assertion is the raise itself
            raise AssertionError("unreadable store read as empty")


class TestPlanLampClose:
    def test_single_open_closes_silently(self):
        plan = plan_lamp_close(["t1"], None)
        assert plan["closed"] == ["t1"]
        assert plan["open_remaining"] == []
        assert plan["note"] is None

    def test_two_open_and_no_declaration_closes_NOTHING(self):
        """The B1+jan1 case, live the afternoon this shipped: guessing which
        crew returned would close the wrong lamp."""
        plan = plan_lamp_close(["b1", "jan1"], None)
        assert plan["closed"] == []
        assert set(plan["open_remaining"]) == {"b1", "jan1"}
        assert "closes_task_ids" in plan["note"]

    def test_explicit_declaration_closes_exactly_those(self):
        plan = plan_lamp_close(["b1", "jan1"], ["jan1"])
        assert plan["closed"] == ["jan1"]
        assert plan["open_remaining"] == ["b1"]
        assert plan["note"] is None

    def test_an_unknown_declared_id_is_reported_never_swallowed(self):
        """A typo'd id must not read as a closed lamp."""
        plan = plan_lamp_close(["b1"], ["b1", "typo"])
        assert plan["closed"] == ["b1"]
        assert "typo" in plan["note"]

    def test_zero_open_is_a_quiet_no_op(self):
        plan = plan_lamp_close([], None)
        assert plan == {"closed": [], "open_remaining": [], "note": None}

    def test_declaration_against_zero_open_reports_all_unknown(self):
        plan = plan_lamp_close([], ["ghost"])
        assert plan["closed"] == []
        assert "ghost" in plan["note"]
