/**
 * The record row — the correctness kill of D42.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/recordRow.test.ts`
 *
 * THE INCIDENT (CEO, 2026-08-24, verbatim): *"like WTF"* — an already-executed
 * chair action rendered on his desk with **Accept** and **Reject** beside it.
 * Measured on the live payload the same morning (`GET /api/v1/fund/desk`, 238
 * open recommendations): exactly one row carries
 * `next_actor_resolved: "nobody"` — `run-coo-triage8` rec 7, a `finding`,
 * status `open`, `next_actor_basis: "explicit"`, `desk_stage:
 * "owned_elsewhere"`. Three fields said it was finished; every surface read
 * only `status === "open"`.
 *
 * Every test below fails if that row is ever offered a decision again.
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  isRecordRow, recordRowNote, routedActor, splitRecordRows,
} from "./recordRow.ts";

/** The live row, field for field, from the payload of 2026-08-24. */
const LIVE_RECORD_ROW = {
  status: "open",
  next_actor: "nobody",
  next_actor_resolved: "nobody",
  next_actor_basis: "explicit",
  next_actor_why: "the row states its next actor is the nobody",
  seat: "coo",
  run_id: "run-coo-triage8",
  rec_id: 7,
};

/* ------------------------------------------------------------- the actor -- */

test("the resolved actor wins over the raw declaration", () => {
  assert.equal(
    routedActor({ next_actor: "ceo", next_actor_resolved: "chair" }), "chair");
});

test("the raw declaration is the fallback when nothing resolved it", () => {
  assert.equal(routedActor({ next_actor: "nobody" }), "nobody");
});

test("an absent, empty or blank actor is null, never a string", () => {
  assert.equal(routedActor({}), null);
  assert.equal(routedActor({ next_actor_resolved: "" }), null);
  assert.equal(routedActor({ next_actor_resolved: "   " }), null);
  assert.equal(routedActor(null), null);
  assert.equal(routedActor(undefined), null);
});

/* ------------------------------------------------------- the predicate ---- */

test("THE INCIDENT ROW: the live nobody row is a record row", () => {
  assert.equal(isRecordRow(LIVE_RECORD_ROW), true);
});

test("a record row is recognised WHILE ITS STATUS IS OPEN — reading status "
  + "here would rebuild the bug inside the guard", () => {
  assert.equal(LIVE_RECORD_ROW.status, "open");
  assert.equal(isRecordRow(LIVE_RECORD_ROW), true);
});

test("every other actor the spine emits is NOT a record row", () => {
  for (const actor of ["ceo", "chair", "seat", "unknown"]) {
    assert.equal(isRecordRow({ status: "open", next_actor_resolved: actor }),
      false, `${actor} must keep its controls`);
  }
});

test("A ROW THAT STATES NO ACTOR IS NOT A RECORD ROW. 'the spine did not say' "
  + "and 'the spine said nobody' are different facts, and only the second "
  + "closes a row — a page that closed the first would silently take the "
  + "CEO's controls off every un-annotated row on his desk", () => {
  assert.equal(isRecordRow({ status: "open" }), false);
  assert.equal(isRecordRow({ status: "open", next_actor_resolved: null }), false);
});

test("the resolved answer wins even when the raw declaration disagrees", () => {
  assert.equal(
    isRecordRow({ status: "open", next_actor: "ceo",
      next_actor_resolved: "nobody" }), true);
  assert.equal(
    isRecordRow({ status: "open", next_actor: "nobody",
      next_actor_resolved: "ceo" }), false);
});

/* ------------------------------------------------------------- the note --- */

test("the note carries the spine's own reason when it sent one", () => {
  const note = recordRowNote(LIVE_RECORD_ROW);
  assert.ok(note.startsWith("Filed for the record"));
  assert.ok(note.includes("the row states its next actor is the nobody"));
});

test("a record row with NO reason still renders a statement, never a blank "
  + "where two buttons were", () => {
  const note = recordRowNote({ status: "open", next_actor_resolved: "nobody" });
  assert.equal(note, "Filed for the record — no decision is owed");
  assert.ok(!note.endsWith("·"));
});

/* ------------------------------------------------------------ the split --- */

const rows = [
  { status: "open", next_actor_resolved: "ceo" },
  { status: "open", next_actor_resolved: "nobody" },
  { status: "open" },
  { status: "accepted", next_actor_resolved: "chair" },
  { status: "staged", next_actor_resolved: "nobody" },
];

test("the split routes the record row out of 'awaiting a decision'", () => {
  const s = splitRecordRows(rows);
  assert.equal(s.awaiting.length, 2);
  assert.equal(s.record.length, 1);
  assert.equal(s.decided.length, 2);
  assert.equal(s.record[0].next_actor_resolved, "nobody");
});

test("THE SPLIT LOSES NOTHING. A tidier desk that dropped a row would look "
  + "exactly like a correct one", () => {
  const s = splitRecordRows(rows);
  assert.equal(s.awaiting.length + s.record.length + s.decided.length,
    rows.length);
  const seen = new Set([...s.awaiting, ...s.record, ...s.decided]);
  assert.equal(seen.size, rows.length);
});

test("A DECIDED ROW IS NEVER RECLASSIFIED AS RECORD. It is a promise the firm "
  + "owes back, and 'decided, awaiting execution' is where the CEO reads it", () => {
  const s = splitRecordRows([{ status: "staged", next_actor_resolved: "nobody" }]);
  assert.equal(s.record.length, 0);
  assert.equal(s.decided.length, 1);
});

test("an empty desk splits into three empty lists, not into undefined", () => {
  const s = splitRecordRows([]);
  assert.deepEqual([s.awaiting, s.record, s.decided], [[], [], []]);
});
