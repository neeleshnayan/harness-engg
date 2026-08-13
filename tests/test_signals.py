"""The signal→order loop. It proposes; it must never execute."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.fund.marketdata import Bars, BarsError
from app.fund.signals import MIN_TRADE_USD, SignalRunner


# --------------------------------------------------------------------- fakes
class FakeStrategies:
    def __init__(self, rows):
        self._rows = rows

    def list(self):
        return list(self._rows)


class FakeNav:
    def __init__(self, total=10_000.0, positions=None):
        self._total = total
        self._positions = positions or []

    def compute(self):
        return SimpleNamespace(total_nav_usd=self._total, positions=self._positions)


class FakePipeline:
    """Records proposals. Has no execute path — mirroring the real contract."""

    def __init__(self, result=None):
        self.proposed = []
        self._result = result or {"status": "pending_approval", "order_id": "o1"}

    def propose_order(self, order, actor):
        self.proposed.append(order)
        return dict(self._result)


def rising(n=300, start=100.0, step=0.5):
    return [start + i * step for i in range(n)]


def falling(n=300, start=250.0, step=0.5):
    return [start - i * step for i in range(n)]


def bars_of(prices, symbol="AAPL"):
    return Bars(symbol=symbol, closes=prices, source="test",
                dates=[f"2026-01-{(i % 28) + 1:02d}" for i in range(len(prices))])


def runner(strategy_rows, prices=None, nav=10_000.0, positions=None,
           pending=None, price=100.0, market_open=True, pipeline=None,
           fetcher=None):
    pipe = pipeline or FakePipeline()
    fetch = fetcher or (lambda sym, lookback_days=400, timeframe='1Day':
                        bars_of(prices or rising(), sym))
    return SignalRunner(
        strategies=FakeStrategies(strategy_rows),
        nav=FakeNav(nav, positions or []),
        pipeline=pipe,
        pricer=lambda s: price,
        pending_lookup=lambda: pending or [],
        bars_fetcher=fetch,
        market_open=(lambda: market_open),
    ), pipe


def strat(**kw):
    base = {
        "strategy_id": "s1", "name": "Trend", "state": "live",
        "allocation_pct": 20.0, "assets": ["AAPL"],
        "definition": {"strategy": "sma", "fast": 10, "slow": 30},
    }
    base.update(kw)
    return base


# --------------------------------------------------------------- the refusals
def test_non_live_strategies_are_not_evaluated():
    r, _ = runner([strat(state="draft")])
    assert r.evaluate() == []


def test_no_allocation_is_skipped_with_a_reason():
    r, _ = runner([strat(allocation_pct=None)])
    d = r.evaluate()[0]
    assert d.action == "skip" and "no allocation" in d.reason
    assert d.signal is None          # unknown, never a flat 0


def test_no_symbols_is_skipped():
    r, _ = runner([strat(assets=[])])
    assert "no symbols" in r.evaluate()[0].reason


def test_definition_without_a_template_is_skipped():
    r, _ = runner([strat(definition={"note": "hand-managed"})])
    assert "no signal template" in r.evaluate()[0].reason


def test_insufficient_history_refuses_rather_than_signalling():
    """An unwarmed indicator is not a flat signal — it is no signal."""
    r, _ = runner([strat()], prices=rising(15))
    d = r.evaluate()[0]
    assert d.action == "skip"
    assert "warm up" in d.reason
    assert d.signal is None


def test_unavailable_bars_are_skipped_not_guessed():
    def boom(sym, lookback_days=400):
        raise BarsError("no data for ZZZZ")
    r, _ = runner([strat()], fetcher=boom)
    d = r.evaluate()[0]
    assert d.action == "skip" and "bars unavailable" in d.reason


# ------------------------------------------------------------------- sizing
def test_long_signal_targets_the_strategy_allocation():
    # 20% of a $10k book over one symbol = $2,000
    r, _ = runner([strat()], prices=rising())
    d = r.evaluate()[0]
    assert d.signal == 1.0
    assert d.target_usd == pytest.approx(2000.0)
    assert d.action == "buy"


def test_allocation_is_split_across_the_strategys_symbols():
    r, _ = runner([strat(assets=["AAPL", "MSFT"])], prices=rising())
    for d in r.evaluate():
        assert d.target_usd == pytest.approx(1000.0)   # 20% of 10k over 2 names


def test_flat_signal_sells_the_whole_position():
    held = [{"symbol": "AAPL", "usd_value": 2000.0}]
    r, _ = runner([strat()], prices=falling(), positions=held)
    d = r.evaluate()[0]
    assert d.signal == 0.0
    assert d.target_usd == pytest.approx(0.0)
    assert d.action == "sell"
    assert d.delta_usd == pytest.approx(-2000.0)


def test_position_already_at_target_holds():
    held = [{"symbol": "AAPL", "usd_value": 2000.0}]
    r, _ = runner([strat()], prices=rising(), positions=held)
    d = r.evaluate()[0]
    assert d.action == "hold"
    assert f"${MIN_TRADE_USD:.0f}" in d.reason


def test_every_builtin_template_is_long_or_flat():
    """Locks the invariant the long-only guard exists for.

    No template currently emits −1, so nothing routes a short today. If someone
    adds one, this fails and forces the borrow/margin question to be answered
    before the signal can reach the venue.
    """
    from app.fund.backtest import signals_for
    px = [100 + (i % 40) * (1 if (i // 40) % 2 == 0 else -1) for i in range(400)]
    for t in ("sma", "rsi", "breakout", "macd", "bollinger",
              "momentum", "atr_trail", "buy_hold"):
        assert set(signals_for(t, px)) <= {0.0, 1.0}, f"{t} emits a short signal"


def test_a_short_target_is_refused_because_the_fund_is_long_only():
    """The guard itself, reached directly — no template can trigger it yet."""
    r, _ = runner([strat()], prices=rising())
    d = r._evaluate_one("s1", "Trend", "AAPL", "sma",
                        {"fast": 10, "slow": 30}, -500.0, 0.0)
    assert d.signal == 1.0 and d.target_usd == pytest.approx(-500.0)
    assert d.action == "skip" and "long-only" in d.reason


# ------------------------------------------------------- proposing behaviour
def test_dry_run_is_the_default_and_writes_nothing():
    r, pipe = runner([strat()], prices=rising())
    out = r.run()
    assert out["dry_run"] is True
    assert pipe.proposed == []
    assert out["counts"]["proposed"] == 1
    assert "nothing was written" in out["note"]


def test_wet_run_proposes_and_never_approves():
    r, pipe = runner([strat()], prices=rising())
    out = r.run(dry_run=False)
    assert len(pipe.proposed) == 1
    o = pipe.proposed[0]
    assert o.symbol == "AAPL" and o.side.value == "buy"
    assert o.strategy_id == "s1"
    assert o.qty == pytest.approx(20.0)          # $2,000 / $100
    assert "PENDING APPROVAL" in out["note"]
    # The runner must expose no way to approve what it proposed.
    assert not hasattr(r, "approve")
    assert not hasattr(pipe, "execute")


def test_a_closed_market_stops_live_proposals():
    r, pipe = runner([strat()], prices=rising(), market_open=False)
    out = r.run(dry_run=False)
    assert out["market_open"] is False
    assert pipe.proposed == []
    assert "CLOSED" in out["note"]


def test_a_closed_market_still_allows_a_dry_run():
    """Looking is free, and this is exactly when you want to look."""
    r, _ = runner([strat()], prices=rising(), market_open=False)
    assert r.run(dry_run=True)["counts"]["proposed"] == 1


def test_unknown_market_state_is_not_treated_as_closed():
    r, pipe = runner([strat()], prices=rising(), market_open=None)
    out = r.run(dry_run=False)
    assert out["market_open"] is None
    assert len(pipe.proposed) == 1        # unknown != closed


def test_an_already_pending_order_is_not_stacked():
    """The same signal on the next tick must not double the position."""
    pending = [{"status": "pending", "strategy_id": "s1", "symbol": "AAPL"}]
    r, pipe = runner([strat()], prices=rising(), pending=pending)
    out = r.run(dry_run=False)
    assert pipe.proposed == []
    assert out["counts"]["suppressed"] == 1
    assert "already pending" in out["suppressed"][0]["reason"]


def test_two_symbols_do_not_suppress_each_other():
    pending = [{"status": "pending", "strategy_id": "s1", "symbol": "AAPL"}]
    r, pipe = runner([strat(assets=["AAPL", "MSFT"])], prices=rising(), pending=pending)
    r.run(dry_run=False)
    assert [o.symbol for o in pipe.proposed] == ["MSFT"]


def test_a_gate_rejection_is_reported_not_swallowed():
    pipe = FakePipeline({"status": "rejected", "order_id": "o9",
                         "breaches": ["position limit"]})
    r, _ = runner([strat()], prices=rising(), pipeline=pipe)
    out = r.run(dry_run=False)
    assert out["counts"]["rejected"] == 1
    assert out["counts"]["proposed"] == 0
    assert out["rejected"][0]["breaches"] == ["position limit"]


def test_an_unpriced_symbol_is_suppressed_not_sized_at_zero():
    r = SignalRunner(
        strategies=FakeStrategies([strat()]), nav=FakeNav(10_000.0, []),
        pipeline=FakePipeline(),
        pricer=lambda s: (_ for _ in ()).throw(RuntimeError("feed down")),
        pending_lookup=lambda: [],
        bars_fetcher=lambda sym, lookback_days=400, timeframe='1Day': bars_of(rising(), sym),
        market_open=lambda: True,
    )
    out = r.run(dry_run=False)
    assert out["counts"]["proposed"] == 0
    assert "no usable price" in out["suppressed"][0]["reason"]


def test_a_zero_price_is_treated_as_no_price():
    r, pipe = runner([strat()], prices=rising(), price=0.0)
    out = r.run(dry_run=False)
    assert pipe.proposed == []
    assert out["counts"]["suppressed"] == 1


# ------------------------------------------- definitions as the book stores them
def test_deployed_is_treated_as_live():
    """The book's funded strategies carry state 'deployed', not 'live'."""
    r, _ = runner([strat(state="deployed")], prices=rising())
    assert r.evaluate()[0].action == "buy"


def test_template_is_read_from_the_type_key():
    """Definitions in this book name the template under 'type'."""
    r, _ = runner([strat(definition={"type": "sma", "fast": 10, "slow": 30})],
                  prices=rising())
    assert r.evaluate()[0].action == "buy"


def test_per_template_param_aliases_are_translated():
    """The RSI definition stores period/low/high, not rsi_* — and must not be
    silently dropped in favour of defaults."""
    p = SignalRunner._params("rsi", {"type": "rsi", "period": 21, "low": 25, "high": 75})
    assert p == {"rsi_period": 21, "rsi_low": 25, "rsi_high": 75}


def test_macd_fast_is_not_confused_with_sma_fast():
    """Both templates use 'fast' in their definition; they are different knobs.
    Routing MACD's fast to the SMA parameter would silently run on defaults."""
    p = SignalRunner._params("macd", {"type": "macd", "fast": 12, "slow": 26, "signal": 9})
    assert p == {"macd_fast": 12, "macd_slow": 26, "macd_signal": 9}
    assert "fast" not in p


def test_unknown_definition_keys_are_dropped_not_forwarded():
    p = SignalRunner._params("sma", {"type": "sma", "fast": 5, "note": "hi", "colour": "red"})
    assert p == {"fast": 5}


def test_warmup_uses_translated_params():
    """A long RSI period must raise the warm-up bar, not fall back to a default."""
    need = SignalRunner._warmup_bars("rsi", {"type": "rsi", "period": 200})
    assert need == 210


def test_the_three_live_strategies_evaluate_end_to_end():
    """The exact definitions the book holds, through the whole path."""
    rows = [
        {"strategy_id": "a", "name": "Momentum", "state": "deployed",
         "allocation_pct": 25.0, "assets": ["AAPL"],
         "definition": {"type": "sma", "fast": 10, "slow": 30}},
        {"strategy_id": "b", "name": "MeanRev", "state": "deployed",
         "allocation_pct": 25.0, "assets": ["INTC"],
         "definition": {"type": "rsi", "period": 14, "low": 30, "high": 70}},
        {"strategy_id": "c", "name": "Trend", "state": "deployed",
         "allocation_pct": 25.0, "assets": ["GLD"],
         "definition": {"type": "macd", "fast": 12, "slow": 26, "signal": 9}},
    ]
    r, _ = runner(rows, prices=rising())
    out = r.evaluate()
    assert len(out) == 3
    # The point of the test: NONE are skipped. Every one produced a real signal,
    # which is what proves the type/param translation worked.
    assert all(d.action != "skip" for d in out), [d.reason for d in out]
    assert all(d.signal is not None for d in out)
    # Trend-followers go long a rising series; the mean-reverter sits it out,
    # because a monotonic rise pins RSI overbought. Different templates
    # disagreeing here is the templates working, not a bug.
    by_name = {d.strategy_name: d for d in out}
    assert by_name["Momentum"].action == "buy"
    assert by_name["Trend"].action == "buy"
    assert by_name["MeanRev"].signal == 0.0
    assert by_name["MeanRev"].action == "hold"     # flat, and already flat


# ---------------------------------------------------------------- timeframes
def test_a_strategy_can_declare_an_intraday_timeframe():
    """Daily bars cross a handful of times a year; intraday is what makes the
    live path observable within a session."""
    seen = {}

    def fetch(sym, lookback_days=400, timeframe="1Day"):
        seen["timeframe"] = timeframe
        return bars_of(rising(), sym)

    r, _ = runner([strat(definition={"type": "sma", "fast": 10, "slow": 30,
                                     "timeframe": "5Min"})], fetcher=fetch)
    r.evaluate()
    assert seen["timeframe"] == "5Min"


def test_timeframe_defaults_to_daily():
    seen = {}

    def fetch(sym, lookback_days=400, timeframe="unset"):
        seen["timeframe"] = timeframe
        return bars_of(rising(), sym)

    r, _ = runner([strat()], fetcher=fetch)
    r.evaluate()
    assert seen["timeframe"] == "1Day"


def test_timeframe_is_never_passed_to_the_signal_function():
    """It selects the DATA, not the indicator. Forwarding it as a keyword would
    crash signals_for and stop the strategy trading."""
    p = SignalRunner._params("sma", {"type": "sma", "fast": 10, "timeframe": "5Min"})
    assert p == {"fast": 10}


def test_an_intraday_strategy_on_a_daily_only_source_is_skipped():
    """Refuse rather than silently substituting daily bars for the 5-minute
    ones the strategy was designed around."""
    def daily_only(sym, lookback_days=400):
        return bars_of(rising(), sym)

    r, _ = runner([strat(definition={"type": "sma", "fast": 10, "slow": 30,
                                     "timeframe": "5Min"})], fetcher=daily_only)
    d = r.evaluate()[0]
    assert d.action == "skip"
    assert "cannot serve 5Min bars" in d.reason


def test_a_daily_strategy_still_works_on_a_daily_only_source():
    def daily_only(sym, lookback_days=400):
        return bars_of(rising(), sym)

    r, _ = runner([strat()], fetcher=daily_only)
    assert r.evaluate()[0].action == "buy"
