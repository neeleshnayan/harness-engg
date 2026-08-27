import test from "node:test";
import assert from "node:assert/strict";

import { CODENAMES, isPlain, jargonIn, meaning } from "./plainEnglish.ts";
import { briefingChips, briefingOf, briefingRows } from "./briefing.ts";
import { benchFlight, seatLamps } from "./seatActivity.ts";
import { consoleQueue } from "./consoleQueue.ts";
import type { DeskRec, DeskRun } from "./seatLib.ts";
import type { DeskView } from "@/lib/fund_api";

/**
 * PLAIN ENGLISH IN FRONT OF THE CEO — the direction, given a test.
 *
 * CEO instruction 2026-08-27, verbatim: *"plain english should be a direction
 * for all teams writing memo's for CEO"*. A style direction with no test decays
 * at the first hurry and nothing goes red.
 *
 * TWO HALVES, and the second is the one that matters:
 *
 *  1. the checker does what it claims (positive AND negative controls — a
 *     checker that finds nothing everywhere is a checker with no domain);
 *  2. EVERY CEO-FACING SENTENCE THIS SLICE EMITS is swept through it, across
 *     the arms where the sentences differ. A sweep that only ran the happy
 *     path would miss exactly the sentences written under pressure: the
 *     unreadable ones, the aborted ones, the disagreement ones.
 *
 * DOMAIN, stated because a zero from a checker needs one before it needs
 * belief: the assertions below compare a COUNTED number of strings, printed
 * by the final test in this file. This makes no claim about the studio's
 * hundreds of pre-existing strings — a checker that went red on ninety files
 * nobody is editing gets switched off, and a switched-off check is worse than
 * none.
 */

/* ------------------------------------------------ the checker has a domain */

test("the checker CATCHES what it claims to catch", () => {
  assert.deepEqual(jargonIn("see app/fund/desk.py for the fold").map((f) => f.kind),
    ["path", "codename"]);
  assert.equal(jargonIn("the open_dispatches list")[0].kind, "identifier");
  assert.equal(jargonIn("call seatLamps for this")[0].kind, "identifier");
  assert.equal(jargonIn("run briefingOf(run) first")[0].kind, "call");
  assert.equal(jargonIn("the `verdict` field")[0].kind, "code_quote");
  assert.equal(jargonIn("the spine could not be read")[0].kind, "codename");
  assert.equal(jargonIn("SEAT_PAGES_DESIGN.md is the brief")[0].kind, "path");
});

test("the checker PASSES ordinary English — it is not a word filter", () => {
  for (const ok of [
    "This seat has nothing running.",
    "Two builders are going at once; the older one has not come back.",
    "We could not read what the validator is doing, so this is at least two.",
    "A quarter of marks arrive late (34 of 134).",
    "Nothing here is waiting on you.",
  ]) {
    assert.deepEqual(jargonIn(ok), [], ok);
  }
});

test("a path is reported ONCE, as a path, not twice under two names", () => {
  const f = jargonIn("open desk.py");
  assert.equal(f.length, 1);
  assert.equal(f[0].kind, "path");
});

test("a codename inside a longer word does not fire", () => {
  assert.deepEqual(jargonIn("inactivity is not a problem here"), []);
  assert.equal(CODENAMES.includes("activity"), true);
  assert.equal(isPlain("the activity was recorded"), false);
});

test("meaning() puts the words first and the digits in brackets", () => {
  assert.equal(meaning("a quarter of marks arrive late", "34 of 134"),
    "a quarter of marks arrive late (34 of 134)");
  // A bracket that only echoes the sentence is chrome, so it is dropped.
  assert.equal(meaning("nothing is waiting on you"), "nothing is waiting on you");
  assert.equal(meaning("nothing is waiting on you", "  "),
    "nothing is waiting on you");
});

/* ------------------------------------------- the sweep over what we render */

const RUN = (over: Record<string, unknown> = {}): DeskRun => ({
  run_id: "run-builder-mach1", seat: "builder", task: "MACH1", model: null,
  tokens: 540438, tool_uses: 236, dispatched_at: "2026-08-27T05:52:00+00:00",
  resolved_at: "2026-08-27T07:21:44+00:00", artifact_path: null,
  verdict: "both kills closed", reasoning: "why", trace_id: null,
  status: "delivered", recommendations: [], ...over,
}) as unknown as DeskRun;

const REC = (over: Record<string, unknown> = {}) => ({
  kind: "dispatch", rec_id: 1, status: "open", text: "do the thing",
  next_actor: "chair", money_at_stake: null, due_date: null, ...over,
}) as unknown as Partial<DeskRec>;

const ACT = (over: Record<string, unknown> = {}) => ({
  status: "working", task: "slice3", since: "2026-08-27T07:32:39+00:00",
  task_id: "t1", returned_run_id: null, review_detectable: true,
  open_dispatches: [{
    status: "working", task: "slice3", since: "2026-08-27T07:32:39+00:00",
    task_id: "t1", returned_run_id: null, review_detectable: true,
  }],
  working_count: 1, awaiting_review_count: 0, last_delivered: null, ...over,
}) as unknown as DeskView["roster"][number]["activity"];

const REQ = (over: Record<string, unknown> = {}) => ({
  request_id: "910c480a-e742-42e2-a8d0-4ba6d31bf475", kind: "audit",
  serves: "builder", subject: "Rebuild the console", status: "approved",
  at: "2026-08-27T06:18:24+00:00", dispatched: false, ...over,
}) as unknown as DeskView["requests"][number];

/** Every CEO-facing string produced by an arm, collected so the sweep can
 *  count its domain rather than assert a zero over nothing. */
function ceoFacingStrings(): string[] {
  const out: string[] = [];
  const add = (s: string | null | undefined) => { if (s) out.push(s); };

  // --- the briefing card, across the arms where its sentences differ ---
  for (const run of [
    RUN(), RUN({ verdict: null }), RUN({ status: "aborted" }),
    RUN({ status: "aborted", verdict: null }), RUN({ status: "weird" }),
    RUN({ recommendations: [REC(), REC({ rec_id: 2, next_actor: "ceo" })] }),
    RUN({ recommendations: [REC({ money_at_stake: 501 }), REC({ rec_id: 2 })] }),
    RUN({ recommendations: [REC({ money_at_stake: 12 })] }),
    RUN({ tokens: null, tool_uses: null, resolved_at: null }),
  ]) {
    const b = briefingOf(run);
    add(b.headlineNote); add(b.rowsNote);
    for (const c of b.chips) { add(c.label); add(c.sub); }
  }
  // The chip builder reached directly, so an arm the runs above do not hit
  // (every ask priced) is still swept.
  for (const c of briefingChips(briefingRows([REC({ money_at_stake: 1 })]), RUN()))
  { add(c.label); add(c.sub); }

  // --- the room's lamps, across all three bases and the disagreement ---
  const rows = [
    seatLamps("builder", ACT()),
    seatLamps("quant", ACT({ open_dispatches: [], working_count: 0, awaiting_review_count: 0, status: "idle" })),
    seatLamps("cfo", null),
    seatLamps("pm", { status: "working", task: "x", since: null, last_delivered: null } as never),
    seatLamps("coo", ACT({ status: "idle", task: null, since: null })),
    seatLamps("adversary", ACT({ open_dispatches: [{ status: "nonsense" }, null], working_count: 0 })),
  ];
  for (const r of rows) add(r.note);
  add(benchFlight(rows).note);
  add(benchFlight([rows[0]]).note);
  add(benchFlight([rows[0], rows[3]]).note);
  add(benchFlight([]).note);

  // --- the console rows ---
  for (const q of [
    consoleQueue([REQ()], []),
    consoleQueue([], []),
    consoleQueue(null, null),
    consoleQueue([REQ({ at: null })], []),
    consoleQueue(Array.from({ length: 30 }, (_, i) =>
      REQ({ request_id: `r${i}` })), []),
  ]) {
    add(q.note); add(q.tailNote);
    // `verbObject` is deliberately NOT swept: it is the record's own words,
    // passed through. Sweeping pass-through content would test the fixture,
    // not the code, and would imply we rewrite what a seat filed. The
    // direction governs the words WE write around it — which is everything
    // else in this list.
    for (const row of q.rows) add(row.ageLabel);
  }
  return out;
}

test("EVERY CEO-facing sentence this slice renders is plain English", () => {
  const strings = ceoFacingStrings();
  const bad = strings
    .map((s) => ({ s, findings: jargonIn(s) }))
    .filter((r) => r.findings.length > 0);
  assert.deepEqual(
    bad.map((b) => `${b.s}  <<${b.findings.map((f) => f.found).join(", ")}>>`),
    [],
  );
});

test("the sweep has a DOMAIN — it compared a stated number of strings", () => {
  const strings = ceoFacingStrings();
  // A zero from a checker needs its domain before it needs belief. This
  // number is the count the sweep above actually inspected; if a later edit
  // silently stops producing sentences, this goes red rather than passing
  // vacuously over an empty list.
  assert.ok(strings.length >= 60,
    `the sweep inspected only ${strings.length} strings — it has lost its domain`);
  assert.equal(new Set(strings).size >= 20, true,
    "the sweep is inspecting the same handful of sentences repeatedly");
});
