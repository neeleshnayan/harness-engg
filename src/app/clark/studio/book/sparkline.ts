/**
 * NAV AS A LINE — the geometry, with no React and no chart library.
 *
 * WHY NOT RECHARTS, which this studio already ships. A sparkline in a page
 * header has no axes, no grid, no tooltip, no legend and no responsiveness
 * beyond its own box; every one of those is what a charting library is FOR,
 * and importing one to draw a polyline puts a `ResponsiveContainer` and a
 * resize observer in the header of the page the CEO opens first. The
 * `NavPanel` on Monitor is the full chart and stays exactly as it is.
 *
 * THE SERIES IS THE STRUCK ONE AND ONLY THE STRUCK ONE. `GET /fund/nav` also
 * carries a `live` figure computed at request time; drawing it as the last
 * point of this line would put two different bases on one curve — a durable
 * fold of the event log, and a marks-right-now number that no event records.
 * The live figure belongs beside the line as a number with its own label, and
 * the header renders it that way.
 *
 * WHAT THE READER LEARNS BEFORE READING A WORD: whether the fund's value is
 * going up, down, or nowhere, and whether the last point broke the pattern.
 * Nothing else. A sparkline that tries to answer more needs axes, and a
 * header with axes in it is a chart that wandered upstairs.
 */

export interface SparkPoint {
  ts?: string | null;
  total_nav_usd?: number | null;
}

export type SparkState = "line" | "too_few" | "flat" | "unreadable";

export interface Spark {
  state: SparkState;
  /** The `d` of a single `<path>`, in the viewBox below. `null` unless the
   *  state is `line` — a caller must not be able to draw an empty string as
   *  a path and get a silent nothing where a sentence belonged. */
  path: string | null;
  /** The final point, for the emphasis dot. `null` unless `line`. */
  last: { x: number; y: number } | null;
  /** How many points were drawn, and how many were offered. Two numbers
   *  because a series that lost half its rows to unreadable values must not
   *  report the survivors as the whole. */
  drawn: number;
  offered: number;
  /** The value range the line spans, for the caller's own label. */
  lowUsd: number | null;
  highUsd: number | null;
  firstUsd: number | null;
  lastUsd: number | null;
  /** The window the line covers, from the points' own stamps. */
  fromTs: string | null;
  toTs: string | null;
  note: string;
}

//: The viewBox the path is drawn in. Unitless — the SVG scales to whatever
//: box the component gives it, so these are shape constants and not sizes.
export const SPARK_W = 100;
export const SPARK_H = 24;
//: Half the stroke, kept clear at top and bottom so the extremes are not
//: clipped by the viewBox edge. Measured against a 1.5-unit stroke.
export const SPARK_PAD = 1.5;

//: Two points is a line, not a curve — the same rule and the same number
//: `NavPanel` uses, and it is imported nowhere because these are two
//: different surfaces with the same honest floor. Below this the caller
//: states the fact instead of drawing a shape.
export const MIN_POINTS = 3;

//: A series whose whole range is under this fraction of its own level is
//: FLAT, and drawing it stretched to the full height would turn rounding
//: noise into a mountain range. 0.05% of $2,000 is $1.
export const FLAT_RANGE_FRACTION = 0.0005;

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/**
 * The line, from the history the spine serves.
 *
 * `null` in means the read failed and the result says so. An EMPTY ARRAY is a
 * different input — the fund has struck no NAV — and gets its own sentence.
 * The two must never converge: one is an outage and one is a young fund.
 */
export function sparkline(points: readonly SparkPoint[] | null | undefined): Spark {
  const base: Spark = {
    state: "unreadable", path: null, last: null, drawn: 0, offered: 0,
    lowUsd: null, highUsd: null, firstUsd: null, lastUsd: null,
    fromTs: null, toTs: null,
    note: "the NAV history could not be read, so the fund's track is UNKNOWN "
      + "— not flat",
  };
  if (!points) return base;

  const offered = points.length;
  const usable = points
    .map((p) => ({ ts: p.ts ?? null, v: num(p.total_nav_usd) }))
    .filter((p): p is { ts: string | null; v: number } => p.v != null);

  if (usable.length < MIN_POINTS) {
    return {
      ...base, state: "too_few", offered, drawn: usable.length,
      firstUsd: usable[0]?.v ?? null,
      lastUsd: usable[usable.length - 1]?.v ?? null,
      fromTs: usable[0]?.ts ?? null,
      toTs: usable[usable.length - 1]?.ts ?? null,
      note: offered === 0
        ? "the fund has struck no NAV yet, so there is no track to draw"
        : `${usable.length} of ${offered} strike(s) carry a readable figure — `
          + `fewer than the ${MIN_POINTS} a line needs. Two points is a line, `
          + "not a track record",
    };
  }

  const values = usable.map((p) => p.v);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const level = Math.abs(high) || 1;
  const range = high - low;

  const common = {
    offered, drawn: usable.length, lowUsd: low, highUsd: high,
    firstUsd: values[0], lastUsd: values[values.length - 1],
    fromTs: usable[0].ts, toTs: usable[usable.length - 1].ts,
  };

  if (range / level < FLAT_RANGE_FRACTION) {
    /* A DEAD FLAT SERIES IS A FINDING, and stretching it to fill the box
     * would render $0.30 of drift as a dramatic climb. The caller says so in
     * words rather than drawing a shape that means nothing. */
    return {
      ...base, ...common, state: "flat",
      note: `${usable.length} strike(s) spanning $${range.toFixed(2)} — the `
        + "series is flat at this scale, so the shape of a line would be noise "
        + "drawn as signal",
    };
  }

  const stepX = (SPARK_W - SPARK_PAD * 2) / (usable.length - 1);
  const usableH = SPARK_H - SPARK_PAD * 2;
  const xy = values.map((v, i) => ({
    x: SPARK_PAD + i * stepX,
    // SVG's y grows DOWNWARD, so a higher NAV is a SMALLER y. Getting this
    // backwards draws a losing fund as a winning one, which is the single
    // worst thing this function could do.
    y: SPARK_PAD + usableH * (1 - (v - low) / range),
  }));

  const path = xy
    .map((p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(2)} ${p.y.toFixed(2)}`)
    .join(" ");

  const dropped = offered - usable.length;
  return {
    ...base, ...common, state: "line", path,
    last: xy[xy.length - 1],
    note: `${usable.length} strike(s), $${low.toFixed(2)} to $${high.toFixed(2)}`
      + (dropped > 0
        ? ` — ${dropped} strike(s) carried no readable figure and are NOT drawn`
        : ""),
  };
}

/** The move from first to last, as a fraction. `null` when there is nothing
 *  to compare or the base is zero. Its own function so the header does not
 *  do arithmetic in JSX. */
export function sparkChange(s: Spark): number | null {
  if (s.firstUsd == null || s.lastUsd == null || s.firstUsd === 0) return null;
  return (s.lastUsd - s.firstUsd) / Math.abs(s.firstUsd);
}
