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
