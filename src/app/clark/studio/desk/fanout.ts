/**
 * FAN-OUT — the workers a seat fired on its last recorded run.
 *
 * CEO instruction, verbatim 2026-08-23: *"would be good to see agents w
 * sub-agents fanned out in the rooms UI too!"* — and, in the same breath,
 * *"changing shape in realtime"*.
 *
 * WHAT THIS IS NOT, said first because the gap is the whole design. This is
 * NOT live. The spine has no dispatch-state store; agents run inside the
 * chair's session and nothing streams their shape. What the spine HAS is the
 * flight recorder, and a run record may carry fan-out evidence in its `meta`.
 * So this reads THE LAST RECORDED RUN and the view says so on every card. A
 * room that drew a from-the-record tree and let it read as live would be the
 * worst possible version of this feature: a floor that looks like it is
 * breathing while showing yesterday.
 *
 * THE PREMISE THE BRIEF STATED, AND WHAT IS ACTUALLY ON THE WIRE (measured
 * against the running spine before this was written):
 *
 *   brief:    `meta.fanout` is `[{worker, brief_one_line, kind, returned,
 *              tokens}]` on new records
 *   measured: ONE run in the whole recorder carries the key —
 *             `run-ed-batch4` — and it holds a free-text STRING:
 *             "3 workers foreground, no falsifier fired, third measured
 *              mid-run catch (the strongest: survivor-universe-as-PIT)".
 *             `meta.workers_fired: 3` sits beside it.
 *
 * So this reader takes BOTH shapes and refuses to confuse them. A structured
 * array becomes a tree. A STRING is rendered as the run's own sentence,
 * labelled unstructured, and is NEVER parsed into workers — reading structure
 * out of English is the same class of mistake as reading a deadline out of
 * prose, which this desk has already been repaired from twice. A bare
 * `workers_fired` count becomes "N workers, no detail filed", which is a
 * different fact again.
 *
 * THE SEAM FOR D33 (asked for explicitly). `seatFanout()` takes a SOURCE
 * object, not a `DeskView`. Today the only source is `{kind: "record", ...}`.
 * When a live dispatch-state endpoint exists, D33 adds `{kind: "live", ...}`
 * and the room swaps the source without the card, the tree or the layout
 * moving — the view already renders `basis` and will simply start saying
 * "live" instead of "last recorded run".
 */

import type { DeskView } from "@/lib/fund_api";

/* ---------------------------------------------------------------- types --- */

/** How a worker came back. The chair's own vocabulary, from the brief. */
export type WorkerOutcome = "used" | "discarded" | "catch" | "unstated";

export interface FanoutWorker {
  worker: string;
  /** One line, as filed. Null when the record states none. */
  brief: string | null;
  kind: string | null;
  outcome: WorkerOutcome;
  /** Null = the record stated no figure. NEVER zero. */
  tokens: number | null;
}

/**
 * What a seat's fan-out looks like, and — always — how we know.
 *
 * `shape` is the honest core of this type. Four values, and collapsing any two
 * of them tells the reader something false about the record.
 */
export type FanoutShape =
  /** A structured array was filed: the tree is real. */
  | "structured"
  /** The record carries prose. Shown verbatim, not parsed. */
  | "prose"
  /** Only a count was filed. */
  | "count"
  /** The run exists and filed no fan-out evidence at all. */
  | "none"
  /** No run for this seat is inside the window this page reads. */
  | "no_run";

export interface SeatFanout {
  seat: string;
  shape: FanoutShape;
  /** Populated only when `shape === "structured"`. */
  workers: FanoutWorker[];
  /** The count the record states, from `workers_fired` or the array length.
   *  Null when the record states none — never zero. */
  count: number | null;
  /** The prose, verbatim, when `shape === "prose"`. */
  prose: string | null;
  /** The run this was read from, so a reader can go and check. */
  runId: string | null;
  at: string | null;
  /** WHERE THIS CAME FROM, rendered on the card. The D33 seam: this becomes
   *  `"live"` when a dispatch-state source exists, and nothing else moves. */
  basis: "last recorded run" | "live";
  /** The sentence the card shows when there is no tree to draw. */
  note: string;
}

/** The only source that exists today. D33 adds a `live` member here. */
export type FanoutSource =
  | { kind: "record"; desk: DeskView | null };

/* -------------------------------------------------------------- parsing --- */

const OUTCOMES: WorkerOutcome[] = ["used", "discarded", "catch"];

function outcomeOf(v: unknown): WorkerOutcome {
  if (typeof v !== "string") return "unstated";
  const t = v.trim().toLowerCase();
  return (OUTCOMES as string[]).includes(t) ? (t as WorkerOutcome) : "unstated";
}

function numberOrNull(v: unknown): number | null {
  // A numeric STRING is refused rather than coerced: a quoted figure is what a
  // number lifted out of prose looks like, and the desk's own routing rules
  // refuse it at the door for exactly that reason.
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function stringOrNull(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length > 0 ? t : null;
}

/**
 * One entry of a structured `meta.fanout` array.
 *
 * A row with no worker name is DROPPED rather than rendered as "unnamed": a
 * tree node with no label is a box, and a box is not evidence.
 */
export function parseWorker(raw: unknown): FanoutWorker | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const r = raw as Record<string, unknown>;
  const worker = stringOrNull(r.worker);
  if (!worker) return null;
  return {
    worker,
    brief: stringOrNull(r.brief_one_line) ?? stringOrNull(r.brief),
    kind: stringOrNull(r.kind),
    outcome: outcomeOf(r.returned),
    tokens: numberOrNull(r.tokens),
  };
}

/* ----------------------------------------------------------- the reader --- */

/**
 * The seat's fan-out, from whatever the source can honestly say.
 *
 * The run chosen is the seat's MOST RECENT by `resolved_at`, from the payload
 * this page holds — which is capped, and the `no_run` note says so rather than
 * implying the seat has never fanned out.
 */
export function seatFanout(source: FanoutSource, seat: string): SeatFanout {
  const base = {
    seat, workers: [] as FanoutWorker[], count: null as number | null,
    prose: null as string | null, runId: null as string | null,
    at: null as string | null, basis: "last recorded run" as const,
  };

  if (source.kind !== "record" || source.desk === null) {
    return {
      ...base, shape: "no_run",
      note: "The desk could not be read, so this seat's fan-out is UNKNOWN — "
        + "not none.",
    };
  }

  const runs = source.desk.runs
    .filter((r) => r.seat === seat)
    .sort((a, b) => (b.resolved_at ?? "").localeCompare(a.resolved_at ?? ""));
  const run = runs[0];
  if (!run) {
    return {
      ...base, shape: "no_run",
      note: "No run by this seat is inside the payload's run window, which is "
        + "capped — that is a limit of what this page reads, not a claim that "
        + "the seat has never fanned out.",
    };
  }

  const meta = (run.meta && typeof run.meta === "object"
    ? run.meta as Record<string, unknown> : {});
  const filed = meta.fanout;
  const fired = numberOrNull(meta.workers_fired);
  const at = run.resolved_at ?? null;

  if (Array.isArray(filed)) {
    const workers = filed.map(parseWorker)
      .filter((w): w is FanoutWorker => w !== null);
    if (workers.length > 0) {
      return {
        ...base, shape: "structured", workers, runId: run.run_id, at,
        // The COUNT is the record's own where it states one: an array that
        // dropped an unnamed row must not silently shrink the number the seat
        // reported firing.
        count: fired ?? workers.length,
        note: fired !== null && fired !== workers.length
          ? `The run reports ${fired} workers and filed ${workers.length} `
            + "readable entries; the difference is unnamed rows, not workers "
            + "that did not run."
          : "Filed as a structured fan-out on this run.",
      };
    }
    return {
      ...base, shape: "none", runId: run.run_id, at, count: fired,
      note: "This run filed a fan-out array with no readable entry in it — a "
        + "defect in the record, not a run with no workers.",
    };
  }

  const prose = stringOrNull(filed);
  if (prose) {
    return {
      ...base, shape: "prose", prose, runId: run.run_id, at, count: fired,
      // NOT PARSED, AND THAT IS THE POINT. Reading worker structure out of
      // English is the same mistake as reading a deadline out of prose.
      note: "This run described its fan-out in prose rather than filing the "
        + "structured form, so it is shown verbatim and NOT broken into "
        + "workers — the shape below is the sentence, not a tree.",
    };
  }

  if (fired !== null) {
    return {
      ...base, shape: "count", runId: run.run_id, at, count: fired,
      note: `This run reports ${fired} worker(s) and filed no detail about `
        + "them.",
    };
  }

  return {
    ...base, shape: "none", runId: run.run_id, at,
    note: "This run filed no fan-out evidence. A seat that ran alone and a "
      + "seat that fanned out without recording it look the same here, and "
      + "the record cannot tell them apart.",
  };
}

/** Seats that have something to draw. Used to decide whether the room shows
 *  the block at all — a column of "no evidence" rows is not a feature. */
export function seatsWithFanout(
  source: FanoutSource, seats: string[],
): SeatFanout[] {
  return seats
    .map((s) => seatFanout(source, s))
    .filter((f) => f.shape === "structured" || f.shape === "prose"
                || f.shape === "count");
}
