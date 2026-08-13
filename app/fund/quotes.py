"""Quote strip for the fund's universe.

Feeds the ticker: the symbols this fund actually cares about — everything held,
plus every asset scoped to a live strategy — with a real day change.

Day change needs a previous close, which is not in the event log (that stores
marks and cost basis). It comes from daily bars instead. Previous close only
moves once a day, so it is cached per symbol per session date; the live price is
not cached.

Anything we cannot price is returned with nulls and ``ok: false`` rather than a
zero, so the UI shows a gap instead of inventing a flat quote.
"""

from __future__ import annotations

import logging
from typing import Any

from app.fund.marketdata import BarsError, fetch_daily_bars, live_price

_log = logging.getLogger(__name__)

# symbol -> (session_date, previous_close)
_prev_close_cache: dict[str, tuple[str, float]] = {}


def _previous_close(symbol: str) -> tuple[float | None, str | None]:
    """Yesterday's close and its date. Cached — it changes once a day."""
    cached = _prev_close_cache.get(symbol)
    try:
        bars = fetch_daily_bars(symbol, lookback_days=7)
    except BarsError as e:
        _log.debug("no bars for %s: %s", symbol, e)
        return (cached[1], cached[0]) if cached else (None, None)

    if not bars or not bars.closes:
        return (cached[1], cached[0]) if cached else (None, None)

    # last bar is the most recent completed session
    close = float(bars.closes[-1])
    date = bars.dates[-1] if bars.dates else ""
    if cached and cached[0] == date:
        return cached[1], date
    _prev_close_cache[symbol] = (date, close)
    return close, date


def quote(symbol: str, held: dict[str, Any] | None = None) -> dict[str, Any]:
    prev, prev_date = _previous_close(symbol)
    try:
        price = live_price(symbol)
    except Exception:
        price = None

    # if there is no live tick, the last completed close is still honest —
    # but say so, rather than passing it off as a live price
    stale = price is None
    if stale:
        price = prev

    change = change_pct = None
    if price is not None and prev not in (None, 0):
        change = price - prev
        change_pct = (change / prev) * 100.0

    row: dict[str, Any] = {
        "symbol": symbol,
        "price": round(price, 4) if price is not None else None,
        "prev_close": round(prev, 4) if prev is not None else None,
        "prev_close_date": prev_date,
        "change": round(change, 4) if change is not None else None,
        "change_pct": round(change_pct, 4) if change_pct is not None else None,
        "stale": stale,
        "ok": price is not None,
        "held": bool(held),
    }
    if held:
        row.update({
            "qty": held.get("qty"),
            "value_usd": held.get("value_usd"),
            "weight_pct": held.get("weight_pct"),
            "unrealized_pnl_pct": held.get("unrealized_pnl_pct"),
        })
    return row


def universe(positions: list[dict[str, Any]], strategies: list[dict[str, Any]]) -> list[str]:
    """What the fund is watching: everything held, plus assets scoped to a
    non-archived strategy. Held symbols come first so the book leads the strip."""
    held = [p.get("symbol") for p in positions if p.get("symbol")]
    scoped: list[str] = []
    for s in strategies:
        if s.get("archived"):
            continue
        for sym in s.get("assets") or []:
            if sym not in held and sym not in scoped:
                scoped.append(sym)
    return held + scoped


def build(positions: list[dict[str, Any]], strategies: list[dict[str, Any]],
          limit: int = 24) -> dict[str, Any]:
    held_by_symbol = {p["symbol"]: p for p in positions if p.get("symbol")}
    syms = universe(positions, strategies)[:limit]
    rows = [quote(s, held_by_symbol.get(s)) for s in syms]
    return {
        "quotes": rows,
        "held_count": sum(1 for r in rows if r["held"]),
        "watch_count": sum(1 for r in rows if not r["held"]),
        "unpriced": [r["symbol"] for r in rows if not r["ok"]],
    }
