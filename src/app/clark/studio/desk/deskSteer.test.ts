import test from "node:test";
import assert from "node:assert/strict";

import { daysUntil, steeringSentence } from "./deskSteer.ts";
import type { CeoDeskView, DeskEngineItem } from "@/lib/fund_api";

/**
 * THE ONE STEERING SENTENCE.
 *
 * Two defects these tests exist to make impossible, both from this desk's own
 * history:
 *
 *  1. **A SECOND RANKING.** The desk has shipped one-quantity-computed-twice
 *     three times (11 vs 6, 1 vs 0, 96 vs 97). A steer that re-sorted the
 *     served rows would be the fourth, and it would be the worst of the four
 *     because it would look like advice. The MOVE test below is what proves
 *     the module READS the spine's order rather than agreeing with it by
 *     coincidence: the fixture's served order deliberately contradicts the
 *     money order, and the steer must follow the served one.
 *  2. **A FABRICATED PRIORITY.** Measured on the live spine 2026-08-23: 11 of
 *     28 rows awaiting the CEO state neither a date nor a figure, so their
 *     order is arrival order. Calling one of them "the one that needs you
 *     most" is unfalsifiable and authoritative-looking, which is the worst
 *     combination on a decision surface.
 */

function item(over: Partial<DeskEngineItem> = {}): DeskEngineItem {
  return {
    source: "recommendation", ref: "rec:run-x#1", seat: "pm",
    title: "a row", kind: "k", status: "open",
    due_date: null, money_at_stake: null, reversibility: "reversible",
    next_actor_resolved: "ceo", next_actor_basis: "explicit",
    at: "2026-08-23T08:00:00+00:00", supersession: null,
    ...over,
  };
}

function view(items: DeskEngineItem[], over: Record<string, unknown> = {}) {
  return {
    at: "2026-08-23T12:00:00+00:00",
    rules_version: "v1",
    greeting: { at: null, since: null, changed: "", needs_you: "",
                on_fire: "", hygiene: null, text: "" },
    decisions: {
      shown: items.length, total: items.length, truncated: false,
      ranked_by: "due_date, then money_at_stake — absent last on both",
      ranked_on_nothing: items.filter(
        (i) => !i.due_date && typeof i.money_at_stake !== "number").length,
      items, note: "",
      ...(over.decisions as object ?? {}),
    },
    on_fire: { shown: 0, total: 0, items: [], risk_halted: false, definition: "" },
    briefings: null,
    matrix: { categories: [], definitions: {}, seats: [], cells: {}, totals: {},
              items_classified: 0, cell_limit: 25, note: "" },
    hygiene: null,
    blocked: { shown: 0, total: 0, items: [], note: "" },
    kill_shelf: { shown: 0, total: 0, items: [], note: "" },
    elsewhere: { by_actor: {}, by_source: {} },
    readable: { recommendations: true, supersessions: true, intray: true, risk: true },
  } as unknown as CeoDeskView;
}

/* ------------------------------------------------------------ the MOVE --- */

test("the steer FOLLOWS the served order, it does not re-derive one", () => {
  /* THE MOVE TEST. The row the spine put first states a small figure; the row
   * behind it states a figure sixty times larger. A module that ranked by
   * money would pick the second and would still 'agree with the data'. Only
   * following the served order gives the first.
   *
   * Stated as a rule: an assertion that this module's answer equals the
   * biggest number cannot distinguish reading from re-ranking. Moving the
   * biggest number away from position zero can. */
  const s = steeringSentence({
    read: "readable",
    view: view([
      item({ title: "the spine put this first", money_at_stake: 25 }),
      item({ ref: "rec:run-x#2", title: "sixty times the money",
             money_at_stake: 1500 }),
    ]),
    needsYou: 2,
  });
  assert.equal(s.basis, "money");
  assert.ok(s.text.includes("the spine put this first"),
    "the steer must name the row the SPINE ranked first, not the largest "
    + "figure — a second comparator here is the fourth instance of this "
    + "desk's oldest defect");
  assert.ok(!s.text.includes("sixty times the money"));
});

test("a dated row beats a priced one only because the SPINE said so", () => {
  /* The spine's own key order is date, then money. This fixture puts the
   * dated row second on purpose: the steer must NOT promote it. */
  const s = steeringSentence({
    read: "readable",
    view: view([
      item({ title: "priced, undated", money_at_stake: 900 }),
      item({ ref: "rec:run-x#2", title: "dated, unpriced",
             due_date: "2026-08-24" }),
    ]),
    needsYou: 2,
  });
  assert.equal(s.basis, "money");
  assert.ok(s.text.includes("priced, undated"));
});

/* --------------------------------------------------------- the branches -- */

test("a dated top row steers on the date, with the days spelled out", () => {
  const mk = (due: string) => steeringSentence({
    read: "readable",
    view: view([item({ title: "T", due_date: due, money_at_stake: 1748.92 })]),
    needsYou: 1,
  });
  assert.match(mk("2026-08-21").text, /2 days OVERDUE/);
  assert.equal(mk("2026-08-21").overdue, true);
  assert.match(mk("2026-08-23").text, /due TODAY/);
  assert.equal(mk("2026-08-23").overdue, true, "today is not tomorrow");
  assert.match(mk("2026-08-24").text, /due tomorrow/);
  assert.equal(mk("2026-08-24").overdue, false);
  assert.match(mk("2026-08-30").text, /due in 7 days/);
  // The money rides along on a dated row; it does not replace the date.
  assert.match(mk("2026-08-24").text, /\$1,748\.92 at stake/);
  assert.equal(mk("2026-08-24").basis, "due_date");
});

test("one day overdue is singular, and the sign is not lost", () => {
  const s = steeringSentence({
    read: "readable",
    view: view([item({ due_date: "2026-08-22" })]), needsYou: 1 });
  assert.match(s.text, /1 day OVERDUE/);
  assert.ok(!s.text.includes("-1"), "the minus sign must not reach the reader");
});

test("a priced top row says so, and says nothing above it is dated", () => {
  const s = steeringSentence({
    read: "readable",
    view: view([item({ title: "R39", money_at_stake: 1748.92 })]),
    needsYou: 1,
  });
  assert.equal(s.basis, "money");
  assert.match(s.text, /\$1,748\.92/);
  assert.match(s.text, /nothing above it states a date/);
  assert.equal(s.overdue, false);
});

test("a top row stating NEITHER refuses to name one, and says why", () => {
  /* THE HONEST BRANCH, and the one the live desk is actually in. */
  const s = steeringSentence({
    read: "readable",
    view: view([item({ title: "unranked" }), item({ ref: "r2" })]),
    needsYou: 2,
  });
  assert.equal(s.basis, "unranked");
  assert.equal(s.item, null,
    "naming a row here would be a fabricated priority — the position is "
    + "arrival order and the module must not dress it as urgency");
  assert.ok(!s.text.includes("unranked\""));
  assert.match(s.text, /2 of 2 state neither/);
  assert.match(s.text, /arrival order/);
  assert.match(s.text, /not a quiet desk/);
});

test("an unstated ranked_on_nothing is 'some of them', never a zero", () => {
  const v = view([item()]);
  // A spine that predates the field. Absence is never zero.
  delete (v.decisions as unknown as Record<string, unknown>).ranked_on_nothing;
  const s = steeringSentence({ read: "readable", view: v, needsYou: 1 });
  assert.equal(s.basis, "unranked");
  assert.match(s.text, /some of them state neither/);
  assert.ok(!/0 of/.test(s.text));
});

/* ------------------------------------------------------- the absences ---- */

test("no view at all is UNKNOWN, never 'nothing to do'", () => {
  const s = steeringSentence({ view: null, read: "unreadable", needsYou: 12 });
  assert.equal(s.basis, "unknown");
  assert.match(s.text, /UNKNOWN/);
  assert.ok(!/nothing/i.test(s.text.replace("not nothing", "")),
    "an unreadable engine must never render as a clear desk");
});

test("an empty ranked list beside a non-zero counter is a DISAGREEMENT", () => {
  const s = steeringSentence({ read: "readable", view: view([]), needsYou: 7 });
  assert.equal(s.basis, "none");
  assert.match(s.text, /7 await you/);
  assert.match(s.text, /disagree/);
});

test("an empty ranked list beside a zero counter is simply quiet", () => {
  const s = steeringSentence({ read: "readable", view: view([]), needsYou: 0 });
  assert.equal(s.basis, "none");
  assert.match(s.text, /Nothing is ranked for you/);
  assert.ok(!/disagree/.test(s.text));
});

test("a truncated page says the steer is over the PAGE, not the queue", () => {
  const v = view([item({ money_at_stake: 10 })],
                 { decisions: { shown: 1, total: 40, truncated: true } });
  const s = steeringSentence({ read: "readable", view: v, needsYou: 40 });
  assert.match(s.text, /capped at 1 of 40/);
  // And the unranked branch carries it too — a cap does not stop mattering
  // because the top row happens to be unrankable.
  const v2 = view([item()], { decisions: { shown: 1, total: 40, truncated: true } });
  assert.match(steeringSentence({ read: "readable", view: v2, needsYou: 40 }).text,
               /capped at 1 of 40/);
});

test("truncated:true with nothing actually cut says nothing", () => {
  /* `truncated` and `total > shown` are two claims and the second is the one
   * a reader can act on. A page flagged truncated that holds every row would
   * otherwise print a caveat about nothing. */
  const v = view([item({ money_at_stake: 10 })],
                 { decisions: { shown: 1, total: 1, truncated: true } });
  assert.ok(!/capped at/.test(steeringSentence({ read: "readable", view: v, needsYou: 1 }).text));
});

test("a long title is clamped, and the clamp is visible", () => {
  const long = "x".repeat(400);
  const s = steeringSentence({
    read: "readable",
    view: view([item({ title: long, money_at_stake: 1 })]), needsYou: 1 });
  assert.ok(s.text.length < 400, "an unclamped COO batch title is 200+ chars");
  assert.ok(s.text.includes("…"), "the clamp must be visible, never silent");
});

test("a row with no text says so rather than rendering a blank", () => {
  const s = steeringSentence({
    read: "readable",
    view: view([item({ title: null, money_at_stake: 5 })]), needsYou: 1 });
  assert.match(s.text, /this row carries no text/);
});

/* ------------------------------------------------------------ the days --- */

test("daysUntil is UTC calendar arithmetic and survives the boundaries", () => {
  assert.equal(daysUntil("2026-09-01", "2026-08-31T23:59:59+00:00"), 1);
  assert.equal(daysUntil("2026-01-01", "2025-12-31T00:00:01+00:00"), 1,
    "a year boundary must not become 366 or 0");
  assert.equal(daysUntil("2026-03-01", "2026-02-28T12:00:00+00:00"), 1,
    "2026 is not a leap year");
  assert.equal(daysUntil("2026-08-23", "2026-08-23T00:00:00+00:00"), 0);
  assert.equal(daysUntil("2026-08-23", "2026-08-23T23:59:59+00:00"), 0,
    "the time of day must not move the calendar-day answer");
});

test("an unparseable date or instant is null, never a number", () => {
  assert.equal(daysUntil("soon", "2026-08-23T00:00:00+00:00"), null);
  assert.equal(daysUntil("2026-8-3", "2026-08-23T00:00:00+00:00"), null,
    "the desk's date format is YYYY-MM-DD; a loose parse is how a malformed "
    + "date sorted lexicographically against real ones");
  assert.equal(daysUntil("2026-08-23", ""), null);
  assert.equal(daysUntil("2026-08-23", "not a time"), null);
});

test("an unparseable due date still steers on the date, saying only its value", () => {
  /* The row IS dated — the spine stored something in `due_date` — so the
   * basis is the date. What the module must not do is invent a day count. */
  const s = steeringSentence({
    read: "readable",
    view: view([item({ due_date: "2026-8-3" })]), needsYou: 1 });
  assert.equal(s.basis, "due_date");
  assert.match(s.text, /dated 2026-8-3/);
  assert.equal(s.overdue, false, "an unreadable date is not an overdue one");
});
