/**
 * The executive desks' derivations — how the CEO's queue is ORDERED, and what
 * the CTO's queue knows about who filed each ask.
 *
 * Brief: docs/briefs/EXEC_DESKS_2026-08-20.md. The CEO desk "ranks the way the
 * coo seat ranks (money, reversibility, staleness)". Implementing that honestly
 * required checking what the spine actually returns for each of the three keys,
 * and the answer is uneven — so the uneven part is stated rather than smoothed:
 *
 *   MONEY — `GET /fund/orders/pending` gives every order an
 *     `impact_preview.notional_usd` (verified live 2026-08-20: the SOFI sell
 *     carries 169.25). Recommendations carry NO money field at all: of the 47
 *     open recommendations on the desk that day, ZERO stated a dollar figure in
 *     a machine-readable place. So a recommendation's money is `null` — not
 *     zero, and not scraped out of its prose. `moneyGap()` below reports how
 *     many items ranked without a money key, and the page prints that sentence.
 *     A ranking that silently pretends to know the money on 47 of 48 rows is
 *     worse than one that says which rows it could not price.
 *
 *   REVERSIBILITY — derived from the item's KIND against the table below. An
 *     order is irreversible once filled; a code fix is revertible. The table is
 *     small, explicit and rendered on the page as a word beside each row, so a
 *     reader can disagree with the classification instead of absorbing it.
 *     An unrecognised kind is `unclassified` and ranks with the URGENT half,
 *     never the safe half — the fail-closed direction.
 *
 *   STALENESS — an order's own `ts`; for a recommendation, the `resolved_at` of
 *     the run that produced it (recommendations carry no timestamp of their
 *     own — verified on the live payload, whose keys are exactly
 *     artifact_path / kind / rec_id / run_id / seat / status / task / text /
 *     trace_id). Null when the run has none.
 */

import type { DeskView, PendingOrder } from "@/lib/fund_api";
import type { DeskRun } from "./seatLib";

/* --------------------------------------------------------- reversibility -- */

export type Reversibility = "irreversible" | "hard" | "reversible" | "unclassified";

/**
 * How hard is this to undo, by kind.
 *
 * `hard` means "undoable only by another versioned decision" — a retirement, an
 * exit rule, a risk-envelope change. Those do not move money the instant they
 * are clicked, but they change what the machine will do without asking again,
 * which is the CEO's scarcest thing to get back.
 */
const REVERSIBILITY_BY_KIND: Readonly<Record<string, Reversibility>> = Object.freeze({
  // Changes the fund's standing behaviour or closes a position.
  retire: "hard",
  close: "hard",
  exit_rule: "hard",
  exits: "hard",
  risk: "hard",
  register: "hard",
  envelope: "hard",
  envelope_v2: "hard",
  // Code and instruments: revertible by a commit.
  fix: "reversible",
  harness: "reversible",
  infra: "reversible",
  code_fix: "reversible",
  measurement: "reversible",
  measure: "reversible",
  // Bookkeeping, routing and process — nothing moves.
  record: "reversible",
  menu_status: "reversible",
  process: "reversible",
  review: "reversible",
  defer: "reversible",
  batch: "reversible",
  block: "reversible",
  decision: "reversible",
  dispatch: "reversible",
  dispatch_request: "reversible",
  next_dispatch: "reversible",
});

export function reversibilityOfKind(kind?: string | null): Reversibility {
  if (!kind) return "unclassified";
  return REVERSIBILITY_BY_KIND[kind] ?? "unclassified";
}

/** Sort weight: lower sorts first. Unclassified sits with the urgent half. */
const REVERSIBILITY_RANK: Record<Reversibility, number> = {
  irreversible: 0,
  hard: 1,
  unclassified: 2,
  reversible: 3,
};

/* ---------------------------------------------------------------- items --- */

export type DeskItemKind = "order" | "recommendation";

export interface DeskItem {
  /** Stable render key. */
  key: string;
  kind: DeskItemKind;
  /** Dollars at stake. `null` = the payload does not state it. NEVER 0. */
  moneyUsd: number | null;
  reversibility: Reversibility;
  /** When this started waiting on the CEO. Null when nothing dates it. */
  waitingSince: string | null;
  /** The raw item, for rendering. Exactly one of these is set. */
  order?: PendingOrder;
  rec?: DeskView["open_recommendations"][number];
}

/** Pending orders as ranked items. Money comes from the impact preview the
 *  spine computed — never from the quantity times a price this page guessed. */
export function orderItems(pending: PendingOrder[]): DeskItem[] {
  return pending.map((o) => ({
    key: `order:${o.order_id}`,
    kind: "order" as const,
    moneyUsd: o.impact_preview?.notional_usd ?? null,
    // A fill cannot be un-filled. This is the only `irreversible` in the fund.
    reversibility: "irreversible" as const,
    waitingSince: o.ts ?? null,
    order: o,
  }));
}

/**
 * Open recommendations as ranked items.
 *
 * `runs` supplies the staleness anchor. A recommendation whose run is not in
 * the list gets `waitingSince: null` and sorts as undated rather than as new —
 * an undated item floating to the top of a freshness sort is how the oldest
 * thing on the desk becomes invisible.
 */
export function recItems(
  recs: DeskView["open_recommendations"],
  runs: DeskRun[],
): DeskItem[] {
  const resolvedAt = new Map<string, string | null>();
  for (const r of runs) resolvedAt.set(r.run_id, r.resolved_at ?? null);
  return recs.map((r) => ({
    key: `rec:${r.run_id}:${r.rec_id}`,
    kind: "recommendation" as const,
    // `money_at_stake` when the seat stated one (spine, 2026-08-20). Absent
    // stays null — the field being optional is the whole point, and coercing
    // an unstated figure to 0 would rank the fund's largest unpriced decision
    // below its smallest priced one.
    moneyUsd: typeof r.money_at_stake === "number" && Number.isFinite(r.money_at_stake)
      ? r.money_at_stake
      : null,
    reversibility: reversibilityOfKind(r.kind),
    waitingSince: resolvedAt.get(r.run_id) ?? null,
    rec: r,
  }));
}

/* ---------------------------------------------------------------- stages -- */

/**
 * Where an item sits relative to the CEO's click.
 *
 * `awaiting_decision` — nobody has decided. This is the CEO's actual queue.
 * `awaiting_execution` — the CEO decided; it is now the CTO's to stage or the
 *   machine's to run. It still belongs ON the desk (a decision that never
 *   executes is a decision that did not happen) but it is NOT a thing to do.
 *
 * The headline counted both, so a desk where the CEO had decided everything and
 * the CTO had staged nothing read as "20 awaiting your decision" — the same
 * number as a desk where nothing had been decided at all (CDO D4).
 */
export type DeskStage = "awaiting_decision" | "awaiting_execution";

export function stageOfItem(i: DeskItem): DeskStage {
  // An order pending approval is the CEO's decision by definition.
  if (i.kind === "order") return "awaiting_decision";
  const status = i.rec?.status;
  // `accepted` = the CEO said yes and the CTO has not staged it.
  // `staged` = staged through the propose path, waiting on the approve click,
  //            which is a click on the ORDER that staging created — the
  //            recommendation itself is decided.
  return status === "accepted" || status === "staged"
    ? "awaiting_execution"
    : "awaiting_decision";
}

export interface DeskSplit {
  awaitingDecision: DeskItem[];
  awaitingExecution: DeskItem[];
}

/** Split a ranked list into the two queues, preserving rank within each. */
export function splitDeskItems(items: DeskItem[]): DeskSplit {
  const awaitingDecision: DeskItem[] = [];
  const awaitingExecution: DeskItem[] = [];
  for (const i of items) {
    (stageOfItem(i) === "awaiting_execution" ? awaitingExecution : awaitingDecision).push(i);
  }
  return { awaitingDecision, awaitingExecution };
}

/* --------------------------------------------------------------- ranking -- */

/**
 * money → reversibility → staleness, then key for stability.
 *
 * Nulls sort LAST within their key rather than first: an unpriced item is not a
 * $0 item, and a $0 item is not urgent. Undated sorts last for the same reason.
 */
export function compareDeskItems(a: DeskItem, b: DeskItem): number {
  // 1 — money, largest first; unpriced last.
  if (a.moneyUsd != null || b.moneyUsd != null) {
    if (a.moneyUsd == null) return 1;
    if (b.moneyUsd == null) return -1;
    if (a.moneyUsd !== b.moneyUsd) return b.moneyUsd - a.moneyUsd;
  }
  // 2 — reversibility, hardest to undo first.
  const ra = REVERSIBILITY_RANK[a.reversibility];
  const rb = REVERSIBILITY_RANK[b.reversibility];
  if (ra !== rb) return ra - rb;
  // 3 — staleness, oldest first; undated last.
  if (a.waitingSince !== b.waitingSince) {
    if (!a.waitingSince) return 1;
    if (!b.waitingSince) return -1;
    return a.waitingSince.localeCompare(b.waitingSince);
  }
  return a.key.localeCompare(b.key);
}

export function rankDeskItems(items: DeskItem[]): DeskItem[] {
  return [...items].sort(compareDeskItems);
}

/** How much of this ranking was made without a money key. Rendered verbatim. */
export function moneyGap(items: DeskItem[]): { priced: number; unpriced: number } {
  let priced = 0;
  let unpriced = 0;
  for (const i of items) (i.moneyUsd == null ? unpriced++ : priced++);
  return { priced, unpriced };
}

/* ------------------------------------------------------------ COO memos --- */

export interface CooMemo {
  runId: string;
  at: string | null;
  /** The run's task, as filed. */
  task: string;
  /** First sentence of the verdict — the line the CEO takes standing up. */
  headline: string;
  /** Everything after it. "" when the verdict was one sentence. */
  rest: string;
  /** The filed document, or null when the run filed nothing. */
  artifactPath: string | null;
  /** Recommendations this memo carries, and how many still await a decision. */
  recCount: number;
  openRecCount: number;
}

/**
 * The COO's batch memos, newest first — the intended top of the CEO desk.
 *
 * Built from the coo seat's RUNS, because a triage memo IS a run: its verdict
 * is the batch summary and its recommendations are the batches. The headline is
 * split with the same `memoParts` rule the approval cards use, so the sentence
 * the CEO reads here is character-for-character the one they read there.
 *
 * A run whose verdict is empty gets an empty headline and the page says the
 * memo filed no verdict — it does NOT fall back to the task, which would pass a
 * dispatch instruction off as the COO's conclusion.
 */
export function cooMemos(
  runs: DeskRun[],
  split: (s?: string | null) => { headline: string; rest: string },
): CooMemo[] {
  return runs
    .filter((r) => r.seat === "coo")
    .map((r) => {
      const parts = split(r.verdict);
      const recs = r.recommendations ?? [];
      return {
        runId: r.run_id,
        at: r.resolved_at ?? r.dispatched_at ?? null,
        task: r.task,
        headline: parts.headline,
        rest: parts.rest,
        artifactPath: r.artifact_path ?? null,
        recCount: recs.length,
        openRecCount: recs.filter((x) => x.status === "open").length,
      };
    })
    .sort((a, b) => {
      // Newest first; undated last rather than first, where a missing
      // timestamp would read as "just filed".
      if (!a.at && !b.at) return 0;
      if (!a.at) return 1;
      if (!b.at) return -1;
      return b.at.localeCompare(a.at);
    });
}

/* ------------------------------------------------- the CTO's ask queue ---- */

/** Where a queued ask sits on the seat files → CEO approves → CTO triggers path. */
export type AskStage = "awaiting_ceo" | "cleared_to_trigger" | "resolved";

export interface QueuedAsk {
  requestId: string;
  /** Who filed it. A SEAT here is the constitution's 2026-08-20 amendment made
   *  visible — "mechanism requests validator" is hierarchy in the data. */
  actor: string;
  /** True when the filer is a bench seat rather than a human. */
  seatFiled: boolean;
  serves: string;
  subject: string;
  note: string | null;
  at: string | null;
  stage: AskStage;
  approvedBy: string | null;
  approvedAt: string | null;
}

/**
 * The bench seats, as the CTO desk's queue distinguishes them from humans.
 *
 * Deliberately a copy of the route whitelist in seatLib rather than an import
 * of the roster: this decides only whether to call a filer "seat-filed", and it
 * must not change shape if `GET /fund/desk` starts returning a new roster row
 * before the UI knows what that seat is.
 */
const BENCH = new Set([
  "mechanism", "analyst", "pm", "quant", "adversary",
  "validator", "riskofficer", "builder", "coo",
]);

export function isSeatFiled(actor?: string | null): boolean {
  return BENCH.has((actor || "").trim().toLowerCase());
}

/**
 * The CTO's dispatch queue: unresolved asks, seat-filed ones identified,
 * CEO-approved ones leading because they are cleared to fire.
 *
 * Approval state comes from the spine's own fold (app/fund/desk.py `_requests`:
 * DESK_REQUEST_APPROVED moves an OPEN request to `approved` and stamps
 * `approved_by` / `approved_at`). Verified on the live payload 2026-08-20:
 * request 5fc56190 — actor "mechanism", serves "validator", status "open" —
 * is the first seat-filed ask the fund has produced, and renders as
 * "awaiting CEO approval" because NO DeskRequestApproved event exists yet.
 */
export function queuedAsks(requests: DeskView["requests"]): QueuedAsk[] {
  return requests
    .filter((r) => r.status !== "resolved")
    .map((r) => {
      const actor = (r.actor || "").trim();
      return {
        requestId: r.request_id,
        actor,
        seatFiled: isSeatFiled(actor),
        serves: r.serves,
        subject: r.subject,
        note: r.note ?? null,
        at: r.at ?? null,
        stage: (r.status === "approved" ? "cleared_to_trigger" : "awaiting_ceo") as AskStage,
        approvedBy: r.approved_by ?? null,
        approvedAt: r.approved_at ?? null,
      };
    })
    .sort((a, b) => {
      // Cleared asks lead — they are the only ones the CTO may act on.
      if (a.stage !== b.stage) return a.stage === "cleared_to_trigger" ? -1 : 1;
      // Then oldest first: an ask that has waited longest is the one at risk of
      // being forgotten. Undated last.
      if (!a.at && !b.at) return 0;
      if (!a.at) return 1;
      if (!b.at) return -1;
      return a.at.localeCompare(b.at);
    });
}

/* -------------------------------------------------------- decision pace --- */

export interface DecisionVelocity {
  /** null = the event log could not be read. Zero decisions is a real 0. */
  today: number | null;
  week: number | null;
  /** The oldest event the window could see, so "0 this week" can be read
   *  against how far back the page can actually see. */
  oldestSeen: string | null;
}

const DECISION_TYPES = new Set(["DeskRecommendationDecided", "DeskRequestApproved"]);

/**
 * The CEO's own productivity strip, from the decision events.
 *
 * `null` when the events could not be read — the strip then says so instead of
 * reporting a very productive zero.
 */
export function decisionVelocity(
  events: { type: string; ts: string }[] | null,
  now: Date,
): DecisionVelocity {
  if (events === null) return { today: null, week: null, oldestSeen: null };
  const dayKey = now.toISOString().slice(0, 10);
  const weekAgo = now.getTime() - 7 * 86_400_000;
  let today = 0;
  let week = 0;
  let oldest: string | null = null;
  for (const e of events) {
    if (!oldest || (e.ts && e.ts < oldest)) oldest = e.ts;
    if (!DECISION_TYPES.has(e.type)) continue;
    if (e.ts?.slice(0, 10) === dayKey) today += 1;
    const t = Date.parse(e.ts);
    if (!Number.isNaN(t) && t >= weekAgo) week += 1;
  }
  return { today, week, oldestSeen: oldest };
}
