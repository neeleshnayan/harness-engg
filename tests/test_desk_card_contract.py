"""The desk-CARD contract: what a desk row RENDERS as, pinned the same way the
desk-STAGE contract pins whose move it is.

WHY THIS FILE EXISTS. `desk_stage_contract.v1.json` binds a COUNT — whose move
is it, and does that put a row on the CEO's number. `desk_card_contract.v1.json`
binds a different question the same way: what does a row LOOK LIKE. Nine
renderable states the CEO's screen either got wrong or could not express on
2026-08-24 — a raw Python dict repr instead of a sentence, a decided row
wearing an undecided row's buttons, a chair adjudication labelled as his own, a
bundle with no visible members, a supersession stated only in prose. The
generator that produces both contracts in one command is
`scripts/gen_desk_contract.py`; the module both contracts describe is
`app/fund/deskcard.py`.

WHAT THIS FILE ASSERTS, mirroring `test_desk_stage_contract.py`'s two halves:

  * the checked-in contract still describes what `deskcard.py` /
    `desk_items()` produce RIGHT NOW (the producing side of the lock);
  * the digest is recomputed, not believed;
  * every pinned case reads by NAME, never by index, so inserting a case
    cannot silently break a pin;
  * the vocabularies the contract declares (`lifecycle`, `wanted_states`) are
    read from `deskcard.py`, never retyped.

This file does not run TypeScript and does not duplicate the stage contract's
generator-runnability check (`test_desk_stage_contract.py` already runs
`gen_desk_contract.py --check` and asserts both contracts print OK there) —
that would be the same subprocess run twice for no new coverage.
"""

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from app.fund import desk as desk_mod
from app.fund import deskcard
from app.fund import deskengine

REPO = Path(__file__).resolve().parents[1]
CONTRACT_PATH = REPO / "contract" / "desk_card_contract.v1.json"


@pytest.fixture(scope="module")
def contract() -> dict:
    assert CONTRACT_PATH.exists(), (
        f"the desk-card contract is missing. Regenerate it with "
        f"`python scripts/gen_desk_contract.py` — the CEO's desk card and "
        f"this test have no other shared definition of what a row renders as.")
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any]:
    """A case looked up by NAME, never by index — an index pin breaks
    silently when a case is inserted ahead of it; a name pin does not."""
    for c in items:
        if c["name"] == name:
            return c
    raise AssertionError(
        f"no case named {name!r} in the contract — the case list changed "
        f"shape and this pin was not updated with it")


class TestTheContractStillDescribesTheCode:
    def test_the_checked_in_contract_matches_deskcard_right_now(self):
        """THE PRODUCING SIDE OF THE LOCK.

        Regenerating `build_cards()` from `desk_items()`/`deskcard.py` must
        reproduce the checked-in bytes. If it does not, a card's rendering
        changed and the contract did not — every pin below would then be
        checking a fossil, and a reviewer reading green tests would have no
        way to know the artifact under test had already drifted.
        """
        sys.path.insert(0, str(REPO / "scripts"))
        import gen_desk_contract  # noqa: PLC0415

        fresh = gen_desk_contract.build_cards()
        onfile = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
        if fresh != onfile:
            diffs = []
            for a, b in zip(fresh.get("cases", []), onfile.get("cases", [])):
                if a != b:
                    diffs.append(f"  case {a.get('name')!r}: "
                                 f"deskcard.py now says {a.get('expect')}, "
                                 f"the contract says {b.get('expect')}")
            for a, b in zip(fresh.get("request_cases", []),
                            onfile.get("request_cases", [])):
                if a != b:
                    diffs.append(f"  request case {a.get('name')!r}: "
                                 f"deskcard.py now says {a.get('expect')}, "
                                 f"the contract says {b.get('expect')}")
            if fresh.get("expect_totals") != onfile.get("expect_totals"):
                diffs.append(f"  totals: deskcard.py {fresh.get('expect_totals')} "
                             f"vs contract {onfile.get('expect_totals')}")
            pytest.fail(
                "`desk_items()`/`deskcard.py`'s rendering no longer matches "
                "the checked-in desk-card contract:\n"
                + "\n".join(diffs or ["  (shape differs)"])
                + "\n\nRun `python scripts/gen_desk_contract.py` to regenerate "
                "both contracts, then commit the result.")

    def test_the_digest_is_recomputed_not_believed(self, contract):
        """A self-declared digest nobody checks is a label, and this fund has
        a rule about labels. Recompute over the generator's own canonical
        form rather than trust the field the file carries."""
        sys.path.insert(0, str(REPO / "scripts"))
        import gen_desk_contract  # noqa: PLC0415

        body = dict(contract)
        stated = body.pop("digest")
        actual = hashlib.sha256(gen_desk_contract._canonical(body)).hexdigest()
        assert actual == stated


class TestEveryCaseIsNamedAndExplained:
    """A case with no name cannot be pinned by name; a case with no `why`
    cannot tell a future reader what regressing it would cost."""

    def test_every_case_has_a_non_empty_name_and_why(self, contract):
        for c in contract["cases"]:
            assert c.get("name"), f"a case in `cases` has no name: {c}"
            assert c.get("why"), f"case {c['name']!r} has no `why`"

    def test_every_request_case_has_a_non_empty_name_and_why(self, contract):
        for c in contract["request_cases"]:
            assert c.get("name"), f"a case in `request_cases` has no name: {c}"
            assert c.get("why"), f"case {c['name']!r} has no `why`"


class TestCaseByCasePins:
    """Named pins on the nine rendering states. Each one reads its case by
    NAME so a case inserted ahead of it cannot silently detach the pin from
    the row it was written for."""

    def test_the_stuck_lamp_is_execution_yours_and_still_the_ceos(self, contract):
        """The whole reason `execution_yours` exists: his own accepted row
        must render with the flag true while staying on his figure
        (`next_actor_resolved == "ceo"`). Lose either half and the desk goes
        back to rendering a successful click identically to a dead one."""
        c = _by_name(contract["cases"], "ACCEPTED, EXECUTION YOURS — the stuck lamp")
        assert c["expect"]["execution_yours"] is True
        assert c["expect"]["next_actor_resolved"] == "ceo"

    def test_the_undecided_baseline_is_not_execution_yours(self, contract):
        """The baseline row — nobody has decided it — must not carry the
        `execution_yours` flag even though it shares `next_actor_resolved ==
        "ceo"` with the stuck lamp above. A fix that lit up every CEO-owed row
        would pass the stuck-lamp case and still be wrong."""
        c = _by_name(contract["cases"], "open recommendation — nobody has decided it")
        assert c["expect"]["execution_yours"] is False
        assert c["expect"]["next_actor_resolved"] == "ceo"

    def test_the_ordinary_decided_row_is_not_execution_yours(self, contract):
        """The CEO said yes, the chair owes the execution: `execution_yours`
        must stay false here or every accepted row would light up regardless
        of who owes the next act."""
        c = _by_name(contract["cases"], "accepted, and the chair owes the execution")
        assert c["expect"]["execution_yours"] is False

    def test_a_dict_payload_renders_its_title_never_its_repr(self, contract):
        """P-1: a recommendation stored with a `title` key and no `text` key
        must not put a raw Python dict repr on the CEO's screen. The repaired
        `title_display` must differ from the stored `title`, must not itself
        start with the brace that made the original bug visible, and the rest
        of the payload must survive somewhere (`detail`) rather than being
        dropped."""
        c = _by_name(contract["cases"], "DICT PAYLOAD — renders its title, never its repr")
        e = c["expect"]
        assert e["title_display"] != e["title"]
        assert not e["title_display"].startswith("{")
        assert isinstance(e["detail"], str) and e["detail"]

    def test_a_supersession_named_in_prose_renders_a_followable_edge(self, contract):
        """One decision note names a real superseder
        (`run-pm-r39`); the parser must resolve it to that ref rather than
        leaving the edge table empty, which is the state that made the
        supersession invisible on the CEO's desk in the first place."""
        c = _by_name(contract["cases"], "SUPERSEDED IN PROSE, with its superseder named")
        e = c["expect"]
        assert e["superseded_by"] is not None
        assert e["superseded_by"]["ref"] == "run-pm-r39"

    def test_superseded_sounding_prose_that_names_nothing_renders_no_edge(
            self, contract):
        """THE NULL CASE, and the reason the parser requires a named target.
        Six of the ten word-level 'supersed' hits in the live corpus are one
        boilerplate sentence stapled to unrelated resolutions, about two
        stray events and not about the row it is attached to. A word-match
        parser would draw six wrong supersession links on the CEO's control
        surface for every one right one — a wrong link looks exactly like a
        right one, so this case must render `superseded_by: None`, not a
        guess."""
        c = _by_name(contract["cases"],
                     "SUPERSEDED-SOUNDING PROSE THAT NAMES NOTHING — the null case")
        assert c["expect"]["superseded_by"] is None

    def test_a_row_closed_by_the_chair_renders_its_own_channel(self, contract):
        """CEO, verbatim: 'I cant form a view of whats closed and adjudicated
        by you.' A row decided by the chair alone must carry
        `adjudication.channel == "chair"`, distinct from a row he decided
        himself — 52 live rows were mislabelled as his own before this
        channel existed."""
        c = _by_name(contract["cases"], "CLOSED BY THE CHAIR — its own visible category")
        assert c["expect"]["adjudication"]["channel"] == "chair"

    def test_a_row_approved_by_the_ceo_and_staged_by_the_chair_uses_the_via_channel(
            self, contract):
        """The delegation-v2 audit trail: his decision, the chair's hand. Must
        render as `via_chair`, not collapsed into either `ceo` or `chair` —
        collapsing either way would misattribute either the decision or the
        execution."""
        c = _by_name(contract["cases"],
                     "approved by the CEO, staged by the chair — the via channel")
        assert c["expect"]["adjudication"]["channel"] == "via_chair"

    def test_a_bundle_with_members_reports_the_cascade_arithmetic(self, contract):
        """The constitution's cascade rule had no machinery until this field:
        a decided bundle with four members must report the exact partition —
        1 done, 2 pending, 1 not_open — and the three legs must sum to the
        total. A cascade block that dropped a member while reporting a
        smaller-looking total would hide exactly the outstanding work the
        CEO needs surfaced."""
        c = _by_name(contract["cases"], "BUNDLE WITH MEMBERS — cascade pending")
        cascade = c["expect"]["cascade"]
        assert cascade["total"] == 4
        assert cascade["done"] == 1
        assert cascade["pending"] == 2
        assert cascade["not_open"] == 1
        assert cascade["done"] + cascade["pending"] + cascade["not_open"] == cascade["total"]


class TestRequestCasePins:
    """Named pins on the structured-request card. Prose-only stays valid
    forever; the structured schema is additive, never a migration."""

    def test_a_prose_only_request_is_not_structured(self, contract):
        """109 live requests were filed before the structured schema existed.
        `structured` must read false for a plain-subject request, or every
        old request would suddenly claim a headline nobody wrote."""
        c = _by_name(contract["request_cases"],
                     "PROSE-ONLY REQUEST — the permanent fallback")
        assert c["expect"]["structured"] is False

    def test_a_structured_request_carries_the_four_questions(self, contract):
        """The CEO-ratified card spec: headline/summary/wanted/next_move all
        present and readable. The `wanted` checklist must preserve per-item
        state in filed order (done, in_progress, then the unstated third
        defaulting to open) and `next_move` must carry both `actor` and
        `act` — a chip naming only an owner is the defect this schema
        replaced."""
        c = _by_name(contract["request_cases"], "STRUCTURED REQUEST — the four questions")
        e = c["expect"]
        assert e["structured"] is True
        assert len(e["wanted"]) == 3
        assert [w["state"] for w in e["wanted"]] == ["done", "in_progress", "open"]
        assert isinstance(e["next_move"], dict)
        assert "actor" in e["next_move"] and "act" in e["next_move"]

    def test_a_half_named_next_move_is_refused(self, contract):
        """Both fields or neither. 'Next move: the chair' with no `act` names
        an owner and leaves the reader to guess the obligation — the exact
        defect the old CEO-APPROVED chip had. A half-filled `next_move` must
        render as `None`, not as a partial promise."""
        c = _by_name(contract["request_cases"], "next_move with an actor and no act — REFUSED")
        assert c["expect"]["next_move"] is None

    def test_a_served_request_reaches_delivered(self, contract):
        """The far end of the lifecycle rail. A resolved request must report
        `lifecycle.current == "delivered"`, or the one member of the cascade
        case that should read `done` would have nothing to point at."""
        c = _by_name(contract["request_cases"], "SERVED REQUEST — the rail reaches delivered")
        assert c["expect"]["lifecycle"]["current"] == "delivered"

    def test_the_request_routing_is_the_one_the_spine_SHIPS(self, contract):
        """THE ROUTING THAT SHIPPED, pinned as data so a later move is a
        deliberate act.

        `open` -> the CEO and `approved` -> the chair are the BASE COMMIT's
        values, lifted out of `desk_items` into `desk.open_request_actor`
        without changing them. Donna's P-2 and the riskofficer's H-2 asked for
        `open` -> chair, and the measurements support it (28 of the 49 requests
        resolved in the live log window carry no approval event at all; the old
        justification was circular, since `DESK_APPROVAL_ALLOWLIST` admits
        nobody but the CEO).

        It was built and then NOT applied: the rendered page showed it would
        also take the CEO's ask-approval control off his screen, because his
        page hangs Approve/Decline on the ask being his. A loosening that
        removes a control is an adversary-blind-then-CEO decision. When it is
        taken, THIS TEST is what has to be edited by hand — which is the point
        of pinning it.
        """
        # THE MOVE WAS TAKEN: routing v2, 2026-08-27, the CEO's decision item
        # by item ("4. Yes") and then in full ("all decisions route to you;
        # you move whats relevant to COO's desk for approval and batching and
        # that dispatches to my desk"). This edit is the deliberate act the
        # docstring above demanded. The ask-approval control note stands: his
        # page hung Approve/Decline on the ask being his, so until the
        # COO-batch stage ships, asks reach him through the board's request
        # card or the chair seeking his word directly — recorded, not hidden.
        by = {c["name"]: c["expect"]["next_actor_resolved"]
              for c in contract["request_cases"]}
        assert by["PROSE-ONLY REQUEST — the permanent fallback"] == "chair"
        assert by["STRUCTURED REQUEST — the four questions"] == "chair",             "status `approved` — the CEO decided; the chair must dispatch it"
        assert by["SERVED REQUEST — the rail reaches delivered"] == "nobody"
        assert contract["expect_totals"]["requests_on_the_ceos_figure"] ==             sum(1 for v in by.values() if v == "ceo")

    def test_every_request_cases_age_hours_is_the_wallclock_sentinel(self, contract):
        """A contract that pinned a real `age_hours` would be stale one
        second after it was written, and every suite that read it after that
        would fail for a reason unrelated to either repo. The generator
        replaces the computed age with the literal sentinel string
        `"<wall-clock>"` before writing the file — asserted here so a future
        edit to the generator cannot quietly start embedding the real
        number again."""
        for c in contract["request_cases"]:
            assert c["expect"]["lifecycle"]["age_hours"] == "<wall-clock>", (
                f"{c['name']!r} pinned a real age_hours instead of the "
                f"wall-clock sentinel")


class TestIdRules:
    """The shorthand-resolution rule, shared across both repos' request-id
    handling: normalise where recording is advisory, refuse where it would
    act."""

    def test_min_prefix_is_read_from_the_module_not_retyped(self, contract):
        """A test asserting `min_prefix == 8` can never tell a real read of
        `deskengine.MIN_ID_PREFIX` from a lucky duplicate typed by hand. This
        reads the constant."""
        assert contract["id_rules"]["min_prefix"] == deskengine.MIN_ID_PREFIX

    def test_an_ambiguous_prefix_is_recorded_ambiguous_never_guessed(self, contract):
        """`abcd1234` matches two live ids by prefix. Picking either would
        close somebody else's ticket, so it must land in `ambiguous` — exactly
        one entry — and `normalised` must stay empty for it: a guess recorded
        as a normalisation would be indistinguishable from a real resolution
        to anyone reading the field."""
        cases = contract["id_rules"]["cases"]
        c = next(x for x in cases if x["declared"] == "abcd1234")
        assert len(c["ambiguous"]) == 1
        assert c["normalised"] == []

    def test_a_seven_character_declaration_is_unresolved_never_a_shorthand(
            self, contract):
        """`3eeb42d` is one character short of `MIN_ID_PREFIX`. It is a typo,
        not a shorthand, and must land in `unresolved` with `normalised`
        empty — matching it by prefix anyway would let a truncated id
        silently address whichever real request happened to share that
        prefix."""
        cases = contract["id_rules"]["cases"]
        c = next(x for x in cases if x["declared"] == "3eeb42d")
        assert c["unresolved"], "a 7-character declaration must be unresolved"
        assert c["normalised"] == []

    def test_a_valid_eight_character_prefix_normalises_to_exactly_one_id(
            self, contract):
        """`3eeb42d4` is the live shorthand: six of thirteen declarations use
        it and it names exactly one request. `normalised` must carry exactly
        one entry, or the resolution either failed to fire or resolved to
        more than the one id it should."""
        cases = contract["id_rules"]["cases"]
        c = next(x for x in cases if x["declared"] == "3eeb42d4")
        assert len(c["normalised"]) == 1


class TestDeclaredVocabulariesMatchTheModule:
    """The contract's declared vocabularies must be READ from `deskcard.py`,
    never retyped — a retyped list can drift from the module silently, and a
    contract pinning its own drift would defeat the entire mechanism."""

    def test_the_lifecycle_vocabulary_matches_deskcard(self, contract):
        assert contract["lifecycle"] == list(deskcard.LIFECYCLE)

    def test_the_wanted_states_vocabulary_matches_deskcard(self, contract):
        assert contract["wanted_states"] == list(deskcard.WANTED_STATES)
