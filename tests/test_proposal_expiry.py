"""A proposed order goes stale. Approving one later executes an old decision."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.fund import pipeline as pipeline_mod
from app.fund.events import EventType
from app.fund.pipeline import PROPOSAL_STALE_AFTER_MINUTES, CommandError


class StubPipeline(pipeline_mod.CommandPipeline):
    """Only the approval path is under test, so construction is bypassed."""

    def __init__(self, events):
        self._events = events
        self.executed = []

    @property
    def _store(self):
        outer = self

        class S:
            @staticmethod
            def by_aggregate(aggregate_id):
                return [e for e in outer._events if e["aggregate_id"] == aggregate_id]

            @staticmethod
            def append(e):
                outer._events.append({
                    "aggregate_id": e.aggregate_id, "type": e.type.value,
                    "payload": e.payload, "ts": _now_iso(),
                })
                return e
        return S()


def _now_iso(minutes_ago: float = 0.0) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def proposed(minutes_ago: float, order_id="o1"):
    return [{
        "aggregate_id": order_id,
        "type": EventType.ORDER_PROPOSED.value,
        "ts": _now_iso(minutes_ago),
        "payload": {"venue": "paper", "symbol": "AAPL", "side": "buy", "qty": 10},
    }]


def test_a_fresh_proposal_is_not_stale():
    p = StubPipeline(proposed(minutes_ago=1))
    assert p._proposal_age_minutes("o1") == pytest.approx(1.0, abs=0.2)


def test_an_old_proposal_is_refused():
    p = StubPipeline(proposed(minutes_ago=PROPOSAL_STALE_AFTER_MINUTES + 30))
    with pytest.raises(CommandError) as e:
        p.approve_order("o1", approver="alice")
    msg = str(e.value)
    assert "past the" in msg
    assert "Re-propose" in msg


def test_the_refusal_happens_before_anything_is_written():
    """A rejected approval must leave no ORDER_APPROVED behind."""
    events = proposed(minutes_ago=PROPOSAL_STALE_AFTER_MINUTES + 5)
    p = StubPipeline(events)
    with pytest.raises(CommandError):
        p.approve_order("o1", approver="alice")
    assert [e["type"] for e in events] == [EventType.ORDER_PROPOSED.value]


def test_an_order_just_inside_the_window_is_still_approvable():
    p = StubPipeline(proposed(minutes_ago=PROPOSAL_STALE_AFTER_MINUTES - 5))
    age = p._proposal_age_minutes("o1")
    assert age is not None and age < PROPOSAL_STALE_AFTER_MINUTES


def test_a_missing_timestamp_does_not_block_approval():
    """An unparseable clock is a worse reason to refuse every approval than to
    let one through slightly late."""
    events = proposed(minutes_ago=0)
    del events[0]["ts"]
    assert StubPipeline(events)._proposal_age_minutes("o1") is None


def test_a_malformed_timestamp_does_not_block_approval():
    events = proposed(minutes_ago=0)
    events[0]["ts"] = "not-a-date"
    assert StubPipeline(events)._proposal_age_minutes("o1") is None


def test_a_naive_timestamp_is_treated_as_utc():
    """Without this the subtraction raises and every approval breaks."""
    events = proposed(minutes_ago=0)
    events[0]["ts"] = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    age = StubPipeline(events)._proposal_age_minutes("o1")
    assert age is not None and abs(age) < 1.0


def test_a_z_suffixed_timestamp_parses():
    events = proposed(minutes_ago=0)
    events[0]["ts"] = datetime.now(timezone.utc).replace(
        tzinfo=None).isoformat(timespec="seconds") + "Z"
    age = StubPipeline(events)._proposal_age_minutes("o1")
    assert age is not None and abs(age) < 1.0


def test_an_unknown_order_has_no_age():
    assert StubPipeline([])._proposal_age_minutes("nope") is None
