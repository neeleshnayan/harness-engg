/**
 * ENGINE STRATEGIES ON ALLOCATE — the inclusion rule, and the honest label.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * WHY THIS FILE EXISTS (CEO, 2026-08-27, verbatim: *"allocate doesnt show the
 * lean strategies"*).
 *
 * MEASURED ON THE LIVE FUND, 2026-08-27, and the picture is worse than the
 * sentence. Allocate folds its strategy list into two populations —
 * `book` (deployed OR holding) and `bench` (everything else, archived
 * excluded). Against the live spine that day:
 *
 *   · `LEAN - HYG fast flip probe` — state `draft`, allocation 0%, exposure $0,
 *     **and a LEAN session RUNNING since 20:42Z**. It fell to the BENCH, under
 *     a heading that reads *"not carrying capital"*. True of the fund's book,
 *     and it says nothing about the fact that the engine was trading it.
 *   · `LEAN - GLD 100d SMA filter` — ARCHIVED, and therefore filtered out of
 *     both populations. **Invisible.** It is also the one strategy on this
 *     fund's whole record that ever raised a signal, and the one whose engine
 *     book diverged from the fund's.
 *
 * SO THE FIX IS AN INCLUSION RULE, NOT A BADGE. kp8 added an ENGINE badge, and
 * a badge can only decorate a row that already renders. **Any strategy whose
 * `definition.engine` is set gets a row here, whatever its state, whatever its
 * allocation, archived or not** — with its live session state beside it.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * THE LABEL IS THE OTHER HALF, and it is the half that touches money.
 *
 * A running engine with a zero allocation is NOT a position. LEAN's live-paper
 * brokerage fills the algorithm's order internally whatever the fund decides;
 * the fund's book moves only when a signal is approved and filled. So the row
 * says *"trading via engine · unallocated"* and the note says the engine
 * PROPOSES. Calling it a position would be a fabricated holding; calling it
 * idle would hide a live container. It is neither, and the label says which.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * ONE FUNCTION, ONE INPUT, EVERY FIELD (the ENG1 lesson, priced): `engineBook`
 * derives the book membership itself rather than taking it as a second
 * argument, so no caller can hand it a `book` computed from a different
 * strategy list than the one it is labelling.
 *
 * THREE-VALUED ON BOTH INPUTS, and they are different absences:
 *   · `strategies === null` — the strategy list could not be read. Which
 *     strategies are engine-run is UNKNOWN, not none.
 *   · `engine === null/undefined` — the ENGINE endpoint could not be read. The
 *     rows still render (they come from the strategy list); every session
 *     state is UNKNOWN, which is NOT "no session". A page that read a failed
 *     engine call as "nothing running" would report a live container as idle.
 */

import type { StrategyView } from "@/lib/fund_api";
import type { EngineStrategies } from "../engine/engineView.ts";
import { engineOf, foldBook, isHolding } from "./bookFold.ts";

/** The tone vocabulary this panel draws from, matching the engine page's. */
export type EngineRowTone = "warn" | "neutral" | "quiet";

/**
 * WHAT THIS ROW IS — a stable token, so nothing has to match on the headline's
 * English. `tradingUnallocated` counted rows by comparing `headline` to a
 * string literal until this existed, which makes every re-wording of a
 * sentence a silent change to a count the CEO reads.
 */
export type EngineRowKind =
  | "session_unknown"
  | "archived_running"
  | "unallocated"
  | "in_book"
  | "archived"
  | "idle";

export interface EngineRow {
  strategy: StrategyView;
  /** The engine's NAME (`lean`), never a boolean — a second engine is carried
   *  rather than folded into "lean" by implication. */
  engine: string;
  /** `running` | `stopped` | `none`, and `null` for "could not be read". */
  session: string | null;
  /** The algorithm the running session is executing, when there is one. */
  sessionAlgorithm: string | null;
  /** Does this row ALSO appear in the book table above? Used to say "in the
   *  book" rather than to hide the row: the engine panel lists every engine
   *  strategy, including the ones that are also deployed, so it can be read
   *  as a complete answer to "what is algorithmic here". */
  inBook: boolean;
  archived: boolean;
  kind: EngineRowKind;
  /** The four-word answer. */
  headline: string;
  tone: EngineRowTone;
  /** The one line under it. Never empty. */
  note: string;
}

export interface EngineBook {
  /** Could the STRATEGY list be read. */
  readable: boolean;
  /** Could the ENGINE endpoint be read — a separate fact, separately absent. */
  sessionsReadable: boolean;
  rows: EngineRow[];
  /** The sentence for a panel with no rows. `null` when there are rows. */
  absence: string | null;
  /** Engine strategies that are RUNNING and carry no allocation — the rows the
   *  CEO is being asked to look at. */
  tradingUnallocated: number;
  /** Strategy ids the ENGINE endpoint knows about and the strategy list does
   *  not. Illumination clause 3: two sources answer one question, so show the
   *  difference rather than picking the prettier number. Empty is the normal
   *  case and the panel says nothing when it is. */
  unmatched: string[];
}

const SESSION_UNREADABLE_NOTE =
  "The engine page could not be read, so whether a session is running is " +
  "UNKNOWN — which is not the same as no session. A LEAN container outlives " +
  "the spine that started it.";

/**
 * Fold the strategy list into the engine panel's rows.
 *
 * `engine` is the `strategies` payload of `GET /fund/engine`. Its `session_state`
 * is the field that answers "is it running" — NOT `session`, which the endpoint
 * does not return; verified against the live payload before this was written.
 */
export function engineBook(
  strategies: StrategyView[] | null | undefined,
  engine: EngineStrategies | null | undefined,
): EngineBook {
  const sessionsReadable = !!engine && engine.readable !== false;

  if (strategies == null) {
    return {
      readable: false,
      sessionsReadable,
      rows: [],
      absence:
        "The strategy list could not be read, so which strategies are " +
        "engine-run is UNKNOWN — not none. An engine may be trading right now.",
      tradingUnallocated: 0,
      unmatched: [],
    };
  }

  // Membership is derived HERE from the same list, so a caller cannot pass a
  // `book` folded from a different one.
  const inBook = new Set(foldBook(strategies).book.map((s) => s.strategy_id));

  const byId = new Map<string, { session_state?: string | null; sessions?: { algorithm?: string | null; state?: string | null }[] }>();
  for (const c of engine?.strategies ?? []) byId.set(c.strategy_id, c);

  const rows: EngineRow[] = [];
  for (const s of strategies) {
    const name = engineOf(s);
    if (!name) continue;                       // hand-managed: the normal case
    const card = byId.get(s.strategy_id);
    const session = sessionsReadable ? (card?.session_state ?? "none") : null;
    const running = (card?.sessions ?? []).find((x) => x.state === "running");
    const archived = s.archived === true;
    const allocated = (s.allocation_pct ?? 0) > 0 || isHolding(s);

    let kind: EngineRowKind;
    let headline: string;
    let tone: EngineRowTone;
    let note: string;
    if (session == null) {
      kind = "session_unknown";
      headline = "session UNKNOWN";
      tone = "warn";
      note = SESSION_UNREADABLE_NOTE;
    } else if (archived && session === "running") {
      // THE LOUDEST ROW THIS PANEL CAN DRAW, and it had no branch until the
      // look-pass: a strategy the fund has declared dead, with a live engine
      // session still running it. Ordered ABOVE the unallocated case because
      // "archived and running" is strictly worse than "running and unfunded",
      // and the old ordering would have labelled it the milder of the two.
      kind = "archived_running";
      headline = "archived · but a session is RUNNING";
      tone = "warn";
      note =
        "This strategy is ARCHIVED — the fund's own “this no longer exists” — " +
        "and an engine session for it is running anyway. Nothing on this page " +
        "can stop it; the engine page is where the session is.";
    } else if (session === "running" && !allocated) {
      kind = "unallocated";
      // THE ROW THIS PANEL EXISTS FOR.
      headline = "trading via engine · unallocated";
      tone = "warn";
      note =
        "The engine is running this strategy right now and the fund has given " +
        "it no capital. It PROPOSES: every order it raises waits for approval, " +
        "and the fund's book moves only on a fill. Nothing here is a position.";
    } else if (session === "running") {
      kind = "in_book";
      headline = "trading via engine · in the book";
      tone = "neutral";
      note =
        "A live engine session and an allocation. Its signals still wait for " +
        "approval; the engine's own paper book and the fund's part on the " +
        "first refusal.";
    } else if (archived) {
      kind = "archived";
      headline = "archived · no session";
      tone = "quiet";
      note =
        "Archived is the fund's own “this no longer exists”. It is listed " +
        "because what it signalled is still on the record and still reconciled.";
    } else {
      kind = "idle";
      headline = "no session running";
      tone = "quiet";
      note =
        "Registered to an engine, with nothing running. On daily bars a quiet " +
        "engine and a dead one look identical from here, so this says only " +
        "that no session is on record.";
    }

    rows.push({
      strategy: s,
      engine: name,
      session,
      sessionAlgorithm: running?.algorithm ?? null,
      inBook: inBook.has(s.strategy_id),
      archived,
      kind,
      headline,
      tone,
      note,
    });
  }

  // Live first, then non-archived, then by name — the same ordering rule the
  // engine page's own cards use, so the two surfaces do not disagree about
  // which strategy is "first".
  rows.sort(
    (a, b) =>
      Number(b.session === "running") - Number(a.session === "running") ||
      Number(a.archived) - Number(b.archived) ||
      (a.strategy.name ?? "").localeCompare(b.strategy.name ?? ""),
  );

  const known = new Set(strategies.map((s) => s.strategy_id));
  const unmatched = (engine?.strategies ?? [])
    .map((c) => c.strategy_id)
    .filter((id) => !known.has(id));

  return {
    readable: true,
    sessionsReadable,
    rows,
    absence: rows.length
      ? null
      : "No strategy on this fund declares an engine. Every sleeve here is " +
        "hand-managed; nothing is algorithmic yet.",
    // Counted on the KIND, never on the sentence: matching a headline string
    // makes every re-wording a silent change to a number the CEO reads.
    tradingUnallocated: rows.filter((r) => r.kind === "unallocated").length,
    unmatched,
  };
}

/**
 * The panel's own headline sentence — the one the CEO reads before the rows.
 *
 * It names the number that matters (running-and-unallocated) or says plainly
 * that there is none. Returns `null` when the panel has nothing to head, so an
 * empty panel does not get a sentence about a state it is not in.
 */
export function engineBookHeadline(b: EngineBook): { text: string; tone: EngineRowTone } | null {
  if (!b.readable) return { text: b.absence ?? "The strategy list could not be read.", tone: "warn" };
  if (!b.sessionsReadable && b.rows.length > 0) {
    return { text: SESSION_UNREADABLE_NOTE, tone: "warn" };
  }
  if (b.rows.length === 0) return null;
  if (b.tradingUnallocated > 0) {
    const n = b.tradingUnallocated;
    return {
      text:
        `${n} engine strateg${n === 1 ? "y is" : "ies are"} running with no allocation. ` +
        `${n === 1 ? "It proposes" : "They propose"}; the book moves on your approval, not on ${n === 1 ? "its" : "their"} signals.`,
      tone: "warn",
    };
  }
  return {
    text: `${b.rows.length} engine strateg${b.rows.length === 1 ? "y" : "ies"}, none running unallocated.`,
    tone: "quiet",
  };
}

/** The disagreement between the two sources, as a sentence, or `null`. */
export function engineBookMismatch(b: EngineBook): string | null {
  if (b.unmatched.length === 0) return null;
  const n = b.unmatched.length;
  return (
    `The engine reports ${n} strateg${n === 1 ? "y" : "ies"} this page's strategy ` +
    `list does not contain (${b.unmatched.join(", ")}). Two sources answer one ` +
    `question and they disagree; the Engine page is the one that can see it.`
  );
}
