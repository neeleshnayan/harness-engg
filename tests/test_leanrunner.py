"""LEAN runner: jobs must be honest about every state the engine can reach."""

import json
import sys
import threading
import time
from pathlib import Path

import pytest

from app.fund.leanrunner import LeanError, LeanRunner

ALGO = """
from AlgorithmImports import *
class SmokeAlgo(QCAlgorithm):
    def initialize(self):
        self.set_cash(1000)
"""

#: Fake docker: writes a plausible LEAN results file into the mounted results
#: dir (extracted from the `-v host:/Results` argument), then exits 0.
FAKE_OK = r"""
import json, sys
res = next(a.rsplit(":", 1)[0] for a in sys.argv if a.endswith(":/Results"))
json.dump({
    "statistics": {"Net Profit": "12.5%", "Sharpe Ratio": "1.4",
                   "Drawdown": "8.0%", "Total Orders": "6"},
    "charts": {"Strategy Equity": {"series": {"Equity": {"values":
        [[1, 1000.0], [2, 1050.0], [3, 1125.0]]}}}},
}, open(res + "/SmokeAlgo.json", "w"))
print("engine ok")
"""

#: Same as FAKE_OK, but also dumps its own argv beside the results so a test can
#: assert on the flags the container was actually given.
FAKE_RECORDING = r"""
import json, sys
res = next(a.rsplit(":", 1)[0] for a in sys.argv if a.endswith(":/Results"))
json.dump(sys.argv, open(res + "/argv.json", "w"))
json.dump({
    "statistics": {"Net Profit": "12.5%", "Sharpe Ratio": "1.4",
                   "Drawdown": "8.0%", "Total Orders": "6"},
    "charts": {"Strategy Equity": {"series": {"Equity": {"values":
        [[1, 1000.0], [2, 1050.0], [3, 1125.0]]}}}},
}, open(res + "/SmokeAlgo.json", "w"))
print("engine ok")
"""

FAKE_FAIL = r"""
import sys
sys.stderr.write("Algorithm.Initialize() blew up: division by zero\n")
sys.exit(1)
"""


def _runner(tmp_path: Path, fake_script: str) -> LeanRunner:
    script = tmp_path / "fake_docker.py"
    script.write_text(fake_script, encoding="utf-8")
    return LeanRunner(workspace=tmp_path / "ws",
                      docker_cmd=[sys.executable, str(script)])


def _docker_argv(tmp_path: Path, job_id: str) -> list[str]:
    """The argv the fake engine was invoked with, for flag assertions."""
    return json.loads(
        (tmp_path / "ws" / "results" / job_id / "argv.json").read_text())


def _wait(r: LeanRunner, job_id: str, timeout=15.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        j = r.job(job_id)
        if j["state"] in ("done", "failed"):
            return j
        time.sleep(0.05)
    raise AssertionError("job never finished")


def test_algorithm_lifecycle(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    saved = r.save_algorithm("smoke", ALGO)
    assert saved["class_name"] == "SmokeAlgo"
    assert [a["name"] for a in r.list_algorithms()] == ["smoke"]
    assert "QCAlgorithm" in r.get_algorithm("smoke")["code"]


def test_rejects_code_without_algorithm_class(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    with pytest.raises(LeanError):
        r.save_algorithm("bad", "print('hello')")
    with pytest.raises(LeanError):
        r.save_algorithm("Bad Name!", ALGO)


def test_backtest_happy_path_parses_results(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    r.save_algorithm("smoke", ALGO)
    job_id = r.submit_backtest("smoke")["job_id"]
    j = _wait(r, job_id)
    assert j["state"] == "done", j.get("error")
    res = j["result"]
    assert res["engine"] == "lean"
    assert res["total_return_pct"] == pytest.approx(12.5)
    assert res["sharpe"] == pytest.approx(1.4)
    assert res["equity_curve"] == [1000.0, 1050.0, 1125.0]


def test_engine_failure_is_a_failed_job_with_the_real_error(tmp_path):
    r = _runner(tmp_path, FAKE_FAIL)
    r.save_algorithm("smoke", ALGO)
    job_id = r.submit_backtest("smoke")["job_id"]
    j = _wait(r, job_id)
    assert j["state"] == "failed"
    assert "division by zero" in j["error"]


def test_an_unknown_job_says_there_is_no_record_of_it(tmp_path):
    """Jobs are now mirrored to Postgres, so "does not survive a restart" is no
    longer true and must not be what an operator is told. The honest message is
    that nothing knows about this id — in memory OR in the ledger."""
    r = _runner(tmp_path, FAKE_OK)
    with pytest.raises(LeanError, match="no record of it"):
        r.job("nope")


# --- dates, orders and the benchmark ---------------------------------------
#
# The Lab's analytics need more than a curve: "is this alpha or beta" regresses
# the equity series against factor returns BY DATE, and "did it beat owning the
# thing" needs a benchmark. These pin the shapes those questions depend on.

def _doc_with(charts=None, orders=None, stats=None):
    return {
        "statistics": stats or {"Net Profit": "4.36%", "Sharpe Ratio": "0.5"},
        "charts": charts or {},
        "orders": orders or {},
    }


def _write(tmp_path, doc):
    d = tmp_path / "res"
    d.mkdir(parents=True, exist_ok=True)
    (d / "Algo.json").write_text(json.dumps(doc), encoding="utf-8")
    return d


def test_equity_curve_carries_its_dates(tmp_path):
    charts = {"Strategy Equity": {"series": {"Equity": {"values": [
        [1748750400, 2000.0], [1748836800, 2010.0], [1748923200, 2025.0],
    ]}}}}
    res = LeanRunner._parse_results(_write(tmp_path, _doc_with(charts)))
    assert res["equity_curve"] == [2000.0, 2010.0, 2025.0]
    assert res["equity_dates"] == ["2025-06-01", "2025-06-02", "2025-06-03"]


def test_ohlc_points_use_the_close(tmp_path):
    charts = {"Strategy Equity": {"series": {"Equity": {"values": [
        [1748750400, 1.0, 9.0, 0.5, 2000.0], [1748836800, 1.0, 9.0, 0.5, 2100.0],
    ]}}}}
    res = LeanRunner._parse_results(_write(tmp_path, _doc_with(charts)))
    assert res["equity_curve"] == [2000.0, 2100.0]


def test_a_zeroed_benchmark_is_dropped_not_plotted(tmp_path):
    """LEAN emits zeros when it cannot benchmark custom data. An unknown is
    not a flat line, and must never be labelled 'buy & hold'."""
    charts = {
        "Strategy Equity": {"series": {"Equity": {"values": [
            [1748750400, 2000.0], [1748836800, 2100.0]]}}},
        "Benchmark": {"series": {"Benchmark": {"values": [
            [1748750400, 0.0], [1748836800, 0.0]]}}},
    }
    res = LeanRunner._parse_results(_write(tmp_path, _doc_with(charts)))
    assert res["benchmark_curve"] == []
    assert res["benchmark_return_pct"] is None


def test_only_filled_orders_are_reported(tmp_path):
    orders = {
        "1": {"status": 3, "direction": 0, "quantity": 3.0, "price": 611.05,
              "value": 1833.15, "time": "2025-06-30T04:00:00Z",
              "symbol": {"value": "SPY"}},
        "2": {"status": 5, "direction": 1, "quantity": 3.0, "price": 620.0,
              "value": 1860.0, "time": "2025-07-30T04:00:00Z",
              "symbol": {"value": "SPY"}},
    }
    res = LeanRunner._parse_results(_write(tmp_path, _doc_with(orders=orders)))
    assert len(res["orders"]) == 1
    assert res["orders"][0] == {
        "time": "2025-06-30T04:00:00Z", "symbol": "SPY", "side": "buy",
        "qty": 3.0, "price": 611.05, "value": 1833.15,
    }


def test_downsampling_keeps_dates_in_step_and_keeps_endpoints(tmp_path):
    vals = [[1748750400 + i * 86400, float(i)] for i in range(1000)]
    charts = {"Strategy Equity": {"series": {"Equity": {"values": vals}}}}
    res = LeanRunner._parse_results(_write(tmp_path, _doc_with(charts)))
    assert len(res["equity_curve"]) == 400
    assert len(res["equity_dates"]) == 400
    assert res["equity_curve"][0] == 0.0
    assert res["equity_curve"][-1] == 999.0        # the last point survives


def test_benchmark_is_absent_when_bars_cannot_be_fetched(monkeypatch):
    """Best-effort: an unreachable data source leaves the comparison absent."""
    import app.fund.marketdata as md

    def boom(*a, **k):
        raise RuntimeError("no data")

    monkeypatch.setattr(md, "fetch_daily_bars", boom)
    res = {"equity_curve": [2000.0, 2100.0],
           "equity_dates": ["2025-06-01", "2025-06-02"],
           "orders": [{"symbol": "SPY"}], "benchmark_curve": []}
    LeanRunner._add_benchmark(res)
    assert res["benchmark_curve"] == []
    assert res.get("benchmark_return_pct") is None


def test_benchmark_normalises_to_the_strategys_starting_equity(monkeypatch):
    import app.fund.marketdata as md

    class Bars:
        closes = [100.0, 110.0, 120.0]
        dates = ["2025-06-01", "2025-06-02", "2025-06-03"]
        source = "test"

    monkeypatch.setattr(md, "fetch_daily_bars", lambda *a, **k: Bars())
    res = {"equity_curve": [2000.0, 2050.0],
           "equity_dates": ["2025-06-01", "2025-06-03"],
           "orders": [{"symbol": "SPY"}, {"symbol": "SPY"}, {"symbol": "QQQ"}],
           "benchmark_curve": []}
    LeanRunner._add_benchmark(res)
    # The curve starts where the strategy started so both are readable on one
    # axis: same money, different decisions.
    #
    # CONTRACT CHANGED (deliberately): this used to pick the MOST-TRADED symbol
    # and measure against that alone. For a strategy that trades several names
    # that bar is close to meaningless — it flatters a rule that dodged the
    # worst name and punishes one that held the best — so a multi-name strategy
    # is now measured against the equal-weight basket of what it could hold.
    assert res["benchmark_kind"] == "equal_weight_basket"
    assert res["benchmark_basket"] == ["QQQ", "SPY"]
    assert res["benchmark_curve"] == [2000.0, 2200.0, 2400.0]
    assert res["benchmark_return_pct"] == pytest.approx(20.0)


# --- robustness: can the result be believed? --------------------------------

def _equity_charts(values):
    return {"Strategy Equity": {"series": {"Equity": {"values": values}}}}


def test_probabilistic_sharpe_is_surfaced():
    """LEAN computes it; it was buried in the statistics fold. It is the one
    number that says whether a Sharpe is distinguishable from luck."""
    from app.fund.leanrunner import _robustness
    rb = _robustness({"Probabilistic Sharpe Ratio": "1.969%", "Total Orders": "41"},
                     [], [], [])
    assert rb["psr_pct"] == pytest.approx(1.969)
    assert rb["total_orders"] == 41


# --- the PSR hurdle's own clock, captured from the run -----------------------
#
# LEAN's published Probabilistic Sharpe Ratio is measured against a hardcoded
# `1/sqrt(tradingDaysPerYear)` (PortfolioStatistics.cs:311), so the clock IS the
# hurdle. Until D38 the belt threw the engine's `algorithmConfiguration` away
# and the only way to know a future image had moved it was to grep summary
# files on the belt host's disk. These three pin the capture at each layer,
# because a capture that exists and is never fed is the unwired-control shape.

def test_psr_inputs_captures_the_runs_own_trading_days_and_the_hurdle():
    """Would catch: `psr_inputs` accepting a configuration and ignoring it —
    the target would then always report the engine's default as if it had been
    read, and a LEAN image that moved the clock would move the hurdle silently.
    Moved to a clock LEAN does not default to, so a hardcoded 252 fails."""
    from app.fund.leanrunner import psr_inputs
    got = psr_inputs({"Sharpe Ratio": "1.4"}, None,
                     {"tradingDaysPerYear": 260})
    assert got["trading_days_per_year"] == 260
    assert got["target"]["trading_days_per_year"] == 260.0
    assert got["target"]["assumed"] is False
    assert got["target"]["per_obs"] == pytest.approx(1.0 / 260 ** 0.5)
    assert got["target"]["annualised"] == pytest.approx(1.0)


@pytest.mark.parametrize("stored", [None, 0, -1, "252", True, [], {}])
def test_an_unusable_trading_days_is_ABSENT_not_the_default(stored):
    """Would catch: a malformed stored clock being written into the capture as
    if the engine had published it — `True` is the sharp case, since `True == 1`
    would silently record a one-trading-day year. Absent is reported absent;
    `target.assumed` then says the hurdle rests on the engine's default."""
    from app.fund.leanrunner import psr_inputs
    got = psr_inputs({}, None, {"tradingDaysPerYear": stored})
    assert got["trading_days_per_year"] is None
    assert got["target"]["assumed"] is True
    assert got["target"]["trading_days_per_year"] == 252.0


def test_the_BELTS_OWN_PARSER_hands_the_configuration_to_the_capture(tmp_path):
    """Through the real call site, not the helper (D17: a helper can be
    flawless and uncalled). Would catch `_parse_results` reading the engine's
    `algorithmConfiguration` and not passing it down — every test above would
    still pass and every stored run would report the default."""
    doc = _doc_with(_equity_charts([[1748750400, 100.0], [1748836800, 101.0]]))
    doc["algorithmConfiguration"] = {"tradingDaysPerYear": 260}
    res = LeanRunner._parse_results(_write(tmp_path, doc))
    assert res is not None
    pin = res["robustness"]["psr_inputs"]
    assert pin["trading_days_per_year"] == 260
    assert pin["target"]["assumed"] is False
    # and a run with no configuration at all says so, rather than inventing one
    plain = LeanRunner._parse_results(_write(
        tmp_path / "b", _doc_with(_equity_charts([[1748750400, 100.0],
                                                  [1748836800, 101.0]]))))
    assert plain["robustness"]["psr_inputs"]["trading_days_per_year"] is None
    assert plain["robustness"]["psr_inputs"]["target"]["assumed"] is True


def test_an_unpriced_run_that_traded_is_flagged():
    """No slippage model and it traded: the result overstates, and loudly."""
    from app.fund.leanrunner import cost_disclosure
    d = cost_disclosure("class X(QCAlgorithm): pass", 0.0, 41)
    assert d["slippage_modelled"] is False
    assert d["unpriced"] is True
    assert "overstates" in d["note"]


def test_no_fills_is_not_an_unpriced_claim():
    """An algorithm that never traded paid nothing because it did nothing —
    a different statement from 'trading was free'."""
    from app.fund.leanrunner import cost_disclosure
    assert cost_disclosure("class X(QCAlgorithm): pass", 0.0, 0)["unpriced"] is False


def test_zero_commission_with_slippage_modelled_is_NOT_unpriced():
    """The case that made the old flag cry wolf: Alpaca genuinely charges no
    commission, so zero fees is correct — the spread is priced separately."""
    from app.fund.leanrunner import cost_disclosure
    code = "sec.set_slippage_model(ConstantSlippageModel(0.0005))"
    d = cost_disclosure(code, 0.0, 41)
    assert d["slippage_modelled"] is True
    assert d["unpriced"] is False
    assert d["note"] == "costs modelled"


def test_explicitly_zeroed_slippage_is_called_out():
    """Setting the model to zero is not the same as pricing the run, and the
    source looks identical to a priced one at a glance."""
    from app.fund.leanrunner import cost_disclosure
    d = cost_disclosure("sec.set_slippage_model(ConstantSlippageModel(0))", 0.0, 41)
    assert d["slippage_modelled"] is False
    assert "explicitly zeroed" in d["note"]


def test_periods_split_the_window_and_expose_one_lucky_stretch():
    from app.fund.leanrunner import _periods
    equity = [100.0] * 10 + [100.0] * 10 + [float(100 + i * 10) for i in range(10)]
    dates = [f"2025-01-{i + 1:02d}" for i in range(30)]
    periods = _periods(equity, dates, n=3)
    assert len(periods) == 3
    assert periods[0]["return_pct"] == 0.0
    assert periods[1]["return_pct"] == 0.0
    assert periods[2]["return_pct"] > 0     # all of it came from the last third
    assert periods[0]["from"] == "2025-01-01"


def test_periods_absent_when_dates_do_not_match_the_curve():
    """No dates means no honest period labels — say nothing rather than guess."""
    from app.fund.leanrunner import _periods
    assert _periods([1.0] * 30, [], n=3) == []


def test_periods_absent_on_a_curve_too_short_to_split():
    from app.fund.leanrunner import _periods
    assert _periods([1.0, 2.0], ["2025-01-01", "2025-01-02"], n=3) == []


def test_unparsable_statistics_are_unknown_not_zero():
    from app.fund.leanrunner import _robustness
    rb = _robustness({"Probabilistic Sharpe Ratio": "n/a"}, [], [], [])
    assert rb["psr_pct"] is None


# --- sweeps: is the good cell an island or a plateau? -----------------------

#: Fake docker that ECHOES the parameter it was given into the return, so a
#: test can prove each grid point actually reached the engine with its own
#: values — the failure this guards is a sweep where every point silently ran
#: identical parameters and the grid looked flat for the wrong reason.
FAKE_PARAMS = r"""
import json, sys
res = next(a.rsplit(":", 1)[0] for a in sys.argv if a.endswith(":/Results"))
params = {}
if "--parameters" in sys.argv:
    raw = sys.argv[sys.argv.index("--parameters") + 1]
    for pair in raw.split(","):
        k, _, v = pair.partition(":")
        params[k] = v
fast = float(params.get("fast", 0))
json.dump({
    "statistics": {"Net Profit": "%s%%" % fast, "Sharpe Ratio": "1.0",
                   "Drawdown": "5.0%", "Total Orders": "4",
                   "Probabilistic Sharpe Ratio": "60.0%"},
    "charts": {"Strategy Equity": {"series": {"Equity": {"values":
        [[1, 1000.0], [2, 1000.0 + fast]]}}}},
}, open(res + "/SmokeAlgo.json", "w"))
"""


def _wait_sweep(r: LeanRunner, sweep_id: str, timeout=60.0) -> dict:
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = r.sweep(sweep_id)
        if s["state"] in ("done", "failed"):
            return s
        time.sleep(0.05)
    raise AssertionError("sweep never finished")


def test_each_grid_point_runs_with_its_own_parameters(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    sub = r.submit_sweep("smoke", {"fast": ["5", "10", "20"]})
    assert sub["total"] == 3
    s = _wait_sweep(r, sub["sweep_id"])
    assert s["state"] == "done"
    got = {p["parameters"]["fast"]: p["total_return_pct"] for p in s["points"]}
    assert got == {"5": 5.0, "10": 10.0, "20": 20.0}


def test_grid_is_the_cartesian_product(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    sub = r.submit_sweep("smoke", {"fast": ["5", "10"], "slow": ["50", "100"]})
    assert sub["total"] == 4
    s = _wait_sweep(r, sub["sweep_id"])
    combos = {(p["parameters"]["fast"], p["parameters"]["slow"]) for p in s["points"]}
    assert combos == {("5", "50"), ("5", "100"), ("10", "50"), ("10", "100")}


def test_summary_reports_the_neighbourhood_not_just_the_winner(tmp_path):
    """Reporting only the best cell is how a fit gets promoted. The gap between
    best and median is the signature the operator needs to see."""
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    s = _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["1", "2", "30"]})["sweep_id"])
    summary = s["summary"]
    assert summary["scored"] == 3
    assert summary["best_return_pct"] == 30.0
    assert summary["median_return_pct"] == 2.0
    assert summary["worst_return_pct"] == 1.0
    assert summary["best_minus_median_pct"] == 28.0   # an island, not a plateau
    assert summary["best"]["parameters"]["fast"] == "30"
    assert summary["positive_share"] == 1.0


def test_a_grid_bigger_than_the_cap_is_refused_with_the_reason(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="Narrow the grid"):
        r.submit_sweep("smoke", {"a": [str(i) for i in range(5)],
                                 "b": [str(i) for i in range(6)]})


def test_parameter_values_cannot_smuggle_a_separator(tmp_path):
    """LEAN packs the whole grid point into one comma-separated flag, so a
    value containing ',' or ':' would silently become other parameters."""
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="cannot contain"):
        r.submit_sweep("smoke", {"fast": ["10,slow:99"]})


def test_bad_parameter_name_is_refused(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="bad parameter name"):
        r.submit_sweep("smoke", {"fast period": ["10"]})


def test_empty_grid_is_refused(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="no parameters"):
        r.submit_sweep("smoke", {})
    with pytest.raises(LeanError, match="no values"):
        r.submit_sweep("smoke", {"fast": []})


def test_an_unknown_sweep_says_there_is_no_record_of_it(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    with pytest.raises(LeanError, match="no record of it"):
        r.sweep("nope")


def test_a_runner_without_a_database_behaves_exactly_as_before(tmp_path):
    """Persistence is optional. Every test constructs a runner with no store, so
    if the mirror were required rather than best-effort, the whole suite would be
    exercising a different object from the one that runs in production."""
    r = _runner(tmp_path, FAKE_OK)
    r.save_algorithm("smoke", ALGO)
    job = _wait(r, r.submit_backtest("smoke")["job_id"])
    assert job["state"] == "done"
    assert r._durable() is None


def test_a_restored_sweep_is_not_reported_as_still_running(tmp_path):
    """The thread driving a sweep dies with the process. A sweep reloaded from
    the mirror mid-flight must not claim to be running, or a poller waits
    forever on work nobody is doing."""
    r = _runner(tmp_path, FAKE_PARAMS)

    class FakeStore:
        def sweep(self, sweep_id):
            return {"sweep_id": sweep_id, "state": "running", "completed": 3,
                    "total": 10, "points": [], "restored": True}

    r._store = FakeStore()          # type: ignore
    r._store_tried = True
    out = r.sweep("half-done")
    assert out["state"] == "interrupted"
    assert "3 of 10" in out["error"]


def test_failed_points_do_not_poison_the_summary(tmp_path):
    """A point that failed is not a zero-return point — it is unscored."""
    r = _runner(tmp_path, FAKE_FAIL)
    r.save_algorithm("smoke", ALGO)
    s = _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["5", "10"]})["sweep_id"])
    assert s["state"] == "done"
    assert all(p["state"] == "failed" for p in s["points"])
    assert s["summary"]["scored"] == 0


# --- holdout: the only test that catches the fit ----------------------------

#: Fake docker that honours start/end by reporting a DIFFERENT equity window
#: per run, and scores by `fast`. Lets a test prove the winner was re-run on
#: dates it was not chosen on.
FAKE_WINDOWED = r"""
import json, sys
res = next(a.rsplit(":", 1)[0] for a in sys.argv if a.endswith(":/Results"))
params = {}
if "--parameters" in sys.argv:
    for pair in sys.argv[sys.argv.index("--parameters") + 1].split(","):
        k, _, v = pair.partition(":")
        params[k] = v
fast = float(params.get("fast", 0))
start, end = params.get("start", "2025-01-01"), params.get("end", "2025-06-30")
# Out of sample the edge collapses: the fit does not survive new data.
ret = fast if start.startswith("2025") else fast / 10.0
json.dump({
    "statistics": {"Net Profit": "%s%%" % ret, "Sharpe Ratio": "1.0",
                   "Drawdown": "5.0%", "Total Orders": "4"},
    "charts": {"Strategy Equity": {"series": {"Equity": {"values": [
        [__import__("calendar").timegm(__import__("time").strptime(start, "%Y-%m-%d")), 1000.0],
        [__import__("calendar").timegm(__import__("time").strptime(end, "%Y-%m-%d")), 1000.0 + ret],
    ]}}}},
}, open(res + "/SmokeAlgo.json", "w"))
"""

#: Same, but IGNORES start/end — every run covers identical dates. This is the
#: algorithm that makes a holdout meaningless without anyone noticing.
FAKE_IGNORES_DATES = FAKE_WINDOWED.replace(
    'start, end = params.get("start", "2025-01-01"), params.get("end", "2025-06-30")',
    'start, end = "2025-01-01", "2025-06-30"')

HOLDOUT = {"train_start": "2025-01-01", "train_end": "2025-06-30",
           "test_start": "2026-01-01", "test_end": "2026-06-30"}


def test_the_winner_is_re_run_on_dates_it_was_not_chosen_on(tmp_path):
    r = _runner(tmp_path, FAKE_WINDOWED)
    r.save_algorithm("smoke", ALGO)
    sub = r.submit_sweep("smoke", {"fast": ["5", "30"]}, holdout=HOLDOUT)
    assert sub["total"] == 3          # two grid points plus the held-out run
    s = _wait_sweep(r, sub["sweep_id"])
    h = s["holdout_result"]
    assert h["state"] == "done"
    assert h["parameters"] == {"fast": "30"}          # the grid's winner
    assert h["train"]["return_pct"] == 30.0
    assert h["test"]["return_pct"] == 3.0             # collapses out of sample
    assert h["train"]["window"] != h["test"]["window"]
    assert h["dates_honoured"] is True


def test_an_algorithm_that_ignores_the_window_is_caught(tmp_path):
    """A 'validation' that silently re-ran the training window is worse than
    none, because it reassures. The runs must cover different dates."""
    r = _runner(tmp_path, FAKE_IGNORES_DATES)
    r.save_algorithm("smoke", ALGO)
    s = _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["5", "30"]},
                                      holdout=HOLDOUT)["sweep_id"])
    h = s["holdout_result"]
    assert h["dates_honoured"] is False
    assert h["train"]["window"] == h["test"]["window"]


def test_overlapping_windows_are_refused(tmp_path):
    r = _runner(tmp_path, FAKE_WINDOWED)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="leak the answer"):
        r.submit_sweep("smoke", {"fast": ["5"]}, holdout={
            "train_start": "2025-01-01", "train_end": "2025-12-31",
            "test_start": "2025-06-01", "test_end": "2026-06-30"})


def test_malformed_holdout_dates_are_refused(tmp_path):
    r = _runner(tmp_path, FAKE_WINDOWED)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="YYYY-MM-DD"):
        r.submit_sweep("smoke", {"fast": ["5"]}, holdout={
            "train_start": "jan 2025", "train_end": "2025-12-31",
            "test_start": "2026-01-01", "test_end": "2026-06-30"})


def test_backwards_window_is_refused(tmp_path):
    r = _runner(tmp_path, FAKE_WINDOWED)
    r.save_algorithm("smoke", ALGO)
    with pytest.raises(LeanError, match="end after they start"):
        r.submit_sweep("smoke", {"fast": ["5"]}, holdout={
            "train_start": "2025-12-31", "train_end": "2025-01-01",
            "test_start": "2026-01-01", "test_end": "2026-06-30"})


def test_a_sweep_without_holdout_still_works(tmp_path):
    r = _runner(tmp_path, FAKE_WINDOWED)
    r.save_algorithm("smoke", ALGO)
    s = _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["5", "30"]})["sweep_id"])
    assert s["state"] == "done"
    assert s["holdout_result"] is None
    assert s["summary"]["scored"] == 2


def test_holdout_skipped_when_nothing_scored(tmp_path):
    r = _runner(tmp_path, FAKE_FAIL)
    r.save_algorithm("smoke", ALGO)
    s = _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["5"]},
                                      holdout=HOLDOUT)["sweep_id"])
    assert s["holdout_result"]["state"] == "skipped"


# --- live sessions: LEAN proposes, never executes ---------------------------

LIVE_ALGO = """
from AlgorithmImports import *
class LiveAlgo(QCAlgorithm):
    def initialize(self):
        self.sym = self.add_data(SpineBars, "GLD", Resolution.DAILY).symbol
        self.set_benchmark(self.sym)
"""

#: Fake docker for live sessions. `run` blocks the way a live container does;
#: `kill` must return at once, or stop_live() waits on its own kill command.
FAKE_LIVE = r"""
import sys, time
if "kill" in sys.argv[:2]:
    sys.exit(0)
time.sleep(60)
"""


def test_live_requires_a_benchmark_on_the_custom_symbol(tmp_path):
    """Without it LEAN adds a SPY minute subscription that live-paper's stub
    data queue cannot serve, and the session dies at startup with an error
    about LiveDataQueue rather than about the algorithm."""
    r = _runner(tmp_path, FAKE_LIVE)
    r.save_algorithm("nobench", ALGO)          # ALGO has no set_benchmark
    with pytest.raises(LeanError, match="set_benchmark"):
        r.start_live("nobench")


def test_only_one_live_session_at_a_time(tmp_path):
    r = _runner(tmp_path, FAKE_LIVE)
    r.save_algorithm("live", LIVE_ALGO)
    r.start_live("live")
    time.sleep(0.3)
    with pytest.raises(LeanError, match="already running"):
        r.start_live("live")


def test_the_signal_token_never_leaves_the_runner(tmp_path):
    """The session dict is returned over the API, so it carries whether a
    token was configured, never the token."""
    r = _runner(tmp_path, FAKE_LIVE)
    r.save_algorithm("live", LIVE_ALGO)
    out = r.start_live("live", strategy_id="strat-1", signal_token="SECRET-TOKEN")
    assert out["signal_configured"] is True
    session = r.live_session(out["session_id"])
    assert "SECRET-TOKEN" not in json.dumps(session)


def test_an_unconfigured_session_says_so(tmp_path):
    r = _runner(tmp_path, FAKE_LIVE)
    r.save_algorithm("live", LIVE_ALGO)
    out = r.start_live("live")
    assert out["signal_configured"] is False


def test_stopping_a_session_marks_it_stopped(tmp_path):
    r = _runner(tmp_path, FAKE_LIVE)
    r.save_algorithm("live", LIVE_ALGO)
    sid = r.start_live("live")["session_id"]
    time.sleep(0.3)
    assert r.stop_live(sid)["state"] == "stopped"
    assert r.live_session(sid)["state"] == "stopped"


def test_unknown_live_session_is_an_error(tmp_path):
    r = _runner(tmp_path, FAKE_LIVE)
    with pytest.raises(LeanError, match="unknown live session"):
        r.live_session("nope")


# --- breakeven cost: how wrong can we be about costs? -----------------------

def _pt(slip, ret, state="done"):
    return {"parameters": {"slip": str(slip)}, "state": state,
            "total_return_pct": ret}


def test_breakeven_is_interpolated_between_the_straddling_points():
    from app.fund.leanrunner import breakeven_cost
    # Profitable at 0 and 5bps, loses money at 10bps.
    out = breakeven_cost([_pt(0.0, 4.0), _pt(0.0005, 2.0), _pt(0.001, -2.0)])
    assert out["breakeven"] is not None
    assert 0.0005 < out["breakeven"] < 0.001
    assert out["bracket"] == [0.0005, 0.001]
    assert 5.0 < out["breakeven_bps"] < 10.0


def test_a_strategy_that_survives_every_cost_says_so():
    """None is ambiguous on its own — 'never crossed' has two opposite
    meanings and the operator needs to know which."""
    from app.fund.leanrunner import breakeven_cost
    out = breakeven_cost([_pt(0.0, 8.0), _pt(0.002, 5.0), _pt(0.01, 3.0)])
    assert out["breakeven"] is None
    assert "still profitable at every cost" in out["reason"]
    assert out["tested_range"] == [0.0, 0.01]


def test_a_strategy_that_loses_even_for_free_says_so():
    from app.fund.leanrunner import breakeven_cost
    out = breakeven_cost([_pt(0.0, -1.0), _pt(0.001, -3.0)])
    assert out["breakeven"] is None
    assert "including the cheapest" in out["reason"]


def test_failed_and_unpriced_points_are_ignored():
    from app.fund.leanrunner import breakeven_cost
    pts = [_pt(0.0, 4.0), _pt(0.001, None, state="failed"),
           {"parameters": {"fast": "10"}, "state": "done", "total_return_pct": 9.9},
           _pt(0.002, -2.0)]
    out = breakeven_cost(pts)
    assert out["bracket"] == [0.0, 0.002]


def test_a_single_point_cannot_be_interpolated():
    from app.fund.leanrunner import breakeven_cost
    out = breakeven_cost([_pt(0.0, 4.0)])
    assert out["breakeven"] is None
    assert "at least two" in out["reason"]


def test_an_ordinary_sweep_is_not_decorated_with_cost_findings():
    """A grid over fast/slow never varied a cost, so a breakeven field would be
    an answer to a question nobody asked."""
    from app.fund.leanrunner import _sweep_summary
    pts = [{"parameters": {"fast": "10"}, "state": "done", "total_return_pct": 4.0},
           {"parameters": {"fast": "20"}, "state": "done", "total_return_pct": 6.0}]
    assert "breakeven_cost" not in _sweep_summary(pts)


def test_a_cost_sweep_reports_breakeven_in_the_summary():
    from app.fund.leanrunner import _sweep_summary
    s = _sweep_summary([_pt(0.0, 4.0), _pt(0.0005, 2.0), _pt(0.001, -2.0)])
    assert s["breakeven_cost"]["breakeven_bps"] is not None


def test_sweep_points_skip_the_network_backed_extras(tmp_path):
    """Capacity and the benchmark each cost a live fetch, and a sweep never
    reads either — the grid rows carry neither. Twenty-four points meant
    twenty-four fetches for numbers nobody looks at, which slowed real sweeps
    and made the suite flaky under load."""
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    calls = []
    r._add_capacity = lambda result: calls.append("capacity")      # type: ignore
    r._add_benchmark = lambda result, code=None: calls.append("benchmark")  # type: ignore

    _wait_sweep(r, r.submit_sweep("smoke", {"fast": ["5", "10"]})["sweep_id"])
    assert calls == []

    # A standalone run still gets them: that is the result a human reads.
    _wait(r, r.submit_backtest("smoke")["job_id"])
    assert "capacity" in calls and "benchmark" in calls


def test_the_fund_cost_assumption_is_injected_into_every_run(tmp_path):
    """The backtest must charge the same number TCA grades fills against.
    Two copies of one belief is how 2bps and 5bps drifted apart."""
    from app.fund.costassumption import slippage_fraction
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    job_id = r.submit_backtest("smoke")["job_id"]
    assert r.job(job_id)["parameters"]["slip"] == str(slippage_fraction())


def test_an_explicit_slip_is_never_overridden(tmp_path):
    """A cost sweep is the one case that must vary it — overriding would make
    breakeven_cost measure the same point repeatedly."""
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)
    job_id = r.submit_backtest("smoke", {"slip": "0.002"})["job_id"]
    assert r.job(job_id)["parameters"]["slip"] == "0.002"


def test_a_flat_engine_benchmark_is_discarded_rather_than_believed(tmp_path):
    """LEAN emits a full-length curve of ZEROS for custom data types, and that
    curve is truthy. Believing it measures the fund against a 0% bar, which
    every profitable strategy clears — a silently flattering benchmark, which is
    worse than no benchmark at all."""
    r = _runner(tmp_path, FAKE_PARAMS)
    result = {
        "benchmark_curve": [0.0] * 5,
        "benchmark_return_pct": 0.0,
        "equity_dates": ["2024-01-02", "2024-01-03"],
        "equity_curve": [1000.0, 1010.0],
        "orders": [{"symbol": "ZZZZ_NOT_A_TICKER"}],
    }
    r._add_benchmark(result)
    assert "benchmark_return_pct" not in result, "a 0% bar was believed"
    assert not result.get("benchmark_curve")


def test_a_zero_padded_engine_benchmark_is_discarded(tmp_path):
    """Where LEAN does emit prices it zero-pads the days before the
    subscription starts. A return computed off a zero base is not a number."""
    r = _runner(tmp_path, FAKE_PARAMS)
    result = {
        "benchmark_curve": [0.0, 0.0, 23.1, 23.4],
        "equity_dates": ["2024-01-02", "2024-01-05"],
        "equity_curve": [1000.0, 1010.0],
        "orders": [{"symbol": "ZZZZ_NOT_A_TICKER"}],
    }
    r._add_benchmark(result)
    assert not result.get("benchmark_curve")


def test_a_single_constituent_engine_benchmark_is_refused_for_a_basket(monkeypatch):
    """set_benchmark names one symbol. For a strategy that CHOOSES among names
    that is one arbitrary constituent, which flatters a rule that dodged the
    worst name and punishes one that held the best."""
    import app.fund.marketdata as md

    class Bars:
        closes = [50.0, 55.0]
        dates = ["2024-01-02", "2024-01-04"]
        source = "test"

    monkeypatch.setattr(md, "fetch_daily_bars", lambda *a, **k: Bars())
    result = {
        "benchmark_curve": [10.0, 11.0, 12.0],          # strictly positive
        "equity_dates": ["2024-01-02", "2024-01-04"],
        "equity_curve": [1000.0, 1010.0],
        "orders": [{"symbol": "AAA"}, {"symbol": "BBB"}],
    }
    LeanRunner._add_benchmark(result)
    assert result["benchmark_kind"] == "equal_weight_basket"
    assert result["benchmark_basket"] == ["AAA", "BBB"]
    assert result["benchmark_return_pct"] == pytest.approx(10.0)


def test_a_bar_missing_most_of_its_universe_is_refused(monkeypatch):
    """A 'basket' built from 2 of 20 names is not that basket. Reporting it as
    one grades the strategy against an accidental sub-portfolio."""
    import app.fund.marketdata as md

    class Bars:
        closes = [50.0, 55.0]
        dates = ["2024-01-02", "2024-01-04"]
        source = "test"

    def only_aaa(symbol, *a, **k):
        if symbol != "AAA":
            raise RuntimeError("no bars")
        return Bars()

    monkeypatch.setattr(md, "fetch_daily_bars", only_aaa)
    result = {
        "equity_dates": ["2024-01-02", "2024-01-04"],
        "equity_curve": [1000.0, 1010.0],
        "orders": [{"symbol": s} for s in ("AAA", "BBB", "CCC", "DDD", "EEE")],
    }
    LeanRunner._add_benchmark(result)
    assert "benchmark_return_pct" not in result
    assert "1 of 5" in result["benchmark_unavailable"]


def test_a_usable_single_name_engine_benchmark_is_kept(tmp_path):
    """The rule must not throw away a benchmark that IS the right question:
    one name traded, strictly positive series."""
    r = _runner(tmp_path, FAKE_PARAMS)
    curve = [10.0, 11.0, 12.0]
    result = {
        "benchmark_curve": list(curve),
        "benchmark_return_pct": 20.0,
        "equity_dates": ["2024-01-02", "2024-01-04"],
        "equity_curve": [1000.0, 1010.0],
        "orders": [{"symbol": "AAA"}],
    }
    r._add_benchmark(result)
    assert result["benchmark_curve"] == curve
    assert result["benchmark_return_pct"] == 20.0


def test_the_declared_universe_is_read_narrowly():
    """A cleverer parser would start guessing, and a guessed benchmark is the
    exact failure this exists to prevent."""
    from app.fund.leanrunner import _declared_universe
    assert _declared_universe('UNIVERSE = ["BBB", "AAA", "AAA"]') == ["AAA", "BBB"]
    assert _declared_universe(None) == []
    assert _declared_universe("def (") == []            # unparseable
    assert _declared_universe("UNIVERSE = [1, 2]") == []  # not tickers
    assert _declared_universe("OTHER = ['AAA']") == []
    assert _declared_universe("UNIVERSE = load()") == []  # computed, unknowable


def test_a_job_is_not_done_until_its_result_is_whole(tmp_path):
    """`state` is what every caller polls on, so flipping it before enrichment
    finishes publishes a half-built result. The gate, arriving the instant the
    flag flips, would find no benchmark and no costs disclosure and fail the
    candidate for missing evidence that was seconds away. A verdict that depends
    on who polled first is not a verdict."""
    r = _runner(tmp_path, FAKE_PARAMS)
    r.save_algorithm("smoke", ALGO)

    seen_state_during_enrichment = []

    def slow_benchmark(result, code=None):
        # Whatever a poller can observe while enrichment is still running must
        # NOT say "done".
        seen_state_during_enrichment.append(r.job(job_id)["state"])
        result["benchmark_return_pct"] = 1.0

    r._add_benchmark = slow_benchmark                                # type: ignore
    job_id = r.submit_backtest("smoke")["job_id"]
    job = _wait(r, job_id)

    assert seen_state_during_enrichment == ["running"], seen_state_during_enrichment
    # And once done, the enriched field is there for the first caller who looks.
    assert job["result"]["benchmark_return_pct"] == 1.0


def test_engine_containers_do_not_stack(tmp_path, monkeypatch):
    """15.2 GB is the ceiling and a stacked sweep already killed a holdout run
    outright (`WinError 1455`). The run did not slow down, it vanished — so the
    cap is not a performance knob, it is the difference between a queue and a
    lost result."""
    import app.fund.leanrunner as lr

    r = _runner(tmp_path, FAKE_OK)
    r.save_algorithm("smoke", ALGO)

    concurrent = {"now": 0, "peak": 0}
    real_run = lr.subprocess.run

    def counting_run(cmd, *a, **k):
        concurrent["now"] += 1
        concurrent["peak"] = max(concurrent["peak"], concurrent["now"])
        try:
            time.sleep(0.15)          # long enough for the others to pile up
            return real_run(cmd, *a, **k)
        finally:
            concurrent["now"] -= 1

    monkeypatch.setattr(lr.subprocess, "run", counting_run)

    ids = [r.submit_backtest("smoke")["job_id"] for _ in range(4)]
    for job_id in ids:
        _wait(r, job_id)

    assert concurrent["peak"] <= lr.MAX_CONCURRENT_CONTAINERS, (
        f"peaked at {concurrent['peak']} containers")
    # And every job still finished — the cap queues work, it does not drop it.
    assert all(r.job(i)["state"] == "done" for i in ids)


def test_a_container_is_given_a_memory_ceiling(tmp_path):
    """Without one, a runaway algorithm exhausts the host and takes unrelated
    runs down with it — the failure is never contained to its cause."""
    import app.fund.leanrunner as lr

    r = _runner(tmp_path, FAKE_RECORDING)
    r.save_algorithm("smoke", ALGO)
    job_id = r.submit_backtest("smoke")["job_id"]
    _wait(r, job_id)
    args = _docker_argv(tmp_path, job_id)
    assert "--memory" in args, args
    assert args[args.index("--memory") + 1] == lr.CONTAINER_MEMORY


def test_queue_time_is_not_charged_to_the_engine_timeout(tmp_path):
    """A job held behind another must not be killed for being second in line,
    and must not report `running` while it waits."""
    import app.fund.leanrunner as lr

    r = _runner(tmp_path, FAKE_OK)
    r.save_algorithm("smoke", ALGO)
    # Hold EVERY slot, then confirm a fresh job sits in `queued`.
    #
    # This used to acquire one, which was the same thing back when the pool was a
    # semaphore of one. It stopped testing anything the moment concurrency rose to
    # 4 — the job simply took a free slot and ran. Written against the configured
    # width so it keeps testing the queueing behaviour at any concurrency.
    held = 0
    try:
        for _ in range(lr.MAX_CONCURRENT_CONTAINERS):
            lr._ENGINE_SLOTS.acquire()
            held += 1
        job_id = r.submit_backtest("smoke")["job_id"]
        time.sleep(0.4)
        assert r.job(job_id)["state"] == "queued"
    finally:
        for _ in range(held):
            lr._ENGINE_SLOTS.release()
    job = _wait(r, job_id)
    assert job["state"] == "done"
    # wall_seconds measures the engine, not the wait.
    assert job["wall_seconds"] < 30


#: A fake engine that records overlap: each run stamps its start and end, so a
#: test can prove two containers were alive at the same instant rather than
#: inferring concurrency from a stopwatch.
FAKE_OVERLAP = r"""
import json, os, sys, time
res = next(a.rsplit(":", 1)[0] for a in sys.argv if a.endswith(":/Results"))
root = os.path.dirname(res)   # ws/results
t0 = time.time()
time.sleep(0.35)
t1 = time.time()
# One file per run. Four processes appending to a SHARED file raced on Windows
# and silently dropped a line, so the harness lost a write and it looked exactly
# like the runner losing a grid point.
with open(os.path.join(root, "span-%d.json" % os.getpid()), "w") as fh:
    json.dump([t0, t1], fh)
json.dump({
    "statistics": {"Net Profit": "12.5%", "Sharpe Ratio": "1.4",
                   "Drawdown": "8.0%", "Total Orders": "6"},
    "charts": {"Strategy Equity": {"series": {"Equity": {"values":
        [[1, 1000.0], [2, 1050.0], [3, 1125.0]]}}}},
}, open(res + "/SmokeAlgo.json", "w"))
print("engine ok")
"""


def _spans(tmp_path: Path) -> list[tuple[float, float]]:
    d = tmp_path / "ws" / "results"
    return [tuple(json.loads(f.read_text())) for f in sorted(d.glob("span-*.json"))]


def _max_overlap(spans: list[tuple[float, float]]) -> int:
    """How many runs were alive at once, at the busiest instant."""
    edges = [(a, 1) for a, _ in spans] + [(b, -1) for _, b in spans]
    edges.sort()
    cur = best = 0
    for _, d in edges:
        cur += d
        best = max(best, cur)
    return best


def test_grid_points_actually_run_concurrently(tmp_path, monkeypatch):
    """The change that mattered, and the one a semaphore alone could not deliver.

    Sweep points were run in a plain `for` loop, so a candidate's 6 grid points
    across 4 walk-forward folds were 24 STRICTLY SEQUENTIAL engine runs — every
    one of them independent — on a 12-core machine using about one core. Raising
    MAX_CONCURRENT_CONTAINERS changed nothing, because the belt never asked for a
    second slot.

    Proven by overlap rather than by elapsed time: a stopwatch would pass on a
    fast machine even if the runs were serial.
    """
    import app.fund.leanrunner as lr

    r = _runner(tmp_path, FAKE_OVERLAP)
    r.save_algorithm("smoke", ALGO)
    sid = r.submit_sweep("smoke", {"fast": ["2", "3", "4", "5"]})["sweep_id"]
    sweep = _wait_sweep(r, sid)

    assert sweep["state"] == "done"
    assert len(sweep["points"]) == 4, "a point went missing under concurrency"
    spans = _spans(tmp_path)
    assert len(spans) == 4
    assert _max_overlap(spans) > 1, (
        "grid points ran one at a time — the sweep is still serialised behind "
        "itself and extra container slots buy nothing")
    assert _max_overlap(spans) <= lr.MAX_CONCURRENT_CONTAINERS, (
        "more containers were alive than the semaphore permits")


def test_concurrency_never_exceeds_the_configured_slots(tmp_path, monkeypatch):
    """The cap is what keeps a wide grid from exhausting the host.

    The original WinError 1455 was a 3 GiB RESERVATION per container stacking on a
    15.2 GB host, not LEAN's real ~450 MiB appetite — but the ceiling still has to
    hold, or the fix would have traded a diagnosed crash for an undiagnosed one.
    """
    import app.fund.leanrunner as lr

    monkeypatch.setattr(lr, "MAX_CONCURRENT_CONTAINERS", 2)
    monkeypatch.setattr(lr, "_ENGINE_SLOTS", threading.BoundedSemaphore(2))
    r = _runner(tmp_path, FAKE_OVERLAP)
    r.save_algorithm("smoke", ALGO)
    sid = r.submit_sweep("smoke", {"fast": ["2", "3", "4", "5", "6", "7"]})["sweep_id"]
    sweep = _wait_sweep(r, sid)

    assert sweep["state"] == "done"
    assert len(sweep["points"]) == 6
    assert _max_overlap(_spans(tmp_path)) <= 2


def test_every_point_is_still_recorded_when_one_of_them_fails(tmp_path):
    """Concurrency must not lose a result, and must not hide a failure.

    Points are appended under a lock; the summary is computed after the join. A
    dropped point would silently shrink the grid the winner was chosen from.
    """
    r = _runner(tmp_path, FAKE_OK)
    r.save_algorithm("smoke", ALGO)
    sid = r.submit_sweep("smoke", {"fast": ["2", "3", "4", "5", "6"]})["sweep_id"]
    sweep = _wait_sweep(r, sid)
    assert sweep["state"] == "done"
    assert len(sweep["points"]) == 5
    assert sweep["completed"] == sweep["total"]
    params = sorted(p["parameters"]["fast"] for p in sweep["points"])
    assert params == ["2", "3", "4", "5", "6"], "a grid point was lost"


# --- results retention ------------------------------------------------------
#
# Engine output grew without bound: 501 directories, 188 MB, and nothing ever
# removed one. The parsed result is mirrored to Postgres, so a settled job's
# directory is debug material rather than the record — but deleting one somebody
# needed costs a debugging session, so every safety property gets a test.

def _mk_result_dir(r: LeanRunner, name: str, age_days: float) -> Path:
    import os
    d = r._ws / "results" / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "out.json").write_text("{}", encoding="utf-8")
    when = time.time() - age_days * 86400.0
    os.utime(d, (when, when))
    return d


def test_prune_removes_only_what_is_past_the_window(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    old = _mk_result_dir(r, "old-job", age_days=5)
    fresh = _mk_result_dir(r, "fresh-job", age_days=0.1)
    out = r.prune_results(max_age_days=1, keep_newest=0)
    assert out["removed"] == 1
    assert not old.exists()
    assert fresh.exists(), "a directory inside the retention window was deleted"


def test_prune_never_touches_a_queued_or_running_job(tmp_path):
    """Whatever its age. A job still writing is not a stale result."""
    r = _runner(tmp_path, FAKE_OK)
    d = _mk_result_dir(r, "busy-job", age_days=99)
    r._jobs["busy-job"] = {"state": "running"}
    out = r.prune_results(max_age_days=1, keep_newest=0)
    assert d.exists(), "deleted the output of a running job"
    assert out["skipped_in_use"] == 1
    assert out["removed"] == 0


def test_prune_never_touches_a_live_session(tmp_path):
    """A live session holds its directory for the whole session."""
    r = _runner(tmp_path, FAKE_OK)
    d = _mk_result_dir(r, "live-abc123", age_days=99)
    out = r.prune_results(max_age_days=1, keep_newest=0)
    assert d.exists(), "deleted a live session's directory"
    assert out["removed"] == 0


def test_the_newest_survive_regardless_of_age(tmp_path):
    """Age alone is the wrong rule.

    After an idle week EVERY directory is stale, and a fresh failure would have
    its evidence swept before anyone read it.
    """
    r = _runner(tmp_path, FAKE_OK)
    dirs = [_mk_result_dir(r, f"job-{i}", age_days=10 + i) for i in range(6)]
    out = r.prune_results(max_age_days=1, keep_newest=3)
    surviving = [d for d in dirs if d.exists()]
    assert len(surviving) == 3
    assert out["removed"] == 3
    # The three kept must be the NEWEST three, which are the lowest ages.
    assert sorted(d.name for d in surviving) == ["job-0", "job-1", "job-2"]


def test_prune_reports_what_it_reclaimed_rather_than_logging_silently(tmp_path):
    import os
    r = _runner(tmp_path, FAKE_OK)
    for i in range(3):
        d = _mk_result_dir(r, f"j{i}", age_days=9)
        (d / "big.bin").write_bytes(b"x" * 200_000)
        # Backdate AGAIN: writing into the directory reset its mtime, so the
        # first version of this test aged the directory and then un-aged it.
        when = time.time() - 9 * 86400.0
        os.utime(d, (when, when))
    out = r.prune_results(max_age_days=1, keep_newest=0)
    assert out["removed"] == 3
    assert out["reclaimed_mb"] > 0.3
    assert "reclaimed" in out["note"]


def test_prune_on_a_missing_results_dir_is_not_an_error(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    import shutil
    shutil.rmtree(r._ws / "results")
    out = r.prune_results()
    assert out["removed"] == 0
    assert "no results dir" in out["note"]
