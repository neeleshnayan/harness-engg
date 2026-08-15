"""Live-vs-backtest divergence: the honesty rules are the tests.

The dangerous outputs here are not wrong numbers but confident ones — a verdict
annualised from two days, or 'fine' from a strategy with no backtest at all.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app.fund import divergence as dv


class _FakeStore:
    def __init__(self, fills):
        self._fills = fills

    def stream(self, **kw):
        return [
            {"type": "OrderFilled", "ts": ts.isoformat(),
             "payload": {"strategy_id": sid}}
            for sid, ts in self._fills
        ]


def _strategy(sid, state="deployed", bt=None):
    return {"strategy_id": sid, "name": f"S {sid}", "state": state, "backtest": bt}


def _bt(total_return=0.10, bars=126, volatility=0.20):
    return {"total_return": total_return, "bars": bars, "volatility": volatility}


NOW = datetime.now(timezone.utc)


def test_no_backtest_is_named_not_skipped():
    out = dv.compare(_FakeStore([]), [_strategy("a", bt=None)], [])
    row = out["rows"][0]
    assert row["comparable"] is False
    assert "no backtest" in row["reason"]


def test_under_fourteen_days_refuses_to_annualise():
    fills = [("a", NOW - timedelta(days=3))]
    attr = [{"strategy_id": "a", "exposure_usd": 110.0, "pnl_usd": 10.0}]
    out = dv.compare(_FakeStore(fills), [_strategy("a", bt=_bt())], attr)
    row = out["rows"][0]
    assert row["comparable"] is False
    assert "live days" in row["reason"]
    # the raw facts are still reported — refusal to conclude, not to inform
    assert row["live_return_pct"] == 10.0


def test_within_band_is_not_flagged():
    # backtest: +10% over ~126 trading days = ~21% annual; vol 20%
    fills = [("a", NOW - timedelta(days=30))]
    # live: +2% over 30 days ≈ +27% annual — 6pp gap, inside a 20pp vol band
    attr = [{"strategy_id": "a", "exposure_usd": 102.0, "pnl_usd": 2.0}]
    out = dv.compare(_FakeStore(fills), [_strategy("a", bt=_bt())], attr)
    row = out["rows"][0]
    assert row["comparable"] is True
    assert row["diverging"] is False


def test_collapse_outside_band_is_flagged():
    # live: -15% over 30 days annualises catastrophically below +21% expected
    fills = [("a", NOW - timedelta(days=30))]
    attr = [{"strategy_id": "a", "exposure_usd": 85.0, "pnl_usd": -15.0}]
    out = dv.compare(_FakeStore(fills), [_strategy("a", bt=_bt())], attr)
    row = out["rows"][0]
    assert row["comparable"] is True
    assert row["diverging"] is True
    assert row["gap_pp"] < 0


def test_lucky_streak_flags_too():
    # +30% in 30 days on a strategy tested at 21%/yr is ALSO not the strategy
    # that was tested. Luck is not validation.
    fills = [("a", NOW - timedelta(days=30))]
    attr = [{"strategy_id": "a", "exposure_usd": 130.0, "pnl_usd": 30.0}]
    out = dv.compare(_FakeStore(fills), [_strategy("a", bt=_bt())], attr)
    assert out["rows"][0]["diverging"] is True
    assert out["rows"][0]["gap_pp"] > 0


def test_archived_strategies_are_not_judged():
    out = dv.compare(_FakeStore([]), [_strategy("a", state="archived", bt=_bt())], [])
    assert out["rows"] == []


def test_no_fills_means_nothing_live():
    out = dv.compare(_FakeStore([]), [_strategy("a", bt=_bt())],
                     [{"strategy_id": "a", "exposure_usd": 0.0, "pnl_usd": 0.0}])
    row = out["rows"][0]
    assert row["comparable"] is False
    assert "no fills" in row["reason"]
