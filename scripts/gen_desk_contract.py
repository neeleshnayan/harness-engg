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

CONTRACT_PATH = REPO / "contract" / "desk_stage_contract.v1.json"

#: How a spine verdict maps onto the page's three stages. THE MAPPING LIVES
#: HERE, on the spine side, on purpose: the page must not own a routing rule of
#: its own, and a mapping table in TypeScript would be the second definition
#: this whole contract exists to prevent. The page consumes it; this states it.
#:
#: `status` is read for ONE thing and it is not routing: telling a row the CEO
#: DECIDED and the firm owes back ("awaiting_execution") from an open row that
#: was never his ("owned_elsewhere"). Both are uncounted; they are different
#: facts and the desk has already paid once for confusing them.
def stage_for(actor: str, status: Any) -> str:
    if actor in ("ceo", "unknown"):
        return "awaiting_decision"
    decided = status in ("accepted", "staged")
    return "awaiting_execution" if decided else "owned_elsewhere"


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
    if "--check" in sys.argv[1:]:
        body = build()
        if not CONTRACT_PATH.exists():
            print(f"MISSING {CONTRACT_PATH}", file=sys.stderr)
            return 1
        onfile = CONTRACT_PATH.read_text(encoding="utf-8")
        if onfile != render(body):
            print("STALE — the checked-in contract does not match desk.py. "
                  "Run without --check to regenerate.", file=sys.stderr)
            return 1
        print(f"OK digest {body['digest']}")
        return 0

    body = build()
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
