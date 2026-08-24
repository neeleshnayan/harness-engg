"""The desk-stage contract: this repo's half of a test that crosses a repo.

THE INCIDENT (adversary kill, 2026-08-22). The CEO's desk counter and the CEO's
desk PAGE live in two repositories. The repair that made the spine the single
definition of "whose move is it" was shipped with a defect of exactly the shape
it was fixing — a row at status `accepted` carrying `next_actor: "ceo"` counted
as CEO load here and rendered as "shown, never counted" there — and **both
suites went green over it**: 12/12 TypeScript, 70/70 pytest. Each suite pinned
its own side. Nothing in either crossed the boundary, so nothing could disagree.

Two green suites pinning opposite behaviours in two repos is how that shipped,
and it is the only failure mode this file exists to make impossible.

WHAT THIS FILE ASSERTS, and what it deliberately does not:

  * ASSERTS that `contract/desk_stage_contract.v1.json` — the artifact checked
    in to BOTH repos, byte-identical — still describes what `desk.py` does RIGHT
    NOW. Change the routing without regenerating and this fails, naming the
    case. That is the producing side of the lock.
  * ASSERTS the contract is internally honest: its `counted_for_ceo` flags sum
    to the `desk_load` total it states, and its stage mapping agrees with that
    partition. A contract that contradicts itself would let the two repos agree
    on a lie.
  * DOES NOT run TypeScript. `deskStageContract.test.ts` in KryptonPay consumes
    the same bytes, runs the page's own functions over the same rows, and
    asserts the same total. The digest is pinned in both places, so neither copy
    moves without a human touching a test.

The residual hole is named rather than papered over: this repo regenerated
while the other copy stays stale is invisible to both hermetic suites, because
there is no shared build. `desk_load` therefore publishes `contract_digest` and
the CEO page renders a warning when the live spine's digest differs from the one
its fixture carries — the drift is detected against a live spine, on screen,
rather than silently.
"""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.fund import desk as desk_mod

REPO = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO / "contract" / "desk_stage_contract.v1.json"

#: The KryptonPay path the other half lives at. Named in failure messages so a
#: reader who breaks this knows the second place they must go.
SIBLING = "KryptonPay/contract/desk_stage_contract.v1.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    assert CONTRACT_PATH.exists(), (
        f"the desk-stage contract is missing. Regenerate it with "
        f"`python scripts/gen_desk_contract.py` — the CEO's desk counter and "
        f"the CEO's desk page have no other shared definition.")
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


class TestTheContractStillDescribesTheCode:
    def test_the_checked_in_contract_matches_desk_py_right_now(self):
        """THE PRODUCING SIDE OF THE LOCK.

        Regenerating from `desk.py` must reproduce the checked-in bytes. If it
        does not, the routing changed and the contract did not — which means
        KryptonPay is now pinning a behaviour this repo no longer has, and the
        two suites are free to go green on opposite answers again.
        """
        sys.path.insert(0, str(REPO / "scripts"))
        import gen_desk_contract  # noqa: PLC0415

        fresh = gen_desk_contract.build()
        onfile = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if fresh != onfile:
            diffs = []
            for i, (a, b) in enumerate(zip(fresh.get("cases", []),
                                           onfile.get("cases", []))):
                if a != b:
                    diffs.append(f"  case {i} {a.get('name')!r}: "
                                 f"desk.py now says {a.get('expect')}, "
                                 f"the contract says {b.get('expect')}")
            if fresh.get("expect_totals") != onfile.get("expect_totals"):
                diffs.append(f"  totals: desk.py {fresh.get('expect_totals')} "
                             f"vs contract {onfile.get('expect_totals')}")
            pytest.fail(
                "`desk.py`'s routing no longer matches the checked-in "
                "desk-stage contract:\n" + "\n".join(diffs or ["  (shape differs)"])
                + "\n\nRun `python scripts/gen_desk_contract.py`, copy the file "
                f"to {SIBLING}, and update CONTRACT_DIGEST in that repo's "
                "deskStageContract.test.ts. Both suites fail until you do — "
                "which is the point: two repos went green on opposite answers "
                "once already.")

    def test_the_generator_is_runnable_as_documented(self):
        """The regenerate instruction in every failure message above must
        actually work. A repair procedure nobody has executed is a procedure
        that does not exist — this fund's oldest lesson, applied to a script.

        `--check`, NOT a bare run. The first version of this test invoked the
        writing path, so the artifact the assertion above compares against was
        being REPLACED by the run under test — under any reordering that test
        would have compared the file to itself and gone green over a routing
        change. A test that repairs the thing it is checking is the exact
        pattern this contract exists to stop, and it appeared here, in the file
        written to stop it, on the first draft.
        """
        before = CONTRACT_PATH.read_bytes()
        r = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "gen_desk_contract.py"),
             "--check"],
            capture_output=True, text=True, cwd=str(REPO), timeout=120)
        assert r.returncode == 0, (
            f"`gen_desk_contract.py --check` says the checked-in contract is "
            f"stale:\n{r.stdout}\n{r.stderr}")
        # BOTH contracts in one command since 2026-08-24 — the card contract
        # joined the stage contract, and checking them separately would let one
        # be regenerated while the other went quietly stale, which is the drift
        # this whole mechanism exists to make impossible.
        assert "OK desk_stage_contract.v1.json digest" in r.stdout
        assert "OK desk_card_contract.v1.json digest" in r.stdout
        assert CONTRACT_PATH.read_bytes() == before, (
            "--check must never write; a checker that edits its subject "
            "cannot fail")

    def test_the_rules_version_travels_with_the_contract(self, contract):
        """A reader must be able to tell WHICH rules produced the numbers they
        are looking at, on either side of the boundary."""
        assert contract["rules_version"] == desk_mod.NEXT_ACTOR_RULES_VERSION

    def test_the_digest_is_recomputed_not_believed(self, contract):
        """A self-declared digest nobody checks is a label, and this fund has a
        rule about labels. Both repos recompute; neither trusts the field."""
        body = dict(contract)
        stated = body.pop("digest")
        actual = hashlib.sha256(json.dumps(
            body, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode("utf-8")).hexdigest()
        assert actual == stated

    def test_the_spine_publishes_the_digest_it_actually_has(self):
        """`desk_load` must publish the digest of the file on disk, so a client
        can compare. It must publish `None` rather than a guess when the file
        cannot be read — an unverifiable agreement is reported unverified."""
        load = desk_mod.desk_load([], [], [])
        assert "contract_digest" in load
        assert load["contract_digest"] == desk_mod.CONTRACT_DIGEST
        assert desk_mod.CONTRACT_DIGEST == json.loads(
            CONTRACT_PATH.read_text(encoding="utf-8"))["digest"]

    def test_an_unreadable_contract_reports_absent_never_agreement(self,
                                                                   monkeypatch):
        """A spine deployed without the contract file must not claim a digest.

        Absence is never zero, and here it is never "agrees" either: a client
        comparing `None` renders "unverified", while a client comparing a
        fabricated value would render agreement it never established.
        """
        monkeypatch.setattr(Path, "read_text",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("nope")))
        assert desk_mod._contract_digest() is None

    def test_a_tampered_contract_reports_absent(self, tmp_path, monkeypatch):
        """A file whose body no longer matches its own digest is not a
        contract. It reports absent rather than publishing either value."""
        body = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        body["cases"][0]["expect"]["counted_for_ceo"] = not \
            body["cases"][0]["expect"]["counted_for_ceo"]
        bad = tmp_path / "desk_stage_contract.v1.json"
        bad.write_text(json.dumps(body), encoding="utf-8")

        real_read = Path.read_text

        def fake_read(self, *a, **k):
            if self.name == "desk_stage_contract.v1.json":
                return real_read(bad, *a, **k)
            return real_read(self, *a, **k)

        monkeypatch.setattr(Path, "read_text", fake_read)
        assert desk_mod._contract_digest() is None


class TestTheContractIsInternallyHonest:
    """A contract that contradicts itself would let two repos agree on a lie."""

    def test_counted_flags_sum_to_the_stated_desk_load_total(self, contract):
        counted = sum(1 for c in contract["cases"]
                      if c["expect"]["counted_for_ceo"])
        assert counted == contract["expect_totals"]["desk_load_total"], (
            "the per-case flags and the stated total disagree — the "
            "TypeScript side asserts the total and the per-case stage "
            "separately, so a contract that disagreed with itself would let "
            "one of those two assertions pass over a defect")

    def test_the_stage_mapping_agrees_with_the_partition(self, contract):
        """`awaiting_decision` is exactly the counted set. This is the sentence
        the whole repair reduces to: the page's counted queue and the spine's
        CEO figure are the same rows, not merely the same size."""
        for c in contract["cases"]:
            e = c["expect"]
            assert (e["stage"] == "awaiting_decision") == e["counted_for_ceo"], (
                f"{c['name']!r}: stage {e['stage']!r} and "
                f"counted_for_ceo={e['counted_for_ceo']} disagree")

    def test_desk_load_over_the_contract_rows_reproduces_the_totals(self,
                                                                    contract):
        """The number itself, recomputed from the rows as stored. The other
        repo asserts `officerDesk(...).awaitingTotal` equals this same
        `desk_load_total` over these same rows — that equality, across two
        languages, is the entire contract."""
        rows = [c["row"] for c in contract["cases"]]
        load = desk_mod.desk_load(rows, [], [])
        want = contract["expect_totals"]
        assert load["total"] == want["desk_load_total"]
        assert load["by_actor"] == want["by_actor"]
        assert load["open_elsewhere"] == want["open_elsewhere"]
        assert (load["decided_awaiting_execution"]
                == want["decided_awaiting_execution"])
        assert load["explicit_next_actor"] == want["explicit_next_actor"]

    def test_the_page_total_is_the_spine_total_minus_written_exceptions(
            self, contract):
        """The arithmetic that keeps this contract honest instead of aspirational.

        The invariant is `desk_load.total == officerDesk(...).awaitingTotal`.
        It does not hold today, in exactly one place, and a contract that
        stated only the invariant would have to be RED to be truthful. So it
        states the invariant AND subtracts the named exceptions — each of which
        carries a reason, an owner, a direction and a live count.

        Fix either side and this stops adding up, which forces a human to edit
        the list and write down what they did. That is the whole mechanism.
        """
        t = contract["expect_totals"]
        assert t["known_divergence_count"] == len(contract["known_divergences"])
        assert t["page_awaiting_total"] == (
            t["desk_load_total"] - t["known_divergence_count"])

    def test_no_divergence_may_be_recorded_without_its_reasons(self, contract):
        """A known divergence with no owner is a defect with a note on it.

        Each entry must say what each side does, WHO IS RIGHT, which direction
        the fix moves the CEO's counter, how many live rows it touches today,
        and whose call it is. Recording a divergence without those turns this
        list into a place to park anything inconvenient — the opposite of what
        it is for.
        """
        required = {"id", "case", "spine_says", "page_does", "who_is_right",
                    "direction_of_the_fix", "live_rows_affected",
                    "live_measured_at", "owner"}
        for d in contract["known_divergences"]:
            missing = required - set(d)
            assert not missing, f"divergence {d.get('id')!r} is missing {missing}"
            assert isinstance(d["live_rows_affected"], int), (
                "how many rows this touches TODAY is a measurement, not a "
                "word — and absence is never zero, so it must be counted")
            assert d["case"] in {c["name"] for c in contract["cases"]}, (
                "a divergence must point at a case both suites actually run")

    def test_when_the_lists_are_empty_the_two_totals_must_be_equal(self,
                                                                   contract):
        """The end state this contract is aiming at, asserted so it cannot be
        reached by accident and left unrecorded: with nothing on the exception
        list, the page's number IS the spine's number."""
        if not contract["known_divergences"]:
            t = contract["expect_totals"]
            assert t["page_awaiting_total"] == t["desk_load_total"]

    def test_the_partition_is_total(self, contract):
        """Every row lands in exactly one of the three legs. A row in none of
        them is a row that left the surface — solving a counting problem by
        dropping work is the same defect wearing the opposite sign."""
        t = contract["expect_totals"]
        assert (t["desk_load_total"] + t["open_elsewhere"]
                + t["decided_awaiting_execution"]) == len(contract["cases"])

    def test_the_kill_case_is_present_and_counts(self, contract):
        """THE KILL, pinned as data.

        The constitution's preserved COO objection, verbatim: *"items at status
        `accepted` whose execution requires the CEO personally (three live
        today, including PM R1, the largest-money decision in the firm)"*. If
        this case ever leaves the contract, the boundary test stops covering
        the one row the boundary was crossed for.
        """
        hits = [c for c in contract["cases"]
                if c["row"].get("status") in ("accepted", "staged")
                and c["row"].get("next_actor") == "ceo"]
        assert len(hits) == 2, "both decided statuses must carry the case"
        for c in hits:
            assert c["expect"]["next_actor_resolved"] == "ceo"
            assert c["expect"]["counted_for_ceo"] is True
            assert c["expect"]["stage"] == "awaiting_decision"

    def test_terminal_rows_are_on_neither_side(self, contract):
        """Nothing follows a terminal row. It is excluded from the desk list
        here and dropped again by the client — the second lock, so a widened
        feed cannot put a closed item back in front of the CEO."""
        assert contract["terminal_cases"], "the terminal cases must exist"
        for c in contract["terminal_cases"]:
            assert c["expect"]["next_actor_resolved"] == "nobody"
            assert c["expect"]["counted_for_ceo"] is False
            assert c["expect"]["on_the_desk_at_all"] is False
        covered = {c["row"]["status"] for c in contract["terminal_cases"]}
        assert covered == set(desk_mod.TERMINAL_STATUSES), (
            "every terminal status must be covered, or a new one could be "
            "added on one side of the boundary and not the other")

    def test_the_contract_covers_every_actor_the_spine_can_produce(self,
                                                                   contract):
        """A case table that misses an actor is a boundary test with a hole in
        it, and the hole would be exactly where nobody thought to look."""
        seen = {c["expect"]["next_actor_resolved"] for c in contract["cases"]}
        seen |= {c["expect"]["next_actor_resolved"]
                 for c in contract["terminal_cases"]}
        assert seen == set(desk_mod.NEXT_ACTORS), (
            f"actors never exercised by the contract: "
            f"{sorted(set(desk_mod.NEXT_ACTORS) - seen)}")

    def test_the_contract_covers_every_basis_the_spine_can_produce(self,
                                                                   contract):
        """The five precedence rungs of `next_actor`, each exercised at least
        once. A rung with no case is a rung the other repo has never been
        tested against."""
        seen = {c["expect"]["next_actor_basis"] for c in contract["cases"]}
        assert seen >= {"default", "kind", "explicit", "lifecycle",
                        "explicit_unrecognised", "status_unrecognised"}, (
            f"precedence rungs never exercised: {seen}")
