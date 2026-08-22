"""Candidate-scoped bar snapshots.

Every test here is written against a SPECIFIC way this module could quietly
corrupt the belt's measurements, because a bar cache that returns *nearly* the
right series is far more dangerous than one that is merely slow: it changes the
number the gate judges and leaves no trace.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pytest

from app.fund import barcache


class _FakeBars:
    def __init__(self, symbol, dates, closes, source="fake", volumes=None):
        self.symbol = symbol
        self.dates = list(dates)
        self.closes = list(closes)
        self.source = source
        self.volumes = list(volumes) if volumes else None


def _days(n, start_day=1):
    """n consecutive ISO dates in 2024-01, as a cheap deterministic calendar."""
    return [f"2024-01-{d:02d}" for d in range(start_day, start_day + n)]


def _fetcher(table):
    """A fetcher over a {symbol: (dates, closes)} table, recording its calls."""
    calls = []

    def fetch(symbol, lookback_days=365, start=None, end=None):
        calls.append((symbol, lookback_days, start, end))
        if symbol not in table:
            raise ValueError(f"no bars for {symbol}")
        dates, closes = table[symbol]
        return _FakeBars(symbol, dates, closes)

    fetch.calls = calls
    return fetch


@pytest.fixture(autouse=True)
def _no_leaked_snapshot():
    """No test may leave a snapshot active — a leak would silently pin the next."""
    yield
    assert barcache.active() is None, "a test leaked an active snapshot"


# --- the fetch happens once ------------------------------------------------


def test_prefetch_fetches_each_leg_exactly_once():
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5]),
                  "TLT": (_days(5), [9, 8, 7, 6, 5])})
    snap = barcache.prefetch(["SPY", "TLT", "SPY"], candidate="c1",
                             lookback_days=700, fetcher=f)
    assert sorted(s for s, *_ in f.calls) == ["SPY", "TLT"]
    assert len(f.calls) == 2
    assert set(snap.legs) == {"SPY", "TLT"}


def test_every_container_of_one_candidate_is_served_identical_bytes():
    """The reason this module exists (ticket 0178d2e8).

    Twenty-two containers of one candidate must not be able to cover twenty-two
    slightly different windows. One fetch, one answer, however many askers.
    """
    f = _fetcher({"SPY": (_days(9), [1, 2, 3, 4, 5, 6, 7, 8, 9])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with barcache.activate(snap):
        served = [barcache.serve("SPY", lookback_days=700) for _ in range(22)]
    assert len(f.calls) == 1, "a second fetch means the containers can disagree"
    first = (served[0].dates, served[0].closes)
    for leg in served[1:]:
        assert (leg.dates, leg.closes) == first


# --- the cache must never invent a window ----------------------------------


def test_exact_shape_is_served_whole_not_resliced():
    """Guards a defect found in this module's own first draft.

    The first implementation re-sliced a trailing-lookback request to "N days
    before taken_at". Vendors do not interpret a lookback as a calendar cut, so
    a SPY leg pinned at lookback_days=2000 (2,000 bars from 2018-09-06) came
    back as 1,377 bars from 2021-03-01 — a truncation invented by the cache,
    which is the Entry 20 defect wearing this module's clothes.
    """
    # A leg whose history reaches much further back than `lookback_days` of
    # calendar days would suggest — exactly the real SPY/yahoo case.
    dates = [f"2018-{m:02d}-01" for m in range(1, 13)] + _days(10)
    f = _fetcher({"SPY": (dates, list(range(len(dates))))})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=2000, fetcher=f)
    with barcache.activate(snap):
        got = barcache.serve("SPY", lookback_days=2000)
    assert got is not None
    assert got.dates == dates, "the pinned leg was re-sliced instead of served whole"
    assert got.closes == list(range(len(dates)))


def test_a_different_lookback_misses_rather_than_approximating():
    f = _fetcher({"SPY": (_days(10), list(range(10)))})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=2000, fetcher=f)
    with barcache.activate(snap):
        assert barcache.serve("SPY", lookback_days=700) is None
    assert snap.misses and snap.misses[0]["symbol"] == "SPY"
    assert "700" in snap.misses[0]["why"]


def test_window_starting_before_the_pinned_leg_is_a_miss():
    """A partial overlap must never be served as if it were the whole window."""
    f = _fetcher({"SPY": (_days(10, start_day=10), list(range(10)))})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with barcache.activate(snap):
        assert barcache.serve("SPY", start="2024-01-01", end="2024-01-15") is None
        assert barcache.serve("SPY", start="2024-01-12", end="2024-01-31") is None


def test_slice_of_an_explicit_window_is_exact():
    dates, closes = _days(10), [float(i) for i in range(10)]
    f = _fetcher({"SPY": (dates, closes)})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with barcache.activate(snap):
        got = barcache.serve("SPY", start="2024-01-03", end="2024-01-06")
    assert got.dates == ["2024-01-03", "2024-01-04", "2024-01-05", "2024-01-06"]
    assert got.closes == [2.0, 3.0, 4.0, 5.0]


# --- fail open, and loud ---------------------------------------------------


def test_a_miss_is_recorded_and_named_never_silent():
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with barcache.activate(snap):
        assert barcache.serve("QQQ", lookback_days=700) is None
    assert len(snap.misses) == 1
    miss = snap.misses[0]
    assert miss["symbol"] == "QQQ"
    assert miss["why"]
    rep = snap.report()
    assert rep["miss_count"] == 1
    assert rep["uniform_data_path"] is False, (
        "a candidate that fell back mid-run must not report a uniform data path")


def test_a_miss_logs_a_warning_naming_the_leg(caplog):
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with caplog.at_level("WARNING"):
        with barcache.activate(snap):
            barcache.serve("QQQ", lookback_days=700)
    named = [r for r in caplog.records if "QQQ" in r.getMessage()]
    assert named, "the miss did not name the leg"
    assert named[0].levelname == "WARNING"


def test_an_unfetchable_leg_is_recorded_absent_not_omitted():
    """Absence is never zero: a universe that half-loaded must say so."""
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY", "NOPE"], candidate="c1",
                             lookback_days=700, fetcher=f)
    assert set(snap.legs) == {"SPY"}
    assert "NOPE" in snap.unavailable
    assert snap.report()["uniform_data_path"] is False


def test_a_leg_whose_dates_and_closes_disagree_is_refused():
    def fetch(symbol, lookback_days=365, start=None, end=None):
        return _FakeBars(symbol, _days(5), [1, 2, 3])   # 5 dates, 3 closes

    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700,
                             fetcher=fetch)
    assert "SPY" not in snap.legs
    assert "not a series" in snap.unavailable["SPY"]


# --- the boundary that protects the fund's money ---------------------------


def test_nothing_is_served_when_no_snapshot_is_active():
    assert barcache.active() is None
    assert barcache.serve("SPY", lookback_days=700) is None


def test_activation_is_restored_even_when_the_block_raises():
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    with pytest.raises(RuntimeError):
        with barcache.activate(snap):
            raise RuntimeError("boom")
    assert barcache.active() is None, (
        "a leaked snapshot would pin the next candidate's data silently")


def test_nested_activation_restores_the_outer_snapshot():
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    a = barcache.prefetch(["SPY"], candidate="a", lookback_days=700, fetcher=f)
    b = barcache.prefetch(["SPY"], candidate="b", lookback_days=700, fetcher=f)
    with barcache.activate(a):
        with barcache.activate(b):
            assert barcache.active().candidate == "b"
        assert barcache.active().candidate == "a"


def test_marketdata_fetch_daily_bars_is_not_wrapped_by_the_cache():
    """THE LOAD-BEARING BOUNDARY.

    The fund's marks, NAV, risk engine, stress and correlation all call
    ``fetch_daily_bars`` IN-PROCESS. If this module ever wraps or patches that
    function, a pinned bar could reach the fund's own book — which is the one
    thing this design is built to make structurally impossible. Nothing is
    served unless a call site explicitly asked.
    """
    from app.fund import marketdata

    f = _fetcher({"SPY": (_days(5), [1.0, 2.0, 3.0, 4.0, 5.0])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    before = marketdata.fetch_daily_bars
    with barcache.activate(snap):
        assert marketdata.fetch_daily_bars is before, (
            "fetch_daily_bars was replaced while a snapshot was active")
    assert marketdata.fetch_daily_bars is before


def test_the_consult_sites_are_exactly_the_two_belt_side_ones():
    """Pins WHO may read a snapshot.

    If a future diff adds a third consult site, this fails and the author has
    to say why that site is belt-side. The list is the safety argument: a
    snapshot is safe because of who reads it, not because of how it is scoped.

    Two, not three: ``_add_capacity`` asks for a 120-day window that no pinned
    leg can match, so consulting there was a guaranteed miss that marked every
    candidate's data path non-uniform. It was removed rather than special-cased.
    """
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    sites = []
    for path in sorted(root.joinpath("app").rglob("*.py")):
        if path.name == "barcache.py":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for i, line in enumerate(text.splitlines(), 1):
            if "barcache.serve(" in line:
                sites.append(f"{path.relative_to(root).as_posix()}:{i}")
    assert len(sites) == 2, f"unexpected barcache.serve call sites: {sites}"
    assert any(s.startswith("app/api/v1/fund.py") for s in sites), (
        "the endpoint that serves LEAN containers no longer consults the snapshot")
    assert sum(s.startswith("app/fund/leanrunner.py") for s in sites) == 1, (
        "the benchmark leg no longer consults the snapshot")


# --- staleness -------------------------------------------------------------


def test_an_expired_snapshot_stops_serving():
    """A leaked activation must not keep serving old bars forever."""
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    snap.taken_at = snap.taken_at - timedelta(seconds=barcache.MAX_AGE_S + 60)
    with barcache.activate(snap):
        assert barcache.serve("SPY", lookback_days=700) is None
    assert "past the" in snap.misses[0]["why"]


# --- checkpointing ---------------------------------------------------------


def test_snapshot_round_trips_through_disk(tmp_path):
    f = _fetcher({"SPY": (_days(5), [1.5, 2.5, 3.5, 4.5, 5.5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    path = snap.save(tmp_path / "snap.json")
    back = barcache.BarSnapshot.load(path)
    assert back.candidate == "c1"
    assert back.taken_at == snap.taken_at
    with barcache.activate(back):
        got = barcache.serve("SPY", lookback_days=700)
    assert got.dates == snap.legs["SPY"].dates
    assert got.closes == snap.legs["SPY"].closes


def test_save_is_atomic_leaving_no_partial_file(tmp_path):
    f = _fetcher({"SPY": (_days(5), [1, 2, 3, 4, 5])})
    snap = barcache.prefetch(["SPY"], candidate="c1", lookback_days=700, fetcher=f)
    path = snap.save(tmp_path / "snap.json")
    assert json.loads(path.read_text(encoding="utf-8"))["candidate"] == "c1"
    assert not list(tmp_path.glob("*.tmp"))
