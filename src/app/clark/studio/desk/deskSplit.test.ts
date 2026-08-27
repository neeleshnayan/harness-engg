/**
 * The desk's two queues, and the money key that ranks them.
 *
 * CDO D4 — `/fund/desk` returns `open`, `accepted` AND `staged` recommendations
 * under ONE key (`open_recommendations`), so "awaiting your decision" counted
 * decisions the CEO had already made. A desk where everything had been decided
 * and nothing staged displayed the same headline number as a desk where nothing
 * had been decided at all. Those are opposite situations.
 *
 * Builder dispatch 3 measured the other half: 47 of 47 open recommendations
 * carried no dollar figure, so the "rank by money" queue ranked by arrival
 * order on 98% of its rows.
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";

import {
  compareDeskItems,
  moneyGap,
  rankCoverage,
  rankReason,
  reversibilityOf,
  orderItems,
  rankDeskItems,
  recItems,
  splitDeskItems,
  stageOfItem,
  deskItemFacts,
  type DeskItem,
} from "./execDesk.ts";
import { hoursBetween } from "./cardAnatomy.ts";
import { cardGlyph } from "./cardGeometry.ts";

/* ------------------------------------------------------------- fixtures -- */

type RecStatus = "open" | "accepted" | "rejected" | "staged" | "done";

const rec = (
  recId: number,
  status: RecStatus,
  extra: Record<string, unknown> = {},
) =>
  ({
    rec_id: recId,
    seat: "validator",
    status,
    text: `recommendation ${recId}`,
    kind: "fix",
    run_id: "run-1",
    task: "an audit",
    ...extra,
  }) as never;

const run = (runId: string, resolvedAt: string | null) =>
  ({ run_id: runId, seat: "validator", task: "t", resolved_at: resolvedAt }) as never;

/* ---------------------------------------------------------------- D4 ----- */

test("an open recommendation awaits a decision; accepted and staged do not", () => {
  const items = recItems(
    [rec(1, "open"), rec(2, "accepted"), rec(3, "staged")],
    [run("run-1", "2026-08-20T10:00:00Z")],
  );
  assert.equal(stageOfItem(items[0]), "awaiting_decision");
  assert.equal(stageOfItem(items[1]), "awaiting_execution");
  assert.equal(stageOfItem(items[2]), "awaiting_execution");
});

test("a pending ORDER always awaits a decision — it is the decision", () => {
  const items = orderItems([
    { order_id: "o1", symbol: "SPY", side: "sell", qty: 1, ts: "2026-08-20T09:00:00Z" } as never,
  ]);
  assert.equal(stageOfItem(items[0]), "awaiting_decision");
});

test("the headline counts ONLY what awaits a decision", () => {
  // The measured shape: everything decided, nothing staged. The old count said
  // three; the honest count is zero.
  const items = recItems(
    [rec(1, "accepted"), rec(2, "accepted"), rec(3, "staged")],
    [run("run-1", "2026-08-20T10:00:00Z")],
  );
  const split = splitDeskItems(items);
  assert.equal(split.awaitingDecision.length, 0);
  assert.equal(split.awaitingExecution.length, 3);
});

test("the split loses nothing and preserves rank within each queue", () => {
  const items = rankDeskItems([
    ...orderItems([
      { order_id: "o1", symbol: "SPY", side: "sell", qty: 1,
        impact_preview: { notional_usd: 500 }, ts: "2026-08-20T09:00:00Z" } as never,
      { order_id: "o2", symbol: "GLD", side: "buy", qty: 1,
        impact_preview: { notional_usd: 900 }, ts: "2026-08-20T08:00:00Z" } as never,
    ]),
    ...recItems([rec(1, "open"), rec(2, "accepted")], [run("run-1", null)]),
  ]);
  const split = splitDeskItems(items);
  assert.equal(
    split.awaitingDecision.length + split.awaitingExecution.length,
    items.length,
    "the split dropped an item",
  );
  // Orders lead by money, largest first — order preserved inside the queue.
  assert.deepEqual(
    split.awaitingDecision.map((i) => i.key),
    ["order:o2", "order:o1", "rec:run-1:1"],
  );
});

test("an unrecognised status is treated as awaiting a decision, not as done", () => {
  // Fail-closed: a status this UI does not know about must land in the queue
  // somebody looks at, never in the one they scroll past.
  const items = recItems([rec(1, "something_new" as RecStatus)], []);
  assert.equal(stageOfItem(items[0]), "awaiting_decision");
});

/* ---------------------------------------------------------------- B2 ----- */

test("money_at_stake is carried onto the ranked item when the seat stated it", () => {
  const items = recItems([rec(1, "open", { money_at_stake: 376.84 })], []);
  assert.equal(items[0].moneyUsd, 376.84);
});

test("an absent money_at_stake stays null and ranks LAST, never as zero", () => {
  const items = recItems(
    [rec(1, "open"), rec(2, "open", { money_at_stake: 10 })],
    [],
  );
  assert.equal(items[0].moneyUsd, null);
  const ranked = rankDeskItems(items);
  assert.equal(ranked[0].moneyUsd, 10, "a priced item must outrank an unpriced one");
  assert.equal(ranked[1].moneyUsd, null);
});

test("a stated ZERO outranks an absent figure — saying nothing is not saying zero", () => {
  const items = recItems(
    [rec(1, "open"), rec(2, "open", { money_at_stake: 0 })],
    [],
  );
  const ranked = rankDeskItems(items);
  assert.equal(ranked[0].moneyUsd, 0);
  assert.equal(ranked[1].moneyUsd, null);
});

test("junk in money_at_stake is null, never a number the seat did not state", () => {
  for (const junk of ["about $400", NaN, Infinity, null, undefined, {}]) {
    const items = recItems([rec(1, "open", { money_at_stake: junk })], []);
    assert.equal(items[0].moneyUsd, null, `${String(junk)} became a number`);
  }
});

test("moneyGap counts the rows the ranking could not price", () => {
  const items = recItems(
    [rec(1, "open"), rec(2, "open"), rec(3, "open", { money_at_stake: 5 })],
    [],
  );
  assert.deepEqual(moneyGap(items), { priced: 1, unpriced: 2 });
});

test("REVERSIBILITY leads the sort, and money is the tie-break inside it", () => {
  /* THE RANKING WAS REORDERED 2026-08-22 AND THIS TEST WAS INVERTED WITH IT.
   * Recorded loudly, because a test rewritten to match the change it was
   * supposed to catch is how a rule gets quietly replaced.
   *
   * WHAT CHANGED: money used to lead. The CEO's complaint was that his desk is
   * "out of order ... Making my flow messy", and the COO's stated rule — which
   * the chair adopted as house rule — is reversibility first: *"a versioned
   * envelope change can be reversed in an afternoon; an unintended short
   * position at a real venue cannot."* Money ranks by how much is moving; it
   * does not rank by how much of it you can get back, and the second is what
   * decides which row the CEO should read first.
   *
   * THIS IS A DESK ORDERING, NOT A CONTROL: it moves no threshold, gates
   * nothing, and changes no number the fund acts on automatically. It changes
   * which row is at the top of a human's list. */
  const bigButRevertible: DeskItem = {
    key: "a", kind: "recommendation", moneyUsd: 100,
    reversibility: "reversible", waitingSince: null, dueDate: null,
  };
  const smallAndFinal: DeskItem = {
    key: "b", kind: "recommendation", moneyUsd: 10,
    reversibility: "irreversible", waitingSince: null, dueDate: null,
  };
  assert.ok(compareDeskItems(smallAndFinal, bigButRevertible) < 0,
    "the irreversible $10 must lead the revertible $100");

  // Inside ONE band, money still decides — it was demoted, not dropped.
  const cheap: DeskItem = { ...bigButRevertible, key: "c", moneyUsd: 5 };
  assert.ok(compareDeskItems(bigButRevertible, cheap) < 0,
    "within a band, the larger figure still leads");
});

test("a dated commitment outranks everything, soonest first", () => {
  /* The top key. A deadline is the one thing on this page that does not wait
   * for a click — and the fund has exactly one live example, whose date is in
   * its PROSE. The field exists, the key is wired, and nothing writes it: see
   * `rankCoverage().dated`, which the page prints rather than implying zero. */
  const dated: DeskItem = {
    key: "d", kind: "recommendation", moneyUsd: 0,
    reversibility: "reversible", waitingSince: null, dueDate: "2026-09-08",
  };
  const sooner: DeskItem = { ...dated, key: "s", dueDate: "2026-09-01" };
  const undatedIrreversible: DeskItem = {
    key: "u", kind: "order", moneyUsd: 1e6,
    reversibility: "irreversible", waitingSince: null, dueDate: null,
  };
  const ranked = rankDeskItems([undatedIrreversible, dated, sooner]);
  assert.deepEqual(ranked.map((i) => i.key), ["s", "d", "u"]);
});

test("every row can say WHY it is where it is, in words", () => {
  /* The instruction was explicit: do not invent a scoring formula and bury it.
   * There is no score — four named keys and a sentence per row. */
  const unpriced: DeskItem = {
    key: "a", kind: "recommendation", moneyUsd: null,
    reversibility: "hard", waitingSince: "2026-08-01T00:00:00Z", dueDate: null,
  };
  const r = rankReason(unpriced);
  assert.match(r, /changes what the machine does without asking again/);
  // An unpriced row must not read as a cheap one.
  assert.match(r, /no dollar figure stated/);
  assert.match(r, /2026-08-01/);

  // A stated zero says nothing moves — it does not say "unimportant".
  assert.match(rankReason({ ...unpriced, moneyUsd: 0 }), /\$0 moves/);
  assert.match(rankReason({ ...unpriced, moneyUsd: 750.36 }), /\$750\.36 at stake/);
  // An unclassified kind says so, and rides with the urgent half.
  assert.match(
    rankReason({ ...unpriced, reversibility: "unclassified" }),
    /unclassified kind/);
  // A dated row leads with its date.
  assert.match(rankReason({ ...unpriced, dueDate: "2026-09-08" }),
    /^due 2026-09-08/);
});

/* --------------------------------------- rankReason's omissions (D42) ----- */

const dated: DeskItem = {
  key: "a", kind: "recommendation", moneyUsd: 630,
  reversibility: "reversible", waitingSince: "2026-08-24T00:00:00Z",
  dueDate: "2026-08-26",
};

test("D42: the DEFAULT is unchanged — every existing caller still gets the "
  + "date and the wait, and this assertion is what makes the option safe to "
  + "have added at all", () => {
  const r = rankReason(dated);
  assert.match(r, /^due 2026-08-26/);
  assert.match(r, /waiting since 2026-08-24/);
});

test("D42: a caller that renders the due chip and the rail's age drops both, "
  + "and KEEPS everything else — a card printed 'due 2026-08-26' in its chip "
  + "and again in this sentence, and 'filed · 3.2h' above 'waiting since "
  + "2026-08-24': the same two facts twice", () => {
  const r = rankReason(dated, { due: true, waiting: true });
  assert.doesNotMatch(r, /due 2026-08-26/);
  assert.doesNotMatch(r, /waiting since/);
  assert.match(r, /revertible by a commit/);
  assert.match(r, /\$630 at stake/);
});

test("D42: the two omissions are INDEPENDENT — a caller with a chip and no "
  + "rail must not silently lose the wait", () => {
  assert.doesNotMatch(rankReason(dated, { due: true }), /due 2026-08-26/);
  assert.match(rankReason(dated, { due: true }), /waiting since 2026-08-24/);
  assert.match(rankReason(dated, { waiting: true }), /^due 2026-08-26/);
  assert.doesNotMatch(rankReason(dated, { waiting: true }), /waiting since/);
});

test("D42: AN UNDATABLE WAIT STILL SPEAKS EVEN WHEN THE WAIT IS OMITTED. The "
  + "caller's rail can only speak from a timestamp, so it says nothing at all "
  + "in exactly the case where this sentence must — absence keeps a voice", () => {
  const r = rankReason({ ...dated, waitingSince: null },
                       { due: true, waiting: true });
  assert.match(r, /age unknown/);
});

test("D42: AND IT DOES NOT SAY 'undated' — that is this codebase's word for a "
  + "missing DATE, and the card carrying this line also carries a due chip. "
  + "The rendered desk showed 'due 2026-08-24' two inches above a line ending "
  + "'· undated'", () => {
  for (const omit of [{}, { due: true, waiting: true }]) {
    assert.doesNotMatch(rankReason({ ...dated, waitingSince: null }, omit),
      /undated/, `omit=${JSON.stringify(omit)}`);
  }
  // The DATED case is untouched and still names the day it started waiting.
  assert.match(rankReason(dated), /waiting since 2026-08-24/);
});

test("a seat's STATED reversibility beats the kind table", () => {
  /* The kind table's weak spot is the CEO's own queue: `awaits-ceo`, `batch`
   * and `challenge` are routing words that say nothing about the act, so every
   * row of his rendered the amber "unclassified kind" sentence. A warning on
   * every row is a warning nobody reads. A seat knows whether its own
   * recommendation can be taken back; when it says so, that wins. */
  assert.equal(reversibilityOf("hard", "awaits-ceo"), "hard");
  assert.equal(reversibilityOf("IRREVERSIBLE ", "fix"), "irreversible",
    "case and whitespace are not a different answer");
  // Unstated falls back to the table, and an UNRECOGNISED value falls back too
  // rather than becoming a fourth class nobody can rank.
  assert.equal(reversibilityOf(null, "fix"), "reversible");
  assert.equal(reversibilityOf("very hard", "fix"), "reversible");
  assert.equal(reversibilityOf(null, "awaits-ceo"), "unclassified");
  // And `unclassified` cannot be DECLARED — it is what we say when nobody did.
  assert.equal(reversibilityOf("unclassified", "fix"), "reversible");

  const items = recItems(
    [rec(1, "open", { kind: "awaits-ceo", reversibility: "hard" })], []);
  assert.equal(items[0].reversibility, "hard");
});

test("rankCoverage states what the ranking could not see", () => {
  const items: DeskItem[] = [
    { key: "a", kind: "recommendation", moneyUsd: null,
      reversibility: "unclassified", waitingSince: null, dueDate: null },
    { key: "b", kind: "recommendation", moneyUsd: 0,
      reversibility: "reversible", waitingSince: null, dueDate: null },
    { key: "c", kind: "order", moneyUsd: 12,
      reversibility: "irreversible", waitingSince: null, dueDate: "2026-09-08" },
  ];
  assert.deepEqual(rankCoverage(items), {
    total: 3, priced: 2, unpriced: 1, zero: 1,
    dated: 1, undated: 2, unclassified: 1,
  });
});

/* -------------------- the staleness anchor, and the cap that used to bind -- */

test("waitingSince comes from the ROW, not from the capped runs window", () => {
  /* M45 SURVIVED the first mutation pass — reverting this to the runs-map
   * lookup broke nothing, because nothing tested it.
   *
   * THE MEASUREMENT that put it here: the live desk carries 324 open
   * recommendations and a 25-run `runs` payload. The map could date 66 of
   * them; the ROWS carry `resolved_at` themselves and can date all 324. On
   * the CEO's own decision list the map dated 7 of 39, so thirty-two cards
   * he is asked to rank by urgency drew their age spine as UNKNOWN.
   *
   * The two AGREE where both exist (66 of 66, zero disagreements), which is
   * what makes this a wider read of one fact rather than a switch to a second
   * one — and it is why the fallback below is still correct. */
  const outsideWindow = recItems(
    [rec(1, "open", { resolved_at: "2026-08-20T10:00:00Z" })],
    [/* the runs payload does NOT contain run-1 */ run("run-99", "2026-08-01T00:00:00Z")],
  );
  assert.equal(outsideWindow[0].waitingSince, "2026-08-20T10:00:00Z",
    "a row whose run fell outside the 25-run window must still be dated");

  // The MAP is still the fallback for a spine that predates the annotation.
  const noRowField = recItems(
    [rec(2, "open")],
    [run("run-1", "2026-08-19T09:00:00Z")],
  );
  assert.equal(noRowField[0].waitingSince, "2026-08-19T09:00:00Z");

  // ...and neither source datable is `null`, never a substituted "now".
  const neither = recItems([rec(3, "open")], []);
  assert.equal(neither[0].waitingSince, null);

  // A blank string on the row is not a date and falls through to the map.
  const blank = recItems(
    [rec(4, "open", { resolved_at: "   " })],
    [run("run-1", "2026-08-18T09:00:00Z")],
  );
  assert.equal(blank[0].waitingSince, "2026-08-18T09:00:00Z");
});

test("an ORDER's card facts carry a kind, so it never wears the unknown mark", () => {
  /* M46 SURVIVED. A pending order has no `kind` in the record — the field
   * belongs to recommendations — so `deskItemFacts` supplies `"order"`
   * knowingly. Without it the only IRREVERSIBLE row on the CEO's desk draws
   * the "kind not recognised" glyph, which is the one row where an honest
   * blank is the wrong answer: the item type IS the answer here. */
  const [o] = orderItems([{
    order_id: "o-1", side: "buy", qty: 1, symbol: "SPY",
    ts: "2026-08-27T10:00:00Z", rationale: "because",
    impact_preview: { notional_usd: 100 },
  } as never]);
  const facts = deskItemFacts(o, "2026-08-27T12:00:00Z");
  assert.equal(facts.kind, "order");
  assert.equal(cardGlyph(facts).family, "position");
  assert.equal(cardGlyph(facts).basis, "matched");
  // The age is the ORDER's own clock, from `ts`.
  assert.equal(facts.ageHours, 2);

  // A recommendation still reads its own kind.
  const [r] = recItems([rec(9, "open", { kind: "harness_defect" })],
                       [run("run-1", "2026-08-27T10:00:00Z")]);
  assert.equal(deskItemFacts(r, "2026-08-27T12:00:00Z").kind, "harness_defect");
});

test("hoursBetween refuses a future stamp rather than reporting a negative age", () => {
  // Two clocks disagreeing is not an age. `null` is the honest answer and it
  // is the same answer an unreadable stamp gets: we cannot say how long.
  assert.equal(hoursBetween("2026-08-27T14:00:00Z", "2026-08-27T12:00:00Z"), null);
  assert.equal(hoursBetween("not-a-time", "2026-08-27T12:00:00Z"), null);
  assert.equal(hoursBetween(null, "2026-08-27T12:00:00Z"), null);
  assert.equal(hoursBetween("2026-08-27T10:00:00Z", "2026-08-27T12:00:00Z"), 2);
});
