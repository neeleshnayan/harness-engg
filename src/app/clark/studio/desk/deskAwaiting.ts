/**
 * ONE FOLD FOR "WHAT AWAITS YOU".
 *
 * THE DEFECT, MEASURED ON THE LIVE DESK 2026-08-23 (screenshot and probe, this
 * branch, before the fix). The CEO's desk rendered, on two consecutive lines:
 *
 *     96 awaiting your decision · in 36 groups, 2 of them COO batches
 *     [ 97 / 50 AWAITING YOU · +9 ELSEWHERE · COO TRIAGE DUE ]
 *
 * **Two numbers, both labelled "awaiting you", eighteen pixels apart, with
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

/** Where the figure on screen came from. Never inferred by the reader. */
export type AwaitingSource = "spine" | "page" | "unknown";

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
  /** Did `/fund/desk` answer at all? */
  deskReadable: boolean;
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

/** Plural-safe "N item(s)" without pulling in a formatter. */
const rows = (n: number) => `${n} row${n === 1 ? "" : "s"}`;

/**
 * The single figure the desk renders for "what awaits you", and how to read it.
 */
export function awaitingHeadline(input: AwaitingInput): AwaitingHeadline {
  const {
    deskReadable, servedTotal, servedComplete, servedUnreadable,
    divertedNotes, cardCount,
  } = input;

  if (!deskReadable) {
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
    parts.push(
      `The fund's own counter says ${servedTotal}; ${rows(divertedNotes)} of `
      + "that are Donna's notes, which ask to be read rather than decided, so "
      + "they are not counted here. That is the one known difference between "
      + "the two folds and it is subtracted by measurement, never by widening "
      + "a tolerance.",
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
