"""The desk must render the firm honestly — kills as kills, absences as absences.

Two lies this surface could tell, both pinned here: an unreviewed artifact shown
as surviving (absence scored as a value), and a request that evaporates on
restart (a toast wearing the costume of a commitment).
"""

from __future__ import annotations

from app.fund import desk
from app.fund.events import Event, EventType


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append(e)
        return e

    def stream(self, since_seq=0, limit=100_000):
        return [{"type": e.type.value, "payload": e.payload} for e in self.events]


def test_the_view_reads_real_artifacts_and_pairs_them_with_verdicts():
    """Runs against the actual docs/ tree — the files ARE the state."""
    v = desk.view(MemStore())
    assert len(v["roster"]) == 9
    assert {r["agent"] for r in v["roster"]} == {"mechanism", "analyst", "pm",
                                                 "quant", "builder", "adversary",
                                                 "validator", "riskofficer",
                                                 "coo"}
    # Every seat carries its justification - a role with no measured reason is
    # ceremony, and the roster rule says it should not exist.
    assert all(r["exists_because"].strip() for r in v["roster"])
    # Both known artifacts are on the desk and both were killed with a review
    # on file. If this fails after adding artifacts, the pairing broke — check
    # the "Artifact attacked:" line in the review.
    by_path = {a["path"]: a for a in v["artifacts"]}
    vrp = by_path.get("docs/proposals/VRP_XYLD_2026-08-19.md")
    assert vrp is not None
    assert vrp["status"] == "killed"
    assert vrp["review"] and vrp["review"]["verdict"] == "KILL"
    assert v["kills"] >= 2


def test_an_unreviewed_artifact_is_not_shown_as_surviving(tmp_path, monkeypatch):
    monkeypatch.setattr(desk, "DOCS", tmp_path)
    (tmp_path / "proposals").mkdir()
    (tmp_path / "proposals" / "NEW_IDEA_2026-08-20.md").write_text(
        "# A new idea\n\nno review yet\n", encoding="utf-8")
    v = desk.view(MemStore())
    a = v["artifacts"][0]
    assert a["status"] == "under_review"
    assert "unreviewed is not the same as surviving" in a["note"]
    assert v["kills"] == 0


def test_requests_fold_from_the_event_log_and_survive_resolution():
    store = MemStore()
    store.append(Event(aggregate_id="r1", aggregate_type="desk_request",
                       type=EventType.DESK_REQUESTED,
                       payload={"request_id": "r1", "kind": "attack",
                                "serves": "adversary", "subject": "the sieve",
                                "at": "2026-08-20T00:00:00Z"}, actor="operator"))
    v = desk.view(store)
    assert v["open_requests"] == 1
    assert v["requests"][0]["subject"] == "the sieve"

    store.append(Event(aggregate_id="r1", aggregate_type="desk_request",
                       type=EventType.DESK_REQUEST_RESOLVED,
                       payload={"request_id": "r1",
                                "resolution": "docs/reviews/X.md",
                                "at": "2026-08-20T01:00:00Z"}, actor="cto"))
    v = desk.view(store)
    assert v["open_requests"] == 0
    assert v["requests"][0]["status"] == "resolved"
    assert v["requests"][0]["resolution"] == "docs/reviews/X.md"


def test_a_seat_filed_ask_is_visible_not_just_counted():
    """Found 2026-08-21: the CEO's desk read '2/20 open' while rendering
    empty. Seat-filed asks write subject/serves; the readers key on
    task/seat — an unnormalized row is counted by desk_load but renders
    blank. An invisible item on the CEO's desk is the worst kind of open
    item: it blocks the funnel and nobody can click it."""
    store = MemStore()
    store.append(Event(aggregate_id="r2", aggregate_type="desk_request",
                       type=EventType.DESK_REQUESTED,
                       payload={"request_id": "r2", "kind": "proposal",
                                "serves": "mechanism",
                                "subject": "propose premia-menu entry 7",
                                "actor": "pm",
                                "at": "2026-08-20T20:08:26Z"}, actor="pm"))
    v = desk.view(store)
    row = v["requests"][0]
    assert row["task"] == "propose premia-menu entry 7"
    assert row["seat"] == "mechanism"
    # And the CEO-typed vocabulary still round-trips untouched.
    store.append(Event(aggregate_id="r3", aggregate_type="desk_request",
                       type=EventType.DESK_REQUESTED,
                       payload={"request_id": "r3", "kind": "attack",
                                "seat": "adversary", "task": "attack the gate",
                                "at": "2026-08-21T00:00:00Z"}, actor="operator"))
    v = desk.view(store)
    row3 = [r for r in v["requests"] if r["request_id"] == "r3"][0]
    assert row3["task"] == "attack the gate"
    assert row3["seat"] == "adversary"


def test_the_execution_honesty_line_is_in_the_payload():
    """The one lie this page must never tell: that the spine can think."""
    v = desk.view(MemStore())
    assert "does not run agents" in v["execution_note"]


# --------------------------------------------------------------- telemetry ---
#
# "Is it running, how often today, at what token cost" (CEO ask, 2026-08-21).
# Three figures, three DIFFERENT ways of being absent. The failure these tests
# exist to make impossible is the one the desk_load counter already made once:
# a number that reads like a count and is actually a floor.


def test_the_day_window_is_utc_and_half_open():
    from datetime import datetime, timezone
    day, start, end = desk.utc_day_bounds(
        datetime(2026, 8, 21, 23, 59, 59, tzinfo=timezone.utc))
    assert day == "2026-08-21"
    assert start.startswith("2026-08-21T00:00:00")
    assert end.startswith("2026-08-22T00:00:00")


def _act(**seats):
    return {s: {"status": v[0], "task": v[1], "since": v[2]}
            for s, v in seats.items()}


def test_runs_today_is_counted_per_seat_and_tokens_summed():
    runs = [
        {"seat": "pm", "tokens": 100, "model": "opus",
         "resolved_at": "2026-08-21T10:00:00+00:00"},
        {"seat": "pm", "tokens": 50, "model": "opus",
         "resolved_at": "2026-08-21T12:00:00+00:00"},
        {"seat": "quant", "tokens": 7, "model": "qwen3.8",
         "resolved_at": "2026-08-21T11:00:00+00:00"},
    ]
    t = desk.seat_telemetry(runs, _act(pm=("idle", None, None)), "2026-08-21")
    assert t["readable"] is True
    pm = t["seats"]["pm"]
    assert pm["runs_today"] == 2
    assert pm["tokens_today"] == 150
    assert pm["tokens_partial"] is False
    assert pm["runs_missing_tokens"] == 0
    assert pm["tokens_by_model"] == {"opus": 150}
    assert pm["last_run_at"] == "2026-08-21T12:00:00+00:00"
    # A model split survives, because the price table lives in the UI and a
    # blend priced at one seat's model would be wrong for the other's.
    assert t["seats"]["quant"]["tokens_by_model"] == {"qwen3.8": 7}
    # A seat that did nothing today is a MEASURED zero — the recorder was read
    # and it had no rows. That is not the same as the absent case below.
    assert t["seats"]["adversary"]["runs_today"] == 0
    assert t["seats"]["adversary"]["tokens_today"] is None


def test_a_run_with_no_token_figure_counts_as_a_run_and_makes_the_sum_partial():
    """The bill must never be understated by a run that forgot to report.

    Two runs, one figure. `tokens_today` is 100 and `tokens_partial` is True,
    so the surface renders "at least 100" — a total rendered flat here would
    claim the seat cost 100 when the honest statement is "at least 100, over
    1 of 2 runs".
    """
    runs = [
        {"seat": "pm", "tokens": 100, "model": "opus",
         "resolved_at": "2026-08-21T10:00:00+00:00"},
        {"seat": "pm", "tokens": None, "model": "opus",
         "resolved_at": "2026-08-21T11:00:00+00:00"},
    ]
    pm = desk.seat_telemetry(runs, {}, "2026-08-21")["seats"]["pm"]
    assert pm["runs_today"] == 2
    assert pm["tokens_today"] == 100
    assert pm["tokens_partial"] is True
    assert pm["runs_missing_tokens"] == 1
    # And with NO figure at all the total is ABSENT, not a partial zero.
    only = desk.seat_telemetry(
        [{"seat": "pm", "tokens": None, "model": "opus",
          "resolved_at": "2026-08-21T10:00:00+00:00"}], {}, "2026-08-21")
    assert only["seats"]["pm"]["runs_today"] == 1
    assert only["seats"]["pm"]["tokens_today"] is None
    assert only["seats"]["pm"]["tokens_partial"] is False


def test_an_unreadable_flight_recorder_reports_absence_not_a_quiet_day():
    t = desk.seat_telemetry(None, {}, "2026-08-21")
    assert t["readable"] is False
    assert "absence, not a quiet day" in t["note"]
    for row in t["seats"].values():
        assert row["runs_today"] is None
        assert row["tokens_today"] is None
        assert row["runs_missing_tokens"] is None


def test_running_now_is_the_dispatch_fold_and_carries_the_task():
    t = desk.seat_telemetry(
        [], _act(builder=("working", "D5: the floor", "2026-08-21T08:00:00Z"),
                 pm=("idle", None, None)), "2026-08-21")
    b = t["seats"]["builder"]
    assert b["running_now"] is True
    assert b["running_task"] == "D5: the floor"
    assert b["running_since"] == "2026-08-21T08:00:00Z"
    # An idle seat carries no task. Idle is a real state, not a gap.
    assert t["seats"]["pm"]["running_now"] is False
    assert t["seats"]["pm"]["running_task"] is None


def test_the_view_carries_telemetry_and_a_store_without_the_day_query_degrades():
    """A store that predates `runs_between` must report UNREADABLE telemetry.

    The tempting failure is to fall back to the capped 25-run list — which
    would put a number on the surface that is a floor, unlabelled. The desk
    already made that exact mistake once (desk_load read 73 against 10 truly
    open). Absent beats a plausible wrong number.
    """
    class OldStore:
        def runs(self, limit=25):
            return [{"seat": "pm", "tokens": 5, "model": "opus",
                     "resolved_at": "2026-08-21T10:00:00+00:00",
                     "recommendations": [], "run_id": "r", "task": "t",
                     "artifact_path": None, "verdict": None}]

        def open_recommendations(self):
            return []

    v = desk.view(MemStore(), OldStore())
    assert v["seat_telemetry"]["readable"] is False
    assert v["seat_telemetry"]["seats"]["pm"]["runs_today"] is None

    class NewStore(OldStore):
        def runs_between(self, start, end, limit=500):
            return [{"seat": "pm", "tokens": 5, "model": "opus",
                     "resolved_at": "2026-08-21T10:00:00+00:00"}]

    v = desk.view(MemStore(), NewStore())
    assert v["seat_telemetry"]["readable"] is True
    assert v["seat_telemetry"]["seats"]["pm"]["runs_today"] == 1
    assert v["seat_telemetry"]["seats"]["pm"]["tokens_today"] == 5
