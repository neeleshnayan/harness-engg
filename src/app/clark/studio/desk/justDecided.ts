/**
 * APPROVED → MOVING TO EXECUTION — the thirty seconds after a decision.
 *
 * CEO, live, 2026-08-27, verbatim: *"if I approve something then lets move it
 * out of awaiting for you (we can keep a 30secs timer before it clears out and
 * it can be tagged visually that approved ->moving to execution or
 * something)"*.
 *
 * WHAT WAS ALREADY TRUE, MEASURED BEFORE BUILDING ANYTHING — because the
 * expensive half of this instruction turned out to be done:
 *
 *   * the record's own CEO lane already excludes an approval whose execution
 *     passes to the chair. Every one of the 18 decided rows on his live desk
 *     carries `execution_yours: true` — HIS execution, not the chair's — and
 *     those must stay. Sweeping them would trip the falsifier the constitution
 *     wrote for exactly this ("one genuinely CEO-awaiting item wrongly swept
 *     off the desk").
 *   * the reading side already splits decided rows out of the awaiting count
 *     and heads them separately.
 *
 * So the count was never the defect. THE MISSING THING IS FEEDBACK: he clicks,
 * the row refetches, and it either vanishes or comes back looking like it did
 * before. One second of feedback is the acceptance criterion, and the record
 * cannot supply it — the transition is a fact about THIS READER'S SESSION.
 *
 * THE LINGER IS KEYED ON AN OBSERVED CHANGE, NEVER ON A STATUS. This is the
 * whole correctness argument. If it were keyed on "status is approved", then
 * every reload would resurrect every approved row for thirty seconds — a page
 * that un-clears its own desk on refresh, forever. So a row is only ever
 * lingered when THIS session watched it move out of `open`; a row that was
 * already decided when the page loaded is recorded and never tagged.
 *
 * THE COUNT IS A TRUTH AND THE LINGER IS A COURTESY. A lingering row is not
 * counted as awaiting for even one frame; it is drawn, in the machine accent
 * at reduced weight, and then it is gone.
 */

/** How long a just-decided row stays on screen. The CEO's own number. */
export const LINGER_MS = 30_000;

/** The statuses that mean "the CEO has decided this". `open` is the only
 *  undecided one; everything else is a decision or a disposition. */
const DECIDED = new Set(["accepted", "approved", "rejected", "declined",
  "staged", "done", "noted"]);

export interface LingerState {
  /** The last status this session saw for each row. */
  seen: Record<string, string>;
  /** When this session watched a row leave `open`. */
  decidedAt: Record<string, number>;
}

export const EMPTY_LINGER: LingerState = { seen: {}, decidedAt: {} };

export interface TrackedRow { id: string; status: string | null | undefined }

/**
 * Fold this render's rows into the linger state.
 *
 * PURE, and it takes `now` rather than reading a clock, so the tests are not
 * a clock. Returns a NEW state; a caller that mutated the old one would make
 * React's identity check miss the update.
 *
 * A row that vanishes from `rows` is dropped from both maps. Without that the
 * state grows for the life of the tab and a row that came back after an hour
 * would be compared against an hour-old status.
 */
export function trackDecisions(
  prev: LingerState, rows: readonly TrackedRow[], now: number,
): LingerState {
  const seen: Record<string, string> = {};
  const decidedAt: Record<string, number> = {};
  for (const row of rows) {
    const status = typeof row.status === "string" ? row.status : "";
    seen[row.id] = status;
    const was = prev.seen[row.id];
    if (was === undefined) {
      // FIRST SIGHT. Recorded, never lingered — this session did not watch
      // this happen, and a page that tagged it would re-clear the desk on
      // every reload for ever.
      continue;
    }
    if (was === "open" && DECIDED.has(status)) {
      decidedAt[row.id] = now;
    } else if (prev.decidedAt[row.id] !== undefined) {
      // Still lingering from an earlier render. Carried, not restarted — a
      // restart on every poll would make the linger permanent.
      decidedAt[row.id] = prev.decidedAt[row.id];
    }
  }
  return { seen, decidedAt };
}

/** The rows still inside their thirty seconds. */
export function lingering(state: LingerState, now: number): string[] {
  return Object.entries(state.decidedAt)
    .filter(([, at]) => now - at < LINGER_MS)
    .map(([id]) => id);
}

/** Is this row inside its linger right now? */
export function isLingering(state: LingerState, id: string, now: number): boolean {
  const at = state.decidedAt[id];
  return at !== undefined && now - at < LINGER_MS;
}

/**
 * The tag's words. Plain English, and it names BOTH halves — what happened and
 * what happens next — because "approved" alone leaves the reader wondering
 * whether anything is now in motion.
 */
export const LINGER_LABEL = "approved — moving to execution";
