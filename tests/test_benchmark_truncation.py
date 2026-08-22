"""The benchmark's data path: truncation, feed provenance, and the pinned leg.

INCIDENT THIS FILE GUARDS (Entry 20, 2026-08-22): one benchmark leg came back
transiently short, ``_add_benchmark`` truncated every other leg to match it
(leanrunner.py, ``n = min(len(x) for x in series)``), and the benchmark return
was computed over a shorter window than the strategy's curve — with NOTHING in
the result saying so. The gate compared two different windows and called it a
comparison. It cost 11.85pp.

The cause fix is the candidate-scoped snapshot (one fetch per leg, so legs
cannot disagree transiently). These tests guard the DETECTOR, which stays
because a genuine data gap can still shorten a leg and the reader must be told.
"""

from __future__ import annotations

import pytest

from app.fund import barcache
from app.fund.leanrunner import LeanRunner, _declared_lookback_days


class _Bars:
    def __init__(self, dates, closes, source="test"):
        self.dates = list(dates)
        self.closes = list(closes)
        self.source = source


def _result(dates, orders):
    return {
        "equity_dates": list(dates),
        "equity_curve": [1000.0 + 10 * i for i in range(len(dates))],
        "orders": [{"symbol": s} for s in orders],
    }


# --- the truncation detector ----------------------------------------------


def test_a_short_leg_is_reported_not_silently_truncated(monkeypatch):
    """Entry 20, 11.85pp: a transiently short leg shortened the whole bar.

    The number may still be truncated — truncating beats padding, because a
    padded leg is a made-up price. What must never happen again is truncating
    SILENTLY.
    """
    import app.fund.marketdata as md

    full = _Bars([f"2024-01-{d:02d}" for d in range(1, 11)],
                 [100.0 + i for i in range(10)])
    short = _Bars([f"2024-01-{d:02d}" for d in range(1, 5)],
                  [100.0 + i for i in range(4)])

    monkeypatch.setattr(md, "fetch_daily_bars",
                        lambda symbol, *a, **k: full if symbol == "AAA" else short)
    result = _result([f"2024-01-{d:02d}" for d in range(1, 11)], ("AAA", "BBB"))
    LeanRunner._add_benchmark(result)

    trunc = result.get("benchmark_truncated")
    assert trunc is not None, "the bar was truncated with nothing saying so"
    assert trunc["bars_used"] == 4
    assert trunc["bars_longest_leg"] == 10
    assert trunc["dropped"] == 6
    assert trunc["shortest_legs"] == ["BBB"], "the short leg was not named"
    assert "does NOT span the same period" in trunc["note"]


def test_legs_of_equal_length_report_no_truncation(monkeypatch):
    """The detector must not cry wolf — otherwise it gets ignored."""
    import app.fund.marketdata as md

    bars = _Bars([f"2024-01-{d:02d}" for d in range(1, 11)],
                 [100.0 + i for i in range(10)])
    monkeypatch.setattr(md, "fetch_daily_bars", lambda *a, **k: bars)
    result = _result([f"2024-01-{d:02d}" for d in range(1, 11)], ("AAA", "BBB"))
    LeanRunner._add_benchmark(result)
    assert "benchmark_truncated" not in result


# --- feed provenance -------------------------------------------------------


def test_a_two_vendor_bar_says_so(monkeypatch):
    """MEASURED 2026-08-22: the belt was doing this on the live path.

    fetch_daily_bars takes Alpaca for a trailing lookback and Yahoo whenever
    BOTH start and end are given (marketdata.py), and the benchmark always gives
    both — so the strategy traded Alpaca closes and was graded against Yahoo
    ones, while the docstring said "the identical feed the algorithm traded".
    The disagreement was small (0.46 bps mean on SPY/TLT, 0.00pp of total
    return) and it was still not one feed. It must be visible on the result.
    """
    import app.fund.marketdata as md

    dates = [f"2024-01-{d:02d}" for d in range(1, 11)]

    def mixed(symbol, *a, **k):
        return _Bars(dates, [100.0 + i for i in range(10)],
                     source="alpaca" if symbol == "AAA" else "yahoo")

    monkeypatch.setattr(md, "fetch_daily_bars", mixed)
    result = _result(dates, ("AAA", "BBB"))
    LeanRunner._add_benchmark(result)
    assert result["benchmark_feed_mixed"] == ["alpaca", "yahoo"]
    assert result["benchmark_feeds"] == ["alpaca", "yahoo"]


def test_a_single_feed_bar_reports_its_feed_and_no_mixture(monkeypatch):
    import app.fund.marketdata as md

    dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
    monkeypatch.setattr(
        md, "fetch_daily_bars",
        lambda *a, **k: _Bars(dates, [100.0 + i for i in range(10)], source="alpaca"))
    result = _result(dates, ("AAA", "BBB"))
    LeanRunner._add_benchmark(result)
    assert result["benchmark_feeds"] == ["alpaca"]
    assert "benchmark_feed_mixed" not in result


# --- the benchmark reads the candidate's pinned leg ------------------------


def test_the_benchmark_is_served_from_the_active_snapshot(monkeypatch):
    """The strategy and its bar must be the SAME closes, not two fetches."""
    import app.fund.marketdata as md

    dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
    pinned_closes = [100.0 + i for i in range(10)]

    def never(*a, **k):
        raise AssertionError("the benchmark refetched instead of using the snapshot")

    def fetcher(symbol, lookback_days=365, start=None, end=None):
        return _Bars(dates, pinned_closes, source="alpaca")

    snap = barcache.prefetch(["AAA", "BBB"], candidate="c1", lookback_days=700,
                             fetcher=fetcher)
    monkeypatch.setattr(md, "fetch_daily_bars", never)
    result = _result(dates, ("AAA", "BBB"))
    with barcache.activate(snap):
        LeanRunner._add_benchmark(result)
    assert result["benchmark_feeds"] == ["alpaca"]
    assert "benchmark_truncated" not in result
    assert snap.hits == 2
    assert snap.misses == []


def test_the_pinned_benchmark_spans_the_strategys_own_window(monkeypatch):
    """MEASURED end-to-end 2026-08-22, and the reason the two arms disagreed.

    Running monthend both ways, the strategy's equity ended 2026-08-21 while the
    DIRECT-path benchmark ended 2026-08-20 — one session short, every time, not
    transiently. Cause: the benchmark asks with start AND end, which routes to
    Yahoo (marketdata.py), and Yahoo lags Alpaca by a session; the strategy
    itself traded the Alpaca series. So the bar was systematically computed over
    a shorter window than the curve it was grading, worth 0.10pp on that run.

    Served from the pinned leg both sides are the same series, so the bar spans
    the strategy's window exactly. That is the property under test.
    """
    import app.fund.marketdata as md

    strategy_dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
    pinned = [f"2024-01-{d:02d}" for d in range(1, 11)]
    lagging = [f"2024-01-{d:02d}" for d in range(1, 10)]      # a session short

    monkeypatch.setattr(
        md, "fetch_daily_bars",
        lambda *a, **k: _Bars(lagging, [100.0 + i for i in range(9)], "yahoo"))

    snap = barcache.prefetch(
        ["AAA", "BBB"], candidate="c1", lookback_days=700,
        fetcher=lambda s, **k: _Bars(pinned, [100.0 + i for i in range(10)],
                                     "alpaca"))
    result = _result(strategy_dates, ("AAA", "BBB"))
    with barcache.activate(snap):
        LeanRunner._add_benchmark(result)

    assert result["benchmark_dates"][-1] == strategy_dates[-1], (
        "the bar does not reach the last session the strategy traded")
    assert len(result["benchmark_curve"]) == len(pinned)
    assert result["benchmark_feeds"] == ["alpaca"]


def test_the_benchmark_falls_back_live_when_the_snapshot_cannot_serve(monkeypatch):
    """Fail OPEN. A snapshot that cannot answer must not cost a benchmark."""
    import app.fund.marketdata as md

    dates = [f"2024-01-{d:02d}" for d in range(1, 11)]
    monkeypatch.setattr(
        md, "fetch_daily_bars",
        lambda *a, **k: _Bars(dates, [100.0 + i for i in range(10)], source="live"))

    # A snapshot holding a DIFFERENT symbol: every leg here must miss.
    snap = barcache.prefetch(
        ["ZZZ"], candidate="c1", lookback_days=700,
        fetcher=lambda s, **k: _Bars(dates, [1.0] * 10))
    result = _result(dates, ("AAA", "BBB"))
    with barcache.activate(snap):
        LeanRunner._add_benchmark(result)
    assert result["benchmark_return_pct"] is not None
    assert result["benchmark_feeds"] == ["live"]
    assert len(snap.misses) == 2, "the fallback happened without being recorded"


# --- the static lookback reader -------------------------------------------


@pytest.mark.parametrize("code,expected", [
    ('url = f"{SPINE}/marketdata/bars?symbol=X&lookback_days=700&format=csv"', 700),
    ('url = ("{S}/marketdata/bars?symbol=X"\n       "&lookback_days=2000&format=csv")', 2000),
    # Two different lookbacks in two real URLs: ambiguous, so no snapshot.
    ('a=f"?lookback_days=700"\nb=f"?lookback_days=900"\n', None),
    # Computed rather than literal: unreadable, so no snapshot.
    ('url = f"?lookback_days={N}"', None),
    ("no lookback here", None),
    # THE ENTRY 20 CASE, and the reason this reads the AST rather than the text.
    # The 170-name algorithm this cache was built for explains its choice in a
    # COMMENT that names the rejected number. A text scan sees 1200 and 2000,
    # calls it ambiguous, and silently declines to snapshot the one candidate
    # that most needed the cache. Comments are not in the AST.
    ('# 2000, not 1200. MEASURED on ACGL: lookback_days=1200 gave 612 bars\n'
     'url = (f"{SPINE}/marketdata/bars?symbol={s}"\n'
     '       f"&lookback_days=2000&format=csv")\n', 2000),
    # A docstring, unlike a comment, IS in the AST — so a number mentioned in
    # prose still counts as ambiguous. Declining is the safe direction.
    ('"""We used to ask lookback_days=1200."""\nurl = f"?lookback_days=2000"\n', None),
    # Outside the endpoint's own bound (gt=1, le=2000) — pinning it would hide
    # a 422 behind a cache hit.
    ("lookback_days=5000", None),
    ("lookback_days=1", None),
])
def test_declared_lookback_days_reads_only_what_is_unambiguous(code, expected):
    assert _declared_lookback_days(code) == expected


def test_declared_lookback_days_matches_the_real_algorithms():
    """A guess here would feed a strategy a window it never asked for."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    algos = root / "lean_workspace" / "algorithms"
    monthend = (algos / "monthend_rebalance_flow" / "main.py").read_text(encoding="utf-8")
    assert _declared_lookback_days(monthend) == 2000
    xs = (algos / "xs_momentum_smallcap" / "main.py").read_text(encoding="utf-8")
    assert _declared_lookback_days(xs) == 700
