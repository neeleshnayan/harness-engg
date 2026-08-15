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

# symbol -> (session_date, latest_close, prior_close)
_prev_close_cache: dict[str, tuple[str, float, float | None]] = {}


def _session_closes(symbol: str) -> tuple[float | None, float | None, str | None]:
    """(latest close, prior close, latest close's date).

    Both are needed because the reference for a day change depends on whether
    the market is open. Intraday, "previous close" is the last completed
    session. Once closed, the live price IS that session's close, so comparing
    the two reports 0.00% — the honest figure after hours is the last session's
    own move, latest vs prior.
    """
    cached = _prev_close_cache.get(symbol)
    try:
        bars = fetch_daily_bars(symbol, lookback_days=10)
    except BarsError as e:
        _log.debug("no bars for %s: %s", symbol, e)
        bars = None

    if not bars or not bars.closes:
        if cached:
            return cached[1], cached[2], cached[0]
        return None, None, None

    latest = float(bars.closes[-1])
    prior = float(bars.closes[-2]) if len(bars.closes) > 1 else None
    date = bars.dates[-1] if bars.dates else ""
    _prev_close_cache[symbol] = (date, latest, prior)
    return latest, prior, date


def quote(symbol: str, held: dict[str, Any] | None = None) -> dict[str, Any]:
    latest, prior, prev_date = _session_closes(symbol)
    try:
        price = live_price(symbol)
    except Exception:
        price = None

    # No live tick: fall back to the last close, and mark it stale rather than
    # passing it off as live.
    stale = price is None
    if stale:
        price = latest

    # Pick the reference the change should be measured against. If the "live"
    # price is just the last close (market shut), the meaningful figure is that
    # session's own move, not zero.
    # Relative tolerance, not absolute: the live tick and the daily bar come from
    # different endpoints and agree to cents, not to floating-point bits. An
    # exact comparison treated 100.95 and 100.949997 as different sources and so
    # measured the change against itself, reporting +0.00% for everything.
    same_as_close = (
        latest is not None and price is not None
        and (abs(price - latest) / max(abs(latest), 1e-9)) < 1e-4
    )
    if same_as_close:
        prev = prior
    else:
        prev = latest

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
    # Second-source telemetry: when the two free feeds have both answered for
    # this symbol, say how far apart they were. A wide gap means one of them is
    # wrong, and the operator should learn that from the strip, not from a NAV
    # mark that quietly moved.
    try:
        from app.fund.marketdata import cross_checks
        cc = cross_checks().get(symbol)
        if cc:
            row["cross_check_bps"] = cc["divergence_bps"]
    except Exception:  # noqa: BLE001 — telemetry must never break a quote
        pass
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
