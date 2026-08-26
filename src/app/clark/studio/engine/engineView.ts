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
  /** Whether this signal still testifies about a LIVE engine's book. Absent
   *  when the reading had no way to ask what is running — which is NOT the
   *  same as `false`, and is why this is optional rather than defaulted. */
  fenced?: boolean;
  liveness?: SignalLiveness;
}

/** Why a signal was or was not counted as live, from the spine's own fold.
 *  `basis` is a stable token (`claimed_by_live_session`,
 *  `predates_session_memory`, …) so a surface can key off it without parsing
 *  a sentence, and `reason` is the sentence a human reads. */
export interface SignalLiveness {
  state: "live" | "fenced" | string;
  basis: string;
  reason?: string | null;
  session_id?: string | null;
  session_algorithm?: string | null;
}

/** What the fence could and could not read. A count without its domain is not
 *  a result, and this fence's domain is "what did we manage to ask". */
export interface FenceDomain {
  version: string;
  sessions_readable: boolean;
  sessions: number | null;
  sessions_running: number | null;
  sessions_known_since: string | null;
  archived_readable: boolean;
  archived_strategies: number | null;
  /** Whether anything asked DOCKER what is running, as opposed to asking the
   *  runner's in-memory session table. Nothing does, and the payload says so
   *  rather than letting a reader conclude it was checked. */
  orphan_containers_checked?: boolean;
  orphan_note?: string;
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
  /** Five fates plus `unclassified` — see `unclassifiedNote`. Typed as a loose
   *  record rather than `Record<Fate, number>` so a bucket the spine adds
   *  later is carried rather than dropped at the type boundary. */
  counts: Record<string, number>;
  /** THREE-VALUED. `null` means the reading had no way to ask what is running,
   *  so it has not established that nothing is fenced — it has not asked. */
  fenced: number | null;
  live: number | null;
  fence: FenceDomain | null;
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
  /** THREE-VALUED. `null` is "cannot tell" and must never render as agreement.
   *  It now carries TWO different reasons — an unreadable book and a fenced
   *  row — so `sync_state` is the field to switch on. This one is kept because
   *  it is still the honest boolean answer to "do they agree". */
  in_sync: boolean | null;
  /** FOUR-VALUED, and the discriminator every renderer uses:
   *  `in_sync` | `diverged` | `undetermined` | `fenced_history`. */
  sync_state?: string;
  /** True when every signal on this (strategy, symbol) came from a session
   *  that no longer exists. The row is HISTORY, not a disagreement now. */
  fenced?: boolean;
  fence_reason?: string | null;
  /** What the DEAD engine had asked for — preserved beside the live reading,
   *  never merged into it and never dropped. */
  fenced_implied_qty?: number | null;
  signals_live?: number;
  signals_fenced?: number;
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
    symbols_in_sync?: number;
    symbols_fenced?: number;
    book_readable: boolean;
    book_unreadable_reason?: string | null;
  };
  signals_raised?: number;
  signals_not_filled?: number;
  signals_fenced?: number;
  signals_live?: number;
  fence?: FenceDomain;
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

/** One engine strategy, joined from four places that never met: the registry
 *  (name, state, allocation), the strategy's own `definition` (rule,
 *  algorithm), the ALGORITHM FILE (the only thing that knows the datasource)
 *  and the event log (what it has actually said). */
export interface EngineStrategyCard {
  strategy_id: string;
  name?: string | null;
  engine: string;
  state?: string | null;
  archived: boolean;
  allocation_pct?: number | null;
  algorithm?: string | null;
  /** The class LEAN will instantiate, read from the FILE. */
  class_name?: string | null;
  /** What the definition SAYS the class is. Carried separately and never
   *  merged, so a definition that has drifted from its file is visible. */
  class_in_definition?: string | null;
  rule?: string | null;
  purpose?: string | null;
  claim_type?: string | null;
  signal_only?: boolean | null;
  assets: string[];
  /** WHICH field answered — `strategy.assets`, `definition.universe`,
   *  `definition.symbol`, or `null` when none did. An empty list WITH a basis
   *  would claim a field was read and found empty. */
  assets_basis?: string | null;
  datasource: EngineDatasource;
  /** THREE-VALUED: `running` | `stopped` | `none`, and `null` for "the session
   *  list could not be read", which is not "nothing is running". */
  session_state?: string | null;
  sessions?: EngineSession[];
  signals?: Record<string, number>;
  signals_fenced?: number;
  last_signal?: SignalRow | null;
  definition_keys?: string[];
}

/** What an algorithm says it subscribes to, read statically from its source.
 *  Every field is independently optional: an unreadable one is `null` with the
 *  reason on the payload, never a plausible default. */
export interface EngineDatasource {
  readable: boolean;
  reason?: string | null;
  class_name?: string | null;
  base?: string | null;
  resolution?: string | null;
  transport?: string | null;
  feed_path?: string | null;
  feed_origin?: string | null;
  lookback_days?: number | null;
  format?: string | null;
  symbols?: string[];
}

export interface EngineStrategies {
  readable: boolean;
  reason?: string | null;
  strategies: EngineStrategyCard[];
  total: number | null;
  archived: number | null;
  engines?: string[];
  /** A live session no card accounts for. Empty is the normal case; a
   *  non-empty list means something is running the registry cannot explain. */
  sessions_unmatched?: EngineSession[];
}

export interface EngineView {
  status: EngineStatus;
  ledger: SignalLedger;
  reconcile: EngineLeg;
  strategies?: EngineStrategies;
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

/**
 * The sentence for signals whose lifecycle this stack has no word for.
 *
 * The spine buckets an order event it cannot name into `unclassified` so that
 * `sum(counts) == total` holds. If the page then rendered only the five known
 * fates, the header would count a signal the strip never showed — the same
 * defect, one layer up. Returns `null` when the count is zero, because a
 * standing sentence about a thing that has never happened is noise.
 */
export function unclassifiedNote(ledger: SignalLedger | null | undefined): string | null {
  const n = ledger?.counts?.unclassified ?? 0;
  if (n <= 0) return null;
  return `${plural(n, "signal")} reached a state this page has no word for. ` +
    `They are counted in the total above and shown in the list below, and the ` +
    `vocabulary needs extending — not the count.`;
}

/** Truncation is a word, never a silently shorter list. */
export function ledgerTruncation(ledger: SignalLedger | null | undefined): string | null {
  if (!ledger) return null;
  if (ledger.returned >= ledger.total) return null;
  return `Showing ${ledger.returned} of ${plural(ledger.total, "signal")}.`;
}

// ------------------------------------------------------------ reconciliation

/**
 * The word and the tone for a row's sync state — ONE function over the FOUR
 * values the spine computes, replacing the pair of three-valued helpers this
 * page shipped with.
 *
 * WHY THE PAIR HAD TO GO. Both read `in_sync`, whose `null` used to mean
 * exactly one thing ("the book could not be read") and now means two, because
 * a FENCED row has no live engine behind it and so has no live quantity to
 * compare. Rendering both as "cannot tell" in the warn tone would put an amber
 * alarm on a row whose entire content is "this is history, and here is why" —
 * and would hide the one case that IS an alarm behind the one that is not.
 *
 * FENCED IS DELIBERATELY `quiet`, NOT `good`. Nothing was compared, so nothing
 * agreed. Colouring it green would teach the reader that the leg is passing.
 */
export function syncLabel(state: string | null | undefined):
  { word: string; tone: Tone } {
  switch (state) {
    case "in_sync": return { word: "in sync", tone: "good" };
    case "diverged": return { word: "DIVERGED", tone: "bad" };
    case "fenced_history": return { word: "fenced history", tone: "quiet" };
    default: return { word: "cannot tell", tone: "warn" };
  }
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
    // FENCED HISTORY IS NOT A PASS AND NOT A FAILURE. Every symbol the engine
    // signalled on was signalled by a session that no longer exists, so there
    // is real history here and no live disagreement. `quiet` for the same
    // reason `no_signals` is quiet: colouring an uncompared thing green
    // teaches the reader that the leg is passing.
    case "fenced_history": return { word: "HISTORY ONLY", sentence, tone: "quiet" };
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

const SYNC_RANK: Record<string, number> = {
  diverged: 0, undetermined: 1, in_sync: 2, fenced_history: 3,
};

/**
 * Rows worth a reader's eye first: live disagreements, then undetermined, then
 * agreement, then fenced history LAST.
 *
 * Ranks on `sync_state` rather than on `in_sync`, because the two rows whose
 * `in_sync` is `null` — an unreadable book and a fenced history row — belong
 * at opposite ends of this list. The old rank put fenced history second, above
 * every symbol that actually agrees.
 */
export function sortedSymbolRows(leg: EngineLeg | null | undefined): EngineSymbolRow[] {
  const rows = leg?.implied?.per_symbol ?? [];
  const rank = (r: EngineSymbolRow) =>
    SYNC_RANK[r.sync_state ?? ""] ?? (r.in_sync === false ? 0 : r.in_sync === null ? 1 : 2);
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
  // A FENCED ROW'S SENTENCE IS THE FENCE'S REASON, and it comes FIRST. Falling
  // through to the drift branches would print "the two books disagree" over a
  // row where no comparison was made, which is the opposite of what fencing
  // established. The reason is the spine's, derived from the record.
  if (row.fenced) {
    const had = row.fenced_implied_qty;
    const asked = had == null
      ? "What it had asked for cannot be summed."
      : `The dead session had asked for ${had}; the fund's book holds ` +
        `${row.book_qty ?? "an unreadable quantity"}.`;
    return `${row.fence_reason ?? "This signal came from a session that no longer exists."} ` +
      `${asked} Kept here as history, not counted as a disagreement.`;
  }
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
  // WHICH session raised a fenced signal, and therefore what the dead engine
  // actually held. Only listed when something IS fenced: a standing sentence
  // about a thing that has not happened pads the honest list, which is its own
  // way of hiding the real entries.
  if ((view.reconcile?.implied?.symbols_fenced ?? 0) > 0) {
    out.push(
      "Which session raised each fenced signal — a signal carries no session " +
      "id, so the fence proves only that NO session on record could have " +
      "raised it, never which one did.");
  }
  if ((view.strategies?.sessions_unmatched?.length ?? 0) > 0) {
    out.push(
      `What ${plural(view.strategies?.sessions_unmatched?.length ?? 0, "live session")} ` +
      `${(view.strategies?.sessions_unmatched?.length ?? 0) === 1 ? "is" : "are"} ` +
      "running — no registered strategy accounts for it.");
  }
  if (view.strategies?.readable === false) {
    out.push(`Which strategies are engine-run — ${view.strategies.reason}`);
  }
  return out;
}

// ------------------------------------------------------------ the fence

/**
 * The sentence that explains WHY rows are missing from the divergence count.
 *
 * A number without its domain is not a result, and the fence removes rows from
 * a verdict the CEO reads. So the count of fenced rows and the anchor it was
 * judged against are stated on the panel, not left in the payload — otherwise
 * "0 symbols disagree" and "3 were excluded from that 0" render identically.
 *
 * Returns `null` when nothing is fenced: a standing explanation of a mechanism
 * that has not fired is noise.
 */
export function fenceNote(leg: EngineLeg | null | undefined): string | null {
  const n = leg?.implied?.symbols_fenced ?? 0;
  if (n <= 0) return null;
  const since = leg?.fence?.sessions_known_since;
  const when = since
    ? ` The engine runner's session memory begins at ${since}; nothing raised before that can have a session on record.`
    : "";
  return `${plural(n, "symbol")} ${n === 1 ? "is" : "are"} FENCED HISTORY and ` +
    `${n === 1 ? "is" : "are"} not counted in the verdict above. A LEAN ` +
    `container starts flat, so signals from a session that no longer exists ` +
    `describe a paper book that is gone.${when}`;
}

/**
 * What the fence could NOT read — the loosening's own honesty check.
 *
 * Fencing removes rows from a divergence verdict, so a reader is entitled to
 * know when the mechanism was working with less than it wanted. Both inputs
 * are three-valued and either being unreadable makes the fence prove less, in
 * the SAFE direction (fewer fences, not more).
 */
export function fenceBlindSpots(leg: EngineLeg | null | undefined): string[] {
  const f = leg?.fence;
  if (!f) return [];
  const out: string[] = [];
  if (f.sessions_readable === false) {
    out.push("The live-session list could not be read, so nothing was fenced — " +
      "every signal is being judged as if its engine might still be running.");
  }
  if (f.archived_readable === false) {
    out.push("The strategy registry could not be read, so no fence reason can " +
      "say whether a strategy was archived.");
  }
  if (!f.sessions_known_since) {
    out.push("The engine runner could not say when its session memory began, " +
      "so no signal can be placed before it and nothing was fenced.");
  }
  // THE RESIDUAL, SHOWN WHENEVER THE FENCE ACTUALLY FIRED. A blind spot that
  // rides in the payload and is never rendered has not been published. It is
  // conditioned on something BEING fenced because the limit only matters once
  // a row has been removed from the verdict on this proof — a standing
  // sentence about an unfired mechanism is the padding that hides real
  // entries.
  if (f.orphan_containers_checked === false
      && (leg?.implied?.symbols_fenced ?? 0) > 0) {
    out.push(f.orphan_note ?? "Nothing asked Docker what is running, so a " +
      "container that went quiet before the last restart is fenced and cannot " +
      "be told from a dead one.");
  }
  return out;
}

/** Venues whose fills carry no cost information: the in-process simulator
 *  fills at our own quote by construction. `alpaca` is the broker's paper
 *  account and DOES produce a real fill against a real book. */
const SIMULATED_VENUES = new Set(["paper", "sim", "simulator"]);

/**
 * The venue every engine signal was proposed against, and why saying so matters.
 *
 * **THE HISTORY IS MIXED, AND THIS SENTENCE IS DERIVED RATHER THAN ASSERTED.**
 * `POST /fund/signals/external` proposed on `venue="paper"` from birth — the
 * in-process simulator, filling at our own quote and carrying zero cost
 * information. On 2026-08-26/27 the CEO changed that to `alpaca`, the broker's
 * paper account, so from that point an engine fill means what every other fill
 * in this fund means. The rows on either side of the change are BOTH on the
 * record and always will be, which is why this reads the venues off the
 * signals instead of stating one: a sentence naming a single venue would have
 * been correct on the day it was written and quietly wrong the next.
 *
 * What it must never do is let a simulated fill read as a real one. A "filled"
 * row on the paper venue is not evidence that anything reached a broker.
 */
export function venueNote(ledger: SignalLedger | null | undefined): string | null {
  const venues = [...new Set(
    (ledger?.signals ?? []).map((s) => (s.venue ?? "").trim().toLowerCase()).filter(Boolean),
  )].sort();
  if (venues.length === 0) return null;
  const simulated = venues.filter((v) => SIMULATED_VENUES.has(v));
  const real = venues.filter((v) => !SIMULATED_VENUES.has(v));
  if (real.length === 0) {
    return `Every engine signal on this record was proposed against the ` +
      `${venues.join(", ").toUpperCase()} venue — a fill here is a simulator ` +
      `fill and carries no cost information.`;
  }
  if (simulated.length === 0) {
    return `Every engine signal on this record was proposed against ` +
      `${real.join(", ")} — a fill here is a real fill at the broker.`;
  }
  const n = (ledger?.signals ?? []).filter(
    (s) => SIMULATED_VENUES.has((s.venue ?? "").trim().toLowerCase())).length;
  return `This record spans a venue change: ${plural(n, "signal")} ` +
    `${n === 1 ? "was" : "were"} proposed against ${simulated.join(", ")} — ` +
    `the in-process simulator, whose fills carry no cost information — and the ` +
    `rest against ${real.join(", ")}. A "filled" row is only evidence of a real ` +
    `fill on the second kind.`;
}

// -------------------------------------------------- the strategy cards

/**
 * ENGINE STRATEGIES — the CEO's quick-sense panel (2026-08-26, verbatim: "I
 * would like to see which datasource; which asset; which strategy which
 * signals etc etc to get a quick sense and imo most of our early work will be
 * algorithmic").
 *
 * Four facts about one strategy lived in four places and nothing joined them.
 * These helpers turn the joined payload into words — and where a join could
 * not be made, into a NAMED absence rather than a blank the reader fills in.
 */

/** The datasource in one line, or an honest absence. Never a default. */
export function datasourceLine(ds: EngineDatasource | null | undefined): string {
  if (!ds || !ds.readable) {
    return ds?.reason ?? "The algorithm's feed could not be read — UNKNOWN, not none.";
  }
  const bits: string[] = [];
  if (ds.class_name) bits.push(ds.class_name);
  if (ds.resolution) bits.push(`${ds.resolution} bars`);
  if (ds.feed_path) bits.push(`${ds.feed_origin ?? ""}${ds.feed_path}`);
  if (ds.format) bits.push(ds.format.toUpperCase());
  // The lookback is the field most likely to differ between two algorithms
  // that otherwise look identical — the two on this fund's record ask for 700
  // and 2000 — so it is always shown when it is known, and named when it is
  // not rather than dropped into the gap where a reader assumes a default.
  bits.push(ds.lookback_days != null
    ? `${ds.lookback_days}-day window`
    : "window NOT DECLARED");
  return bits.join(" · ");
}

/** The symbols, with the field that answered — or a named absence. */
export function assetsLine(card: EngineStrategyCard): string {
  if (!card.assets?.length) {
    return "No field on this strategy names a symbol.";
  }
  const basis = card.assets_basis ? ` (from ${card.assets_basis})` : "";
  return `${card.assets.join(" · ")}${basis}`;
}

/** Is this strategy's engine running, and can we tell. THREE-VALUED. */
export function sessionLabel(card: EngineStrategyCard): { word: string; tone: Tone } {
  switch (card.session_state) {
    case "running": return { word: "SESSION RUNNING", tone: "neutral" };
    case "stopped": return { word: "session stopped", tone: "quiet" };
    case "none": return { word: "no session", tone: "quiet" };
    // `null`/undefined: the list could not be read. NOT "no session" — an
    // engine we cannot ask about may be doing anything.
    default: return { word: "session UNKNOWN", tone: "warn" };
  }
}

/**
 * The class LEAN will run, and a warning when the definition disagrees.
 *
 * The two are carried separately by the spine precisely so this can be
 * detected; merging them with an `or` would hide a definition that has drifted
 * from its file behind a plausible name.
 */
export function classLine(card: EngineStrategyCard): string {
  const file = card.class_name;
  const declared = card.class_in_definition;
  if (file && declared && file !== declared) {
    return `${file} — the DEFINITION says ${declared}; the file is what runs.`;
  }
  if (file) return file;
  if (declared) return `${declared} (from the definition; the algorithm file could not be read)`;
  return "class UNKNOWN";
}

/** Live strategies first, archived last, each group by name. */
export function sortedCards(s: EngineStrategies | null | undefined): EngineStrategyCard[] {
  return [...(s?.strategies ?? [])].sort(
    (a, b) => Number(a.archived) - Number(b.archived) ||
      (a.name ?? "").localeCompare(b.name ?? ""));
}

/**
 * The sentence for a panel with no cards — and it distinguishes the two
 * reasons, which is the whole point.
 *
 * `readable: false` is "the registry could not be read": UNKNOWN algorithms,
 * not none. An empty readable list is a fact about the fund.
 */
export function strategiesAbsence(s: EngineStrategies | null | undefined): string | null {
  if (!s) return "The engine strategies have not been read.";
  if (!s.readable) {
    return s.reason ?? "Which strategies are engine-run could not be read — UNKNOWN, not none.";
  }
  if ((s.strategies?.length ?? 0) > 0) return null;
  return "No strategy on this fund declares an engine. Every strategy here is " +
    "hand-managed; nothing is algorithmic yet.";
}

/**
 * A live session no registered strategy accounts for.
 *
 * The loudest thing this payload can carry, and it gets its own sentence: it
 * means something is running that the registry cannot explain, and it is the
 * SAME evidence the fence refuses to read as death. Returns `null` in the
 * normal case, so the sentence appears only when it is a finding.
 */
export function unmatchedSessionNote(s: EngineStrategies | null | undefined): string | null {
  const n = s?.sessions_unmatched?.length ?? 0;
  if (n <= 0) return null;
  const names = (s?.sessions_unmatched ?? [])
    .map((x) => x.algorithm ?? x.session_id ?? "unnamed").join(", ");
  return `${plural(n, "live session")} ${n === 1 ? "is" : "are"} running that no ` +
    `registered strategy accounts for (${names}). Its signals cannot be ` +
    `attributed, and it is running outside anything this page can describe.`;
}

/** The fate strip for ONE strategy — same vocabulary as the ledger's. */
export function cardBuckets(card: EngineStrategyCard): FateBucket[] {
  const counts = card.signals ?? {};
  return FATE_ORDER.map((fate) => ({
    fate,
    label: FATE_LABEL[fate],
    help: FATE_HELP[fate],
    n: counts[fate] ?? 0,
    tone: fateTone(fate),
    countTone: countTone(fate, counts[fate] ?? 0),
  }));
}
