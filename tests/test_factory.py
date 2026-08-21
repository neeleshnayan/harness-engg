"""The conveyor belt — one call from hypothesis to verdict, with a memory.

Two properties carry the design. The winner is verified in FULL before it is
judged, because the sweep's own rows carry no costs, benchmark or capacity, and
judging a trimmed row would silently waive most of the bar. And every verdict
is recorded with its failures, so a dead end stays dead instead of being
rediscovered every few weeks with fresh enthusiasm.
"""

import os
import time
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("SKIP_PG_TESTS") == "1", reason="Postgres tests disabled")

TEST_DB = "krypton_fund_test"


class FakeRunner:
    """A LEAN runner that answers instantly and records what it was asked."""

    def __init__(self, passing=False, sweep_state="done", scored=True):
        self.passing, self.sweep_state, self.scored = passing, sweep_state, scored
        self.verified_params = None

    def get_algorithm(self, name):
        if name == "missing":
            from app.fund.leanrunner import LeanError
            raise LeanError("unknown algorithm 'missing'")
        return {"name": name, "code": "class X(QCAlgorithm): pass"}

    def submit_sweep(self, algorithm, grid, holdout=None):
        # Walk-forward folds arrive here too, one sweep per fold. Recorded so a
        # test can assert the belt actually ran them rather than trusting it.
        self.sweeps_requested = getattr(self, "sweeps_requested", 0) + 1
        return {"sweep_id": "sw1"}

    def sweep(self, sweep_id):
        # A cost sweep result is part of what v2 requires: never cost-swept is
        # not the same as robust to costs, and v1 could not tell them apart.
        summary = ({"best": {"parameters": {"fast": "10"}},
                    "breakeven_cost": {"breakeven_bps": 25.0}}
                   if self.scored else {})
        return {"state": self.sweep_state, "algorithm": "a", "summary": summary,
                "points": [{"parameters": {"fast": "10"}, "state": "done",
                            "total_return_pct": 20.0}],
                # Windows added 2026-08-21 so the captured envelope carries what
                # the engine actually covered. EQUAL LENGTH deliberately: the
                # gate annualises each leg over its own window, so unequal ones
                # would silently move this fixture's retention (20/16 cumulative
                # = 0.80, but over 363 vs 588 days = 0.48) and change what the
                # pass/fail tests above are asserting about the GATE rather than
                # about the fixture.
                "holdout_result": {"state": "done", "dates_honoured": True,
                                   "train": {"return_pct": 20.0,
                                             "window": ["2024-01-02", "2024-12-30"]},
                                   "test": {"return_pct": 16.0,
                                            "total_orders": 40,
                                            "window": ["2025-01-02", "2025-12-31"]}}}

    def submit_backtest(self, algorithm, parameters=None):
        self.verified_params = parameters
        return {"job_id": "job1"}

    def job(self, job_id):
        rb = {"total_orders": 40 if self.passing else 3,
              "psr_pct": 80.0 if self.passing else 10.0,
              "costs": {"slippage_modelled": True}}
        return {"state": "done", "algorithm": "a", "parameters": {"fast": "10"},
                "job_id": job_id, "wall_seconds": 11.4,
                "result": {"total_return_pct": 20.0, "benchmark_return_pct": 10.0,
                           "capacity": {"capacity_usd": 5_000_000.0},
                           "equity_curve": [100.0, 110.0, 120.0],
                           "equity_dates": ["2025-01-02", "2025-06-02", "2026-01-02"],
                           "benchmark_curve": [100.0, 105.0, 110.0],
                           "orders": [{"symbol": "SPY", "side": "buy", "qty": 3.0}],
                           "raw_files": ["/Results/job1/out.json"],
                           "robustness": rb}}


def _factory(runner):
    pytest.importorskip("psycopg")
    import psycopg
    from app.fund.pgstore import dsn
    head, _, _ = dsn().rpartition("/")
    test_dsn = f"{head}/{TEST_DB}"
    try:
        conn = psycopg.connect(dsn(), connect_timeout=3, autocommit=True)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"no Postgres reachable: {e}")
    with conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,))
            if not cur.fetchone():
                cur.execute(f'CREATE DATABASE "{TEST_DB}"')
    from app.fund.factory import CandidateFactory
    f = CandidateFactory(runner=runner, dsn_str=test_dsn)
    with psycopg.connect(test_dsn) as c:
        with c.cursor() as cur:
            cur.execute("TRUNCATE fund_candidates")
        c.commit()
    return f


def _settle(f, cid, timeout=15.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        row = f.get(cid)
        if row and row["state"] in ("done", "failed"):
            return row
        time.sleep(0.1)
    raise AssertionError("candidate never settled")


def test_a_failing_candidate_is_killed_with_its_reasons():
    f = _factory(FakeRunner(passing=False))
    cid = f.submit("algo", {"fast": ["10", "20"]})["candidate_id"]
    row = _settle(f, cid)
    assert row["state"] == "done"
    assert row["passed"] is False
    assert any("anecdote" in x for x in row["failures"])
    assert any("luck" in x for x in row["failures"])


def test_a_passing_candidate_is_recorded_as_passed():
    """Gate v2 requires walk-forward evidence, so the belt has to supply it.

    CONTRACT CHANGED (deliberately, 2026-08-17): under v1 this candidate passed
    on a single held-out window. A null audit then showed random strategies
    clearing that bar half the time, so v2 asks for consistency across
    independent folds — and a holdout has to be present for the belt to build
    them from.
    """
    r = FakeRunner(passing=True)
    f = _factory(r)
    cid = f.submit("algo", {"fast": ["10"]},
                   holdout={"train_start": "2024-01-01",
                            "train_end": "2024-12-31",
                            "test_start": "2025-01-01",
                            "test_end": "2026-08-14"})["candidate_id"]
    row = _settle(f, cid)
    assert row["passed"] is True, row["failures"]
    assert row["failures"] == []
    assert row["winner"] == {"fast": "10"}
    # More than one sweep: the grid, plus one per walk-forward fold.
    assert r.sweeps_requested > 1, "the belt never ran the folds"


def test_a_candidate_with_no_holdout_cannot_clear_v2():
    """No holdout means no folds can be built, and gate v2 treats a missing
    walk-forward as a failure rather than a waiver — the whole point of the
    change is that untested is not the same as passed."""
    f = _factory(FakeRunner(passing=True))
    cid = f.submit("algo", {"fast": ["10"]})["candidate_id"]
    row = _settle(f, cid)
    assert row["passed"] is False
    assert any("walk-forward" in x for x in row["failures"]), row["failures"]


def test_the_winner_is_re_run_in_full_before_judgement():
    """The sweep's rows carry no costs, benchmark or capacity — judging one
    would waive most of the bar without saying so."""
    r = FakeRunner(passing=True)
    f = _factory(r)
    _settle(f, f.submit("algo", {"fast": ["10"]})["candidate_id"])
    assert r.verified_params == {"fast": "10"}


def test_history_remembers_why_something_died():
    f = _factory(FakeRunner(passing=False))
    _settle(f, f.submit("algo", {"fast": ["10"]})["candidate_id"])
    hist = f.history("algo")
    assert len(hist) == 1
    assert hist[0]["passed"] is False and hist[0]["failures"]


def test_an_unscored_grid_is_an_error_not_a_verdict():
    """Nothing scored means nothing to judge, and a 'fail' would imply we
    looked at something."""
    f = _factory(FakeRunner(scored=False))
    row = _settle(f, f.submit("algo", {"fast": ["10"]})["candidate_id"])
    assert row["state"] == "failed"
    assert "nothing to judge" in row["error"]


def test_a_failed_sweep_never_produces_a_verdict():
    f = _factory(FakeRunner(sweep_state="failed"))
    row = _settle(f, f.submit("algo", {"fast": ["10"]})["candidate_id"])
    assert row["state"] == "failed"
    assert row["passed"] is None


def test_a_typo_fails_immediately_rather_than_on_the_belt():
    f = _factory(FakeRunner())
    from app.fund.leanrunner import LeanError
    with pytest.raises(LeanError):
        f.submit("missing", {"fast": ["10"]})


def test_the_scoreboard_treats_kills_as_the_product():
    f = _factory(FakeRunner(passing=False))
    _settle(f, f.submit("algo", {"fast": ["10"]})["candidate_id"])
    sb = f.scoreboard()
    assert sb["judged"] == 1 and sb["killed"] == 1 and sb["passed"] == 0
    assert "not a gate" in sb["note"]


# --- the evidence behind the verdict (2026-08-21) ---------------------------
#
# The CEO, three times in one day: "i can see monthend_rebalance_flow but cant
# see the analytics behind". The belt computed the curve, the fills, the cost
# grid and the folds, handed the folds to the gate, and stored none of them.
# These fail if that regresses.

HOLDOUT = {"train_start": "2024-01-01", "train_end": "2024-12-31",
           "test_start": "2025-01-01", "test_end": "2026-08-14"}


def _judged(passing=True, holdout=HOLDOUT):
    r = FakeRunner(passing=passing)
    f = _factory(r)
    cid = f.submit("algo", {"fast": ["10"]}, holdout=holdout)["candidate_id"]
    _settle(f, cid)
    return f, cid


def test_a_verdict_is_stored_with_the_evidence_it_was_computed_from():
    f, cid = _judged()
    row = f.get(cid)
    a = row["analytics"]
    assert a["available"] is True, a
    res = a["verification"]["result"]
    assert res["equity_curve"] == [100.0, 110.0, 120.0]
    assert res["orders"][0]["symbol"] == "SPY"
    assert a["verification"]["job_id"] == "job1"
    assert a["sweep"]["summary"]["breakeven_cost"]["breakeven_bps"] == 25.0


def test_the_per_fold_rows_are_served_on_the_candidate_read():
    """Accepted quant recommendation, run-quant-entry11: the rows had to be
    reconstructed 'from sweeps by grid-key luck'. Each carries its requested
    dates and dates_honoured."""
    f, cid = _judged()
    folds = f.get(cid)["walkforward"]["folds"]
    assert folds, "the belt ran the folds and stored none of them"
    assert {"train_start", "train_end", "test_start", "test_end"} <= set(folds[0])
    assert "dates_honoured" in folds[0]


def test_the_index_read_serves_folds_but_not_the_curve():
    """~80 KB of curve per candidate has one reader — the panel for the run you
    opened. The folds are a kilobyte and the index is unreadable without them."""
    f, cid = _judged()
    row = next(r for r in f.history("algo") if r["candidate_id"] == cid)
    assert row["walkforward"]["folds"]
    assert row["analytics_available"] is True
    assert "analytics" not in row


def test_a_candidate_judged_before_capture_reads_as_not_captured_not_empty():
    """The live state of every candidate judged before 2026-08-21. An empty
    panel would say 'this ran and produced nothing', which is a claim about the
    strategy rather than about our storage."""
    import psycopg
    from app.fund import runanalytics
    f, cid = _judged()
    with psycopg.connect(f._dsn) as c:
        with c.cursor() as cur:
            cur.execute("UPDATE fund_candidates SET analytics = NULL "
                        "WHERE candidate_id = %s", (cid,))
        c.commit()
    row = f.get(cid)
    assert row["analytics"]["available"] is False
    assert row["analytics"]["reason"] == runanalytics.NOT_CAPTURED
    assert row["analytics_available"] is False
    assert row["analytics_absence"]["reason"] == runanalytics.NOT_CAPTURED
    # The verdict is still there. Absent evidence never removes the judgement.
    assert row["verdict"]["gate_version"]


def test_pruning_leaves_a_tombstone_and_never_a_null():
    """Pruned and never-captured must stay distinguishable: one has evidence
    that expired and is re-runnable, the other never had any."""
    from app.fund import runanalytics
    f, cid = _judged()
    out = f.prune_analytics(max_age_days=0, keep_newest=0)
    assert cid in out["pruned"], out
    row = f.get(cid)
    assert row["analytics"]["available"] is False
    assert row["analytics"]["reason"] == runanalytics.PRUNED
    assert row["analytics"]["reason"] != runanalytics.NOT_CAPTURED
    assert row["analytics"]["pruned_at"]


def test_pruning_is_idempotent_and_does_not_re_report_a_tombstone():
    f, cid = _judged()
    f.prune_analytics(max_age_days=0, keep_newest=0)
    again = f.prune_analytics(max_age_days=0, keep_newest=0)
    assert again["count"] == 0, "a tombstone was pruned a second time"


def test_the_newest_candidates_survive_the_prune_whatever_their_age():
    """Age alone is the wrong rule: after an idle month every row is stale and
    the most recent evidence anyone has would be swept."""
    f, cid = _judged()
    out = f.prune_analytics(max_age_days=0, keep_newest=1)
    assert out["count"] == 0
    assert f.get(cid)["analytics"]["available"] is True


def test_an_errored_candidate_stores_no_analytics_and_says_so():
    """A sweep that failed produced no evidence — the row must not imply one."""
    from app.fund import runanalytics
    f = _factory(FakeRunner(sweep_state="failed"))
    cid = f.submit("algo", {"fast": ["10"]})["candidate_id"]
    _settle(f, cid)
    row = f.get(cid)
    assert row["state"] == "failed"
    assert row["analytics"]["available"] is False
    assert row["analytics"]["reason"] == runanalytics.NOT_CAPTURED


def test_a_candidate_with_no_holdout_records_why_the_folds_are_missing():
    """'Never asked for' and 'attempted and crashed' both returned a bare None,
    so the stored verdict read 'no walk-forward test' for each — true of one and
    misleading about the other."""
    from app.fund import runanalytics
    f, cid = _judged(holdout=None)
    wf = f.get(cid)["analytics"]["walkforward"]
    assert wf["present"] is False
    assert wf["reason"] == runanalytics.UNAVAILABLE
    assert "no holdout window was supplied" in wf["note"]
