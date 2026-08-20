/**
 * Desk derivations — every number on the seat pages and the office view is
 * computed HERE, from a spine payload, by a pure function.
 *
 * Why a separate module rather than inline in the pages: these are the figures
 * a manager calibrates trust on ("has the adversary ever changed my mind?",
 * "what has this seat cost?"). A metric derived inline in JSX cannot be tested,
 * and an untested derivation is exactly how a page ends up asserting a number
 * the API never returned. Everything here is a pure function over shapes read
 * from a real response, and every one of them has a test that fails if the
 * derivation starts inventing.
 *
 * Two rules the whole file obeys, inherited from the harness:
 *
 *   1. **Absence is never zero.** A missing token count is `null`, not 0. A
 *      seat that was never dispatched has `null` dispatches, not 0 — the page
 *      says "never dispatched" rather than drawing an empty bar.
 *   2. **No number is stated that an endpoint did not return.** Where a
 *      lane-native metric the brief asks for has no field behind it, the
 *      derivation returns an `Absent` marker naming what is missing, and the
 *      page renders that sentence instead of a look-alike figure.
 */

import type { DeskView, SpineEvent } from "@/lib/fund_api";

/* ------------------------------------------------------------------ seats -- */

/** The bench, in the order the constitution lists it.
 *
 * Kept here as the ROUTE whitelist only — an unknown `[seat]` must 404 rather
 * than render an empty shell. Everything displayed about a seat (lane, emits,
 * why it exists) is read from `GET /fund/desk`, never restated here: the roster
 * lives in app/fund/desk.py and a second copy would be a second thing to drift.
 */
export const SEATS = [
  "mechanism",
  "analyst",
  "pm",
  "quant",
  "adversary",
  "validator",
  "riskofficer",
  "builder",
  "coo",
] as const;

export type SeatId = (typeof SEATS)[number];

export function isSeat(s: string | undefined | null): s is SeatId {
  return !!s && (SEATS as readonly string[]).includes(s);
}

/** Which request kind the desk routes to which seat.
 *
 * Mirror of `REQUEST_KINDS` in app/fund/desk.py — used only to PRE-FILL the
 * composer on a seat page, so "ask the pm to re-review" is one field and one
 * click. The spine validates the kind on POST regardless; if this map ever
 * drifts, the request is rejected with a 422 listing the valid kinds rather
 * than silently filed to the wrong seat.
 */
export const SEAT_REQUEST_KIND: Record<SeatId, string> = {
  mechanism: "proposal",
  analyst: "thesis",
  pm: "portfolio_review",
  quant: "implement",
  adversary: "attack",
  validator: "audit",
  riskofficer: "policy_audit",
  builder: "build",
  coo: "triage",
};

/** Declared model placement, per the quota-era dispatch rules in the workspace
 *  constitution (.claude/CLAUDE.md, 2026-08-20).
 *
 *  DECLARED, not measured: the spine cannot see which model a session used. The
 *  page renders this as a declaration and shows the models actually OBSERVED on
 *  the seat's runs (`run.model`) beside it — when the two disagree, that gap is
 *  itself the finding (the cost model records one such: the pm and analyst first
 *  runs inherited the Fable main-session model because the dispatch was not
 *  pinned).
 */
export const SEAT_PLACEMENT: Record<SeatId, string> = {
  mechanism: "Opus",
  analyst: "split — survey/scan local (qwen), thesis judgement Opus",
  pm: "Opus",
  quant: "hybrid — local 4090 drafts, Opus reviews, the belt judges",
  adversary: "Opus — never downgraded, never local",
  validator: "Opus (its simulations run on local compute)",
  riskofficer: "Opus",
  builder: "Opus",
  coo: "Opus — judgement near governance, never downgraded, never local",
};

/* ------------------------------------------------------------- absences --- */

/** A metric that has no field behind it yet.
 *
 * Rendered as a sentence naming the missing input, so a reader can tell the
 * difference between "measured, and it is zero" and "nothing measures this".
 * The two look identical on a dashboard and mean opposite things.
 */
export interface Absent {
  absent: true;
  /** What is missing, in the reader's terms. */
  what: string;
  /** The endpoint or field that would supply it. Named so the CTO can build it. */
  needs: string;
}

export function absent(what: string, needs: string): Absent {
  return { absent: true, what, needs };
}

export function isAbsent(v: unknown): v is Absent {
  return typeof v === "object" && v !== null && (v as Absent).absent === true;
}

/* --------------------------------------------------------------- typing --- */

export type DeskRun = DeskView["runs"][number];
export type DeskArtifact = DeskView["artifacts"][number];
export type DeskRequest = DeskView["requests"][number];
export type DeskRec = DeskView["runs"][number]["recommendations"][number];

/* ------------------------------------------------------------ economics --- */

/** Anthropic first-party list prices, $ per million tokens.
 *
 * Source: ClarkHarness/docs/COST_MODEL_2026-08-20.md ("API pricing in force,
 * checked 2026-08-20"). Rendered on-page in full beside any figure derived from
 * it, because a dollar number whose price table is invisible is indistinguishable
 * from a made-up one.
 *
 * The flight recorder stores a token TOTAL, not an input/output split, so a cost
 * from it is a blend estimate and is labelled as one everywhere it appears.
 * The blend below is the same 90/10 in/out the cost model uses for its working
 * number (~$0.70 per 100k-token Opus dispatch).
 */
export const PRICE_TABLE: Record<string, { inPerMTok: number; outPerMTok: number }> = {
  opus: { inPerMTok: 5.0, outPerMTok: 25.0 },
  fable: { inPerMTok: 10.0, outPerMTok: 50.0 },
  sonnet: { inPerMTok: 3.0, outPerMTok: 15.0 },
  haiku: { inPerMTok: 1.0, outPerMTok: 5.0 },
  // Local inference on the 4090 costs electricity, not API dollars. Zero here
  // is a MEASURED zero (no API call is made), not an unknown rendered as zero.
  local: { inPerMTok: 0.0, outPerMTok: 0.0 },
};

/** Share of tokens assumed to be input. Agentic work is input-heavy (context
 *  re-reads); the cost model's realistic column uses this same split. */
export const ASSUMED_INPUT_SHARE = 0.9;

/** Which price row a recorded `run.model` string maps to, or null if none does.
 *
 * Null is the important return: an unknown model must produce NO cost figure
 * rather than a default-priced one. A cost silently computed at Opus rates for
 * a model that was actually Fable understates the bill by 2× — the exact error
 * the cost model already caught once.
 */
export function priceRowFor(model: string | null | undefined): string | null {
  const m = (model || "").toLowerCase();
  if (!m) return null;
  for (const key of Object.keys(PRICE_TABLE)) {
    if (m.includes(key)) return key;
  }
  if (m.includes("qwen") || m.includes("ollama")) return "local";
  return null;
}

/** Blended $ estimate for one run, or null when it cannot be computed.
 *
 * Returns null — never 0 — when the model is unpriced or the token total was
 * not recorded. A zero would read as "this run was free".
 */
export function estimateCostUsd(model: string | null | undefined,
                                tokens: number | null | undefined): number | null {
  if (tokens == null || !Number.isFinite(tokens)) return null;
  const key = priceRowFor(model);
  if (!key) return null;
  const p = PRICE_TABLE[key];
  const inTok = tokens * ASSUMED_INPUT_SHARE;
  const outTok = tokens * (1 - ASSUMED_INPUT_SHARE);
  return (inTok * p.inPerMTok + outTok * p.outPerMTok) / 1_000_000;
}

export interface TokenStats {
  /** Runs considered. */
  runs: number;
  /** How many of them recorded a token total. Shown whenever it is < runs:
   *  an average over 2 of 9 runs is not the seat's average. */
  reported: number;
  total: number | null;
  avg: number | null;
  min: number | null;
  max: number | null;
  /** Sum of per-run estimates, and how many runs could be priced. */
  costUsd: number | null;
  priced: number;
}

/** Dispatch economics for one seat's runs. Nulls survive; they do not become 0. */
export function tokenStats(runs: DeskRun[]): TokenStats {
  const toks = runs
    .map((r) => r.tokens)
    .filter((t): t is number => t != null && Number.isFinite(t));
  let cost: number | null = null;
  let priced = 0;
  for (const r of runs) {
    const c = estimateCostUsd(r.model, r.tokens);
    if (c != null) {
      cost = (cost ?? 0) + c;
      priced += 1;
    }
  }
  return {
    runs: runs.length,
    reported: toks.length,
    total: toks.length ? toks.reduce((a, b) => a + b, 0) : null,
    avg: toks.length ? toks.reduce((a, b) => a + b, 0) / toks.length : null,
    min: toks.length ? Math.min(...toks) : null,
    max: toks.length ? Math.max(...toks) : null,
    costUsd: cost,
    priced,
  };
}

/* --------------------------------------------------------------- events --- */

export const DESK_EVENT_TYPES = {
  requested: "DeskRequested",
  dispatched: "DeskDispatched",
  resolved: "DeskRequestResolved",
  decided: "DeskRecommendationDecided",
} as const;

/** Event payloads are `Record<string, any>` on the wire; this narrows the few
 *  keys the desk folds on, all of them verified against a live response. */
type Payload = Record<string, unknown>;

const str = (p: Payload, k: string): string | null => {
  const v = p[k];
  return typeof v === "string" && v ? v : null;
};

export interface DispatchStats {
  /** null = never dispatched. Zero would claim we counted zero dispatches for a
   *  seat that has been running all week but whose events fell outside the
   *  window — the caller states the window, this states the count. */
  dispatches: number | null;
  lastAt: string | null;
  /** Distinct actors who dispatched this seat (ceo / cto), for the office view. */
  actors: string[];
}

export function dispatchStats(events: SpineEvent[], seat: string): DispatchStats {
  const rows = events.filter(
    (e) => e.type === DESK_EVENT_TYPES.dispatched &&
           str(e.payload as Payload, "seat") === seat,
  );
  if (!rows.length) return { dispatches: null, lastAt: null, actors: [] };
  const times = rows.map((e) => e.ts).filter(Boolean).sort();
  return {
    dispatches: rows.length,
    lastAt: times.length ? times[times.length - 1] : null,
    actors: Array.from(new Set(rows.map((e) => e.actor).filter(Boolean))),
  };
}

/* ---------------------------------------------------------------- traces -- */

export type TraceNodeKind = "request" | "dispatch" | "run" | "decision";

export interface TraceNode {
  kind: TraceNodeKind;
  at: string | null;
  actor: string | null;
  label: string;
  /** Present on run nodes; the gate's or the seat's verdict, verbatim. */
  verdict?: string | null;
  seat?: string | null;
  runId?: string | null;
  status?: string | null;
}

export interface TraceThread {
  traceId: string;
  /** True when the thread was keyed by a run/request id because no trace_id was
   *  recorded. Rendered as such — an untraced run is not part of some other
   *  chain, and merging every untraced item into one "null" thread would draw a
   *  conversation that never happened. */
  synthetic: boolean;
  seats: string[];
  nodes: TraceNode[];
  /** Earliest and latest node timestamps, for the day filter. */
  first: string | null;
  last: string | null;
}

/**
 * Group desk events and flight-recorder runs into chatter threads by trace_id.
 *
 * The trace is born at the desk request (its id doubles as the trace id) and is
 * carried verbatim onto the dispatch, the run, its recommendations and the
 * decision events — so one id replays the whole conversation. Verified against
 * the live log: DeskRequested / DeskDispatched / DeskRequestResolved /
 * DeskRecommendationDecided all carry `trace_id` in their payloads.
 */
export function traceThreads(events: SpineEvent[], runs: DeskRun[]): TraceThread[] {
  const threads = new Map<string, TraceThread>();

  const push = (key: string, synthetic: boolean, node: TraceNode) => {
    let t = threads.get(key);
    if (!t) {
      t = { traceId: key, synthetic, seats: [], nodes: [], first: null, last: null };
      threads.set(key, t);
    }
    t.nodes.push(node);
    if (node.seat && !t.seats.includes(node.seat)) t.seats.push(node.seat);
  };

  for (const e of events) {
    const p = (e.payload || {}) as Payload;
    const trace = str(p, "trace_id");
    if (e.type === DESK_EVENT_TYPES.requested) {
      push(trace || str(p, "request_id") || e.event_id, !trace, {
        kind: "request",
        at: e.ts,
        actor: e.actor,
        seat: str(p, "serves"),
        label: str(p, "subject") || "(request)",
      });
    } else if (e.type === DESK_EVENT_TYPES.dispatched) {
      push(trace || str(p, "task_id") || e.event_id, !trace, {
        kind: "dispatch",
        at: e.ts,
        actor: e.actor,
        seat: str(p, "seat"),
        label: str(p, "task") || "(dispatch)",
      });
    } else if (e.type === DESK_EVENT_TYPES.decided) {
      push(trace || str(p, "run_id") || e.event_id, !trace, {
        kind: "decision",
        at: e.ts,
        actor: e.actor,
        seat: str(p, "seat"),
        runId: str(p, "run_id"),
        status: str(p, "status"),
        label: str(p, "text") || "(recommendation)",
      });
    }
  }

  for (const r of runs) {
    push(r.trace_id || r.run_id, !r.trace_id, {
      kind: "run",
      at: r.resolved_at || r.dispatched_at || null,
      actor: null,
      seat: r.seat,
      runId: r.run_id,
      verdict: r.verdict ?? null,
      label: r.task,
    });
  }

  const out = Array.from(threads.values());
  for (const t of out) {
    t.nodes.sort((a, b) => (a.at || "").localeCompare(b.at || ""));
    const times = t.nodes.map((n) => n.at).filter((x): x is string => !!x).sort();
    t.first = times[0] ?? null;
    t.last = times.length ? times[times.length - 1] : null;
  }
  out.sort((a, b) => (b.last || "").localeCompare(a.last || ""));
  return out;
}

export interface FeedItem extends TraceNode {
  traceId: string;
  synthetic: boolean;
}

/**
 * The wire: every interaction on the desk as one reverse-chronological stream —
 * the ask, the dispatch, the delivery, the decision — so the office reads like
 * a room where the seats can be watched talking. Built by flattening the trace
 * threads, deliberately: the live view and the audit trail are the SAME nodes,
 * so nothing can appear on the wire that a trace replay would not show.
 */
export function wireFeed(events: SpineEvent[], runs: DeskRun[],
                         limit = 30): FeedItem[] {
  const items: FeedItem[] = [];
  for (const t of traceThreads(events, runs)) {
    for (const n of t.nodes) {
      items.push({ ...n, traceId: t.traceId, synthetic: t.synthetic });
    }
  }
  items.sort((a, b) => (b.at || "").localeCompare(a.at || ""));
  return items.slice(0, limit);
}

/* ------------------------------------------------------------------ days -- */

/** UTC date key. The event log is UTC and the fund's day boundaries are the
 *  venue's, not the reader's — a local-time bucket would move a dispatch to a
 *  different day depending on who opened the page. */
export function dayKey(ts: string | null | undefined): string | null {
  if (!ts) return null;
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString().slice(0, 10);
}

/** Every day the desk did something, newest first. Days with no desk activity
 *  are absent from the list rather than rendered as empty columns. */
export function activeDays(events: SpineEvent[], runs: DeskRun[]): string[] {
  const days = new Set<string>();
  for (const e of events) {
    if (Object.values(DESK_EVENT_TYPES).includes(e.type as never)) {
      const k = dayKey(e.ts);
      if (k) days.add(k);
    }
  }
  for (const r of runs) {
    const k = dayKey(r.resolved_at);
    if (k) days.add(k);
  }
  return Array.from(days).sort().reverse();
}

export interface DayFold {
  day: string;
  dispatches: number;
  requests: number;
  resolutions: number;
  decisions: number;
  /** Runs whose resolved_at falls on this day. */
  runs: DeskRun[];
  /** Runs that recorded a verdict. */
  verdicts: number;
  /** Verdicts that read as a kill. At this firm a kill is a WIN and the strip
   *  renders it as one — the count exists so a good day of killing does not
   *  look like a day of nothing. */
  kills: number;
  /** Sum of tokens over runs resolved that day; null when none reported. */
  tokens: number | null;
  /** Blended $ estimate over the same runs; null when nothing could be priced. */
  costUsd: number | null;
  seats: string[];
  /** Who triggered the day's dispatches (ceo / cto), from the event actor. */
  actors: string[];
}

/** Does a verdict string read as a kill? Matched on the vocabulary the desk
 *  actually uses (adversary verdicts are KILL / SURVIVES / CANNOT TELL; the
 *  gate's are longer sentences that contain KILLED / FAILS). Deliberately
 *  conservative: "CANNOT TELL" is not a kill, and neither is a sentence that
 *  merely mentions the word. */
export function isKillVerdict(verdict: string | null | undefined): boolean {
  const v = (verdict || "").trim().toUpperCase();
  if (!v) return false;
  return v.startsWith("KILL") || v.startsWith("KILLED") || v.startsWith("FAIL");
}

/** The three verdicts the bench actually stamps, and nothing else.
 *
 * A memo thread stamps a verdict the way a clerk stamps a file — which only
 * works for a verdict that IS one word. Several real verdicts are sentences
 * ("POLICY CORRECT, WORLD FALSE; FIX INCOMPLETE (F1)…"), and compressing one of
 * those into a stamp would assert a cleaner finding than the seat delivered. So
 * this returns null for anything it does not recognise, and the card renders the
 * verdict verbatim instead. Recognition is on the OPENING word only, the same
 * rule `isKillVerdict` uses — a verdict that merely mentions "kill" is not one.
 */
export function verdictStamp(verdict: string | null | undefined): "KILL" | "SURVIVES" | "CANNOT TELL" | null {
  const v = (verdict || "").trim().toUpperCase();
  if (!v) return null;
  if (v.startsWith("KILL") || v.startsWith("FAIL")) return "KILL";
  if (v.startsWith("SURVIVE")) return "SURVIVES";
  if (v.startsWith("CANNOT TELL")) return "CANNOT TELL";
  return null;
}

export function foldDay(events: SpineEvent[], runs: DeskRun[], day: string): DayFold {
  const on = (ts: string | null | undefined) => dayKey(ts) === day;
  const dayEvents = events.filter((e) => on(e.ts));
  const dayRuns = runs.filter((r) => on(r.resolved_at));
  const dispatched = dayEvents.filter((e) => e.type === DESK_EVENT_TYPES.dispatched);
  const toks = dayRuns
    .map((r) => r.tokens)
    .filter((t): t is number => t != null && Number.isFinite(t));
  let cost: number | null = null;
  for (const r of dayRuns) {
    const c = estimateCostUsd(r.model, r.tokens);
    if (c != null) cost = (cost ?? 0) + c;
  }
  const seats = new Set<string>();
  for (const e of dispatched) {
    const s = str(e.payload as Payload, "seat");
    if (s) seats.add(s);
  }
  for (const r of dayRuns) seats.add(r.seat);
  return {
    day,
    dispatches: dispatched.length,
    requests: dayEvents.filter((e) => e.type === DESK_EVENT_TYPES.requested).length,
    resolutions: dayEvents.filter((e) => e.type === DESK_EVENT_TYPES.resolved).length,
    decisions: dayEvents.filter((e) => e.type === DESK_EVENT_TYPES.decided).length,
    runs: dayRuns,
    verdicts: dayRuns.filter((r) => !!r.verdict).length,
    kills: dayRuns.filter((r) => isKillVerdict(r.verdict)).length,
    tokens: toks.length ? toks.reduce((a, b) => a + b, 0) : null,
    costUsd: cost,
    seats: Array.from(seats).sort(),
    actors: Array.from(new Set(dispatched.map((e) => e.actor).filter(Boolean))).sort(),
  };
}

/* ------------------------------------------------------- lane-native ------ */

export interface RecFunnel {
  made: number;
  open: number;
  accepted: number;
  rejected: number;
  staged: number;
  done: number;
}

/**
 * The PM's decision funnel — made → accepted / rejected / staged / done.
 *
 * Folded from `run.recommendations[].status` over the seat's own runs, NOT from
 * `open_recommendations`: that list deliberately carries only open / accepted /
 * staged, so a funnel built on it would show a fund that has never rejected
 * anything. Rejections are the part of the record most worth keeping.
 */
export function recFunnel(runs: DeskRun[]): RecFunnel {
  const f: RecFunnel = { made: 0, open: 0, accepted: 0, rejected: 0, staged: 0, done: 0 };
  for (const r of runs) {
    for (const rec of r.recommendations || []) {
      f.made += 1;
      const s = rec.status;
      if (s === "open") f.open += 1;
      else if (s === "accepted") f.accepted += 1;
      else if (s === "rejected") f.rejected += 1;
      else if (s === "staged") f.staged += 1;
      else if (s === "done") f.done += 1;
    }
  }
  return f;
}

export interface KillBoard {
  kill: number;
  survives: number;
  cannotTell: number;
  other: number;
  /** Artifacts with a review on file, and the ones without. An unreviewed
   *  artifact is NOT a survivor — the desk payload states this itself and the
   *  board keeps the two apart. */
  reviewed: DeskArtifact[];
  unreviewed: DeskArtifact[];
}

/** The adversary's board, from run verdicts and from reviews on file. */
export function killBoard(runs: DeskRun[], artifacts: DeskArtifact[]): KillBoard {
  const board: KillBoard = {
    kill: 0, survives: 0, cannotTell: 0, other: 0, reviewed: [], unreviewed: [],
  };
  const verdicts: string[] = [];
  for (const r of runs) if (r.verdict) verdicts.push(r.verdict);
  for (const a of artifacts) {
    if (a.review) {
      board.reviewed.push(a);
      if (a.review.verdict) verdicts.push(a.review.verdict);
    } else {
      board.unreviewed.push(a);
    }
  }
  for (const raw of verdicts) {
    const v = raw.trim().toUpperCase();
    if (v.startsWith("KILL")) board.kill += 1;
    else if (v.startsWith("SURVIVE")) board.survives += 1;
    else if (v.startsWith("CANNOT")) board.cannotTell += 1;
    else board.other += 1;
  }
  return board;
}

export interface AutopolicyAudit {
  /** Approvals whose approver names the auto-policy. */
  auto: SpineEvent[];
  /** Every approval in the window, for the ratio. */
  approvals: number;
  /** Exit rules that fired — the only orders v1's envelope can cover. */
  exitsFired: number;
  /** Halts and resumes in the window; the policy must not act while halted. */
  halts: number;
}

/**
 * What the risk officer supervises: auto-approvals actually made, against what
 * could have been auto-approved.
 *
 * `payload.approver` is the field: `app/fund/autopolicy.py` approves through the
 * ordinary pipeline with `approver=f"auto-policy-{AUTOPOLICY_VERSION}"`, so an
 * auto-approval is identifiable in the log forever. Verified against a live
 * OrderApproved event, whose payload is `{"approver": "<name>"}`.
 */
export function autopolicyAudit(events: SpineEvent[]): AutopolicyAudit {
  const approvals = events.filter((e) => e.type === "OrderApproved");
  const auto = approvals.filter((e) => {
    const a = str(e.payload as Payload, "approver") || "";
    return a.toLowerCase().startsWith("auto-policy");
  });
  return {
    auto,
    approvals: approvals.length,
    exitsFired: events.filter((e) => e.type === "ExitRuleTriggered").length,
    halts: events.filter((e) => e.type === "TradingHalted" || e.type === "TradingResumed").length,
  };
}

/** Artifacts this seat is implicated in, by the review/authorship the payload
 *  can actually prove. The desk payload has no author field, so:
 *   - the adversary owns artifacts that HAVE a review (it wrote them),
 *   - everyone else's artifacts are matched by the run's artifact_path.
 *  Anything not matchable is left out rather than guessed at. */
export function artifactsForRuns(runs: DeskRun[], artifacts: DeskArtifact[]): DeskArtifact[] {
  const paths = new Set(
    runs.map((r) => (r.artifact_path || "").replace(/\\/g, "/")).filter(Boolean),
  );
  return artifacts.filter(
    (a) => paths.has(a.path) || (a.review ? paths.has(a.review.review_path) : false),
  );
}

/* ------------------------------------------------- the production shelf --- */

/** One thing a desk produced, on a date. The spine has no "artifact authored
 *  by seat X" field, so a shelf entry is anchored to a RUN — the only record
 *  that ties a seat to a delivery — and enriched from the artifact fold when the
 *  run named a path that the fold also carries. */
export interface ShelfItem {
  runId: string;
  /** resolved_at; null when the flight recorder never recorded one. */
  at: string | null;
  /** The artifact's own title where the fold has it, else the run's task. */
  title: string;
  /** Which of those two the title came from — the page says so rather than
   *  passing a task off as a filed document title. */
  titleFrom: "artifact" | "task";
  /** null = this run filed no artifact path. Rendered as "no artifact filed",
   *  never as an empty spine. */
  path: string | null;
  /** Present only when `path` matched something in the desk's artifact fold. */
  kind: string | null;
  status: string | null;
  /** The run's verdict, else the artifact's review verdict. Null is null. */
  verdict: string | null;
}

/**
 * What one desk produced, in time order — the CEO's "what each desk is
 * producing (across time)".
 *
 * Deliberately run-anchored. Matching artifacts to a seat any other way would
 * require an author field that `GET /fund/desk` does not return (see
 * `artifactsForRuns`), and a shelf that guessed authorship would credit the
 * wrong desk. A run that filed nothing still appears, marked as having filed
 * nothing: a delivery with no artifact is a fact about the record, not a gap to
 * hide.
 */
export function productionShelf(runs: DeskRun[], artifacts: DeskArtifact[]): ShelfItem[] {
  // Two indexes, because the fold stores an adversarial REVIEW under the
  // artifact it reviewed rather than as an artifact of its own. Indexing only
  // by `artifact.path` would leave every review the adversary ever filed
  // looking like a document the fold has never heard of — the same asymmetry
  // `artifactsForRuns` already has to work around.
  const byPath = new Map<string, DeskArtifact>();
  const byReviewPath = new Map<string, DeskArtifact>();
  for (const a of artifacts) {
    byPath.set(a.path.replace(/\\/g, "/"), a);
    if (a.review?.review_path) {
      byReviewPath.set(a.review.review_path.replace(/\\/g, "/"), a);
    }
  }

  const items = runs.map((r): ShelfItem => {
    const path = (r.artifact_path || "").replace(/\\/g, "/") || null;
    const art = path ? byPath.get(path) ?? null : null;
    const reviewed = path && !art ? byReviewPath.get(path) ?? null : null;

    if (reviewed) {
      // A review's title and verdict are its own; the killed/survives status
      // belongs to the document it reviewed, not to the review, so it is not
      // copied across.
      return {
        runId: r.run_id,
        at: r.resolved_at ?? r.dispatched_at ?? null,
        title: reviewed.review!.review_title || r.task,
        titleFrom: reviewed.review!.review_title ? "artifact" : "task",
        path,
        kind: "review",
        status: null,
        verdict: r.verdict ?? reviewed.review!.verdict ?? null,
      };
    }

    return {
      runId: r.run_id,
      at: r.resolved_at ?? r.dispatched_at ?? null,
      title: art?.title || r.task,
      titleFrom: art?.title ? "artifact" : "task",
      path,
      kind: art?.kind ?? null,
      status: art?.status ?? null,
      verdict: r.verdict ?? art?.review?.verdict ?? null,
    };
  });

  // Newest first; undated entries sort last rather than to the top, where an
  // empty timestamp would otherwise read as "just now".
  items.sort((a, b) => {
    if (!a.at && !b.at) return 0;
    if (!a.at) return 1;
    if (!b.at) return -1;
    return b.at.localeCompare(a.at);
  });
  return items;
}

/* ------------------------------------------------------------ formatting -- */

export const fmtTokens = (n: number | null | undefined): string =>
  n == null ? "—" : n >= 1000 ? `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k` : `${n}`;

export const fmtUsd = (n: number | null | undefined): string =>
  n == null ? "—" : `$${n.toFixed(n < 10 ? 2 : 0)}`;

/** UTC, always — the log is UTC and a local-time render invites the reader to
 *  compare it with a timestamp that means something else. */
export const fmtAt = (ts: string | null | undefined): string =>
  !ts ? "—" : `${ts.slice(0, 16).replace("T", " ")}Z`;
