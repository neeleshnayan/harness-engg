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
  orderItems,
  rankDeskItems,
  recItems,
  splitDeskItems,
  stageOfItem,
  type DeskItem,
} from "./execDesk.ts";

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

test("compareDeskItems still prefers larger money, then harder-to-undo", () => {
  const a: DeskItem = {
    key: "a", kind: "recommendation", moneyUsd: 100,
    reversibility: "reversible", waitingSince: null,
  };
  const b: DeskItem = {
    key: "b", kind: "recommendation", moneyUsd: 10,
    reversibility: "irreversible", waitingSince: null,
  };
  assert.ok(compareDeskItems(a, b) < 0, "money leads the sort");
});
