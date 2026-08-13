"""Tests for the statistical-honesty layer.

The point of this module is to stop a lucky backtest reading as an edge, so the
tests are mostly adversarial: feed it noise and assert that it refuses to be
impressed.
"""

import math
import random

import pytest

from app.fund import statistics as S


def _noise(n, mu=0.0004, sd=0.012, seed=11):
    rng = random.Random(seed)
    return [rng.gauss(mu, sd) for _ in range(n)]


class TestSharpeInference:
    def test_pure_noise_is_not_reported_as_an_edge(self):
        """A zero-edge series can still show a flattering Sharpe. The CI must
        span zero, which is the whole reason this module exists."""
        a = S.assess_series(_noise(252, mu=0.0003), n_trials=1)
        assert a["reliable"] is True
        assert a["could_be_zero"] is True
        assert any("cannot distinguish this from no edge" in w for w in a["warnings"])

    def test_standard_error_shrinks_with_more_data(self):
        few = S.sharpe_standard_error(1.0, 100)
        many = S.sharpe_standard_error(1.0, 10_000)
        assert few > many
        # Lo (2002): SE = sqrt((1 + SR^2/2)/T)
        assert few == pytest.approx(math.sqrt((1 + 0.5) / 100))

    def test_standard_error_needs_two_observations(self):
        assert S.sharpe_standard_error(1.0, 1) is None

    def test_short_series_refuses_inference_rather_than_guessing(self):
        a = S.assess_series([0.01] * 10)
        assert a["reliable"] is False
        assert "below the" in a["reason"]


class TestAnnualisation:
    def test_iid_returns_give_the_sqrt_q_rule(self):
        ann = S.annualisation_factor(_noise(600, seed=3))
        assert ann["usable"] is True
        assert ann["factor"] == pytest.approx(math.sqrt(252), rel=0.10)

    def test_positive_autocorrelation_lowers_the_factor(self):
        """Serial correlation makes sqrt(q) overstate Sharpe. Getting the sign
        wrong here would flatter every trending strategy."""
        rng = random.Random(5)
        r = [0.0]
        for _ in range(600):
            r.append(0.6 * r[-1] + rng.gauss(0.0004, 0.01))
        ann = S.annualisation_factor(r)
        assert ann["autocorrelations"][0] > 0.4
        assert ann["factor"] < ann["naive_factor"]
        assert ann["inflation_vs_naive"] > 0

    def test_flags_smoothed_returns(self):
        rng = random.Random(9)
        r = [0.0]
        for _ in range(400):
            r.append(0.5 * r[-1] + rng.gauss(0.0005, 0.008))
        a = S.assess_series(r)
        assert any("smoothed" in w or "serially correlated" in w for w in a["warnings"])


class TestSelectionBias:
    def test_single_trial_has_no_penalty(self):
        assert S.selection_penalty(1.0, 1, 252)["applies"] is False

    def test_more_trials_raise_the_bar(self):
        lo = S.expected_max_sharpe(5)
        hi = S.expected_max_sharpe(500)
        assert hi > lo > 0

    def test_best_of_many_noise_runs_is_flagged(self):
        """The exact failure this catches: sweeping 50 configurations and
        reporting the winner as if it were the only thing tried."""
        r = _noise(252, mu=0.0003)
        sr = S.sharpe_per_period(r)
        sel = S.selection_penalty(sr, 50, len(r))
        assert sel["applies"] is True
        assert sel["clears_noise"] is False


class TestMinTrackRecord:
    def test_below_target_sharpe_has_no_finite_answer(self):
        out = S.min_track_record_length(-0.2, 250)
        assert out["usable"] is False
        assert "no amount of additional data" in out["reason"]

    def test_weak_edge_needs_more_data_than_strong_edge(self):
        weak = S.min_track_record_length(0.02, 250, returns=_noise(250))
        strong = S.min_track_record_length(0.20, 250, returns=_noise(250))
        assert weak["required_obs"] > strong["required_obs"]

    def test_negative_skew_demands_more_data(self):
        """Negative skew is the shape that flatters Sharpe, so it should raise
        the evidentiary bar, not lower it."""
        rng = random.Random(4)
        sym = [rng.gauss(0.001, 0.01) for _ in range(400)]
        neg = [rng.gauss(0.0015, 0.006) for _ in range(390)] + [-0.09] * 10
        sr = 0.1
        a = S.min_track_record_length(sr, 400, returns=sym)
        b = S.min_track_record_length(sr, 400, returns=neg)
        assert S.skewness(neg) < S.skewness(sym)
        assert b["required_obs"] > a["required_obs"]


class TestMoments:
    def test_kurtosis_of_normal_is_about_three(self):
        assert S.kurtosis(_noise(5000, seed=2)) == pytest.approx(3.0, abs=0.35)

    def test_fat_tails_are_flagged(self):
        rng = random.Random(1)
        r = [rng.gauss(0.0005, 0.006) for _ in range(380)] + [-0.12, 0.11, -0.14, 0.13] * 5
        a = S.assess_series(r)
        assert S.kurtosis(r) > 5.0
        assert any("kurtosis" in w for w in a["warnings"])
