"""Dump the ALPHA verdict for an enumerated domain of results.

Run from each worktree; the two dumps must agree on gate_version, passed,
failures and criteria. `checks` is allowed to gain keys and the diff of the
key SETS is printed rather than asserted here.
"""
import json
import sys

from app.fund.gate import evaluate

FOLDS = [{"train_start": "2021-01-01", "train_end": "2021-12-31",
          "test_start": "2022-01-01", "test_end": "2022-03-31"},
         {"train_start": "2021-04-01", "train_end": "2022-03-31",
          "test_start": "2022-04-01", "test_end": "2022-06-30"},
         {"train_start": "2021-07-01", "train_end": "2022-06-30",
          "test_start": "2022-07-01", "test_end": "2022-09-30"},
         {"train_start": "2021-10-01", "train_end": "2022-09-30",
          "test_start": "2022-10-01", "test_end": "2022-12-31"}]


def daily(n, drift, seed):
    rs, dts = [], []
    import datetime
    x = seed
    d0 = datetime.date(2021, 1, 4)
    for i in range(n):
        x = (1103515245 * x + 12345) % (2 ** 31)
        rs.append(drift + (x / 2 ** 31 - 0.5) * 0.02)
        dts.append((d0 + datetime.timedelta(days=i)).isoformat())
    return rs, dts


def result(i):
    strat, dts = daily(400, 0.0004 * (i % 3), 7 + i)
    bench, _ = daily(400, 0.0002, 99 + i)
    r = {
        "total_return_pct": [10.0, None, 5.0, 50.0][i % 4],
        "benchmark_return_pct": [8.0, 8.0, None, 60.0][i % 4],
        "capacity": {"capacity_usd": [500_000.0, None, 10.0, 1e6][i % 4]},
        "robustness": {
            "psr_pct": [80.0, None, 20.0, 99.0][i % 4],
            "total_orders": [50, 5, None, 400][i % 4],
            "costs": {"slippage_modelled": bool(i % 2)},
        },
        "daily_returns": {"present": True, "dates": dts, "strategy": strat,
                          "benchmark": bench, "benchmark_present": True,
                          "n": len(strat)},
        "benchmark_curve": None,
        "benchmark_population": ({"basis": "declared_universe",
                                  "population": ["SPY", "TLT"],
                                  "point_in_time": True} if i % 2 else None),
    }
    if i % 3 == 0:
        # The recomputed-basket shape, so the new code path is exercised on the
        # alpha side too: it must change checks and nothing else.
        import datetime
        d0 = datetime.date(2021, 1, 4)
        lv, cur = [], 100.0
        bd = []
        for j in range(300):
            cur *= 1.0003
            lv.append(cur)
            bd.append((d0 + datetime.timedelta(days=j)).isoformat())
        r["benchmark_curve"] = lv
        r["benchmark_dates"] = bd
        r["benchmark_series_source"] = "recomputed_basket"
    return r


def holdout(i):
    if i % 5 == 0:
        return None
    return {"state": "done",
            "train": {"return_pct": [20.0, -5.0, 0.01, 30.0][i % 4],
                      "window": ["2021-01-01", "2021-12-31"]},
            "test": {"return_pct": [10.0, -4.0, 3.0, 1.0][i % 4],
                     "total_orders": [30, 0, 12, 40][i % 4],
                     "window": ["2022-01-01", "2022-03-31"]}}


def sweep(i):
    return [None,
            {"breakeven_cost": {"breakeven_bps": 25.0}},
            {"breakeven_cost": {"breakeven_bps": 2.0}},
            {"breakeven_cost": {"reason": "still profitable at every cost tested",
                                "tested_range": [0.0001, 0.0005]}},
            {"breakeven_cost": {"reason": "still profitable at every cost tested",
                                "tested_range": [0.0001, 0.0020]}},
            {"breakeven_cost": {"reason": "no cost sweep was run"}}][i % 6]


def walk(i):
    if i % 7 == 0:
        return None
    if i % 7 == 1:
        return {"not_testable": True, "note": "too slow for the history"}
    return {"folds_measurable": 2 + (i % 4), "folds_retained": 1 + (i % 3),
            "median_retention": 0.6, "requested_folds": FOLDS[:2 + (i % 3)],
            "history_floor": {"effective": "2021-03-02", "binding_leg": "SPY",
                              "data_path": "pinned", "deepened": True}}


def clean(with_premia_shape):
    import datetime
    strat, dts = daily(400, 0.0006, 3)
    bench, _ = daily(400, 0.0001, 11)
    r = {
        "total_return_pct": 60.0, "benchmark_return_pct": 20.0,
        "capacity": {"capacity_usd": 5_000_000.0},
        "robustness": {"psr_pct": 92.0, "total_orders": 300,
                       "costs": {"slippage_modelled": True}},
        "daily_returns": {"present": True, "dates": dts, "strategy": strat,
                          "benchmark": bench, "benchmark_present": True,
                          "n": len(strat)},
    }
    if with_premia_shape:
        d0 = datetime.date(2021, 1, 4)
        lv, bd, cur = [], [], 100.0
        for j in range(400):
            cur *= (1.0 + bench[j])
            lv.append(cur)
            bd.append((d0 + datetime.timedelta(days=j)).isoformat())
        r["benchmark_curve"] = lv
        r["benchmark_dates"] = bd
        r["benchmark_series_source"] = "recomputed_basket"
    ho = {"state": "done",
          "train": {"return_pct": 20.0, "window": ["2021-01-01", "2021-12-31"]},
          "test": {"return_pct": 18.0, "total_orders": 40,
                   "window": ["2022-01-01", "2022-12-31"]}}
    sw = {"breakeven_cost": {"breakeven_bps": 45.0}}
    wf = {"folds_measurable": 4, "folds_retained": 4, "median_retention": 0.9,
          "requested_folds": FOLDS,
          "history_floor": {"effective": "2021-03-02"}}
    return r, ho, sw, wf


CASES = [(result(i), holdout(i), sweep(i), walk(i)) for i in range(60)]
CASES.append(clean(False))
CASES.append(clean(True))

out = []
for i, (res_, ho_, sw_, wf_) in enumerate(CASES):
    v = evaluate(res_, ho_, sw_, walkforward=wf_)
    out.append({"i": i, "gate_version": v["gate_version"],
                "passed": v["passed"], "failures": v["failures"],
                "criteria": v["criteria"],
                "check_keys": sorted(v["checks"]),
                "checks": {k: v["checks"][k] for k in sorted(v["checks"])}})
sys.stdout.write(json.dumps(out, sort_keys=True, default=str))
