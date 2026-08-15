"""The second price source: fallback and disagreement, measured not assumed.

One feed was a single point of failure for every mark in NAV. These tests pin
the three behaviours that matter: primary wins when both answer, the fallback
carries the mark when the primary dies, and a wide disagreement is RECORDED
rather than silently averaged away.
"""

import pytest

from app.fund import marketdata as md


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    monkeypatch.setattr(md, "_QUOTE_CACHE", {})
    monkeypatch.setattr(md, "_CROSS_CHECK", {})


class _Bars:
    def __init__(self, close):
        self.closes = [close]


def test_primary_wins_when_both_answer(monkeypatch):
    monkeypatch.setattr(md, "_from_yahoo", lambda s, lookback_days: _Bars(101.00))
    monkeypatch.setattr(md, "_from_stooq_quote", lambda s: 101.02)
    assert md.live_price("GLD") == 101.00
    # Agreement is recorded too — "we checked" is information.
    cc = md.cross_checks()["GLD"]
    assert cc["primary"] == 101.00 and cc["secondary"] == 101.02
    assert cc["divergence_bps"] < md.CROSS_SOURCE_WARN_BPS


def test_fallback_carries_the_mark_when_primary_dies(monkeypatch):
    def dead(*a, **k):
        raise md.BarsError("yahoo down")
    monkeypatch.setattr(md, "_from_yahoo", dead)
    monkeypatch.setattr(md, "_from_stooq_quote", lambda s: 99.50)
    assert md.live_price("SPY") == 99.50


def test_both_dead_is_none_not_zero(monkeypatch):
    def dead(*a, **k):
        raise md.BarsError("down")
    monkeypatch.setattr(md, "_from_yahoo", dead)
    monkeypatch.setattr(md, "_from_stooq_quote", lambda s: None)
    assert md.live_price("MSFT") is None


def test_wide_disagreement_is_recorded_and_primary_still_used(monkeypatch, caplog):
    monkeypatch.setattr(md, "_from_yahoo", lambda s, lookback_days: _Bars(100.00))
    monkeypatch.setattr(md, "_from_stooq_quote", lambda s: 102.00)  # 200 bps apart
    with caplog.at_level("WARNING"):
        px = md.live_price("INTC")
    assert px == 100.00, "disagreement must not silently switch or average sources"
    assert md.cross_checks()["INTC"]["divergence_bps"] == pytest.approx(200.0)
    assert any("cross-check" in r.message for r in caplog.records)


def test_cache_prevents_repeat_fetches(monkeypatch):
    calls = {"n": 0}
    def once(s, lookback_days):
        calls["n"] += 1
        return _Bars(50.0)
    monkeypatch.setattr(md, "_from_yahoo", once)
    monkeypatch.setattr(md, "_from_stooq_quote", lambda s: 50.0)
    md.live_price("SOFI"); md.live_price("SOFI")
    assert calls["n"] == 1


def _fake_urlopen(csv_text):
    import contextlib, io as _io
    @contextlib.contextmanager
    def opener(url, timeout=None):
        yield _io.BytesIO(csv_text.encode("utf-8"))
    return opener


def test_stooq_parses_a_real_row(monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        "GLD.US,2026-08-15,22:00:00,400.1,402.3,399.8,401.53,1200000\n"))
    assert md._from_stooq_quote("GLD") == 401.53


def test_stooq_rejects_nd_and_zero(monkeypatch):
    import urllib.request
    # Unknown tickers come back as N/D; a zero close would zero a position.
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        "XXXX.US,N/D,N/D,N/D,N/D,N/D,N/D,N/D\n"))
    assert md._from_stooq_quote("XXXX") is None
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen(
        "Symbol,Date,Time,Open,High,Low,Close,Volume\n"
        "YYYY.US,2026-08-15,22:00:00,0,0,0,0,0\n"))
    assert md._from_stooq_quote("YYYY") is None
