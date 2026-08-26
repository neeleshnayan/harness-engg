/**
 * THE PER-SEAT TRAY TESTS — a seat's in-tray and out-tray, as queries over one
 * fold, never a store with state of its own.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketTrays.test.ts`
 *
 * WHAT THIS GUARDS, straight from `ticketTrays.ts`'s own header:
 *
 *   - `seatOf`: `dispatched_to` wins over `filed_for`; whitespace is absence.
 *   - `trayFor`: null population -> null tray (never an empty one rendered as
 *     "nothing waiting"); terminal tickets excluded from EVERY tray even when
 *     `state` alone would say otherwise; the four tray buckets read `state`
 *     and `type` exactly as specified; `oldestWaitingHours` is the max age
 *     across the in-tray, null (never 0) when nothing is readable; and `note`
 *     tells the two different reasons a tray can be empty.
 *   - `allTrays`: null in, null out; roster comes from the data, not a list;
 *     the sort is a TOTAL order (count desc, then age desc, then name asc).
 *   - `chairQueue`: null in, null out; only non-terminal `returned` rows,
 *     oldest first by `lastTransitionAt`, ticket id as the final tiebreak.
 *   - `lastTransitionAt`: last transition with a readable `at`, skipping
 *     trailing blanks; falls back to `filed_at`; null when neither reads.
 */

import assert from "node:assert/strict";
import test from "node:test";
import type { Ticket, TicketState, TicketTransition } from "@/lib/fund_api";

import {
  allTrays, chairQueue, lastTransitionAt, seatOf, trayFor,
} from "./ticketTrays.ts";

/* ------------------------------------------------------------ the maker --- */

let seq = 0;

/** A ticket with an INERT default: `filed`, no seat assignment at all
 *  (`filed_for` and `dispatched_to` both null), not a lesson, one hour old,
 *  no transitions. A test opts a ticket INTO a tray field by field, so a tray
 *  cannot pass by accident when a rule stops firing. */
function tk(over: Partial<Ticket> = {}): Ticket {
  seq += 1;
  const state = (over.state ?? "filed") as TicketState;
  return {
    ticket_id: over.ticket_id ?? `t-${seq}`,
    type: over.type ?? "recommendation",
    state,
    subject: over.subject ?? `subject ${seq}`,
    filed_for: over.filed_for === undefined ? null : over.filed_for,
    filed_by: over.filed_by ?? "cto",
    filed_at: over.filed_at === undefined ? null : over.filed_at,
    trace_id: over.trace_id ?? null,
    parent_id: over.parent_id ?? null,
    source: over.source ?? "deskstore.recommendations",
    transitions: over.transitions ?? [],
    refused_transitions: over.refused_transitions ?? [],
    terminal: over.terminal ?? false,
    next_actor: over.next_actor ?? "chair",
    next_actor_basis: over.next_actor_basis ?? "kind",
    next_actor_why: over.next_actor_why ?? "the chair's move",
    age_hours: over.age_hours ?? 1,
    age_basis: over.age_basis ?? "event_timestamps",
    age_in_state_hours: over.age_in_state_hours === undefined
      ? 1 : over.age_in_state_hours,
    age_in_state_basis: over.age_in_state_basis ?? "event_timestamps",
    decided: over.decided ?? false,
    decision_count: over.decision_count ?? 0,
    decided_state: over.decided_state ?? null,
    decided_at: over.decided_at ?? null,
    decided_by: over.decided_by ?? null,
    canonical_ticket_id: over.canonical_ticket_id ?? null,
    decision_basis: over.decision_basis ?? "transitions",
    dispatched_to: over.dispatched_to === undefined ? null : over.dispatched_to,
    ...over,
  } as Ticket;
}

function trans(over: Partial<TicketTransition> = {}): TicketTransition {
  return {
    from: over.from ?? null,
    to: over.to ?? "approved",
    at: over.at === undefined ? "2026-08-25T00:00:00+00:00" : over.at,
    actor: over.actor ?? "cto",
    basis: over.basis ?? "dispatch",
  };
}

/* ----------------------------------------------------------- seatOf ------- */

test("seatOf: dispatched_to wins over filed_for when both are non-blank", () => {
  const t = tk({ dispatched_to: "builder", filed_for: "pm" });
  assert.equal(seatOf(t), "builder");
});

test("seatOf: falls back to filed_for when dispatched_to is absent", () => {
  const t = tk({ dispatched_to: null, filed_for: "pm" });
  assert.equal(seatOf(t), "pm");
});

test("seatOf: a whitespace-only dispatched_to is absence, not a seat", () => {
  const t = tk({ dispatched_to: "   ", filed_for: "pm" });
  assert.equal(seatOf(t), "pm");
});

test("seatOf: a whitespace-only filed_for is absence too", () => {
  const t = tk({ dispatched_to: null, filed_for: "   " });
  assert.equal(seatOf(t), null);
});

test("seatOf: both absent -> null", () => {
  const t = tk({ dispatched_to: null, filed_for: null });
  assert.equal(seatOf(t), null);
});

/* --------------------------------------------------- trayFor: unread pop -- */

test("trayFor(seat, null) returns null — never an empty tray for an unread population", () => {
  assert.equal(trayFor("builder", null), null);
});

test("trayFor(seat, undefined) returns null", () => {
  assert.equal(trayFor("builder", undefined), null);
});

/* ------------------------------------------- trayFor: terminal exclusion -- */

test("a ticket with state 'approved' but terminal:true appears in NO tray", () => {
  // A tray trusting `state` alone would show finished work as owed. This is
  // the load-bearing case: the field the code checks first (`terminal`)
  // contradicts the field a naive reader would check (`state`).
  const t = tk({
    ticket_id: "sneaky", state: "approved", terminal: true,
    dispatched_to: "builder",
  });
  const tray = trayFor("builder", [t])!;
  assert.equal(tray.awaitingDispatch.length, 0);
  assert.equal(tray.inFlight.length, 0);
  assert.equal(tray.outTray.length, 0);
  assert.equal(tray.unconsumedLessons.length, 0);
});

test("a terminal lesson is excluded from unconsumedLessons even though type and state would otherwise qualify", () => {
  const t = tk({
    ticket_id: "sneaky-lesson", type: "lesson", state: "filed", terminal: true,
    dispatched_to: "pm",
  });
  const tray = trayFor("pm", [t])!;
  assert.equal(tray.unconsumedLessons.length, 0);
});

/* -------------------------------------------- boundary table: ten states -- */

test("boundary table: every one of the ten ticket states lands in the right tray (or none)", () => {
  const TERMINALS: TicketState[] = [
    "done", "declined", "superseded", "merged", "expired",
  ];
  const ALL_STATES: TicketState[] = [
    "filed", "approved", "in_flight", "returned", "accepted",
    ...TERMINALS,
  ];
  for (const state of ALL_STATES) {
    const terminal = TERMINALS.includes(state);
    const t = tk({
      ticket_id: `boundary-${state}`, state, terminal, dispatched_to: "builder",
      type: "recommendation",
    });
    const tray = trayFor("builder", [t])!;
    const inAwaiting = tray.awaitingDispatch.some((x) => x.ticket_id === t.ticket_id);
    const inFlight = tray.inFlight.some((x) => x.ticket_id === t.ticket_id);
    const inOut = tray.outTray.some((x) => x.ticket_id === t.ticket_id);

    assert.equal(inAwaiting, !terminal && state === "approved",
      `state=${state}: awaitingDispatch membership`);
    assert.equal(inFlight, !terminal && state === "in_flight",
      `state=${state}: inFlight membership`);
    assert.equal(inOut, !terminal && state === "returned",
      `state=${state}: outTray membership`);
  }
});

test("boundary table: a lesson ticket lands in unconsumedLessons for every state except in_flight and every terminal", () => {
  const TERMINALS: TicketState[] = [
    "done", "declined", "superseded", "merged", "expired",
  ];
  const ALL_STATES: TicketState[] = [
    "filed", "approved", "in_flight", "returned", "accepted",
    ...TERMINALS,
  ];
  for (const state of ALL_STATES) {
    const terminal = TERMINALS.includes(state);
    const t = tk({
      ticket_id: `lesson-${state}`, state, terminal, type: "lesson",
      dispatched_to: "analyst",
    });
    const tray = trayFor("analyst", [t])!;
    const expected = !terminal && state !== "in_flight";
    assert.equal(
      tray.unconsumedLessons.some((x) => x.ticket_id === t.ticket_id),
      expected,
      `state=${state}: unconsumedLessons membership`,
    );
  }
});

/* -------------------------------------------------- oldestWaitingHours --- */

test("oldestWaitingHours is null, not 0, for an empty tray", () => {
  const tray = trayFor("builder", [])!;
  assert.equal(tray.awaitingDispatch.length, 0);
  assert.equal(tray.unconsumedLessons.length, 0);
  assert.equal(tray.oldestWaitingHours, null);
});

test("oldestWaitingHours is null when every age in the in-tray is unreadable", () => {
  const rows = [
    tk({
      state: "approved", dispatched_to: "builder", age_in_state_hours: null,
      age_in_state_basis: "unknown",
    }),
    tk({
      type: "lesson", state: "filed", dispatched_to: "builder",
      age_in_state_hours: null, age_in_state_basis: "unknown",
    }),
  ];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.awaitingDispatch.length, 1);
  assert.equal(tray.unconsumedLessons.length, 1);
  assert.equal(tray.oldestWaitingHours, null);
});

test("oldestWaitingHours is the MAX across awaitingDispatch and unconsumedLessons, ignoring unreadable ages", () => {
  const rows = [
    tk({ state: "approved", dispatched_to: "builder", age_in_state_hours: 5 }),
    tk({ state: "approved", dispatched_to: "builder", age_in_state_hours: 40 }),
    tk({
      type: "lesson", state: "filed", dispatched_to: "builder",
      age_in_state_hours: 12,
    }),
    tk({
      type: "lesson", state: "filed", dispatched_to: "builder",
      age_in_state_hours: null, age_in_state_basis: "unknown",
    }),
  ];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.oldestWaitingHours, 40);
});

/* ------------------------------------------------------------- the note --- */
//
// SHARED-WORD CHECK, DONE BY HAND: the four branch phrases below were read
// side by side before picking the assertion regex for each — "ticket
// anywhere is in `returned`" (A), "awaiting the chair's review" (B),
// "ticket exists in the record at all" (C), and "addressed to this seat"
// (D) — none of the four substrings appears in any of the other three
// branches' note text, so a mismatched branch cannot satisfy the wrong test.

test("note branch A: no ticket anywhere is returned -> says the door is unused", () => {
  const rows = [tk({ state: "filed", dispatched_to: "builder" })];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.outTray.length, 0);
  assert.match(tray.note, /NO ticket anywhere is in `returned`/);
});

test("note branch B: another seat has a returned ticket, this seat does not -> says this seat's queue is clear", () => {
  const rows = [
    tk({ state: "returned", dispatched_to: "pm" }),
    tk({ state: "filed", dispatched_to: "builder" }),
  ];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.outTray.length, 0);
  assert.match(tray.note, /awaiting the chair's review/);
  assert.doesNotMatch(tray.note, /NO ticket anywhere is in `returned`/);
});

test("note branch C: no lesson ticket exists anywhere -> says BINDS are carried by hand", () => {
  const rows = [tk({ type: "recommendation", state: "filed", dispatched_to: "builder" })];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.unconsumedLessons.length, 0);
  assert.match(tray.note, /`lesson` ticket exists in the record at all/);
});

test("note branch D: a lesson exists but not for this seat -> says none is addressed to this seat", () => {
  const rows = [
    tk({ type: "lesson", state: "filed", dispatched_to: "pm" }),
    tk({ type: "recommendation", state: "filed", dispatched_to: "builder" }),
  ];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.unconsumedLessons.length, 0);
  assert.match(tray.note, /no unconsumed lesson is addressed to this seat/);
  assert.doesNotMatch(tray.note, /`lesson` ticket exists in the record at all/);
});

test("both trays holding work collapses the note to the plain sentence", () => {
  const rows = [
    tk({ state: "returned", dispatched_to: "builder" }),
    tk({ type: "lesson", state: "filed", dispatched_to: "builder" }),
  ];
  const tray = trayFor("builder", rows)!;
  assert.equal(tray.outTray.length, 1);
  assert.equal(tray.unconsumedLessons.length, 1);
  assert.equal(tray.note, "both trays hold work");
});

/* ------------------------------------------------------------- allTrays --- */

test("allTrays(null) returns null", () => {
  assert.equal(allTrays(null), null);
});

test("allTrays(undefined) returns null", () => {
  assert.equal(allTrays(undefined), null);
});

test("allTrays derives its roster FROM THE DATA — a seat only ever seen in dispatched_to gets a tray", () => {
  const rows = [tk({ state: "approved", dispatched_to: "quant", filed_for: null })];
  const trays = allTrays(rows)!;
  assert.ok(trays.some((t) => t.seat === "quant"));
});

test("allTrays sorts by (awaitingDispatch + unconsumedLessons) count, descending, first", () => {
  const rows = [
    tk({ state: "approved", dispatched_to: "alpha" }),
    tk({ state: "approved", dispatched_to: "bravo" }),
    tk({ state: "approved", dispatched_to: "bravo" }),
  ];
  const trays = allTrays(rows)!;
  const names = trays.map((t) => t.seat);
  assert.deepEqual(names, ["bravo", "alpha"]);
});

test("allTrays breaks a count tie by oldestWaitingHours, descending", () => {
  const rows = [
    tk({ state: "approved", dispatched_to: "alpha", age_in_state_hours: 10 }),
    tk({ state: "approved", dispatched_to: "bravo", age_in_state_hours: 90 }),
  ];
  const trays = allTrays(rows)!;
  assert.deepEqual(trays.map((t) => t.seat), ["bravo", "alpha"]);
});

test("allTrays breaks a count+age tie by seat name, ascending", () => {
  const rows = [
    tk({ state: "approved", dispatched_to: "bravo", age_in_state_hours: 10 }),
    tk({ state: "approved", dispatched_to: "alpha", age_in_state_hours: 10 }),
  ];
  const trays = allTrays(rows)!;
  assert.deepEqual(trays.map((t) => t.seat), ["alpha", "bravo"]);
});

test("allTrays: the order is TOTAL — the same population in a different input order yields the same output order", () => {
  const rowsA = [
    tk({ ticket_id: "r1", state: "approved", dispatched_to: "alpha", age_in_state_hours: 10 }),
    tk({ ticket_id: "r2", state: "approved", dispatched_to: "bravo", age_in_state_hours: 90 }),
    tk({ ticket_id: "r3", state: "approved", dispatched_to: "charlie", age_in_state_hours: 10 }),
    tk({ ticket_id: "r4", state: "approved", dispatched_to: "charlie", age_in_state_hours: 5 }),
  ];
  const rowsB = [...rowsA].reverse();
  const namesA = allTrays(rowsA)!.map((t) => t.seat);
  const namesB = allTrays(rowsB)!.map((t) => t.seat);
  assert.deepEqual(namesA, namesB);
  // charlie: count 2, age 10 beats bravo: count 1, age 90 on count first;
  // alpha: count 1, age 10 is behind bravo (count tie broken? no, bravo has
  // count 1 too) -- bravo (age 90) then alpha (age 10), charlie leads both
  // on count.
  assert.deepEqual(namesA, ["charlie", "bravo", "alpha"]);
});

/* ------------------------------------------------------------ chairQueue -- */

test("chairQueue(null) returns null", () => {
  assert.equal(chairQueue(null), null);
});

test("chairQueue(undefined) returns null", () => {
  assert.equal(chairQueue(undefined), null);
});

test("chairQueue returns only non-terminal 'returned' tickets", () => {
  const rows = [
    tk({ ticket_id: "keep", state: "returned", terminal: false }),
    tk({ ticket_id: "drop-terminal", state: "returned", terminal: true }),
    tk({ ticket_id: "drop-not-returned", state: "approved" }),
  ];
  const q = chairQueue(rows)!;
  assert.deepEqual(q.map((t) => t.ticket_id), ["keep"]);
});

test("chairQueue orders oldest first by lastTransitionAt", () => {
  const rows = [
    tk({
      ticket_id: "newer", state: "returned",
      transitions: [trans({ to: "returned", at: "2026-08-25T12:00:00+00:00" })],
    }),
    tk({
      ticket_id: "older", state: "returned",
      transitions: [trans({ to: "returned", at: "2026-08-24T00:00:00+00:00" })],
    }),
  ];
  const q = chairQueue(rows)!;
  assert.deepEqual(q.map((t) => t.ticket_id), ["older", "newer"]);
});

test("chairQueue: a null/unreadable lastTransitionAt sorts to the end, not the front", () => {
  const rows = [
    tk({
      ticket_id: "unreadable", state: "returned", filed_at: null,
      transitions: [],
    }),
    tk({
      ticket_id: "readable", state: "returned",
      transitions: [trans({ to: "returned", at: "2026-08-24T00:00:00+00:00" })],
    }),
  ];
  const q = chairQueue(rows)!;
  assert.deepEqual(q.map((t) => t.ticket_id), ["readable", "unreadable"]);
});

test("chairQueue: two tickets sharing an identical last-transition instant get a deterministic order by ticket id, under either input order", () => {
  const same = "2026-08-25T00:00:00+00:00";
  const a = tk({
    ticket_id: "bbb", state: "returned",
    transitions: [trans({ to: "returned", at: same })],
  });
  const b = tk({
    ticket_id: "aaa", state: "returned",
    transitions: [trans({ to: "returned", at: same })],
  });
  const q1 = chairQueue([a, b])!;
  const q2 = chairQueue([b, a])!;
  assert.deepEqual(q1.map((t) => t.ticket_id), ["aaa", "bbb"]);
  assert.deepEqual(q2.map((t) => t.ticket_id), ["aaa", "bbb"]);
});

/* ------------------------------------------------------- lastTransitionAt -- */

test("lastTransitionAt reads the last transition's 'at' when it is non-blank", () => {
  const t = tk({
    transitions: [
      trans({ to: "approved", at: "2026-08-20T00:00:00+00:00" }),
      trans({ to: "in_flight", at: "2026-08-21T00:00:00+00:00" }),
    ],
  });
  assert.equal(lastTransitionAt(t), "2026-08-21T00:00:00+00:00");
});

test("lastTransitionAt skips trailing entries whose 'at' is null or blank", () => {
  const t = tk({
    transitions: [
      trans({ to: "approved", at: "2026-08-20T00:00:00+00:00" }),
      trans({ to: "in_flight", at: null }),
      trans({ to: "returned", at: "   " }),
    ],
  });
  assert.equal(lastTransitionAt(t), "2026-08-20T00:00:00+00:00");
});

test("lastTransitionAt falls back to filed_at when there are no transitions", () => {
  const t = tk({ transitions: [], filed_at: "2026-08-19T00:00:00+00:00" });
  assert.equal(lastTransitionAt(t), "2026-08-19T00:00:00+00:00");
});

test("lastTransitionAt returns null when neither transitions nor filed_at are readable", () => {
  const t = tk({
    transitions: [trans({ at: null }), trans({ at: "  " })],
    filed_at: null,
  });
  assert.equal(lastTransitionAt(t), null);
});

test("lastTransitionAt returns null when filed_at is blank and there are no transitions", () => {
  const t = tk({ transitions: [], filed_at: "   " });
  assert.equal(lastTransitionAt(t), null);
});

test("MUTANT M52: a CLOSED lesson still proves lessons exist", () => {
  // COMPUTING `anyLesson` OVER THE LIVE ROWS INSTEAD OF THE WHOLE POPULATION
  // SURVIVED, because no test carried a terminal lesson. The note it drives
  // says "NO `lesson` ticket exists in the record at all — BINDS are still
  // carried by hand", and that sentence is about the RECORD, not about what is
  // currently open. One consumed lesson makes it false, and the mutant would
  // keep printing it.
  const closedLesson = tk({ ticket_id: "L1", type: "lesson", filed_for: "pm",
                            state: "done", terminal: true });
  const other = tk({ ticket_id: "X", filed_for: "pm" });
  const tray = trayFor("pm", [closedLesson, other])!;
  assert.equal(tray.unconsumedLessons.length, 0,
    "a closed lesson is not unconsumed");
  assert.doesNotMatch(tray.note, /exists in the record at all/,
    "but the record DOES hold a lesson, so the never-filed sentence is false");
  assert.match(tray.note, /no unconsumed lesson is addressed to this seat/);
});
