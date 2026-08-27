"""THE NAV RECORD'S HOLES — can a missing trading day still hide in the series?

WHY THIS FILE EXISTS. This fund struck no NAV between 2026-08-24T19:14:46Z and
2026-08-26T13:52:04Z — 42.6 hours, swallowing the whole of Tuesday 2026-08-25, a
trading day — and nothing noticed. The chart drew a straight line between the
two surviving points; the event log was complete, tamper-evident, and silent
about the day it did not contain; the ``nav_strike`` heartbeat was in memory on
a process that was not running.

The tests that matter most here are NOT the ones proving the 42.6h hole is
found. They are the ones proving that:

  * a WEEKEND gap — 65 hours of it, in this fund's own history — is NOT a hole,
    because an instrument that cries every Monday is an instrument nobody reads;
  * an UNREADABLE history reads unreadable and never "no gaps found", which is
    absence rendering as zero, the one thing this codebase forbids;
  * the tolerance is READ from ``heartbeat.BUDGETS_SECONDS`` and not copied —
    ``test_tolerance_is_read_not_copied`` MOVES the budget and watches the
    verdict follow, because asserting two numbers are equal cannot tell a read
    from a duplicate that happens to agree today.

Every instant here is written down. Nothing in this file passes because the
clock cooperated.
"""
from datetime import date, datetime, timedelta, timezone

import pytest

from app.fund import heartbeat, navgap


def _at(iso: str) -> datetime:
    return datetime.fromisoformat(iso)


def _strikes(*isos: str) -> list[dict]:
    return [{"ts": s, "total_nav_usd": 2000.0} for s in isos]


# The real outage, verbatim from GET /fund/nav/history on 2026-08-27.
OUTAGE_BEFORE = "2026-08-24T19:14:46.808135+00:00"
OUTAGE_AFTER = "2026-08-26T13:52:04.644736+00:00"
# The real weekend gap, same source: 65.18 wall hours, Friday evening to Monday
# morning, containing 20 minutes of trading time.
WEEKEND_BEFORE = "2026-08-21T20:39:12.135773+00:00"
WEEKEND_AFTER = "2026-08-24T13:50:10.719943+00:00"


# --------------------------------------------------------------- the calendar

class TestCalendar:
    def test_ordinary_weekday_has_a_regular_session(self):
        bounds = navgap.session_bounds(date(2026, 8, 25))
        assert bounds is not None
        assert bounds[0].isoformat() == "2026-08-25T13:30:00+00:00"
        assert bounds[1].isoformat() == "2026-08-25T20:00:00+00:00"

    def test_weekend_has_no_session(self):
        assert navgap.session_bounds(date(2026, 8, 22)) is None  # Saturday
        assert navgap.session_bounds(date(2026, 8, 23)) is None  # Sunday

    def test_holiday_has_no_session(self):
        """2026-07-03 is the observed Independence Day: a WEEKDAY the venue shuts.

        Mutant: dropping the HOLIDAYS check makes this a normal Friday and a
        legitimate closure reads as a 6.5-hour hole every year.
        """
        assert date(2026, 7, 3).weekday() < 5
        assert navgap.session_bounds(date(2026, 7, 3)) is None

    def test_early_close_is_a_short_trading_day_not_a_closed_one(self):
        """A half-day is a TRADING day. Treating it as a full one reports a
        3-hour hole every Black Friday; treating it as shut hides a real one."""
        bounds = navgap.session_bounds(date(2026, 11, 27))
        assert bounds is not None
        assert bounds[1].astimezone(navgap.MARKET_TZ).hour == 13

    def test_outside_the_sourced_range_is_unknown_not_assumed(self):
        assert navgap.calendar_covers(date(2026, 1, 1))
        assert navgap.calendar_covers(date(2027, 12, 31))
        assert not navgap.calendar_covers(date(2025, 12, 31))
        assert not navgap.calendar_covers(date(2028, 1, 1))

    def test_overlap_walks_market_days_not_utc_days(self):
        """A UTC date boundary falls in the MIDDLE of a US session.

        Mutant: iterating UTC dates splits 2026-08-25's session across two
        calendar days and double-counts or drops the overlap. One full session
        is 6.5 hours and this asserts exactly that.
        """
        got = navgap.trading_overlap(_at("2026-08-25T00:00:00+00:00"),
                                     _at("2026-08-26T00:00:00+00:00"))
        assert got["seconds"] == pytest.approx(6.5 * 3600)
        assert got["trading_days"] == ["2026-08-25"]
        assert got["covered"] is True

    def test_the_day_walk_is_in_MARKET_time_at_the_calendar_boundary(self):
        """Mutant M06: walking UTC dates instead of market-local ones.

        MEASURED equivalent for ``seconds`` and ``trading_days`` — 20,000
        random intervals, zero disagreements — because every US regular session
        lies strictly inside one UTC date while the two date labels differ only
        during 00:00-05:00Z, which contains no session. It is NOT equivalent at
        the calendar's coverage boundary, and the market-local reading is the
        conservative one: 02:00Z on 2026-01-01 is 2025-12-31 in New York, a date
        the sourced table has no opinion about. Claiming coverage there would be
        a confident answer about a day nobody looked up.
        """
        got = navgap.trading_overlap(_at("2026-01-01T02:00:00+00:00"),
                                     _at("2026-01-01T03:00:00+00:00"))
        assert got["uncovered_days"] == ["2025-12-31"]
        assert got["covered"] is False

    def test_overlap_over_an_uncovered_date_reports_it_and_does_not_count_it(self):
        got = navgap.trading_overlap(_at("2025-06-02T00:00:00+00:00"),
                                     _at("2025-06-04T00:00:00+00:00"))
        assert got["covered"] is False
        assert got["uncovered_days"]
        assert got["seconds"] == 0.0

    def test_empty_interval_is_zero_and_covered(self):
        got = navgap.trading_overlap(_at("2026-08-25T15:00:00+00:00"),
                                     _at("2026-08-25T15:00:00+00:00"))
        assert got == {"seconds": 0.0, "uncovered_days": [], "covered": True,
                       "trading_days": []}

    def test_an_empty_interval_on_an_UNCOVERED_date_is_still_covered(self):
        """Mutant M05: ``end <= start`` to ``end < start``.

        A zero-length interval spans no days at all, so there is nothing the
        calendar needed to know — reporting it as uncovered would put an
        UNDETERMINED verdict on a gap of no duration.
        """
        got = navgap.trading_overlap(_at("2025-06-02T15:00:00+00:00"),
                                     _at("2025-06-02T15:00:00+00:00"))
        assert got["covered"] is True
        assert got["uncovered_days"] == []

    def test_a_day_touched_with_zero_overlap_is_not_a_trading_day_of_the_gap(self):
        """Mutant M07: ``hi > lo`` to ``hi >= lo``.

        An interval ending exactly at the opening bell contains none of that
        session. Listing the date anyway would put a day in the note that the
        gap did not actually swallow — and the note is what a human reads.
        """
        got = navgap.trading_overlap(_at("2026-08-25T12:00:00+00:00"),
                                     _at("2026-08-25T13:30:00+00:00"))
        assert got["seconds"] == 0.0
        assert got["trading_days"] == []


# ------------------------------------------------------------ the real outage

class TestTheOutageIsFound:
    def test_the_42_hour_hole_is_detected_and_dated(self):
        """The incident: no strike 2026-08-24T19:14:46Z -> 2026-08-26T13:52:04Z.

        If this ever goes green with hole_count 0, the fund is back to a record
        that cannot tell a missing Tuesday from a Tuesday that did not exist.
        """
        got = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"))
        assert got["state"] == navgap.STATE_HOLES
        assert got["hole_count"] == 1
        hole = got["holes"][0]
        assert hole["from"] == OUTAGE_BEFORE
        assert hole["to"] == OUTAGE_AFTER
        assert hole["hours"] == pytest.approx(42.62, abs=0.01)
        # Monday 19:14->20:00 + all of Tuesday + Wednesday 13:30->13:52.
        assert hole["trading_hours"] == pytest.approx(7.62, abs=0.01)
        assert "2026-08-25" in hole["trading_days"]

    def test_the_note_names_the_missing_trading_day(self):
        got = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"))
        assert "2026-08-25" in got["note"]

    def test_a_weekend_gap_is_not_a_trading_time_hole(self):
        """65.18 wall hours, Friday evening to Monday morning, and NOT a finding.

        Mutant: measuring a gap by wall duration instead of trading seconds
        makes this the largest hole in the fund's history and buries the real
        one under it.
        """
        got = navgap.completeness(
            _strikes(WEEKEND_BEFORE, WEEKEND_AFTER),
            now=_at("2026-08-24T14:00:00+00:00"))
        assert got["state"] == navgap.STATE_COMPLETE
        assert got["hole_count"] == 0
        gap = got["gaps"][0]
        assert gap["hours"] == pytest.approx(65.18, abs=0.01)
        assert gap["trading_hours"] == pytest.approx(0.34, abs=0.01)
        assert gap["verdict"] == "ok"

    def test_the_largest_wall_gap_is_reported_even_when_it_is_not_a_hole(self):
        """Both facts ride the payload. A reader asking "what is the biggest
        interval in this series" gets the weekend; a reader asking "what is
        missing" gets nothing. Collapsing them loses one of the answers."""
        got = navgap.completeness(
            _strikes(WEEKEND_BEFORE, WEEKEND_AFTER),
            now=_at("2026-08-24T14:00:00+00:00"))
        assert got["largest_gap"]["hours"] == pytest.approx(65.18, abs=0.01)
        assert got["largest_gap"]["verdict"] == "ok"


# ---------------------------------------------------------------- absence

class TestAbsenceIsNeverZero:
    def test_unreadable_history_reads_unreadable(self):
        got = navgap.completeness(None, now=_at("2026-08-26T14:00:00+00:00"))
        assert got["state"] == navgap.STATE_UNREADABLE
        assert got["readable"] is False
        assert got["hole_count"] is None
        assert got["stale"] is None
        assert got["strikes_total"] is None

    def test_unreadable_never_claims_completeness(self):
        """The defect this guards: rendering an unreadable series as a clean one.

        Asserts the PROPERTY, not one phrasing of it — the note must not be able
        to be read as a clean bill of health.
        """
        got = navgap.completeness(None, now=_at("2026-08-26T14:00:00+00:00"))
        assert got["state"] != navgap.STATE_COMPLETE
        assert got["hole_count"] != 0
        assert navgap.warnings(got), "an unreadable record must warn"

    def test_an_empty_history_is_not_complete_when_the_window_had_sessions(self):
        """Zero strikes ever is not a clean record. The generalisation matters:
        the fund's own engine ledger once printed "nothing has ever run, so
        there is no liveness question to answer" over exactly this shape."""
        got = navgap.completeness([], now=_at("2026-08-26T14:00:00+00:00"),
                                  lookback_hours=72)
        assert got["readable"] is True
        assert got["state"] == navgap.STATE_HOLES
        assert got["gaps"][0]["kind"] == "no-strikes-ever"

    def test_an_empty_history_over_a_weekend_only_window_is_complete(self):
        """The null arm of the test above: with no trading time in the window,
        an empty history really has missed nothing, and saying so is honest."""
        got = navgap.completeness([], now=_at("2026-08-23T12:00:00+00:00"),
                                  lookback_hours=24)
        assert got["state"] == navgap.STATE_COMPLETE
        assert got["hole_count"] == 0

    def test_an_unparsable_timestamp_makes_the_series_unreadable(self):
        """A dropped strike MANUFACTURES a gap that never happened. Silently
        skipping the row would invent a hole and blame the fund for it."""
        got = navgap.completeness(
            [{"ts": OUTAGE_BEFORE}, {"ts": "not a timestamp"},
             {"ts": OUTAGE_AFTER}],
            now=_at("2026-08-26T14:00:00+00:00"))
        assert got["state"] == navgap.STATE_UNREADABLE
        assert got["unparsed_strikes"] == 1
        assert got["strikes_total"] == 3

    def test_a_missing_ts_key_counts_as_unparsable(self):
        got = navgap.completeness([{"total_nav_usd": 1.0}],
                                  now=_at("2026-08-26T14:00:00+00:00"))
        assert got["state"] == navgap.STATE_UNREADABLE
        assert got["unparsed_strikes"] == 1

    def test_a_date_outside_the_calendar_is_undetermined_not_clear(self):
        got = navgap.completeness(
            _strikes("2025-06-02T13:00:00+00:00", "2025-06-04T13:00:00+00:00"),
            now=_at("2025-06-04T13:30:00+00:00"))
        assert got["state"] == navgap.STATE_UNDETERMINED
        assert got["gaps"][0]["verdict"] == "undetermined"
        assert got["gaps"][0]["calendar_covered"] is False

    def test_a_confirmed_hole_outranks_an_undetermined_gap(self):
        """Precedence: confirmed bad news is louder than unknown news, and the
        undetermined gap still rides the payload rather than being swallowed."""
        got = navgap.completeness(
            _strikes("2025-06-02T13:00:00+00:00", "2025-06-04T13:00:00+00:00",
                     OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"),
            lookback_hours=24 * 500)
        assert got["state"] == navgap.STATE_HOLES
        assert any(g["verdict"] == "undetermined" for g in got["gaps"])


# ---------------------------------------------------------------- tolerance

class TestToleranceIsReadNotCopied:
    def test_the_tolerance_comes_from_the_heartbeat_budget(self):
        assert navgap.tolerance_seconds() == heartbeat.BUDGETS_SECONDS[
            navgap.TOLERANCE_KEY]

    def test_tolerance_is_read_not_copied(self, monkeypatch):
        """MOVE the budget and watch the verdict follow.

        Asserting equality with the source cannot distinguish a read from a
        hardcoded duplicate that happens to agree today. This moves the number:
        a 2.0-hour trading gap is a hole under a 1h budget and clean under a 3h
        one, and only a genuine read produces both answers.
        """
        strikes = _strikes("2026-08-25T14:00:00+00:00",
                           "2026-08-25T16:00:00+00:00")
        now = _at("2026-08-25T16:01:00+00:00")

        monkeypatch.setitem(heartbeat.BUDGETS_SECONDS, navgap.TOLERANCE_KEY,
                            3600.0)
        tight = navgap.completeness(strikes, now=now)

        monkeypatch.setitem(heartbeat.BUDGETS_SECONDS, navgap.TOLERANCE_KEY,
                            3.0 * 3600.0)
        loose = navgap.completeness(strikes, now=now)

        assert tight["tolerance_seconds"] == 3600.0
        assert loose["tolerance_seconds"] == 10800.0
        assert tight["hole_count"] == 1
        assert loose["hole_count"] == 0

    def test_an_absent_budget_yields_undetermined_never_a_default(self, monkeypatch):
        """No budget means no verdict. Substituting a number of our own here
        would be a threshold nobody versioned, invented inside a reader."""
        monkeypatch.delitem(heartbeat.BUDGETS_SECONDS, navgap.TOLERANCE_KEY)
        got = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"))
        assert got["tolerance_seconds"] is None
        assert got["tolerance_source"] == "absent"
        assert got["state"] == navgap.STATE_UNDETERMINED
        assert got["hole_count"] == 0
        assert got["stale"] is None

    @pytest.mark.parametrize("value", [None, 0, 0.0, -1, "ninety minutes",
                                       float("nan"), object()])
    def test_an_unusable_budget_is_absent_not_zero(self, monkeypatch, value):
        """Every unusable value collapses to ABSENT, never to zero.

        Zero would be the worst of them: a zero budget makes every interval
        between two strikes a hole, and the instrument would scream at a
        perfectly healthy fund on the day someone deleted a number.
        """
        monkeypatch.setitem(heartbeat.BUDGETS_SECONDS, navgap.TOLERANCE_KEY,
                            value)
        assert navgap.tolerance_seconds() is None

    @pytest.mark.parametrize("offset,expected", [
        (-1.0, "ok"),
        (0.0, "ok"),        # STRICTLY greater than the budget is a hole
        (+1.0, "hole"),
    ])
    def test_the_boundary_is_strictly_greater(self, offset, expected):
        """The whole classification rests on one comparison, so it gets a table.

        A gap exactly AT the budget is within budget: the heartbeat's own
        ``status()`` uses ``> budget``, and two definitions of "overdue" is how a
        fund ends up with two answers to one question. The offsets are measured
        against the LIVE budget rather than a copy of it, so moving the budget
        moves this table with it instead of breaking it.
        """
        budget = navgap.tolerance_seconds()
        assert budget is not None
        # Wholly inside one regular session, so trading seconds == wall seconds.
        start = datetime(2026, 8, 25, 14, 0, tzinfo=timezone.utc)
        end = start + timedelta(seconds=budget + offset)
        assert navgap.session_bounds(date(2026, 8, 25))[1] >= end
        got = navgap.completeness(
            [{"ts": start.isoformat()}, {"ts": end.isoformat()}], now=end)
        assert got["gaps"][0]["trading_seconds"] == pytest.approx(
            budget + offset)
        assert got["gaps"][0]["verdict"] == expected


# ---------------------------------------------------------------- staleness

class TestStaleness:
    def test_staleness_is_measured_in_trading_time(self):
        """Overnight is not staleness. The newest strike being 12 hours old at
        06:00 UTC is a closed market, not a dead strike loop."""
        got = navgap.completeness(
            _strikes("2026-08-26T19:55:00+00:00"),
            now=_at("2026-08-27T06:00:00+00:00"))
        assert got["staleness_seconds"] == pytest.approx(10 * 3600 + 5 * 60, abs=1)
        assert got["staleness_trading_seconds"] == pytest.approx(300, abs=1)
        assert got["stale"] is False

    def test_a_missing_closing_mark_is_stale(self):
        """The live case on 2026-08-27: last strike 2026-08-26T17:28Z, the
        session ran to 20:00Z, and no closing mark was ever struck."""
        got = navgap.completeness(
            _strikes("2026-08-26T17:28:19.060139+00:00"),
            now=_at("2026-08-27T06:00:00+00:00"))
        assert got["stale"] is True
        assert got["staleness_trading_seconds"] == pytest.approx(2.53 * 3600,
                                                                 abs=60)

    def test_the_staleness_leg_and_the_gap_list_cannot_disagree(self):
        """One interval, computed once. Two folds over the same interval is how
        a payload ends up contradicting itself on two surfaces."""
        got = navgap.completeness(
            _strikes("2026-08-26T17:28:19.060139+00:00"),
            now=_at("2026-08-27T06:00:00+00:00"))
        tail = [g for g in got["gaps"] if g["kind"] == "since-newest"]
        assert len(tail) == 1
        assert tail[0]["trading_seconds"] == got["staleness_trading_seconds"]


# ------------------------------------------------------------------ window

class TestTheWindow:
    def test_a_hole_straddling_the_window_start_is_still_found(self):
        """The anchor: the last strike BEFORE the window is supplied so a gap
        that begins outside it is still measured. Pre-filtering the history to
        the window is exactly how this hole would be lost."""
        got = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"),
            lookback_hours=1.0)
        assert got["leading_anchor"] == OUTAGE_BEFORE
        assert got["hole_count"] == 1
        assert got["strikes_in_window"] == 1

    def test_strikes_before_the_window_are_not_counted_as_in_it(self):
        got = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"),
            lookback_hours=1.0)
        assert got["strikes_total"] == 2
        assert got["strikes_in_window"] == 1

    def test_no_anchor_when_the_history_begins_inside_the_window(self):
        got = navgap.completeness(
            _strikes(OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"),
            lookback_hours=24 * 365)
        assert got["leading_anchor"] is None

    def test_an_unsorted_history_is_sorted_before_folding(self):
        """Mutant M16: dropping ``parsed.sort()``.

        THIS TEST USED TO PASS AGAINST THAT MUTANT, and the mutation pass is
        what caught it. Unsorted, the pair folds to a zero-length backwards gap
        plus a SINCE-NEWEST leg from the older stamp — which is also 42 hours
        and also a hole, so ``hole_count == 1`` and ``holes[0]['from']`` were
        both satisfied by the defect. The assertions that separate the two are
        ``newest_strike_at`` (the LATEST stamp, not the last element) and the
        hole's KIND: correct is one between-strikes gap, broken is a
        since-newest one.
        """
        got = navgap.completeness(
            _strikes(OUTAGE_AFTER, OUTAGE_BEFORE),
            now=_at("2026-08-26T14:00:00+00:00"))
        assert got["newest_strike_at"] == OUTAGE_AFTER
        assert got["hole_count"] == 1
        assert got["holes"][0]["from"] == OUTAGE_BEFORE
        assert got["holes"][0]["to"] == OUTAGE_AFTER
        assert got["holes"][0]["kind"] == "between-strikes"

    def test_a_strike_exactly_at_the_window_start_is_inside_the_window(self):
        """Mutant M17: ``>=`` to ``>``. One strike, at the boundary, either
        counted or silently demoted to the anchor."""
        start = _at("2026-08-25T14:00:00+00:00")
        got = navgap.completeness(
            _strikes(start.isoformat()),
            now=_at("2026-08-25T15:00:00+00:00"), lookback_hours=1.0)
        assert got["window_start"] == start.isoformat()
        assert got["strikes_in_window"] == 1
        assert got["leading_anchor"] is None

    def test_the_anchor_is_the_LAST_strike_before_the_window(self):
        """Mutant M18: ``before[-1]`` to ``before[0]``.

        With two strikes before the window, the wrong one makes the leading gap
        far larger than it was and invents a hole out of a healthy stretch.
        """
        got = navgap.completeness(
            _strikes("2026-08-25T13:35:00+00:00",
                     "2026-08-25T14:30:00+00:00",
                     "2026-08-25T15:10:00+00:00"),
            now=_at("2026-08-25T15:20:00+00:00"), lookback_hours=0.5)
        assert got["leading_anchor"] == "2026-08-25T14:30:00+00:00"
        assert got["hole_count"] == 0

    def test_holes_are_ordered_worst_first(self):
        """Mutant M22: dropping ``reverse=True``.

        The note names ``holes[0]``, so the order decides which hole a human is
        told about. Two holes here, deliberately different sizes.
        """
        got = navgap.completeness(
            _strikes("2026-08-25T13:30:00+00:00",   # then a 2h hole
                     "2026-08-25T15:30:00+00:00",
                     "2026-08-25T19:59:00+00:00",   # then a 4.5h hole
                     "2026-08-26T13:31:00+00:00"),
            now=_at("2026-08-26T13:32:00+00:00"))
        assert got["hole_count"] == 2
        seconds = [h["trading_seconds"] for h in got["holes"]]
        assert seconds == sorted(seconds, reverse=True)
        assert got["holes"][0]["from"] == "2026-08-25T15:30:00+00:00"

    def test_a_naive_timestamp_is_read_as_utc(self):
        """The log is UTC-only. Reading a naive stamp as host-local would move
        every gap by the machine's offset — and the answer would change with
        the machine."""
        aware = navgap.completeness(_strikes("2026-08-25T14:00:00+00:00"),
                                    now=_at("2026-08-25T15:00:00+00:00"))
        naive = navgap.completeness(_strikes("2026-08-25T14:00:00"),
                                    now=_at("2026-08-25T15:00:00+00:00"))
        assert naive["newest_strike_at"] == aware["newest_strike_at"]

    def test_a_z_suffix_parses(self):
        got = navgap.completeness(_strikes("2026-08-25T14:00:00Z"),
                                  now=_at("2026-08-25T15:00:00+00:00"))
        assert got["state"] != navgap.STATE_UNREADABLE


# ----------------------------------------------------------------- summary

class TestSummaryAndWarnings:
    def test_the_summary_is_derived_and_never_refolds(self):
        report = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00"))
        got = navgap.summary(report)
        assert got["state"] == report["state"]
        assert got["hole_count"] == report["hole_count"]
        assert got["gaps_measured"] == len(report["gaps"])
        assert "gaps" not in got

    def test_the_hole_cap_publishes_both_numbers(self):
        """HW1's lesson: a list that agrees with a count agrees only inside the
        cap. Name the cap, say whether it bound."""
        # 2026-06-01 is a Monday; 6/7 and 13/14 are weekends, so this is twelve
        # trading days, each carrying one 6.5-hour intraday hole.
        many = []
        for day in range(1, 17):
            many.append(f"2026-06-{day:02d}T13:30:00+00:00")
            many.append(f"2026-06-{day:02d}T19:59:00+00:00")
        report = navgap.completeness(_strikes(*many),
                                     now=_at("2026-06-16T20:00:00+00:00"),
                                     lookback_hours=24 * 30)
        got = navgap.summary(report)
        assert report["hole_count"] > navgap.SUMMARY_HOLE_LIMIT
        assert got["holes_shown"] == navgap.SUMMARY_HOLE_LIMIT
        assert got["holes_capped"] is True
        assert got["hole_count"] == report["hole_count"]

    def test_the_cap_flag_is_false_at_EXACTLY_the_limit(self):
        """The boundary the 12-hole fixture above cannot see.

        Found by the Gauntlet: flipping ``>`` to ``>=`` in ``holes_capped`` left
        the whole suite green, because every fixture sat well above the limit.
        Ten holes shown out of ten held is not a capped list.
        """
        many = []
        for day in range(1, 15):        # 2026-06-01 Mon; 6/7 and 13/14 weekends
            many.append(f"2026-06-{day:02d}T13:30:00+00:00")
            many.append(f"2026-06-{day:02d}T19:59:00+00:00")
        report = navgap.completeness(_strikes(*many),
                                     now=_at("2026-06-14T20:00:00+00:00"),
                                     lookback_hours=24 * 30)
        assert report["hole_count"] == navgap.SUMMARY_HOLE_LIMIT
        got = navgap.summary(report)
        assert got["holes_shown"] == navgap.SUMMARY_HOLE_LIMIT
        assert got["holes_capped"] is False

    def test_the_blank_shape_and_the_real_shape_carry_THE_SAME_KEYS(self):
        """A payload whose shape depends on which branch produced it hands every
        consumer two contracts wearing one name.

        Found by the Gauntlet: the last-resort payload carried 10 keys where
        every other path carried 19, so eleven fields were ABSENT rather than
        null on the one path a reader most needs to interpret.
        """
        real = navgap.summary(navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T14:00:00+00:00")))
        blank = navgap.blank_summary("the reader could not run")
        assert set(blank) == set(real) == set(navgap.SUMMARY_KEYS)

    def test_the_blank_shape_can_never_be_read_as_clean(self):
        blank = navgap.blank_summary("the reader could not run")
        assert blank["state"] == navgap.STATE_UNREADABLE
        assert blank["readable"] is False
        assert blank["hole_count"] is None
        assert blank["stale"] is None
        assert [w["key"] for w in blank["warnings"]] == ["nav_record_unreadable"]

    def test_the_blank_shape_computes_nothing(self, monkeypatch):
        """It exists for the case where the reader raised, so it must not call
        the reader. Poison every function it could reach and it still returns."""
        def poison(*a, **k):
            raise AssertionError("blank_summary must not compute anything")
        monkeypatch.setattr(navgap, "completeness", poison)
        monkeypatch.setattr(navgap, "trading_overlap", poison)
        monkeypatch.setattr(navgap, "tolerance_seconds", poison)
        assert navgap.blank_summary("x")["state"] == navgap.STATE_UNREADABLE

    def test_a_clean_record_warns_about_nothing(self):
        """An EMPTY warnings list is a measured zero — it looked."""
        report = navgap.completeness(
            _strikes(WEEKEND_BEFORE, WEEKEND_AFTER),
            now=_at("2026-08-24T14:00:00+00:00"))
        assert navgap.warnings(report) == []

    def test_an_unreadable_record_warns_and_says_only_that(self):
        report = navgap.completeness(None, now=_at("2026-08-26T14:00:00+00:00"))
        got = navgap.warnings(report)
        assert [w["key"] for w in got] == ["nav_record_unreadable"]

    def test_a_stale_strike_and_a_hole_are_two_separate_warnings(self):
        report = navgap.completeness(
            _strikes(OUTAGE_BEFORE, OUTAGE_AFTER),
            now=_at("2026-08-26T18:00:00+00:00"))
        keys = [w["key"] for w in navgap.warnings(report)]
        assert "nav_strike_stale" in keys
        assert "nav_record_holes" in keys

    def test_unknown_staleness_warns_rather_than_passing_quietly(self, monkeypatch):
        monkeypatch.delitem(heartbeat.BUDGETS_SECONDS, navgap.TOLERANCE_KEY)
        report = navgap.completeness(
            _strikes("2026-08-26T17:28:19+00:00"),
            now=_at("2026-08-27T06:00:00+00:00"))
        keys = [w["key"] for w in navgap.warnings(report)]
        assert "nav_strike_staleness_unknown" in keys

    def test_an_undetermined_record_warns_by_its_own_name(self):
        """Mutant M33: dropping the UNDETERMINED warning.

        A gap the calendar cannot judge must not leave the liveness payload
        silent — silence there is indistinguishable from a clean record, which
        is the exact collapse this module exists to prevent.
        """
        report = navgap.completeness(
            _strikes("2025-06-02T13:00:00+00:00", "2025-06-04T13:00:00+00:00"),
            now=_at("2025-06-04T13:30:00+00:00"))
        assert report["state"] == navgap.STATE_UNDETERMINED
        keys = [w["key"] for w in navgap.warnings(report)]
        assert "nav_record_undetermined" in keys
