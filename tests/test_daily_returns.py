"""The gate's data path — aligned daily returns, undownsampled.

Adversary round 4, recommendation 4, CEO-accepted 2026-08-21: gate v5 cannot
compute a premia statistic from what the belt stores today, because every curve
is thinned to 400 points for DRAWING before it is saved. A 5.47-year run loses
roughly two thirds of its observations to a decision made for a chart.

`gate.py` is NOT touched by any of this. The data is captured; what judges it is
a separate, versioned change.
"""

import math

from app.fund.leanrunner import _daily_returns
from app.fund import runanalytics as ra


def test_returns_are_differenced_from_the_levels():
    got = _daily_returns([100, 110, 99], ["d1", "d2", "d3"],
                         [10, 11, 10], ["d1", "d2", "d3"])
    assert got["present"] is True
    assert got["dates"] == ["d2", "d3"]
    assert got["strategy"] == [0.1, -0.1]
    assert abs(got["benchmark"][0] - 0.1) < 1e-9
    assert got["n"] == 2


def test_the_two_legs_are_aligned_BY_DATE_not_by_index():
    """THE correctness property. The series come from different engine charts
    and are not guaranteed to be the same length; a positional zip pairs
    Tuesday's strategy with Wednesday's benchmark and every downstream beta is
    then wrong by one day."""
    got = _daily_returns([100, 110, 99], ["d1", "d2", "d3"],
                         [10, 11], ["d1", "d3"])
    # d2 has no benchmark, so it is dropped rather than paired with d3's.
    assert got["dates"] == ["d3"]
    assert got["dropped_unmatched_days"] == 1
    assert "dropped rather than zero-filled" in got["note"]


def test_an_unmatched_day_is_DROPPED_never_zero_filled():
    """Carrying it with a zero on the missing side invents a flat day for an
    instrument that did not trade."""
    got = _daily_returns([100, 110, 121], ["d1", "d2", "d3"],
                         [10, 11], ["d1", "d2"])
    assert 0.0 not in got["benchmark"]
    assert len(got["strategy"]) == len(got["benchmark"])


def test_a_missing_benchmark_is_ABSENT_not_flat():
    got = _daily_returns([100, 110], ["d1", "d2"], [], [])
    assert got["benchmark_present"] is False
    assert got["benchmark"] == []
    assert "ABSENT rather than flat" in got["note"]
    # The strategy leg still comes back — half a series is better than none, so
    # long as the half is named.
    assert got["strategy"] == [0.1]


def test_a_zero_or_negative_level_breaks_the_chain_rather_than_dividing():
    got = _daily_returns([100, 0, 50, 55], ["d1", "d2", "d3", "d4"], [], [])
    assert all(math.isfinite(r) for r in got["strategy"])
    assert got["strategy"] == [0.1]      # only d3 -> d4 survives


def test_a_curve_without_dates_is_absent_not_empty():
    got = _daily_returns([100, 110], [], [], [])
    assert got["present"] is False
    assert "absent, not empty" in got["reason"]


def test_a_single_point_cannot_be_differenced():
    assert _daily_returns([100], ["d1"], [], [])["present"] is False


def test_the_series_is_NOT_downsampled():
    """The whole point. 400 is the chart cap; a longer run must keep every
    observation."""
    n = 1400
    dates = [f"2020-01-{i:04d}" for i in range(n)]
    levels = [100.0 * (1.001 ** i) for i in range(n)]
    got = _daily_returns(levels, dates, levels, dates)
    assert got["n"] == n - 1
    assert got["n"] > 400


# --- the envelope carries them ----------------------------------------------


def _series(n=3):
    return {"present": True, "dates": [f"d{i}" for i in range(n)],
            "strategy": [0.01] * n, "benchmark": [0.005] * n,
            "benchmark_present": True, "n": n, "dropped_unmatched_days": 0}


def test_the_capture_envelope_preserves_every_leg():
    a = ra.capture(
        job={"job_id": "j", "state": "done",
             "result": {"daily_returns": _series(5), "orders": []}},
        sweep={"sweep_id": "s", "holdout_result": {
            "state": "done",
            "test": {"daily_returns": _series(4)},
            "daily_returns_note": "test leg captured; TRAIN leg NOT captured"}},
        walkforward={"folds": [
            {"fold": 1, "measurable": True, "daily_returns": _series(3)},
            {"fold": 2, "measurable": True, "daily_returns": _series(3)},
        ]})
    got = ra.daily_return_legs(a)
    assert got["captured"] == ["fold_1_test", "fold_2_test", "holdout_test",
                               "verification"]
    assert got["total_observations"] == 5 + 4 + 3 + 3
    assert got["missing"] == []
    assert got["legs"]["verification"]["n"] == 5


def test_a_leg_that_captured_NOTHING_is_named_missing():
    """A premia statistic computed over three legs when five were expected must
    be visibly that, rather than silently narrower."""
    a = ra.capture(
        job={"job_id": "j", "state": "done", "result": {"orders": []}},
        sweep={"sweep_id": "s", "holdout_result": {"state": "done", "test": {}}},
        walkforward={"folds": [{"fold": 1, "measurable": False}]})
    got = ra.daily_return_legs(a)
    assert got["captured"] == []
    assert "verification" in got["missing"]
    assert "holdout_test" in got["missing"]
    assert "fold_1_test" in got["missing"]
    assert "NOT captured" in got["note"]


def test_the_train_legs_absence_is_stated_in_every_note():
    """It is a deliberate half, not an oversight, and the payload says which."""
    got = ra.daily_return_legs(ra.capture(job=None, sweep=None, walkforward=None))
    assert "Train legs are never captured" in got["note"]


def test_a_leg_without_a_benchmark_is_counted_but_not_claimed():
    s = _series(3)
    s["benchmark_present"] = False
    s["benchmark"] = []
    a = ra.capture(job={"job_id": "j", "state": "done",
                        "result": {"daily_returns": s, "orders": []}},
                   sweep=None, walkforward=None)
    got = ra.daily_return_legs(a)
    assert "verification" in got["captured"]
    assert got["legs_with_benchmark"] == []
