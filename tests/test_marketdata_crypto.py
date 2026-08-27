"""The crypto namespace: which symbols exist, what was served, and how old it is.

Offline. Every source is mocked; nothing here touches a network.

THE THREE INCIDENTS THESE GUARD AGAINST, all measured 2026-08-27:

  1. **The sixteen-coin hardcode.** `_CRYPTO_IDS` decided which symbols were
     crypto. Alpaca lists 36 USD pairs; sixteen were reachable. `AAVE-USD` —
     an explicit pair on the venue's own tradable list — was REFUSED with
     "Invalid symbol 'AAVE-USD'", because AAVE was not one of the sixteen and
     the hyphen then failed the equity path's alnum check.
  2. **The GETH collision** (Ed, D-C2). `GET /fund/marketdata/bars?symbol=GETH`
     returned HTTP 200 with real daily bars for *Green EnviroTech Holdings
     Corp.* on OTC Markets at $0.0001, and a genuine no-such-symbol returned
     422 saying "Could not reach Yahoo Finance ... HTTP 404" — an outage
     sentence for a ticker that does not exist. Both pass a 200-and-non-empty
     check.
  3. **The four corpses** (analyst, crypto landscape v1). TRX quotes stale
     since 2023-04, NEAR/MATIC since 2023-06, MKR since 2025-09, all served at
     HTTP 200 with no warning. "Filter on quote freshness, never on 'the
     endpoint returned a row.'"
"""
import json
import urllib.error

import pytest

from app.fund import marketdata as md
from app.fund.marketdata import (
    CRYPTO_QUOTE_STALE_DAYS,
    BarsError,
    StaleSeries,
    SymbolNotFound,
    WrongInstrument,
    crypto_pair,
    crypto_universe,
    fetch_daily_bars,
    resolve_namespace,
    series_freshness,
)


# --- fakes ----------------------------------------------------------------

class _Resp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Bar:
    """The shape alpaca-py's CryptoBar presents to `_from_alpaca_crypto`."""

    def __init__(self, day: str, close: float = 100.0):
        from datetime import date, datetime, timezone
        d = date.fromisoformat(day)
        self.timestamp = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
        self.close = close
        self.open = close
        self.high = close
        self.low = close
        self.volume = 1.0


def _days(n: int, last: str) -> list[str]:
    from datetime import date, timedelta
    end = date.fromisoformat(last)
    return [(end - timedelta(days=i)).isoformat() for i in range(n - 1, -1, -1)]


def _today() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date().isoformat()


def _yahoo(closes, stamps, meta=None, error=None):
    if error:
        body = {"chart": {"result": None, "error": {"description": error}}}
    else:
        body = {"chart": {"result": [{
            "timestamp": stamps,
            "meta": meta or {},
            "indicators": {"quote": [{"close": closes}]},
        }], "error": None}}
    return json.dumps(body).encode()


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Nothing in this file may reach a network, in either direction.

    The universe cache is cleared per test too: a module-level cache that
    survived between tests would let one test's fake universe decide another
    test's routing, which is the kind of coupling that makes a suite pass for
    the wrong reason.
    """
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    md._UNIVERSE_CACHE.clear()

    def _boom(*a, **k):
        raise AssertionError("a test reached the network")

    monkeypatch.setattr(md.urllib.request, "urlopen", _boom)
    monkeypatch.setattr(md, "_alpaca_crypto_rows", lambda *a, **k: None)
    monkeypatch.setattr(md, "_has_edgar_cik", lambda base: False)
    yield
    md._UNIVERSE_CACHE.clear()


def _universe(monkeypatch, *pairs, readable=True, note=None):
    value = {"pairs": frozenset(pairs) if readable else None,
             "bases": frozenset(p.split("/")[0] for p in pairs) if readable else None,
             "readable": readable, "source": "alpaca", "read_at": 0.0, "note": note}
    monkeypatch.setattr(md, "crypto_universe", lambda refresh=False: value)
    return value


# --- 1. freshness: three states, one function -----------------------------

def test_freshness_reads_live_stale_and_unreadable_as_three_different_things():
    assert series_freshness(_days(30, _today()))["state"] == "live"
    assert series_freshness(_days(30, "2023-04-19"))["state"] == "stale"
    assert series_freshness([])["state"] == "unreadable"
    assert series_freshness(None)["state"] == "unreadable"
    assert series_freshness(["not-a-date"])["state"] == "unreadable"


def test_an_unreadable_clock_is_not_reported_as_current_or_as_stopped():
    got = series_freshness([])
    assert got["age_days"] is None
    assert got["latest"] is None
    assert "unknown, not current" in got["note"]


def test_a_stale_series_says_how_old_in_words_a_person_reads():
    got = series_freshness(["2023-04-19"], asof="2026-08-27")
    assert got["state"] == "stale"
    assert got["age_days"] == 1226.0
    assert "2023-04-19" in got["note"] and "3.36 years" in got["note"]
    assert "it is not a current quote" in got["note"]


@pytest.mark.parametrize("age_days,expect", [
    (0, "live"), (1, "live"),
    (int(CRYPTO_QUOTE_STALE_DAYS) - 1, "live"),
    (int(CRYPTO_QUOTE_STALE_DAYS), "live"),        # the bound is INCLUSIVE
    (int(CRYPTO_QUOTE_STALE_DAYS) + 1, "stale"),   # and one day past it is not
    (400, "stale"),
])
def test_the_staleness_bound_is_probed_at_it_and_on_both_sides(age_days, expect):
    from datetime import date, timedelta
    asof = date.fromisoformat("2026-08-27")
    latest = (asof - timedelta(days=age_days)).isoformat()
    assert series_freshness([latest], asof=asof.isoformat())["state"] == expect


def test_freshness_is_judged_against_the_window_that_was_asked_for():
    """Two-year-old bars are not stale when two-year-old bars are the request."""
    got = series_freshness(_days(30, "2022-09-01"), asof="2022-09-01")
    assert got["state"] == "live"
    assert got["asof"] == "2022-09-01"
    # ...and the SAME series judged against today is stale. One series, two
    # questions, two answers — which is why `asof` is an argument.
    assert series_freshness(_days(30, "2022-09-01"))["state"] == "stale"


def test_an_unparsable_asof_judges_nothing_rather_than_defaulting_to_today():
    got = series_freshness(_days(5, "2026-08-27"), asof="whenever")
    assert got["state"] == "unreadable"
    assert "nothing was judged" in got["note"]


# --- 2. the pair form -----------------------------------------------------

@pytest.mark.parametrize("symbol,expect", [
    ("BTC/USD", ("BTC", "USD")),
    ("BTC-USD", ("BTC", "USD")),
    ("btc/usdt", ("BTC", "USDT")),
    ("AAVE-USD", ("AAVE", "USD")),
    ("ETH/BTC", ("ETH", "BTC")),
    ("BRK-B", None),        # an equity ticker that happens to carry a hyphen
    ("TOO-LONG-SYM", None),
    ("AAPL", None),
    ("", None),
    ("-USD", None),         # no base
])
def test_a_pair_is_recognised_by_its_form_and_nothing_else(symbol, expect):
    assert crypto_pair(symbol) == expect


# --- 3. the universe: unreadable is never empty ---------------------------

def test_no_credentials_makes_the_universe_UNREADABLE_never_an_empty_list():
    """An empty set here would read as 'Alpaca lists no crypto' and silently
    un-list the entire asset class."""
    got = crypto_universe()
    assert got["readable"] is False
    assert got["pairs"] is None and got["bases"] is None
    assert "UNKNOWN, not empty" in got["note"]


def test_a_venue_that_answers_with_nothing_is_unreadable_not_an_empty_universe(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    monkeypatch.setattr(md.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(json.dumps([]).encode()))
    got = crypto_universe()
    assert got["readable"] is False
    assert got["pairs"] is None
    assert "has never been true of this venue" in got["note"]


def test_a_failed_read_names_the_failure_and_stays_unreadable(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")

    def _die(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(md.urllib.request, "urlopen", _die)
    got = crypto_universe()
    assert got["readable"] is False
    assert "TimeoutError" in got["note"] and "UNKNOWN, not empty" in got["note"]


def test_a_FAILED_read_expires_far_sooner_than_a_successful_one(monkeypatch):
    """Found by the read-through, not by a test.

    A success and a failure were cached for the same hour, so one network blip
    would leave the router reading `universe_readable: False` — and classing
    bare tickers off the coin-id map alone — for the next sixty minutes. A
    success is a fact that stays true; a failure is a fact about one moment.
    """
    assert md._UNIVERSE_FAILURE_TTL_S < md._UNIVERSE_TTL_S

    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    calls = []

    def _die(*a, **k):
        calls.append(1)
        raise TimeoutError("blip")

    monkeypatch.setattr(md.urllib.request, "urlopen", _die)
    assert crypto_universe()["readable"] is False
    assert crypto_universe()["readable"] is False      # still inside the short TTL
    assert len(calls) == 1

    # Age the cached failure past the SHORT ttl but well inside the long one.
    md._UNIVERSE_CACHE["value"]["read_at"] -= md._UNIVERSE_FAILURE_TTL_S + 1
    crypto_universe()
    assert len(calls) == 2, "the failure was held for the success TTL"

    # A SUCCESS aged by the same amount is NOT re-read — the two really are
    # different lifetimes and not one constant with a longer name.
    rows = [{"symbol": "BTC/USD", "tradable": True}]
    monkeypatch.setattr(md.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(json.dumps(rows).encode()))
    assert crypto_universe(refresh=True)["readable"] is True
    md._UNIVERSE_CACHE["value"]["read_at"] -= md._UNIVERSE_FAILURE_TTL_S + 1
    before = md._UNIVERSE_CACHE["value"]["read_at"]
    crypto_universe()
    assert md._UNIVERSE_CACHE["value"]["read_at"] == before


def test_a_read_universe_carries_pairs_and_bases_and_drops_the_untradable(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "k")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "s")
    rows = [{"symbol": "BTC/USD", "tradable": True},
            {"symbol": "ONDO/USD", "tradable": True},
            {"symbol": "DEAD/USD", "tradable": False}]
    monkeypatch.setattr(md.urllib.request, "urlopen",
                        lambda *a, **k: _Resp(json.dumps(rows).encode()))
    got = crypto_universe()
    assert got["readable"] is True
    assert got["pairs"] == frozenset({"BTC/USD", "ONDO/USD"})
    assert got["bases"] == frozenset({"BTC", "ONDO"})


# --- 4. routing -----------------------------------------------------------

def test_an_explicit_pair_needs_no_list_at_all(monkeypatch):
    """THE HARDCODE'S BITE. AAVE is not one of the sixteen coin ids and the
    venue list is unreadable here — and the pair still routes as crypto,
    because the caller already said which namespace it meant."""
    _universe(monkeypatch, readable=False, note="no credentials")
    assert "AAVE" not in md._CRYPTO_IDS
    got = resolve_namespace("AAVE-USD")
    assert got["crypto"] is True and got["basis"] == "pair_form"


def test_a_bare_ticker_that_files_with_the_sec_stays_an_equity(monkeypatch):
    """BTC is CIK 0002015034, the Grayscale Bitcoin Mini Trust ETF. Pricing it
    as bitcoin spot is a ~1000x error in anything that touches it."""
    monkeypatch.setattr(md, "_has_edgar_cik", lambda base: base == "BTC")
    _universe(monkeypatch, "BTC/USD")
    got = resolve_namespace("BTC")
    assert got["crypto"] is False and got["basis"] == "equity_filer"
    assert "Use BTC-USD for the crypto asset" in got["note"]


def test_a_bare_ticker_on_the_venues_list_is_crypto_even_outside_the_coin_map(monkeypatch):
    """The whole point of reading the venue's list: ONDO is tradable there and
    has never been in the hand-written map."""
    _universe(monkeypatch, "ONDO/USD")
    assert "ONDO" not in md._CRYPTO_IDS
    got = resolve_namespace("ONDO")
    assert got["crypto"] is True and got["basis"] == "venue_listed"


def test_an_unreadable_venue_list_degrades_to_the_coin_map_AND_SAYS_SO(monkeypatch):
    _universe(monkeypatch, readable=False, note="ALPACA_API_KEY ... not set")
    got = resolve_namespace("SOL")
    assert got["crypto"] is True and got["basis"] == "coin_id"
    assert got["universe_readable"] is False
    assert "could not be read" in got["note"]


def test_an_unlisted_bare_ticker_against_an_UNREADABLE_list_carries_the_doubt(monkeypatch):
    """Classed an equity WITHOUT having checked the crypto namespace is a
    different fact from classed an equity against a list we actually read, and
    a caller that cannot tell them apart will believe the first is the second."""
    _universe(monkeypatch, readable=False, note="no credentials")
    got = resolve_namespace("ONDO")
    assert got["crypto"] is False and got["basis"] == "unlisted"
    assert "WITHOUT having checked the crypto namespace" in got["note"]
    # ...and against a READ list the same ticker is classed with no caveat.
    _universe(monkeypatch, "BTC/USD")
    clean = resolve_namespace("WHATEVER")
    assert clean["basis"] == "unlisted" and clean["note"] is None


def test_the_equity_path_does_not_pay_an_edgar_lookup_for_an_ordinary_ticker(monkeypatch):
    """AAPL must not buy a round trip to learn it is not a coin — the old code
    never charged it one either."""
    _universe(monkeypatch, "BTC/USD")
    calls = []
    monkeypatch.setattr(md, "_has_edgar_cik",
                        lambda base: calls.append(base) or False)
    resolve_namespace("AAPL")
    assert calls == []
    # ...and it IS asked when the ticker is a plausible coin, which is the
    # question it exists to answer.
    resolve_namespace("BTC")
    assert calls == ["BTC"]


# --- 5. the pair that used to be refused ----------------------------------

def test_a_venue_listed_pair_outside_the_coin_map_now_fetches(monkeypatch):
    """THE ITEM-2 REGRESSION PIN. Before this diff `fetch_daily_bars('AAVE-USD')`
    raised "Invalid symbol 'AAVE-USD'"; the hyphen failed the equity path's
    alnum check after the sixteen-name dictionary declined it."""
    _universe(monkeypatch, "AAVE/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows",
                        lambda pair, start, end=None: [_Bar(d, 120.0) for d in
                                                       _days(30, _today())])
    bars = fetch_daily_bars("AAVE-USD", lookback_days=30)
    assert bars.source == "alpaca-crypto"
    assert bars.symbol == "AAVE/USD"
    assert len(bars.closes) == 30
    assert bars.freshness == "live"
    assert bars.adjustment.startswith("n/a")


# --- 6. the GETH class: real bars, wrong instrument ------------------------

def test_a_crypto_request_answered_with_an_equity_is_REFUSED(monkeypatch):
    """`GETH` is a token to one namespace and an OTC penny stock to another,
    and the source publishes which one it served."""
    _universe(monkeypatch, "BTC/USD")
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([0.0001] * 30, stamps,
               meta={"instrumentType": "EQUITY", "symbol": "GETH",
                     "longName": "Green EnviroTech Holdings Corp.",
                     "fullExchangeName": "OTC Markets OTCPK"})))
    with pytest.raises(WrongInstrument) as e:
        fetch_daily_bars("GETH-USD", lookback_days=30)
    assert "Green EnviroTech" in str(e.value)
    assert "wrong instrument" in str(e.value)


def test_an_equity_request_answered_with_a_cryptocurrency_is_REFUSED(monkeypatch):
    _universe(monkeypatch, "BTC/USD")
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([1.0] * 30, stamps,
               meta={"instrumentType": "CRYPTOCURRENCY", "longName": "Whatever USD"})))
    with pytest.raises(WrongInstrument):
        fetch_daily_bars("WHTVR", lookback_days=30)


def test_an_equity_from_an_off_exchange_venue_is_NAMED_not_silently_priced(monkeypatch):
    """Not refused — what this fund may hold is a mandate question a data
    module does not decide. What it can do is stop the answer arriving
    silently at $0.0001."""
    _universe(monkeypatch, "BTC/USD")
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([0.0001] * 30, stamps,
               meta={"instrumentType": "EQUITY",
                     "longName": "Green EnviroTech Holdings Corp.",
                     "fullExchangeName": "OTC Markets OTCPK"})))
    bars = fetch_daily_bars("GETH", lookback_days=30)
    assert bars.instrument_name == "Green EnviroTech Holdings Corp."
    assert bars.exchange == "OTC Markets OTCPK"
    assert "off-exchange venue" in bars.identity_note
    # An ordinary listing carries no such note — zero is quiet.
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([400.0] * 30, stamps,
               meta={"instrumentType": "ETF", "longName": "SPDR S&P 500",
                     "fullExchangeName": "NYSEArca"})))
    assert fetch_daily_bars("SPY", lookback_days=30).identity_note is None


# --- 7. no such symbol is not an outage -----------------------------------

def test_a_404_says_the_symbol_does_not_exist_and_NOT_that_the_feed_is_down(monkeypatch):
    """The old message was "Could not reach Yahoo Finance for ZZZZZ: HTTP Error
    404" — an outage sentence on the one failure that never clears by itself."""
    _universe(monkeypatch, "BTC/USD")

    def _404(*a, **k):
        raise urllib.error.HTTPError("u", 404, "Not Found", None, None)

    monkeypatch.setattr(md.urllib.request, "urlopen", _404)
    with pytest.raises(SymbolNotFound) as e:
        fetch_daily_bars("ZZZZZ", lookback_days=30)
    text = str(e.value)
    assert "No such symbol" in text
    # THE SHARED-WORD AUDIT: the outage sentence must be gone, not merely
    # joined by a better one. A `match=` on "No such symbol" alone would pass
    # on a message that still opened with "Could not reach".
    assert "Could not reach" not in text
    assert "the feed was reachable" in text


def test_a_real_outage_still_reports_an_outage(monkeypatch):
    """The other half of the same fact: making 404 distinct must not make
    everything distinct."""
    _universe(monkeypatch, "BTC/USD")

    def _down(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(md.urllib.request, "urlopen", _down)
    with pytest.raises(BarsError) as e:
        fetch_daily_bars("AAPL", lookback_days=30)
    assert "Could not reach Yahoo Finance" in str(e.value)
    assert not isinstance(e.value, SymbolNotFound)


def test_a_500_is_an_outage_and_a_404_is_not(monkeypatch):
    _universe(monkeypatch, "BTC/USD")

    def _500(*a, **k):
        raise urllib.error.HTTPError("u", 500, "Server Error", None, None)

    monkeypatch.setattr(md.urllib.request, "urlopen", _500)
    with pytest.raises(BarsError) as e:
        fetch_daily_bars("AAPL", lookback_days=30)
    assert not isinstance(e.value, SymbolNotFound)


def test_the_charts_own_error_is_also_a_missing_symbol_not_an_outage(monkeypatch):
    _universe(monkeypatch, "BTC/USD")
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo(None, None, error="No data found, symbol may be delisted")))
    with pytest.raises(SymbolNotFound):
        fetch_daily_bars("ZZZQQ", lookback_days=30)


# --- 8. the corpses -------------------------------------------------------

def test_a_pair_whose_tape_stopped_is_REFUSED_with_the_date_it_stopped(monkeypatch):
    """TRX/USD: 332 bars ending 2023-04-19, served at HTTP 200 with no warning.
    Zero rows in a recent window and rows in the full history is exactly how a
    corpse presents."""
    _universe(monkeypatch, "TRX/USD")

    def _rows(pair, start, end=None):
        # A trailing window asks with a datetime; the ever-probe asks with the
        # epoch string. That is the only difference between the two calls.
        return ([_Bar(d) for d in _days(332, "2023-04-19")]
                if isinstance(start, str) else [])

    monkeypatch.setattr(md, "_alpaca_crypto_rows", _rows)
    with pytest.raises(StaleSeries) as e:
        fetch_daily_bars("TRX/USD", lookback_days=30)
    assert "2023-04-19" in str(e.value)
    assert "332 daily bars" in str(e.value)


def test_a_pair_the_venue_NEVER_listed_falls_through_rather_than_reading_stale(monkeypatch):
    """Zero rows in both windows is 'this venue has no opinion', which is not
    the same fact as 'this tape stopped' and must not borrow its refusal."""
    _universe(monkeypatch, "BTC/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows", lambda *a, **k: [])
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([2.0] * 30, stamps, meta={"instrumentType": "CRYPTOCURRENCY",
                                         "longName": "Some Coin USD"})))
    bars = fetch_daily_bars("SOMECOIN-USD", lookback_days=30)
    assert bars.source == "yahoo"


def test_a_series_that_STOPPED_is_refused_even_when_the_venue_serves_the_window(monkeypatch):
    """The other shape of the same corpse: rows come back, and they are old."""
    _universe(monkeypatch, "MKR/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows",
                        lambda *a, **k: [_Bar(d) for d in _days(50, "2025-09-05")])
    with pytest.raises(StaleSeries) as e:
        fetch_daily_bars("MKR/USD", lookback_days=30)
    assert "2025-09-05" in str(e.value)


def test_an_explicit_historical_window_is_not_a_mistake_and_is_not_refused(monkeypatch):
    """Asking for 2022 is asking for 2022. Freshness is judged against the
    window's own end, so history stays reachable."""
    _universe(monkeypatch, "TRX/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows",
                        lambda *a, **k: [_Bar(d) for d in _days(93, "2022-09-01")])
    bars = fetch_daily_bars("TRX/USD", start="2022-06-01", end="2022-09-01")
    assert bars.source == "alpaca-crypto" and len(bars.closes) == 93
    assert bars.freshness == "live"      # relative to the window that was asked for


def test_a_window_whose_END_is_past_the_tape_is_SERVED_and_FLAGGED_not_refused(monkeypatch):
    """The half the first pass did not test, found by mutation (M31).

    A caller asking 2022-06-01..2026-01-01 gets bars that stop in 2023. That is
    not a mistake to refuse — an explicit window is the caller asking for
    history, and the ONE case the refusal exists for is a trailing window,
    where "give me the last 30 days" means "give me now". So the bars come back
    and the object says the tape stopped.

    Deleting `and not (start and end)` from the refusal survived every other
    test in this file, because they all asked for windows the tape covered.
    """
    _universe(monkeypatch, "TRX/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows",
                        lambda *a, **k: [_Bar(d) for d in _days(93, "2023-04-19")])
    bars = fetch_daily_bars("TRX/USD", start="2022-06-01", end="2026-01-01")
    assert bars.source == "alpaca-crypto" and len(bars.closes) == 93
    assert bars.freshness == "stale"
    assert "2023-04-19" in bars.freshness_note


def test_a_stale_verdict_from_the_venue_is_not_shopped_around_to_another_source(monkeypatch):
    """Finding a source willing to serve a dead tape is not a second opinion —
    it is a louder version of the same silence."""
    _universe(monkeypatch, "TRX/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows",
                        lambda *a, **k: [_Bar(d) for d in _days(50, "2023-04-19")])
    reached = []
    monkeypatch.setattr(md.urllib.request, "urlopen",
                        lambda *a, **k: reached.append(1) or _Resp(b"{}"))
    with pytest.raises(StaleSeries):
        fetch_daily_bars("TRX/USD", lookback_days=30)
    assert reached == []


# --- 9. what a non-venue crypto source is worth ---------------------------

def test_crypto_bars_from_a_non_venue_source_carry_the_namespace_caveat(monkeypatch):
    """MEASURED: `HYPE-USD` is Hyperliquid at Alpaca (~$82) and *Supreme
    Finance* at $5.4e-06 on Yahoo. Same six characters, two assets, both at
    HTTP 200."""
    _universe(monkeypatch, "HYPE/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows", lambda *a, **k: None)
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([5.4e-06] * 30, stamps,
               meta={"instrumentType": "CRYPTOCURRENCY",
                     "longName": "Supreme Finance USD"})))
    bars = fetch_daily_bars("HYPE-USD", lookback_days=30)
    assert bars.source == "yahoo"
    assert "on the venue's tradable list but these bars came from yahoo" in bars.identity_note
    assert "Supreme Finance USD" in bars.identity_note


def test_a_pair_absent_from_the_venues_list_says_there_is_nothing_to_check_against(monkeypatch):
    _universe(monkeypatch, "BTC/USD")
    monkeypatch.setattr(md, "_alpaca_crypto_rows", lambda *a, **k: None)
    stamps = [1_700_000_000 + i * 86400 for i in range(30)]
    monkeypatch.setattr(md.urllib.request, "urlopen", lambda *a, **k: _Resp(
        _yahoo([3.0] * 30, stamps, meta={"instrumentType": "CRYPTOCURRENCY",
                                         "longName": "Guarded Ether USD"})))
    bars = fetch_daily_bars("GETH-USD", lookback_days=30)
    assert "NOT on the venue's tradable list" in bars.identity_note
    assert "nothing here to check the identity against" in bars.identity_note


# --- 10. the equity path is not disturbed ---------------------------------

def test_the_equity_path_still_prefers_the_venue_and_still_refuses_junk(monkeypatch):
    _universe(monkeypatch, "BTC/USD")
    with pytest.raises(BarsError) as e:
        fetch_daily_bars("TOO-LONG-SYM")
    assert "Invalid symbol" in str(e.value)


# --------------------------------------------------------------------------
# bars_payload — the endpoint's ONE shape, and B1's unfinished half
# --------------------------------------------------------------------------

def test_the_live_basis_carries_the_identity_the_endpoint_used_to_DROP():
    """INCIDENT 2, ALL THE WAY TO THE WIRE.

    ``Bars`` has carried ``instrument_name``/``instrument_type``/``exchange``/
    ``identity_note`` since the GETH collision was measured. The endpoint
    built its response as a six-key dict literal and dropped every one of
    them, so the fix stopped one function short of the only reader that
    matters: *a caller asking for a bare GETH must SEE "Green EnviroTech
    Holdings Corp." rather than infer an identity from the string it typed.*
    """
    bars = md.Bars(
        symbol="GETH", closes=[1e-4, 1e-4], source="yahoo",
        dates=["2026-08-25", "2026-08-26"],
        instrument_name="Green EnviroTech Holdings Corp.",
        instrument_type="EQUITY", exchange="OTC Markets",
        identity_note="asked for GETH; the source served an EQUITY on OTC Markets",
        freshness="live", latest_bar_age_days=1.0,
        freshness_note="the newest bar is 2026-08-26, 1 day(s) before 2026-08-27")

    out = md.bars_payload(
        md.BASIS_LIVE, symbol=bars.symbol, source=bars.source,
        dates=bars.dates, closes=bars.closes, bars=bars)

    assert out["instrument_name"] == "Green EnviroTech Holdings Corp."
    assert out["instrument_type"] == "EQUITY"
    assert out["exchange"] == "OTC Markets"
    assert "EQUITY on OTC Markets" in out["identity_note"]
    assert out["freshness"] == "live"
    assert out["latest_bar_age_days"] == 1.0
    assert out["basis"] == md.BASIS_LIVE


def test_a_live_source_that_said_NOTHING_about_identity_reports_None():
    """The vendor's SILENCE is a real fact and it is reported as itself.

    This is the arm that must not be confused with the pinned/archive arms
    below: here the source was asked and answered nothing; there the path
    never records identity at all. Same ``None`` on ``instrument_name``,
    different ``identity_note``, and that note is the only thing separating
    them for a reader.
    """
    bars = md.Bars(symbol="SPY", closes=[1.0], source="yahoo",
                           dates=["2026-08-26"])
    out = md.bars_payload(
        md.BASIS_LIVE, symbol="SPY", source="yahoo",
        dates=["2026-08-26"], closes=[1.0], bars=bars)
    assert out["instrument_name"] is None
    assert out["identity_note"] is None
    assert out["basis"] == md.BASIS_LIVE


def test_the_pinned_and_archive_bases_SAY_they_never_recorded_an_identity():
    """ABSENCE AT THE SOURCE AND ABSENCE IN OUR OWN STORAGE ARE DIFFERENT
    FINDINGS WITH DIFFERENT FIXES.

    The belt's snapshot cache and the point-in-time archive both store dates,
    closes and a source string — nothing else. A consumer doing
    ``payload.get("instrument_name")`` on either would read ``None`` and
    conclude the vendor said nothing, which is false: the vendor was never
    asked to say anything that survived. The note says so, in words, on the
    payload.
    """
    for basis in (md.BASIS_PINNED, md.BASIS_ARCHIVE):
        out = md.bars_payload(
            basis, symbol="SPY", source="yahoo",
            dates=["2026-08-25", "2026-08-26"], closes=[1.0, 2.0])
        assert out["instrument_name"] is None, basis
        assert out["instrument_type"] is None, basis
        assert out["exchange"] is None, basis
        assert out["identity_note"] is not None, basis
        assert "never recorded" in out["identity_note"], basis
        assert "UNKNOWN" in out["identity_note"], basis
        assert out["basis"] == basis
    # And the two notes NAME their own path, so a reader knows which store to
    # go and fix. Identical sentences here would make the field decoration.
    pin = md.bars_payload(md.BASIS_PINNED, symbol="S",
                                  source="y", dates=["2026-08-26"], closes=[1.0])
    arc = md.bars_payload(md.BASIS_ARCHIVE, symbol="S",
                                  source="y", dates=["2026-08-26"], closes=[1.0])
    assert "pinned snapshot" in pin["identity_note"]
    assert "point-in-time archive" in arc["identity_note"]
    assert pin["identity_note"] != arc["identity_note"]


def test_every_basis_returns_the_SAME_KEY_SET():
    """THE SAFETY PROPERTY, ASSERTED DIRECTLY.

    Three return paths that used to be three dict literals; the comment on
    one of them asserted "same keys as the live branch below, so no consumer
    can tell the two apart by shape" and nothing checked it — which is how
    seven fields landed on one branch and none on the other two. The equality
    is now structural, and this is the test that says so.
    """
    bars = md.Bars(symbol="SPY", closes=[1.0], source="yahoo",
                           dates=["2026-08-26"], instrument_name="SPDR S&P 500")
    keys = {
        b: set(md.bars_payload(
            b, symbol="SPY", source="yahoo", dates=["2026-08-26"],
            closes=[1.0], bars=bars if b == md.BASIS_LIVE else None))
        for b in (md.BASIS_LIVE, md.BASIS_PINNED,
                  md.BASIS_ARCHIVE)
    }
    assert (keys[md.BASIS_LIVE] == keys[md.BASIS_PINNED]
            == keys[md.BASIS_ARCHIVE]), keys
    # ...and the set is the one the endpoint's consumers read.
    assert keys[md.BASIS_LIVE] == {
        "symbol", "source", "closes", "dates", "start", "end", "basis",
        "instrument_name", "instrument_type", "exchange", "identity_note",
        "freshness", "latest_bar_age_days", "freshness_note"}


def test_freshness_is_COMPUTED_on_the_non_live_bases_not_blanked():
    """The archive and the cache hold the dates, so how old the series is
    needs no vendor metadata. Blanking it would report "unreadable" for a
    question we can answer from what we already have."""
    pin = md.bars_payload(
        md.BASIS_PINNED, symbol="SPY", source="yahoo",
        dates=["2020-01-02", "2020-01-03"], closes=[1.0, 2.0])
    assert pin["freshness"] == "stale"
    assert pin["latest_bar_age_days"] is not None
    assert "2020-01-03" in pin["freshness_note"]

    # A point-in-time view is judged against ITS OWN end date. Bars from 2020
    # served under `as_of=2020-01-03` are exactly what was asked for; calling
    # them stale would put a warning on a correct answer.
    arc = md.bars_payload(
        md.BASIS_ARCHIVE, symbol="SPY", source="yahoo",
        dates=["2020-01-02", "2020-01-03"], closes=[1.0, 2.0])
    assert arc["freshness"] == "live"
    assert arc["latest_bar_age_days"] == 0.0


def test_an_EMPTY_series_is_unreadable_freshness_not_live():
    """Absence is never zero, and a series with no dates has an age nobody
    can read — not an age of nothing."""
    out = md.bars_payload(md.BASIS_PINNED, symbol="SPY",
                                  source="yahoo", dates=[], closes=[])
    assert out["freshness"] == "unreadable"
    assert out["latest_bar_age_days"] is None
    assert out["start"] is None and out["end"] is None
    assert "unknown, not current" in out["freshness_note"]


def test_an_unknown_basis_RAISES_rather_than_defaulting():
    """A typo must not fall through to a default that claims a live identity
    for an archived series — the one wrong answer this function exists to
    prevent, and the direction a default would fail in."""
    with pytest.raises(ValueError, match="unknown bars basis"):
        md.bars_payload("guess", symbol="SPY", source="y",
                                dates=["2026-08-26"], closes=[1.0])


def test_extra_keys_ride_ON_TOP_and_cannot_silently_drop_a_field():
    """``snapshot: True`` and the archive's own extras are additions, not
    replacements. The pinned branch's honest "where this came from" flag has
    to survive the move into the shared builder."""
    out = md.bars_payload(
        md.BASIS_PINNED, symbol="SPY", source="yahoo",
        dates=["2026-08-26"], closes=[1.0], extra={"snapshot": True})
    assert out["snapshot"] is True
    assert out["basis"] == md.BASIS_PINNED
    assert out["symbol"] == "SPY"
