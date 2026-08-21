/**
 * "Whose move is it" on the CEO's desk — the third stage, and the number.
 *
 * THE INCIDENT, the CEO in his own words (2026-08-22): *"they sustain on my
 * queue even if that work has been done"*, and *"since morning my desk has
 * stale; out of order and poorly designed stuff. Making my flow messy"*.
 *
 * The page had its own status-label rule and the spine's counter had another.
 * On one live payload they rendered 11 and 6 for the same question, eight
 * pixels apart on the same line. This file pins the repair: ONE definition, in
 * the spine, read off the row — and the rows it routes away stay on the page.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskOwnership.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import {
  type DeskItem, recItems, splitDeskItems, stageOfItem,
} from "./execDesk.ts";
import { hasContent, officerDesk } from "./officerQueues.ts";

const rec = (o: Record<string, unknown>) =>
  ({ run_id: "r1", rec_id: 1, seat: "pm", kind: "process", status: "open",
     text: "t", task: "task", artifact_path: null, trace_id: null,
     ...o }) as never;

const run = (o: Record<string, unknown> = {}) =>
  ({ run_id: "r1", seat: "pm", task: "t",
     resolved_at: "2026-08-21T10:00:00+00:00", ...o }) as never;

const item = (o: Partial<DeskItem>): DeskItem => ({
  key: "k", kind: "recommendation", moneyUsd: null,
  reversibility: "reversible", waitingSince: null, dueDate: null, ...o,
});

/* ----------------------------------------------------------- the stage --- */

test("an open row the CEO must decide awaits his decision", () => {
  assert.equal(
    stageOfItem(item({ nextActor: "ceo", rec: rec({ status: "open" }) })),
    "awaiting_decision");
});

test("a DECIDED row is awaiting execution — the CEO's complaint, pinned", () => {
  for (const status of ["accepted", "staged"]) {
    assert.equal(
      stageOfItem(item({ nextActor: "chair", rec: rec({ status }) })),
      "awaiting_execution", status);
  }
});

test("an OPEN row owned by the chair is neither his decision nor a promise", () => {
  /* The distinction that earns the third stage. Nobody decided it, so calling
   * it "decided, awaiting execution" would report a promise the firm never
   * made; nobody is waiting on the CEO, so counting it is the complaint. */
  for (const actor of ["chair", "seat", "nobody"]) {
    assert.equal(
      stageOfItem(item({ nextActor: actor, rec: rec({ status: "open" }) })),
      "owned_elsewhere", actor);
  }
});

test("an UNKNOWN owner stays with the CEO", () => {
  /* Absence is never zero, including the absence of an answer about who owns a
   * row. Routing an unreadable row away would make it disappear from the one
   * number that is supposed to tell him what he still owes. */
  assert.equal(
    stageOfItem(item({ nextActor: "unknown", rec: rec({ status: "open" }) })),
    "awaiting_decision");
});

test("a pending ORDER is the CEO's decision whatever else is true", () => {
  assert.equal(stageOfItem(item({ kind: "order", nextActor: "chair" })),
               "awaiting_decision");
});

test("a spine with no routing falls back to the OLD rule, never to a guess", () => {
  /* Degrading to the previous behaviour is the only safe direction: guessing
   * would put the page back to having its own second definition. */
  assert.equal(stageOfItem(item({ rec: rec({ status: "open" }) })),
               "awaiting_decision");
  assert.equal(stageOfItem(item({ rec: rec({ status: "accepted" }) })),
               "awaiting_execution");
});

test("the page NEVER re-derives the routing from kind or status", () => {
  /* The whole repair is that there is one definition. A second one in
   * TypeScript would be free to drift from the Python, which is exactly how
   * 11 and 6 ended up on the same line. */
  const src = readFileSync(new URL("./execDesk.ts", import.meta.url), "utf8");
  const fn = src.slice(src.indexOf("export function stageOfItem"),
                       src.indexOf("export interface DeskSplit"));
  assert.ok(fn.includes("i.nextActor"), "the stage must read the spine's field");
  assert.ok(!fn.includes("KIND_ACTORS") && !fn.includes("awaits-ceo"),
    "no kind table may be re-implemented on the client");
});

/* ------------------------------------------------------------ the split -- */

test("the split loses nothing across all three queues", () => {
  const items = recItems([
    rec({ rec_id: 1, status: "open", next_actor_resolved: "ceo" }),
    rec({ rec_id: 2, status: "accepted", next_actor_resolved: "chair" }),
    rec({ rec_id: 3, status: "open", kind: "build",
          next_actor_resolved: "chair" }),
    rec({ rec_id: 4, status: "open", kind: "handoff_to_quant",
          next_actor_resolved: "seat" }),
  ], [run()]);
  const s = splitDeskItems(items);
  assert.equal(s.awaitingDecision.length, 1);
  assert.equal(s.awaitingExecution.length, 1);
  assert.equal(s.ownedElsewhere.length, 2);
  assert.equal(
    s.awaitingDecision.length + s.awaitingExecution.length
      + s.ownedElsewhere.length,
    items.length, "every item must land in exactly one queue");
});

/* --------------------------------------------------------- the queues ---- */

test("chair-owned rows are SHOWN and NOT COUNTED", () => {
  /* Both halves matter and they pull in opposite directions. Counting them was
   * the complaint; hiding them would be a worse answer to it — "do not solve a
   * counting problem by hiding work". */
  const mine = recItems([rec({ rec_id: 1, status: "open",
                               next_actor_resolved: "ceo" })], [run()]);
  const theirs = recItems([rec({ rec_id: 2, status: "open", kind: "build",
                                 next_actor_resolved: "chair" })], [run()]);
  const d = officerDesk({
    awaitingDecision: mine, awaitingExecution: [], ownedElsewhere: theirs,
    memos: [], asks: [],
  });
  assert.equal(d.awaitingTotal, 1, "only the CEO's row counts");
  assert.equal(d.others.elsewhere.length, 1, "and the chair's row is still here");
  assert.ok(hasContent(d.others));
});

test("a queue holding ONLY somebody else's work is not empty", () => {
  /* `hasContent` decides whether a queue renders at all. If it ignored the new
   * bucket, an officer whose entire output was engineering tickets would
   * vanish from the page — hiding by omission rather than by filtering. */
  const theirs = recItems([rec({ rec_id: 2, seat: "validator", status: "open",
                                 kind: "harness",
                                 next_actor_resolved: "chair" })], [run()]);
  const d = officerDesk({
    awaitingDecision: [], awaitingExecution: [], ownedElsewhere: theirs,
    memos: [], asks: [],
  });
  assert.equal(d.awaitingTotal, 0);
  assert.ok(hasContent(d.others), "a queue of others' work must still render");
});

test("a caller that predates the third stage still works", () => {
  const d = officerDesk({
    awaitingDecision: [], awaitingExecution: [], memos: [], asks: [],
  });
  assert.equal(d.others.elsewhere.length, 0);
  assert.equal(d.awaitingTotal, 0);
});

test("the CEO page renders the routed-away rows and says why", () => {
  const src = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  assert.ok(src.includes("ownedElsewhere: split.ownedElsewhere"),
    "the page must pass the third queue through to the officer routing");
  assert.ok(src.includes("Open, and not yours"),
    "the routed-away rows need a section of their own");
  assert.ok(src.includes("next_actor_why"),
    "each routed row must carry the spine's reason, so a reader can disagree");
  assert.ok(src.includes("with the chair or a seat"),
    "the headline must say where the rows that left the count went");
});
