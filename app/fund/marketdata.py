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
from typing import Any
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
    #: Full OHLC, when the source provides it. Both Alpaca and Yahoo return it
    #: and we used to discard it, which made a candlestick chart impossible —
    #: a close-only series cannot show the range a signal actually fired inside.
    opens: list[float] | None = None
    highs: list[float] | None = None
    lows: list[float] | None = None
    volumes: list[float] | None = None
    start: str | None = None
    end: str | None = None
    #: Whether corporate actions have been applied. An unadjusted series turns a
    #: split into a crash, so a backtest run on one is measuring the wrong thing
    #: — this travels with the bars rather than being assumed by the caller.
    adjusted: bool = False
    adjustment: str = "none"
    #: Bar size, and the caveat that comes with an intraday one (short history,
    #: IEX-only on Alpaca's free tier). Travels with the data so a consumer
    #: cannot silently treat a thin intraday series as a deep daily one.
    timeframe: str = "1Day"
    intraday_note: str | None = None


def _from_alpaca(symbol: str, lookback_days: int, timeframe: str = "1Day") -> Bars | None:
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        return None
    try:
        from datetime import datetime, timedelta, timezone

        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
        from alpaca.data.enums import Adjustment

        client = StockHistoricalDataClient(key, secret)
        start = datetime.now(timezone.utc) - timedelta(days=lookback_days + 5)

        tf = TimeFrame.Day
        if timeframe != "1Day":
            spec = INTRADAY_TIMEFRAMES.get(timeframe)
            if spec is None:
                return None
            amount, unit = spec["alpaca"]
            tf = TimeFrame(amount, getattr(TimeFrameUnit, unit))
        # Alpaca defaults to adjustment="raw". On a raw series a 4:1 split is a
        # 75% single-day crash that never happened, and every momentum, breakout
        # and drawdown number computed downstream is then measuring a corporate
        # action. ALL applies both splits and dividends, which is the series a
        # total-return backtest is supposed to run on.
        req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=tf,
                               start=start, adjustment=Adjustment.ALL)
        bars = client.get_stock_bars(req)
        rows = bars.data.get(symbol, []) if hasattr(bars, "data") else []
        closes = [float(b.close) for b in rows]
        # Intraday bars need the time, not just the date — a chart or a fill
        # marker keyed on the date alone collapses a whole session into a point.
        dates = [(b.timestamp.date().isoformat() if timeframe == "1Day"
                  else b.timestamp.isoformat()) for b in rows]
        if not closes:
            return None
        return Bars(symbol=symbol, closes=closes, dates=dates, source="alpaca",
                    opens=[float(b.open) for b in rows],
                    highs=[float(b.high) for b in rows],
                    lows=[float(b.low) for b in rows],
                    volumes=[float(getattr(b, "volume", 0) or 0) for b in rows],
                    adjusted=True, adjustment="split+dividend",
                    start=dates[0] if dates else None, end=dates[-1] if dates else None)
    except Exception as e:  # noqa: BLE001 — fall through to the no-key source
        raise BarsError(f"Alpaca bars failed for {symbol}: {e}") from e


# Crypto tickers -> CoinGecko coin ids (free, no key; better crypto coverage
# than Alpaca/Yahoo and supports exact date ranges). Accepts BTC, BTC-USD, BTC/USDT.
_CRYPTO_IDS = {
    "BTC": "bitcoin", "XBT": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "DOGE": "dogecoin", "ADA": "cardano", "XRP": "ripple", "BNB": "binancecoin",
    "DOT": "polkadot", "LTC": "litecoin", "MATIC": "matic-network", "AVAX": "avalanche-2",
    "LINK": "chainlink", "TRX": "tron", "USDC": "usd-coin", "USDT": "tether",
}


def _crypto_id(symbol: str) -> str | None:
    base = (symbol or "").upper().split("-")[0].split("/")[0].strip()
    return _CRYPTO_IDS.get(base)


def _epoch(d: str) -> int:
    return int(datetime.fromisoformat(d).replace(tzinfo=timezone.utc).timestamp())


def _from_coingecko(symbol: str, lookback_days: int,
                    start: str | None = None, end: str | None = None) -> Bars | None:
    """Free daily closes for a crypto asset. Range endpoint honours exact windows."""
    coin = _crypto_id(symbol)
    if not coin:
        return None
    base = "https://api.coingecko.com/api/v3/coins/" + coin + "/market_chart"
    if start and end:
        url = f"{base}/range?vs_currency=usd&from={_epoch(start)}&to={_epoch(end)}"
    else:
        url = f"{base}?vs_currency=usd&days={max(1, lookback_days)}&interval=daily"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ClarkHarness)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            payload = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        raise BarsError(f"Could not reach CoinGecko for {symbol}: {e}") from e
    # prices: [[ms_epoch, price], ...]; collapse to one close per calendar date.
    by_date: dict[str, float] = {}
    for ms, px in payload.get("prices", []):
        d = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
        by_date[d] = float(px)  # last price seen for the date = daily close
    dates = sorted(by_date)
    closes = [by_date[d] for d in dates]
    if len(closes) < 2:
        raise BarsError(f"Not enough CoinGecko bars for '{symbol}' (got {len(closes)}).")
    return Bars(symbol=symbol.upper(), closes=closes, dates=dates, source="coingecko",
                # Crypto has no splits or dividends, so there is nothing to adjust
                # for — this is "not applicable", not "we skipped it".
                adjusted=True, adjustment="n/a — no corporate actions",
                start=dates[0], end=dates[-1])


def _yahoo_range(lookback_days: int) -> str:
    for days, rng in ((365, "1y"), (730, "2y"), (1825, "5y"), (3650, "10y")):
        if lookback_days <= days:
            return rng
    return "max"


def _from_yahoo(symbol: str, lookback_days: int,
                start: str | None = None, end: str | None = None,
                interval: str = "1d") -> Bars:
    # Yahoo Finance chart API — free, no key. Returns epoch timestamps + OHLC.
    if start and end:
        window = f"period1={_epoch(start)}&period2={_epoch(end)}"
    else:
        window = f"range={_yahoo_range(lookback_days)}"
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?{window}&interval={interval}"
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
    indicators = result.get("indicators") or {}
    raw_closes = ((indicators.get("quote") or [{}])[0]).get("close") or []
    # Yahoo serves the split/dividend-adjusted series in a SEPARATE field, and
    # `quote.close` is the raw one. Reading the raw field puts a phantom crash on
    # every split date; prefer adjclose and only fall back when it is absent.
    adj_closes = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []
    use_adjusted = len(adj_closes) == len(raw_closes) and any(c is not None for c in adj_closes)
    series = adj_closes if use_adjusted else raw_closes

    quote = (indicators.get("quote") or [{}])[0]
    raw_o, raw_h = quote.get("open") or [], quote.get("high") or []
    raw_l, raw_v = quote.get("low") or [], quote.get("volume") or []

    def at(seq, i):
        return seq[i] if i < len(seq) and seq[i] is not None else None

    closes: list[float] = []
    dates: list[str] = []
    opens: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    volumes: list[float] = []
    for i, ts in enumerate(stamps):
        c = at(series, i)
        if c is None:
            continue  # Yahoo emits null on non-trading gaps
        closes.append(float(c))
        when = datetime.fromtimestamp(ts, tz=timezone.utc)
        dates.append(when.date().isoformat() if interval == "1d" else when.isoformat())

        # Open/high/low are RAW even when the close is adjusted, so they must be
        # scaled by the same factor. Without this a candle drawn on a post-split
        # date would have its close outside its own high-low range.
        rc = at(raw_closes, i)
        factor = (float(c) / float(rc)) if (use_adjusted and rc) else 1.0
        o, h, low_, v = at(raw_o, i), at(raw_h, i), at(raw_l, i), at(raw_v, i)
        opens.append(float(o) * factor if o is not None else float(c))
        highs.append(float(h) * factor if h is not None else float(c))
        lows.append(float(low_) * factor if low_ is not None else float(c))
        volumes.append(float(v) if v is not None else 0.0)

    if (interval == "1d" and not (start and end)
            and lookback_days and len(closes) > lookback_days):
        n = lookback_days
        closes, dates = closes[-n:], dates[-n:]
        opens, highs, lows, volumes = opens[-n:], highs[-n:], lows[-n:], volumes[-n:]
    if len(closes) < 2:
        raise BarsError(f"Not enough bars for '{symbol}' to backtest (got {len(closes)}).")
    return Bars(
        symbol=symbol.upper(),
        closes=closes,
        dates=dates,
        source="yahoo",
        opens=opens, highs=highs, lows=lows, volumes=volumes,
        adjusted=use_adjusted,
        adjustment="split+dividend" if use_adjusted else "none",
        start=dates[0] if dates else None,
        end=dates[-1] if dates else None,
    )


#: Intraday timeframes, mapped to each source's own spelling and to how far
#: back that source will actually serve them. The limits are the vendors', not
#: ours — asking for a year of 1-minute bars returns a truncated series, and a
#: strategy warmed up on a truncated series is warmed up on nothing.
INTRADAY_TIMEFRAMES: dict[str, dict[str, Any]] = {
    "1Min":  {"alpaca": (1, "Minute"),  "yahoo": "1m",  "max_days": 7},
    "5Min":  {"alpaca": (5, "Minute"),  "yahoo": "5m",  "max_days": 60},
    "15Min": {"alpaca": (15, "Minute"), "yahoo": "15m", "max_days": 60},
    "1Hour": {"alpaca": (1, "Hour"),    "yahoo": "60m", "max_days": 730},
}
DAILY = "1Day"


def fetch_bars(symbol: str, lookback_days: int = 365,
               start: str | None = None, end: str | None = None,
               timeframe: str = DAILY) -> Bars:
    """Bars at a chosen timeframe. ``1Day`` (default) or an intraday interval.

    Intraday exists because a daily SMA(10/30) crosses a handful of times a
    year: a strategy on daily bars cannot be observed trading within a session,
    which makes the live path effectively untestable.

    Two caveats travel with intraday and are recorded on the returned bars
    rather than left for the caller to remember:

      * Alpaca's free tier is **IEX only** — a few percent of consolidated
        volume. Daily closes are close enough to the official ones; intraday is
        a genuinely different tape.
      * History is short (7 days of 1-minute bars, 60 of 5-minute). A long
        lookback silently returns fewer bars than asked for, which is exactly
        how a strategy ends up running on an unwarmed indicator.
    """
    tf = (timeframe or DAILY).strip()
    if tf == DAILY:
        return fetch_daily_bars(symbol, lookback_days=lookback_days, start=start, end=end)
    if tf not in INTRADAY_TIMEFRAMES:
        raise BarsError(
            f"unknown timeframe {tf!r}; use {DAILY} or one of "
            f"{', '.join(INTRADAY_TIMEFRAMES)}"
        )

    symbol = (symbol or "").strip().upper()
    if not symbol.replace(".", "").isalnum() or len(symbol) > 6:
        raise BarsError(f"Invalid symbol '{symbol}'.")

    spec = INTRADAY_TIMEFRAMES[tf]
    days = min(int(lookback_days), int(spec["max_days"]))

    bars = _from_alpaca(symbol, days, timeframe=tf)
    if bars is None:
        bars = _from_yahoo(symbol, days, interval=spec["yahoo"])
    bars.timeframe = tf
    bars.intraday_note = (
        f"{tf} bars from {bars.source}"
        + (" — IEX only on Alpaca's free tier, which is a fraction of "
           "consolidated volume" if bars.source == "alpaca" else "")
        + f"; this source serves at most {spec['max_days']} days at this timeframe"
    )
    return bars


def fetch_daily_bars(symbol: str, lookback_days: int = 365,
                     start: str | None = None, end: str | None = None) -> Bars:
    """Daily closes for a symbol. Crypto -> CoinGecko; equities -> Alpaca (if keyed) else Yahoo.

    ``start``/``end`` (ISO ``YYYY-MM-DD``) fetch an exact historical window; omit
    them for a trailing ``lookback_days`` window.
    """
    symbol = (symbol or "").strip().upper()
    # Crypto: CoinGecko first (free tier ≈ last 365 days). For deeper history it
    # errors, so fall back to Yahoo's crypto series (e.g. ETH-USD) which serves
    # full history + exact date ranges for free.
    if _crypto_id(symbol):
        base = symbol.split("-")[0].split("/")[0]
        try:
            cg = _from_coingecko(symbol, lookback_days, start=start, end=end)
            if cg is not None:
                return cg
        except BarsError:
            pass
        return _from_yahoo(f"{base}-USD", lookback_days, start=start, end=end)
    # Equities/ETFs: alnum tickers only (e.g. AAPL, GLD, SPY).
    if not symbol.replace(".", "").isalnum() or len(symbol) > 6:
        raise BarsError(f"Invalid symbol '{symbol}'.")
    alpaca = _from_alpaca(symbol, lookback_days) if not (start and end) else None
    if alpaca is not None:
        return alpaca
    return _from_yahoo(symbol, lookback_days, start=start, end=end)


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
