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
import { hoursBetween } from "./cardAnatomy.ts";

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
   *  READ FROM THE SPINE'S `due_date`, NEVER PARSED OUT OF `text`: reading a
   *  deadline out of English is the same class of mistake as the "EXECUTED"
   *  text-grep this desk was repaired from.
   *
   *  This comment previously said "null on every row today". It is no longer
   *  true and had gone stale silently — measured against the live payload
   *  2026-08-27, 12 of 39 decision rows carry a date, the earliest three
   *  already past. `rankCoverage()` prints the live count either way, which
   *  is why the number belongs there and not in this sentence. */
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
 * THE STALENESS ANCHOR IS THE ROW'S OWN `resolved_at`, AND IT USED TO BE A
 * LOOKUP IN A CAPPED LIST. `runs` is the desk payload's 25-run window; a
 * recommendation whose run fell outside it got `waitingSince: null`.
 *
 * MEASURED 2026-08-27 against the live desk: 324 open recommendations, 25
 * runs in the payload. The map could date **66**; the rows carry the field
 * themselves and can date **324**. On the CEO's own decision list the map
 * dated **7 of 39** — so thirty-two rows he is asked to rank by urgency had
 * no readable waiting time, and every card's age encoding read UNKNOWN.
 *
 * The two AGREE where both exist — 66 of 66, zero disagreements, and zero
 * rows the map could date that the row could not. So this is a wider read of
 * ONE fact, not a switch to a second one, and the check is the only thing
 * that makes that sentence safe to write. The map stays as a fallback for a
 * spine that predates the row annotation.
 *
 * The original comment's argument is the argument FOR this: *"an undated item
 * floating to the top of a freshness sort is how the oldest thing on the desk
 * becomes invisible."* Exactly so — and it was undated because of a cap on a
 * neighbouring payload, not because the fund did not know.
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
    waitingSince: (typeof r.resolved_at === "string" && r.resolved_at.trim())
      ? r.resolved_at
      : (resolvedAt.get(r.run_id) ?? null),
    // Never parsed out of `text`. See DeskItem.dueDate.
    dueDate: typeof r.due_date === "string" && r.due_date.trim()
      ? r.due_date.trim()
      : null,
    nextActor: r.next_actor_resolved ?? null,
    rec: r,
  }));
}

/* ----------------------------------------------- the shared contract ------ */

/**
 * The desk-stage contract this build's expectations were generated against.
 *
 * `contract/desk_stage_contract.v1.json` is produced BY `app/fund/desk.py` in
 * ClarkHarness and checked in to both repos, byte-identical. Each repo's suite
 * pins its own copy, which catches an edit on either side and does NOT catch
 * ClarkHarness being regenerated while this copy stays stale — there is no
 * shared build for a hermetic test to live in.
 *
 * So the spine publishes `desk_load.contract_digest` and the page compares. It
 * is the one place a silent drift between the counter and this page could
 * still hide, and a silent drift between the counter and this page is the
 * entire 11-vs-6 defect, which has now shipped twice.
 *
 * Changing this means regenerating in ClarkHarness, copying the file here, and
 * updating this literal AND `PINNED_DIGEST` in `deskStageContract.test.ts`.
 * Three deliberate acts, on purpose.
 */
export const CONTRACT_DIGEST =
  "c02655184d8eb8ea58bc6cc27203a6816cba01dc3acd1a63bc0feb7ceeb00500";

/** What the live spine's contract digest says about this page's fixture.
 *  `null` = they agree and nothing is rendered. */
export type ContractDrift = "drifted" | "unverified" | null;

/**
 * Compare the live spine's contract digest against this build's.
 *
 * THREE OUTCOMES, THREE RENDERINGS, and two of them are absences:
 *
 *   `null`         — the spine and this page were built against the same
 *                    contract. Silent; a control that shouts when it is happy
 *                    stops being read.
 *   `"unverified"` — the spine sent no digest (it predates the field) or sent
 *                    `null` (it could not read or could not verify its own
 *                    contract file). This is NOT agreement, and must never
 *                    render as agreement. Absence is never zero and it is
 *                    never "fine" either.
 *   `"drifted"`    — a real disagreement. The counter and this page are
 *                    running different rules, and the numbers on this screen
 *                    may not mean what they say.
 */
export function contractDrift(
  liveDigest?: string | null,
): ContractDrift {
  if (typeof liveDigest !== "string" || !liveDigest) return "unverified";
  return liveDigest === CONTRACT_DIGEST ? null : "drifted";
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
 *
 * THE ACTOR IS CONSULTED **BEFORE** THE STATUS, and that ordering is the whole
 * repair (killed by the adversary 2026-08-22, on the first cut of this
 * function). The first version returned `awaiting_execution` for any
 * accepted/staged row and only then looked at `nextActor` — so an ACCEPTED row
 * carrying `next_actor: "ceo"` fell out before the field was ever read. That
 * row is not a hypothetical: it is the COO's preserved objection in the
 * constitution, verbatim — *"items at status `accepted` whose execution
 * requires the CEO personally (three live today, including PM R1, the
 * largest-money decision in the firm)"* — and it is the exact case the spine's
 * explicit `next_actor` field exists to express, ranked ABOVE the lifecycle in
 * `desk.py::next_actor`'s own precedence list. Under the old ordering the
 * spine counted such a row as CEO load and this page filed it under "shown,
 * never counted": server 1, page 0, on the same line of `ceo/page.tsx`. That
 * is the 11-vs-6 divergence reintroduced by the field introducing it.
 *
 * The precedence below MIRRORS `desk.py::next_actor` because it consumes that
 * function's answer rather than recomputing it — terminal rows never reach
 * here (`recItems` drops them), the actor decides, and status is used for one
 * thing only: telling a decided row that is not the CEO's ("you said yes,
 * the chair owes you the execution") from an open one that is not his
 * ("nobody has decided this and it was never yours"). Those are different
 * facts and the desk has already paid for confusing them once.
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
  const actor = i.nextActor;
  // 1 — THE SPINE'S ANSWER, whatever the lifecycle says. `unknown` stays with
  // the CEO on purpose: a row whose owner could not be read is work he may
  // still owe, and routing it away would answer an unmeasurable with a zero.
  // `desk_load` counts `ceo` and `unknown` toward his figure and nothing else;
  // this line is the client half of that same partition.
  if (actor === "ceo" || actor === "unknown") return "awaiting_decision";
  if (actor === "chair" || actor === "seat" || actor === "nobody") {
    // Somebody else's — but WHOSE somebody-else depends on whether a decision
    // was made. A decided row is a promise the firm owes back to the CEO; an
    // open one was never his.
    return decided ? "awaiting_execution" : "owned_elsewhere";
  }
  // 2 — no routing on the row at all (a spine predating the annotation, which
  // sends null, or a caller that built the item by hand, which leaves it
  // undefined). The OLD status rule, unchanged: degrade to the previous
  // behaviour, never to a guess.
  return decided ? "awaiting_execution" : "awaiting_decision";
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
 * What this sentence says when it cannot date the WAIT.
 *
 * IT USED TO SAY "undated", AND ON A DATED CARD THAT IS A LIE — caught by
 * looking at the rendered desk: the first card carried a `due 2026-08-24` chip
 * and a line ending "· undated" two inches below it. "undated" is this
 * codebase's word for a missing DATE (a memo's, a run's, an ask's — twenty
 * other uses, all of them about a timestamp), and here it meant something
 * else entirely: the producing run is outside the payload's window, so how
 * long the row has been waiting cannot be computed. `OrderCard` already had
 * the right idiom for exactly that fact, so this borrows it rather than
 * inventing a third phrasing.
 */
const UNDATED_WAIT = "age unknown";

export interface RankReasonOmit {
  /** The caller renders the date itself (the due chip). */
  due?: boolean;
  /** The caller renders the wait itself (the lifecycle rail's age). */
  waiting?: boolean;
}

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
 *
 * `omit` EXISTS BECAUSE A FACT RENDERED TWICE ON ONE CARD IS CLUTTER (D42,
 * found by looking at the rendered desk). The recommendation card printed
 * "due 2026-08-26" in its chip AND again as this sentence's first clause, and
 * after the lifecycle rail landed it printed "filed · 3.2h" above "waiting
 * since 2026-08-24" — the same timestamp twice, once as an age and once as a
 * date. Both defaults are FALSE, so every existing caller is unchanged; only
 * a caller that demonstrably renders the fact itself may drop it.
 */
export function rankReason(i: DeskItem, omit: RankReasonOmit = {}): string {
  const parts: string[] = [];
  if (i.dueDate && !omit.due) parts.push(`due ${i.dueDate}`);
  parts.push(REVERSIBILITY_REASON[i.reversibility]);
  if (i.moneyUsd == null) {
    parts.push("no dollar figure stated — ordered by age within its band, not priced as small");
  } else if (i.moneyUsd === 0) {
    parts.push("$0 moves — ranked on reversibility, not on size");
  } else {
    parts.push(`$${i.moneyUsd.toLocaleString("en-US", { maximumFractionDigits: 2 })} at stake`);
  }
  /* THE WAIT IS OMITTED ONLY WHEN A CALLER ALREADY SHOWS IT — never because it
     is inconvenient. `UNDATED_WAIT` still renders in that case: a caller's
     rail can say "how long has this sat here" from a timestamp, and it says
     nothing at all when there is no timestamp, which is exactly when this
     sentence must speak. Absence keeps a voice. */
  if (!omit.waiting) {
    parts.push(i.waitingSince
      ? `waiting since ${i.waitingSince.slice(0, 10)}` : UNDATED_WAIT);
  } else if (!i.waitingSince) {
    parts.push(UNDATED_WAIT);
  }
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
  /**
   * CAN THE CEO STILL ACT ON THIS? Deliberately NOT the same question as
   * `stage`, and separating the two is a repair rather than a refinement.
   *
   * The card used to render its Approve/Decline buttons on
   * `stage === "awaiting_ceo"`. When request routing v2 moved an open request
   * to the chair (2026-08-24), every ask left that stage — and the buttons
   * went with them, silently removing the CEO's ability to approve a desk
   * request from his own page. Caught by looking at the rendered page; no test
   * and no type could have seen it, because both halves were individually
   * correct.
   *
   * WHOSE MOVE IT IS decides counting and placement. WHETHER A CONTROL EXISTS
   * is a different question and answers to the row's own lifecycle: an ask
   * that is neither approved nor declined can still be approved or declined,
   * whatever the counter says about whose queue it sits on. Routing must never
   * take a control away.
   */
  approvable: boolean;
  /** THE REQUEST CARD (spec: docs/design/REQUEST_CARD_2026-08-24.md,
   *  CEO-ratified). Every field OPTIONAL and read from the spine; a request
   *  filed as prose — which all 109 rows filed before the schema were — has
   *  `structured: false` and renders through the old one-blob fallback.
   *  Forever: this is not a deprecation path. */
  card: AskCard;
}

export interface AskCard {
  structured: boolean;
  /** The card's NAME. For a prose ask this is the subject's first LINE,
   *  untouched — the renderer knows its own width and does the truncating. */
  headline: string | null;
  summary: string | null;
  /** The full narrative, behind the details toggle. Nothing is deleted; it is
   *  just not charged to a reader who did not ask for it. */
  incident: string | null;
  wanted: { text: string; state: "open" | "in_progress" | "done";
    note?: string | null }[];
  /** Whose move and WHAT ACT — both or neither. The old "CEO-APPROVED —
   *  TRIGGER IT" chip named an owner and left the obligation to be guessed,
   *  and it named the wrong owner. */
  nextMove: { actor: string; act: string } | null;
  lifecycle: AskLifecycle | null;
}

export interface AskLifecycle {
  stages: { stage: string; at: string | null; reached: boolean;
    current: boolean }[];
  current: string;
  /** Hours in the CURRENT stage. NULL when the stage carries no timestamp —
   *  never 0. Request 0c295ec7 was approved 22 minutes after filing and then
   *  sat 2.5 days; "awaiting dispatch · 0.0h" over that would be this fund's
   *  oldest mistake on its newest surface. */
  ageHours: number | null;
  declined: boolean;
}

/** The card fields as the spine sends them, or an empty prose card. */
function askCard(r: DeskView["requests"][number]): AskCard {
  const row = r as Record<string, unknown>;
  const str = (k: string) => {
    const v = row[k];
    return typeof v === "string" && v.trim() ? v.trim() : null;
  };
  const wanted = Array.isArray(row.wanted) ? row.wanted as AskCard["wanted"] : [];
  const nm = row.next_move as { actor?: string; act?: string } | null | undefined;
  return {
    structured: row.structured === true,
    // The fallback is the subject's first line — computed on the SPINE, and
    // repeated here only for a spine that predates the field.
    headline: str("headline")
      ?? ((r.task ?? r.subject ?? "").split("\n")[0].trim() || null),
    summary: str("summary"),
    incident: str("incident"),
    wanted,
    nextMove: nm && nm.actor && nm.act ? { actor: nm.actor, act: nm.act } : null,
    lifecycle: (row.lifecycle && typeof row.lifecycle === "object")
      ? {
        stages: (row.lifecycle as { stages?: AskLifecycle["stages"] }).stages ?? [],
        current: String((row.lifecycle as { current?: string }).current ?? ""),
        ageHours: typeof (row.lifecycle as { age_hours?: unknown }).age_hours
          === "number"
          ? (row.lifecycle as { age_hours: number }).age_hours : null,
        declined: (row.lifecycle as { declined?: boolean }).declined === true,
      }
      : null,
  };
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
/**
 * What stage an ask is at — READ from the spine, derived only as a fallback.
 *
 * THE DIVERGENCE THIS CLOSES (2026-08-24, found by looking at the rendered
 * page). An open desk request used to be `awaiting_ceo` here, decided by this
 * function. The spine moved the same rule (`desk.OPEN_REQUEST_ACTOR`: an open
 * request is blocked on the CHAIR dispatching it — 28 of the 49 requests
 * resolved in the live log window carry no approval event at all), and this
 * page went on listing **eleven** asks as decisions he owed. Its own
 * reconciliation banner reported the two counts disagreeing by exactly eleven.
 *
 * Both suites were green over it, because each pinned its own side. That is
 * the 11-vs-6 defect, for the third time, and the answer is the same one that
 * worked twice before: the spine owns the rule and the client reads it.
 *
 * The DERIVED branch is kept for a spine that predates the field, and it
 * reproduces the OLD behaviour exactly — degrade to yesterday, never to a
 * guess.
 */
export function askStage(r: DeskView["requests"][number]): AskStage {
  if (r.status === "declined") return "declined";
  if (r.status === "resolved") return "resolved";
  const spine = (r as { next_actor_resolved?: string | null })
    .next_actor_resolved;
  if (typeof spine === "string" && spine) {
    // The CEO owes it only if the spine says the next actor is him. Everything
    // else the chair fires — shown, never counted as his decision.
    return spine === "ceo" ? "awaiting_ceo" : "cleared_to_trigger";
  }
  return r.status === "approved" ? "cleared_to_trigger" : "awaiting_ceo";
}

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
        stage: askStage(r),
        approvedBy: r.approved_by ?? null,
        approvedAt: r.approved_at ?? null,
        declinedBy: r.declined_by ?? null,
        declinedAt: r.declined_at ?? null,
        declineReason: r.decline_reason ?? null,
        // The lifecycle, not the routing. See `approvable`.
        approvable: r.status !== "approved" && r.status !== "declined"
          && r.status !== "resolved",
        card: askCard(r),
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


/* ------------------------------------------- the card's geometric facts --- */

/**
 * A desk row, as the four things its PICTURE is drawn from.
 *
 * The adapter exists so the geometry module can stay ignorant of `DeskItem`.
 * `cardGeometry` is consumed by the CEO desk, the chair desk, the seat pages
 * and the ticket board, whose row types agree about nothing — a geometry
 * module that imported one of them would have to be forked for the next.
 *
 * TWO FIELDS ARE COMPUTED HERE AND BOTH ARE ABSENCE-CRITICAL:
 *
 *   * `ageHours` from `waitingSince`. An unreadable or missing stamp gives
 *     `null`, NOT `0`: a row whose age nobody can read is not a fresh row,
 *     and the spine drawn for one must not look like the spine drawn for the
 *     other.
 *   * `kind` from the recommendation, when there is one. An ORDER has no
 *     `kind` in the record and gets `"order"` — a literal this function
 *     supplies knowingly rather than an absence, because the item type IS the
 *     answer for an order and pretending otherwise would put the
 *     "kind not recognised" mark on the only irreversible row on the desk.
 */
export function deskItemFacts(item: DeskItem, now: string): {
  dueDate: string | null;
  moneyAtStake: number | null;
  ageHours: number | null;
  kind: string | null;
  reversibility: string;
} {
  return {
    dueDate: item.dueDate,
    moneyAtStake: item.moneyUsd,
    ageHours: hoursBetween(item.waitingSince, now),
    kind: item.kind === "order" ? "order" : (item.rec?.kind ?? null),
    reversibility: item.reversibility,
  };
}

/* `hoursBetween` is NOT redefined here. `cardAnatomy.ts` has had it since the
   lifecycle rail was built, with the same three refusals (unreadable stamp,
   unparseable instant, negative age) argued out in its own comment — and I
   wrote a byte-equivalent second copy before noticing. Two implementations of
   "how long has this waited" is precisely the duplication this desk has been
   repaired from twice; the existing one is now exported. */
