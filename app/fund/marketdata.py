"""Historical daily bars for backtesting — free sources, no paid data required.

Resolution order, EQUITIES:
  1. Alpaca (free IEX feed) when ALPACA_API_KEY / ALPACA_SECRET_KEY are set —
     same account the live venue uses.
  2. Yahoo Finance chart API — a free, **no-key** JSON endpoint. Default fallback
     so "backtest by symbol" works out of the box with no credentials.

Resolution order, CRYPTO (`CRYPTO_SOURCE_ORDER`):
  1. Alpaca's crypto data — the venue's own tape, public without credentials.
  2. CoinGecko, for a base it knows by id.
  3. Yahoo's `X-USD` series.

A ticker is not an identity, so what a source SERVED travels with the bars
(`instrument_name` / `instrument_type` / `exchange`) and how old the newest bar
is travels as a state (`freshness`), never as a number a caller must interpret.

Returns a plain list of close prices (oldest first) — exactly what
``SimpleBacktester`` / ``sma_crossover_signals`` consume. Network/parse failures
raise ``BarsError`` with a readable message; the caller maps it to HTTP 422.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request
from typing import Any
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class BarsError(Exception):
    """Raised when daily bars cannot be fetched or parsed."""


class SymbolNotFound(BarsError):
    """THE SOURCE SAYS THERE IS NO SUCH SYMBOL. Not an outage.

    Its own class because the two were indistinguishable and the message read
    like the wrong one: asking for a nonexistent ticker produced *"Could not
    reach Yahoo Finance for ZZZZZ: HTTP Error 404: Not Found"* — an outage
    sentence for a symbol that simply does not exist. An operator retries an
    outage; a nonexistent symbol is a typo or a delisting and retrying it
    forever is how a dead name stays in a universe.
    """


class WrongInstrument(BarsError):
    """The source served bars, and they are for something else.

    MEASURED, 2026-08-27, and this is why it exists: ``GETH`` returns HTTP 200
    with real daily bars for *Green EnviroTech Holdings Corp.* on OTC Markets
    at $0.0001 — a penny stock standing in for whatever the caller meant. A
    naive "200 and non-empty" check passes it. ``HYPE-USD`` on the same source
    is *Supreme Finance* at $5.4e-06, not the Hyperliquid token Alpaca lists
    and quotes near $40. Both are real bars for the wrong asset.
    """


class StaleSeries(BarsError):
    """The series exists and stopped. Absence wearing values.

    MEASURED on Alpaca's own crypto data, 2026-08-27: ``TRX/USD`` serves 332
    daily bars ending 2023-04-19, ``MATIC/USD`` 904 ending 2023-06-23,
    ``NEAR/USD`` 264 ending 2023-06-23, ``MKR/USD`` 1,709 ending 2025-09-05 —
    all at HTTP 200, none carrying any indication that the tape stopped years
    ago. Four of the pairs the analyst screened were corpses that answered
    like live ones.
    """


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
    #: WHAT THE SOURCE SAYS IT SERVED, when it says anything. A ticker is not
    #: an identity — `GETH` is a crypto token to one namespace and an OTC penny
    #: stock to another — so the resolved instrument travels with its bars
    #: rather than being assumed from the string that was asked for.
    instrument_name: str | None = None
    instrument_type: str | None = None
    exchange: str | None = None
    #: WHAT IS DOUBTFUL ABOUT THAT IDENTITY, in words. Its own field rather
    #: than sharing `freshness_note`, because "these bars are old" and "these
    #: bars may be a different asset" are different warnings and a reader who
    #: sees one where the other was meant has been misled by the shape of the
    #: payload rather than by its content.
    identity_note: str | None = None
    #: HOW OLD THE NEWEST BAR IS, and what that makes the series. `live`,
    #: `stale` or `unreadable` — never a bare number a caller has to interpret,
    #: and never absent, because "we did not look" and "it is current" are the
    #: two readings this field exists to keep apart. See `series_freshness`.
    freshness: str | None = None
    latest_bar_age_days: float | None = None
    freshness_note: str | None = None


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
        # SET HERE TOO, and that is not decoration: `freshness` is documented on
        # the dataclass as never absent, and a source that left it None would
        # make "we did not look" indistinguishable from "it is current" on the
        # one path the live fund uses most. Equity freshness is REPORTED and
        # never enforced — the bound for an exchange with holidays is a
        # calendar question, not a constant.
        fresh = (series_freshness(dates) if timeframe == "1Day"
                 else {"state": None, "age_days": None, "note": None})
        return Bars(symbol=symbol, closes=closes, dates=dates, source="alpaca",
                    opens=[float(b.open) for b in rows],
                    highs=[float(b.high) for b in rows],
                    lows=[float(b.low) for b in rows],
                    volumes=[float(getattr(b, "volume", 0) or 0) for b in rows],
                    adjusted=True, adjustment="split+dividend",
                    start=dates[0] if dates else None, end=dates[-1] if dates else None,
                    instrument_type="EQUITY", exchange="alpaca",
                    freshness=fresh["state"], latest_bar_age_days=fresh["age_days"],
                    freshness_note=fresh["note"])
    except Exception as e:  # noqa: BLE001 — fall through to the no-key source
        raise BarsError(f"Alpaca bars failed for {symbol}: {e}") from e


#: Quote currencies that make a symbol a crypto pair BY ITS FORM.
#:
#: This is what replaces the old arrangement, where a 16-entry dictionary
#: decided which symbols existed. `AAVE-USD` — an explicit pair, on Alpaca's
#: own tradable list — was REFUSED as an "Invalid symbol" because AAVE was not
#: one of the sixteen and the hyphen then failed the equity path's alnum check.
#: A caller who writes a pair has already said which namespace it means, and
#: no list is needed to hear it.
#:
#: MEASURED against Alpaca's crypto assets, 2026-08-27: 73 pairs quoted in
#: exactly four currencies — USD (36), USDT, USDC and BTC. USDG and EUR are
#: carried because Alpaca has listed both historically and a quote currency
#: appearing is not a reason to refuse the pair.
CRYPTO_QUOTE_CURRENCIES: tuple[str, ...] = (
    "USD", "USDT", "USDC", "USDG", "EUR", "BTC", "ETH",
)

#: How old the newest bar may be before a series reads STALE rather than live.
#:
#: THREE calendar days, and the reason is the market's own clock: crypto trades
#: 24/7, so a gap of more than a couple of days is not a weekend, a holiday or
#: a half-session — it is a tape that stopped. The corpses this catches are not
#: marginal (TRX 3.4 years, MATIC and NEAR 3.2, MKR 0.98 as of 2026-08-27), so
#: the bound is not doing fine discrimination and does not need to.
#:
#: Deliberately NOT applied to equities: there the same question needs an
#: exchange calendar (a Thursday-to-Tuesday gap is normal in a holiday week),
#: and `navgap.HOLIDAYS` already owns that calendar. Widening this to equities
#: is a separate, calendar-aware piece of work.
CRYPTO_QUOTE_STALE_DAYS = 3.0

#: How long a read of the venue's list may take before it counts as
#: unreadable. It is on the routing path of a bare-ticker fetch, so it needs a
#: bound it owns rather than whatever the default socket timeout happens to be.
_UNIVERSE_TIMEOUT_S = 10.0

#: How long Alpaca's tradable-crypto list is cached. The list changes when
#: Alpaca lists or delists, which is a matter of months, not minutes.
_UNIVERSE_TTL_S = 3600.0
_UNIVERSE_CACHE: dict[str, Any] = {}


def series_freshness(dates: list[str] | None, asof: str | None = None,
                     bound_days: float = CRYPTO_QUOTE_STALE_DAYS) -> dict[str, Any]:
    """Is this series current, stopped, or unreadable? ONE function, three states.

    Computed from ONE input — the series' own dates — so a caller cannot hand
    in an empty list and then patch two of the four fields afterwards. That
    shape is how a payload comes to contradict itself.

    ``asof`` is the date freshness is judged AGAINST, and it defaults to today
    rather than being required, because the question "is this current" only has
    a meaning relative to something. A caller who asked for an explicit
    historical window passes that window's end: two-year-old bars are exactly
    what was requested and are not stale.

    THE THREE STATES:

      * ``live`` — the newest bar is within ``bound_days`` of ``asof``.
      * ``stale`` — there are bars and the newest is older than that.
      * ``unreadable`` — there are no dates, or they cannot be parsed. NOT the
        same as stale, and not the same as live: we do not know.
    """
    out: dict[str, Any] = {"state": "unreadable", "latest": None,
                           "age_days": None, "bound_days": float(bound_days),
                           "asof": None, "note": None}
    if not dates:
        out["note"] = ("the series carried no dates, so how old it is cannot "
                       "be read — unknown, not current")
        return out
    try:
        latest = datetime.fromisoformat(str(dates[-1])[:10]).date()
    except ValueError:
        out["note"] = (f"the newest date on this series ({dates[-1]!r}) could "
                       f"not be parsed, so how old it is cannot be read")
        return out
    try:
        reference = (datetime.fromisoformat(str(asof)[:10]).date() if asof
                     else datetime.now(timezone.utc).date())
    except ValueError:
        out["note"] = (f"the date to judge freshness against ({asof!r}) could "
                       f"not be parsed, so nothing was judged")
        return out

    age = float((reference - latest).days)
    out.update({"latest": latest.isoformat(), "age_days": age,
                "asof": reference.isoformat()})
    if age <= bound_days:
        out["state"] = "live"
        out["note"] = (f"the newest bar is {latest.isoformat()}, "
                       f"{age:.0f} day(s) before {reference.isoformat()}")
        return out
    out["state"] = "stale"
    out["note"] = (f"the newest bar is {latest.isoformat()} — {age:.0f} days "
                   f"({age / 365.25:.2f} years) before {reference.isoformat()}, "
                   f"past the {bound_days:g}-day bound. The series exists and "
                   f"it stopped; it is not a current quote")
    return out


def crypto_pair(symbol: str) -> tuple[str, str] | None:
    """``('BTC', 'USD')`` for BTC/USD, BTC-USD or BTC/USDT; None for a bare ticker.

    Only a KNOWN quote currency makes a pair, so an equity ticker that happens
    to carry a hyphen (``BRK-B``) is not mistaken for one.
    """
    raw = (symbol or "").upper().strip()
    for sep in ("/", "-"):
        if sep in raw:
            base, _, quote = raw.partition(sep)
            if base and quote in CRYPTO_QUOTE_CURRENCIES:
                return base, quote
    return None


def crypto_universe(refresh: bool = False) -> dict[str, Any]:
    """Alpaca's own tradable crypto pairs — the venue's list, not ours.

    THE MECHANISM THAT REPLACES THE SIXTEEN-COIN DICTIONARY as the answer to
    "which crypto does this fund know about". That dictionary is still here
    and still correct at its ACTUAL job — mapping a ticker to a CoinGecko coin
    id — but it was also standing in for the universe, and a universe written
    by hand goes stale in the direction nobody notices: Alpaca lists 36 USD
    pairs today (measured 2026-08-27) and sixteen of them were reachable.

    **UNREADABLE IS NOT EMPTY.** The list needs credentials; without them, or
    with the venue unreachable, this returns ``readable: False`` and a reason
    — never an empty set, which would read as "Alpaca lists no crypto" and
    silently un-list the whole asset class.

    Cached for an hour: the answer changes when Alpaca lists or delists.
    """
    import time as _time
    now = _time.time()
    hit = _UNIVERSE_CACHE.get("value")
    if hit and not refresh and now - float(hit.get("read_at") or 0) < _UNIVERSE_TTL_S:
        return hit

    out: dict[str, Any] = {"pairs": None, "bases": None, "readable": False,
                           "source": "alpaca", "read_at": now, "note": None}
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not (key and secret):
        out["note"] = ("ALPACA_API_KEY / ALPACA_SECRET_KEY are not set, so the "
                       "venue's tradable-crypto list could not be read — "
                       "UNKNOWN, not empty")
        _UNIVERSE_CACHE["value"] = out
        return out
    try:
        # Read with a BOUNDED urllib call rather than through the SDK. This sits
        # on the routing path of every bare-ticker bars fetch, so it needs a
        # timeout it actually owns; the SDK does not expose one. MEASURED on
        # this code, 2026-08-27: 1.34 s cold, 0.003 ms warm from the cache, 73
        # pairs. A borrowed figure from a sibling call would not have been the
        # cost of THIS one.
        host = ("https://paper-api.alpaca.markets"
                if (os.getenv("ALPACA_PAPER", "true").strip().lower()
                    not in ("false", "0", "no"))
                else "https://api.alpaca.markets")
        req = urllib.request.Request(
            host + "/v2/assets?asset_class=crypto&status=active",
            headers={"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret,
                     "User-Agent": "ClarkHarness"})
        with urllib.request.urlopen(req, timeout=_UNIVERSE_TIMEOUT_S) as r:
            assets = json.loads(r.read().decode("utf-8", "replace"))
        pairs = {str(a.get("symbol", "")).upper() for a in assets
                 if isinstance(a, dict) and a.get("tradable")}
        pairs.discard("")
        if not pairs:
            # A reachable venue that lists nothing is a different fact from an
            # unreachable one, and it is not a fact this venue has ever
            # produced. Reported as unreadable rather than believed.
            out["note"] = ("Alpaca answered with no tradable crypto pairs at "
                           "all, which has never been true of this venue — "
                           "treated as unreadable rather than as an empty "
                           "universe")
            _UNIVERSE_CACHE["value"] = out
            return out
        out.update({
            "pairs": frozenset(pairs),
            "bases": frozenset(p.split("/")[0].split("-")[0] for p in pairs),
            "readable": True,
        })
    except Exception as e:  # noqa: BLE001 — any failure is "we could not read it"
        out["note"] = (f"the venue's tradable-crypto list could not be read "
                       f"({type(e).__name__}: {e}) — UNKNOWN, not empty")
    _UNIVERSE_CACHE["value"] = out
    return out


# Crypto tickers -> CoinGecko coin ids (free, no key; better crypto coverage
# than Alpaca/Yahoo and supports exact date ranges). Accepts BTC, BTC-USD, BTC/USDT.
#
# NO LONGER THE UNIVERSE. This maps a ticker to the id CoinGecko needs and
# nothing else; which symbols are crypto is `crypto_pair` (by form) and
# `crypto_universe` (by the venue's list). A symbol absent from here is not
# "not crypto" — it is a symbol CoinGecko cannot be asked about by id.
_CRYPTO_IDS = {
    "BTC": "bitcoin", "XBT": "bitcoin", "ETH": "ethereum", "SOL": "solana",
    "DOGE": "dogecoin", "ADA": "cardano", "XRP": "ripple", "BNB": "binancecoin",
    "DOT": "polkadot", "LTC": "litecoin", "MATIC": "matic-network", "AVAX": "avalanche-2",
    "LINK": "chainlink", "TRX": "tron", "USDC": "usd-coin", "USDT": "tether",
}


#: Bare tickers that are ALSO listed US equities. Routing these to CoinGecko
#: prices a different instrument entirely.
#:
#: MEASURED against the SEC ticker map, 2026-08-21:
#:     BTC -> CIK 0002015034  Grayscale Bitcoin Mini Trust ETF
#:     ETH -> CIK 0002020455  Grayscale Ethereum Staking Mini ETF
#:
#: So `BTC` in this fund's equity namespace is a Grayscale ETF trading at tens
#: of dollars, and `_crypto_id` was pricing it as bitcoin spot at tens of
#: thousands — a ~1000x error in any position, exposure or drawdown that touched
#: it. The ambiguity is real and only the CALLER's namespace resolves it, so an
#: EXPLICIT crypto form (`BTC-USD`, `BTC/USDT`) still routes to CoinGecko; a
#: bare ticker with an EDGAR CIK does not.
#:
#: The CIK lookup is the test rather than a hardcoded list, so a future
#: `SOL`/`DOGE` ETF is handled the day it lists rather than the day someone
#: notices.
def _has_edgar_cik(base: str) -> bool:
    """Whether this bare ticker is a filed US issuer. Best effort and CACHED
    upstream; a lookup failure returns False so a network problem degrades to
    the old behaviour rather than blanking crypto entirely."""
    try:
        from app.fund.edgar import cik_for
        return bool(cik_for(base))
    except Exception:  # noqa: BLE001
        return False


def _crypto_id(symbol: str) -> str | None:
    raw = (symbol or "").upper().strip()
    base = raw.split("-")[0].split("/")[0].strip()
    coin = _CRYPTO_IDS.get(base)
    if not coin:
        return None
    # An explicit pair (BTC-USD, BTC/USDT) is unambiguous: the caller said
    # crypto. Only a BARE ticker is ambiguous, and only then does the equity
    # namespace get to win.
    explicit = raw != base
    if explicit:
        return coin
    if _has_edgar_cik(base):
        logger.info("%s resolves to an EDGAR filer — routing to equities, not "
                    "CoinGecko. Use %s-USD for the crypto asset.", base, base)
        return None
    return coin


def resolve_namespace(symbol: str) -> dict[str, Any]:
    """WHICH NAMESPACE DID THE CALLER MEAN — crypto or equities?

    One function, one input, and every basis named, because the answer used to
    be a dictionary lookup whose two possible outcomes ("crypto" and "not in my
    list") were doing the work of five different facts.

    THE BASES, in the order they are tried:

      * ``pair_form`` — the symbol IS a pair (``BTC/USD``, ``AAVE-USD``). The
        caller has already said which namespace it means; no list is consulted
        and none can refuse it.
      * ``equity_filer`` — a BARE ticker that is a filed US issuer. `BTC` is
        CIK 0002015034, the Grayscale Bitcoin Mini Trust ETF, and pricing it as
        bitcoin spot is a ~1000x error in any position that touches it. The
        equity namespace wins a bare ticker, exactly as before.
      * ``venue_listed`` — a bare ticker on Alpaca's own tradable crypto list.
      * ``coin_id`` — a bare ticker CoinGecko knows by id. This is the old
        sixteen-name behaviour, kept as a FALLBACK so that losing the venue
        list degrades to what the fund did yesterday rather than to nothing.
      * ``unlisted`` — none of the above; the equity path takes it.

    ``universe_readable`` travels with the answer: a bare ticker classed
    ``unlisted`` while the venue list could not be read is a DIFFERENT fact
    from one classed unlisted against a list we actually read, and a caller
    that cannot tell them apart will believe the first is the second.
    """
    raw = (symbol or "").upper().strip()
    pair = crypto_pair(raw)
    if pair:
        return {"crypto": True, "base": pair[0], "quote": pair[1],
                "basis": "pair_form", "universe_readable": None,
                "note": None}

    base = raw
    universe = crypto_universe()
    readable = bool(universe.get("readable"))
    listed = readable and base in (universe.get("bases") or frozenset())
    known = base in _CRYPTO_IDS
    if not (listed or known):
        return {"crypto": False, "base": base, "quote": None,
                "basis": "unlisted", "universe_readable": readable,
                "note": (None if readable else
                         "the venue's crypto list could not be read, so a bare "
                         "ticker absent from the coin-id map is being read as "
                         "an equity WITHOUT having checked the crypto "
                         "namespace: " + str(universe.get("note")))}
    # ASKED ONLY OF A PLAUSIBLE CRYPTO TICKER, never of every symbol. `AAPL`
    # must not pay for an EDGAR round trip to learn it is not a coin, and the
    # old code never charged it one either.
    if _has_edgar_cik(base):
        return {"crypto": False, "base": base, "quote": None,
                "basis": "equity_filer", "universe_readable": readable,
                "note": (f"{base} is a filed US issuer, so the bare ticker is "
                         f"read in the equity namespace. Use {base}-USD for "
                         f"the crypto asset.")}
    if listed:
        return {"crypto": True, "base": base, "quote": "USD",
                "basis": "venue_listed", "universe_readable": True,
                "note": None}
    return {"crypto": True, "base": base, "quote": "USD",
            "basis": "coin_id", "universe_readable": readable,
            "note": (None if readable else
                     "the venue's crypto list could not be read, so this was "
                     "classed from the coin-id map alone: "
                     + str(universe.get("note")))}


#: The earliest daily crypto bar Alpaca serves. MEASURED 2026-08-27: asking
#: from 2015-01-01 returns first bars of 2021-01-01 (BTC/USD, MATIC/USD) and
#: 2022-04-01 (TRX/USD) — never earlier. Used only to ask "did this pair EVER
#: trade here", which is what separates a corpse from a name the venue has
#: never listed.
_ALPACA_CRYPTO_EPOCH = "2015-01-01"


def _alpaca_crypto_rows(pair: str, start, end=None) -> list[Any] | None:
    """Daily bars for one pair, or None when the SDK/venue cannot be asked.

    Separated from `_from_alpaca_crypto` so the "did it EVER trade" probe and
    the ordinary fetch go through exactly one piece of request code — two
    copies would be two chances to ask a slightly different question and
    compare the answers as if they were the same one.
    """
    try:
        from alpaca.data.historical import CryptoHistoricalDataClient
        from alpaca.data.requests import CryptoBarsRequest
        from alpaca.data.timeframe import TimeFrame
    except Exception as e:  # noqa: BLE001 — SDK absent: fall through, do not fail
        logger.info("alpaca crypto SDK unavailable (%s); falling back", e)
        return None
    # Crypto market data is public on Alpaca; the keys are used when present so
    # the request rides the same account as the venue, and their absence is not
    # a reason to refuse.
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    try:
        client = (CryptoHistoricalDataClient(key, secret) if (key and secret)
                  else CryptoHistoricalDataClient())
        req = CryptoBarsRequest(symbol_or_symbols=pair, timeframe=TimeFrame.Day,
                                start=start, end=end)
        got = client.get_crypto_bars(req)
        return list(got.data.get(pair, [])) if hasattr(got, "data") else []
    except Exception as e:  # noqa: BLE001
        logger.info("alpaca crypto bars failed for %s (%s); falling back", pair, e)
        return None


def _from_alpaca_crypto(pair: str, lookback_days: int, start: str | None = None,
                        end: str | None = None) -> Bars | None:
    """The VENUE'S OWN bars for a crypto pair. None when Alpaca cannot serve it.

    Preferred over every other crypto source for one reason that is worth more
    than convenience: this is the tape the fund would execute against. A
    backtest run on a different venue's series for the same ticker is not a
    backtest of the same asset — measured on this very endpoint, `HYPE-USD` is
    Hyperliquid at Alpaca and *Supreme Finance* at $5.4e-06 on Yahoo.

    RETURNS None when the pair produced no bars in ANY window, because a venue
    that never listed a name has no opinion about it and another source may.
    RAISES ``StaleSeries`` when it produced bars that STOPPED — there the venue
    does have an opinion and it is the one nobody was hearing.
    """
    from datetime import timedelta as _td

    if start and end:
        rows = _alpaca_crypto_rows(pair, start, end)
        asof: str | None = end
    else:
        days = max(2, int(lookback_days or 365))
        rows = _alpaca_crypto_rows(
            pair, datetime.now(timezone.utc) - _td(days=days + 5))
        asof = None
    if rows is None:
        return None

    if not rows:
        # AN EMPTY WINDOW IS TWO DIFFERENT FACTS and they are separated by one
        # more question. MEASURED 2026-08-27: over the last 90 days TRX/USD and
        # ZZZZ/USD both return zero rows at HTTP 200; over all of history TRX
        # returns 332 rows ending 2023-04-19 and ZZZZ returns none. One is a
        # corpse and one was never listed, and the cheap window cannot tell.
        ever = _alpaca_crypto_rows(pair, _ALPACA_CRYPTO_EPOCH)
        if not ever:
            return None
        last = ever[-1].timestamp.date().isoformat()
        fresh = series_freshness([last], asof=asof)
        raise StaleSeries(
            f"{pair} has not traded at the venue since {last}: "
            f"{len(ever)} daily bars, {fresh['note']}. The endpoint answers "
            f"with real rows for a tape that stopped — ask for an explicit "
            f"start/end window if the history is what you want.")

    closes = [float(b.close) for b in rows]
    dates = [b.timestamp.date().isoformat() for b in rows]
    if len(closes) < 2:
        raise BarsError(f"Not enough Alpaca crypto bars for '{pair}' "
                        f"(got {len(closes)}).")
    fresh = series_freshness(dates, asof=asof)
    if fresh["state"] == "stale" and not (start and end):
        raise StaleSeries(
            f"{pair} is served by the venue but its tape stopped: "
            f"{fresh['note']}.")
    return Bars(
        symbol=pair, closes=closes, dates=dates, source="alpaca-crypto",
        opens=[float(b.open) for b in rows],
        highs=[float(b.high) for b in rows],
        lows=[float(b.low) for b in rows],
        volumes=[float(getattr(b, "volume", 0) or 0) for b in rows],
        # Crypto has no splits or dividends, so there is nothing to adjust for
        # — this is "not applicable", not "we skipped it".
        adjusted=True, adjustment="n/a — no corporate actions",
        start=dates[0], end=dates[-1],
        instrument_type="CRYPTOCURRENCY", exchange="alpaca",
        freshness=fresh["state"], latest_bar_age_days=fresh["age_days"],
        freshness_note=fresh["note"])


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
    # SAME BOUND, SAME REASON, AS THE VENUE PATH. A dead coin's id keeps
    # answering here too, and a series that stopped is not a quote wherever it
    # came from. An explicit start/end window is the caller asking for history
    # and is judged against that window's own end.
    fresh = series_freshness(dates, asof=end)
    if fresh["state"] == "stale" and not (start and end):
        raise StaleSeries(f"{symbol} at CoinGecko: {fresh['note']}.")
    return Bars(symbol=symbol.upper(), closes=closes, dates=dates, source="coingecko",
                # Crypto has no splits or dividends, so there is nothing to adjust
                # for — this is "not applicable", not "we skipped it".
                adjusted=True, adjustment="n/a — no corporate actions",
                start=dates[0], end=dates[-1],
                instrument_type="CRYPTOCURRENCY", exchange="coingecko",
                freshness=fresh["state"], latest_bar_age_days=fresh["age_days"],
                freshness_note=fresh["note"])


def _yahoo_range(lookback_days: int) -> str:
    for days, rng in ((365, "1y"), (730, "2y"), (1825, "5y"), (3650, "10y")):
        if lookback_days <= days:
            return rng
    return "max"


#: Yahoo's own word for what an instrument IS. Read off the chart payload's
#: `meta.instrumentType`, which it publishes on every 200. MEASURED
#: 2026-08-27: EQUITY (GETH, on OTC Markets), ETF (SPY, BTC), CRYPTOCURRENCY
#: (BTC-USD, AAVE-USD, GETH-USD). An equity and an ETF are the same namespace
#: for this fund's purposes; a cryptocurrency is not.
_EQUITY_INSTRUMENT_TYPES = ("EQUITY", "ETF", "MUTUALFUND", "INDEX")


def _from_yahoo(symbol: str, lookback_days: int,
                start: str | None = None, end: str | None = None,
                interval: str = "1d", expect: str | None = None) -> Bars:
    """Yahoo Finance chart API — free, no key. Epoch timestamps + OHLC.

    ``expect`` is ``"crypto"`` or ``"equity"`` when the caller knows which
    namespace it asked in, and it is checked against what Yahoo says it
    served. THE MEASURED REASON: a <=6-character ticker collides with
    something on this endpoint almost every time — ``GETH`` returns HTTP 200
    with real bars for *Green EnviroTech Holdings Corp.* at $0.0001 — and
    every check downstream was "did we get a 200 and some rows", which that
    passes.
    """
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
    except urllib.error.HTTPError as e:
        # A 404 HERE MEANS THE SYMBOL, NOT THE SERVICE. It used to be reported
        # as "Could not reach Yahoo Finance for ZZZZZ: HTTP Error 404" — an
        # outage sentence, on the one failure that will never clear by itself.
        if getattr(e, "code", None) == 404:
            raise SymbolNotFound(
                f"No such symbol '{symbol}' at Yahoo Finance (it answered 404 "
                f"for it). This is the symbol, not the feed — the feed was "
                f"reachable.") from e
        raise BarsError(f"Could not reach Yahoo Finance for {symbol}: {e}") from e
    except Exception as e:  # noqa: BLE001
        raise BarsError(f"Could not reach Yahoo Finance for {symbol}: {e}") from e

    chart = (payload or {}).get("chart", {})
    if chart.get("error"):
        raise SymbolNotFound(
            f"No such symbol '{symbol}' at Yahoo Finance: "
            f"{chart['error'].get('description', 'unknown symbol')}.")
    result = (chart.get("result") or [None])[0]
    if not result:
        raise SymbolNotFound(
            f"No such symbol '{symbol}' at Yahoo Finance (it answered with no "
            f"result for it).")

    meta = result.get("meta") or {}
    kind = str(meta.get("instrumentType") or "").upper() or None
    who = meta.get("longName") or meta.get("shortName")
    venue = meta.get("fullExchangeName") or meta.get("exchangeName")
    if expect == "crypto" and kind and kind != "CRYPTOCURRENCY":
        raise WrongInstrument(
            f"'{symbol}' was asked for as a crypto asset and Yahoo Finance "
            f"served a {kind}: {who!r} on {venue!r}. Real bars, wrong "
            f"instrument — refused rather than priced.")
    if expect == "equity" and kind == "CRYPTOCURRENCY":
        raise WrongInstrument(
            f"'{symbol}' was asked for in the equity namespace and Yahoo "
            f"Finance served a cryptocurrency: {who!r}. Refused rather than "
            f"priced.")

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
    fresh = series_freshness(dates, asof=end) if interval == "1d" else None
    # THE VENUE IS PART OF THE IDENTITY. `GETH` resolves to a real company with
    # real daily bars — on OTC Markets, at $0.0001 — and every check the fund
    # had was "did we get a 200 and some rows". Named, not refused: an OTC
    # listing is not by itself wrong, and what this fund may hold is a mandate
    # question a data module does not get to decide. What it can do is stop the
    # answer from arriving silently.
    identity = (f"{symbol.upper()} resolved to {who!r} on {venue!r} — an "
                f"off-exchange venue; confirm this is the instrument you meant"
                if any(t in str(venue or "").upper()
                       for t in ("OTC", "PINK", "PNK")) else None)
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
        # WHAT THE SOURCE SAYS IT SERVED. Carried on every series, including
        # the equity ones, because the collision that produced this field was
        # in the equity namespace: a caller holding `GETH` bars can now read
        # "Green EnviroTech Holdings Corp." off the object instead of
        # discovering it from a $0.0001 mark.
        instrument_name=who, instrument_type=kind, exchange=venue,
        identity_note=identity,
        # REPORTED for every daily series and ENFORCED for none of them here.
        # The equity bound is an exchange-calendar question `navgap.HOLIDAYS`
        # owns; the crypto refusal lives on the crypto path, where 24/7 makes
        # a multi-day gap unambiguous.
        freshness=(fresh or {}).get("state"),
        latest_bar_age_days=(fresh or {}).get("age_days"),
        freshness_note=(fresh or {}).get("note"),
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
    """Daily closes for a symbol, in the namespace the caller actually meant.

    ``start``/``end`` (ISO ``YYYY-MM-DD``) fetch an exact historical window; omit
    them for a trailing ``lookback_days`` window.

    ROUTING is `resolve_namespace`: an explicit pair (``BTC/USD``, ``AAVE-USD``)
    is crypto by its form, a bare ticker that files with the SEC is an equity,
    and the rest is decided against the venue's own tradable list with the
    coin-id map as the fallback when that list cannot be read.

    CRYPTO SOURCES, in order: the venue (Alpaca), then CoinGecko, then Yahoo —
    see `CRYPTO_SOURCE_ORDER` for why the venue leads. Equities are unchanged:
    Alpaca when keyed, else Yahoo.

    THREE REFUSALS THAT USED TO BE 200s WITH REAL NUMBERS IN THEM, each its own
    exception class so a caller can tell them apart:
    `SymbolNotFound` (no such symbol — NOT an outage),
    `WrongInstrument` (real bars for something else),
    `StaleSeries` (a crypto tape that stopped). An explicit start/end window
    suppresses the last one, because asking for history is not a mistake.
    """
    symbol = (symbol or "").strip().upper()
    where = resolve_namespace(symbol)
    if where["crypto"]:
        return _crypto_daily_bars(symbol, where, lookback_days, start, end)
    # Equities/ETFs: alnum tickers only (e.g. AAPL, GLD, SPY).
    if not symbol.replace(".", "").isalnum() or len(symbol) > 6:
        raise BarsError(f"Invalid symbol '{symbol}'.")
    alpaca = _from_alpaca(symbol, lookback_days) if not (start and end) else None
    if alpaca is not None:
        return alpaca
    bars = _from_yahoo(symbol, lookback_days, start=start, end=end, expect="equity")
    # A bare ticker that reached the equity path only because the venue's
    # crypto list could not be read is carrying an unchecked assumption, and
    # the assumption travels rather than being dropped here.
    if where.get("note"):
        bars.identity_note = " | ".join(
            x for x in (bars.identity_note, where["note"]) if x)
    return bars


#: The crypto sources, in the order they are asked and with the reason for the
#: order. THE VENUE COMES FIRST and that is the correctness change, not a
#: preference: a backtest run on a different venue's series for the same
#: ticker is not a backtest of the same asset. MEASURED 2026-08-27 — `HYPE-USD`
#: is Hyperliquid on Alpaca (~$40, on its tradable list) and *Supreme Finance*
#: at $5.4e-06 on Yahoo. Same six characters, two different assets, both
#: served at HTTP 200.
CRYPTO_SOURCE_ORDER = ("alpaca-crypto", "coingecko", "yahoo")


def _crypto_daily_bars(symbol: str, where: dict[str, Any], lookback_days: int,
                       start: str | None, end: str | None) -> Bars:
    """Daily bars for a crypto pair: the venue first, then the free sources.

    A ``StaleSeries`` from the venue is NOT caught and retried elsewhere. That
    would be the whole defect rebuilt: the venue said this tape stopped, and
    finding a source willing to serve it anyway is not a second opinion, it is
    a louder version of the same silence.
    """
    base = where["base"]
    try:
        venue = _from_alpaca_crypto(f"{base}/USD", lookback_days, start=start, end=end)
        if venue is not None:
            return venue
    except StaleSeries:
        raise
    except BarsError as e:
        logger.info("alpaca crypto declined %s (%s); trying the free sources", symbol, e)

    # CoinGecko: free tier is roughly the last 365 days by id, and it supports
    # exact date ranges. Only reachable for a base it knows by id.
    try:
        cg = _from_coingecko(symbol, lookback_days, start=start, end=end)
        if cg is not None:
            return cg
    except BarsError:
        pass

    bars = _from_yahoo(f"{base}-USD", lookback_days, start=start, end=end,
                       expect="crypto")
    # NAMED, NOT ASSUMED AWAY. The pair is on the venue's list and the bars
    # came from somewhere else, so the ticker namespaces may not agree — which
    # is exactly how HYPE-USD would have been priced as Supreme Finance. The
    # bars are still returned: refusing would leave a listed pair unpriceable
    # whenever the venue's own data path is down. The caller is told.
    universe = crypto_universe()
    listed = bool(universe.get("readable")) and base in (universe.get("bases") or frozenset())
    note = (f"{base} is on the venue's tradable list but these bars came from "
            f"{bars.source}, whose crypto ticker namespace is its own — "
            f"confirm the instrument before trading on them"
            if listed else
            f"{base} is NOT on the venue's tradable list and these bars came "
            f"from {bars.source}, whose crypto ticker namespace is its own — "
            f"there is nothing here to check the identity against")
    bars.identity_note = " | ".join(
        x for x in (bars.identity_note, f"{note} (served: {bars.instrument_name!r})")
        if x)
    return bars


# --- live marks (free) -----------------------------------------------------
# Cache last quotes so NAV recompute / projections don't hammer the source.
_QUOTE_CACHE: dict[str, tuple[float, float]] = {}
_QUOTE_TTL_S = 300.0

#: Last cross-source comparison per symbol: (primary, secondary, bps, epoch).
#: Kept so /quotes can surface "the two feeds disagree" instead of the fund
#: finding out via a bad mark. Telemetry, not the NAV record.
_CROSS_CHECK: dict[str, tuple[float, float, float, float]] = {}

#: Two closes for the same day should agree to rounding. Wider than this and
#: one of the feeds is stale or wrong — worth a warning, not worth guessing
#: which. 50bps is far outside normal close-vs-close noise.
CROSS_SOURCE_WARN_BPS = 50.0


def _from_stooq_quote(symbol: str) -> float | None:
    """Last close from stooq's CSV quote endpoint. US equities are `aapl.us`.

    Deliberately minimal: one row, one number. Stooq is the second opinion,
    not a bars provider — history stays with Alpaca/Yahoo.
    """
    import csv
    import io as _io
    import urllib.request

    url = f"https://stooq.com/q/l/?s={symbol.lower()}.us&f=sd2t2ohlcv&h&e=csv"
    try:
        with urllib.request.urlopen(url, timeout=6) as r:
            rows = list(csv.DictReader(_io.TextIOWrapper(r, encoding="utf-8")))
        close = float(rows[0]["Close"])
        # Stooq answers unknown tickers with N/D rows that float() rejects,
        # and occasionally with zeros — a zero mark would zero a position.
        return close if close > 0 else None
    except Exception:  # noqa: BLE001
        return None


def live_price(symbol: str) -> float | None:
    """Latest free mark for a symbol (most-recent daily close), cached ~5min.

    Two independent sources: Yahoo primary, stooq fallback. One feed was a
    single point of failure for every mark in NAV — a Yahoo outage didn't
    degrade the fund's pricing, it removed it. On a fresh Yahoo fetch the
    stooq figure is also pulled once and compared; a gap wider than
    CROSS_SOURCE_WARN_BPS is logged and kept in _CROSS_CHECK for /quotes to
    surface. The primary is still used — the point of a second source is to
    KNOW the feeds disagree, not to silently average two numbers into one
    that neither feed reported.

    Returns None only when both fail, so callers can fall back to a seed
    price. When Alpaca is configured the venue uses its own live marks and
    this path is unused.
    """
    import logging
    import time

    log = logging.getLogger(__name__)
    symbol = (symbol or "").strip().upper()
    if not symbol.isalnum() or len(symbol) > 6:
        return None
    now = time.time()
    hit = _QUOTE_CACHE.get(symbol)
    if hit and now - hit[1] < _QUOTE_TTL_S:
        return hit[0]

    px: float | None = None
    try:
        px = _from_yahoo(symbol, lookback_days=5).closes[-1]
    except Exception:  # noqa: BLE001
        px = None

    second = _from_stooq_quote(symbol)

    if px is not None and second is not None and px > 0:
        bps = abs(px - second) / px * 10_000.0
        _CROSS_CHECK[symbol] = (px, second, bps, now)
        if bps > CROSS_SOURCE_WARN_BPS:
            log.warning(
                "mark cross-check %s: yahoo %.4f vs stooq %.4f (%.1f bps apart) — "
                "using primary, but one of these is wrong",
                symbol, px, second, bps,
            )
    elif px is None and second is not None:
        log.warning("mark fallback %s: yahoo unavailable, using stooq %.4f", symbol, second)
        px = second

    if px is not None:
        _QUOTE_CACHE[symbol] = (px, now)
    return px


def cross_checks() -> dict[str, dict[str, float]]:
    """The latest primary-vs-secondary comparison per symbol, for /quotes."""
    return {
        s: {"primary": p, "secondary": sec, "divergence_bps": round(bps, 2), "at_epoch": at}
        for s, (p, sec, bps, at) in _CROSS_CHECK.items()
    }
