/**
 * How much of the fund is actually at work — folded from the strategy list by
 * pure functions, so every figure on Allocate has a test behind it.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS — defect C1, "Allocate's false zero" (found 2026-08-20
 * by running the page against the live spine; CEO-accepted for fix the same
 * day).
 *
 * Allocate used to compute its headline figures over
 * `strategies.filter(s => !s.archived && s.state === "deployed")`. On
 * 2026-08-20 the fund had ZERO deployed strategies and THREE paused ones
 * holding $810.21 of a $1,878.60 NAV — 43.1%. The page therefore read
 * "Deployed (actual) 0.0% — of NAV actually at work" and "Unallocated 100.0%"
 * on the same screen as "39.6% sitting in cash", two statements that cannot
 * both be true. A pause stops a strategy from TRADING; it does not sell its
 * positions. The state was being used as a filter when it is only a label.
 *
 * The rule this module encodes: **capital at work is a property of the
 * POSITIONS, never of the state string.** A strategy's state decides what the
 * badge says and whether new orders may be generated. It decides nothing about
 * whether its dollars are exposed to the market.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * Absence discipline, the second rule here:
 *
 *   `actual_pct` absent over every strategy returns `null`, NOT 0. "The fund
 *   holds nothing" and "the spine did not tell us what the fund holds" are
 *   opposite facts that render identically as 0.0%. Every sum below reports how
 *   many rows actually carried the field so the caller can say so.
 */

import type { StrategyView } from "@/lib/fund_api";

/** Sum with provenance. `value` is null when NO input carried the field. */
export interface Folded {
  /** null = nothing to sum, not zero. */
  value: number | null;
  /** How many strategies contributed a number. */
  reported: number;
  /** How many were considered. `reported < considered` means a partial sum. */
  considered: number;
}

const foldField = (
  rows: StrategyView[],
  pick: (s: StrategyView) => number | null | undefined,
): Folded => {
  let value: number | null = null;
  let reported = 0;
  for (const s of rows) {
    const v = pick(s);
    if (v == null || !Number.isFinite(v)) continue;
    value = (value ?? 0) + v;
    reported += 1;
  }
  return { value, reported, considered: rows.length };
};

/**
 * Is this strategy carrying capital RIGHT NOW?
 *
 * Positions first, exposure second — `actual_pct` is derived from exposure
 * against NAV, so on a spine that could not strike a NAV the percentage can be
 * absent while the dollars are not. Either one being non-zero means the book is
 * exposed. A strategy whose exposure is absent AND whose actual_pct is absent
 * is NOT reported as holding: unknown is not "holding", and it is not "flat"
 * either — `holdingUnknown` below counts those separately so the page can say
 * so instead of picking a side.
 */
export function isHolding(s: StrategyView): boolean {
  const a = s.actual_pct;
  const e = s.exposure_usd;
  if (a != null && Number.isFinite(a) && a !== 0) return true;
  if (e != null && Number.isFinite(e) && e !== 0) return true;
  return false;
}

/** Strategies whose exposure the spine did not report at all. */
export function holdingUnknown(rows: StrategyView[]): StrategyView[] {
  return rows.filter((s) => s.actual_pct == null && s.exposure_usd == null);
}

export interface BookFold {
  /** Every non-archived strategy — the population every total is folded over. */
  all: StrategyView[];
  /** What the "Live allocations" table lists: anything DEPLOYED (its intent is
   *  live even at zero exposure) or anything HOLDING (its dollars are live
   *  whatever its state says). The union, deliberately — a paused strategy
   *  sitting on a quarter of NAV belongs in the book, not on the bench. */
  book: StrategyView[];
  /** Non-archived, not deployed, holding nothing. Genuinely idle. */
  bench: StrategyView[];
  /** Non-archived, NOT deployed, but still holding — the population the
   *  "paused but still holding" notice exists for. */
  holdingWhileNotDeployed: StrategyView[];
  /** Sum of `allocation_pct` over `all` — the fund's stated intent. */
  target: Folded;
  /** Sum of `actual_pct` over `all` — the fund's actual exposure. THIS is the
   *  number C1 was getting wrong. */
  actual: Folded;
  /** Sum of `exposure_usd` over `all`. */
  exposureUsd: Folded;
  /** Largest |actual − target| across `book`; null when no row carried both. */
  worstDrift: number | null;
}

/**
 * Fold the strategy list into the figures Allocate renders.
 *
 * Totals are over ALL non-archived strategies, not over a state-filtered
 * subset — see the C1 note at the top of this file. Archived strategies are
 * excluded because archiving is the fund's own "this no longer exists"; if an
 * archived strategy still held positions that would be a spine defect, and one
 * this fold would hide, so `archivedStillHolding` is surfaced separately.
 */
export function foldBook(strategies: StrategyView[]): BookFold {
  const all = strategies.filter((s) => !s.archived);
  const book = all.filter((s) => s.state === "deployed" || isHolding(s));
  const bench = all.filter((s) => !(s.state === "deployed" || isHolding(s)));
  const holdingWhileNotDeployed = all.filter(
    (s) => s.state !== "deployed" && isHolding(s),
  );

  let worstDrift: number | null = null;
  for (const s of book) {
    if (s.actual_pct == null || s.allocation_pct == null) continue;
    const d = Math.abs(s.actual_pct - s.allocation_pct);
    if (worstDrift == null || d > worstDrift) worstDrift = d;
  }

  return {
    all,
    book,
    bench,
    holdingWhileNotDeployed,
    target: foldField(all, (s) => s.allocation_pct),
    actual: foldField(all, (s) => s.actual_pct),
    exposureUsd: foldField(all, (s) => s.exposure_usd),
    worstDrift,
  };
}

/** Archived strategies that still report exposure — a contradiction worth
 *  showing rather than filtering away. Empty is the expected answer. */
export function archivedStillHolding(strategies: StrategyView[]): StrategyView[] {
  return strategies.filter((s) => s.archived && isHolding(s));
}

/**
 * Cash as a percentage of NAV. Null in, null out — a NAV the spine could not
 * report must not become a 0% cash reading, which is the most reassuring
 * possible rendering of "we cannot see the fund" (defect C3).
 */
export function cashPctOfNav(
  cashUsd: number | null | undefined,
  navUsd: number | null | undefined,
): number | null {
  if (cashUsd == null || navUsd == null) return null;
  if (!Number.isFinite(cashUsd) || !Number.isFinite(navUsd) || navUsd <= 0) return null;
  return (cashUsd / navUsd) * 100;
}
