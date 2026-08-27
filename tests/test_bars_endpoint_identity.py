"""THE ROUTE, not the module — B1's identity fields all the way to the wire.

`tests/test_marketdata_crypto.py` proves `bars_payload` returns the identity
block. That is necessary and it is NOT the claim: the defect this file exists
for was a correct function whose CALLER built its own dict literal. Eight
green tests on `bars_payload` would say nothing about a route that still
returned six keys.

So every test here calls the ROUTE HANDLER, through the real app, with the
vendor mocked at the boundary the handler actually crosses.

THE INCIDENT, measured 2026-08-27 against the running spine:

    GET /fund/marketdata/bars?symbol=GETH&lookback_days=5
    -> 200 {"symbol":"GETH","source":"yahoo","closes":[1e-04,...],
            "dates":[...],"start":"2026-08-20","end":"2026-08-26"}

Real daily bars for *Green EnviroTech Holdings Corp.*, an OTC penny stock at
$0.0001, served under a ticker a crypto caller meant as a token — with the
resolved instrument known to `fetch_daily_bars` and absent from every byte
the caller received.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import fund as fundapi
from app.fund import marketdata as md


GETH = md.Bars(
    symbol="GETH", closes=[1e-4, 1e-4], source="yahoo",
    dates=["2026-08-25", "2026-08-26"], start="2026-08-25", end="2026-08-26",
    instrument_name="Green EnviroTech Holdings Corp.",
    instrument_type="EQUITY", exchange="OTC Markets",
    identity_note=("asked for GETH; the source served an EQUITY named "
                   "'Green EnviroTech Holdings Corp.' on OTC Markets"),
    freshness="live", latest_bar_age_days=1.0,
    freshness_note="the newest bar is 2026-08-26, 1 day(s) before 2026-08-27")


@pytest.fixture()
def client(monkeypatch):
    """The route, with the vendor and the archive both stubbed.

    `_barstore` is stubbed to None rather than left alone because a Postgres
    archive present in the environment would take the `as_of` branch and,
    worse, would make the live branch's write attempt a network call. The
    stub makes the arm under test the arm that runs.
    """
    monkeypatch.setattr(fundapi, "fetch_daily_bars", lambda *a, **k: GETH)
    monkeypatch.setattr(fundapi, "_barstore", lambda: None)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    return TestClient(app)


def test_the_route_serves_the_instrument_the_source_actually_resolved(client):
    """THE GETH INCIDENT, CLOSED AT THE WIRE."""
    r = client.get("/api/v1/fund/marketdata/bars",
                   params={"symbol": "GETH", "lookback_days": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["instrument_name"] == "Green EnviroTech Holdings Corp."
    assert body["instrument_type"] == "EQUITY"
    assert body["exchange"] == "OTC Markets"
    assert "Green EnviroTech" in body["identity_note"]
    assert body["freshness"] == "live"
    assert body["latest_bar_age_days"] == 1.0
    assert body["freshness_note"]
    # WHICH PATH SERVED IT. A reader who cannot tell a live fetch from a
    # pinned leg cannot interpret the freshness beside it either.
    assert body["basis"] == md.BASIS_LIVE


def test_the_route_did_not_lose_a_single_key_it_used_to_serve(client):
    """ADDITIVE, and this is what makes the word mean something.

    Every consumer of this endpoint — LEAN containers, offline scripts, the
    belt — reads the six original keys. The rewrite moved the construction
    into a shared builder; it must not have moved a value.
    """
    body = client.get("/api/v1/fund/marketdata/bars",
                      params={"symbol": "GETH", "lookback_days": 5}).json()
    assert body["symbol"] == "GETH"
    assert body["source"] == "yahoo"
    assert body["closes"] == [1e-4, 1e-4]
    assert body["dates"] == ["2026-08-25", "2026-08-26"]
    # start/end are the FETCHER's own bounds, deliberately overriding the
    # dates-derived pair: a source may report a window wider than the bars it
    # returned, and this branch's numbers do not move.
    assert body["start"] == "2026-08-25"
    assert body["end"] == "2026-08-26"


def test_the_csv_format_is_untouched_by_the_identity_block(client):
    """LEAN's remote-file reader iterates LINES as data points, so a stray
    header or a JSON blob on this path costs a backtest its history. The
    identity fields are a JSON-only addition and this asserts it."""
    r = client.get("/api/v1/fund/marketdata/bars",
                   params={"symbol": "GETH", "lookback_days": 5,
                           "format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert r.text == "2026-08-25,0.0001\n2026-08-26,0.0001"
    assert "instrument_name" not in r.text


def test_a_source_that_named_nothing_serves_the_keys_with_None(client,
                                                               monkeypatch):
    """The KEY SET does not depend on what the vendor said.

    A consumer doing `body["instrument_name"]` must not raise on a symbol
    whose source volunteered no name — absence is a value here, not a missing
    key, and the two are different bugs at the call site.
    """
    plain = md.Bars(symbol="SPY", closes=[1.0], source="yahoo",
                    dates=["2026-08-26"], start="2026-08-26", end="2026-08-26")
    monkeypatch.setattr(fundapi, "fetch_daily_bars", lambda *a, **k: plain)
    body = client.get("/api/v1/fund/marketdata/bars",
                      params={"symbol": "SPY"}).json()
    for key in ("instrument_name", "instrument_type", "exchange",
                "identity_note", "freshness", "latest_bar_age_days",
                "freshness_note"):
        assert key in body, key
        assert body[key] is None, key


def test_the_pinned_branch_serves_the_SAME_KEYS_as_the_live_one(client,
                                                                monkeypatch):
    """THE COMMENT THAT WAS NEVER CHECKED, NOW CHECKED.

    The pinned branch carried *"Same keys as the live branch below, so no
    consumer can tell the two apart by shape"* — and when seven fields landed
    on the live branch the sentence quietly became false. Both branches now
    build from one function, and this is the assertion that keeps them equal.
    """
    from app.fund import barcache
    leg = barcache.SnapshotLeg(symbol="GETH", dates=["2026-08-25", "2026-08-26"],
                               closes=[1e-4, 1e-4], source="yahoo")
    monkeypatch.setattr(fundapi.barcache, "serve", lambda *a, **k: leg)

    pinned = client.get("/api/v1/fund/marketdata/bars",
                        params={"symbol": "GETH", "lookback_days": 5}).json()
    monkeypatch.setattr(fundapi.barcache, "serve", lambda *a, **k: None)
    live = client.get("/api/v1/fund/marketdata/bars",
                      params={"symbol": "GETH", "lookback_days": 5}).json()

    assert set(pinned) - {"snapshot"} == set(live)
    assert pinned["snapshot"] is True
    assert pinned["basis"] == md.BASIS_PINNED
    # AND THE PINNED ROW DOES NOT CLAIM AN IDENTITY IT NEVER HELD. The cache
    # stores dates and closes; a `None` here without the note would read as
    # "the vendor said nothing", which is a different and false finding.
    assert pinned["instrument_name"] is None
    assert "never recorded" in pinned["identity_note"]
    assert live["instrument_name"] == "Green EnviroTech Holdings Corp."
