"""POST /fund/lean/gate/judge/{job_id} — which BAR the manual path applies.

THE DEFECT THIS FILE EXISTS FOR (adversary, D23 blind review, 2026-08-23,
docs/reviews/ADVERSARY_D23_D24_2026-08-23.md, non-loosening defect 1):

    "POST /fund/lean/gate/judge/{job_id} (fund.py:2548-2566) accepts no
    claim_type — a premia candidate re-judged there silently reverts to the
    alpha bar and is stamped v4.3. The factory path IS wired."

And the reason it survived to be found by a reviewer rather than by the suite:
before this file, ZERO tests had ever called this endpoint. That is the same
shape as `POST /fund/risk/resume` (builder D17) — an endpoint with no test
survives adversary review of the module around it. The absence was the finding
both times.

Everything here drives the REAL route through a real TestClient, because the
contract under test is what the DOOR does with a query parameter, and a test
that called `evaluate` directly would have passed against the broken version.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class FakeLean:
    """Enough of a LeanRunner for the two reads this endpoint performs."""

    def __init__(self, job, sweep):
        self._job, self._sweep = job, sweep
        self.calls: list[str] = []

    def job(self, job_id):
        self.calls.append(f"job:{job_id}")
        if job_id != "J1":
            from app.fund.leanrunner import LeanError
            raise LeanError(f"no such job {job_id}")
        return self._job

    def sweep(self, sweep_id):
        self.calls.append(f"sweep:{sweep_id}")
        if sweep_id != "S1":
            from app.fund.leanrunner import LeanError
            raise LeanError(f"no such sweep {sweep_id}")
        return self._sweep


def _result():
    """A premia-shaped result whose two bars DISAGREE, which is the whole point.

    The strategy trails its benchmark on total return — so the ALPHA bar fails
    it on `must_beat_benchmark` — while carrying no premia inputs, so the PREMIA
    bar fails it on the unmeasured comparison. Two different failure sentences
    and two different version stamps, which is how a test can tell which bar
    ran. A fixture that failed both bars the same way could not.
    """
    return {
        "total_return_pct": 5.0, "benchmark_return_pct": 60.0,
        "capacity": {"capacity_usd": 5_000_000.0},
        "robustness": {"psr_pct": 92.0, "total_orders": 300,
                       "costs": {"slippage_modelled": True}},
    }


@pytest.fixture()
def client(monkeypatch):
    from app.api.v1 import fund as fundapi
    lean = FakeLean(
        job={"state": "done", "algorithm": "algo_x",
             "parameters": {"lookback": 20}, "result": _result()},
        sweep={"holdout_result": None, "summary": None})
    monkeypatch.setattr(fundapi, "_lean", lambda: lean)
    app = FastAPI()
    app.include_router(fundapi.router, prefix="/api/v1")
    c = TestClient(app)
    c.lean = lean
    return c


URL = "/api/v1/fund/lean/gate/judge/J1"


def test_the_default_is_alpha_and_is_stamped_v43(client):
    r = client.post(URL, params={"sweep_id": "S1"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gate_version"] == "v4.3"
    assert body["checks"]["claim_type"] == "alpha"
    assert body["checks"]["must_beat_benchmark_applied"] is True
    assert any("expensive way to hold the underlying" in f
               for f in body["failures"])


def test_a_premia_candidate_is_judged_by_the_PREMIA_bar_not_the_alpha_one(
        client):
    """THE DEFECT, as a verdict difference rather than a field difference.

    Before the fix this call returned the alpha verdict — `must_beat_benchmark`
    applied to a claim type whose entire definition is that it must not be, and
    the stored stamp said v4.3 so nothing in the record showed which bar had
    run.
    """
    r = client.post(URL, params={"sweep_id": "S1", "claim_type": "premia"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gate_version"] == "v5r3-premia"
    assert body["checks"]["claim_type"] == "premia"
    assert body["checks"]["must_beat_benchmark_applied"] is False
    assert not any("expensive way to hold the underlying" in f
                   for f in body["failures"])
    # And it still FAILS — on the premia sentence, because this run carries no
    # captured comparison. Fail closed, not "premia therefore easier".
    assert body["passed"] is False
    assert any("premia comparison could not be measured" in f
               for f in body["failures"])


@pytest.mark.parametrize("bad", ["premai", "Premia", "beta", "", "alpha "])
def test_an_unknown_claim_type_is_REFUSED_not_silently_judged(client, bad):
    """Fail closed in BOTH directions.

    The gate's own answer to an unknown type is to apply the alpha bar and add a
    failure — safe, but silent about the typo, and it spends a verdict. At the
    door the honest answer is 400 with the vocabulary named, and crucially the
    job is never even read: `calls` is empty, so a refusal cannot be mistaken
    for a judgement that happened to fail.
    """
    r = client.post(URL, params={"sweep_id": "S1", "claim_type": bad})
    assert r.status_code == 400, r.text
    assert "unknown claim type" in r.json()["detail"]
    assert client.lean.calls == []


def test_the_endpoints_vocabulary_is_the_GATES_vocabulary(client):
    """One definition of what a claim type is, not three.

    MOVE test (D16): if the door held its own copy of the list, adding a type to
    the gate would leave the door refusing it. Asserting that `premia` is
    accepted and `beta` is not cannot distinguish a read from a copy; monkey-
    patching the gate's tuple can.
    """
    from app.fund import gate
    r = client.post(URL, params={"sweep_id": "S1", "claim_type": "beta"})
    assert r.status_code == 400
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(gate, "CLAIM_TYPES", ("alpha", "premia", "beta"))
        r2 = client.post(URL, params={"sweep_id": "S1", "claim_type": "beta"})
    assert r2.status_code == 200, r2.text


def test_a_missing_job_or_sweep_is_a_404_and_a_running_job_is_a_409(
        client, monkeypatch):
    """The pre-existing refusals still refuse, and in the same order.

    The claim-type check was inserted BEFORE these reads deliberately — an
    unknown type should not cost a store lookup — so this pins that the reads
    still happen for a good type, and still produce their own codes.
    """
    assert client.post("/api/v1/fund/lean/gate/judge/NOPE",
                       params={"sweep_id": "S1"}).status_code == 404
    assert client.post(URL, params={"sweep_id": "NOPE"}).status_code == 404
    client.lean._job = {**client.lean._job, "state": "running"}
    r = client.post(URL, params={"sweep_id": "S1", "claim_type": "premia"})
    assert r.status_code == 409
    assert "running" in r.json()["detail"]
