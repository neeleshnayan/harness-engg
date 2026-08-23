"""A synthetic cash feed for the premia tests, and nothing else.

Gate v5r2 reads the REALISED risk-free series from the fund's own feed over the
candidate's own window. A test must therefore be able to say what the cash rate
WAS, exactly, without touching the network — and, more importantly, must be able
to say it DIFFERENTLY twice, because "the rate is read rather than assumed" can
only be proved by moving it (D16).

Two shapes, because they prove different things:

  * ``cash_feed(rate_pct)`` — a constant per-session rate. The excess Sharpe is
    then exactly ``sharpe_at_rf(raw_moments, rate_pct)``, so a fixture's expected
    answer is closed form rather than eyeballed.
  * ``cash_feed(rate_pct, second_half_pct=...)`` — a rate that CHANGES inside
    the window. Its mean is a constant that no single-rate rule could
    distinguish it from, and its Sharpe answer is different — which is the only
    way to show the code consumes a series and not an average.

The dates are consecutive weekdays, matching ``_dates`` in the premia tests and
matching what the real feed serves (sessions, not calendar days).
"""
from __future__ import annotations

import datetime
from typing import Any, Optional


class FakeBars:
    """The two attributes ``rf_series`` reads, and a source label."""

    def __init__(self, dates: list[str], closes: list[float], source: str):
        self.dates, self.closes, self.source = dates, closes, source


def weekdays_between(start: str, end: str) -> list[str]:
    d = datetime.date.fromisoformat(start[:10])
    last = datetime.date.fromisoformat(end[:10])
    out = []
    while d <= last:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def per_obs(annual_pct: float, obs_per_year: float) -> float:
    """An annual rate at one observation's frequency, compounded — the same
    conversion ``statistics.sharpe_at_rf`` applies, so the two agree exactly."""
    return (1.0 + annual_pct / 100.0) ** (1.0 / float(obs_per_year)) - 1.0


def cash_feed(annual_pct: float, obs_per_year: float = 261.0,
              symbol: str = "BIL", second_half_pct: Optional[float] = None,
              calls: Optional[list] = None, short_by: int = 0) -> Any:
    """A fetcher ``(symbol, start, end) -> FakeBars`` for a cash instrument.

    ``short_by`` truncates the series from the END by that many sessions, which
    is how a real feed behaves at the edge of its history and is what
    ``coverage.rf_dropped_days`` exists to report.
    """
    def fetch(sym: str, start: str, end: str):
        if calls is not None:
            calls.append((sym, start, end))
        if sym != symbol:
            raise RuntimeError(f"no cash series for {sym}")
        dates = weekdays_between(start, end)
        if short_by:
            dates = dates[:-short_by]
        half = len(dates) // 2
        level, closes = 100.0, []
        for i, _d in enumerate(dates):
            rate = (annual_pct if (second_half_pct is None or i < half)
                    else second_half_pct)
            closes.append(level)
            level *= (1.0 + per_obs(rate, obs_per_year))
        return FakeBars(dates, closes, "synthetic-cash")

    return fetch


def no_feed(sym: str, start: str, end: str):
    """A feed that is reachable and has nothing. Distinct from `rf_bars=None`,
    which is 'nobody supplied a source at all' — the gate must fail closed on
    both, and a test that only exercises one has not tested the pair."""
    raise RuntimeError(f"the feed has no history for {sym} over {start}..{end}")
