"""What trading actually cost, against what the backtests assumed it cost.

The sign convention carries most of the weight here: unless a bad sell reads as
positive like a bad buy does, two real costs net toward zero and the fund
concludes it trades for free.
"""

from __future__ import annotations

import pytest

from app.fund.events import EventType
from app.fund.tca import ASSUMED_COST_BPS_PER_SIDE, TransactionCosts, summarise


class MemStore:
    def __init__(self):
        self.events: list[dict] = []
        self._seq = 0

    def add(self, oid, etype, payload, ts):
        self._seq += 1
        self.events.append({
            "seq": self._seq, "aggregate_id": oid, "aggregate_type": "order",
            "type": etype, "payload": payload, "actor": "test", "ts": ts,
        })

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)


def lifecycle(store, oid="o1", *, side="buy", decision=100.0, arrival=None,
              fill=100.0, qty=10.0, fees=0.0, strategy_id="s1",
              t_prop="2026-08-13T19:29:33+00:00",
              t_appr="2026-08-13T19:31:16+00:00",
              t_subm="2026-08-13T19:31:17+00:00",
              t_fill="2026-08-13T19:31:20+00:00",
              submitted=True):
    store.add(oid, EventType.ORDER_PROPOSED.value,
              {"symbol": "MSFT", "side": side, "qty": qty, "strategy_id": strategy_id,
               "impact_preview": {"quote_price": decision}}, t_prop)
    store.add(oid, EventType.ORDER_APPROVED.value, {"approver": "operator"}, t_appr)
    if submitted:
        store.add(oid, EventType.ORDER_SUBMITTED.value,
                  {"venue": "alpaca", "venue_ref": "v1", "arrival_price": arrival}, t_subm)
    store.add(oid, EventType.ORDER_FILLED.value,
              {"symbol": "MSFT", "side": side, "strategy_id": strategy_id,
               "filled_qty": qty, "avg_price": fill, "fees": fees}, t_fill)
    return store


# ------------------------------------------------------------ sign convention
def test_a_buy_filled_above_the_decision_price_is_a_cost():
    s = lifecycle(MemStore(), side="buy", decision=100.0, fill=100.5)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps == pytest.approx(50.0)


def test_a_sell_filled_below_the_decision_price_is_also_a_cost():
    """Positive means worse for the fund, whichever way the order points."""
    s = lifecycle(MemStore(), side="sell", decision=100.0, fill=99.5)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps == pytest.approx(50.0)


def test_a_buy_filled_below_the_decision_price_is_a_saving():
    s = lifecycle(MemStore(), side="buy", decision=100.0, fill=99.5)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps == pytest.approx(-50.0)


def test_a_bad_buy_and_a_bad_sell_do_not_cancel_out():
    """The bug this convention exists to prevent: two real costs netting to
    nothing and the fund concluding it trades for free."""
    s = MemStore()
    lifecycle(s, "o1", side="buy", decision=100.0, fill=100.5)
    lifecycle(s, "o2", side="sell", decision=100.0, fill=99.5)
    out = summarise(TransactionCosts(s).costs())
    assert out["total_bps"]["mean"] == pytest.approx(50.0)


# --------------------------------------------------------------- the split
def test_the_cost_splits_into_deliberation_and_execution():
    """Decision 100 -> arrival 100.3 while the human thought -> fill 100.5."""
    s = lifecycle(MemStore(), side="buy", decision=100.0, arrival=100.3, fill=100.5)
    [r] = TransactionCosts(s).costs()
    assert r.delay_bps == pytest.approx(30.0)
    assert r.execution_bps == pytest.approx(19.94, abs=0.05)
    assert r.total_bps == pytest.approx(50.0)
    assert r.has_split is True


def test_the_split_is_absent_rather_than_zero_when_arrival_is_unknown():
    """Orders placed before arrival capture existed must not claim their delay
    cost was nothing — unknown and zero are different claims."""
    s = lifecycle(MemStore(), decision=100.0, arrival=None, fill=100.5)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps == pytest.approx(50.0)
    assert r.delay_bps is None and r.execution_bps is None
    assert r.has_split is False


def test_a_missing_submit_event_still_yields_a_total():
    s = lifecycle(MemStore(), decision=100.0, fill=100.5, submitted=False)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps == pytest.approx(50.0)
    assert r.has_split is False


# ------------------------------------------------------------------ latency
def test_approval_latency_measures_the_whole_human_pause():
    """From proposal to submit — the wait the market actually sees, not the
    instant between clicking approve and the order going out."""
    s = lifecycle(MemStore())      # 19:29:33 -> 19:31:17
    [r] = TransactionCosts(s).costs()
    assert r.approval_latency_s == pytest.approx(104.0)


def test_time_at_the_venue_is_measured_separately():
    s = lifecycle(MemStore())      # 19:31:17 -> 19:31:20
    [r] = TransactionCosts(s).costs()
    assert r.submit_to_fill_s == pytest.approx(3.0)


# ------------------------------------------------------- what gets included
def test_an_unfilled_order_has_no_realised_cost():
    s = MemStore()
    s.add("o1", EventType.ORDER_PROPOSED.value,
          {"symbol": "F", "side": "buy", "impact_preview": {"quote_price": 10.0}},
          "2026-08-13T19:00:00+00:00")
    assert TransactionCosts(s).costs() == []


def test_a_fill_with_no_proposal_is_skipped_rather_than_measured_against_nothing():
    s = MemStore()
    s.add("o1", EventType.ORDER_FILLED.value,
          {"symbol": "F", "side": "buy", "filled_qty": 1, "avg_price": 10.0},
          "2026-08-13T19:00:00+00:00")
    assert TransactionCosts(s).costs() == []


def test_a_zero_decision_price_does_not_divide_by_zero():
    s = lifecycle(MemStore(), decision=0.0, fill=10.0)
    [r] = TransactionCosts(s).costs()
    assert r.total_bps is None


def test_orders_come_back_newest_first():
    s = MemStore()
    lifecycle(s, "old", t_fill="2026-08-10T10:00:00+00:00")
    lifecycle(s, "new", t_fill="2026-08-13T10:00:00+00:00")
    assert [r.order_id for r in TransactionCosts(s).costs()] == ["new", "old"]


# ------------------------------------------------------------- dollars & fees
def test_the_cost_is_reported_in_dollars_as_well_as_bps():
    s = lifecycle(MemStore(), decision=100.0, fill=100.5, qty=10.0)
    [r] = TransactionCosts(s).costs()
    assert r.notional_usd == pytest.approx(1005.0)
    assert r.total_usd == pytest.approx(5.025, abs=0.01)


def test_fees_are_expressed_against_notional():
    s = lifecycle(MemStore(), decision=100.0, fill=100.0, qty=10.0, fees=1.0)
    [r] = TransactionCosts(s).costs()
    assert r.fees_bps == pytest.approx(10.0)


# ---------------------------------------------------- against the assumption
# The verdict grades the EXECUTION leg (arrival -> fill) on informative
# venues only. total_bps includes the human approval pause, and the paper
# venue fills at its own quote — both would put non-cost numbers into a
# "realised cost" verdict (validator audit 8b863152, 2026-08-20).

def test_realised_cost_is_reported_against_what_the_backtest_assumed():
    s = lifecycle(MemStore(), decision=100.0, arrival=100.0, fill=100.05)  # 5bps exec
    v = summarise(TransactionCosts(s).costs())["vs_assumption"]
    assert v["assumed_bps_per_side"] == ASSUMED_COST_BPS_PER_SIDE
    assert v["realised_bps_per_side"] == pytest.approx(5.0)
    assert v["excess_bps"] == pytest.approx(5.0 - ASSUMED_COST_BPS_PER_SIDE)


def test_approval_latency_drift_is_not_graded_as_cost():
    """decision 100 -> arrival 99 is the market moving during the human
    pause; execution is clean. The verdict must read ~0, not -100bps —
    the -12.59bps 'cheaper than modelled' incident, pinned."""
    s = lifecycle(MemStore(), decision=100.0, arrival=99.0, fill=99.0)
    v = summarise(TransactionCosts(s).costs())["vs_assumption"]
    assert v["realised_bps_per_side"] == pytest.approx(0.0)


def test_paper_venue_fills_are_excluded_from_the_verdict():
    """The paper connector fills at its own quote — execution slippage is
    identically zero by construction. A tautology must not be averaged
    into a measurement, so paper-only history yields NO verdict."""
    s = MemStore()
    s.add("p1", EventType.ORDER_PROPOSED.value,
          {"symbol": "SOFI", "side": "sell", "qty": 1.0,
           "impact_preview": {"quote_price": 18.56}}, "2026-08-20T13:00:00+00:00")
    s.add("p1", EventType.ORDER_SUBMITTED.value,
          {"venue": "paper", "venue_ref": "v9", "arrival_price": 18.56},
          "2026-08-20T13:00:01+00:00")
    s.add("p1", EventType.ORDER_FILLED.value,
          {"symbol": "SOFI", "side": "sell", "filled_qty": 1.0,
           "avg_price": 18.56, "fees": 0.0}, "2026-08-20T13:00:02+00:00")
    v = summarise(TransactionCosts(s).costs())["vs_assumption"]
    assert v is None


def test_fills_without_an_arrival_price_carry_no_verdict():
    """No arrival leg -> no execution measurement. total_bps still reports;
    the assumption verdict does not pretend."""
    s = lifecycle(MemStore(), decision=100.0, fill=100.05)  # arrival=None
    out = summarise(TransactionCosts(s).costs())
    assert out["total_bps"]["n"] == 1
    assert out["vs_assumption"] is None


def test_a_small_sample_is_flagged_as_unreliable():
    """Three fills is an observation, not an estimate. The number is still
    shown — with the sample size beside it so it cannot be quoted as one."""
    s = MemStore()
    for i in range(3):
        lifecycle(s, f"o{i}", decision=100.0, arrival=100.0, fill=100.5)
    v = summarise(TransactionCosts(s).costs())["vs_assumption"]
    assert v["sample"] == 3 and v["reliable"] is False


def test_a_large_sample_is_flagged_reliable():
    s = MemStore()
    for i in range(20):
        lifecycle(s, f"o{i}", decision=100.0, arrival=100.0, fill=100.5)
    v = summarise(TransactionCosts(s).costs())["vs_assumption"]
    assert v["reliable"] is True


def test_no_fills_yields_no_verdict_rather_than_a_zero():
    assert summarise([])["vs_assumption"] is None
    assert summarise([])["orders"] == 0


# ---------------------------------------------------------------- by strategy
def test_costs_split_by_strategy():
    s = MemStore()
    lifecycle(s, "o1", strategy_id="fast", decision=100.0, fill=100.5)
    lifecycle(s, "o2", strategy_id="slow", decision=100.0, fill=100.05)
    out = TransactionCosts(s).by_strategy()
    assert out["fast"]["total_bps"]["mean"] == pytest.approx(50.0)
    assert out["slow"]["total_bps"]["mean"] == pytest.approx(5.0)


def test_orders_with_no_strategy_are_grouped_as_discretionary():
    s = lifecycle(MemStore(), strategy_id=None)
    assert "(discretionary)" in TransactionCosts(s).by_strategy()


def test_the_worst_fill_is_the_most_expensive_one():
    s = MemStore()
    lifecycle(s, "o1", decision=100.0, fill=100.5)       # +50bps
    lifecycle(s, "o2", decision=100.0, fill=99.5)        # -50bps
    st = summarise(TransactionCosts(s).costs())["total_bps"]
    assert st["worst"] == pytest.approx(50.0)
    assert st["best"] == pytest.approx(-50.0)


# ---------------------------------------------------------------------------
# JAN1 (2026-08-27): "which venues cannot measure cost" has one owner.
#
# ``OrderCost.informative`` used to carry its own ``!= "paper"`` literal while
# ``executionquality.SIMULATED_VENUES`` carried the same judgement separately.
# The behavioural pin in tests/test_executionquality_store.py iterates the very
# list it checks against, so it could only ever catch the drift after someone
# shipped it. These pin the READ: they fail if tca decides this for itself again.

def _submitted_on(venue):
    s = MemStore()
    s.add("v1", EventType.ORDER_PROPOSED.value,
          {"symbol": "SOFI", "side": "sell", "qty": 1.0,
           "impact_preview": {"quote_price": 18.56}}, "2026-08-20T13:00:00+00:00")
    s.add("v1", EventType.ORDER_SUBMITTED.value,
          {"venue": venue, "venue_ref": "r", "arrival_price": 18.56},
          "2026-08-20T13:00:01+00:00")
    s.add("v1", EventType.ORDER_FILLED.value,
          {"symbol": "SOFI", "side": "sell", "filled_qty": 1.0,
           "avg_price": 18.60, "fees": 0.0}, "2026-08-20T13:00:02+00:00")
    [row] = TransactionCosts(s).costs()
    return row


def test_tca_reads_the_simulated_venue_list_rather_than_keeping_one():
    from app.fund import executionquality

    # The list the OWNER publishes decides the verdict, venue by venue.
    for venue in executionquality.SIMULATED_VENUES:
        assert _submitted_on(venue).informative is False, venue
    assert _submitted_on("alpaca").informative is True


def test_informative_carries_no_venue_literal_of_its_own():
    """Pinned on the STATEMENT with its indentation, not on the word.

    The first version of this test scanned the whole function source for
    ``"paper"`` and was failed by the docstring's own explanation of the
    literal it had just removed. A bare substring of source is satisfiable by
    prose in the same function; a whole statement is not.
    """
    import inspect

    from app.fund.tca import OrderCost
    src = inspect.getsource(OrderCost.informative.fget)
    body = src.rsplit('"""', 1)[-1]     # code only, past the docstring
    assert '"paper"' not in body and "'paper'" not in body, (
        "informative names a venue itself again; "
        "executionquality.SIMULATED_VENUES owns that list")
    assert '        return (self.venue or "") not in SIMULATED_VENUES' in src
