/**
 * The ticket card contract — the tests that fail if a closed row grows a
 * button again, or if "whose move" and "does a control exist" ever collapse
 * back into one flag.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketCard.test.ts`
 *
 * THE INCIDENT (CEO, 2026-08-24, verbatim): *"like WTF"* — an already-executed
 * chair action rendered with Accept/Reject beside it. `ticketCard.ts`
 * generalises `recordRow.ts`'s single-field fix (`next_actor_resolved ===
 * "nobody"`) to the whole ticket lifecycle: any of the five terminal states,
 * read from the spine's own `terminal` flag first and the state-name list
 * only as a fallback.
 *
 * Every test below is written from the module's own docstring contract, not
 * from watching the code run. Where a test fails, the file stops and reports
 * the mismatch rather than bending either side to match the other.
 */

import assert from "node:assert/strict";
import test from "node:test";
import type { Ticket, TicketState } from "@/lib/fund_api";

import { CARD_HEADLINE_MAX } from "./cardAnatomy.ts";
import {
  TERMINAL_STATES, WORKING_STATES, STATE_LABEL,
  isTerminal, ticketLamp, ticketTitle, ticketAdjudication, ticketCardState,
  awaitingCount, recordCount,
  BOARD_ROW_CAP, listCap,
} from "./ticketCard.ts";

/* ------------------------------------------------------------ the maker --- */

let seq = 0;

/** A ticket with an INERT default shape, overridable field by field — copied
 *  from `ticketExceptions.test.ts`'s fixture-maker pattern. Defaults: `filed`,
 *  the chair's move, not decided, one hour old, no money, no citation. A test
 *  opts IN to whatever it is probing, so a rule that stops firing cannot pass
 *  a test by accident. */
function tk(over: Partial<Ticket> = {}): Ticket {
  seq += 1;
  const state = (over.state ?? "filed") as TicketState;
  return {
    ticket_id: over.ticket_id ?? `t-${seq}`,
    type: (over.type ?? "recommendation") as Ticket["type"],
    state,
    subject: over.subject ?? `subject ${seq}`,
    filed_for: over.filed_for ?? "builder",
    filed_by: over.filed_by ?? "cto",
    filed_at: over.filed_at ?? "2026-08-25T00:00:00+00:00",
    trace_id: over.trace_id ?? null,
    parent_id: over.parent_id ?? null,
    source: over.source ?? "deskstore.recommendations",
    transitions: over.transitions ?? [],
    refused_transitions: over.refused_transitions ?? [],
    terminal: over.terminal ?? false,
    next_actor: over.next_actor ?? "chair",
    next_actor_basis: over.next_actor_basis ?? "kind",
    next_actor_why: over.next_actor_why ?? "",
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

/* ================================================================= *
 * 1. isTerminal — the flag wins, the state list is the fallback only
 * ================================================================= */

test("the spine's terminal flag WINS over the state name, in both directions", () => {
  // A working-looking state explicitly flagged terminal must read terminal —
  // and a terminal-looking state explicitly flagged false must read open.
  // Neither direction may fall back to the state list once the flag exists.
  assert.equal(isTerminal({ terminal: true, state: "filed" }), true);
  assert.equal(isTerminal({ terminal: false, state: "done" }), false);
});

test("a MISSING flag falls back to the state list, and does not default open", () => {
  // The contract's own warning: a payload missing the flag must not default
  // to "still open". Simulate the flag genuinely absent from the payload
  // (not merely `undefined` as a key, but never set) via a cast — the runtime
  // check is `typeof t.terminal === "boolean"`.
  const noFlag = { state: "done" } as unknown as Pick<Ticket, "terminal" | "state">;
  assert.equal(isTerminal(noFlag), true);
  const noFlagOpen = { state: "filed" } as unknown as Pick<Ticket, "terminal" | "state">;
  assert.equal(isTerminal(noFlagOpen), false);
});

test("BOUNDARY TABLE: all five terminal states, flag absent, all read terminal", () => {
  assert.deepEqual(TERMINAL_STATES.length, 5);
  for (const state of TERMINAL_STATES) {
    const row = { state } as unknown as Pick<Ticket, "terminal" | "state">;
    assert.equal(isTerminal(row), true, `${state} must fall back to terminal`);
  }
});

test("BOUNDARY TABLE: all five working states, flag absent, all read open", () => {
  assert.deepEqual(WORKING_STATES.length, 5);
  for (const state of WORKING_STATES) {
    const row = { state } as unknown as Pick<Ticket, "terminal" | "state">;
    assert.equal(isTerminal(row), false, `${state} must fall back to open`);
  }
});

/* ==================================================================== *
 * 2 & 3. controls precedence, and countedAsAwaiting computed separately
 * ==================================================================== */

test("PRECEDENCE: terminal beats everything, even a decided CEO row", () => {
  // If terminal did not short-circuit first, this exact combination
  // (next_actor ceo, decided true) would read "execute" per rule 4.
  const c = ticketCardState(tk({
    terminal: true, state: "done", next_actor: "ceo", decided: true,
  }));
  assert.equal(c.controls, "none");
});

test("PRECEDENCE: next_actor 'nobody' is none, even when not terminal", () => {
  const c = ticketCardState(tk({ terminal: false, next_actor: "nobody" }));
  assert.equal(c.controls, "none");
});

test("PRECEDENCE: an actor that is neither ceo nor unknown is none — it is someone else's move", () => {
  const c = ticketCardState(tk({ next_actor: "chair" }));
  assert.equal(c.controls, "none");
});

test("PRECEDENCE: decided true, actor ceo, gives execute", () => {
  const c = ticketCardState(tk({ next_actor: "ceo", decided: true }));
  assert.equal(c.controls, "execute");
});

test("PRECEDENCE: decided true, actor UNKNOWN, still gives execute", () => {
  // `unknown` rides the same lane as `ceo` for control routing — it is only
  // excluded from the awaiting-actor attribution, never from the control
  // decision. A version that filtered `unknown` out earlier would report
  // "none" here instead.
  const c = ticketCardState(tk({ next_actor: "unknown", decided: true }));
  assert.equal(c.controls, "execute");
});

test("PRECEDENCE: decided false, actor ceo, gives decide", () => {
  const c = ticketCardState(tk({ next_actor: "ceo", decided: false }));
  assert.equal(c.controls, "decide");
});

test("PRECEDENCE: decided false, actor unknown, gives decide", () => {
  const c = ticketCardState(tk({ next_actor: "unknown", decided: false }));
  assert.equal(c.controls, "decide");
});

test("BOUNDARY TABLE: controls is always one of exactly three values", () => {
  const cases: Ticket[] = [
    tk({ terminal: true, state: "done" }),
    tk({ next_actor: "nobody" }),
    tk({ next_actor: "chair" }),
    tk({ next_actor: "ceo", decided: true }),
    tk({ next_actor: "ceo", decided: false }),
  ];
  const seen = new Set(cases.map((t) => ticketCardState(t).controls));
  for (const v of seen) {
    assert.ok(["decide", "execute", "none"].includes(v),
      `${v} is not one of the three control values`);
  }
  // And the five cases above must have produced all three, so the table is
  // not accidentally exercising only one branch.
  assert.deepEqual([...seen].sort(), ["decide", "execute", "none"]);
});

test("countedAsAwaiting and controls DIFFER on the chair's move — the whole "
  + "point of computing them separately", () => {
  // The chair's move: no control on this surface (it is not the CEO's
  // button), but somebody (the chair) genuinely owes an action, so the row
  // must still be counted as awaiting. One flag answering both questions is
  // exactly the D39 defect this file's docstring names.
  const c = ticketCardState(tk({ terminal: false, next_actor: "chair" }));
  assert.equal(c.controls, "none");
  assert.equal(c.countedAsAwaiting, true);
  assert.equal(c.awaitingActor, "chair");
});

test("countedAsAwaiting and controls also differ on a terminal CEO-routed row "
  + "— both are 'none'/'false' here, but for UNRELATED reasons", () => {
  // A row that WOULD have gone to the CEO's decide lane, except it is
  // terminal. controls=none from the terminal short-circuit; countedAsAwaiting
  // =false from the `!terminal` clause. Neither is derived from the other.
  const c = ticketCardState(tk({
    terminal: true, state: "done", next_actor: "ceo", decided: false,
  }));
  assert.equal(c.controls, "none");
  assert.equal(c.countedAsAwaiting, false);
  assert.equal(c.awaitingActor, null);
});

test("countedAsAwaiting is false for 'nobody' and for an empty actor, true otherwise", () => {
  assert.equal(ticketCardState(tk({ next_actor: "nobody" })).countedAsAwaiting, false);
  assert.equal(ticketCardState(tk({ next_actor: "" })).countedAsAwaiting, false);
  assert.equal(ticketCardState(tk({ next_actor: "ceo" })).countedAsAwaiting, true);
  assert.equal(ticketCardState(tk({ next_actor: "chair" })).countedAsAwaiting, true);
});

/* ============================================================= *
 * 4. controlsWhy is always non-empty, and branches never share a
 *    distinguishing phrase (the shared-word rule)
 * ============================================================= */

test("controlsWhy is non-empty across every branch of the precedence chain", () => {
  const rows: Ticket[] = [
    tk({ terminal: true, state: "done" }),
    tk({ next_actor: "nobody" }),
    tk({ next_actor: "chair" }),
    tk({ next_actor: "ceo", decided: true }),
    tk({ next_actor: "ceo", decided: false }),
  ];
  for (const t of rows) {
    const c = ticketCardState(t);
    assert.ok(c.controlsWhy.trim().length > 0,
      `empty controlsWhy for ${t.ticket_id}`);
  }
});

test("the terminal reason names the state's own label and 'terminal state' — "
  + "distinct from every other branch's wording (no other branch says "
  + "'terminal')", () => {
  const c = ticketCardState(tk({ terminal: true, state: "declined" }));
  assert.match(c.controlsWhy, /terminal state/);
  assert.match(c.controlsWhy, /Terminal is terminal/);
});

test("the 'nobody' reason, with no spine-supplied why, is the exact fallback "
  + "sentence — distinct from the terminal sentence and the 'not yours' one", () => {
  const c = ticketCardState(tk({ next_actor: "nobody", next_actor_why: "" }));
  assert.equal(c.controlsWhy, "Filed for the record — no decision is owed.");
});

test("the 'someone else's move' reason names the actor and says 'not yours' — "
  + "the word 'yours' does not appear in any other branch's fallback text", () => {
  const c = ticketCardState(tk({ next_actor: "chair", next_actor_why: "" }));
  assert.equal(c.controlsWhy, "This is the chair's move, not yours.");
});

test("the 'execute' reason says 'decided this already' and 'execution, not "
  + "another decision' — the word 'execution' appears in no other branch", () => {
  const c = ticketCardState(tk({
    next_actor: "ceo", decided: true, decided_at: null,
  }));
  assert.equal(c.controlsWhy,
    "You decided this already — what is owed is the execution, not another decision.");
});

test("the 'execute' reason appends the decided_at timestamp when present", () => {
  const c = ticketCardState(tk({
    next_actor: "ceo", decided: true, decided_at: "2026-08-20T00:00:00+00:00",
  }));
  assert.match(c.controlsWhy, /\(2026-08-20T00:00:00\+00:00\)/);
});

test("the 'decide' reason, with no spine why, is the exact fallback — "
  + "distinct from every branch above (says 'Your decision is owed', not "
  + "'not yours' and not 'execution')", () => {
  const c = ticketCardState(tk({
    next_actor: "ceo", decided: false, next_actor_why: "",
  }));
  assert.equal(c.controlsWhy, "Your decision is owed.");
});

test("a spine-supplied next_actor_why overrides the fallback text on the "
  + "branches that read it", () => {
  const notYours = ticketCardState(tk({
    next_actor: "chair", next_actor_why: "the chair must dispatch this first",
  }));
  assert.equal(notYours.controlsWhy, "the chair must dispatch this first");

  const decide = ticketCardState(tk({
    next_actor: "ceo", decided: false, next_actor_why: "your call, boss",
  }));
  assert.equal(decide.controlsWhy, "your call, boss");
});

/* ================================================== *
 * 5. ticketTitle
 * ================================================== */

test("a short string subject is not clamped and is not unreadable", () => {
  const title = ticketTitle("a normal subject line");
  assert.equal(title.line, "a normal subject line");
  assert.equal(title.tail, "");
  assert.equal(title.clamped, false);
  assert.equal(title.looksUnreadable, false);
  assert.equal(title.absent, false);
});

test("a subject longer than CARD_HEADLINE_MAX is clamped, and tail is never null", () => {
  const long = "word ".repeat(40).trim(); // well past the 87-char default
  assert.ok(long.length > CARD_HEADLINE_MAX);
  const title = ticketTitle(long);
  assert.equal(title.clamped, true);
  assert.ok(title.line.length <= CARD_HEADLINE_MAX + 1); // + the ellipsis glyph
  assert.notEqual(title.tail, null);
  assert.equal(typeof title.tail, "string");
  assert.ok(title.tail.length > 0);
});

test("a subject that starts '{' and ends '}' looks unreadable — the "
  + "Python-repr case", () => {
  const title = ticketTitle("{'run_id': 'run-1', 'rec': 7}");
  assert.equal(title.looksUnreadable, true);
  assert.equal(title.absent, false);
});

test("a NON-STRING subject (object) looks unreadable and never renders as "
  + "'[object Object]'", () => {
  const title = ticketTitle({ run_id: "run-1", rec: 7 });
  assert.equal(title.looksUnreadable, true);
  assert.ok(!title.line.includes("[object Object]"));
  assert.ok(!title.tail.includes("[object Object]"));
  // It renders the actual JSON, so the reader can see what is stored.
  assert.match(title.line, /run_id/);
});

test("a NON-STRING subject (number) also looks unreadable, never coerced silently", () => {
  const title = ticketTitle(42);
  assert.equal(title.looksUnreadable, true);
  assert.ok(!title.line.includes("[object Object]"));
});

test("null, undefined and whitespace-only subjects are absent, and NOT unreadable", () => {
  for (const subject of [null, undefined, "   ", ""]) {
    const title = ticketTitle(subject);
    assert.equal(title.absent, true, `${JSON.stringify(subject)} should be absent`);
    assert.equal(title.looksUnreadable, false,
      `${JSON.stringify(subject)} should not ALSO be flagged unreadable`);
  }
});

test("tail is a string, never null, across clamped, unclamped and absent subjects", () => {
  for (const subject of [null, undefined, "short", "word ".repeat(40)]) {
    const title = ticketTitle(subject);
    assert.equal(typeof title.tail, "string");
  }
});

/* ================================================== *
 * 6. ticketLamp — BOUNDARY TABLE across all four lamps
 * ================================================== */

test("BOUNDARY TABLE: every terminal state, flag set, lamps as 'record'", () => {
  for (const state of TERMINAL_STATES) {
    assert.equal(ticketLamp({ terminal: true, state }), "record",
      `${state} must lamp as record`);
  }
});

test("terminal wins over state name for the lamp too — an in_flight row "
  + "explicitly flagged terminal must still lamp 'record', not 'working'", () => {
  assert.equal(ticketLamp({ terminal: true, state: "in_flight" }), "record");
});

test("in_flight, not terminal, lamps 'working'", () => {
  assert.equal(ticketLamp({ terminal: false, state: "in_flight" }), "working");
});

test("returned, not terminal, lamps 'awaiting-review' — the middle state "
  + "the constitution says the floor used to render as indistinguishable "
  + "from a seat still thinking", () => {
  assert.equal(ticketLamp({ terminal: false, state: "returned" }), "awaiting-review");
});

test("BOUNDARY TABLE: the remaining working states (filed, approved, "
  + "accepted) all lamp 'idle'", () => {
  for (const state of ["filed", "approved", "accepted"] as const) {
    assert.equal(ticketLamp({ terminal: false, state }), "idle",
      `${state} must lamp idle`);
  }
});

test("the four lamps are pairwise distinct strings, so a UI switch cannot "
  + "collapse two of them by accident", () => {
  const lamps = new Set([
    ticketLamp({ terminal: true, state: "done" }),
    ticketLamp({ terminal: false, state: "in_flight" }),
    ticketLamp({ terminal: false, state: "returned" }),
    ticketLamp({ terminal: false, state: "filed" }),
  ]);
  assert.equal(lamps.size, 4);
});

/* ======================================================== *
 * 7. ticketAdjudication — null when undecided, reads lineage
 * ======================================================== */

test("an undecided ticket has no adjudication, however its other fields look", () => {
  const adj = ticketAdjudication(tk({
    decided: false, decided_state: "done", decided_by: "ceo",
    decided_at: "2026-08-20T00:00:00+00:00",
  }));
  assert.equal(adj, null);
});

test("a decided ticket reads decided_state/decided_by/decided_at/"
  + "decision_count/canonical_ticket_id — and NOT `state`", () => {
  const t = tk({
    state: "filed", // deliberately different from decided_state
    decided: true,
    decided_state: "accepted",
    decided_by: "ceo",
    decided_at: "2026-08-21T00:00:00+00:00",
    decision_count: 3,
    canonical_ticket_id: "t-canon",
  });
  const adj = ticketAdjudication(t)!;
  assert.equal(adj.state, "accepted", "must read decided_state, not `state`");
  assert.notEqual(adj.state, t.state);
  assert.equal(adj.actor, "ceo");
  assert.equal(adj.at, "2026-08-21T00:00:00+00:00");
  assert.equal(adj.count, 3);
  assert.equal(adj.canonicalTicketId, "t-canon");
});

test("a decided ticket with a non-number decision_count falls back to 0, "
  + "never to the ticket's other counters", () => {
  const t = tk({ decided: true, decision_count: undefined as unknown as number });
  const adj = ticketAdjudication(t)!;
  assert.equal(adj.count, 0);
});

test("ticketCardState's own adjudication field agrees with ticketAdjudication", () => {
  const t = tk({ decided: true, decided_state: "done", decided_by: "ceo" });
  const c = ticketCardState(t);
  assert.deepEqual(c.adjudication, ticketAdjudication(t));
});

/* ================================================== *
 * 8. citationOwed
 * ================================================== */

test("a terminal DONE ticket with no citation owes one", () => {
  const c = ticketCardState(tk({ terminal: true, state: "done", citation: null }));
  assert.equal(c.citationOwed, true);
  assert.equal(c.citation, null);
});

test("a terminal DONE ticket with a whitespace-only citation still owes one "
  + "— blank is not present", () => {
  const c = ticketCardState(tk({ terminal: true, state: "done", citation: "   " }));
  assert.equal(c.citationOwed, true);
  assert.equal(c.citation, null);
});

test("a terminal DONE ticket WITH a real citation owes nothing", () => {
  const c = ticketCardState(tk({
    terminal: true, state: "done", citation: "run-42 rec 3",
  }));
  assert.equal(c.citationOwed, false);
  assert.equal(c.citation, "run-42 rec 3");
});

test("a terminal ticket in a DIFFERENT terminal state never owes a citation "
  + "— the rule is specifically 'done', not 'any terminal'", () => {
  for (const state of ["declined", "superseded", "merged", "expired"] as const) {
    const c = ticketCardState(tk({ terminal: true, state, citation: null }));
    assert.equal(c.citationOwed, false, `${state} must not owe a citation`);
  }
});

test("a NON-terminal ticket in state 'done' (an inconsistent payload) owes nothing "
  + "— citationOwed requires terminal AND done together, not either alone", () => {
  const c = ticketCardState(tk({ terminal: false, state: "done", citation: null }));
  assert.equal(c.citationOwed, false);
});

/* ==================================================== *
 * 9. ageInStateHours / ageKnown — null/NaN/Infinity, never 0
 * ==================================================== */

test("a null age_in_state_hours gives ageKnown false and ageInStateHours null", () => {
  const c = ticketCardState(tk({ age_in_state_hours: null }));
  assert.equal(c.ageKnown, false);
  assert.equal(c.ageInStateHours, null);
});

test("a NaN age gives ageKnown false and ageInStateHours null, not NaN itself", () => {
  const c = ticketCardState(tk({ age_in_state_hours: NaN }));
  assert.equal(c.ageKnown, false);
  assert.equal(c.ageInStateHours, null);
});

test("an Infinity age gives ageKnown false and ageInStateHours null", () => {
  const c = ticketCardState(tk({ age_in_state_hours: Infinity }));
  assert.equal(c.ageKnown, false);
  assert.equal(c.ageInStateHours, null);
  const c2 = ticketCardState(tk({ age_in_state_hours: -Infinity }));
  assert.equal(c2.ageKnown, false);
  assert.equal(c2.ageInStateHours, null);
});

test("a genuine ZERO age is known and renders as 0, not as the unknown case — "
  + "the contract's 'never 0' is about UNKNOWN never rendering as 0, not "
  + "about a real 0 being forbidden", () => {
  const c = ticketCardState(tk({ age_in_state_hours: 0 }));
  assert.equal(c.ageKnown, true);
  assert.equal(c.ageInStateHours, 0);
});

test("a finite positive age is known and passes through unchanged", () => {
  const c = ticketCardState(tk({ age_in_state_hours: 12.5 }));
  assert.equal(c.ageKnown, true);
  assert.equal(c.ageInStateHours, 12.5);
});

/* ==================================================== *
 * 10. awaitingCount / recordCount
 * ==================================================== */

test("awaitingCount counts countedAsAwaiting, NOT rows that render a button", () => {
  // Two rows: one is the chair's move (no button, but awaiting), one is the
  // CEO's own decide lane (a button, and also awaiting). A count of "rows
  // with a button" would read 1; the correct count is 2.
  const rows = [
    tk({ ticket_id: "chairs-move", next_actor: "chair" }),
    tk({ ticket_id: "ceo-decide", next_actor: "ceo", decided: false }),
  ];
  assert.equal(awaitingCount(rows), 2);
  const withButton = rows.filter((t) => ticketCardState(t).controls !== "none").length;
  assert.equal(withButton, 1, "sanity: only one of the two rows has a button");
});

test("awaitingCount excludes terminal rows and 'nobody' rows", () => {
  const rows = [
    tk({ terminal: true, state: "done", next_actor: "ceo" }),
    tk({ next_actor: "nobody" }),
    tk({ next_actor: "ceo" }),
  ];
  assert.equal(awaitingCount(rows), 1);
});

test("recordCount counts terminals, independent of next_actor", () => {
  const rows = [
    tk({ terminal: true, state: "done", next_actor: "ceo" }),
    tk({ terminal: true, state: "expired", next_actor: "chair" }),
    tk({ terminal: false, state: "filed" }),
  ];
  assert.equal(recordCount(rows), 2);
});

test("an empty population gives awaitingCount 0 and recordCount 0, not NaN", () => {
  assert.equal(awaitingCount([]), 0);
  assert.equal(recordCount([]), 0);
});

/* ================================================== *
 * ticketCardState — a few end-to-end field sanity checks
 * ================================================== */

test("ticketCardState's stateLabel matches STATE_LABEL for every state", () => {
  for (const state of [...TERMINAL_STATES, ...WORKING_STATES]) {
    const c = ticketCardState(tk({ state, terminal: TERMINAL_STATES.includes(state) }));
    assert.equal(c.stateLabel, STATE_LABEL[state]);
  }
});

test("ticketCardState's lamp field agrees with the standalone ticketLamp function", () => {
  const t = tk({ state: "returned", terminal: false });
  assert.equal(ticketCardState(t).lamp, ticketLamp(t));
});

/* --------------------------------------------------------- the list cap --- */

test("a capped list says how many are NOT on screen", () => {
  // THE DEFECT, FOUND ON THE RENDERED BOARD: the header read "showing 369 of
  // 713" over a list that drew 200. Both numbers were true about something and
  // neither was true about what was on screen — the exact shape of the
  // truncation that lost the CEO a $915 item on his own desk.
  const c = listCap(369, 713, 200);
  assert.equal(c.shown, 200);
  assert.equal(c.matched, 369);
  assert.equal(c.hidden, 169);
  assert.equal(c.capped, true);
  assert.match(c.note, /showing 200 of 369 matching rows — 169 are NOT on screen/);
  assert.match(c.note, /713 ticket\(s\) in the fold/);
});

test("an uncapped list says it is showing everything, and does not warn", () => {
  const c = listCap(12, 713, 200);
  assert.equal(c.shown, 12);
  assert.equal(c.hidden, 0);
  assert.equal(c.capped, false);
  assert.match(c.note, /showing all 12 matching row\(s\)/);
  assert.doesNotMatch(c.note, /NOT on screen/);
});

test("the cap boundary is exact — at the cap nothing is hidden", () => {
  const at = listCap(200, 713, 200);
  const over = listCap(201, 713, 200);
  assert.equal(at.capped, false, "exactly the cap is not a truncation");
  assert.equal(at.hidden, 0);
  assert.equal(over.capped, true);
  assert.equal(over.hidden, 1, "one row over is one row hidden, and it is said");
});

test("an empty list is a real answer, never a truncation", () => {
  const c = listCap(0, 713, 200);
  assert.equal(c.shown, 0);
  assert.equal(c.capped, false);
  assert.match(c.note, /showing all 0 matching row\(s\) of 713/);
});

test("the cap has a named default, so a page cannot invent one inline", () => {
  assert.equal(typeof BOARD_ROW_CAP, "number");
  assert.equal(listCap(1000, 1000).shown, BOARD_ROW_CAP);
  assert.equal(listCap(1000, 1000).hidden, 1000 - BOARD_ROW_CAP);
});

test("MUTANT M26: an UNCLOSED brace is not a repr — both ends are checked", () => {
  // DROPPING `endsWith("}")` SURVIVED THE WHOLE SUITE: no test carried a
  // subject that opens a brace and never closes one. The looser check would
  // flag a legitimate sentence beginning "{" as a broken row, and a false
  // "this row is broken" costs the reader the same trust a missed one does.
  assert.equal(ticketTitle("{'id': 'E20-1'}").looksUnreadable, true);
  assert.equal(ticketTitle("{unclosed and never closed").looksUnreadable, false);
  assert.equal(ticketTitle("closed but never opened}").looksUnreadable, false);
});
