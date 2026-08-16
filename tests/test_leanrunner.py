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
