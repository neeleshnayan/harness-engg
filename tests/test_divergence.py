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


def _strategy(sid, state="deployed", bt=None, archived=False):
    return {"strategy_id": sid, "name": f"S {sid}", "state": state,
            "backtest": bt, "archived": archived}


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


# --- archived is a fact the row must carry (2026-08-21) ---------------------
#
# The defect: three of the four rows this endpoint served on 2026-08-21 were
# archived (`Momentum — Large Cap Tech`, `Mean Reversion — Cyclicals`,
# `Trend — Sector & Commodity`), and the row said nothing about it. The Studio's
# Live-vs-backtest panel labelled all four "deployed" and the CEO was reading
# dead strategies as live comparisons.


def test_a_row_says_whether_the_strategy_is_archived():
    """A PAUSED-and-archived strategy is still in `rows` — the audit wants it —
    but the reader has to be able to tell. It could not."""
    out = dv.compare(_FakeStore([]),
                     [_strategy("a", state="paused", bt=_bt(), archived=True)], [])
    assert out["rows"][0]["archived"] is True


def test_a_live_strategy_is_not_marked_archived():
    out = dv.compare(_FakeStore([]), [_strategy("a", bt=_bt())], [])
    assert out["rows"][0]["archived"] is False


def test_a_registry_that_omits_the_flag_reads_as_NOT_archived():
    """`archived` absent means the registry predates the flag. Defaulting to
    True would hide a live strategy; the row says so rather than guessing."""
    s = {"strategy_id": "a", "name": "S a", "state": "deployed", "backtest": _bt()}
    assert dv.compare(_FakeStore([]), [s], [])["rows"][0]["archived"] is False


def test_the_live_counts_exclude_archived_and_the_old_count_does_not_move():
    """`n_deployed` keeps its old meaning — silently redefining a number a
    caller already reads is worse than adding one beside it."""
    rows = [_strategy("a", state="paused", bt=_bt(), archived=True),
            _strategy("b", state="paused", bt=_bt(), archived=True),
            _strategy("c", bt=_bt())]
    out = dv.compare(_FakeStore([]), rows, [])
    assert out["n_deployed"] == 3
    assert out["n_archived"] == 2
    assert out["n_live"] == 1
    assert "2 of these 3 strategies are ARCHIVED" in out["archived_note"]


def test_no_archived_rows_means_no_archived_note_at_all():
    """An absent note, not an empty sentence — a panel that always prints a
    reassurance is one nobody reads."""
    out = dv.compare(_FakeStore([]), [_strategy("a", bt=_bt())], [])
    assert out["archived_note"] is None
    assert out["n_archived"] == 0
