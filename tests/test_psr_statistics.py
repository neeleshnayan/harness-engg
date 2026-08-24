"""Boundary and null tests for the four PSR-family pure functions in
app.fund.statistics: psr_from_moments, psr_from_series, implied_target_sharpe,
sharpe_bar_for_psr — plus sharpe_advantage_series, whose identity the whole
premia-advantage design rests on.

Every assertion here is either an exact edge (n_obs=1 vs 2, psr_pct=0 vs
0.001), a null case with a known trivial answer (z=0 gives psr_pct==50), or a
round trip that proves the inversion functions actually invert psr_from_moments
and psr_from_series rather than merely resembling them. Tolerances are stated
explicitly on every float comparison; nothing here uses pytest.approx's
default relative tolerance blind.
"""

import math
import random

import pytest

from app.fund.statistics import (
    implied_target_sharpe,
    mean_std,
    psr_from_moments,
    psr_from_series,
    sharpe_advantage_series,
    sharpe_bar_for_psr,
    sharpe_bar_for_psr_from_moments,
)


# ---------------------------------------------------------------------------
# A. BOUNDARIES
# ---------------------------------------------------------------------------


def test_psr_from_moments_n_obs_one_is_unusable():
    """sqrt(n - 1) is the whole engine of the z statistic; at n=1 it is
    sqrt(0) and there is no sample at all to speak of."""
    out = psr_from_moments(1, 0.05, 0.0, 3.0)
    assert out["usable"] is False
    assert "fewer than 2 observations" in out["reason"]


def test_psr_from_moments_n_obs_two_is_usable():
    """The other side of the same boundary: two observations is degenerate
    but not undefined, and the function must not refuse it."""
    out = psr_from_moments(2, 0.05, 0.0, 3.0)
    assert out["usable"] is True
    assert out["n_obs"] == 2


def test_psr_from_moments_nonpositive_shape_refuses_a_number():
    """A large positive skew paired with a large positive Sharpe drives
    shape = 1 - g3*SR + (g4-1)/4*SR^2 negative. That is a degenerate moment
    estimate, and the function must say so rather than take a sqrt of a
    negative number or silently clamp it."""
    sr, g3, g4 = 5.0, 3.0, 3.0
    shape = 1.0 - g3 * sr + ((g4 - 1.0) / 4.0) * (sr ** 2)
    assert shape < 0, "test construction must actually drive shape negative"
    out = psr_from_moments(100, sr, g3, g4)
    assert out["usable"] is False
    assert "non-positive variance term" in out["reason"]


def test_psr_from_series_length_zero_is_unmeasurable():
    out = psr_from_series([])
    assert out["measurable"] is False
    assert out["n_obs"] == 0
    assert "usable observation" in out["reason"]


def test_psr_from_series_length_one_is_unmeasurable():
    out = psr_from_series([0.01])
    assert out["measurable"] is False
    assert out["n_obs"] == 1


def test_psr_from_series_length_two_is_measurable():
    """Two distinct observations carry a mean and a (nonzero) sample stdev,
    so a per-observation Sharpe exists even though it is a wild estimate."""
    out = psr_from_series([0.01, 0.02])
    assert out["measurable"] is True
    assert out["n_obs"] == 2
    assert out["psr_pct"] is not None


@pytest.mark.parametrize("psr_pct", [0.0, 100.0])
def test_implied_target_sharpe_exact_zero_and_hundred_are_unmeasurable(psr_pct):
    """Phi^-1(0) and Phi^-1(1) are both infinite; the target the PSR was
    measured against cannot be recovered at the exact boundary."""
    series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003]
    out = implied_target_sharpe(psr_pct, series)
    assert out["measurable"] is False
    assert "cannot be inverted" in out["reason"]


def test_implied_target_sharpe_fifty_is_measurable():
    series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003]
    out = implied_target_sharpe(50.0, series)
    assert out["measurable"] is True


@pytest.mark.parametrize("psr_pct", [0.001, 99.999])
def test_implied_target_sharpe_just_inside_each_end_is_measurable(psr_pct):
    """The refusal in the two tests above must sit exactly at the boundary,
    not swallow values that are merely close to it."""
    series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003]
    out = implied_target_sharpe(psr_pct, series)
    assert out["measurable"] is True
    assert out["target_per_obs"] is not None


@pytest.mark.parametrize("level_pct", [0.0, 100.0])
def test_sharpe_bar_for_psr_zero_and_hundred_are_unmeasurable(level_pct):
    series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003]
    out = sharpe_bar_for_psr(level_pct, series)
    assert out["measurable"] is False
    assert "not a probability strictly" in out["reason"]


def test_sharpe_bar_for_psr_fifty_is_measurable():
    series = [0.01, -0.02, 0.015, -0.005, 0.02, -0.01, 0.008, -0.003]
    out = sharpe_bar_for_psr(50.0, series)
    assert out["measurable"] is True
    assert out["sharpe_per_obs"] is not None


# ---------------------------------------------------------------------------
# B. NULL TESTS
# ---------------------------------------------------------------------------


def test_psr_from_moments_sharpe_equal_target_zero_gives_exactly_fifty():
    """z = (SR - SR*) * sqrt(n-1) / sqrt(shape) is exactly zero when SR ==
    target, independent of n, skew or kurtosis — and Phi(0) == 0.5 exactly."""
    out = psr_from_moments(37, 0.2, -0.4, 5.0, target_sharpe=0.2)
    assert out["psr_pct"] == 50.0


def test_psr_from_moments_sharpe_equal_target_zero_at_target_zero():
    out = psr_from_moments(37, 0.0, -0.4, 5.0, target_sharpe=0.0)
    assert out["psr_pct"] == 50.0


def test_psr_from_moments_sharpe_equal_nonzero_target_gives_exactly_fifty():
    """Same null case restated at a non-zero target, so the 50.0 result is
    shown not to be an artefact of target_sharpe defaulting to zero."""
    out = psr_from_moments(200, 0.35, 0.6, 4.2, target_sharpe=0.35)
    assert out["psr_pct"] == 50.0


def test_implied_target_sharpe_at_fifty_recovers_the_series_own_sharpe():
    """The null test that proves the inversion is an inversion: z=0 at
    psr_pct=50, so the recovered target must equal the series' own
    per-observation Sharpe exactly (to float precision), independent of n,
    skew, or kurtosis, which all cancel out of the z=0 term."""
    series = [0.012, -0.007, 0.031, 0.004, -0.019, 0.008, 0.0, -0.011, 0.022, 0.005]
    measured = psr_from_series(series)
    assert measured["measurable"] is True
    out = implied_target_sharpe(50.0, series)
    assert out["measurable"] is True
    # Against the RAW Sharpe, at float precision. Both figures are computed from
    # the series rather than round-tripped through a reported field, so this is
    # the exact identity with nothing between it and the arithmetic.
    mu, sd = mean_std(series)
    assert out["target_per_obs"] == pytest.approx(mu / sd, abs=1e-12)
    assert out["target_per_obs"] == pytest.approx(out["sharpe_per_obs"], abs=1e-12)
    # AND THE PUBLIC FIELD'S PRECISION CEILING, stated rather than discovered:
    # `psr_from_series` rounds `sharpe_per_obs` to 8 decimals for the record, so
    # a caller comparing against THAT cannot do better than ~1e-8. Asserted so
    # nobody later "tightens" this test to 1e-12 against the rounded field and
    # calls the resulting failure a defect.
    assert measured["sharpe_per_obs"] == pytest.approx(mu / sd, abs=1e-8)


def test_sharpe_bar_for_psr_at_fifty_returns_the_target_itself():
    """At level 50, z=0, and the quadratic in sharpe_bar_for_psr collapses to
    (x - T)^2 * (n-1) == 0, i.e. x == T exactly."""
    series = [0.012, -0.007, 0.031, 0.004, -0.019, 0.008, 0.0, -0.011, 0.022, 0.005]
    target = 0.017
    out = sharpe_bar_for_psr(50.0, series, target_sharpe=target)
    assert out["measurable"] is True
    assert out["sharpe_per_obs"] == pytest.approx(target, abs=1e-9)


# ---------------------------------------------------------------------------
# C. ROUND TRIP
# ---------------------------------------------------------------------------


def _make_series(seed: int, n: int = 120) -> list:
    rng = random.Random(seed)
    return [rng.gauss(0.001, 0.02) for _ in range(n)]


ROUND_TRIP_SEEDS = [1, 2, 3]


@pytest.mark.parametrize("seed", ROUND_TRIP_SEEDS)
def test_round_trip_implied_target_of_own_psr_is_zero(seed):
    """psr_from_series measures against target 0 by default; feeding its own
    reported PSR back through implied_target_sharpe must recover ~0.0, because
    that IS the target it was computed against. Series constructed with
    random.Random(seed) for seed in {1, 2, 3} so this is reproducible.

    THE TOLERANCE IS 1e-5 AND THAT IS A PROPERTY OF THE API, not slack. The
    reported `psr_pct` is rounded to three decimals for the record, so the
    probability handed back carries up to 5e-6 of rounding; near p=0.5 the
    normal inverse turns that into ~1.25e-5 of z and the recovered target moves
    by `sqrt(shape/(n-1))` times it — order 1e-6 on these series. Round-tripping
    through a DISPLAY-rounded field cannot do better, and a test asserting 1e-9
    here would be asserting a precision the stored record does not carry.
    """
    series = _make_series(seed)
    measured = psr_from_series(series)
    assert measured["measurable"] is True
    inverted = implied_target_sharpe(measured["psr_pct"], series)
    assert inverted["measurable"] is True
    assert inverted["target_per_obs"] == pytest.approx(0.0, abs=1e-5)


ROUND_TRIP_LEVELS = [10, 25, 50, 75, 90, 99]


@pytest.mark.parametrize("seed", ROUND_TRIP_SEEDS)
@pytest.mark.parametrize("level", ROUND_TRIP_LEVELS)
def test_round_trip_sharpe_bar_feeds_back_to_the_same_level(seed, level):
    """sharpe_bar_for_psr(L, series) returns the per-observation Sharpe a
    series of this shape needs to hit level L. Feeding that Sharpe back
    through psr_from_moments with the same n/skew/kurtosis must reproduce L
    to within 1e-6 (sharpe_bar_for_psr already self-verifies its root to
    1e-6, so the round trip cannot be looser than that)."""
    series = _make_series(seed)
    measured = psr_from_series(series)
    assert measured["measurable"] is True
    n = measured["n_obs"]
    skew = measured["skew"]
    kurt = measured["kurtosis"]

    bar = sharpe_bar_for_psr(level, series, target_sharpe=0.0)
    assert bar["measurable"] is True
    x = bar["sharpe_per_obs"]

    back = psr_from_moments(n, x, skew, kurt, target_sharpe=0.0)
    assert back["usable"] is True
    assert back["psr_pct"] == pytest.approx(float(level), abs=1e-6)


# ---------------------------------------------------------------------------
# D. FLAT-SERIES REFUSALS
# ---------------------------------------------------------------------------


def test_psr_from_series_flat_series_is_unmeasurable_with_dispersion_reason():
    """A constant series has NO dispersion, not a tiny one — asserted against
    the exact sentence, not a shared word, so a refactor that changes the
    wording is caught rather than silently accepted."""
    out = psr_from_series([0.001] * 100)
    assert out["measurable"] is False
    assert out["reason"] == (
        "the series has no dispersion, so no Sharpe exists for "
        "it and no probability can be attached to one"
    )


def test_implied_target_sharpe_flat_series_is_unmeasurable_with_dispersion_reason():
    out = implied_target_sharpe(50.0, [0.001] * 100)
    assert out["measurable"] is False
    assert out["reason"] == (
        "no usable return series, so the target this PSR was "
        "measured against cannot be recovered"
    )


def test_sharpe_bar_for_psr_flat_series_is_unmeasurable_with_dispersion_reason():
    out = sharpe_bar_for_psr(50.0, [0.001] * 100)
    assert out["measurable"] is False
    assert out["reason"] == "no usable return series to state a bar against"


def test_small_but_real_dispersion_is_still_measurable():
    """The flat-series floor must not swallow genuine signal.

    A series with a small but ORDINARY dispersion — a per-observation Sharpe of
    about 0.1, which is a perfectly normal daily figure — must be measured, not
    refused alongside a constant one. This is the other side of the
    `_no_dispersion` boundary and the reason that floor is relative to the mean
    rather than an absolute number.
    """
    series = [0.00001 + (0.0001 if i % 2 else -0.0001) for i in range(200)]
    out = psr_from_series(series)
    assert out["measurable"] is True
    assert out["psr_pct"] is not None
    assert implied_target_sharpe(50.0, series)["measurable"] is True
    assert sharpe_bar_for_psr(50.0, series)["measurable"] is True


def test_a_near_constant_series_is_UNDEFINED_not_certain():
    """THE OTHER degenerate shape, and it refuses on its own ground.

    `[0.001, 0.0010001] * 50` clears the `_no_dispersion` floor — its standard
    deviation is 5.0e-8, five orders of magnitude above it — and yet its
    per-observation Sharpe is about 19,900, at which Bailey & López de Prado's
    variance term `1 - g3*SR + (g4-1)/4*SR^2` is hugely NEGATIVE and the
    expansion means nothing at all.

    So the two guards refuse for two different reasons and BOTH refuse, which is
    the point: `_no_dispersion` asks "does a Sharpe exist", the shape term asks
    "is this expansion valid", and a series can pass the first and fail the
    second. What must never happen is a confident number, and what must never
    happen in the gate is a PASS — an unreadable luck filter FAILS the candidate
    (see `test_gate.py`'s absent-PSR cases). Written after a boundary sweep
    asserted this series was measurable and it was not; the spec was wrong and
    the code was right, which is worth a test that says so.
    """
    series = [0.001, 0.0010001] * 50
    out = psr_from_series(series)
    assert out["measurable"] is False
    assert out["psr_pct"] is None
    assert "non-positive variance term" in (out["reason"] or "")
    # NOT the flat-series sentence — the two refusals are distinguishable, and a
    # reader who cannot tell them apart would look for the wrong defect.
    assert "no dispersion" not in (out["reason"] or "")


# ---------------------------------------------------------------------------
# E. DIRECTION / MONOTONICITY
# ---------------------------------------------------------------------------


def test_psr_from_moments_increasing_in_sharpe():
    """Raising the observed Sharpe with everything else fixed must raise the
    probability the true Sharpe beats the target — a sign error here would
    invert what the whole gate treats as evidence of an edge."""
    n, g3, g4 = 100, 0.0, 3.0
    psrs = [
        psr_from_moments(n, sr, g3, g4)["psr_pct"]
        for sr in (0.0, 0.05, 0.1, 0.2, 0.3)
    ]
    assert psrs == sorted(psrs)
    assert psrs[0] < psrs[-1]


def test_psr_from_moments_decreasing_in_target_sharpe():
    """Raising the bar (target_sharpe) with the observed Sharpe fixed must
    lower the probability of clearing it."""
    n, sr, g3, g4 = 100, 0.15, 0.0, 3.0
    psrs = [
        psr_from_moments(n, sr, g3, g4, target_sharpe=t)["psr_pct"]
        for t in (0.0, 0.05, 0.1, 0.15, 0.2)
    ]
    assert psrs == sorted(psrs, reverse=True)
    assert psrs[0] > psrs[-1]


def test_target_above_sharpe_puts_psr_below_fifty():
    out = psr_from_moments(100, 0.05, 0.0, 3.0, target_sharpe=0.2)
    assert out["psr_pct"] < 50.0


def test_more_observations_raises_psr_for_a_positive_sharpe():
    """More data at the same shape (same per-observation Sharpe, skew,
    kurtosis) must make a genuine positive edge look MORE confident, not
    less — n enters only through sqrt(n-1) in the numerator of z."""
    sr, g3, g4 = 0.1, 0.0, 3.0
    psr_50 = psr_from_moments(50, sr, g3, g4)["psr_pct"]
    psr_500 = psr_from_moments(500, sr, g3, g4)["psr_pct"]
    assert psr_500 > psr_50


# ---------------------------------------------------------------------------
# F. sharpe_advantage_series
# ---------------------------------------------------------------------------


def test_sharpe_advantage_mismatched_lengths_names_both_counts():
    out = sharpe_advantage_series([0.01, 0.02, 0.03], [0.01, 0.02])
    assert out["measurable"] is False
    assert "3" in out["reason"]
    assert "2" in out["reason"]


def test_sharpe_advantage_length_below_two_is_unmeasurable():
    out = sharpe_advantage_series([0.01], [0.02])
    assert out["measurable"] is False
    assert "1" in out["reason"]


def test_sharpe_advantage_flat_strategy_leg_is_unmeasurable():
    strategy = [0.005] * 20
    benchmark = [0.01 * ((-1) ** i) for i in range(20)]
    out = sharpe_advantage_series(strategy, benchmark)
    assert out["measurable"] is False
    assert "no dispersion" in out["reason"]


def test_sharpe_advantage_flat_benchmark_leg_is_unmeasurable():
    strategy = [0.01 * ((-1) ** i) for i in range(20)]
    benchmark = [0.005] * 20
    out = sharpe_advantage_series(strategy, benchmark)
    assert out["measurable"] is False
    assert "no dispersion" in out["reason"]


@pytest.mark.parametrize("seed", [11, 22])
def test_sharpe_advantage_mean_equals_difference_of_leg_sharpes(seed):
    """THE KEY IDENTITY the whole design rests on: d_t = s_t/sd_s - b_t/sd_b
    means mean(d) == SR_s - SR_b exactly, per observation. Two independently
    constructed random series verify it to float precision."""
    rng = random.Random(seed)
    strategy = [rng.gauss(0.002, 0.015) for _ in range(80)]
    benchmark = [rng.gauss(0.0005, 0.01) for _ in range(80)]
    out = sharpe_advantage_series(strategy, benchmark)
    assert out["measurable"] is True

    mu_s = sum(strategy) / len(strategy)
    sd_s = (sum((x - mu_s) ** 2 for x in strategy) / (len(strategy) - 1)) ** 0.5
    mu_b = sum(benchmark) / len(benchmark)
    sd_b = (sum((x - mu_b) ** 2 for x in benchmark) / (len(benchmark) - 1)) ** 0.5
    expected = mu_s / sd_s - mu_b / sd_b

    assert out["mean_per_obs"] == pytest.approx(expected, abs=1e-12)
    assert out["sharpe_strategy_per_obs"] == pytest.approx(mu_s / sd_s, abs=1e-12)
    assert out["sharpe_benchmark_per_obs"] == pytest.approx(mu_b / sd_b, abs=1e-12)


def test_sharpe_advantage_constant_multiple_legs_is_unmeasurable():
    """Two legs that are exact constant multiples of each other have an
    advantage series with zero dispersion — a degenerate estimate, not a
    certain advantage."""
    benchmark = [0.01, -0.02, 0.03, 0.015, -0.005, 0.02, -0.01, 0.008, 0.012, -0.004]
    strategy = [2.0 * x for x in benchmark]
    out = sharpe_advantage_series(strategy, benchmark)
    assert out["measurable"] is False
    assert out["reason"] == (
        "the two legs differ by a constant, so the advantage "
        "has no dispersion and no probability attaches to it"
    )


# ---------------------------------------------------------------------------
# G. THE BOUNDARIES THE FIRST SWEEP MISSED
#
# Found by the Gauntlet's boundary-table pass over the diff: each of these
# inequalities was probed far from its edge and never AT it.
# ---------------------------------------------------------------------------

def test_a_shape_term_of_EXACTLY_zero_is_undefined_not_certain():
    """`shape <= 0` was only ever probed strictly negative.

    The boundary is reachable in closed form: `1 - g3*sr + (g4-1)/4*sr^2 == 0`
    at sr = 1 for g3 = 1 + (g4-1)/4. With g4 = 3.0 that is g3 = 1.5, and the
    variance term lands on zero exactly.
    """
    exact = psr_from_moments(100, 1.0, 1.5, 3.0, 0.0)
    assert exact["usable"] is False
    assert "non-positive variance term" in exact["reason"]
    # a hair to the STABLE side is usable, so the refusal is a boundary and not
    # a whole region quietly swallowed
    assert psr_from_moments(100, 1.0, 1.49, 3.0, 0.0)["usable"] is True


def test_the_dispersion_floor_is_probed_ON_BOTH_SIDES_of_its_boundary():
    """`sd <= max(1e-12, |mu| * 1e-9)`, straddled as tightly as floats allow.

    Constructed as a two-point series: for [mu - h, mu + h] the sample standard
    deviation (ddof=1) is h * sqrt(2), so h is the dial.

    EXACT EQUALITY IS NOT CONSTRUCTIBLE HERE and the test says so rather than
    pretending: aiming h at the floor lands on 1.0000000514e-09 against a floor
    of 1e-09, because the round trip through sqrt(2) and the variance sum is not
    exact at this scale. So the boundary is bracketed at 0.9x and 1.1x, which is
    what a float boundary can honestly be probed at.
    """
    mu = 1.0
    floor = abs(mu) * 1e-9
    def two_point(scale):
        h = floor * scale / math.sqrt(2.0)
        return [mu - h, mu + h]
    under = two_point(0.9)
    assert mean_std(under)[1] < floor
    assert psr_from_series(under)["measurable"] is False
    assert "no dispersion" in psr_from_series(under)["reason"]
    over = two_point(1.1)
    assert mean_std(over)[1] > floor
    assert psr_from_series(over)["measurable"] is True


def test_a_TWO_POINT_advantage_is_always_degenerate_and_three_is_the_floor():
    """The advantage's real minimum sample size is THREE, not two.

    Not an implementation choice — an arithmetic fact, and worth pinning because
    it is surprising. Standardising a two-point series puts its values at
    exactly -1/sqrt(2) and +1/sqrt(2) whatever the numbers were, so the
    vol-scaled difference `x/sd_s - y/sd_b` is the SAME on both points for ANY
    two pairs. The advantage therefore has no dispersion at n=2 and no
    probability attaches to it, and the refusal comes from the degeneracy check
    rather than from the length check.
    """
    two = sharpe_advantage_series([0.01, -0.02], [0.005, 0.004])
    assert two["measurable"] is False
    assert "differ by a constant" in two["reason"]     # NOT the length reason
    three = sharpe_advantage_series([0.01, -0.02, 0.004],
                                    [0.005, 0.004, -0.01])
    assert three["measurable"] is True
    assert three["n"] == 3
    one = sharpe_advantage_series([0.01], [0.005])
    assert one["measurable"] is False
    assert "paired observation" in one["reason"]       # the LENGTH reason


def test_the_quadratic_handles_a_vanishing_leading_coefficient():
    """`abs(a) < 1e-18` is the degenerate branch where the quadratic collapses
    to a linear equation. Reached by making `(n-1) == z^2 (g4-1)/4` exactly."""
    from statistics import NormalDist
    level = 90.0
    z = NormalDist().inv_cdf(level / 100.0)
    n = 50
    g4 = 1.0 + 4.0 * (n - 1) / (z * z)
    got = sharpe_bar_for_psr_from_moments(level, n, 0.3, g4, 0.0)
    # Either it solves the linear case or it says it cannot — what it must NOT
    # do is raise, and what it must not do is return a root that fails its own
    # verification.
    assert got["measurable"] in (True, False)
    if got["measurable"]:
        back = psr_from_moments(n, got["sharpe_per_obs"], 0.3, g4, 0.0)
        assert back["psr_pct"] == pytest.approx(level, abs=1e-6)
