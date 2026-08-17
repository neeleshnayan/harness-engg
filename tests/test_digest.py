"""The morning digest: a reading order that never invents a number.

Two properties under test. Silence must READ as silence — "nothing was read
overnight" is a finding about the schedule, and an empty section the eye skips is
not. And one broken subsystem must not blank the page: a digest that fails closed
teaches the operator to stop opening it, which is precisely the failure it exists
to prevent.
"""

from datetime import datetime, timedelta, timezone

from app.fund.digest import build, _headline, _judged_note


class FakeObs:
    def __init__(self, rows=None, band=None):
        self._rows = rows or []
        self._band = band or {"measured": False}

    def since(self, when):
        return self._rows

    def coverage(self, adv_lo=None, adv_hi=None):
        return {"observations": len(self._rows), "band": self._band}


class FakeFactory:
    def __init__(self, rows):
        self._rows = rows

    def history(self, limit=50):
        return self._rows


def _cand(passed, failures=None, when=None):
    return {"candidate_id": "abc", "algorithm": "x", "passed": passed,
            "failures": failures or [],
            "finished_at": (when or datetime.now(timezone.utc)).isoformat()}


def test_an_idle_loop_is_reported_as_idle_not_as_a_clean_page():
    out = build(observations=FakeObs([]), factory=FakeFactory([]))
    assert out["read"]["overnight"] == 0
    assert "finding about the schedule" in out["read"]["note"]
    assert "loop was idle" in out["headline"]


def test_a_broken_subsystem_does_not_blank_the_page():
    class Exploding:
        def since(self, when):
            raise RuntimeError("postgres is down")

        def coverage(self, **k):
            raise RuntimeError("postgres is down")

    out = build(observations=Exploding(), factory=FakeFactory([]))
    assert "unavailable" in out["read"]
    # The rest of the page still rendered.
    assert "judged" in out and "headline" in out


def test_a_crashed_candidate_is_never_counted_as_a_failure():
    """A run nobody scored is not evidence. Folding it into the failures would
    inflate the appearance of rigour with runs that never happened."""
    out = build(observations=FakeObs([]),
                factory=FakeFactory([_cand(True), _cand(False, ["died"]),
                                     _cand(None)]))
    j = out["judged"]
    assert (j["passed"], j["failed"], j["unjudged"]) == (1, 1, 1)
    assert "not evidence either way" in j["note"]


def test_the_gates_own_sentences_are_carried_verbatim():
    """The wording IS the evidence — a tidier paraphrase is a weaker claim."""
    sentence = "kept only -21% of its edge out of sample; 50% is the floor"
    out = build(observations=FakeObs([]),
                factory=FakeFactory([_cand(False, [sentence])]))
    assert out["judged"]["deaths"][0]["because"] == [sentence]


def test_a_passing_candidate_asks_for_a_human_and_says_why():
    out = build(observations=FakeObs([]), factory=FakeFactory([_cand(True)]))
    assert out["needs_you"]["count"] == 1
    assert "passing is not deploying" in out["needs_you"]["items"][0]["why_you"]


def test_a_broken_chain_outranks_every_other_headline():
    """Worst news first: a broken chain must beat a good backtest, because it
    changes whether any number on the page can be trusted."""
    class Store:
        def verify_chain(self):
            return {"ok": False, "checked": 12}

    out = build(store=Store(), observations=FakeObs([]),
                factory=FakeFactory([_cand(True)]))
    assert "CHAIN DOES NOT VERIFY" in out["headline"]


def test_nav_is_reported_only_when_it_was_actually_computed():
    """Never a placeholder. The digest is the page nobody double-checks, so an
    invented figure here is the most dangerous number in the fund."""
    out = build(observations=FakeObs([]), factory=FakeFactory([]), nav=None)
    assert "nav_usd" not in out["health"]
    out2 = build(observations=FakeObs([]), factory=FakeFactory([]),
                 nav={"total_nav_usd": 2026.89})
    assert out2["health"]["nav_usd"] == 2026.89


def test_an_empty_belt_says_the_loop_did_not_run():
    assert "did not run" in _judged_note(0, 0, 0, 0)


def test_a_calibration_run_is_never_presented_as_a_proposal():
    """Three random-entry nulls cleared gate v1, and the digest promptly asked a
    human to review them as opportunities. A null that passes is a finding about
    the GATE; putting it on the same page as a real proposal is how a measuring
    instrument gets mistaken for a discovery."""
    out = build(observations=FakeObs([]),
                factory=FakeFactory([
                    {"candidate_id": "n1", "algorithm": "null_random_smallcap",
                     "passed": True, "failures": [],
                     "finished_at": datetime.now(timezone.utc).isoformat()},
                ]))
    assert out["needs_you"]["count"] == 0, out["needs_you"]["items"]
    # Counted, not hidden: the belt DID run, and concealing that would make the
    # night look quieter than it was.
    assert out["judged"]["calibration_runs"] == 1
    assert "NOT proposals" in out["judged"]["note"]


def test_a_real_candidate_alongside_a_null_still_asks_for_the_human():
    out = build(observations=FakeObs([]),
                factory=FakeFactory([
                    {"candidate_id": "n1", "algorithm": "null_random_smallcap",
                     "passed": True, "failures": [],
                     "finished_at": datetime.now(timezone.utc).isoformat()},
                    _cand(True),
                ]))
    assert out["needs_you"]["count"] == 1
    assert out["judged"]["candidates"] == 1
    assert out["judged"]["calibration_runs"] == 1


def test_a_failing_DEPLOYED_strategy_needs_a_human():
    """The digest reported "nothing needs a decision today" on the exact morning
    three deployed strategies failed the gate. A passing candidate is an
    opportunity; a failing deployed one is live money governed by something that
    just did not survive its own test, and it outranks everything else on the
    page."""
    out = build(observations=FakeObs([]),
                factory=FakeFactory([
                    {"candidate_id": "c1", "algorithm": "momentum_large_cap_tech",
                     "passed": False, "failures": ["an expensive way to hold it"],
                     "finished_at": datetime.now(timezone.utc).isoformat()},
                ]),
                deployed={"momentum_large_cap_tech"})
    assert out["needs_you"]["count"] == 1
    item = out["needs_you"]["items"][0]
    assert item["kind"] == "deployed_strategy_failed"
    assert "nothing here changes a position" in item["why_you"]
    assert "DEPLOYED strategy(s) failed" in out["headline"]


def test_a_failing_RESEARCH_candidate_asks_for_nothing():
    """Research is supposed to fail. Only live money makes a failure a decision."""
    out = build(observations=FakeObs([]),
                factory=FakeFactory([_cand(False, ["died honestly"])]),
                deployed={"something_else"})
    assert out["needs_you"]["count"] == 0
    assert "died" in out["headline"]
