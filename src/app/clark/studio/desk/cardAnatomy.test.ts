/**
 * Card anatomy — the clamp, the rail, and the whose-move line.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/cardAnatomy.test.ts`
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`. The property that cannot be
 * checked by looking at the page, and is therefore the reason this file
 * exists: **a clamp that swallowed a sentence renders identically to one that
 * did not.** `rejoin` is asserted lossless on every case, including the live
 * strings that motivated the clamp.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  CARD_HEADLINE_MAX, bodyWithTail, clampLine, nextMoveLine, recLifecycle,
  rejoin,
} from "./cardAnatomy.ts";

/** Verbatim from the CEO's desk, 2026-08-24 — the four headlines that ran to
 *  two or three rendered lines. Lengths: 190, 152, 148, 121. */
const LIVE_HEADLINES = [
  "MONDAY 1 of 3 (before 12:30Z): APPROVE R39 AS ONE SEQUENCE, stop conditions "
  + "binding on you too - no probe at broker means everything stops; "
  + "unsourceable residual > $10 means stop and file.",
  "MONDAY 2 of 3: WITHDRAW R37 (SUPERSEDED-PENDING chip applied): it would "
  + "disarm the TLT/DBC 09-08 exits for a premise ('broker holds zero') that "
  + "dies at R39 step 4.",
  "MONDAY 3 of 3: SIGN THE SET - drift-severity consequence (running "
  + "unratified, fired correctly), R20, R21, R22-TIGHTENING half (the "
  + "unguarded limits endpoint).",
  "NO DEADLINE: SIGN OR REVERSE the desk-counter predicate (live unsigned 3 "
  + "triages; 7% looser; the change is right, unsigned is the defect).",
];

/* -------------------------------------------------------------- the clamp - */

test("a short headline is untouched and reports itself unclamped", () => {
  const c = clampLine("A short name");
  assert.deepEqual(c, { line: "A short name", tail: "", clamped: false });
});

test("THE CLAMP IS LOSSLESS. Every live headline rejoins to itself", () => {
  for (const h of LIVE_HEADLINES) {
    const c = clampLine(h);
    assert.equal(c.clamped, true, `expected a clamp on ${h.length} chars`);
    assert.equal(rejoin(c), h.replace(/\s+/g, " ").trim());
  }
});

test("the rendered line fits the budget and ends in an ellipsis", () => {
  for (const h of LIVE_HEADLINES) {
    const c = clampLine(h);
    assert.ok(c.line.length <= CARD_HEADLINE_MAX + 1,
      `${c.line.length} > ${CARD_HEADLINE_MAX + 1}`);
    assert.ok(c.line.endsWith("…"));
  }
});

test("THE CUT IS AT A WORD BOUNDARY — a mid-word cut invents a word nobody "
  + "wrote, and this repo's own memoParts carries the reason it cuts "
  + "carefully", () => {
  for (const h of LIVE_HEADLINES) {
    const c = clampLine(h);
    const head = c.line.replace(/…$/, "");
    assert.ok(h.startsWith(head), "the head must be a literal prefix");
    // The character after the head in the original is whitespace, i.e. the cut
    // landed between words rather than inside one.
    assert.match(h.slice(head.length, head.length + 1), /\s/);
  }
});

test("a boundary table around the max: at, one under, one over", () => {
  const word = "ab "; // 3 chars, so lengths land exactly where intended
  const at = word.repeat(CARD_HEADLINE_MAX / 3).trim();
  assert.equal(at.length, CARD_HEADLINE_MAX - 1);
  assert.equal(clampLine(at).clamped, false);

  const exact = `${at}c`; // CARD_HEADLINE_MAX
  assert.equal(exact.length, CARD_HEADLINE_MAX);
  assert.equal(clampLine(exact).clamped, false, "<= max is not clamped");

  const over = `${at} cd`; // CARD_HEADLINE_MAX + 2
  assert.ok(over.length > CARD_HEADLINE_MAX);
  assert.equal(clampLine(over).clamped, true, "> max is clamped");
});

test("ONE UNBREAKABLE TOKEN IS RETURNED WHOLE. A url or an id cut to a "
  + "fragment plus an ellipsis is unreadable AND unsearchable, and the tail "
  + "would be a second fragment", () => {
  const id = "a".repeat(CARD_HEADLINE_MAX + 40);
  const c = clampLine(id);
  assert.equal(c.clamped, false);
  assert.equal(c.line, id);
  assert.equal(rejoin(c), id);
});

test("absence clamps to an empty line, never to the string 'null'", () => {
  assert.deepEqual(clampLine(null), { line: "", tail: "", clamped: false });
  assert.deepEqual(clampLine(undefined), { line: "", tail: "", clamped: false });
});

test("whitespace is collapsed so a subject full of newlines is one line", () => {
  assert.equal(clampLine("  a\n\n  b\tc  ").line, "a b c");
});

/* ---------------------------------------------------------- the tail join - */

test("the tail leads the body — it is the rest of the same sentence", () => {
  assert.equal(bodyWithTail("and then some.", "A later paragraph."),
    "and then some. A later paragraph.");
});

test("either half missing still gives a clean string", () => {
  assert.equal(bodyWithTail("", "rest"), "rest");
  assert.equal(bodyWithTail("tail", ""), "tail");
  assert.equal(bodyWithTail("", null), "");
});

/* ---------------------------------------------------------------- the rail */

const NOW = "2026-08-24T12:00:00+00:00";

test("an undecided row is CURRENT at filed and its executed stage is FUTURE — "
  + "a recommendation cannot have been carried out before it was accepted, "
  + "and that one IS a fact the record supports", () => {
  const l = recLifecycle(
    { status: "open", resolved_at: "2026-08-24T08:00:00+00:00" }, NOW);
  assert.deepEqual(l.stages.map((s) => [s.stage, s.state]), [
    ["filed", "current"], ["decided", "future"], ["executed", "future"],
  ]);
  assert.equal(l.ageHours, 4);
});

test("A DECIDED ROW'S EXECUTED STAGE IS 'unrecorded', NOT reached and NOT "
  + "future. Nothing on this desk records that a recommendation was carried "
  + "out; a tick would claim an execution nobody logged and a dim future "
  + "stage would claim one that happened never did", () => {
  const l = recLifecycle({
    status: "accepted",
    resolved_at: "2026-08-23T12:00:00+00:00",
    decided_at: "2026-08-24T09:00:00+00:00",
  }, NOW);
  assert.deepEqual(l.stages.map((s) => [s.stage, s.state]), [
    ["filed", "reached"], ["decided", "current"], ["executed", "unrecorded"],
  ]);
  assert.equal(l.ageHours, 3, "the age is measured from the CURRENT stage");
});

test("the age is ABSENT when nothing dates the current stage — this desk has "
  + "already shipped one age rendered where it should have been absent", () => {
  assert.equal(recLifecycle({ status: "open" }, NOW).ageHours, null);
  assert.equal(recLifecycle({ status: "open", resolved_at: "not a date" }, NOW)
    .ageHours, null);
  assert.equal(recLifecycle(null, NOW).ageHours, null);
});

test("a stage entered a moment ago HAS an age and it is zero — the mirror of "
  + "the absence rule, and rendering nothing there would hide a fact", () => {
  const l = recLifecycle({ status: "open", resolved_at: NOW }, NOW);
  assert.equal(l.ageHours, 0);
});

test("an empty-string timestamp is absence, not the epoch", () => {
  assert.equal(recLifecycle({ status: "open", resolved_at: "" }, NOW).ageHours,
    null);
  const l = recLifecycle(
    { status: "accepted", resolved_at: NOW, decided_at: "" }, NOW);
  assert.equal(l.stages[1].state, "future",
    "an undated decision is not a decision");
});

/* ------------------------------------------------------ whose move is it -- */

test("the whose-move line names the actor and carries the spine's reason", () => {
  assert.deepEqual(
    nextMoveLine({ next_actor_resolved: "chair", next_actor_why: "because" }),
    { actor: "chair", why: "because" });
});

test("NO ACTOR MEANS NO LINE. The old chip named an owner and left the "
  + "obligation to be guessed, and it named the wrong owner", () => {
  assert.equal(nextMoveLine({}), null);
  assert.equal(nextMoveLine({ next_actor_resolved: "  " }), null);
  assert.equal(nextMoveLine(null), null);
});

test("'unknown' is the spine saying it could not read an owner, so it is NOT "
  + "rendered as an instruction to somebody called unknown", () => {
  assert.equal(nextMoveLine({ next_actor_resolved: "unknown" }), null);
});

test("an actor without a reason still gets a line, with why null", () => {
  assert.deepEqual(nextMoveLine({ next_actor_resolved: "nobody" }),
    { actor: "nobody", why: null });
});
