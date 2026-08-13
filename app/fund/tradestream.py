"""Live fill events from the venue, instead of asking every N seconds.

Polling makes a fill invisible for up to one interval. During that window NAV is
stale, the reconciler reports a divergence that is not real, and the risk engine
evaluates a book that no longer matches the venue — which an operator
experiences as "I sold it and the system does not know". At a 300-second
interval that was five minutes; even at 20 it is 20 seconds of wrong.

Alpaca pushes the same information over a websocket as it happens, so this
subscribes to ``trade_updates`` and feeds each one through the SAME code path
the poller uses. Nothing here interprets a fill differently; it just arrives
sooner.

**The poller stays.** This is deliberate redundancy, not a replacement:

    stream  — fast, and can silently drop frames, disconnect, or miss
              everything that happened while the process was down
    poller  — slow, and cannot miss

Redundancy is only safe if the second observer is harmless, so every path into
the ledger is idempotent (see ``CommandPipeline._emit_fill``): the event log
itself is the key, and a fill already recorded is refused rather than
double-booked.

A dead stream is worse than no stream, because it looks like a quiet market. So
connection state is tracked and surfaced rather than assumed, and a failure here
must never take the spine down — it degrades to polling, which is what the fund
ran on before.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable

_log = logging.getLogger(__name__)

#: Reconnect backoff, in seconds. Caps rather than growing without bound: a
#: venue that is down for an hour should still be retried every half minute, not
#: once more at the end of it.
_BACKOFF_START = 1.0
_BACKOFF_MAX = 30.0

#: Trade-update event names Alpaca sends that change an order's state. Anything
#: else (``new``, ``pending_new``, ``calculated`` …) is a status we already know.
TERMINAL_EVENTS = {"fill", "canceled", "rejected", "expired", "done_for_day"}
PARTIAL_EVENTS = {"partial_fill"}


class TradeStream:
    """Subscribes to venue trade updates and applies them to the ledger."""

    def __init__(self, pipeline, key: str, secret: str, paper: bool = True,
                 stream_factory: Callable[..., Any] | None = None):
        self._pipeline = pipeline
        self._key = key
        self._secret = secret
        self._paper = paper
        self._factory = stream_factory
        self._stream = None
        self._stop = False
        self._state: dict[str, Any] = {
            "enabled": True,
            "connected": False,
            "last_event_ts": None,
            "last_error": None,
            "events_seen": 0,
            "applied": 0,
            "duplicates": 0,
            "reconnects": 0,
        }

    # ------------------------------------------------------------------ state
    def state(self) -> dict[str, Any]:
        """Connection health, for whoever is reporting whether this works.

        ``connected`` is not a claim the socket is healthy — it is the last
        thing we observed. ``last_event_ts`` is the honest liveness signal, and
        a consumer should treat a long silence during market hours as suspect.
        """
        return dict(self._state)

    # -------------------------------------------------------------- lifecycle
    async def run(self) -> None:
        """Connect, subscribe, and keep reconnecting until stopped."""
        backoff = _BACKOFF_START
        while not self._stop:
            try:
                self._stream = self._build()
                self._stream.subscribe_trade_updates(self._on_update)
                self._state.update(connected=True, last_error=None)
                _log.warning("trade stream: connected (paper=%s)", self._paper)
                await self._drive(self._stream)
                # A clean return means the socket closed on us.
                self._state["connected"] = False
                if self._stop:
                    return
                raise ConnectionError("trade stream closed by the venue")
            except asyncio.CancelledError:
                self._state["connected"] = False
                raise
            except Exception as e:  # noqa: BLE001
                self._state.update(connected=False, last_error=f"{type(e).__name__}: {e}")
                self._state["reconnects"] += 1
                if self._stop:
                    return
                _log.warning("trade stream: %s — reconnecting in %.0fs "
                             "(polling still covers fills)", e, backoff)
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise
                backoff = min(backoff * 2, _BACKOFF_MAX)
            else:
                backoff = _BACKOFF_START

    def _build(self):
        if self._factory is not None:
            return self._factory(self._key, self._secret, paper=self._paper)
        from alpaca.trading.stream import TradingStream
        return TradingStream(self._key, self._secret, paper=self._paper)

    @staticmethod
    async def _drive(stream) -> None:
        """Run the stream inside OUR event loop.

        ``TradingStream.run()`` calls ``asyncio.run`` internally, which cannot be
        used from inside a running loop, so the coroutine underneath it is
        awaited directly. That is a private method: if a future alpaca-py removes
        it we fall back to running the blocking entry point on a worker thread,
        which is slower to shut down but always works.
        """
        runner = getattr(stream, "_run_forever", None)
        if runner is not None:
            await runner()
        else:
            await asyncio.to_thread(stream.run)

    def stop(self) -> None:
        self._stop = True
        self._state["enabled"] = False
        for name in ("stop_ws", "stop", "close"):
            fn = getattr(self._stream, name, None)
            if fn is None:
                continue
            try:
                res = fn()
                if asyncio.iscoroutine(res):
                    asyncio.get_event_loop().create_task(res)
                return
            except Exception:  # noqa: BLE001 — shutdown must not raise
                continue

    # ---------------------------------------------------------------- handler
    async def _on_update(self, data: Any) -> None:
        """One trade update. Never raises: a bad frame must not kill the socket."""
        try:
            self._state["events_seen"] += 1
            self._state["last_event_ts"] = time.time()
            outcome = self.apply(data)
            if outcome == "applied":
                self._state["applied"] += 1
            elif outcome == "duplicate":
                self._state["duplicates"] += 1
        except Exception as e:  # noqa: BLE001
            # Losing one update is survivable — the poller will catch it.
            # Losing the socket is not.
            self._state["last_error"] = f"handler: {type(e).__name__}: {e}"
            _log.warning("trade stream: could not apply an update (%s); "
                         "the settlement poller will catch it", e)

    def apply(self, data: Any) -> str:
        """Turn one trade update into ledger events. Pure enough to test."""
        event = str(_get(data, "event") or "").lower()
        order = _get(data, "order")
        if order is None:
            return "ignored"

        # Our order id IS the client_order_id we submitted with, which is what
        # makes a venue-pushed update addressable in our own log.
        order_id = _get(order, "client_order_id")
        if not order_id:
            return "ignored"

        if event not in TERMINAL_EVENTS and event not in PARTIAL_EVENTS:
            return "ignored"

        from app.fund.connectors.alpaca import map_status

        status = map_status(
            _get(order, "status"),
            _get(order, "filled_qty") or _get(data, "qty") or 0,
            _get(order, "filled_avg_price") or _get(data, "price"),
        )
        res = self._pipeline.apply_venue_status(str(order_id), status)
        if res.get("status") == "unknown_order":
            # An order this book never proposed — a manual trade in the venue's
            # own UI, or another process on the same account. Reported, never
            # invented into the ledger.
            _log.warning("trade stream: %s for an order we did not place (%s)",
                         event, order_id)
            return "foreign"
        return "duplicate" if res.get("duplicate") else "applied"


def _get(obj: Any, name: str) -> Any:
    """Read a field from an SDK object or a plain dict."""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    v = getattr(obj, name, None)
    return getattr(v, "value", v) if hasattr(v, "value") else v
