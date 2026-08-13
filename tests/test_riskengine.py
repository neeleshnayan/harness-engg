"""Tests for the structural risk layers.

Built on synthetic price series with *known* correlation structure, so the
assertions can be exact rather than "looks about right". The failure these guard
against is subtle: a correlation engine that silently returns plausible numbers
while measuring the wrong thing is worse than one that crashes.
"""

import math
from decimal import Decimal

import numpy as np
import pytest

from app.fund import correlation as C
from app.fund import riskmetrics as RM
from app.fund.regime import absorption_ratio, mahalanobis_series
from app.fund.risk import RiskGate, RiskLimits
from app.fund.stress import StressTester
from app.fund.connectors.base import Order, Side


# --- fakes -----------------------------------------------------------------

class FakeBars:
    def __init__(self, symbol, closes, dates):
        self.symbol, self.closes, self.dates = symbol, closes, dates
        self.source, self.start, self.end = "fake", dates[0], dates[-1]


def _dates(n, start_day=1):
    """Sequential ISO dates. Weekends do not matter for the maths."""
    out, y, m, d = [], 2024, 1, start_day
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}-{d:02d}")
        d += 1
        if d > 28:
            d, m = 1, m + 1
        if m > 12:
            m, y = 1, y + 1
    return out


def series_from_returns(rets, p0=100.0):
    px = [p0]
    for r in rets:
        px.append(px[-1] * (1.0 + r))
    return px


def make_fetcher(returns_by_symbol, n_dates=None):
    n = n_dates or (len(next(iter(returns_by_symbol.values()))) + 1)
    dates = _dates(n)

    def fetch(symbol, lookback_days=250, start=None, end=None):
        s = symbol.upper()
        if s not in returns_by_symbol:
            raise ValueError(f"no data for {s}")
        closes = series_from_returns(returns_by_symbol[s])
        return FakeBars(s, closes[:n], dates[:n])
    return fetch


class FakeNav:
    def __init__(self, positions_usd, cash=0.0):
        self._pos, self._cash = positions_usd, cash

    def compute(self):
        pos = [{"symbol": s, "usd_value": Decimal(str(v)), "qty": Decimal("1"),
                "mark": Decimal(str(v))} for s, v in self._pos.items()]
        total = sum(self._pos.values()) + self._cash

        class Snap:
            total_nav_usd = Decimal(str(total))
            positions = pos
            breakdown = {"cash": Decimal(str(self._cash)),
                         "positions": Decimal(str(sum(self._pos.values())))}
            units_outstanding = Decimal(str(total))
            nav_per_unit = Decimal("1")
        return Snap()


def _rng(seed=0):
    return np.random.default_rng(seed)


# --- correlation & effective bets -------------------------------------------

class TestEffectiveBets:
    def test_identical_assets_are_one_bet(self):
        """Four names moving identically must report ~1 effective bet. If this
        ever reports 4, the crowding alarm is worthless."""
        base = list(_rng(1).normal(0.0005, 0.01, 300))
        rets = {s: base for s in ("AAA", "BBB", "CCC", "DDD")}
        analytics = C.CorrelationAnalytics(
            FakeNav({s: 250.0 for s in rets}), fetcher=make_fetcher(rets))
        C.clear_bars_cache()
        out = analytics.analyse(lookback_days=300)
        assert out["measurable"] is True
        assert out["effective_bets"] == pytest.approx(1.0, abs=0.05)
        assert out["avg_pairwise_correlation"] == pytest.approx(1.0, abs=0.01)
        # With correlation 1 there is no diversification left to lose.
        assert out["stressed_vol_pct"] == pytest.approx(out["portfolio_vol_pct"], rel=0.02)

    def test_independent_assets_approach_n_bets(self):
        g = _rng(2)
        rets = {s: list(g.normal(0.0005, 0.01, 400))
                for s in ("AAA", "BBB", "CCC", "DDD")}
        analytics = C.CorrelationAnalytics(
            FakeNav({s: 250.0 for s in rets}), fetcher=make_fetcher(rets))
        C.clear_bars_cache()
        out = analytics.analyse(lookback_days=400)
        assert out["effective_bets"] > 3.0
        assert abs(out["avg_pairwise_correlation"]) < 0.2
        # Independent names: stressed vol must be materially worse than actual.
        assert out["stressed_vol_pct"] > out["portfolio_vol_pct"] * 1.5

    def test_symbol_without_history_is_excluded_not_invented(self):
        g = _rng(3)
        rets = {"AAA": list(g.normal(0, 0.01, 300)), "BBB": list(g.normal(0, 0.01, 300))}
        analytics = C.CorrelationAnalytics(
            FakeNav({"AAA": 100.0, "BBB": 100.0, "GHOST": 100.0}),
            fetcher=make_fetcher(rets))
        C.clear_bars_cache()
        out = analytics.analyse(lookback_days=300)
        assert "GHOST" in out["excluded"]
        assert out["positions_covered_pct"] == pytest.approx(66.7, abs=0.5)
        assert any("Only 67% of gross exposure" in line
                   for line in out["interpretation"])

    def test_no_positions_is_not_measurable(self):
        out = C.CorrelationAnalytics(FakeNav({})).analyse()
        assert out["measurable"] is False


class TestAlignedReturns:
    def test_dates_are_intersected(self):
        """Correlating series over different dates is meaningless; the
        intersection must win, not the longest series."""
        C.clear_bars_cache()
        long_d, short_d = _dates(200), _dates(120)

        def fetch(symbol, lookback_days=250, start=None, end=None):
            n = 200 if symbol == "LONG" else 120
            d = long_d if symbol == "LONG" else short_d
            return FakeBars(symbol, series_from_returns([0.001] * (n - 1)), d[:n])

        used, rets, dates, excluded = C.aligned_returns(["LONG", "SHORT"], fetcher=fetch)
        assert set(used) == {"LONG", "SHORT"}
        assert len(rets["LONG"]) == len(rets["SHORT"]) == 119

    def test_too_little_overlap_is_reported(self):
        C.clear_bars_cache()

        def fetch(symbol, lookback_days=250, start=None, end=None):
            return FakeBars(symbol, series_from_returns([0.001] * 5), _dates(6))

        used, rets, dates, excluded = C.aligned_returns(["A", "B"], fetcher=fetch)
        assert used == []
        assert all("overlapping trading days" in v for v in excluded.values())


# --- risk contribution ------------------------------------------------------

class TestRiskContribution:
    def test_euler_decomposition_sums_to_total(self):
        """The defining property: components must add to portfolio vol exactly.
        A non-zero residual means the decomposition is wrong."""
        g = _rng(4)
        mat = g.normal(0, 0.01, (500, 4))
        w = np.array([0.4, 0.3, 0.2, 0.1])
        out = RM.risk_contributions(["A", "B", "C", "D"], w, RM.sample_covariance(mat))
        assert out["measurable"] is True
        assert out["decomposition_residual"] == pytest.approx(0.0, abs=1e-9)
        assert sum(r["risk_share_pct"] for r in out["contributions"]) == pytest.approx(100.0, abs=0.1)

    def test_volatile_name_carries_more_risk_than_capital(self):
        """The headline finding the module exists to produce: equal capital,
        unequal risk."""
        g = _rng(5)
        mat = np.column_stack([
            g.normal(0, 0.03, 500),   # volatile
            g.normal(0, 0.005, 500),  # calm
        ])
        w = np.array([0.5, 0.5])
        out = RM.risk_contributions(["VOL", "CALM"], w, RM.sample_covariance(mat))
        top = out["largest_risk_contributor"]
        assert top["symbol"] == "VOL"
        assert top["risk_share_pct"] > 80.0
        assert top["risk_vs_capital_gap_pct"] > 30.0

    def test_zero_variance_is_reported_not_divided_by(self):
        out = RM.risk_contributions(["A"], np.array([1.0]), np.zeros((1, 1)))
        assert out["measurable"] is False


# --- tail -------------------------------------------------------------------

class TestTail:
    def test_expected_shortfall_is_never_below_var(self):
        """ES averages the losses beyond VaR, so it cannot be smaller. If it
        ever is, the tail slice is wrong."""
        g = _rng(6)
        r = list(g.normal(0.0005, 0.012, 500))
        out = RM.historical_tail(r, nav_usd=2000.0)
        assert out["measurable"] is True
        for lvl in out["levels"].values():
            assert lvl["expected_shortfall_pct"] >= lvl["var_pct"]
            assert lvl["tail_observations"] > 0

    def test_short_history_refuses_to_estimate_a_tail(self):
        out = RM.historical_tail([0.01, -0.02] * 10)
        assert out["measurable"] is False
        assert "credible tail estimate" in out["reason"]

    def test_fat_tail_shows_up_as_larger_shortfall(self):
        g = _rng(7)
        calm = list(g.normal(0, 0.01, 600))
        jumpy = list(g.normal(0, 0.008, 570)) + [-0.15] * 30
        a = RM.historical_tail(calm)["levels"]["0.975"]["expected_shortfall_pct"]
        b = RM.historical_tail(jumpy)["levels"]["0.975"]["expected_shortfall_pct"]
        assert b > a

    def test_caveats_state_the_method_limit(self):
        g = _rng(8)
        out = RM.historical_tail(list(g.normal(0, 0.01, 300)))
        assert any("cannot see a loss larger than the worst day" in c
                   for c in out["caveats"])


class TestVolRegime:
    def test_ewma_reacts_to_a_recent_vol_spike(self):
        """A regime change must show up in EWMA well before the equal-weighted
        window notices — that gap is the entire point of running both."""
        g = _rng(9)
        quiet = g.normal(0, 0.005, 400)
        loud = g.normal(0, 0.03, 40)
        mat = np.concatenate([quiet, loud]).reshape(-1, 1)
        out = RM.vol_regime(mat, np.array([1.0]))
        assert out["measurable"] is True
        assert out["ewma_vol_pct"] > out["equal_weighted_vol_pct"]
        assert out["ratio"] > 1.25
        assert "understate" in out["verdict"]


# --- regime -----------------------------------------------------------------

class TestAbsorptionRatio:
    def test_perfectly_coupled_market_absorbs_everything(self):
        base = _rng(10).normal(0, 0.01, 300)
        mat = np.column_stack([base] * 5)
        assert absorption_ratio(np.cov(mat, rowvar=False, ddof=1), n_eigen=1) == pytest.approx(1.0, abs=1e-6)

    def test_independent_market_absorbs_little(self):
        mat = _rng(11).normal(0, 0.01, (600, 10))
        ar = absorption_ratio(np.cov(mat, rowvar=False, ddof=1), n_eigen=2)
        assert ar < 0.45

    def test_coupled_market_scores_higher_than_independent(self):
        g = _rng(12)
        common = g.normal(0, 0.01, 600)
        coupled = np.column_stack([common + g.normal(0, 0.002, 600) for _ in range(10)])
        independent = g.normal(0, 0.01, (600, 10))
        a = absorption_ratio(np.cov(coupled, rowvar=False, ddof=1), n_eigen=2)
        b = absorption_ratio(np.cov(independent, rowvar=False, ddof=1), n_eigen=2)
        assert a > b


class TestTurbulence:
    def test_is_causal_and_scores_only_after_history(self):
        mat = _rng(13).normal(0, 0.01, (400, 4))
        vals, offset = mahalanobis_series(mat, min_history=250)
        assert offset == 250
        assert len(vals) == 150

    def test_unusual_joint_move_scores_high(self):
        """Turbulence measures unusual COMBINATIONS, not just big moves: two
        assets that always move together, suddenly diverging."""
        g = _rng(14)
        common = g.normal(0, 0.01, 300)
        mat = np.column_stack([common, common + g.normal(0, 0.001, 300)])
        mat = np.vstack([mat, np.array([[0.03, -0.03]])])   # they split apart
        vals, _ = mahalanobis_series(mat, min_history=250)
        assert vals[-1] > np.quantile(vals[:-1], 0.99)

    def test_too_little_history_returns_nothing(self):
        vals, _ = mahalanobis_series(_rng(15).normal(0, 0.01, (50, 3)), min_history=250)
        assert vals == []


# --- stress -----------------------------------------------------------------

class TestReverseStress:
    def test_uniform_move_to_halt_is_arithmetically_right(self):
        """NAV 1000 (800 exposure, 200 cash), peak 1000, 10% halt -> need $100
        of loss -> 12.5% fall on the exposed 800."""
        st = StressTester(FakeNav({"AAA": 800.0}, cash=200.0))
        out = st.reverse(drawdown_limit_pct=0.10, peak_nav=1000.0)
        assert out["measurable"] is True
        assert out["loss_to_halt_usd"] == pytest.approx(100.0)
        assert out["uniform_move_to_halt_pct"] == pytest.approx(-12.5, abs=0.01)

    def test_cash_cushions_the_required_move(self):
        """More cash = a bigger equity move needed to breach. This is the
        intuition the cash floor is supposed to buy, made explicit."""
        lean = StressTester(FakeNav({"AAA": 1000.0}, cash=0.0)).reverse(0.10, 1000.0)
        rich = StressTester(FakeNav({"AAA": 500.0}, cash=500.0)).reverse(0.10, 1000.0)
        assert abs(rich["uniform_move_to_halt_pct"]) > abs(lean["uniform_move_to_halt_pct"])

    def test_already_breached_says_so(self):
        out = StressTester(FakeNav({"AAA": 800.0})).reverse(0.10, peak_nav=1000.0)
        assert out["already_breached"] is True

    def test_small_position_cannot_breach_alone(self):
        """$100 of loss is needed; TINY is only $50, so even going to zero it
        cannot trip the halt by itself."""
        out = StressTester(FakeNav({"BIG": 950.0, "TINY": 50.0}, cash=0.0)).reverse(0.10, 1000.0)
        tiny = next(r for r in out["single_name"] if r["symbol"] == "TINY")
        assert tiny["possible"] is False
        big = next(r for r in out["single_name"] if r["symbol"] == "BIG")
        assert big["possible"] is True

    def test_no_exposure_is_not_measurable(self):
        assert StressTester(FakeNav({}, cash=1000.0)).reverse(0.10, 1000.0)["measurable"] is False


class TestHistoricalReplay:
    def test_missing_history_is_reported_not_backfilled(self):
        def fetch(symbol, lookback_days=250, start=None, end=None):
            raise ValueError("no data")

        out = StressTester(FakeNav({"AAA": 100.0}), fetcher=fetch).replay()
        assert out["measurable"] is False
        assert all(s["measurable"] is False for s in out["scenarios"])

    def test_pnl_follows_the_real_window_return(self):
        def fetch(symbol, lookback_days=250, start=None, end=None):
            return FakeBars(symbol, [100.0, 50.0], ["2020-02-19", "2020-03-23"])

        out = StressTester(FakeNav({"AAA": 1000.0}), fetcher=fetch).replay()
        covid = next(s for s in out["scenarios"] if s["key"] == "covid_2020")
        assert covid["pnl_usd"] == pytest.approx(-500.0)
        assert covid["nav_change_pct"] == pytest.approx(-50.0)


# --- pre-trade gate ---------------------------------------------------------

class TestCashFloorGate:
    def test_percentage_cash_floor_blocks_the_order(self):
        """This floor previously existed only as a post-hoc alarm — the book
        could be traded to zero cash and merely be told about it afterwards."""
        limits = RiskLimits(min_cash_pct=0.05, max_position_pct=0.9,
                            max_order_notional_pct=0.9)
        nav = FakeNav({"AAA": 1800.0}, cash=200.0).compute()
        order = Order(venue="paper", symbol="BBB", side=Side.BUY, qty=1.5)
        decision = RiskGate(limits).check(order, quote_price=100.0, nav=nav)
        assert decision.ok is False
        assert any("floor 5.0%" in b for b in decision.breaches)

    def test_order_inside_the_floor_passes(self):
        limits = RiskLimits(min_cash_pct=0.05, max_position_pct=0.9,
                            max_order_notional_pct=0.9)
        nav = FakeNav({"AAA": 1800.0}, cash=200.0).compute()
        order = Order(venue="paper", symbol="BBB", side=Side.BUY, qty=0.5)
        assert RiskGate(limits).check(order, quote_price=100.0, nav=nav).ok is True

    def test_sells_are_not_blocked_by_the_cash_floor(self):
        # Concentration is deliberately not binding here, so the only thing that
        # could reject this order is the cash floor — which must not apply to a
        # sell, since selling is how you *restore* cash.
        limits = RiskLimits(min_cash_pct=0.50, max_position_pct=1.0,
                            max_order_notional_pct=0.9)
        nav = FakeNav({"AAA": 1800.0}, cash=0.0).compute()
        order = Order(venue="paper", symbol="AAA", side=Side.SELL, qty=1.0)
        assert RiskGate(limits).check(order, quote_price=100.0, nav=nav).ok is True
