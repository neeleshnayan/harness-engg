"""The desk query scripts — they render, and they render ABSENCE as absence.

A script library exists to stop seats re-authoring folds. That only helps if
the scripts are correct, so the render functions are pure (body in, string out)
and tested here without a database.

THE PROPERTY THAT MATTERS MOST IS NOT THE ARITHMETIC — the arithmetic is tested
in `test_metrics.py`, and the scripts deliberately carry no second copy of it.
What is tested here is that the output a seat COPIES OUT carries the
qualifiers: `ABSENT`, `UNKNOWN`, `UPPER BOUND`, `FLOOR`. A script that renders
a missing token count as `0` would launder the absence at exactly the moment
it enters a memo, which is worse than the payload having been wrong, because
the payload is at least auditable.

One test also pins the quirk list itself: `_common.py`'s docstring is the
place seats are told to read, and a quirk silently deleted from it costs the
next seat the tool calls it cost the last one.
"""

import importlib
import pathlib
import sys

import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "desk"


@pytest.fixture(autouse=True)
def _on_path():
    p = str(SCRIPTS)
    if p not in sys.path:
        sys.path.insert(0, p)
    yield
    for m in ("_common", "day_events", "friction", "run_stats", "nav_day"):
        sys.modules.pop(m, None)
    if p in sys.path:
        sys.path.remove(p)


def mod(name):
    return importlib.import_module(name)


# --- the library contract ---------------------------------------------------

@pytest.mark.parametrize("name", ["day_events", "friction", "run_stats",
                                  "nav_day"])
def test_every_script_documents_how_to_run_it(name):
    doc = mod(name).__doc__ or ""
    assert "scripts/desk/" in doc, f"{name} does not show its own command line"
    assert "venv/Scripts/python.exe" in doc, (
        f"{name} does not name the interpreter — there is no psql here and the "
        f"system python has no psycopg")


def test_the_quirk_list_still_carries_every_trap_it_was_written_for():
    """`_common.py`'s docstring is where seats are sent. Each line below cost
    somebody tool calls before it was written down; deleting one silently
    charges the next seat the same price."""
    doc = mod("_common").__doc__ or ""
    for trap in ("PascalCase", "event_type", "TEXT", "tokens_used",
                 "avg_price", "venue", "request_id", "psql", "5433",
                 "only '%s','%b','%t' are allowed"):
        assert trap in doc, f"the quirk list lost {trap!r}"


def test_absent_and_unknown_have_words_not_zeros():
    C = mod("_common")
    assert C.money(None) == "ABSENT"
    assert C.money("not-a-number") == "UNREADABLE"
    assert C.num(None) == "ABSENT"
    assert C.money(0) == "$0.00", "a real zero must still render as a zero"


def test_the_banner_says_when_the_spine_did_not_answer():
    """A number's provenance is part of the number."""
    C = mod("_common")
    assert "source=spine" in C.banner("spine", "x")
    assert "spine did not answer" in C.banner("postgres", "x")


def test_fetch_prefers_the_spine_and_falls_back_without_losing_the_answer(monkeypatch):
    C = mod("_common")
    monkeypatch.setattr(C, "from_spine", lambda p: {"from": "spine"})
    assert C.fetch("/x", lambda: {"from": "pg"}) == ("spine", {"from": "spine"})
    monkeypatch.setattr(C, "from_spine", lambda p: None)
    assert C.fetch("/x", lambda: {"from": "pg"}) == ("postgres", {"from": "pg"})


# --- day_events -------------------------------------------------------------

def _day_body(**over):
    body = {
        "day": "2026-08-21", "complete_day": True,
        "events": {"total": 3, "by_type": {"NavStruck": 3}, "untyped": 0},
        "decisions": {"total": 1, "by_actor": {"ceo": 1},
                      "by_status": {"accepted": 1},
                      "by_actor_status": {"ceo/accepted": 1}},
        "nav": {"strikes": 3, "open_usd": 100.0, "close_usd": 110.0,
                "open_ts": None, "close_ts": None, "unreadable_strikes": 0,
                "complete": True},
        "fills": {"count": 0, "notional_usd": 0.0, "complete": True,
                  "unreadable": 0, "by_venue": {}, "venue_unstated": 0,
                  "by_side": {}},
        "reconciliation_mismatches": 0,
        "desk_requests": {"filed": 1, "approved": 0, "resolved": 0,
                          "declined": 0},
        "runs": {"total_runs": 0, "total_tokens": 0, "total_tool_uses": 0,
                 "runs_missing_tokens": 0, "runs_missing_duration": 0,
                 "runs_failed": 0, "runs_unrecorded_status": 0,
                 "by_seat": {}, "note": "0 run(s)"},
        "unknown_sections": [],
    }
    body.update(over)
    return body


def test_day_events_renders_a_whole_day():
    out = mod("day_events").render(_day_body())
    assert "2026-08-21" in out
    assert "$100.00" in out and "$110.00" in out


def test_day_events_marks_a_day_still_running():
    out = mod("day_events").render(_day_body(complete_day=False))
    assert "DAY STILL RUNNING" in out


def test_day_events_prints_UNKNOWN_nav_rather_than_a_dollar_zero():
    out = mod("day_events").render(_day_body(
        nav={"state": "UNKNOWN", "value": None, "reason": "NONE_ON_DAY",
             "note": "the fund was not marked"},
        unknown_sections=["nav"]))
    assert "nav UNKNOWN" in out and "NONE_ON_DAY" in out
    # The NAV LINE specifically carries no dollar figure. (The fills line may
    # legitimately read $0.00 — zero fills really is zero notional, and that
    # is a measured zero, not an absence.)
    nav_line = [ln for ln in out.splitlines() if ln.startswith("nav ")][0]
    assert "$" not in nav_line


def test_day_events_prints_UNKNOWN_runs_rather_than_an_empty_seat_table():
    out = mod("day_events").render(_day_body(
        runs={"state": "UNKNOWN", "value": None,
              "reason": "RECORDER_UNREACHABLE", "note": "not configured"},
        unknown_sections=["runs"]))
    assert "runs UNKNOWN" in out and "RECORDER_UNREACHABLE" in out


def test_day_events_names_a_missing_venue_instead_of_bucketing_it():
    out = mod("day_events").render(_day_body(
        fills={"count": 2, "notional_usd": 20.0, "complete": True,
               "unreadable": 0, "by_venue": {"alpaca": 1},
               "venue_unstated": 1, "by_side": {"buy": 2}}))
    assert "venue NOT STATED on 1" in out
    assert "paper" not in out


def test_day_events_renders_an_unknown_wall_clock_as_UNKNOWN_not_zero():
    out = mod("day_events").render(_day_body(
        runs={"total_runs": 1, "total_tokens": 5, "total_tool_uses": 1,
              "runs_missing_tokens": 0, "runs_missing_duration": 1,
              "runs_failed": 0, "runs_unrecorded_status": 1,
              "by_seat": {"pm": {"runs": 1, "tokens": 5, "tool_uses": 1,
                                 "median_duration_seconds": None,
                                 "by_status": {"unrecorded": 1}}},
              "note": "n"}))
    assert "median_wall=UNKNOWN" in out
    assert "median_wall=0" not in out


# --- friction ---------------------------------------------------------------

def _friction_body(**over):
    body = {
        "requests": [
            {"request_id": "r1", "task": "do a thing", "seat": "pm",
             "state": "approved_undispatched", "waiting_on": "chair",
             "terminal": False, "age_hours": 20.0, "age_in_state_hours": 3.0,
             "dispatch_seen": False, "dispatch_detectable": False},
            {"request_id": "r2", "task": None, "seat": None,
             "state": "open", "waiting_on": "ceo", "terminal": False,
             "age_hours": None, "age_in_state_hours": None,
             "dispatch_seen": False, "dispatch_detectable": False},
        ],
        "count": 2, "open_count": 2,
        "by_state": {"open": 1, "approved_undispatched": 1,
                     "approved_dispatched": 0, "resolved": 0, "declined": 0},
        "waiting_on": {"chair": 1, "ceo": 1},
        "approved_undispatched": 1,
        "oldest_open_hours": 20.0, "oldest_open_request_id": "r1",
        "dispatch_link_coverage": {"dispatch_events": 24, "linkable": 10,
                                   "unlinkable_no_request_id": 14,
                                   "orphan_request_id": 1, "complete": False},
        "note": "n",
    }
    body.update(over)
    return body


def test_friction_flags_the_undispatched_count_as_an_UPPER_BOUND():
    """14 of 24 dispatch events are unlinkable, so the figure is a ceiling. A
    number printed without that qualifier gets quoted without it."""
    out = mod("friction").render(_friction_body())
    assert "UPPER BOUND" in out
    assert "14 carry no request_id" in out


def test_friction_drops_the_qualifier_only_when_coverage_is_COMPLETE():
    out = mod("friction").render(_friction_body(
        dispatch_link_coverage={"dispatch_events": 10, "linkable": 10,
                                "unlinkable_no_request_id": 0,
                                "orphan_request_id": 0, "complete": True}))
    assert "UPPER BOUND" not in out


def test_friction_renders_an_unreadable_age_as_ABSENT_not_zero_hours():
    out = mod("friction").render(_friction_body())
    # The r2 row has no readable filing time. Its two age cells must both read
    # ABSENT — not "0.0h", which would sort it as the newest thing on a list
    # ranked by age. Asserted on the ROW, because a naive substring check for
    # "0.0h" also matches the legitimate "20.0h" one line above.
    row = [ln for ln in out.splitlines() if "(no task recorded)" in ln][0]
    assert row.split()[0] == "ABSENT" and row.split()[1] == "ABSENT"
    assert "0.0h" not in row


def test_friction_names_a_row_with_no_task_instead_of_printing_a_blank():
    out = mod("friction").render(_friction_body())
    assert "(no task recorded)" in out


def test_friction_hides_terminal_rows_by_default_and_shows_them_with_all():
    body = _friction_body()
    body["requests"].append({"request_id": "r3", "task": "done thing",
                             "seat": "pm", "state": "resolved",
                             "waiting_on": None, "terminal": True,
                             "age_hours": 40.0, "age_in_state_hours": 1.0,
                             "dispatch_seen": True,
                             "dispatch_detectable": False})
    assert "done thing" not in mod("friction").render(body)
    assert "done thing" in mod("friction").render(body, show_all=True)


# --- run_stats --------------------------------------------------------------

def _stats_body(**over):
    body = {
        "total_runs": 2, "total_tokens": 100, "total_tool_uses": 5,
        "runs_missing_tokens": 1, "runs_missing_duration": 1,
        "runs_failed": 0, "runs_unrecorded_status": 2,
        "row_count": 2, "rows_read": 2, "truncated": False, "complete": True,
        "by_seat": {
            "quiet": {"runs": 1, "tokens": None, "tool_uses": None,
                      "median_duration_seconds": None,
                      "first_resolved_at": None, "last_resolved_at": None,
                      "by_status": {"unrecorded": 1}},
            "loud": {"runs": 1, "tokens": 100, "tool_uses": 5,
                     "median_duration_seconds": 600.0,
                     "first_resolved_at": "2026-08-21T00:00:00+00:00",
                     "last_resolved_at": "2026-08-21T00:00:00+00:00",
                     "by_status": {"unrecorded": 1}},
        },
        "note": "the 0 recorded failure(s) are a FLOOR",
    }
    body.update(over)
    return body


def test_run_stats_prints_a_seat_with_no_tokens_as_ABSENT_not_zero():
    """A zero would make the least-measured seat the cheapest on the meter."""
    out = mod("run_stats").render(_stats_body())
    assert "ABSENT" in out
    lines = [ln for ln in out.splitlines() if ln.startswith("quiet")]
    assert lines and "0" not in lines[0].replace("UNKNOWN", ""), lines


def test_run_stats_shouts_when_it_did_not_read_every_row():
    out = mod("run_stats").render(_stats_body(rows_read=5, row_count=50,
                                              truncated=True, complete=False))
    assert out.startswith("TRUNCATED: 5 of 50")
    assert "FLOOR" in out


def test_run_stats_carries_the_floor_warning_on_the_failure_count():
    out = mod("run_stats").render(_stats_body())
    assert "unrecorded 2" in out
    assert "FLOOR" in out


def test_run_stats_renders_an_UNKNOWN_recorder_as_such():
    out = mod("run_stats").render(
        {"state": "UNKNOWN", "value": None, "reason": "RECORDER_UNREACHABLE",
         "note": "not configured"})
    assert out.startswith("UNKNOWN — RECORDER_UNREACHABLE")


# --- nav_day ----------------------------------------------------------------

def test_nav_day_prints_the_sentence_not_a_zero_when_nothing_was_struck():
    out = mod("nav_day").render(
        {"day": "2026-08-16", "strikes": [], "count": 0,
         "note": "no NavStruck on 2026-08-16 — the fund was not marked, which "
                 "is not the same as being marked at zero"})
    assert "not the same as being marked at zero" in out
    assert "$0.00" not in out


def test_nav_day_shows_each_strike_and_the_change_between_them():
    out = mod("nav_day").render({"day": "2026-08-21", "count": 2, "note": "",
                                 "strikes": [
        {"seq": 1, "ts": "2026-08-21T09:00:00+00:00", "total_nav_usd": 100.0,
         "cash_usd": 40.0, "positions_usd": 60.0, "position_count": 2},
        {"seq": 2, "ts": "2026-08-21T18:00:00+00:00", "total_nav_usd": 110.5,
         "cash_usd": 40.0, "positions_usd": 70.5, "position_count": 2}]})
    assert "+10.50" in out
    assert "open $100.00 -> close $110.50" in out


def test_nav_day_lists_an_unreadable_strike_rather_than_dropping_it():
    """A strike that happened and could not be parsed is a fact worth seeing;
    dropping it would make the day look one strike quieter than it was."""
    out = mod("nav_day").render({"day": "2026-08-21", "count": 2, "note": "",
                                 "strikes": [
        {"seq": 1, "ts": "2026-08-21T09:00:00+00:00", "total_nav_usd": None,
         "cash_usd": None, "positions_usd": None, "position_count": None},
        {"seq": 2, "ts": "2026-08-21T18:00:00+00:00", "total_nav_usd": 110.5,
         "cash_usd": 40.0, "positions_usd": 70.5, "position_count": 2}]})
    assert "ABSENT" in out
    assert "1 strike(s) carried NO readable total" in out
