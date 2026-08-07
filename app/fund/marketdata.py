"""Historical daily bars for backtesting — free sources, no paid data required.

Resolution order:
  1. Alpaca (free IEX feed) when ALPACA_API_KEY / ALPACA_SECRET_KEY are set —
     same account the live venue uses.
  2. Yahoo Finance chart API — a free, **no-key** JSON endpoint. Default fallback
     so "backtest by symbol" works out of the box with no credentials.

Returns a plain list of close prices (oldest first) — exactly what
``SimpleBacktester`` / ``sma_crossover_signals`` consume. Network/parse failures
raise ``BarsError`` with a readable message; the caller maps it to HTTP 422.
"""

from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone


class BarsError(Exception):
    """Raised when daily bars cannot be fetched or parsed."""


@dataclass
class Bars:
    symbol: str
    closes: list[float]
    source: str
    dates: list[str] | None = None  # ISO date per close (for time-axis charts)
    start: str | None = None
    end: str | None = None


def _from_alpaca(symbol: str, lookback_days: int) -> Bars | None:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    try:
        from datetime import datetime, timedelta, timezone

        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        client = StockHistoricalDataClient(key, secret)
        start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=start)
        bars = client.get_stock_bars(req)
        rows = bars.data.get(symbol, []) if hasattr(bars, "data") else []
        closes = [float(b.close) for b in rows]
        dates = [b.timestamp.date().isoformat() for b in rows]
        if not closes:
            return None
        return Bars(symbol=symbol, closes=closes, dates=dates, source="alpaca",
                    start=dates[0] if dates else None, end=dates[-1] if dates else None)
    except Exception as e:  # noqa: BLE001 — fall through to the no-key source
        raise BarsError(f"Alpaca bars failed for {symbol}: {e}") from e


def _yahoo_range(lookback_days: int) -> str:
    for days, rng in ((365, "1y"), (730, "2y"), (1825, "5y"), (3650, "10y")):
        if lookback_days <= days:
            return rng
    return "max"


def _from_yahoo(symbol: str, lookback_days: int) -> Bars:
    # Yahoo Finance chart API — free, no key. Returns epoch timestamps + OHLC.
    rng = _yahoo_range(lookback_days)
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range={rng}&interval=1d"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ClarkHarness)"})
        with urllib.request.urlopen(req, timeout=15) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        raise BarsError(f"Could not reach Yahoo Finance for {symbol}: {e}") from e

    chart = (payload or {}).get("chart", {})
    if chart.get("error"):
        raise BarsError(f"No daily bars for '{symbol}': {chart['error'].get('description', 'unknown symbol')}.")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise BarsError(f"No daily bars for '{symbol}' (check the symbol).")

    stamps = result.get("timestamp") or []
    raw_closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    closes: list[float] = []
    dates: list[str] = []
    for ts, c in zip(stamps, raw_closes):
        if c is None:
            continue  # Yahoo emits null on non-trading gaps
        closes.append(float(c))
        dates.append(datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat())

    if lookback_days and len(closes) > lookback_days:
        closes, dates = closes[-lookback_days:], dates[-lookback_days:]
    if len(closes) < 2:
        raise BarsError(f"Not enough bars for '{symbol}' to backtest (got {len(closes)}).")
    return Bars(
        symbol=symbol.upper(),
        closes=closes,
        dates=dates,
        source="yahoo",
        start=dates[0] if dates else None,
        end=dates[-1] if dates else None,
    )


def fetch_daily_bars(symbol: str, lookback_days: int = 365) -> Bars:
    """Fetch daily close prices for a symbol (Alpaca if keyed, else Yahoo)."""
    symbol = (symbol or "").strip().upper()
    if not symbol.isalnum() or len(symbol) > 6:
        raise BarsError(f"Invalid symbol '{symbol}'.")
    alpaca = _from_alpaca(symbol, lookback_days)
    if alpaca is not None:
        return alpaca
    return _from_yahoo(symbol, lookback_days)


# --- live marks (free) -----------------------------------------------------
# Cache last quotes so NAV recompute / projections don't hammer the source.
_QUOTE_CACHE: dict[str, tuple[float, float]] = {}
_QUOTE_TTL_S = 300.0


def live_price(symbol: str) -> float | None:
    """Latest free mark for a symbol (most-recent daily close), cached ~5min.

    Returns None on any failure so callers can fall back to a seed price. Lets
    the paper venue mark positions at real market levels without a paid feed —
    'paper execution, live marks'. When Alpaca is configured the venue uses its
    own live marks instead and this path is unused.
    """
    import time

    symbol = (symbol or "").strip().upper()
    if not symbol.isalnum() or len(symbol) > 6:
        return None
    now = time.time()
    hit = _QUOTE_CACHE.get(symbol)
    if hit and now - hit[1] < _QUOTE_TTL_S:
        return hit[0]
    try:
        bars = _from_yahoo(symbol, lookback_days=5)
        px = bars.closes[-1]
        _QUOTE_CACHE[symbol] = (px, now)
        return px
    except Exception:  # noqa: BLE001
        return None
