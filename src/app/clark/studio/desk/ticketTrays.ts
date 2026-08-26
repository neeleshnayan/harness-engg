/**
 * PER-DESK VIEWS — a seat's in-tray and out-tray, as QUERIES over one fold.
 *
 * The design's Part 3, first paragraph: *"each seat gets an in-tray (`approved`
 * tickets awaiting its dispatch + unconsumed `lesson` tickets addressed to it)
 * and an out-tray (`returned` tickets it produced awaiting chair review)"* —
 * *"all queries over one fold, no per-view state."*
 *
 * THE "NO PER-VIEW STATE" CLAUSE IS THE LOAD-BEARING ONE and it is why this
 * file is a filter and not a store. Failure 3 in the design's own table —
 * *executed-shown-open, 16 rows, "like WTF"* — happened because views kept
 * state of their own and a decision landed in one of them. A tray that is a
 * `filter()` cannot go stale relative to the fold; a tray with a cache can.
 *
 * WHY A CHAIR CARES: the COO's BATCH PLAN mandate says a seat's next brief
 * should be composed FROM its in-tray rather than from the chair's memory.
 * That turns "what does the builder owe" from archaeology into a `SELECT`, and
 * the in-tray below is that select.
 *
 * MEASURED ON THE LIVE FOLD, 2026-08-26 (713 tickets), because a view whose
 * shape nobody checked is a view that renders zero forever:
 *
 *   `approved` tickets by seat: builder 37, mechanism 3, analyst 2,
 *   validator 2, pm 2, coo 1 — **47 blessed and undispatched**, which is
 *   failure 7 of the design's table with a name on every row.
 *
 *   `returned` tickets: **0**. The state was born two days ago and nothing has
 *   used the door yet, so every out-tray is empty AND SAYS WHY — an empty tray
 *   from an unused state and an empty tray from a cleared queue are different
 *   facts, and only the second is good news.
 *
 *   `lesson` tickets: **0 of 713.** The type exists; nothing has filed one.
 *   The BINDS backlog is still carried by hand.
 */

import type { Ticket } from "@/lib/fund_api";
import { isTerminal } from "./ticketCard";

/* --------------------------------------------------------------- the seat -- */

/**
 * Which seat a ticket belongs to.
 *
 * `dispatched_to` WINS OVER `filed_for` WHERE BOTH EXIST, because a dispatch
 * names the seat it actually went to while `filed_for` records who it was
 * filed on behalf of, and the live record has 37 rows where only the first is
 * populated. Both are the spine's own attribution; neither is inferred from a
 * subject line.
 */
export function seatOf(t: Ticket): string | null {
  const d = typeof t.dispatched_to === "string" ? t.dispatched_to.trim() : "";
  if (d) return d;
  const f = typeof t.filed_for === "string" ? t.filed_for.trim() : "";
  return f || null;
}

/* -------------------------------------------------------------- the trays -- */

export interface SeatTray {
  seat: string;
  /** Blessed, undispatched: the chair owes this seat a dispatch. */
  awaitingDispatch: Ticket[];
  /** Lessons addressed to this seat that no dispatch has consumed. */
  unconsumedLessons: Ticket[];
  /** Work this seat returned that the chair has not reviewed. The
   *  constitution's missing middle state, finally queryable. */
  outTray: Ticket[];
  /** Currently running under this seat's name. */
  inFlight: Ticket[];
  /** The single oldest thing in the in-tray, in hours, or null if the fold
   *  could not read the ages. NEVER 0 for "nothing waiting" — the caller
   *  distinguishes an empty tray from an unreadable one by the array length. */
  oldestWaitingHours: number | null;
  /** True when this seat's trays are empty because the STATES themselves are
   *  unused across the whole population, not because its queue is clear. */
  note: string;
}

function ageOf(t: Ticket): number | null {
  const h = t.age_in_state_hours;
  return typeof h === "number" && Number.isFinite(h) ? h : null;
}

function oldest(rows: readonly Ticket[]): number | null {
  const ages = rows.map(ageOf).filter((h): h is number => h !== null);
  return ages.length ? Math.max(...ages) : null;
}

/**
 * One seat's trays.
 *
 * TERMINAL TICKETS ARE EXCLUDED FROM EVERY TRAY, unconditionally and before
 * any other filter. A `done` ticket whose state string still reads `approved`
 * cannot exist in the fold, but a future adapter could produce one, and a
 * tray that trusted `state` alone would then show finished work as owed.
 */
export function trayFor(
  seat: string, tickets: readonly Ticket[] | null | undefined,
): SeatTray | null {
  if (!tickets) return null;
  const live = tickets.filter((t) => !isTerminal(t));
  const mine = live.filter((t) => seatOf(t) === seat);

  const awaitingDispatch = mine.filter((t) => t.state === "approved");
  const inFlight = mine.filter((t) => t.state === "in_flight");
  const outTray = mine.filter((t) => t.state === "returned");
  const unconsumedLessons = mine.filter(
    (t) => t.type === "lesson" && t.state !== "in_flight");

  // WHY AN EMPTY TRAY IS EMPTY. Measured across the WHOLE population, not this
  // seat's slice: "nobody has ever used this state" and "this seat's queue is
  // clear" are different facts and only the second is good news.
  const anyReturned = live.some((t) => t.state === "returned");
  const anyLesson = tickets.some((t) => t.type === "lesson");
  const notes: string[] = [];
  if (!outTray.length) {
    notes.push(anyReturned
      ? "nothing of this seat's is awaiting the chair's review"
      : "NO ticket anywhere is in `returned` — the state exists and no door "
        + "has been used yet, so an empty out-tray here says nothing about "
        + "this seat");
  }
  if (!unconsumedLessons.length) {
    notes.push(anyLesson
      ? "no unconsumed lesson is addressed to this seat"
      : "NO `lesson` ticket exists in the record at all — BINDS are still "
        + "carried by hand, so this tray cannot yet be a measurement");
  }

  return {
    seat,
    awaitingDispatch,
    unconsumedLessons,
    outTray,
    inFlight,
    oldestWaitingHours: oldest([...awaitingDispatch, ...unconsumedLessons]),
    note: notes.join("; ") || "both trays hold work",
  };
}

/**
 * Every seat that appears anywhere in the population, with its trays.
 *
 * THE ROSTER COMES FROM THE DATA, NOT FROM A LIST. A hardcoded roster drops a
 * seat the moment one is added — `seat_telemetry` enumerates a map rather than
 * the roster and reports no runs at all for any seat missing from it, which is
 * the same defect one layer down. Sorted by what is waiting, longest first,
 * because that is the order a chair reads it in.
 */
export function allTrays(
  tickets: readonly Ticket[] | null | undefined,
): SeatTray[] | null {
  if (!tickets) return null;
  const seats = new Set<string>();
  for (const t of tickets) {
    const s = seatOf(t);
    if (s) seats.add(s);
  }
  const trays = [...seats]
    .map((s) => trayFor(s, tickets))
    .filter((x): x is SeatTray => x !== null);
  trays.sort((a, b) => {
    const aw = a.awaitingDispatch.length + a.unconsumedLessons.length;
    const bw = b.awaitingDispatch.length + b.unconsumedLessons.length;
    if (aw !== bw) return bw - aw;
    // A TOTAL ORDER, so the board cannot reshuffle between two reads of the
    // same fold: seats tied on volume fall to age, then to name.
    const ao = a.oldestWaitingHours ?? -1, bo = b.oldestWaitingHours ?? -1;
    if (ao !== bo) return bo - ao;
    return a.seat < b.seat ? -1 : 1;
  });
  return trays;
}

/**
 * The chair's own queue: everything RETURNED, oldest first.
 *
 * A ROUNDED FIELD IS NOT A SORT KEY. `age_in_state_hours` rounds to three
 * decimals — 3.6 seconds — so two tickets returned in the same few seconds tie
 * and a stable sort hands their order to whatever the fold produced. The raw
 * instant breaks the tie and the id breaks that, so the order is TOTAL and the
 * "longest ignored" board cannot lead with its newest row.
 */
export function chairQueue(
  tickets: readonly Ticket[] | null | undefined,
): Ticket[] | null {
  if (!tickets) return null;
  const rows = tickets.filter((t) => !isTerminal(t) && t.state === "returned");
  return [...rows].sort((a, b) => {
    const at = lastTransitionAt(a), bt = lastTransitionAt(b);
    if (at !== bt) {
      if (!at) return 1;
      if (!bt) return -1;
      return at < bt ? -1 : 1;
    }
    return a.ticket_id < b.ticket_id ? -1 : 1;
  });
}

/** When this ticket last moved, from the transition list rather than from a
 *  rounded duration. Null when the fold recorded no instant. */
export function lastTransitionAt(t: Ticket): string | null {
  const list = t.transitions ?? [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const at = list[i]?.at;
    if (typeof at === "string" && at.trim()) return at.trim();
  }
  return typeof t.filed_at === "string" && t.filed_at.trim()
    ? t.filed_at.trim() : null;
}
