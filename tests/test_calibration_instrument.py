"""The calibration instrument's own guards.

`scripts/instruments/d36/calibrate.py` produced the table that justified the
v4.4 level. An instrument that produces a headline number is code, it is the
least-reviewed code in a dispatch, and a large number pointing the way you
expect is the one nobody questions (D28). These are its null and input tests.
"""
from __future__ import annotations

import importlib.util
import os

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "..", "scripts", "instruments", "d36",
                     "calibrate.py")
_spec = importlib.util.spec_from_file_location("d36_calibrate", _PATH)
calib = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(calib)


def test_the_shipped_level_is_PINNED_and_not_read_from_the_live_criteria():
    """THE INSTRUMENT MUST OUTLIVE THE CHANGE IT JUSTIFIED.

    The shipped arm is the bar AS IT STOOD. Reading `gate.CRITERIA` would make
    the script compare the new bar with itself the moment the diff merged, and
    the table quoted in the GATE_VERSION note would stop being reproducible by
    the instrument that produced it. Found by the Gauntlet on the finished diff.
    """
    from app.fund import gate
    assert calib.SHIPPED_ENGINE_LEVEL == 65.0
    # THE INEQUALITY PROOF IS DEAD AND ITS REPLACEMENT IS STRONGER. This test
    # used to assert `gate.CRITERIA["min_psr_pct"] == 50.0` — the two values
    # differed, so their difference proved the pin was not a read. D37 reverted
    # the live criterion to 65.0 and the two agree again, at which point
    # equality cannot distinguish a pin from a read at all: the exact defect
    # this test was written about, arriving through the back door.
    #
    # So MOVE THE SOURCE instead (D16, applied in the negative). If the pin were
    # secretly a read, moving the live criterion would move it.
    assert gate.CRITERIA["min_psr_pct"] == 65.0        # they agree TODAY
    original = gate.CRITERIA["min_psr_pct"]
    try:
        gate.CRITERIA["min_psr_pct"] = 12.5
        fresh = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(fresh)                # re-executed, not cached
        assert fresh.SHIPPED_ENGINE_LEVEL == 65.0
    finally:
        gate.CRITERIA["min_psr_pct"] = original
    src = open(_PATH, encoding="utf-8").read()
    assert 'gate.CRITERIA["min_psr_pct"]' not in src.replace(
        "gate.CRITERIA['min_psr_pct']", "")  # the print line uses quotes


def test_the_engine_target_emulation_is_a_RANGE_not_a_point():
    """A conclusion resting on the midpoint must be visible as such, so the
    emulated target is swept across the whole measured range."""
    lo, hi = calib.ENGINE_TARGET_RANGE
    assert lo < calib.ENGINE_TARGET_MID < hi
    assert (lo, hi) == (0.0700, 0.0792)


def test_the_universe_and_the_cash_name_are_fixed_in_the_instrument():
    """A population that changes between runs is not a population, it is two."""
    assert calib.RISKY == ["SPY", "QQQ", "IWM", "TLT", "XLK", "XLE", "XLF",
                           "XLV"]
    assert calib.CASH == "BIL"


def test_the_breakeven_is_ZERO_when_the_draw_never_beat_its_bar():
    """The null case for the cost sweep: no edge is not a fragile edge, and the
    two must not share a number."""
    losing = [0.0] * 50
    winning = [0.001] * 50
    assert calib.breakeven_bps(losing, winning, turnover=0.5,
                               rebalances=10) == 0.0
    got = calib.breakeven_bps(winning, losing, turnover=0.5, rebalances=10)
    assert got is not None and got > 0.0


def test_the_breakeven_is_ABSENT_when_nothing_was_traded():
    """Zero turnover has no cost per trade to solve for — absent, not zero."""
    assert calib.breakeven_bps([0.01] * 5, [0.0] * 5, 0.0, 10) is None
    assert calib.breakeven_bps([0.01] * 5, [0.0] * 5, 0.5, 0) is None


def test_compounded_pct_is_zero_on_a_flat_series():
    assert calib.compounded_pct([0.0] * 100) == 0.0
    assert calib.compounded_pct([]) == 0.0


def test_every_failure_sentence_the_gate_emits_is_CLASSIFIABLE():
    """The census groups failures by criterion. A sentence the classifier does
    not know reads as a criterion that never fires, so the unclassified bucket
    is reported — and this test makes an unknown sentence a RED, not a row."""
    assert calib.classify("returns 5% against 9% for simply owning it: an "
                          "expensive way to hold the underlying"
                          ) == "must_beat_benchmark"
    assert calib.classify("the probability that the true Sharpe is above zero "
                          "is 3%, below the 50.0% this bar requires — on this "
                          "much history that is not distinguishable from luck"
                          ) == "luck filter (target zero)"
    assert calib.classify("something nobody has written yet").startswith(
        "UNCLASSIFIED")
