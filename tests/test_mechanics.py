"""The mechanics view must not flatter the fund.

The first version of this module built its funnel from the factory scoreboard and
told a completely false story: "19 swept -> 3 survived -> 3 deployed". Every part of
that was wrong in the same direction. All three passes were `null_random_smallcap` —
random noise leaking through an older gate — and the three deployed strategies are
not those three; they predate the gate and currently fail it. Two misreadings
stacked into one plausible funnel.

So these tests mostly assert that the view REFUSES to flatter: instruments stay out
of the survival rate, an unavailable subsystem never renders as zero, and the
unbuilt rungs of the evolution ladder stay unlit.
"""

from __future__ import annotations

from app.fund import mechanics
from app.fund.mechanics import _cause, build


def _cand(algorithm, passed, failures=(), grid=None,
          finished="2026-08-17T00:00:00Z"):
    return {"candidate_id": f"{algorithm}-{passed}-{len(failures)}-{finished}",
            "algorithm": algorithm, "state": "done", "passed": passed,
            "failures": list(failures), "grid": grid or {}, "winner": None,
            "finished_at": finished}


CANDIDATES = {
    "scoreboard": {"submitted": 4, "judged": 4, "passed": 2, "killed": 2},
    "candidates": [
        # Two instruments, and BOTH pass. A null passing is the gate leaking.
        _cand("null_random_smallcap", True),
        _cand("null_random_smallcap", True, finished="2026-08-17T01:00:00Z"),
        # Two genuine research attempts, both killed.
        _cand("xs_momentum_smallcap", False,
              ["probabilistic Sharpe 2.9% is below 65.0%"],
              {"top_n": ["3", "5"], "hold_days": ["21", "63"]}),
        _cand("mean_reversion_cyclicals", False,
              ["returns 9% against 34% for simply owning it"]),
    ],
}
STRATEGIES = {"strategies": [
    {"strategy_id": "a", "name": "A", "state": "deployed", "depth": 0,
     "assets": ["INTC"]},
    {"strategy_id": "b", "name": "B", "state": "draft", "depth": 0, "assets": []},
]}


def test_the_funnel_excludes_calibration_instruments():
    """The exact regression. Instruments must never enter the survival rate."""
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    steps = {s["step"]: s["count"] for s in out["funnel"]["steps"]}
    assert steps["Swept"] == 2, "instruments leaked into the research funnel"
    assert steps["Judged"] == 2
    assert steps["Survived"] == 0, (
        "a null passing was counted as a research survivor — the exact bug this "
        "module shipped with")


def test_the_leak_is_reported_separately_and_named_a_leak():
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    cal = out["funnel"]["calibration"]
    assert cal["submitted"] == 2 and cal["passed"] == 2
    assert "leak" in cal["note"].lower()
    assert "not attempts to make money" in cal["note"]
    # It must now ATTRIBUTE each leak to the generation that let it through. The
    # verdict column carried gate_version from day one and was never SELECTed, so
    # this used to read "a stored verdict does not record which version judged it"
    # — a gap that existed only in the reader.
    assert "RESOLVED" in cal["caveat"]
    assert cal["by_gate_version"] == {"unrecorded": 2}, cal["by_gate_version"]


def test_a_leak_is_attributed_to_the_gate_generation_that_let_it_through():
    """Reading the cohort as evolution needs the bar each verdict actually faced.

    Live at the time of writing: all three nulls that ever passed were judged
    under v1, which is the generation the calibration effort then replaced.
    """
    rows = list(CANDIDATES["candidates"])
    rows[0] = {**rows[0], "gate_version": "v1"}
    rows[1] = {**rows[1], "gate_version": "v1"}
    out = build(candidates={**CANDIDATES, "candidates": rows},
                strategies=STRATEGIES)
    assert out["funnel"]["calibration"]["by_gate_version"] == {"v1": 2}
    cohort = {c["algorithm"]: c for c in out["cohort"]["candidates"]}
    assert cohort["null_random_smallcap"]["gate_version"] == "v1"


def test_deployed_is_not_presented_as_downstream_of_survived():
    """0 survived and 1 deployed is not a funnel, and must not be drawn as one."""
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    dep = [s for s in out["funnel"]["steps"] if s["step"] == "Deployed"][0]
    assert dep["count"] == 1
    assert "NOT downstream" in (dep["absent_note"] or "")


def test_an_unavailable_subsystem_is_uncounted_not_zero():
    out = build(candidates=CANDIDATES, strategies=STRATEGIES, observations=None)
    read = [s for s in out["funnel"]["steps"] if s["step"] == "Read"][0]
    assert read["count"] is None, "an absent research store rendered as a count"
    assert "UNCOUNTED" in (read["absent_note"] or "")


def test_variation_is_counted_as_the_grid_product():
    """A candidate is a population, not an organism: 2 x 2 = 4 variants."""
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    rows = {c["algorithm"]: c for c in out["cohort"]["candidates"]}
    assert rows["xs_momentum_smallcap"]["variants"] == 4
    assert rows["mean_reversion_cyclicals"]["variants"] == 1
    swept = [s for s in out["funnel"]["steps"] if s["step"] == "Swept"][0]
    assert "5 parameter variants" in swept["what"]


def test_absence_and_failure_are_different_causes():
    """No-trades is the test not happening; kept-14% is a bad measurement."""
    assert _cause("the held-out test placed no trades at all, so it says nothing") \
        == "Holdout never traded (absence, not failure)"
    assert _cause("kept only 14% of its edge out of sample; 50% is the floor") \
        == "Edge did not survive out of sample"


def test_every_failure_sentence_maps_to_a_named_cause():
    """An 'Other' bucket hides what is doing the killing.

    Measured live: 'Other' was 20.5% of the chart until the two holdout sentences
    were mapped. The chart's whole job is to say which criterion earns its keep.
    """
    live = [
        "cost robustness was never measured (no cost sweep was run)",
        "kept its edge in only 0 of 4 independent folds (0%), under the floor",
        "only 13 fills; 20 is the minimum before a Sharpe describes anything",
        "returns 64% against 411% for simply owning it",
        "probabilistic Sharpe 2.983% is below 65.0%",
        "only 2 fold(s) could be measured, below the 3 required",
        "kept only -10% of its edge out of sample; 50% is the floor",
        "the held-out test placed no trades at all, so it says nothing either way",
        "NOT TESTABLE on the history available",
    ]
    for f in live:
        assert _cause(f) != "Other", f"unmapped failure sentence: {f}"


def test_the_unbuilt_rungs_stay_unlit():
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    by = {r["rung"]: r["status"] for r in out["ladder"]["rungs"]}
    assert by["Specialisation by domain"] == "not started"
    assert by["Selection by a calibrated gate"] == "running"
    assert "phylogeny we do not have" in out["ladder"]["note"]

    # Population search moved blocked -> partial when the vectorised sieve landed.
    # It must NOT read "running": the sieve's signal path has never been compared
    # against LEAN on the same spec, so it is trusted to reject and never to
    # approve, and 101 LEAN-hours for a full search is unblocked rather than cheap.
    pop = by["Population search"]
    assert pop == "partial", f"population search is {pop!r}"
    detail = next(r["detail"] for r in out["ladder"]["rungs"]
                  if r["rung"] == "Population search")
    assert "never been compared against LEAN" in detail
    assert "not cheap" in detail


def test_the_arc_carries_evidence_on_every_beat():
    """A beat without a number behind it is mythology, and drifts like it."""
    out = build(candidates=CANDIDATES, strategies=STRATEGIES)
    beats = out["arc"]["beats"]
    assert len(beats) >= 7
    for b in beats:
        assert b["title"].strip() and b["body"].strip()
        assert b["evidence"].strip(), f"beat {b['beat']} has no evidence"
    # The arc must end where the fund actually is, not where it hopes to be.
    last = beats[-1]
    assert last["at"] == "now"
    assert "not yet evolution" in last["body"]


def test_the_timeline_uses_utc_for_both_streams():
    """Build marks dated by the local calendar sat a day AFTER their effects."""
    for b in mechanics.BUILD_MARKS:
        assert b["at"] == "2026-08-17", (
            "a build mark drifted off the UTC axis; the exit wiring is logged at "
            "2026-08-17T19:58Z and marks must share that day")
    out = build(candidates=CANDIDATES, strategies=STRATEGIES,
                events={"events": [
                    {"seq": 1, "type": "ExitRuleTriggered",
                     "ts": "2026-08-17T19:58:29Z",
                     "payload": {"symbol": "INTC", "reason": "fired"}},
                    {"seq": 2, "type": "NavStruck", "ts": "2026-08-17T18:00:00Z",
                     "payload": {}},
                ]})
    t = out["timeline"]
    assert t["window"]["days"] >= 1
    assert any(mk["type"] == "ExitRuleTriggered" for mk in t["marks"])
    # NavStruck is deliberately NOT a milestone — thousands of them would bury the
    # few events that changed how the fund works.
    assert all(mk["type"] != "NavStruck" for mk in t["marks"])
    assert "UTC" in t["caveat"]


def test_a_broken_block_does_not_blank_the_page():
    class Boom(dict):
        def get(self, *a, **k):
            raise RuntimeError("subsystem down")

    # Seeded so it is TRUTHY. An empty dict short-circuits `candidates or {}` and
    # never reaches .get — the first version of this test passed a falsy Boom and
    # was therefore testing nothing at all.
    out = build(candidates=Boom(sentinel=1), strategies=STRATEGIES)
    assert "unavailable" in out["funnel"]
    # Other blocks still rendered.
    assert out["selector"]["generations"]


def test_the_selector_lineage_names_what_killed_each_generation():
    out = build(candidates=CANDIDATES, strategies=STRATEGIES, gate_version="v4")
    gens = out["selector"]["generations"]
    assert [g["version"] for g in gens] == ["v1", "v2", "v3", "v4"]
    assert gens[-1]["died_of"] is None, "the current generation cannot be dead"
    for g in gens[:-1]:
        assert g["died_of"] and g["metric"]
    assert "loosening" in gens[2]["died_of"].lower()
