"""Offline tests for the free bars provider (no network)."""

import json

import pytest

from app.fund import marketdata
from app.fund.marketdata import BarsError, fetch_daily_bars


class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _yahoo_payload(closes, stamps, error=None):
    if error:
        body = {"chart": {"result": None, "error": {"description": error}}}
    else:
        body = {"chart": {"result": [{
            "timestamp": stamps,
            "indicators": {"quote": [{"close": closes}]},
        }], "error": None}}
    return json.dumps(body).encode()


def _patch_urlopen(monkeypatch, payload):
    monkeypatch.setattr(marketdata.urllib.request, "urlopen", lambda *a, **k: _FakeResp(payload))
    # No Alpaca keys → Yahoo path.
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)


def test_parses_closes_and_dates(monkeypatch):
    stamps = [1_700_000_000 + i * 86400 for i in range(4)]
    _patch_urlopen(monkeypatch, _yahoo_payload([100.0, 101.5, 103.0, 102.0], stamps))
    bars = fetch_daily_bars("AAPL", lookback_days=365)
    assert bars.source == "yahoo"
    assert bars.closes == [100.0, 101.5, 103.0, 102.0]
    assert len(bars.dates) == 4 and bars.start and bars.end


def test_filters_null_closes(monkeypatch):
    stamps = [1_700_000_000 + i * 86400 for i in range(4)]
    _patch_urlopen(monkeypatch, _yahoo_payload([100.0, None, 103.0, None], stamps))
    bars = fetch_daily_bars("AAPL")
    assert bars.closes == [100.0, 103.0]
    assert len(bars.dates) == 2


def test_unknown_symbol_raises(monkeypatch):
    _patch_urlopen(monkeypatch, _yahoo_payload(None, None, error="No data found, symbol may be delisted"))
    with pytest.raises(BarsError):
        fetch_daily_bars("ZZZQQ")


def test_too_few_bars_raises(monkeypatch):
    _patch_urlopen(monkeypatch, _yahoo_payload([100.0], [1_700_000_000]))
    with pytest.raises(BarsError):
        fetch_daily_bars("AAPL")


def test_invalid_symbol_rejected(monkeypatch):
    """THIS FILE SAYS "no network" AT THE TOP AND THIS TEST DID NOT ENFORCE IT.

    Its four siblings all go through `_patch_urlopen`, which deletes the Alpaca
    credentials; this one took a `monkeypatch` fixture and never used it. That
    was harmless while routing was a dictionary lookup, and stopped being
    harmless when routing gained a venue read: with real credentials in the
    ambient environment — which `app/main.py`'s `load_dotenv()` puts there —
    the refusal path could reach live Alpaca before refusing. Found by the
    Gauntlet, by execution.

    The assertion is unchanged; what is added is the proof that reaching it
    costs nothing.
    """
    monkeypatch.delenv("ALPACA_API_KEY", raising=False)
    monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
    reached = []
    monkeypatch.setattr(marketdata.urllib.request, "urlopen",
                        lambda *a, **k: reached.append(1) or _FakeResp(b"{}"))
    with pytest.raises(BarsError):
        fetch_daily_bars("TOO-LONG-SYM")
    assert reached == [], "an invalid symbol reached the network before refusing"
