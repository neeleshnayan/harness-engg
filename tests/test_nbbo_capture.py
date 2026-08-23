"""Contract tests for ``scripts/execution/nbbo_capture.py``.

Mechanical authorship against the written contract in the dispatch brief.
Everything here is injected: no network, no Postgres, no real clock inside
an assertion path (except where ``run_loop`` itself gives no way to inject
one — noted at the call site).

Import strategy: ``tests/conftest.py`` already inserts ``<repo>/scripts``
onto ``sys.path`` (so the suite's ``import _fake_firestore`` works), and
``scripts/execution`` has no ``__init__.py`` — it is picked up as a PEP 420
namespace package. ``from execution import nbbo_capture`` was verified to
import cleanly under that setup before this file was written.
"""

from __future__ import annotations

import ast
import pathlib
from datetime import datetime, timedelta, timezone

import pytest

from execution import nbbo_capture
from app.fund.executionquality import (
    effective_spread_bps, mid_of, signed_effective_spread_bps,
)

NOW = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Fakes
# --------------------------------------------------------------------------


class FakeStore:
    """Stands in for ``QuoteStore``. Never touches Postgres.

    ``.record(**kw)`` appends the raw call to ``.calls`` (so a test can
    assert on exactly what the caller passed through) and returns a dict
    shaped like the real ``QuoteStore.record`` return value, computed by
    calling the SAME arithmetic functions production uses — so this fake
    cannot silently disagree with ``app.fund.executionquality``.
    """

    def __init__(self):
        self.calls: list[dict] = []
        self._next_id = 1

    def ensure_schema(self) -> bool:
        return True

    def record(self, *, order_id, event_kind, event_seq, event_ts, basis,
               capture_run, symbol=None, side=None, submitted_venue=None,
               was_submitted=False, bid=None, ask=None, bid_size=None,
               ask_size=None, quote_ts=None, feed=None,
               quote_absent_reason=None, fill_price=None,
               filled_qty=None) -> dict:
        self.calls.append(dict(
            order_id=order_id, event_kind=event_kind, event_seq=event_seq,
            event_ts=event_ts, basis=basis, capture_run=capture_run,
            symbol=symbol, side=side, submitted_venue=submitted_venue,
            was_submitted=was_submitted, bid=bid, ask=ask,
            bid_size=bid_size, ask_size=ask_size, quote_ts=quote_ts,
            feed=feed, quote_absent_reason=quote_absent_reason,
            fill_price=fill_price, filled_qty=filled_qty))

        # Mirror QuoteStore.record's own derivation exactly (mid_of, then
        # the caller's stated absence reason overrides a derived one and
        # drops any mid it disowned) so this fake cannot drift from what
        # the real store would have computed and stored.
        mid, derived_reason = mid_of(bid, ask)
        reason = quote_absent_reason or derived_reason
        if mid is not None and quote_absent_reason:
            mid, reason = None, quote_absent_reason
        eff = effective_spread_bps(fill_price, mid) if mid is not None else None
        signed = (signed_effective_spread_bps(fill_price, mid, side)
                  if mid is not None else None)

        row_id = self._next_id
        self._next_id += 1
        return {
            "quote_row_id": row_id, "created": True, "order_id": order_id,
            "event_seq": event_seq, "basis": basis, "mid": mid,
            "effective_spread_bps": eff,
            "signed_effective_spread_bps": signed,
            "quote_absent_reason": reason,
        }


class FakeQuotes:
    """Stands in for ``IexQuotes``. Never touches the network.

    Pass ``by_symbol`` for the normal case; pass ``raises`` to make
    ``.latest`` raise that exception instead (simulating a vendor outage).
    """

    def __init__(self, by_symbol: dict | None = None, raises: Exception | None = None):
        self._by_symbol = by_symbol or {}
        self._raises = raises
        self.calls: list[list[str]] = []

    def latest(self, symbols: list[str]) -> dict:
        self.calls.append(list(symbols))
        if self._raises is not None:
            raise self._raises
        return {s: self._by_symbol[s] for s in symbols if s in self._by_symbol}


# --------------------------------------------------------------------------
# Event builders — verbatim shapes from the live log
# --------------------------------------------------------------------------


def _event(seq, aggregate_id, aggregate_type, etype, ts, payload):
    return {
        "seq": seq, "aggregate_id": aggregate_id,
        "aggregate_type": aggregate_type, "type": etype,
        "actor": "test", "ts": ts, "payload": payload,
    }


def proposed(seq, oid, symbol, side, ts, qty=5.31, venue="alpaca"):
    return _event(seq, oid, "order", "OrderProposed", ts, {
        "qty": qty, "side": side, "venue": venue, "symbol": symbol,
        "rationale": "test",
    })


def submitted(seq, oid, ts, venue="paper", venue_ref="4a8f", arrival_price=28.38):
    return _event(seq, oid, "order", "OrderSubmitted", ts, {
        "venue": venue, "venue_ref": venue_ref, "arrival_price": arrival_price,
    })


def partial(seq, oid, ts, avg_price="18.41", cumulative_qty="2.0"):
    return _event(seq, oid, "order", "OrderPartiallyFilled", ts, {
        "avg_price": avg_price, "cumulative_qty": cumulative_qty,
    })


def filled(seq, oid, ts, symbol, side, avg_price="28.38", filled_qty="5.31",
           fees="0", strategy_id="s"):
    return _event(seq, oid, "order", "OrderFilled", ts, {
        "fees": fees, "side": side, "symbol": symbol,
        "avg_price": avg_price, "filled_qty": filled_qty,
        "strategy_id": strategy_id,
    })


def declined(seq, oid, ts):
    return _event(seq, oid, "order", "OrderDeclined", ts, {})


def rejected(seq, oid, ts):
    return _event(seq, oid, "order", "OrderRejected", ts, {})


def approved(seq, oid, ts):
    return _event(seq, oid, "order", "OrderApproved", ts, {})


def iso(dt: datetime) -> str:
    return dt.isoformat()


# ==========================================================================
# 1. too_old — fails closed
# ==========================================================================


def test_too_old_fresh_event_is_none():
    """A 1s-old event under a 120s bound may be quoted (returns None)."""
    ts = iso(NOW - timedelta(seconds=1))
    assert nbbo_capture.too_old(ts, 120.0, now=NOW) is None


def test_too_old_boundary_just_below_is_fresh():
    """age < bound: still fresh. Distinguishes the strict side of the boundary."""
    ts = iso(NOW - timedelta(seconds=119.5))
    result = nbbo_capture.too_old(ts, 120.0, now=NOW)
    assert result is None


def test_too_old_boundary_exactly_at_bound_is_fresh():
    """age == bound is NOT a refusal: the guard is ``age > max_age_s``, non-strict
    at equality. A test that cannot tell >= from > would pass on either
    implementation, which defeats the point of a boundary test."""
    ts = iso(NOW - timedelta(seconds=120.0))
    result = nbbo_capture.too_old(ts, 120.0, now=NOW)
    assert result is None


def test_too_old_boundary_just_above_bound_is_stale():
    """age > bound by even half a second is a refusal, not a fresh quote."""
    ts = iso(NOW - timedelta(seconds=120.5))
    result = nbbo_capture.too_old(ts, 120.0, now=NOW)
    assert isinstance(result, str)
    assert result.startswith("event_too_old_for_live_quote:")


def test_too_old_very_stale_event_names_age_and_bound():
    """An hour-old event is refused, and the reason carries BOTH numbers —
    an operator reading the row must be able to see the age and the bound
    without cross-referencing the config."""
    ts = iso(NOW - timedelta(seconds=3600))
    result = nbbo_capture.too_old(ts, 120.0, now=NOW)
    assert result.startswith("event_too_old_for_live_quote:")
    assert "3600" in result
    assert "120" in result


@pytest.mark.parametrize("bad_ts", [None, "", "not a date", 12345])
def test_too_old_unreadable_timestamp_fails_closed(bad_ts):
    """THE FAIL-CLOSED CASE. An unreadable timestamp must be refused, exactly,
    never silently treated as fresh. Treating an unparseable ts as fresh would
    attach today's market to an event of unknown age — the exact fabrication
    this instrument exists to prevent. The reason string is exact, not a
    prefix: this branch has no variable content to interpolate, so any
    deviation from the literal string is itself a defect."""
    result = nbbo_capture.too_old(bad_ts, 120.0, now=NOW)
    assert result == "event_timestamp_unreadable"


def test_too_old_future_event_beyond_bound_is_flagged():
    """A clock disagreement large enough to matter must be visible, not
    silently accepted as 'very fresh'."""
    ts = iso(NOW + timedelta(seconds=200))
    result = nbbo_capture.too_old(ts, 120.0, now=NOW)
    assert result.startswith("event_timestamp_in_the_future:")
    assert "200" in result


def test_too_old_naive_timestamp_is_treated_as_utc_not_crashed_on():
    """A timestamp with no timezone must be assumed UTC rather than raising —
    a capture loop that crashes on one malformed-but-parseable row takes the
    whole batch down with it."""
    naive_ts = (NOW - timedelta(seconds=1)).replace(tzinfo=None).isoformat()
    assert "+" not in naive_ts and "Z" not in naive_ts
    result = nbbo_capture.too_old(naive_ts, 120.0, now=NOW)
    assert result is None


# ==========================================================================
# 2. capturable
# ==========================================================================


def test_capturable_filters_to_three_types_sorted_by_seq():
    """Only OrderSubmitted / OrderPartiallyFilled / OrderFilled on an ``order``
    aggregate survive, and the result is sorted ascending by seq even though
    the input is newest-first. A same-typed event on a DIFFERENT aggregate
    type must be excluded despite matching the type string literally."""
    ts = iso(NOW)
    events = [
        filled(50, "o5", ts, "AAPL", "buy"),                 # capturable
        # Same TYPE STRING as OrderFilled, but not an order aggregate.
        _event(49, "not-an-order", "portfolio", "OrderFilled", ts, {}),
        approved(40, "o4", ts),                               # not capturable
        partial(30, "o3", ts),                                # capturable
        declined(20, "o2", ts),                                # not capturable
        submitted(10, "o1", ts),                               # capturable
        rejected(5, "o0", ts),                                 # not capturable
    ]
    out = nbbo_capture.capturable(events)

    seqs = [int(e["seq"]) for e in out]
    assert seqs == sorted(seqs), "capturable() must return ascending seq order"
    assert seqs == [10, 30, 50]
    # The non-order aggregate whose type literally reads "OrderFilled" must
    # not have leaked through.
    assert "not-an-order" not in {e["aggregate_id"] for e in out}
    assert {e["type"] for e in out} == {
        "OrderSubmitted", "OrderPartiallyFilled", "OrderFilled"}


def test_capturable_excludes_decision_events():
    """OrderProposed/OrderApproved/OrderDeclined/OrderRejected carry no price
    and no market to compare it against — they must never reach the batch."""
    ts = iso(NOW)
    events = [
        proposed(1, "o1", "AAPL", "buy", ts),
        approved(2, "o1", ts),
        declined(3, "o2", ts),
        rejected(4, "o3", ts),
    ]
    assert nbbo_capture.capturable(events) == []


# ==========================================================================
# 3. gap_below
# ==========================================================================


def _page(seqs):
    return [{"seq": s} for s in seqs]


def test_gap_below_short_page_is_never_a_gap():
    """A short page (fewer than EVENTS_PAGE rows) proves the endpoint reached
    back to the checkpoint on its own — even if its lowest seq is far above
    since_seq, that is the true state of the log, not a cut-off page."""
    since_seq = 100
    batch = _page([since_seq + 500, since_seq + 501, since_seq + 502])
    assert len(batch) < nbbo_capture.EVENTS_PAGE
    assert nbbo_capture.gap_below(batch, since_seq) is None


def test_gap_below_full_page_flush_with_checkpoint_is_no_gap():
    """A full page whose lowest seq is exactly since_seq+1 covers everything;
    nothing was cut off."""
    since_seq = 100
    seqs = [since_seq + 1 + i for i in range(nbbo_capture.EVENTS_PAGE)]
    batch = _page(seqs)
    assert len(batch) == nbbo_capture.EVENTS_PAGE
    assert min(s["seq"] for s in batch) == since_seq + 1
    assert nbbo_capture.gap_below(batch, since_seq) is None


def test_gap_below_full_page_with_gap_reports_missing_range():
    """A full page whose lowest seq is since_seq+5 proves seq+1..seq+4 were
    served to nobody — the gap detector must name exactly that range."""
    since_seq = 100
    seqs = [since_seq + 5 + i for i in range(nbbo_capture.EVENTS_PAGE)]
    batch = _page(seqs)
    assert len(batch) == nbbo_capture.EVENTS_PAGE
    assert min(s["seq"] for s in batch) == since_seq + 5
    assert nbbo_capture.gap_below(batch, since_seq) == (since_seq + 1, since_seq + 4)


def test_gap_below_boundary_lowest_seq_plus_one_vs_plus_two():
    """The boundary the gap arithmetic hinges on: lowest == since_seq+1 must
    read as 'no gap' and lowest == since_seq+2 must read as a one-seq gap.
    A fencepost error here would silently drop or duplicate exactly one
    event per gap."""
    since_seq = 100
    flush = _page([since_seq + 1 + i for i in range(nbbo_capture.EVENTS_PAGE)])
    off_by_one = _page([since_seq + 2 + i for i in range(nbbo_capture.EVENTS_PAGE)])
    assert nbbo_capture.gap_below(flush, since_seq) is None
    assert nbbo_capture.gap_below(off_by_one, since_seq) == (since_seq + 1, since_seq + 1)


# ==========================================================================
# 4. checkpoint round trip
# ==========================================================================


def test_read_checkpoint_missing_file_is_none_not_zero():
    """No checkpoint file means 'never run here'. A 0 would replay the whole
    log through a live-quote path, stamping today's market on every
    historical event — None is the only honest return here."""
    path = pathlib.Path("this_file_does_not_exist_at_all.seq")
    assert not path.exists()
    result = nbbo_capture.read_checkpoint(path)
    assert result is None


def test_read_checkpoint_unparseable_contents_are_none(tmp_path):
    """A checkpoint file with garbage inside must not crash the loop, and must
    not be silently treated as seq 0 either."""
    path = tmp_path / "checkpoint.seq"
    path.write_text("not a number", encoding="utf-8")
    assert nbbo_capture.read_checkpoint(path) is None


def test_read_checkpoint_empty_file_is_none(tmp_path):
    """An empty (e.g. truncated) checkpoint file is unreadable, not zero."""
    path = tmp_path / "checkpoint.seq"
    path.write_text("", encoding="utf-8")
    assert nbbo_capture.read_checkpoint(path) is None


def test_write_then_read_checkpoint_round_trips(tmp_path):
    """The whole point of the checkpoint: what is written is what comes back."""
    path = tmp_path / "checkpoint.seq"
    nbbo_capture.write_checkpoint(path, 4242)
    assert nbbo_capture.read_checkpoint(path) == 4242


def test_write_checkpoint_leaves_no_leftover_tmp_file(tmp_path):
    """The atomic-write pattern (write to .tmp, os.replace) must leave the
    directory with only the final file — a stray .tmp file is a leaked
    write that a later run could accidentally pick up."""
    path = tmp_path / "checkpoint.seq"
    nbbo_capture.write_checkpoint(path, 7)
    names = {p.name for p in tmp_path.iterdir()}
    assert names == {"checkpoint.seq"}
    assert not any(n.endswith(".tmp") for n in names)


def test_write_checkpoint_replaces_an_existing_value(tmp_path):
    """Writing over an existing checkpoint must replace it, not append or
    fail — a capture loop calls this once per tick against the same path."""
    path = tmp_path / "checkpoint.seq"
    nbbo_capture.write_checkpoint(path, 5)
    nbbo_capture.write_checkpoint(path, 9)
    assert nbbo_capture.read_checkpoint(path) == 9


# ==========================================================================
# 5. capture_batch — every path writes exactly one row per capturable event
# ==========================================================================


def test_capture_batch_every_path_writes_exactly_one_row():
    """THE CENTRAL INVARIANT. A batch mixing a fresh quotable fill, a stale
    event, a symbol-less order and a symbol the vendor doesn't return must
    produce exactly one result per capturable event — no branch may return
    without a row, because a dropped row and a fill measured at zero are
    indistinguishable in a coverage count."""
    fresh_ts = iso(NOW - timedelta(seconds=5))
    stale_ts = iso(NOW - timedelta(seconds=3600))

    events = [
        # A: fresh, symbol known (AAPL), vendor HAS a quote -> quotable.
        proposed(1, "oA", "AAPL", "buy", fresh_ts),
        filled(2, "oA", fresh_ts, "AAPL", "buy", avg_price="101.00"),
        # B: symbol known (MSFT) but the event itself is stale.
        proposed(3, "oB", "MSFT", "buy", stale_ts),
        filled(4, "oB", stale_ts, "MSFT", "buy"),
        # C: fresh, but no event in this order's lifecycle names a symbol.
        submitted(5, "oC", fresh_ts),
        # D: fresh, symbol known (ZORP) but absent from the vendor's response.
        proposed(6, "oD", "ZORP", "buy", fresh_ts),
        submitted(7, "oD", fresh_ts),
    ]
    store = FakeStore()
    quotes = FakeQuotes(by_symbol={"AAPL": {"bid": 100.0, "ask": 102.0,
                                            "bid_size": 1, "ask_size": 1,
                                            "quote_ts": fresh_ts}})

    results = nbbo_capture.capture_batch(
        events, store, quotes, run_id="r1", max_age_s=120.0, now=NOW)

    capturable_count = len(nbbo_capture.capturable(events))
    assert capturable_count == 4  # A-fill, B-fill, C-submitted, D-submitted
    assert len(results) == capturable_count

    by_order = {r["order_id"]: r for r in results}
    assert by_order["oA"]["quote_absent_reason"] is None
    assert by_order["oA"]["mid"] is not None

    assert by_order["oB"]["quote_absent_reason"].startswith(
        "event_too_old_for_live_quote:")

    assert by_order["oC"]["quote_absent_reason"].startswith("symbol_unknown:")

    assert by_order["oD"]["quote_absent_reason"] == "no_quote_returned_for:ZORP"


def test_capture_batch_vendor_failure_does_not_drop_the_batch():
    """A vendor outage must not silently vanish. Every event still gets a
    row, and the row names the exception class so a bad hour is visible as
    a bad hour rather than a coverage hole."""
    fresh_ts = iso(NOW - timedelta(seconds=5))
    events = [
        proposed(1, "oA", "AAPL", "buy", fresh_ts),
        filled(2, "oA", fresh_ts, "AAPL", "buy"),
        proposed(3, "oB", "MSFT", "buy", fresh_ts),
        submitted(4, "oB", fresh_ts),
    ]
    store = FakeStore()
    quotes = FakeQuotes(raises=RuntimeError("vendor timeout"))

    results = nbbo_capture.capture_batch(
        events, store, quotes, run_id="r1", max_age_s=120.0, now=NOW)

    capturable_count = len(nbbo_capture.capturable(events))
    assert len(results) == capturable_count
    for r in results:
        reason = r["quote_absent_reason"]
        assert reason.startswith("quote_fetch_failed:")
        assert "RuntimeError" in reason


def test_capture_batch_passes_order_symbol_and_side_through_to_partial_fill():
    """OrderPartiallyFilled carries neither symbol nor side in its own
    payload — those must come from the order's OrderProposed leg."""
    fresh_ts = iso(NOW - timedelta(seconds=5))
    events = [
        proposed(1, "oA", "DBA", "buy", fresh_ts),
        partial(2, "oA", fresh_ts, avg_price="18.41", cumulative_qty="2.0"),
    ]
    store = FakeStore()
    quotes = FakeQuotes(by_symbol={})

    results = nbbo_capture.capture_batch(
        events, store, quotes, run_id="r1", max_age_s=120.0, now=NOW)

    assert len(results) == 1
    assert store.calls[0]["symbol"] == "DBA"
    assert store.calls[0]["side"] == "buy"
    assert results[0]["order_id"] == "oA"


def test_capture_batch_dry_run_writes_nothing_but_still_computes():
    """A preview that cannot show whether the fill would be measured is not a
    preview: dry_run must return the same computed numbers a real run would
    produce, without ever calling the store."""
    fresh_ts = iso(NOW - timedelta(seconds=5))
    events = [
        proposed(1, "oA", "AAPL", "buy", fresh_ts),
        filled(2, "oA", fresh_ts, "AAPL", "buy", avg_price="101.00"),
    ]
    store = FakeStore()
    quotes = FakeQuotes(by_symbol={"AAPL": {"bid": 100.0, "ask": 102.0,
                                            "bid_size": 1, "ask_size": 1,
                                            "quote_ts": fresh_ts}})

    results = nbbo_capture.capture_batch(
        events, store, quotes, run_id="r1", max_age_s=120.0, now=NOW,
        dry_run=True)

    assert store.calls == []
    assert len(results) == 1
    row = results[0]
    assert row["dry_run"] is True
    assert row["mid"] is not None
    assert row["effective_spread_bps"] is not None


# ==========================================================================
# 6. run_loop
# ==========================================================================


@pytest.fixture
def no_sleep(monkeypatch):
    """Never actually sleep in a test loop."""
    monkeypatch.setattr(nbbo_capture.time, "sleep", lambda s: None)


def _stale_capturable_event(seq):
    """A minimal capturable event, deliberately dated far in the past so its
    staleness (real or fake clock) never matters to what these run_loop
    tests check: tick count, checkpoint advancement, and error handling."""
    return submitted(seq, f"o{seq}", "2020-01-01T00:00:00+00:00")


def test_run_loop_runs_max_ticks_and_advances_last_seq(tmp_path, monkeypatch, no_sleep):
    """A two-tick run must stop at exactly two ticks and report the highest
    seq it actually served, not the checkpoint it started from.

    NOTE: run_loop's own signature has no injectable clock — capture_batch
    is called internally without a ``now``, so staleness inside this test
    is judged against the real wall clock. The event used here is dated in
    2020 specifically so that fact never affects what this test asserts.
    """
    calls = []

    def fake_fetch(spine, since_seq, limit=nbbo_capture.EVENTS_PAGE, timeout=10.0):
        calls.append(since_seq)
        seq = since_seq + 1
        return [_stale_capturable_event(seq)]

    monkeypatch.setattr(nbbo_capture, "fetch_events", fake_fetch)

    checkpoint = tmp_path / "checkpoint.seq"
    summary = nbbo_capture.run_loop(
        spine="http://fake", store=FakeStore(), quotes=FakeQuotes(),
        run_id="r1", checkpoint=checkpoint, from_seq=10, poll_s=0.0,
        max_age_s=120.0, max_ticks=2, dry_run=False)

    assert summary["ticks"] == 2
    assert summary["last_seq"] == 12  # from_seq(10) +1 each tick, twice
    assert summary["last_seq"] == max(calls) + 1


def test_run_loop_writes_the_checkpoint(tmp_path, monkeypatch, no_sleep):
    """A live (non-dry) run must persist its progress so a restart resumes
    from where it left off rather than replaying or skipping."""

    def fake_fetch(spine, since_seq, limit=nbbo_capture.EVENTS_PAGE, timeout=10.0):
        seq = since_seq + 1
        return [_stale_capturable_event(seq)]

    monkeypatch.setattr(nbbo_capture, "fetch_events", fake_fetch)

    checkpoint = tmp_path / "checkpoint.seq"
    summary = nbbo_capture.run_loop(
        spine="http://fake", store=FakeStore(), quotes=FakeQuotes(),
        run_id="r1", checkpoint=checkpoint, from_seq=10, poll_s=0.0,
        max_age_s=120.0, max_ticks=2, dry_run=False)

    assert nbbo_capture.read_checkpoint(checkpoint) == summary["last_seq"]


def test_run_loop_with_explicit_from_seq_ignores_the_checkpoint_file(
        tmp_path, monkeypatch, no_sleep):
    """When from_seq is given explicitly, the loop must start there and must
    NOT consult a pre-existing checkpoint file for its starting point — the
    caller's explicit instruction outranks stale on-disk state."""
    checkpoint = tmp_path / "checkpoint.seq"
    # A checkpoint file already exists, deliberately pointing somewhere else.
    nbbo_capture.write_checkpoint(checkpoint, 999999)

    calls = []

    def fake_fetch(spine, since_seq, limit=nbbo_capture.EVENTS_PAGE, timeout=10.0):
        calls.append(since_seq)
        return [_stale_capturable_event(since_seq + 1)]

    monkeypatch.setattr(nbbo_capture, "fetch_events", fake_fetch)

    nbbo_capture.run_loop(
        spine="http://fake", store=FakeStore(), quotes=FakeQuotes(),
        run_id="r1", checkpoint=checkpoint, from_seq=10, poll_s=0.0,
        max_age_s=120.0, max_ticks=1, dry_run=False)

    assert calls[0] == 10, (
        "the first fetch must start from the explicit from_seq (10), not "
        "the stale checkpoint file (999999)")


def test_run_loop_survives_fetch_events_raising_every_tick(
        tmp_path, monkeypatch, no_sleep):
    """A spine outage must not crash the loop, must not fabricate rows, and
    must not move the checkpoint — there is nothing real to record."""

    def always_raises(spine, since_seq, limit=nbbo_capture.EVENTS_PAGE, timeout=10.0):
        raise ConnectionError("spine unreachable")

    monkeypatch.setattr(nbbo_capture, "fetch_events", always_raises)

    checkpoint = tmp_path / "checkpoint.seq"
    summary = nbbo_capture.run_loop(
        spine="http://fake", store=FakeStore(), quotes=FakeQuotes(),
        run_id="r1", checkpoint=checkpoint, from_seq=10, poll_s=0.0,
        max_age_s=120.0, max_ticks=2, dry_run=False)

    assert summary["spine_errors"] == 2
    assert summary["rows_written"] == 0
    assert not checkpoint.exists(), (
        "a loop that never saw a real batch must never create a checkpoint file")


def test_run_loop_dry_run_never_writes_the_checkpoint_file(
        tmp_path, monkeypatch, no_sleep):
    """dry_run must be a true preview: it may compute rows in memory but must
    never persist a checkpoint, since nothing was actually captured."""

    def fake_fetch(spine, since_seq, limit=nbbo_capture.EVENTS_PAGE, timeout=10.0):
        return [_stale_capturable_event(since_seq + 1)]

    monkeypatch.setattr(nbbo_capture, "fetch_events", fake_fetch)

    checkpoint = tmp_path / "checkpoint.seq"
    nbbo_capture.run_loop(
        spine="http://fake", store=FakeStore(), quotes=FakeQuotes(),
        run_id="r1", checkpoint=checkpoint, from_seq=10, poll_s=0.0,
        max_age_s=120.0, max_ticks=2, dry_run=True)

    assert not checkpoint.exists()


# ==========================================================================
# 7. load_env — never called at module scope
# ==========================================================================


def test_load_env_not_called_at_import_time():
    """A module-scope load_dotenv()/load_env() call leaks the operator's
    real FUND_STORE/FUND_MODE into every test process that imports this
    file — which is exactly how one merge night produced 109 false reds.
    This is a SOURCE-LEVEL guard (parsed via ast), not a behavioural one: it
    must catch the mistake even if nothing observable happens to change in
    this particular test environment."""
    source = pathlib.Path(nbbo_capture.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def module_level_call_names(node):
        names = []
        for child in ast.iter_child_nodes(node):
            # A def/class body is a NEW scope: code inside it runs only when
            # called, never at import time. Do not descend into it.
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                  ast.ClassDef)):
                continue
            if isinstance(child, ast.Call):
                f = child.func
                if isinstance(f, ast.Name):
                    names.append(f.id)
                elif isinstance(f, ast.Attribute):
                    names.append(f.attr)
            names.extend(module_level_call_names(child))
        return names

    called_at_module_scope = module_level_call_names(tree)
    assert "load_dotenv" not in called_at_module_scope
    assert "load_env" not in called_at_module_scope
