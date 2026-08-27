/**
 * THE CONSOLE'S QUEUE — one ranked list of what is on the chair's hands.
 *
 * The CEO approved the Main board with *"Cool lets get this"*, and its
 * instruction is the idiom this module serves: **queues are rows, never
 * essays.** Date · seat · verb-and-object · money · age, one tap to open, and
 * an honest tail. The console it replaces rendered three separate card stacks,
 * each one a paragraph tall, none of them ranked — so the oldest thing on the
 * desk (142 hours, measured on the live record 2026-08-27) was indis-
 * tinguishable from the newest, and the chair's actual question — *what should
 * I fire next* — had no answer on the page.
 *
 * TWO POPULATIONS, ONE LIST, AND THAT IS THE POINT. The chair's work arrives
 * as approved requests nobody has fired AND as recommendations routed to the
 * chair. Rendering them as two stacks makes the reader do the merge, and a
 * reader doing a merge picks the stack they scrolled to. Each row keeps its
 * `origin`, so nothing is blurred; the RANKING is shared, which is the part
 * that decides what gets done.
 *
 * THE RANK IS THE SPINE'S, AND THIS FILE DOES NOT RE-DERIVE IT. CEO decision
 * 2026-08-27, verbatim: *"can we add ordering to my desk say high-priority to
 * low; time-sensitive or not; blocker or not?"* — three bands (blocker ·
 * dated · the rest), folded once in `desk.desk_band` and carried on every row.
 * Three surfaces show slices of this queue, and three copies of a priority
 * rule is three priority rules: the day they disagree, the disagreement is
 * invisible because each surface looks internally consistent. So the band
 * arrives on the wire and this module SORTS BY IT, never computes it.
 *
 * WHEN THE BAND IS NOT ON THE WIRE — an older record — this module does NOT
 * quietly invent one. It falls back to age, sets `rankBasis: "age_only"`, and
 * the console says which order it is showing. A page that silently ranked by
 * something other than what its header claims is the confident-wrong-answer
 * failure, and it is worse than an obviously degraded one.
 *
 * Age is the last tie-break and never the lead, because a queue sorted by age
 * alone does the least urgent thing first as soon as it falls behind.
 *
 * THE TAIL IS EXACT AND SAYS THE RANK. "64 more, ranked the same way" is a
 * different promise from "showing 6" — the first tells the reader that the
 * things they cannot see are things the page has already judged less urgent.
 * Truncation that does not say so is the failure this desk has been repaired
 * from before; here the count is computed, not estimated.
 */

import type { DeskView } from "@/lib/fund_api";

/* ---------------------------------------------------------------- types --- */

export type RowOrigin = "request" | "recommendation";

/** The spine's three bands. `unbanded` is this client's word for a row whose
 *  payload carried no band at all — it is NOT a fourth priority level, and it
 *  never draws a chip. */
export type Band = "blocker" | "time_sensitive" | "rest" | "unbanded";

export interface ConsoleRow {
  id: string;
  origin: RowOrigin;
  /** Read from the payload. Never computed here. */
  band: Band;
  bandRank: number;
  /** The chip's word, as the spine wrote it. Empty string = draw no chip. */
  bandLabel: string;
  /** On whose authority: `declared` · `not_blocking` · `due_date` ·
   *  `undeclared` · `unreadable` · `absent` (the payload said nothing). */
  bandBasis: string;
  /** The plain sentence behind the chip, from the spine. */
  bandNote: string | null;
  /** THE FIVE ACTION TAGS (CEO, 2026-08-28: "Pending, In FLight, Executed,
   *  Deprioritised, Completed"). Folded on the spine (`deskcard.action_tag`)
   *  and READ here, never computed — the band rule's own discipline. Null =
   *  the wire carried none (an older payload); no chip is drawn. */
  actionTag: string | null;
  /** The chip's word, exactly as the spine wrote it. */
  actionTagLabel: string | null;
  /** The seat the work is FOR. Null when the record names none. */
  seat: string | null;
  /** Who asked, when that is a different party from the seat — the org chart
   *  gaining an edge, which must never look like the CEO typing. */
  filedBy: string | null;
  seatFiled: boolean;
  /** The record's OWN words for the work. Passed through, never rewritten:
   *  the plain-English direction governs the words WE write around this. */
  verbObject: string;
  /** `YYYY-MM-DD`. The only field that can make a row happen without a click. */
  dueDate: string | null;
  /** Null when the record states none. NEVER zero. */
  money: number | null;
  at: string | null;
  /** Null when the row carries no timestamp — undated is not brand new. */
  ageHours: number | null;
  /** `18h` / `5.7d`, or null when undated. */
  ageLabel: string | null;
  /** Everything the fold shows: the brief as filed, and who approved it. */
  detail: string | null;
  approvedBy: string | null;
  approvedAt: string | null;
}

export interface ConsoleQueue {
  /** Ranked, and capped at `shown`. */
  rows: ConsoleRow[];
  /** Every row the rank produced, before the cap. */
  total: number;
  /** How many the cap hid. Zero when nothing was hidden. */
  hidden: number;
  /** The sentence under the list. Null when there is no tail. */
  tailNote: string | null;
  /** True when either population could not be read, so `total` is a floor. */
  isFloor: boolean;
  /** `bands` when every row arrived with the spine's priority band; `age_only`
   *  when one or more did not, and the list is therefore ordered by how long
   *  things have waited. Rendered — a page whose order differs from its header
   *  is worse than one that is obviously degraded. */
  rankBasis: "bands" | "age_only";
  /** How many rows carried no band. Zero when the record is current. */
  unbanded: number;
  /** The sentence above the list. Absence in words, always. */
  note: string;
}

/** How many rows the console shows before the tail. Six on the Main board;
 *  eight here because the board was drawn at 1240px and the studio container
 *  is 1200px with a denser row. Changing this changes only what is FOLDED —
 *  `total` and `hidden` are computed from the full ranked list. */
export const SHOWN = 8;

/* -------------------------------------------------------------- helpers --- */

function str(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length > 0 ? t : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Hours since `at`, measured against `now` so the tests are not a clock. */
export function ageHoursOf(at: string | null, now: number): number | null {
  if (!at) return null;
  const t = Date.parse(at);
  if (Number.isNaN(t)) return null;
  const h = (now - t) / 3_600_000;
  return h >= 0 ? h : null;
}

/** `18h` under a day, `5.7d` above it. A queue's age is read at a glance and
 *  `137.4h` is a number a reader has to divide. */
export function ageLabelOf(hours: number | null): string | null {
  if (hours == null) return null;
  if (hours < 1) return "<1h";
  if (hours < 24) return `${Math.round(hours)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

const HUMANS = new Set(["ceo", "cto", "neelesh", "abhishek", "chair",
  "neelesh-via-cto", "neelesh-via-co-cto"]);

const BANDS: Band[] = ["blocker", "time_sensitive", "rest"];

/**
 * The row's band, READ from the payload.
 *
 * The one thing this must never do is fall back to computing a band from
 * `due_date` or `blocks` when the payload is silent. That fallback would look
 * harmless and would be a SECOND implementation of the CEO's priority rule,
 * living in a different language from the first — and the two would agree for
 * exactly as long as nobody edited either.
 */
export function bandOf(raw: Record<string, unknown>): {
  band: Band; bandRank: number; bandLabel: string; bandBasis: string;
  bandNote: string | null;
} {
  const b = raw.band;
  if (typeof b === "string" && (BANDS as string[]).includes(b)) {
    const rank = num(raw.band_rank);
    return {
      band: b as Band,
      // The spine's rank when it stated one, its own index otherwise — the
      // ORDER of `BANDS` here mirrors the spine's tuple and nothing else.
      bandRank: rank ?? BANDS.indexOf(b as Band) + 1,
      bandLabel: typeof raw.band_label === "string" ? raw.band_label : "",
      bandBasis: str(raw.band_basis) ?? "undeclared",
      bandNote: str(raw.band_note),
    };
  }
  return {
    band: "unbanded",
    // Sorted BEHIND every banded row rather than into `rest`: an unbanded row
    // has not been judged, and mixing it into the lowest judged band would
    // claim it had.
    bandRank: BANDS.length + 1,
    bandLabel: "",
    // ABSENT AND UNREADABLE ARE DIFFERENT FACTS, and the first version of this
    // reader collapsed them — every unknown value, including a band word the
    // record actually sent, reported as `absent`. That is the exact conflation
    // the rest of this diff is built against, at the one seam where the two
    // repos meet. Found by the Gauntlet, not by 28 tests.
    //   `absent`     the row carried no band (`undefined` — an older record,
    //                and also what a JS spread leaves behind, which is why
    //                this keys on the VALUE and not on `"band" in raw`: the
    //                two disagree for a spread and agree for parsed JSON, and
    //                the read site cannot tell them apart anyway).
    //   `unreadable` the row carried SOMETHING this client cannot read — a
    //                newer band word, or a malformed one. The reader should
    //                be told a judgement EXISTS and could not be read, rather
    //                than that none was made.
    bandBasis: b === undefined ? "absent" : "unreadable",
    bandNote: null,
  };
}

/* ---------------------------------------------------------- the sources --- */

function fromRequest(r: DeskView["requests"][number], now: number): ConsoleRow | null {
  const raw = r as unknown as Record<string, unknown>;
  // CLEARED TO TRIGGER, exactly: the CEO said yes and nobody has fired it.
  // Anything still `open` is somebody else's decision and belongs in a
  // different count — folding the two made a queue where nothing was
  // actionable read identically to one where everything was.
  if (raw.status !== "approved" || raw.dispatched === true) return null;
  const verbObject = str(raw.subject) ?? str(raw.task) ?? str(raw.headline);
  if (!verbObject) return null;
  const id = str(raw.request_id);
  if (!id) return null;
  const at = str(raw.at);
  const actor = str(raw.actor);
  const hours = ageHoursOf(at, now);
  return {
    id, origin: "request", ...bandOf(raw),
    // Every row this builder admits is `approved` and undispatched — a
    // decision landed, the follow-through is owed. That is `in_flight` in the
    // spine's five-tag vocabulary (deskcard.ACTION_TAG_LABELS), mirrored here
    // because a request's serializer does not carry the fold yet.
    actionTag: "in_flight", actionTagLabel: "In flight",
    seat: str(raw.serves) ?? str(raw.seat),
    filedBy: actor,
    seatFiled: actor != null && !HUMANS.has(actor.toLowerCase()),
    verbObject,
    // A desk request carries no due date and no figure on the wire (measured
    // against the live record, 2026-08-27). Absent, not zero — and the rank
    // below therefore puts every request behind every dated recommendation,
    // which is correct rather than a gap.
    dueDate: str(raw.due_date),
    money: num(raw.money_at_stake),
    at, ageHours: hours, ageLabel: ageLabelOf(hours),
    detail: str(raw.note),
    approvedBy: str(raw.approved_by), approvedAt: str(raw.approved_at),
  };
}

function fromRec(r: Record<string, unknown>, now: number): ConsoleRow | null {
  // The chair's own backlog: routed to the chair and not yet done. `status`
  // is read rather than assumed — a `staged` row is already moving.
  const actor = str(r.next_actor_resolved) ?? str(r.next_actor);
  if (actor !== "chair") return null;
  if (r.status !== "open" && r.status !== "accepted") return null;
  const verbObject = str(r.text_display) ?? str(r.text);
  if (!verbObject) return null;
  const runId = str(r.run_id), recId = num(r.rec_id);
  if (!runId || recId == null) return null;
  const at = str(r.resolved_at);
  const hours = ageHoursOf(at, now);
  const seat = str(r.seat);
  return {
    id: `${runId}#${recId}`, origin: "recommendation", ...bandOf(r),
    actionTag: str(r.action_tag), actionTagLabel: str(r.action_tag_label),
    seat, filedBy: seat, seatFiled: seat != null && !HUMANS.has(seat),
    verbObject,
    dueDate: str(r.due_date),
    money: num(r.money_at_stake),
    at, ageHours: hours, ageLabel: ageLabelOf(hours),
    detail: str(r.task), approvedBy: null, approvedAt: null,
  };
}

/* ----------------------------------------------------------- the ranking -- */

/**
 * BAND first (the spine's), then date, then money, then age.
 *
 * The tie-breaks INSIDE a band mirror `desk.band_sort_key` deliberately, and
 * that duplication is the one place this file is allowed to know the rule —
 * because a client cannot sort by a key it does not hold. What it must never
 * duplicate is the BAND ASSIGNMENT itself, which is the judgement; ordering
 * within an assigned band is arithmetic over fields already on the row.
 *
 * Exported so the order can be tested without the cap in the way: a test that
 * can only see the capped list cannot tell a wrong order from a wrong cap.
 */
export function rankRows(rows: ConsoleRow[]): ConsoleRow[] {
  return [...rows].sort((a, b) => {
    if (a.bandRank !== b.bandRank) return a.bandRank - b.bandRank;
    if (a.dueDate && b.dueDate) {
      if (a.dueDate !== b.dueDate) return a.dueDate < b.dueDate ? -1 : 1;
    } else if (a.dueDate) return -1;
    else if (b.dueDate) return 1;
    // A row with no figure ranks BELOW a row with one, rather than being
    // treated as worth nothing — absent and zero are different facts and the
    // sort is one of the places that quietly conflates them.
    const am = a.money ?? -1, bm = b.money ?? -1;
    if (am !== bm) return bm - am;
    const ah = a.ageHours ?? -1, bh = b.ageHours ?? -1;
    if (ah !== bh) return bh - ah;
    // An explicit last key: two undated, unpriced, same-age rows must not
    // shuffle between renders. `id` is stable and unique by construction.
    return a.id < b.id ? -1 : a.id > b.id ? 1 : 0;
  });
}

/* ------------------------------------------------------------ the queue --- */

export function consoleQueue(
  requests: readonly DeskView["requests"][number][] | null | undefined,
  recommendations: readonly Record<string, unknown>[] | null | undefined,
  opts: { now?: number; shown?: number } = {},
): ConsoleQueue {
  const now = opts.now ?? Date.now();
  const shown = opts.shown ?? SHOWN;
  const reqRead = Array.isArray(requests);
  const recRead = Array.isArray(recommendations);

  const rows = rankRows([
    ...(reqRead ? requests! : []).map((r) => fromRequest(r, now)),
    ...(recRead ? recommendations! : []).map((r) => fromRec(r, now)),
  ].filter((r): r is ConsoleRow => r !== null));

  const hidden = Math.max(0, rows.length - shown);
  const isFloor = !reqRead || !recRead;
  const unbanded = rows.filter((r) => r.band === "unbanded").length;
  const rankBasis = unbanded > 0 ? "age_only" as const : "bands" as const;

  const note = !reqRead && !recRead
    ? "We could not read the queue. What is waiting on you is unknown, not "
      + "nothing."
    : !reqRead
      ? "We could not read the approved asks, so this list is only the "
        + "recommendations. There is more, we just cannot see it."
      : !recRead
        ? "We could not read the recommendations, so this list is only the "
          + "approved asks. There is more, we just cannot see it."
        : rows.length === 0
          ? "Nothing is waiting on you. Everything approved has been started."
          : rankBasis === "age_only"
            ? `${unbanded} of these have not been sorted into blockers, dated `
              + "work and the rest, so this list is ordered by how long things "
              + "have waited rather than by how urgent they are."
            : "Blockers first, then anything with a date, then the rest by "
              + "money at risk.";

  return {
    rows: rows.slice(0, shown),
    total: rows.length,
    hidden,
    tailNote: hidden > 0
      ? `${hidden} more, ranked the same way — nothing is hidden silently.`
      : null,
    isFloor, rankBasis, unbanded,
    note,
  };
}
