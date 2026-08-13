"""Live fill stream — and the idempotency that makes it safe to run alongside
the poller."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.fund.connectors.base import FillState
from app.fund.tradestream import TradeStream


# --------------------------------------------------------------------- fakes
class FakePipeline:
    """Records what the stream asked the ledger to do."""

    def __init__(self, result=None, unknown=False):
        self.calls = []
        self._result = result
        self._unknown = unknown

    def apply_venue_status(self, order_id, status):
        self.calls.append((order_id, status))
        if self._unknown:
            return {"status": "unknown_order", "order_id": order_id}
        return self._result or {"status": "filled", "order_id": order_id, "duplicate": False}


def update(event="fill", client_order_id="o1", status="filled",
           filled_qty=10, price=100.0):
    return SimpleNamespace(
        event=event,
        order=SimpleNamespace(client_order_id=client_order_id, status=status,
                              filled_qty=filled_qty, filled_avg_price=price),
        qty=filled_qty, price=price,
    )


def stream(pipeline, **kw):
    return TradeStream(pipeline, "k", "s", paper=True, **kw)


# ------------------------------------------------------------------ mapping
def test_a_fill_reaches_the_ledger():
    p = FakePipeline()
    assert stream(p).apply(update()) == "applied"
    order_id, status = p.calls[0]
    assert order_id == "o1"
    assert status.state == FillState.FILLED
    assert status.filled_qty == 10


def test_our_order_id_is_the_client_order_id():
    """The venue only knows us by what we submitted with — that is what makes a
    pushed update addressable in our own log."""
    p = FakePipeline()
    stream(p).apply(update(client_order_id="904d818e-c3a0"))
    assert p.calls[0][0] == "904d818e-c3a0"


def test_a_partial_fill_is_applied():
    p = FakePipeline(result={"status": "working", "order_id": "o1"})
    assert stream(p).apply(update(event="partial_fill", status="partially_filled",
                                  filled_qty=4)) == "applied"
    assert p.calls[0][1].state == FillState.PARTIAL


@pytest.mark.parametrize("event,status", [
    ("canceled", "canceled"), ("rejected", "rejected"), ("expired", "expired"),
])
def test_terminal_failures_are_applied(event, status):
    p = FakePipeline(result={"status": "failed", "order_id": "o1"})
    assert stream(p).apply(update(event=event, status=status, filled_qty=0)) == "applied"
    assert p.calls[0][1].state == FillState.FAILED


def test_noise_events_are_ignored():
    """`new`, `pending_new`, `calculated` tell us nothing we did not know."""
    p = FakePipeline()
    for e in ("new", "pending_new", "calculated", "order_replace_rejected"):
        assert stream(p).apply(update(event=e)) == "ignored"
    assert p.calls == []


def test_an_update_without_an_order_is_ignored():
    p = FakePipeline()
    assert stream(p).apply(SimpleNamespace(event="fill", order=None)) == "ignored"


def test_an_update_without_a_client_id_is_ignored():
    p = FakePipeline()
    assert stream(p).apply(update(client_order_id=None)) == "ignored"


def test_a_dict_shaped_update_works():
    """The SDK object shape is not guaranteed; dicts must parse the same."""
    p = FakePipeline()
    raw = {"event": "fill",
           "order": {"client_order_id": "o9", "status": "filled",
                     "filled_qty": 3, "filled_avg_price": 50.0}}
    assert stream(p).apply(raw) == "applied"
    assert p.calls[0][0] == "o9"


# ------------------------------------------------------------- foreign fills
def test_an_order_we_never_placed_is_reported_not_invented():
    """Somebody trading the same venue account by hand is not ours to record."""
    p = FakePipeline(unknown=True)
    s = stream(p)
    assert s.apply(update(client_order_id="not-ours")) == "foreign"


# ---------------------------------------------------------------- accounting
def test_a_duplicate_is_counted_separately_from_an_application():
    p = FakePipeline(result={"status": "filled", "order_id": "o1", "duplicate": True})
    s = stream(p)
    assert s.apply(update()) == "duplicate"


def test_the_handler_never_raises_on_a_bad_frame():
    """Losing one update is survivable; losing the socket is not."""
    class Boom:
        def apply_venue_status(self, *a, **k):
            raise RuntimeError("ledger unavailable")
    s = stream(Boom())
    asyncio.run(s._on_update(update()))          # must not raise
    assert "ledger unavailable" in s.state()["last_error"]
    assert s.state()["events_seen"] == 1


def test_state_tracks_what_happened():
    p = FakePipeline()
    s = stream(p)
    asyncio.run(s._on_update(update()))
    st = s.state()
    assert st["events_seen"] == 1
    assert st["applied"] == 1
    assert st["last_event_ts"] is not None


# ------------------------------------------------------------------ recovery
def test_a_failed_connection_retries_and_does_not_raise():
    """A stream failure must degrade to polling, never take the spine down."""
    attempts = []

    def factory(*a, **k):
        attempts.append(1)
        raise ConnectionError("handshake failed")

    s = stream(FakePipeline(), stream_factory=factory)

    async def drive():
        task = asyncio.create_task(s.run())
        await asyncio.sleep(0.05)
        s.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(drive())
    assert attempts, "it should have tried to connect"
    assert s.state()["connected"] is False
    assert "handshake failed" in (s.state()["last_error"] or "")


def test_stop_is_safe_before_anything_connected():
    s = stream(FakePipeline())
    s.stop()                       # must not raise
    assert s.state()["enabled"] is False
