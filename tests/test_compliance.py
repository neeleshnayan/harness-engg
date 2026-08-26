"""The pattern-day-trader rule, and the rest of what the broker forbids.

This fund holds about $2,000 and runs a strategy that flips several times a
day. Four day trades inside five business days restricts the account to
closing-only for ninety days, so these tests guard the difference between a
working fund and one that cannot open a position until November.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.fund.compliance import (
    MARKET_TZ,
    PDT_EQUITY_THRESHOLD,
    AccountState,
    ComplianceGate,
    DayTradeLedger,
    market_day,
)
from app.fund.connectors.base import Order, Side
from app.fund.events import EventType


class MemStore:
    def __init__(self):
        self.events: list[dict] = []
        self._seq = 0

    def append_fill(self, symbol: str, side: str, when: datetime):
        self._seq += 1
        self.events.append({
            "seq": self._seq,
            "aggregate_id": f"o{self._seq}",
            "aggregate_type": "order",
            "type": EventType.ORDER_FILLED.value,
            "payload": {"symbol": symbol, "side": side, "qty": 1, "price": 100.0},
            "actor": "test",
            "ts": when.isoformat(),
        })

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)

    def by_aggregate(self, aggregate_id):
        return [e for e in self.events if e["aggregate_id"] == str(aggregate_id)]


def now_et() -> datetime:
    return datetime.now(MARKET_TZ)


def order(symbol="SPY", side=Side.SELL, qty=10.0) -> Order:
    return Order(venue="alpaca", symbol=symbol, side=side, qty=qty)


def account(**kw) -> AccountState:
    base = dict(known=True, equity=2000.0, daytrade_count=0,
                pattern_day_trader=False, trading_blocked=False,
                account_blocked=False, shorting_enabled=True, status="ACTIVE")
    base.update(kw)
    return AccountState(**base)


def gate(store: MemStore) -> ComplianceGate:
    return ComplianceGate(DayTradeLedger(store))


# --------------------------------------------------------- the trading day
def test_a_late_utc_evening_is_still_the_same_new_york_session():
    """21:00 UTC is 17:00 ET the same day, not the next one.

    Counting on UTC dates would split one session across two and undercount
    day trades exactly at the boundary where the rule bites.
    """
    assert market_day("2026-08-13T21:00:00+00:00") == "2026-08-13"


def test_an_early_utc_morning_belongs_to_the_previous_session():
    """01:00 UTC is the prior evening in New York."""
    assert market_day("2026-08-14T01:00:00+00:00") == "2026-08-13"


def test_an_unparseable_or_naive_timestamp_is_not_guessed():
    assert market_day("not a timestamp") is None
    assert market_day("2026-08-13T21:00:00") is None      # no timezone


# ------------------------------------------------------ day-trade detection
def test_selling_what_was_bought_today_is_a_day_trade():
    s = MemStore()
    s.append_fill("SPY", "buy", now_et())
    assert DayTradeLedger(s).would_create_day_trade(order(side=Side.SELL)) is True


def test_covering_today_s_short_is_also_a_day_trade():
    """The rule is direction-agnostic: a round trip is a round trip."""
    s = MemStore()
    s.append_fill("SPY", "sell", now_et())
    assert DayTradeLedger(s).would_create_day_trade(order(side=Side.BUY)) is True


def test_a_first_trade_in_a_symbol_is_not_a_day_trade():
    s = MemStore()
    assert DayTradeLedger(s).would_create_day_trade(order()) is False


def test_selling_what_was_bought_yesterday_is_not_a_day_trade():
    s = MemStore()
    s.append_fill("SPY", "buy", now_et() - timedelta(days=1))
    assert DayTradeLedger(s).would_create_day_trade(order(side=Side.SELL)) is False


def test_a_same_side_fill_today_does_not_make_a_day_trade():
    """Adding to a position is not closing it."""
    s = MemStore()
    s.append_fill("SPY", "buy", now_et())
    assert DayTradeLedger(s).would_create_day_trade(order(side=Side.BUY)) is False


def test_another_symbol_s_round_trip_does_not_taint_this_one():
    s = MemStore()
    s.append_fill("MSFT", "buy", now_et())
    assert DayTradeLedger(s).would_create_day_trade(order(symbol="SPY")) is False


# ------------------------------------------------------- our own count
def test_our_own_count_folds_round_trips_from_the_log():
    s = MemStore()
    s.append_fill("SPY", "buy", now_et())
    s.append_fill("SPY", "sell", now_et())          # one round trip
    s.append_fill("MSFT", "buy", now_et())
    s.append_fill("MSFT", "sell", now_et())         # two
    s.append_fill("F", "buy", now_et())             # open only — not a round trip
    assert DayTradeLedger(s).count() == 2


def test_old_round_trips_fall_out_of_the_window():
    s = MemStore()
    s.append_fill("SPY", "buy", now_et() - timedelta(days=30))
    s.append_fill("SPY", "sell", now_et() - timedelta(days=30))
    assert DayTradeLedger(s).count() == 0


# ------------------------------------------------------------- the PDT block
# ------------------------------------------- the retired PDT enforcement -----
# THE PDT BLOCK WAS RETIRED 2026-08-27 (CEO signature on AB4-2, adversary
# blind pass docs/reviews/ADVERSARY_BATCH4_2026-08-24.md item 2): the rule it
# enforced ended 2026-06-04. Eight enforcement tests that asserted the block's
# behaviour were removed WITH the block - a green test over an uncalled
# control is the HW3 orphaned-control pattern. What replaces them pins the
# RETIREMENT, so the block cannot quietly return.

def test_the_retired_pdt_rule_blocks_nothing_whatever_the_count():
    """The incident this pins: a day trade that v-before-retirement refused.

    Fourth day trade, sub-$25k account, broker count at the old cliff - the
    exact input the retired block refused with "pattern-day-trader rule".
    Retired means the gate has NOTHING to say about it: no block, no PDT
    warning. If this fails, the block came back without the review chain
    (adversary blind + the CEO's click) that removing it required."""
    s = MemStore()
    s.append_fill("SPY", "buy", now_et())
    d = gate(s).check(order(side=Side.SELL), account(daytrade_count=9))
    assert d.ok is True
    assert d.blocks == []
    assert not any("day trade" in w or "pattern" in w for w in d.warnings)


def test_the_retirement_holds_on_an_unreadable_account_too():
    """The old block failed CLOSED on unknown equity (not knowing is not big).
    Retired is retired on every arm: an unreadable broker changes nothing."""
    s = MemStore()
    for sym in ("SPY", "MSFT", "F"):
        s.append_fill(sym, "buy", now_et())
        s.append_fill(sym, "sell", now_et())
    s.append_fill("NVDA", "buy", now_et())
    d = gate(s).check(order(symbol="NVDA", side=Side.SELL),
                      AccountState.unknown("timeout"))
    assert d.ok is True
    assert d.blocks == []


def test_the_day_trade_ledger_still_counts_honestly():
    """The LEDGER outlives the rule: the count is a fact about the account,
    reported by /fund/compliance beside `retired: true`, and the reconciler
    cross-checks it. Three round trips is three, retirement or not."""
    s = MemStore()
    for sym in ("SPY", "MSFT", "F"):
        s.append_fill(sym, "buy", now_et())
        s.append_fill(sym, "sell", now_et())
    assert DayTradeLedger(s).count() == 3


# ------------------------------------------------------- the other hard stops
def test_a_blocked_account_stops_everything():
    s = MemStore()
    d = gate(s).check(order(side=Side.BUY), account(account_blocked=True))
    assert d.ok is False
    assert any("account is blocked" in b for b in d.blocks)


def test_blocked_trading_stops_everything():
    s = MemStore()
    d = gate(s).check(order(side=Side.BUY), account(trading_blocked=True))
    assert d.ok is False


def test_a_sell_warns_when_shorting_is_disabled():
    s = MemStore()
    d = gate(s).check(order(side=Side.SELL), account(shorting_enabled=False))
    assert d.ok is True                              # closing a long is still fine
    assert any("shorting is disabled" in w for w in d.warnings)


def test_a_buy_says_nothing_about_shorting():
    s = MemStore()
    d = gate(s).check(order(side=Side.BUY), account(shorting_enabled=False))
    assert d.warnings == []


def test_an_unknown_flag_is_not_read_as_permission():
    """None means unread. Only an explicit False disables shorting, and only an
    explicit True blocks the account — neither may be inferred from silence."""
    s = MemStore()
    d = gate(s).check(order(side=Side.SELL), AccountState(known=True, equity=2000.0,
                                                         daytrade_count=0))
    assert d.ok is True
    assert not any("shorting" in w for w in d.warnings)


# --------------------------------------------------------------- serialisation
def test_account_state_round_trips_to_a_dict():
    d = account().to_dict()
    assert d["daytrade_count"] == 0 and d["known"] is True


def test_unknown_carries_the_reason():
    a = AccountState.unknown("connection refused")
    assert a.known is False and a.error == "connection refused"
