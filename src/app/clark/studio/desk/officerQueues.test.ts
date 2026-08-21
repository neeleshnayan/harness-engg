/**
 * The four officer queues, tested from the ways a queue misleads its reader.
 *
 * The CEO asked for the split by name. What makes it dangerous is the COUNT:
 * this desk has already shipped one defect where a number said "20 awaiting
 * your decision" on a desk where everything had been decided (CDO D4), and one
 * where it said "0 awaiting you" while two items genuinely waited (D6). Every
 * test below is about a number or a button being wrong in one of those two
 * directions.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import type { DeskItem } from "./execDesk.ts";
import {
  DECIDABLE_SECRETARY_KIND, hasContent, isSecretaryNote, officerDesk,
  officerOfItem,
} from "./officerQueues.ts";

const rec = (seat: string, over: Record<string, unknown> = {}): DeskItem => ({
  key: `rec:${seat}:${String(over.rec_id ?? Math.random())}`,
  kind: "recommendation",
  moneyUsd: null,
  reversibility: "reversible",
  waitingSince: null,
  dueDate: null,
  rec: {
    run_id: "r1", rec_id: 1, seat, kind: "process", status: "open",
    text: "t", task: "task", artifact_path: null, trace_id: null,
    ...over,
  } as DeskItem["rec"],
});

const order = (id = "o1"): DeskItem => ({
  key: `order:${id}`,
  kind: "order",
  moneyUsd: 169.25,
  reversibility: "irreversible",
  waitingSince: "2026-08-21T09:00:00+00:00",
  dueDate: null,
  order: { order_id: id } as DeskItem["order"],
});

const desk = (over: Partial<Parameters<typeof officerDesk>[0]> = {}) =>
  officerDesk({ awaitingDecision: [], awaitingExecution: [], memos: [], asks: [], ...over });

/* ------------------------------------------------------------- routing --- */

describe("who owns an item", () => {
  it("sends the COO's recommendations to Vishesh", () => {
    assert.equal(officerOfItem(rec("coo")), "vishesh");
  });

  it("sends the secretary's to Donna", () => {
    assert.equal(officerOfItem(rec("secretary")), "donna");
  });

  it("sends a PENDING ORDER to Fable, not to the strategy's author", () => {
    // An order is on this desk because the CTO staged it. It carries no seat,
    // and naming the author would attribute the staging to someone who did not
    // do it.
    assert.equal(officerOfItem(order()), "fable");
  });

  it("sends the bench to Others", () => {
    for (const s of ["quant", "pm", "analyst", "validator", "builder",
                     "adversary", "mechanism", "riskofficer"]) {
      assert.equal(officerOfItem(rec(s)), "others", s);
    }
  });

  it("sends an UNKNOWN seat to Others rather than dropping it", () => {
    // The live desk carries `cdo-trial`, which is not on the roster. A queue
    // that discarded it would hide a real open recommendation.
    assert.equal(officerOfItem(rec("cdo-trial")), "others");
    assert.equal(officerOfItem(rec("")), "others");
  });

  it("is case- and whitespace-insensitive, because the field is free text", () => {
    assert.equal(officerOfItem(rec("  COO ")), "vishesh");
  });
});

/* ------------------------------------------------- Donna's read-only rule -- */

describe("Donna's notes", () => {
  it("treats ONLY `suggestion` as decidable", () => {
    assert.equal(isSecretaryNote(rec("secretary", { kind: "suggestion" })), false);
    assert.equal(isSecretaryNote(rec("secretary", { kind: "note" })), true);
  });

  it("treats her PRE-VOCABULARY kinds as notes, not as decisions", () => {
    // Her one live run files `record_keeping` and `org_observation`. Under a
    // `kind === "note"` test those would sprout accept/reject buttons — exactly
    // what the CEO objected to: "this seems more like a note and I don't know
    // what to accept". The whitelist fails toward read-only.
    for (const k of ["record_keeping", "org_observation", "", "anything"]) {
      assert.equal(isSecretaryNote(rec("secretary", { kind: k })), true, k);
    }
  });

  it("puts notes in `notes` and keeps them OUT of the count", () => {
    const d = desk({ awaitingDecision: [
      rec("secretary", { kind: "org_observation" }),
      rec("secretary", { kind: "note" }),
    ] });
    assert.equal(d.donna.notes.length, 2);
    assert.equal(d.donna.awaiting.length, 0);
    assert.equal(d.donna.awaitingCount, 0);
    assert.equal(d.awaitingTotal, 0, "a desk of notes is not a backlog");
  });

  it("counts a SUGGESTION, because that one is a decision", () => {
    const d = desk({ awaitingDecision: [
      rec("secretary", { kind: DECIDABLE_SECRETARY_KIND }),
      rec("secretary", { kind: "note" }),
    ] });
    assert.equal(d.donna.awaiting.length, 1);
    assert.equal(d.donna.notes.length, 1);
    assert.equal(d.donna.awaitingCount, 1);
  });

  it("still has CONTENT on a day of pure notes, so her queue does not vanish", () => {
    const d = desk({ awaitingDecision: [rec("secretary", { kind: "note" })] });
    assert.equal(d.donna.awaitingCount, 0);
    assert.equal(hasContent(d.donna), true);
  });
});

/* --------------------------------------------------------------- counts --- */

describe("the counts", () => {
  it("sums the four queues into the headline", () => {
    const d = desk({ awaitingDecision: [
      rec("coo"), rec("quant"), rec("pm"),
      rec("secretary", { kind: "suggestion" }),
    ], asks: [] });
    assert.equal(d.vishesh.awaitingCount, 1);
    assert.equal(d.donna.awaitingCount, 1);
    assert.equal(d.others.awaitingCount, 2);
    assert.equal(d.awaitingTotal, 4);
  });

  it("counts an ask only while it AWAITS the CEO", () => {
    const ask = (stage: string) => ({
      requestId: `x${stage}`, actor: "pm", seatFiled: true, serves: "quant",
      subject: "s", note: null, at: null, stage, approvedBy: null,
      approvedAt: null, declinedBy: null, declinedAt: null, declineReason: null,
    }) as Parameters<typeof officerDesk>[0]["asks"][number];
    const d = desk({ asks: [
      ask("awaiting_ceo"), ask("cleared_to_trigger"), ask("declined"),
    ] });
    assert.equal(d.fable.asks.length, 3, "all three still render");
    assert.equal(d.fable.awaitingCount, 1, "only one needs a click");
  });

  it("never counts a DECIDED item, in any queue", () => {
    const d = desk({
      awaitingExecution: [rec("coo"), rec("quant"), order()],
    });
    assert.equal(d.awaitingTotal, 0);
    assert.equal(d.vishesh.decided.length, 1);
    assert.equal(d.others.decided.length, 1);
    assert.equal(d.fable.decided.length, 1);
  });

  it("counts an order in Fable's queue", () => {
    const d = desk({ awaitingDecision: [order("a"), order("b")] });
    assert.equal(d.fable.awaitingCount, 2);
  });

  it("does not double-count an ask that is also in `awaiting`", () => {
    // Asks live in their own list; `awaiting` holds orders and recommendations.
    const ask = {
      requestId: "q", actor: "pm", seatFiled: true, serves: "quant", subject: "s",
      note: null, at: null, stage: "awaiting_ceo", approvedBy: null,
      approvedAt: null, declinedBy: null, declinedAt: null, declineReason: null,
    } as Parameters<typeof officerDesk>[0]["asks"][number];
    const d = desk({ awaitingDecision: [order()], asks: [ask] });
    assert.equal(d.fable.awaitingCount, 2);
    assert.equal(d.awaitingTotal, 2);
  });
});

/* --------------------------------------------------------------- others --- */

describe("the Others bucket", () => {
  it("groups by seat name, busiest first then alphabetical", () => {
    const d = desk({ awaitingDecision: [
      rec("quant"), rec("quant"), rec("analyst"), rec("pm"), rec("pm"),
    ] });
    assert.deepEqual(d.others.groups.map((g) => [g.seat, g.items.length]),
      [["pm", 2], ["quant", 2], ["analyst", 1]]);
  });

  it("names an unattributed item rather than hiding it", () => {
    const d = desk({ awaitingDecision: [rec("")] });
    assert.deepEqual(d.others.groups.map((g) => g.seat), ["unattributed"]);
    assert.equal(d.others.awaitingCount, 1);
  });
});

/* -------------------------------------------------------------- ordering -- */

describe("routing does not re-rank", () => {
  it("preserves the money-first order it was handed", () => {
    // An item's officer says who is asking, not how urgent it is. Re-sorting
    // here would quietly demote a large decision because of whose desk it came
    // off.
    const a = rec("quant", { rec_id: 1 });
    const b = rec("quant", { rec_id: 2 });
    const c = rec("quant", { rec_id: 3 });
    const d = desk({ awaitingDecision: [a, b, c] });
    assert.deepEqual(d.others.awaiting.map((x) => x.key), [a.key, b.key, c.key]);
  });
});

describe("an empty desk", () => {
  it("produces four queues, all zero, none with content", () => {
    const d = desk();
    assert.equal(d.all.length, 4);
    assert.deepEqual(d.all.map((x) => x.id), ["vishesh", "donna", "fable", "others"]);
    assert.equal(d.awaitingTotal, 0);
    assert.equal(d.all.every((x) => !hasContent(x)), true);
  });
});
