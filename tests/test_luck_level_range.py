"""``_luck_leg``'s range check on the luck level — the D37 boundary suite.

The luck level (``min_psr_pct`` for an alpha claim, ``premia_min_luck_pct``
for a premia claim) must be a real number strictly inside ``(0, 100)`` or the
leg refuses rather than silently treating an off-range number as an
off-switch. This file pins that boundary as a table, run for both claim
types, plus the two ways a level can be unreadable and the ordering rule
that the off-switch is checked before the level is.

Every case below checks the SPECIFIC clause a reader would use to tell one
refusal from another — "(0, 100)" for a range refusal, "no readable level"
for a non-numeric one — because both sentences contain the word "luck" and a
test that only checked for that word would be satisfied by the wrong branch.
"""
from __future__ import annotations

import pytest

from test_luck_filter import _alpha, _premia, judge
from test_premia_gate import CLEAN_HOLDOUT, CLEAN_SWEEP, CLEAN_WALK
from app.fund.gate import evaluate

# =========================================================================
# fixtures shared by every case below
# =========================================================================


def _judge_alpha(level, **extra):
    """An alpha claim, engine-reported basis (the shipped default), with a
    clean engine PSR of 90% so `measurable` never turns on the DATA rather
    than the level under test."""
    r = _alpha(psr=90.0)
    return evaluate(r, CLEAN_HOLDOUT, CLEAN_SWEEP, walkforward=CLEAN_WALK,
                    criteria={"min_psr_pct": level}, **extra)


def _judge_premia(level, **extra):
    """A premia claim, target-zero basis (the shipped default), with a clean
    measurable +0.20 advantage so `measurable` never turns on the DATA rather
    than the level under test."""
    res = _premia(0.20)
    return judge(res, premia_min_luck_pct=level, **extra)


def _judge(claim_type, level, **extra):
    return _judge_alpha(level, **extra) if claim_type == "alpha" \
        else _judge_premia(level, **extra)


# =========================================================================
# THE BOUNDARY TABLE — contract point 2, both ends strict
# =========================================================================

@pytest.mark.parametrize("claim_type", ["alpha", "premia"])
@pytest.mark.parametrize("level", [-1.0, 0.0, 100.0, 100.1, 1e9])
def test_a_level_outside_open_0_100_is_refused_with_the_range_reason(
        claim_type, level):
    """Negative, both closed endpoints, just over the top, and wildly over —
    each must refuse rather than pass (a silent off-switch, the shape the
    adversary named) or raise. Both claim types read this check, so both are
    probed: a guard that covers only one caller is a guard with a documented
    bypass.
    """
    out = _judge(claim_type, level)
    luck = out["checks"]["luck"]
    assert luck["measurable"] is False, luck
    assert "(0, 100)" in luck["reason"], luck["reason"]
    assert any("the luck filter could not be applied" in f
               for f in out["failures"]), out["failures"]
    assert out["passed"] is False


@pytest.mark.parametrize("claim_type", ["alpha", "premia"])
@pytest.mark.parametrize("level", [0.001, 1.0, 50.0, 99.9, 99.999])
def test_a_level_strictly_inside_0_100_is_read_and_not_refused(
        claim_type, level):
    """A level inside the open interval — including two values a hair off
    each boundary — must be READ: the criterion may still pass or fail on
    what it measures, but the range refusal must never fire and the reader
    must be able to see the level that was actually applied.
    """
    out = _judge(claim_type, level)
    luck = out["checks"]["luck"]
    assert luck["level_pct"] == level
    assert "(0, 100)" not in (luck["reason"] or "")
    assert not any("(0, 100)" in f for f in out["failures"]), out["failures"]


# =========================================================================
# THE OTHER REFUSAL — a non-numeric level, and it must NOT wear the range
# sentence (contract point 4: the two refusals must not be conflated)
# =========================================================================

@pytest.mark.parametrize("claim_type", ["alpha", "premia"])
@pytest.mark.parametrize("raw_level", [None, "65", True, False])
def test_a_non_numeric_level_gets_the_no_readable_level_reason_not_the_range_one(
        claim_type, raw_level):
    """``None``, a string, and both bools. Python says
    ``isinstance(True, int)`` is true, so a check that only tests
    ``isinstance(level, (int, float))`` would silently accept a bool as a
    level — this is the case that would catch that regression. All four must
    land on the PRE-EXISTING "no readable level" sentence, never on the range
    one: they never reached a float to test against (0, 100) at all.
    """
    out = _judge(claim_type, raw_level)
    luck = out["checks"]["luck"]
    assert luck["measurable"] is False, luck
    assert "no readable level" in luck["reason"], luck["reason"]
    assert "(0, 100)" not in luck["reason"]
    assert any("no readable level" in f for f in out["failures"]), \
        out["failures"]


# =========================================================================
# ORDERING — contract point 5: the off-switch is checked before the level
# =========================================================================

def test_declining_the_filter_skips_an_out_of_range_level_without_refusing():
    """A premia claim with the filter switched off and an out-of-range level
    must PASS the luck leg — it must never read far enough to refuse over a
    level it was never going to apply. If the level were checked first, this
    would refuse over 250.0 instead.
    """
    res = _premia(-0.03)
    out = judge(res, premia_require_luck_filter=False, premia_min_luck_pct=250.0)
    luck = out["checks"]["luck"]
    assert luck["applied"] is False
    assert luck["reason"] is not None and "declines to apply" in luck["reason"]
    assert not any("luck filter could not be applied" in f
                   for f in out["failures"]), out["failures"]
    assert out["passed"] is True, out["failures"]


def test_declining_the_filter_skips_an_absent_level_without_refusing():
    """Same ordering claim, with the level absent (``None``) rather than
    out-of-range — the off-switch must win over this refusal too.
    """
    res = _premia(-0.03)
    out = judge(res, premia_require_luck_filter=False, premia_min_luck_pct=None)
    luck = out["checks"]["luck"]
    assert luck["applied"] is False
    assert luck["reason"] is not None and "declines to apply" in luck["reason"]
    assert not any("luck filter could not be applied" in f
                   for f in out["failures"]), out["failures"]
    assert out["passed"] is True, out["failures"]
