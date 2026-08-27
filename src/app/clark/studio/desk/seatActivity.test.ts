import test from "node:test";
import assert from "node:assert/strict";

import { benchFlight, seatLamps } from "./seatActivity.ts";
import type { DeskView } from "@/lib/fund_api";

/**
 * THE ROOM TELLS THE TRUTH ABOUT PARALLELISM.
 *
 * THE INCIDENT: the CEO, on the floor, 2026-08-27 — *"1 builder working but 2
 * in reality"*. The spine's fold kept only a seat's newest dispatch, and the
 * floor drew what the spine served.
 *
 * The tests that matter here are NOT the happy path. They are:
 *
 *  - the OLD ENVELOPE arm. A spine that has not been restarted since the fold
 *    shipped serves no `open_dispatches`, and drawing zero lamps for a working
 *    seat because a key is missing is the absence-as-zero the non-negotiables
 *    forbid. `basis: "headline_only"` + `countIsFloor` is the whole point.
 *  - the UNREADABLE arm. No envelope at all must read UNKNOWN, never idle.
 *  - the counts coming from the SPINE, not from a recount here. Two counts of
 *    one population is two counts.
 */

type Activity = DeskView["roster"][number]["activity"];

const NEW = (over: Record<string, unknown> = {}) => ({
  status: "working", task: "slice3", since: "2026-08-27T07:32:39+00:00",
  task_id: "t-slice3", returned_run_id: null, review_detectable: true,
  open_dispatches: [
    { status: "working", task: "slice3", since: "2026-08-27T07:32:39+00:00",
      task_id: "t-slice3", returned_run_id: null, review_detectable: true },
    { status: "working", task: "ops1", since: "2026-08-27T07:20:00+00:00",
      task_id: "t-ops1", returned_run_id: null, review_detectable: true },
  ],
  working_count: 2, awaiting_review_count: 0, last_delivered: null,
  ...over,
}) as unknown as Activity;

/* ------------------------------------------------------- the incident ----- */

test("two open dispatches draw two lamps, each with its own task", () => {
  const r = seatLamps("builder", NEW());
  assert.equal(r.basis, "open_dispatches");
  assert.equal(r.drawn, 2);
  assert.deepEqual(r.lamps.map((l) => l.task), ["slice3", "ops1"]);
  assert.deepEqual(r.lamps.map((l) => l.taskId), ["t-slice3", "t-ops1"]);
  assert.equal(r.countIsFloor, false);
});

test("the counts are the SPINE'S, and absent when the spine states none", () => {
  const r = seatLamps("builder", NEW());
  assert.equal(r.workingCount, 2);
  assert.equal(r.awaitingCount, 0);
  // Strip the spine's counts: the lamps still draw, but the COUNTS go absent
  // rather than being recounted here under the spine's authority.
  const stripped = seatLamps("builder", NEW({
    working_count: undefined, awaiting_review_count: undefined,
  }));
  assert.equal(stripped.drawn, 2, "the lamps are still drawn");
  assert.equal(stripped.workingCount, null);
  assert.equal(stripped.awaitingCount, null);
});

test("a returned dispatch is its own state, not a second working lamp", () => {
  const r = seatLamps("builder", NEW({
    open_dispatches: [
      { status: "awaiting_review", task: "eng3", task_id: "t1",
        since: "2026-08-27T05:00:00+00:00", returned_run_id: "run-builder-eng3",
        review_detectable: true },
      { status: "working", task: "slice3", task_id: "t2",
        since: "2026-08-27T07:00:00+00:00", returned_run_id: null,
        review_detectable: true },
    ],
    working_count: 1, awaiting_review_count: 1,
  }));
  assert.deepEqual(r.lamps.map((l) => l.state),
    ["awaiting_review", "working"]);
  assert.equal(r.lamps[0].returnedRunId, "run-builder-eng3");
  assert.equal(r.workingCount, 1);
  assert.equal(r.awaitingCount, 1);
});

/* ---------------------------------------------- the payload that predates -- */

test("an OLD envelope draws ONE lamp and says the number is a floor", () => {
  const old = {
    status: "working", task: "slice3", since: "2026-08-27T07:32:39+00:00",
    task_id: "t-slice3", returned_run_id: null, review_detectable: true,
    last_delivered: null,
  } as unknown as Activity;
  const r = seatLamps("builder", old);
  assert.equal(r.basis, "headline_only");
  assert.equal(r.drawn, 1);
  assert.equal(r.countIsFloor, true);
  // NOT zero, and NOT two. The counts are absent because the payload does not
  // carry them — a recount of a list that only holds the newest row would be a
  // confident answer built on a truncated list.
  assert.equal(r.workingCount, null);
  assert.equal(r.awaitingCount, null);
  assert.match(r.note, /floor, not a count/);
});

test("an OLD envelope on an IDLE seat draws no lamp and still says floor", () => {
  const old = {
    status: "idle", task: null, since: null, last_delivered: null,
  } as unknown as Activity;
  const r = seatLamps("coo", old);
  assert.equal(r.basis, "headline_only");
  assert.equal(r.drawn, 0);
  assert.equal(r.countIsFloor, true, "old envelopes cannot prove a seat idle");
});

test("no envelope at all reads UNKNOWN, never idle", () => {
  for (const nothing of [null, undefined]) {
    const r = seatLamps("cfo", nothing);
    assert.equal(r.basis, "unreadable");
    assert.equal(r.headline, null);
    assert.equal(r.drawn, 0);
    assert.equal(r.workingCount, null);
    assert.match(r.note, /UNKNOWN — not idle/);
  }
});

/* ------------------------------------------------------ the disagreement -- */

test("headline idle + an open dispatch is reported as a DISAGREEMENT", () => {
  // The spine documents this on purpose: `working_on` is retired when the
  // NEWEST dispatch resolves, so an older open dispatch leaves the headline
  // reading idle. Clause 3 of the illumination principle: show both.
  const r = seatLamps("builder", NEW({
    status: "idle", task: null, since: null, task_id: null,
    open_dispatches: [
      { status: "working", task: "the older one", task_id: "t-old",
        since: "2026-08-27T05:00:00+00:00", returned_run_id: null,
        review_detectable: true },
    ],
    working_count: 1, awaiting_review_count: 0,
  }));
  assert.equal(r.headline, "idle");
  assert.equal(r.understates, true);
  assert.equal(r.drawn, 1);
  assert.match(r.note, /headline is the compatibility surface/);
});

test("headline idle with an EMPTY list is not a disagreement", () => {
  const r = seatLamps("quant", NEW({
    status: "idle", task: null, since: null, task_id: null,
    open_dispatches: [], working_count: 0, awaiting_review_count: 0,
  }));
  assert.equal(r.understates, false);
  assert.equal(r.workingCount, 0, "a measured zero, and it is reported");
  assert.match(r.note, /An idle seat costs zero/);
});

/* ------------------------------------------------------- broken rows ------ */

test("a row with an unreadable state is DROPPED and the drop is reported", () => {
  const r = seatLamps("builder", NEW({
    open_dispatches: [
      { status: "working", task: "real", task_id: "t1", since: null,
        returned_run_id: null, review_detectable: true },
      { status: "elsewhere", task: "bogus", task_id: "t2" },
      "a string",
      null,
    ],
    working_count: 1, awaiting_review_count: 0,
  }));
  assert.equal(r.drawn, 1);
  assert.match(r.note, /3 carried no readable state/);
  assert.match(r.note, /not a job that is not running/);
});

test("review_detectable absent reads as NOT detectable, never as true", () => {
  const r = seatLamps("builder", NEW({
    open_dispatches: [
      { status: "working", task: "x", task_id: "t1", since: null,
        returned_run_id: null },
    ],
    working_count: 1, awaiting_review_count: 0,
  }));
  assert.equal(r.lamps[0].reviewDetectable, false);
});

test("blank strings are absent, not empty labels", () => {
  const r = seatLamps("builder", NEW({
    open_dispatches: [
      { status: "working", task: "   ", task_id: "", since: "",
        returned_run_id: "", review_detectable: true },
    ],
    working_count: 1, awaiting_review_count: 0,
  }));
  assert.equal(r.lamps[0].task, null);
  assert.equal(r.lamps[0].taskId, null);
  assert.equal(r.lamps[0].since, null);
  assert.equal(r.lamps[0].returnedRunId, null);
});

/* --------------------------------------------------------- the bench ------ */

test("the bench total sums the lamps, and is a FLOOR if any seat is old", () => {
  const modern = seatLamps("builder", NEW());
  const old = seatLamps("quant", {
    status: "working", task: "belt", since: null, last_delivered: null,
  } as unknown as Activity);
  const clean = benchFlight([modern]);
  assert.deepEqual([clean.working, clean.awaiting, clean.isFloor], [2, 0, false]);
  const mixed = benchFlight([modern, old]);
  assert.equal(mixed.working, 3);
  assert.equal(mixed.isFloor, true);
  assert.match(mixed.note, /only their newest dispatch/);
});

test("an unreadable seat NAMES itself in the bench note and floors the total", () => {
  const b = benchFlight([seatLamps("builder", NEW()), seatLamps("cfo", null)]);
  assert.deepEqual(b.unreadable, ["cfo"]);
  assert.equal(b.isFloor, true);
  assert.match(b.note, /cfo/);
  assert.match(b.note, /this total is a floor/);
});

test("an empty bench is zero and says so without claiming a floor", () => {
  const b = benchFlight([]);
  assert.deepEqual([b.working, b.awaiting, b.isFloor], [0, 0, false]);
  assert.deepEqual(b.unreadable, []);
});
