/**
 * The desk engine, client side — PRESENTATION ONLY.
 *
 * THE ONE RULE THIS FILE EXISTS TO KEEP: nothing here decides which column a
 * row belongs in, whose move it is, or whether a row may be approved. The
 * spine's `desk_matrix` / `next_actor` / `approval_refusal` already answered
 * all three, and a TypeScript copy of any of them would be a second definition
 * free to drift from the first. That is not a hypothetical — this desk shipped
 * a counter reading 11 beside a page reading 6, eight pixels apart, because the
 * page carried its own status rule.
 *
 * So what lives here is: ordering for the eye, labels, and the sentences that
 * turn a supersession edge into something a human can act on.
 *
 * The CEO's frame (2026-08-23, verbatim): *"like put a matrix view that shows
 * intra-team ticket count -> I click it expands the list; then different
 * categories for whats closed, whats ticking, whats blocking, whats open"* —
 * given after the previous page earned *"this feels like an infine scroll"*.
 */

import type {
  CeoDeskView, DeskBriefing, DeskCategory, DeskEngineItem,
  DeskMatrix, DeskMatrixCell, DeskSupersessionEdge,
} from "@/lib/fund_api";

/** The four columns, in the CEO's own order, with the words he used. */
export const CATEGORY_LABELS: Record<DeskCategory, string> = {
  open: "Open",
  ticking: "Ticking",
  blocking: "Blocking",
  closed: "Closed",
};

export interface MatrixRow {
  seat: string;
  cells: Record<DeskCategory, DeskMatrixCell>;
  /** Every column summed — the seat's whole ticket count, which is the number
   *  the CEO asked to see first. */
  total: number;
  /** What is not closed. The row's real load. */
  live: number;
}

const EMPTY_CELL: DeskMatrixCell = { count: 0, shown: 0, truncated: false, items: [] };

/** The matrix as ordered rows, ready to render.
 *
 *  Seat ORDER comes from the spine (most-open first); this function does not
 *  re-sort, because the order is part of the fold's answer. It fills missing
 *  cells with an explicit zero so a row never renders ragged — and a filled
 *  zero is honest here, unlike everywhere else on this desk, because the
 *  matrix's own contract is that every item lands in exactly one column: a
 *  seat with no BLOCKING rows genuinely has none.
 */
export function matrixRows(m: DeskMatrix | null | undefined): MatrixRow[] {
  if (!m || !Array.isArray(m.seats)) return [];
  return m.seats.map((seat) => {
    const raw = m.cells?.[seat] ?? ({} as Record<DeskCategory, DeskMatrixCell>);
    const cells = {} as Record<DeskCategory, DeskMatrixCell>;
    let total = 0;
    let live = 0;
    for (const cat of m.categories) {
      const cell = raw[cat] ?? EMPTY_CELL;
      cells[cat] = cell;
      total += cell.count;
      if (cat !== "closed") live += cell.count;
    }
    return { seat, cells, total, live };
  });
}

/** Is there anything behind this cell to expand? */
export function expandable(cell: DeskMatrixCell | undefined): boolean {
  return !!cell && cell.count > 0;
}

/** The sentence a truncated cell must carry, or null.
 *
 *  A cap read as a count is how this desk truncated the firm's first spend
 *  meter, so the shortfall is always spelled out with both numbers.
 */
export function truncationNote(cell: DeskMatrixCell | undefined): string | null {
  if (!cell || !cell.truncated) return null;
  return `showing ${cell.shown} of ${cell.count} — the payload caps each cell; `
    + `open the seat's own page for the rest`;
}

/** Stable key for an expanded cell. */
export function cellKey(seat: string, cat: DeskCategory): string {
  return `${seat}::${cat}`;
}

/* ------------------------------------------------------- supersession ----- */

export interface SupersessionChip {
  /** Two words, for the chip itself. */
  label: string;
  /** Why the row cannot be approved, in one sentence. */
  detail: string;
  /** The named future event, when there is one. */
  diesAt: string | null;
  /** The branch in which the row lives again. */
  revivesIf: string | null;
  /** The row that replaces it, or null for a row killed on its merits. */
  superseder: string | null;
  /** Whether the approve control must be disabled. Read from the EDGE, not
   *  guessed from the mode string, so the UI and the server's refusal move
   *  together. */
  blocksApproval: boolean;
}

/** Turn an edge into the chip and the sentence beside it.
 *
 *  THE PENDING CASE IS THE DANGEROUS ONE, not the softer one, and the wording
 *  says so. R37's premise was TRUE when it was filed and stops being true at
 *  R39 step 4; the risk was never the row today, it was the row clicked after
 *  the event that made it wrong. A chip reading "pending" as though it meant
 *  "not yet decided" would invite exactly that click.
 */
export function supersessionChip(
  edge: DeskSupersessionEdge | null | undefined,
): SupersessionChip | null {
  if (!edge || edge.retracted_at) return null;
  const superseder = edge.superseder_ref ?? null;
  if (edge.mode === "killed") {
    return {
      label: "KILLED",
      detail: `Killed on its merits and moved to the kill shelf. ${edge.reason}`,
      diesAt: null, revivesIf: null, superseder,
      blocksApproval: true,
    };
  }
  if (edge.mode === "superseded_pending") {
    return {
      label: "SUPERSEDED · PENDING",
      detail: "Its premise dies at a named event that has not happened yet — "
        + "which is why it cannot be approved. Approving it after the event "
        + "is the failure this chip exists to prevent.",
      diesAt: edge.dies_at_event ?? null,
      revivesIf: edge.revives_if ?? null,
      superseder,
      blocksApproval: true,
    };
  }
  return {
    label: "SUPERSEDED",
    detail: `Replaced, and no longer approvable. ${edge.reason}`,
    diesAt: null,
    revivesIf: edge.revives_if ?? null,
    superseder,
    blocksApproval: true,
  };
}

/* ---------------------------------------------------------- briefings ----- */

export interface BadgeView { text: string; tone: "verified" | "unverified" | "unknown"; }

/** The shelf badge, with `unknown` kept distinct from `unverified`.
 *
 *  A memo the chair HAS checked must never be shown as unchecked because the
 *  verification ledger was unreadable. Those are different facts, and the
 *  second one is an outage, not a judgement about the memo.
 */
export function badgeView(b: DeskBriefing): BadgeView {
  if (b.badge === "chair-verified") return { text: "chair-verified", tone: "verified" };
  if (b.badge === "unknown") return { text: "verification unknown", tone: "unknown" };
  return { text: "chair-unverified", tone: "unverified" };
}

/* THREE EXPORTS WERE DELETED HERE (D31, cleanup ticket dce47670), all
   test-only and all superseded:

   - `SectionCount` / `sectionCounts()` built a header strip of seven counts
     for a design that never shipped. The desk now carries ONE number in its
     header and a count per lane, and a second per-section count path is
     exactly how this desk came to render 11 and 6 for one question.
   - `COLLAPSED_BY_DEFAULT` named which matrix column starts shut; `DeskMatrix`
     never imported it and decides expansion from `expandable(cell)` and its
     own `open` state. A constant nothing reads is a specification pretending
     to be a control.
   - `hygieneLine()` composed a hygiene sentence CLIENT-SIDE. The spine now
     serves one, verbatim, on `greeting.hygiene`, and the desk renders that.
     Two sentences for one measurement is one sentence too many, and only the
     spine's is generated from the fold it describes. Its only consumer was
     `EngineViews.HygieneLine`, deleted in the same pass — also unrendered.

   Together with `MetricOrAbsent` and `SeatBadge` this is 5 dead surfaces
   removed; the tests that pinned them went with them. */

/** Every recommendation carrying a live edge, keyed `<run_id>#<rec_id>`.
 *
 *  READ FROM `blocked`, WHICH IS UNCAPPED — deliberately not from the matrix
 *  cells, which the spine caps at 25 apiece. A surface that gathered its
 *  blocked rows from the matrix would silently miss the 26th, and the one row
 *  a surface must never miss is the one whose approve button has to be off.
 *
 *  Any page building its own cards from the older `/fund/desk` payload (which
 *  knows nothing about supersession) must consult this before it renders a
 *  control. The server refuses regardless; this is what stops the CEO being
 *  offered a button that fails.
 */
export function blockedRecs(v: CeoDeskView | null): Map<string, DeskSupersessionEdge> {
  const out = new Map<string, DeskSupersessionEdge>();
  for (const it of v?.blocked?.items ?? []) {
    if (it.source !== "recommendation" || !it.supersession) continue;
    if (it.run_id == null || it.rec_id == null) continue;
    out.set(`${it.run_id}#${it.rec_id}`, it.supersession);
  }
  return out;
}

/** Rows the CEO can actually act on, from the payload's own decision list.
 *
 *  A FILTER, not a re-rank: the spine ordered them (due date, then money,
 *  absent last on both) and re-sorting here would be the second definition
 *  again. The only thing dropped is anything carrying a live edge, and the
 *  spine already dropped those — this is a belt, and it is cheap.
 */
export function actionable(v: CeoDeskView | null): DeskEngineItem[] {
  if (!v) return [];
  return v.decisions.items.filter((i) => !supersessionChip(i.supersession)?.blocksApproval);
}
