/**
 * WHAT THIS SEAT WAS TOLD — the context inspector.
 *
 * From the context-engine design, chartered by the CEO 2026-08-27: *"maybe it
 * should be part of UI too as to what context/working memory of each agent."*
 * On every job row, a fold: the CEO can open any lamp and see exactly what the
 * worker started with.
 *
 * THE HONEST VERSION, AND WHY IT IS NOT THE DESIGNED ONE. The design's full
 * answer is the CONTEXT PACK — guide claims, family ledgers, working memory,
 * unconsumed instructions, live payload samples — assembled by an endpoint
 * that does not exist yet (slice CE-1). Rendering an empty pane and calling it
 * "the context" would be the worst available version: a surface that looks
 * like it is showing you everything while showing you nothing.
 *
 * So this renders what the record ACTUALLY holds today, and names the gap:
 *
 *   1. THE TASK the job was dispatched with — always present, and it is the
 *      one-line version of the brief.
 *   2. THE ASKS IT SERVED, in full. A job's record can name the desk requests
 *      it was fired against, and those requests carry the brief VERBATIM — the
 *      SLICE 3 charter on the live record is 2,000 characters of instruction
 *      sitting in a field nothing rendered. That IS what the seat was told.
 *   3. WHETHER A PACK WAS RECORDED. Today: never. It reads *"no pack
 *      recorded"* — a stated absence, never an empty pane.
 *
 * WHEN CE-1 LANDS nothing here moves except the pack section filling in. The
 * shape below already has its slot, deliberately unimplemented rather than
 * absent, so the seam is visible to whoever builds it.
 */

import type { DeskRun, DeskRequest } from "./seatLib.ts";

/* ---------------------------------------------------------------- types --- */

export interface ServedBrief {
  requestId: string;
  /** The ask's own headline. Null when the record carries none. */
  subject: string | null;
  /** The brief as filed, verbatim. Null when the ask carried only a subject. */
  brief: string | null;
  /** True when the id was named by the job and no matching ask was found in
   *  what this page read — a DIFFERENT fact from "the job served nothing". */
  missing: boolean;
}

export interface ContextView {
  runId: string | null;
  /** The dispatch's one-line task. */
  task: string | null;
  /** The asks this job was fired against, with their briefs. */
  served: ServedBrief[];
  /** The assembled pack, when one is ever recorded. `null` today, always. */
  pack: null;
  /** Plain English, on the surface, saying which of the above is true. */
  note: string;
  /** True when there is genuinely nothing to open — the fold is not drawn. */
  empty: boolean;
}

/* -------------------------------------------------------------- reading --- */

function str(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length > 0 ? t : null;
}

/**
 * What a job was told, from the record.
 *
 * `requests` is the population this page READ, which is capped — so an id that
 * finds no match is reported `missing` rather than dropped. Dropping it would
 * turn "we did not look far enough" into "it served nothing", and those are
 * different facts with different fixes.
 */
export function contextOf(
  run: DeskRun | null | undefined,
  requests: readonly DeskRequest[] | null | undefined,
): ContextView {
  if (!run) {
    return {
      runId: null, task: null, served: [], pack: null, empty: true,
      note: "There is no record of this job, so what it was told is unknown.",
    };
  }
  const r = run as unknown as Record<string, unknown>;
  const meta = (r.meta && typeof r.meta === "object" && !Array.isArray(r.meta)
    ? r.meta as Record<string, unknown> : {});
  const ids = Array.isArray(meta.serves_requests)
    ? meta.serves_requests.map(str).filter((x): x is string => x !== null)
    : [];

  const byId = new Map<string, DeskRequest>();
  for (const q of requests ?? []) {
    const id = str((q as unknown as Record<string, unknown>).request_id);
    if (id) byId.set(id, q);
  }

  const served: ServedBrief[] = ids.map((id) => {
    const q = byId.get(id) as unknown as Record<string, unknown> | undefined;
    if (!q) return { requestId: id, subject: null, brief: null, missing: true };
    return {
      requestId: id,
      subject: str(q.subject) ?? str(q.task) ?? str(q.headline),
      // `note` is where the chair files the brief verbatim. Measured on the
      // live record 2026-08-27: the SLICE 3 charter is ~2,000 characters of
      // instruction in this field, and nothing rendered it.
      brief: str(q.note),
      missing: false,
    };
  });

  const task = str(r.task);
  const withBrief = served.filter((s) => s.brief).length;
  const missing = served.filter((s) => s.missing).length;

  // ONE function, ONE input, every field — including the sentence. A caller
  // that built the view and then corrected the note afterwards is how a
  // payload comes to contradict itself, and the note is always the part
  // nobody remembers to correct.
  let note: string;
  if (served.length === 0) {
    note = task
      ? "This job records the line it was given and nothing more. No pack "
        + "recorded — the fund does not yet assemble one, so what else the "
        + "worker was told is not on the record."
      : "No pack recorded, and this job does not even carry the line it was "
        + "given. What it was told is unknown, not nothing.";
  } else if (missing === served.length) {
    note = `This job names ${served.length} ask(s) it was fired against, and `
      + "none of them is in the batch this page read. They exist; we did not "
      + "look far enough. No pack recorded.";
  } else {
    note = `The brief${withBrief === 1 ? "" : "s"} below ${withBrief === 1 ? "is" : "are"} `
      + "what the chair actually wrote, word for word."
      + (missing > 0 ? ` ${missing} further ask(s) were named and not found in `
        + "what this page read." : "")
      + " No pack recorded — the fund does not yet assemble one.";
  }

  return {
    runId: str(r.run_id), task, served, pack: null, note,
    empty: !task && served.length === 0,
  };
}
