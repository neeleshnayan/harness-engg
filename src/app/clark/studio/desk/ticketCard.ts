/**
 * WHAT A TICKET RENDERS AS — and, above everything, WHEN IT RENDERS NO CONTROL.
 *
 * THE INCIDENT (CEO, 2026-08-24, on his own desk, verbatim): *"like WTF"* — an
 * already-executed chair action rendered with **Accept** and **Reject** beside
 * it. `recordRow.ts` closed that case for one value of one field:
 * `next_actor_resolved === "nobody"`. **This generalises it to the lifecycle**,
 * which is what the CEO asked for on 2026-08-26: *"no stale cards are there"*.
 *
 * THE CONTRACT, in one sentence: **a ticket in a terminal state
 * (`done` / `declined` / `superseded` / `merged` / `expired`) renders NO
 * decision control and is counted as awaiting NOBODY** — and neither of those
 * two facts is derived from the other, because D39's P-2 was one flag
 * answering both "whose move is it" and "does this control exist", and routing
 * a request to the chair silently removed the CEO's own approve button.
 * `controls` and `countedAsAwaiting` are computed separately here on purpose.
 *
 * THREE CONTROL STATES, NOT TWO. The v1 card contract's sharpest case was
 * "ACCEPTED, EXECUTION YOURS — the stuck lamp": a row the CEO had already
 * accepted came back with an Accept button, so *a successful click and a dead
 * click were the same picture*. On the highway that distinction is a field —
 * `decided` survives the move out of `filed` (`tickets.py` §1.5) — so it is
 * read, never inferred from the state name.
 *
 *   `decide`  — undecided, his move. The only state with Accept/Reject.
 *   `execute` — HE decided; the doing is his. No Accept, a different control.
 *   `none`    — not his move, or nothing is owed at all.
 *
 * ABSENCE AND UNREADABILITY, both kept visible rather than tidied:
 *
 *   - **A terminal ticket that carries no citation says so.** The design makes
 *     a citation mandatory for `done` ("no citation, no close"); a row folded
 *     from legacy events often has none, and rendering that as a clean close
 *     would launder a bookkeeping gap into a completed one.
 *   - **A subject that is a serialised payload renders as broken, not blank.**
 *     Seven of the 713 live tickets carry a subject that starts `{` and ends
 *     `}` — a Python repr where a sentence belongs. The row IS broken and the
 *     reader should see that it is.
 *   - **An unreadable age renders UNKNOWN, never 0h.**
 */

import type { Ticket, TicketState } from "@/lib/fund_api";
import { CARD_HEADLINE_MAX, clampLine, type ClampedLine } from "./cardAnatomy.ts";
import { NOBODY } from "./recordRow.ts";

/* -------------------------------------------------------- the vocabulary --- */

/** The five states after which nothing is owed. READ FROM THE SPINE'S OWN
 *  `terminal` FIELD in practice — this list exists so a payload that predates
 *  the field, or a hand-built row, still lands on the right side, and so a
 *  test can enumerate the five without retyping them. */
export const TERMINAL_STATES: readonly TicketState[] =
  ["done", "declined", "superseded", "merged", "expired"];

export const WORKING_STATES: readonly TicketState[] =
  ["filed", "approved", "in_flight", "returned", "accepted"];

/**
 * Is this ticket finished?
 *
 * THE SPINE'S `terminal` FLAG WINS AND THE STATE LIST IS THE FALLBACK, in that
 * order. Two derivations of one fact is how this desk once read 11 where the
 * spine read 6 — but a payload with the flag missing must not default to
 * "still open", which is the direction that puts a button on a closed row.
 */
export function isTerminal(t: Pick<Ticket, "terminal" | "state">): boolean {
  if (typeof t.terminal === "boolean") return t.terminal;
  return TERMINAL_STATES.includes(t.state);
}

/** What a state is called on screen. The lifecycle labels the design names,
 *  in the reader's words rather than the machine's. */
export const STATE_LABEL: Readonly<Record<TicketState, string>> = {
  filed: "filed",
  approved: "approved, awaiting dispatch",
  in_flight: "in flight",
  returned: "returned — the chair owes a review",
  accepted: "accepted, execution owed",
  done: "done",
  declined: "declined",
  superseded: "superseded",
  merged: "merged into another ticket",
  expired: "expired",
};

/* ------------------------------------------------------------ the lamps --- */

/**
 * The three lamps of the constitution's dispatch states, plus the record.
 *
 * *"A dispatch has three states and the floor currently renders two: working,
 * awaiting the chair's review, and closed. Because the middle state has no
 * rendering, an unreviewed return is indistinguishable from a seat still
 * thinking."* `returned` is that middle state, and this is where it finally
 * gets a lamp.
 */
export type TicketLamp = "working" | "awaiting-review" | "idle" | "record";

export function ticketLamp(t: Pick<Ticket, "terminal" | "state">): TicketLamp {
  if (isTerminal(t)) return "record";
  if (t.state === "in_flight") return "working";
  if (t.state === "returned") return "awaiting-review";
  return "idle";
}

/* ----------------------------------------------------------- the subject --- */

export interface TicketTitle {
  /** What the card renders on its face. */
  line: string;
  /** What was cut, for the disclosure behind it. Empty string, never null. */
  tail: string;
  clamped: boolean;
  /** The stored subject looks like a serialised payload, not a sentence. The
   *  card renders a warning line; it does NOT hide the row. */
  looksUnreadable: boolean;
  /** The subject is absent or blank. Different from unreadable: nothing was
   *  stored, rather than something unreadable was. */
  absent: boolean;
}

/**
 * The subject as a card face.
 *
 * A NON-STRING SUBJECT IS NOT COERCED SILENTLY. `subject` is typed `unknown`
 * because the fold copies whatever the source event carried; `String({})`
 * gives `"[object Object]"`, which is a tidy blank wearing a value. An object
 * subject is reported `looksUnreadable` and rendered as its JSON so the reader
 * can see what is actually stored.
 */
export function ticketTitle(
  subject: unknown, max = CARD_HEADLINE_MAX,
): TicketTitle {
  let raw: string;
  let structured = false;
  if (subject === null || subject === undefined) {
    raw = "";
  } else if (typeof subject === "string") {
    raw = subject;
  } else {
    structured = true;
    try { raw = JSON.stringify(subject) ?? String(subject); }
    catch { raw = String(subject); }
  }
  const t = raw.trim();
  const reprish = t.startsWith("{") && t.endsWith("}");
  const c: ClampedLine = clampLine(t, max);
  return {
    line: c.line,
    tail: c.tail,
    clamped: c.clamped,
    looksUnreadable: structured || reprish,
    absent: t.length === 0,
  };
}

/* ------------------------------------------------------ the adjudication --- */

export interface TicketAdjudication {
  /** The state the decision put it in — `approved` / `accepted` / a terminal. */
  state: TicketState | null;
  actor: string | null;
  at: string | null;
  /** How many decisions this ticket has ever received. More than one is not
   *  an error here — it is `filed -> approved -> ... -> accepted`, an ordinary
   *  lifecycle — but it IS the number the one-decision-one-row rule watches. */
  count: number;
  /** Where the canonical decision lives, when this row is not it. */
  canonicalTicketId: string | null;
}

/** Who decided this ticket and when, or null if nobody ever has.
 *
 *  READ FROM THE FOLD'S LINEAGE, never from `state`. A ticket that was decided
 *  and has since moved on still carries its decision — that permanence is the
 *  whole of §1.5 and it is what makes "one decision, one row" checkable. */
export function ticketAdjudication(t: Ticket): TicketAdjudication | null {
  if (!t.decided) return null;
  return {
    state: t.decided_state ?? null,
    actor: t.decided_by ?? null,
    at: t.decided_at ?? null,
    count: typeof t.decision_count === "number" ? t.decision_count : 0,
    canonicalTicketId: t.canonical_ticket_id ?? null,
  };
}

/* -------------------------------------------------------- the controls ----- */

export type TicketControl = "decide" | "execute" | "none";

export interface TicketCardState {
  ticketId: string;
  type: Ticket["type"];
  state: TicketState;
  stateLabel: string;
  terminal: boolean;
  lamp: TicketLamp;
  title: TicketTitle;
  /** WHICH CONTROL EXISTS. Never derived from the count below. */
  controls: TicketControl;
  /** The sentence a reader needs to interpret the absence — or presence — of
   *  a control. Always non-empty: a row with no buttons and no sentence is the
   *  absence-as-blank defect wearing a layout. */
  controlsWhy: string;
  /** WHETHER ANYONE IS WAITING. Never derived from the control above. */
  countedAsAwaiting: boolean;
  /** Who, when anyone. Null when nobody is. */
  awaitingActor: string | null;
  adjudication: TicketAdjudication | null;
  /** For a terminal ticket: the citation the design makes mandatory, or null
   *  with `citationOwed` true. */
  citation: string | null;
  citationOwed: boolean;
  /** Hours in the current state, and whether that number could be read. */
  ageInStateHours: number | null;
  ageKnown: boolean;
}

/**
 * The one function every ticket surface asks "what does this row render as".
 *
 * ONE DERIVATION, MANY CALLERS. The v1 contract exists because four surfaces
 * each answered this question their own way and three got the stuck lamp
 * wrong. There is one answer here and the contract file pins it.
 */
export function ticketCardState(t: Ticket): TicketCardState {
  const terminal = isTerminal(t);
  const actor = typeof t.next_actor === "string" ? t.next_actor.trim() : "";
  const adjudication = ticketAdjudication(t);
  const citation = typeof t.citation === "string" && t.citation.trim()
    ? t.citation.trim() : null;
  const ageKnown = typeof t.age_in_state_hours === "number"
    && Number.isFinite(t.age_in_state_hours);

  // --- CONTROL EXISTENCE. Terminal first, and nothing below can override it.
  let controls: TicketControl;
  let controlsWhy: string;
  if (terminal) {
    controls = "none";
    controlsWhy = `This ticket is ${STATE_LABEL[t.state]} — a terminal state. `
      + "Terminal is terminal: there is no reopen transition, and a dispute "
      + "with it is a new challenge ticket, not a button here.";
  } else if (actor === NOBODY) {
    controls = "none";
    controlsWhy = t.next_actor_why?.trim()
      ? `Filed for the record — no decision is owed · ${t.next_actor_why.trim()}`
      : "Filed for the record — no decision is owed.";
  } else if (actor !== "ceo" && actor !== "unknown") {
    controls = "none";
    controlsWhy = t.next_actor_why?.trim()
      || `This is the ${actor || "next actor"}'s move, not yours.`;
  } else if (t.decided) {
    controls = "execute";
    controlsWhy = "You decided this already"
      + (adjudication?.at ? ` (${adjudication.at})` : "")
      + " — what is owed is the execution, not another decision.";
  } else {
    controls = "decide";
    controlsWhy = t.next_actor_why?.trim() || "Your decision is owed.";
  }

  // --- THE COUNT. Computed from the lifecycle, independently of the control.
  //     A terminal ticket is awaiting nobody however it is routed; a working
  //     ticket routed to `nobody` is awaiting nobody too, and both facts are
  //     read rather than inferred from `controls === "none"`.
  const countedAsAwaiting = !terminal && actor !== "" && actor !== NOBODY;

  return {
    ticketId: t.ticket_id,
    type: t.type,
    state: t.state,
    stateLabel: STATE_LABEL[t.state] ?? t.state,
    terminal,
    lamp: ticketLamp(t),
    title: ticketTitle(t.subject),
    controls,
    controlsWhy,
    countedAsAwaiting,
    awaitingActor: countedAsAwaiting ? actor : null,
    adjudication,
    citation,
    // "No citation, no close" is the design's rule (Part 1.2). A legacy fold
    // often cannot supply one, so the card SAYS the citation is owed instead
    // of rendering a clean close over a bookkeeping gap.
    citationOwed: terminal && t.state === "done" && citation === null,
    ageInStateHours: ageKnown ? (t.age_in_state_hours as number) : null,
    ageKnown,
  };
}

/**
 * How many of a population are awaiting somebody — the count the desk prints.
 *
 * IT IS A COUNT OF `countedAsAwaiting`, NOT A COUNT OF ROWS WITH BUTTONS.
 * Those two numbers differ on every row that is somebody else's move, and
 * conflating them is how a heading once said "awaiting a decision" over rows
 * that had none.
 */
export function awaitingCount(tickets: readonly Ticket[]): number {
  return tickets.filter((t) => ticketCardState(t).countedAsAwaiting).length;
}

/** The five terminals, counted. Rendered beside the awaiting count so a reader
 *  can see the population is whole rather than filtered. */
export function recordCount(tickets: readonly Ticket[]): number {
  return tickets.filter((t) => isTerminal(t)).length;
}

/* ---------------------------------------------------------- the list cap --- */

/**
 * How many rows a board list draws before it stops.
 *
 * A CAP, NEVER A COUNT. The last cap this desk shipped without a sentence took
 * the CEO's own desk from 57 rows to 50 with nothing on screen saying so, and
 * he lost a $915 item behind it.
 */
export const BOARD_ROW_CAP = 200;

export interface ListCap {
  /** How many rows the caller will actually draw. */
  shown: number;
  /** How many matched the filter. */
  matched: number;
  hidden: number;
  capped: boolean;
  /** The sentence beside the list. Always non-empty — a list with no sentence
   *  about its own bounds is the truncation defect waiting to happen again. */
  note: string;
}

/**
 * What a capped list must say about itself.
 *
 * THE DEFECT THIS CLOSES WAS FOUND ON THE RENDERED PAGE, not by a test: the
 * board's header read *"showing 369 of 713"* while the list drew 200. Both
 * numbers were true about something and neither was true about what was on
 * screen — which is precisely the shape of the truncation that started this
 * dispatch. Extracted from JSX because a ternary inside a `<span>` cannot be
 * reached by the test runner.
 *
 * @param matched rows passing the current filter.
 * @param total   the whole population behind the filter.
 */
export function listCap(
  matched: number, total: number, cap = BOARD_ROW_CAP,
): ListCap {
  const shown = Math.min(matched, cap);
  const hidden = Math.max(0, matched - cap);
  return {
    shown,
    matched,
    hidden,
    capped: hidden > 0,
    note: hidden > 0
      ? `showing ${shown} of ${matched} matching rows — ${hidden} are NOT on `
        + `screen. ${total} ticket(s) in the fold.`
      : `showing all ${shown} matching row(s) of ${total} in the fold.`,
  };
}
