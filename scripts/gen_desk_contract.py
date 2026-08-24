"""Generate the desk-stage CONTRACT that the spine and the CEO's page share.

WHY THIS FILE EXISTS, and it is not a convenience.

`desk_load()` (this repo) and `stageOfItem()`/`officerDesk()` (KryptonPay) are
two implementations of one question: *whose move is it, and does that put the
row on the CEO's number?* On 2026-08-22 they answered 11 and 6 for the same
payload, eight pixels apart on the same line. The repair was to make the SPINE
the single definition and have the page read its answer.

The repair was then shipped with a defect of exactly the same shape, and **both
repos' suites went green over it** — 12/12 TypeScript and 70/70 pytest — because
each suite pinned its own side and nothing in either crossed the boundary. A row
at status `accepted` carrying `next_actor: "ceo"` (the constitution's preserved
COO objection, three live rows on 2026-08-21 including PM R1) counted as CEO
load in Python and rendered as "shown, never counted" in TypeScript.

**Two green suites pinning opposite behaviours in two repos is how that
shipped.** This file is the boundary-crossing artifact that makes it impossible
to do again quietly:

  1. it enumerates the cases as DATA, with the answer computed by `desk.py`
     itself — never typed in by hand, so it cannot encode a wish;
  2. it is checked in to BOTH repos at ``contract/desk_stage_contract.v1.json``,
     byte-identical;
  3. `tests/test_desk_stage_contract.py` here asserts the checked-in file still
     matches what `desk.py` produces RIGHT NOW — so a change to the routing
     fails this repo's suite until the contract is regenerated;
  4. `deskStageContract.test.ts` there runs the page's own functions over the
     same rows and asserts the same numbers, with the digest pinned in its
     source — so the copy cannot be edited without a human touching the test;
  5. `desk_load` publishes `contract_digest`, and the CEO page renders a visible
     warning when the live spine's digest differs from the one its fixture was
     generated against. That is the one drift a hermetic test cannot see
     (this repo regenerated, the other not updated), so it is detected where it
     can be — against a live spine, on screen, rather than silently.

Run: ``python scripts/gen_desk_contract.py`` (writes the file, prints the
digest). Then copy the file to KryptonPay and update the pinned digest there;
both suites will tell you if you forget.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from app.fund import desk as desk_mod  # noqa: E402
from app.fund import deskcard  # noqa: E402
from app.fund import deskengine  # noqa: E402

CONTRACT_PATH = REPO / "contract" / "desk_stage_contract.v1.json"
CARD_CONTRACT_PATH = REPO / "contract" / "desk_card_contract.v1.json"

#: How a spine verdict maps onto the page's three stages.
#:
#: MOVED INTO ``app/fund/deskcard.py`` ON 2026-08-24 AND ALIASED HERE. The
#: mapping still lives on the spine side — the page must not own a routing rule
#: of its own, and a mapping table in TypeScript would be the second definition
#: this whole contract exists to prevent. But it lived in a GENERATOR SCRIPT,
#: which the running spine never imports: the one definition both repos are
#: pinned to could not be called by the code being pinned. It is now a function
#: in the package, the spine annotates every row with its answer
#: (``desk_stage``), and this script consumes it like everyone else. Behaviour
#: is byte-identical: every ``expect.stage`` in the regenerated v1 file is
#: unchanged, which is the assertion that matters. The DIGEST does move in the
#: same commit, and not because of this — ``_annotated`` now attaches the card
#: fields, so the embedded rows carry more keys. Two changes in one digest is
#: worth saying out loud rather than letting a reviewer infer that a mapping
#: move rewrote the contract.
stage_for = deskcard.desk_stage


#: The cases. Each one is a row shape the live corpus produces or the
#: constitution names, with a sentence saying what would break if it regressed.
#: Nothing here states an EXPECTED answer — `desk.py` computes every one.
CASES: list[dict[str, Any]] = [
    {
        "name": "open row, kind nobody has seen",
        "why": "the default: a recommendation is a thing a seat asks the firm "
               "to decide, and the decision channel is the CEO's. 84 distinct "
               "kinds over 219 rows, 49 seen exactly once — the default IS the "
               "common case.",
        "row": {"status": "open", "kind": "some-kind-nobody-registered"},
    },
    {
        "name": "open row, engineering kind",
        "why": "routes to the chair by KIND_ACTORS. Moves 18.7% of rows off "
               "the CEO's counter; if this regresses the counter goes back to "
               "measuring the bench's output volume.",
        "row": {"status": "open", "kind": "harness_gap"},
    },
    {
        "name": "open row, seat-to-seat handoff",
        "why": "a prefix that names its own recipient. Never the CEO's load.",
        "row": {"status": "open", "kind": "handoff_to_mechanism"},
    },
    {
        "name": "open row, nothing is owed",
        "why": "`no_action` records a fact. Counting it would be the CEO's "
               "original complaint in a new costume.",
        "row": {"status": "open", "kind": "no_action"},
    },
    {
        "name": "ACCEPTED row whose execution is the CEO'S OWN — the kill",
        "why": "THE CASE THE EXPLICIT FIELD EXISTS FOR, and the one the first "
               "TypeScript cut got wrong. Constitution, verbatim: 'items at "
               "status `accepted` whose execution requires the CEO personally "
               "(three live today, including PM R1, the largest-money decision "
               "in the firm)'. `next_actor` outranks the lifecycle in "
               "desk.py::next_actor's precedence; the page returned "
               "awaiting_execution before it read the field, so the spine "
               "counted 1 and the page counted 0.",
        "row": {"status": "accepted", "kind": "awaits-ceo", "next_actor": "ceo"},
    },
    {
        "name": "STAGED row whose execution is the CEO's own",
        "why": "the same defect on the other decided status. Pinned "
               "separately because a fix that special-cased `accepted` would "
               "pass the case above and still ship the bug.",
        "row": {"status": "staged", "kind": "exit_rule", "next_actor": "ceo"},
    },
    {
        "name": "accepted row with an UNREADABLE explicit actor",
        "why": "the second half of the same kill. An unrecognised claim "
               "resolves to `unknown`, and desk_load counts ceo+unknown — so a "
               "decided row must not swallow it either. Absence is never zero "
               "and an unreadable claim is never a licence to guess.",
        "row": {"status": "accepted", "kind": "process", "next_actor": "Whoever"},
    },
    {
        "name": "accepted row, no explicit actor",
        "why": "the ordinary decided row: the CEO said yes, the chair owes the "
               "execution. Shown, never counted. Re-counting it was the "
               "original complaint.",
        "row": {"status": "accepted", "kind": "process"},
    },
    {
        "name": "staged row, no explicit actor",
        "why": "as above, one step further along the propose path.",
        "row": {"status": "staged", "kind": "retire"},
    },
    {
        "name": "accepted row explicitly owned by a seat",
        "why": "decided AND somebody else's. Must read as a promise the firm "
               "owes back (awaiting_execution), not as an open ticket "
               "(owned_elsewhere) — reporting the second would drop a "
               "commitment the firm actually made.",
        "row": {"status": "accepted", "kind": "process", "next_actor": "seat"},
    },
    {
        "name": "open row explicitly handed to the chair",
        "why": "nobody decided it and it was never the CEO's. The third "
               "stage's whole reason for existing.",
        "row": {"status": "open", "kind": "process", "next_actor": "chair"},
    },
    {
        "name": "status outside the vocabulary",
        "why": "whether a decision is outstanding cannot be read, so it counts "
               "rather than disappears. This fund has answered an "
               "unmeasurable with zero four separate times.",
        "row": {"status": "in-progress-ish", "kind": "process"},
    },
    {
        "name": "row with no status at all",
        "why": "None is treated as open, not as decided. A missing label must "
               "never promote a row past the CEO.",
        "row": {"kind": "process"},
    },
    {
        "name": "SECRETARY note — the second divergence, found BY this contract",
        "why": "Donna's seat definition says a `note` asks to be READ, not "
               "decided, and the CEO said so himself ('this seems more like a "
               "note and I don't know what to accept'). The page therefore "
               "routes every secretary row that is not a `suggestion` into a "
               "read-only bucket and does NOT count it. This module has no "
               "such rule: the kind falls through to the CEO and the row is "
               "counted. Server 1, page 0 — the same shape as the kill, in a "
               "different place, and this contract's first new find. It is "
               "recorded as a KNOWN DIVERGENCE rather than fixed here, because "
               "the fix moves a row OFF the CEO's counter and therefore makes "
               "the registered COO triage trigger fire LATER. That is the "
               "loosening direction and it is a human's call, not a builder's.",
        "row": {"status": "open", "kind": "record_keeping", "seat": "secretary"},
    },
]

#: WHERE THE TWO SIDES DISAGREE TODAY, named so it cannot be forgotten and
#: cannot go quietly green in either direction.
#:
#: A contract that only stated the invariant would be a contract that had to be
#: RED to be honest. This states the invariant AND every measured exception, so
#: the suites can be green over a truth rather than green over a wish. Fix
#: either side and the arithmetic below stops adding up, which forces this list
#: to be edited by a human who then has to write down what they did.
KNOWN_DIVERGENCES: list[dict[str, Any]] = [
    {
        "id": "secretary_notes_uncounted_by_page",
        "case": "SECRETARY note — the second divergence, found BY this contract",
        "spine_says": "ceo — `record_keeping` is not in KIND_ACTORS, so an "
                      "undecided row falls through to the CEO and is counted",
        "page_does": "officerQueues routes any secretary row whose kind is not "
                     "`suggestion` into `notes`: shown, read-only, never "
                     "counted (its rule 2)",
        "who_is_right": "the PAGE, on the seat definition and the CEO's own "
                        "words. The spine over-counts.",
        "direction_of_the_fix": "LOOSENING — routing these rows away lowers the "
                                "CEO's figure, so the registered COO triage "
                                "trigger (>=50) fires LATER. A threshold-"
                                "affecting change is a human decision.",
        "live_rows_affected": 0,
        "live_measured_at": "2026-08-22, GET /fund/desk: 1 secretary row in the "
                            "payload, status `accepted` kind `suggestion`, "
                            "which both sides agree is uncounted. The "
                            "divergence is LATENT, not live — and Donna's "
                            "first run filed `record_keeping` and "
                            "`org_observation`, so the row shape exists.",
        "owner": "the CEO, via the chair — a routing rule that changes when the "
                 "COO is summoned is a versioned change with a written reason",
    },
]

#: Terminal rows never reach the page — `open_recommendations()` excludes them
#: and the client's `recItems` drops them a second time. Held apart from CASES
#: so the contract can assert BOTH sides drop them, rather than asserting a
#: stage for a row that has none.
TERMINAL_CASES: list[dict[str, Any]] = [
    {"name": f"terminal row ({s})",
     "why": "nothing follows a terminal row and no label may claim otherwise. "
            "The spine excludes it from the desk list; the client drops it "
            "again, so a widened feed cannot put a closed item back in front "
            "of the CEO as though a click were owed on it.",
     "row": {"status": s, "kind": "awaits-ceo", "next_actor": "ceo"}}
    for s in desk_mod.TERMINAL_STATUSES
]


def _canonical(obj: Any) -> bytes:
    """Byte-stable serialisation for the digest: sorted keys, no whitespace
    slack, explicit UTF-8. Two repos comparing a hash need the same bytes on
    both sides of a filesystem that disagrees about line endings."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def build() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    cases: list[dict[str, Any]] = []
    for i, c in enumerate(CASES):
        row = {"run_id": "contract", "rec_id": i + 1, "seat": "pm",
               "text": c["name"], "task": "contract", "artifact_path": None,
               "trace_id": None, **c["row"]}
        verdict = desk_mod.next_actor(row)
        annotated = desk_mod._annotated(row)
        cases.append({
            "name": c["name"],
            "why": c["why"],
            "row": annotated,
            "expect": {
                "next_actor_resolved": verdict["actor"],
                "next_actor_basis": verdict["basis"],
                # The one that decides the headline number. Mirrors desk_load's
                # own partition: ceo + unknown, nothing else.
                "counted_for_ceo": verdict["actor"] in ("ceo", "unknown"),
                "stage": stage_for(verdict["actor"], row.get("status")),
            },
        })
        rows.append(annotated)

    terminal: list[dict[str, Any]] = []
    for i, c in enumerate(TERMINAL_CASES):
        row = {"run_id": "contract", "rec_id": 900 + i, "seat": "pm",
               "text": c["name"], "task": "contract", "artifact_path": None,
               "trace_id": None, **c["row"]}
        verdict = desk_mod.next_actor(row)
        terminal.append({
            "name": c["name"], "why": c["why"],
            "row": desk_mod._annotated(row),
            "expect": {"next_actor_resolved": verdict["actor"],
                       "counted_for_ceo": False,
                       "on_the_desk_at_all": False},
        })

    # desk_load over exactly the non-terminal rows, with the other two
    # components zeroed so the recommendation leg is the whole number and the
    # client's `awaitingTotal` is comparable to it directly.
    load = desk_mod.desk_load(list(rows), [], [])

    divergent_cases = {d["case"] for d in KNOWN_DIVERGENCES}
    # Every divergence must name a case that EXISTS, or the arithmetic below
    # would be subtracting a row nobody tests.
    unknown = divergent_cases - {c["name"] for c in cases}
    if unknown:
        raise SystemExit(f"KNOWN_DIVERGENCES names cases that do not exist: "
                         f"{sorted(unknown)}")
    # Each divergence removes exactly one COUNTED row from the page's figure.
    # Asserted rather than assumed: a divergence over an already-uncounted row
    # would silently make the arithmetic wrong in the safe-looking direction.
    for d in KNOWN_DIVERGENCES:
        c = next(x for x in cases if x["name"] == d["case"])
        if not c["expect"]["counted_for_ceo"]:
            raise SystemExit(
                f"divergence {d['id']!r} points at a case the spine does not "
                f"count; there is nothing for the page to disagree with")

    body: dict[str, Any] = {
        "contract": "desk_stage",
        "version": 1,
        "rules_version": desk_mod.NEXT_ACTOR_RULES_VERSION,
        # What this contract does and does not bind, stated rather than
        # implied. It covers the RECOMMENDATION leg of `desk_load` — the leg
        # the kill was on. The other two legs (pending orders, requests
        # awaiting approval) are one-to-one by construction and are asserted
        # separately in KryptonPay's `deskStageContract.test.ts`; they are not
        # in these rows and no number here includes them.
        "covers": "the open_recommendations leg of desk_load only",
        "cases": cases,
        "terminal_cases": terminal,
        "known_divergences": KNOWN_DIVERGENCES,
        "expect_totals": {
            # THE INVARIANT, and it is the only reason this file exists:
            # `desk_load(rows, [], []).total` (Python) must equal
            # `officerDesk(split(rank(recItems(rows)))).awaitingTotal`
            # (TypeScript) over the same rows — MINUS the divergences named
            # above, each of which is a written, owned, measured exception
            # rather than a rounding error.
            "desk_load_total": load["total"],
            "page_awaiting_total": load["total"] - len(KNOWN_DIVERGENCES),
            "known_divergence_count": len(KNOWN_DIVERGENCES),
            "by_actor": load["by_actor"],
            "open_elsewhere": load["open_elsewhere"],
            "decided_awaiting_execution": load["decided_awaiting_execution"],
            "explicit_next_actor": load["explicit_next_actor"],
        },
    }
    body["digest"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body


def render(body: dict[str, Any]) -> str:
    """The on-disk rendering. 2-space indent so a reviewer can read the diff;
    the digest is over the CANONICAL form, so a reformat here cannot silently
    change what the two repos agree on."""
    return json.dumps(body, indent=2, ensure_ascii=False) + "\n"


# ============================================================================
# THE CARD CONTRACT (v1, 2026-08-24) — the SECOND boundary-crossing artifact
#
# The stage contract above binds ONE question: whose move is it, and does that
# put the row on the CEO's number. It is a contract about a COUNT.
#
# This one binds a different question the same way: what does a row LOOK LIKE.
# Nine renderable states, each of which the CEO's screen either got wrong or
# could not express on 2026-08-24 — a repr instead of a sentence, a decided row
# wearing an undecided row's buttons, a chair adjudication labelled as his own,
# a bundle with no visible members, a supersession stated only in prose.
#
# TWO FILES RATHER THAN ONE, and that is the deliberate choice. Folding these
# cases into the stage contract would move its digest on every card change,
# which is precisely the file that must NOT churn: it is the one pinning a
# threshold's population. Two contracts, two digests, one generator, one set of
# rules. The generator is shared so neither can be regenerated without the
# other being re-checked in the same command.
# ============================================================================

#: Each case is a row shape the LIVE corpus produced on 2026-08-24, with the
#: measured count that made it worth a case. Nothing here states an expected
#: answer: `desk_items` computes every field, so the file cannot encode a wish.
CARD_CASES: list[dict[str, Any]] = [
    {
        "name": "open recommendation — nobody has decided it",
        "why": "the baseline. 20 of the 34 rows on his live decision list. "
               "Every other case is defined by how it must NOT look like this "
               "one.",
        "rec": {"status": "open", "kind": "awaits-ceo", "text": "Decide this."},
    },
    {
        "name": "ACCEPTED, EXECUTION YOURS — the stuck lamp",
        "why": "14 of the 34 rows on his live decision list (2026-08-24). He "
               "accepted R39 at seq 1281, the write landed, the page refetched "
               "— and the row came back with an Accept button on it, because "
               "nothing on screen distinguished 'you decided this, now execute "
               "it' from 'nobody has decided this'. A successful click and a "
               "dead click were the same picture. `execution_yours` must be "
               "true here and false on the row above, and NEITHER may change "
               "any count: both are inside awaiting_decision.",
        "rec": {"status": "accepted", "kind": "awaits-ceo", "next_actor": "ceo",
                "text": "Approve R39 as one sequence.",
                "decided_by": "ceo", "decided_at": "2026-08-24T09:12:00+00:00"},
    },
    {
        "name": "accepted, and the chair owes the execution",
        "why": "the ordinary decided row. Shown, never counted, and NOT "
               "`execution_yours` — a fix that made every accepted row light "
               "up would pass the case above and still be wrong.",
        "rec": {"status": "accepted", "kind": "process",
                "text": "Stage the exit rules.",
                "decided_by": "ceo", "decided_at": "2026-08-24T09:12:00+00:00"},
    },
    {
        "name": "CLOSED BY THE CHAIR — its own visible category",
        "why": "CEO, verbatim 2026-08-24: 'your desk on the UI only marks "
               "items as CEO approved... I cant form a view of whats closed "
               "and adjudicated by you.' Of 227 live rows, 185 are decided — "
               "122 by the CEO, 52 by the chair alone (co-cto 39, cto 13), 11 "
               "via-chair — and the desk labelled all 185 the same way, which "
               "is to say it labelled none of them. The citation is the "
               "decision note, verbatim and untruncated.",
        "rec": {"status": "accepted", "kind": "process",
                "text": "Merge the D37 bundle.",
                "decided_by": "co-cto", "decided_at": "2026-08-24T07:00:00+00:00",
                "note": "Merged under delegation v2; suites green on the "
                        "merged tree."},
    },
    {
        "name": "approved by the CEO, staged by the chair — the via channel",
        "why": "11 live rows. Distinct from both: his decision, the chair's "
               "hand, and the bracketed instruction is the audit trail "
               "delegation v2 promised. Lifted verbatim, never summarised.",
        "rec": {"status": "accepted", "kind": "governance",
                "text": "Adopt the request card schema.",
                "decided_by": "neelesh-via-cto [Agree]",
                "decided_at": "2026-08-24T08:00:00+00:00"},
    },
    {
        "name": "DICT PAYLOAD — renders its title, never its repr",
        "why": "P-1, measured: 2 of 227 live rows (run-cfo-8 recs 1 and 2) "
               "rendered as a raw Python dict repr on the CEO's desk, both "
               "`accepted`. The stored `text` is left exactly as stored; "
               "`title_display` carries the repaired line and `detail` carries "
               "what would otherwise have been lost behind it.",
        "rec": {"status": "open", "kind": "harness_gap",
                "text": "{'id': 'O4', 'title': 'Validate serves_requests ids "
                        "at the filing door', 'detail': 'app/api/v1/fund.py:"
                        "2136-2140 stores declared request ids with no check.'}"},
    },
    {
        "name": "SUPERSEDED IN PROSE, with its superseder named",
        "why": "the supersession TABLE is empty live (blocked: 0). One "
               "decision note names a real superseder and must render a "
               "followable edge.",
        "rec": {"status": "accepted", "kind": "exit_rule",
                "text": "The 2026-09-08 exit package.",
                "decided_by": "cto", "decided_at": "2026-08-23T12:00:00+00:00",
                "note": "SUPERSEDED BY THE R39 PLAN (run-pm-r39): R37 is with "
                        "the adversary."},
    },
    {
        "name": "SUPERSEDED-SOUNDING PROSE THAT NAMES NOTHING — the null case",
        "why": "THE CASE THAT MUST RENDER NO EDGE, and the reason the parser "
               "requires a named target. Six of the ten word-level 'supersed' "
               "hits in the live corpus are ONE boilerplate sentence stapled "
               "to unrelated resolutions, about two stray events and not about "
               "the row at all. A word-match parser would have drawn six wrong "
               "links on the CEO's control surface and one right one. A wrong "
               "link looks exactly like a right one; a gap looks like a gap.",
        "rec": {"status": "accepted", "kind": "process",
                "text": "Recorded rather than hidden.",
                "decided_by": "cto", "decided_at": "2026-08-23T12:00:00+00:00",
                "note": "They are inert - they resolve nothing and were "
                        "superseded by this correctly-addressed event minutes "
                        "later."},
    },
    {
        "name": "BUNDLE WITH MEMBERS — cascade pending",
        "why": "the constitution's cascade rule (2026-08-21) has had no "
               "machinery since it was written: nothing in the schema could "
               "say which items a batch carried, so 'did the cascade happen' "
               "was unanswerable except by reading prose. FOUR members, and "
               "the arithmetic is 1 done / 2 pending / 1 not_open — each of "
               "the three outcomes exercised at least once, on purpose. "
               "`not_open` is the honest third: a finished recommendation "
               "leaves the open population entirely, so absence means "
               "'finished, or never filed, and this fold cannot tell which'. "
               "It is never counted as done. This block executes nothing.",
        "rec": {"status": "accepted", "kind": "batch",
                "text": "Accept COO triage #8 as one batch.",
                "decided_by": "ceo", "decided_at": "2026-08-24T09:00:00+00:00",
                "members": [{"run_id": "run-member", "rec_id": 1},
                            {"run_id": "run-member", "rec_id": 2},
                            {"request_id": "req-structured"},
                            {"request_id": "req-served"}]},
    },
    {
        "name": "bundle members, referenced",
        "why": "the two rows the bundle above points at: one still open, one "
               "closed. Present so the cascade arithmetic (1 done, 1 pending, "
               "1 unresolvable) is derived from real rows rather than from a "
               "hand-written lookup.",
        "rec": {"status": "open", "kind": "process", "text": "Member one.",
                "run_id": "run-member", "rec_id": 1},
    },
]

#: Desk-request cases. The structured schema is OPTIONAL forever; the fallback
#: is not a deprecation path, it is the permanent shape of the 109 rows already
#: filed.
CARD_REQUEST_CASES: list[dict[str, Any]] = [
    {
        "name": "PROSE-ONLY REQUEST — the permanent fallback",
        "why": "109 requests exist and none was filed under a schema that did "
               "not exist. `structured` is false, the headline is the "
               "subject's first LINE untouched, and the whole subject stays "
               "available as the incident. No migration: rewriting an old "
               "subject to look structured would invent a headline the filer "
               "never wrote.",
        "req": {"request_id": "req-prose", "kind": "build", "serves": "builder",
                "status": "open", "at": "2026-08-22T10:00:00+00:00",
                "subject": "DESK RENDERING + ROUTING (Donna P-1/P-2/P-3)\n"
                           "Five rows rendered as raw Python reprs this "
                           "weekend, including the two that were genuinely "
                           "his."},
    },
    {
        "name": "STRUCTURED REQUEST — the four questions",
        "why": "the CEO-ratified card spec (KryptonPay/docs/design/"
               "REQUEST_CARD_2026-08-24.md). Headline, summary, the wanted "
               "checklist with per-item state, and an explicit actor+act — the "
               "old 'CEO-APPROVED — TRIGGER IT' chip implied his move when it "
               "was the chair's.",
        "req": {"request_id": "req-structured", "kind": "build",
                "serves": "builder", "status": "approved",
                "at": "2026-08-22T10:00:00+00:00",
                "approved_at": "2026-08-22T10:22:00+00:00",
                "approved_by": "ceo",
                "headline": "Repair the CEO's desk read path",
                "summary": "His clicks land; the fold that renders them back "
                           "to him does not.",
                "incident": "Six defects pooled in a starved batch.",
                "wanted": [{"text": "Dict payloads render their text",
                            "state": "done"},
                           {"text": "Cascade block under decided bundles",
                            "state": "in_progress",
                            "note": "spine half landed"},
                           {"text": "Contract test crossing the boundary"}],
                "next_move": {"actor": "the chair",
                              "act": "batch this into a builder dispatch"}},
    },
    {
        "name": "SERVED REQUEST — the rail reaches delivered",
        "why": "the far end of the lifecycle, and the one member of the "
               "cascade above that resolves to `done`. Requests keep their "
               "terminal rows in `desk._requests`, so a request member's "
               "closure is READABLE where a finished recommendation's is not "
               "— which is why the cascade reports `done` and `not_open` as "
               "two different facts rather than one optimistic one.",
        "req": {"request_id": "req-served", "kind": "build", "serves": "builder",
                "status": "resolved", "at": "2026-08-20T10:00:00+00:00",
                "approved_at": "2026-08-20T10:30:00+00:00",
                "approved_by": "neelesh-via-co-cto [lets go]",
                "resolved_at": "2026-08-21T09:00:00+00:00",
                "subject": "Ship the third dispatch state.",
                "resolution": "SERVED by builder D30."},
    },
    {
        "name": "next_move with an actor and no act — REFUSED",
        "why": "both fields or neither. 'Next move: the chair' names an owner "
               "and leaves the reader to guess the obligation, which is "
               "exactly the defect the spec says the old chip had.",
        "req": {"request_id": "req-halfmove", "kind": "build",
                "serves": "builder", "status": "open",
                "at": "2026-08-22T10:00:00+00:00", "subject": "Half a move.",
                "next_move": {"actor": "the chair"}},
    },
]


#: The id pool the shorthand cases resolve against. Two entries share the head
#: ``abcd1234`` on purpose: the ambiguous case must be exercised by a pool that
#: is genuinely ambiguous, not asserted from a comment.
_ID_POOL = ["3eeb42d4-1111-4111-8111-111111111111",
            "a26debb9-827a-47e9-9cac-c5ca1ba2213f",
            "abcd1234-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "abcd1234-bbbb-4bbb-8bbb-bbbbbbbbbbbb"]


def build_cards() -> dict[str, Any]:
    """The card contract, computed by ``desk_items`` over the cases above."""
    recs = []
    for i, c in enumerate(CARD_CASES, 1):
        row = {"run_id": c["rec"].get("run_id", "card"),
               "rec_id": c["rec"].get("rec_id", i),
               "seat": "pm", "task": "contract", "artifact_path": None,
               "trace_id": None, "resolved_at": "2026-08-24T06:00:00+00:00",
               **c["rec"]}
        recs.append(row)
    reqs = [{**c["req"]} for c in CARD_REQUEST_CASES]

    items = desk_mod.desk_items(recs, reqs)
    by_ref = {}
    for it in items:
        key = (it.get("run_id"), it.get("rec_id")) if it["source"] == "recommendation" \
            else it.get("request_id")
        by_ref[key] = it

    #: The fields a renderer is allowed to depend on. Enumerated rather than
    #: dumping the whole item, so ADDING a field to `desk_items` does not churn
    #: this digest — only changing one of the fields the CEO's card actually
    #: reads does. A contract that broke on every unrelated addition would be
    #: regenerated without being read, which is a contract nobody checks.
    rec_fields = ("status", "next_actor_resolved", "execution_yours",
                  "title", "title_display", "detail", "adjudication",
                  "superseded_by", "cascade", "decided_by", "decided_at")
    req_fields = ("status", "next_actor_resolved", "title_display", "summary",
                  "detail", "wanted", "next_move", "structured", "lifecycle",
                  "adjudication")

    cases = []
    for i, c in enumerate(CARD_CASES, 1):
        it = by_ref[(c["rec"].get("run_id", "card"), c["rec"].get("rec_id", i))]
        cases.append({"name": c["name"], "why": c["why"],
                      "row": {k: recs[i - 1].get(k)
                              for k in ("status", "kind", "text", "note",
                                        "decided_by", "decided_at", "members",
                                        "next_actor")
                              if k in recs[i - 1]},
                      "expect": {k: it.get(k) for k in rec_fields}})

    req_cases = []
    for c in CARD_REQUEST_CASES:
        it = by_ref[c["req"]["request_id"]]
        # `lifecycle.age_hours` is wall-clock and is EXCLUDED from the pinned
        # expectation: a contract that embedded an age would be stale one
        # second after it was written, and would fail every suite thereafter
        # for a reason that has nothing to do with either repo. The rail's
        # SHAPE is pinned; the clock is asserted separately, live.
        exp = {k: it.get(k) for k in req_fields}
        if isinstance(exp.get("lifecycle"), dict):
            exp["lifecycle"] = {**exp["lifecycle"], "age_hours": "<wall-clock>"}
        req_cases.append({"name": c["name"], "why": c["why"],
                          "row": c["req"], "expect": exp})

    body: dict[str, Any] = {
        "contract": "desk_card",
        "version": 1,
        "rules_version": desk_mod.NEXT_ACTOR_RULES_VERSION,
        "request_routing_version": desk_mod.REQUEST_ROUTING_VERSION,
        "covers": ("what a desk row RENDERS as — the nine states the CEO's "
                   "window either got wrong or could not express on "
                   "2026-08-24. It binds no count; the stage contract binds "
                   "the count."),
        "lifecycle": list(deskcard.LIFECYCLE),
        "wanted_states": list(deskcard.WANTED_STATES),
        "adjudication_channels": [deskcard.CHANNEL_CEO,
                                  deskcard.CHANNEL_VIA_CHAIR,
                                  deskcard.CHANNEL_CHAIR, "unknown"],
        "cases": cases,
        "request_cases": req_cases,
        # THE ID RULE, SHARED (COO triage #8 J1). It crosses the boundary
        # because both sides handle request ids: the spine normalises an
        # 8-character shorthand at the runs door and REFUSES one at the
        # approve/resolve doors, and a client that posted a shorthand would now
        # get a 404 where it used to get a phantom 200. Pinning the rule here
        # means neither side can move it alone.
        "id_rules": {
            "min_prefix": deskengine.MIN_ID_PREFIX,
            "doors_refusing_unknown_ids": [
                "POST /fund/desk/requests/{id}/approve",
                "POST /fund/desk/requests/{id}/decline",
                "POST /fund/desk/requests/{id}/resolve"],
            "note": ("a shorthand is normalised where it is RECORDED "
                     "(meta.serves_requests, advisory) and refused where it "
                     "would ACT (the three doors). A 200 against an id no "
                     "fold has seen is the worst shape: the caller believes "
                     "it acted and the real row is untouched."),
            "cases": [
                {"declared": d, "why": why,
                 **deskengine.resolve_request_ids([d], _ID_POOL)}
                for d, why in (
                    ("3eeb42d4",
                     "the live shorthand: 6 of 13 declarations, 0 closes"),
                    ("a26debb9-827a-47e9-9cac-c5ca1ba2213f",
                     "a full id, untouched and unreported"),
                    ("abcd1234",
                     "AMBIGUOUS — never guessed; picking one closes somebody "
                     "else's ticket"),
                    ("THE DESK, REDESIGNED",
                     "prose: 2 live declarations. Kept verbatim, reported "
                     "unresolved, never dropped"),
                    ("3eeb42d",
                     "seven characters — a typo, not a shorthand"),
                )],
        },
        "expect_totals": {
            # THE INVARIANT THIS FILE EXISTS FOR: the count does not move.
            # `execution_yours` is a PICTURE over an unchanged number, and if
            # a future change makes it a fourth stage these two figures
            # separate and both suites go red.
            "execution_yours": sum(1 for c in cases
                                   if c["expect"]["execution_yours"]),
            "counted_for_ceo": sum(
                1 for c in cases
                if c["expect"]["next_actor_resolved"] in deskcard.CEO_ACTORS),
            "superseded_edges": sum(1 for c in cases
                                    if c["expect"]["superseded_by"]),
            "repaired_reprs": sum(
                1 for c in cases
                if c["expect"]["title_display"] != c["expect"]["title"]),
            "requests_on_the_ceos_figure": sum(
                1 for c in req_cases
                if c["expect"]["next_actor_resolved"] in deskcard.CEO_ACTORS),
        },
    }
    body["digest"] = hashlib.sha256(_canonical(body)).hexdigest()
    return body


def main() -> int:
    # `--check` NEVER WRITES, and that separation is not tidiness.
    #
    # The first cut of the test suite ran this script as a subprocess to prove
    # the "regenerate it" instruction in every failure message actually works —
    # and the script wrote the file, so the very artifact the next assertion
    # compares against was being replaced by the run under test. Under any
    # reordering that makes the match test vacuous: it would compare the file
    # to itself and pass over a routing change. A test that repairs the thing
    # it is checking is the bug-blessing pattern this whole contract exists to
    # stop, so the read path and the write path are different flags.
    # BOTH CONTRACTS, ONE COMMAND. They are separate files with separate
    # digests, and checking them separately would let one be regenerated while
    # the other silently went stale — which is the drift the whole mechanism
    # exists to make impossible.
    pairs = ((CONTRACT_PATH, build), (CARD_CONTRACT_PATH, build_cards))

    if "--check" in sys.argv[1:]:
        bad = False
        for path, builder in pairs:
            body = builder()
            if not path.exists():
                print(f"MISSING {path}", file=sys.stderr)
                bad = True
                continue
            if path.read_text(encoding="utf-8") != render(body):
                print(f"STALE — {path.name} does not match desk.py. "
                      f"Run without --check to regenerate.", file=sys.stderr)
                bad = True
                continue
            print(f"OK {path.name} digest {body['digest']}")
        return 1 if bad else 0

    body = build()
    cards = build_cards()
    CARD_CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    CARD_CONTRACT_PATH.write_text(render(cards), encoding="utf-8", newline="\n")
    print(f"wrote {CARD_CONTRACT_PATH}")
    print(f"card digest   : {cards['digest']}")
    CONTRACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Newline-terminated, LF, UTF-8, 2-space indent: readable in review, and the
    # digest is over the canonical form rather than this rendering, so a
    # reformat cannot silently change what the two repos agree on.
    CONTRACT_PATH.write_text(render(body), encoding="utf-8", newline="\n")
    print(f"wrote {CONTRACT_PATH}")
    print(f"rules_version : {body['rules_version']}")
    print(f"digest        : {body['digest']}")
    print(f"desk_load total (CEO's figure over the cases): "
          f"{body['expect_totals']['desk_load_total']} of {len(body['cases'])}")
    print("\nNow copy this file to KryptonPay/contract/desk_stage_contract.v1.json")
    print("and set CONTRACT_DIGEST in deskStageContract.test.ts to the digest "
          "above.\nBoth suites fail until you do.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
