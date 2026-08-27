/**
 * THE BOOK AS A PICTURE — one strip, every holding's width is its weight.
 *
 * The CEO's desk has never rendered the book at all. What the fund HOLDS was
 * a number on a different page, and "am I concentrated" was a question that
 * needed a table read row by row. A strip answers it in one glance: seven
 * segments of visibly different widths, and a visible void where the cash is.
 *
 * CASH IS DRAWN, NOT OMITTED, and that is the design decision this module
 * turns on. A strip of positions alone always fills its track, so a fund 71%
 * in cash and a fund 0% in cash draw the identical picture. Cash is the
 * VOID — an unfilled region with a border and a label — so "how much of this
 * fund is not doing anything" is the first thing the eye reads.
 *
 * WHAT THIS MODULE REFUSES TO DO:
 *
 *   * **It never computes a weight from a price.** Every figure comes from
 *     the spine's own `usd_value`, which the NAV fold produced. A UI that
 *     multiplied `qty * mark` would be a second NAV, and NAV folds from the
 *     event log only.
 *   * **It never renormalises to make the strip add up.** If the parts do not
 *     sum to the stated total, that DISAGREEMENT is the finding and it is
 *     published (`residualPct`), because a strip silently scaled to 100% is a
 *     picture that can never be wrong.
 *   * **It never renders an unreadable book as an empty one.** `null` in,
 *     `unreadable` out — a flat empty track and a fund holding nothing are
 *     different facts.
 */

/** One holding, exactly as `GET /fund/nav` serves it. */
export interface BookPosition {
  symbol?: string | null;
  usd_value?: number | null;
  qty?: number | null;
  mark?: number | null;
}

/** The `live` or `last_struck` block of `GET /fund/nav`. */
export interface BookSource {
  ts?: string | null;
  total_nav_usd?: number | null;
  positions?: readonly BookPosition[] | null;
  breakdown?: { cash?: number | null; positions?: number | null } | null;
}

export type BookState = "book" | "flat" | "unreadable";

export interface BookSegment {
  /** `null` for the cash void — cash is not a holding and does not get a
   *  ticker, and giving it one would put it in the same list as SPY. */
  symbol: string | null;
  kind: "position" | "cash";
  usd: number;
  /** `0`..`1` of the stated total. */
  weight: number;
  label: string;
}

export interface BookStrip {
  state: BookState;
  segments: BookSegment[];
  /** The denominator every weight is against. `null` when unreadable. */
  totalUsd: number | null;
  cashUsd: number | null;
  cashWeight: number | null;
  /** The largest single POSITION's weight — the concentration answer, which
   *  is what a reader is really asking the strip. `null` with no positions. */
  topWeight: number | null;
  topSymbol: string | null;
  positionCount: number;
  /**
   * `total - (cash + positions)`, as a fraction of total. `0` when they
   * reconcile. PUBLISHED rather than absorbed: a strip that renormalises to
   * fill its track cannot show that the parts disagree with the whole, and
   * this fund's non-negotiables put that disagreement on the surface.
   */
  residualPct: number | null;
  /** How old this reading is, and from which block. */
  asOf: string | null;
  note: string;
}

const EMPTY: BookStrip = {
  state: "unreadable", segments: [], totalUsd: null, cashUsd: null,
  cashWeight: null, topWeight: null, topSymbol: null, positionCount: 0,
  residualPct: null, asOf: null,
  note: "the fund's NAV block could not be read, so what it holds is UNKNOWN "
    + "— not empty",
};

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/**
 * The strip, from ONE nav block.
 *
 * THE UNREADABLE CASE IS AN INPUT VALUE. `null` in gives `unreadable` out
 * with every field absent — a caller must not be able to hand in an empty
 * positions array and then correct `state` afterwards, which is the shape
 * that produces a payload contradicting itself.
 */
export function bookStrip(src: BookSource | null | undefined): BookStrip {
  if (!src) return { ...EMPTY, segments: [] };

  const total = num(src.total_nav_usd);
  if (total == null || total <= 0) {
    return {
      ...EMPTY, segments: [], asOf: src.ts ?? null,
      note: total == null
        ? "the fund stated no total NAV, so no weight can be computed — the "
          + "book is UNKNOWN, not empty"
        : "the fund's stated total NAV is not positive, so a weight has no "
          + "meaning here",
    };
  }

  const cash = num(src.breakdown?.cash);
  const rows = (src.positions ?? [])
    .map((p) => ({ symbol: (p.symbol ?? "").trim(), usd: num(p.usd_value) }))
    // A position with no usd_value is DROPPED from the strip and counted in
    // the residual below rather than drawn at zero width — an invisible
    // segment is a lie with no pixels.
    .filter((p): p is { symbol: string; usd: number } =>
      !!p.symbol && p.usd != null && p.usd > 0)
    .sort((a, b) => b.usd - a.usd);

  const segments: BookSegment[] = rows.map((r) => ({
    symbol: r.symbol, kind: "position" as const, usd: r.usd,
    weight: r.usd / total,
    label: `${r.symbol} · ${((r.usd / total) * 100).toFixed(1)}% · $${r.usd.toFixed(0)}`,
  }));

  if (cash != null && cash > 0) {
    segments.push({
      symbol: null, kind: "cash", usd: cash, weight: cash / total,
      label: `cash · ${((cash / total) * 100).toFixed(1)}% · $${cash.toFixed(0)}`,
    });
  }

  const held = rows.reduce((s, r) => s + r.usd, 0);
  const accounted = held + (cash ?? 0);
  const residual = (total - accounted) / total;
  const top = rows[0] ?? null;

  const state: BookState = rows.length === 0 ? "flat" : "book";
  return {
    state,
    segments,
    totalUsd: total,
    cashUsd: cash,
    cashWeight: cash == null ? null : cash / total,
    topWeight: top ? top.usd / total : null,
    topSymbol: top ? top.symbol : null,
    positionCount: rows.length,
    residualPct: residual,
    asOf: src.ts ?? null,
    note: bookNote(state, rows.length, cash, total, residual),
  };
}

/** How far from 1.0 the parts may sit before the strip says so.
 *  Half a percent of a $2,000 fund is $10 — below the rounding the payload
 *  itself carries, and above anything a real disagreement would hide in. */
export const RESIDUAL_TOLERANCE = 0.005;

function bookNote(state: BookState, n: number, cash: number | null,
                  total: number, residual: number): string {
  if (state === "flat") {
    return cash == null
      ? "the fund holds no positions, and its cash figure could not be read"
      : `the fund holds no positions — all $${cash.toFixed(0)} of it is cash`;
  }
  const base = `${n} position${n === 1 ? "" : "s"} against `
    + `$${total.toFixed(0)} of NAV`;
  if (Math.abs(residual) > RESIDUAL_TOLERANCE) {
    // THE DISAGREEMENT IS THE FINDING. Stated, never absorbed.
    return `${base}. The parts do not add up to the whole: cash plus positions `
      + `leaves ${(residual * 100).toFixed(1)}% of NAV unaccounted for, so this `
      + "strip is drawn against the stated total and does not fill it";
  }
  return `${base}, cash included`;
}

/**
 * The plain-English sentence for a reader who wants one.
 *
 * Deliberately ONE sentence and deliberately about CONCENTRATION, because
 * that is the question a strip is scanned for and the one a list of weights
 * makes you compute yourself.
 */
export function bookHeadline(s: BookStrip): string {
  if (s.state === "unreadable") return s.note;
  if (s.state === "flat") return s.note;
  const top = `${s.topSymbol} is the largest holding at `
    + `${((s.topWeight ?? 0) * 100).toFixed(0)}% of the fund`;
  if (s.cashWeight == null) return `${top}; the cash figure could not be read.`;
  return `${top}, and ${(s.cashWeight * 100).toFixed(0)}% is cash.`;
}
