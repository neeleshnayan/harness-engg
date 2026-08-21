"""EDGAR point-in-time, exhibits, and the crypto/equity namespace collision.

All three fixes come from the analyst's cycle-2 defects. All three were
RE-VERIFIED against the live API before being coded, and one of them refuted the
brief — see `test_the_acceptance_stamp_is_stored_as_UTC_without_a_shift`.
"""

import json
from datetime import datetime

import pytest

from app.fund import edgar, marketdata


# --- 1. the acceptance stamp ------------------------------------------------


def test_the_acceptance_stamp_is_stored_as_UTC_without_a_shift():
    """THE BRIEF WAS WRONG AND THIS IS THE GUARD.

    Dispatch 7's brief asserted acceptanceDateTime "carries a Z suffix but is ET
    = the stamp minus 4 hours" and asked for the shift on the way in. Two
    measurements against live EDGAR on 2026-08-21 refute it:

      * hour histogram (n=2,400): activity 10:00-02:00 with a DEAD ZONE at
        03:00-09:00 — precisely EDGAR's 06:00-22:00 ET window read as UTC. Under
        the ET reading, 43.6% of filings arrive while EDGAR is shut.
      * decisive (n=30,732): EDGAR dates a filing the NEXT business day after
        17:30 ET. The roll-over starts at raw hour 21, dominates at 22-23, and
        is ZERO at hours 10-20. 21:30 UTC is 17:30 EDT. Under the ET reading it
        would sit at raw hour 17, where 1,723 filings are same-day and none roll.
      * corroborating: the SRPT 8-K accepted at 20:06:23Z has index entries
        stamped `2026-08-05 16:06:23` — the same instant rendered in ET.

    Applying the -4h shift would have moved every stamp at hours 22-23 into the
    previous evening, MANUFACTURING the sub-daily lookahead the column exists to
    remove. If anyone re-proposes the shift, this test is the argument.
    """
    assert edgar._utc("2026-08-05T20:06:23.000Z") == "2026-08-05T20:06:23.000+00:00"
    parsed = datetime.fromisoformat(edgar._utc("2026-08-05T20:06:23.000Z"))
    assert parsed.utcoffset().total_seconds() == 0
    assert parsed.hour == 20, "the hour must not move"


def test_a_naive_stamp_is_never_produced():
    """A naive timestamp landing in a TIMESTAMPTZ column is read in the SERVER's
    zone — which is how a stamp silently moves by whatever the container is set
    to."""
    out = edgar._utc("2026-08-05T20:06:23.000Z")
    assert out.endswith("+00:00")
    assert datetime.fromisoformat(out).tzinfo is not None


def test_an_absent_stamp_stays_absent():
    for empty in (None, "", "   "):
        assert edgar._utc(empty) is None


# --- the parallel-array read ------------------------------------------------


def test_a_short_column_pads_rather_than_truncating_the_result():
    """`items` is absent on older feeds. A bare zip() would silently cut every
    filing after the shortest column."""
    rec = {"form": ["8-K", "10-Q", "10-K"], "items": ["2.02"]}
    assert edgar._col(rec, "items", 3) == ["2.02", None, None]
    assert edgar._col(rec, "missing", 3) == [None, None, None]


def _submissions(monkeypatch, rec):
    monkeypatch.setattr(edgar, "cik_for", lambda t: "0000873303")
    monkeypatch.setattr(edgar, "_throttled_get",
                        lambda url, timeout=60.0: json.dumps(
                            {"filings": {"recent": rec}}).encode())


def test_a_filing_carries_accepted_at_period_and_items(monkeypatch):
    _submissions(monkeypatch, {
        "form": ["8-K"], "filingDate": ["2026-08-05"],
        "accessionNumber": ["0001193125-26-335056"],
        "primaryDocument": ["srpt-20260805.htm"],
        "acceptanceDateTime": ["2026-08-05T20:06:23.000Z"],
        "reportDate": ["2026-08-05"], "items": ["2.02,9.01"],
    })
    f = edgar.recent_filings("SRPT", forms=["8-K"])[0]
    assert f.accepted_at == "2026-08-05T20:06:23.000+00:00"
    assert f.period == "2026-08-05"
    assert f.items == "2.02,9.01"
    assert edgar.ITEM_EARNINGS in f.items
    assert f.to_dict()["accepted_at"] == f.accepted_at


def test_a_feed_without_the_new_fields_yields_None_not_a_guess(monkeypatch):
    """An older feed must not have `filed` back-filled into `accepted_at` — that
    would invent a time of day and defeat the whole point."""
    _submissions(monkeypatch, {
        "form": ["10-Q"], "filingDate": ["2026-07-31"],
        "accessionNumber": ["x"], "primaryDocument": ["a.htm"],
    })
    f = edgar.recent_filings("AAPL", forms=["10-Q"])[0]
    assert f.accepted_at is None and f.period is None and f.items is None


# --- 2. the 8-K exhibit -----------------------------------------------------


def _index(monkeypatch, names):
    items = [{"name": n, "size": str(s)} for n, s in names]
    monkeypatch.setattr(edgar, "_throttled_get",
                        lambda url, timeout=60.0: json.dumps(
                            {"directory": {"item": items}}).encode())


def _filing(form="8-K"):
    return edgar.Filing("SRPT", "0000873303", form, "2026-08-05",
                        "0001193125-26-335056", "srpt-20260805.htm")


def test_the_exhibit_is_found_under_every_real_naming_convention(monkeypatch):
    """Measured in the wild: `srpt-ex99_1.htm` and the DFIN-style
    `d101719dex991.htm` both appear on real SRPT 8-Ks."""
    for name in ("srpt-ex99_1.htm", "d101719dex991.htm", "ex-99_1.htm",
                 "abc-ex99.1.htm", "EX991.HTM"):
        _index(monkeypatch, [("srpt-20260805.htm", 47594), (name, 887797)])
        got = edgar.exhibit_url(_filing())
        assert got["is_exhibit"] is True, name
        assert got["document"] == name


def test_exhibit_99_10_is_NOT_mistaken_for_99_1(monkeypatch):
    """An exhibit-numbering collision would attach the wrong document to an
    earnings read and nothing downstream would notice."""
    _index(monkeypatch, [("srpt-ex99_10.htm", 900000),
                         ("srpt-ex99_11.htm", 900000)])
    got = edgar.exhibit_url(_filing())
    assert got["is_exhibit"] is False
    assert "no EX-99.1" in got["reason"]


def test_the_largest_candidate_wins(monkeypatch):
    """Filers occasionally ship a stub beside the real exhibit."""
    _index(monkeypatch, [("a-ex99_1.htm", 500), ("b-ex99_1.htm", 887797)])
    assert edgar.exhibit_url(_filing())["document"] == "b-ex99_1.htm"


def test_no_exhibit_falls_back_to_the_primary_AND_SAYS_SO(monkeypatch):
    """The fallback is the point: a zero-yield read must be attributable to the
    filing rather than to us having read the cover page."""
    _index(monkeypatch, [("srpt-20260805.htm", 47594)])
    got = edgar.exhibit_url(_filing())
    assert got["is_exhibit"] is False
    assert got["document"] == "srpt-20260805.htm"
    assert "primary document" in got["reason"]


def test_an_unreadable_index_degrades_rather_than_raising(monkeypatch):
    def boom(url, timeout=60.0):
        raise OSError("network down")
    monkeypatch.setattr(edgar, "_throttled_get", boom)
    got = edgar.exhibit_url(_filing())
    assert got["is_exhibit"] is False
    assert "could not be read" in got["reason"]
    assert got["url"] == _filing().url


def test_only_readable_document_types_are_considered(monkeypatch):
    _index(monkeypatch, [("srpt-ex99_1.zip", 999999), ("srpt-ex99_1.htm", 100)])
    assert edgar.exhibit_url(_filing())["document"] == "srpt-ex99_1.htm"


def test_a_10Q_is_not_sent_looking_for_an_exhibit(monkeypatch):
    """Only 8-Ks bury their content in EX-99.1. A 10-Q's primary document IS
    the filing, and an index fetch per 10-Q would be a request for nothing."""
    calls = []
    monkeypatch.setattr(edgar, "_throttled_get",
                        lambda url, timeout=60.0: calls.append(url) or b"<html>x</html>")
    edgar.document_text(_filing("10-Q"), focus=False)
    assert not any("index.json" in u for u in calls)


# --- 3. the crypto / equity namespace collision -----------------------------


def test_a_bare_ticker_with_an_EDGAR_CIK_is_NOT_priced_as_crypto(monkeypatch):
    """MEASURED: BTC in the equity namespace is CIK 0002015034, Grayscale
    Bitcoin Mini Trust ETF — tens of dollars. CoinGecko was pricing it as
    bitcoin spot at tens of thousands: a ~1000x error in any exposure or
    drawdown that touched it."""
    monkeypatch.setattr(marketdata, "_has_edgar_cik", lambda b: b in ("BTC", "ETH"))
    assert marketdata._crypto_id("BTC") is None
    assert marketdata._crypto_id("ETH") is None


def test_an_EXPLICIT_pair_still_routes_to_crypto(monkeypatch):
    """The ambiguity is only in the BARE ticker. `BTC-USD` is the caller saying
    crypto, and it must keep working."""
    monkeypatch.setattr(marketdata, "_has_edgar_cik", lambda b: True)
    assert marketdata._crypto_id("BTC-USD") == "bitcoin"
    assert marketdata._crypto_id("BTC/USDT") == "bitcoin"
    assert marketdata._crypto_id("eth-usd") == "ethereum"


def test_a_coin_with_no_equity_listing_is_unaffected(monkeypatch):
    monkeypatch.setattr(marketdata, "_has_edgar_cik", lambda b: False)
    assert marketdata._crypto_id("SOL") == "solana"
    assert marketdata._crypto_id("DOGE") == "dogecoin"


def test_a_lookup_failure_degrades_to_the_OLD_behaviour(monkeypatch):
    """A network problem must not blank crypto pricing entirely."""
    def boom(b):
        raise OSError("no network")
    monkeypatch.setattr(marketdata, "_has_edgar_cik", boom)
    with pytest.raises(OSError):
        marketdata._crypto_id("BTC")
    # And the real helper swallows it:
    monkeypatch.undo()
    monkeypatch.setattr("app.fund.edgar.cik_for",
                        lambda t: (_ for _ in ()).throw(OSError("no network")))
    assert marketdata._has_edgar_cik("BTC") is False


def test_a_non_crypto_symbol_is_never_routed_to_coingecko():
    assert marketdata._crypto_id("SPY") is None
    assert marketdata._crypto_id("") is None
