import test from "node:test";
import assert from "node:assert/strict";

import {
  AGE_DAY_HOURS, AGE_LONG_HOURS, AGE_WEEK_HOURS, BAND_ORDER, GLYPH_LABEL,
  type CardFacts, type CardScale,
  cardAge, cardBand, cardGeometry, cardGlyph, cardMoney, fmtUsdCompact,
  moneyScale,
} from "./cardGeometry.ts";

/**
 * THE CARD'S PICTURE — the tests that fail if a rectangle starts lying.
 *
 * The whole module exists because the CEO could not SCAN his desk, so every
 * test here asks the scanning question: does this encoding say the true thing
 * before a word is read, and can two different facts ever draw the same
 * pixels?
 */

const NOW = "2026-08-27T13:00:00+00:00";
const S: CardScale = {
  now: NOW,
  moneyFullScaleUsd: 1000,
  moneyScaleWhy: "$1.0k, the largest figure on this list",
};

/* ------------------------------------------------------------- the band --- */

test("overdue is the ONE condition that spends colour", () => {
  const b = cardBand({ dueDate: "2026-08-24" }, S);
  assert.equal(b.tone, "blocker");
  assert.equal(b.daysOverdue, 3);
  assert.equal(b.label, "3 days overdue");
  assert.match(b.why, /2026-08-24/);
});

test("the overdue boundary is EXCLUSIVE at today — due today is not late", () => {
  // Strict-vs-non-strict at the boundary. Due today is `dated`, not `blocker`:
  // a commitment with hours left on it is not a broken one, and colouring it
  // amber would put the alarm tone on rows where nothing is wrong.
  assert.equal(cardBand({ dueDate: "2026-08-27" }, S).tone, "dated");
  assert.equal(cardBand({ dueDate: "2026-08-27" }, S).label, "due today");
  assert.equal(cardBand({ dueDate: "2026-08-26" }, S).tone, "blocker");
  assert.equal(cardBand({ dueDate: "2026-08-26" }, S).daysOverdue, 1);
  assert.equal(cardBand({ dueDate: "2026-08-26" }, S).label, "1 day overdue");
  assert.equal(cardBand({ dueDate: "2026-08-28" }, S).tone, "dated");
  assert.equal(cardBand({ dueDate: "2026-08-28" }, S).daysOverdue, null);
});

test("a row with NO date is quiet, and says the reason", () => {
  const b = cardBand({}, S);
  assert.equal(b.tone, "quiet");
  assert.equal(b.daysOverdue, null);
  assert.match(b.why, /carries no due date/);
});

test("an UNREADABLE date is not a date and not a severity", () => {
  /* `"soon"` sorts after `"2026-08-27"` under string comparison and would
   * read as a future date forever. It is rejected by SHAPE, and the row is
   * quiet with the failure stated in words — giving it a tone would put a
   * severity on a parsing bug. */
  const b = cardBand({ dueDate: "soon" }, S);
  assert.equal(b.tone, "quiet");
  assert.match(b.why, /cannot read/);
  assert.match(b.why, /soon/);
  // ...and it is DISTINGUISHABLE from a row with no date at all.
  assert.notEqual(b.why, cardBand({}, S).why);
});

test("an unreadable CLOCK reports dated, never on-time", () => {
  /* The permissive direction is the dangerous one here: with an unreadable
   * `now`, every row silently becoming "not overdue" would take the amber off
   * the whole desk and nothing would say why. */
  const b = cardBand({ dueDate: "2026-01-01" },
                     { ...S, now: "not-an-instant" });
  assert.equal(b.tone, "dated");
  assert.equal(b.daysOverdue, null);
  assert.match(b.why, /UNKNOWN/);
});

test("the band order is published so nothing invents a second one", () => {
  assert.ok(BAND_ORDER.blocker < BAND_ORDER.dated);
  assert.ok(BAND_ORDER.dated < BAND_ORDER.quiet);
});

/* ------------------------------------------------------------ the money --- */

test("ZERO AND ABSENT DRAW DIFFERENTLY — the rule the whole module is for", () => {
  const zero = cardMoney({ moneyAtStake: 0 }, S);
  const absent = cardMoney({ moneyAtStake: null }, S);

  assert.equal(zero.render, "zero");
  assert.equal(absent.render, "unpriced");
  assert.notEqual(zero.render, absent.render);
  assert.notEqual(zero.label, absent.label);
  // Both draw no bar, and that is exactly why the RENDER must differ: a
  // zero-width rectangle and a missing rectangle are the same pixels, so the
  // difference has to be carried by the branch, not by the width.
  assert.equal(zero.fraction, 0);
  assert.equal(absent.fraction, 0);
  assert.equal(zero.usd, 0);
  assert.equal(absent.usd, null);
});

test("undefined and NaN are unpriced, not zero", () => {
  assert.equal(cardMoney({}, S).render, "unpriced");
  assert.equal(cardMoney({ moneyAtStake: undefined }, S).render, "unpriced");
  assert.equal(cardMoney({ moneyAtStake: NaN }, S).render, "unpriced");
});

test("the bar's width is proportional and CLAMPED, never overflowing", () => {
  assert.equal(cardMoney({ moneyAtStake: 500 }, S).fraction, 0.5);
  assert.equal(cardMoney({ moneyAtStake: 1000 }, S).fraction, 1);
  const over = cardMoney({ moneyAtStake: 4000 }, S);
  assert.equal(over.fraction, 1, "clamped, not wrapped");
  assert.match(over.why, /larger than the scale/);
  // A negative figure draws by MAGNITUDE — a bar cannot have negative width,
  // and the sign is on the number beside it.
  assert.equal(cardMoney({ moneyAtStake: -250 }, S).fraction, 0.25);
  assert.equal(cardMoney({ moneyAtStake: -250 }, S).label, "-$250");
});

test("a priced row with NO denominator states the figure and draws nothing", () => {
  const m = cardMoney({ moneyAtStake: 500 },
                      { ...S, moneyFullScaleUsd: null });
  assert.equal(m.render, "unscaled");
  assert.equal(m.usd, 500);
  assert.equal(m.fraction, 0);
  assert.match(m.why, /no scale is not a measurement|no bar is drawn/);
  // ...and it is its OWN branch: a reader must not confuse "we could not draw
  // this" with "there is nothing to draw".
  assert.notEqual(m.render, cardMoney({ moneyAtStake: 0 }, S).render);
  assert.notEqual(m.render, cardMoney({ moneyAtStake: null }, S).render);
  // A zero or negative denominator is the same failure as a missing one.
  assert.equal(cardMoney({ moneyAtStake: 5 },
                         { ...S, moneyFullScaleUsd: 0 }).render, "unscaled");
});

test("the denominator is the list's own largest priced figure", () => {
  const rows: CardFacts[] = [
    { moneyAtStake: 630 }, { moneyAtStake: 1847.36 },
    { moneyAtStake: 0 }, { moneyAtStake: null }, { moneyAtStake: 94.29 },
  ];
  const sc = moneyScale(rows);
  assert.equal(sc.moneyFullScaleUsd, 1847.36);
  // The why states its DOMAIN — three of five rows priced above zero, so a
  // reader knows the scale was not set by the whole list.
  assert.match(sc.moneyScaleWhy, /3 of 5/);
});

test("a list with nothing priced returns NO denominator, never a substitute", () => {
  const sc = moneyScale([{ moneyAtStake: 0 }, { moneyAtStake: null }, {}]);
  assert.equal(sc.moneyFullScaleUsd, null);
  assert.match(sc.moneyScaleWhy, /nothing on this list/);
  // The null test: an EMPTY list too, and the domain it compared is zero rows.
  assert.equal(moneyScale([]).moneyFullScaleUsd, null);
});

test("compact dollars are legible at every magnitude the desk carries", () => {
  assert.equal(fmtUsdCompact(1847.36), "$1.8k");
  assert.equal(fmtUsdCompact(630), "$630");
  assert.equal(fmtUsdCompact(94.29), "$94");
  assert.equal(fmtUsdCompact(0.5), "$0.50");
  assert.equal(fmtUsdCompact(9.99), "$9.99");
  assert.equal(fmtUsdCompact(10), "$10", "the round-to-dollars boundary");
  assert.equal(fmtUsdCompact(1_000), "$1.0k", "the k boundary");
  assert.equal(fmtUsdCompact(999), "$999");
  assert.equal(fmtUsdCompact(1_000_000), "$1.0M", "the M boundary");
  assert.equal(fmtUsdCompact(-1847.36), "-$1.8k");
});

/* -------------------------------------------------------------- the age --- */

test("age fills the spine and NEVER dims the card", () => {
  // The encoding choice, asserted: `fill` rises with age. If this ever
  // becomes an opacity that FALLS, the oldest row on the desk becomes the
  // hardest to read, which is backwards.
  const steps = [0.5, 5, 30, 200, 800].map((h) => cardAge({ ageHours: h }));
  for (let i = 1; i < steps.length; i += 1) {
    assert.ok(steps[i].fill >= steps[i - 1].fill,
              `fill must not fall as age rises (${i})`);
  }
  assert.equal(steps[steps.length - 1].fill, 1);
});

test("the age steps are probed AT their boundaries", () => {
  assert.equal(cardAge({ ageHours: AGE_DAY_HOURS - 0.01 }).step, 1);
  assert.equal(cardAge({ ageHours: AGE_DAY_HOURS }).step, 2);
  assert.equal(cardAge({ ageHours: AGE_WEEK_HOURS - 0.01 }).step, 2);
  assert.equal(cardAge({ ageHours: AGE_WEEK_HOURS }).step, 3);
  assert.equal(cardAge({ ageHours: AGE_LONG_HOURS - 0.01 }).step, 3);
  assert.equal(cardAge({ ageHours: AGE_LONG_HOURS }).step, 4);
  // The constants are what the code uses — proven by MOVING across them
  // rather than by asserting their values, which a duplicate would satisfy.
  assert.equal(AGE_DAY_HOURS, 24);
  assert.equal(AGE_WEEK_HOURS, 168);
});

test("an UNKNOWN age is step 0 and draws nothing, not an empty spine", () => {
  for (const bad of [null, undefined, NaN, -1]) {
    const a = cardAge({ ageHours: bad as number | null });
    assert.equal(a.step, 0, String(bad));
    assert.equal(a.known, false, String(bad));
    assert.equal(a.fill, 0, String(bad));
    assert.match(a.why, /UNKNOWN/);
  }
  // A fresh row is KNOWN and non-zero, so "unknown" and "an hour old" are
  // never the same picture.
  const fresh = cardAge({ ageHours: 0 });
  assert.equal(fresh.known, true);
  assert.ok(fresh.fill > 0);
});

test("the age label speaks hours then days", () => {
  assert.equal(cardAge({ ageHours: 0.5 }).label, "under an hour");
  assert.equal(cardAge({ ageHours: 20 }).label, "20h");
  assert.equal(cardAge({ ageHours: 50 }).label, "2.1d");
  assert.equal(cardAge({ ageHours: 400 }).label, "17d");
});

/* ------------------------------------------------------------ the glyph --- */

test("the free-text kinds on the LIVE desk all land on a family", () => {
  /* THE FIXTURE IS THE LIVE RECORD, not an idealised list. These are the 23
   * distinct `kind` values on the CEO's desk, curled 2026-08-27. A lookup
   * table keyed on the exact string would have matched `awaits-ceo` and
   * fallen through on 22 of them. */
  const LIVE = [
    "awaits-ceo", "decision", "research-lane-free", "harness_defect",
    "threshold-proposal", "live-fact-for-decision", "universe_decision",
    "written-reason-update", "position-relabel", "allocation-decline",
    "risk_parameter", "exit-rule-preregistration", "data-probe-spec",
    "alarm_wiring", "threshold_question", "threshold_recommendation",
    "challenge", "menu_section", "governance-escalation", "policy-question",
    "data-acquisition-request", "ceo-decision", "risk-note",
  ];
  assert.equal(LIVE.length, 23, "the measured domain");
  const unmatched = LIVE.filter((k) => cardGlyph({ kind: k }).basis !== "matched");
  assert.deepEqual(unmatched, [],
    `every live kind must reach a family, not the fallthrough: ${unmatched}`);
});

test("the keyword ORDER is load-bearing and is asserted", () => {
  // `threshold_question` contains both words. It is a threshold matter before
  // it is a question, and the table's order is the only thing that says so.
  assert.equal(cardGlyph({ kind: "threshold_question" }).family, "threshold");
  assert.equal(cardGlyph({ kind: "policy-question" }).family, "decision");
  assert.equal(cardGlyph({ kind: "challenge" }).family, "challenge");
});

test("an unrecognised kind gets its OWN shape, never a borrowed one", () => {
  const g = cardGlyph({ kind: "sponglewhatsit" });
  assert.equal(g.family, "unclassified");
  assert.equal(g.basis, "default");
  assert.match(g.why, /no family recognises it/);
});

test("an ABSENT kind and an UNRECOGNISED one are different facts", () => {
  const absent = cardGlyph({ kind: null });
  const unknown = cardGlyph({ kind: "sponglewhatsit" });
  assert.equal(absent.basis, "absent");
  assert.equal(unknown.basis, "default");
  assert.notEqual(absent.basis, unknown.basis);
  assert.notEqual(absent.label, unknown.label);
  // Whitespace is absence, not a kind called " ".
  assert.equal(cardGlyph({ kind: "   " }).basis, "absent");
});

test("every family has a label", () => {
  const families = new Set(Object.keys(GLYPH_LABEL));
  assert.equal(families.size, 7);
  for (const [k, v] of Object.entries(GLYPH_LABEL)) {
    assert.ok(v && v.length > 0, k);
  }
});

/* ------------------------------------------------------------ the whole --- */

test("cardGeometry returns all four encodings from ONE input", () => {
  const g = cardGeometry(
    { dueDate: "2026-08-24", moneyAtStake: 500, ageHours: 200,
      kind: "harness_defect" }, S);
  assert.equal(g.band.tone, "blocker");
  assert.equal(g.money.render, "bar");
  assert.equal(g.money.fraction, 0.5);
  assert.equal(g.age.step, 3);
  assert.equal(g.glyph.family, "defect");
});

test("the four encodings agree with their own single-purpose functions", () => {
  /* The composition must not add a rule. If `cardGeometry` ever grows a
   * branch its parts do not have, the component and the tests are looking at
   * two different modules. */
  const facts: CardFacts[] = [
    { dueDate: "2026-08-24", moneyAtStake: 630, ageHours: 70, kind: "awaits-ceo" },
    {},
    { dueDate: "soon", moneyAtStake: 0, ageHours: NaN, kind: "  " },
    { dueDate: "2026-08-27", moneyAtStake: 9e9, ageHours: 9e9, kind: "challenge" },
  ];
  for (const f of facts) {
    const g = cardGeometry(f, S);
    assert.deepEqual(g.band, cardBand(f, S));
    assert.deepEqual(g.money, cardMoney(f, S));
    assert.deepEqual(g.age, cardAge(f));
    assert.deepEqual(g.glyph, cardGlyph(f));
  }
});

test("EVERY encoding carries a why — a rectangle with no provenance is decor", () => {
  const g = cardGeometry({}, { ...S, moneyFullScaleUsd: null });
  for (const [name, part] of Object.entries(g)) {
    const why = (part as { why?: string }).why;
    assert.ok(why && why.length > 10,
      `${name} must explain itself: the illumination principle binds a `
      + "rectangle exactly as hard as it binds a number");
  }
});

/* -------------------------------- the compact date, and why it exists ----- */

test("the band carries a SHORT form that fits the figure column", () => {
  /* THE MEASUREMENT THAT PUT IT THERE: with the due date as an inline chip
   * before the headline, 39 live cards produced FOUR distinct headline start
   * positions spanning 119px — every dated row indented by the width of its
   * own chip. The column is fixed at 7.5rem and 10px mono, so the label had
   * to be short; truncating at the render site would have made the component
   * decide what the label means. */
  assert.equal(cardBand({ dueDate: "2026-08-24" }, S).short, "3d late");
  assert.equal(cardBand({ dueDate: "2026-08-26" }, S).short, "1d late");
  assert.equal(cardBand({ dueDate: "2026-08-27" }, S).short, "today");
  assert.equal(cardBand({ dueDate: "2026-08-28" }, S).short, "28 Aug");
  assert.equal(cardBand({ dueDate: "2026-09-03" }, S).short, "3 Sep");
  assert.equal(cardBand({ dueDate: "2027-01-01" }, S).short, "1 Jan");
  // Every month name resolves — an off-by-one on the index would print the
  // wrong month for eleven of twelve dates and look completely normal.
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  for (let m = 1; m <= 12; m += 1) {
    const iso = `2027-${String(m).padStart(2, "0")}-15`;
    assert.equal(cardBand({ dueDate: iso }, S).short, `15 ${months[m - 1]}`,
                 `month ${m}`);
  }
});

test("a row with no readable date has NO short form at all", () => {
  // `null`, not `""`. The component renders the line only when there is one,
  // and an empty string would render an empty element that takes vertical
  // space on 27 of 39 rows.
  assert.equal(cardBand({}, S).short, null);
  assert.equal(cardBand({ dueDate: "soon" }, S).short, null);
  assert.equal(cardBand({}, S).due, null);
  assert.equal(cardBand({ dueDate: "soon" }, S).due, null);
});

test("`due` is the VALIDATED date and nothing re-validates it downstream", () => {
  assert.equal(cardBand({ dueDate: "2026-08-24" }, S).due, "2026-08-24");
  // A stamp is accepted and reduced to its day, so a payload that starts
  // carrying instants does not lose its date.
  assert.equal(cardBand({ dueDate: "2026-08-24T09:00:00Z" }, S).due, "2026-08-24");
  assert.equal(cardBand({ dueDate: "2026-08-24T09:00:00Z" }, S).short, "3d late");
});

test("the short form and the long label never disagree about lateness", () => {
  for (const d of ["2026-08-01", "2026-08-26", "2026-08-27", "2026-08-28",
                   "2026-12-31", "soon", ""]) {
    const b = cardBand({ dueDate: d }, S);
    if (b.short === null) { assert.equal(b.tone, "quiet"); continue; }
    const shortSaysLate = b.short.endsWith("late");
    assert.equal(shortSaysLate, b.tone === "blocker",
      `${d}: short "${b.short}" and tone "${b.tone}" must agree`);
  }
});

/* ------------------------------- branches the mutation pass found bare ---- */

test("a kind matched CASE-INSENSITIVELY — every live kind is lower-case today", () => {
  /* M23 SURVIVED. Every one of the 23 kinds on the live desk is already
   * lower-case, so `.toLowerCase()` was never exercised and deleting it broke
   * nothing. The day a seat files `kind: "Threshold-Proposal"` — which
   * nothing prevents, the field is free text — the fold-free version drops it
   * to `unclassified`. The measured population is not the possible one. */
  assert.equal(cardGlyph({ kind: "THRESHOLD-PROPOSAL" }).family, "threshold");
  assert.equal(cardGlyph({ kind: "Harness_Defect" }).family, "defect");
  assert.equal(cardGlyph({ kind: "Awaits-CEO" }).family, "decision");
  assert.equal(cardGlyph({ kind: "CHALLENGE" }).basis, "matched");
});

test("the 'question' keyword is REACHABLE on its own", () => {
  /* M22 SURVIVED, and the reason is worth the test: every question-bearing
   * kind in the live record (`policy-question`, `threshold_question`) matches
   * an EARLIER keyword, so the `question` entry has never fired. It is a
   * deliberate catch-all for a kind nobody has filed yet, and a table entry
   * no input reaches is indistinguishable from one that has been deleted. */
  assert.equal(cardGlyph({ kind: "open-question" }).family, "decision");
  assert.equal(cardGlyph({ kind: "open-question" }).why, "kind open-question — matched on question");
  // ...and the precedence over it still holds where it should.
  assert.match(cardGlyph({ kind: "policy-question" }).why, /matched on policy/);
  assert.match(cardGlyph({ kind: "threshold_question" }).why, /matched on threshold/);
});
