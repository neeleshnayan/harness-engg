"""The sieve may only reject, and it must not reject the wrong things.

Two failure modes, and they are not symmetric. Wasting a container on a dud costs
14 minutes. Rejecting a real edge destroys it permanently and silently, because
nothing downstream will ever look at that candidate again. So the tests here are
mostly about the second kind.

The other thing they pin is the bug that made the first version useless: screening
on RAW return killed only 16% of a real momentum grid, because in a rising market
almost any long-only rule shows a positive Sharpe. The sieve was measuring beta and
calling it edge.
"""

from __future__ import annotations

import math

import pytest

from app.fund import prescreen
from app.fund.prescreen import (MIN_SHARPE, SpecError, grid_to_specs, population,
                                screen, validate)


def _spec(**kw):
    base = {"kind": "xs_momentum", "lookback_days": 20, "hold_days": 5, "top_n": 2}
    base.update(kw)
    return base


def _trending(n=400, drift=0.0006, seed=1):
    """A deterministic pseudo-random walk. No Math.random anywhere near a test."""
    out, x = [], 100.0
    s = seed
    for i in range(n):
        s = (s * 1103515245 + 12345) % (2 ** 31)
        shock = ((s / (2 ** 31)) - 0.5) * 0.02
        x *= (1.0 + drift + shock)
        out.append(x)
    return out


# --- the one rule -------------------------------------------------------------

def test_a_passing_candidate_makes_no_claim_beyond_worth_a_container():
    closes = {f"S{i}": _trending(seed=i + 1, drift=0.0004 * (i + 1))
              for i in range(5)}
    got = screen(_spec(), list(closes), closes)
    assert got["verdict"] in ("worth_a_container", "rejected")
    if got["verdict"] == "worth_a_container":
        assert "NOT a pass" in got["claim"]
        assert "cannot approve" in got["claim"]
        # It must never emit anything that could be mistaken for a gate verdict.
        assert "passed" not in got


def test_a_rejection_says_why_and_names_the_false_negative_risk():
    closes = {f"S{i}": _trending(seed=i + 1)[:50] for i in range(3)}
    got = screen(_spec(), list(closes), closes)
    assert got["verdict"] == "rejected"
    assert got["reason"]
    assert "false-negative" in got["claim"]


# --- specs, not code ----------------------------------------------------------

def test_an_unknown_kind_is_refused_not_approximated():
    with pytest.raises(SpecError, match="refused rather than approximated"):
        validate(_spec(kind="some_clever_ml_thing"))


@pytest.mark.parametrize("bad", [
    {"lookback_days": 1}, {"hold_days": 0}, {"top_n": 0},
])
def test_incoherent_specs_are_refused(bad):
    with pytest.raises(SpecError):
        validate(_spec(**bad))


def test_a_sieve_error_is_refused_not_counted_as_a_rejection():
    """Collapsing the two would quietly convert bugs into verdicts."""
    out = population([_spec(kind="nonsense")], ["A", "B"],
                     {"A": _trending(), "B": _trending(seed=9)})
    assert out["rejected"] == []
    assert len(out["refused"]) == 1
    assert "refused is NOT rejected" in out["note"]


# --- the beta-not-edge bug ----------------------------------------------------

def test_it_screens_on_excess_return_not_raw():
    """The bug that made the first version a decoration.

    Every symbol here rises at the SAME rate, so no cross-sectional rule can add
    anything — the ranking is pure noise on top of a common trend. A raw-return
    sieve sees a healthy positive Sharpe and keeps it. An excess-return sieve sees
    approximately nothing, which is the truth.
    """
    closes = {f"S{i}": _trending(seed=i + 1, drift=0.0008) for i in range(6)}
    got = screen(_spec(lookback_days=40, hold_days=10), list(closes), closes)
    assert got["verdict"] == "rejected", (
        "a rule with no cross-sectional information survived a market-wide trend — "
        "the sieve is measuring beta and calling it edge")
    assert "excess-return Sharpe" in got["reason"]
    assert "not more than owning the universe" in got["reason"]


def test_a_market_neutral_book_keeps_its_return():
    """Net exposure scaling, which is what makes one formula right for both families.

    Subtracting a FULL benchmark from a long-short book would penalise it for beta
    it never held. The subtraction is scaled by net exposure, so a book that nets
    ~zero has ~nothing removed.
    """
    import numpy as np

    closes_arr = np.array(
        [_trending(seed=i + 1, drift=0.001) for i in range(4)], dtype=float).T
    ls, _ = prescreen._equity_curve(
        validate(_spec(long_short=True, lookback_days=20, hold_days=5)),
        ["A", "B", "C", "D"], closes_arr, np)
    lo, _ = prescreen._equity_curve(
        validate(_spec(long_short=False, lookback_days=20, hold_days=5)),
        ["A", "B", "C", "D"], closes_arr, np)
    # Both are excess series; neither should be a pure copy of the other.
    assert ls.shape == lo.shape and ls.shape[0] > 0
    assert not np.allclose(ls, lo)


# --- no look-ahead ------------------------------------------------------------

def test_the_signal_cannot_see_the_return_it_earns():
    """A rule fed a series where the FUTURE is knowable must not score infinitely.

    Constructed so one symbol jumps on a single known day. If the sieve were using
    same-bar information the jump would be captured perfectly and the Sharpe would
    be absurd. This is a smoke test for the one-bar shift, not a proof of it.
    """
    import numpy as np

    n = 400
    base = [_trending(seed=k + 1, drift=0.0002) for k in range(4)]
    base[0] = list(base[0])
    base[0][300] = base[0][300] * 1.5          # a single large, isolated jump
    closes_arr = np.array(base, dtype=float).T
    port, _ = prescreen._equity_curve(
        validate(_spec(lookback_days=20, hold_days=5)),
        ["A", "B", "C", "D"], closes_arr, np)
    sh = prescreen._sharpe(port, np)
    assert sh is None or abs(sh) < 12.0, (
        f"Sharpe {sh} implies the signal saw the bar it was paid for")


# --- population ---------------------------------------------------------------

def test_the_population_is_the_grid_product():
    specs = grid_to_specs("xs_momentum", (20, 40), (5, 10), (2, 3), (False, True))
    assert len(specs) == 2 * 2 * 2 * 2
    assert all(s["kind"] == "xs_momentum" for s in specs)


def test_population_reports_a_kill_rate_and_keeps_the_three_buckets_apart():
    closes = {f"S{i}": _trending(seed=i + 1, drift=0.0003 * (i + 1))
              for i in range(6)}
    specs = grid_to_specs("xs_momentum", (20, 40), (5, 21), (2, 3))
    out = population(specs, list(closes), closes)
    assert out["population"] == len(specs)
    assert len(out["worth_a_container"]) + len(out["rejected"]) \
        + len(out["refused"]) == len(specs)
    assert out["kill_rate_pct"] is not None


def test_the_floor_is_the_measured_one_not_a_round_number():
    """0.45 was chosen from a swept table, and 0.60 was rejected on purpose.

    If this ever reads 0.60 without the audit being re-run, someone traded a 12%
    false-negative rate for container hours.
    """
    assert MIN_SHARPE == 0.45


def test_too_few_observations_is_a_rejection_with_the_count_named():
    closes = {"A": _trending(n=60), "B": _trending(n=60, seed=7)}
    got = screen(_spec(), ["A", "B"], closes)
    assert got["verdict"] == "rejected"
    assert "aligned observations" in got["reason"]


def test_a_single_symbol_cannot_be_ranked():
    got = screen(_spec(), ["A"], {"A": _trending()})
    assert got["verdict"] == "rejected"
    assert "cross-sectional rule has nothing to rank" in got["reason"]
