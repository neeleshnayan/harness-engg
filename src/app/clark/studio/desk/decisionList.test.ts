/**
 * The decision list — the first screenful, and the number on it.
 *
 * THE MEASUREMENT THIS IS BUILT FROM (2026-08-22, live corpus replayed through
 * the merged spine's own code): the CEO's page said "3 awaiting your decision"
 * and put the first Accept button 11,608px — 14.7 screenfuls — below his name,
 * behind 49,549 characters. The largest block on the page was Fable's queue of
 * 23 asks, headed "0 awaiting you", of which ZERO awaited him.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/decisionList.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import {
  orderItems, rankDeskItems, recItems, splitDeskItems, type QueuedAsk,
} from "./execDesk.ts";
import { officerDesk } from "./officerQueues.ts";
import { countCheck, decisionList, foldedCounts } from "./decisionList.ts";
import { memoParts } from "../memo.ts";

const rec = (o: Record<string, unknown>) =>
  ({ run_id: "r1", rec_id: 1, seat: "pm", kind: "process", status: "open",
     text: "A decision. With a second sentence that is not the headline.",
     task: "task", artifact_path: null, trace_id: null,
     next_actor_resolved: "ceo", ...o }) as never;

const run = (o: Record<string, unknown> = {}) =>
  ({ run_id: "r1", seat: "pm", task: "the run's task", verdict: null,
     resolved_at: "2026-08-21T10:00:00+00:00", ...o }) as never;

const ask = (o: Partial<QueuedAsk> = {}): QueuedAsk => ({
  requestId: "q1", actor: "mechanism", seatFiled: true, serves: "validator",
  subject: "attack the thing", note: null, at: "2026-08-21T09:00:00+00:00",
  stage: "awaiting_ceo", approvedBy: null, approvedAt: null,
  declinedBy: null, declinedAt: null, declineReason: null, ...o,
});

/** Build the whole pipeline the page builds, from raw rows. */
function build(rows: unknown[], runs: unknown[], asks: QueuedAsk[],
               pending: unknown[] = []) {
  const ranked = rankDeskItems([
    ...orderItems(pending as never),
    ...recItems(rows as never, runs as never),
  ]);
  const split = splitDeskItems(ranked);
  const desk = officerDesk({
    awaitingDecision: split.awaitingDecision,
    awaitingExecution: split.awaitingExecution,
    ownedElsewhere: split.ownedElsewhere,
    memos: [], asks,
  });
  return { desk, list: decisionList(desk, asks, runs as never, memoParts) };
}

/* ------------------------------------------------------- THE INVARIANT ---- */

test("the card count IS the header number — always, including the awkward cases", () => {
  /* THE WHOLE POINT OF THE RESTRUCTURE: "the first screenful is exactly N
   * cards, where N is the header number, and nothing above them". If those two
   * numbers can differ, the restructure is a lie told in layout — and this desk
   * has already shipped one-number-computed-twice twice (11 vs 6, then 1 vs 0).
   *
   * Every case here is one where a naive "count the open rows" would get a
   * DIFFERENT answer from the officer desk. */
  const cases: { name: string; rows: unknown[]; asks: QueuedAsk[];
                 pending: unknown[] }[] = [
    { name: "nothing at all", rows: [], asks: [], pending: [] },
    { name: "plain open rows", asks: [], pending: [],
      rows: [rec({ rec_id: 1 }), rec({ rec_id: 2 })] },
    { name: "a Donna NOTE, counted by neither", asks: [], pending: [],
      rows: [rec({ rec_id: 1 }),
             rec({ rec_id: 2, seat: "secretary", kind: "record_keeping" })] },
    { name: "a Donna SUGGESTION, counted by both", asks: [], pending: [],
      rows: [rec({ rec_id: 2, seat: "secretary", kind: "suggestion" })] },
    { name: "rows routed away from the CEO", asks: [], pending: [],
      rows: [rec({ rec_id: 1 }),
             rec({ rec_id: 2, next_actor_resolved: "chair" }),
             rec({ rec_id: 3, next_actor_resolved: "seat" })] },
    { name: "a decided row the CEO still owns — the D9 kill", asks: [],
      pending: [],
      rows: [rec({ rec_id: 1, status: "accepted",
                   next_actor_resolved: "ceo" })] },
    { name: "terminal rows, dropped entirely", asks: [], pending: [],
      rows: [rec({ rec_id: 1 }), rec({ rec_id: 2, status: "done" }),
             rec({ rec_id: 3, status: "noted" })] },
    { name: "asks in all four states", pending: [],
      rows: [rec({ rec_id: 1 })],
      asks: [ask({ requestId: "a" }),
             ask({ requestId: "b", stage: "cleared_to_trigger" }),
             ask({ requestId: "c", stage: "declined" }),
             ask({ requestId: "d" })] },
    { name: "pending orders", asks: [], rows: [rec({ rec_id: 1 })],
      pending: [{ order_id: "o1", ts: "2026-08-22T00:00:00Z",
                  impact_preview: { notional_usd: 750 } }] },
    { name: "everything at once", pending: [{ order_id: "o1" }],
      rows: [rec({ rec_id: 1 }),
             rec({ rec_id: 2, seat: "secretary", kind: "org_observation" }),
             rec({ rec_id: 3, next_actor_resolved: "chair" }),
             rec({ rec_id: 4, status: "accepted",
                   next_actor_resolved: "ceo" }),
             rec({ rec_id: 5, status: "rejected" })],
      asks: [ask({ requestId: "a" }),
             ask({ requestId: "b", stage: "declined" })] },
  ];

  for (const c of cases) {
    const { desk, list } = build(c.rows, [run()], c.asks, c.pending);
    assert.equal(list.total, desk.awaitingTotal,
      `${c.name}: the list shows ${list.total} cards under a header saying `
      + `${desk.awaitingTotal}`);
    assert.equal(list.all.length, list.total, `${c.name}: total must be flat`);
    assert.equal(
      list.groups.reduce((n, g) => n + g.decisions.length, 0), list.total,
      `${c.name}: a decision must be in exactly one group`);
  }
});

test("nothing that is NOT awaiting him reaches the list", () => {
  /* The measured defect: 23 asks under a heading reading "0 awaiting you",
   * occupying 9,596px above every decision control. A cleared ask is the
   * chair's to fire and a declined one is terminal; neither is a card. */
  const { list } = build([rec({ rec_id: 1 })], [run()], [
    ask({ requestId: "cleared", stage: "cleared_to_trigger" }),
    ask({ requestId: "declined", stage: "declined" }),
  ]);
  assert.equal(list.total, 1);
  assert.ok(!list.all.some((d) => d.kind === "ask"),
    "no ask that is not awaiting the CEO may occupy a decision card");
});

test("a decided row and an elsewhere row are folded, not listed", () => {
  const { desk, list } = build([
    rec({ rec_id: 1 }),
    rec({ rec_id: 2, status: "accepted", next_actor_resolved: "chair" }),
    rec({ rec_id: 3, next_actor_resolved: "seat" }),
    rec({ rec_id: 4, seat: "secretary", kind: "record_keeping" }),
  ], [run()], [ask({ requestId: "c", stage: "cleared_to_trigger" })]);

  assert.equal(list.total, 1);
  const folded = foldedCounts(desk, [
    ask({ requestId: "c", stage: "cleared_to_trigger" })]);
  assert.equal(folded.decided, 1);
  assert.equal(folded.elsewhere, 1);
  assert.equal(folded.donna, 1);
  assert.equal(folded.settledAsks, 1);
  assert.equal(folded.total, 4,
    "everything taken off the first screenful must be countable behind a "
    + "named heading — disclosure is not concealment, and a section labelled "
    + "only 'more' is concealment with a chevron");
});

test("the folded PARTS sum to the folded TOTAL — one door per count", () => {
  /* THE DEFECT THIS PINS, found by looking at the rendered page: the header's
   * "N more on file" was computed here and the page then added Donna's daily
   * to her door label on its own, so the five doors summed to 134 under a
   * header saying 133. One quantity computed in two places, on the page whose
   * entire defect history is one quantity computed in two places.
   *
   * `donnaHasDaily` is a parameter for exactly this reason, and the sum is
   * asserted with the daily both present and absent. */
  for (const hasDaily of [false, true]) {
    const { desk } = build([
      rec({ rec_id: 1 }),
      rec({ rec_id: 2, status: "accepted", next_actor_resolved: "chair" }),
      rec({ rec_id: 3, next_actor_resolved: "seat" }),
      rec({ rec_id: 4, seat: "secretary", kind: "record_keeping" }),
    ], [run()], [ask({ requestId: "c", stage: "cleared_to_trigger" }),
                 ask({ requestId: "d", stage: "declined" })]);
    const f = foldedCounts(desk, [
      ask({ requestId: "c", stage: "cleared_to_trigger" }),
      ask({ requestId: "d", stage: "declined" })], hasDaily);
    assert.equal(
      f.decided + f.elsewhere + f.donna + f.memos + f.settledAsks, f.total,
      `hasDaily=${hasDaily}: the doors must sum to the header's "N more on file"`);
    assert.equal(f.donna, hasDaily ? 2 : 1,
      "her door counts what is BEHIND it — a door that understates its "
      + "contents teaches a reader not to open it");
  }
});

/* ----------------------------------------------------------- grouping ----- */

test("rows group under the memo that proposed them", () => {
  const { list } = build([
    rec({ rec_id: 1, run_id: "coo1", seat: "coo" }),
    rec({ rec_id: 2, run_id: "coo1", seat: "coo" }),
    rec({ rec_id: 3, run_id: "b1", seat: "builder" }),
  ], [
    run({ run_id: "coo1", seat: "coo",
          verdict: "31 ITEMS INTO 7 BATCHES. Then a lot more prose." }),
    run({ run_id: "b1", seat: "builder", task: "the D9 brief" }),
  ], []);

  assert.equal(list.groups.length, 2);
  const batch = list.groups.find((g) => g.runId === "coo1")!;
  assert.equal(batch.isBatch, true);
  assert.equal(batch.heading, "31 ITEMS INTO 7 BATCHES.",
    "a COO group is headed by its verdict's FIRST SENTENCE — the same "
    + "memoParts split the approval cards use, so the sentence is identical "
    + "on both surfaces");
  assert.equal(batch.decisions.length, 2);
  assert.equal(list.batches, 1);

  const other = list.groups.find((g) => g.runId === "b1")!;
  assert.equal(other.isBatch, false);
  assert.equal(other.heading, "the D9 brief",
    "a non-COO group is headed by what the seat was ASKED to do, never by a "
    + "conclusion invented for it");
});

test("a run the payload does not carry gets NO heading, not a guessed one", () => {
  /* `desk.runs` is capped at 25. A row from an older run is still a decision
   * and must still be a card; its heading is unknown and says so. Inventing
   * one from the row's own text would put a seat's prose where a memo's
   * conclusion belongs. */
  const { list } = build([rec({ rec_id: 1, run_id: "ancient" })], [], []);
  assert.equal(list.total, 1);
  assert.equal(list.groups[0].heading, null);
  assert.equal(list.groups[0].runId, "ancient");
});

test("grouping never demotes a better-ranked decision", () => {
  /* The hazard the officer routing was careful about, reintroduced by
   * grouping: an item's group says WHO is asking, not how urgent it is. A
   * $750 irreversible order behind a chore because the chore's group came
   * first would be the ranking silently overruled by layout. */
  const { list } = build([
    // reversible chore, from an early run
    rec({ rec_id: 1, run_id: "chore", kind: "process" }),
    // hard-to-undo, from a later run — must lead
    rec({ rec_id: 2, run_id: "urgent", kind: "exit_rule" }),
  ], [run({ run_id: "chore" }), run({ run_id: "urgent" })], []);
  assert.equal(list.groups[0].runId, "urgent",
    "the group holding the hardest-to-undo row must lead");
});

test("a dated row leads everything, including its own group", () => {
  const { list } = build([
    rec({ rec_id: 1, run_id: "a", kind: "exit_rule" }),
    rec({ rec_id: 2, run_id: "b", kind: "process", due_date: "2026-09-08" }),
  ], [run({ run_id: "a" }), run({ run_id: "b" })], []);
  assert.equal(list.all[0].kind, "rec");
  assert.equal(
    (list.all[0] as { item: { dueDate: string | null } }).item.dueDate,
    "2026-09-08",
    "the one key that does not wait for a click must lead the list");
});

test("orders are their own group and asks are LAST", () => {
  const { list } = build(
    [rec({ rec_id: 1 })], [run()], [ask({ requestId: "a" })],
    [{ order_id: "o1", impact_preview: { notional_usd: 750 } }]);
  assert.equal(list.groups[0].key, "orders",
    "an irreversible fill outranks everything; its group leads");
  assert.equal(list.groups[list.groups.length - 1].key, "asks",
    "an ask carries neither money nor a reversibility class, so it is placed "
    + "rather than ranked — and placed where that is visible");
  assert.equal(list.total, 3);
});

/* ------------------------------------------------- the runtime check ------ */

test("the count check catches the two numbers on one line disagreeing", () => {
  /* THE THIRD INSTANCE, caught before it shipped. The CEO's header renders the
   * page's count and the COO chip eight pixels right of it renders the
   * spine's; nothing compared them. They have disagreed twice — 11 vs 6, then
   * 1 vs 0 on an accepted row he still owned. This is the runtime half of the
   * shared contract: the tests pin what the tests exercise, this pins what he
   * is looking at, against whatever spine is actually running. */
  assert.equal(countCheck({ spineTotal: 3, pageTotal: 3, divertedNotes: 0 }),
    null, "agreement is silent");

  const drift = countCheck({ spineTotal: 7, pageTotal: 6, divertedNotes: 0 });
  assert.ok(drift, "a one-row disagreement must be reported");
  assert.match(drift!, /counts 6 .*says 7/);
  assert.match(drift!, /treat the LARGER/,
    "the safe direction on 'one of these is wrong about what you owe' is the "
    + "bigger number — failing toward 'he must look'");
});

test("the ONE known divergence is subtracted by measurement, not tolerated", () => {
  /* Donna's notes: counted by the spine, not by the page, page is right, the
   * fix is a loosening of a registered trigger and therefore a human's call.
   * Recorded in the contract's `known_divergences` and subtracted here — a
   * fuzzy tolerance would hide the next real one inside it. */
  assert.equal(countCheck({ spineTotal: 5, pageTotal: 3, divertedNotes: 2 }),
    null, "exactly the known divergence is not drift");
  assert.ok(countCheck({ spineTotal: 6, pageTotal: 3, divertedNotes: 2 }),
    "one MORE than the known divergence is drift and must be reported");
  assert.ok(countCheck({ spineTotal: 4, pageTotal: 3, divertedNotes: 2 }),
    "one FEWER is also drift — the subtraction is an equality, not a ceiling");
});

test("a spine that sent no total is quiet, not accusing", () => {
  /* Absent is not disagreement. Shouting about a missing field on every
   * 15-second poll trains the reader to ignore the one time it means
   * something; the footer carries the "unverified" sentence instead. */
  for (const v of [undefined, null]) {
    assert.equal(countCheck({ spineTotal: v, pageTotal: 3, divertedNotes: 0 }),
      null);
  }
});

test("the page renders the count check", () => {
  const src = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
  assert.ok(src.includes("countCheck({"),
    "the check must actually be called — an unwired control is the pattern "
    + "this firm names in its own doctrine");
  assert.ok(src.includes("{countDrift}"),
    "and its sentence must reach the screen");
  assert.ok(src.includes("divertedNotes: officers.donna.notes.length"),
    "the known divergence must be measured from the live routing, not "
    + "hardcoded — a constant here would go stale the day the spine is fixed");
});

/* ------------------------------------------------ the live corpus ---------- */

test("against the LIVE corpus: three cards, and they are the three", () => {
  /* The fixture is the live `/fund/desk` payload put through the MERGED
   * spine's own `_annotated` + `desk_load` (scripts/gen_desk_contract.py's
   * sibling, gen_desk_d10.py) — 110 recommendations, 43 requests. Generated
   * with the spine's code rather than hand-written, because a hand-written
   * fixture is the author's belief about the shape and the belief has been
   * wrong twice on this surface. */
  let fixture: {
    open_recommendations: unknown[]; runs: unknown[];
    desk_load: { total: number };
  };
  try {
    fixture = JSON.parse(readFileSync(
      new URL("./__fixtures__/desk_live_d10.json", import.meta.url), "utf8"));
  } catch {
    // The fixture is committed beside this test; if it is gone, say so rather
    // than skipping quietly. A skipped assertion reads exactly like a passing
    // one in a suite tail.
    throw new Error(
      "the live-corpus fixture is missing — this assertion is the only one "
      + "here that runs against real data, and losing it silently would leave "
      + "the module tested only against rows its author invented");
  }

  const { desk, list } = build(
    fixture.open_recommendations, fixture.runs, [], []);
  assert.equal(list.total, desk.awaitingTotal);
  assert.equal(list.total, fixture.desk_load.total,
    "the card count must equal the SPINE's own desk_load total on the real "
    + "corpus, not merely the client's recomputation of it");
  assert.equal(list.total, 3, "measured 2026-08-22: three real decisions");
  // And the folded remainder is the mass the restructure moves off screen.
  const folded = foldedCounts(desk, []);
  assert.equal(folded.decided, 103);
  assert.equal(folded.elsewhere, 4);
});
