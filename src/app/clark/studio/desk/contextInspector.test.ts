import test from "node:test";
import assert from "node:assert/strict";

import { contextOf } from "./contextInspector.ts";
import type { DeskRequest, DeskRun } from "./seatLib.ts";

/**
 * WHAT THIS SEAT WAS TOLD.
 *
 * The one thing this must never do is render an empty pane and let it read as
 * "this is the context". The pack the design calls for does not exist yet, so
 * every arm below says *no pack recorded* — a stated absence — and the
 * material that DOES exist (the dispatch line, and the asks' verbatim briefs)
 * is rendered as itself.
 *
 * The sharpest test is `missing`: a job that names asks this page did not
 * read must not look like a job that served nothing. "We did not look far
 * enough" and "there was nothing" are different facts with different fixes,
 * and the capped payload makes the first one common.
 */

const RUN = (over: Record<string, unknown> = {}): DeskRun => ({
  run_id: "run-builder-mach1", seat: "builder",
  task: "MACH1 - v5 draft redesign", meta: {}, ...over,
}) as unknown as DeskRun;

const REQ = (over: Record<string, unknown> = {}): DeskRequest => ({
  request_id: "e1d0fdf4", subject: "Close the v5 residuals",
  note: "THE BUILD, one KP+spine diff, fires on the next free builder slot.",
  status: "approved", ...over,
}) as unknown as DeskRequest;

test("no run at all is UNKNOWN, and the fold is not drawn", () => {
  const c = contextOf(null, []);
  assert.equal(c.empty, true);
  assert.match(c.note, /unknown/);
});

test("a job with only its dispatch line says so, and NAMES the missing pack", () => {
  const c = contextOf(RUN(), []);
  assert.equal(c.task, "MACH1 - v5 draft redesign");
  assert.deepEqual(c.served, []);
  assert.equal(c.pack, null);
  assert.equal(c.empty, false);
  assert.match(c.note, /No pack recorded/);
  assert.match(c.note, /not on the record/);
});

test("a job with NEITHER a line NOR asks is unknown, not nothing", () => {
  const c = contextOf(RUN({ task: null }), []);
  assert.equal(c.empty, true);
  assert.match(c.note, /unknown, not nothing/);
});

test("the ask's brief is rendered VERBATIM — that is what the seat was told", () => {
  const c = contextOf(RUN({ meta: { serves_requests: ["e1d0fdf4"] } }), [REQ()]);
  assert.equal(c.served.length, 1);
  assert.equal(c.served[0].subject, "Close the v5 residuals");
  assert.match(c.served[0].brief!, /one KP\+spine diff/);
  assert.equal(c.served[0].missing, false);
  assert.match(c.note, /word for word/);
  assert.match(c.note, /No pack recorded/);
});

test("an ask named but NOT in what this page read is `missing`, not dropped", () => {
  // The payload's request list is capped. Dropping the id would turn "we did
  // not look far enough" into "it served nothing".
  const c = contextOf(RUN({ meta: { serves_requests: ["nowhere"] } }), [REQ()]);
  assert.equal(c.served.length, 1);
  assert.equal(c.served[0].missing, true);
  assert.equal(c.served[0].brief, null);
  assert.match(c.note, /did not look far enough/);
});

test("a partial find reports BOTH the briefs and the shortfall", () => {
  const c = contextOf(
    RUN({ meta: { serves_requests: ["e1d0fdf4", "nowhere"] } }), [REQ()]);
  assert.equal(c.served.filter((s) => s.missing).length, 1);
  assert.match(c.note, /word for word/);
  assert.match(c.note, /1 further ask\(s\) were named and not found/);
});

test("an ask with a subject and no brief is not a brief with an empty string", () => {
  const c = contextOf(RUN({ meta: { serves_requests: ["e1d0fdf4"] } }),
    [REQ({ note: "   " })]);
  assert.equal(c.served[0].brief, null);
  assert.equal(c.served[0].subject, "Close the v5 residuals");
});

test("a junk serves_requests entry is dropped, not rendered as an id", () => {
  const c = contextOf(
    RUN({ meta: { serves_requests: [null, 7, "", "  ", "e1d0fdf4"] } }), [REQ()]);
  assert.deepEqual(c.served.map((s) => s.requestId), ["e1d0fdf4"]);
});

test("a non-object meta does not throw and reads as no asks served", () => {
  for (const junk of ["a string", 7, [], null, undefined]) {
    const c = contextOf(RUN({ meta: junk }), [REQ()]);
    assert.deepEqual(c.served, []);
  }
});

test("an unreadable request list is survived — the line is still shown", () => {
  const c = contextOf(RUN({ meta: { serves_requests: ["e1d0fdf4"] } }), null);
  assert.equal(c.served[0].missing, true);
  assert.equal(c.task, "MACH1 - v5 draft redesign");
});

test("the pack slot is null on every arm — it is a seam, not a feature", () => {
  for (const c of [
    contextOf(RUN(), []),
    contextOf(RUN({ meta: { serves_requests: ["e1d0fdf4"] } }), [REQ()]),
    contextOf(null, []),
  ]) {
    assert.equal(c.pack, null);
  }
});
