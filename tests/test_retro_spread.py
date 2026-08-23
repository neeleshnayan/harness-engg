"""The retro reader — the half of the instrument that reads a real market.

THIS FILE EXISTS BECAUSE THE GAUNTLET FOUND THE SCRIPT HAD NONE. Five hundred
lines producing the fund's only quote-based execution-cost number, and no test
touched it; in particular its own central refusal — declining to print a
coverage percentage when the log was read over a capped HTTP page — was
implemented correctly and guarded by nothing.

No network and no database anywhere here: the vendor is injected, the log is a
list of dicts in the real measured shape.
"""

from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone

import pytest

from app.fund.executionquality import MARK_BASIS, RETRO_BASIS, RETRO_FEED
from execution import retro_spread as rs

NOW = datetime(2026, 8, 23, 20, 0, 0, tzinfo=timezone.utc)


def ev(seq, oid, type_, payload, ts, aggregate_type="order"):
    return {"seq": seq, "aggregate_id": oid, "aggregate_type": aggregate_type,
            "type": type_, "actor": "test", "ts": ts, "payload": payload}


def one_order(ts="2026-08-14T13:30:03+00:00", venue="alpaca",
              arrival=778.30, fill="778.58"):
    return [
        ev(1, "o1", "OrderProposed",
           {"qty": 1.0, "side": "buy", "venue": venue, "symbol": "SPY"}, ts),
        ev(2, "o1", "OrderSubmitted",
           {"venue": venue, "venue_ref": "r", "arrival_price": arrival}, ts),
        ev(3, "o1", "OrderFilled",
           {"fees": "0", "side": "buy", "symbol": "SPY", "avg_price": fill,
            "filled_qty": "1.0", "strategy_id": "s"}, ts),
    ]


class FakeSip:
    """The consolidated tape, injected. ``quotes`` maps symbol -> dict."""

    def __init__(self, quotes=None, raises=None):
        self.quotes = quotes or {}
        self.raises = raises
        self.calls = []

    def in_force(self, symbol, at, lookback_s=rs.QUOTE_LOOKBACK_S):
        self.calls.append((symbol, at, lookback_s))
        if self.raises is not None:
            raise self.raises
        return self.quotes.get(symbol)


SPY_QUOTE = {"bid": 778.39, "ask": 778.41, "bid_size": 100, "ask_size": 100,
             "quote_ts": "2026-08-14T13:30:02.900000+00:00",
             "bid_exchange": "P", "ask_exchange": "N"}

SOURCE_FULL = {"source": "postgres:fund_events", "events_in_log": 1254,
               "order_events_read": 3, "truncated": False}
SOURCE_CUT = {"source": "http:x", "events_in_log": None, "page_returned": 1000,
              "page_cap": 1000, "order_events_read": 3, "truncated": True}


# --- the refusal the Gauntlet found untested ------------------------------

def test_a_truncated_read_refuses_to_report_coverage_at_all():
    """A COVERAGE PERCENTAGE OFF A CAPPED READ DESCRIBES THE PAGE, NOT THE FUND.

    ``/fund/events`` serves at most a thousand rows and offers no way to page
    backwards, so an HTTP read cannot see the head of the log. Reporting
    "91% of fills measured" from it would silently mean "91% of the fills in
    the newest page", and the figure would IMPROVE as the fund forgot its own
    history. The honest answer is no answer.

    ``coverage is None`` is the refusal; ``readable: False`` would be wrong
    here, because it is not the store that could not be read.
    """
    report = rs.build_report(one_order(), SOURCE_CUT)
    assert report["coverage"] is None
    # And the mark table IS still produced: what can be said is still said.
    assert report["mark"]["summary"]["fills"] == 1


def test_an_uncapped_read_does_report_coverage():
    """The other side of the same boundary — otherwise the test above passes
    on a function that never reports coverage at all."""
    report = rs.build_report(one_order(), SOURCE_FULL)
    cov = report["coverage"]
    assert cov is not None and cov["readable"] is True
    assert cov["fill_events_total"] == 1
    assert cov["measured"] == 0 and cov["uncaptured"] == 1
    assert cov["pct_measured"] == 0.0


def test_the_renderer_says_REFUSED_rather_than_printing_nothing():
    """An absent coverage block must be VISIBLY absent in the printed table.

    A section that simply does not appear reads as "there was nothing to
    report", which is the opposite of what a refusal means.
    """
    out = io.StringIO()
    rs.render(rs.build_report(one_order(), SOURCE_CUT), out=out)
    text = out.getvalue()
    assert "REFUSED" in text
    assert "truncated=True" in text


# --- the vendor's delay boundary ------------------------------------------

def test_an_event_inside_the_consolidated_delay_is_refused_not_fetched():
    """The subscription does not serve consolidated data for recent events, so
    asking is a guaranteed error. The row says which rule refused it and the
    vendor is never called — a refusal that still burns a network round trip
    would turn a known limit into an intermittent one."""
    recent = (NOW - timedelta(minutes=5)).isoformat()
    sip = FakeSip({"SPY": SPY_QUOTE})
    rows = rs.quote_rows_for(one_order(ts=recent), sip, run_id="r", now=NOW)
    assert len(rows) == 1
    assert rows[0]["mid"] is None
    assert rows[0]["quote_absent_reason"].startswith("within_sip_delay:")
    assert str(rs.MEASURED_SIP_DELAY_MINUTES) in rows[0]["quote_absent_reason"]
    assert sip.calls == [], "the vendor was called for data it will not serve"


@pytest.mark.parametrize("minutes_ago, served", [
    (rs.MEASURED_SIP_DELAY_MINUTES - 1, False),
    (rs.MEASURED_SIP_DELAY_MINUTES, False),
    (rs.MEASURED_SIP_DELAY_MINUTES + 1, True),
])
def test_the_delay_cutoff_is_probed_at_its_own_boundary(minutes_ago, served):
    """Strictly inside, exactly at, strictly outside.

    The cutoff is NON-STRICT (``at >= now - delay`` refuses), and the exact
    boundary is a deliberate choice rather than a measurement: the vendor probe
    observed 14 minutes refused and 16 minutes served and never observed 15:00
    itself. Refusing there costs one recoverable absence row; attempting there
    would record a vendor error as if the market had had no quote.

    A test probing only five minutes and an hour could not tell ``>`` from
    ``>=`` and this choice would drift on the next edit.
    """
    ts = (NOW - timedelta(minutes=minutes_ago)).isoformat()
    sip = FakeSip({"SPY": SPY_QUOTE})
    row = rs.quote_rows_for(one_order(ts=ts), sip, run_id="r", now=NOW)[0]
    assert (row["mid"] is not None) is served


# --- the quote row --------------------------------------------------------

def test_a_quoted_fill_carries_the_consolidated_basis_and_its_feed():
    """The retro rows must be distinguishable from the live IEX rows by their
    own columns, or a reader averaging by feed averages two markets."""
    sip = FakeSip({"SPY": SPY_QUOTE})
    row = rs.quote_rows_for(one_order(), sip, run_id="r", now=NOW)[0]
    assert row["basis"] == RETRO_BASIS
    assert row["feed"] == RETRO_FEED
    assert row["quote_ts"] == SPY_QUOTE["quote_ts"]
    assert row["mid"] == pytest.approx((778.39 + 778.41) / 2)
    assert row["effective_spread_bps"] == pytest.approx(
        2 * abs(778.58 - 778.40) / 778.40 * 10_000)
    assert row["stored"] is False


@pytest.mark.parametrize("vendor, expect_prefix", [
    (FakeSip({}), "no_consolidated_quote_within_"),
    (FakeSip(raises=TimeoutError("slow")), "quote_fetch_failed:TimeoutError"),
])
def test_every_unquotable_fill_gets_a_row_that_says_why(vendor, expect_prefix):
    """AN UNMEASURED FILL MUST BE VISIBLY UNMEASURED.

    A fill that produced no row and a fill measured at zero cost look the same
    in every average anyone computes later, so there is no path here that
    returns without a row.
    """
    rows = rs.quote_rows_for(one_order(), vendor, run_id="r", now=NOW)
    assert len(rows) == 1
    assert rows[0]["mid"] is None
    assert rows[0]["effective_spread_bps"] is None
    assert rows[0]["quote_absent_reason"].startswith(expect_prefix)


def test_a_fill_whose_order_names_no_symbol_is_refused_before_the_vendor():
    """Nothing can be quoted without a symbol, and asking the vendor for None
    is a different error message about the same fact."""
    events = [ev(3, "o1", "OrderFilled",
                 {"fees": "0", "avg_price": "10.0", "filled_qty": "1.0"},
                 "2026-08-14T13:30:03+00:00")]
    sip = FakeSip({"SPY": SPY_QUOTE})
    row = rs.quote_rows_for(events, sip, run_id="r", now=NOW)[0]
    assert row["quote_absent_reason"].startswith("symbol_unknown:")
    assert sip.calls == []


# --- the two tables never merge -------------------------------------------

def test_the_mark_table_is_never_written_to_the_quote_store():
    """THE STRUCTURAL SEPARATION, asserted rather than promised.

    An arrival mark is not a midpoint; a shortfall against it is not an
    effective spread. ``MARK_BASIS`` is deliberately not a value the quote
    table's basis CHECK will accept, so the two cannot be conflated even by a
    caller who tries.
    """
    from app.fund.executionquality import BASES
    assert MARK_BASIS not in BASES
    report = rs.build_report(one_order(), SOURCE_FULL)
    assert all(r["basis"] == MARK_BASIS for r in report["mark"]["rows"])
    assert report["mark"]["summary"]["basis"] == MARK_BASIS


def test_build_report_does_not_touch_the_vendor_unless_asked():
    """``--quotes`` is opt-in: the default read is a pure fold of the log, so
    the report runs with no credentials and no network."""
    report = rs.build_report(one_order(), SOURCE_FULL)
    assert report["quote"] is None
    out = io.StringIO()
    rs.render(report, out=out)
    assert "TABLE 2 - not run" in out.getvalue()


# --- the census -----------------------------------------------------------

def test_the_census_names_what_the_instrument_ignores():
    """Counting only the types it reads would make the instrument look
    complete. The census reports the ignored types by name so a new order
    event type is visible as unread rather than invisible."""
    events = one_order() + [
        ev(4, "o2", "OrderDeclined", {"reason": "expired"}, "2026-08-14T00:00:00+00:00"),
        ev(5, "o3", "OrderRejected", {"symbol": "NVDA", "breaches": []}, "2026-08-14T00:00:00+00:00"),
    ]
    c = rs.census(events)
    assert c["order_event_types"]["OrderFilled"] == 1
    assert set(c["read_by_this_instrument"]) == {
        "OrderSubmitted", "OrderPartiallyFilled", "OrderFilled"}
    assert set(c["ignored"]) == {"OrderProposed", "OrderDeclined",
                                 "OrderRejected"}


def test_the_census_counts_are_ordered_by_frequency_not_by_name():
    """The table is read by a human looking for the big numbers first."""
    events = one_order() + one_order()
    for i, e in enumerate(events):
        e["seq"] = i + 1
    counts = list(rs.census(events)["order_event_types"].values())
    assert counts == sorted(counts, reverse=True)


# --- the HTTP path is honest about its cap --------------------------------

def test_the_http_reader_reports_its_own_cap_as_truncation(monkeypatch):
    """A page that came back FULL may have been cut; the reader says so, and
    ``build_report`` then refuses coverage. Tested through the real function
    with only the socket replaced."""
    import json as _json

    class Resp:
        def __init__(self, payload):
            self._b = _json.dumps(payload).encode()

        def read(self):
            return self._b

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    full = [ev(i + 1, f"o{i}", "OrderFilled",
               {"symbol": "SPY", "avg_price": "1.0", "filled_qty": "1.0",
                "side": "buy"}, "2026-08-14T13:30:03+00:00")
            for i in range(1000)]
    monkeypatch.setattr(rs.__dict__["urllib"] if "urllib" in rs.__dict__
                        else __import__("urllib.request",
                                        fromlist=["request"]),
                        "urlopen", lambda url, timeout=20: Resp({"events": full}))
    _, source = rs.read_events_from_spine("http://x")
    assert source["truncated"] is True
    assert source["page_cap"] == 1000
    assert source["events_in_log"] is None, (
        "the HTTP path cannot know the log's size and must not guess it")


# --- SipQuotes.in_force itself --------------------------------------------
#
# Added after mutation: every test above injects a FakeSip, so the real
# selection rule inside SipQuotes.in_force was exercised by nothing and a
# mutant that let a POST-TRADE quote into the cost denominator survived.
# Only the SDK client is faked here; the selection logic is the real one.

class _Q:
    def __init__(self, ts, bid, ask):
        self.timestamp = ts
        self.bid_price, self.ask_price = bid, ask
        self.bid_size = self.ask_size = 100
        self.bid_exchange, self.ask_exchange = "P", "N"


class _Page:
    def __init__(self, rows):
        self.data = {"SPY": rows}


class _Client:
    def __init__(self, rows):
        self.rows = rows
        self.requests = []

    def get_stock_quotes(self, req):
        self.requests.append(req)
        return _Page(self.rows)


def _sip(rows):
    s = rs.SipQuotes(key="k", secret="s")
    s._client = _Client(rows)
    return s


AT = datetime(2026, 8, 14, 13, 30, 3, tzinfo=timezone.utc)


def test_the_quote_in_force_is_the_last_one_BEFORE_the_fill():
    """A QUOTE PRINTED AFTER THE FILL DID NOT GOVERN IT.

    Picking the NEAREST quote instead of the last preceding one lets a
    post-trade print become the midpoint a cost is measured against — and the
    quote right after a trade is exactly the one the trade moved, so the error
    is not random. It biases every measured spread toward zero.

    The vendor page here is deliberately ordered so the nearest quote in TIME
    is the one 10ms AFTER the fill; the correct answer is the one 100ms before.
    """
    rows = [
        _Q(AT - timedelta(milliseconds=900), 100.00, 100.10),
        _Q(AT - timedelta(milliseconds=100), 100.02, 100.12),   # <- in force
        _Q(AT + timedelta(milliseconds=10), 100.50, 100.60),    # after
    ]
    got = _sip(rows).in_force("SPY", AT)
    assert got["bid"] == 100.02 and got["ask"] == 100.12


def test_a_quote_exactly_at_the_fill_timestamp_counts_as_in_force():
    """The boundary: ``ts > at`` is excluded, so ``ts == at`` is kept. A quote
    stamped at the same instant is the one the print happened against."""
    rows = [_Q(AT - timedelta(seconds=1), 99.0, 99.1), _Q(AT, 100.0, 100.1)]
    got = _sip(rows).in_force("SPY", AT)
    assert got["bid"] == 100.0


def test_a_page_of_only_later_quotes_returns_nothing_rather_than_the_nearest():
    """None, not the closest available. An absent quote is reported absent by
    the caller; a fabricated one is unrecoverable."""
    rows = [_Q(AT + timedelta(milliseconds=1), 100.0, 100.1),
            _Q(AT + timedelta(seconds=1), 101.0, 101.1)]
    assert _sip(rows).in_force("SPY", AT) is None


def test_an_empty_page_returns_none():
    """No quotes in the window at all — the 2026-08-21 06:51Z fills, which
    were submitted outside regular hours when no consolidated quote exists."""
    assert _sip([]).in_force("SPY", AT) is None


def test_in_force_asks_only_for_the_window_it_will_use():
    """The request must be bounded by the lookback, not open-ended: a wide
    window returns a quote from a different market state and the selection
    rule would happily pick it."""
    s = _sip([_Q(AT, 100.0, 100.1)])
    s.in_force("SPY", AT, lookback_s=2.0)
    req = s._client.requests[0]
    # MEASURED SDK FACT: StockQuotesRequest normalises start/end to NAIVE
    # datetimes, dropping the tzinfo it was handed. Compare in one frame rather
    # than loosening the assertion until it passes.
    def naive(d):
        return d.replace(tzinfo=None) if d.tzinfo else d
    assert naive(req.start) == naive(AT) - timedelta(seconds=2.0)
    assert timedelta(0) <= naive(req.end) - naive(AT) <= timedelta(seconds=1)


# --- the two-stores flag split (found by the first real --store run) -------

def test_the_event_log_dsn_and_the_quote_store_dsn_are_separate_flags():
    """ONE FLAG NAMING TWO DATABASES CAN ONLY EVER BE HALF RIGHT.

    ``--dsn`` used to feed both the ``fund_events`` reader and the
    ``fund_execution_quotes`` writer. The first real ``--store`` run pointed
    the writer at a scratch database and died on
    ``relation "fund_events" does not exist`` — the reader had followed it.

    Asserted on the parser rather than on prose: the two options exist, and
    ``--store-dsn`` defaults to None so the single-database case still works
    with one flag.
    """
    p = rs.build_parser()
    both = p.parse_args(["--quotes", "--store", "--run-id", "r",
                         "--dsn", "postgresql://a/log",
                         "--store-dsn", "postgresql://b/quotes"])
    assert both.dsn == "postgresql://a/log"
    assert both.store_dsn == "postgresql://b/quotes"
    one = p.parse_args(["--dsn", "postgresql://a/log"])
    assert one.store_dsn is None, (
        "--store-dsn must default to absent so it can fall back to --dsn")


def test_store_without_a_run_id_or_without_quotes_is_refused():
    """Two refusals with two different reasons, and neither is a silent no-op.

    A stored row that cannot name the process that wrote it cannot be fenced
    off later; and ``--store`` alone would look like it did something while
    there was nothing to store, because the mark table is never stored.
    """
    for argv in (["--quotes", "--store"], ["--store", "--run-id", "r"]):
        with pytest.raises(SystemExit):
            rs.main(argv)


def test_main_actually_builds_the_store_from_store_dsn(monkeypatch):
    """A FLAG THAT NOTHING READS IS A FLAG THAT DOES NOTHING.

    Mutation showed the parser test passing while ``main`` still built the
    QuoteStore from ``--dsn``: the option existed, was documented, and was
    ignored. Same family as a helper that is flawless and uncalled — drive the
    real call site and assert which DSN arrived.
    """
    built = {}

    class SpyStore:
        def __init__(self, dsn=None):
            built["dsn"] = dsn

        def ensure_schema(self):
            return True

        def rows(self, limit=None, basis=None):
            return [], False

    monkeypatch.setattr(rs, "QuoteStore", SpyStore)
    monkeypatch.setattr(rs, "read_events_from_store",
                        lambda dsn=None: ([], {"source": "test",
                                               "events_in_log": 0,
                                               "order_events_read": 0,
                                               "truncated": False}))
    monkeypatch.setattr(rs, "SipQuotes", lambda: FakeSip({}))
    monkeypatch.setattr(rs, "render", lambda report, out=None: None)

    rs.main(["--quotes", "--store", "--run-id", "r",
             "--dsn", "postgresql://a/log",
             "--store-dsn", "postgresql://b/quotes"])
    assert built["dsn"] == "postgresql://b/quotes", (
        "main built the quote store from --dsn; --store-dsn is decoration")


def test_store_dsn_falls_back_to_dsn_when_absent(monkeypatch):
    """One database is still the normal case and must still work with one flag."""
    built = {}

    class SpyStore:
        def __init__(self, dsn=None):
            built["dsn"] = dsn

        def ensure_schema(self):
            return True

        def rows(self, limit=None, basis=None):
            return [], False

    monkeypatch.setattr(rs, "QuoteStore", SpyStore)
    monkeypatch.setattr(rs, "read_events_from_store",
                        lambda dsn=None: ([], {"source": "test",
                                               "events_in_log": 0,
                                               "order_events_read": 0,
                                               "truncated": False}))
    monkeypatch.setattr(rs, "SipQuotes", lambda: FakeSip({}))
    monkeypatch.setattr(rs, "render", lambda report, out=None: None)

    rs.main(["--quotes", "--store", "--run-id", "r",
             "--dsn", "postgresql://a/both"])
    assert built["dsn"] == "postgresql://a/both"
