/**
 * THE CEO'S EXCEPTIONS FILTER — the tests that fail if his desk lies again.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketExceptions.test.ts`
 *
 * THE INCIDENTS THESE GUARD (both the CEO's own words, both measured):
 *
 *   1. **"I filed an item worth $915 and could not find it"** — it sat at
 *      position 19 of 50 on a list of 57 whose own payload said 25 rows were
 *      in arrival order. `$915.0` is a real value in the live record; the
 *      money line is set below it precisely so that row surfaces, and
 *      `the money line surfaces the $915 row` fails if anyone raises it past.
 *   2. **"like WTF"** (2026-08-24) — an already-finished row rendering a
 *      decision control. Generalised here from `next_actor: nobody` to every
 *      terminal state: a terminal ticket is never on his desk, never counted,
 *      never escalated.
 *
 * AND ONE STRUCTURAL GUARD THAT IS WORTH MORE THAN EITHER: the split is
 * **exhaustive and disjoint by cardinality**. A filter that tidies a desk by
 * dropping a row would otherwise pass every other test in this file — a
 * quieter desk is exactly what a dropped row looks like.
 */

import assert from "node:assert/strict";
import test from "node:test";
import type { Ticket, TicketState, TicketType } from "@/lib/fund_api";

import {
  AGE_THRESHOLD_HOURS, CEO_EXCEPTIONS_VERSION, MISSING_JOIN_HOURS,
  MONEY_LINE_USD, PRE_HIGHWAY_FENCE, RULE_LABEL, RULE_ORDER,
  ceoExceptions, exceptionsNote, isDecisionRule, linkageReadable,
} from "./ticketExceptions.ts";

/* ------------------------------------------------------------ the maker --- */

let seq = 0;

/** A ticket with the fold's own defaults, overridable field by field.
 *
 *  DEFAULTS ARE THE INERT CASE ON PURPOSE: `filed`, chair's move, no money, no
 *  date, one hour old. A test that has to opt IN to every rule cannot pass by
 *  accident when a rule stops firing. */
function tk(over: Partial<Ticket> = {}): Ticket {
  seq += 1;
  const state = (over.state ?? "filed") as TicketState;
  return {
    ticket_id: over.ticket_id ?? `t-${seq}`,
    type: (over.type ?? "recommendation") as TicketType,
    state,
    subject: over.subject ?? `subject ${seq}`,
    filed_for: over.filed_for ?? "builder",
    filed_by: over.filed_by ?? "cto",
    filed_at: over.filed_at ?? `2026-08-2${(seq % 4) + 1}T00:00:00+00:00`,
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
    age_in_state_hours: over.age_in_state_hours ?? 1,
    age_in_state_basis: over.age_in_state_basis ?? "event_timestamps",
    decided: over.decided ?? false,
    decision_count: over.decision_count ?? 0,
    decided_state: over.decided_state ?? null,
    decided_at: over.decided_at ?? null,
    decided_by: over.decided_by ?? null,
    canonical_ticket_id: over.canonical_ticket_id ?? null,
    decision_basis: over.decision_basis ?? "transitions",
    ...over,
  } as Ticket;
}

const NOW = "2026-08-26T12:00:00+00:00";

/** The row he could not find, field for field from the live record. */
const THE_915_ROW = tk({
  ticket_id: "the-915",
  next_actor: "chair",
  money_at_stake: 915.0,
  state: "accepted",
  age_in_state_hours: 50,
});

/* ------------------------------------------------------- rule 1: his move -- */

test("a ticket the spine routes to the CEO is on his desk, and says why", () => {
  const x = ceoExceptions([tk({
    next_actor: "ceo",
    next_actor_why: "the row states its next actor is the ceo",
  })], NOW)!;
  assert.equal(x.decisionOwed.length, 1);
  assert.equal(x.decisionOwed[0].primary, "your_move");
  assert.equal(x.decisionOwed[0].why,
    "the row states its next actor is the ceo");
});

test("an UNREADABLE next actor counts toward him, never away from him", () => {
  // The live record carries three of these — a seat name the spine's actor
  // vocabulary does not contain. Routing them away would be the quiet way to
  // shrink his desk.
  const x = ceoExceptions([tk({ next_actor: "unknown" })], NOW)!;
  assert.equal(x.totals.decisionOwed, 1);
  assert.equal(x.totals.board, 0);
});

test("a row that is somebody ELSE'S move is on the board, not his desk", () => {
  const x = ceoExceptions([tk({ next_actor: "chair" })], NOW)!;
  assert.equal(x.totals.decisionOwed, 0);
  assert.equal(x.totals.board, 1);
});

test("`nobody` is not the CEO — a finished-but-open row leaves his desk", () => {
  const x = ceoExceptions([tk({ next_actor: "nobody" })], NOW)!;
  assert.equal(x.totals.decisionOwed, 0);
  assert.equal(x.totals.board, 1);
});

/* -------------------------------------- the split: decision vs execution --- */

test("a row he already DECIDED owes an execution, not a decision", () => {
  // This is the 57 -> 33 reduction, and it is the whole headline. `decided`
  // survives the move out of `filed`, so the split reads the fold's lineage
  // rather than guessing from `state`.
  const x = ceoExceptions([
    tk({ next_actor: "ceo", decided: false, state: "filed" }),
    tk({ next_actor: "ceo", decided: true, state: "accepted" }),
  ], NOW)!;
  assert.equal(x.totals.decisionOwed, 1);
  assert.equal(x.totals.executionOwed, 1);
  assert.equal(x.executionOwed[0].executionOwed, true);
});

test("the execution split reads `decided`, NOT the state name", () => {
  // A row can be `accepted` without ever having been decided by anyone (a
  // legacy status mapped through), and a decided row can have moved on. A
  // split keyed on `state === "accepted"` would get both backwards.
  const x = ceoExceptions([
    tk({ next_actor: "ceo", state: "accepted", decided: false }),
    tk({ next_actor: "ceo", state: "filed", decided: true }),
  ], NOW)!;
  assert.equal(x.decisionOwed.length, 1);
  assert.equal(x.decisionOwed[0].ticket.state, "accepted");
  assert.equal(x.executionOwed.length, 1);
  assert.equal(x.executionOwed[0].ticket.state, "filed");
});

/* ------------------------------------------------------ rule 4: the money -- */

test("the money line surfaces the $915 row the CEO could not find", () => {
  // FAILS IF ANYONE RAISES THE LINE PAST $915. The incident is the basis for
  // the level, so the level cannot move above the incident without this
  // going red — which is the point of pinning the incident and not the number.
  const x = ceoExceptions([THE_915_ROW], NOW)!;
  assert.equal(x.totals.escalated, 1);
  assert.equal(x.escalated[0].primary, "money");
  assert.match(x.escalated[0].why, /915/);
  assert.ok(MONEY_LINE_USD <= 915,
    `the money line is $${MONEY_LINE_USD}; the row that motivated it is $915`);
});

test("the money line is inclusive at the boundary, and exclusive below it", () => {
  const at = ceoExceptions([tk({ money_at_stake: MONEY_LINE_USD })], NOW)!;
  const below = ceoExceptions(
    [tk({ money_at_stake: MONEY_LINE_USD - 0.01 })], NOW)!;
  assert.equal(at.totals.escalated, 1, "at the line is ON the desk");
  assert.equal(below.totals.escalated, 0, "a cent below is not");
  assert.equal(below.totals.board, 1);
});

test("an ABSENT figure is unknown, never 'below the line'", () => {
  const x = ceoExceptions([tk({ money_at_stake: null })], NOW)!;
  const money = x.reports.find((r) => r.rule === "money")!;
  assert.equal(money.unknown, 1);
  assert.equal(money.evaluable, 0);
  assert.equal(money.domain, 1);
  assert.match(money.note, /UNKNOWN, not below the line/);
});

test("a non-finite figure is unknown, not a comparison", () => {
  // `NaN >= 900` is false, so a NaN would silently land in "below the line"
  // and be counted as evaluable. It is absence with a numeric type.
  const x = ceoExceptions([tk({ money_at_stake: NaN })], NOW)!;
  assert.equal(x.reports.find((r) => r.rule === "money")!.unknown, 1);
});

/* -------------------------------------------------------- rule 2: the age -- */

test("a ticket past its own state's threshold escalates, and says the number", () => {
  const lvl = AGE_THRESHOLD_HOURS.approved!;
  const x = ceoExceptions(
    [tk({ state: "approved", age_in_state_hours: lvl + 1 })], NOW)!;
  assert.equal(x.totals.escalated, 1);
  assert.equal(x.escalated[0].primary, "aged");
  assert.match(x.escalated[0].why, new RegExp(`${lvl}h threshold`));
});

test("the threshold is PER STATE — the same age passes in one and fails in another", () => {
  // `in_flight` is 72h and `accepted` is 144h. One age, two verdicts: a
  // single global threshold would make this test impossible to write.
  const age = 100;
  const flight = ceoExceptions(
    [tk({ state: "in_flight", age_in_state_hours: age })], NOW)!;
  const accepted = ceoExceptions(
    [tk({ state: "accepted", age_in_state_hours: age })], NOW)!;
  assert.equal(flight.totals.escalated, 1);
  assert.equal(accepted.totals.escalated, 0);
});

test("the age threshold is inclusive at the boundary", () => {
  const lvl = AGE_THRESHOLD_HOURS.in_flight!;
  const at = ceoExceptions(
    [tk({ state: "in_flight", age_in_state_hours: lvl })], NOW)!;
  const below = ceoExceptions(
    [tk({ state: "in_flight", age_in_state_hours: lvl - 0.001 })], NOW)!;
  assert.equal(at.totals.escalated, 1);
  assert.equal(below.totals.escalated, 0);
});

test("an UNREADABLE age never satisfies a threshold", () => {
  // A rule that fired on a null age would be inventing the measurement it
  // needs. `age_in_state_basis: "unknown"` is the fold's own word for it.
  const x = ceoExceptions([tk({
    state: "approved", age_in_state_hours: null, age_in_state_basis: "unknown",
  })], NOW)!;
  assert.equal(x.totals.escalated, 0);
  const aged = x.reports.find((r) => r.rule === "aged")!;
  assert.equal(aged.unknown, 1);
  assert.equal(aged.evaluable, 0);
});

test("every terminal state carries a null threshold, not a large number", () => {
  for (const s of ["done", "declined", "superseded", "merged", "expired"] as const) {
    assert.equal(AGE_THRESHOLD_HOURS[s], null,
      `${s} is terminal; nothing ages after it is finished`);
  }
  for (const s of ["filed", "approved", "in_flight", "returned", "accepted"] as const) {
    assert.equal(typeof AGE_THRESHOLD_HOURS[s], "number",
      `${s} is a working state and must carry a level`);
  }
});

/* --------------------------------------------------- rule 3: missing join -- */

test("the missing-join rule cannot speak about a FENCED ticket", () => {
  // The whole point. A pre-highway row has no parent the record supports, so
  // "no dispatch serves it" is not a conclusion available in either
  // direction. Reporting it as blocked would be inventing linkage; reporting
  // it as fine would be absence-as-zero.
  const fenced = tk({
    state: "accepted", age_in_state_hours: MISSING_JOIN_HOURS + 10,
    parent_basis: PRE_HIGHWAY_FENCE,
  });
  const x = ceoExceptions([fenced], NOW)!;
  assert.equal(x.totals.escalated, 0);
  const join = x.reports.find((r) => r.rule === "missing_join")!;
  assert.equal(join.domain, 1);
  assert.equal(join.evaluable, 0);
  assert.equal(join.unknown, 1);
  assert.match(join.note, /never 'nothing is blocked'/);
  assert.equal(linkageReadable(fenced), false);
});

test("an accepted ticket with readable linkage and no server IS blocked", () => {
  const x = ceoExceptions([tk({
    ticket_id: "orphan", state: "accepted", parent_basis: "run_trace_id",
    age_in_state_hours: MISSING_JOIN_HOURS + 1,
  })], NOW)!;
  assert.equal(x.totals.escalated, 1);
  assert.equal(x.escalated[0].primary, "missing_join");
});

test("an accepted ticket that IS somebody's parent is not blocked", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "served", state: "accepted", parent_basis: "run_trace_id",
         age_in_state_hours: MISSING_JOIN_HOURS + 1 }),
    tk({ ticket_id: "the-dispatch", type: "dispatch", state: "in_flight",
         parent_id: "served" }),
  ], NOW)!;
  assert.equal(x.totals.escalated, 0);
});

test("only ACCEPTED tickets are in the missing-join rule's domain", () => {
  const x = ceoExceptions([tk({
    state: "approved", parent_basis: "run_trace_id",
    age_in_state_hours: MISSING_JOIN_HOURS + 50,
  })], NOW)!;
  assert.equal(x.reports.find((r) => r.rule === "missing_join")!.domain, 0);
});

/* ----------------------------------------------------- rule 5: challenges -- */

test("a challenge against a CLOSED ticket reaches him", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "closed", terminal: true, state: "declined",
         next_actor: "nobody" }),
    tk({ ticket_id: "ch", type: "challenge", parent_id: "closed" }),
  ], NOW)!;
  assert.equal(x.totals.escalated, 1);
  assert.equal(x.escalated[0].primary, "challenge");
  assert.match(x.escalated[0].why, /closed/);
});

test("a challenge against a LIVE ticket is not this rule's business", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "live", state: "filed" }),
    tk({ ticket_id: "ch", type: "challenge", parent_id: "live" }),
  ], NOW)!;
  assert.equal(x.totals.escalated, 0);
});

test("zero challenges reports its DOMAIN beside the zero", () => {
  // A zero from an empty domain is not a finding, and this repo has shipped
  // two vacuous passes that printed a clean result with nothing behind it.
  const x = ceoExceptions([tk({}), tk({})], NOW)!;
  const ch = x.reports.find((r) => r.rule === "challenge")!;
  assert.equal(ch.caught, 0);
  assert.equal(ch.domain, 0);
  assert.match(ch.note, /empty domain/);
});

/* ------------------------------------------------- terminal is terminal ---- */

test("NO terminal ticket reaches his desk, under ANY of the five rules", () => {
  // The generalisation of D42's `nobody` case to all five terminals. Each row
  // below would fire a different rule if it were working; none may fire.
  const terminals: TicketState[] =
    ["done", "declined", "superseded", "merged", "expired"];
  const rows = terminals.flatMap((state) => [
    tk({ state, terminal: true, next_actor: "ceo" }),
    tk({ state, terminal: true, money_at_stake: 10_000 }),
    tk({ state, terminal: true, age_in_state_hours: 10_000 }),
  ]);
  const x = ceoExceptions(rows, NOW)!;
  assert.equal(x.totals.decisionOwed, 0);
  assert.equal(x.totals.executionOwed, 0);
  assert.equal(x.totals.escalated, 0);
  assert.equal(x.totals.board, 0);
  assert.equal(x.totals.record, rows.length);
});

test("a terminal ticket is not counted as working either", () => {
  const x = ceoExceptions(
    [tk({ terminal: true, state: "done" }), tk({})], NOW)!;
  assert.equal(x.totals.working, 1);
  assert.equal(x.totals.terminal, 1);
});

/* ------------------------------------------------ exhaustive and disjoint -- */

test("every ticket lands in exactly one bucket — the cardinality guard", () => {
  // THE TEST A TIDY-BY-DROPPING DEFECT CANNOT SURVIVE. Ten rows spanning
  // every rule, every state and both terminality answers.
  const rows = [
    tk({ next_actor: "ceo" }),
    tk({ next_actor: "ceo", decided: true }),
    tk({ next_actor: "unknown" }),
    tk({ money_at_stake: 5000 }),
    tk({ state: "approved", age_in_state_hours: 500 }),
    tk({ state: "accepted", parent_basis: "run_trace_id",
         age_in_state_hours: 500 }),
    tk({}),
    tk({ next_actor: "nobody" }),
    tk({ terminal: true, state: "done" }),
    tk({ terminal: true, state: "expired" }),
  ];
  const x = ceoExceptions(rows, NOW)!;
  const t = x.totals;
  assert.equal(
    t.decisionOwed + t.executionOwed + t.escalated + t.board + t.record,
    rows.length, "buckets must partition the population");
  const ids = [
    ...x.decisionOwed.map((r) => r.ticket.ticket_id),
    ...x.executionOwed.map((r) => r.ticket.ticket_id),
    ...x.escalated.map((r) => r.ticket.ticket_id),
    ...x.board.map((b) => b.ticket_id),
    ...x.record.map((b) => b.ticket_id),
  ];
  assert.equal(new Set(ids).size, rows.length, "and no row may appear twice");
});

test("the totals are COUNTED, not restated from each other", () => {
  const rows = [tk({ next_actor: "ceo" }), tk({}), tk({ terminal: true })];
  const x = ceoExceptions(rows, NOW)!;
  assert.equal(x.totals.decisionOwed, x.decisionOwed.length);
  assert.equal(x.totals.board, x.board.length);
  assert.equal(x.totals.record, x.record.length);
  assert.equal(x.totals.all, rows.length);
});

/* -------------------------------------------------------- the precedence --- */

test("when several rules fire, `your_move` wins and the rest still ride", () => {
  const x = ceoExceptions([tk({
    next_actor: "ceo", money_at_stake: 5000,
    state: "approved", age_in_state_hours: 500,
  })], NOW)!;
  assert.equal(x.totals.decisionOwed, 1);
  const row = x.decisionOwed[0];
  assert.equal(row.primary, "your_move");
  assert.deepEqual(row.rules, ["your_move", "money", "aged"]);
});

test("RULE_ORDER covers every rule exactly once and starts with the only decision rule", () => {
  assert.equal(new Set(RULE_ORDER).size, RULE_ORDER.length);
  assert.deepEqual([...RULE_ORDER].sort(), Object.keys(RULE_LABEL).sort());
  assert.equal(RULE_ORDER.filter(isDecisionRule).length, 1);
  assert.equal(RULE_ORDER[0], "your_move");
});

test("a row's rules are ordered by RULE_ORDER, not by check order", () => {
  const x = ceoExceptions([tk({
    state: "approved", age_in_state_hours: 500, money_at_stake: 5000,
  })], NOW)!;
  assert.deepEqual(x.escalated[0].rules, ["money", "aged"]);
});

/* ------------------------------------------------------------ the order ---- */

test("dated rows come first, soonest first; undated fall to the money key", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "no-date-big", next_actor: "ceo", money_at_stake: 1000 }),
    tk({ ticket_id: "late", next_actor: "ceo", due_date: "2026-09-30" }),
    tk({ ticket_id: "soon", next_actor: "ceo", due_date: "2026-08-27" }),
    tk({ ticket_id: "no-date-small", next_actor: "ceo", money_at_stake: 1 }),
  ], NOW)!;
  assert.deepEqual(x.decisionOwed.map((r) => r.ticket.ticket_id),
    ["soon", "late", "no-date-big", "no-date-small"]);
});

test("a row with NOTHING to rank on sorts last and SAYS it is unranked", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "bare", next_actor: "ceo" }),
    tk({ ticket_id: "priced", next_actor: "ceo", money_at_stake: 5 }),
  ], NOW)!;
  assert.deepEqual(x.decisionOwed.map((r) => r.ticket.ticket_id),
    ["priced", "bare"]);
  assert.equal(x.decisionOwed[1].rankedOn, "nothing");
  assert.equal(x.rankedOnNothing, 1);
});

test("the order is TOTAL — rows equal on every key still have one order", () => {
  // A stable sort over a partial key hands the order to whatever the fold
  // produced. Two rows filed in the same millisecond tie on date, money and
  // instant; the id breaks it, so the list cannot reshuffle between reads.
  const same = { next_actor: "ceo", filed_at: "2026-08-25T00:00:00+00:00" };
  const a = ceoExceptions([tk({ ...same, ticket_id: "bbb" }),
                           tk({ ...same, ticket_id: "aaa" })], NOW)!;
  const b = ceoExceptions([tk({ ...same, ticket_id: "aaa" }),
                           tk({ ...same, ticket_id: "bbb" })], NOW)!;
  assert.deepEqual(a.decisionOwed.map((r) => r.ticket.ticket_id), ["aaa", "bbb"]);
  assert.deepEqual(b.decisionOwed.map((r) => r.ticket.ticket_id), ["aaa", "bbb"]);
});

test("an empty due_date string is absence, not a date that sorts first", () => {
  const x = ceoExceptions([
    tk({ ticket_id: "blank", next_actor: "ceo", due_date: "   " }),
    tk({ ticket_id: "dated", next_actor: "ceo", due_date: "2026-12-01" }),
  ], NOW)!;
  assert.deepEqual(x.decisionOwed.map((r) => r.ticket.ticket_id),
    ["dated", "blank"]);
  assert.equal(x.decisionOwed[1].rankedOn, "nothing");
});

/* ------------------------------------------------------- the unread case --- */

test("an UNREAD population returns null — never an empty desk", () => {
  // The one answer that must never be fabricated. A filter over an unread
  // population that returned `{decisionOwed: []}` would render "nothing awaits
  // you" for a read that had not happened.
  assert.equal(ceoExceptions(null, NOW), null);
  assert.equal(ceoExceptions(undefined, NOW), null);
  assert.equal(exceptionsNote(null), null);
});

test("an EMPTY population is a real answer and reads as one", () => {
  const x = ceoExceptions([], NOW)!;
  assert.equal(x.totals.all, 0);
  assert.match(exceptionsNote(x)!, /^0 decision\(s\) await you/);
});

/* ------------------------------------------------------------- the note ---- */

test("the note states the arrival-order caveat only when it is true", () => {
  const bare = ceoExceptions([tk({ next_actor: "ceo" })], NOW)!;
  const dated = ceoExceptions(
    [tk({ next_actor: "ceo", due_date: "2026-09-01" })], NOW)!;
  assert.match(exceptionsNote(bare)!, /arrival order and not a ranking/);
  assert.doesNotMatch(exceptionsNote(dated)!, /arrival order/);
});

test("the overdue sentence agrees with its own count, singular and plural", () => {
  // A COUNT-DRIVEN SENTENCE IS A BRANCH. The first draft rendered "17 of them
  // is past its stated date" on the live page and no test could see it,
  // because the count was right. Both arms are pinned here so the singular
  // cannot be lost the next time someone edits the plural.
  const one = ceoExceptions(
    [tk({ next_actor: "ceo", due_date: "2026-08-01" })], NOW)!;
  const two = ceoExceptions([
    tk({ next_actor: "ceo", due_date: "2026-08-01" }),
    tk({ next_actor: "ceo", due_date: "2026-08-02" }),
  ], NOW)!;
  assert.match(exceptionsNote(one)!, /1 of them is past its stated date/);
  assert.match(exceptionsNote(two)!, /2 of them are past their stated dates/);
});

test("a date in the future is not overdue, and the boundary is TODAY", () => {
  // `desk._overdue` treats a due date equal to today as overdue — the day it
  // is due is the last day it is not late, and this desk has always read it
  // the other way. Pinned against the spine's own comparison.
  const today = ceoExceptions(
    [tk({ next_actor: "ceo", due_date: NOW.slice(0, 10) })], NOW)!;
  const tomorrow = ceoExceptions(
    [tk({ next_actor: "ceo", due_date: "2026-08-27" })], NOW)!;
  assert.equal(today.decisionOwed[0].overdue, true);
  assert.equal(tomorrow.decisionOwed[0].overdue, false);
});

test("a row with no date is never overdue", () => {
  const x = ceoExceptions([tk({ next_actor: "ceo" })], NOW)!;
  assert.equal(x.decisionOwed[0].overdue, false);
  assert.doesNotMatch(exceptionsNote(x)!, /past its stated date/);
});

test("the note counts the board and the record so nothing is hidden", () => {
  const x = ceoExceptions([
    tk({ next_actor: "ceo" }), tk({}), tk({ terminal: true, state: "done" }),
  ], NOW)!;
  assert.match(exceptionsNote(x)!, /1 working ticket\(s\) are on the board and 1 are closed/);
});

/* ---------------------------------------------------------- the version ---- */

test("the version string names the levels as unratified", () => {
  // The design says X and Y are CEO-set. They are not yet, and a surface that
  // printed a version implying otherwise would be laundering a builder's
  // judgement into a decision.
  assert.match(CEO_EXCEPTIONS_VERSION, /BUILDER'S PROPOSAL/);
  assert.match(CEO_EXCEPTIONS_VERSION, /ratification/);
});

/* --------------------------------------- mutation survivors, closed ------ */

test("MUTANT M04: every level is pinned, so a move is deliberate", () => {
  // A ONE-HOUR NUDGE TO ANY LEVEL SURVIVED THE WHOLE SUITE. Every other test
  // READS `AGE_THRESHOLD_HOURS` — which is right, and is what proves the value
  // is read rather than copied — but reading it means no test can see it move.
  //
  // THESE VALUES ARE THE BUILDER'S PROPOSAL AND THIS TEST DOES NOT CLAIM THEY
  // ARE CORRECT. It claims only that changing one is a deliberate act with a
  // diff a human reads, which is the direction rule applied to a display
  // threshold. When the CEO ratifies or moves a level, this literal moves with
  // it, in the same commit, on purpose.
  assert.deepEqual(
    { filed: AGE_THRESHOLD_HOURS.filed, approved: AGE_THRESHOLD_HOURS.approved,
      in_flight: AGE_THRESHOLD_HOURS.in_flight,
      returned: AGE_THRESHOLD_HOURS.returned,
      accepted: AGE_THRESHOLD_HOURS.accepted },
    { filed: 96, approved: 96, in_flight: 72, returned: 48, accepted: 144 });
});

test("every level lies inside the band where it can discriminate", () => {
  // THE MEASURED CLAIM, AND THE ONE WORTH GUARDING MORE THAN THE VALUES. Over
  // the live record every working ticket's age-in-state is between 43.1h and
  // 146.8h. A level below the floor admits its state's whole population; a
  // level above the ceiling can never fire. Either way the level stops being a
  // measurement and becomes a tie-break wearing one's clothes, which is the
  // failure this fund has already priced once.
  //
  // The band is the RECORD's, so it will widen as the record ages — these
  // numbers are the floor and ceiling measured 2026-08-26 by
  // `scripts/instruments/kp6/exception_curve.mjs`, and a level outside them
  // needs a re-measurement, not a wider constant.
  const FLOOR = 43.1, CEILING = 146.8;
  for (const [state, lvl] of Object.entries(AGE_THRESHOLD_HOURS)) {
    if (lvl === null) continue;
    assert.ok(lvl > FLOOR && lvl < CEILING,
      `${state} at ${lvl}h is outside the 43.1-146.8h band the record can `
      + "discriminate in: it either admits everything or can never fire");
  }
});
