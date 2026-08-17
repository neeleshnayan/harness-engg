"""The gap between a rule that evaluates and a rule that acts.

`ExitRules.check()` was correct, tested, and inert. `EXIT_RULE_TRIGGERED` was
emitted by no code anywhere, and nothing turned a fired rule into a proposal — so
the $500 sleeve's primary falsification condition ("an exit fires and no proposal
appears in the queue") was guaranteed true before any order existed.

These tests pin the behaviour that closes it, and the invariant that matters most:
the machine proposes and never closes.
"""

from __future__ import annotations

from app.fund.events import Event, EventType
from app.fund.exitrule import ExitRules, build


class FakeStore:
    """Yields DICTS, like the real store. An earlier fake yielded objects, which
    is why ten green tests coexisted with a fold that found nothing."""

    def __init__(self, events=None):
        self.events = list(events or [])
        self.appended: list[Event] = []

    def stream(self, since_seq=0, limit=100_000):
        return list(self.events)

    def append(self, event):
        self.appended.append(event)
        self.events.append({"type": event.type.value, "payload": event.payload})
        return event


class FakePipeline:
    def __init__(self, status="pending", boom=False):
        self.status = status
        self.boom = boom
        self.orders = []

    def propose_order(self, order, actor):
        if self.boom:
            raise RuntimeError("venue unreachable")
        self.orders.append(order)
        return {"status": self.status, "order_id": f"ord-{len(self.orders)}"}


def _set_event(**kw):
    rule = build(kw.pop("strategy_id", "s1"), kw.pop("kind", "loss_pct"),
                 threshold_pct=kw.pop("threshold_pct", 10.0),
                 symbol=kw.pop("symbol", "ABC"), note=kw.pop("note", ""))
    return {"type": EventType.EXIT_RULE_SET.value, "payload": rule}


POS_DOWN = [{"symbol": "ABC", "unrealized_pnl_pct": -25.0, "qty": 7}]
POS_FLAT = [{"symbol": "ABC", "unrealized_pnl_pct": -1.0, "qty": 7}]


def test_a_fired_rule_raises_a_closing_proposal_and_records_the_trigger():
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    out = ExitRules(store).enforce(POS_DOWN, pipeline=pipe)

    assert len(out["raised"]) == 1
    assert len(pipe.orders) == 1
    order = pipe.orders[0]
    assert order.symbol == "ABC"
    assert order.side.value == "sell"
    assert order.qty == 7
    # The rule is quoted where the human will read it: on the approval card.
    assert "PRE-COMMITTED EXIT FIRED" in order.rationale
    assert "before the position existed" in order.rationale
    assert "override" in (order.critique or "")

    triggered = [e for e in store.appended
                 if e.type == EventType.EXIT_RULE_TRIGGERED]
    assert len(triggered) == 1
    assert triggered[0].payload["order_id"] == "ord-1"
    assert triggered[0].payload["symbol"] == "ABC"
    assert triggered[0].payload["reason"]


def test_it_proposes_and_never_closes():
    """The invariant the whole harness rests on.

    Nothing in this path may fill, settle or close. It hands a SELL to the
    ordinary proposal pipeline, where the pre-trade gate runs and a human clicks.
    """
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    out = ExitRules(store).enforce(POS_DOWN, pipeline=pipe)
    assert out["raised"][0]["proposal_status"] == "pending"
    kinds = {e.type for e in store.appended}
    assert kinds == {EventType.EXIT_RULE_TRIGGERED}, \
        "enforce() wrote something other than the trigger event"


def test_a_second_tick_does_not_raise_a_duplicate():
    """Without idempotency the 30-second tick buries the queue in one decision."""
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    rules = ExitRules(store)

    first = rules.enforce(POS_DOWN, pipeline=pipe)
    assert len(first["raised"]) == 1

    second = rules.enforce(POS_DOWN, pipeline=pipe)
    assert second["raised"] == []
    assert len(second["skipped"]) == 1
    assert "already triggered" in second["skipped"][0]["why_skipped"]
    assert len(pipe.orders) == 1, "a duplicate proposal was raised"


def test_recommitting_a_rule_lets_it_fire_again():
    """A fresh EXIT_RULE_SET is a fresh commitment and clears `triggered`."""
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    rules = ExitRules(store)
    rules.enforce(POS_DOWN, pipeline=pipe)
    assert len(pipe.orders) == 1

    store.events.append(_set_event())          # supersede with a new commitment
    again = rules.enforce(POS_DOWN, pipeline=pipe)
    assert len(again["raised"]) == 1
    assert len(pipe.orders) == 2


def test_an_overridden_rule_is_not_re_raised():
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    store.events.append({
        "type": EventType.EXIT_RULE_OVERRIDDEN.value,
        "payload": {"strategy_id": "s1", "symbol": "ABC", "kind": "loss_pct",
                    "reason": "earnings in two days, holding through", "at": "x"}})
    out = ExitRules(store).enforce(POS_DOWN, pipeline=pipe)
    assert out["raised"] == []
    assert "deliberately overridden" in out["skipped"][0]["why_skipped"]
    assert pipe.orders == []


def test_the_trigger_is_recorded_even_when_the_proposal_fails():
    """Ordering matters most exactly when something is already wrong.

    If the proposal cannot be raised, the log must still show the exit fired.
    Recording it only on success would lose the trigger in the one case where the
    operator most needs to know.
    """
    store = FakeStore([_set_event()])
    pipe = FakePipeline(boom=True)
    out = ExitRules(store).enforce(POS_DOWN, pipeline=pipe)

    assert out["raised"] == []
    assert len(out["failed"]) == 1
    assert "venue unreachable" in out["failed"][0]["error"]
    triggered = [e for e in store.appended
                 if e.type == EventType.EXIT_RULE_TRIGGERED]
    assert len(triggered) == 1
    assert triggered[0].payload["order_id"] is None
    assert "worst state" in out["note"]


def test_a_fired_rule_with_no_position_quantity_is_a_failure_not_a_skip():
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    out = ExitRules(store).enforce(
        [{"symbol": "ABC", "unrealized_pnl_pct": -25.0, "qty": 0}], pipeline=pipe)
    assert out["raised"] == []
    assert len(out["failed"]) == 1
    assert "no position quantity" in out["failed"][0]["error"]
    assert pipe.orders == []


def test_a_holding_rule_raises_nothing():
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    out = ExitRules(store).enforce(POS_FLAT, pipeline=pipe)
    assert out["raised"] == [] and out["failed"] == []
    assert pipe.orders == []
    assert store.appended == []
    assert "no exit fired" in out["note"]


def test_an_unmarked_position_is_unevaluable_not_fine():
    store = FakeStore([_set_event()])
    pipe = FakePipeline()
    out = ExitRules(store).enforce(
        [{"symbol": "ABC", "unrealized_pnl_pct": None, "qty": 7}], pipeline=pipe)
    assert out["raised"] == []
    assert len(out["unevaluable"]) == 1
    assert "not the same as fine" in out["note"]
