import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

import {
  awaitingHeadline, deskShelves, heroFigure, shelfAbsenceNote,
} from "./deskAwaiting.ts";
import { deskLanes, laneCount, decidedCount, laneGlyph } from "./deskLanes.ts";
import { steeringSentence } from "./deskSteer.ts";
import { readState } from "./deskRead.ts";
import type { CeoDeskView, DeskView } from "@/lib/fund_api";

/**
 * TICKET fccb9cf3 — LOADING IS NOT UNREADABLE.
 *
 * THE INCIDENT, reported by the CEO from his own desk on 2026-08-24: during
 * the recompile that followed the D42 merge, the page sat for about thirty
 * seconds saying *"The desk could not be read… UNKNOWN — not none"* while
 * every fetch behind it was still PENDING. Nothing had failed. The fund's
 * loudest honesty sentence — the one reserved for "we asked and could not find
 * out" — was being printed for "we have not been answered yet".
 *
 * Every test in this file fails if that behaviour returns, and each one names
 * the surface it guards. THE OTHER HALF IS GUARDED TOO, and deliberately in
 * the same file: for every loading assertion there is an unreadable assertion
 * a few lines away holding the failure language EXACTLY as it shipped. A fix
 * that quieted the failure case as well would be a loosening of the absence
 * discipline wearing this ticket's clothes, and it would pass a file that only
 * tested the new state.
 *
 * WHAT MAKES THESE TESTS UNABLE TO BLESS THE BUG: the two states are asserted
 * against DIFFERENT, non-overlapping vocabulary. "could not be read" and
 * "UNKNOWN" belong to the failure branch and to nothing else; "Reading" and
 * "not been counted yet" belong to the loading branch and to nothing else.
 * A single branch that produced one string for both inputs would fail one of
 * every pair below, whichever way it collapsed.
 */

/* --------------------------------------------------------------- fixtures */

const NOW = "2026-08-24T09:00:00+00:00";

/** The smallest desk payload the lanes will fold. Never used for a loading
 *  case — a loading read has no payload by construction, which is the point. */
function desk(): DeskView {
  return {
    open_recommendations: [], requests: [], runs: [], roster: [],
    artifacts: [], desk_load: {}, open_requests: 0, kills: 0,
    execution_note: "", note: "",
  } as unknown as DeskView;
}

function engineView(): CeoDeskView {
  return {
    at: NOW,
    decisions: {
      items: [{ title: "a dated row", due_date: "2026-08-24",
                money_at_stake: 100 }],
      total: 1, shown: 1, truncated: false, ranked_on_nothing: 0,
      ranked_by: "due_date",
    },
  } as unknown as CeoDeskView;
}

/* -------------------------------------------------------- 0. the two glyphs */

test("fccb9cf3: heroFigure renders three different things for three different "
  + "facts, and the number for a number", () => {
  const h = (over: Record<string, unknown>) => ({
    value: null, atLeast: false, source: "spine", note: null,
    reconciliation: null, ...over,
  } as Parameters<typeof heroFigure>[0]);
  assert.equal(heroFigure(h({ value: 57 })), "57");
  assert.equal(heroFigure(h({ value: 0 })), "0",
    "a MEASURED zero is a number and must render as one");
  assert.equal(heroFigure(h({ source: "unknown" })), "unknown");
  assert.equal(heroFigure(h({ source: "loading" })), "…",
    "the whole ticket: a pending read must not wear the failure's word");
  assert.notEqual(heroFigure(h({ source: "loading" })),
    heroFigure(h({ source: "unknown" })),
    "if these two ever agree, the CEO is back to reading an outage that is "
    + "not happening");
});

test("fccb9cf3: the FLOOR suffix rides a real figure only — there is no floor "
  + "under a number that does not exist", () => {
  const h = (over: Record<string, unknown>) => ({
    value: null, atLeast: true, source: "spine", note: null,
    reconciliation: null, ...over,
  } as Parameters<typeof heroFigure>[0]);
  assert.equal(heroFigure(h({ value: 12 })), "12+");
  assert.equal(heroFigure(h({ source: "loading" })), "…",
    "never `…+`");
  assert.equal(heroFigure(h({ source: "unknown" })), "unknown",
    "never `unknown+`");
});

test("fccb9cf3: laneGlyph makes the same distinction in the lane headers, "
  + "where five of them said `unknown` at once", () => {
  const c = (over: Record<string, unknown>) =>
    ({ value: null, shown: 0, source: "unknown", note: null, ...over }) as
      Parameters<typeof laneGlyph>[0];
  assert.equal(laneGlyph(c({ value: 40, source: "spine" })), "40");
  assert.equal(laneGlyph(c({ value: 0, source: "page" })), "0");
  assert.equal(laneGlyph(c({ source: "unknown" })), "unknown");
  assert.equal(laneGlyph(c({ source: "loading" })), "…");
});

/* ------------------------------------------------- 1. the hero and its fold */

test("fccb9cf3: the HEADLINE while the desk read is in flight says it is "
  + "reading, and does not say the desk could not be read", () => {
  const h = awaitingHeadline({
    read: "loading", divertedNotes: 0, cardCount: 0,
  });
  assert.equal(h.value, null, "no number — the read has not answered");
  assert.equal(h.source, "loading",
    "`unknown` is the word for a read that FAILED; this one has not");
  assert.match(h.note!, /Reading the desk/);
  assert.ok(!/could not be read/.test(h.note!),
    "this is the exact sentence the CEO watched for thirty seconds");
  assert.ok(!/UNKNOWN/.test(h.note!),
    "UNKNOWN is a finding about the world, and none has been made yet");
});

test("fccb9cf3: and the FAILED read keeps every word of its loud sentence — "
  + "the fix splits the two states, it does not quiet the real one", () => {
  const h = awaitingHeadline({
    read: "unreadable", divertedNotes: 0, cardCount: 0,
  });
  assert.equal(h.value, null);
  assert.equal(h.source, "unknown");
  assert.equal(h.note,
    "The desk could not be read, so what awaits you is UNKNOWN, not none. "
    + "Anything waiting is still waiting.",
    "byte-identical to what shipped before this ticket");
});

test("fccb9cf3: a loading read NEVER falls through to the page's own fold, "
  + "even when the page happens to hold cards", () => {
  /* THE HAZARD THIS PINS. The loading branch is checked before the
   * served-figure branch. Move it after, and a loading read with no served
   * total drops into "counted by this page" and renders `cardCount` — a
   * confident number for a question nobody has answered. */
  const h = awaitingHeadline({
    read: "loading", servedTotal: null, divertedNotes: 0, cardCount: 9,
  });
  assert.equal(h.value, null, "9 cards in hand is not an answer to 'how many "
    + "await you' when the fold that decides it has not returned");
  assert.equal(h.source, "loading");
});

/* ---------------------------------------------------------- 2. the shelves */

test("fccb9cf3: the shelf line has NO shelves while the read is in flight — "
  + "a partition of a number nobody has yet is not four zeroes", () => {
  assert.equal(deskShelves("loading", [], 0, "2026-08-24"), null);
  assert.equal(
    deskShelves("loading", [{ dueDate: "2026-08-24", executionYours: false }],
      3, "2026-08-24"),
    null, "rows in hand do not make the partition final");
});

test("fccb9cf3: the sentence that replaces the shelves says WHICH absence it "
  + "is — the two branches swapped under mutation with the suite green while "
  + "they lived in the page's JSX", () => {
  const loading = shelfAbsenceNote("loading");
  const failed = shelfAbsenceNote("unreadable");
  assert.match(loading, /Reading the desk/);
  assert.ok(!/could not be read/.test(loading),
    "the pending sentence must not borrow the failure's words");
  assert.match(failed, /The desk could not be read/);
  assert.ok(!/Reading the desk/.test(failed),
    "and the failure must not borrow the pending one's — 'Reading…' for a "
    + "read that already failed is a progress bar for nothing in progress");
  assert.notEqual(loading, failed);
});

test("fccb9cf3: an unreadable desk still has no shelves (unchanged), and a "
  + "READABLE one still returns real zeroes", () => {
  assert.equal(deskShelves("unreadable", [], 0, "2026-08-24"), null);
  assert.deepEqual(deskShelves("readable", [], 0, "2026-08-24"),
    { decideToday: 0, exec: 0, asks: 0, noDeadline: 0 },
    "an empty desk that WAS read is a measurement and must survive the fix");
});

/* ------------------------------------------------------------ 3. the lanes */

test("fccb9cf3: all five lanes say they are being read, not that they are "
  + "UNKNOWN, while the desk fetch is in flight", () => {
  const ls = deskLanes({
    desk: null, read: "loading", awaitingShown: 0, awaitingServed: null,
    blocked: new Map(), now: NOW,
  });
  assert.equal(ls.length, 5);
  for (const l of ls) {
    assert.equal(l.count.value, null, `${l.id} must render no number`);
    assert.equal(l.count.source, "loading", `${l.id} is not a finding yet`);
    assert.match(l.count.note!, /Reading the desk/, l.id);
    assert.ok(!/Neither the fund nor this page could count/.test(l.count.note!),
      `${l.id} claimed an outage while the read was pending`);
  }
});

test("fccb9cf3: the UNREADABLE lanes keep their sentence exactly — this is "
  + "the assertion that stops the fix from swallowing the real state", () => {
  const ls = deskLanes({
    desk: null, read: "unreadable", awaitingShown: 0, awaitingServed: null,
    blocked: new Map(), now: NOW,
  });
  for (const l of ls) {
    assert.equal(l.count.value, null, `${l.id} must be UNKNOWN, not 0`);
    assert.equal(l.count.source, "unknown");
    assert.match(l.count.note!, /Neither the fund nor this page could count/);
    assert.match(l.count.note!, /UNKNOWN — not none/);
    assert.match(l.count.note!, /Anything waiting is still waiting/);
  }
});

test("fccb9cf3: a READABLE desk still renders its zeroes and its own sentence "
  + "— the third state must not have eaten the first", () => {
  const ls = deskLanes({
    desk: desk(), read: "readable", awaitingShown: 0, awaitingServed: 0,
    blocked: new Map(), now: NOW,
  });
  const resolved = ls.find((l) => l.id === "resolved")!;
  assert.equal(resolved.count.value, 0, "read and empty is a real zero");
  assert.equal(resolved.count.source, "page");
});

test("fccb9cf3: `loading` OUTRANKS a served figure in laneCount — a read that "
  + "has not returned cannot have served a number, and the honest answer to "
  + "that contradiction is the state that is certainly true", () => {
  const c = laneCount(162, 0, "decided work", "loading");
  assert.equal(c.value, null,
    "rendering 162 here would be printing a figure from a payload the page "
    + "has just declared it does not have");
  assert.equal(c.source, "loading");
});

test("fccb9cf3: decidedCount passes the loading state through instead of "
  + "computing its remainder sentence over rows it has not read", () => {
  const c = decidedCount(169, 0, 0, "loading");
  assert.equal(c.value, null);
  assert.equal(c.source, "loading");
  assert.match(c.note!, /Reading the desk/);
  assert.ok(!/decided in all/.test(c.note!),
    "the like-with-like remainder sentence is a claim about rows on screen");
});

/* ------------------------------------------------------------ 4. the steer */

test("fccb9cf3: the steering sentence is quiet while the ENGINE read is in "
  + "flight, and never says the engine could not be read", () => {
  const s = steeringSentence({ view: null, read: "loading", needsYou: null });
  assert.equal(s.basis, "loading");
  assert.equal(s.overdue, false, "a pending read is not an overdue anything");
  assert.equal(s.item, null);
  assert.match(s.text, /Reading the desk engine/);
  assert.ok(!/could not be read/.test(s.text));
  assert.ok(!/UNKNOWN/.test(s.text));
});

test("fccb9cf3: the FAILED engine read keeps its UNKNOWN sentence, unchanged",
  () => {
    const s = steeringSentence({
      view: null, read: "unreadable", needsYou: 12,
    });
    assert.equal(s.basis, "unknown");
    assert.equal(s.text,
      "The desk engine could not be read, so what to look at first is "
      + "UNKNOWN — not nothing.");
  });

test("fccb9cf3: a view that HAS arrived is steered on, whatever the read "
  + "state claims — the loading branch guards an absent view, not a present "
  + "one, and this is what makes that clause load-bearing", () => {
  /* Without the `&& !view` in the loading guard, a caller holding a payload
   * and a stale `loading` flag would be told "not worked out yet" about a
   * ranking that is sitting in its hand. */
  const s = steeringSentence({
    view: engineView(), read: "loading", needsYou: 1,
  });
  assert.equal(s.basis, "due_date");
  assert.match(s.text, /Start here/);
});

/* ------------------------------------ 5. the pages read the state, not null */

const CEO = readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8");
const SEAT = readFileSync(new URL("./[seat]/page.tsx", import.meta.url), "utf8");
const OFFICE = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");
/** Comment-stripped, because this repo has already shipped a source test that
 *  passed on prose (D20/D28) — a rule named in a comment is not a rule. */
const strip = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");

test("fccb9cf3 (null test for the three source checks below): each page still "
  + "contains the landmark those checks are about", () => {
  assert.ok(strip(CEO).includes("readState("), "the CEO desk derives a state");
  assert.ok(strip(SEAT).includes("readState("), "the seat page derives one");
  assert.ok(strip(OFFICE).includes("readState("), "the office derives one");
});

test("fccb9cf3: the CEO desk derives THREE read states — one per endpoint — "
  + "because the desk, the engine and the event log fail separately", () => {
  const src = strip(CEO);
  for (const [name, got, failed] of [
    ["deskRead", "desk !== null", "err !== null"],
    ["engineRead", "engine !== null", "engineErr"],
    ["eventsRead", "events !== null", "eventsErr"],
  ] as const) {
    assert.ok(src.includes(`const ${name} = readState(${got}, ${failed})`),
      `${name} must be derived from its own payload AND its own failure flag; `
      + "the failure flag is what separates 'not yet' from 'not ever'");
  }
});

test("fccb9cf3: EVERY page passes its OWN failure flag — a literal there is a "
  + "page that can never report a failed read, and it survived the first "
  + "mutation pass on two of the three", () => {
  /* The mutant is `readState(x !== null, false)`: the suite stayed green
   * because nothing asserted what the SECOND argument was. A page wired that
   * way renders "reading…" for ever over a dead spine — the ticket's own
   * defect with its polarity reversed, which is the worse direction. */
  const wiring: [string, string][] = [
    [strip(OFFICE), "readState(d !== null, err !== null)"],
    [strip(SEAT), "readState(desk !== null, deskErr !== null)"],
    [strip(CEO), "readState(desk !== null, err !== null)"],
  ];
  for (const [src, call] of wiring) {
    assert.ok(src.includes(call), `expected the wiring \`${call}\``);
  }
  for (const [src] of wiring) {
    assert.ok(!/readState\([^)]*,\s*(false|true)\s*\)/.test(src),
      "a literal second argument means the failed state is unreachable");
  }
});

test("fccb9cf3: the CEO desk HANDS its derived state to the two folds that "
  + "choose a sentence from it — a literal argument there renders one state's "
  + "words in both, which is the ticket, and it survived a mutation pass", () => {
  /* THE CEILING THIS TEST SITS AT, stated rather than implied: node's runner
   * refuses `.tsx`, so a call inside JSX can only be checked as source text.
   * The rendered proof for these two lines is the browser pass in the
   * dispatch report, not this file. */
  const src = strip(CEO);
  assert.ok(src.includes("{shelfAbsenceNote(deskRead)}"),
    "the shelf sentence must be chosen from the state the page derived");
  assert.ok(!/shelfAbsenceNote\(\s*"/.test(src),
    "a literal read state pins the sentence to one branch for ever");
  assert.ok(src.includes("{heroFigure(headline)}"),
    "and the hero figure from the one fold");
});

test("fccb9cf3: no page decides an UNREADABLE sentence from a bare null any "
  + "more — the expression that caused the incident is gone from the CEO "
  + "desk's shelf line, its lane (a) and the seat page's ask list", () => {
  const ceo = strip(CEO);
  assert.ok(!ceo.includes("deskReadable: desk !== null"),
    "the headline fold read the null directly; that IS the defect");
  assert.ok(!/deskShelves\(\s*desk !== null/.test(ceo),
    "the shelf line partitioned on the null directly");
  assert.ok(ceo.includes('deskRead === "loading"'),
    "the page must branch on the state it derived, or deriving it is theatre");
  const seat = strip(SEAT);
  assert.ok(!seat.includes("{desk == null && runs != null"),
    "the artifact-fold warning fired on a pending desk read");
});
