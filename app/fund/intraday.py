"""Intraday NAV samples — a P&L trace, deliberately NOT the NAV record.

Struck NAV is a fund event: it sets the price at which units are issued and
redeemed, it is appended to the permanent log, and it happens on a schedule the
mandate defines. Striking it every minute so a chart looks smooth would flood an
append-only ledger with hundreds of events a day and destroy the meaning of
"the day's NAV".

So intraday tracking is a separate thing with separate honesty rules:

  * samples live in memory only and are LOST on restart — they are telemetry,
    not a record, and nothing may be reconciled or reported from them
  * they are labelled ``struck: false`` so no consumer can mistake one for the
    official mark
  * the buffer is bounded, so a long-running process cannot grow without limit

What they are good for is the question an operator actually asks during a live
session: "is the fund up or down since the open, and how did it get there?"
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable

#: One sample a minute for ~24h. Bounded so an always-on process cannot leak.
MAX_SAMPLES = 1500

#: Minimum spacing. Sampling faster than the price cache refreshes just records
#: the same marks repeatedly and makes the chart look busier than reality.
MIN_INTERVAL_SECONDS = 55.0


class IntradayNav:
    """A bounded, in-memory time series of NAV samples."""

    def __init__(self, max_samples: int = MAX_SAMPLES,
                 min_interval: float = MIN_INTERVAL_SECONDS,
                 clock: Callable[[], float] = time.monotonic):
        self._buf: deque[dict[str, Any]] = deque(maxlen=max_samples)
        self._min_interval = min_interval
        self._clock = clock
        self._last = None

    def sample(self, nav_usd: float, nav_per_unit: float | None,
               cash_usd: float | None = None, force: bool = False) -> bool:
        """Record one point. Returns False if throttled."""
        now = self._clock()
        if not force and self._last is not None and (now - self._last) < self._min_interval:
            return False
        self._last = now
        self._buf.append({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "total_nav_usd": round(float(nav_usd), 4),
            "nav_per_unit": round(float(nav_per_unit), 8) if nav_per_unit is not None else None,
            "cash_usd": round(float(cash_usd), 2) if cash_usd is not None else None,
            "struck": False,
        })
        return True

    def series(self, minutes: int = 180) -> dict[str, Any]:
        """The last ``minutes`` of samples, oldest first, with the change across
        the window computed from the endpoints actually returned."""
        pts = list(self._buf)
        if minutes > 0 and pts:
            cutoff = time.time() - minutes * 60
            kept = []
            for p in pts:
                try:
                    t = datetime.fromisoformat(p["ts"]).timestamp()
                except (ValueError, KeyError):
                    continue
                if t >= cutoff:
                    kept.append(p)
            pts = kept or pts[-1:]

        first = pts[0] if pts else None
        last = pts[-1] if pts else None
        change_usd = change_pct = None
        if first and last and first.get("total_nav_usd"):
            change_usd = round(last["total_nav_usd"] - first["total_nav_usd"], 2)
            change_pct = round(
                (last["total_nav_usd"] / first["total_nav_usd"] - 1.0) * 100.0, 4
            )

        return {
            "samples": pts,
            "n": len(pts),
            "window_minutes": minutes,
            "change_usd": change_usd,
            "change_pct": change_pct,
            "from_ts": first["ts"] if first else None,
            "to_ts": last["ts"] if last else None,
            "note": "in-memory intraday samples, lost on restart and never struck — "
                    "telemetry for watching the session, not the NAV record",
        }

    def __len__(self) -> int:
        return len(self._buf)
