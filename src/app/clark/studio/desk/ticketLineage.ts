/**
 * TICKET LINEAGE — the chain behind one ticket, and the five ways a link can
 * be missing.
 *
 * CEO, 2026-08-26, verbatim: *"we want to cleanup the lineage."* The chain he
 * wants is the one the design names (§1.5): a recommendation → the run that
 * produced it → the ask that triggered it → the dispatch that served it, plus
 * the decision that closed it and any supersession edge.
 *
 * **THE HARD PART IS NOT DRAWING THE CHAIN. IT IS SAYING WHY A LINK IS NOT
 * THERE**, and this is the file where the fund's oldest rule earns its keep.
 * Measured on the live fold, 2026-08-26, 713 tickets:
 *
 *   | link state         | rows | what it means                             |
 *   |--------------------|-----:|-------------------------------------------|
 *   | `found`            |  122 | `parent_id` is set AND resolves. 70 point |
 *   |                    |      | at a dispatch, 52 at an ask; **0 dangle** |
 *   | `fenced`           |  443 | `parent_basis: unlinkable_pre_highway` —  |
 *   |                    |      | the record cannot support a link at all   |
 *   | `not_applicable`   |  148 | an ask or a chair-born dispatch. It has   |
 *   |                    |      | no parent BY DESIGN, not by loss          |
 *   | `absent`           |    0 | the record was read and holds no link      |
 *   | `dangling`         |    0 | a link that names a ticket nobody has seen |
 *
 * **`fenced` IS NOT `absent` AND RENDERING IT AS "no lineage" WOULD BE THE
 * ABSENCE-AS-ZERO DEFECT ON THE SURFACE BUILT TO END IT.** 443 of 713 rows —
 * 62% — are in that cohort. A chain drawing them as unconnected would be
 * telling the reader the firm's bookkeeping is clean where in truth it is
 * unreadable, and the bookkeeping is the thing worth fixing.
 *
 * `not_applicable` earns its own value for the same reason in the other
 * direction: an ask at the head of its own chain is not a broken link, and
 * folding it into `absent` would make 148 healthy rows look damaged and put a
 * repair target on work that needs none.
 *
 * `dangling` is 0 today and the value exists anyway: a link that names an id
 * the fold has never seen is exactly the phantom shape the highway's door
 * guard exists to refuse, and a lineage view that silently dropped one would
 * hide the arrival of the defect it is watching for.
 *
 * WHAT THIS MODULE DOES NOT DO. It does not walk the event log — the fold has
 * already done that and re-deriving a link in TypeScript is how this desk once
 * read 11 where the spine read 6. It does not classify a supersession mode
 * (`supersessionChip` owns those sentences). And it never infers a parent from
 * a shared prefix: **the 8-char-prefix habit is what rotted 54 of 56 linkages**
 * and every match here is a full-id equality.
 */

import type { Ticket } from "@/lib/fund_api";
import { PRE_HIGHWAY_FENCE } from "./ticketExceptions.ts";

/* ---------------------------------------------------------------- types --- */

export type LinkState =
  | "found" | "fenced" | "not_applicable" | "absent" | "dangling";

/** The sentence each state renders. One place, so five surfaces cannot phrase
 *  the same absence five ways — and so `fenced` can never quietly acquire the
 *  wording of `absent`. */
export const LINK_SENTENCE: Readonly<Record<LinkState, string>> = {
  found: "linked",
  fenced: "LINEAGE UNKNOWN — this ticket predates the highway and the record "
    + "cannot support a link; it is fenced, not unlinked",
  not_applicable: "no parent by design — this ticket is the head of its own "
    + "chain",
  absent: "the record was read and holds no parent for this ticket",
  dangling: "the link names a ticket the fold has never seen — a phantom "
    + "reference, not a missing one",
};

/** Types that legitimately head their own chain. An `ask` is filed by a seat
 *  or a human; a chair-born `dispatch` has no backing request by definition
 *  (design §1.4, the lamp-close case). Measured: 148 of 713 rows. */
export const ROOT_TYPES: readonly Ticket["type"][] = ["ask", "dispatch"];

export interface LineageLink {
  state: LinkState;
  /** The ticket at the other end, when there is one and it resolves. */
  ticket: Ticket | null;
  /** The id the row NAMED, even when it does not resolve — a dangling link
   *  must show which id it named or the reader cannot chase it. */
  namedId: string | null;
  sentence: string;
  /** The fold's own word for how the link was derived (`run_trace_id`), so a
   *  reader can tell a link the record supported from one a sweep asserted. */
  basis: string | null;
}

export interface TicketLineage {
  ticket: Ticket;
  /** Nearest parent first, then ITS parent, and so on. Empty when the parent
   *  link is not `found`. */
  ancestors: Ticket[];
  parent: LineageLink;
  /** Tickets naming this one as their parent. */
  children: Ticket[];
  /** Other tickets on the same `trace_id`, excluding this one and everything
   *  already shown as an ancestor or a child — the cohort a reader would
   *  otherwise have to reconstruct by eye. */
  traceCohort: Ticket[];
  traceId: string | null;
  /** Set when the fold says the canonical decision lives on ANOTHER ticket
   *  (a `merged` row). Null when this row is its own canonical. */
  canonical: LineageLink | null;
  /** Every applied state change, oldest first — the walkable history. */
  transitions: Ticket["transitions"];
  /** Transitions the fold REFUSED under terminal precedence. Kept, because
   *  "this was attempted and correctly refused" is the fact that says a guard
   *  did its job. */
  refused: Ticket["refused_transitions"];
  /** How deep the walk went before it stopped, and why it stopped. */
  depth: number;
  truncated: boolean;
}

/* -------------------------------------------------------------- the walk --- */

/** A cycle or a pathological chain must not hang the page. Ten is far past
 *  anything the model produces (ask → dispatch → recommendation is three) and
 *  reaching it is reported, never silently accepted. */
export const MAX_LINEAGE_DEPTH = 10;

function linkFor(t: Ticket, index: Map<string, Ticket>): LineageLink {
  const named = typeof t.parent_id === "string" && t.parent_id.trim()
    ? t.parent_id.trim() : null;
  if (named) {
    const parent = index.get(named) ?? null;
    const state: LinkState = parent ? "found" : "dangling";
    return {
      state, ticket: parent, namedId: named,
      sentence: LINK_SENTENCE[state], basis: t.parent_basis ?? null,
    };
  }
  if (t.parent_basis === PRE_HIGHWAY_FENCE) {
    return { state: "fenced", ticket: null, namedId: null,
             sentence: LINK_SENTENCE.fenced, basis: t.parent_basis };
  }
  if (ROOT_TYPES.includes(t.type)) {
    return { state: "not_applicable", ticket: null, namedId: null,
             sentence: LINK_SENTENCE.not_applicable, basis: t.parent_basis ?? null };
  }
  return { state: "absent", ticket: null, namedId: null,
           sentence: LINK_SENTENCE.absent, basis: t.parent_basis ?? null };
}

/**
 * Build a full-id index once. Callers hold it across many rows.
 *
 * FULL IDS ONLY. No prefix matching, no `startsWith`, no "did you mean" here —
 * a shorthand is a help string at a door, never a join.
 */
export function ticketIndex(tickets: readonly Ticket[]): Map<string, Ticket> {
  const m = new Map<string, Ticket>();
  for (const t of tickets) m.set(t.ticket_id, t);
  return m;
}

/**
 * The chain behind one ticket.
 *
 * @param id the ticket to anchor on. Returns null when the population does not
 *   contain it — an anchor the fold has never seen is not an empty lineage, it
 *   is an unknown ticket, and the caller must say which.
 */
export function lineageFor(
  id: string, tickets: readonly Ticket[], index?: Map<string, Ticket>,
): TicketLineage | null {
  const idx = index ?? ticketIndex(tickets);
  const anchor = idx.get(id);
  if (!anchor) return null;

  const parent = linkFor(anchor, idx);

  const ancestors: Ticket[] = [];
  const seen = new Set<string>([anchor.ticket_id]);
  let cursor = parent.ticket;
  let truncated = false;
  while (cursor) {
    if (seen.has(cursor.ticket_id)) { truncated = true; break; }
    if (ancestors.length >= MAX_LINEAGE_DEPTH) { truncated = true; break; }
    seen.add(cursor.ticket_id);
    ancestors.push(cursor);
    cursor = linkFor(cursor, idx).ticket;
  }

  const children = tickets.filter((t) => t.parent_id === anchor.ticket_id);

  const traceId = typeof anchor.trace_id === "string" && anchor.trace_id.trim()
    ? anchor.trace_id.trim() : null;
  const shown = new Set<string>([
    anchor.ticket_id,
    ...ancestors.map((t) => t.ticket_id),
    ...children.map((t) => t.ticket_id),
  ]);
  const traceCohort = traceId
    ? tickets.filter((t) => t.trace_id === traceId && !shown.has(t.ticket_id))
    : [];

  const canonicalId = anchor.canonical_ticket_id;
  const canonical: LineageLink | null =
    typeof canonicalId === "string" && canonicalId && canonicalId !== anchor.ticket_id
      ? (() => {
          const row = idx.get(canonicalId) ?? null;
          const state: LinkState = row ? "found" : "dangling";
          return { state, ticket: row, namedId: canonicalId,
                   sentence: LINK_SENTENCE[state],
                   basis: anchor.decision_basis ?? null };
        })()
      : null;

  return {
    ticket: anchor,
    ancestors,
    parent,
    children,
    traceCohort,
    traceId,
    canonical,
    transitions: anchor.transitions ?? [],
    refused: anchor.refused_transitions ?? [],
    depth: ancestors.length,
    truncated,
  };
}

/* ------------------------------------------------------------- coverage --- */

export interface LineageCoverage {
  total: number;
  found: number;
  fenced: number;
  notApplicable: number;
  absent: number;
  dangling: number;
  /** The denominator a coverage PERCENTAGE may honestly use: rows that could
   *  carry a link at all. The fenced cohort is reported BESIDE it, never
   *  inside it (design §2.5, and the clean-field rule).
   *
   *  A `linkablePct` computed over the whole population would read 17% today
   *  and would be measuring how much history predates the highway, not how
   *  well the highway links. */
  linkable: number;
  linkablePct: number | null;
  note: string;
}

/**
 * Where the population's linkage actually stands.
 *
 * THE PERCENTAGE HAS AN EXPLICIT DENOMINATOR AND THE FENCE IS OUTSIDE IT. This
 * is the one number a future dispatch will be judged on ("any post-highway run
 * lands unlinkable to its ticket" falsifies design failure 1), so it must not
 * silently improve as old rows age out of view.
 */
export function lineageCoverage(
  tickets: readonly Ticket[] | null | undefined,
): LineageCoverage | null {
  if (!tickets) return null;
  const idx = ticketIndex(tickets);
  let found = 0, fenced = 0, notApplicable = 0, absent = 0, dangling = 0;
  for (const t of tickets) {
    switch (linkFor(t, idx).state) {
      case "found": found += 1; break;
      case "fenced": fenced += 1; break;
      case "not_applicable": notApplicable += 1; break;
      case "absent": absent += 1; break;
      case "dangling": dangling += 1; break;
    }
  }
  const linkable = found + absent + dangling;
  return {
    total: tickets.length,
    found, fenced, notApplicable, absent, dangling,
    linkable,
    linkablePct: linkable > 0 ? (found / linkable) * 100 : null,
    note: linkable > 0
      ? `${found} of ${linkable} linkable ticket(s) carry a parent the record `
        + `supports. ${fenced} more are FENCED as pre-highway — the record `
        + `cannot support a link for them, which is not the same as their `
        + `having none — and ${notApplicable} head their own chain by design.`
      : `no ticket in this population could carry a parent: ${fenced} are `
        + `fenced as pre-highway and ${notApplicable} head their own chain by `
        + "design, so a coverage percentage would have no denominator",
  };
}
