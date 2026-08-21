"""The factor pack v0 — daily factor series, rolling betas, residuals.

The pack has no thresholds and issues no verdicts, so there is no bar here to
loosen. What there IS to get wrong is every one of the ways a missing number can
be dressed up as a measured one, and each test below is one of those:

  * a beta that could not be computed must not come back as 0.0 — a zero beta is
    a real answer ("these are unrelated") and has to stay distinguishable from
    "nobody looked";
  * a rolling beta's un-filled head must be None, not zero. A zero-padded head
    opens a chart at "no exposure" and drags any mean over the series toward
    "less exposed than we are";
  * a factor leg the feed cannot serve must be NAMED, not dropped. A pack that
    quietly loses a leg produces a residual against a model nobody chose;
  * residuals compound, they do not sum. Summing returns overstates by the cross
    terms — the same arithmetic error that once made walk-forward retention
    divide cumulative windows of unequal length.
"""

import math

import pytest

from app.fund import factors as fp


class _Bars:
    def __init__(self, dates, closes):
        self.dates, self.closes = list(dates), list(closes)
        self.volumes = []


def _walk(n, step=0.001, start=100.0, first_day=1):
    """A deterministic close series and its ISO dates."""
    dates, closes, c = [], [], start
    for i in range(n):
        c *= (1.0 + step)
        closes.append(round(c, 6))
        dates.append(f"2025-{1 + (i + first_day - 1) // 28:02d}-"
                     f"{1 + (i + first_day - 1) % 28:02d}")
    return _Bars(dates, closes)


_feed_seq = iter(range(1, 10_000))


def _feed(mapping):
    """A fake bar fetcher with a UNIQUE __name__.

    Load-bearing, and it cost three confusing failures to find:
    `correlation.aligned_returns` memoises on
    ``(symbols, lookback_days, fetcher.__name__)``. Two different closures both
    called `fetch` therefore COLLIDE in that cache, and the second test in a run
    silently receives the first test's data — which is how a test asserting that
    a missing leg is reported absent instead saw four healthy legs.

    Benign in production, where the fetcher is always `fetch_daily_bars`. Not
    benign here, and worth the sentence for whoever writes the next fixture.
    """
    def fetch(sym, lookback_days=400, **kw):
        if sym not in mapping:
            raise ValueError(f"no bars for {sym}")
        return mapping[sym]
    fetch.__name__ = f"fetch_fake_{next(_feed_seq)}"
    return fetch


# --- returns ----------------------------------------------------------------


def test_daily_returns_are_simple_period_returns():
    assert fp.daily_returns([100.0, 110.0, 99.0]) == pytest.approx([0.1, -0.1])


def test_a_zero_or_negative_close_never_divides():
    """One bad bar would otherwise emit an infinity into every regression that
    reads this series."""
    out = fp.daily_returns([100.0, 0.0, 50.0, 55.0])
    assert all(math.isfinite(r) for r in out)
    assert out == pytest.approx([0.1])   # only the 50 -> 55 step survives


def test_a_non_numeric_close_breaks_the_chain_rather_than_the_process():
    out = fp.daily_returns([100.0, None, 110.0, 121.0])
    assert out == pytest.approx([0.1])


def test_an_empty_series_returns_no_returns_rather_than_raising():
    assert fp.daily_returns([]) == []
    assert fp.daily_returns(None) == []


# --- the factor series ------------------------------------------------------


def test_every_premia_leg_is_served_when_the_feed_has_it():
    feed = _feed({s: _walk(120, step=0.001 * (i + 1))
                  for i, s in enumerate(fp.PREMIA_PROXIES.values())})
    out = fp.factor_series(fetcher=feed)
    assert set(out["factors"]) == set(fp.PREMIA_PROXIES)
    assert out["absent"] == {}
    assert out["n_obs"] > 0


def test_a_leg_the_feed_cannot_serve_is_NAMED_not_dropped():
    """The load-bearing case. Silently narrowing the model produces a residual
    against a model nobody chose."""
    served = {s: _walk(120) for s in ("SPY", "TLT", "DBC")}   # no UUP
    out = fp.factor_series(fetcher=_feed(served))
    assert "dollar" not in out["factors"]
    assert "dollar" in out["absent"]
    assert "UUP" in out["absent"]["dollar"] or "price history" in out["absent"]["dollar"]
    assert "ABSENT" in out["note"]
    assert "dollar" in out["note"]


def test_an_absent_leg_is_never_zero_filled():
    served = {s: _walk(120) for s in ("SPY", "TLT", "DBC")}
    out = fp.factor_series(fetcher=_feed(served))
    assert all(any(abs(v) > 0 for v in series) or series == []
               for series in out["factors"].values())
    assert "dollar" not in out["factors"], "a missing leg must not appear at all"


def test_the_note_says_how_many_legs_are_present_out_of_how_many_asked_for():
    served = {s: _walk(120) for s in ("SPY", "TLT")}
    out = fp.factor_series(fetcher=_feed(served))
    assert "2 of 4 legs" in out["note"]


# --- beta -------------------------------------------------------------------


def test_a_perfectly_geared_series_has_the_gearing_as_its_beta():
    x = [0.01, -0.02, 0.015, -0.005] * 20
    y = [2.0 * v for v in x]
    out = fp.beta(y, x)
    assert out["measurable"] is True
    assert out["beta"] == pytest.approx(2.0, abs=1e-9)
    assert out["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_too_few_observations_is_UNMEASURED_and_never_a_zero_beta():
    """A zero beta says 'these are unrelated', which is a claim. Absence is
    not a claim."""
    out = fp.beta([0.01] * 10, [0.01] * 10)
    assert out["measurable"] is False
    assert out["beta"] is None
    assert out["beta"] != 0.0
    assert "under the" in out["reason"]


def test_a_factor_that_never_moved_yields_no_beta_rather_than_a_division():
    out = fp.beta([0.01, -0.01] * 40, [0.0] * 80)
    assert out["measurable"] is False
    assert out["beta"] is None
    assert "did not move" in out["reason"]


def test_a_genuinely_zero_beta_is_reported_as_a_MEASURED_zero():
    # Orthogonal by construction: x alternates, y is constant-magnitude but
    # uncorrelated with it.
    x = [0.01, -0.01] * 40
    y = [0.01, 0.01, -0.01, -0.01] * 20
    out = fp.beta(y, x)
    assert out["measurable"] is True
    assert out["beta"] == pytest.approx(0.0, abs=1e-9)
    assert out["beta"] is not None


def test_a_non_finite_value_is_unmeasured_rather_than_propagated():
    y = [0.01] * 79 + [float("nan")]
    out = fp.beta(y, [0.01, -0.01] * 40)
    assert out["measurable"] is False
    assert "non-finite" in out["reason"]


# --- rolling beta -----------------------------------------------------------


def test_the_rolling_head_is_None_and_emphatically_not_zero():
    """A zero-padded head opens a chart at 'no exposure' and drags every mean
    over the series toward less-exposed-than-we-are."""
    x = [0.01, -0.02, 0.015] * 40
    y = [1.5 * v for v in x]
    roll = fp.rolling_beta(y, x, window=10)
    assert roll[:9] == [None] * 9
    assert all(v is not None for v in roll[9:])
    assert 0.0 not in roll[:9]


def test_the_rolling_series_is_aligned_to_the_input_length():
    x = [0.01, -0.02] * 50
    roll = fp.rolling_beta([2 * v for v in x], x, window=20)
    assert len(roll) == len(x)


def test_a_series_shorter_than_the_window_is_all_None():
    assert fp.rolling_beta([0.01] * 5, [0.01] * 5, window=20) == [None] * 5


def test_the_rolling_beta_tracks_a_regime_change():
    """The property the SRPT reader needs: a name whose sector beta drifted has
    no single residual worth quoting, and this is how they see it."""
    x = [0.01, -0.012, 0.008, -0.006] * 30
    y = [0.5 * v for v in x[:60]] + [2.0 * v for v in x[60:]]
    roll = fp.rolling_beta(y, x, window=20)
    assert roll[59] == pytest.approx(0.5, abs=1e-6)
    assert roll[-1] == pytest.approx(2.0, abs=1e-6)


# --- residuals --------------------------------------------------------------


def test_a_pure_beta_series_has_essentially_no_residual():
    x = [0.01, -0.02, 0.015, -0.005] * 20
    out = fp.residual_series([1.3 * v for v in x], x)
    assert out["measurable"] is True
    assert out["beta"] == pytest.approx(1.3, abs=1e-9)
    assert out["cumulative_residual_pct"] == pytest.approx(0.0, abs=1e-6)


def test_the_cumulative_residual_COMPOUNDS_rather_than_sums():
    # 80 periods of exactly +1% residual: compounding gives (1.01^80 - 1) =
    # 121.7%, summing would give 80%. Summing returns is the arithmetic error
    # that once made retention divide unequal cumulative windows.
    x = [0.0] * 80
    y = [0.01] * 80
    out = fp.residual_series(y, x, b=0.0)
    assert out["cumulative_residual_pct"] == pytest.approx(
        (1.01 ** 80 - 1.0) * 100.0, abs=1e-3)
    assert out["cumulative_residual_pct"] != pytest.approx(80.0, abs=1.0)


def test_a_supplied_beta_is_used_and_SAID_to_have_been_supplied():
    """Re-fitting a beta on the window you are judging is how a residual becomes
    a curve fit, so which one was used has to be on the record."""
    x = [0.01, -0.02] * 40
    fitted = fp.residual_series([2.0 * v for v in x], x)
    supplied = fp.residual_series([2.0 * v for v in x], x, b=1.0)
    assert fitted["beta_source"] == "fitted on this window"
    assert supplied["beta_source"] == "supplied"
    assert supplied["beta"] == 1.0
    assert supplied["cumulative_residual_pct"] != fitted["cumulative_residual_pct"]


def test_an_unmeasurable_beta_produces_no_residual_series_at_all():
    out = fp.residual_series([0.01] * 5, [0.01] * 5)
    assert out["measurable"] is False
    assert out["residuals"] is None
    assert out["cumulative_residual_pct"] is None


# --- the SRPT revival shape -------------------------------------------------


def test_the_beta_adjusted_residual_reports_both_the_full_and_rolling_beta():
    """A residual is only as good as the beta that produced it."""
    xb = _walk(200, step=0.002)
    sr = _Bars(xb.dates, [round(100.0 * (1.0 + 0.003) ** i, 6)
                          for i in range(len(xb.dates))])
    out = fp.beta_adjusted_residual("SRPT", "XBI", window=20,
                                    fetcher=_feed({"SRPT": sr, "XBI": xb}))
    assert out["measurable"] is True
    assert out["beta"] is not None
    assert out["rolling_beta_last"] is not None
    assert out["rolling_beta_min"] is not None
    assert "ABSENT rather than zero" in out["rolling_beta_note"]


def test_a_symbol_the_feed_cannot_serve_is_named_not_silently_skipped():
    out = fp.beta_adjusted_residual("NOSUCH", "XBI",
                                    fetcher=_feed({"XBI": _walk(200)}))
    assert out["measurable"] is False
    assert "NOSUCH" in out["reason"]
    assert out["beta"] is None
    assert out["cumulative_residual_pct"] is None


def test_a_missing_SECTOR_is_named_too_not_only_the_name():
    out = fp.beta_adjusted_residual("SRPT", "NOSECTOR",
                                    fetcher=_feed({"SRPT": _walk(200)}))
    assert out["measurable"] is False
    assert "NOSECTOR" in out["reason"]


def test_the_pack_issues_no_verdict_about_a_revival():
    """It computes the residual and stops. Whether a condition is MET is a
    judgement belonging to the seat that pre-registered it, and a helper that
    answered it would be a threshold hiding in a utility module."""
    xb = _walk(200, step=0.002)
    out = fp.beta_adjusted_residual("SRPT", "XBI",
                                    fetcher=_feed({"SRPT": xb, "XBI": xb}))
    for banned in ("revive", "revival", "passed", "verdict", "triggered"):
        assert banned not in {k.lower() for k in out}


def test_the_proxies_are_the_ones_verified_against_the_feed():
    """Checked 2026-08-21: all four premia legs and both biotech legs returned
    551 bars from the fund's own feed. A change here is a change to what every
    residual in the firm is measured against."""
    assert fp.PREMIA_PROXIES == {"mkt": "SPY", "duration": "TLT",
                                 "commodity": "DBC", "dollar": "UUP"}
    assert fp.BIOTECH_PROXIES == {"xbi": "XBI", "ibb": "IBB"}
