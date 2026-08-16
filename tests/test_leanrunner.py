"""LEAN runner: jobs must be honest about every state the engine can reach."""

import json
import sys
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


def test_unknown_job_says_jobs_do_not_survive_restart(tmp_path):
    r = _runner(tmp_path, FAKE_OK)
    with pytest.raises(LeanError, match="re-run"):
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
    # Most-traded symbol wins, and the curve starts where the strategy started
    # so both are readable on one axis: same money, different decisions.
    assert res["benchmark_symbol"] == "SPY"
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


def test_zero_fees_with_fills_is_flagged_as_a_no_cost_backtest():
    """Custom data carries no fee model, so every run here trades for free —
    which flatters turnover. Stated, never silently 'corrected'."""
    from app.fund.leanrunner import _robustness
    rb = _robustness({"Total Fees": "$0.00"}, [], [], [{"symbol": "SPY"}])
    assert rb["total_fees"] == 0.0
    assert rb["fees_are_zero"] is True


def test_no_fills_is_not_a_free_lunch_claim():
    """An algorithm that never traded paid nothing because it did nothing —
    that is not the same statement as 'trading was free'."""
    from app.fund.leanrunner import _robustness
    rb = _robustness({"Total Fees": "$0.00"}, [], [], [])
    assert rb["fees_are_zero"] is False


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


def test_unknown_sweep_says_sweeps_do_not_survive_restart(tmp_path):
    r = _runner(tmp_path, FAKE_PARAMS)
    with pytest.raises(LeanError, match="re-run"):
        r.sweep("nope")


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
