/**
 * THE ONE STEERING SENTENCE.
 *
 * CEO instruction for the redesigned desk: the header is the ANSWER, not a
 * dashboard — a greeting, the one number, and ONE sentence saying what to do
 * next. This module writes that sentence and nothing else.
 *
 * IT READS THE SPINE'S RANKING; IT DOES NOT RE-RANK. `GET /fund/desk/ceo`
 * returns `decisions.items` already ordered — its own `ranked_by` string says
 * *"due_date, then money_at_stake — absent last on both"* — and this desk has
 * shipped one-quantity-computed-twice three times (11 vs 6, 1 vs 0, 96 vs 97).
 * A second comparator here would be the fourth. So the steer is `items[0]`,
 * and the tests prove it FOLLOWS the served order rather than agreeing with it
 * by coincidence: a fixture whose served order contradicts the money order
 * must produce the served answer.
 *
 * THE HONESTY THAT MAKES THIS SAFE, and it is the whole reason the module is
 * not a one-liner. Measured on the live spine 2026-08-23, twice: **11 of 28
 * rows awaiting the CEO stated NEITHER a date nor a dollar figure, then 13 of
 * 28** — the total held while the unrankable share grew, inside one
 * afternoon. The spine reports it as `ranked_on_nothing`, which is why this
 * module reads that field rather than carrying either figure. For those rows the order IS ARRIVAL ORDER.
 * Naming an arbitrary row "the one that needs you most" would be a fabricated
 * priority on the firm's decision surface — worse than no sentence, because it
 * is unfalsifiable and looks authoritative. So:
 *
 *   * a top row stating a DATE steers on the date, and says how many days;
 *   * a top row stating only MONEY steers on the money, and says so;
 *   * a top row stating NEITHER produces the honest sentence instead: nothing
 *     here is ranked, and here is how many rows could not be ranked.
 *
 * `at` is passed in rather than read from the clock so the day arithmetic is
 * testable and so the sentence is computed against the spine's own timestamp,
 * not the browser's.
 */

import type { CeoDeskView, DeskEngineItem } from "@/lib/fund_api";

/** What the sentence is resting on. Rendered, never inferred by the reader. */
export type SteerBasis = "due_date" | "money" | "unranked" | "none" | "unknown";

export interface Steer {
  basis: SteerBasis;
  /** The sentence. Always non-empty — every branch has something true to say. */
  text: string;
  /** The row it points at, so the header can link to it. Null on every branch
   *  that does not name a row. */
  item: DeskEngineItem | null;
  /** True only when a DATED commitment is today or already past. The one
   *  condition on this desk that outranks a click. */
  overdue: boolean;
}

/** Whole days from `from` to `to`, or null when either is unparseable.
 *
 *  Both are treated as UTC calendar days: a due date is `YYYY-MM-DD` with no
 *  time in it, and comparing it against a local-midnight instant is how a
 *  deadline lands a day early for half the world.
 */
export function daysUntil(dueDate: string, from: string): number | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dueDate.trim());
  if (!m) return null;
  const due = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const t = Date.parse(from);
  if (!Number.isFinite(t)) return null;
  const now = new Date(t);
  const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
  return Math.round((due - today) / 86_400_000);
}

/** "$1,748.92" — money for a sentence, not for a table. */
function usd(n: number): string {
  return n.toLocaleString("en-US", {
    style: "currency", currency: "USD",
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  });
}

/** The first sentence of a row's title, clamped. A steering line is a pointer,
 *  not a summary — an uncapped COO batch title is 200+ characters. */
function pointer(title: string | null | undefined, max = 120): string {
  const t = (title ?? "").replace(/\s+/g, " ").trim();
  if (!t) return "this row carries no text";
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1).trimEnd()}…`;
}

export interface SteerInput {
  /** The served CEO desk. `null` = unreachable, and the steer says so. */
  view: CeoDeskView | null;
  /** The figure the header is already rendering, so the two agree by
   *  construction rather than by two folds happening to match. */
  needsYou: number | null;
}

/**
 * The sentence under the number.
 */
export function steeringSentence(input: SteerInput): Steer {
  const { view, needsYou } = input;

  if (!view) {
    return {
      basis: "unknown",
      text: "The desk engine could not be read, so what to look at first is "
        + "UNKNOWN — not nothing.",
      item: null,
      overdue: false,
    };
  }

  const d = view.decisions;
  const items = d?.items ?? [];

  if (items.length === 0) {
    return {
      basis: "none",
      text: needsYou === 0 || needsYou === null
        ? "Nothing is ranked for you right now."
        : `The fund's counter says ${needsYou} await you and the ranked list `
          + "came back empty — those two disagree, and the banner above says so.",
      item: null,
      overdue: false,
    };
  }

  const top = items[0];
  // The cap is the SPINE'S. A steer computed over a truncated page is a steer
  // over a page, and the difference matters when the row that matters most is
  // the one that did not fit.
  const truncated = d.truncated === true && d.total > d.shown;
  const truncNote = truncated
    ? ` The list is capped at ${d.shown} of ${d.total}, so this is the first `
      + "row of the page the spine sent, not provably of the whole queue."
    : "";

  if (top.due_date) {
    const days = daysUntil(top.due_date, view.at ?? view.greeting?.at ?? "");
    const when = days === null
      ? `dated ${top.due_date}`
      : days < 0 ? `${-days} day${days === -1 ? "" : "s"} OVERDUE`
        : days === 0 ? "due TODAY"
          : days === 1 ? "due tomorrow"
            : `due in ${days} days`;
    const money = typeof top.money_at_stake === "number"
      ? `, ${usd(top.money_at_stake)} at stake` : "";
    return {
      basis: "due_date",
      text: `Start here — ${when}${money}: ${pointer(top.title)}${truncNote}`,
      item: top,
      overdue: days !== null && days <= 0,
    };
  }

  if (typeof top.money_at_stake === "number") {
    return {
      basis: "money",
      text: `Start here — the largest figure on your desk at `
        + `${usd(top.money_at_stake)}, and nothing above it states a date: `
        + `${pointer(top.title)}${truncNote}`,
      item: top,
      overdue: false,
    };
  }

  // THE HONEST BRANCH. Nothing at the top of the served ranking states a date
  // or a figure, so its position is arrival order and this refuses to dress it
  // up as urgency.
  const unranked = typeof d.ranked_on_nothing === "number"
    ? d.ranked_on_nothing : null;
  const howMany = unranked === null
    ? "some of them"
    : `${unranked} of ${d.total}`;
  return {
    basis: "unranked",
    text: "Nothing on your desk can be called most urgent: the top row states "
      + `neither a deadline nor a figure, and ${howMany} state neither. Their `
      + "order is arrival order. That is a gap in what the seats record, not a "
      + "quiet desk." + truncNote,
    item: null,
    overdue: false,
  };
}
