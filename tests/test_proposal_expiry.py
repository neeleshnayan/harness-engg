"""Stale proposals must be expired by the machine, not discovered by the operator.

The approve path already refuses a stale proposal - correctly. But refusal alone
left the queue holding buttons whose only possible outcome was an error, and the
one time it happened the signal had INVERTED: a take-profit proposal on a position
that had since fallen 8%. These tests pin the worker-side expiry and the staleness
fields the approval card renders.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.fund.events import Event, EventType
from app.fund.pipeline import PROPOSAL_STALE_AFTER_MINUTES


def _pipeline_with(store):
    from app.fund.pipeline import CommandPipeline
    from app.fund.connectors.paper import PaperConnector
    from app.fund.projections.nav import NavService
    return CommandPipeline(connector=PaperConnector(store),
                           nav_service=NavService(store), store=store)


class MemStore:
    def __init__(self):
        self.events = []

    def append(self, event):
        self.events.append(event)
        return event

    def by_aggregate(self, agg_id):
        out = []
        for e in self.events:
            if e.aggregate_id == agg_id:
                out.append({"type": e.type.value, "payload": e.payload,
                            "ts": getattr(e, "ts", None)})
        return out

    def stream(self, since_seq=0, limit=100_000):
        return [{"type": e.type.value, "payload": e.payload} for e in self.events]


def _proposed(store, order_id, minutes_ago):
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    e = Event(aggregate_id=order_id, aggregate_type="order",
              type=EventType.ORDER_PROPOSED,
              payload={"symbol": "TLT", "side": "buy", "qty": 1.0}, actor="t")
    e.ts = ts
    store.append(e)


def test_expiry_declines_only_what_is_past_the_limit():
    store = MemStore()
    _proposed(store, "old-1", PROPOSAL_STALE_AFTER_MINUTES + 60)
    _proposed(store, "fresh-1", 5)
    p = _pipeline_with(store)
    out = p.expire_stale_proposals([
        {"order_id": "old-1", "symbol": "TLT"},
        {"order_id": "fresh-1", "symbol": "DBC"},
    ])
    assert out["count"] == 1
    assert out["expired"][0]["order_id"] == "old-1"
    declines = [e for e in store.events if e.type == EventType.ORDER_DECLINED]
    assert len(declines) == 1
    assert declines[0].aggregate_id == "old-1"
    # The reason rides on the record - an expiry with no reason is just a
    # disappearance, and disappearances are what the log exists to prevent.
    assert "staleness limit" in declines[0].payload["reason"]
    assert declines[0].payload["approver"] == "worker"


def test_unknown_age_is_never_expired():
    """An unparseable timestamp means age UNKNOWN, and unknown is not stale.

    Expiring on unknown age would let a clock-format change silently clear the
    queue - absence read as a value, the exact error the fund refuses elsewhere.
    """
    store = MemStore()
    e = Event(aggregate_id="odd-1", aggregate_type="order",
              type=EventType.ORDER_PROPOSED, payload={"symbol": "X"}, actor="t")
    e.ts = "not-a-timestamp"
    store.append(e)
    p = _pipeline_with(store)
    out = p.expire_stale_proposals([{"order_id": "odd-1", "symbol": "X"}])
    assert out["count"] == 0
    assert not [e for e in store.events if e.type == EventType.ORDER_DECLINED]


def test_pending_rows_carry_age_and_staleness():
    from app.fund.projections.orders import _age_minutes, _is_stale
    fresh = datetime.now(timezone.utc).isoformat()
    old = (datetime.now(timezone.utc)
           - timedelta(minutes=PROPOSAL_STALE_AFTER_MINUTES + 30)).isoformat()
    assert _is_stale(fresh) is False
    assert _is_stale(old) is True
    # Unknown is None - not fresh, not stale, and the card must render it as
    # unknown rather than defaulting either way.
    assert _is_stale("garbage") is None
    assert _age_minutes(None) is None
    assert _age_minutes(old) > PROPOSAL_STALE_AFTER_MINUTES
