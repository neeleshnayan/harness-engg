/**
 * Number formatting — ONE money(), ONE pct(), for the whole Studio.
 *
 * Written for the CEO's dead-code mandate (second pass, 2026-08-20). Before
 * this file there were TEN copies of the same `money` and NINE of the same
 * `pct`, one per surface, pasted rather than imported. That is not merely
 * untidy: the copies had already drifted in their DEFAULTS — `money` defaulted
 * to two decimals on Monitor, Allocate, the approval queue, NavPanel and
 * ExecutionAnalytics, and to zero on Risk, RebalancePanel and CandidateVerdict;
 * `pct` defaulted to one decimal everywhere except Monitor, where it was two.
 * A reader comparing "cash 12.35%" on one page with "cash 12.3%" on another has
 * no way to know whether the fund moved or the formatter did.
 *
 * Two rules this module exists to keep, both inherited from the harness:
 *
 *   1. **Absence is never zero.** `null`/`undefined` render as an em dash, and
 *      that branch is first in every function. `money(0)` is "$0.00" — a
 *      MEASURED zero — and it must stay distinguishable from "—".
 *   2. **A unit conversion is never implicit.** `pct` formats a number that is
 *      ALREADY a percent (12.3 → "12.3%"). `pctFromFraction` formats a number
 *      that is a fraction (0.123 → "12.3%"). They are separate exports with
 *      separate names because the one call site that needed the second
 *      (ExecutionAnalytics' win rate) had silently defined its own `pct` doing
 *      the ×100 — and an import of the wrong one understates a win rate by
 *      100×. The test asserts the two disagree.
 *
 * Locale note: `toLocaleString(undefined, …)` follows the reader's locale for
 * grouping, exactly as all ten copies did. Kept rather than pinned to en-US so
 * this consolidation changes no rendered character anywhere.
 */

/** The one em dash the Studio uses for "no value". U+2014. */
export const DASH = "—";

/**
 * Dollars. `dp` decimal places, always exactly that many (min = max), so a
 * column of figures stays aligned under `tabular-nums`.
 *
 * Default 2 — the dominant convention (6 of the 10 retired copies). The
 * surfaces that had defaulted to 0 (Risk, RebalancePanel, CandidateVerdict)
 * now pass `0` explicitly at each call site rather than inheriting a different
 * default, so their rendering is unchanged to the character.
 */
export const money = (n?: number | null, dp = 2): string =>
  n == null
    ? DASH
    : `$${Number(n).toLocaleString(undefined, {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })}`;

/**
 * A number that is ALREADY a percentage, rendered as one. 12.3 → "12.3%".
 *
 * Default 1 decimal — the dominant convention (8 of the 9 retired copies).
 */
export const pct = (n?: number | null, dp = 1): string =>
  n == null ? DASH : `${Number(n).toFixed(dp)}%`;

/**
 * A number that is a FRACTION of one, rendered as a percentage. 0.123 → "12.3%".
 *
 * Deliberately not an option on `pct`. A boolean or a flag would make the two
 * conversions one call away from each other; a distinct name makes picking the
 * wrong one a visible mistake at the call site.
 */
export const pctFromFraction = (n?: number | null, dp = 1): string =>
  n == null ? DASH : `${(Number(n) * 100).toFixed(dp)}%`;

/**
 * Signed dollars, sign OUTSIDE the currency symbol: −$163.15, not $-163.15.
 *
 * The minus is U+2212 (a typographic minus), matching the two copies retired
 * from NavPanel and ExecutionAnalytics. A P&L cell reads at a glance from the
 * leading glyph, so the sign must come first.
 */
export const signedMoney = (n?: number | null, dp = 2): string =>
  n == null
    ? DASH
    : `${n >= 0 ? "+" : "−"}$${Math.abs(Number(n)).toLocaleString(undefined, {
        minimumFractionDigits: dp,
        maximumFractionDigits: dp,
      })}`;

/**
 * A signed percentage: +2.50% / -2.50%.
 *
 * Only the PLUS is added — the minus arrives from `toFixed` itself, which is
 * the ASCII hyphen-minus. That asymmetry is inherited verbatim from the two
 * retired copies and is kept so no rendered character changes; it is noted
 * here rather than "fixed" because a silent glyph change to every return
 * figure on NavPanel is not something a consolidation should smuggle in.
 */
export const signedPct = (n?: number | null, dp = 2): string =>
  n == null ? DASH : `${n >= 0 ? "+" : ""}${Number(n).toFixed(dp)}%`;

/**
 * Abbreviated dollars for backtest-scale figures: $1.2bn / $3.4m / $56k.
 *
 * Kept distinct from `money` rather than folded into it — this one is lossy by
 * design (it is for a LEAN result summary where the magnitude is the point),
 * and lossy formatting must never be reachable by passing a different `dp` to
 * the function the book's real dollars go through.
 *
 * Note the behaviour inherited verbatim from LeanResults: values below $1,000
 * still take the `k` branch, so $250 renders "$0k". Preserved rather than
 * corrected because this dispatch's mandate is consolidation, not a rendering
 * change; flagged here so the next reader knows it is known, not overlooked.
 */
export const moneyCompact = (n?: number | null): string =>
  n == null
    ? DASH
    : n >= 1e9
      ? `$${(n / 1e9).toFixed(1)}bn`
      : n >= 1e6
        ? `$${(n / 1e6).toFixed(1)}m`
        : `$${(n / 1e3).toFixed(0)}k`;
