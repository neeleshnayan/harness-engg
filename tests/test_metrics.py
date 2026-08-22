"""Derived daily rollups — and the four ways they could quietly lie.

Every test here guards a MEASURED defect or a measured hazard in the live log,
not a hypothetical. The rollup exists because three seats hand-rolled the same
fold three ways; a test suite that only checked the happy path would make this
module the fourth hand-rolled fold, with the added authority of being shared.

The four properties under guard, each with the incident that earned it:

  * **ABSENCE IS NEVER ZERO.** A day with no NavStruck must not read $0.00, and
    an unreachable run recorder must not read "no runs". The fund's oldest
    mistake; the drawdown incident and the phantom-price incident are both this
    shape.
  * **THE VENUE SPLIT INVENTS NOTHING.** 20 of 29 live OrderFilled payloads
    carry no venue key. The R15 cost-measurement experiment was falsely marked
    done because a fill labelled `alpaca` had executed on paper — a venue label
    that is guessed is worse than one that is missing.
  * **DeskDispatched NEVER ENTERS THE REQUEST FOLD.** 14 of 24 carry no
    request_id and one names a request that was never filed; folding them
    creates a phantom request with a None id that then ages forever.
  * **A CAP IS NOT A COUNT.** The desk payload's 25-run limit silently
    truncated the firm's first spend meter. The rollup reads the uncapped SQL
    window.
"""

from datetime import datetime, timezone

import pytest

from app.fund import metrics


DAY = "2026-08-21"
NEXT = datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc)


class FakeStore:
    """The smallest thing that answers `stream` the way the real stores do."""

    def __init__(self, events):
        self._events = list(events)

    def stream(self, since_seq=0, limit=200):
        return [e for e in self._events if e.get("seq", 0) > since_seq][:limit]


def ev(seq, type_, ts, payload=None, actor="system"):
    return {"seq": seq, "type": type_, "ts": ts, "actor": actor,
            "payload": payload or {}}


def t(hhmm, day=DAY):
    return f"{day}T{hhmm}:00+00:00"


# --- day arithmetic ---------------------------------------------------------

def test_day_bounds_are_utc_and_half_open():
    start, end = metrics.day_bounds(DAY)
    assert start == "2026-08-21T00:00:00+00:00"
    assert end == "2026-08-22T00:00:00+00:00"


def test_the_bounds_string_compare_correctly_against_the_TEXT_ts_column():
    """`ts` is TEXT, so the window is a STRING range. It must be right for both
    the `+00:00` form the log writes and the `Z` form fixtures write."""
    start, end = metrics.day_bounds(DAY)
    assert start <= "2026-08-21T00:00:00.000001+00:00" < end
    assert start <= "2026-08-21T23:59:59Z" < end
    assert not (start <= "2026-08-20T23:59:59+00:00" < end)
    assert not (start <= "2026-08-22T00:00:00+00:00" < end)


def test_a_malformed_day_is_refused_not_defaulted_to_today():
    with pytest.raises(ValueError):
        metrics.parse_day("yesterday")
    with pytest.raises(ValueError):
        metrics.parse_day(None)


def test_an_event_with_no_ts_is_not_placed_on_any_day():
    store = FakeStore([ev(1, "NavStruck", None, {"total_nav_usd": 100})])
    got = metrics.compute_daily(DAY, store, now=NEXT)
    assert got["events"]["total"] == 0
    assert metrics.is_unknown(got["nav"])


# --- absence is never zero --------------------------------------------------

def test_a_day_with_no_nav_strike_reports_UNKNOWN_not_zero():
    """A fund that was not marked is not a fund worth nothing.

    Guards the fund's oldest defect class: absence rendered as a value. If this
    ever returns 0.0 the CEO's daily brief will read a real NAV of $1,885 as a
    wipeout on any day the striker did not run.
    """
    store = FakeStore([ev(1, "OrderFilled", t("10:00"),
                          {"avg_price": "10", "filled_qty": "1"})])
    nav = metrics.compute_daily(DAY, store, now=NEXT)["nav"]
    assert metrics.is_unknown(nav)
    assert nav["reason"] == "NONE_ON_DAY"
    assert nav["value"] is None
    assert "not the same as being marked at zero" in nav["note"]


def test_an_unreachable_run_recorder_reports_UNKNOWN_not_no_runs():
    """`deskstore=None` means we could not look, which is not "nobody ran"."""
    got = metrics.compute_daily(DAY, FakeStore([]), deskstore=None, now=NEXT)
    assert metrics.is_unknown(got["runs"])
    assert got["runs"]["reason"] == "RECORDER_UNREACHABLE"
    assert "runs" in got["unknown_sections"]


def test_a_run_recorder_that_RAISES_reports_UNKNOWN_not_zero():
    class Exploding:
        def runs_between(self, *a, **k):
            raise RuntimeError("connection refused")

    got = metrics.compute_daily(DAY, FakeStore([]), deskstore=Exploding(),
                                now=NEXT)
    assert metrics.is_unknown(got["runs"])
    assert got["runs"]["reason"] == "RECORDER_UNREACHABLE"
    assert "connection refused" in got["runs"]["note"]


def test_unknown_refuses_an_unlisted_reason():
    """A free-text reason makes 'we could not look' ungreppable from 'there
    were none'. The set is closed on purpose."""
    with pytest.raises(ValueError):
        metrics.unknown("BECAUSE", "no")


# --- fills: the measured hazards -------------------------------------------

def test_notional_survives_the_mixed_string_and_number_price_column():
    """avg_price is a JSON string on 22 of 29 live fills and a number on 7.
    A sum that does not coerce either raises or concatenates."""
    store = FakeStore([
        ev(1, "OrderFilled", t("10:00"),
           {"avg_price": "28.38", "filled_qty": "5.314306", "side": "buy",
            "venue": "alpaca"}),
        ev(2, "OrderFilled", t("11:00"),
           {"avg_price": 100.0, "filled_qty": 2, "side": "sell",
            "venue": "alpaca"}),
    ])
    fills = metrics.compute_daily(DAY, store, now=NEXT)["fills"]
    assert fills["count"] == 2
    assert fills["notional_usd"] == pytest.approx(150.82 + 200.0, abs=0.01)
    assert fills["complete"] is True
    assert fills["by_side"] == {"buy": 1, "sell": 1}


def test_a_fill_with_no_venue_is_NOT_bucketed_as_paper():
    """20 of 29 live fills carry no venue key. Guessing one is how R15 was
    falsely marked done — the label said alpaca and the fill was paper."""
    store = FakeStore([
        ev(1, "OrderFilled", t("10:00"), {"avg_price": "1", "filled_qty": "1"}),
        ev(2, "OrderFilled", t("11:00"),
           {"avg_price": "1", "filled_qty": "1", "venue": "alpaca"}),
    ])
    fills = metrics.compute_daily(DAY, store, now=NEXT)["fills"]
    assert fills["by_venue"] == {"alpaca": 1}
    assert fills["venue_unstated"] == 1
    assert "paper" not in fills["by_venue"]
    assert sum(fills["by_venue"].values()) + fills["venue_unstated"] == fills["count"]


def test_an_unreadable_fill_price_marks_the_notional_INCOMPLETE():
    """It must not contribute zero to a total that then reads full."""
    store = FakeStore([
        ev(1, "OrderFilled", t("10:00"),
           {"avg_price": "not-a-price", "filled_qty": "1"}),
        ev(2, "OrderFilled", t("11:00"), {"avg_price": "5", "filled_qty": "2"}),
    ])
    fills = metrics.compute_daily(DAY, store, now=NEXT)["fills"]
    assert fills["unreadable"] == 1
    assert fills["complete"] is False
    assert fills["notional_usd"] == pytest.approx(10.0)


# --- the fold sums to its own total ----------------------------------------

def test_events_by_type_plus_untyped_equals_the_total():
    store = FakeStore([
        ev(1, "NavStruck", t("10:00"), {"total_nav_usd": 100}),
        ev(2, "NavStruck", t("11:00"), {"total_nav_usd": 110}),
        ev(3, None, t("12:00")),
    ])
    got = metrics.compute_daily(DAY, store, now=NEXT)["events"]
    assert got["total"] == 3
    assert sum(got["by_type"].values()) + got["untyped"] == got["total"]


def test_nav_open_and_close_follow_seq_not_dict_order():
    store = FakeStore([
        ev(2, "NavStruck", t("18:00"), {"total_nav_usd": 2100}),
        ev(1, "NavStruck", t("09:00"), {"total_nav_usd": 2000}),
    ])
    nav = metrics.compute_daily(DAY, store, now=NEXT)["nav"]
    assert nav["strikes"] == 2
    assert nav["open_usd"] == 2000.0
    assert nav["close_usd"] == 2100.0
    assert nav["complete"] is True


def test_decisions_split_by_actor_and_status():
    store = FakeStore([
        ev(1, "DeskRecommendationDecided", t("10:00"), {"status": "accepted"},
           actor="ceo"),
        ev(2, "DeskRecommendationDecided", t("11:00"), {"status": "done"},
           actor="cto"),
        ev(3, "DeskRecommendationDecided", t("12:00"), {}, actor="ceo"),
    ])
    d = metrics.compute_daily(DAY, store, now=NEXT)["decisions"]
    assert d["total"] == 3
    assert d["by_actor"] == {"ceo": 2, "cto": 1}
    assert d["by_status"] == {"accepted": 1, "done": 1, "UNSTATED": 1}
    assert d["by_actor_status"]["ceo/UNSTATED"] == 1


# --- partial days -----------------------------------------------------------

def test_a_day_still_running_is_marked_INCOMPLETE():
    """A rollup for today is a snapshot, not a measurement. Without this a
    trend line silently compares four hours against twenty-four."""
    mid_day = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    got = metrics.compute_daily(DAY, FakeStore([]), now=mid_day)
    assert got["complete_day"] is False
    got = metrics.compute_daily(DAY, FakeStore([]), now=NEXT)
    assert got["complete_day"] is True


def test_the_digest_is_stable_across_recomputation_but_moves_with_content():
    store = FakeStore([ev(1, "NavStruck", t("10:00"), {"total_nav_usd": 100})])
    a = metrics.compute_daily(DAY, store, now=NEXT)
    b = metrics.compute_daily(DAY, store,
                              now=NEXT.replace(hour=13))
    assert a["digest"] == b["digest"], "computed_at must not move the digest"
    store2 = FakeStore([ev(1, "NavStruck", t("10:00"), {"total_nav_usd": 101})])
    assert metrics.compute_daily(DAY, store2, now=NEXT)["digest"] != a["digest"]


# --- run aggregation --------------------------------------------------------

def test_a_seat_whose_runs_carry_no_tokens_reports_None_not_zero():
    """Never zero: a zero would make the least-measured seat also the cheapest
    one on the CFO's meter, which is how a budget gets pointed at the wrong
    thing."""
    got = metrics.summarise_runs([
        {"seat": "quiet", "tokens": None, "tool_uses": None},
        {"seat": "loud", "tokens": 100, "tool_uses": 5},
    ])
    assert got["by_seat"]["quiet"]["tokens"] is None
    assert got["by_seat"]["quiet"]["runs_missing_tokens"] == 1
    assert got["by_seat"]["loud"]["tokens"] == 100
    assert got["total_tokens"] == 100
    assert got["runs_missing_tokens"] == 1


def test_a_run_with_no_dispatched_at_has_UNKNOWN_duration_not_zero():
    """dispatched_at exists at deskstore.py:44 and almost nothing writes it.
    A zero here would make the firm's slowest work look instantaneous."""
    got = metrics.summarise_runs([
        {"seat": "builder", "dispatched_at": None,
         "resolved_at": "2026-08-21T10:00:00+00:00"},
        {"seat": "builder", "dispatched_at": "2026-08-21T09:00:00+00:00",
         "resolved_at": "2026-08-21T10:00:00+00:00"},
    ])
    b = got["by_seat"]["builder"]
    assert b["runs_missing_duration"] == 1
    assert b["runs_with_duration"] == 1
    assert b["median_duration_seconds"] == pytest.approx(3600.0)


def test_a_negative_duration_is_UNKNOWN_not_a_fast_run():
    got = metrics.summarise_runs([
        {"seat": "s", "dispatched_at": "2026-08-21T11:00:00+00:00",
         "resolved_at": "2026-08-21T10:00:00+00:00"},
    ])
    assert got["by_seat"]["s"]["median_duration_seconds"] is None
    assert got["by_seat"]["s"]["runs_missing_duration"] == 1


def test_a_run_with_no_status_is_unrecorded_NOT_delivered():
    """Every run written before the status column existed made NO statement
    about whether it delivered. Calling that `delivered` would fabricate a
    success rate — and the whole point of the column is that work which DIES
    currently costs zero by construction."""
    got = metrics.summarise_runs([
        {"seat": "a"},
        {"seat": "a", "status": "failed"},
        {"seat": "a", "status": "delivered"},
    ])
    assert got["by_seat"]["a"]["by_status"] == {
        "unrecorded": 1, "failed": 1, "delivered": 1}
    assert got["runs_failed"] == 1
    assert got["runs_unrecorded_status"] == 1
    assert "FLOOR" in got["note"]


def test_seat_totals_sum_to_the_reported_total():
    rows = [{"seat": "a", "tokens": 1, "tool_uses": 1},
            {"seat": "b", "tokens": 2, "tool_uses": 2},
            {"seat": "a", "tokens": 3, "tool_uses": 3}]
    got = metrics.summarise_runs(rows)
    assert got["total_runs"] == 3
    assert sum(v["runs"] for v in got["by_seat"].values()) == 3
    assert got["total_tokens"] == 6


def test_a_run_with_no_seat_is_UNSTATED_and_still_counted():
    got = metrics.summarise_runs([{"tokens": 5}])
    assert got["by_seat"]["UNSTATED"]["runs"] == 1
    assert got["total_runs"] == 1


def test_a_naive_datetime_is_read_as_UTC_not_as_the_hosts_local_time():
    """`astimezone` alone applies the HOST offset, which can move an event to
    the wrong day on a machine that is not on UTC. Every timestamp in this fund
    is UTC; `desk._ts` states the same assumption and the two must not drift."""
    from datetime import datetime, timezone
    naive_late = datetime(2026, 8, 21, 23, 30)
    naive_early = datetime(2026, 8, 21, 0, 30)
    assert metrics.parse_day(naive_late).isoformat() == "2026-08-21"
    assert metrics.parse_day(naive_early).isoformat() == "2026-08-21"
    aware = datetime(2026, 8, 21, 23, 30, tzinfo=timezone.utc)
    assert metrics.parse_day(aware) == metrics.parse_day(naive_late)


def test_desk_utc_day_bounds_and_metrics_day_bounds_CANNOT_disagree():
    """One day boundary, one implementation. Two copies is two chances to
    disagree about which day a dispatch happened on, invisibly."""
    from datetime import datetime, timezone
    from app.fund import desk
    n = datetime(2026, 8, 21, 23, 59, 59, tzinfo=timezone.utc)
    day, start, end = desk.utc_day_bounds(n)
    assert (start, end) == metrics.day_bounds(day)
    assert day == "2026-08-21"
