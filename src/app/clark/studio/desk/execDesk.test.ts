/**
 * Tests for the executive desks' derivations.
 *
 * Run: node --experimental-strip-types --test src/app/clark/studio/desk/execDesk.test.ts
 *
 * Fixtures are shapes VERIFIED against the live spine on 2026-08-20 — the
 * pending SOFI sell with its impact preview, and request 5fc56190, the first
 * seat-filed ask the fund has produced. Three bugs this week came from reading
 * keys an endpoint never returned; these fixtures are the guard against a
 * fourth.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import type { DeskView, PendingOrder } from "../../../../lib/fund_api.ts";
import { memoParts } from "../memo.ts";
import type { DeskRun } from "./seatLib.ts";
import {
  compareDeskItems, cooMemos, decisionVelocity, isSeatFiled, moneyGap,
  asksForCeo, orderItems, queuedAsks, rankDeskItems, recItems,
  reversibilityOfKind,
} from "./execDesk.ts";

/* ------------------------------------------------------------- fixtures -- */

/** Verbatim from GET /api/v1/fund/orders/pending, 2026-08-20. */
const sofiSell: PendingOrder = {
  order_id: "20ab9a86-1830-48bb-b1f9-7d6ff089f54e",
  symbol: "SOFI",
  side: "sell",
  qty: 9.18819,
  strategy_id: "ca78408f-cf68-43d1-b5b9-6b467c4e7a98",
  thesis_id: null,
  rationale: "[pm · rec 2] T3 (re-staged fresh): Retire Mean Reversion - Cyclicals.",
  limit_price: null,
  impact_preview: {
    cash_after: 912.76, nav_before: 1878.6, cash_before: 743.51,
    quote_price: 18.42, notional_usd: 169.25,
  },
  ts: "2026-08-20T13:12:52.695919+00:00",
  age_minutes: 10.0,
};

const rec = (o: Partial<DeskView["open_recommendations"][number]>) =>
  o as DeskView["open_recommendations"][number];

const run = (o: Partial<DeskRun>) => o as DeskRun;

/* ------------------------------------------------------- reversibility --- */

test("reversibility is table-driven and fails towards urgent", () => {
  assert.equal(reversibilityOfKind("fix"), "reversible");
  assert.equal(reversibilityOfKind("retire"), "hard");
  assert.equal(reversibilityOfKind("envelope_v2"), "hard");
  // An unrecognised kind must NOT be classed as safe — a new kind appearing on
  // the desk would otherwise sink to the bottom of the CEO's queue silently.
  assert.equal(reversibilityOfKind("some_new_kind_2027"), "unclassified");
  assert.equal(reversibilityOfKind(undefined), "unclassified");
  assert.equal(reversibilityOfKind(null), "unclassified");
});

/* --------------------------------------------------------------- money --- */

test("an order's money comes from the spine's impact preview", () => {
  const [item] = orderItems([sofiSell]);
  assert.equal(item.moneyUsd, 169.25);
  assert.equal(item.reversibility, "irreversible");
  assert.equal(item.waitingSince, "2026-08-20T13:12:52.695919+00:00");
});

test("an order with no impact preview is unpriced, NOT zero", () => {
  const [item] = orderItems([{ ...sofiSell, impact_preview: undefined }]);
  assert.equal(item.moneyUsd, null);
  assert.notEqual(item.moneyUsd, 0);
});

test("a recommendation is unpriced — no money is scraped from its prose", () => {
  // The live desk carried 47 open recommendations on 2026-08-20 and not one
  // stated a dollar figure in a machine-readable field. If a future version
  // starts parsing "$634.55" out of `text`, this assertion is what catches it:
  // a number lifted from prose is an assertion the endpoint never made.
  const [item] = recItems(
    [rec({ run_id: "run-coo-1", rec_id: 1, seat: "coo", kind: "batch",
           text: "BATCH A (FIRST, expires 12:21:40Z, $634.55): approve all four sells." })],
    [run({ run_id: "run-coo-1", seat: "coo", resolved_at: "2026-08-20T10:52:47Z" })],
  );
  assert.equal(item.moneyUsd, null);
  assert.equal(item.waitingSince, "2026-08-20T10:52:47Z");
});

test("a recommendation whose run is unknown is undated, not new", () => {
  const [item] = recItems(
    [rec({ run_id: "run-missing", rec_id: 1, seat: "pm", kind: "fix", text: "x" })],
    [],
  );
  assert.equal(item.waitingSince, null);
});

/* ------------------------------------------------------------- ranking --- */

test("money leads, and an unpriced item never outranks a priced one", () => {
  const priced = orderItems([sofiSell]);
  const unpriced = recItems(
    [rec({ run_id: "r", rec_id: 1, seat: "pm", kind: "retire", text: "close it" })],
    [run({ run_id: "r", seat: "pm", resolved_at: "2020-01-01T00:00:00Z" })],
  );
  // The recommendation is far older AND classed `hard`; money still wins.
  const ranked = rankDeskItems([...unpriced, ...priced]);
  assert.equal(ranked[0].kind, "order");
  assert.equal(ranked[1].kind, "recommendation");
});

test("bigger money first", () => {
  const small = orderItems([{ ...sofiSell, order_id: "small",
    impact_preview: { notional_usd: 10 } }]);
  const big = orderItems([{ ...sofiSell, order_id: "big",
    impact_preview: { notional_usd: 5000 } }]);
  const ranked = rankDeskItems([...small, ...big]);
  assert.equal(ranked[0].order?.order_id, "big");
});

test("with no money on either side, harder-to-undo leads", () => {
  const runs = [run({ run_id: "r", seat: "pm", resolved_at: "2026-08-20T10:00:00Z" })];
  const items = recItems([
    rec({ run_id: "r", rec_id: 1, seat: "pm", kind: "fix", text: "reversible" }),
    rec({ run_id: "r", rec_id: 2, seat: "pm", kind: "retire", text: "hard" }),
    rec({ run_id: "r", rec_id: 3, seat: "pm", kind: "who_knows", text: "unclassified" }),
  ], runs);
  const ranked = rankDeskItems(items);
  assert.deepEqual(ranked.map((i) => i.rec?.kind), ["retire", "who_knows", "fix"]);
});

test("at equal money and reversibility, the OLDEST leads and undated sinks", () => {
  const items = recItems([
    rec({ run_id: "new", rec_id: 1, seat: "pm", kind: "fix", text: "new" }),
    rec({ run_id: "old", rec_id: 1, seat: "pm", kind: "fix", text: "old" }),
    rec({ run_id: "none", rec_id: 1, seat: "pm", kind: "fix", text: "undated" }),
  ], [
    run({ run_id: "new", seat: "pm", resolved_at: "2026-08-20T10:00:00Z" }),
    run({ run_id: "old", seat: "pm", resolved_at: "2026-08-01T10:00:00Z" }),
    run({ run_id: "none", seat: "pm" }),
  ]);
  const ranked = rankDeskItems(items);
  assert.deepEqual(ranked.map((i) => i.rec?.text), ["old", "new", "undated"]);
});

test("the comparator is a total order — sorting is stable and idempotent", () => {
  const items = [
    ...orderItems([sofiSell]),
    ...recItems([
      rec({ run_id: "r", rec_id: 1, seat: "pm", kind: "fix", text: "a" }),
      rec({ run_id: "r", rec_id: 2, seat: "pm", kind: "fix", text: "b" }),
    ], [run({ run_id: "r", seat: "pm", resolved_at: "2026-08-20T10:00:00Z" })]),
  ];
  const once = rankDeskItems(items).map((i) => i.key);
  const twice = rankDeskItems(rankDeskItems(items)).map((i) => i.key);
  assert.deepEqual(once, twice);
  assert.equal(compareDeskItems(items[0], items[0]), 0);
});

test("the money gap is counted so the page can state it", () => {
  const items = [
    ...orderItems([sofiSell]),
    ...recItems([rec({ run_id: "r", rec_id: 1, seat: "pm", kind: "fix", text: "a" })],
                [run({ run_id: "r", seat: "pm" })]),
  ];
  assert.deepEqual(moneyGap(items), { priced: 1, unpriced: 1 });
});

/* ---------------------------------------------------------- COO memos ---- */

test("COO memos are newest first and split with the shared memo rule", () => {
  const memos = cooMemos([
    run({ run_id: "run-coo-1", seat: "coo", task: "FOUNDING TRIAGE",
          resolved_at: "2026-08-20T10:52:47.131514+00:00",
          artifact_path: "docs/coo/TRIAGE_2026-08-20.md",
          verdict: "20 OPEN ITEMS -> 6 BATCHES. Two objections followed.",
          recommendations: [
            { rec_id: 1, seat: "coo", status: "open", text: "a" },
            { rec_id: 2, seat: "coo", status: "accepted", text: "b" },
          ] }),
    run({ run_id: "run-coo-0", seat: "coo", task: "older",
          resolved_at: "2026-08-19T09:00:00Z", verdict: "OLDER.", recommendations: [] }),
    // Not the coo — must not appear.
    run({ run_id: "run-pm-1", seat: "pm", task: "pm", verdict: "X.", recommendations: [] }),
  ], memoParts);

  assert.deepEqual(memos.map((m) => m.runId), ["run-coo-1", "run-coo-0"]);
  assert.equal(memos[0].headline, "20 OPEN ITEMS -> 6 BATCHES.");
  assert.equal(memos[0].rest, "Two objections followed.");
  assert.equal(memos[0].artifactPath, "docs/coo/TRIAGE_2026-08-20.md");
  assert.equal(memos[0].recCount, 2);
  assert.equal(memos[0].openRecCount, 1);
});

test("a COO memo with no verdict does NOT borrow its task as a headline", () => {
  // Passing a dispatch instruction off as the COO's conclusion would be putting
  // words in a colleague's mouth on the CEO's most-read surface.
  const [m] = cooMemos(
    [run({ run_id: "r", seat: "coo", task: "TRIAGE EVERYTHING", verdict: null,
           recommendations: [] })],
    memoParts,
  );
  assert.equal(m.headline, "");
  assert.equal(m.task, "TRIAGE EVERYTHING");
});

/* ------------------------------------------------------- the ask queue --- */

test("seat-filed asks are identified; humans are not seats", () => {
  assert.equal(isSeatFiled("mechanism"), true);
  assert.equal(isSeatFiled("coo"), true);
  assert.equal(isSeatFiled("ceo"), false);
  assert.equal(isSeatFiled("cto"), false);
  assert.equal(isSeatFiled(""), false);
  assert.equal(isSeatFiled(undefined), false);
  // The live log's `actor` field carries 200-character sentences. A prefix
  // match would give one of those a seat's face and attribute a machine note
  // to a colleague; matching is exact.
  assert.equal(isSeatFiled("cto-stale-guard: the GLD position this ticket closes"), false);
});

test("request 5fc56190 — the first seat-filed ask — renders as awaiting the CEO", () => {
  // Verbatim from GET /api/v1/fund/desk, 2026-08-20. No DeskRequestApproved
  // event exists for it, so the spine's fold reports status "open".
  const asks = queuedAsks([{
    at: "2026-08-20T11:23:09.044665+00:00",
    kind: "audit",
    note: "Seat-filed ask (defect D1, CTO-verified). Awaits CEO approval, then CTO trigger.",
    actor: "mechanism",
    serves: "validator",
    subject: "mechanism requests validator: audit walk-forward window geometry for short holds.",
    trace_id: "5fc56190-a73a-4bac-8944-6bdc16b67f37",
    request_id: "5fc56190-a73a-4bac-8944-6bdc16b67f37",
    status: "open",
  }]);
  assert.equal(asks.length, 1);
  assert.equal(asks[0].actor, "mechanism");
  assert.equal(asks[0].seatFiled, true);
  assert.equal(asks[0].serves, "validator");
  assert.equal(asks[0].stage, "awaiting_ceo");
  assert.equal(asks[0].approvedBy, null);
  assert.equal(asks[0].approvedAt, null);
});

test("CEO-approved asks lead the queue, then oldest first; resolved drop out", () => {
  const asks = queuedAsks([
    { request_id: "old-open", kind: "audit", serves: "validator", subject: "s",
      status: "open", actor: "cto", at: "2026-08-19T00:00:00Z" },
    { request_id: "new-open", kind: "audit", serves: "validator", subject: "s",
      status: "open", actor: "mechanism", at: "2026-08-20T00:00:00Z" },
    { request_id: "cleared", kind: "build", serves: "builder", subject: "s",
      status: "approved", actor: "ceo", at: "2026-08-20T05:00:00Z",
      approved_by: "ceo", approved_at: "2026-08-20T06:00:00Z" },
    { request_id: "done", kind: "build", serves: "builder", subject: "s",
      status: "resolved", actor: "ceo", at: "2026-08-18T00:00:00Z" },
  ]);
  assert.deepEqual(asks.map((a) => a.requestId), ["cleared", "old-open", "new-open"]);
  assert.equal(asks[0].stage, "cleared_to_trigger");
  assert.equal(asks[0].approvedBy, "ceo");
});

/* -------------------------------------------------------- decision pace -- */

test("decision velocity is null — not zero — when the log is unreadable", () => {
  const v = decisionVelocity(null, new Date("2026-08-20T12:00:00Z"));
  assert.equal(v.today, null);
  assert.equal(v.week, null);
  assert.notEqual(v.today, 0);
});

test("decision velocity counts both decision event types, today and this week", () => {
  const v = decisionVelocity([
    { type: "DeskRecommendationDecided", ts: "2026-08-20T10:00:00Z" },
    { type: "DeskRecommendationDecided", ts: "2026-08-20T11:00:00Z" },
    { type: "DeskRequestApproved", ts: "2026-08-18T11:00:00Z" },
    { type: "DeskRecommendationDecided", ts: "2026-07-01T11:00:00Z" },  // outside the week
    { type: "NavStruck", ts: "2026-08-20T11:30:00Z" },                  // not a decision
  ], new Date("2026-08-20T12:00:00Z"));
  assert.equal(v.today, 2);
  assert.equal(v.week, 3);
  // The window's own floor, so "0 this week" can be read against how far back
  // this fold can actually see (the events endpoint caps at 1000 rows).
  assert.equal(v.oldestSeen, "2026-07-01T11:00:00Z");
});

test("a genuinely quiet day reports 0, distinct from null", () => {
  const v = decisionVelocity([], new Date("2026-08-20T12:00:00Z"));
  assert.equal(v.today, 0);
  assert.equal(v.week, 0);
  assert.notEqual(v.today, null);
});

/* --------------------------------- the ask lifecycle, all four states ----- */
//
// The defect these guard, found live 2026-08-21: asks rendered only on the CTO
// console, so the CEO's own page read "0 awaiting you" while the spine's
// desk_load counted 2 — the CEO could not see or click items waiting on the
// CEO. And the spine gained a FOURTH state the same day.

const ASK = {
  at: "2026-08-21T09:00:00+00:00",
  kind: "audit",
  actor: "pm",
  request_id: "abc12345-0000-0000-0000-000000000000",
} as const;

test("a DECLINED ask is terminal and never reads as done", () => {
  // Folding `declined` in with `resolved` would erase the difference between
  // "we did it" and "the CEO said no".
  const [a] = queuedAsks([{
    ...ASK, serves: "quant", subject: "pm requests quant: implement the survivor",
    status: "declined", declined_by: "ceo", declined_at: "2026-08-21T10:00:00+00:00",
    decline_reason: "the survivor is not funded this quarter",
  }]);
  assert.equal(a.stage, "declined");
  assert.notEqual(a.stage, "resolved");
  assert.equal(a.declinedBy, "ceo");
  assert.equal(a.declineReason, "the survivor is not funded this quarter");
});

test("an APPROVED ask stays on the queue as cleared, rather than disappearing", () => {
  // A blessing nobody acted on is exactly the thing that goes quiet.
  const [a] = queuedAsks([{
    ...ASK, serves: "quant", subject: "s", status: "approved",
    approved_by: "ceo", approved_at: "2026-08-21T10:00:00+00:00",
  }]);
  assert.equal(a.stage, "cleared_to_trigger");
  assert.equal(a.approvedBy, "ceo");
  assert.equal(a.declinedBy, null);
});

test("the normalized task/seat spelling is preferred over subject/serves", () => {
  // The spine normalizes seat vocabulary onto task/seat. An unnormalized ask was
  // COUNTED by desk_load and rendered as a BLANK ROW — invisible work on a
  // visually clear desk.
  const [a] = queuedAsks([{
    ...ASK, serves: "quant", subject: "old spelling",
    task: "normalized task", seat: "validator", status: "open",
  }]);
  assert.equal(a.subject, "normalized task");
  assert.equal(a.serves, "validator");
});

test("the OLD spelling still renders when the spine sent no normalized field", () => {
  const [a] = queuedAsks([{
    ...ASK, serves: "quant", subject: "old spelling", status: "open",
  }]);
  assert.equal(a.subject, "old spelling");
  assert.equal(a.serves, "quant");
});

test("declined asks sink below anything still needing a decision", () => {
  const asks = queuedAsks([
    { ...ASK, request_id: "d", serves: "q", subject: "declined", status: "declined",
      decline_reason: "no" },
    { ...ASK, request_id: "o", serves: "q", subject: "open", status: "open" },
    { ...ASK, request_id: "c", serves: "q", subject: "cleared", status: "approved" },
  ]);
  assert.deepEqual(asks.map((a) => a.stage),
    ["cleared_to_trigger", "awaiting_ceo", "declined"]);
});

test("a resolved ask is off the queue entirely — it is history", () => {
  const asks = queuedAsks([{
    ...ASK, serves: "q", subject: "done", status: "resolved",
    resolution: "filed at docs/x.md",
  }]);
  assert.equal(asks.length, 0);
});

test("the CEO's ordering leads with what awaits the CEO, not with what is cleared", () => {
  // Found by looking, 2026-08-21: the first render of the CEO desk reused the
  // CTO console's order and buried the one ask awaiting the CEO beneath three
  // already-approved ones, on a page subtitled "everything awaiting your click".
  const asks = queuedAsks([
    { ...ASK, request_id: "c1", serves: "q", subject: "cleared", status: "approved",
      at: "2026-08-21T07:00:00+00:00" },
    { ...ASK, request_id: "d1", serves: "q", subject: "declined", status: "declined",
      decline_reason: "no", at: "2026-08-21T06:00:00+00:00" },
    { ...ASK, request_id: "o1", serves: "q", subject: "open", status: "open",
      at: "2026-08-21T09:00:00+00:00" },
  ]);
  assert.equal(queuedAsks.length >= 0, true);
  assert.deepEqual(asksForCeo(asks).map((a) => a.stage),
    ["awaiting_ceo", "cleared_to_trigger", "declined"]);
  // And the CTO's own ordering is untouched — it leads with cleared.
  assert.equal(asks[0].stage, "cleared_to_trigger");
});

test("within a stage the CEO sees the oldest ask first", () => {
  const asks = queuedAsks([
    { ...ASK, request_id: "n", serves: "q", subject: "newer", status: "open",
      at: "2026-08-21T12:00:00+00:00" },
    { ...ASK, request_id: "o", serves: "q", subject: "older", status: "open",
      at: "2026-08-19T12:00:00+00:00" },
  ]);
  assert.deepEqual(asksForCeo(asks).map((a) => a.subject), ["older", "newer"]);
});
