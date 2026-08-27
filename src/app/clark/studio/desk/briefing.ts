/**
 * THE BRIEFING CONTRACT — how every seat delivery renders, everywhere.
 *
 * The CEO approved the Studio Work Surfaces canvas with *"Cool lets get
 * this"*, and the SeatOffice board is this contract's picture:
 *
 *     headline  ->  stat chips (<= 4)  ->  recommendation rows  ->  the fold
 *
 * **A run record rendered as paragraphs is a defect.** That is not a style
 * preference, it is a measured one: the engine page shipped nine paragraphs
 * of honest prose and the CEO's verdict was *"too much text; we need
 * analytics and graphs and meaningful and minimal UI"*. Nine went to
 * one-surfaced-eight-folded and nothing was lost. This module is that lesson
 * made structural, so the next surface cannot re-derive it wrongly.
 *
 * WHAT THE CHIPS ARE, AND THE GAP THIS NAMES. The canvas's chips are the
 * delivery's FINDINGS — `94.3% a contract constant`, `+0.66%/yr excess`. The
 * flight recorder holds no structured findings: `verdict` and `reasoning` are
 * free text and parsing numbers out of English is the mistake this desk has
 * been repaired from twice. So the chips here are the run's MEASURED FACTS
 * from the record — who must move, what is at stake, how many asks, what it
 * cost, how long it ran — and the finding-chips wait for a field that does
 * not exist. Said plainly rather than approximated, because a chip that
 * looked like a finding and was a token count would be worse than no chip.
 *
 * THE CHIP CAP IS RELEVANCE, NOT TRUNCATION. Five chips can be earned and
 * four slots exist; the priority order is decision value (who must move, then
 * money, then volume, then cost, then duration) and a chip with nothing to
 * say is not rendered at all — zero is quiet. Nothing is lost by the cap:
 * every number is in the fold.
 *
 * ABSENCE IS A SENTENCE HERE TOO. A run with no verdict has no headline and
 * says so; a run with no recommendations says the seat asked for nothing,
 * which is a real and reportable delivery; an ABORTED run is never dressed as
 * a delivery, because "it stopped" and "it delivered" are the two facts a
 * chair most needs kept apart.
 */

import type { DeskRun, DeskRec } from "./seatLib.ts";

/* ---------------------------------------------------------------- types --- */

/** Whose move it is, as the record states it — never inferred from prose. */
export type NextActor = "ceo" | "chair" | "seat" | "nobody" | "unstated";

export interface BriefingChip {
  /** The mono uppercase label under the figure. */
  label: string;
  /** The figure, already formatted. `tabular-nums` is applied by the view. */
  value: string;
  /** The quiet half-sentence beside it. Null when the figure speaks alone. */
  sub: string | null;
  /** `warn` only where the CEO must move — the one place tone carries state.
   *  Everything else is `plain`: hierarchy comes from type and space. */
  tone: "plain" | "warn";
}

export interface BriefingRow {
  recId: number | null;
  kind: string | null;
  text: string;
  nextActor: NextActor;
  /** `null` when the record states none. NEVER zero — a recommendation with
   *  no figure and one worth nothing are different facts. */
  moneyAtStake: number | null;
  dueDate: string | null;
  reversibility: string | null;
  status: string | null;
}

export type RunOutcome = "delivered" | "aborted" | "unstated";

export interface Briefing {
  runId: string;
  seat: string | null;
  outcome: RunOutcome;
  /** The delivery's own claim, one line. Null when the run filed no verdict. */
  headline: string | null;
  /** The sentence shown INSTEAD of a headline. Null when a headline exists. */
  headlineNote: string | null;
  chips: BriefingChip[];
  rows: BriefingRow[];
  /** The sentence shown when there are no rows — a real delivery, not a gap. */
  rowsNote: string | null;
  /** Everything one reach away: the distilled why, the artifact, the clock. */
  fold: {
    reasoning: string | null;
    artifactPath: string | null;
    task: string | null;
    dispatchedAt: string | null;
    resolvedAt: string | null;
    /** Wall clock in minutes, or null when either stamp is missing. */
    ranMinutes: number | null;
    tokens: number | null;
    toolUses: number | null;
    model: string | null;
  };
}

/* -------------------------------------------------------------- helpers --- */

const ACTORS: NextActor[] = ["ceo", "chair", "seat", "nobody"];

export function nextActorOf(rec: Partial<DeskRec>): NextActor {
  const raw = (rec as Record<string, unknown>).next_actor;
  if (typeof raw !== "string") return "unstated";
  const t = raw.trim().toLowerCase();
  return (ACTORS as string[]).includes(t) ? (t as NextActor) : "unstated";
}

function str(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const t = v.trim();
  return t.length > 0 ? t : null;
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/** Minutes between two stamps. Null when either is missing OR unparseable —
 *  an unreadable timestamp is not a zero-length run. */
export function ranMinutes(from: unknown, to: unknown): number | null {
  const a = str(from), b = str(to);
  if (!a || !b) return null;
  const ta = Date.parse(a), tb = Date.parse(b);
  if (Number.isNaN(ta) || Number.isNaN(tb)) return null;
  const m = (tb - ta) / 60_000;
  // A negative duration means the record disagrees with itself. Reported as
  // absent rather than as a negative number nobody can act on.
  return m >= 0 ? m : null;
}

/** A duration a human reads at a glance. `128` -> `2h 8m`. */
export function fmtDuration(minutes: number | null): string | null {
  if (minutes == null) return null;
  if (minutes < 1) return "<1m";
  if (minutes < 60) return `${Math.round(minutes)}m`;
  const h = Math.floor(minutes / 60);
  const m = Math.round(minutes - h * 60);
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

/** `540438` -> `540k`. Whole thousands only: a token count's last three
 *  digits are noise and printing them is chrome that pays no rent. */
export function fmtTokensShort(n: number | null): string | null {
  if (n == null) return null;
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${Math.round(n / 1000)}k`;
  return `${(n / 1_000_000).toFixed(1)}M`;
}

function fmtMoney(n: number): string {
  return n >= 1000 ? `$${Math.round(n).toLocaleString("en-US")}`
    : `$${n.toFixed(n % 1 === 0 ? 0 : 2)}`;
}

/* --------------------------------------------------------------- rows ----- */

export function briefingRows(recs: readonly Partial<DeskRec>[] | null | undefined): BriefingRow[] {
  return (recs ?? [])
    .map((r) => {
      const rec = r as Record<string, unknown>;
      // A row with no text is DROPPED rather than rendered blank: a
      // recommendation nobody can read is not a recommendation, and an empty
      // line in this list would be counted by the eye as an ask.
      const text = str(rec.text_display) ?? str(rec.text);
      if (!text) return null;
      return {
        recId: num(rec.rec_id),
        kind: str(rec.kind),
        text,
        nextActor: nextActorOf(r),
        moneyAtStake: num(rec.money_at_stake),
        dueDate: str(rec.due_date),
        reversibility: str(rec.reversibility),
        status: str(rec.status),
      };
    })
    .filter((r): r is BriefingRow => r !== null);
}

/* -------------------------------------------------------------- chips ----- */

/** The chip cap. Four is the canvas's number and the reason is legibility:
 *  a strip a reader must count is a table. */
export const MAX_CHIPS = 4;

/**
 * The chips a run has EARNED, in decision-value order, capped at four.
 *
 * Exported separately from `briefingOf` so the priority order is testable on
 * its own — the cap is the part most likely to be got wrong by a later edit,
 * and a test that can only see the capped output cannot tell a wrong order
 * from a wrong cap.
 */
export function briefingChips(rows: BriefingRow[], run: Partial<DeskRun>): BriefingChip[] {
  const chips: BriefingChip[] = [];

  // 1. WHO MUST MOVE. The one thing on this card that can be overdue, and the
  //    only chip that ever carries a tone.
  const ceo = rows.filter((r) => r.nextActor === "ceo").length;
  if (ceo > 0) {
    chips.push({
      // Not "1 recommendation / 2 recommendations": the CEO's question is
      // not how many rows there are, it is whether anything is waiting on
      // him. The sub-line answers that and does not need a plural.
      label: "needs you", value: String(ceo), sub: "waiting on your call",
      tone: "warn",
    });
  }

  // 2. MONEY. Summed only over rows that STATE a figure, and the sub-line says
  //    how many did — a total over 2 of 9 rows is a floor, and rendering it as
  //    "at stake" without the denominator overstates what the record supports.
  const priced = rows.filter((r) => r.moneyAtStake != null);
  const total = priced.reduce((s, r) => s + (r.moneyAtStake ?? 0), 0);
  if (priced.length > 0 && total > 0) {
    chips.push({
      label: "at stake", value: fmtMoney(total),
      sub: priced.length === rows.length ? "every ask carries a figure"
        : `${priced.length} of ${rows.length} asks carry a figure`,
      tone: "plain",
    });
  }

  // 3. VOLUME. Zero is quiet: a run that asked for nothing gets no chip, and
  //    `rowsNote` says so in words below the strip instead.
  if (rows.length > 0) {
    chips.push({
      label: "asks", value: String(rows.length),
      sub: ceo > 0 ? `${rows.length - ceo} on the chair or a seat` : "none need you",
      tone: "plain",
    });
  }

  // 4. COST.
  const tokens = fmtTokensShort(num(run.tokens));
  if (tokens) {
    const tools = num(run.tool_uses);
    chips.push({
      label: "tokens", value: tokens,
      sub: tools != null ? `${tools} tool calls` : null, tone: "plain",
    });
  }

  // 5. THE CLOCK.
  const ran = fmtDuration(ranMinutes(run.dispatched_at, run.resolved_at));
  if (ran) chips.push({ label: "ran for", value: ran, sub: null, tone: "plain" });

  return chips.slice(0, MAX_CHIPS);
}

/* ---------------------------------------------------------- the briefing -- */

export function briefingOf(run: DeskRun): Briefing {
  const r = run as unknown as Record<string, unknown>;
  const outcome: RunOutcome = r.status === "delivered" ? "delivered"
    : r.status === "aborted" ? "aborted" : "unstated";
  const rows = briefingRows(run.recommendations);
  const headline = str(r.verdict);

  // AN ABORTED RUN IS NEVER DRESSED AS A DELIVERY. "It stopped" and "it
  // delivered" are the two facts a chair most needs kept apart, and a verdict
  // string on an aborted run is what the seat had reached, not what it
  // concluded.
  //
  // PLAIN ENGLISH, and it is checked (`plainEnglish.ts`). These three
  // sentences are the ones the CEO reads when something is off; the technical
  // version is one tap down, in the detail below the card.
  const headlineNote = headline
    ? (outcome === "aborted"
      ? "This job STOPPED before it finished. The line above is as far as it "
        + "got, not a conclusion it stands behind."
      : null)
    : outcome === "aborted"
      ? "This job STOPPED before it finished and reached no conclusion. That "
        + "is different from finishing and finding nothing."
      : "This job recorded no conclusion. What it found is in the detail "
        + "below, or nowhere — it did not conclude that there was nothing.";

  return {
    runId: str(r.run_id) ?? "",
    seat: str(r.seat),
    outcome,
    headline,
    headlineNote,
    chips: briefingChips(rows, run),
    rows,
    rowsNote: rows.length === 0
      ? "This seat is not asking you for anything. Coming back with nothing "
        + "to decide is a result, not a blank page."
      : null,
    fold: {
      reasoning: str(r.reasoning),
      artifactPath: str(r.artifact_path),
      task: str(r.task),
      dispatchedAt: str(r.dispatched_at),
      resolvedAt: str(r.resolved_at),
      ranMinutes: ranMinutes(r.dispatched_at, r.resolved_at),
      tokens: num(r.tokens),
      toolUses: num(r.tool_uses),
      model: str(r.model),
    },
  };
}
