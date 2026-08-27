import test from "node:test";
import assert from "node:assert/strict";

import {
  SHOWN, ageHoursOf, ageLabelOf, bandOf, consoleQueue, rankRows,
} from "./consoleQueue.ts";
import type { DeskView } from "@/lib/fund_api";

/**
 * THE CONSOLE'S QUEUE — rows, ranked by the SPINE'S bands, with an honest tail.
 *
 * Two things are being defended here and only one of them is the sort:
 *
 *  1. THE BAND IS READ, NEVER RE-DERIVED. The CEO's priority rule (blocker ·
 *     dated · the rest) is folded once in the record. A client that recomputed
 *     it from `due_date` when the payload was silent would be a second
 *     implementation of one rule in a different language, agreeing exactly
 *     until somebody edited either. `test_an_unbanded_row_is_NOT_re_derived`
 *     is the whole point of this file.
 *  2. THE TAIL IS EXACT AND SAYS THE RANK. "64 more, ranked the same way" is a
 *     different promise from "showing 6": the first tells the reader that what
 *     they cannot see has already been judged less urgent.
 */

const NOW = Date.parse("2026-08-27T08:00:00+00:00");

const REQ = (over: Record<string, unknown> = {}) => ({
  request_id: "req-1", kind: "audit", serves: "builder", actor: "cto",
  subject: "Rebuild the console", status: "approved", dispatched: false,
  at: "2026-08-27T06:00:00+00:00",
  band: "rest", band_rank: 3, band_label: "", band_basis: "undeclared",
  band_note: "Nobody said whether this holds anything up.",
  ...over,
}) as unknown as DeskView["requests"][number];

const REC = (over: Record<string, unknown> = {}) => ({
  run_id: "run-1", rec_id: 1, seat: "builder", status: "open",
  text: "Fire the adversary blind review", next_actor_resolved: "chair",
  resolved_at: "2026-08-27T04:00:00+00:00",
  band: "rest", band_rank: 3, band_label: "", band_basis: "undeclared",
  band_note: "Nobody said whether this holds anything up.",
  ...over,
});

/* ------------------------------------------------- the band is READ, not made */

test("the band arrives from the payload, with its label and its reason", () => {
  const q = consoleQueue([], [REC({
    band: "blocker", band_rank: 1, band_label: "blocker",
    band_basis: "declared", band_note: "The seat says it is holding something up.",
  })], { now: NOW });
  const row = q.rows[0];
  assert.equal(row.band, "blocker");
  assert.equal(row.bandRank, 1);
  assert.equal(row.bandLabel, "blocker");
  assert.equal(row.bandBasis, "declared");
  assert.match(row.bandNote!, /holding something up/);
  assert.equal(q.rankBasis, "bands");
});

test("an unbanded row is NOT re-derived from its own due_date", () => {
  // THE DEFECT THIS FILE EXISTS FOR. The row has a date and no band. A client
  // that "helpfully" made it time-sensitive would be re-implementing the CEO's
  // priority rule here, in a second language, silently.
  const q = consoleQueue([], [REC({
    band: undefined, band_rank: undefined, band_label: undefined,
    band_basis: undefined, band_note: undefined, due_date: "2026-09-01",
  })], { now: NOW });
  assert.equal(q.rows[0].band, "unbanded");
  assert.equal(q.rows[0].bandBasis, "absent");
  assert.equal(q.rows[0].bandLabel, "", "an unbanded row draws no chip");
  assert.equal(q.rows[0].dueDate, "2026-09-01", "the date is still shown");
  assert.equal(q.unbanded, 1);
  assert.equal(q.rankBasis, "age_only");
  assert.match(q.note, /ordered by how long things have waited/);
});

test("an unrecognised band word is treated as unbanded, never as `rest`", () => {
  const q = consoleQueue([], [REC({ band: "urgent", band_rank: 0 })], { now: NOW });
  assert.equal(q.rows[0].band, "unbanded");
});

test("an unbanded row sorts BEHIND every judged row, including `rest`", () => {
  const q = consoleQueue([], [
    REC({ rec_id: 1, band: undefined, band_rank: undefined }),
    REC({ rec_id: 2 }),
  ], { now: NOW });
  assert.deepEqual(q.rows.map((r) => r.id), ["run-1#2", "run-1#1"]);
});

/* ----------------------------------------------------------------- rank ---- */

const ROW = (over: Record<string, unknown>) => ({
  id: "x", origin: "recommendation" as const, band: "rest" as const,
  bandRank: 3, bandLabel: "", bandBasis: "undeclared", bandNote: null,
  actionTag: null, actionTagLabel: null,
  seat: null, filedBy: null, seatFiled: false, verbObject: "x",
  dueDate: null, money: null, at: null, ageHours: null, ageLabel: null,
  detail: null, approvedBy: null, approvedAt: null, ...over,
});

test("band beats date, and date beats money", () => {
  const out = rankRows([
    ROW({ id: "rich", money: 9999 }),
    ROW({ id: "dated", bandRank: 2, dueDate: "2026-12-01" }),
    ROW({ id: "blocking", bandRank: 1 }),
  ]);
  assert.deepEqual(out.map((r) => r.id), ["blocking", "dated", "rich"]);
});

test("a far-dated BLOCKER still outranks a soon-dated non-blocker", () => {
  const out = rankRows([
    ROW({ id: "soon", bandRank: 2, dueDate: "2026-08-28" }),
    ROW({ id: "blocker", bandRank: 1, dueDate: "2027-06-01" }),
  ]);
  assert.deepEqual(out.map((r) => r.id), ["blocker", "soon"]);
});

test("absent money sorts LAST, behind a stated zero", () => {
  const out = rankRows([
    ROW({ id: "absent" }), ROW({ id: "zero", money: 0 }),
    ROW({ id: "cheap", money: 0.5 }),
  ]);
  assert.deepEqual(out.map((r) => r.id), ["cheap", "zero", "absent"]);
});

test("age is the LAST tie-break, never the lead", () => {
  const out = rankRows([
    ROW({ id: "new", money: 100, ageHours: 1 }),
    ROW({ id: "old", money: 10, ageHours: 900 }),
  ]);
  assert.deepEqual(out.map((r) => r.id), ["new", "old"]);
  const tied = rankRows([
    ROW({ id: "new", ageHours: 1 }), ROW({ id: "old", ageHours: 900 }),
  ]);
  assert.deepEqual(tied.map((r) => r.id), ["old", "new"]);
});

test("the order is stable and does not mutate the caller's array", () => {
  const rows = [ROW({ id: "b" }), ROW({ id: "a" })];
  const out = rankRows(rows);
  assert.deepEqual(rows.map((r) => r.id), ["b", "a"]);
  assert.deepEqual(out.map((r) => r.id), ["a", "b"]);
});

/* ------------------------------------------------------- what gets in ------ */

test("only APPROVED-and-UNDISPATCHED requests are cleared to trigger", () => {
  const q = consoleQueue([
    REQ({ request_id: "open", status: "open" }),
    REQ({ request_id: "declined", status: "declined" }),
    REQ({ request_id: "resolved", status: "resolved" }),
    REQ({ request_id: "fired", status: "approved", dispatched: true }),
    REQ({ request_id: "ready", status: "approved", dispatched: false }),
  ], [], { now: NOW });
  assert.deepEqual(q.rows.map((r) => r.id), ["ready"]);
});

test("only chair-routed, still-live recommendations are on the chair's list", () => {
  const q = consoleQueue([], [
    REC({ rec_id: 1, next_actor_resolved: "ceo" }),
    REC({ rec_id: 2, next_actor_resolved: "nobody" }),
    REC({ rec_id: 3, status: "staged" }),
    REC({ rec_id: 4, status: "open" }),
    REC({ rec_id: 5, status: "accepted" }),
  ], { now: NOW });
  assert.deepEqual(q.rows.map((r) => r.id).sort(), ["run-1#4", "run-1#5"]);
});

test("a row with no readable words is dropped, not rendered blank", () => {
  const q = consoleQueue([REQ({ subject: "  ", task: null, headline: null })],
    [REC({ text: null, text_display: null })], { now: NOW });
  assert.equal(q.total, 0);
});

test("a seat-filed ask is marked as such — the org chart gaining an edge", () => {
  const q = consoleQueue([
    REQ({ request_id: "byseat", actor: "mechanism" }),
    REQ({ request_id: "byhuman", actor: "ceo" }),
  ], [], { now: NOW });
  const byId = Object.fromEntries(q.rows.map((r) => [r.id, r.seatFiled]));
  assert.equal(byId["byseat"], true);
  assert.equal(byId["byhuman"], false);
});

/* --------------------------------------------------------------- the tail -- */

test("the tail is EXACT and says the rank", () => {
  const many = Array.from({ length: SHOWN + 12 }, (_, i) =>
    REQ({ request_id: `r${String(i).padStart(2, "0")}` }));
  const q = consoleQueue(many, [], { now: NOW });
  assert.equal(q.total, SHOWN + 12);
  assert.equal(q.rows.length, SHOWN);
  assert.equal(q.hidden, 12);
  assert.match(q.tailNote!, /^12 more, ranked the same way/);
  assert.match(q.tailNote!, /nothing is hidden silently/);
});

test("no tail when nothing is hidden", () => {
  const q = consoleQueue([REQ()], [], { now: NOW });
  assert.equal(q.hidden, 0);
  assert.equal(q.tailNote, null);
});

/* ---------------------------------------------------------- absence -------- */

test("an unreadable population is a FLOOR and says which half is missing", () => {
  const both = consoleQueue(null, null, { now: NOW });
  assert.equal(both.isFloor, true);
  assert.match(both.note, /unknown, not nothing/);

  const noReqs = consoleQueue(null, [REC()], { now: NOW });
  assert.equal(noReqs.isFloor, true);
  assert.equal(noReqs.total, 1, "the half we CAN read is still shown");
  assert.match(noReqs.note, /could not read the approved asks/);

  const noRecs = consoleQueue([REQ()], null, { now: NOW });
  assert.match(noRecs.note, /could not read the recommendations/);
});

test("a readable and EMPTY queue is a measurement, not a failure", () => {
  const q = consoleQueue([], [], { now: NOW });
  assert.equal(q.isFloor, false);
  assert.equal(q.total, 0);
  assert.match(q.note, /Nothing is waiting on you/);
});

/* ------------------------------------------------------------ the clock --- */

test("age is measured against a supplied clock, so the test is not one", () => {
  assert.equal(ageHoursOf("2026-08-27T06:00:00+00:00", NOW), 2);
  assert.equal(ageHoursOf(null, NOW), null);
  assert.equal(ageHoursOf("not a date", NOW), null);
  // A future stamp is a record disagreeing with itself, not a negative age.
  assert.equal(ageHoursOf("2026-08-28T00:00:00+00:00", NOW), null);
});

test("an undated row is undated, NOT brand new", () => {
  const q = consoleQueue([REQ({ at: null })], [], { now: NOW });
  assert.equal(q.rows[0].ageHours, null);
  assert.equal(q.rows[0].ageLabel, null);
});

test("age reads the way a person says it", () => {
  assert.equal(ageLabelOf(null), null);
  assert.equal(ageLabelOf(0.4), "<1h");
  assert.equal(ageLabelOf(18), "18h");
  assert.equal(ageLabelOf(23.6), "24h");
  assert.equal(ageLabelOf(142.11), "5.9d");
});

test("bandOf on a bare object is `unbanded` with no chip and no note", () => {
  assert.deepEqual(bandOf({}), {
    band: "unbanded", bandRank: 4, bandLabel: "", bandBasis: "absent",
    bandNote: null,
  });
});

/* --------------------------------------- boundaries the Gauntlet found bare */
//
// Every test below probes an inequality the first pass tested only in the
// middle of its range. A cap tested with a twelve-row margin proves the cap
// exists; it does not prove it is off by nothing.

test("the age label's DAY boundary is probed at 23, 24 and 25 hours", () => {
  assert.equal(ageLabelOf(23), "23h");
  assert.equal(ageLabelOf(23.6), "24h", "still hours, rounded — not a day");
  assert.equal(ageLabelOf(24), "1.0d", "the boundary is exclusive on hours");
  assert.equal(ageLabelOf(25), "1.0d");
});

test("the tail appears at SHOWN+1 and NOT at exactly SHOWN", () => {
  const at = (n: number) => consoleQueue(
    Array.from({ length: n }, (_, i) =>
      REQ({ request_id: `r${String(i).padStart(2, "0")}` })), [], { now: NOW });
  const exact = at(SHOWN);
  assert.equal(exact.rows.length, SHOWN);
  assert.equal(exact.hidden, 0);
  assert.equal(exact.tailNote, null, "nothing is hidden at exactly the cap");
  const over = at(SHOWN + 1);
  assert.equal(over.rows.length, SHOWN);
  assert.equal(over.hidden, 1);
  assert.match(over.tailNote!, /^1 more, ranked the same way/);
  const under = at(SHOWN - 1);
  assert.equal(under.rows.length, SHOWN - 1);
  assert.equal(under.tailNote, null);
});

test("an UNRECOGNISED band is `unreadable`, not `absent` — they are different", () => {
  // The record sent a judgement this client cannot read (a newer spine, or a
  // malformed row). Reporting it as "nobody judged this" is the absence-vs-
  // unreadable conflation the rest of this module exists against.
  const unknown = consoleQueue([], [REC({ band: "urgent", band_rank: 0 })],
    { now: NOW }).rows[0];
  assert.equal(unknown.band, "unbanded");
  assert.equal(unknown.bandBasis, "unreadable");
  assert.equal(unknown.bandLabel, "", "still no chip — we cannot read it");

  const missing = consoleQueue([], [REC({
    band: undefined, band_rank: undefined, band_label: undefined,
    band_basis: undefined, band_note: undefined,
  })], { now: NOW }).rows[0];
  assert.equal(missing.band, "unbanded");
  assert.equal(missing.bandBasis, "absent");

  // ...and both still sort behind every judged row, because neither has been
  // placed in the order.
  assert.equal(unknown.bandRank, missing.bandRank);
});
