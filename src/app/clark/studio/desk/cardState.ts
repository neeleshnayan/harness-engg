/**
 * What a desk row RENDERS as — the client half of `app/fund/deskcard.py`.
 *
 * THE INCIDENT (CEO, 2026-08-24, verbatim): *"Why is this issue persisting;
 * shakes my confidence that information is flowing seemlessly in the org."*
 *
 * His clicks land. The write path is event-sourced and sound. What failed is
 * this half — the read path, the sentences on his screen:
 *
 *   * he accepted R39 (spine event seq 1281), the POST returned 200, the page
 *     refetched, and the row came back WITH AN ACCEPT BUTTON ON IT, because
 *     nothing here distinguished "you decided this, now execute it" from
 *     "nobody has decided this". **14 of the 34 rows on his live decision list
 *     are that shape.** A successful click and a dead click were one picture;
 *   * **52 of 227 rows were adjudicated by the chair alone** (`co-cto` 39,
 *     `cto` 13) and rendered as though he had approved them — *"I cant form a
 *     view of whats closed and adjudicated by you"*;
 *   * **2 rows rendered as a raw Python dict repr.**
 *
 * NOTHING HERE RE-DERIVES A SPINE ANSWER. Every value below is READ off the
 * payload; the one thing this file computes is a fallback for a spine that
 * predates the annotation, and it degrades to the OLD behaviour rather than to
 * a guess. That rule is not style: this page and the spine's counter each
 * carried their own copy of "whose move is it" and rendered 11 and 6 for the
 * same payload, eight pixels apart, twice.
 *
 * THE COUNTS DO NOT MOVE. `executionYours` is a PICTURE over the existing
 * `awaiting_decision` stage — `desk_load.total` counts ceo+unknown and the
 * desk-stage contract pins this page's total to it. Anything here that changed
 * a number would be moving a threshold's population while calling itself a
 * rendering change.
 */

import type { DeskItem } from "./execDesk.ts";

type Rec = NonNullable<DeskItem["rec"]>;

/** Statuses that mean the CEO already said yes. Mirrors the spine's
 *  `deskcard.DECIDED_STATUSES`; the contract pins the pair equal. */
const DECIDED = new Set(["accepted", "staged"]);

/** Actors whose rows sit on the CEO's figure. The client half of the spine's
 *  partition — `ceo` and `unknown`, nothing else. `unknown` stays with him
 *  because a row whose owner could not be read is work he may still owe. */
const CEO_ACTORS = new Set(["ceo", "unknown"]);

/**
 * Is this a row he DECIDED whose next act is still his?
 *
 * READS the spine's `execution_yours` when it is there. The local computation
 * is the fallback for a spine that predates it — same inputs, same rule, and
 * it exists so an older spine renders the OLD picture rather than a wrong new
 * one. When both are available the spine wins, always.
 */
export function executionYours(i: DeskItem): boolean {
  if (i.kind !== "recommendation") return false;
  const r = i.rec;
  if (typeof r?.execution_yours === "boolean") return r.execution_yours;
  const actor = i.nextActor;
  if (typeof actor !== "string") return false;
  return CEO_ACTORS.has(actor) && DECIDED.has(String(r?.status));
}

/* ------------------------------------------------- the display sentence --- */

/**
 * The line to put on the card, and the paragraph to hide behind the toggle.
 *
 * DEFENSIVE EVEN AFTER THE SPINE FIX, and the reason is that the two halves
 * repair different populations. The filing door stops NEW reprs; the spine's
 * `text_display` repairs STORED ones on the way out; this last check catches a
 * spine that has neither — an older build, a cached response, a fixture. Three
 * layers for a defect that put a Python repr in front of the one person whose
 * confidence is the product.
 *
 * It never invents: with nothing readable it returns the raw text unchanged,
 * because a blank card is worse than an ugly one.
 */
export function cardText(r: Rec | undefined | null): {
  headline: string; detail: string | null; repaired: boolean;
} {
  const raw = String(r?.text ?? "").trim();
  const fromSpine = typeof r?.text_display === "string"
    ? r.text_display.trim() : "";
  if (fromSpine) {
    return {
      headline: fromSpine,
      detail: (typeof r?.text_detail === "string" && r.text_detail.trim())
        ? r.text_detail.trim() : null,
      repaired: fromSpine !== raw,
    };
  }
  // No annotation from the spine: the stored value, unchanged. `repaired` is
  // false because nothing was repaired — the caller asks `looksUnreadable`
  // separately and renders the warning line, so the row shows as broken
  // rather than as a tidy blank.
  return { headline: raw, detail: null, repaired: false };
}

/** Does the stored text look like a serialised payload rather than a sentence?
 *  Rendered as a warning line, never hidden: the row IS broken and the CEO
 *  should see that it is, rather than see a tidy blank. */
export function looksUnreadable(r: Rec | undefined | null): boolean {
  if (typeof r?.text_display === "string" && r.text_display.trim()) {
    return false;
  }
  const raw = String(r?.text ?? "").trim();
  return raw.startsWith("{") && raw.endsWith("}");
}

/* ----------------------------------------------------- who adjudicated ---- */

export type AdjudicationChannel = "ceo" | "via_chair" | "chair" | "unknown";

export interface Adjudication {
  channel: AdjudicationChannel;
  actor: string;
  at: string | null;
  label: string;
  citation: string | null;
  instruction: string | null;
}

/**
 * Who closed this row, read straight off the spine. `null` = undecided.
 *
 * NOT RE-DERIVED HERE. The spine already parses the actor string (including
 * the bracketed CEO instruction the approval guard writes); a second parser in
 * TypeScript is the divergence this desk has now shipped twice. A spine that
 * does not send the field renders no chip, which is the honest degradation:
 * "we do not know who closed it" beats a chip that guesses.
 */
export function adjudicationOf(r: Rec | undefined | null): Adjudication | null {
  const a = r?.adjudication;
  return a && typeof a === "object" && typeof a.channel === "string" ? a : null;
}

/** The chair's own dispositions — the category the CEO asked for by name.
 *  `via_chair` is deliberately NOT included: that is HIS decision with the
 *  chair's hand on it, and merging the two would answer his question with the
 *  wrong number (63 where the truth is 52). */
export function closedByTheChair(r: Rec | undefined | null): boolean {
  return adjudicationOf(r)?.channel === "chair";
}

/* ------------------------------------------------------- what replaced it - */

export interface SupersededBy {
  ref: string; phrase: string; quote: string;
}

/** The row this one's decision note says superseded it, or null.
 *
 *  Parsed on the SPINE, where the corpus is, and only when the note NAMES its
 *  superseder: six of the ten word-level "supersed" hits in the live record
 *  are one boilerplate sentence about something else entirely. A wrong link
 *  looks exactly like a right one; a gap looks like a gap. */
export function supersededBy(r: Rec | undefined | null): SupersededBy | null {
  const s = r?.superseded_by;
  return s && typeof s === "object" && typeof s.ref === "string" ? s : null;
}

/* ------------------------------------------------------------- cascade ---- */

export interface CascadeMember {
  ref: string; status: string | null;
  state: "done" | "pending" | "not_open";
}

export interface Cascade {
  total: number; done: number; pending: number; not_open: number;
  members: CascadeMember[]; note: string;
}

/** The cascade block under a decided bundle, or null.
 *
 *  A REMINDER, NEVER A CONTROL. The constitution's cascade rule says the chair
 *  validates each member against the record and then executes; this renders
 *  the outstanding count so that step cannot be forgotten silently. No button
 *  on it does anything. */
export function cascadeOf(r: Rec | undefined | null): Cascade | null {
  const c = r?.cascade;
  return c && typeof c === "object" && typeof c.total === "number" ? c : null;
}

/** The one sentence a cascade chip shows. Absent when nothing is outstanding
 *  and nothing is unreadable — a chip that fired on a finished bundle would be
 *  noise on every row, which is how a warning stops being read.
 *
 *  ONE SENTENCE, NOT THE SPINE'S WHOLE NOTE. The first cut rendered the chip
 *  AND `cascade.note` beside it, which on screen read as two paragraphs saying
 *  the same thing twice — caught by looking at the page. The note is the
 *  spine's sentence for an API reader; the card gets the count and the one
 *  caveat that changes what the count means. */
export function cascadeChip(c: Cascade | null): string | null {
  if (!c) return null;
  const caveat = c.not_open
    ? ` · ${c.not_open} no longer on the open desk, not counted as done`
    : "";
  if (c.pending) {
    return `Cascade pending · ${c.pending} of ${c.total} undecided${caveat}`;
  }
  if (c.not_open) {
    return `Cascade · ${c.done} of ${c.total} confirmed closed${caveat}`;
  }
  return null;
}

/* ------------------------------------------------- the acceptance lamp ---- */

export type ClickFeedback =
  | { state: "idle" }
  | { state: "sending" }
  /** The POST returned and the refetch has not landed yet. THE ONE-SECOND
   *  ANSWER: the acceptance criterion is that a successful click looks
   *  different within a second, and a refetch of seven endpoints does not
   *  always finish in one. */
  | { state: "landed"; status: string; at: string }
  | { state: "failed"; message: string };

/**
 * What the row should say right now, given the payload and the click.
 *
 * THE STUCK LAMP, IN ONE FUNCTION. The old page had exactly two renderings —
 * a row with buttons, and no row — so every outcome of a click that did not
 * remove the row looked like nothing happening. An accepted row whose
 * execution is still the CEO's own does NOT leave his list (correctly: he owes
 * the execution), so it came back looking untouched.
 *
 * `pending` here means the button is live. Everything else is a statement.
 */
export function rowLamp(i: DeskItem, feedback: ClickFeedback): {
  tone: "actionable" | "sending" | "decided" | "failed";
  label: string | null;
  showButtons: boolean;
} {
  if (feedback.state === "sending") {
    return { tone: "sending", label: "Recording…", showButtons: false };
  }
  if (feedback.state === "failed") {
    return { tone: "failed", label: `Not recorded: ${feedback.message}`,
      showButtons: true };
  }
  if (feedback.state === "landed") {
    return { tone: "decided", label: `Recorded ${feedback.status}`,
      showButtons: false };
  }
  const r = i.rec;
  if (i.kind === "recommendation" && r && DECIDED.has(String(r.status))) {
    const adj = adjudicationOf(r);
    const who = adj?.channel === "chair" ? "Closed by the chair"
      : adj?.channel === "via_chair" ? "You approved this; the chair staged it"
        : "You accepted this";
    return {
      tone: "decided",
      label: executionYours(i)
        ? `${who} — execution yours`
        : `${who} — the chair owes the execution`,
      // NO ACCEPT BUTTON ON A ROW ALREADY ACCEPTED. Offering one is what made
      // a landed click indistinguishable from a dead one, and clicking it
      // again writes a second decision event over a decision that already
      // happened.
      showButtons: false,
    };
  }
  return { tone: "actionable", label: null, showButtons: true };
}
