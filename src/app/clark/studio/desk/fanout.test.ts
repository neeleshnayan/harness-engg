import test from "node:test";
import assert from "node:assert/strict";

import { parseWorker, seatFanout, seatsWithFanout } from "./fanout.ts";
import type { DeskView } from "@/lib/fund_api";

/**
 * FAN-OUT, FROM THE RECORD.
 *
 * The premise this file was written against, MEASURED on the running spine
 * before a line of the module existed: the brief said `meta.fanout` is a
 * structured array `[{worker, brief_one_line, kind, returned, tokens}]` on new
 * records. Exactly ONE run in the whole recorder carries the key —
 * `run-ed-batch4` — and it holds a free-text STRING. So the reader takes both
 * shapes and the tests below pin the thing that matters: **prose is never
 * parsed into workers.** Reading structure out of English is the same class
 * of mistake as reading a deadline out of prose, and this desk has been
 * repaired from that twice.
 */

function run(over: Record<string, unknown> = {}) {
  return {
    run_id: "run-x", seat: "mechanism", task: "t",
    resolved_at: "2026-08-23T10:00:00+00:00", recommendations: [],
    ...over,
  };
}

function desk(runs: Record<string, unknown>[]): DeskView {
  return {
    roster: [], protocol: [], artifacts: [], requests: [], runs,
    open_recommendations: [], open_requests: 0, kills: 0,
    execution_note: "", note: "",
  } as unknown as DeskView;
}

const src = (runs: Record<string, unknown>[]) =>
  ({ kind: "record" as const, desk: desk(runs) });

/* ------------------------------------------------------------- the tree -- */

test("a structured array becomes a tree, with every field kept apart", () => {
  const f = seatFanout(src([run({
    meta: {
      workers_fired: 3,
      fanout: [
        { worker: "recount", brief_one_line: "re-count the fertility claim",
          kind: "crunch", returned: "catch", tokens: 41000 },
        { worker: "survey", brief_one_line: "prior art", kind: "research",
          returned: "used", tokens: 12000 },
        { worker: "sweep", returned: "discarded" },
      ],
    },
  })]), "mechanism");
  assert.equal(f.shape, "structured");
  assert.equal(f.count, 3);
  assert.equal(f.basis, "last recorded run",
    "the basis is on screen on every card; a from-the-record tree that let "
    + "itself read as live would be worse than no tree");
  assert.deepEqual(f.workers.map((w) => w.outcome),
                   ["catch", "used", "discarded"]);
  assert.equal(f.workers[0].tokens, 41000);
  assert.equal(f.workers[2].brief, null, "a worker with no brief states none");
  assert.equal(f.workers[2].kind, null);
  assert.equal(f.workers[2].tokens, null, "absent tokens are null, never 0");
});

test("an unrecognised outcome is UNSTATED, not silently 'used'", () => {
  const f = seatFanout(src([run({
    meta: { fanout: [{ worker: "w", returned: "maybe" }] },
  })]), "mechanism");
  assert.equal(f.workers[0].outcome, "unstated");
  const g = seatFanout(src([run({
    meta: { fanout: [{ worker: "w" }] },
  })]), "mechanism");
  assert.equal(g.workers[0].outcome, "unstated");
});

test("the seat's own COUNT survives an unreadable entry", () => {
  /* A row with no worker name is dropped — a tree node with no label is a box.
   * But the number the seat reported firing must NOT shrink with it, or the
   * card would under-report the fan-out because of a bookkeeping defect. */
  const f = seatFanout(src([run({
    meta: { workers_fired: 3, fanout: [{ worker: "a" }, { brief_one_line: "x" }] },
  })]), "mechanism");
  assert.equal(f.workers.length, 1);
  assert.equal(f.count, 3);
  assert.match(f.note, /reports 3 workers and filed 1 readable entries/);
  assert.match(f.note, /not workers that did not run/);
});

test("a token figure given as a STRING is refused, not coerced", () => {
  const f = seatFanout(src([run({
    meta: { fanout: [{ worker: "w", tokens: "41000" }] },
  })]), "mechanism");
  assert.equal(f.workers[0].tokens, null,
    "a quoted figure is what a number lifted out of prose looks like; the "
    + "desk's own routing rules refuse it at the door for the same reason");
});

/* ------------------------------------------------------------ the prose -- */

test("PROSE IS NEVER PARSED INTO WORKERS — the whole point", () => {
  /* The one live example, verbatim from `run-ed-batch4`. */
  const real = "3 workers foreground, no falsifier fired, third measured "
    + "mid-run catch (the strongest: survivor-universe-as-PIT)";
  const f = seatFanout(src([run({
    meta: { workers_fired: 3, fanout: real },
  })]), "mechanism");
  assert.equal(f.shape, "prose");
  assert.deepEqual(f.workers, [],
    "a sentence mentioning three workers is not three workers; inventing "
    + "nodes from English is the defect this reader exists to avoid");
  assert.equal(f.prose, real, "shown verbatim");
  assert.equal(f.count, 3, "the count comes from `workers_fired`, which IS a number");
  assert.match(f.note, /NOT broken into workers/);
  assert.match(f.note, /the shape below is the sentence, not a tree/);
});

test("a blank prose string is not prose", () => {
  const f = seatFanout(src([run({ meta: { fanout: "   " } })]), "mechanism");
  assert.equal(f.shape, "none");
});

/* ---------------------------------------------------------- the absences -- */

test("five shapes, and none of them is another", () => {
  const shape = (meta: unknown) =>
    seatFanout(src([run({ meta })]), "mechanism").shape;
  assert.equal(shape({ fanout: [{ worker: "a" }] }), "structured");
  assert.equal(shape({ fanout: "some prose" }), "prose");
  assert.equal(shape({ workers_fired: 2 }), "count");
  assert.equal(shape({}), "none");
  assert.equal(seatFanout(src([]), "mechanism").shape, "no_run");
  assert.equal(seatFanout({ kind: "record", desk: null }, "mechanism").shape,
               "no_run");
});

test("no run in the window says WINDOW, not 'never fanned out'", () => {
  const f = seatFanout(src([run({ seat: "pm" })]), "mechanism");
  assert.equal(f.shape, "no_run");
  assert.match(f.note, /capped/);
  assert.match(f.note, /not a claim that the seat has never fanned out/);
  assert.equal(f.count, null, "absent is never zero");
});

test("an unreadable desk is UNKNOWN, not an empty fan-out", () => {
  const f = seatFanout({ kind: "record", desk: null }, "mechanism");
  assert.match(f.note, /UNKNOWN — not none/);
  assert.equal(f.count, null);
});

test("a run that filed nothing says the two cases are indistinguishable", () => {
  const f = seatFanout(src([run({ meta: {} })]), "mechanism");
  assert.equal(f.shape, "none");
  assert.match(f.note, /ran alone and a seat that fanned out without recording/);
  assert.equal(f.runId, "run-x", "the run is still named, so it can be checked");
});

test("an empty fanout ARRAY is a defect in the record, not a lone run", () => {
  const f = seatFanout(src([run({ meta: { fanout: [] } })]), "mechanism");
  assert.equal(f.shape, "none");
  assert.match(f.note, /defect in the record, not a run with no workers/);
});

/* --------------------------------------------------------- run selection -- */

test("the MOST RECENT run wins, by resolved_at and not by payload order", () => {
  const f = seatFanout(src([
    run({ run_id: "old", resolved_at: "2026-08-01T00:00:00+00:00",
          meta: { workers_fired: 9 } }),
    run({ run_id: "new", resolved_at: "2026-08-23T00:00:00+00:00",
          meta: { workers_fired: 2 } }),
  ]), "mechanism");
  assert.equal(f.runId, "new");
  assert.equal(f.count, 2);
});

test("another seat's run is never this seat's fan-out", () => {
  const f = seatFanout(src([
    run({ run_id: "theirs", seat: "builder", meta: { workers_fired: 7 } }),
    run({ run_id: "mine", seat: "mechanism", meta: { workers_fired: 1 } }),
  ]), "mechanism");
  assert.equal(f.runId, "mine");
  assert.equal(f.count, 1);
});

test("seatsWithFanout keeps only the seats with something to draw", () => {
  const s = src([
    run({ run_id: "a", seat: "mechanism", meta: { fanout: [{ worker: "w" }] } }),
    run({ run_id: "b", seat: "pm", meta: { fanout: "prose" } }),
    run({ run_id: "c", seat: "quant", meta: { workers_fired: 2 } }),
    run({ run_id: "d", seat: "coo", meta: {} }),
  ]);
  assert.deepEqual(
    seatsWithFanout(s, ["mechanism", "pm", "quant", "coo", "cfo"])
      .map((f) => f.seat),
    ["mechanism", "pm", "quant"],
    "a column of 'no evidence' rows is not a feature");
});

/* -------------------------------------------------------------- parsing -- */

test("parseWorker drops what it cannot label and keeps what it can", () => {
  assert.equal(parseWorker(null), null);
  assert.equal(parseWorker("a string"), null);
  assert.equal(parseWorker([]), null);
  assert.equal(parseWorker({}), null, "no worker name, no node");
  assert.equal(parseWorker({ worker: "   " }), null);
  const w = parseWorker({ worker: " w ", brief: "b", returned: "USED" });
  assert.equal(w!.worker, "w");
  assert.equal(w!.brief, "b", "`brief` is accepted beside `brief_one_line`");
  assert.equal(w!.outcome, "used", "the outcome vocabulary is case-insensitive");
});
