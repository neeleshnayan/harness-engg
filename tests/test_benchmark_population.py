"""WHICH universe the benchmark was built from, and what it cannot fix.

THE DEFECT THIS FILE GUARDS (measured 2026-08-17, re-confirmed by the CFO
2026-08-23 and ticketed 739b5ac9): the belt's benchmark holds the strategy's
declared UNIVERSE, and every universe this fund screens is screened with
``AssetStatus.ACTIVE`` — names alive TODAY. A 2024 backtest is therefore graded
against the names that made it to 2026. The bias is measured at -6.90pp +/-
2.40 over 20 months (docs/SURVIVORSHIP_2026-08-17.md, n=26) and it runs in the
KILL direction, because the vanished names GAINED less than the survivors
rather than dying. The correction was written (``asof.membership``) and had
exactly one consumer in the repo — a capture script. Nothing in the belt read
it.

The half that can be closed is closed here (look-ahead listing). The half that
cannot is LABELLED, loudly, in the payload the gate stores: measured on this
machine 2026-08-23, ``fund_delisted`` holds 23,307 names, 0 with a measured ADV
and 5 with any bar in ``fund_bars`` — so the dead cannot be priced and cannot
be put into any bar. Counting them is not holding them.

The rule these tests exist to enforce: a benchmark that cannot be built
point-in-time must SAY SO IN ITS OWN PAYLOAD. Silently serving the biased
number is the failure; serving it with a label is the honest state of the
evidence.
"""

from __future__ import annotations

from app.fund.asof import population_report, read_population
from app.fund.gate import evaluate
from app.fund.leanrunner import LeanRunner


class _Bars:
    def __init__(self, dates, closes, source="test"):
        self.dates = list(dates)
        self.closes = list(closes)
        self.source = source


DATES = [f"2024-01-{d:02d}" for d in range(1, 11)]


def _result(symbols):
    return {
        "equity_dates": list(DATES),
        "equity_curve": [1000.0 + 10 * i for i in range(len(DATES))],
        "orders": [{"symbol": s} for s in symbols],
    }


def _serve_all(monkeypatch):
    import app.fund.marketdata as md
    monkeypatch.setattr(
        md, "fetch_daily_bars",
        lambda symbol, *a, **k: _Bars(DATES, [100.0 + i for i in range(10)]))


# --- (a) the survivor-only path is LABELLED, never silent -------------------


def test_a_bar_with_no_as_of_snapshot_is_labelled_survivor_only(monkeypatch):
    """The old behaviour still runs; what changed is that it now confesses."""
    _serve_all(monkeypatch)
    result = _result(("AAA", "BBB"))
    LeanRunner._add_benchmark(
        result, population=population_report(["AAA", "BBB"], DATES[0],
                                             listed=None, priced_delisted=set()))

    pop = result["benchmark_population"]
    assert pop["basis"] == "survivor_only"
    assert pop["point_in_time"] is False
    assert pop["listing_asof_applied"] is False
    assert pop["survivorship_corrected"] is False
    assert "no as-of listing snapshot exists" in pop["reason"]
    # And the comparison is still made — an absent benchmark helps nobody.
    assert result["benchmark_return_pct"] is not None


def test_the_reason_names_the_snapshots_that_do_exist():
    """A gap a reader can act on. 'Unavailable' with no dates is atmosphere."""
    out = population_report(["AAA"], "2024-02-26", listed=None,
                            snapshots=["2025-01-01"])
    assert "2025-01-01" in out["reason"]
    empty = population_report(["AAA"], "2024-02-26", listed=None, snapshots=[])
    assert "no snapshots at all" in empty["reason"]


def test_an_unreadable_register_is_unknown_and_never_clean(monkeypatch):
    """Unreadable is not unchanged. Measured shape, not a reasoned one.

    ``read_population`` is pointed at a DSN nothing answers; the report must
    come back UNKNOWN with the failure named, and must NOT come back saying the
    population needed no correction.
    """
    out = read_population(["AAA", "BBB"], "2024-01-01",
                          dsn_str="postgresql://nobody@127.0.0.1:1/none")
    assert out["basis"] == "survivor_only"
    assert out["listing_asof_applied"] is False
    assert out["point_in_time"] is False
    assert "could not be read" in out["reason"]
    assert out["delisted_priceable"] is None, "unknown was rendered as a number"
    assert "UNKNOWN" in out["survivorship_note"]


# --- (b) where a snapshot EXISTS, the population follows it -----------------


CS = {"AAA": "CS", "BBB": "CS"}


def test_a_name_not_listed_on_the_start_date_is_dropped_and_named(monkeypatch):
    """Look-ahead listing: the half this fund's data CAN close."""
    _serve_all(monkeypatch)
    result = _result(("AAA", "BBB"))
    LeanRunner._add_benchmark(
        result,
        population=population_report(["AAA", "BBB"], DATES[0], listed={"AAA"},
                                     priced_delisted=set(),
                                     snapshot_types={"CS"}, types=CS))

    pop = result["benchmark_population"]
    assert pop["basis"] == "listing_asof"
    assert pop["listing_asof_applied"] is True
    assert pop["population"] == ["AAA"]
    assert pop["excluded_not_listed"] == ["BBB"]
    assert pop["unjudgeable_by_snapshot"] == []
    # The bar itself must be the ONE name, not the two it wanted.
    assert result["benchmark_basket"] == ["AAA"]
    assert result["benchmark_kind"] == "single"


def test_the_population_is_READ_from_the_snapshot_not_copied(monkeypatch):
    """MOVE the listed set and the bar must move with it.

    An assertion that the population equals the wanted names cannot tell a read
    from a hardcoded agreement. So the same two names are judged against two
    different snapshots and the basket must differ.
    """
    _serve_all(monkeypatch)
    baskets = []
    for listed in ({"AAA"}, {"BBB"}):
        result = _result(("AAA", "BBB"))
        LeanRunner._add_benchmark(
            result, population=population_report(["AAA", "BBB"], DATES[0],
                                                 listed=listed,
                                                 priced_delisted=set(),
                                                 snapshot_types={"CS"},
                                                 types=CS))
        baskets.append(result["benchmark_basket"])
    assert baskets == [["AAA"], ["BBB"]]


def test_a_snapshot_that_does_not_cover_a_name_may_not_condemn_it(monkeypatch):
    """THE ETF TRAP — the defect the naive wiring of this ticket would ship.

    MEASURED against the live register 2026-08-23: the only snapshot
    (2025-01-01) holds types CS and ADRC only, because ``snapshot()`` captures
    exactly those two; ``fund_ticker_reference`` covers the same two, so SPY,
    TLT, GLD and IWM appear in NEITHER. A plain ``wanted & membership(as_of)``
    — which is what the ticket asked for in one line — drops every ETF as "not
    listed". Verified against the live register before the type rule existed:
    the population for [SPY, TLT, SRPT] came back as ["SRPT"].

    Absence from a snapshot that cannot see your type is not evidence.
    """
    _serve_all(monkeypatch)
    result = _result(("AAA", "BBB"))
    LeanRunner._add_benchmark(
        result,
        population=population_report(
            ["AAA", "BBB"], DATES[0], listed={"AAA"}, priced_delisted=set(),
            # BBB is an ETF: absent from the snapshot AND absent from the
            # reference, so its type is unknown to us.
            snapshot_types={"CS", "ADRC"}, types={"AAA": "CS"}))

    pop = result["benchmark_population"]
    assert pop["population"] == ["AAA", "BBB"], "an ETF was condemned by a CS-only snapshot"
    assert pop["excluded_not_listed"] == []
    assert pop["unjudgeable_by_snapshot"] == ["BBB"]
    assert "not evidence of not being listed" in pop["unjudgeable_note"]
    assert result["benchmark_basket"] == ["AAA", "BBB"]


def test_a_snapshot_with_unknown_type_coverage_judges_nobody():
    """Coverage we cannot read is coverage we cannot rely on."""
    out = population_report(["AAA", "BBB"], "2024-01-01", listed={"AAA"},
                            priced_delisted=set(), snapshot_types=None,
                            types=CS)
    assert out["population"] == ["AAA", "BBB"]
    assert out["basis"] == "survivor_only"
    assert out["listing_asof_applied"] is False
    assert "coverage is UNKNOWN" in out["reason"]


# --- (c) an unbuildable population REFUSES, it does not degrade -------------


def test_a_population_with_nothing_listed_refuses_the_benchmark(monkeypatch):
    """The one branch that must never fall back to the survivor screen."""
    _serve_all(monkeypatch)
    result = _result(("AAA", "BBB"))
    LeanRunner._add_benchmark(
        result, population=population_report(["AAA", "BBB"], DATES[0],
                                             listed={"ZZZ"},
                                             priced_delisted=set(),
                                             snapshot_types={"CS"}, types=CS))

    assert result["benchmark_population"]["usable"] is False
    assert "no population to hold" in result["benchmark_unavailable"]
    assert "benchmark_return_pct" not in result, (
        "a bar was served from a population the register rejected")
    assert "benchmark_curve" not in result


# --- the DEFAULT call site, not just the injected one -----------------------


def test_the_default_path_labels_the_bar_without_being_asked(monkeypatch):
    """Driven through the real call site with no ``population=`` argument.

    A helper can be flawless and uncalled (D17). ``_add_benchmark`` is what the
    belt invokes, and it must reach the reader on its own.
    """
    _serve_all(monkeypatch)
    seen = {}

    def reader(wanted, as_of):
        seen["wanted"], seen["as_of"] = list(wanted), as_of
        return population_report(wanted, as_of, listed=None, priced_delisted=set())

    import app.fund.leanrunner as lr
    monkeypatch.setattr(lr, "_population_report", reader)
    result = _result(("AAA", "BBB"))
    LeanRunner._add_benchmark(result)

    assert seen["as_of"] == DATES[0], "the reader was asked about the wrong date"
    assert seen["wanted"] == ["AAA", "BBB"]
    assert result["benchmark_population"]["basis"] == "survivor_only"


def test_the_engine_single_name_bar_is_labelled_too(monkeypatch):
    """The one early return that keeps a benchmark. No bar leaves unlabelled."""
    _serve_all(monkeypatch)
    result = _result(("AAA",))
    result["benchmark_curve"] = [100.0 + i for i in range(10)]
    result["benchmark_return_pct"] = 9.0
    LeanRunner._add_benchmark(result)

    pop = result["benchmark_population"]
    assert pop["basis"] == "engine_single_name"
    assert pop["population"] == ["AAA"]
    assert pop["point_in_time"] is False
    # the engine's own curve survived — this branch must not recompute
    assert result["benchmark_return_pct"] == 9.0


# --- (d) survivorship is never claimed as corrected -------------------------


def test_survivorship_is_open_in_both_branches_and_says_why():
    """Counting the dead is not holding them.

    Measured on this machine 2026-08-23: 23,307 rows in ``fund_delisted``, 5 of
    them with any bar in ``fund_bars``. A membership read can remove a name; it
    cannot add one that has no prices.
    """
    for listed in (None, {"AAA", "BBB"}):
        out = population_report(["AAA", "BBB"], "2024-01-01", listed=listed,
                                priced_delisted=set())
        assert out["survivorship_corrected"] is False
        assert out["point_in_time"] is False
        assert "cannot be put into any benchmark" in out["survivorship_note"]
        assert "KILL" in out["survivorship_direction"]

    priced = population_report(["AAA"], "2024-01-01", listed=None,
                               priced_delisted={"DEAD1", "DEAD2"})
    assert priced["delisted_priceable"] == 2
    assert priced["survivorship_corrected"] is False, (
        "priceable dead names are not the same as a corrected bar — no as-of "
        "BAND screen exists to say which of them belonged")


# --- (e) the verdict records which population it judged ---------------------


def test_the_gate_records_the_population_label():
    v = evaluate({"total_return_pct": 20.0, "benchmark_return_pct": 10.0,
                  "benchmark_population": {"basis": "listing_asof",
                                           "point_in_time": False,
                                           "listing_asof_applied": True,
                                           "survivorship_corrected": False,
                                           "as_of": "2024-01-01",
                                           "population": ["AAA", "BBB"]}})
    label = v["checks"]["benchmark_population"]
    assert label["basis"] == "listing_asof"
    assert label["listing_asof_applied"] is True
    assert label["survivorship_corrected"] is False
    assert label["names"] == 2


def test_an_unlabelled_benchmark_is_reported_absent_not_assumed_clean():
    """Every verdict stored before this shipped is in this branch."""
    v = evaluate({"total_return_pct": 20.0, "benchmark_return_pct": 10.0})
    label = v["checks"]["benchmark_population"]
    assert label["basis"] is None
    assert "unlabelled is not corrected" in label["note"]


def test_no_benchmark_means_no_population_label():
    """A label on a comparison that was never made would be decoration."""
    v = evaluate({"total_return_pct": 20.0})
    assert "benchmark_population" not in v["checks"]
