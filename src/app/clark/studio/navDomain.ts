/**
 * A y-domain that survives a flat series.
 *
 * Recharts' `["auto", "auto"]` derives the range from the data, so a series
 * where every point is identical collapses to zero height and the line
 * degenerates against the axis edge — it reads as a broken chart.
 *
 * That is not an edge case for this fund. NAV is marked from prices, so the
 * moment the market closes every sample is the same number, and the intraday
 * chart is flat for the ~17.5 hours a day the venue is shut. Most of the time,
 * in other words.
 *
 * So a flat series gets a small symmetric band and draws down the middle, which
 * is the honest picture: nothing moved. The caller should also SAY nothing
 * moved — a flat line through the centre of a chart still invites the reader to
 * look for a trend in it.
 */

/** Fraction of the value to pad by when a series has no spread at all. */
const FLAT_PAD_RATIO = 0.001;   // 10bp — enough to render, too small to mislead
const MIN_PAD = 0.01;

export function navDomain(values: (number | null | undefined)[]): [number, number] | ["auto", "auto"] {
  const vs = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (vs.length === 0) return ["auto", "auto"];

  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  if (hi - lo > Number.EPSILON * Math.max(1, Math.abs(hi))) {
    return ["auto", "auto"];       // real spread — let recharts do its thing
  }

  const pad = Math.max(Math.abs(hi) * FLAT_PAD_RATIO, MIN_PAD);
  return [lo - pad, hi + pad];
}

/** True when every point is the same — worth telling the reader about. */
export function isFlat(values: (number | null | undefined)[]): boolean {
  const vs = values.filter((v): v is number => v != null && Number.isFinite(v));
  if (vs.length < 2) return false;
  const lo = Math.min(...vs);
  const hi = Math.max(...vs);
  return hi - lo <= Number.EPSILON * Math.max(1, Math.abs(hi));
}
