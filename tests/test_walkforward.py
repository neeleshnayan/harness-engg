"""Walk-forward: one holdout is one draw, and an unmeasurable fold is not a zero.

The property under test throughout: a fold that could not produce a retention
figure must say why, and must never contribute a number to the distribution.
Collapsing "never traded", "crashed" and "lost money in training" into 0% would
make a strategy nobody examined look identical to one that was examined and
failed — and would let a thin result pass for a robust one.
"""

import pytest

from app.fund.walkforward import (RETENTION_FLOOR, folds, retention,
                                  summarise, window_for)


def test_folds_do_not_overlap_their_test_legs():
    """Overlapping tests count the same days twice, so one lucky patch would
    look like several independent successes."""
    w = folds("2024-01-01", "2026-08-14", train_days=252, test_days=63)
    assert len(w) >= 2
    for a, b in zip(w, w[1:]):
        assert a["test_end"] <= b["test_start"]
    for f in w:
        assert f["train_end"] < f["test_start"], "training must end before the exam"


def test_folds_never_run_past_the_data():
    w = folds("2025-01-01", "2025-12-31", train_days=252, test_days=63)
    assert all(f["test_end"] <= "2025-12-31" for f in w)


def test_a_fold_that_placed_no_trades_is_not_zero_retention():
    """Warm-up starvation produces a flat zero that looks exactly like a lost
    edge. The gate learned this the hard way; the folds must not relearn it."""
    out = retention(train_return=20.0, test_return=0.0, test_orders=0)
    assert out["retention"] is None
    assert out["measurable"] is False
    assert "no trades" in out["reason"]


def test_a_negative_training_leg_has_no_retention_to_measure():
    """test/train with a negative denominator inverts sign: a fold that lost
    money in BOTH legs would report positive retention and read as a success."""
    out = retention(train_return=-10.0, test_return=-5.0, test_orders=12)
    assert out["retention"] is None
    assert "no edge to retain" in out["reason"]


def test_a_missing_return_is_unmeasured_not_zero():
    out = retention(train_return=20.0, test_return=None, test_orders=8)
    assert out["retention"] is None
    assert "unmeasured" in out["reason"]


def test_a_real_fold_measures_the_ratio():
    out = retention(train_return=20.0, test_return=12.0, test_orders=30)
    assert out["measurable"] is True
    assert out["retention"] == pytest.approx(0.6)


def _fold(ret, measurable=True, reason=None):
    return {"retention": ret, "measurable": measurable, "reason": reason}


def test_the_summary_reports_its_own_denominator():
    """A median over two folds when four were attempted is a different claim
    from a median over four, and hiding that is how thin passes for robust."""
    out = summarise([_fold(0.8), _fold(0.6),
                     _fold(None, False, "the test leg placed no trades"),
                     _fold(None, False, "unmeasured")])
    assert out["folds_attempted"] == 4
    assert out["folds_measurable"] == 2
    assert out["folds_unmeasurable"] == 2
    assert "could not be measured" in out["verdict"]


def test_consistent_retention_across_folds_is_said_plainly():
    out = summarise([_fold(0.9), _fold(0.7), _fold(0.6)])
    assert out["folds_retained"] == 3
    assert out["median_retention"] == pytest.approx(0.7)
    assert "all 3" in out["verdict"]


def test_one_good_fold_among_bad_ones_is_called_inconsistent():
    """This is precisely what a single flattering window looks like from the
    inside, and the reason a one-window verdict is weak evidence."""
    out = summarise([_fold(1.2), _fold(0.1), _fold(-0.3), _fold(0.05)])
    assert out["folds_retained"] == 1
    assert "inconsistent" in out["verdict"]


def test_no_measurable_fold_is_an_absence_of_evidence():
    out = summarise([_fold(None, False, "the test leg placed no trades"),
                     _fold(None, False, "the test leg placed no trades")])
    assert out["median_retention"] is None
    assert out["folds_retained"] == 0
    assert "absence of evidence" in out["verdict"]


def test_the_floor_matches_the_gate():
    """A per-fold bar different from the gate's would make the two disagree
    about the same strategy."""
    from app.fund.gate import CRITERIA
    assert RETENTION_FLOOR == CRITERIA["min_holdout_retention"]


def test_a_near_zero_training_edge_has_no_meaningful_retention():
    """From the null audit: a random strategy trained at +3.7%, tested at +50.5%,
    and reported "kept 1379% of its edge" — clearing a 50% floor on a denominator
    too small to divide by. A tiny positive edge is as unusable as a negative one.
    """
    from app.fund.walkforward import MIN_TRAIN_RETURN_PCT
    out = retention(train_return=3.66, test_return=50.5, test_orders=40)
    assert out["retention"] is None
    assert out["measurable"] is False
    assert "near-zero denominator" in out["reason"]
    # A judgement, not a measurement: below this an "edge" sits under the
    # benchmark and inside single-name noise, so its persistence means nothing.
    assert MIN_TRAIN_RETURN_PCT == 5.0


def test_the_window_fits_the_number_of_folds_the_gate_demands():
    """The bug this closes made gate v2 unclearable by anything.

    Folds were sized from the CALLER'S holdout. The audits used 2025-01-01 to
    2026-08-14, which fits two folds, while the gate asks for three — so every
    candidate failed with "the consistency test did not run" regardless of
    quality, and the sentence described our arithmetic rather than the strategy.
    """
    from app.fund.gate import CRITERIA
    need = CRITERIA["min_walkforward_folds"]
    w = window_for("2026-08-14", min_folds=need, floor="2024-02-26")
    assert len(w) >= need, f"only {len(w)} folds for a {need}-fold requirement"


def test_the_window_never_runs_past_its_end():
    w = window_for("2026-08-14", min_folds=3, floor="2024-02-26")
    assert all(f["test_end"] <= "2026-08-14" for f in w)


def test_the_window_respects_the_history_floor():
    """Reaching before the first bar is not harmful — such a fold places no
    trades and is reported unmeasurable — but it spends engine time on runs that
    cannot say anything."""
    w = window_for("2026-08-14", min_folds=3, floor="2025-06-01")
    assert all(f["train_start"] >= "2025-06-01" for f in w)


def test_calendar_rounding_slack_is_present():
    """Without a step of slack the last fold overshot by ONE DAY and silently
    produced K-1 folds — the trading-to-calendar conversion rounds down at every
    term, so the naive reach-back is always a little short."""
    for end in ("2026-08-14", "2026-06-30", "2026-03-31"):
        w = window_for(end, min_folds=3, floor="2023-01-01")
        assert len(w) >= 3, f"{end} produced only {len(w)} folds"


def test_retention_compares_rates_not_unequal_windows():
    """The bug that made gate v2 unpassable by anything, with the real numbers.

    Measured with a strategy that reads future prices: a 12-month train leg
    returned +302.3% while its 3-month test leg returned +8.85%. The raw ratio is
    0.029 against a 0.5 floor — so perfect foreknowledge "lost 97% of its edge".
    A ratio of cumulative returns over unequal windows measures the windows.
    """
    raw = retention(302.3, 8.846, 40)
    assert raw["retention"] < 0.05
    assert raw["basis"] == "cumulative"

    ann = retention(302.3, 8.846, 40, train_days=365, test_days=91)
    assert ann["basis"] == "annualised"
    assert ann["retention"] > raw["retention"] * 4, "annualising must move this a lot"
    assert ann["test_annual_pct"] > 35


def test_missing_window_lengths_say_so_rather_than_assume_a_duration():
    """A rate computed over an assumed duration is a fabricated number, and this
    one decides verdicts."""
    out = retention(20.0, 12.0, 30)
    assert out["basis"] == "cumulative"
    assert "unequal periods" in out["reason"]


def test_a_total_loss_annualises_without_blowing_up():
    """-100% has no real root; it must stay -100% rather than raise."""
    out = retention(50.0, -100.0, 30, train_days=365, test_days=91)
    assert out["measurable"] is True
    assert out["retention"] < 0


# --- v3: the fold geometry follows the strategy's own clock -------------------

def test_the_holding_period_is_read_from_the_source_then_the_grid():
    """Same pattern as the benchmark reading UNIVERSE: statically, because the
    engine has exited by the time results are judged."""
    from app.fund.walkforward import declared_hold_days
    assert declared_hold_days("HOLD_DAYS = 42")["hold_days"] == 42
    assert declared_hold_days("HOLD_DAYS = 42")["source"] == "declared"
    got = declared_hold_days(None, {"hold_days": ["21", "63"]})
    assert got["hold_days"] == 63, "the SLOWEST setting decides the leg length"
    assert got["source"] == "grid:hold_days"


def test_an_assumed_holding_period_is_reported_as_assumed():
    """A test leg sized from a guessed hold would look rigorous while measuring
    nothing, so the guess is labelled."""
    from app.fund.walkforward import declared_hold_days
    got = declared_hold_days(None, {"fast": ["3"]})
    assert got["source"] == "assumed"
    assert "declare HOLD_DAYS" in got["note"]


def test_a_fast_rule_gets_folds_and_a_slow_one_is_told_it_is_untestable():
    """The measured asymmetry: ~30 months supports 6 folds for a 5-day hold and
    one for a 63-day hold."""
    from app.fund.walkforward import window_for_strategy
    fast = window_for_strategy("2026-08-14", 5, min_folds=2, floor="2024-02-26")
    slow = window_for_strategy("2026-08-14", 63, min_folds=2, floor="2024-02-26")
    assert fast["enough"] is True
    assert len(fast["folds"]) >= 2
    assert slow["enough"] is False
    assert "NOT TESTABLE" in slow["note"]
    # The leg scales with the hold: four decisions each.
    assert slow["test_days"] == 63 * 4
