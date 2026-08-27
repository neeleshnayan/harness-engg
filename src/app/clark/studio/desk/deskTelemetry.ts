/**
 * Desk telemetry — is the seat running, how often today, at what token cost.
 *
 * The CEO's ask (2026-08-21). Three figures, and the whole reason this is a
 * module rather than three expressions in JSX is that each of them has a
 * DIFFERENT way of being absent, and on a dashboard all three absences look
 * exactly like a quiet day:
 *
 *   running now  — the dispatch/resolve fold the spine already computes. The
 *                  desk card has shown it as a dot for a while; the CEO asked
 *                  for it as a WORD, because a dot is a thing you notice only
 *                  if you were already looking at that card.
 *   runs today   — exact, from the spine's UTC day window. NOT folded from
 *                  `desk.runs`, which is capped at the 25 most recent runs
 *                  ACROSS ALL SEATS: on a day with 26 runs that fold silently
 *                  drops one, and the seat it drops is the quietest one.
 *   tokens today — a sum that is only a TOTAL when every run in it reported a
 *                  figure. When some did not, it is a floor and is rendered
 *                  with a "≥". Rendering a floor flat understates the bill by
 *                  whatever the silent runs cost, which is the same error the
 *                  cost model already caught once at model-pricing level.
 *
 * The dollar figure is computed HERE, from `tokens_by_model` and seatLib's
 * price table, so the table stays in one place. An unpriced model contributes
 * NOTHING and makes the estimate a floor too — never a default-priced guess.
 */

import type { DeskView } from "@/lib/fund_api";
// `Absent` is imported as a TYPE separately: node's type-stripping keeps value
// imports at runtime, and an interface in a value import list is a runtime
// error the compiler will not catch (`isolatedModules` allows the write).
import type { Absent } from "./seatLib.ts";
import { absent, estimateCostUsd, priceRowFor } from "./seatLib.ts";

/** The spine's per-seat rollup, as `GET /fund/desk` returns it. Optional on the
 *  type because a spine that predates the rollup returns nothing here — and the
 *  page must render that as a stated gap, not as zeros. */
export interface SpineSeatTelemetry {
  running_now: boolean;
  running_task: string | null;
  running_since: string | null;
  runs_today: number | null;
  tokens_today: number | null;
  tokens_partial: boolean;
  runs_missing_tokens: number | null;
  tokens_by_model: Record<string, number>;
  last_run_at: string | null;
}

export interface SpineTelemetryBlock {
  day: string;
  readable: boolean;
  seats: Record<string, SpineSeatTelemetry>;
  note: string;
}

export interface SeatTelemetry {
  seat: string;
  /** The UTC day the counts are for, or null when nothing could be read. */
  day: string | null;
  runningNow: boolean;
  /** THE THIRD DISPATCH STATE: the seat returned and the chair has not
   *  reviewed it. Mutually exclusive with `runningNow` — a returned seat is
   *  an obligation on the chair, not a busy bench slot, and reading it as
   *  "running" is what made two finished dispatches look live for 21 and 19
   *  hours on 2026-08-22. */
  awaitingReview: boolean;
  /** The run that came back, when the spine could identify it. */
  returnedRunId: string | null;
  runningTask: string | null;
  runningSince: string | null;
  /** A number when the recorder was read, an `Absent` sentence when it was not.
   *  Zero here is a MEASURED zero: the day window was queried and was empty. */
  runsToday: number | Absent;
  /** A number, or `Absent` when no run in the day reported a token figure. */
  tokensToday: number | Absent;
  /** True when SOME runs reported and some did not — the sum is a floor. */
  tokensPartial: boolean;
  /** How many of today's runs recorded no token figure. */
  runsMissingTokens: number | null;
  /** Blended $ estimate over today's runs, or null when nothing could be
   *  priced. Null is not $0 — see seatLib.estimateCostUsd. */
  costUsdToday: number | null;
  /** Tokens the cost estimate could NOT price, because their model is not in
   *  the table. Non-zero makes the dollar figure a floor as well. */
  unpricedTokens: number;
  /** Where the figures came from, so the surface can say so. */
  source: "spine" | "unavailable";
}

/** The absence sentence used when the whole desk read failed. */
const DESK_UNREADABLE = absent(
  "runs and token cost today",
  "GET /fund/desk could not be read — this is an unknown, not a quiet desk",
);

/** The absence sentence used when the spine has no rollup (older deployment). */
const NO_ROLLUP = absent(
  "runs and token cost today",
  "this spine does not return `seat_telemetry` on GET /fund/desk yet — folding " +
  "it from the capped 25-run payload would put a floor on screen dressed as a count",
);

/** The absence sentence used when the flight recorder itself was unreadable. */
const RECORDER_UNREADABLE = absent(
  "runs and token cost today",
  "the flight recorder could not be read for today's window",
);

/**
 * One seat's telemetry, from a desk payload that may be null, may predate the
 * rollup, or may report the recorder as unreadable.
 *
 * There is deliberately NO client-side fallback that folds `view.runs` into a
 * count. That fold is available, it is easy, and it is wrong: the payload's run
 * list is capped across all seats, so the number it produces is a floor. The
 * desk has already shipped one number of exactly that shape (`desk_load` read
 * 73 against 10 truly open, 3.65x, and it took a COO triage to notice). An
 * absence sentence a reader can act on beats a plausible wrong number every
 * time.
 */
export function seatTelemetry(
  view: DeskView | null | undefined,
  seat: string,
): SeatTelemetry {
  const base: SeatTelemetry = {
    seat,
    day: null,
    runningNow: false,
    awaitingReview: false,
    returnedRunId: null,
    runningTask: null,
    runningSince: null,
    runsToday: DESK_UNREADABLE,
    tokensToday: DESK_UNREADABLE,
    tokensPartial: false,
    runsMissingTokens: null,
    costUsdToday: null,
    unpricedTokens: 0,
    source: "unavailable",
  };
  if (!view) return base;

  // Running-now survives even when the rollup does not: it is folded from the
  // roster the desk payload has always carried.
  const rosterRow = view.roster?.find((r) => r.agent === seat);
  const runningFromRoster = rosterRow?.activity?.status === "working";
  // The third state is folded the same way, from the same roster, and is
  // EXCLUSIVE with running: `status` is one string, so a returned dispatch can
  // never also read as a busy seat.
  const awaitingFromRoster = rosterRow?.activity?.status === "awaiting_review";
  const openFromRoster = runningFromRoster || awaitingFromRoster;
  base.runningNow = runningFromRoster;
  base.awaitingReview = awaitingFromRoster;
  base.returnedRunId = awaitingFromRoster
    ? rosterRow?.activity?.returned_run_id ?? null
    : null;
  // The task and the clock belong to the DISPATCH, which is still open in both
  // live states — blanking them the moment a run lands would erase what the
  // chair now owes a review on.
  base.runningTask = openFromRoster ? rosterRow?.activity?.task ?? null : null;
  base.runningSince = openFromRoster ? rosterRow?.activity?.since ?? null : null;

  const block = view.seat_telemetry;
  if (!block) {
    return { ...base, runsToday: NO_ROLLUP, tokensToday: NO_ROLLUP };
  }
  base.day = block.day ?? null;
  if (!block.readable) {
    return { ...base, runsToday: RECORDER_UNREADABLE, tokensToday: RECORDER_UNREADABLE };
  }

  const row = block.seats?.[seat];
  if (!row) {
    // The rollup was readable and this seat is not in it. That is a roster
    // disagreement, not a quiet seat, and it is worth saying out loud.
    return {
      ...base,
      runsToday: absent("runs today",
        `the spine's telemetry block does not carry a row for "${seat}"`),
      tokensToday: absent("tokens today",
        `the spine's telemetry block does not carry a row for "${seat}"`),
    };
  }

  // running_now from the rollup wins where present — same fold, one hop closer
  // to the events it came from. Same for the third state, with one asymmetry
  // that matters: `awaiting_review` is OPTIONAL on the wire, so an absent key
  // falls back to the roster rather than reading as `false`. A spine that
  // predates the split would otherwise report every returned seat as not
  // awaiting, which is the state this whole change exists to make visible.
  const running = row.running_now ?? runningFromRoster;
  const awaiting = row.awaiting_review ?? awaitingFromRoster;
  const open = running || awaiting;

  let cost: number | null = null;
  let unpriced = 0;
  for (const [model, tokens] of Object.entries(row.tokens_by_model || {})) {
    const c = estimateCostUsd(model, tokens);
    if (c == null) {
      // An unknown model contributes no dollars. Pricing it at Opus rates for a
      // run that was actually Fable understates the bill by 2x — the exact
      // error the cost model caught in the real record.
      if (priceRowFor(model) == null) unpriced += tokens;
      continue;
    }
    cost = (cost ?? 0) + c;
  }

  return {
    seat,
    day: block.day ?? null,
    runningNow: running,
    awaitingReview: awaiting,
    returnedRunId: awaiting
      ? row.returned_run_id ?? base.returnedRunId
      : null,
    runningTask: open ? row.running_task ?? base.runningTask : null,
    runningSince: open ? row.running_since ?? base.runningSince : null,
    runsToday: row.runs_today ?? absent("runs today", "the rollup returned no count"),
    tokensToday: row.tokens_today == null
      ? absent("tokens today",
               (row.runs_today ?? 0) === 0
                 ? "no run resolved for this seat today"
                 : "no run this seat resolved today recorded a token figure")
      : row.tokens_today,
    tokensPartial: !!row.tokens_partial,
    runsMissingTokens: row.runs_missing_tokens ?? null,
    costUsdToday: cost,
    unpricedTokens: unpriced,
    source: "spine",
  };
}

/** Compact token rendering: `480k`, `1.2M`, `900`. A dash for absent — never a
 *  zero, because "no figure" and "measured zero tokens" mean opposite things
 *  about whether the seat ran.
 *
 *  RE-EXPORTED FROM `tokenScale.ts` (2026-08-27). This body was the closest of
 *  the three to right and still rendered 999,999 as `1000k`: it tested the RAW
 *  value against the million boundary instead of the ROUNDED one, so a figure
 *  that had already carried into millions was spoken in four-digit thousands. */
import { fmtTokensCompact } from "./tokenScale.ts";
export { fmtTokensCompact };

/** The floor marker. A sum missing one run's figure is "≥", and the reason is
 *  put in the caller's title attribute rather than implied. */
export function tokensLabel(t: SeatTelemetry): string {
  if (typeof t.tokensToday !== "number") return "—";
  const floor = t.tokensPartial || t.unpricedTokens > 0;
  return `${floor ? "≥" : ""}${fmtTokensCompact(t.tokensToday)}`;
}

export function costLabel(t: SeatTelemetry): string {
  if (t.costUsdToday == null) return "—";
  const floor = t.tokensPartial || t.unpricedTokens > 0;
  return `${floor ? "≥" : "≈"}$${t.costUsdToday.toFixed(t.costUsdToday < 10 ? 2 : 0)}`;
}

/**
 * The sentence a reader needs to interpret the two numbers beside it.
 *
 * Always returned, never conditional: a figure whose caveat is only rendered
 * when there IS a caveat trains the reader to skip the caveat line.
 */
export function telemetryNote(t: SeatTelemetry): string {
  if (t.source !== "spine") {
    const a = t.runsToday;
    return typeof a === "number" ? "" : `${a.what} — not measured: ${a.needs}.`;
  }
  const parts: string[] = [];
  const runs = t.runsToday;
  if (typeof runs === "number") {
    parts.push(runs === 0
      ? `No run resolved for this seat on ${t.day} (UTC).`
      : `${runs} run${runs === 1 ? "" : "s"} resolved on ${t.day} (UTC).`);
  }
  if (t.tokensPartial && t.runsMissingTokens) {
    parts.push(
      `${t.runsMissingTokens} of them recorded no token figure, so the total ` +
      "is a floor, not a sum.");
  }
  if (t.unpricedTokens > 0) {
    parts.push(
      `${fmtTokensCompact(t.unpricedTokens)} tokens ran on a model with no ` +
      "row in the price table and are not in the dollar estimate.");
  }
  if (typeof t.tokensToday === "number" && t.costUsdToday != null) {
    parts.push("The dollar figure is a blend estimate at list prices — see a " +
               "seat page for the table.");
  }
  return parts.join(" ");
}
