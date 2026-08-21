/**
 * The CEO's desk, split into FOUR QUEUES BY PERSON.
 *
 * CEO verbatim, 2026-08-21: *"my desk should have 4 queues -> Vishesh, Donna,
 * Fable and Others segregated by team member name."*
 *
 * The desk was already ranked (money → reversibility → staleness) and already
 * split by stage (awaiting a decision vs awaiting execution). What it was not,
 * was ROUTED: everything from every seat landed in one list, so "who is asking
 * me for this" was a per-row read rather than a structure. A CEO scanning a
 * queue wants to know whose desk an item came off before deciding it, because
 * the answer changes how long the decision takes.
 *
 * FOUR RULES, and each is a decision rather than a default:
 *
 *   1. **Donna's notes never carry buttons.** Her seat definition says a `note`
 *      "asks to be READ, not decided", and only a `suggestion` is "a concrete,
 *      doable thing". This module treats ONLY `suggestion` as decidable and
 *      everything else from her as a note — which is deliberately stricter than
 *      testing for `kind === "note"`. Her one live run predates that vocabulary
 *      and files `record_keeping` / `org_observation`; under a `=== "note"`
 *      test those would sprout accept/reject buttons, which is precisely the
 *      thing the CEO objected to ("this seems more like a note and I don't know
 *      what to accept"). Fail toward read-only.
 *
 *   2. **A note is never COUNTED as awaiting a decision.** It is not work the
 *      CEO owes anyone. Counting it would reintroduce the CDO-D4 defect at the
 *      queue level: a desk of nothing but notes would read as a backlog.
 *
 *   3. **Decided items stay visible and stay uncounted**, exactly as they do on
 *      the page today. A decision that never executes is a decision that did not
 *      happen, and the CEO is the only person positioned to notice.
 *
 *   4. **An unrecognised seat goes to OTHERS under its own name — never
 *      dropped, never silently folded into a known officer.** The live desk
 *      carries `cdo-trial`, which is not on the roster; a queue that quietly
 *      discarded it would hide a real open recommendation.
 */

import type { DeskItem } from "./execDesk";
import type { CooMemo, QueuedAsk } from "./execDesk";

export type OfficerId = "vishesh" | "donna" | "fable" | "others";

/** Which seat each officer IS, for the face and the seat-page link. `others`
 *  is a bucket rather than a person and has no seat. */
export const OFFICER_SEAT: Record<OfficerId, string | null> = {
  vishesh: "coo",
  donna: "secretary",
  fable: "cto",
  others: null,
};

export const OFFICER_LABEL: Record<OfficerId, string> = {
  vishesh: "Vishesh",
  donna: "Donna",
  fable: "Fable",
  others: "Others",
};

export const OFFICER_ROLE: Record<OfficerId, string> = {
  vishesh: "COO — triages your desk into batches; endorses, never decides",
  donna: "Secretary — documents the day from the record; never decides",
  fable: "CTO — stages what you accept, and routes the bench's asks up",
  others: "The bench, by seat",
};

/** The seats whose items belong to a named officer. Everything else is Others.
 *
 *  `fable` collects the CTO's OWN recommendations. Orders and asks reach the
 *  Fable queue by their kind rather than by a seat, below — a pending order has
 *  no seat field at all, and it is on the desk because the CTO staged it. */
const OFFICER_OF_SEAT: Record<string, OfficerId> = {
  coo: "vishesh",
  secretary: "donna",
  cto: "fable",
  fable: "fable",
};

/** The ONE kind of Donna item that can be accepted or rejected.
 *
 *  See rule 1 above: this is a whitelist, not a blacklist, on purpose. */
export const DECIDABLE_SECRETARY_KIND = "suggestion";

export function isSecretaryNote(item: DeskItem): boolean {
  return (item.rec?.kind ?? "") !== DECIDABLE_SECRETARY_KIND;
}

export interface OfficerQueue {
  id: OfficerId;
  label: string;
  role: string;
  /** The seat behind the face, or null for the Others bucket. */
  seat: string | null;
  /** Items that need a click from the CEO, in the rank they arrived in. */
  awaiting: DeskItem[];
  /** Decided, not yet executed. Shown, never counted. */
  decided: DeskItem[];
  /** Donna only: items to READ. Shown, never counted, no buttons. */
  notes: DeskItem[];
  /** Vishesh only: the COO's batch memos, newest first. */
  memos: CooMemo[];
  /** Fable only: the seat-filed ask queue, in the CEO's ordering. */
  asks: QueuedAsk[];
  /** Others only: `awaiting` re-grouped under each seat's own name. */
  groups: { seat: string; items: DeskItem[] }[];
  /** THE number. Only things genuinely waiting on the CEO. */
  awaitingCount: number;
}

const empty = (id: OfficerId): OfficerQueue => ({
  id,
  label: OFFICER_LABEL[id],
  role: OFFICER_ROLE[id],
  seat: OFFICER_SEAT[id],
  awaiting: [], decided: [], notes: [], memos: [], asks: [], groups: [],
  awaitingCount: 0,
});

/** Which officer owns this item. Exported so a test can assert the routing
 *  table directly rather than inferring it from bucket sizes. */
export function officerOfItem(item: DeskItem): OfficerId {
  // An order is on this desk because the CTO staged it through the propose
  // path. It carries no seat, and attributing it to the strategy's author
  // would name someone who did not put it there.
  if (item.kind === "order") return "fable";
  const seat = (item.rec?.seat ?? "").trim().toLowerCase();
  return OFFICER_OF_SEAT[seat] ?? "others";
}

export interface OfficerDesk {
  vishesh: OfficerQueue;
  donna: OfficerQueue;
  fable: OfficerQueue;
  others: OfficerQueue;
  /** In render order. */
  all: OfficerQueue[];
  /** The headline: every queue's awaitingCount, summed. */
  awaitingTotal: number;
}

/**
 * Route the already-ranked desk into the four queues.
 *
 * Takes items that have ALREADY been ranked and split by stage, so the ordering
 * inside each queue is the same money-first ordering the desk has always used.
 * Routing does not re-rank: an item's officer says who is asking, not how
 * urgent it is, and letting the routing reorder would quietly demote a large
 * decision because of whose desk it came from.
 */
export function officerDesk(input: {
  awaitingDecision: DeskItem[];
  awaitingExecution: DeskItem[];
  memos: CooMemo[];
  asks: QueuedAsk[];
}): OfficerDesk {
  const q: Record<OfficerId, OfficerQueue> = {
    vishesh: empty("vishesh"),
    donna: empty("donna"),
    fable: empty("fable"),
    others: empty("others"),
  };

  for (const item of input.awaitingDecision) {
    const id = officerOfItem(item);
    if (id === "donna" && isSecretaryNote(item)) {
      // Rule 1 + 2: read-only, and never part of the count.
      q.donna.notes.push(item);
      continue;
    }
    q[id].awaiting.push(item);
  }
  for (const item of input.awaitingExecution) {
    q[officerOfItem(item)].decided.push(item);
  }

  q.vishesh.memos = input.memos;
  q.fable.asks = input.asks;

  // Others: grouped under each seat's own name, seats in descending queue size
  // then alphabetical, so the busiest bench seat leads and the order is stable.
  const bySeat = new Map<string, DeskItem[]>();
  for (const item of q.others.awaiting) {
    const seat = (item.rec?.seat ?? "").trim().toLowerCase() || "unattributed";
    const list = bySeat.get(seat) ?? [];
    list.push(item);
    bySeat.set(seat, list);
  }
  q.others.groups = [...bySeat.entries()]
    .map(([seat, items]) => ({ seat, items }))
    .sort((a, b) => (b.items.length - a.items.length) || a.seat.localeCompare(b.seat));

  q.vishesh.awaitingCount = q.vishesh.awaiting.length;
  q.donna.awaitingCount = q.donna.awaiting.length;
  // Only asks AWAITING THE CEO count. A cleared ask is the CTO's to fire and a
  // declined one is terminal; counting either would put work on this number
  // that no click of the CEO's can remove.
  q.fable.awaitingCount =
    q.fable.awaiting.length +
    input.asks.filter((a) => a.stage === "awaiting_ceo").length;
  q.others.awaitingCount = q.others.awaiting.length;

  const all = [q.vishesh, q.donna, q.fable, q.others];
  return {
    ...q,
    all,
    awaitingTotal: all.reduce((n, x) => n + x.awaitingCount, 0),
  };
}

/**
 * Whether a queue has anything at all to render.
 *
 * Distinct from `awaitingCount > 0`: a queue holding only notes, only decided
 * items or only cleared asks is not EMPTY, it just needs nothing from the CEO,
 * and collapsing it away would hide Donna's entire output on a day she filed
 * only notes.
 */
export function hasContent(qq: OfficerQueue): boolean {
  return qq.awaiting.length > 0 || qq.decided.length > 0 || qq.notes.length > 0
    || qq.memos.length > 0 || qq.asks.length > 0;
}
