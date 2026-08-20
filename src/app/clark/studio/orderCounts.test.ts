/**
 * Tests for order-status counting.
 *
 * Run: node --experimental-strip-types --test src/app/clark/studio/orderCounts.test.ts
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE INCIDENT — defect C2, "nothing in flight" (2026-08-20).
 *
 * Monitor caught a failed order-history read into `[]`. MonitorVerdict then
 * printed "nothing in flight" and OrderFlow printed "Nothing in flight — every
 * order has reached a terminal state", both about an order book that had never
 * been read. The first test below is the one that fails if `null` is ever again
 * allowed to collapse into `0`.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import type { OrderHistoryRow } from "../../../lib/fund_api.ts";
import {
  hasRecentFailure, inFlightCount, settledCount,
} from "./orderCounts.ts";

const o = (status: string, ts?: string) =>
  ({ order_id: `${status}-${ts ?? "x"}`, status, ts } as unknown as OrderHistoryRow);

test("C2: an unread order history counts as null, NEVER zero", () => {
  assert.equal(inFlightCount(null), null);
  assert.equal(settledCount(null), null);
  assert.equal(hasRecentFailure(null, Date.now()), null);
  // The whole defect in one line: these must not be equal.
  assert.notEqual(inFlightCount(null), inFlightCount([]));
});

test("a genuinely empty order book counts as zero — that IS a measurement", () => {
  assert.equal(inFlightCount([]), 0);
  assert.equal(settledCount([]), 0);
  assert.equal(hasRecentFailure([], Date.now()), false);
});

test("in-flight means the VENUE may still act; pending waits on a human", () => {
  const rows = [
    o("approved"), o("working"), o("partial"),
    o("pending"),            // waiting on the CEO, not on the market
    o("filled"), o("rejected"), o("declined"),
  ];
  assert.equal(inFlightCount(rows), 3);
  // Settled excludes pending AND the three in-flight states.
  assert.equal(settledCount(rows), 3);   // filled, rejected, declined
});

test("a recent failure is found; an old one is not; unknown stays unknown", () => {
  const now = Date.parse("2026-08-20T12:00:00Z");
  assert.equal(hasRecentFailure([o("rejected", "2026-08-20T11:00:00Z")], now), true);
  assert.equal(hasRecentFailure([o("rejected", "2026-08-01T11:00:00Z")], now), false);
  // A failure with no timestamp cannot be placed in the window; it is not
  // counted as recent, and the caller still sees the row in the table.
  assert.equal(hasRecentFailure([o("rejected", undefined)], now), false);
  assert.equal(hasRecentFailure(null, now), null);
});
