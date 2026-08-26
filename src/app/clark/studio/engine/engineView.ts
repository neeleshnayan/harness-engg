/**
 * ENGINE — the reading logic behind the page, kept out of JSX so it can be tested.
 *
 * THE QUESTION THIS PAGE EXISTS FOR (CEO, 2026-08-26, verbatim: "Lean should
 * publish to our UI and DB what is filling vs whats not and our books should
 * reconcile", and minutes later "can you also add some UI element that helps me
 * see whats hppening on Lean").
 *
 * A live LEAN session keeps its OWN paper book. It agrees with the fund's book
 * only while every signal it raises is approved — LEAN's paper brokerage fills
 * the algorithm's order internally whatever the fund decides. **The first
 * DECLINED signal makes the two books diverge**, and from then on the engine
 * reasons about a position the fund does not hold. That already happened once
 * on this fund's record (GLD, 2026-08-16) and nothing rendered it.
 *
 * THREE ABSENCES ARE KEPT APART HERE, because collapsing any pair of them is
 * how this page would lie (theme.ts, the illumination principle, clause 2):
 *
 *   1. NO SIGNAL WAS EVER RAISED — a fact about the fund. Not an error, and
 *      not agreement either: nothing was compared.
 *   2. A SIGNAL IS STILL IN THE QUEUE — nobody has decided. Not a failure.
 *   3. THE ENGINE CANNOT BE READ — no session publishes holdings, so its own
 *      book is UNKNOWN. Never zero, and never "in sync".
 *
 * Nothing on this page acts, halts, or crosses a threshold. It is a reading.
 */

// --------------------------------------------------------------- wire shapes

/** The five fates a raised signal can be in. `awaiting` is NOT a failure. */
export type Fate = "filled" | "in_flight" | "awaiting" | "refused" | "failed";

export interface SignalRow {
  order_id: string;
  seq?: number | null;
  raised_at?: string | null;
  source?: string | null;
  algo_id?: string | null;
  reason?: string | null;
  strategy_id?: string | null;
  strategy_name?: string | null;
  symbol?: string | null;
  side?: string | null;
  qty?: number | null;
  venue?: string | null;
  status: string;
  outcome: Fate | string;
  terminal: boolean;
  reached_venue: boolean;
  decided_at?: string | null;
  decided_by?: string | null;
  filled_qty?: number | null;
  avg_price?: number | null;
  filled_at?: string | null;
  failure_reason?: string | null;
  annotations?: { type: string; at?: string | null; actor?: string | null; reason?: string | null }[];
}

export interface LedgerDomain {
  events_scanned: number;
  seq_first?: number | null;
  seq_last?: number | null;
  scan_limit: number;
  window_bound: boolean;
}

export interface SignalLedger {
  signals: SignalRow[];
  counts: Record<Fate, number>;
  total: number;
  returned: number;
  sources: string[];
  last_signal_at?: string | null;
  domain: LedgerDomain;
}

export interface EngineSymbolRow {
  strategy_id?: string | null;
  strategy_name?: string | null;
  symbol: string;
  book_qty: number | null;
  engine_qty: number | null;
  engine_implied_qty: number | null;
  /** True when at least one signal on this (strategy, symbol) carries no
   *  quantity, so the implied position is UNKNOWN rather than a partial sum.
   *  Without this field a null implied quantity would read as "the engine has
   *  not signalled here", which is the opposite of what it means. */
  implied_unquantified?: boolean;
  drift: number | null;
  /** THREE-VALUED. `null` is "cannot tell" and must never render as agreement. */
  in_sync: boolean | null;
  signals?: Record<string, number>;
  other_fills?: number;
}

export interface EngineLeg {
  readable?: boolean;
  direct?: {
    readable: boolean;
    qty_basis: string;
    sessions: number;
    sessions_running: number;
    reason: string;
    would_need: string;
  };
  implied?: {
    basis: string;
    is_model: boolean;
    model: string;
    per_symbol: EngineSymbolRow[];
    symbols_out_of_sync: number;
    symbols_undetermined: number;
    book_readable: boolean;
    book_unreadable_reason?: string | null;
  };
  signals_raised?: number;
  signals_not_filled?: number;
  verdict: { state: string; sentence: string; symbols?: string[] };
  domain?: LedgerDomain;
}

export interface EngineSession {
  session_id?: string | null;
  algorithm?: string | null;
  strategy_id?: string | null;
  state?: string | null;
  started_at?: string | null;
  stopped_at?: string | null;
  signal_configured?: boolean | null;
  error?: string | null;
  log_tail?: string[];
  log_tail_pending?: boolean;
}

export interface EngineStatus {
  state: string;
  note: string;
  sessions: EngineSession[];
  sessions_readable?: boolean;
  /** The exception text, added by the endpoint — the only layer that saw it.
   *  The STATE is the module's; only the CAUSE is the endpoint's. */
  sessions_error?: string | null;
  last_signal_at?: string | null;
  last_signal_scope: string;
  last_bar_seen: string | null;
  last_bar_seen_note: string;
  liveness_provable: boolean | null;
  liveness_note: string;
}

export interface EngineView {
  status: EngineStatus;
  ledger: SignalLedger;
  reconcile: EngineLeg;
}

// ------------------------------------------------------------------- fates

/** The tone vocabulary this page draws from — deliberately small. */
export type Tone = "good" | "warn" | "bad" | "quiet" | "neutral";

export const FATE_ORDER: Fate[] = ["filled", "in_flight", "awaiting", "refused", "failed"];

export const FATE_LABEL: Record<Fate, string> = {
  filled: "Filled",
  in_flight: "In flight",
  awaiting: "Awaiting a click",
  refused: "Refused",
  failed: "Failed",
};

/**
 * One sentence each, because the whole point of the page is that these five
 * are DIFFERENT. "Awaiting" beside "Failed" with no explanation is how a
 * reader learns to treat a queue as an outage.
 */
export const FATE_HELP: Record<Fate, string> = {
  filled: "Approved, sent, and filled. The fund's book moved.",
  in_flight: "Approved and on its way — not yet a fill, not a failure.",
  awaiting: "Sitting in the approval queue. Nobody has decided yet; this is not a failure.",
  refused: "Somebody or the risk gate said no. A decision was taken.",
  failed: "It reached the venue and did not complete.",
};

/**
 * `1 signal` / `2 signals`. Not cosmetic: these sentences are the surface the
 * CEO reads, and "1 signal(s)" is the tell of a number formatted by a machine
 * that did not look at it. It shipped in the first draft of this page.
 */
export function plural(n: number, word: string, pluralForm?: string): string {
  return `${n} ${n === 1 ? word : (pluralForm ?? word + "s")}`;
}

export function fateTone(fate: Fate | string): Tone {
  switch (fate) {
    case "filled": return "good";
    case "in_flight": return "neutral";
    case "awaiting": return "warn";
    // A refusal is a DECISION somebody took, not an absence. It was "quiet"
    // until the look-pass: on the live reading the only non-zero count in the
    // row was REFUSED, and it rendered as the dimmest thing on the strip while
    // four zeros shouted in colour.
    case "refused": return "neutral";
    case "failed": return "bad";
    default: return "quiet";
  }
}

/**
 * The tone for a COUNT, which is not the tone for its bucket.
 *
 * MEASURED DEFECT (look-pass, 2026-08-26): the fate strip toned each figure by
 * its bucket alone, so on the live reading — 0/0/0/1/0 — the four ZEROS
 * rendered in green, amber and red while the single real count sat in the
 * muted grey. The eye went to the absences. An amber "awaiting a click" at
 * zero also asserts a queue that is empty.
 *
 * So: a zero is quiet, whatever bucket it is in; a count carries its bucket's
 * meaning. Nothing is hidden — the label and its sentence are unchanged — but
 * the emphasis follows the fact rather than the category.
 */
export function countTone(fate: Fate | string, n: number): Tone {
  return n === 0 ? "quiet" : fateTone(fate);
}

export interface FateBucket {
  fate: Fate;
  label: string;
  help: string;
  n: number;
  /** The bucket's own meaning — used for a row's chip, where the fact is the
   *  fate rather than a count. */
  tone: Tone;
  /** The tone for the FIGURE. See countTone: a zero is quiet whatever bucket
   *  it sits in, or the absences out-shout the facts. */
  countTone: Tone;
}

/**
 * All five buckets, always, zero included.
 *
 * A bucket that disappears when it is empty makes "no signal was refused" and
 * "this reading does not report refusals" the same rendering — which is the
 * absence-as-zero defect wearing a layout.
 */
export function fateBuckets(ledger: SignalLedger | null | undefined): FateBucket[] {
  const counts = ledger?.counts;
  return FATE_ORDER.map((fate) => ({
    fate,
    label: FATE_LABEL[fate],
    help: FATE_HELP[fate],
    n: counts ? (counts[fate] ?? 0) : 0,
    tone: fateTone(fate),
    countTone: countTone(fate, counts ? (counts[fate] ?? 0) : 0),
  }));
}

/**
 * The sentence for a ledger with no rows — never an empty table with no words.
 *
 * Returns `null` when there ARE rows, so the caller renders the table instead.
 * The domain rides along because a count without its domain is not a result:
 * "no engine has ever raised a signal" and "the window this read covered does
 * not reach the one that was raised" are different facts.
 */
export function ledgerAbsence(ledger: SignalLedger | null | undefined): string | null {
  if (!ledger) return null;
  if (ledger.total > 0) return null;
  const d = ledger.domain;
  const scanned = d ? `${d.events_scanned.toLocaleString()} events` : "the record";
  if (d?.window_bound) {
    return `No engine signal in the ${scanned} this read covered — and the window BOUND at ` +
      `${d.scan_limit.toLocaleString()}, so an older signal would be unread rather than absent.`;
  }
  return `No engine has ever raised a signal. Read over ${scanned}` +
    (d?.seq_first != null && d?.seq_last != null ? ` (seq ${d.seq_first}–${d.seq_last})` : "") +
    ". Nothing was raised, which is not the same as nothing being wrong.";
}

/** Truncation is a word, never a silently shorter list. */
export function ledgerTruncation(ledger: SignalLedger | null | undefined): string | null {
  if (!ledger) return null;
  if (ledger.returned >= ledger.total) return null;
  return `Showing ${ledger.returned} of ${plural(ledger.total, "signal")}.`;
}

// ------------------------------------------------------------ reconciliation

/** The word for a three-valued sync flag. `null` is never "in sync". */
export function syncWord(inSync: boolean | null | undefined): string {
  if (inSync === true) return "in sync";
  if (inSync === false) return "DIVERGED";
  return "cannot tell";
}

export function syncTone(inSync: boolean | null | undefined): Tone {
  if (inSync === true) return "good";
  if (inSync === false) return "bad";
  return "warn";
}

/**
 * The headline for the third leg: one word, one sentence, one tone.
 *
 * `no_signals` is deliberately NOT "good". A fund that has never run an engine
 * has not reconciled its engine against its book; it has nothing to reconcile,
 * and colouring that green would teach the reader that the leg is passing.
 */
export function reconcileHeadline(leg: EngineLeg | null | undefined):
  { word: string; sentence: string; tone: Tone } {
  if (!leg) {
    return {
      word: "UNREAD",
      sentence: "The engine leg has not been read.",
      tone: "warn",
    };
  }
  const state = leg.verdict?.state ?? "unknown";
  const sentence = leg.verdict?.sentence ?? "No sentence was returned with this verdict.";
  switch (state) {
    case "in_sync": return { word: "IN SYNC", sentence, tone: "good" };
    case "diverged": return { word: "DIVERGED", sentence, tone: "bad" };
    case "no_signals": return { word: "NOTHING TO COMPARE", sentence, tone: "quiet" };
    case "unreadable": return { word: "UNREADABLE", sentence, tone: "warn" };
    default: return { word: "UNKNOWN", sentence, tone: "warn" };
  }
}

/**
 * The caveat that must ride with every number in this leg, in one sentence.
 *
 * The engine's own book is NOT what is being shown: it cannot be read. What is
 * shown is the book its signals IMPLY under a stated model. A page that let
 * the reader believe otherwise would be claiming a measurement it never took.
 */
export function impliedCaveat(leg: EngineLeg | null | undefined): string | null {
  const direct = leg?.direct;
  if (!direct) return null;
  if (direct.readable) return null;
  // "The quantities below" is only true when there ARE quantities below. On
  // the no-signals arm the caveat rendered over an empty table, promising a
  // reading of something that was not on screen — found by looking at that
  // arm, 2026-08-26. The UNKNOWN half stays either way: the engine's book is
  // unreadable whether or not it has ever signalled, and that is the fact
  // this sentence exists to carry.
  const hasRows = (leg?.implied?.per_symbol?.length ?? 0) > 0;
  const model = hasRows
    ? ` The quantities below are what its signals IMPLY, not what it reports.`
    : ` Nothing has been signalled, so there is no implied position to show either.`;
  return `The engine's own holdings are UNKNOWN — ${direct.reason}${model}` +
    ` To read them directly: ${direct.would_need}.`;
}

/** Rows worth a reader's eye first: disagreements, then undetermined, then rest. */
export function sortedSymbolRows(leg: EngineLeg | null | undefined): EngineSymbolRow[] {
  const rows = leg?.implied?.per_symbol ?? [];
  const rank = (r: EngineSymbolRow) => (r.in_sync === false ? 0 : r.in_sync === null ? 1 : 2);
  return [...rows].sort((a, b) => rank(a) - rank(b) || a.symbol.localeCompare(b.symbol));
}

/**
 * Why a row disagrees, in the row's own numbers — or `null` when it does not.
 *
 * Names the OTHER possible cause too. A drift on a (strategy, symbol) that
 * also carries hand-staged fills is not necessarily the engine's story, and a
 * page that always blames the engine is a page that will be wrong loudly.
 */
export function driftExplanation(row: EngineSymbolRow): string | null {
  // An unquantified row is not a disagreement — it is an unanswered question,
  // and it needs its own sentence rather than the silence of a `null`.
  if (row.implied_unquantified) {
    return "At least one signal on this symbol carries no quantity, so what " +
      "the engine implies it holds cannot be summed. This is not a " +
      "disagreement; it is an unanswered question.";
  }
  if (row.in_sync !== false) return null;
  const unfilled = (row.signals?.raised ?? 0) - (row.signals?.filled ?? 0);
  const parts: string[] = [];
  if (unfilled > 0) {
    parts.push(`${unfilled} of ${plural(row.signals?.raised ?? 0, "signal")} on this symbol never filled`);
  }
  if ((row.other_fills ?? 0) > 0) {
    parts.push(`${plural(row.other_fills ?? 0, "fill")} on this strategy came from somewhere other than the engine`);
  }
  if (parts.length === 0) return "The two books disagree and no signal or outside fill explains it.";
  return `${parts.join("; ")}.`;
}

// -------------------------------------------------------------- engine status

/**
 * Is the engine doing anything, and can we tell?
 *
 * **NO SESSION IS NOT AN ALARM.** `GET /fund/lean/live` has returned an empty
 * list for the whole life of this fund because a live session has never been
 * started. Rendering that in the warn tone would train its reader to ignore
 * the one day it means something.
 *
 * **SILENCE IS NOT EVIDENCE, IN EITHER DIRECTION.** On daily bars a healthy
 * algorithm speaks once a day at most. So a running session gets a truthful
 * "cannot tell" rather than a green light or a red one.
 */
export function engineHeadline(status: EngineStatus | null | undefined):
  { word: string; sentence: string; tone: Tone } {
  if (!status) {
    return { word: "UNREAD", sentence: "The engine has not been read.", tone: "warn" };
  }
  switch (status.state) {
    case "no_session":
      return { word: "NOT RUNNING", sentence: status.note, tone: "quiet" };
    case "running":
      return { word: "RUNNING", sentence: status.note, tone: "neutral" };
    case "failed":
      return { word: "FAILED", sentence: status.note, tone: "bad" };
    case "stopped":
      return { word: "STOPPED", sentence: status.note, tone: "quiet" };
    default:
      return { word: "UNKNOWN", sentence: status.note, tone: "warn" };
  }
}

/**
 * What this page CANNOT tell you, listed as words.
 *
 * Clause 2 of the illumination principle applied to a page whose subject is
 * mostly unreadable today: the honest surface names its own blind spots rather
 * than leaving blank regions the reader fills in optimistically.
 */
export function unknownsList(view: EngineView | null | undefined): string[] {
  if (!view) return [];
  const out: string[] = [];
  const direct = view.reconcile?.direct;
  if (direct && !direct.readable) {
    out.push(`What the engine itself holds — ${direct.reason}`);
  }
  // Only where the question arises. With no session ever started there is no
  // "bar the engine last processed" to be missing, and listing it would pad
  // the honest list with a non-question — which is its own way of hiding the
  // real entries.
  if (view.status && view.status.state !== "no_session" && view.status.last_bar_seen == null) {
    out.push(view.status.last_bar_seen_note ?? "The bar the engine last processed — UNKNOWN.");
  }
  if (view.status?.liveness_provable === false) {
    out.push(view.status.liveness_note);
  }
  if (view.status?.sessions_readable === false) {
    out.push("Whether any session is running — the live-session list could not be read.");
  }
  if (view.reconcile?.implied?.book_readable === false) {
    out.push(`The fund's own per-strategy book — ${view.reconcile.implied.book_unreadable_reason}`);
  }
  return out;
}

/**
 * The venue every engine signal is proposed against, and why saying so matters.
 *
 * `POST /fund/signals/external` builds its Order with `venue="paper"` — a
 * hardcoded literal, and a separate CEO decision that is open on his desk at
 * the time of writing. While it stands, an engine signal that IS approved and
 * DOES fill fills against the in-process paper simulator and never reaches
 * Alpaca. This page's job is to make that consequence visible, not to change
 * it: a "filled" row here is not evidence of a real fill.
 */
export function venueNote(ledger: SignalLedger | null | undefined): string | null {
  const venues = new Set(
    (ledger?.signals ?? []).map((s) => (s.venue ?? "").trim()).filter(Boolean),
  );
  if (venues.size === 0) return null;
  if (venues.size === 1 && venues.has("paper")) {
    return "Every engine signal on this record was proposed against the PAPER venue — " +
      "a fill here is a simulator fill and carries no cost information.";
  }
  return `Engine signals on this record name ${[...venues].sort().join(", ")}.`;
}
