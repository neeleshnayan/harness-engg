/**
 * THE LANES — five named queues instead of one scroll.
 *
 * CEO instruction for the redesigned desk: lanes, not a scroll. AWAITING YOU
 * open by default; everything else collapsed and COUNT-FIRST, each row naming
 * the person it is now waiting on.
 *
 *   a. AWAITING YOU                 — the only open lane
 *   b. DECIDED, AWAITING EXECUTION  — you said yes; who has it now
 *   c. APPROVED, AWAITING DISPATCH  — the chair's queue
 *   d. OPEN ELSEWHERE               — nobody has decided, and it is not yours
 *   e. RESOLVED TODAY               — with the resolution text
 *
 * THE ONE PROPERTY THIS MODULE EXISTS TO HOLD: **a lane's number is the FUND'S
 * number, and the rows are this page's fold, and when they differ the lane says
 * so.** Measured live 2026-08-23, `desk_load` reported 162 decided-awaiting-
 * execution (167 ninety minutes later) and 46 open-elsewhere (then 48) while
 * `/fund/desk`'s recommendation feed — which is what the page can actually
 * render — carried different subsets. The figures move with the day and the
 * DISAGREEMENT is the invariant, which is why no number here is hardcoded. A
 * lane that printed its own row count as the fund's figure would be the
 * quantity-computed-twice defect for the fourth time on this desk; a lane that
 * printed the fund's figure and rendered fewer rows without comment would be
 * worse, because the reader would think they had seen everything.
 *
 * So `laneCount()` has five answers, each of which a reader can act on:
 *   - the desk read has not answered yet                 → "…", and it says so
 *   - served figure present, equal to the rows           → one number
 *   - served figure present, larger than the rows        → "N · showing M"
 *   - served figure absent, the desk readable            → the row count, said
 *                                                          to be the page's own
 *   - served figure absent AND the desk unreadable       → UNKNOWN, as a word
 *
 * The unreadable one was missing from the first cut and all five lanes
 * rendered `0` on an unreachable spine. The LOADING one was missing until
 * ticket fccb9cf3 — the CEO watched five lanes call themselves UNKNOWN for
 * thirty seconds while the fetch was merely in flight. `desk !== null` cannot
 * tell "not yet" from "not ever"; `DeskRead` can. See `laneCount`.
 *
 * SUPERSEDED ROWS NEVER APPEAR IN AN ACTIVE LANE. They are withdrawn by
 * lineage — the server refuses their approval — so a lane that listed one
 * would be offering a control the spine rejects. They are removed here, the
 * number removed is reported, and the row itself is reachable through the
 * lineage drawer, labelled, with its replacement linked.
 */

import type { DeskLoad, DeskSupersessionEdge, DeskView } from "@/lib/fund_api";
import { READING_DESK, type DeskRead } from "./deskRead.ts";

/* ---------------------------------------------------------------- types --- */

export type LaneId =
  | "awaiting" | "decided" | "dispatch" | "elsewhere" | "resolved";

export interface LaneCount {
  /** The number to render. `null` = not a number, and `source` says which
   *  kind: UNKNOWN because nothing could count it, or NOT YET because the
   *  read has not returned. Never 0 for either. */
  value: number | null;
  /** How many rows this page can actually put on screen. */
  shown: number;
  /** Where `value` came from. `unknown` means NEITHER fold could speak;
   *  `loading` means neither has been asked to yet. */
  source: "spine" | "page" | "unknown" | "loading";
  /** Non-null whenever a reader would otherwise misread the pair. */
  note: string | null;
}

export interface LaneRow {
  key: string;
  /** The one line. */
  text: string;
  /** Whose move it is now — the EXECUTOR for a decided row, the OWNER for an
   *  open-elsewhere one. Null means the record names nobody, which is a
   *  finding and is rendered as one. */
  actor: string | null;
  /** Why that actor, as the SPINE resolved it. Never re-derived here. */
  actorWhy: string | null;
  seat: string | null;
  at: string | null;
  /** Extra line the lane's own semantics earn: the resolution text on a
   *  resolved row, the decider on a decided one. Null when there is none. */
  detail: string | null;
  /** What the lineage drawer opens on. */
  anchor: { kind: "rec"; runId: string; recId: number }
        | { kind: "request"; requestId: string };
}

export interface Lane {
  id: LaneId;
  label: string;
  /** What is in this lane, and why it is not in another one. */
  lede: string;
  count: LaneCount;
  rows: LaneRow[];
  openByDefault: boolean;
  /** Rows removed because a live supersession edge makes them unapprovable. */
  withdrawn: number;
}

export interface LaneInput {
  desk: DeskView | null;
  /** The state of the `/fund/desk` read. Passed in rather than derived from
   *  `desk === null` here, because `null` is BOTH the value before the first
   *  answer and the value after a failed one, and this module used to read the
   *  first as the second on every lane at once (ticket fccb9cf3). */
  read: DeskRead;
  /** Rows the CEO owes a click on, already built by `decisionList`. Passed as a
   *  COUNT rather than as rows: lane (a) renders the existing decision cards,
   *  which carry controls this module knows nothing about. */
  awaitingShown: number;
  /** The header's figure, so lane (a) and the header cannot disagree. */
  awaitingServed: number | null;
  /** `<run_id>#<rec_id>` for every recommendation carrying a live edge. */
  blocked: Map<string, DeskSupersessionEdge>;
  /** UTC instant the page is rendering for — the spine's `at`, not the
   *  browser's clock, so "today" is the fund's day. */
  now: string;
}

/* -------------------------------------------------------------- helpers --- */

/** `YYYY-MM-DD` in UTC, or null. The desk's day is the fund's day. */
export function utcDay(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return null;
  return new Date(t).toISOString().slice(0, 10);
}

/**
 * The pair of numbers a lane renders, and the sentence that keeps them honest.
 *
 * `read` IS NOT DECORATION AND NEITHER OF ITS NON-DEFAULT VALUES WAS IN THE
 * FIRST CUT. Without the unreadable case, a spine that served no figure fell
 * back to the page's row count — and on an UNREADABLE desk the page's row
 * count is zero, so all five lanes rendered a confident `0`. That is the
 * absence-as-zero error, in the desk whose whole discipline is that absence is
 * never zero, written by the person writing this comment and caught by the
 * test three lines below the one that was passing. Neither fold speaking is
 * UNKNOWN, and UNKNOWN renders as a word.
 *
 * The loading case is the same error one step earlier, and it reached the CEO:
 * a read still in flight has not TRIED and failed, so calling it UNKNOWN is a
 * claim about the world made from a pending promise. It is checked FIRST,
 * before the served figure, because a read that has not returned cannot have
 * served anything — a `served` number arriving with `read === "loading"` would
 * be a contradiction, and the honest answer to a contradiction is the state
 * that is certainly true.
 */
export function laneCount(
  served: number | null | undefined, shown: number, what: string,
  read: DeskRead = "readable",
): LaneCount {
  if (read === "loading") {
    return {
      value: null, shown, source: "loading",
      note: `Not counted yet: ${what}.`,
    };
  }
  if (typeof served !== "number" || !Number.isFinite(served)) {
    if (read === "unreadable") {
      return {
        value: null, shown, source: "unknown",
        note: `Neither the fund nor this page could count ${what}, so it is `
          + "UNKNOWN — not none. Anything waiting is still waiting.",
      };
    }
    return {
      value: shown, shown, source: "page",
      note: `Counted by this page, not by the fund — the spine served no `
        + `figure for ${what}.`,
    };
  }
  if (served === shown) {
    return { value: served, shown, source: "spine", note: null };
  }
  if (served > shown) {
    return {
      value: served, shown, source: "spine",
      note: `The fund counts ${served}; this page can render ${shown} of them. `
        + "The rest are outside the payload it reads, not resolved.",
    };
  }
  // MORE ROWS THAN THE FUND COUNTS. Rare, and worth shouting about rather than
  // clamping: the two folds disagree about which rows exist.
  return {
    value: served, shown, source: "spine",
    note: `The fund counts ${served} and this page holds ${shown} rows for `
      + `${what}. That is a disagreement about which rows exist, not a `
      + "rounding — neither figure is safe alone.",
  };
}

/**
 * Lane b's count, compared LIKE WITH LIKE (2026-08-24, the live 169-vs-187).
 *
 * The fund's `decided_awaiting_execution` deliberately EXCLUDES decided rows
 * whose next act is also the CEO's — its partition puts those in his awaiting
 * figure. This lane deliberately INCLUDES them: they are decided work. Both
 * folds were right, and feeding the two different partitions into `laneCount`
 * read as "a disagreement about which rows exist" when no row's existence was
 * in dispute — two numbers that sound like the same number, the exact defect
 * the spine's own counter was repaired from, reproduced between the repos.
 *
 * So the guard now compares the SAME partition (`sameBasis` = this page's
 * decided rows whose next actor is neither the CEO nor unknown), and when the
 * folds agree, the lane says what the remainder IS instead of alarming.
 */
export function decidedCount(
  served: number | null | undefined, sameBasis: number, total: number,
  read: DeskRead = "readable",
): LaneCount {
  const base = laneCount(served, sameBasis,
    "decided work awaiting someone else", read);
  if (base.note !== null) return { ...base, shown: total };
  const alsoYours = total - sameBasis;
  return {
    value: total, shown: total, source: "page",
    note: alsoYours > 0
      ? `${total} decided in all: the fund counts ${sameBasis} awaiting `
        + `someone else, and ${alsoYours} ${alsoYours === 1 ? "is a decided "
        + "row" : "are decided rows"} whose next act is also yours — those `
        + "appear under Awaiting you as well."
      : null,
  };
}

/**
 * The glyph a lane header renders for its count.
 *
 * TWO KINDS OF NOT-A-NUMBER AND THEY MUST NOT SHARE A WORD. `unknown` is a
 * finding — the fund was asked and could not say. `…` is a read still in
 * flight, which is a finding about nothing (ticket fccb9cf3). It takes the
 * whole `LaneCount` because the VALUE cannot tell them apart; that is the
 * defect, one level down.
 *
 * IT LIVES HERE RATHER THAN IN `DeskLaneViews.tsx`, where it was, because
 * node's type stripper refuses `.tsx` and a decision that only exists inside a
 * component is a decision nothing can test. Same move, same reason, as
 * `chipShowsTotal` in deskAwaiting.
 */
export function laneGlyph(c: LaneCount): string {
  if (c.value !== null) return String(c.value);
  return c.source === "loading" ? "…" : "unknown";
}

/**
 * Why an OPEN lane has no rows in it — three reasons, only one of them empty.
 *
 * Extracted from `DeskLaneViews.tsx` on the Gauntlet's finding: the diff that
 * pulled `laneGlyph` out of that file for exactly this reason left its sibling
 * ternary forty lines below, untested, deciding between a measurement ("read
 * and is empty"), a pointer at the note, and — new — a read that has measured
 * nothing at all. A rule applied to one half of a file and not the other is
 * the shape of the defect this whole ticket is about.
 */
export function laneEmptyNote(c: LaneCount): string {
  if (c.source === "loading") return "Not read yet.";
  if (c.value === 0) return "This lane was read and is empty.";
  return "This page holds no rows for this lane — see the note above.";
}

/** Rows of an actor, said plainly. `null` is a finding, not a blank. */
function actorOf(rec: {
  next_actor_resolved?: string | null; next_actor?: string | null;
}): string | null {
  const v = rec.next_actor_resolved ?? rec.next_actor ?? null;
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t && t !== "unknown" ? t : null;
}

/* ------------------------------------------------------------ the lanes --- */

export function deskLanes(input: LaneInput): Lane[] {
  const { desk, read, awaitingShown, awaitingServed, blocked, now } = input;
  const load: DeskLoad | undefined = desk?.desk_load;
  const recs = desk?.open_recommendations ?? [];
  const requests = desk?.requests ?? [];
  const today = utcDay(now);

  const isBlocked = (runId: string, recId: number) =>
    blocked.has(`${runId}#${recId}`);

  /* ---- b. decided by you, awaiting execution --------------------------- */

  const decidedAll = recs.filter(
    (r) => r.status === "accepted" || r.status === "staged");
  const decidedLive = decidedAll.filter((r) => !isBlocked(r.run_id, r.rec_id));
  const decidedRows: LaneRow[] = decidedLive.map((r) => ({
    key: `${r.run_id}#${r.rec_id}`,
    text: r.text,
    actor: actorOf(r),
    actorWhy: r.next_actor_why ?? null,
    seat: r.seat ?? null,
    at: r.decided_at ?? null,
    detail: r.decided_by
      ? `decided by ${r.decided_by}`
      : "decided — the decision event recorded no actor",
    anchor: { kind: "rec", runId: r.run_id, recId: r.rec_id },
  }));

  /* ---- c. approved, awaiting the chair's dispatch ---------------------- */

  const approved = requests.filter((r) => r.status === "approved");
  const dispatchRows: LaneRow[] = approved.map((r) => ({
    key: `req:${r.request_id}`,
    text: r.task ?? r.subject ?? "this ask recorded no subject",
    // A cleared ask is the chair's by construction — the constitution's own
    // chain: a seat files, the CEO approves, the CHAIR triggers. Written as a
    // constant rather than read from a field because no field carries it and
    // inventing one would be worse than naming the rule.
    actor: "chair",
    actorWhy: "approved asks are dispatched by the chair; the approval is not "
      + "itself a trigger",
    seat: r.seat ?? r.serves ?? null,
    at: r.approved_at ?? r.at ?? null,
    detail: r.approved_by
      ? `approved by ${r.approved_by}`
      : "approved — the approval event recorded no actor",
    anchor: { kind: "request", requestId: r.request_id },
  }));

  /* ---- d. open, and owned elsewhere ------------------------------------ */

  const elsewhereAll = recs.filter(
    (r) => r.status === "open" && actorOf(r) !== null && actorOf(r) !== "ceo");
  const elsewhereLive = elsewhereAll.filter(
    (r) => !isBlocked(r.run_id, r.rec_id));
  const elsewhereRows: LaneRow[] = elsewhereLive.map((r) => ({
    key: `${r.run_id}#${r.rec_id}`,
    text: r.text,
    actor: actorOf(r),
    actorWhy: r.next_actor_why
      ?? "routed away from your desk; the spine stated no reason",
    seat: r.seat ?? null,
    at: null,
    detail: null,
    anchor: { kind: "rec", runId: r.run_id, recId: r.rec_id },
  }));

  /* ---- e. resolved today ----------------------------------------------- */

  // Requests only, and on purpose: a RESOLUTION is the only field on this desk
  // that records that something was carried out. A decided recommendation is a
  // decision, not an outcome, and putting the two in one lane would let a
  // click read as a result.
  const resolvedRows: LaneRow[] = requests
    .filter((r) => r.status === "resolved"
      && today !== null && utcDay(r.resolved_at) === today)
    .map((r) => ({
      key: `req:${r.request_id}`,
      text: r.task ?? r.subject ?? "this ask recorded no subject",
      actor: null,
      actorWhy: null,
      seat: r.seat ?? r.serves ?? null,
      at: r.resolved_at ?? null,
      detail: (r.resolution ?? "").trim()
        || "resolved with no resolution text recorded — closed, and the record "
           + "does not say what was done",
      anchor: { kind: "request", requestId: r.request_id },
    }));
  resolvedRows.sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""));

  return [
    {
      id: "awaiting",
      label: "Awaiting you",
      lede: "Every row that needs your click, ranked by the fund. Nothing else "
        + "on this page is waiting on you.",
      count: laneCount(awaitingServed, awaitingShown, "what awaits you", read),
      rows: [],
      openByDefault: true,
      withdrawn: 0,
    },
    {
      id: "decided",
      label: "Decided by you, awaiting execution",
      lede: "You said yes; these have not happened yet. Each names who has it "
        + "now — the missing third state this desk rendered as nothing.",
      count: decidedCount(load?.decided_awaiting_execution,
        decidedLive.filter((r) => {
          const a = actorOf(r);
          return a !== null && a !== "ceo" && a !== "unknown";
        }).length,
        decidedRows.length, read),
      rows: decidedRows,
      openByDefault: false,
      withdrawn: decidedAll.length - decidedLive.length,
    },
    {
      id: "dispatch",
      label: "Approved, awaiting dispatch",
      lede: "You approved these asks; the chair fires them. An approval is "
        + "recorded on the log and triggers nothing by itself.",
      count: laneCount(load?.requests_approved_undispatched, dispatchRows.length,
        "the chair's dispatch queue", read),
      rows: dispatchRows,
      openByDefault: false,
      withdrawn: 0,
    },
    {
      id: "elsewhere",
      label: "Open elsewhere",
      lede: "Nobody has decided these and nobody is waiting on you for them. "
        + "Each names the actor it went to and the spine's reason.",
      count: laneCount(load?.open_elsewhere, elsewhereRows.length,
        "open work owned elsewhere", read),
      rows: elsewhereRows,
      openByDefault: false,
      withdrawn: elsewhereAll.length - elsewhereLive.length,
    },
    {
      id: "resolved",
      label: "Resolved today",
      lede: "Closed on the fund's own UTC day, each with the resolution text "
        + "the record carries. A closure with no text is shown as one.",
      // NO SERVED FIGURE EXISTS for this lane, and that is stated rather than
      // hidden: `desk_load` counts what is open, never what closed today.
      count: laneCount(null, resolvedRows.length, "today's resolutions", read),
      rows: resolvedRows,
      openByDefault: false,
      withdrawn: 0,
    },
  ];
}

/** Total rows the five lanes account for, excluding the awaiting lane's cards
 *  (which the page renders itself). Used for the one honesty line under the
 *  lanes, so a reader can see the page is not quietly dropping rows. */
export function lanesAccountedFor(lanes: Lane[]): number {
  return lanes.reduce((n, l) => n + l.rows.length, 0);
}
