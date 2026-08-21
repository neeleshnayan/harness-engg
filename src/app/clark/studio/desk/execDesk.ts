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
  // The secretary's two kinds (seat definition, 2026-08-21). A `suggestion` is
  // "a concrete, doable thing" like adopting a filename convention — undoable
  // by doing the opposite. Classified because the alternative was visible on
  // the CEO's page: an unclassified suggestion rendered the sentence
  // 'kind "suggestion" is unclassified — ranked as if hard to undo', which is
  // both noise and a mis-rank. `note` is here for completeness; a note is never
  // ranked, because it is never a decision.
  suggestion: "reversible",
  note: "reversible",
});

export function reversibilityOfKind(kind?: string | null): Reversibility {
  if (!kind) return "unclassified";
  return REVERSIBILITY_BY_KIND[kind] ?? "unclassified";
}

/**
 * How hard to undo, STATED by the seat if it said, inferred from kind if not.
 *
 * The inference is thin exactly where the CEO reads most: `awaits-ceo`, `batch`
 * and `challenge` are routing words that say nothing about the act, so the
 * amber "unclassified kind" sentence fired on almost every row of his own
 * queue — honest, and noise, and noise on every row is how a warning stops
 * being read. A seat knows whether its own recommendation can be taken back.
 *
 * The stated value WINS over the table rather than being a fallback for it: a
 * declaration by whoever knows beats a lookup on a word they happened to pick.
 * Nothing writes it yet, and the page prints how many rows went unclassified
 * rather than implying the table covered them.
 */
export function reversibilityOf(
  stated?: string | null, kind?: string | null,
): Reversibility {
  const v = (stated ?? "").trim().toLowerCase();
  if (v === "irreversible" || v === "hard" || v === "reversible") return v;
  return reversibilityOfKind(kind);
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
  /** A DATED COMMITMENT (YYYY-MM-DD), not an arrival time — the day something
   *  happens whether or not anybody clicks. The top ranking key.
   *
   *  Null on every row today, and that is the honest state rather than an
   *  oversight: the fund's one live example (a 2026-09-08 auto-close) states
   *  its date in PROSE, and reading a deadline out of English is the same
   *  class of mistake as the "EXECUTED" text-grep this desk is being repaired
   *  from. The field is here, the ranking key is wired, and `rankCoverage()`
   *  prints the zero until a seat fills it in. */
  dueDate: string | null;
  /** Whose move it is, as the SPINE resolved it — never re-derived here. Two
   *  implementations of one predicate is how this page came to show 11 and 6
   *  for the same thing eight pixels apart. Undefined from a spine that
   *  predates the annotation, which falls the surface back to the old
   *  status rule. */
  nextActor?: string | null;
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
    // A pending order has no deadline of its own — it waits until it is
    // approved or it goes stale. Null, not "today".
    dueDate: null,
    // An order pending approval is the CEO's click by definition; there is no
    // other actor it could be waiting on.
    nextActor: "ceo",
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
/** Statuses that are FINISHED. A terminal row is not desk work — it is record.
 *  `noted` joined them 2026-08-21 (CEO): read, closed, and deliberately never
 *  decided. The spine's `open_recommendations` already excludes all three; this
 *  is the second lock, so a widened feed cannot put a closed item back in front
 *  of the CEO as though a click were owed on it. */
const TERMINAL_REC_STATUSES = new Set(["rejected", "done", "noted"]);

export function recItems(
  recs: DeskView["open_recommendations"],
  runs: DeskRun[],
): DeskItem[] {
  const resolvedAt = new Map<string, string | null>();
  for (const r of runs) resolvedAt.set(r.run_id, r.resolved_at ?? null);
  return recs.filter((r) => !TERMINAL_REC_STATUSES.has(String(r.status))).map((r) => ({
    key: `rec:${r.run_id}:${r.rec_id}`,
    kind: "recommendation" as const,
    // `money_at_stake` when the seat stated one (spine, 2026-08-20). Absent
    // stays null — the field being optional is the whole point, and coercing
    // an unstated figure to 0 would rank the fund's largest unpriced decision
    // below its smallest priced one.
    moneyUsd: typeof r.money_at_stake === "number" && Number.isFinite(r.money_at_stake)
      ? r.money_at_stake
      : null,
    reversibility: reversibilityOf(r.reversibility, r.kind),
    waitingSince: resolvedAt.get(r.run_id) ?? null,
    // Never parsed out of `text`. See DeskItem.dueDate.
    dueDate: typeof r.due_date === "string" && r.due_date.trim()
      ? r.due_date.trim()
      : null,
    nextActor: r.next_actor_resolved ?? null,
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
export type DeskStage =
  | "awaiting_decision"
  | "awaiting_execution"
  | "owned_elsewhere";

/**
 * THREE stages since 2026-08-22, and the third one exists because the CEO said
 * *"they sustain on my queue even if that work has been done"*.
 *
 * `owned_elsewhere` is an OPEN row that is not the CEO's to decide — an
 * engineering ticket, a seat-to-seat handoff. Nobody has decided it, so calling
 * it `awaiting_execution` would say the firm made a promise it did not make;
 * leaving it in `awaiting_decision` is what put chair work on the CEO's number.
 * It gets its own stage, is shown, and is not counted.
 *
 * The routing is the SPINE'S, read off `next_actor_resolved`. It is not
 * re-derived here: this page and the spine's counter each had their own rule
 * and rendered 11 and 6 for the same payload, eight pixels apart. A spine that
 * predates the annotation sends no field, and the old status rule is the
 * fallback — degrading to the previous behaviour, never to a guess.
 */
export function stageOfItem(i: DeskItem): DeskStage {
  // An order pending approval is the CEO's decision by definition.
  if (i.kind === "order") return "awaiting_decision";
  const status = i.rec?.status;
  // `accepted` = the CEO said yes and the CTO has not staged it.
  // `staged` = staged through the propose path, waiting on the approve click,
  //            which is a click on the ORDER that staging created — the
  //            recommendation itself is decided.
  const decided = status === "accepted" || status === "staged";
  if (decided) return "awaiting_execution";
  const actor = i.nextActor;
  // `unknown` stays with the CEO on purpose: a row whose owner could not be
  // read is work he may still owe, and routing it away would answer an
  // unmeasurable with a zero.
  if (actor === "chair" || actor === "seat" || actor === "nobody") {
    return "owned_elsewhere";
  }
  return "awaiting_decision";
}

export interface DeskSplit {
  awaitingDecision: DeskItem[];
  awaitingExecution: DeskItem[];
  /** Open, real, and somebody else's. Shown, never counted. */
  ownedElsewhere: DeskItem[];
}

/** Split a ranked list into the three queues, preserving rank within each. */
export function splitDeskItems(items: DeskItem[]): DeskSplit {
  const awaitingDecision: DeskItem[] = [];
  const awaitingExecution: DeskItem[] = [];
  const ownedElsewhere: DeskItem[] = [];
  for (const i of items) {
    const stage = stageOfItem(i);
    if (stage === "awaiting_execution") awaitingExecution.push(i);
    else if (stage === "owned_elsewhere") ownedElsewhere.push(i);
    else awaitingDecision.push(i);
  }
  return { awaitingDecision, awaitingExecution, ownedElsewhere };
}

/* --------------------------------------------------------------- ranking -- */

/**
 * deadline → reversibility → money → staleness, then key for stability.
 *
 * REORDERED 2026-08-22, on the CEO's complaint that his desk is "out of order
 * ... Making my flow messy", and on the COO's stated rule, which the chair
 * adopted as house rule and which this now implements literally:
 *
 *   *"A versioned envelope change can be reversed in an afternoon; an
 *   unintended short position at a real venue cannot."*
 *
 * The previous order was money FIRST, which is why a $750 armed short sat level
 * with any other four-figure row and a doc-indexing chore with no figure sank
 * below both. Money is a good second key and a bad first one: it ranks by how
 * much is moving, not by how much of it you can get back.
 *
 * THE FOUR KEYS, in order, and what each is for:
 *
 *   1. DEADLINE — a dated commitment outranks everything, earliest first. The
 *      fund has exactly one live example (a 2026-09-08 auto-close) and the date
 *      is in its PROSE, which is where it has to stop being: `due_date` is a
 *      field now, nothing writes it yet, and `rankCoverage()` reports the zero
 *      out loud. Scraping a date out of English would be the same class of
 *      mistake as the "EXECUTED" grep this desk is being repaired from.
 *   2. REVERSIBILITY — how much of this you can get back. Unclassified ranks
 *      with the urgent half, which is the fail-closed direction.
 *   3. MONEY — larger first, WITHIN the band. `0` is a real measurement and is
 *      not "unimportant": it means nothing moves, and it still sits above every
 *      reversible row in the fund because its band put it there. Unpriced sorts
 *      last within its band and the row SAYS it is unpriced, rather than
 *      looking like a small one.
 *   4. STALENESS — oldest first; undated last.
 *
 * Every one of these is visible: `rankReason()` renders the sentence beside the
 * row. A ranking a reader cannot argue with is a ranking a reader cannot check.
 */
export function compareDeskItems(a: DeskItem, b: DeskItem): number {
  // 1 — a dated commitment first, soonest due at the top. Undated is not
  // "later", it is unknown, and it sorts after everything dated.
  if (a.dueDate !== b.dueDate) {
    if (!a.dueDate) return 1;
    if (!b.dueDate) return -1;
    return a.dueDate.localeCompare(b.dueDate);
  }
  // 2 — reversibility, hardest to undo first.
  const ra = REVERSIBILITY_RANK[a.reversibility];
  const rb = REVERSIBILITY_RANK[b.reversibility];
  if (ra !== rb) return ra - rb;
  // 3 — money, largest first; unpriced last WITHIN the band it already earned.
  if (a.moneyUsd != null || b.moneyUsd != null) {
    if (a.moneyUsd == null) return 1;
    if (b.moneyUsd == null) return -1;
    if (a.moneyUsd !== b.moneyUsd) return b.moneyUsd - a.moneyUsd;
  }
  // 4 — staleness, oldest first; undated last.
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

/** Why a band leads, in the words a reader can disagree with. */
const REVERSIBILITY_REASON: Record<Reversibility, string> = {
  irreversible: "cannot be undone once it fills",
  hard: "changes what the machine does without asking again",
  unclassified: "unclassified kind — ranked as if hard to undo",
  reversible: "revertible by a commit or the opposite click",
};

/**
 * The sentence that explains this row's position, in plain words.
 *
 * The CEO's instruction on the ranking was explicit: *do not invent a scoring
 * formula and bury it* — a human should be able to look at two rows and say why
 * one is above the other. So there is no score. There are four named keys, and
 * this returns the ones that actually separated this row, in the order they
 * were applied.
 *
 * Absences are stated, never smoothed: an unpriced row says it is unpriced
 * rather than reading as a cheap one, and a $0 row says nothing moves rather
 * than reading as unimportant.
 */
export function rankReason(i: DeskItem): string {
  const parts: string[] = [];
  if (i.dueDate) parts.push(`due ${i.dueDate}`);
  parts.push(REVERSIBILITY_REASON[i.reversibility]);
  if (i.moneyUsd == null) {
    parts.push("no dollar figure stated — ordered by age within its band, not priced as small");
  } else if (i.moneyUsd === 0) {
    parts.push("$0 moves — ranked on reversibility, not on size");
  } else {
    parts.push(`$${i.moneyUsd.toLocaleString("en-US", { maximumFractionDigits: 2 })} at stake`);
  }
  parts.push(i.waitingSince ? `waiting since ${i.waitingSince.slice(0, 10)}` : "undated");
  return parts.join(" · ");
}

/**
 * What the ranking could and could not see, as counts.
 *
 * Printed on the page beside the list. A ranking that silently pretends to know
 * the money on 47 of 48 rows is worse than one that says which rows it could
 * not price — and the same is now true of the deadline key, which is wired and
 * fed by nothing.
 */
export function rankCoverage(items: DeskItem[]): {
  total: number; priced: number; unpriced: number; zero: number;
  dated: number; undated: number; unclassified: number;
} {
  let priced = 0, unpriced = 0, zero = 0, dated = 0, undated = 0, unclassified = 0;
  for (const i of items) {
    if (i.moneyUsd == null) unpriced++;
    else { priced++; if (i.moneyUsd === 0) zero++; }
    if (i.dueDate) dated++; else undated++;
    if (i.reversibility === "unclassified") unclassified++;
  }
  return { total: items.length, priced, unpriced, zero, dated, undated, unclassified };
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

/** Where a queued ask sits on the seat files → CEO approves → CTO triggers path.
 *
 *  `declined` added 2026-08-21 with the spine's fourth state. It is TERMINAL:
 *  a resolve cannot overwrite it, because executing a declined ask would be the
 *  CTO overriding the CEO's no. Folding it in with `resolved` would erase the
 *  difference between "done" and "refused". */
export type AskStage =
  | "awaiting_ceo" | "cleared_to_trigger" | "resolved" | "declined";

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
  declinedBy: string | null;
  declinedAt: string | null;
  /** The rejection's MANDATORY written reason — the spine refuses one without. */
  declineReason: string | null;
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
        // The spine normalizes seat vocabulary onto task/seat; the older
        // subject/serves spelling is still on historical events. Read the
        // normalized field first and fall back — an unnormalized ask rendered
        // as a BLANK ROW while desk_load counted it, which is how two items sat
        // invisible on a visually clear desk (2026-08-21).
        serves: r.seat ?? r.serves,
        subject: r.task ?? r.subject,
        note: r.note ?? null,
        at: r.at ?? null,
        stage: (r.status === "declined" ? "declined"
          : r.status === "approved" ? "cleared_to_trigger"
            : "awaiting_ceo") as AskStage,
        approvedBy: r.approved_by ?? null,
        approvedAt: r.approved_at ?? null,
        declinedBy: r.declined_by ?? null,
        declinedAt: r.declined_at ?? null,
        declineReason: r.decline_reason ?? null,
      };
    })
    .sort((a, b) => {
      // Declined asks sink: they are terminal and need no action from anyone.
      if ((a.stage === "declined") !== (b.stage === "declined")) {
        return a.stage === "declined" ? 1 : -1;
      }
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

/**
 * The same asks, ordered for the CEO instead of for the CTO.
 *
 * `queuedAsks` leads with CLEARED asks because on the CTO console those are the
 * only ones the CTO may act on. On the CEO's desk that ordering is exactly
 * backwards, and it showed: the first render buried the single ask AWAITING THE
 * CEO beneath three already-approved ones, on a page whose entire subtitle is
 * "everything awaiting your click".
 *
 * A separate function rather than a flag, and here rather than inline in JSX,
 * for the reason the CEO page's own docstring gives about ranking: an order
 * derived inside a component cannot be checked, and a queue that silently
 * mis-ranks is worse than an unranked one because the reader trusts its top.
 */
export function asksForCeo(asks: QueuedAsk[]): QueuedAsk[] {
  const rank = (s: AskStage) =>
    s === "awaiting_ceo" ? 0 : s === "cleared_to_trigger" ? 1 : 2;
  return [...asks].sort((a, b) => {
    const d = rank(a.stage) - rank(b.stage);
    if (d !== 0) return d;
    // Within a stage, oldest first — the one at risk of being forgotten.
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

/* ----------------------------------------------- the secretary's memo ----- */

/**
 * How old the memo on the CEO's desk is, in plain words.
 *
 * The CEO asked for "her memo for today from her yesterdays EoD" (request
 * 920ecbe5). A memo with no visible age reads as this morning's, and the
 * secretary runs at END OF DAY — so the memo on the desk is normally
 * yesterday's, and that has to be legible rather than inferred.
 *
 * Days are compared as UTC calendar days, because the log is UTC and the memo
 * is named for a UTC day; comparing against a local midnight would call the
 * same file "today" in one timezone and "yesterday" in another.
 *
 * An undated or unparseable memo returns `null` — NOT "today". A guess here
 * would be the exact error the date was added to prevent.
 */
export function memoDayLabel(
  date: string | null | undefined,
  now: Date,
): string | null {
  if (!date || !/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  const then = Date.parse(`${date}T00:00:00Z`);
  if (Number.isNaN(then)) return null;
  const today = Date.parse(`${now.toISOString().slice(0, 10)}T00:00:00Z`);
  const days = Math.round((today - then) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "yesterday";
  // A memo from the FUTURE is a clock disagreement, not a memo. Saying so is
  // better than "-2 days ago", which reads like a rendering bug and hides one.
  if (days < 0) return `dated ${-days} day${days === -1 ? "" : "s"} ahead`;
  return `${days} days ago`;
}

/**
 * Un-hard-wrap a filed memo so it reads as prose on screen.
 *
 * Donna writes to an 80-column file. The renderer treats one source line as one
 * paragraph, so a hard-wrapped sentence arrived as five separately spaced lines
 * — legible, but it made a six-sentence memo look like a list of fragments
 * (seen on the CEO desk, 2026-08-21, before this).
 *
 * Deliberately NOT done inside the markdown renderer: that component renders
 * live model output on three other surfaces, and re-flowing text there is a
 * different decision with different risks. This re-flows only what the
 * secretary filed.
 *
 * The join is conservative — blank lines, headings, bullets, numbered items and
 * table rows all START a block and are never merged into what precedes them,
 * so nothing gets swallowed. Horizontal rules are dropped because the renderer
 * has no rule and would print `---` at the reader.
 */
export function unwrapMemoMarkdown(md: string | null | undefined): string {
  if (!md) return "";
  const starts = (l: string) =>
    !l.trim()
    || /^#{1,6}\s/.test(l)
    || /^\s*[-*•]\s+/.test(l)
    || /^\s*\d+[.)]\s+/.test(l)
    || /^\s*\|/.test(l)
    || /^\s*>/.test(l);
  const isRule = (l: string) => /^\s*([-*_])\s*\1\s*\1[\s\-*_]*$/.test(l);
  const out: string[] = [];
  for (const raw of md.replace(/\r\n/g, "\n").split("\n")) {
    const line = raw.trimEnd();
    if (isRule(line)) continue;
    const prev = out.length ? out[out.length - 1] : null;
    if (!starts(line) && prev !== null && prev.trim() && !/^#{1,6}\s/.test(prev)) {
      out[out.length - 1] = `${prev} ${line.trim()}`;
      continue;
    }
    out.push(line);
  }
  return out.join("\n");
}
