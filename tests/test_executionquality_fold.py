"""Tests for the fold/derive layer of app.fund.executionquality.

SCOPE: fold_order_lifecycles, fill_legs, execution_class, class_of_row,
retro_mark_rows, summarise_mark_rows, summarise_quote_rows, coverage.

Deliberately excluded: the arithmetic primitives (mid_of, spread_bps_of,
effective_spread_bps, signed_effective_spread_bps, mark_shortfall_bps --
another module's job) and QuoteStore/psycopg (no database anywhere here).
Every fixture is a plain dict built by the small helpers below; nothing in
this file imports psycopg, opens a connection, or monkeypatches app modules.
"""

from __future__ import annotations

import random

import pytest

from app.fund.executionquality import (
    EXECUTION_CLASSES,
    class_of_row,
    coverage,
    execution_class,
    fill_legs,
    fold_order_lifecycles,
    retro_mark_rows,
    summarise_mark_rows,
    summarise_quote_rows,
)


# --- fixture helpers --------------------------------------------------------


def ev(seq, order_id, type_, payload, *, aggregate_type="order",
       actor="test-actor", ts=None):
    """One raw log row, in the exact shape fold_order_lifecycles reads:
    seq, aggregate_id, aggregate_type, type, actor, ts, payload."""
    return {
        "seq": seq,
        "aggregate_id": order_id,
        "aggregate_type": aggregate_type,
        "type": type_,
        "actor": actor,
        "ts": ts or f"2026-08-23T00:00:{seq:02d}+00:00",
        "payload": payload,
    }


def sofi_multileg_events(order_id="5d495c88", include_proposed=True):
    """THE ONE REAL MULTI-LEG ORDER from the live log, verbatim: 5d495c88,
    SOFI, sell, submitted venue alpaca, arrival_price 18.44."""
    events = []
    if include_proposed:
        events.append(ev(60, order_id, "OrderProposed", {
            "qty": 6.81181, "side": "sell", "venue": "alpaca", "symbol": "SOFI",
            "critique": "c", "rationale": "r",
        }))
    events += [
        ev(67, order_id, "OrderSubmitted",
           {"venue": "alpaca", "venue_ref": "f916f1af", "arrival_price": 18.44}),
        ev(78, order_id, "OrderPartiallyFilled",
           {"avg_price": "18.41", "cumulative_qty": "2.0"}),
        ev(83, order_id, "OrderPartiallyFilled",
           {"avg_price": "18.446", "cumulative_qty": "5.0"}),
        ev(84, order_id, "OrderPartiallyFilled",
           {"avg_price": "18.438178", "cumulative_qty": "5.81181"}),
        ev(85, order_id, "OrderFilled",
           {"fees": "0", "side": "sell", "symbol": "SOFI",
            "avg_price": "18.431105", "filled_qty": "6.81181",
            "strategy_id": "ca78408f"}),
    ]
    return events


def _expected_incremental(pairs):
    """Reimplementation of the increment formula, kept independent of the
    source so a test built from it cannot agree with a hardcoded duplicate.

    ``pairs`` is [(price, cumulative_qty), ...] in fill order.
    """
    out = []
    prev_p = prev_q = None
    for p, q in pairs:
        if prev_p is None:
            out.append(p)
        elif q <= prev_q:
            out.append(None)
        else:
            out.append((p * q - prev_p * prev_q) / (q - prev_q))
        prev_p, prev_q = p, q
    return out


def qrow(order_id, event_seq, *, event_kind="filled", symbol="AAA",
         submitted_venue="alpaca", was_submitted=True,
         effective_spread_bps=None, signed_effective_spread_bps=None,
         feed="sip"):
    """A stored quote row, in the shape summarise_quote_rows/coverage read."""
    return {
        "order_id": order_id, "event_seq": event_seq, "event_kind": event_kind,
        "symbol": symbol, "submitted_venue": submitted_venue,
        "was_submitted": was_submitted,
        "effective_spread_bps": effective_spread_bps,
        "signed_effective_spread_bps": signed_effective_spread_bps,
        "feed": feed,
    }


# --- 1. fold_order_lifecycles is order-independent --------------------------


def test_fold_is_order_independent():
    """The spine serves /fund/events NEWEST FIRST while EventStore.stream is
    oldest-first; a fold that silently assumed either one would be right only
    half the time. Folding the same events oldest-first, newest-first, and
    shuffled must produce byte-identical output."""
    events = sofi_multileg_events()
    events += [
        ev(10, "aaa11111", "OrderProposed", {"symbol": "AAPL", "side": "buy"}),
        ev(11, "aaa11111", "OrderSubmitted", {"venue": "paper", "arrival_price": 100.0}),
        ev(12, "aaa11111", "OrderFilled", {"symbol": "AAPL", "side": "buy",
                                            "avg_price": "100.0", "filled_qty": "1.0"}),
    ]

    oldest_first = sorted(events, key=lambda e: e["seq"])
    newest_first = list(reversed(oldest_first))
    shuffled = events[:]
    random.Random(42).shuffle(shuffled)

    r1 = fold_order_lifecycles(oldest_first)
    r2 = fold_order_lifecycles(newest_first)
    r3 = fold_order_lifecycles(shuffled)

    assert r1 == r2 == r3
    assert set(r1) == {"5d495c88", "aaa11111"}


# --- 2. symbol/side recovered from whichever event carries them ------------


def test_symbol_and_side_none_when_no_source_carries_them():
    """OrderSubmitted and OrderPartiallyFilled payloads never carry symbol or
    side. An order with no OrderProposed and no OrderFilled must report both
    as None -- never '' or '?', which would silently pass a downstream symbol
    filter or quote lookup for a name that was never named."""
    oid = "onlysub01"
    events = [
        ev(1, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 10.0}),
        ev(2, oid, "OrderPartiallyFilled", {"avg_price": "10.0", "cumulative_qty": "1.0"}),
    ]
    rec = fold_order_lifecycles(events)[oid]
    assert rec["symbol"] is None
    assert rec["side"] is None
    assert rec["symbol"] != ""
    assert rec["symbol"] != "?"
    assert rec["side"] != ""
    assert rec["side"] != "?"


def test_symbol_recovered_from_orderfilled_when_no_proposed():
    """7 of 29 filled orders in the live log predate the propose path and
    carry no OrderProposed at all. OrderFilled must still supply the symbol
    and side for those orders."""
    oid = "fromfill1"
    events = [
        ev(1, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 50.0}),
        ev(2, oid, "OrderFilled", {"symbol": "XYZ", "side": "buy",
                                    "avg_price": "50.0", "filled_qty": "3.0"}),
    ]
    rec = fold_order_lifecycles(events)[oid]
    assert rec["symbol"] == "XYZ"
    assert rec["side"] == "buy"


def test_symbol_recovered_from_orderproposed_when_never_filled():
    """A declined or still-open order has no OrderFilled at all; OrderProposed
    is the only remaining source of symbol/side and must be used."""
    oid = "fromprop1"
    events = [
        ev(1, oid, "OrderProposed", {"symbol": "QQQ", "side": "sell",
                                      "qty": 2.0, "venue": "alpaca",
                                      "critique": "c", "rationale": "r"}),
        ev(2, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 400.0}),
    ]
    rec = fold_order_lifecycles(events)[oid]
    assert rec["symbol"] == "QQQ"
    assert rec["side"] == "sell"


# --- 3. non-order aggregates are ignored ------------------------------------


def test_non_order_aggregates_never_appear():
    """nav/desk/strategy rows can carry a 'symbol' key that looks exactly
    like an order payload; the fold must filter on aggregate_type, never on
    payload shape, or a non-order aggregate would leak into the output."""
    events = [
        ev(1, "navrow01", "NavSnapshot", {"symbol": "SPY"}, aggregate_type="nav"),
        ev(2, "deskrow1", "DeskItemOpened", {"symbol": "AAPL"}, aggregate_type="desk"),
        ev(3, "stratrow1", "StrategyRebalanced", {"symbol": "MSFT"}, aggregate_type="strategy"),
        ev(4, "realorder", "OrderSubmitted", {"venue": "alpaca", "arrival_price": 1.0}),
    ]
    out = fold_order_lifecycles(events)
    assert set(out) == {"realorder"}
    assert "navrow01" not in out
    assert "deskrow1" not in out
    assert "stratrow1" not in out


# --- 4. execution_class 3-way partition -------------------------------------


@pytest.mark.parametrize("venue", [None, "alpaca", "paper", ""])
def test_execution_class_not_submitted_regardless_of_venue(venue):
    """was_submitted False means no OrderSubmitted exists for this order at
    all; whatever venue string happens to be lying around must never
    override that -- not_submitted is a fact about existence, not venue."""
    assert execution_class(venue, False) == "not_submitted"


@pytest.mark.parametrize("venue", ["paper", "PAPER", " paper "])
def test_execution_class_simulated_case_and_whitespace_insensitive(venue):
    """The venue string comes straight off the connector; case and incidental
    whitespace must not create a false 'executed' classification for the
    simulated venue."""
    assert execution_class(venue, True) == "simulated"


def test_execution_class_executed_for_real_venue():
    """The plain positive case: submitted to a named real venue is executed."""
    assert execution_class("alpaca", True) == "executed"


@pytest.mark.parametrize("venue", [None, ""])
def test_execution_class_unnamed_venue_on_real_submission_is_executed(venue):
    """THE IMPORTANT ONE. A mis-classification here would silently drop a
    genuine fill out of the fund's cost sample: an order that WAS submitted
    by a connector that recorded no venue name is a real execution, not a
    backfill, and must classify as EXECUTED -- the conservative direction
    that keeps the observation in the scrutinised population."""
    assert execution_class(venue, True) == "executed"


def test_class_of_row_agrees_with_execution_class():
    """class_of_row derives from a STORED row's raw columns; it must reach
    the same verdict as calling execution_class directly on the same facts,
    or a reader of stored rows would disagree with the classifier itself."""
    row = {"submitted_venue": "alpaca", "was_submitted": True, "other": "ignored"}
    assert class_of_row(row) == execution_class("alpaca", True) == "executed"

    row2 = {"submitted_venue": None, "was_submitted": False}
    assert class_of_row(row2) == execution_class(None, False) == "not_submitted"


# --- 5. fill_legs ------------------------------------------------------------


def test_fill_legs_one_row_per_fill_event_not_per_order():
    """The SOFI order carries 4 fill events (3 partial + 1 terminal); fill_legs
    must emit 4 rows for that single order, never 1 row per order."""
    lifecycles = fold_order_lifecycles(sofi_multileg_events())
    legs = fill_legs(lifecycles)
    sofi_legs = [l for l in legs if l["order_id"] == "5d495c88"]
    assert len(sofi_legs) == 4


def test_fill_legs_submitted_event_produces_no_leg():
    """OrderSubmitted carries a price (arrival_price) but is not a fill; an
    order with only a submitted event and no fill events must contribute
    zero legs, not a phantom leg at the arrival price."""
    oid = "submitonly"
    events = [ev(1, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 5.0})]
    lifecycles = fold_order_lifecycles(events)
    assert fill_legs(lifecycles) == []


def test_fill_legs_sorted_by_event_seq_ascending():
    """Every summary downstream assumes ascending seq order. Interleave two
    orders so the per-order-then-concatenate construction is NOT already
    sorted, and check the final merged output is."""
    events = (
        sofi_multileg_events(order_id="orderA", include_proposed=False)
        + [
            ev(70, "orderB", "OrderSubmitted", {"venue": "alpaca", "arrival_price": 9.0}),
            ev(72, "orderB", "OrderFilled", {"symbol": "ZZ", "side": "buy",
                                              "avg_price": "9.0", "filled_qty": "1.0"}),
        ]
    )
    lifecycles = fold_order_lifecycles(events)
    legs = fill_legs(lifecycles)
    seqs = [l["event_seq"] for l in legs]
    assert seqs == sorted(seqs)
    # and it is a genuine check, not a vacuous one over a single-order list
    assert {l["order_id"] for l in legs} == {"orderA", "orderB"}


def test_fill_legs_multi_leg_flag():
    """multi_leg must be True on EVERY leg of the 4-leg SOFI order and False
    on a single-fill order -- the flag decides which legs a summary averages
    versus reports apart, so getting it wrong on even one leg corrupts a mean."""
    single_oid = "single001"
    events = sofi_multileg_events() + [
        ev(1, single_oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 20.0}),
        ev(2, single_oid, "OrderFilled", {"symbol": "SNGL", "side": "buy",
                                           "avg_price": "20.0", "filled_qty": "1.0"}),
    ]
    lifecycles = fold_order_lifecycles(events)
    legs = fill_legs(lifecycles)
    sofi_legs = [l for l in legs if l["order_id"] == "5d495c88"]
    single_legs = [l for l in legs if l["order_id"] == single_oid]
    assert len(sofi_legs) == 4
    assert all(l["multi_leg"] is True for l in sofi_legs)
    assert len(single_legs) == 1
    assert single_legs[0]["multi_leg"] is False


def test_fill_legs_incremental_price_on_sofi_fixture():
    """incremental_price is the price of the shares that arrived in THIS leg,
    not the order's running average. Expected values are derived here, fresh,
    from the fixture's own (price, cumulative_qty) pairs via an independent
    reimplementation of the formula -- never a copied literal -- so this test
    cannot agree with a hardcoded duplicate of the source's own number."""
    pairs = [(18.41, 2.0), (18.446, 5.0), (18.438178, 5.81181), (18.431105, 6.81181)]
    expected = _expected_incremental(pairs)

    lifecycles = fold_order_lifecycles(sofi_multileg_events())
    legs = fill_legs(lifecycles)
    sofi_legs = sorted([l for l in legs if l["order_id"] == "5d495c88"],
                        key=lambda l: l["event_seq"])
    assert len(sofi_legs) == len(expected)
    for leg, exp in zip(sofi_legs, expected):
        assert leg["incremental_price"] == pytest.approx(exp)


# --- 6. retro_mark_rows: exclusive, ORDERED classification ------------------


def test_retro_mark_multi_leg_running_average_equal_to_mark_is_cumulative_not_identity():
    """ORDER MATTERS: cumulative is checked before identity. A leg of a
    multi-leg order whose running-average price happens to equal the arrival
    mark exactly is still a running average, not an arithmetic identity, and
    must classify 'cumulative' -- never 'identity'."""
    oid = "cumeqmark"
    mark = 18.41
    events = [
        ev(1, oid, "OrderProposed", {"symbol": "SOFI", "side": "sell"}),
        ev(2, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": mark}),
        # This leg's avg_price equals the mark exactly -- would read
        # "identity" in isolation, but the order has a second fill leg below,
        # so it is multi_leg and must be classified "cumulative" instead.
        ev(3, oid, "OrderPartiallyFilled", {"avg_price": "18.41", "cumulative_qty": "2.0"}),
        ev(4, oid, "OrderFilled", {"symbol": "SOFI", "side": "sell",
                                    "avg_price": "18.50", "filled_qty": "5.0"}),
    ]
    rows = retro_mark_rows(events)
    first_leg = next(r for r in rows if r["event_seq"] == 3)
    assert first_leg["multi_leg"] is True
    assert first_leg["fill_price"] == pytest.approx(mark)
    assert first_leg["classification"] == "cumulative"
    assert first_leg["classification"] != "identity"


def test_retro_mark_identity_when_fill_equals_mark():
    """A single-leg fill at exactly the arrival mark is an arithmetic
    identity, not a measurement: shortfall is exactly 0.0 with nothing
    having moved in the market."""
    oid = "identity1"
    value = 82.78500366210938
    events = [
        ev(1, oid, "OrderSubmitted", {"venue": "paper", "arrival_price": value}),
        ev(2, oid, "OrderFilled", {"symbol": "GLD", "side": "buy",
                                    "avg_price": str(value), "filled_qty": "1.0"}),
    ]
    rows = retro_mark_rows(events)
    assert len(rows) == 1
    assert rows[0]["classification"] == "identity"
    assert rows[0]["shortfall_bps"] == 0.0


def test_retro_mark_no_mark_when_no_submitted():
    """A filled order with no OrderSubmitted has no arrival mark at all;
    nothing can be computed and shortfall_bps must be None, never 0.0 --
    absence is never zero."""
    oid = "nosub001"
    events = [
        ev(1, oid, "OrderFilled", {"symbol": "SPY", "side": "buy",
                                    "avg_price": "500.0", "filled_qty": "1.0"}),
    ]
    rows = retro_mark_rows(events)
    assert len(rows) == 1
    assert rows[0]["classification"] == "no_mark"
    assert rows[0]["shortfall_bps"] is None


def test_retro_mark_unusable_when_side_unreadable_and_mark_differs():
    """A real price difference we cannot sign is measured in magnitude and
    unmeasured in direction: it is reclassified to 'unusable' with no
    shortfall, never a guessed sign that could silently flip a saving into a
    reported cost or vice versa."""
    oid = "nosidefil"
    events = [
        ev(1, oid, "OrderSubmitted", {"venue": "alpaca", "arrival_price": 10.0}),
        # no side anywhere: OrderFilled omits it here, and there is no
        # OrderProposed to recover it from either.
        ev(2, oid, "OrderFilled", {"symbol": "NOSIDE",
                                    "avg_price": "11.0", "filled_qty": "1.0"}),
    ]
    rows = retro_mark_rows(events)
    assert len(rows) == 1
    row = rows[0]
    assert row["side"] is None
    assert row["classification"] == "unusable"
    assert row["shortfall_bps"] is None


# --- 7. summarise_mark_rows ---------------------------------------------------


def test_summarise_mark_rows_identity_rows_never_move_the_mean():
    """The summary statistic is over 'measured' rows ONLY. Adding identity
    rows (each a real 0.0 that is arithmetic, not execution) must leave the
    measured mean untouched and must raise excluded_identities by exactly
    the count added."""
    measured_rows = [
        {"classification": "measured", "shortfall_bps": 5.0},
        {"classification": "measured", "shortfall_bps": 10.0},
        {"classification": "measured", "shortfall_bps": -3.0},
    ]
    identity_rows = [
        {"classification": "identity", "shortfall_bps": 0.0},
        {"classification": "identity", "shortfall_bps": 0.0},
    ]
    base = summarise_mark_rows(measured_rows)
    with_identities = summarise_mark_rows(measured_rows + identity_rows)

    assert base["shortfall_bps"]["mean"] == with_identities["shortfall_bps"]["mean"]
    assert base["excluded_identities"] == 0
    assert with_identities["excluded_identities"] == 2


def test_summarise_mark_rows_zero_measured_gives_none_not_zero():
    """With zero 'measured' rows, shortfall_bps must be None -- not 0.0 and
    not an empty dict -- because there is no sample to summarise and a fund
    whose panel reads 0.0 with nothing measured is the absence-as-zero
    failure this instrument exists to avoid."""
    rows = [
        {"classification": "no_mark", "shortfall_bps": None},
        {"classification": "identity", "shortfall_bps": 0.0},
        {"classification": "cumulative", "shortfall_bps": 3.0},
    ]
    out = summarise_mark_rows(rows)
    assert out["shortfall_bps"] is None


# --- 8. summarise_quote_rows ---------------------------------------------------


def test_summarise_quote_rows_headline_class_is_executed():
    """The panel's headline number must always name the executed population
    -- never simulated, never a flat average across all three classes."""
    rows = [qrow("o1", 1, submitted_venue="alpaca", effective_spread_bps=2.0)]
    out = summarise_quote_rows(rows)
    assert out["headline_class"] == "executed"


def test_summarise_quote_rows_by_execution_class_has_all_classes_with_leg_buckets():
    """Every one of EXECUTION_CLASSES must appear in by_execution_class, each
    carrying single_leg and multi_leg sub-buckets -- a missing class would
    silently drop a whole population from the report."""
    rows = [
        qrow("o1", 1, submitted_venue="alpaca", was_submitted=True, effective_spread_bps=1.0),
        qrow("o2", 2, submitted_venue="paper", was_submitted=True, effective_spread_bps=1.0),
        qrow("o3", 3, submitted_venue=None, was_submitted=False, effective_spread_bps=1.0),
    ]
    out = summarise_quote_rows(rows)
    assert set(out["by_execution_class"]) == set(EXECUTION_CLASSES)
    for cls in EXECUTION_CLASSES:
        bucket = out["by_execution_class"][cls]
        assert "single_leg" in bucket
        assert "multi_leg" in bucket


def test_summarise_quote_rows_executed_mean_unpolluted_by_simulated_outlier():
    """A flat mean over this fund's real log would report execution cost near
    four hundred basis points, because one simulated leg (the GLD phantom-
    price incident) reads in the thousands of bps. The executed bucket's mean
    must be computed over executed rows only, unmoved by a huge simulated
    spread sitting in the same row set."""
    executed_rows = [
        qrow(f"exec{i}", i, submitted_venue="alpaca", was_submitted=True,
             effective_spread_bps=2.0)
        for i in range(3)
    ]
    simulated_outlier = qrow("simphantom", 99, submitted_venue="paper",
                              was_submitted=True, effective_spread_bps=15000.0)
    rows = executed_rows + [simulated_outlier]
    out = summarise_quote_rows(rows)
    executed_bucket = out["by_execution_class"]["executed"]
    simulated_bucket = out["by_execution_class"]["simulated"]
    assert executed_bucket["effective_spread_bps"]["mean"] == pytest.approx(2.0)
    assert simulated_bucket["effective_spread_bps"]["mean"] == pytest.approx(15000.0)


def test_summarise_quote_rows_none_spread_counts_as_unmeasured_never_zero():
    """A row with effective_spread_bps None means 'we could not compute
    this'. It must be counted as unmeasured, and excluded from the mean --
    folding it in as 0.0 would understate the fund's cost silently."""
    rows = [
        qrow("m1", 1, submitted_venue="alpaca", was_submitted=True, effective_spread_bps=4.0),
        qrow("m2", 2, submitted_venue="alpaca", was_submitted=True, effective_spread_bps=None),
    ]
    out = summarise_quote_rows(rows)
    bucket = out["by_execution_class"]["executed"]
    assert bucket["measured"] == 1
    assert bucket["unmeasured"] == 1
    assert bucket["fills"] == 2
    assert bucket["effective_spread_bps"]["mean"] == pytest.approx(4.0)


def test_summarise_quote_rows_by_symbol_fills_equals_measured_plus_unmeasured():
    """by_symbol must report fills == measured + unmeasured for every symbol,
    so a symbol with fills but no usable quotes cannot be misread as a symbol
    with no fills at all."""
    rows = [
        qrow("a1", 1, symbol="AAA", submitted_venue="alpaca", effective_spread_bps=1.0),
        qrow("a2", 2, symbol="AAA", submitted_venue="alpaca", effective_spread_bps=None),
        qrow("b1", 3, symbol="BBB", submitted_venue="paper", effective_spread_bps=3.0),
    ]
    out = summarise_quote_rows(rows)
    by_symbol = {s["symbol"]: s for s in out["by_symbol"]}
    assert by_symbol["AAA"]["fills"] == by_symbol["AAA"]["measured"] + by_symbol["AAA"]["unmeasured"]
    assert by_symbol["AAA"]["fills"] == 2
    assert by_symbol["BBB"]["fills"] == by_symbol["BBB"]["measured"] + by_symbol["BBB"]["unmeasured"]
    assert by_symbol["BBB"]["fills"] == 1


def test_summarise_quote_rows_feeds_never_mixed():
    """An IEX mid and a consolidated SIP mid describe different markets;
    by_feed must never blend rows from the two feeds into one figure."""
    rows = [
        qrow("i1", 1, feed="iex", submitted_venue="alpaca", effective_spread_bps=8.0),
        qrow("s1", 2, feed="sip", submitted_venue="alpaca", effective_spread_bps=2.0),
    ]
    out = summarise_quote_rows(rows)
    assert out["by_feed"]["iex"]["mean"] == pytest.approx(8.0)
    assert out["by_feed"]["sip"]["mean"] == pytest.approx(2.0)


# --- 9. coverage ---------------------------------------------------------------


def test_coverage_unreadable_store_reports_none_not_zero():
    """quote_rows=None means the store could not be read AT ALL -- a
    different fact from 'read and found nothing' -- and must report every
    count as None, never 0, with fill_events_total still correctly computed
    from the log alone."""
    log_legs = [
        {"order_id": "o1", "event_seq": 1},
        {"order_id": "o1", "event_seq": 2},
        {"order_id": "o2", "event_seq": 3},
    ]
    out = coverage(log_legs, None)
    assert out == {
        "readable": False, "fill_events_total": 3, "measured": None,
        "quote_absent": None, "uncaptured": None, "pct_measured": None,
        "reason": "the execution-quote store could not be read",
    }


def test_coverage_empty_store_with_legs_is_a_real_zero():
    """quote_rows=[] with 5 log legs means the capture service ran and
    captured nothing: measured 0 and pct_measured 0.0 are real measurements,
    not an absence, and must be the float 0.0, never None."""
    log_legs = [{"order_id": f"o{i}", "event_seq": i} for i in range(5)]
    out = coverage(log_legs, [])
    assert out["readable"] is True
    assert out["measured"] == 0
    assert out["uncaptured"] == 5
    assert out["pct_measured"] == 0.0
    assert out["pct_measured"] is not None


def test_coverage_quote_present_with_no_usable_mid_counts_as_quote_absent():
    """A quote row that WAS captured but has no usable midpoint belongs in
    quote_absent -- never in measured, and never inflating uncaptured -- the
    honest middle state between 'never reached' and 'measured'."""
    log_legs = [{"order_id": "o1", "event_seq": 1}, {"order_id": "o2", "event_seq": 2}]
    quote_rows = [
        {"order_id": "o1", "event_seq": 1, "event_kind": "filled",
         "effective_spread_bps": None},
    ]
    out = coverage(log_legs, quote_rows)
    assert out["measured"] == 0
    assert out["quote_absent"] == 1
    assert out["uncaptured"] == 1


def test_coverage_quote_row_not_in_log_does_not_inflate_measured():
    """A quote row whose (order_id, event_seq) is not present in the log is
    not a real fill's measurement and must not count toward measured, even
    though it carries a numeric effective_spread_bps."""
    log_legs = [{"order_id": "o1", "event_seq": 1}]
    quote_rows = [
        {"order_id": "ghost", "event_seq": 999, "event_kind": "filled",
         "effective_spread_bps": 5.0},
    ]
    out = coverage(log_legs, quote_rows)
    assert out["measured"] == 0
    assert out["uncaptured"] == 1


def test_coverage_zero_fill_events_gives_none_pct_not_zero():
    """With no denominator, pct_measured must be None -- 0.0 would falsely
    claim a measured rate of zero rather than honestly saying there was
    nothing to measure."""
    out = coverage([], [])
    assert out["fill_events_total"] == 0
    assert out["pct_measured"] is None


# ===========================================================================
# Added by the builder to close three mutation survivors (M23, M29, M65).
# Each docstring names the mutant it kills.
# ===========================================================================

def test_the_submitted_venue_is_read_from_the_submitted_leg_not_the_fill():
    """KILLS M23: the fold dropping submitted_venue entirely.

    THE REAL CASE, order 17d64dcd (DBA, 2026-08-21): OrderSubmitted says
    ``paper`` and OrderFilled says ``alpaca``. Those are a fact and a wish —
    the submitted leg carries what the connector that ran the order handed
    back, the filled leg carries a string the proposer put on the request.
    ``tca.py`` preferred the wish and counted a simulated fill as an
    informative execution cost for a day.

    Nothing else in this file would notice if the fold stopped populating
    submitted_venue: every other test passes a venue to execution_class
    directly, so the whole class partition would silently read ``executed``.
    """
    events = [
        ev(1, "17d64dcd", "OrderProposed",
           {"qty": 5.314306, "side": "buy", "venue": "alpaca",
            "symbol": "DBA"}),
        ev(2, "17d64dcd", "OrderSubmitted",
           {"venue": "paper", "venue_ref": "4a8f",
            "arrival_price": 28.3799991607666}),
        ev(3, "17d64dcd", "OrderFilled",
           {"fees": "0", "side": "buy", "venue": "alpaca", "symbol": "DBA",
            "avg_price": "28.3799991607666", "filled_qty": "5.314306",
            "strategy_id": "sleeve_premia_carry"}),
    ]
    rec = fold_order_lifecycles(events)["17d64dcd"]
    assert rec["submitted_venue"] == "paper"
    assert rec["filled_venue"] == "alpaca"
    assert rec["was_submitted"] is True

    leg = fill_legs(fold_order_lifecycles(events))[0]
    assert leg["submitted_venue"] == "paper"
    assert leg["execution_class"] == "simulated", (
        "the fill leg followed the proposer's wish instead of the connector's "
        "fact - this is the tca.py defect reproduced")


def test_an_order_never_submitted_has_no_submitted_venue_and_says_so():
    """The other half of M23: absent, and absent for the right reason.

    Seven of the live log's twenty nine filled orders have no OrderSubmitted
    at all. submitted_venue must be None AND was_submitted must be False, so
    a reader can tell "never sent to anybody" from "sent by a connector that
    recorded no venue name".
    """
    events = [
        ev(1, "backfill-1", "OrderFilled",
           {"fees": "0", "side": "buy", "venue": "alpaca", "symbol": "SOFI",
            "avg_price": "18.15", "filled_qty": "8.0"}),
    ]
    rec = fold_order_lifecycles(events)["backfill-1"]
    assert rec["submitted_venue"] is None
    assert rec["was_submitted"] is False
    assert fill_legs({"backfill-1": rec})[0]["execution_class"] == "not_submitted"


def _qrow(order_id, seq, cls_venue, eff, submitted=True, kind="filled"):
    return {"order_id": order_id, "event_seq": seq, "event_kind": kind,
            "symbol": "SPY", "submitted_venue": cls_venue,
            "was_submitted": submitted, "feed": "sip",
            "effective_spread_bps": eff,
            "signed_effective_spread_bps": eff}


def test_single_and_multi_leg_buckets_partition_their_class_exactly():
    """KILLS M29: the single-leg bucket silently emptied.

    single_leg is THE headline figure — on a single-fill order ``avg_price``
    IS the print, so its effective spread is the textbook quantity, while a
    multi-leg order's is a running average against a point-in-time mid. A
    mutation that made single_leg always empty survived every other test in
    this file, which means nothing was checking the number the report puts a
    marker beside.

    Asserted as a partition (single + multi == the class, and neither is
    silently zero) rather than as two independent counts, because two counts
    that are both wrong in the same direction still add up.
    """
    rows = [
        _qrow("single-a", 1, "alpaca", 2.0),
        _qrow("single-b", 2, "alpaca", 4.0),
        _qrow("multi", 3, "alpaca", 10.0, kind="partially_filled"),
        _qrow("multi", 4, "alpaca", 20.0),
    ]
    ex = summarise_quote_rows(rows)["by_execution_class"]["executed"]
    assert ex["fills"] == 4
    assert ex["single_leg"]["fills"] == 2
    assert ex["multi_leg"]["fills"] == 2
    assert ex["single_leg"]["fills"] + ex["multi_leg"]["fills"] == ex["fills"]
    # The numbers, not just the counts: pooling the two would give 9.0.
    assert ex["single_leg"]["effective_spread_bps"]["mean"] == 3.0
    assert ex["multi_leg"]["effective_spread_bps"]["mean"] == 15.0
    assert ex["effective_spread_bps"]["mean"] == 9.0


def test_a_lone_fill_is_single_leg_and_the_multi_bucket_is_absent_not_zero():
    """The empty half of the partition reports None, never a mean of 0.0.

    An execution-cost panel reading 0.0 bps because nothing landed in the
    bucket is the absence-as-zero failure at the top of the non-negotiables.
    """
    ex = summarise_quote_rows([_qrow("solo", 1, "alpaca", 3.5)])
    ex = ex["by_execution_class"]["executed"]
    assert ex["single_leg"]["effective_spread_bps"]["n"] == 1
    assert ex["multi_leg"]["fills"] == 0
    assert ex["multi_leg"]["effective_spread_bps"] is None


def test_the_identity_tolerance_is_probed_at_its_own_edge():
    """GAUNTLET 5: nothing probed MARK_IDENTITY_TOLERANCE at the tolerance.

    The tolerance is 1e-12 and non-strict, so a difference EXACTLY at it is an
    identity and anything larger is a measurement. Only a zero difference was
    ever tested, which cannot tell 1e-12 from 1.0 — and a tolerance widened by
    accident silently reclassifies real sub-basis-point fills as arithmetic and
    drops them out of the fund's cost sample.
    """
    from app.fund.executionquality import MARK_IDENTITY_TOLERANCE as TOL

    def classify(diff):
        mark = 100.0
        events = [
            ev(1, "t1", "OrderSubmitted",
               {"venue": "alpaca", "venue_ref": "r", "arrival_price": mark}),
            ev(2, "t1", "OrderFilled",
               {"fees": "0", "side": "buy", "symbol": "SPY",
                "avg_price": repr(mark + diff), "filled_qty": "1.0"}),
        ]
        return retro_mark_rows(events)[0]["classification"]

    assert classify(0.0) == "identity"
    assert classify(TOL) == "identity"
    # Strictly above the tolerance. 1e-9 is comfortably representable beside
    # 100.0 (the float spacing there is about 1.4e-14), so this really is a
    # difference the arithmetic can see.
    assert classify(1e-9) == "measured"


def test_a_genuine_quantity_of_zero_is_kept_not_coalesced_away():
    """`a or b` REACHES PAST A REAL ZERO.

    ``filled_qty`` on a terminal fill and ``cumulative_qty`` on a partial spell
    the same fact, and the fold used to pick between them with ``or``. A fill
    of exactly zero shares is falsy, so it would silently become the other key
    and then None — an absent quantity where a measured zero belongs. No fill
    in the live log carries a zero quantity, which is the only reason this
    would have shipped unnoticed.
    """
    events = [
        ev(1, "z1", "OrderFilled",
           {"fees": "0", "side": "buy", "symbol": "SPY", "avg_price": "10.0",
            "filled_qty": 0, "cumulative_qty": 99.0}),
    ]
    leg = fill_legs(fold_order_lifecycles(events))[0]
    assert leg["filled_qty"] == 0.0, "a real zero was coalesced into 99.0"


def test_a_quantity_that_is_absent_falls_through_to_the_other_spelling():
    """The other side of the same branch, so the fix cannot be "always take
    filled_qty" — a partial fill has only ``cumulative_qty``."""
    events = [
        ev(1, "z2", "OrderPartiallyFilled",
           {"avg_price": "10.0", "cumulative_qty": "2.5"}),
    ]
    leg = fill_legs(fold_order_lifecycles(events))[0]
    assert leg["filled_qty"] == 2.5


def test_two_events_with_no_sequence_number_do_not_share_a_key():
    """A seq of 0/absent must not make two events one.

    ``coverage`` keys on ``(order_id, event_seq)``; a missing seq mapped onto a
    shared sentinel would silently merge two fills into one and shrink the
    denominator of the fund's own coverage figure.
    """
    events = [
        {"aggregate_id": "n1", "aggregate_type": "order", "type": "OrderFilled",
         "actor": "t", "ts": "2026-08-23T00:00:00+00:00",
         "payload": {"symbol": "SPY", "side": "buy", "avg_price": "1.0",
                     "filled_qty": "1.0"}},
        {"aggregate_id": "n2", "aggregate_type": "order", "type": "OrderFilled",
         "actor": "t", "ts": "2026-08-23T00:00:00+00:00",
         "payload": {"symbol": "SPY", "side": "buy", "avg_price": "2.0",
                     "filled_qty": "1.0"}},
    ]
    legs = fill_legs(fold_order_lifecycles(events))
    assert len(legs) == 2
    cov = coverage(legs, [])
    assert cov["fill_events_total"] == 2 and cov["uncaptured"] == 2


def test_coverage_matches_a_quote_row_whose_event_seq_is_zero():
    """A SEQ OF ZERO IS A SEQ, NOT AN ABSENT ONE.

    The fold gives a seq-less event ``event_seq = 0``, so a captured quote for
    it carries 0 too. Keying that onto the missing-seq sentinel would make the
    fill read as uncaptured forever while a perfectly good row sat in the
    table — coverage understating itself, permanently and invisibly.
    """
    log_legs = [{"order_id": "o0", "event_seq": 0}]
    quote_rows = [{"order_id": "o0", "event_seq": 0, "event_kind": "filled",
                   "effective_spread_bps": 2.5}]
    out = coverage(log_legs, quote_rows)
    assert out["measured"] == 1
    assert out["uncaptured"] == 0
    assert out["pct_measured"] == 100.0
