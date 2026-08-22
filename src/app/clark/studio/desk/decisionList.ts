/**
 * THE DECISION LIST — the CEO's desk reduced to the things he must click.
 *
 * THE INCIDENT, MEASURED (2026-08-22, this branch, against the live corpus
 * replayed through the merged spine's own code). The CEO: *"since morning my
 * desk has stale; out of order and poorly designed stuff. Making my flow
 * messy."* The page said **3 awaiting your decision** and then:
 *
 *   | block                                   |     px |  chars | buttons |
 *   |-----------------------------------------|-------:|-------:|--------:|
 *   | Vishesh — 3 COO memos, all "0 of N open"|    708 |  2,548 |       0 |
 *   | Donna — her daily, already read         |    951 |  3,052 |       0 |
 *   | **Fable — 23 asks, NONE awaiting him**  |**9,596**| 42,986 |       0 |
 *   | Others — the 3 actual decisions         |    754 |  2,642 |   **6** |
 *   | Decided, awaiting execution (103)       | 12,050 | 35,972 |       0 |
 *
 * **The first Accept button sat 11,608px — 14.7 screenfuls — below his name,
 * behind 49,549 characters of text, and the three decisions he actually owed
 * occupied 3% of a 24,627px page.** The largest single block was a queue
 * headed "0 awaiting you": 22 asks the chair had already been cleared to fire
 * and 1 terminal decline, none of them his.
 *
 * So this module computes the ONE list the first screenful renders, and the
 * page renders nothing above it. Everything else — memos, notes, decided rows,
 * others' work, cleared asks — moves behind named disclosure at the foot. Named
 * disclosure is not concealment: every row stays reachable and stays counted
 * where it belongs, which is the constraint that separates this from hiding
 * work to make a number look better.
 *
 * THE INVARIANT THIS MODULE EXISTS TO HOLD, and it is asserted in the tests:
 *
 *     decisionList(...).total === officerDesk(...).awaitingTotal
 *
 * The header number and the number of cards below it are the same number
 * BY CONSTRUCTION — the list is built from the officer desk's own queues
 * rather than re-derived from the payload. This desk has now shipped the
 * same defect twice by computing one quantity in two places (11 and 6, then
 * 1 and 0); a third would be a pattern rather than a mistake.
 */

import type { DeskItem, QueuedAsk } from "./execDesk";
// The `.ts` extension on a VALUE import, matching `deskTelemetry.ts`: type
// imports are erased and resolve either way, a value import must name the file
// the type-stripping test runner will actually open.
import { compareDeskItems } from "./execDesk.ts";
import type { OfficerDesk } from "./officerQueues";
import type { DeskRun } from "./seatLib";

/** How long a group heading may be before it competes with the decisions.
 *
 *  Measured, not chosen: a builder run's `task` is the whole dispatch brief
 *  (the D9 one is 197 characters) and it rendered as two full lines above
 *  three cards. One line at this page's width is ~95 characters. */
const HEADING_MAX = 92;

/** A group heading, cut to one line and ellipsised IN THE TEXT.
 *
 *  Cut here rather than with CSS `truncate` so the ellipsis is part of what a
 *  screen reader gets and the cut point is the same everywhere — the same
 *  reason `memoSubject` does it, whose rule this follows. */
export function clampHeading(s?: string | null): string {
  const t = (s ?? "").replace(/\s+/g, " ").trim();
  if (!t) return "";
  if (t.length <= HEADING_MAX) return t;
  return `${t.slice(0, HEADING_MAX - 1).trimEnd()}…`;
}

/** One thing to decide. Exactly one branch is populated. */
export type Decision =
  | { kind: "rec"; key: string; item: DeskItem }
  | { kind: "order"; key: string; item: DeskItem }
  | { kind: "ask"; key: string; ask: QueuedAsk };

export interface DecisionGroup {
  key: string;
  /** The run that produced these rows. Null for orders and asks, which have
   *  no producing run in the payload. */
  runId: string | null;
  seat: string | null;
  /** The line that heads the group. Null when the producing run is not in the
   *  payload's (capped) run list — stated as unknown rather than invented. */
  heading: string | null;
  /** True when the producing run is the COO's, i.e. this group IS one of
   *  Vishesh's triage batches. */
  isBatch: boolean;
  decisions: Decision[];
}

export interface DecisionList {
  groups: DecisionGroup[];
  /** Every decision, flat, in render order. */
  all: Decision[];
  /** MUST equal `officerDesk(...).awaitingTotal`. Asserted in the tests. */
  total: number;
  /** How many groups are COO batches — the "31 items → 7 batches" reduction,
   *  rendered rather than restated in prose. */
  batches: number;
}

/**
 * The rows the CEO owes a click on, grouped by the memo that proposed them.
 *
 * GROUPING BY THE PRODUCING RUN, AND WHY IT IS NOT AN INVENTED RELATION.
 * The chair asked for "the COO's batch becomes the GROUPING of the cards" and
 * ruled the `covered_by` relation out of scope — it needs a decision on the
 * batch format that is not a builder's to make. `run_id` is not that relation
 * and does not pretend to be: it is a field already on every recommendation,
 * pointing at the run in `desk.runs` that filed it. Grouping by it puts a
 * memo's recommendations under that memo, which for a COO run IS the batch and
 * for any other seat is still the honest answer to "who is asking me for
 * this". Nothing here reads prose and nothing infers a link that is not a key.
 *
 * WHAT IT CANNOT DO, said plainly: it cannot put another seat's row under a
 * COO batch that endorses it, because no field records that. When the CEO
 * accepts a COO batch today, the rows it endorses stay open under their own
 * seats. That is the `covered_by` gap, and the page says so rather than
 * implying the grouping is complete.
 *
 * ORDER IS PRESERVED THROUGH THE GROUPING. Groups are ordered by their
 * best-ranked member and rows keep their rank inside a group, so nothing is
 * demoted for having come off a busy desk. A grouping that re-ordered would
 * quietly sink a large decision because of who filed it — the same defect the
 * officer routing was careful to avoid.
 */
export function decisionList(
  desk: OfficerDesk,
  asks: QueuedAsk[],
  runs: DeskRun[],
  splitMemo: (s?: string | null) => { headline: string; rest: string },
): DecisionList {
  // Built FROM the officer desk's own queues, never re-derived from the
  // payload — that is what makes `total === awaitingTotal` a fact about the
  // code rather than a hope about two computations agreeing.
  const items = desk.all.flatMap((q) => q.awaiting);
  // Re-sorted because concatenating four queues loses the global rank the
  // ranking established. Same comparator, so the order is identical to the
  // flat list the desk used before it was routed by person.
  items.sort(compareDeskItems);

  const runById = new Map<string, DeskRun>();
  for (const r of runs) runById.set(r.run_id, r);

  const order: string[] = [];
  const byKey = new Map<string, DecisionGroup>();

  const push = (key: string, make: () => DecisionGroup, d: Decision) => {
    let g = byKey.get(key);
    if (!g) {
      g = make();
      byKey.set(key, g);
      order.push(key);
    }
    g.decisions.push(d);
  };

  for (const item of items) {
    if (item.kind === "order") {
      // Orders have no producing run: they are on the desk because the chair
      // staged them through the propose path. One group, named for what they
      // are rather than filed under whoever authored the strategy.
      push("orders", () => ({
        key: "orders", runId: null, seat: null,
        heading: "Staged at the venue, awaiting your approval",
        isBatch: false, decisions: [],
      }), { kind: "order", key: item.key, item });
      continue;
    }
    const runId = item.rec?.run_id ?? null;
    const key = runId ? `run:${runId}` : "unattributed";
    push(key, () => {
      const run = runId ? runById.get(runId) : undefined;
      const isBatch = (run?.seat ?? "").toLowerCase() === "coo";
      return {
        key,
        runId,
        seat: item.rec?.seat ?? run?.seat ?? null,
        // The COO's batch line is her VERDICT's first sentence — the same
        // `memoParts` split the approval cards use, so the sentence the CEO
        // reads here is character-for-character the one he reads there.
        // For any other seat the run's task is the honest heading: it is what
        // the seat was asked to do, not a conclusion invented for it.
        //
        // CAPPED, and the cap was earned by looking at it: a builder run's
        // task is the whole dispatch brief, and unclamped it rendered as TWO
        // FULL LINES of 10px uppercase above three cards — reintroducing, as
        // chrome, exactly the already-read prose this restructure removes. A
        // heading is a label for a group, not a summary of it; the memo itself
        // is one door away at the foot.
        heading: run
          ? (clampHeading(isBatch ? splitMemo(run.verdict).headline : "")
             || clampHeading(run.task) || null)
          : null,
        isBatch,
        decisions: [],
      };
    }, { kind: "rec", key: item.key, item });
  }

  // Asks LAST, in a group of their own, and the reason is stated rather than
  // being a layout habit: an ask carries neither a money figure nor a
  // reversibility class, so pushing it through a ranking whose first three
  // keys are deadline, reversibility and money would give it a position it
  // has not earned. It is counted — it does await his endorsement — and it is
  // placed where a reader can see it was not ranked with the rest.
  const mine = asks.filter((a) => a.stage === "awaiting_ceo");
  if (mine.length > 0) {
    order.push("asks");
    byKey.set("asks", {
      key: "asks", runId: null, seat: null,
      heading: "Bench asks — a seat or a human wants work dispatched",
      isBatch: false,
      decisions: mine.map((a) => ({
        kind: "ask" as const, key: `ask:${a.requestId}`, ask: a,
      })),
    });
  }

  const groups = order.map((k) => byKey.get(k)!);
  const all = groups.flatMap((g) => g.decisions);
  return {
    groups,
    all,
    total: all.length,
    batches: groups.filter((g) => g.isBatch).length,
  };
}

/**
 * DO THE SPINE'S COUNT AND THIS PAGE'S COUNT STILL AGREE? Checked at runtime,
 * on screen, every poll.
 *
 * WHY THIS EXISTS AND WHY IT IS NOT PARANOIA. The CEO's header renders the
 * PAGE's number (`officerDesk(...).awaitingTotal`) and the COO triage chip
 * eight pixels to its right renders the SPINE's (`desk_load.total`). Those are
 * two implementations of one question, and they have disagreed twice: 11 vs 6
 * in August, then 1 vs 0 on an accepted row the CEO still owned — a defect
 * that shipped with both repos' suites green, because each suite pinned its
 * own side.
 *
 * The shared contract file now pins them in the tests. A test pins what the
 * tests exercise; this pins what the CEO is actually looking at, against
 * whatever spine is actually running. It caught the third instance before it
 * shipped, on a fixture built to exercise something else.
 *
 * THE ONE LEGITIMATE DIFFERENCE, subtracted rather than tolerated: Donna's
 * notes. `desk.py` has no rule for them so they fall through to the CEO and
 * are counted; `officerQueues` routes any secretary row that is not a
 * `suggestion` into a read-only bucket and does not count it. The PAGE is
 * right, on her seat definition and the CEO's own words, and the fix is a
 * loosening of a registered trigger and therefore a human's call — so it is
 * recorded in the contract's `known_divergences` and subtracted here BY
 * MEASUREMENT, never by widening a tolerance.
 *
 * Returns null when they agree, or the sentence to render.
 */
export function countCheck(args: {
  /** `desk_load.total`, or null/undefined from a spine that did not send it. */
  spineTotal?: number | null;
  /** `officerDesk(...).awaitingTotal`. */
  pageTotal: number;
  /** Secretary rows the page diverted to read-only — the one known,
   *  measured, owned divergence. */
  divertedNotes: number;
}): string | null {
  const { spineTotal, pageTotal, divertedNotes } = args;
  // A spine that sent no total is UNVERIFIED, not agreeing — but it is also
  // not evidence of drift, and shouting about an absent field on every poll
  // would train the reader to ignore the one time it means something. The
  // footer says "unverified"; this stays quiet.
  if (typeof spineTotal !== "number") return null;
  const expected = spineTotal - divertedNotes;
  if (expected === pageTotal) return null;
  return (
    `This page counts ${pageTotal} awaiting you and the spine's own counter `
    + `says ${spineTotal}`
    + (divertedNotes > 0
      ? ` (less ${divertedNotes} of Donna's notes, which the page does not `
        + "count and the spine does — the one known difference)"
      : "")
    + `. They should agree and they do not, by ${Math.abs(expected - pageTotal)}. `
    + "One of the two is wrong about what you owe; treat the LARGER as the "
    + "number of things that might need you until it is resolved."
  );
}

/**
 * WHERE THE RANKING IS RESTING ON A WORD RATHER THAN A NUMBER.
 *
 * THE HAZARD, reported by the adversary and NOT killed on: promoting
 * reversibility above money makes a ~30-entry free-text `kind` lookup the top
 * LIVE key, because `due_date` separates zero rows (nothing writes it). So an
 * unpriced chore whose kind nobody registered sorts as `unclassified` — rank 2,
 * the fail-closed direction — while a row carrying a real dollar figure whose
 * kind IS in the table as `reversible` sorts at rank 3, below it. A $500k
 * decision can sit under a $0 chore because of a word.
 *
 * WHAT I DECIDED, and the reasoning, because this is the seam between a defect
 * and a decision:
 *
 *   * NOT to reorder the keys. The CEO ordered them this week, on the COO's
 *     stated rule, and no live row is affected — all rows are $0 today, so the
 *     hazard is real and currently a no-op. Changing a standing decision needs
 *     new evidence or a demonstrated consequence, and "I can construct a case"
 *     is neither.
 *   * NOT to let money jump a band. That is the ordering the CEO rejected,
 *     smuggled in as a tie-break.
 *   * NOT to widen the kind table on my own. It is my judgement from D3 and it
 *     has wanted a human review since; guessing harder is not reviewing it.
 *
 *   * TO MAKE IT VISIBLE, WITH THE FIGURES. The brief's constraint was "do not
 *     let it silently sort a real decision downward", and the operative word is
 *     silently. This returns the sentence the page prints when the hazard is
 *     actually live, naming the dollar amount that got outranked and the kind
 *     that outranked it. When it fires, the CEO has the evidence to reopen the
 *     ordering; until then it says nothing, because a warning about a
 *     hypothetical is noise.
 */
export function orderingHazard(decisions: Decision[]): string | null {
  const items = decisions.flatMap((d) => (d.kind === "ask" ? [] : [d.item]));
  let worstPriced: DeskItem | null = null;
  const outranking: DeskItem[] = [];
  // The list is already in render order, so "above" is simply "earlier".
  for (const i of items) {
    if (i.reversibility === "unclassified" && i.dueDate == null) {
      outranking.push(i);
      continue;
    }
    if (i.reversibility !== "reversible") continue;
    if (typeof i.moneyUsd !== "number" || i.moneyUsd <= 0) continue;
    if (outranking.length === 0) continue;
    if (!worstPriced || i.moneyUsd > worstPriced.moneyUsd!) worstPriced = i;
  }
  if (!worstPriced) return null;
  const kinds = [...new Set(outranking.map((i) => i.rec?.kind ?? "(no kind)"))];
  const money = worstPriced.moneyUsd!.toLocaleString(
    "en-US", { maximumFractionDigits: 2 });
  return (
    `THE ORDER ABOVE IS RESTING ON A WORD. A $${money} decision is sorted `
    + `BELOW ${outranking.length} row(s) carrying no dollar figure, because `
    + `their kind (${kinds.join(", ")}) is not in the reversibility table and `
    + "an unrecognised kind ranks with the urgent half — the fail-closed "
    + "direction, which is right in general and wrong here. Nothing writes "
    + "`due_date`, so reversibility is the top LIVE key and it is a lookup on "
    + "free text. Two ways out, both yours: a seat states `reversibility` on "
    + "the recommendation, or the kind goes in the table."
  );
}

export interface FoldedCounts {
  decided: number;
  elsewhere: number;
  /** Donna's notes PLUS her daily when one is on file — what is behind her
   *  door, not a subset of it. */
  donna: number;
  memos: number;
  settledAsks: number;
  /** The header's "N more on file". MUST equal the sum of the five above. */
  total: number;
}

/**
 * Everything the first screenful does NOT show, as counts — so each door can
 * say what is behind it before a reader opens it.
 *
 * A collapsed section labelled only "more" is concealment with a chevron. Each
 * of these is a different fact with a different reason for being off the
 * decision list, and the labels say which.
 *
 * ONE FUNCTION OWNS BOTH THE PARTS AND THE TOTAL, and that is not tidiness.
 * The first cut computed the header's "N more on file" here and then let the
 * page add the daily to Donna's door label on its own — so the doors summed to
 * 134 under a header saying 133. That is a quantity computed in two places on
 * the page whose entire defect history is quantities computed in two places.
 * `donnaHasDaily` is therefore a parameter, and a test asserts the parts sum.
 */
export function foldedCounts(
  desk: OfficerDesk, asks: QueuedAsk[], donnaHasDaily = false,
): FoldedCounts {
  const decided = desk.all.reduce((n, q) => n + q.decided.length, 0);
  const elsewhere = desk.all.reduce((n, q) => n + q.elsewhere.length, 0);
  const donna = desk.all.reduce((n, q) => n + q.notes.length, 0)
    + (donnaHasDaily ? 1 : 0);
  const memos = desk.all.reduce((n, q) => n + q.memos.length, 0);
  const settledAsks = asks.filter((a) => a.stage !== "awaiting_ceo").length;
  return {
    decided, elsewhere, donna, memos, settledAsks,
    total: decided + elsewhere + donna + memos + settledAsks,
  };
}
