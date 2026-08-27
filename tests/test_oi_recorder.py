"""The open-interest recorder — the fold, and the four ways it could lie.

WHY THIS FILE EXISTS. Binance serves ``openInterestHist`` on a **30-day rolling
window**, so every unpolled day destroys a day of history nothing buys back.
A collector for that job has exactly four ways to fail quietly, and this file is
one section per way:

  * append the same point twice, so a series double-counts (``TestIdempotent``);
  * absorb a RESTATED value silently, so a source that changed its mind about a
    settled number leaves no trace (``TestConflictsAreNeverAbsorbed``);
  * report a hole as coverage (``TestCoverageReportsGaps``);
  * read an EMPTY RESPONSE as "nothing new" when an unknown symbol answers with
    exactly the same bytes at HTTP 200 (``TestEmptyIsNotUpToDate``).

Every test here is offline. The live-API claims this module rests on are
measured by ``--selftest`` and by the probes named in its docstring, not by a
unit test that would go red whenever the internet does.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts", "data"))

import oi_recorder as R  # noqa: E402


def api_row(ts_ms, oi="100.0", value="1000.0", supply="20000000.0"):
    return {"symbol": "BTCUSDT", "sumOpenInterest": oi,
            "sumOpenInterestValue": value, "CMCCirculatingSupply": supply,
            "timestamp": ts_ms}


def stored(ts_ms, oi="100.0", period="1h", observed_at="2026-08-27T06:00:00+00:00"):
    return R.normalise(api_row(ts_ms, oi=oi), period, observed_at)


H = 3_600_000
T0 = 1_787_788_800_000  # 2026-08-27T00:00:00Z


# --------------------------------------------------------------- normalise

class TestNormalise:
    def test_carries_the_api_fields_verbatim(self):
        got = R.normalise(api_row(T0), "1h", "2026-08-27T01:00:00+00:00")
        assert got["sumOpenInterest"] == "100.0"
        assert got["timestamp"] == T0
        assert got["at"] == "2026-08-27T00:00:00+00:00"
        assert got["period"] == "1h"
        assert got["observed_at"] == "2026-08-27T01:00:00+00:00"

    def test_when_it_happened_and_when_we_saw_it_are_different_fields(self):
        """A series whose rows cannot say when they were collected cannot later
        answer "was this watched live or backfilled from the rolling window"."""
        got = R.normalise(api_row(T0), "1h", "2026-08-29T00:00:00+00:00")
        assert got["at"] != got["observed_at"]

    @pytest.mark.parametrize("bad", [{}, {"timestamp": None},
                                     {"timestamp": "yesterday"}])
    def test_a_row_without_a_usable_timestamp_is_dropped_not_guessed(self, bad):
        assert R.normalise(bad, "1h", "x") is None

    def test_a_missing_value_field_is_absent_not_zero(self):
        row = api_row(T0)
        del row["CMCCirculatingSupply"]
        got = R.normalise(row, "1h", "x")
        assert "CMCCirculatingSupply" not in got


# --------------------------------------------------------------- idempotency

class TestIdempotent:
    def test_a_second_run_appends_nothing(self):
        """The acceptance: two consecutive runs produce zero duplicates."""
        rows = [stored(T0), stored(T0 + H), stored(T0 + 2 * H)]
        again = R.merge(rows, rows)
        assert again["new"] == []
        assert again["duplicates"] == 3
        assert again["conflicts"] == []

    def test_only_the_genuinely_new_points_are_appended(self):
        held = [stored(T0), stored(T0 + H)]
        served = [stored(T0), stored(T0 + H), stored(T0 + 2 * H)]
        got = R.merge(held, served)
        assert [r["timestamp"] for r in got["new"]] == [T0 + 2 * H]
        assert got["duplicates"] == 2

    def test_a_duplicate_inside_one_response_is_folded_once(self):
        """Mutant: keying on the incoming list's position rather than on the
        timestamp lets one malformed response double every point."""
        got = R.merge([], [stored(T0), stored(T0)])
        assert len(got["new"]) == 1

    def test_the_key_is_the_timestamp_not_the_period(self):
        """MEASURED: ``period`` is a sampling grid, not an aggregation — the 1h
        and 5m series carry identical values at identical timestamps. So the
        same instant seen through a different grid is the SAME observation, and
        recording it twice would invent a point."""
        got = R.merge([stored(T0, period="1h")], [stored(T0, period="5m")])
        assert got["new"] == []
        assert got["duplicates"] == 1

    def test_a_corrupt_stored_line_does_not_become_a_key(self):
        got = R.merge([{"_unreadable": "}}}"}], [stored(T0)])
        assert len(got["new"]) == 1


# --------------------------------------------------------------- conflicts

class TestConflictsAreNeverAbsorbed:
    def test_a_restated_value_is_a_conflict_not_a_duplicate(self):
        """A settled point coming back DIFFERENT is a fact about the source.

        Mutant: comparing on the timestamp alone makes this a duplicate and the
        disagreement vanishes — the series would then silently contain whichever
        version arrived first, with nothing anywhere saying there were two.
        """
        got = R.merge([stored(T0, oi="100.0")], [stored(T0, oi="101.0")])
        assert got["new"] == []
        assert got["duplicates"] == 0
        assert len(got["conflicts"]) == 1
        c = got["conflicts"][0]
        assert c["held"]["sumOpenInterest"] == "100.0"
        assert c["served"]["sumOpenInterest"] == "101.0"

    def test_the_stored_value_wins_and_the_conflict_is_reported(self):
        got = R.merge([stored(T0, oi="100.0")], [stored(T0, oi="101.0")])
        assert got["new"] == [], "a conflict must never be appended as a point"

    @pytest.mark.parametrize("field", R.VALUE_FIELDS)
    def test_every_value_field_can_raise_a_conflict(self, field):
        """Enumerated by name rather than compared as a blob: a field dropped
        from VALUE_FIELDS would otherwise silently stop being watched."""
        held = stored(T0)
        served = dict(stored(T0))
        served[field] = "999999.0"
        got = R.merge([held], [served])
        assert len(got["conflicts"]) == 1

    def test_a_different_observed_at_is_not_a_conflict(self):
        """Seeing the same point again later is the NORMAL case. Only the
        VALUES disagreeing is a finding."""
        a = stored(T0, observed_at="2026-08-27T06:00:00+00:00")
        b = stored(T0, observed_at="2026-08-28T06:00:00+00:00")
        got = R.merge([a], [b])
        assert got["conflicts"] == []
        assert got["duplicates"] == 1


# --------------------------------------------------------------- coverage

class TestCoverageReportsGaps:
    def test_a_contiguous_series_has_no_gaps(self):
        rows = [stored(T0 + i * H) for i in range(5)]
        got = R.coverage(rows, "1h")
        assert got["points"] == 5
        assert got["gaps"] == []
        assert got["missing_points"] == 0
        assert got["complete"] is True

    def test_a_hole_is_reported_with_how_many_points_are_missing(self):
        """The acceptance: a gap in coverage is REPORTED, not silent."""
        rows = [stored(T0), stored(T0 + H), stored(T0 + 12 * H)]
        got = R.coverage(rows, "1h")
        assert got["complete"] is False
        assert len(got["gaps"]) == 1
        assert got["gaps"][0]["missing_points"] == 10
        assert got["missing_points"] == 10
        assert got["gaps"][0]["hours"] == 11.0

    def test_an_empty_store_is_not_complete(self):
        """Zero points is a series with nothing in it, not a clean one.

        Mutant: returning ``complete: True`` for an empty store makes a
        collector that has never run report perfect coverage.
        """
        got = R.coverage([], "1h")
        assert got["complete"] is None
        assert got["points"] == 0
        assert got["missing_points"] is None

    def test_an_unsorted_store_is_sorted_before_measuring(self):
        rows = [stored(T0 + 3 * H), stored(T0), stored(T0 + H)]
        got = R.coverage(rows, "1h")
        assert got["gaps"][0]["missing_points"] == 1

    def test_a_period_with_no_declared_step_cannot_count_gaps_and_says_so(self):
        got = R.coverage([stored(T0), stored(T0 + 99 * H)], "3h")
        assert got["complete"] is None
        assert got["missing_points"] is None
        assert "cannot be counted" in got["note"]

    def test_the_step_matches_the_period_not_a_constant(self):
        """Mutant: hardcoding an hourly step makes every 5m series look like a
        continuous run of holes."""
        rows = [stored(T0), stored(T0 + 300_000)]
        assert R.coverage(rows, "5m")["gaps"] == []
        assert R.coverage(rows, "1h")["gaps"] == []
        assert R.PERIOD_SECONDS["5m"] == 300


# --------------------------------------------------------------- settled

class TestSettleMargin:
    def test_the_default_margin_keeps_everything(self):
        """The default is the MEASUREMENT — these rows are snapshots and do not
        mutate — not an oversight."""
        rows = [stored(T0), stored(T0 + H)]
        kept, dropped = R.settled(rows, now_ms=T0 + H, margin_seconds=0)
        assert dropped == 0
        assert len(kept) == 2

    def test_a_margin_withholds_only_the_young_rows(self):
        rows = [stored(T0), stored(T0 + H)]
        kept, dropped = R.settled(rows, now_ms=T0 + H + 60_000,
                                  margin_seconds=600)
        assert dropped == 1
        assert [r["timestamp"] for r in kept] == [T0]

    def test_the_boundary_row_at_exactly_the_margin_is_kept(self):
        rows = [stored(T0)]
        kept, dropped = R.settled(rows, now_ms=T0 + 600_000,
                                  margin_seconds=600)
        assert dropped == 0

    def test_a_zero_margin_keeps_even_a_future_stamped_row(self):
        """Mutant: ``margin_seconds <= 0`` to ``< 0``.

        With the mutant, margin 0 still runs the cutoff and quietly withholds a
        row stamped ahead of our clock. Withholding is the MARGIN's job; the
        default's job is to record what the source served, including a stamp we
        find surprising — a collector that silently drops the surprising row
        destroys the evidence that the source produced one.
        """
        rows = [stored(T0 + H)]
        kept, dropped = R.settled(rows, now_ms=T0, margin_seconds=0)
        assert dropped == 0
        assert len(kept) == 1


# --------------------------------------------------------------- absence

class TestEmptyIsNotUpToDate:
    def test_an_unknown_symbol_is_named_as_a_typo_not_an_outage(self, monkeypatch):
        """MEASURED: ``symbol=NOTASYMBOL`` returns ``[]`` at HTTP 200 — the same
        bytes as a real outage. The venue's symbol list is what separates them.
        """
        monkeypatch.setattr(R, "fetch", lambda *a, **k: pytest.fail(
            "must not call the API for a symbol the venue does not list"))
        got = R.record_symbol("NOTASYMBOL", root="/nowhere", period="1h",
                              limit=10, margin_seconds=0,
                              known={"BTCUSDT"}, dry_run=True)
        assert got["state"] == "unknown_symbol"

    def test_an_empty_response_for_a_valid_symbol_is_a_refusal(self, monkeypatch,
                                                               tmp_path):
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [])
        got = R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                              limit=10, margin_seconds=0, known={"BTCUSDT"},
                              dry_run=True)
        assert got["state"] == "served_nothing"
        assert "appended" not in got

    def test_an_unreadable_symbol_list_is_said_out_loud(self, monkeypatch,
                                                        tmp_path):
        """None from ``tradable_symbols`` is a THIRD state. Collapsing it into
        "the symbol is fine" would let a typo record nothing forever, quietly.
        """
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [])
        got = R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                              limit=10, margin_seconds=0, known=None,
                              dry_run=True)
        assert got["state"] == "served_nothing_symbol_unverified"
        assert "UNREADABLE" in got["note"]

    def test_a_transport_failure_is_unreadable_not_empty(self, monkeypatch,
                                                         tmp_path):
        def boom(*a, **k):
            raise OSError("network down")
        monkeypatch.setattr(R, "fetch", boom)
        got = R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                              limit=10, margin_seconds=0, known={"BTCUSDT"},
                              dry_run=True)
        assert got["state"] == "unreadable"
        assert "network down" in got["note"]

    def test_verify_on_a_store_that_does_not_exist_says_absent(self, tmp_path):
        got = R.verify_symbol("BTCUSDT", root=str(tmp_path), period="1h")
        assert got["state"] == "absent"
        assert "nothing has ever been recorded" in got["note"]

    def test_an_error_object_at_http_200_is_raised_not_stored(self, monkeypatch):
        """Binance reports its own errors as a 200 with a code/msg object.
        Iterating that dict would store its KEYS as rows."""
        monkeypatch.setattr(R, "_get", lambda *a, **k: {
            "code": -1130, "msg": "parameter 'startTime' is invalid."})
        with pytest.raises(RuntimeError, match="binance refused"):
            R.fetch("BTCUSDT", "1h", 10)


# --------------------------------------------------------------- storage

class TestStorage:
    def test_round_trip_through_jsonl(self, tmp_path):
        path = R.store_path(str(tmp_path), "BTCUSDT")
        R.append_jsonl(path, [stored(T0), stored(T0 + H)])
        back = R.read_jsonl(path)
        assert [r["timestamp"] for r in back] == [T0, T0 + H]

    def test_a_corrupt_line_is_surfaced_not_skipped(self, tmp_path):
        """Skipping it would make the held count silently wrong, and the next
        run would re-append a point the file already has."""
        path = R.store_path(str(tmp_path), "BTCUSDT")
        R.append_jsonl(path, [stored(T0)])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("{not json\n")
        back = R.read_jsonl(path)
        assert len(back) == 2
        assert "_unreadable" in back[1]

    def test_a_second_record_run_writes_no_new_lines(self, monkeypatch, tmp_path):
        """End to end on the real fold: run twice, count the file's lines."""
        rows = [api_row(T0 + i * H) for i in range(4)]
        monkeypatch.setattr(R, "fetch", lambda *a, **k: rows)
        for _ in range(2):
            R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                            limit=10, margin_seconds=0, known={"BTCUSDT"},
                            dry_run=False)
        path = R.store_path(str(tmp_path), "BTCUSDT")
        with open(path, encoding="utf-8") as fh:
            assert len([ln for ln in fh if ln.strip()]) == 4

    def test_a_dry_run_writes_nothing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0)])
        got = R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                              limit=10, margin_seconds=0, known={"BTCUSDT"},
                              dry_run=True)
        assert got["state"] == "dry_run"
        assert got["appended"] == 1
        assert not os.path.exists(R.store_path(str(tmp_path), "BTCUSDT"))

    def test_a_conflict_lands_in_the_sidecar_and_not_in_the_series(
            self, monkeypatch, tmp_path):
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0, oi="1.0")])
        R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h", limit=10,
                        margin_seconds=0, known={"BTCUSDT"}, dry_run=False)
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0, oi="2.0")])
        got = R.record_symbol("BTCUSDT", root=str(tmp_path), period="1h",
                              limit=10, margin_seconds=0, known={"BTCUSDT"},
                              dry_run=False)
        assert got["conflicts"] == 1
        series = R.read_jsonl(R.store_path(str(tmp_path), "BTCUSDT"))
        assert [r["sumOpenInterest"] for r in series] == ["1.0"]
        side = R.read_jsonl(R.conflict_path(str(tmp_path), "BTCUSDT"))
        assert len(side) == 1
        assert side[0]["served"]["sumOpenInterest"] == "2.0"
        assert side[0]["detected_at"]

    def test_the_store_is_utf8_regardless_of_the_host_default(self, tmp_path):
        """This host's default text encoding is cp1252 and it raises on bytes
        the API itself serves. Every read and write here states utf-8."""
        path = R.store_path(str(tmp_path), "BTCUSDT")
        row = stored(T0)
        row["note"] = "— an em dash é"
        R.append_jsonl(path, [row])
        with open(path, "rb") as fh:
            raw = fh.read()
        assert json.loads(raw.decode("utf-8"))["note"] == row["note"]


# --------------------------------------------------------------- the exits

class TestExitCodes:
    def test_verify_exits_zero_even_with_gaps(self, monkeypatch, tmp_path,
                                              capsys):
        """A gap is a FINDING, not a crash. A scheduled --verify that exits
        non-zero on a known hole trains its reader to ignore it."""
        path = R.store_path(str(tmp_path), "BTCUSDT")
        R.append_jsonl(path, [stored(T0), stored(T0 + 12 * H)])
        code = R.main(["--verify", "--symbols", "BTCUSDT",
                       "--root", str(tmp_path)])
        assert code == 0
        assert "GAP" in capsys.readouterr().out

    def test_a_recording_run_exits_nonzero_when_a_symbol_could_not_be_read(
            self, monkeypatch, tmp_path):
        monkeypatch.setattr(R, "tradable_symbols", lambda: {"BTCUSDT"})

        def boom(*a, **k):
            raise OSError("down")
        monkeypatch.setattr(R, "fetch", boom)
        assert R.main(["--symbols", "BTCUSDT", "--root", str(tmp_path)]) == 1

    def test_a_clean_recording_run_exits_zero(self, monkeypatch, tmp_path):
        monkeypatch.setattr(R, "tradable_symbols", lambda: {"BTCUSDT"})
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0)])
        assert R.main(["--symbols", "BTCUSDT", "--root", str(tmp_path)]) == 0

    def test_a_run_that_recorded_a_CONFLICT_exits_nonzero(self, monkeypatch,
                                                          tmp_path):
        """Mutant: dropping ``or r.get("conflicts")`` from the failure test.

        The run SUCCEEDED in the ordinary sense — it fetched, it appended
        nothing, it wrote a sidecar — so ``state == "recorded"`` on its own
        would exit 0 and the scheduled wrapper would log OK over a source that
        restated a settled number. A conflict is the one thing here worth
        waking someone for.
        """
        monkeypatch.setattr(R, "tradable_symbols", lambda: {"BTCUSDT"})
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0, oi="1.0")])
        assert R.main(["--symbols", "BTCUSDT", "--root", str(tmp_path)]) == 0
        monkeypatch.setattr(R, "fetch", lambda *a, **k: [api_row(T0, oi="2.0")])
        assert R.main(["--symbols", "BTCUSDT", "--root", str(tmp_path)]) == 1
