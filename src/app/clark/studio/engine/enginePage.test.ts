/**
 * SOURCE-LEVEL PINS for the engine page.
 *
 * WHY THIS FILE IS ODD, stated so nobody mistakes it for a real render test:
 * KryptonPay has NO DOM test runner, so every `.tsx` call site in this repo is
 * unverifiable by execution. Mutation proved the cost — T20 (`<Qty v={r.book_qty} />`
 * replaced by `{r.book_qty ?? 0}`, which renders UNKNOWN as a zero on the fund's
 * reconciliation screen) SURVIVED the whole suite.
 *
 * So this reads the SOURCE and pins the small number of expressions where the
 * page could quietly re-introduce the exact defect the module below it exists
 * to prevent. It is weaker than a render test and stronger than nothing, and
 * every assertion here names the mutant it kills.
 */

import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const PAGE = readFileSync(join(HERE, "page.tsx"), "utf8");

test("every quantity cell goes through Qty, which never prints 0 for UNKNOWN", () => {
  // KILLS T20. The four numeric columns of the reconciliation table are the
  // one place on this page where an absence would be indistinguishable from a
  // measured zero, and Qty is the only thing standing between them.
  for (const field of ["r.engine_qty", "r.engine_implied_qty", "r.book_qty", "r.drift"]) {
    assert.ok(
      PAGE.includes(`<Qty v={${field}}`),
      `${field} must be rendered by <Qty>, not interpolated directly`,
    );
  }
  // A positive control: a field this test does NOT know about would not be
  // caught, so assert the set it checks is the set the table renders.
  const cells = [...PAGE.matchAll(/<Qty v=\{([^}]+)\}/g)].map((m) => m[1].trim());
  assert.deepEqual(new Set(cells),
    new Set(["r.engine_qty", "r.engine_implied_qty", "r.book_qty", "r.drift"]));
});

test("Qty renders a word, not a number, when the value is absent", () => {
  assert.match(PAGE, /if \(v == null\) \{[\s\S]{0,200}unknown/);
  assert.match(PAGE, /unknown = "UNKNOWN"/);
});

test("the page reads its verdict words from the module, never inline", () => {
  // A second copy of "in sync" in JSX is how the page and its tested module
  // start disagreeing. The page must call syncWord/reconcileHeadline.
  assert.ok(PAGE.includes("syncWord(r.in_sync)"));
  assert.ok(PAGE.includes("reconcileHeadline(leg)"));
  assert.ok(PAGE.includes("engineHeadline(status)"));
  assert.doesNotMatch(PAGE, /"in sync"/);
});

test("the figure on the fate strip is toned by countTone, not by bucket", () => {
  // KILLS the page-side half of T1: the module's countTone is useless if the
  // page reaches past it for b.tone.
  assert.ok(PAGE.includes("TONE_TEXT[b.countTone]"));
  assert.ok(!PAGE.includes("TONE_TEXT[b.tone]"));
});

test("the page has no control that acts — it is a reading", () => {
  // The brief's hard boundary. The only button is the refresh, and the only
  // client call is the read.
  const calls = [...PAGE.matchAll(/fundApiClient\.(\w+)/g)].map((m) => m[1]);
  assert.deepEqual([...new Set(calls)], ["getEngine"]);
  // CODE tokens, not prose. The first version of this assertion matched
  // /approve|decline/ against the whole file and failed on the page's own
  // English ("Sitting in the approval queue", "declined") — a doesNotMatch
  // defeated by the very sentences the page exists to say. The Gauntlet's
  // shared-word rule applies to negative assertions too.
  const handlers = [...PAGE.matchAll(/onClick=\{([^}]*)\}/g)].map((m) => m[1].trim());
  assert.deepEqual(handlers, ["() => void load()"]);
  assert.doesNotMatch(PAGE, /fundApi\.post|\.post\(|method:\s*"POST"/);
});

test("a failed read clears the payload rather than showing a stale one", () => {
  assert.match(PAGE, /catch \(e\) \{[\s\S]{0,400}setView\(null\)/);
});
