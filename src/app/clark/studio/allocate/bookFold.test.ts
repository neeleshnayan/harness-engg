/**
 * Tests for the Allocate book fold.
 *
 * Run: node --experimental-strip-types --test src/app/clark/studio/allocate/bookFold.test.ts
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE INCIDENT THESE GUARD — defect C1, "Allocate's false zero" (2026-08-20).
 *
 * The live spine on 2026-08-20 returned six non-archived strategies: ZERO
 * deployed, three PAUSED holding 8.6847% + 9.0094% + 25.4344% = 43.1285% of a
 * $1,878.60 NAV. Allocate folded its totals over `state === "deployed"` and
 * printed "Deployed (actual) 0.0% — of NAV actually at work" beside
 * "Unallocated 100.0% · 39.6% sitting in cash".
 *
 * `liveSpine2026_08_20` below is that exact payload, field for field. The first
 * test asserts 43.1285, so it FAILS the moment anyone reintroduces a state
 * filter into the fold — which is the only way this defect can come back.
 * ─────────────────────────────────────────────────────────────────────────────
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import type { StrategyView } from "../../../../lib/fund_api.ts";
import {
  archivedStillHolding, cashPctOfNav, engineCount, engineOf, foldBook,
  holdingUnknown, isHolding,
} from "./bookFold.ts";

/** Only the fields the fold reads; cast once, here, so the tests stay legible. */
const s = (o: Partial<StrategyView>): StrategyView => o as StrategyView;

/** Verbatim from GET /api/v1/fund/strategies on 2026-08-20 (nav_usd 1878.6). */
const liveSpine2026_08_20: StrategyView[] = [
  s({ strategy_id: "6cca6a31", name: "Momentum — Large Cap Tech", state: "paused",
      archived: false, allocation_pct: 0.0, actual_pct: 8.6847, exposure_usd: 163.15 }),
  s({ strategy_id: "ca78408f", name: "Mean Reversion — Cyclicals", state: "paused",
      archived: false, allocation_pct: 0.0, actual_pct: 9.0094, exposure_usd: 169.25 }),
  s({ strategy_id: "e54f40af", name: "Trend — Sector & Commodity", state: "paused",
      archived: false, allocation_pct: 0.0, actual_pct: 25.4344, exposure_usd: 477.81 }),
  s({ strategy_id: "3c593166", name: "TEST - Fast Intraday (5m SMA)", state: "paused",
      archived: false, allocation_pct: 0.0, actual_pct: 0.0, exposure_usd: 0.0 }),
  s({ strategy_id: "5374e89e", name: "backtested one", state: "backtested",
      archived: false, allocation_pct: 0.0, actual_pct: 0.0, exposure_usd: 0.0 }),
  s({ strategy_id: "a356b00a", name: "draft one", state: "draft",
      archived: false, allocation_pct: 0.0, actual_pct: 0.0, exposure_usd: 0.0 }),
];

test("C1: capital held by PAUSED strategies is counted as at work", () => {
  const f = foldBook(liveSpine2026_08_20);
  // The number the page rendered as 0.0% for as long as the defect lived.
  assert.equal(f.actual.value?.toFixed(4), "43.1285");
  assert.notEqual(f.actual.value, 0);
  // Zero strategies are deployed — so any fold that still filters on state
  // returns 0 here and this assertion is what catches it.
  assert.equal(f.all.filter((x) => x.state === "deployed").length, 0);
});

test("C1: state is a label — the book lists holders regardless of state", () => {
  const f = foldBook(liveSpine2026_08_20);
  assert.deepEqual(f.book.map((x) => x.strategy_id), ["6cca6a31", "ca78408f", "e54f40af"]);
  assert.equal(f.holdingWhileNotDeployed.length, 3);
  // Flat strategies (including the flat PAUSED one) belong on the bench.
  assert.deepEqual(f.bench.map((x) => x.strategy_id), ["3c593166", "5374e89e", "a356b00a"]);
});

test("a deployed strategy at zero exposure is still in the book", () => {
  // Intent is live even when the position is not — the union, not either half.
  const f = foldBook([
    s({ strategy_id: "d", state: "deployed", archived: false,
        allocation_pct: 20, actual_pct: 0, exposure_usd: 0 }),
  ]);
  assert.deepEqual(f.book.map((x) => x.strategy_id), ["d"]);
  assert.equal(f.bench.length, 0);
});

test("absent is not zero — an unreported actual_pct folds to null", () => {
  // `StrategyView` types these as OPTIONAL (`actual_pct?: number`), so the
  // absent case on the wire is a missing key, not an explicit null. Both are
  // exercised: the fold's guard is `== null`, which must cover each.
  const f = foldBook([
    s({ strategy_id: "a", state: "paused", archived: false }),
  ]);
  assert.equal(f.actual.value, null);
  assert.notEqual(f.actual.value, 0);
  assert.equal(f.actual.reported, 0);
  assert.equal(f.actual.considered, 1);
  assert.deepEqual(holdingUnknown(f.all).map((x) => x.strategy_id), ["a"]);
});

test("a JSON null on the wire is absent too, not zero", () => {
  // Defensive: the endpoint's declared type says undefined, but a spine that
  // serialises an explicit null must not be summed as 0.
  const withNulls = [
    { strategy_id: "a", state: "paused", archived: false,
      allocation_pct: null, actual_pct: null, exposure_usd: null },
  ] as unknown as StrategyView[];
  const f = foldBook(withNulls);
  assert.equal(f.actual.value, null);
  assert.equal(f.actual.reported, 0);
  assert.equal(isHolding(withNulls[0]), false);
  assert.equal(holdingUnknown(f.all).length, 1);
});

test("a partial sum reports that it is partial", () => {
  const f = foldBook([
    s({ strategy_id: "a", state: "deployed", archived: false, actual_pct: 10 }),
    s({ strategy_id: "b", state: "deployed", archived: false }),
  ]);
  assert.equal(f.actual.value, 10);
  assert.equal(f.actual.reported, 1);
  assert.equal(f.actual.considered, 2);
});

test("isHolding follows the positions, never the state string", () => {
  assert.equal(isHolding(s({ state: "paused", actual_pct: 25.4, exposure_usd: 477.81 })), true);
  // Exposure present, percentage absent (a NAV that could not be struck).
  assert.equal(isHolding(s({ state: "paused", exposure_usd: 477.81 })), true);
  assert.equal(isHolding(s({ state: "deployed", actual_pct: 0, exposure_usd: 0 })), false);
  // Unknown is not "holding" — and it is not "flat" either; holdingUnknown says so.
  assert.equal(isHolding(s({ state: "paused" })), false);
});

test("archived strategies are excluded, and a holding one is surfaced not hidden", () => {
  const rows = [
    ...liveSpine2026_08_20,
    s({ strategy_id: "gone", state: "paused", archived: true,
        allocation_pct: 0, actual_pct: 12, exposure_usd: 200 }),
  ];
  const f = foldBook(rows);
  assert.equal(f.all.find((x) => x.strategy_id === "gone"), undefined);
  assert.equal(f.actual.value?.toFixed(4), "43.1285");   // unchanged by the archived row
  assert.deepEqual(archivedStillHolding(rows).map((x) => x.strategy_id), ["gone"]);
});

test("worst drift is null when no row reported both a target and an actual", () => {
  const f = foldBook([
    s({ strategy_id: "a", state: "deployed", archived: false, actual_pct: 12 }),
  ]);
  assert.equal(f.worstDrift, null);
  assert.notEqual(f.worstDrift, 0);
});

test("worst drift is the largest absolute gap across the book", () => {
  const f = foldBook(liveSpine2026_08_20);
  // Every holder sits at target 0 while holding — the drift IS the holding.
  assert.equal(f.worstDrift?.toFixed(4), "25.4344");
});

test("C3: cash percentage is null when NAV could not be read", () => {
  assert.equal(cashPctOfNav(743.4, null), null);
  assert.equal(cashPctOfNav(null, 1878.6), null);
  assert.equal(cashPctOfNav(743.4, 0), null);       // no division by a zero NAV
  assert.equal(cashPctOfNav(743.4, 1878.6)?.toFixed(1), "39.6");
});

test("C3: an unread strategy list is not an empty book", () => {
  // The page passes `strategies ?? []` into the fold, so the fold's answer for
  // "nothing" and the page's answer for "unknown" must be told apart by the
  // page's own null check — this asserts the fold does not paper over it.
  const empty = foldBook([]);
  assert.equal(empty.actual.value, null);
  assert.equal(empty.book.length, 0);
  assert.equal(empty.all.length, 0);
});

/* ───────────────────────────────────────────────────────────────────────────
 * CDO D2 (2026-08-20) — the AT WORK hero rendered 0.0% directly above a banner
 * saying archived strategies still held exposure.
 *
 * `actual` folds over NON-archived rows, which is right for "what is the book
 * supposed to be" and wrong for the hero: a book whose only exposure sits on an
 * archived row is not a flat book. `actualIncludingArchived` is the true book
 * number, and it is null — never zero — when nothing reported a percentage.
 * ─────────────────────────────────────────────────────────────────────────── */

test("D2: the hero total includes archived rows that still hold", () => {
  const rows = [
    s({ strategy_id: "live", state: "paused", archived: false,
        allocation_pct: 0, actual_pct: 0, exposure_usd: 0 }),
    s({ strategy_id: "gone", state: "paused", archived: true,
        allocation_pct: 0, actual_pct: 25.4344, exposure_usd: 477.81 }),
  ];
  const f = foldBook(rows);
  // The old hero number: a flat, reassuring zero.
  assert.equal(f.actual.value, 0);
  // The true book: a quarter of NAV is in positions.
  assert.equal(f.actualIncludingArchived.value, 25.4344);
  assert.equal(f.archivedActual.value, 25.4344);
  // And the contradiction is still surfaced separately, as before.
  assert.equal(archivedStillHolding(rows).length, 1);
});

test("D2: with nothing reported, the hero total is ABSENT, not zero", () => {
  // `actual_pct` is OMITTED, not null: StrategyView types it optional
  // (`actual_pct?: number`), so absence on the wire is a missing key.
  const rows = [
    s({ strategy_id: "gone", state: "paused", archived: true,
        allocation_pct: 0, exposure_usd: 477.81 }),
  ];
  const f = foldBook(rows);
  assert.equal(f.actualIncludingArchived.value, null,
    "an unmeasurable total must render as a dash, never as 0.0%");
  assert.equal(archivedStillHolding(rows).length, 1,
    "exposure_usd alone still makes it a holder");
});

test("D2: with no archived rows the two totals agree", () => {
  const f = foldBook(liveSpine2026_08_20);
  assert.equal(
    f.actualIncludingArchived.value?.toFixed(4),
    f.actual.value?.toFixed(4),
    "the hero must not change on a book with no archived holders",
  );
  assert.equal(f.archivedActual.value, null);
});

// ------------------------------------------------- engine provenance (2026-08-27)

test("an engine strategy is identified by its definition, never by its name", () => {
  // THE DEFECT THIS GUARDS. The live record carries "TEST - Fast Intraday
  // (5m SMA)" — a hand-managed strategy whose name looks like a machine's —
  // and would carry an engine strategy named plainly the day somebody names
  // one that way. Matching the "LEAN - " prefix badges the first and misses
  // the second, and both errors point at money: an ENGINE badge is how the
  // CEO tells an algorithmic sleeve from one he sizes by hand.
  assert.equal(engineOf({ definition: { engine: "lean", algorithm: "x" } }), "lean");
  assert.equal(engineOf({ definition: { type: "sma", fast: 10 } }), null);
  assert.equal(engineOf({ definition: null }), null);
  assert.equal(engineOf({}), null);
});

test("a name that looks like a machine's does not earn a badge", () => {
  const lookalike = { name: "LEAN - not really", definition: { type: "sma" } } as never;
  assert.equal(engineOf(lookalike), null);
});

test("the engine NAME is carried, so a second engine is not folded into 'lean'", () => {
  assert.equal(engineOf({ definition: { engine: "zipline" } }), "zipline");
  assert.equal(engineOf({ definition: { engine: "  lean  " } }), "lean");
  // A non-string or blank engine key names no engine — never `true`, and never
  // the empty string, which would render an empty badge.
  assert.equal(engineOf({ definition: { engine: true } as never }), null);
  assert.equal(engineOf({ definition: { engine: "   " } }), null);
});

test("an unreadable bench has an UNKNOWN engine count, not zero", () => {
  assert.equal(engineCount(null), null);
  assert.equal(engineCount(undefined), null);
  assert.equal(engineCount([]), 0);
  assert.equal(engineCount([
    { definition: { engine: "lean" } },
    { definition: { type: "sma" } },
    { definition: { engine: "lean" } },
  ]), 2);
});
