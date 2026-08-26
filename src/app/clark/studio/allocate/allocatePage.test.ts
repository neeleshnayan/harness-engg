/**
 * SOURCE-LEVEL PINS for the allocate page's engine provenance.
 *
 * Same caveat as `enginePage.test.ts`: KryptonPay has no DOM runner, so a
 * `.tsx` call site is unverifiable by execution and this reads the source
 * instead. Weaker than a render test, stronger than nothing, and every
 * assertion names what it prevents.
 *
 * THE DEFECT THIS FILE EXISTS FOR IS A FAMILY DEFECT. Allocate renders the
 * strategy name in TWO places — the book table and the bench list — and the
 * measured pattern in this codebase is a fix applied to one member of a family
 * and not its sibling. An ENGINE badge on the book and not the bench would
 * make an algorithmic strategy findable exactly while it is deployed and
 * invisible while it is waiting to be, which is the half that matters: the
 * bench is where the CEO decides what to fund.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const PAGE = readFileSync(join(HERE, "page.tsx"), "utf8");

test("the engine badge renders in BOTH places a strategy name appears", () => {
  const badges = [...PAGE.matchAll(/<EngineBadge strategy=\{s\} \/>/g)];
  assert.equal(badges.length, 2, "the book table AND the bench list");
  // A positive control on the count: assert it equals the number of places the
  // page renders a strategy NAME, so a third list added later cannot slip past
  // this test by leaving the number at 2.
  const names = [...PAGE.matchAll(/\{s\.name\}/g)];
  assert.equal(badges.length, names.length);
});

test("the badge is decided by the definition, not by the name", () => {
  assert.ok(PAGE.includes("engineOf(strategy)"));
  // A prefix match anywhere on this page would badge "TEST - Fast Intraday
  // (5m SMA)" — a hand-managed strategy — and miss an engine strategy named
  // plainly.
  assert.doesNotMatch(PAGE, /startsWith\(["'`]LEAN/);
  assert.doesNotMatch(PAGE, /name.*includes\(["'`]LEAN/);
});

test("a hand-managed strategy gets NO badge, so the badge means something", () => {
  // A badge on every row is a badge on none. `engineOf` returning null must
  // render nothing at all, not a "manual" chip.
  assert.match(PAGE, /if \(!engine\) return null;/);
});

test("the badge LINKS to the engine page, where the datasource actually lives", () => {
  // Findability is the requirement, and a label that says "this is different"
  // without saying where to look has only done half of it.
  assert.match(PAGE, /href="\/clark\/studio\/engine"/);
});

test("allocate gained no control it did not have", () => {
  // The badge is a link. A start/stop or run button would be a control on a
  // page whose whole job is sizing, and it is not in this diff.
  assert.doesNotMatch(PAGE, /startLive|stopLive|runAlgorithm|lean\/live/);
});

// ------------------------------------- the engine inclusion rule (2026-08-27)

/** The page with its comments removed — the surface a NEGATIVE assertion must
 *  read. Measured on the engine page the same day: a `doesNotMatch` scan that
 *  reads prose fails on the comment explaining the very fix it checks. */
const CODE = PAGE.replace(/\/\*[\s\S]*?\*\//g, "");

test("the engine panel exists and is fed by the tested fold", () => {
  // KILLS THE DEFECT THE CEO NAMED. A badge can only decorate a row that
  // already renders; the inclusion rule is what makes an archived or
  // unallocated engine strategy appear at all.
  assert.match(CODE, /engineBook\(strategies, engine\)/);
  assert.match(CODE, /engineRows\.rows\.map\(/);
  assert.doesNotMatch(CODE, /engineRows\.rows\.slice|engineRows\.rows\.filter/);
  assert.ok(CODE.includes("engineBookHeadline(engineRows)"));
  assert.ok(CODE.includes("engineBookMismatch(engineRows)"));
});

test("the engine read fails on its OWN, and never blanks the book", () => {
  // Defect C3's rule applied to the third source: `Promise.allSettled`, not
  // `all`. A dead engine endpoint must not take the strategy table with it.
  assert.match(CODE, /Promise\.allSettled\(\[[\s\S]{0,400}getEngine\(\)/);
  assert.doesNotMatch(CODE, /Promise\.all\(\[/);
  // And a failed engine read is NULL — which engineBook renders as UNKNOWN.
  // `?? []` here would report a live LEAN container as "no session running".
  assert.match(CODE, /setEngine\(e\.status === "fulfilled" \? \(e\.value\.strategies \?\? null\) : null\)/);
});

test("the panel's words all come from the module, never inline in JSX", () => {
  // A second copy of "trading via engine" in JSX is how the page and its
  // tested module start disagreeing about what a running session means.
  assert.doesNotMatch(CODE, /trading via engine|unallocated|no session running/);
  assert.match(CODE, /\{r\.headline\}/);
  assert.match(CODE, /\{r\.note\}/);
});

test("allocate STILL gained no control it did not have", () => {
  // Re-asserted after the panel landed: a per-engine-strategy row is exactly
  // the shape a start/stop button would arrive in, and this page's job is
  // sizing.
  assert.doesNotMatch(CODE, /startLive|stopLive|runAlgorithm|lean\/live/);
});
