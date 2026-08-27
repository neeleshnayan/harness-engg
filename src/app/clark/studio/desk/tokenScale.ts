/**
 * How a token count is spoken. ONE implementation, three absence contracts.
 *
 * THE DEFECT, and the CEO said it in the plainest possible way: the desk
 * printed `18863k` where a person says `18.9M`. Eighteen thousand eight
 * hundred and sixty-three thousand is not a number anybody reads; it is a
 * number a formatter produced because it had no branch above a thousand.
 *
 * THREE IMPLEMENTATIONS OF ONE RULE EXISTED, and each was wrong differently:
 *
 *   | function                     | 999,999   | 18,863,000 |
 *   |------------------------------|-----------|------------|
 *   | `seatLib.fmtTokens`          | `1000k`   | `18863k`   |
 *   | `deskTelemetry.fmtTokensCompact` | `1000k` | `18.9M`  |
 *   | `briefing.fmtTokensShort`    | `1000k`   | `18.9M`   |
 *
 * All three round 999,999 to `1000k` — a four-digit thousands figure, which
 * is the same defect as `18863k` at one twentieth the size, and the reason
 * this is a rounding rule rather than a magnitude test. `Math.round(n/1000)`
 * hitting 1000 means the value has REACHED the next unit and must be spoken
 * in it.
 *
 * WHY ONE CORE AND THREE WRAPPERS RATHER THAN ONE FUNCTION. The three call
 * sites disagree about ABSENCE, and they are all correct to:
 *
 *   * `fmtTokens` renders inline in a sentence and wants an em dash;
 *   * `fmtTokensCompact` sits in a stat tile and wants an em dash;
 *   * `fmtTokensShort` returns `null` so `cto/page.tsx` can substitute a
 *     whole clause ("no token totals filed") rather than a dash.
 *
 * Absence is a rendering decision that belongs to the reader's context; the
 * SCALE is not. So the scale is written once and the wrappers are three lines
 * each — which is the opposite of the old arrangement, where the absence
 * contracts agreed and the arithmetic did not.
 *
 * NEVER A ZERO FOR AN ABSENCE. `0` is a measured figure (a run that reported
 * zero tokens) and `null`/`undefined`/`NaN` mean nobody reported one. This
 * module keeps them apart, because "the seat ran for free" and "we do not
 * know what the seat cost" are opposite claims about whether to worry.
 */

//: Where thousands begin. A count below this is spoken in full — three digits
//: are as readable as `0.4k` and one fewer transformation to distrust.
export const K = 1_000;
//: Where millions begin.
export const M = 1_000_000;

/**
 * The scale, and nothing else. Finite numbers only — the wrappers own absence.
 *
 * THE CARRY IS THE POINT. Round first, then check whether the rounded value
 * has reached the next unit: 999,999 rounds to 1000 thousands, which is a
 * million and is spoken `1.0M`. Testing the RAW value against the boundary
 * (`n >= 1_000_000`) is what produced `1000k`, and every one of the three
 * implementations made exactly that mistake.
 *
 * Negatives are formatted by magnitude with the sign restored. A token count
 * should never be negative; if one ever is, `-18.9M` is a legible symptom and
 * `-18863k` is a second bug on top of the first.
 */
export function tokenScale(n: number): string {
  const neg = n < 0;
  const abs = Math.abs(n);
  if (abs < K) return `${n}`;

  const sign = neg ? "-" : "";
  if (abs < M) {
    const k = Math.round(abs / K);
    // The carry: 999,999 -> 1000k -> 1.0M.
    if (k >= K) return `${sign}${(k / K).toFixed(1)}M`;
    return `${sign}${k}k`;
  }
  const m = abs / M;
  // 999,999,999 -> 1000.0M -> 1000M is still legible and this fund will never
  // see it; a B unit for a figure that cannot occur is dead code with a test.
  return `${sign}${m.toFixed(1)}M`;
}

/** True when this value carries no measurement — as opposed to a measured
 *  zero, which is a figure and renders as one. */
export function tokensAbsent(n: number | null | undefined): boolean {
  return n == null || !Number.isFinite(n);
}

/** Inline-in-a-sentence rendering. Em dash for absent. */
export function fmtTokens(n: number | null | undefined): string {
  return tokensAbsent(n) ? "—" : tokenScale(n as number);
}

/** Stat-tile rendering. Identical to `fmtTokens`; kept as its own name because
 *  two call sites import it and a rename is churn with no reader benefit. */
export const fmtTokensCompact = fmtTokens;

/** Rendering for a caller that substitutes its own CLAUSE for absence.
 *  `null` out, deliberately — `cto/page.tsx` prints "no token totals filed",
 *  which a dash cannot say. */
export function fmtTokensShort(n: number | null | undefined): string | null {
  return tokensAbsent(n) ? null : tokenScale(n as number);
}
