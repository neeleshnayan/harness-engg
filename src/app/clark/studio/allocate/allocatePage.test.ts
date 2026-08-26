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
