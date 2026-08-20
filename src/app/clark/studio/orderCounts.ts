/**
 * Order-status counting — the one place that decides what "in flight" means,
 * and the one place that decides what an UNREAD order history counts as.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * DEFECT C2, "nothing in flight" (found 2026-08-20 by running Monitor against a
 * dead spine; CEO-accepted for fix the same day).
 *
 * `studio/page.tsx` fetched the order history with
 * `.catch(() => ({ orders: [] }))`. A failed read therefore produced an empty
 * array, three separate consumers counted zero rows in it, and the operator's
 * one-line verdict said "nothing in flight" — a positive operational all-clear
 * assembled from an order book nobody had managed to read. Orders could have
 * been working at the venue the whole time.
 *
 * The rule this module encodes: **an unread list is `null`, and every count
 * derived from it is `null`.** Not zero. The two are one keystroke apart
 * (`orders?.filter(...).length ?? 0` rebuilds the bug exactly) and mean opposite
 * things to someone deciding whether to walk away from the screen.
 */

import type { OrderHistoryRow } from "@/lib/fund_api";

/** Left the human's hands, not yet terminal — the venue may still act on these.
 *  `pending` is excluded: it is waiting on a human, not on the market, and the
 *  approval queue counts it separately. */
export const IN_FLIGHT = new Set(["approved", "working", "partial"]);

/** As above, plus `pending` — used where "not yet settled" is the question. */
export const UNSETTLED = new Set(["pending", "approved", "working", "partial"]);

/** Orders the venue may still act on. `null` in, `null` out. */
export function inFlightCount(orders: OrderHistoryRow[] | null): number | null {
  if (orders === null) return null;
  return orders.filter((o) => IN_FLIGHT.has(o.status)).length;
}

/** Orders that have reached a terminal state. `null` in, `null` out. */
export function settledCount(orders: OrderHistoryRow[] | null): number | null {
  if (orders === null) return null;
  return orders.filter((o) => !UNSETTLED.has(o.status)).length;
}

/**
 * Was anything rejected or failed in the last `windowMs`?
 *
 * Three-valued on purpose: `true` = yes, `false` = no, `null` = the history
 * could not be read so we cannot tell. A caller that collapses null to false
 * is claiming a clean recent record it has not seen.
 */
export function hasRecentFailure(
  orders: OrderHistoryRow[] | null,
  now: number,
  windowMs = 24 * 3600_000,
): boolean | null {
  if (orders === null) return null;
  return orders.some((o) =>
    ["failed", "rejected"].includes(o.status)
    && o.ts != null
    && now - new Date(o.ts).getTime() < windowMs);
}
