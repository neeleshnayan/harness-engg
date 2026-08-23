/**
 * ONE FOLD FOR "WHAT AWAITS YOU" — the test that fails if the desk goes back
 * to rendering two numbers for one question.
 *
 * THE INCIDENT, named: on 2026-08-23 the live CEO desk rendered "96 awaiting
 * your decision" with "97 / 50 AWAITING YOU" on the line beneath it. 96 was
 * the page's own fold, 97 the counter the spine serves; the difference was one
 * of Donna's notes, which is the ONE known divergence and is therefore exactly
 * the case the existing drift warning stays silent about. So the page's own
 * guard was correctly quiet at the moment two different numbers were on
 * screen, and nothing else was watching.
 *
 * Third instance of a quantity computed twice on this desk (11 vs 6, then
 * 1 vs 0, then 96 vs 97). The first two were fixed by pinning the two
 * computations together; this one removes the second computation.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskAwaiting.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import { awaitingHeadline, chipShowsTotal } from "./deskAwaiting.ts";
import { countCheck } from "./decisionList.ts";

/* --------------------------------------------------- the served figure --- */

test("THE LIVE SHAPE: the served counter is what renders, less the known notes", () => {
  // The exact figures measured off the running spine and the running page on
  // 2026-08-23, hardcoded: desk_load.total 97, one secretary note diverted,
  // 96 cards below. The header used to say 96 and the chip 97.
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 97, servedComplete: true,
    divertedNotes: 1, cardCount: 96,
  });
  assert.equal(h.value, 96, "the figure is the fund's 97 less the one note");
  assert.equal(h.source, "spine");
  assert.equal(h.atLeast, false);
  assert.equal(h.reconciliation, null, "97 − 1 === 96 cards: nothing to warn about");
  assert.ok(h.note, "the subtraction must be stated, never silent");
  assert.match(h.note!, /97/, "the unadjusted served figure stays visible");
  assert.match(h.note!, /read rather than decided/);
  // GRAMMAR IS PART OF THE CONTRACT HERE, and this pins a slip that reached a
  // screenshot: the one-clause version rendered "1 row of that are Donna's
  // notes". A count that can be 1 must not share a verb with a plural noun.
  assert.match(h.note!, /one row this page does not: a note from Donna, which asks/);
  assert.ok(!/rows? of that are/.test(h.note!));
});

test("the singular and plural adjustments both read as English", () => {
  const one = awaitingHeadline({
    deskReadable: true, servedTotal: 10, servedComplete: true,
    divertedNotes: 1, cardCount: 9,
  }).note!;
  const many = awaitingHeadline({
    deskReadable: true, servedTotal: 10, servedComplete: true,
    divertedNotes: 3, cardCount: 7,
  }).note!;
  assert.match(one, /one row .* a note from Donna, which asks to be read/);
  assert.match(many, /3 rows .* notes from Donna, which ask to be read/);
  assert.ok(!/1 rows|one rows/.test(one));
  assert.ok(!/3 row /.test(many));
});

test("no notes to divert: the served figure is rendered verbatim and needs no gloss", () => {
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 42, servedComplete: true,
    divertedNotes: 0, cardCount: 42,
  });
  assert.equal(h.value, 42);
  assert.equal(h.source, "spine");
  assert.equal(h.note, null, "a figure needing no explanation gets none");
  assert.equal(h.reconciliation, null);
});

/* ------------------------------------------------------ the fallbacks ---- */

test("a spine with no counter falls back to the page fold AND SAYS SO", () => {
  for (const served of [undefined, null, Number.NaN]) {
    const h = awaitingHeadline({
      deskReadable: true, servedTotal: served as number | null | undefined,
      divertedNotes: 3, cardCount: 11,
    });
    assert.equal(h.value, 11, "the cards are the fallback figure");
    assert.equal(h.source, "page");
    assert.ok(h.note, "a page-computed figure must never look like a served one");
    assert.match(h.note!, /this build's own fold/);
    assert.equal(h.reconciliation, null,
      "there is no second number to reconcile against");
  }
});

test("an unreadable desk is UNKNOWN, never zero", () => {
  const h = awaitingHeadline({
    deskReadable: false, servedTotal: 5, divertedNotes: 0, cardCount: 0,
  });
  assert.equal(h.value, null, "null, not 0 — absence is never zero");
  assert.equal(h.source, "unknown");
  assert.match(h.note!, /UNKNOWN, not none/);
});

test("an incomplete count is a FLOOR and names what could not be read", () => {
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 12, servedComplete: false,
    servedUnreadable: ["pending_orders", "requests"],
    divertedNotes: 0, cardCount: 12,
  });
  assert.equal(h.value, 12);
  assert.equal(h.atLeast, true, "the '+' suffix must be driven by this");
  assert.match(h.note!, /FLOOR and not a total/);
  assert.match(h.note!, /pending_orders, requests/);
});

test("an unreadable list that is absent does not fabricate an empty one", () => {
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 12, servedComplete: false,
    servedUnreadable: null, divertedNotes: 0, cardCount: 12,
  });
  assert.equal(h.atLeast, true);
  assert.match(h.note!, /FLOOR and not a total\./,
    "with nothing to name, the sentence ends rather than listing nothing");
  assert.ok(!/could not read\s*\./.test(h.note!),
    "an empty 'could not read' clause is worse than no clause");
});

/* ------------------------------------------------------ the adjustment --- */

test("the adjustment may only REMOVE, and is REFUSED rather than clamped", () => {
  // More notes diverted than the fund counts as awaiting: the two folds
  // disagree about which rows exist. A clamp to zero would hide that.
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 2, servedComplete: true,
    divertedNotes: 5, cardCount: 2,
  });
  assert.equal(h.value, 2, "unadjusted — the subtraction was refused, not applied");
  assert.ok(h.value! >= 0, "and never negative");
  assert.match(h.note!, /refused rather than clamped/);
  assert.equal(h.reconciliation, null,
    "the refused figure still equals the cards, so there is nothing further to say");
});

test("an adjustment exactly equal to the total is applied, and reaches zero honestly", () => {
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 3, servedComplete: true,
    divertedNotes: 3, cardCount: 0,
  });
  assert.equal(h.value, 0, "zero because it was measured, not because it was absent");
  assert.equal(h.reconciliation, null);
  assert.match(h.note!, /3 rows this page does not/);
});

/* --------------------------------------------------- the reconciliation -- */

test("a residual disagreement is LOUD and points at the larger number", () => {
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 9, servedComplete: true,
    divertedNotes: 1, cardCount: 6,
  });
  assert.equal(h.value, 8);
  assert.ok(h.reconciliation, "8 against 6 cards must be reported");
  assert.match(h.reconciliation!, /treat the LARGER/);
});

test("the reconciliation sentence is countCheck's, not a second copy of it", () => {
  // Two functions phrasing one disagreement is the same defect as two
  // functions counting one queue. This asserts the delegation by OUTPUT,
  // which a re-implementation that happened to read similarly would fail.
  const cases = [
    { served: 9, notes: 1, cards: 6 },
    { served: 7, notes: 0, cards: 6 },
    { served: 40, notes: 3, cards: 40 },
    { served: 5, notes: 5, cards: 1 },
  ];
  for (const c of cases) {
    const h = awaitingHeadline({
      deskReadable: true, servedTotal: c.served, servedComplete: true,
      divertedNotes: c.notes, cardCount: c.cards,
    });
    const applied = c.notes > 0 && c.notes <= c.served ? c.notes : 0;
    assert.equal(h.reconciliation, countCheck({
      spineTotal: h.value! + applied,
      pageTotal: c.cards,
      divertedNotes: applied,
    }), `case ${JSON.stringify(c)}`);
  }
});

test("the refused case reconciles against the figure ON SCREEN, not the unapplied one", () => {
  // served 2, 5 notes refused, 4 cards. The figure rendered is 2, so the
  // disagreement is 2-vs-4. Reconciling against 2−5=−3 would report a
  // disagreement of 7 about a number nobody can see.
  const h = awaitingHeadline({
    deskReadable: true, servedTotal: 2, servedComplete: true,
    divertedNotes: 5, cardCount: 4,
  });
  assert.equal(h.value, 2);
  assert.ok(h.reconciliation);
  assert.match(h.reconciliation!, /counts 4 /);
  assert.match(h.reconciliation!, /says 2/);
  assert.ok(!/-3|−3/.test(h.reconciliation!),
    "a negative expected figure must never reach the reader");
});

/* ------------------------------------------------------------- wiring ---- */

const code = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
const PAGE = code(readFileSync(new URL("./ceo/page.tsx", import.meta.url), "utf8"));
const CHIP = code(readFileSync(new URL("./components.tsx", import.meta.url), "utf8"));

test("the UNKNOWN sentence appears exactly once on the page", () => {
  /* Found by the dead-spine pass, in code written the same hour: the header's
   * new `headline.note` and the decision section's pre-existing copy rendered
   * the same sentence 300px apart. One sentence, one owner. */
  const h = awaitingHeadline({
    deskReadable: false, divertedNotes: 0, cardCount: 0,
  });
  const marker = "UNKNOWN, not none";
  assert.ok(h.note!.includes(marker), "the fold owns the sentence");
  const inPage = PAGE.split(marker).length - 1;
  assert.equal(inPage, 0,
    "the page must not carry its own copy — it renders headline.note");
});

test("the CEO desk renders the ONE fold and no second figure beside it", () => {
  assert.ok(/awaitingHeadline\(/.test(PAGE),
    "an unwired fold is the pattern this firm names in its own doctrine");
  assert.ok(/\{headline\.reconciliation\}/.test(PAGE),
    "the disagreement sentence must reach the screen");
  assert.ok(/headline\.note/.test(PAGE),
    "the gloss that says which fold produced the figure must render");
  // THE DEFECT ITSELF: the triage chip must not print a rival total on the one
  // page that already renders the figure.
  assert.ok(/total="already-on-screen"/.test(PAGE),
    "the chip beside the headline must not carry a second 'awaiting you' count");
  assert.ok(/divertedNotes: officers\.donna\.notes\.length/.test(PAGE),
    "the known divergence is measured from the live routing, never hardcoded");
});

test("chipShowsTotal: exactly one case prints a second figure", () => {
  /* Found by mutation: inverting this condition inside the chip's JSX put the
   * rival number back on the CEO's desk AND removed it from the CTO's, and
   * every test still passed. There is no DOM test runner here, so the
   * predicate lives in a module that can be called. Hardcoded on both sides
   * of the boundary — a test parametrised by the value it pins pins nothing. */
  assert.equal(chipShowsTotal("show"), true);
  assert.equal(chipShowsTotal("already-on-screen"), false);
});

test("the chip can suppress its total, and does so only when asked", () => {
  // Default-on: the CTO console renders the chip alone and it is the only
  // count there. A fix applied to one file in a family and not its sibling is
  // its own failure mode.
  assert.ok(/total\s*=\s*"show"/.test(CHIP),
    "the chip's total stays on by default for surfaces with no figure of their own");
  assert.ok(/total\?:\s*ChipTotal/.test(CHIP),
    "and the suppression is a named case, not a bare boolean");
  assert.ok(/chipShowsTotal\(total\)/.test(CHIP),
    "the chip must call the tested predicate, not restate it inline");
  const CTO = code(readFileSync(new URL("./cto/page.tsx", import.meta.url), "utf8"));
  assert.ok(!/total="already-on-screen"/.test(CTO),
    "the CTO console has no headline of its own — its chip must keep the total");
});
