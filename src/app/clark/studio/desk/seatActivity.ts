/**
 * WHAT A SEAT IS ACTUALLY DOING — every open dispatch, not the newest one.
 *
 * THE CEO, on the floor, 2026-08-27, verbatim: *"1 builder working but 2 in
 * reality"*. He was right and the room was wrong. Two builders at once is a
 * VERSIONED PERMISSION in the constitution (disjoint write scopes, serialized
 * suites), so the floor was not mis-drawing an impossible state — it was
 * mis-drawing a permitted, live, deliberately-chosen one, on the surface a
 * human uses to decide whether a slot is free.
 *
 * The spine half shipped in the same diff: `desk._activity` now folds
 * `open_dispatches` / `working_count` / `awaiting_review_count` beside the
 * headline fields it already served. This module is the reading half, and it
 * exists as a tested pure function rather than inline JSX because the whole
 * feature is a COUNT, and a count computed in three places is three counts.
 *
 * THE FIELD MAY NOT BE THERE, AND THAT IS THE INTERESTING CASE. A spine that
 * has not been restarted since this diff serves the old envelope: no
 * `open_dispatches`, no counts. Rendering zero lamps for a working seat
 * because a key is missing is the absence-as-zero the non-negotiables forbid,
 * and it is precisely how a half-shipped payload change reads as a regression.
 * So `basis` is a first-class output with three values, `note` says which in
 * words, and the room prints it:
 *
 *   `open_dispatches`  the spine folded the list — the count is the truth.
 *   `headline_only`    the payload predates the fold. ONE lamp is drawn from
 *                      the headline and the room says the count is a FLOOR,
 *                      never that the seat holds exactly one.
 *   `unreadable`       there is no activity envelope at all (the desk failed,
 *                      or this seat is absent from the roster it served).
 *                      No lamps, and the note says UNKNOWN rather than idle.
 *
 * `understates` carries the one disagreement the spine documents on purpose:
 * the headline is retired when the NEWEST dispatch resolves, so a seat holding
 * an older open dispatch reports `status: "idle"` while `working_count` is 1.
 * The list is the truth; the headline is the compatibility surface. Where they
 * disagree the room shows both, per the illumination principle's clause 3.
 */

import type { DeskView } from "@/lib/fund_api";

/* ---------------------------------------------------------------- types --- */

/** A dispatch is OPEN in exactly two states. `idle` is a property of a SEAT,
 *  never of a dispatch — a lamp that could be idle would be a lamp for
 *  something that is not there. */
export type LampState = "working" | "awaiting_review";

export interface SeatLamp {
  /** Null when the dispatch event carried none. Never invented. */
  taskId: string | null;
  /** The dispatch's own words — what the room shows on hover. */
  task: string | null;
  /** When it was dispatched, for the age the room prints beside it. */
  since: string | null;
  state: LampState;
  /** The run that came back, so a click can open it. */
  returnedRunId: string | null;
  /** Whether the spine could TELL a returned dispatch from a running one FOR
   *  THIS DISPATCH. `false` makes `working` an honest floor, not a reading. */
  reviewDetectable: boolean;
}

export type LampBasis = "open_dispatches" | "headline_only" | "unreadable";

export interface SeatLamps {
  seat: string;
  /** Newest first, as the spine ordered them. */
  lamps: SeatLamp[];
  /** Null under `headline_only` and `unreadable` — the payload did not say,
   *  and a floor is not a count. NEVER zero for "we could not tell". */
  workingCount: number | null;
  awaitingCount: number | null;
  /** How many lamps are drawn. Under `headline_only` this is 0 or 1 and is a
   *  FLOOR — `countIsFloor` says so rather than leaving the reader to guess. */
  drawn: number;
  countIsFloor: boolean;
  basis: LampBasis;
  /** The seat's single-lamp state, unchanged from the pre-fold payload. */
  headline: "working" | "awaiting_review" | "idle" | null;
  /** The headline says idle and the list says a dispatch is open. */
  understates: boolean;
  /** The sentence the room prints. Absence in WORDS, always. */
  note: string;
}

type Activity = DeskView["roster"][number]["activity"];

/* -------------------------------------------------------------- reading --- */

function str(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length > 0 ? t : null;
}

function lampOf(raw: unknown): SeatLamp | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  // A row whose state is neither open state is DROPPED rather than defaulted
  // to `working`: defaulting would draw a lamp for something the spine did not
  // say was running, which is the invention this whole module exists against.
  const state = r.status === "working" || r.status === "awaiting_review"
    ? (r.status as LampState) : null;
  if (!state) return null;
  return {
    taskId: str(r.task_id),
    task: str(r.task),
    since: str(r.since),
    state,
    returnedRunId: str(r.returned_run_id),
    // Absent reads as NOT detectable. `true` is a claim that the spine looked
    // and could tell; a missing key is not that claim.
    reviewDetectable: r.review_detectable === true,
  };
}

function countOf(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) && v >= 0 ? v : null;
}

/**
 * One seat's lamps, from ONE input.
 *
 * Every field above is computed here, from the activity envelope alone. The
 * alternative — a caller that reads `open_dispatches` and then patches `note`
 * and `basis` afterwards — is the shape that ships a payload contradicting
 * itself, because the fields nobody looks at are the fields nobody patches.
 */
export function seatLamps(seat: string, activity: Activity | null | undefined): SeatLamps {
  const base = {
    seat, lamps: [] as SeatLamp[], workingCount: null as number | null,
    awaitingCount: null as number | null, drawn: 0, countIsFloor: false,
    understates: false,
  };

  if (!activity || typeof activity !== "object") {
    return {
      ...base, basis: "unreadable", headline: null,
      note: "The fund's record said nothing about this seat, so what it is "
        + "doing is UNKNOWN — not nothing.",
    };
  }

  const a = activity as unknown as Record<string, unknown>;
  const headline = a.status === "working" || a.status === "awaiting_review"
    || a.status === "idle" ? (a.status as SeatLamps["headline"]) : null;
  const filed = a.open_dispatches;

  if (!Array.isArray(filed)) {
    // THE OLD ENVELOPE. One lamp from the headline, and the count is a FLOOR.
    const one = headline === "idle" || headline === null ? null : lampOf({
      status: headline, task_id: a.task_id, task: a.task, since: a.since,
      returned_run_id: a.returned_run_id,
      review_detectable: a.review_detectable,
    });
    const lamps = one ? [one] : [];
    return {
      ...base, lamps, drawn: lamps.length, countIsFloor: true,
      basis: "headline_only", headline,
      note: "The fund is running an older version of its own record, which "
        + "reports only the most recent job per seat. A seat doing two things "
        + "looks like a seat doing one. Treat the number below as at least, "
        + "not exactly.",
    };
  }

  const lamps = filed.map(lampOf).filter((l): l is SeatLamp => l !== null);
  const working = countOf(a.working_count);
  const awaiting = countOf(a.awaiting_review_count);
  const dropped = filed.length - lamps.length;
  // The SPINE'S counts, not `lamps.filter(...).length`. Recounting here would
  // be a second implementation of the rule, and the two drift the first time
  // a state is added. Where the spine states none, absent — never a recount
  // wearing the spine's authority.
  const understates = headline === "idle" && lamps.length > 0;

  // PLAIN ENGLISH, and it is checked (see `plainEnglish.ts`). These four
  // sentences are read by the CEO on the floor; the technical version of each
  // is one tap down, on the job itself.
  let note: string;
  if (lamps.length === 0) {
    note = "This seat has nothing running. A seat sitting idle costs the fund "
      + "nothing, and that is on purpose.";
  } else if (dropped > 0) {
    note = `The record lists ${filed.length} jobs for this seat and `
      + `${dropped} of them could not be read. Those are jobs we cannot see, `
      + "not jobs that stopped.";
  } else if (understates) {
    note = "This seat's most recent job has finished, but an older one is "
      + "still going. The lamps below are what is actually running.";
  } else {
    note = "Everything this seat has running, taken from the fund's own "
      + "record of what was started and what came back.";
  }

  return {
    ...base, lamps, drawn: lamps.length, basis: "open_dispatches", headline,
    workingCount: working, awaitingCount: awaiting, understates, note,
  };
}

/**
 * The floor's headline: how many jobs are in flight across the bench.
 *
 * Returned as a THREE-part answer rather than an integer, because the honest
 * total depends on what every seat's basis is. One seat on the old envelope
 * makes the whole bench total a floor, and a room that printed "3 in flight"
 * over a payload that could only see three of four is the confident-answer
 * failure this desk has already been repaired from twice.
 */
export interface BenchFlight {
  working: number;
  awaiting: number;
  /** True when ANY seat's lamps came from the headline or could not be read —
   *  so the totals above are lower bounds. */
  isFloor: boolean;
  /** Seats whose activity could not be read at all. Named, not counted. */
  unreadable: string[];
  note: string;
}

export function benchFlight(rows: SeatLamps[]): BenchFlight {
  let working = 0, awaiting = 0, floor = false;
  const unreadable: string[] = [];
  for (const r of rows) {
    if (r.basis === "unreadable") { unreadable.push(r.seat); floor = true; continue; }
    if (r.basis === "headline_only") floor = true;
    working += r.lamps.filter((l) => l.state === "working").length;
    awaiting += r.lamps.filter((l) => l.state === "awaiting_review").length;
  }
  const note = unreadable.length > 0
    ? `We could not read what ${unreadable.join(" and ")} `
      + `${unreadable.length === 1 ? "is" : "are"} doing, so the count above `
      + "is at least this many, not exactly this many."
    : floor
      ? "At least one seat only reported its most recent job, so the count "
        + "above is at least this many, not exactly this many."
      : "Everything the bench has running right now.";
  return { working, awaiting, isFloor: floor, unreadable, note };
}
