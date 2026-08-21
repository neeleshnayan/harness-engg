"""The evidence a verdict was computed from, and the four ways it can be absent.

Guards the 2026-08-21 defect the CEO reported three times in one day — "i can
see monthend_rebalance_flow but cant see the analytics behind". The belt
measured an equity curve, the fills, the cost grid and the per-fold rows, handed
the folds to the gate, and let every one of them fall out of scope. What
survived was three failure sentences.

Every test below fails if the envelope stops carrying something, and — the
harder half — if any of the four absences starts rendering as another. An empty
panel where "this ran before we kept the evidence" belongs is the same class of
bug as a zero where a None belongs, and this fund has now fixed that class in
the gate, the NAV fold and the risk monitor.
"""

from app.fund import runanalytics as ra


def _job(**over):
    job = {
        "job_id": "job-1", "state": "done", "wall_seconds": 12.4,
        "parameters": {"slip": "0.0005"},
        "result": {
            "total_return_pct": 42.456, "benchmark_return_pct": 40.75,
            "equity_curve": [100.0, 101.0], "equity_dates": ["2025-01-02", "2025-01-03"],
            "benchmark_curve": [100.0, 100.5],
            "orders": [{"symbol": "SPY", "side": "buy", "qty": 71.0}],
            "robustness": {"psr_pct": 0.584, "total_orders": 254},
            "capacity": {"capacity_usd": 341381399.49},
            "statistics": {"Total Orders": "254"},
            "raw_files": ["/Results/job-1/x.json"],
        },
    }
    job.update(over)
    return job


def _sweep(**over):
    s = {
        "sweep_id": "sw-1", "state": "done", "total": 2, "completed": 2,
        "summary": {"best": {"parameters": {"slip": "0.0005"}},
                    "breakeven_cost": {"breakeven_bps": 5.92}},
        "points": [{"parameters": {"slip": "0.0005"}, "state": "done",
                    "total_return_pct": 42.456, "window": ["2021-03-01", "2025-02-28"],
                    "result": {"orders": []}}],
        "holdout": {"train_start": "2021-03-01", "test_end": "2026-08-19"},
        "holdout_result": {"state": "done", "dates_honoured": True},
    }
    s.update(over)
    return s


def _walk(**over):
    w = {
        "algorithm": "monthend_rebalance_flow",
        "folds_measurable": 4, "folds_retained": 2, "median_retention": 0.5469,
        "folds": [
            {"fold": 1, "train_start": "2021-03-01", "test_end": "2022-01-01",
             "measurable": True, "retention": 0.9, "dates_honoured": True},
            {"fold": 2, "measurable": False, "timed_out": True,
             "reason": "the engine hit its wall-clock ceiling"},
        ],
    }
    w.update(over)
    return w


# --- the payload actually survives -----------------------------------------


def test_the_equity_curve_and_the_fills_survive_capture():
    """THE headline defect. The curve existed in memory and reached no store."""
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    res = a["verification"]["result"]
    assert res["equity_curve"] == [100.0, 101.0]
    assert res["equity_dates"] == ["2025-01-02", "2025-01-03"]
    assert res["benchmark_curve"] == [100.0, 100.5]
    assert res["orders"][0]["symbol"] == "SPY"
    assert res["robustness"]["psr_pct"] == 0.584
    assert res["capacity"]["capacity_usd"] == 341381399.49


def test_the_per_fold_rows_survive_capture():
    """The rows the quant seat had to reconstruct 'from sweeps by grid-key luck'
    (run-quant-entry11, accepted 2026-08-21)."""
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    rows = ra.folds(a)
    assert rows is not None and len(rows) == 2
    assert rows[0]["dates_honoured"] is True
    assert rows[1]["timed_out"] is True


def test_the_cost_sweep_band_survives_capture():
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    assert a["sweep"]["summary"]["breakeven_cost"]["breakeven_bps"] == 5.92
    assert a["sweep"]["points"][0]["total_return_pct"] == 42.456


def test_container_paths_are_dropped_because_they_stop_resolving():
    """`raw_files` points inside a results directory pruned within a day. Storing
    it in the durable envelope would preserve a link that is already broken."""
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    assert "raw_files" not in a["verification"]["result"]


def test_a_sweep_point_does_not_drag_a_whole_result_into_the_envelope():
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    assert "result" not in a["sweep"]["points"][0]


def test_truncating_the_fill_list_is_announced_never_silent():
    """A table silently cut in half would misstate what the strategy did."""
    many = _job()
    many["result"]["orders"] = [{"symbol": "SPY"}] * (ra.MAX_ORDERS + 5)
    res = ra.capture(job=many, sweep=_sweep(), walkforward=_walk())["verification"]["result"]
    assert len(res["orders"]) == ra.MAX_ORDERS
    assert res["orders_truncated"] is True
    assert res["orders_total"] == ra.MAX_ORDERS + 5
    assert str(ra.MAX_ORDERS + 5) in res["orders_truncated_note"]


def test_a_fill_list_inside_the_cap_is_not_marked_truncated():
    res = ra.capture(job=_job(), sweep=_sweep(),
                     walkforward=_walk())["verification"]["result"]
    assert "orders_truncated" not in res
    assert "orders_total" not in res


# --- the four absences, each distinct from the others -----------------------


def test_never_captured_is_not_an_empty_panel():
    """The state of all 37 candidates judged before this column existed."""
    v = ra.view(None)
    assert v["available"] is False
    assert v["reason"] == ra.NOT_CAPTURED
    assert "before the belt kept its analytics" in v["note"]
    assert "re-run" in v["note"].lower()


def test_pruned_is_distinguishable_from_never_captured():
    """The reason the prune writes a tombstone rather than setting NULL.

    One had evidence that expired and can be re-run to get it back; the other
    never had any. A NULL for both would send the reader to the wrong place, and
    is the absence-is-not-zero error wearing a retention policy's clothes.
    """
    v = ra.view(ra.pruned(when="2026-11-19T00:00:00+00:00", retention_days=90))
    assert v["available"] is False
    assert v["reason"] == ra.PRUNED
    assert v["reason"] != ra.NOT_CAPTURED
    assert v["pruned_at"] == "2026-11-19T00:00:00+00:00"
    assert "aged out" in v["note"]


def test_a_crashed_walkforward_is_unavailable_and_says_it_was_attempted():
    """Distinct from 'never asked for'. Both used to return a bare None and the
    stored verdict said 'no walk-forward test' for each — true of one, and
    misleading about the other, where the leg ran and threw."""
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=None,
                   walkforward_note="the walk-forward leg raised KeyError: 'folds'")
    wf = a["walkforward"]
    assert wf["present"] is False
    assert wf["reason"] == ra.UNAVAILABLE
    assert "KeyError" in wf["note"]


def test_not_testable_is_not_a_failure_and_carries_the_hold_period():
    """A rule too slow for our history has not been examined. Calling that a
    failure repeats the error the gate spent a week removing."""
    a = ra.capture(job=_job(), sweep=_sweep(),
                   walkforward={"not_testable": True,
                                "note": "1 fold(s) fit; a 63-day hold needs a 252-day test leg",
                                "hold_days": 63, "hold_days_source": "declared"})
    wf = a["walkforward"]
    assert wf["present"] is False
    assert wf["reason"] == ra.NOT_TESTABLE
    assert wf["reason"] != ra.UNAVAILABLE
    assert wf["hold_days"] == 63 and wf["hold_days_source"] == "declared"


def test_a_verification_run_with_no_result_is_named_not_blanked():
    a = ra.capture(job={"job_id": "j", "state": "failed",
                        "error": "timed out after 900s — engine killed"},
                   sweep=_sweep(), walkforward=_walk())
    v = a["verification"]
    assert v["present"] is False
    assert v["reason"] == ra.UNAVAILABLE
    assert "timed out" in v["note"]
    assert v["job_id"] == "j"


def test_folds_returns_none_rather_than_an_empty_list():
    """`[]` reads as 'the walk-forward ran and found no folds' — a claim about
    the strategy. None says the rows are not here."""
    assert ra.folds(None) is None
    assert ra.folds({"walkforward": {"present": False, "reason": ra.UNAVAILABLE}}) is None
    assert ra.folds({"walkforward": {"present": True, "folds": []}}) is None


def test_view_returns_one_shape_so_no_consumer_branches_on_null():
    for a in (None, ra.pruned(), ra.capture(job=_job(), sweep=_sweep(),
                                            walkforward=_walk())):
        v = ra.view(a)
        assert "available" in v
        assert isinstance(v["available"], bool)


def test_a_missing_result_is_none_not_an_empty_dict():
    """`{}` renders as 'ran and produced nothing'; None says there is no result."""
    assert ra.trim_result(None) is None
    assert ra.trim_result({}) is None


def test_the_schema_version_travels_with_the_document():
    """A stored envelope has to say which reader can read it — the same reason
    GATE_VERSION is stamped on every verdict."""
    a = ra.capture(job=_job(), sweep=_sweep(), walkforward=_walk())
    assert a["schema"] == ra.ANALYTICS_SCHEMA
    assert a["captured_at"]
    assert ra.pruned()["schema"] == ra.ANALYTICS_SCHEMA
