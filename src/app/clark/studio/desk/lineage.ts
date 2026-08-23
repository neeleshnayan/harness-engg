/**
 * LINEAGE — the chain behind one row on the desk, folded from served data only.
 *
 * CEO standard for the desk, verbatim 2026-08-23: *"well arranged and
 * maintained for lineage across our work output"*. The chain a reader wants is
 *
 *   originating request → the run(s) that served it → the recommendations they
 *   filed → the decision (who, when, and the verbatim instruction) → execution
 *   evidence → supersession edges
 *
 * and the whole of it is reconstructible from `GET /fund/desk`, `GET
 * /fund/events` and `GET /fund/desk/supersessions`. Nothing here invents a
 * link: every edge below is a KEY the spine already stores, and every edge the
 * store does not carry is reported ABSENT with the reason, never omitted.
 *
 * WHY ABSENCE IS THE HARD PART HERE, MEASURED BEFORE THIS FILE WAS WRITTEN
 * (live spine, 2026-08-23):
 *
 *   | join                                       | populated |
 *   |--------------------------------------------|-----------|
 *   | run.meta.serves_requests → request         | 2 of 117 runs declare service |
 *   | requests carrying ANY evidence edge        | 0 of 69 open/approved |
 *   | DeskDispatched → request_id                | 10 of 24 linkable (spine's own count) |
 *   | decision events carrying the verbatim note | 300 of 551 |
 *
 * A lineage view that drew a clean chain over that would be lying about the
 * firm's bookkeeping, and the bookkeeping is the thing worth fixing. So each
 * stage carries a three-valued `state`:
 *
 *   `found`      — the store holds this edge and here it is
 *   `absent`     — the store was READ and holds no such edge
 *   `unreadable` — the store could not be read; the edge is UNKNOWN, not absent
 *
 * and the fold reports its own join coverage so a reader can tell "this row has
 * no run" from "almost no row has a run".
 *
 * WHAT THIS MODULE DOES NOT DO. It does not decide whether a row is
 * approvable — `deskEngine.blockedRecs` and the server's own refusal own that.
 * It does not re-rank anything. And it does not classify a supersession mode:
 * `supersessionChip` already owns those sentences and a second copy would be
 * free to drift.
 */

import type {
  DeskRecommendation, DeskSupersessionEdge, DeskView, SpineEvent,
} from "@/lib/fund_api";

/* ---------------------------------------------------------------- types --- */

export type LineageState = "found" | "absent" | "unreadable";

/** One stage of the chain. `rows` is empty on anything but `found`. */
export interface LineageStage<T> {
  state: LineageState;
  rows: T[];
  /** The sentence a reader needs to interpret this stage. Always present —
   *  an empty stage with no sentence is the absence-as-zero defect wearing a
   *  layout. */
  note: string;
}

export interface LineageRequest {
  requestId: string;
  kind: string | null;
  seat: string | null;
  actor: string | null;
  subject: string | null;
  status: string | null;
  at: string | null;
  approvedBy: string | null;
  approvedAt: string | null;
  /** Three-valued, from the APPROVAL event's own disclosure (D22 review). See
   *  `SupersessionCheck`. */
  approvalSupersessionReadable: SupersessionCheck;
}

export interface LineageDispatch {
  taskId: string;
  seat: string | null;
  at: string | null;
  actor: string | null;
}

export interface LineageRun {
  runId: string;
  seat: string;
  task: string;
  at: string | null;
  artifactPath: string | null;
  verdict: string | null;
  /** HOW this run was joined to the request — stated, because the joins are of
   *  very different strength and a reader is entitled to know which one held.
   *  `serves_requests` is a declaration; `trace_id` is a coincidence of ids
   *  that is usually right and is not a declaration. */
  joinedBy: "serves_requests" | "trace_id" | "dispatch_task_id" | "direct";
}

export interface LineageDecision {
  runId: string;
  recId: number;
  status: string;
  actor: string | null;
  at: string | null;
  /** The instruction as the decider typed it. Null = the decision event
   *  recorded none, which is NOT the same as an empty instruction. */
  verbatim: string | null;
  /** Whether the supersession brake was consulted when this was decided. */
  supersessionReadable: SupersessionCheck;
}

/**
 * The D22 disclosure, read for the first time by anything.
 *
 * `app/api/v1/fund.py` writes `supersession_readable` onto the
 * `DeskRecommendationDecided` and `DeskRequestApproved` payloads, and its own
 * docstring says why: *"An approval taken during an outage was
 * indistinguishable in the record from a verified one."* Until this file
 * nothing read it — the field appeared in the repo exactly where it was
 * promised and nowhere else.
 *
 * FOUR values, and collapsing any two of them re-creates the defect:
 *   `checked`         — true. The brake ran.
 *   `NOT_CONSULTED`   — false. The edge store was unreadable and the approval
 *                       was taken anyway. This is the one that must be LOUD.
 *   `not_applicable`  — null. The status does not advance the row, so no check
 *                       was due. Writing `false` here would claim an outage.
 *   `undisclosed`     — the key is absent: the event predates the disclosure.
 */
export type SupersessionCheck =
  | "checked" | "not_consulted" | "not_applicable" | "undisclosed";

export function supersessionCheckOf(payload: unknown): SupersessionCheck {
  if (!payload || typeof payload !== "object") return "undisclosed";
  const p = payload as Record<string, unknown>;
  if (!("supersession_readable" in p)) return "undisclosed";
  const v = p.supersession_readable;
  if (v === null) return "not_applicable";
  if (v === false) return "not_consulted";
  if (v === true) return "checked";
  // A value the disclosure does not define. Reported as undisclosed rather
  // than coerced: a truthy string here would otherwise read as "checked".
  return "undisclosed";
}

/** The sentence each state earns. Only one of the four is a warning. */
export function supersessionCheckSentence(c: SupersessionCheck): string {
  switch (c) {
    case "checked":
      return "the supersession brake was consulted before this was recorded";
    case "not_consulted":
      return "THE SUPERSESSION BRAKE WAS NOT CONSULTED — the edge store was "
        + "unreadable and this was recorded anyway. It may have replaced or "
        + "been replaced by another row without anything checking.";
    case "not_applicable":
      return "no brake check was due — this status does not advance the row";
    default:
      return "this event predates the supersession disclosure, so whether the "
        + "brake ran is UNKNOWN rather than no";
  }
}

/** Does this state deserve the page's warning treatment? */
export function supersessionCheckIsAlarm(c: SupersessionCheck): boolean {
  return c === "not_consulted";
}

export interface Lineage {
  /** What was asked for. */
  request: LineageStage<LineageRequest>;
  /** Who was sent. */
  dispatches: LineageStage<LineageDispatch>;
  /** What came back. */
  runs: LineageStage<LineageRun>;
  /** What it recommended. */
  recommendations: LineageStage<DeskRecommendation & { run_id: string }>;
  /** What was decided, and in whose words. */
  decisions: LineageStage<LineageDecision>;
  /** Evidence that the decision was CARRIED OUT — not that it was made. */
  execution: LineageStage<{ at: string | null; actor: string | null; text: string }>;
  /** Replaced by / replaces. */
  supersessions: LineageStage<DeskSupersessionEdge>;
  /** How this chain was assembled, for a reader who wants to disagree with it. */
  joinNote: string;
  /** WHICH STORES COULD NOT BE READ, recorded from the SOURCES rather than
   *  inferred from the stages. The two are not the same thing and conflating
   *  them names the wrong culprit: an unreadable DESK makes the decisions
   *  stage unknown while the event log answered perfectly, and a warning line
   *  reading "the event log could not be read" there sends a reader to
   *  investigate a healthy store. */
  storesUnread: string[];
}

/** Everything the fold reads. Each may be null, and null means UNREADABLE. */
export interface LineageSources {
  desk: DeskView | null;
  events: SpineEvent[] | null;
  /** Edges keyed by `target_ref`. Null = the supersession store was not read. */
  edges: DeskSupersessionEdge[] | null;
  /** `hygiene.runs_declaring_service` / `runs_read` from `GET /fund/desk/ceo`.
   *  Reported so a row with no run reads as "the join is 2% populated", not as
   *  "this row was never served". */
  runsDeclaringService?: number | null;
  runsRead?: number | null;
}

/** What the drawer was opened on. Exactly one field is set. */
export type LineageAnchor =
  | { kind: "request"; requestId: string }
  | { kind: "rec"; runId: string; recId: number };

/* ------------------------------------------------------------- helpers --- */

const UNREADABLE_DESK =
  "The desk could not be read, so this part of the chain is UNKNOWN, not empty.";
const UNREADABLE_LOG =
  "The event log could not be read, so this part of the chain is UNKNOWN, "
  + "not empty.";

function stage<T>(state: LineageState, rows: T[], note: string): LineageStage<T> {
  return { state, rows, note };
}

/** `rec:<run_id>#<rec_id>` — the spine's own canonical form (deskengine.py). */
export function recRef(runId: string, recId: number): string {
  return `rec:${runId}#${recId}`;
}

/** `req:<request_id>` — the spine's own canonical form. */
export function reqRef(requestId: string): string {
  return `req:${requestId}`;
}

/**
 * The request ids a run DECLARES it served.
 *
 * `meta.serves_requests` is the only declared run→request edge the spine
 * stores. Read defensively: `meta` is free-form JSON, the key is absent on
 * most runs, and an EMPTY list is a run that carries the key and declares
 * nothing — which is a different fact from a run that never carried it, and
 * both are honestly "no declared service" here.
 */
export function servesRequests(run: { meta?: unknown } | null | undefined): string[] {
  const meta = run?.meta;
  if (!meta || typeof meta !== "object") return [];
  const raw = (meta as Record<string, unknown>).serves_requests;
  if (!Array.isArray(raw)) return [];
  return raw.map((x) => String(x ?? "").trim()).filter((s) => s.length > 0);
}

/* ------------------------------------------------------------ the fold --- */

/**
 * The chain behind one anchor.
 *
 * Read the stages in order; each is independently three-valued, because the
 * stores fail independently. A page that rendered "no lineage" when only the
 * supersession table was down would be making the outage look like a clean
 * record, which is the exact failure the D22 disclosure was written against.
 */
export function lineageFor(anchor: LineageAnchor, src: LineageSources): Lineage {
  const { desk, events, edges } = src;

  /* ---- 1. the anchor's own row, and the request it belongs to ---------- */

  let requestId: string | null = null;
  let traceId: string | null = null;
  let anchorRunId: string | null = null;

  if (anchor.kind === "request") {
    requestId = anchor.requestId;
    traceId = desk?.requests.find((r) => r.request_id === requestId)?.trace_id ?? null;
  } else {
    anchorRunId = anchor.runId;
    const run = desk?.runs.find((r) => r.run_id === anchor.runId);
    const rec = desk?.open_recommendations.find(
      (r) => r.run_id === anchor.runId && r.rec_id === anchor.recId);
    traceId = run?.trace_id ?? rec?.trace_id ?? null;
    // A run's DECLARED service is the strong edge back to the ask. Where it is
    // absent the trace id is the fallback, and the join is labelled as such.
    const declared = servesRequests(run as { meta?: unknown } | undefined);
    requestId = declared[0]
      ?? (traceId && desk?.requests.some((r) => r.request_id === traceId)
        ? traceId : null);
  }

  const requestRow = requestId
    ? desk?.requests.find((r) => r.request_id === requestId) ?? null
    : null;

  const approvalEvent = events?.find(
    (e) => e.type === "DeskRequestApproved"
      && e.payload?.request_id === requestId) ?? null;

  const request: LineageStage<LineageRequest> = desk === null
    ? stage("unreadable", [], UNREADABLE_DESK)
    : requestRow
      ? stage("found", [{
        requestId: requestRow.request_id,
        kind: requestRow.kind ?? null,
        seat: requestRow.seat ?? requestRow.serves ?? null,
        actor: requestRow.actor ?? null,
        subject: requestRow.task ?? requestRow.subject ?? null,
        status: requestRow.status ?? null,
        at: requestRow.at ?? null,
        approvedBy: requestRow.approved_by ?? null,
        approvedAt: requestRow.approved_at ?? null,
        approvalSupersessionReadable: events === null
          ? "undisclosed"
          : supersessionCheckOf(approvalEvent?.payload),
      }], "the ask this work descends from")
      : stage("absent", [],
        anchor.kind === "request"
          ? "This request is not in the desk payload — it is outside the "
            + "window this page reads, not missing from the firm."
          : "No originating request. The run that filed this row declares no "
            + "`serves_requests` and its trace id matches no request, so the "
            + "chain starts at the run. That is a bookkeeping gap, not "
            + "evidence that nobody asked for it.");

  /* ---- 2. dispatches naming that request ------------------------------- */

  const dispatchEvents = (events ?? []).filter(
    (e) => e.type === "DeskDispatched" && requestId != null
      && e.payload?.request_id === requestId);

  const dispatches: LineageStage<LineageDispatch> = events === null
    ? stage("unreadable", [], UNREADABLE_LOG)
    : dispatchEvents.length > 0
      ? stage("found", dispatchEvents.map((e) => ({
        taskId: String(e.payload?.task_id ?? e.aggregate_id),
        seat: (e.payload?.seat as string | undefined) ?? null,
        at: (e.payload?.at as string | undefined) ?? e.ts ?? null,
        actor: e.actor ?? null,
      })), "the chair fired it")
      : stage("absent", [], requestId
        ? "No dispatch event names this request. The spine's own coverage "
          + "figure says most dispatch events carry no `request_id` at all, so "
          + "this is usually a missing field rather than an undispatched ask."
        : "No request to dispatch — see above.");

  /* ---- 3. the runs that served it -------------------------------------- */

  const allRuns = desk?.runs ?? [];
  const runRows: LineageRun[] = [];
  const seen = new Set<string>();
  const add = (r: DeskView["runs"][number], joinedBy: LineageRun["joinedBy"]) => {
    if (seen.has(r.run_id)) return;
    seen.add(r.run_id);
    runRows.push({
      runId: r.run_id,
      seat: r.seat,
      task: r.task,
      at: r.resolved_at ?? r.dispatched_at ?? null,
      artifactPath: r.artifact_path ?? null,
      verdict: r.verdict ?? null,
      joinedBy,
    });
  };
  // ORDER MATTERS: the strongest join is attributed first, so a run that both
  // declares service AND shares a trace is labelled by the declaration.
  if (requestId) {
    for (const r of allRuns) {
      if (servesRequests(r as { meta?: unknown }).includes(requestId)) {
        add(r, "serves_requests");
      }
    }
  }
  if (anchorRunId) {
    const own = allRuns.find((r) => r.run_id === anchorRunId);
    if (own) add(own, "direct");
  }
  if (traceId) {
    for (const r of allRuns) if (r.trace_id === traceId) add(r, "trace_id");
  }
  for (const d of dispatchEvents) {
    const tid = d.payload?.task_id;
    for (const r of allRuns) if (tid && r.trace_id === tid) add(r, "dispatch_task_id");
  }

  const declaring = src.runsDeclaringService;
  const read = src.runsRead;
  const coverage = typeof declaring === "number" && typeof read === "number" && read > 0
    ? ` The declared run→request join is ${declaring} of ${read} runs firm-wide,`
      + " so an empty stage here is the norm and not a fact about this row."
    : " The spine reported no coverage figure for the declared run→request"
      + " join, so how populated it is here is unknown.";

  const runs: LineageStage<LineageRun> = desk === null
    ? stage("unreadable", [], UNREADABLE_DESK)
    : runRows.length > 0
      ? stage("found", runRows, "what came back")
      : stage("absent", [],
        `No run in the desk payload is joined to this row.${coverage}`
        + " The payload also carries only the most recent runs, so an older"
        + " run would be outside this window rather than absent.");

  /* ---- 4. the recommendations those runs filed ------------------------- */

  const recRows: (DeskRecommendation & { run_id: string })[] = [];
  for (const r of runRows) {
    const run = allRuns.find((x) => x.run_id === r.runId);
    for (const rec of run?.recommendations ?? []) {
      recRows.push({ ...rec, run_id: r.runId });
    }
  }
  const recommendations: LineageStage<DeskRecommendation & { run_id: string }> =
    desk === null
      ? stage("unreadable", [], UNREADABLE_DESK)
      : recRows.length > 0
        ? stage("found", recRows, "what it recommended")
        : stage("absent", [], runRows.length === 0
          ? "No run, so no recommendations to list."
          : "These runs filed no recommendations. A run can deliver a finding "
            + "without asking for a decision, and that is a result, not a gap.");

  /* ---- 5. the decisions, with the instruction verbatim ----------------- */

  const wanted = new Set<string>();
  for (const rec of recRows) wanted.add(`${rec.run_id}#${rec.rec_id}`);
  if (anchor.kind === "rec") wanted.add(`${anchor.runId}#${anchor.recId}`);

  const decisionRows: LineageDecision[] = [];
  for (const e of events ?? []) {
    if (e.type !== "DeskRecommendationDecided") continue;
    const runId = e.payload?.run_id;
    const recId = e.payload?.rec_id;
    if (typeof runId !== "string" || typeof recId !== "number") continue;
    if (!wanted.has(`${runId}#${recId}`)) continue;
    const note = e.payload?.note;
    decisionRows.push({
      runId,
      recId,
      status: String(e.payload?.status ?? "unknown"),
      actor: e.actor ?? null,
      at: (e.payload?.at as string | undefined) ?? e.ts ?? null,
      // An EMPTY string is not an instruction. The spine writes "" when the
      // decider typed nothing, and rendering that as a quoted instruction
      // would put empty quotation marks under a decision.
      verbatim: typeof note === "string" && note.trim().length > 0
        ? note : null,
      supersessionReadable: supersessionCheckOf(e.payload),
    });
  }
  decisionRows.sort((a, b) => (a.at ?? "").localeCompare(b.at ?? ""));

  // THE JOIN'S INPUT CAN FAIL WITHOUT THE LOG FAILING, and reporting that as
  // "no decision" would be an outage wearing an empty record's clothes. A
  // request anchor has no rec of its own: the rows it owns are enumerated from
  // the DESK's run list, so an unreadable desk leaves nothing to look up and
  // the stage is UNKNOWN even though the log answered perfectly.
  const cannotEnumerate = desk === null && wanted.size === 0;
  const decisions: LineageStage<LineageDecision> = events === null
    ? stage("unreadable", [], UNREADABLE_LOG)
    : cannotEnumerate
      ? stage("unreadable", [],
        "The event log was read, but the desk was not — so which rows belong "
        + "to this chain could not be established, and whether any of them was "
        + "decided is UNKNOWN rather than no.")
      : decisionRows.length > 0
        ? stage("found", decisionRows, "what was decided, and in whose words")
        : stage("absent", [],
          "No decision has been recorded against these rows in the events this "
          + "page can see. The log endpoint is capped, so an older decision is "
          + "outside the window rather than absent.");

  /* ---- 6. execution evidence ------------------------------------------- */

  // DELIBERATELY NARROW. The desk records that a decision was MADE in several
  // places and that it was CARRIED OUT in exactly one: the resolution text on
  // the request. Treating `status: accepted` as execution is the "EXECUTED"
  // text-grep this desk was repaired from, so it is not done here.
  const resolveEvents = (events ?? []).filter(
    (e) => e.type === "DeskRequestResolved" && requestId != null
      && e.payload?.request_id === requestId);

  const execution: LineageStage<{ at: string | null; actor: string | null; text: string }> =
    events === null
      ? stage("unreadable", [], UNREADABLE_LOG)
      : resolveEvents.length > 0
        ? stage("found", resolveEvents.map((e) => ({
          at: (e.payload?.at as string | undefined) ?? e.ts ?? null,
          actor: e.actor ?? null,
          text: String(e.payload?.resolution ?? "").trim()
            || "resolved with no resolution text recorded",
        })), "evidence it was carried out")
        : stage("absent", [],
          "Nothing records that this was CARRIED OUT. The desk stores a "
          + "resolution on the request and nothing else; an accepted "
          + "recommendation with no resolved request is a decision made and "
          + "not yet evidenced, which is different from one that failed.");

  /* ---- 7. supersession edges ------------------------------------------- */

  const refs = new Set<string>();
  if (requestId) refs.add(reqRef(requestId));
  if (anchor.kind === "rec") refs.add(recRef(anchor.runId, anchor.recId));
  for (const rec of recRows) refs.add(recRef(rec.run_id, rec.rec_id));

  const edgeRows = (edges ?? []).filter(
    (e) => refs.has(e.target_ref)
      || (e.superseder_ref != null && refs.has(e.superseder_ref)));

  const supersessions: LineageStage<DeskSupersessionEdge> = edges === null
    ? stage("unreadable", [],
      "The supersession store could not be read, so whether this row was "
      + "replaced is UNKNOWN — not no.")
    : edgeRows.length > 0
      ? stage("found", edgeRows, "replaced by, or replaces")
      : stage("absent", [],
        "The supersession store was read and holds no edge touching this row.");

  const joins = runRows.map((r) => r.joinedBy);
  const joinNote = runRows.length === 0
    ? "This chain was assembled from the request's own id alone; no run is "
      + "joined to it."
    : `Joined by ${Array.from(new Set(joins)).join(", ")}. `
      + "`serves_requests` is a declaration by the run; `trace_id` is a shared "
      + "id and is a weaker claim.";

  const storesUnread: string[] = [];
  if (desk === null) storesUnread.push("the desk");
  if (events === null) storesUnread.push("the event log");
  if (edges === null) storesUnread.push("the supersession store");

  return {
    request, dispatches, runs, recommendations, decisions, execution,
    supersessions, joinNote, storesUnread,
  };
}

/**
 * The stores behind this chain that could not be read, for the ONE warning
 * line the drawer prints above everything.
 *
 * Kept apart from the per-stage sentences on purpose: a reader scanning a
 * chain needs to know at the TOP that part of it is an outage, before they
 * read six stages and conclude the record is thin.
 */
export function unreadableStages(l: Lineage): string[] {
  return l.storesUnread;
}

/**
 * The loudest supersession-check finding anywhere in this chain.
 *
 * `not_consulted` outranks everything: it is the only value that says a
 * governance brake was skipped. Returns null when nothing in the chain
 * discloses anything at all.
 */
export function worstSupersessionCheck(l: Lineage): SupersessionCheck | null {
  const seen: SupersessionCheck[] = [];
  for (const r of l.request.rows) seen.push(r.approvalSupersessionReadable);
  for (const d of l.decisions.rows) seen.push(d.supersessionReadable);
  if (seen.length === 0) return null;
  if (seen.includes("not_consulted")) return "not_consulted";
  if (seen.includes("checked")) return "checked";
  if (seen.includes("not_applicable")) return "not_applicable";
  return "undisclosed";
}
