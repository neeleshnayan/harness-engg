"""How far back a candidate may look, and which leg decides — item (b) of 58c4fff5.

WHAT MOVED: ``WALKFORWARD_HISTORY_FLOOR`` went from 2024-02-26 to 1993-01-29.
MEASURED, not inherited — ``GET /fund/marketdata/bars?symbol=SPY&
start_date=1990-01-01&end_date=2026-08-23&format=csv`` returns 8,448 rows
beginning 1993-01-29. The old value was never the feed's start; it was the reach
of a trailing window nobody re-measured.

WHY THIS FILE EXISTS RATHER THAN A ONE-LINE CONSTANT CHANGE. Two facts measured
on 2026-08-23 make the naive flip harmful:

  * PER-SYMBOL HISTORY IS NOT UNIFORM. On this fund's own feed SPY serves from
    1993-01-29 and UUP from 2007-03-01 — fourteen years apart (TLT 2002-07-30,
    IBB 2001-02-12, GLD 2004-11-18, DBA 2007-01-05). A single global floor is
    right for one symbol and wrong for the rest.
  * THE CONTAINERS CANNOT REACH 1993. Counted, not eyeballed: of the sixteen
    algorithms in this repo ELEVEN fetch ``lookback_days=700``, three fetch
    900 and two fetch 2000 — and the bars endpoint caps the parameter at 2000.
    So a fold planned in 1993 would be fed nothing, and one planned in 2023 is
    fed partially.

Enforcing the container reach as a floor would take a 21-day hold's span from
850 days to 700 — two folds against a requirement of four — and return NOT
TESTABLE for every 21-day-hold candidate in the repo, including the Entry 20
re-judge this pair was sequenced in front of. So the floor RATCHETS: it deepens
where the candidate's own declared data path can serve the depth, never
shortens a window that already exists, and the reach is REPORTED with a count
of the folds that fall outside it.

The first live reading of that count, on a 700-day algorithm: 2 of 4 planned
folds already begin before the reach. That was true before this change and
nothing said so.
"""

from __future__ import annotations

import pytest

from app.fund.factory import (HISTORY_FLOOR_RATCHET, WALKFORWARD_HISTORY_FLOOR,
                              effective_history_floor)

END = "2026-08-04"


def _code(lookback):
    return (f'url = f"{{SPINE}}/marketdata/bars?symbol={{s}}'
            f'&lookback_days={lookback}&format=csv"')


def test_the_configured_floor_is_the_feeds_measured_start():
    """8,448 SPY bars from 1993-01-29 on the start_date/end_date route."""
    assert WALKFORWARD_HISTORY_FLOOR == "1993-01-29"
    assert HISTORY_FLOOR_RATCHET == "2024-02-26"


# --- the ratchet ------------------------------------------------------------


def test_a_shallow_container_cannot_shorten_the_window():
    """The majority case: eleven of the sixteen algorithms declare 700 days.

    Their reach is LATER than the floor this fund already enforces. A floor may
    deepen a window and never shorten one, so the ratchet holds and the reach
    is reported instead of applied.
    """
    out = effective_history_floor(_code(700), END)
    assert out["data_path"] == "2024-09-03"
    assert out["effective"] == HISTORY_FLOOR_RATCHET
    assert out["deepened"] is False
    assert out["ratcheted_from"] == "2024-09-03"
    assert "may deepen a window and never shorten one" in out["ratchet_note"]
    assert "PARTIALLY fed, not" in out["ratchet_note"]


def test_a_deep_container_deepens_the_window():
    """A 2000-day declaration is proof the containers can be fed to 2021."""
    out = effective_history_floor(_code(2000), END)
    assert out["effective"] == "2021-02-11"
    assert out["deepened"] is True
    assert out["binding_leg"] == "data_path"
    assert "ratcheted_from" not in out


def test_an_unknown_reach_deepens_nothing():
    """UNKNOWN IS NOT UNLIMITED, and this is where that rule is enforced.

    An algorithm declaring no lookback gets the endpoint's 180-day default —
    the SHALLOWEST data path in the repo, not the deepest. Treating the unknown
    as non-binding would hand it a 33-year window fed by six months of bars.
    """
    out = effective_history_floor("class X: pass", END)
    assert out["data_path"] is None
    assert out["effective"] == HISTORY_FLOOR_RATCHET
    assert out["deepened"] is False
    assert "UNKNOWN" in out["data_path_note"]
    assert out["binding_leg"] == "ratchet (data-path reach unknown)"


def test_two_different_declared_lookbacks_are_unknown_not_the_larger():
    """The static reader declines on ambiguity; the floor must decline with it."""
    code = 'a = f"?lookback_days=700"\nb = f"?lookback_days=2000"\n'
    out = effective_history_floor(code, END)
    assert out["data_path"] is None
    assert out["effective"] == HISTORY_FLOOR_RATCHET


def test_a_genuinely_shallower_feed_beats_every_other_leg():
    """No container can serve a bar that does not exist."""
    out = effective_history_floor(_code(2000), END, floor="2025-01-01")
    assert out["effective"] == "2025-01-01"
    assert out["binding_leg"] == "configured"


def test_the_floor_is_READ_from_the_constants_not_hardcoded():
    """MOVE both constants and the answer must move with them."""
    out = effective_history_floor(_code(2000), END, floor="1999-09-09",
                                  ratchet="2010-01-01")
    assert out["ratchet"] == "2010-01-01"
    assert out["configured"] == "1999-09-09"
    # data path 2021-02-11 is LATER than a 2010 ratchet, so it is refused
    assert out["effective"] == "2010-01-01"
    assert out["ratcheted_from"] == "2021-02-11"


# --- per-symbol availability is reported absent, never assumed --------------


def test_per_symbol_availability_is_declared_unmeasured():
    """SPY 1993-01-29 vs UUP 2007-03-01 is fourteen years of spread.

    The belt does not measure it at plan time and must say so rather than let a
    reader assume every leg reaches the floor. Reporting the archive's earliest
    row instead would be worse than silence: it is a lower bound on
    availability, so it would shorten windows on the strength of our own fetch
    history.
    """
    out = effective_history_floor(_code(2000), END)
    assert out["per_symbol"] is None
    assert "LOWER BOUND" in out["per_symbol_note"]
    assert "truncation detector" in out["per_symbol_note"]


# --- the verdict records the window it looked at ----------------------------


def test_the_gate_records_how_deep_the_belt_looked():
    from app.fund.gate import evaluate
    out = evaluate({}, walkforward={
        "folds_measurable": 4, "folds_retained": 3,
        "history_floor": {"effective": "2021-02-11", "binding_leg": "data_path",
                          "data_path": "2021-02-11", "deepened": True},
        "folds_before_data_path_reach": 0})
    got = out["checks"]["walkforward_history_floor"]
    assert got["effective"] == "2021-02-11"
    assert got["deepened"] is True
    assert got["folds_before_data_path_reach"] == 0


def test_a_walkforward_that_never_stated_its_window_says_UNSTATED():
    """Every verdict stored before this shipped is in this branch."""
    from app.fund.gate import evaluate
    out = evaluate({}, walkforward={"folds_measurable": 4, "folds_retained": 3})
    got = out["checks"]["walkforward_history_floor"]
    assert got["effective"] is None
    assert "UNSTATED, not default" in got["note"]


def test_no_walkforward_means_no_window_label():
    from app.fund.gate import evaluate
    assert "walkforward_history_floor" not in evaluate({})["checks"]


# --- the pair is ordered, and the order is checkable ------------------------


def test_the_deeper_floor_is_judged_by_the_scaled_requirement():
    """(b) MUST NEVER SHIP ALONE. Measured: the flip alone takes the
    walk-forward leg's false-positive rate from 3.03% to 6.87% at a 21-day
    hold (3,000 draws, real retention, real fold plans). This asserts the
    mechanism that prevents it — a window deepened past four folds' worth is
    required to produce more than four."""
    from app.fund.gate import folds_required
    from app.fund.walkforward import window_for_strategy

    deep = effective_history_floor(_code(2000), END)["effective"]
    plan = window_for_strategy(END, 21, min_folds=4, floor=deep)
    need = folds_required({"requested_folds": plan["folds"]})
    assert need["scaled"] is True
    assert need["required"] > 4, need


@pytest.mark.parametrize("hold", [1, 2, 3, 5, 10, 21, 42, 63])
def test_a_ratcheted_candidate_is_planned_exactly_as_before(hold):
    """The 700-day majority — and every algorithm that declares nothing — must
    see the identical fold plan they saw under the old constant."""
    from app.fund.walkforward import window_for_strategy
    floor = effective_history_floor(_code(700), END)["effective"]
    before = window_for_strategy(END, hold, min_folds=4, floor="2024-02-26")
    after = window_for_strategy(END, hold, min_folds=4, floor=floor)
    assert after["folds"] == before["folds"]
