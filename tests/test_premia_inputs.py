"""The belt side of gate v5r2: the premia legs, the REALISED cash leg, and the
PSR's identifying inputs.

The measurements these tests encode were taken on 2026-08-23 against the four
stored candidates that carry analytics (`fund_candidates.analytics IS NOT
NULL`), reproducible with:

    select candidate_id, analytics from fund_candidates where analytics is not null
"""
from __future__ import annotations

import datetime
import math

import pytest

from premia_feed import cash_feed, per_obs
from app.fund import statistics as st
from app.fund.factory import check_claim_type
from app.fund.gate import evaluate
from app.fund.leanrunner import _returns_from_curve, premia_inputs, psr_inputs

DAY0 = datetime.date(2021, 1, 4)


def trading_dates(n: int) -> list[str]:
    out, d = [], DAY0
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def calendar_dates(n: int) -> list[str]:
    return [(DAY0 + datetime.timedelta(days=i)).isoformat() for i in range(n)]


def drifting(n: int, per_obs: float, amp: float, seed: int) -> list[float]:
    """A deterministic series whose REALISED mean is exactly ``per_obs``.

    The noise is centred before it is added. Without that the realised mean of
    a 500-observation draw wanders by more than the drift being tested, and a
    fixture built to separate two Sharpes silently stops separating them.
    """
    x, noise = seed, []
    for _ in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        noise.append((x / 2 ** 31 - 0.5) * amp)
    mu = sum(noise) / n
    return [per_obs + z - mu for z in noise]


def levels(returns, start=100.0):
    out, lvl = [], start
    for r in returns:
        out.append(lvl)
        lvl *= (1.0 + r)
    out.append(lvl)
    return out


def compounded_pct(returns):
    lvl = 1.0
    for r in returns:
        lvl *= (1.0 + r)
    return (lvl - 1.0) * 100.0


# --- the leg the comparison is actually built from -----------------------

def test_the_premia_leg_is_built_from_the_bar_the_gate_judges_by():
    """MEASURED DEFECT, 2026-08-23: the payload carries TWO benchmarks.

    ``_add_benchmark`` discards the engine's own benchmark series for any
    multi-name strategy and installs a recomputed equal-weight basket in
    ``benchmark_curve``/``benchmark_return_pct`` — but ``daily_returns
    ["benchmark"]``, which was built earlier in ``_parse_results``, still holds
    the DISCARDED series. On the three stored ``monthend_rebalance_flow``
    candidates the discarded leg compounds to +110.9% against the installed
    bar's +41.55%; on ``announcement_premium`` it is +19.8% against +84.78%.

    Judging a Sharpe comparison off the wrong leg flips the answer on three of
    those four. This test plants the same shape — a discarded leg that looks
    far better than the real bar — and requires the comparison to use the bar.
    """
    n = 500
    dts = trading_dates(n + 1)
    strat = drifting(n, 0.0006, 0.012, 3)
    real_bar = drifting(n, 0.0002, 0.012, 5)          # the installed basket
    discarded = drifting(n, 0.0020, 0.012, 7)         # the engine's own series
    assert compounded_pct(discarded) > 3 * compounded_pct(real_bar)

    res = {
        "daily_returns": {"present": True, "dates": dts[1:], "strategy": strat,
                          "benchmark": discarded, "benchmark_present": True,
                          "n": n},
        "benchmark_curve": levels(real_bar),
        "benchmark_dates": dts,
        "benchmark_return_pct": round(compounded_pct(real_bar), 2),
        "benchmark_series_source": "recomputed_basket",
    }
    got = premia_inputs(res)
    assert got["measurable"] is True
    assert got["benchmark_leg_source"] == "recomputed_basket"
    # The leg used is the BAR, not the discarded series.
    assert got["benchmark"]["total_return_pct"] == pytest.approx(
        compounded_pct(real_bar), abs=1e-6)
    assert got["benchmark"]["total_return_pct"] != pytest.approx(
        compounded_pct(discarded), abs=1.0)
    # And the disagreement is REPORTED rather than left to be rediscovered.
    d = got["daily_returns_benchmark_leg"]
    assert d["agrees_with_headline"] is False
    assert d["compounded_total_pct"] == pytest.approx(
        compounded_pct(discarded), abs=0.01)


def test_using_the_discarded_leg_would_flip_the_premia_verdict():
    """The consequence, not just the disagreement — this is why it matters.

    Same evidence, two candidate benchmark legs. Against the real bar the
    strategy has a premium; against the discarded leg it does not. If the
    implementation ever reverts to reading ``daily_returns["benchmark"]``, the
    first assertion below survives and the second dies.
    """
    n = 500
    dts = trading_dates(n + 1)
    strat = drifting(n, 0.0006, 0.012, 3)
    real_bar = drifting(n, 0.0002, 0.012, 5)
    discarded = drifting(n, 0.0020, 0.012, 7)
    base = {"total_return_pct": 40.0,
            "benchmark_return_pct": round(compounded_pct(real_bar), 2),
            "capacity": {"capacity_usd": 5e6},
            "robustness": {"psr_pct": 92.0, "total_orders": 300,
                           "costs": {"slippage_modelled": True}},
            "daily_returns": {"present": True, "dates": dts[1:],
                              "strategy": strat, "benchmark": discarded,
                              "benchmark_present": True, "n": n},
            "benchmark_curve": levels(real_bar), "benchmark_dates": dts,
            "benchmark_series_source": "recomputed_basket"}
    real = premia_inputs(base)
    wrong = premia_inputs({**base, "benchmark_curve": levels(discarded)})
    s = st.sharpe_at_rf(real["strategy"], 0.0)
    assert s > st.sharpe_at_rf(real["benchmark"], 0.0)
    assert s < st.sharpe_at_rf(wrong["benchmark"], 0.0)


def test_the_engine_kept_branch_uses_the_daily_returns_leg():
    """A single-name strategy keeps the engine's bar, and then the two agree."""
    n = 300
    dts = trading_dates(n + 1)
    strat = drifting(n, 0.0006, 0.012, 3)
    bar = drifting(n, 0.0002, 0.012, 5)
    got = premia_inputs({
        "daily_returns": {"present": True, "dates": dts[1:], "strategy": strat,
                          "benchmark": bar, "benchmark_present": True, "n": n},
        # Downsampled to 400 points by `_parse_results` and carrying NO dates
        # on this branch — which is exactly why the curve must not be used.
        "benchmark_curve": [1.0, 2.0, 3.0],
        "benchmark_series_source": "engine_single_name",
    })
    assert got["measurable"] is True
    assert got["benchmark_leg_source"] == "engine_single_name"
    assert got["benchmark"]["total_return_pct"] == pytest.approx(
        compounded_pct(bar), abs=1e-6)


def test_the_real_add_benchmark_sets_the_marker_on_BOTH_of_its_branches():
    """Drive the producer, not a stub — the marker IS the producer's contract.

    D17/D18: a helper can be flawless and uncalled, and a test that stubs the
    producer cannot test the producer's contract. Mutation caught this exact
    gap: deleting the recomputed-basket marker survived a suite that only ever
    set the field by hand in a fixture.
    """
    import app.fund.marketdata as md
    from app.fund.leanrunner import LeanRunner

    class Bars:
        closes = [100.0, 110.0, 120.0]
        dates = ["2025-06-01", "2025-06-02", "2025-06-03"]
        source = "test"

    monkeypatch_target = getattr(md, "fetch_daily_bars")
    try:
        md.fetch_daily_bars = lambda *a, **k: Bars()      # type: ignore
        # Multi-name: the engine's bar is discarded and a basket installed.
        multi = {"equity_curve": [2000.0, 2050.0],
                 "equity_dates": ["2025-06-01", "2025-06-03"],
                 "orders": [{"symbol": "SPY"}, {"symbol": "QQQ"}],
                 "benchmark_curve": []}
        LeanRunner._add_benchmark(multi)
        assert multi["benchmark_kind"] == "equal_weight_basket"
        assert multi["benchmark_series_source"] == "recomputed_basket"

        # Single name with a usable engine curve: the engine's bar is KEPT.
        single = {"equity_curve": [2000.0, 2050.0],
                  "equity_dates": ["2025-06-01", "2025-06-03"],
                  "orders": [{"symbol": "SPY"}],
                  "benchmark_curve": [100.0, 105.0]}
        LeanRunner._add_benchmark(single)
        assert single["benchmark_series_source"] == "engine_single_name"
    finally:
        md.fetch_daily_bars = monkeypatch_target            # type: ignore


def test_an_unmarked_result_reports_the_premia_legs_ABSENT():
    """No marker means the belt did not decide which series is the bar.

    Absence, with the reason, rather than a guess: picking a leg here would be
    the same defect the marker exists to close.
    """
    n = 100
    dts = trading_dates(n + 1)
    got = premia_inputs({
        "daily_returns": {"present": True, "dates": dts[1:],
                          "strategy": drifting(n, 0.001, 0.01, 3),
                          "benchmark": drifting(n, 0.001, 0.01, 4),
                          "benchmark_present": True, "n": n}})
    assert got["measurable"] is False
    assert "no benchmark leg could be built" in got["reason"]


def test_the_benchmark_unavailable_sentence_is_carried_into_the_reason():
    n = 100
    dts = trading_dates(n + 1)
    got = premia_inputs({
        "daily_returns": {"present": True, "dates": dts[1:],
                          "strategy": drifting(n, 0.001, 0.01, 3),
                          "benchmark": [], "benchmark_present": False, "n": n},
        "benchmark_unavailable": "only 2 of 20 names in the bar had usable bars",
    })
    assert got["measurable"] is False
    assert "only 2 of 20 names" in got["reason"]


def test_no_daily_series_is_absent_not_empty():
    got = premia_inputs({"daily_returns": {
        "present": False, "dates": [], "strategy": [], "benchmark": [],
        "reason": "the equity curve carries no usable dates"}})
    assert got["measurable"] is False
    assert "absent, not zero" in got["reason"]
    assert "no usable dates" in got["reason"]


def test_the_window_is_the_intersection_and_the_coverage_is_reported():
    """A bar that stops early must shorten the COMPARISON, not be padded.

    Real shape: stored candidate 144387901688 runs to 2026-08-21 and its bar
    stops at 2026-08-04, so 611 of the strategy's 907 observations are
    comparable — 67.4%.
    """
    n = 500
    dts = trading_dates(n + 1)
    bar = drifting(300, 0.0002, 0.012, 5)
    got = premia_inputs({
        "daily_returns": {"present": True, "dates": dts[1:],
                          "strategy": drifting(n, 0.0006, 0.012, 3),
                          "benchmark": [], "benchmark_present": False, "n": n},
        "benchmark_curve": levels(bar), "benchmark_dates": dts[:301],
        "benchmark_series_source": "recomputed_basket"})
    assert got["window"]["n"] == 300
    assert got["window"]["last"] == dts[300]
    cov = got["coverage"]
    assert cov["common_days"] == 300
    assert cov["strategy_days"] == 500
    assert cov["fraction"] == 0.6
    # NO CASH LEG WAS SUPPLIED, so no session count is claimed. The bar is the
    # leg that truncated, and deriving a session calendar from it would let the
    # truncation shrink its own denominator (300 of 300 clears a majority; 300
    # of 500 does not). Absent, not assumed.
    assert cov["strategy_sessions"] is None
    assert cov["session_fraction"] is None
    assert cov["session_basis"] is None
    assert cov["rf_dropped_days"] == 0
    # Both legs measured over the SAME 300 days, not 300 against 500.
    assert got["strategy"]["n"] == got["benchmark"]["n"] == 300


# --- the realised cash leg (gate v5r2, the D23 kill's belt half) ---------

def _lean_shaped(n_cal: int, rf_pct: float | None = 3.0, **kw):
    """A result in LEAN'S REAL SHAPE: a CALENDAR-day strategy series against a
    SESSION-day bar. This is what every stored candidate looks like — the engine
    emits an equity point every calendar day and pads the weekends with zeros —
    and it is the shape in which the v5r1 coverage denominator was wrong.
    """
    cal = calendar_dates(n_cal + 1)
    sess = [d for d in cal
            if datetime.date.fromisoformat(d).weekday() < 5]
    strat = drifting(n_cal, 0.0006, 0.012, 3)
    bar = drifting(len(sess) - 1, 0.0002, 0.012, 5)
    res = {
        "daily_returns": {"present": True, "dates": cal[1:], "strategy": strat,
                          "benchmark": [], "benchmark_present": False,
                          "n": n_cal},
        "benchmark_curve": levels(bar)[:len(sess)], "benchmark_dates": sess,
        "benchmark_series_source": "recomputed_basket",
    }
    fetch = None if rf_pct is None else cash_feed(rf_pct, obs_per_year=261.0,
                                                  **kw)
    return premia_inputs(res, rf_bars=fetch), cal, sess


def test_the_coverage_denominator_is_SESSIONS_not_calendar_days():
    """THE ~19pp OF SLACK, measured and removed.

    The adversary: "premia_inputs coverage divides trading days by calendar
    days: 0.67-0.69 on all 15 real specimens, ~19pp of slack in the majority
    check, and a reader cannot tell whether anything is missing."

    Both numbers are reported, so a reader can see exactly what the calendar
    denominator was hiding — and the fraction the majority test reads is the
    session one. On a full-coverage run the calendar fraction sits near 252/365
    while the session fraction is 1.0: the entire gap was weekends.
    """
    got, cal, sess = _lean_shaped(500)
    cov = got["coverage"]
    assert cov["strategy_days"] == 500                 # calendar days
    assert cov["strategy_sessions"] == len(sess) - 1   # sessions in the span
    assert cov["session_basis"] == "benchmark+cash"
    # The v5r1 number, kept beside the new one rather than quietly replaced.
    assert 0.66 < cov["fraction"] < 0.72, cov
    # Nothing was actually missing, and only the session figure can say so.
    assert cov["session_fraction"] == 1.0, cov
    assert cov["session_fraction"] - cov["fraction"] > 0.28, cov


def test_the_excess_legs_are_the_raw_legs_net_of_the_SAME_cash_return():
    """One cash series, subtracted from both sides, on one window.

    Checked against the arithmetic rather than against a stored number: for a
    constant cash rate the excess mean is the raw mean minus the per-observation
    rate and the dispersion is UNCHANGED, so both are closed form.
    """
    got, _cal, _sess = _lean_shaped(500, rf_pct=3.0)
    assert got["excess_measurable"] is True
    assert got["rf"]["measurable"] is True
    assert got["rf"]["symbol"] == "BIL"
    assert got["rf"]["basis"] == "realised_series"
    assert got["rf"]["realised_annual_pct"] == pytest.approx(3.0, abs=0.05)
    # The per-observation rate the FEED actually paid — not one re-derived from
    # the leg's own clock, which differs by the window's holidays and would make
    # this assertion agree with the code only to four decimals.
    c = per_obs(3.0, 261.0)
    for leg in ("strategy", "benchmark"):
        raw, ex = got[leg], got[f"{leg}_excess"]
        assert ex["n"] == raw["n"]
        assert ex["mean"] == pytest.approx(raw["mean"] - c, abs=1e-12)
        assert ex["stdev"] == pytest.approx(raw["stdev"], abs=1e-12)


def test_no_cash_source_leaves_the_RAW_capture_intact_and_the_excess_absent():
    """The two flags, at the belt. An rf outage must not delete the volatility
    capture — a control losing its instrument because a different control failed
    is the unwired-kill-switch family."""
    got, _cal, _sess = _lean_shaped(500, rf_pct=None)
    assert got["measurable"] is True
    assert got["strategy"]["ann_vol_pct"] is not None
    assert got["benchmark"]["ann_vol_pct"] is not None
    assert got["excess_measurable"] is False
    assert got["strategy_excess"] is None
    assert got["benchmark_excess"] is None
    assert "not a zero one" in got["rf"]["reason"]


def test_the_stored_schema_says_2_so_a_v5r1_capture_is_distinguishable():
    got, _c, _s = _lean_shaped(500)
    assert got["schema"] == 2


def test_the_cash_leg_is_fetched_over_the_STRATEGYS_span_not_the_bars():
    """Written because the other choice was made first and was wrong.

    Fetching over the strategy-and-bar intersection means a TRUNCATED BAR cuts
    the cash leg to match, and then nothing in the payload can say how many
    sessions the run contained — so the coverage majority would shrink its own
    denominator exactly when a leg went missing. The request must span the
    strategy.
    """
    calls: list = []
    cal = calendar_dates(501)
    sess = [d for d in cal if datetime.date.fromisoformat(d).weekday() < 5]
    half = sess[:len(sess) // 2]
    bar = drifting(len(half) - 1, 0.0002, 0.012, 5)
    res = {
        "daily_returns": {"present": True, "dates": cal[1:],
                          "strategy": drifting(500, 0.0006, 0.012, 3),
                          "benchmark": [], "benchmark_present": False,
                          "n": 500},
        "benchmark_curve": levels(bar)[:len(half)], "benchmark_dates": half,
        "benchmark_series_source": "recomputed_basket",
    }
    got = premia_inputs(res, rf_bars=cash_feed(3.0, obs_per_year=261.0,
                                               calls=calls))
    _sym, start, end = calls[0]
    assert start < cal[1] and end > cal[-1], calls
    # The bar covers half the run; the denominator still counts the whole run.
    assert got["coverage"]["strategy_sessions"] == len(sess) - 1
    assert got["coverage"]["common_days"] == len(half) - 1
    assert got["coverage"]["session_fraction"] < 0.55


def test_a_cash_series_that_shares_no_dates_is_an_absence_not_a_zero():
    """A feed that answers with a series from the wrong era.

    The raw pair survives — it was measurable — and the excess pair does not,
    with the reason naming the window rather than a bare False.
    """
    cal = calendar_dates(301)
    sess = [d for d in cal if datetime.date.fromisoformat(d).weekday() < 5]
    bar = drifting(len(sess) - 1, 0.0002, 0.012, 5)

    def elsewhere(_sym, _start, _end):
        from premia_feed import FakeBars
        d = calendar_dates(30)
        return FakeBars([x.replace("2021", "1999") for x in d],
                        [100.0 + i for i in range(30)], "synthetic-cash")

    got = premia_inputs({
        "daily_returns": {"present": True, "dates": cal[1:],
                          "strategy": drifting(300, 0.0006, 0.012, 3),
                          "benchmark": [], "benchmark_present": False,
                          "n": 300},
        "benchmark_curve": levels(bar)[:len(sess)], "benchmark_dates": sess,
        "benchmark_series_source": "recomputed_basket"}, rf_bars=elsewhere)
    assert got["measurable"] is True
    assert got["excess_measurable"] is False
    assert "no window on which an excess return could be formed" in \
        got["rf"]["reason"]
    assert got["coverage"]["strategy_sessions"] is None


def test_a_curve_with_a_bad_level_breaks_the_chain_rather_than_dividing():
    got = _returns_from_curve([100.0, 110.0, 0.0, 50.0, 55.0],
                              ["d1", "d2", "d3", "d4", "d5"])
    assert set(got) == {"d2", "d5"}
    assert got["d2"] == pytest.approx(0.10)
    assert got["d5"] == pytest.approx(0.10)


def test_a_curve_and_its_dates_of_different_lengths_yields_nothing():
    assert _returns_from_curve([1.0, 2.0, 3.0], ["d1", "d2"]) == {}


# --- the clock, and why it is derived ------------------------------------

def test_the_annualisation_is_self_correcting_across_clocks():
    """THE MEASURED REASON the factor is derived and not 252.

    LEAN emits an equity point on every CALENDAR day, so ~29% of the return
    series is weekend zeros (584 of 1,998 on stored candidate a663a592ff1d).
    Annualising that at sqrt(252) understates volatility by sqrt(365.25/252)
    = 1.2039 in theory, and by a measured 1.2033 to 1.2047 on the four stored
    candidates — reproduced against the engine's own published
    ``Annual Standard Deviation``.

    Deriving the factor from the dates removes the question: the same
    underlying path, presented on a calendar clock with weekend zeros or on
    its trading-day clock, gives the same annualised volatility and the same
    Sharpe. Measured on real data too — 12.026% calendar against 12.021%
    trading-day on that candidate.
    """
    trading = trading_dates(500)
    moves = drifting(500, 0.0004, 0.02, 17)
    cal_dates, cal_moves = [], []
    d = datetime.date.fromisoformat(trading[0])
    i = 0
    while i < len(moves):
        iso = d.isoformat()
        if d.weekday() < 5:
            cal_dates.append(iso)
            cal_moves.append(moves[i])
            i += 1
        else:
            cal_dates.append(iso)
            cal_moves.append(0.0)
        d += datetime.timedelta(days=1)

    t = st.leg_moments(moves, trading)
    c = st.leg_moments(cal_moves, cal_dates)
    assert t["obs_per_year"] == pytest.approx(261, abs=2)
    assert c["obs_per_year"] == pytest.approx(365.25, abs=0.5)
    assert c["ann_vol_pct"] == pytest.approx(t["ann_vol_pct"], rel=0.01)
    assert (st.sharpe_at_rf(c, 0.0)
            == pytest.approx(st.sharpe_at_rf(t, 0.0), rel=0.01))
    # And the naive sqrt(252) on the calendar clock is the 17% error.
    naive = st.mean_std(cal_moves)[1] * math.sqrt(252) * 100
    assert naive == pytest.approx(t["ann_vol_pct"] / 1.2039, rel=0.02)


@pytest.mark.parametrize("dates,n,fragment", [
    ([], 0, "a series and its clock must be the same length"),
    (["2021-01-04"], 1, "same length"),
    (["not-a-date", "2021-01-05"], 2, "could not be parsed"),
    (["2021-01-04", "2021-01-04"], 2, "spans 0 day(s)"),
])
def test_an_unreadable_clock_is_absent_and_never_252(dates, n, fragment):
    got = st.observations_per_year(dates, n)
    assert got["usable"] is False
    assert got["obs_per_year"] is None
    assert fragment in got["reason"]


def test_a_leg_with_no_dispersion_is_unmeasurable():
    got = st.leg_moments([0.001] * 100, trading_dates(100))
    assert got["measurable"] is False
    assert "zero dispersion" in got["reason"]
    assert st.sharpe_at_rf(got, 0.0) is None


def test_sharpe_at_rf_refuses_a_leg_MARKED_unmeasurable_whatever_it_carries():
    """The `measurable` flag is the contract, not the numbers beside it.

    Found by mutation and confirmed by capturing outputs under both arms:
    removing this guard is NOT a no-op. It is currently unreachable through
    ``leg_moments`` — every unmeasurable shape it emits also has a zero or
    absent stdev, so the arithmetic guard below catches them — but
    ``sharpe_at_rf`` is public, takes a stored dict, and the day an
    unmeasurable reason arrives that leaves the moments populated (too few
    observations for inference, say) the flag is the only thing standing
    between a caller and a Sharpe computed from a leg the belt refused to
    measure. Measured divergence: 6 of 60 probed cases, e.g. 0.1587 against
    None.
    """
    looks_fine = {"measurable": False, "obs_per_year": 252.0,
                  "stdev": 0.1, "mean": 0.001}
    assert st.sharpe_at_rf(looks_fine, 0.0) is None
    assert st.sharpe_at_rf(looks_fine, 4.0) is None
    assert st.sharpe_at_rf({**looks_fine, "measurable": True}, 0.0) is not None


def test_sharpe_at_rf_is_affine_in_the_per_observation_rate():
    """The property the two-endpoint stress test rests on."""
    m = st.leg_moments(drifting(500, 0.0004, 0.02, 23), trading_dates(500))
    k = m["obs_per_year"]
    pts = []
    for rf in (0.0, 2.0, 4.0, 6.0):
        c = (1.0 + rf / 100.0) ** (1.0 / k) - 1.0
        pts.append((c, st.sharpe_at_rf(m, rf)))
    slope = (pts[1][1] - pts[0][1]) / (pts[1][0] - pts[0][0])
    for c, sh in pts[1:]:
        assert sh == pytest.approx(pts[0][1] + slope * (c - pts[0][0]),
                                   abs=1e-9)
    assert slope == pytest.approx(-math.sqrt(k) / m["stdev"], rel=1e-9)


def test_max_drawdown_is_a_positive_fraction_and_absent_on_an_empty_series():
    assert st.max_drawdown([]) is None
    assert st.max_drawdown([0.1, -0.5, 0.1]) == pytest.approx(0.5)
    assert st.max_drawdown([0.1, 0.1]) == 0.0


# --- the PSR capture -----------------------------------------------------

REAL_STATS = {
    # Verbatim from stored candidate 144387901688 (announcement_premium).
    "Beta": "0.102", "Alpha": "0.192", "Drawdown": "15.300%",
    "Sharpe Ratio": "1.666", "Sortino Ratio": "2.343",
    "Treynor Ratio": "1.903", "Tracking Error": "0.209",
    "Annual Variance": "0.014", "Information Ratio": "0.849",
    "Annual Standard Deviation": "0.116", "Net Profit": "118.614%",
    "Compounding Annual Return": "36.994%",
    "Probabilistic Sharpe Ratio": "80.370%", "Total Orders": "6997",
}


def test_the_psr_capture_takes_the_identifying_statistics_verbatim():
    """Strings, not floats: the "%" is what says which scale the engine was on.

    The gate's most binding criterion reads ``Probabilistic Sharpe Ratio``
    verbatim and nobody could say against what target. The validator's
    inversion put the effective bar at annualised Sharpe 1.39-1.49 — not zero
    — and no belt run has ever stored the inputs that would settle it.
    """
    got = psr_inputs(REAL_STATS, None)
    assert got["statistics"]["Probabilistic Sharpe Ratio"] == "80.370%"
    assert got["statistics"]["Annual Standard Deviation"] == "0.116"
    assert got["statistics"]["Information Ratio"] == "0.849"
    assert got["statistics_missing"] == []
    # The engine publishes no benchmark Sharpe, and the capture says so rather
    # than omitting the key.
    assert got["benchmark_sharpe_published"] is None
    assert "publishes NO benchmark Sharpe" in got["benchmark_sharpe_note"]


def test_the_psr_capture_names_the_statistics_the_engine_did_not_write():
    got = psr_inputs({"Sharpe Ratio": "1.0"}, None)
    assert "Probabilistic Sharpe Ratio" in got["statistics_missing"]
    assert "Beta" in got["statistics_missing"]
    assert got["statistics"] == {"Sharpe Ratio": "1.0"}


def test_a_psr_with_no_sample_length_says_UNKNOWN_not_zero():
    """PSR's z-statistic scales with sqrt(n-1); a PSR with no n is unreadable."""
    got = psr_inputs(REAL_STATS, None)
    assert got["observations"]["n"] is None
    assert "absent, not zero" in got["observations"]["note"]


def test_the_capture_checks_the_engines_volatility_rule_still_holds():
    """A live check, not a claim: 0.11627 computed against 0.116 published.

    If a future engine build changes how it annualises, this field says so
    instead of a statistic silently shifting by 17%.
    """
    n = 900
    dts = calendar_dates(n)
    # A series whose sd*sqrt(252) is exactly 0.116, as the real one's is.
    target_sd = 0.116 / math.sqrt(252)
    raw = drifting(n, 0.0009, 1.0, 29)
    mu, sd = st.mean_std(raw)
    series = [0.0009 + (r - mu) / sd * target_sd for r in raw]
    got = psr_inputs(REAL_STATS, {"strategy": series, "dates": dts})
    rep = got["engine_volatility_reproduction"]
    assert rep["published_annual_standard_deviation"] == 0.116
    assert rep["series_stdev_times_sqrt_252"] == pytest.approx(0.116, abs=5e-4)
    assert rep["reproduces"] is True
    assert got["observations"]["n"] == n
    assert got["observations"]["obs_per_year"] == pytest.approx(365.25, abs=0.1)

    # And it FAILS to reproduce when the engine's number disagrees.
    other = psr_inputs({**REAL_STATS, "Annual Standard Deviation": "0.250"},
                       {"strategy": series, "dates": dts})
    assert other["engine_volatility_reproduction"]["reproduces"] is False


@pytest.mark.parametrize("raw,expect", [
    ("0.116", 11.6),        # what the engine actually writes today
    ("11.600%", 11.6),      # the shape a blind x100 would report as 1160%
    ("0.116%", 0.116),
    (None, None), ("n/a", None), ("", None),
])
def test_the_engines_volatility_is_read_with_its_unit_not_assumed(raw, expect):
    """The same statistics block writes "0.116" and "15.300%" side by side.

    So the unit is read off the string. A blind multiply by 100 is the
    unit-confusion shape, and it would be invisible in a field nobody
    re-derives.
    """
    from app.fund.leanrunner import _annual_vol_fraction, _annual_vol_pct
    stats = dict(REAL_STATS)
    if raw is None:
        stats.pop("Annual Standard Deviation")
    else:
        stats["Annual Standard Deviation"] = raw
    got = _annual_vol_pct(stats)
    frac = _annual_vol_fraction(stats)
    if expect is None:
        assert got is None and frac is None
    else:
        assert got == pytest.approx(expect)
        # The percentage is DERIVED from the fraction, never re-parsed, so the
        # two cannot drift and the stored fraction carries no scaling artefact.
        assert frac == pytest.approx(expect / 100.0)
        assert got == frac * 100.0


def test_the_robustness_block_carries_the_engines_volatility():
    """It was in hand on every run and thrown away on every run."""
    from app.fund.leanrunner import _robustness
    got = _robustness(REAL_STATS, [], [], [])
    assert got["engine_annual_vol_pct"] == pytest.approx(11.6)
    assert got["psr_inputs"]["statistics"]["Sharpe Ratio"] == "1.666"


def test_the_capture_counts_the_zero_return_days():
    """29.2% zeros on a real 1,998-observation series is the calendar clock."""
    dts = calendar_dates(10)
    got = psr_inputs(REAL_STATS,
                     {"strategy": [0.0, 0.01, 0.0, 0.0, -0.01,
                                   0.0, 0.02, 0.0, 0.0, 0.01],
                      "dates": dts})
    assert got["observations"]["zero_return_days"] == 6


# --- the belt refuses a claim type the gate cannot judge -----------------

@pytest.mark.parametrize("given,expect", [
    (None, "alpha"), ("alpha", "alpha"), ("premia", "premia")])
def test_a_known_claim_type_is_accepted(given, expect):
    got = check_claim_type(given)
    assert got["known"] is True
    assert got["claim_type"] == expect
    assert got["reason"] is None


@pytest.mark.parametrize("given", ["premai", "ALPHA", "", "beta", 7])
def test_an_unknown_claim_type_is_refused_at_submission(given):
    """Refused before the containers, not after twenty minutes of them."""
    got = check_claim_type(given)
    assert got["known"] is False
    assert "unknown claim type" in got["reason"]


def test_the_belt_and_the_gate_read_ONE_vocabulary():
    """Two copies of "which claim types exist" would fail silently.

    The gate's answer to an unrecognised type is to judge it as alpha and fail
    it; a belt that accepted a word the gate did not know would spend the whole
    engine budget to produce that failure.
    """
    from app.fund import gate
    for word in gate.CLAIM_TYPES:
        assert check_claim_type(word)["known"] is True
    assert check_claim_type("premia-ish")["known"] is False
    # And the gate itself refuses the same word.
    out = evaluate({}, None, None, claim_type="premia-ish")
    assert any("unrecognised claim type" in f for f in out["failures"])
