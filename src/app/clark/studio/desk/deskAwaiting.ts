/**
 * ONE FOLD FOR "WHAT AWAITS YOU".
 *
 * THE DEFECT, MEASURED ON THE LIVE DESK 2026-08-23 (screenshot and probe, this
 * branch, before the fix). The CEO's desk rendered, on two consecutive lines:
 *
 *     96 awaiting your decision · in 36 groups, 2 of them COO batches
 *     [ 97 / 50 AWAITING YOU · +9 ELSEWHERE · COO TRIAGE DUE ]
 *
 * **Two numbers, both labelled "awaiting you", on consecutive lines, with
 * nothing on the page saying which one to believe.** 96 is this page's own
 * fold of the payload; 97 is the counter the spine serves. They differ by the
 * one row Donna filed as a note, which the page routes to read-only and the
 * spine counts. And because that difference is KNOWN, `countCheck` stays
 * silent about it — so the page's own drift warning is, correctly, quiet at
 * exactly the moment two different numbers are on screen.
 *
 * The desk has shipped a quantity-computed-twice defect three times now: 11 vs
 * 6, then 1 vs 0, and now 96 vs 97 rendered side by side without comment. Each
 * previous fix pinned the two computations to each other. This one removes the
 * second computation from the headline instead.
 *
 * THE RULE: **the served counter is the fund's number and the page renders
 * it.** The page's own fold survives as a fallback for a spine that does not
 * serve one — and when it is used, IT SAYS SO on screen. A figure this build
 * computed is a different claim from a figure the fund computed, and a reader
 * is entitled to know which they are looking at.
 *
 * THE ONE ADJUSTMENT, and why it is not a second fold. `desk.py` has no rule
 * for a secretary's note, so a row that "asks to be READ, not decided" falls
 * through to the CEO's count; `officerQueues` routes it read-only on Donna's
 * seat definition and the CEO's own words ("this seems more like a note and I
 * don't know what to accept"). The PAGE is right and the fix is a loosening of
 * a registered trigger, which is a human's call. So the served figure is
 * rendered LESS those rows, the subtraction is stated in the note, and the
 * count of them is a CLASSIFICATION of the spine's own rows rather than a
 * rival total. Absence is never zero here either: an adjustment that would
 * drive the figure below zero is REFUSED and reported, not clamped.
 *
 * WHAT THIS MODULE DOES NOT DO. It does not decide what is on the page — the
 * cards still come from `decisionList`, which is built from the officer desk
 * by construction. So the headline and the cards can still disagree, and when
 * they do this module returns the sentence that says so loudly. That is one
 * number plus a named warning, which is a different thing from two numbers
 * presented as equals.
 *
 * AND IT DOES NOT WRITE THAT SENTENCE ITSELF. `countCheck` already owns it,
 * with four tests and a named history; this module moves the CALL SITE rather
 * than the logic. Two functions phrasing one disagreement is the same defect
 * as two functions counting one queue.
 */

import { countCheck } from "./decisionList.ts";
import { READING_DESK, type DeskRead } from "./deskRead.ts";

/** Where the figure on screen came from. Never inferred by the reader.
 *
 *  `loading` is NOT a source of a figure — it is the admission that there is
 *  no figure yet. It lives in this union so the header can render a calm
 *  glyph for it instead of the word `unknown`, which on this desk means "we
 *  asked and could not find out" (ticket fccb9cf3). */
export type AwaitingSource = "spine" | "page" | "unknown" | "loading";

/**
 * Whether a surface's triage chip may print the served total.
 *
 * `show` — this chip is the only figure on screen (the CTO console).
 * `already-on-screen` — the surface renders the served figure itself, so a
 *   second one would be the 96-vs-97 defect again.
 */
export type ChipTotal = "show" | "already-on-screen";

/**
 * A one-line predicate, extracted for one measured reason: inverting it inside
 * the chip's JSX put the rival number back on the CEO's desk AND removed it
 * from the CTO's, and every test still passed — a mutant that SURVIVED,
 * because there is no DOM test runner here and a source regex cannot tell
 * `===` from `!==` in any way that means something. A decision that only
 * exists inside a component is a decision nothing can check.
 */
export function chipShowsTotal(total: ChipTotal): boolean {
  return total === "show";
}

export interface AwaitingHeadline {
  /** The one number to render. `null` means UNKNOWN — never 0. */
  value: number | null;
  /** The spine could not count everything it was asked to, so the figure is a
   *  FLOOR. Rendered as a `+` suffix, exactly as the triage chip does. */
  atLeast: boolean;
  source: AwaitingSource;
  /** Rendered beneath the figure whenever there is something a reader must
   *  know to read it correctly. `null` when the number needs no gloss. */
  note: string | null;
  /** Non-null when the figure and the cards actually on screen disagree. The
   *  loud one — this is the third-instance catcher, not a footnote. */
  reconciliation: string | null;
}

export interface AwaitingInput {
  /** What is known about the `/fund/desk` read: still in flight, failed, or
   *  answered. It replaced a `deskReadable` boolean, which could not tell a
   *  pending fetch from an outage and reported the first as the second for
   *  about thirty seconds on the CEO's own desk. */
  read: DeskRead;
  /** `desk_load.total`. Absent on a spine that predates the counter. */
  servedTotal?: number | null;
  /** `desk_load.complete`. `false` makes the served figure a floor. */
  servedComplete?: boolean | null;
  /** `desk_load.unreadable` — what the spine could not count. */
  servedUnreadable?: string[] | null;
  /** Secretary rows this page routed to read-only: the one known, measured,
   *  owned divergence between the two folds. */
  divertedNotes: number;
  /** `decisionList(...).total` — the number of cards actually rendered. */
  cardCount: number;
}

/** Plural-safe "1 row" / "N rows", without pulling in a formatter. */
const rows = (n: number) => `${n} row${n === 1 ? "" : "s"}`;

/**
 * The single figure the desk renders for "what awaits you", and how to read it.
 */
export function awaitingHeadline(input: AwaitingInput): AwaitingHeadline {
  const {
    read, servedTotal, servedComplete, servedUnreadable,
    divertedNotes, cardCount,
  } = input;

  // STILL IN FLIGHT. Checked FIRST and returning before anything is counted:
  // a read that has not answered cannot have served a total, and a page that
  // fell through to the page-fold branch here would print its own `0` while
  // the answer was on its way.
  if (read === "loading") {
    return {
      value: null,
      atLeast: false,
      source: "loading",
      note: `${READING_DESK} This figure has not been counted yet — nothing `
        + "here has failed, and nothing here is a zero.",
      reconciliation: null,
    };
  }

  if (read === "unreadable") {
    return {
      value: null,
      atLeast: false,
      source: "unknown",
      note:
        "The desk could not be read, so what awaits you is UNKNOWN, not none. "
        + "Anything waiting is still waiting.",
      reconciliation: null,
    };
  }

  // A spine that serves no counter is not a spine that counted zero. Fall back
  // to this build's own fold and SAY that is what is on screen.
  if (typeof servedTotal !== "number" || !Number.isFinite(servedTotal)) {
    return {
      value: cardCount,
      atLeast: false,
      source: "page",
      note:
        "Counted by this page, not by the fund: the spine served no desk "
        + "counter, so this figure is this build's own fold of the payload. It "
        + "matches the cards below by construction and has not been checked "
        + "against anything else.",
      reconciliation: null,
    };
  }

  const atLeast = servedComplete === false;
  const unreadable = (servedUnreadable ?? []).filter((s) => !!s);

  // The adjustment. It may only ever REMOVE rows the page has classified as
  // read-only, and it may never take the figure below zero — a subtraction
  // larger than the total means the classification and the count disagree
  // about which rows exist, which is a finding, not a licence to pick a
  // number.
  const adjustable = divertedNotes > 0 && divertedNotes <= servedTotal;
  const value = adjustable ? servedTotal - divertedNotes : servedTotal;

  const parts: string[] = [];
  if (adjustable) {
    // Written as two clauses rather than one because the one-clause version
    // shipped to a screenshot as "1 row of that are Donna's notes". A count
    // that can be 1 cannot share a verb with a plural noun.
    parts.push(
      `The fund's own counter says ${servedTotal}. It counts `
      + (divertedNotes === 1
        ? "one row this page does not: a note from Donna, which asks"
        : `${divertedNotes} rows this page does not: notes from Donna, which ask`)
      + " to be read rather than decided. That is the one known difference "
      + "between the two folds and it is subtracted by measurement, never by "
      + "widening a tolerance.",
    );
  }
  if (divertedNotes > servedTotal) {
    parts.push(
      `This page routed ${rows(divertedNotes)} to read-only, which is MORE `
      + `than the ${servedTotal} the fund's counter reports awaiting you. The `
      + "subtraction is refused rather than clamped: the two are disagreeing "
      + "about which rows exist, and that is worth knowing.",
    );
  }
  if (atLeast) {
    parts.push(
      "The spine could not count everything, so this is a FLOOR and not a "
      + "total"
      + (unreadable.length ? `; it could not read ${unreadable.join(", ")}.` : "."),
    );
  }

  // The cards on screen come from the page's fold. If the fund's adjusted
  // figure and the cards disagree, one of them is wrong about what the CEO
  // owes and neither is safe to present alone.
  //
  // Delegated to `countCheck`, which already owns this sentence and its four
  // tests. `applied` is passed rather than `divertedNotes` so the comparison
  // is against the figure ACTUALLY on screen: in the refused case nothing was
  // subtracted, and passing the unapplied subtraction would make the check
  // reconcile a number the page is not showing.
  const applied = adjustable ? divertedNotes : 0;
  const reconciliation = countCheck({
    spineTotal: value + applied,
    pageTotal: cardCount,
    divertedNotes: applied,
  });

  return {
    value,
    atLeast,
    source: "spine",
    note: parts.length ? parts.join(" ") : null,
    reconciliation,
  };
}

/**
 * THE HERO GLYPH — the largest thing on the CEO's desk, as one string.
 *
 * Extracted from the JSX for the reason this repo keeps re-learning: node's
 * type stripper refuses `.tsx`, so a ternary inside a component is a decision
 * no test can reach, and the only guard available for it is a source-text pin
 * that a reformat breaks and a rename fools. It was a three-way ternary the
 * day it decided the difference between "we could not find out" and "we have
 * not been told yet" (ticket fccb9cf3), which is exactly the kind of decision
 * that should not live where nothing can execute it.
 *
 * The `+` suffix rides here too, so the caller renders ONE expression. It can
 * only ever attach to a real number: `atLeast` marks the served figure as a
 * FLOOR, and there is no floor under a figure that does not exist.
 */
export function heroFigure(h: AwaitingHeadline): string {
  if (h.value === null) return h.source === "loading" ? "…" : "unknown";
  return h.atLeast ? `${h.value}+` : String(h.value);
}

/* ------------------------------------------------------- the shelf line --- */

/**
 * THE SHELF LINE — the hero number partitioned, and honest about not knowing.
 *
 * The line itself is the CEO's ("are you sure?" on seeing 51 awaiting him, and
 * he was right: one number was conflating four obligations). What this
 * function adds, D42, is the case the first cut did not have: **an unreadable
 * desk rendered `0 to decide today · 0 decided — execution yours · 0 asks
 * awaiting your routing call · 0 with no deadline` underneath a hero that
 * correctly said `unknown`.** Four confident zeros beside an admitted unknown,
 * about the same rows, on the CEO's own desk — found in the dead-spine pass,
 * which is why that pass is not optional.
 *
 * `null` is the whole point of the return type. The caller renders a sentence,
 * never a row of dashes the eye reads as zeroes.
 */
export interface DeskShelves {
  decideToday: number;
  exec: number;
  asks: number;
  noDeadline: number;
}

/** One card's worth of the two fields the shelves partition on. */
export interface ShelfItem {
  dueDate: string | null;
  /** The spine's `execution_yours` as this page resolved it. */
  executionYours: boolean;
}

/**
 * @param read the state of the `/fund/desk` read. ONLY `readable` partitions
 *   anything: a pending read and a failed one both return null, because the
 *   partition of a number nobody has yet is not a row of zeroes. The CALLER
 *   holds the same `read` value and writes the sentence, so the two states
 *   get two different sentences from one source rather than one sentence
 *   from a boolean that cannot tell them apart.
 * @param today the fund's UTC day, `YYYY-MM-DD` — passed in, never read from
 *   the browser, because "due today" must mean the fund's day and because a
 *   clock a test cannot set is a branch a test cannot reach.
 */
export function deskShelves(
  read: DeskRead, items: readonly ShelfItem[], asks: number, today: string,
): DeskShelves | null {
  if (read !== "readable") return null;
  let decideToday = 0, exec = 0, noDeadline = 0;
  for (const it of items) {
    if (it.executionYours) { exec += 1; continue; }
    if (it.dueDate && it.dueDate <= today) decideToday += 1;
    else noDeadline += 1;
  }
  return { decideToday, exec, asks, noDeadline };
}
