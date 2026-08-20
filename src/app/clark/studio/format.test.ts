/**
 * Tests for the consolidated formatters.
 *
 * Run: node --experimental-strip-types --test src/app/clark/studio/format.test.ts
 *
 * These guard the two properties that made ten pasted copies dangerous rather
 * than merely redundant: the absent branch, and the unit convention.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DASH, money, moneyCompact, pct, pctFromFraction, signedMoney, signedPct,
} from "./format.ts";

test("absent is a dash, never a zero — money", () => {
  assert.equal(money(null), DASH);
  assert.equal(money(undefined), DASH);
  // The whole point: a measured zero must NOT look like an absent one.
  assert.equal(money(0), "$0.00");
  assert.notEqual(money(0), money(null));
});

test("absent is a dash, never a zero — pct", () => {
  assert.equal(pct(null), DASH);
  assert.equal(pct(undefined), DASH);
  assert.equal(pct(0), "0.0%");
  assert.notEqual(pct(0), pct(null));
});

test("money keeps the dominant two-decimal default and honours an explicit dp", () => {
  assert.equal(money(1234.5), "$1,234.50");
  // Risk / RebalancePanel / CandidateVerdict pass 0 explicitly after the
  // consolidation; their rendering must be unchanged.
  assert.equal(money(1234.5, 0), "$1,235");
  assert.equal(money(1234, 0), "$1,234");
});

test("pct keeps the dominant one-decimal default and honours an explicit dp", () => {
  assert.equal(pct(12.345), "12.3%");
  // Monitor's retired copy defaulted to 2; its call sites now pass 2.
  assert.equal(pct(12.345, 2), "12.35%");
});

test("pct and pctFromFraction are NOT interchangeable — the 100x trap", () => {
  // ExecutionAnalytics' local `pct` multiplied by 100. Importing the shared
  // `pct` there instead would have rendered a 62% win rate as "0.6%". If these
  // two ever agree on a non-zero input, one of them has silently changed.
  assert.equal(pct(0.62), "0.6%");
  assert.equal(pctFromFraction(0.62), "62.0%");
  assert.notEqual(pct(0.62), pctFromFraction(0.62));
  assert.equal(pctFromFraction(null), DASH);
});

test("signedMoney puts the sign outside the currency symbol", () => {
  assert.equal(signedMoney(163.15), "+$163.15");
  // NOT "$-163.15" — the leading glyph is what a P&L column is read by.
  assert.equal(signedMoney(-163.15), "−$163.15");
  assert.equal(signedMoney(0), "+$0.00");
  assert.equal(signedMoney(null), DASH);
});

test("signedPct signs the positive branch and leaves toFixed's own minus", () => {
  assert.equal(signedPct(2.5), "+2.50%");
  assert.equal(signedPct(-2.5), "-2.50%");
  assert.equal(signedPct(null), DASH);
});

test("moneyCompact is lossy and stays separate from money", () => {
  assert.equal(moneyCompact(2_500_000_000), "$2.5bn");
  assert.equal(moneyCompact(3_400_000), "$3.4m");
  assert.equal(moneyCompact(56_000), "$56k");
  assert.equal(moneyCompact(null), DASH);
  // The inherited sub-$1k behaviour, asserted so it cannot change unnoticed.
  assert.equal(moneyCompact(250), "$0k");
  // A book figure must never be reachable through the lossy path by accident.
  assert.notEqual(moneyCompact(1878.6), money(1878.6));
});
