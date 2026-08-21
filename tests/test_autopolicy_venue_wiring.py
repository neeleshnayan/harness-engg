"""The worker tick that feeds the auto-approval envelope its venue read (v4).

`tests/test_autopolicy.py` pins the POLICY. This file pins the WIRING, which
had no test at all and is where v4's new input actually arrives: the broker
round trip lives in `run_autopolicy_tick`, and a policy that reads the venue
correctly while the tick never hands it one is a check that is not there.

Three properties, each of which is a way the wiring could be wrong while every
policy test still passed:

  1. the venue read REACHES the policy — the 2026-09-08 shape declines end to
     end, gathered rather than hand-built;
  2. an unreachable broker is not read as a flat account — the single most
     dangerous confusion on this path, because an empty positions list is what
     both return;
  3. the broker is asked ONCE PER TICK, not once per order, and not at all when
     the queue is empty. Cost that scales with the queue is how a control gets
     rate-limited off at the worst possible moment.
"""

from __future__ import annotations

import app.fund.heartbeat as heartbeat_mod
from app.api.v1 import fund as fund_router
from app.fund.autopolicy import EXIT_MARKER

TLT_BOOK = 3.019871           # live /fund/venue/reconcile, 2026-08-21
TLT_BROKER = 0.0              # the broker's own answer, same reading

HB_JOBS = [{"job": j, "ok": True, "age_seconds": 3.0}
           for j in ("exit_check", "risk_monitor", "settlement")]


class FakePos:
    def __init__(self, symbol, qty):
        self.symbol, self.qty = symbol, qty


class FakeConnector:
    """Counts its own round trips, so 'once per tick' is measured not assumed."""

    def __init__(self, positions=None, boom=False):
        self._positions = positions if positions is not None else []
        self.boom = boom
        self.calls = 0

    def positions(self):
        self.calls += 1
        if self.boom:
            raise ConnectionError("alpaca unreachable")
        return list(self._positions)

    def price(self, symbol):
        return 82.045          # the live TLT mark; agrees with the strike below


class FakeOrders:
    def __init__(self, rows):
        self.rows = rows

    def pending(self):
        return list(self.rows)


class FakePipeline:
    def __init__(self):
        self.approved = []

    def approve_order(self, oid, approver, policy_evaluation=None):
        self.approved.append((oid, approver, policy_evaluation))
        return {"status": "submitted"}


class FakeControl:
    def is_halted(self):
        return False


class MemStore:
    """Dict rows with the keys the gatherer reads — same shape as
    pgstore.stream(), matching tests/test_marksanity.py."""

    def __init__(self, rows=None):
        self.rows = list(rows or [])

    def add(self, type_, payload, aggregate_id="x", ts="2026-08-20T08:00:00Z"):
        self.rows.append({"type": type_, "payload": payload,
                          "aggregate_id": aggregate_id, "ts": ts})
        return self

    def stream(self, since_seq=0, limit=100_000):
        return list(self.rows)


def _tlt_log(order_id="o1"):
    """The real 2026-09-08 setup, from the live event log: ExitRuleSet seq 178
    (TLT, kind=time, on_date 2026-09-08, sleeve_beta_500) committed
    2026-08-18, the position opened 2026-08-19, the rule fired."""
    s = MemStore()
    s.add("ExitRuleSet", {"strategy_id": "sleeve_beta_500", "symbol": "TLT",
                          "kind": "time", "at": "2026-08-18T02:11:39+00:00"})
    s.add("OrderFilled", {"symbol": "TLT", "side": "buy",
                          "filled_qty": TLT_BOOK,
                          "strategy_id": "sleeve_beta_500",
                          "at": "2026-08-19T18:20:54+00:00"})
    s.add("NavStruck", {"total_nav_usd": 1885.74,
                        "positions": [{"symbol": "TLT", "mark": 82.045}]})
    s.add("ExitRuleTriggered", {"order_id": order_id, "symbol": "TLT",
                                "kind": "time",
                                "strategy_id": "sleeve_beta_500"})
    return s


def _pending(order_id="o1", symbol="TLT", qty=TLT_BOOK):
    return {"order_id": order_id, "symbol": symbol, "side": "sell", "qty": qty,
            # exitrule.py hardcodes venue="paper" on EVERY exit it raises,
            # whatever connector executes it. Carried here so the test order is
            # the real shape — and so a future venue-string check would be
            # caught by the assertions below rather than passing them.
            "venue": "paper",
            "rationale": f"{EXIT_MARKER}. 21 calendar days.",
            "age_minutes": 0.5}


def _wire(monkeypatch, connector, rows, store=None):
    pipe = FakePipeline()
    monkeypatch.setattr(fund_router, "_connector", connector)
    monkeypatch.setattr(fund_router, "_orders", FakeOrders(rows))
    monkeypatch.setattr(fund_router, "_pipeline", pipe)
    monkeypatch.setattr(fund_router, "_control", FakeControl())
    monkeypatch.setattr(fund_router, "_store", store or _tlt_log())
    monkeypatch.setattr(heartbeat_mod, "report", lambda: {"jobs": HB_JOBS})
    return pipe


def test_the_tick_declines_the_2026_09_08_exit_end_to_end(monkeypatch):
    """The whole path: pending queue -> venue snapshot -> gatherer -> policy.

    The broker holds ZERO TLT (live reading). The fund's book holds 3.019871.
    v3 approved this twelve checks out of twelve. If this ever asserts an
    approval, the machine sells shares that do not exist and opens a real
    short.
    """
    conn = FakeConnector(positions=[FakePos("SPY", 0.217757)])   # no TLT row
    pipe = _wire(monkeypatch, conn, [_pending()])

    out = fund_router.run_autopolicy_tick()

    assert pipe.approved == [], "nothing may be approved against a flat broker"
    assert out["policy_version"] == "v4"
    assert len(out["skipped"]) == 1
    assert "venue_holds_position" in out["skipped"][0]["failed_checks"]
    assert conn.calls == 1


def test_the_tick_approves_once_the_broker_actually_holds_the_shares(monkeypatch):
    """v4 must refuse the flat-broker case without refusing everything —
    otherwise it is a kill switch wearing a policy's name, and the fund's
    pre-committed exits stop executing."""
    conn = FakeConnector(positions=[FakePos("TLT", TLT_BOOK)])
    pipe = _wire(monkeypatch, conn, [_pending()])

    out = fund_router.run_autopolicy_tick()

    assert [a["order_id"] for a in out["approved"]] == ["o1"]
    assert len(pipe.approved) == 1
    oid, approver, verdict = pipe.approved[0]
    assert approver == "auto-policy-v4"
    # The approval event must carry the full evaluation for the riskofficer,
    # including what the BROKER said — that is the new audit surface.
    names = {c["check"]: c for c in verdict["checks"]}
    assert names["venue_holds_position"]["ok"] is True
    assert names["book_venue_in_sync"]["ok"] is True
    assert str(TLT_BOOK) in names["venue_holds_position"]["detail"]


def test_an_unreachable_broker_declines_and_is_not_read_as_flat(monkeypatch):
    """A network error must not become 'the account holds nothing'. The
    detail string has to say we could not LOOK, because reconnecting the
    broker and stopping the order are different fixes."""
    conn = FakeConnector(boom=True)
    pipe = _wire(monkeypatch, conn, [_pending()])

    out = fund_router.run_autopolicy_tick()

    assert pipe.approved == []
    assert "venue_holds_position" in out["skipped"][0]["failed_checks"]
    assert "book_venue_in_sync" in out["skipped"][0]["failed_checks"]


def test_the_broker_is_asked_once_per_tick_not_once_per_order(monkeypatch):
    """Five orders, one round trip. A per-order read makes the policy's cost a
    function of the queue length, which is how a control gets rate-limited off
    at exactly the moment the queue is long."""
    conn = FakeConnector(positions=[FakePos("TLT", TLT_BOOK)])
    rows = [_pending(order_id=f"o{i}") for i in range(1, 6)]
    _wire(monkeypatch, conn, rows, store=_tlt_log(order_id="o1"))

    fund_router.run_autopolicy_tick()

    assert conn.calls == 1, f"one tick, one broker round trip, got {conn.calls}"


def test_an_empty_queue_costs_the_broker_nothing(monkeypatch):
    """The normal case. The snapshot is taken AFTER the empty-queue return, so
    an idle fund does not poll Alpaca every 30 seconds forever."""
    conn = FakeConnector(positions=[FakePos("TLT", TLT_BOOK)])
    _wire(monkeypatch, conn, [])

    out = fund_router.run_autopolicy_tick()

    assert out["note"] == "queue empty"
    assert conn.calls == 0


def test_the_tick_never_reads_the_orders_own_venue_string(monkeypatch):
    """exitrule.py stamps venue="paper" on every exit regardless of which
    connector executes it, so an `order["venue"] == "paper"` check would have
    passed the exact orders that go to Alpaca. Changing the string must change
    nothing."""
    verdicts = []
    for venue in ("paper", "alpaca", "moon", None):
        conn = FakeConnector(positions=[])          # broker holds nothing
        row = _pending()
        row["venue"] = venue
        _wire(monkeypatch, conn, [row])
        out = fund_router.run_autopolicy_tick()
        verdicts.append(tuple(sorted(out["skipped"][0]["failed_checks"])))
    assert len(set(verdicts)) == 1, verdicts
