"""The engine's annualisation clock, and whether the series agrees with it.

THE INCIDENT THESE GUARD AGAINST (crypto program W3 blocker 1, 2026-08-27):
``psr_inputs`` reproduced the engine's ``Annual Standard Deviation`` with a
LITERAL ``sqrt(252.0)`` while the run's own ``tradingDaysPerYear`` was read
fifty lines above it in the same function. The two agreed on all 196 stored
result files (measured: 196 of 196 carry 252, no other value appears) and
would have diverged on the first crypto run — reporting ``reproduces: False``,
which reads as "the engine changed its formula" when the checker had simply
used the wrong clock.

The second half is the blocker itself: LEAN annualises by
``Settings.TradingDaysPerYear``, which it takes from the BROKERAGE MODEL and
not from the security type. A 24/7 series scored at 252 understates every
sqrt-annualised statistic by sqrt(365/252) = 1.2034, and before this diff no
field on a stored verdict said so.

The tests are written so that restoring either defect turns one of them red:
the clock is proved READ by MOVING it (an assertion that it equals 252 cannot
tell a read from a hardcoded duplicate that happens to agree today).
"""
import math

import pytest

from app.fund.leanrunner import (
    CLOCK_AGREEMENT_TOLERANCE,
    LINEARLY_ANNUALISED_STATISTICS,
    SQRT_ANNUALISED_STATISTICS,
    annualisation_clock,
    psr_inputs,
)


def calendar_days(n: int, start: str = "2024-01-01") -> list[str]:
    """n consecutive CALENDAR dates — the shape LEAN emits for both classes."""
    from datetime import date, timedelta
    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=i)).isoformat() for i in range(n)]


def trading_days(n: int, start: str = "2024-01-01") -> list[str]:
    """n consecutive WEEKDAYS — a series that really is observed ~252/yr."""
    from datetime import date, timedelta
    out, d = [], date.fromisoformat(start)
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


# --- the clock the engine used, read rather than typed --------------------

def test_the_reproduction_uses_the_RUNS_clock_not_a_literal_252():
    """THE MOVE TEST. A hardcoded 252 that agrees today cannot pass this.

    The series is built so its standard deviation times sqrt(365) is exactly
    the published figure. Under the old literal the recomputation was
    sd*sqrt(252) = 0.0829, `reproduces` read False, and a reader would have
    concluded the engine's formula had changed.
    """
    n = 730
    series = [0.001 if i % 2 else -0.001 for i in range(n)]  # sd = 0.001 exactly
    published = 0.001 * math.sqrt(365.0)
    got = psr_inputs(
        {"Annual Standard Deviation": f"{published:.5f}"},
        {"strategy": series, "dates": calendar_days(n)},
        {"tradingDaysPerYear": 365},
    )
    rep = got["engine_volatility_reproduction"]
    assert rep["clock"] == 365.0
    assert rep["clock_assumed"] is False
    assert rep["series_stdev_annualised"] == pytest.approx(published, abs=5e-4)
    assert rep["reproduces"] is True
    # And the same series against a 252 run does NOT reproduce, which is what
    # makes the assertion above a measurement rather than a tautology.
    at_252 = psr_inputs(
        {"Annual Standard Deviation": f"{published:.5f}"},
        {"strategy": series, "dates": calendar_days(n)},
        {"tradingDaysPerYear": 252},
    )
    assert at_252["engine_volatility_reproduction"]["reproduces"] is False


def test_an_absent_clock_is_named_as_assumed_never_reported_as_read():
    n = 60
    series = [0.001 if i % 2 else -0.001 for i in range(n)]
    got = psr_inputs({"Annual Standard Deviation": "0.016"},
                     {"strategy": series, "dates": calendar_days(n)}, None)
    rep = got["engine_volatility_reproduction"]
    assert rep["clock_assumed"] is True
    assert rep["clock"] == 252.0
    assert "ASSUMED" in rep["note"]
    # The field that says what the RUN carried stays absent — the assumption
    # lives in the reproduction block and never leaks into the capture.
    assert got["trading_days_per_year"] is None


# --- both series shapes ---------------------------------------------------

def test_an_equity_shaped_run_reports_the_engine_understating():
    """LEAN pads the equity curve with weekend zeros, so the series it scored
    carries 365.25 observations a year while the engine annualised at 252."""
    n = 1000
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)},
                              {"tradingDaysPerYear": 252})
    assert got["state"] == "engine_understates"
    assert got["series_obs_per_year"] == pytest.approx(365.25, abs=0.2)
    assert got["engine_obs_per_year"] == 252.0
    assert got["factor_for_sqrt_annualised"] == pytest.approx(1.2039, abs=0.002)
    assert got["factor_for_linearly_annualised"] == pytest.approx(1.4494, abs=0.005)
    assert "UNDERSTATES" in got["note"]


def test_a_crypto_shaped_run_at_the_equity_clock_is_the_blocker_and_it_shows():
    """The reason this batch exists: 24/7 daily bars, scored at 252."""
    n = 1000
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)},
                              {"tradingDaysPerYear": 252})
    assert got["state"] == "engine_understates"
    # sqrt(365.25/252): the factor the validator measured, on the series' own
    # calendar rather than on an assumed one.
    assert got["factor_for_sqrt_annualised"] == pytest.approx(1.2039, abs=0.002)


def test_a_crypto_run_at_the_crypto_clock_agrees():
    """A crypto algorithm that DOES set a crypto brokerage model is scored at
    365 and the two clocks then agree — the disclosure must be quiet there."""
    n = 1000
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)},
                              {"tradingDaysPerYear": 365})
    assert got["state"] == "agree"
    assert got["factor_for_sqrt_annualised"] == pytest.approx(1.0003, abs=0.001)
    assert "the same clock" in got["note"]


def test_a_pure_weekday_series_is_NOT_a_252_series_and_the_clock_says_so():
    """252 is weekdays MINUS holidays, and the difference is not noise.

    Measured here rather than assumed: 750 consecutive weekdays from
    2024-01-01 carry 261.29 observations a year — 3.7% more than the engine's
    convention, a 1.8% re-scaling of every sqrt-annualised statistic. A
    tolerance loose enough to call this AGREE would also swallow a 360-day
    convention, so it reads as a disagreement deliberately.
    """
    n = 750
    got = annualisation_clock({"strategy": [0.0] * n, "dates": trading_days(n)},
                              {"tradingDaysPerYear": 252})
    assert got["series_obs_per_year"] == pytest.approx(261.29, abs=0.05)
    assert got["state"] == "engine_understates"
    assert got["factor_for_sqrt_annualised"] == pytest.approx(1.0183, abs=0.001)


def test_a_weekday_series_with_holidays_removed_agrees_with_252():
    """The other direction of the same fact: a series really observed on the
    ~252 days a US exchange opens, scored at 252, reads AGREE.

    Built by dropping one weekday in 29 from the weekday calendar — 260.6 x
    (1 - 1/29) = 251.6 — which is the arithmetic of ~9 market holidays a year.
    """
    weekdays = trading_days(900)
    dates = [d for i, d in enumerate(weekdays) if i % 29]
    got = annualisation_clock({"strategy": [0.0] * len(dates), "dates": dates},
                              {"tradingDaysPerYear": 252})
    assert got["series_obs_per_year"] == pytest.approx(252, abs=2)
    assert got["state"] == "agree"


def test_an_engine_clock_longer_than_the_series_reports_overstating():
    n = 750
    got = annualisation_clock({"strategy": [0.0] * n, "dates": trading_days(n)},
                              {"tradingDaysPerYear": 365})
    assert got["state"] == "engine_overstates"
    assert got["factor_for_sqrt_annualised"] < 1.0
    assert "OVERSTATES" in got["note"]


# --- absence, in each of its own shapes -----------------------------------

def test_no_series_at_all_is_its_own_state_and_says_so():
    got = annualisation_clock(None, {"tradingDaysPerYear": 252})
    assert got["state"] == "series_absent"
    assert got["series_obs_per_year"] is None
    assert "absent, not 252" in got["series_clock_note"]
    # The engine's own clock is still reported — one side being unreadable
    # does not blank the side that was readable.
    assert got["engine_obs_per_year"] == 252.0
    assert got["engine_annualisation_factor"] == pytest.approx(math.sqrt(252))


def test_an_unparsable_series_clock_is_NOT_the_same_state_as_no_series():
    n = 40
    got = annualisation_clock({"strategy": [0.0] * n, "dates": ["not-a-date"] * n},
                              {"tradingDaysPerYear": 252})
    assert got["state"] == "series_clock_unreadable"
    # The reader's own reason travels verbatim rather than being re-worded.
    assert "could not be parsed" in got["series_clock_note"]


def test_a_missing_engine_clock_is_its_own_state_when_the_series_is_fine():
    n = 400
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)}, {})
    assert got["state"] == "engine_clock_absent"
    assert got["engine_obs_per_year"] is None
    assert got["factor_for_sqrt_annualised"] is None
    assert "absent, not the engine's default" in got["engine_clock_note"]
    # The side that WAS readable is still reported.
    assert got["series_obs_per_year"] == pytest.approx(365.25, abs=0.5)


def test_both_sides_missing_keeps_both_reasons_even_though_state_names_one():
    got = annualisation_clock(None, None)
    assert got["state"] == "series_absent"          # precedence, stated in the docstring
    assert got["series_clock_note"] is not None
    assert got["engine_clock_note"] is not None      # and the other side is NOT lost


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), 0, -252, True, "252", None])
def test_an_unusable_engine_clock_is_absent_never_a_number(bad):
    """A NaN fails every comparison, so `tdy <= 0` alone would let it through
    and the capture would then report NaN as the run's clock."""
    n = 100
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)},
                              {"tradingDaysPerYear": bad})
    assert got["state"] == "engine_clock_absent"
    assert got["engine_obs_per_year"] is None


# --- the agreement boundary ------------------------------------------------

_TOL = CLOCK_AGREEMENT_TOLERANCE
_TICK = 1e-9  # far below the tolerance, far above float noise at this scale


@pytest.mark.parametrize("factor_offset,expect", [
    (-0.20, False),
    (-0.02, False),
    (-(_TOL + _TICK), False),
    (-(_TOL - _TICK), True),        # just inside, below 1.0
    (0.0, True),
    (+(_TOL - _TICK), True),        # just inside, above 1.0
    (+(_TOL + _TICK), False),
    (0.02, False),
    (0.20, False),
])
def test_the_agreement_boundary_is_probed_on_both_sides(factor_offset, expect):
    """A strict-vs-non-strict slip here would silently re-classify a run.

    Probed on the extracted predicate, where the boundary is an ARGUMENT: the
    engine clock is 1.0 and the series clock is ``(1 + offset)**2``, so the
    factor is the offset. Driving the same case through
    ``annualisation_clock`` cannot test the boundary at all — the clock comes
    out of a date arithmetic that lands wherever it lands.
    """
    from app.fund.leanrunner import clocks_agree
    assert clocks_agree((1.0 + factor_offset) ** 2, 1.0) is expect


def test_the_exact_boundary_is_asymmetric_in_binary_floating_point():
    """MEASURED, and recorded so nobody 'fixes' it into a false symmetry.

    The sqrt round-trip is exact here; the SUBTRACTION is not. ``1.005 - 1.0``
    evaluates to 0.004999999999999893 and passes ``<= 0.005``, while
    ``1.0 - 0.995`` evaluates to 0.005000000000000004 and fails it. So the two
    boundary points land on opposite sides of the comparison for reasons that
    have nothing to do with clocks, ``<=`` versus ``<`` AT EXACTLY the
    tolerance is not observable through this function, and a mutation between
    them is EQUIVALENT rather than a test gap. The cases either side (above)
    are what actually pin the comparison.
    """
    from app.fund.leanrunner import clocks_agree
    assert clocks_agree((1.0 + _TOL) ** 2, 1.0) is True
    assert clocks_agree((1.0 - _TOL) ** 2, 1.0) is False
    assert math.sqrt((1.0 + _TOL) ** 2) - 1.0 < _TOL
    assert 1.0 - math.sqrt((1.0 - _TOL) ** 2) > _TOL


def test_the_predicate_the_boundary_table_probes_is_the_one_the_clock_uses():
    """Otherwise the table above would guard a function nobody calls."""
    from app.fund.leanrunner import clocks_agree
    n = 1000
    dates = calendar_days(n)
    got = annualisation_clock({"strategy": [0.0] * n, "dates": dates},
                              {"tradingDaysPerYear": 252})
    series_k = got["series_obs_per_year"]
    assert clocks_agree(series_k, 252.0) is False
    assert got["state"] != "agree"
    assert clocks_agree(series_k, series_k) is True
    same = annualisation_clock({"strategy": [0.0] * n, "dates": dates},
                               {"tradingDaysPerYear": series_k})
    assert same["state"] == "agree"


def test_the_two_annualisation_families_are_named_and_do_not_overlap():
    """The correction differs between them, so a reader holding one number
    would apply the wrong one to variance."""
    assert set(SQRT_ANNUALISED_STATISTICS) & set(LINEARLY_ANNUALISED_STATISTICS) == set()
    assert "Sharpe Ratio" in SQRT_ANNUALISED_STATISTICS
    assert "Annual Variance" in LINEARLY_ANNUALISED_STATISTICS
    # Compounding Annual Return comes from the window's elapsed time, not from
    # K, so a wrong clock does not move it and it belongs to NEITHER family.
    assert "Compounding Annual Return" not in SQRT_ANNUALISED_STATISTICS
    assert "Compounding Annual Return" not in LINEARLY_ANNUALISED_STATISTICS


def test_the_linear_factor_is_the_square_of_the_sqrt_factor():
    n = 1000
    got = annualisation_clock({"strategy": [0.0] * n, "dates": calendar_days(n)},
                              {"tradingDaysPerYear": 252})
    assert got["factor_for_linearly_annualised"] == pytest.approx(
        got["factor_for_sqrt_annualised"] ** 2, rel=1e-4)


# --- the capture carries it, on every path --------------------------------

def test_the_clock_block_is_present_even_when_there_is_no_daily_series():
    """`psr_inputs` returns early with no series. A result that carries the
    field only on the happy path is a field nobody can rely on."""
    got = psr_inputs({"Sharpe Ratio": "1.0"}, None, {"tradingDaysPerYear": 252})
    assert got["annualisation_clock"]["state"] == "series_absent"
    assert got["annualisation_clock"]["engine_obs_per_year"] == 252.0


def test_the_capture_and_the_clock_block_read_the_same_clock():
    """Two fields, one belief. They are computed through one reader, so they
    cannot drift the way two copies of the guard would."""
    n = 300
    got = psr_inputs({"Sharpe Ratio": "1.0"},
                     {"strategy": [0.0] * n, "dates": calendar_days(n)},
                     {"tradingDaysPerYear": 365})
    assert got["trading_days_per_year"] == 365
    assert got["annualisation_clock"]["engine_obs_per_year"] == 365.0
    assert got["engine_volatility_reproduction"]["clock"] == 365.0


def test_nothing_here_rescales_the_engines_own_statistics():
    """The disclosure must stay a disclosure: applying the factor to a
    criterion is a threshold change and a threshold moves only by a versioned
    human decision."""
    n = 500
    stats = {"Sharpe Ratio": "1.5", "Annual Standard Deviation": "0.116"}
    got = psr_inputs(stats, {"strategy": [0.001] * n, "dates": calendar_days(n)},
                     {"tradingDaysPerYear": 252})
    # The captured statistics are the engine's, verbatim and unscaled.
    assert got["statistics"]["Sharpe Ratio"] == "1.5"
    assert got["statistics"]["Annual Standard Deviation"] == "0.116"
    assert "threshold change" in got["annualisation_clock"]["note"]
