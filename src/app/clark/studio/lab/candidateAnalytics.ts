/**
 * Reading the belt's evidence — the arithmetic and the absence rules, apart
 * from the pixels.
 *
 * The CEO, three times on 2026-08-21: *"i can see monthend_rebalance_flow but
 * cant see the analytics behind"*. The spine keeps that evidence from the same
 * day (ClarkHarness `app/fund/runanalytics.py`); this module is the half of the
 * Lab panel that can be tested without a DOM — which matters here more than
 * usual, because every function below exists to keep an ABSENCE from rendering
 * as a number.
 *
 * Four things a fold can be, and this file refuses to collapse them:
 *
 *   * measurable — it has a retention figure, and the figure means something;
 *   * unmeasurable, strategy-side — it placed no trades, or the training leg
 *     made nothing worth retaining. A real finding;
 *   * unmeasurable, OURS — the engine ran out of wall clock and the container
 *     was killed. Six of these were read as findings about a rule before the
 *     reason was split out (quant seat, run-quant-entry11, 2026-08-21);
 *   * unchecked — `dates_honoured` is null. NOT the same as dishonoured, and
 *     not the same as honoured.
 *
 * Shapes here were read off the live endpoint's producer, not assumed:
 * `_rows()` in ClarkHarness `app/fund/factory.py` and `WalkForward.evaluate` in
 * `app/fund/walkforward.py`.
 */

/** The four typed absences the spine can report. Mirrors runanalytics.py. */
export const NOT_CAPTURED = "not_captured";
export const PRUNED = "pruned";
export const UNAVAILABLE = "unavailable";
export const NOT_TESTABLE = "not_testable";

export interface FoldRow {
  fold?: number;
  /** Requested window — what the belt ASKED the engine to cover. */
  train_start?: string | null;
  train_end?: string | null;
  test_start?: string | null;
  test_end?: string | null;
  /** Covered window — what the engine's own equity curve reported. */
  train_window?: string[] | null;
  test_window?: string[] | null;
  state?: string | null;
  sweep_id?: string | null;
  chosen?: Record<string, string> | null;
  train_return_pct?: number | null;
  test_return_pct?: number | null;
  test_orders?: number | null;
  test_psr_pct?: number | null;
  dates_honoured?: boolean | null;
  retention?: number | null;
  measurable?: boolean | null;
  timed_out?: boolean | null;
  reason?: string | null;
  basis?: string | null;
}

export interface SweepPoint {
  parameters?: Record<string, string> | null;
  state?: string | null;
  error?: string | null;
  total_return_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  psr_pct?: number | null;
  total_orders?: number | null;
  window?: string[] | null;
}

export interface AnalyticsEnvelope {
  available?: boolean;
  reason?: string | null;
  note?: string | null;
  pruned_at?: string | null;
  schema?: string;
  captured_at?: string | null;
  verification?: {
    present?: boolean;
    reason?: string | null;
    note?: string | null;
    job_id?: string | null;
    state?: string | null;
    wall_seconds?: number | null;
    parameters?: Record<string, string> | null;
    result?: {
      total_return_pct?: number | null;
      benchmark_return_pct?: number | null;
      sharpe?: number | null;
      max_drawdown_pct?: number | null;
      equity_curve?: number[] | null;
      equity_dates?: string[] | null;
      benchmark_curve?: number[] | null;
      orders?: { symbol?: string | null; side?: string | null; qty?: number | null;
                 price?: number | null; value?: number | null; time?: string | null }[] | null;
      orders_total?: number | null;
      orders_truncated?: boolean | null;
      orders_truncated_note?: string | null;
      statistics?: Record<string, string> | null;
      robustness?: Record<string, unknown> | null;
      capacity?: { capacity_usd?: number | null; reason?: string | null } | null;
    } | null;
  } | null;
  sweep?: {
    present?: boolean;
    reason?: string | null;
    note?: string | null;
    sweep_id?: string | null;
    points?: SweepPoint[] | null;
    summary?: {
      best?: { parameters?: Record<string, string> | null;
               total_return_pct?: number | null } | null;
      breakeven_cost?: { breakeven_bps?: number | null; reason?: string | null } | null;
    } | null;
    holdout?: Record<string, string> | null;
    holdout_result?: Record<string, unknown> | null;
  } | null;
  walkforward?: {
    present?: boolean;
    reason?: string | null;
    note?: string | null;
    hold_days?: number | null;
    hold_days_source?: string | null;
    folds?: FoldRow[] | null;
    folds_measurable?: number | null;
    folds_retained?: number | null;
    folds_timed_out?: number | null;
    median_retention?: number | null;
    verdict?: string | null;
  } | null;
}

export interface CandidateRow {
  candidate_id: string;
  algorithm: string;
  state?: string | null;
  passed?: boolean | null;
  failures?: string[] | null;
  error?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  grid?: Record<string, string[]> | null;
  holdout?: Record<string, string> | null;
  winner?: Record<string, string> | null;
  gate_version?: string | null;
  verdict?: { verdict?: string | null; passed?: boolean | null;
              failures?: string[] | null; gate_version?: string | null;
              checks?: Record<string, unknown> | null } | null;
  walkforward?: {
    folds_measurable?: number | null;
    folds_retained?: number | null;
    median_retention?: number | null;
    retained_share?: number | null;
    not_testable?: boolean | null;
    folds?: FoldRow[] | null;
  } | null;
  analytics_available?: boolean | null;
  analytics_absence?: { reason?: string | null; note?: string | null;
                        pruned_at?: string | null } | null;
  analytics?: AnalyticsEnvelope | null;
}

/* ------------------------------------------------------------------ folds */

export type FoldTone = "kept" | "lost" | "ours" | "theirs";

export interface FoldVerdict {
  /** Short label for the cell. Never a number when there is no number. */
  label: string;
  tone: FoldTone;
  /** The sentence the spine gave, when there is no figure. */
  reason: string | null;
  /** True only when the engine's clock, not the strategy, ended this fold. */
  ours: boolean;
}

/** The floor the gate and the folds share (ClarkHarness walkforward.RETENTION_FLOOR).
 *
 *  Duplicated here ONLY to colour a cell, never to decide anything: the retained
 *  count that the verdict rests on is computed server-side and read, not
 *  recomputed. A second implementation of a criterion is how two surfaces start
 *  disagreeing about the same strategy. */
export const RETENTION_FLOOR = 0.5;

/**
 * What one fold says, with a killed container kept apart from a real finding.
 *
 * `ours` is the field the panel colours on. A fold the engine killed is OUR
 * failure and demands "re-run it with more time"; a fold that placed no trades
 * is the strategy's and demands something else entirely. Rendering both as a
 * grey dash — which is what an unguarded `retention ?? "—"` does — merges them.
 */
export function foldVerdict(row: FoldRow): FoldVerdict {
  if (row.measurable !== true) {
    const ours = row.timed_out === true;
    return {
      label: ours ? "engine killed" : "not measured",
      tone: ours ? "ours" : "theirs",
      reason: row.reason ?? null,
      ours,
    };
  }
  const r = row.retention;
  if (r == null) {
    // measurable with no figure should be impossible; say so rather than print
    // a zero, because a silent 0% here reads as "kept none of its edge".
    return {
      label: "inconsistent record",
      tone: "theirs",
      reason: "the fold is marked measurable but carries no retention figure — " +
        "that is a defect in the record, not a result",
      ours: false,
    };
  }
  return {
    label: `${(r * 100).toFixed(0)}%`,
    tone: r >= RETENTION_FLOOR ? "kept" : "lost",
    reason: null,
    ours: false,
  };
}

export type HonouredState = "honoured" | "dishonoured" | "unchecked";

/**
 * Whether a fold's test leg really ran different dates from its training leg.
 *
 * THREE states, because `null` is a real one. The check needs both windows to
 * compare; when the engine reported only one, the answer is UNCHECKED — which
 * is not "honoured" (it would claim a validation that never happened) and not
 * "dishonoured" (it would accuse the algorithm of ignoring start/end on no
 * evidence). Falsy-coalescing this field in either direction is the bug.
 */
export function honoured(row: FoldRow): HonouredState {
  if (row.dates_honoured === true) return "honoured";
  if (row.dates_honoured === false) return "dishonoured";
  return "unchecked";
}

/** Requested vs covered, as one line, with each half absent on its own terms. */
export function windowLine(row: FoldRow): { requested: string; covered: string } {
  const req = row.test_start && row.test_end
    ? `${row.test_start} → ${row.test_end}`
    : "not recorded";
  const w = row.test_window;
  const cov = w && w.length >= 2 ? `${w[0]} → ${w[1]}` : "engine reported none";
  return { requested: req, covered: cov };
}

/**
 * The fold counts, read from the server's own summary rather than recomputed.
 *
 * `timedOut` is surfaced separately and deliberately: "2 of 4" is a different
 * claim when one of the missing two was our clock running out.
 */
export function foldTally(rows: FoldRow[] | null | undefined) {
  const list = rows ?? [];
  return {
    attempted: list.length,
    measurable: list.filter((f) => f.measurable === true).length,
    retained: list.filter((f) => f.measurable === true &&
      (f.retention ?? -Infinity) >= RETENTION_FLOOR).length,
    timedOut: list.filter((f) => f.timed_out === true).length,
  };
}

/* ------------------------------------------------------------- cost sweep */

export interface CostRow {
  /** The swept value, as text — never parsed into a number for display. */
  value: string;
  /** Basis points per side, when the parameter is a decimal fraction. */
  bps: number | null;
  returnPct: number | null;
  state: string | null;
  error: string | null;
}

/**
 * The cost band: return at each swept slippage, in ascending cost order.
 *
 * The gate reads ONE scalar out of `breakeven_cost`; the shape is what tells a
 * reader whether an edge dies at 3bps or at 50, and it was reachable only by
 * querying Postgres by hand. A point that FAILED keeps its row with its error —
 * dropping it would silently narrow the band and make a partial sweep look
 * complete.
 */
export function costBand(points: SweepPoint[] | null | undefined,
                         param = "slip"): CostRow[] {
  const rows: CostRow[] = [];
  for (const p of points ?? []) {
    const raw = (p.parameters ?? {})[param];
    if (raw == null) continue;
    const n = Number(raw);
    rows.push({
      value: String(raw),
      // Rounded to four decimals, because binary floating point does not have
      // 0.0003: `0.0003 * 10_000` is 2.9999999999999996 and would have printed
      // as cost-band noise beside an exact "1" and "5". Four decimals keeps
      // sub-basis-point grids exact and is far finer than any cost this fund
      // can measure.
      bps: Number.isFinite(n) ? Math.round(n * 10_000 * 1e4) / 1e4 : null,
      returnPct: p.total_return_pct ?? null,
      state: p.state ?? null,
      error: p.error ?? null,
    });
  }
  rows.sort((a, b) => (a.bps ?? Infinity) - (b.bps ?? Infinity));
  return rows;
}

/**
 * The one sentence the cost band deserves.
 *
 * "still profitable at every cost tested" and "never measured" are opposite
 * findings and the spine already distinguishes them; this only refuses to turn
 * either into a number.
 */
export function breakevenSentence(
  be: { breakeven_bps?: number | null; reason?: string | null } | null | undefined,
  swept: number,
): string {
  if (be?.breakeven_bps != null) {
    return `The edge crosses zero at ${be.breakeven_bps}bps of slippage per side.`;
  }
  if (be?.reason) return be.reason;
  if (swept <= 1) {
    return "Only one cost was tested, so there is no band — a single point " +
      "cannot say where the edge dies, and the gate reads that as NOT MEASURED " +
      "rather than as robust.";
  }
  return "No breakeven was computed. Not measured is not the same as robust.";
}

/* --------------------------------------------------------------- absence */

export interface AbsenceView { reason: string; note: string; prunedAt?: string | null }

/**
 * Why there is nothing to render, in the candidate's own words.
 *
 * Never invents a sentence: the spine ships one with every absence, and a
 * client-side fallback that read "no data" would erase the distinction between
 * "judged before we kept evidence" and "the payload aged out". The fallback
 * below fires only if the field itself is missing, and says exactly that.
 */
export function absenceOf(c: CandidateRow): AbsenceView | null {
  if (c.analytics_available === true) return null;
  if (c.analytics?.available === true) return null;
  const a = c.analytics_absence ?? c.analytics ?? null;
  const reason = (a?.reason as string | undefined) ?? UNAVAILABLE;
  const note = (a?.note as string | undefined) ??
    "the spine reported no analytics for this run and gave no reason — that " +
    "gap is in the record, not in the strategy";
  return { reason, note, prunedAt: (a as { pruned_at?: string | null })?.pruned_at ?? null };
}

/** A short badge for the index, distinct per absence. */
export function absenceLabel(reason: string | null | undefined): string {
  switch (reason) {
    case NOT_CAPTURED: return "not captured";
    case PRUNED: return "aged out";
    case NOT_TESTABLE: return "not testable";
    case UNAVAILABLE: return "unavailable";
    default: return "unknown";
  }
}

/* ------------------------------------------------------------ the curve */

/**
 * A price/equity series rebased to 1.0 at its own first point.
 *
 * DEFECT FOUND BY LOOKING, 2026-08-21. `EquityChart`'s docstring claimed "the
 * series are already normalised to 1.0" and formatted its axis as
 * `(v - 1) * 100`%. They are not normalised: the engine reports raw account
 * equity. Measured on a real job (53ef3e67d89a):
 *
 *     equity     100000.0 → 102746.10   (min 93496.73, max 103468.05)
 *     benchmark     683.68 →    734.30   (min 630.35,   max 757.62)
 *
 * Two consequences, both live in the shipped Lab before this:
 *
 *   1. the axis labels read "10346705%", "5204820%", "62935%";
 *   2. worse, the two series share ONE axis in RAW units, so a benchmark near
 *      684 was drawn flat against the floor beneath an equity near 100,000 —
 *      and the strategy-versus-buy-and-hold comparison the chart exists for was
 *      not merely mislabelled, it was not visible at all. The break-even line,
 *      guarded by `lo <= 1 && hi >= 1`, could never draw either.
 *
 * Rebasing each series to its OWN start is the only comparison that means
 * anything when the two are quoted in different units — it plots percentage
 * growth from a common origin, which is what the reader is being asked to
 * compare.
 *
 * Returns null rather than a rescued array when the base is zero or not finite:
 * dividing by it would emit Infinity or NaN into an SVG path, and a chart drawn
 * from a broken series is worse than a stated absence.
 */
export function rebase(series: number[] | null | undefined): number[] | null {
  if (!series || series.length < 2) return null;
  const base = series[0];
  if (!Number.isFinite(base) || base === 0) return null;
  const out = series.map((v) => v / base);
  return out.every((v) => Number.isFinite(v)) ? out : null;
}

/* ----------------------------------------------------------- gate verdict */

/**
 * The gate's own sentence, verbatim, plus its failures.
 *
 * Never re-worded and never summarised into a score. The gate returns sentences
 * precisely so a verdict cannot be negotiated ("0.61 is nearly 0.65"), and a UI
 * that paraphrased them would hand that back.
 */
export function gateSentence(c: CandidateRow): {
  sentence: string; failures: string[]; version: string | null; passed: boolean | null;
} {
  const v = c.verdict ?? null;
  const failures = v?.failures ?? c.failures ?? [];
  const passed = v?.passed ?? c.passed ?? null;
  const version = v?.gate_version ?? c.gate_version ?? null;
  const sentence = v?.verdict
    ?? (c.state === "orphaned"
      ? "ORPHANED — the runner died before this could be judged. Neither passed nor killed."
      : c.error
        ? `no verdict: ${c.error}`
        : "no verdict was stored for this candidate");
  return { sentence, failures, version, passed };
}
