/**
 * The request card's two pure pieces.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/requestCard.test.ts`
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`, CEO-ratified after request
 * `0c295ec7` rendered as a wall of prose. The rail's whole job is the sentence
 * that card buried: approved 22 minutes after filing, then idle 2.5 days.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { ageLabel } from "./cardState.ts";
import { queuedAsks } from "./execDesk.ts";
import type { DeskView } from "@/lib/fund_api";

/* ------------------------------------------------------------ the age ----- */

test("an age past a day reads in days — 2.5d is the story", () => {
  assert.equal(ageLabel(60), "2.5d");
  assert.equal(ageLabel(24), "1.0d");
});

test("an age under a day reads in hours", () => {
  assert.equal(ageLabel(4), "4.0h");
  assert.equal(ageLabel(23.9), "23.9h");
});

test("A MISSING AGE RENDERS NOTHING, never 0.0h", () => {
  /* "awaiting dispatch · 0.0h" over a row idle for two and a half days would
     be this fund's oldest mistake on its newest surface. Absence is absence. */
  assert.equal(ageLabel(null), null);
  assert.equal(ageLabel(Number.NaN), null);
  assert.equal(ageLabel(Number.POSITIVE_INFINITY), null);
});

test("a genuine zero is still a zero", () => {
  /* The mirror of the rule above: a stage entered a moment ago HAS an age and
     it is 0.0h. Rendering nothing there would hide a fact, which is the same
     error pointed the other way. */
  assert.equal(ageLabel(0), "0.0h");
});

/* ------------------------------------------------ the card off the wire --- */

const req = (o: Record<string, unknown>) =>
  ({ request_id: "q", status: "open", kind: "build", serves: "builder",
     at: "2026-08-22T10:00:00+00:00", ...o }) as unknown as
    DeskView["requests"][number];

test("a PROSE ask keeps its subject and is marked unstructured", () => {
  /* All 109 requests filed before the schema existed. There is no migration
     and never will be: rewriting an old subject to look structured would
     invent a headline the filer never wrote. */
  const [a] = queuedAsks([req({
    subject: "DESK RENDERING + ROUTING\nFive rows rendered as raw reprs." })]);
  assert.equal(a.card.structured, false);
  assert.equal(a.card.headline, "DESK RENDERING + ROUTING");
  assert.equal(a.card.wanted.length, 0);
  assert.equal(a.card.nextMove, null);
});

test("a STRUCTURED ask carries all four answers", () => {
  const [a] = queuedAsks([req({
    structured: true,
    headline: "Repair the CEO's desk read path",
    summary: "His clicks land; the fold does not.",
    incident: "Six defects pooled in a starved batch.",
    wanted: [{ text: "dict payloads", state: "done" },
             { text: "cascade", state: "in_progress", note: "spine half" },
             { text: "contract test", state: "open" }],
    next_move: { actor: "the chair", act: "batches this into a dispatch" },
    lifecycle: { current: "awaiting_dispatch", age_hours: 60.0,
                 declined: false,
                 stages: [{ stage: "filed", at: null, reached: true,
                            current: false }] },
  })]);
  assert.equal(a.card.structured, true);
  assert.equal(a.card.headline, "Repair the CEO's desk read path");
  assert.equal(a.card.summary, "His clicks land; the fold does not.");
  assert.deepEqual(a.card.wanted.map((w) => w.state),
                   ["done", "in_progress", "open"]);
  assert.deepEqual(a.card.nextMove,
                   { actor: "the chair", act: "batches this into a dispatch" });
  assert.equal(a.card.lifecycle?.ageHours, 60.0);
  assert.equal(a.card.lifecycle?.current, "awaiting_dispatch");
});

test("a next_move missing its ACT renders nothing at all", () => {
  /* The spec's own complaint about the old chip: it named an owner and left
     the reader to guess the obligation. Both fields or neither. */
  const [a] = queuedAsks([req({ subject: "s",
                                next_move: { actor: "the chair" } })]);
  assert.equal(a.card.nextMove, null);
});

test("a spine with no lifecycle renders no rail rather than an empty one", () => {
  const [a] = queuedAsks([req({ subject: "s" })]);
  assert.equal(a.card.lifecycle, null);
});

test("a non-numeric age from the wire is absent, not coerced", () => {
  const [a] = queuedAsks([req({
    subject: "s",
    lifecycle: { current: "filed", age_hours: "2.5", stages: [] } })]);
  assert.equal(a.card.lifecycle?.ageHours, null);
});

test("an ask with no subject at all reports no headline, not an empty one", () => {
  const [a] = queuedAsks([req({})]);
  assert.equal(a.card.headline, null);
});

/* ------------------------------------------- the control the routing took -- */

/**
 * A REMOVED CONTROL, found by looking at the rendered page.
 *
 * The ask card rendered its Approve/Decline buttons on
 * `stage === "awaiting_ceo"`. Request routing v2 moved an OPEN request to the
 * chair on 2026-08-24 — correctly, and for a measured reason — and every ask
 * left that stage. The buttons went with them, so the CEO could no longer
 * approve a desk request from his own page at all.
 *
 * Neither half was wrong on its own and no test could see it: the routing was
 * right, the render was right, and one flag was doing two jobs. Whose move it
 * is decides COUNTING; whether a control exists answers to the row's own
 * LIFECYCLE. Routing must never take a control away.
 */
test("AN OPEN ASK STAYS APPROVABLE EVEN WHEN IT IS THE CHAIR'S MOVE", () => {
  const [a] = queuedAsks([req({ status: "open",
                                next_actor_resolved: "chair" })]);
  assert.equal(a.stage, "cleared_to_trigger", "counted as the chair's");
  assert.equal(a.approvable, true,
               "and STILL approvable — the CEO's control did not move");
});

test("an ask he has already approved is no longer approvable", () => {
  const [a] = queuedAsks([req({ status: "approved" })]);
  assert.equal(a.approvable, false);
});

test("a declined ask is not approvable — a decline is terminal", () => {
  const [a] = queuedAsks([req({ status: "declined" })]);
  assert.equal(a.approvable, false);
});

test("a resolved ask is not approvable", () => {
  /* `queuedAsks` filters resolved rows out entirely today; asserted anyway so
     a widened filter cannot put an approve button on served history. */
  const rows = queuedAsks([req({ status: "resolved" })]);
  for (const a of rows) assert.equal(a.approvable, false);
});
