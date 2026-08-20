"""Drawdown reference rebase — the repair that can only ever LOWER the peak.

The defect (PM sleeve-v2 R1, CEO-accepted 2026-08-21): `assess()` takes the
trailing-365d MAX of NAV history as the drawdown peak, and the fund's
$2,036.35 high includes the phantom-fill era — money the fund never had. A peak
inflated by a bad mark caps risk capacity for a YEAR.

The repair mirrors the loss-reference rebase: it moves no threshold, it moves
the point the limit is measured FROM, once, in the log, with a mandatory
reason. What makes it safe is the DIRECTION, and every test below is about
direction:

  * a rebase may only LOWER the reference — raising it would manufacture a
    drawdown out of nothing AND pre-inflate the denominator so a future real
    drawdown looked smaller;
  * a rebase can never HIDE a real peak — a genuine high observed since the
    rebase raises the reference straight back;
  * the HISTORICAL max_drawdown_pct is not rebased at all. A rebase moves the
    live control's reference; it does not edit what happened.
"""

from __future__ import annotations

import pytest

from app.fund.events import EventType
from app.fund.riskmonitor import (
    HALT_INTEGRITY,
    HALT_LOSS,
    RiskControl,
    effective_peak,
)


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, e):
        self.events.append({"type": e.type.value, "payload": e.payload,
                            "actor": e.actor,
                            "ts": e.payload.get("at") or "2026-08-21T12:00:00+00:00"})
        return e

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


def snaps(*pairs):
    return [{"ts": ts, "total_nav_usd": v} for ts, v in pairs]


# The incident's own numbers.
PHANTOM_PEAK = 2036.35
HONEST_PEAK = 1950.00
NAV_NOW = 1885.00


# ---------------------------------------------------------- the pure peak ---


def test_with_no_rebase_the_peak_is_the_trailing_high_exactly_as_before():
    p = effective_peak(snaps(("2026-08-18T00:00:00Z", 1900.0),
                             ("2026-08-19T00:00:00Z", PHANTOM_PEAK),
                             ("2026-08-20T00:00:00Z", 1890.0)),
                       NAV_NOW, None)
    assert p["peak_nav"] == PHANTOM_PEAK
    assert p["basis"] == "trailing_365d"
    assert p["rebase"] is None
    assert "never been rebased" in p["note"]


def test_a_rebase_lowers_the_peak_and_the_pre_rebase_history_stops_counting():
    """The whole point: the phantom era's high no longer caps risk capacity."""
    p = effective_peak(
        snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK),
              ("2026-08-20T00:00:00Z", 1890.0)),
        NAV_NOW,
        {"nav_usd": HONEST_PEAK, "at": "2026-08-21T00:00:00Z",
         "reason": "the 2036.35 high includes the phantom GLD mark",
         "actor": "neelesh", "previous_peak_usd": PHANTOM_PEAK})
    assert p["peak_nav"] == HONEST_PEAK
    assert p["basis"] == "rebased"
    # The un-rebased figure is still reported, so the panel can show both and
    # a reader can never mistake the new peak for the whole history.
    assert p["unrebased_peak_nav"] == PHANTOM_PEAK
    assert p["rebase"]["previous_peak_usd"] == PHANTOM_PEAK
    assert "2,036.35" in p["note"]


def test_a_LATER_GENUINE_HIGH_raises_the_reference_straight_back():
    """A rebase shortens a phantom's shadow; it cannot hide a real peak."""
    p = effective_peak(
        snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK),
              ("2026-08-22T00:00:00Z", 1975.0)),      # AFTER the rebase
        NAV_NOW,
        {"nav_usd": HONEST_PEAK, "at": "2026-08-21T00:00:00Z"})
    assert p["peak_nav"] == 1975.0
    assert p["basis"] == "post_rebase_high"
    assert "raised the reference back" in p["note"]


def test_current_nav_is_always_a_floor_on_the_peak():
    """A reference below current NAV cannot make the drawdown negative."""
    p = effective_peak(snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK)),
                       2100.0,
                       {"nav_usd": HONEST_PEAK, "at": "2026-08-21T00:00:00Z"})
    assert p["peak_nav"] == 2100.0
    assert p["basis"] == "current_nav"


def test_a_rebase_with_no_usable_timestamp_is_IGNORED_not_applied_blindly():
    """Without a time, "observations after it" is unanswerable — so applying it
    would silently erase real history rather than shorten a phantom's shadow."""
    for bad in ({"nav_usd": HONEST_PEAK, "at": None},
                {"nav_usd": HONEST_PEAK},
                {"nav_usd": 0, "at": "2026-08-21T00:00:00Z"},
                {"nav_usd": "not a number", "at": "2026-08-21T00:00:00Z"}):
        p = effective_peak(snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK)),
                           NAV_NOW, bad)
        assert p["peak_nav"] == PHANTOM_PEAK, bad
        assert p["basis"] == "trailing_365d", bad


def test_an_empty_history_falls_back_to_current_nav_not_to_zero():
    p = effective_peak([], NAV_NOW, None)
    assert p["peak_nav"] == NAV_NOW
    p2 = effective_peak(None, NAV_NOW, None)
    assert p2["peak_nav"] == NAV_NOW


# --------------------------------------------------------- the direction ----


def test_raising_the_peak_is_REFUSED():
    """The move this control must never make.

    Raising the peak manufactures a drawdown out of nothing — a way to halt the
    fund by typing — and pre-inflates the denominator so a future real drawdown
    reads smaller than it is.
    """
    c = RiskControl(MemStore())
    with pytest.raises(ValueError, match="may only LOWER"):
        c.rebase_drawdown_reference(new_peak=2100.0, current_peak=PHANTOM_PEAK,
                                    reason="wishful", actor="neelesh")
    # Equal is not lower either.
    with pytest.raises(ValueError, match="may only LOWER"):
        c.rebase_drawdown_reference(new_peak=PHANTOM_PEAK,
                                    current_peak=PHANTOM_PEAK,
                                    reason="no-op", actor="neelesh")
    assert c._store.events == [], "a refused rebase must write NOTHING"


def test_a_rebase_requires_a_written_reason():
    c = RiskControl(MemStore())
    with pytest.raises(ValueError, match="written reason"):
        c.rebase_drawdown_reference(new_peak=HONEST_PEAK,
                                    current_peak=PHANTOM_PEAK,
                                    reason="   ", actor="neelesh")


def test_a_non_positive_peak_is_refused():
    c = RiskControl(MemStore())
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError, match="non-positive"):
            c.rebase_drawdown_reference(new_peak=bad, current_peak=PHANTOM_PEAK,
                                        reason="r", actor="neelesh")
    with pytest.raises(ValueError, match="must be a number"):
        c.rebase_drawdown_reference(new_peak="x", current_peak=PHANTOM_PEAK,
                                    reason="r", actor="neelesh")


def test_it_is_REFUSED_while_an_integrity_halt_is_open():
    """You cannot re-anchor a peak while the fund cannot measure itself.

    Same rule as the loss rebase, for the same reason: it would launder a bad
    mark into the fund's own reference — the phantom incident with a signature.
    """
    c = RiskControl(MemStore())
    c.halt(reason="stale marks", actor="monitor", halt_class=HALT_INTEGRITY)
    with pytest.raises(ValueError, match="INTEGRITY halt"):
        c.rebase_drawdown_reference(new_peak=HONEST_PEAK,
                                    current_peak=PHANTOM_PEAK,
                                    reason="r", actor="neelesh")
    # A LOSS halt does NOT block it — that is the halt this repair exists for.
    c2 = RiskControl(MemStore())
    c2.halt(reason="drawdown", actor="monitor", halt_class=HALT_LOSS)
    got = c2.rebase_drawdown_reference(new_peak=HONEST_PEAK,
                                       current_peak=PHANTOM_PEAK,
                                       reason="phantom era excluded",
                                       actor="neelesh")
    assert got["status"] == "rebased"


def test_the_event_carries_old_peak_new_peak_and_the_reason():
    c = RiskControl(MemStore())
    got = c.rebase_drawdown_reference(
        new_peak=HONEST_PEAK, current_peak=PHANTOM_PEAK,
        reason="the 2036.35 high includes the phantom GLD mark of 2026-08-20",
        actor="neelesh")
    ev = [e for e in c._store.events
          if e["type"] == EventType.DRAWDOWN_REFERENCE_REBASED.value]
    assert len(ev) == 1
    p = ev[0]["payload"]
    assert p["nav_usd"] == HONEST_PEAK
    assert p["previous_peak_usd"] == PHANTOM_PEAK
    assert "phantom GLD mark" in p["reason"]
    assert p["at"]
    assert ev[0]["actor"] == "neelesh"
    assert got["status"] == "rebased"


def test_the_fold_returns_the_LAST_rebase_and_none_before_any():
    c = RiskControl(MemStore())
    assert c.drawdown_reference() is None, "None is 'never rebased', not 'zero'"
    c.rebase_drawdown_reference(new_peak=1990.0, current_peak=PHANTOM_PEAK,
                                reason="first pass", actor="neelesh")
    c.rebase_drawdown_reference(new_peak=HONEST_PEAK, current_peak=1990.0,
                                reason="second, tighter", actor="neelesh")
    ref = c.drawdown_reference()
    assert ref["nav_usd"] == HONEST_PEAK
    assert ref["previous_peak_usd"] == 1990.0


def test_the_rebase_token_changes_with_the_peak_it_would_replace():
    c = RiskControl(MemStore())
    a = c.drawdown_rebase_token(PHANTOM_PEAK)
    b = c.drawdown_rebase_token(1990.0)
    assert len(a) == 8 and a != b
    c.rebase_drawdown_reference(new_peak=HONEST_PEAK, current_peak=PHANTOM_PEAK,
                                reason="r", actor="neelesh")
    assert c.drawdown_rebase_token(PHANTOM_PEAK) != a


# ------------------------------------------------------ the whole picture ---


def test_end_to_end_the_phantom_peak_stops_capping_risk_capacity():
    """The PM's R1, arithmetic and all.

    At a $2,036.35 peak and $1,885.00 NAV the drawdown reads 7.43% against a
    10% limit — 74% of the budget consumed by an era that included a fabricated
    mark. Rebased to an honest $1,950.00 the same NAV reads 3.33%.
    """
    before = effective_peak(snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK)),
                            NAV_NOW, None)["peak_nav"]
    dd_before = (before - NAV_NOW) / before * 100.0
    assert round(dd_before, 2) == 7.43

    after = effective_peak(
        snaps(("2026-08-19T00:00:00Z", PHANTOM_PEAK)), NAV_NOW,
        {"nav_usd": HONEST_PEAK, "at": "2026-08-21T00:00:00Z"})["peak_nav"]
    dd_after = (after - NAV_NOW) / after * 100.0
    assert round(dd_after, 2) == 3.33
    # The repair RELEASES capacity; it must never manufacture it beyond the
    # honest peak, which the direction rule above guarantees.
    assert dd_after < dd_before
