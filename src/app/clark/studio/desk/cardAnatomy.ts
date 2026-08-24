/**
 * CARD ANATOMY — the shared shape every desk card wears.
 *
 * Spec: `docs/design/REQUEST_CARD_2026-08-24.md`, CEO-ratified. D39 built the
 * request card's four questions on the ASK payload and stopped there; the CEO
 * then asked *"SO WHAT DID WE DO?"*, and the honest answer was that the DATA
 * became truthful while the page still looked like the thing he had rejected.
 * Two gaps, both measured on his live desk (2026-08-24, 238 recommendations,
 * 109 requests):
 *
 *   * **The headline was the dump.** All 109 requests are prose-only, and the
 *     spine's `card.headline` for a prose ask is the subject's first LINE —
 *     which, for a subject with no newline in it, is the whole subject. On the
 *     rendered page that is seven lines of body copy sitting where the spec
 *     asks for a NAME, and no "+ the incident" toggle appeared, because the
 *     collapsed detail and the headline were the same string.
 *   * **Recommendation rows had no anatomy at all** — no clamp, no rail, no
 *     whose-move line. `memoParts` gives the first SENTENCE, and on this desk
 *     the median first sentence of a recommendation is well past a line.
 *
 * NOTHING IS DELETED BY A CLAMP, and that is the property the test pins:
 * `clampLine` returns the tail it cut, every caller puts the tail back into
 * the collapsed body, and `rejoin()` reconstructs the original. A clamp that
 * dropped text would look identical on screen to one that did not.
 */

/**
 * The DEFAULT headline budget, for callers with no type scale of their own.
 *
 * MEASURED, AND THE FIRST NUMBER I WROTE HERE WAS WRONG. The draft said "at
 * this page's card width (~640px of 14px text) a line holds roughly 90
 * characters" and neither half survived the browser: a CDP binary search over
 * the rendered desk (`scratchpad/d42_probe_width.js`) found the 16px card is
 * **539px** wide and holds **61–65** characters, and the 13px card is 555–670px
 * and holds **87–96**. One budget cannot serve three type sizes, so the real
 * per-scale numbers live on `CardStyle.headlineMax` in `deskCardStyle.ts`,
 * beside the type they belong to.
 *
 * 87 is kept here as the default because it is the FLOOR of the measured
 * 13px range — the scale the request card and the shared `RecRow` use. It
 * over-clamps a wide card by a few characters and never wraps a narrow one.
 *
 * What the clamp is worth, measured on the same page: the four recommendation
 * headlines on the CEO's live desk were 190, 152, 148 and 121 characters, and
 * the first bench ask rendered SEVEN lines as its own name.
 */
export const CARD_HEADLINE_MAX = 87;

/**
 * The budget for the EMPHASISED request card's 15px face.
 *
 * MEASURED THE SAME WAY, on the same page: at 15px in the ask card's ~670px
 * column the boundary sits near 80 characters — a 78-character headline
 * rendered on one line and an 86-character one wrapped. 76 keeps a margin.
 *
 * A CHARACTER BUDGET CANNOT GUARANTEE A LINE IN A PROPORTIONAL FONT, and this
 * comment is the honest version of a claim the first draft made too strongly:
 * "MMMM" and "iiii" are the same four characters and nowhere near the same
 * width, so the guarantee here is "one line for a typical headline, sometimes
 * two for a wide-glyph one — never the seven this replaced".
 *
 * Reproduce: `scratchpad/d42_probe_width.js` through `d42shot.js`.
 */
export const ASK_HEADLINE_MAX = 76;

export interface ClampedLine {
  /** What the card renders. Carries a trailing ellipsis when it was cut. */
  line: string;
  /** What was cut, verbatim, for the caller to put behind the toggle.
   *  Empty string when nothing was cut — NEVER null, so a caller cannot
   *  accidentally render "null" or treat absence as a missing key. */
  tail: string;
  clamped: boolean;
}

/**
 * Cut a headline to one line at a word boundary, keeping the remainder.
 *
 * WORD BOUNDARY, NOT CHARACTER. `memoParts`' own docstring carries the reason
 * this repo cuts carefully: a truncation "could cut a 'not' off the front of a
 * claim". Cutting mid-word additionally invents a word that was never written.
 * When there is no space to cut at (one very long token — an id, a URL) the
 * whole thing is returned UNCUT: an unbreakable token rendered as a fragment
 * plus an ellipsis is unreadable and unsearchable, and a wide row is a smaller
 * problem than a mangled identifier.
 */
export function clampLine(
  text?: string | null, max = CARD_HEADLINE_MAX,
): ClampedLine {
  const t = String(text ?? "").replace(/\s+/g, " ").trim();
  if (t.length <= max) return { line: t, tail: "", clamped: false };
  const cut = t.lastIndexOf(" ", max);
  if (cut <= 0) return { line: t, tail: "", clamped: false };
  return {
    line: `${t.slice(0, cut).trimEnd()}…`,
    tail: t.slice(cut).trim(),
    clamped: true,
  };
}

/** Put a clamped line and its tail back together.
 *
 *  Exists FOR THE TEST, and the test is the point: it asserts that clamping is
 *  lossless over the live corpus, which is the one property a screenshot
 *  cannot check. A clamp that swallowed a sentence renders identically. */
export function rejoin(c: ClampedLine): string {
  const head = c.line.replace(/…$/, "");
  return c.tail ? `${head} ${c.tail}` : head;
}

/**
 * Join a clamped tail onto whatever body the card already had.
 *
 * The order is TAIL FIRST because the tail is the rest of the sentence the
 * headline started; putting the later paragraphs before it would read as a
 * different document.
 */
export function bodyWithTail(tail: string, rest?: string | null): string {
  const r = (rest ?? "").trim();
  if (!tail) return r;
  return r ? `${tail} ${r}` : tail;
}

/* --------------------------------------------- the recommendation rail ---- */

export type RailState = "reached" | "current" | "future" | "unrecorded";

export interface RailStage {
  stage: string;
  state: RailState;
  /** The timestamp that put this stage in that state, when one exists. */
  at: string | null;
}

export interface RecLifecycle {
  stages: RailStage[];
  /** Hours the row has sat in its CURRENT stage. Null when nothing dates it —
   *  and null renders as nothing, never as `0.0h`. */
  ageHours: number | null;
}

/** The fields the rail reads. Structural, so a test builds three of them
 *  rather than the recommendation's other forty. */
export interface RailedRec {
  status?: string | null;
  /** When the producing RUN was resolved — the moment this row was filed. */
  resolved_at?: string | null;
  decided_at?: string | null;
}

const HOUR_MS = 3600 * 1000;

function hoursBetween(from: string | null, nowIso: string): number | null {
  if (!from) return null;
  const a = Date.parse(from);
  const b = Date.parse(nowIso);
  if (!Number.isFinite(a) || !Number.isFinite(b)) return null;
  return (b - a) / HOUR_MS;
}

/**
 * Where a recommendation stands, from fields the spine actually serves.
 *
 * THREE STAGES, AND THE THIRD ONE IS A CONFESSION. `filed` and `decided` are
 * both dated on the payload (`resolved_at`, `decided_at`). **Nothing on this
 * desk records that a recommendation was EXECUTED** — no field, no event
 * consumed by this projection — so `executed` renders as `unrecorded` on a
 * decided row rather than as reached or as a dim future stage. Both of the
 * alternatives assert something the record cannot support: "reached" would
 * claim an execution nobody logged, and a dim "future" on a row the chair
 * carried out last week would claim it never happened. Absence is never zero
 * and it is never a tick either.
 *
 * On an UNDECIDED row `executed` is genuinely `future`: a recommendation
 * cannot have been carried out before it was accepted, so that one IS a fact
 * the record supports.
 *
 * `now` is a PARAMETER. A rail that read the wall clock could not be tested
 * for the 0.0h case, and this desk has already shipped one age that was
 * rendered when it should have been absent.
 */
export function recLifecycle(
  r: RailedRec | null | undefined, nowIso: string,
): RecLifecycle {
  const filedAt = (r?.resolved_at ?? null) || null;
  const decidedAt = (r?.decided_at ?? null) || null;
  const decided = !!decidedAt;

  const stages: RailStage[] = [
    { stage: "filed", state: decided ? "reached" : "current", at: filedAt },
    { stage: "decided", state: decided ? "current" : "future", at: decidedAt },
    { stage: "executed", state: decided ? "unrecorded" : "future", at: null },
  ];
  const currentAt = decided ? decidedAt : filedAt;
  return { stages, ageHours: hoursBetween(currentAt, nowIso) };
}

/** Human labels for the recommendation rail. Sentence case, matching
 *  `STAGE_LABEL` in `cardState.ts`, which does the same job for asks. */
export const REC_STAGE_LABEL: Record<string, string> = {
  filed: "filed",
  decided: "decided",
  executed: "executed",
};

/* ------------------------------------------------------- whose move is it - */

/**
 * The fourth question — whose move, and what act — for a recommendation.
 *
 * The spec's rule is NEVER AMBIGUOUS: the old chip named an owner and left the
 * obligation to be guessed, and it named the wrong owner. So this returns null
 * rather than a half-sentence whenever the spine did not state an actor, and
 * the card renders nothing instead of "Next move: ".
 *
 * The ACT is the spine's `next_actor_why` where it sent one. It is not
 * paraphrased here: the desk has twice shipped a divergence by keeping a
 * second opinion in TypeScript about something the spine already answered.
 */
export function nextMoveLine(r: {
  next_actor_resolved?: string | null; next_actor?: string | null;
  next_actor_why?: string | null;
} | null | undefined): { actor: string; why: string | null } | null {
  const raw = r?.next_actor_resolved ?? r?.next_actor ?? null;
  if (typeof raw !== "string") return null;
  const actor = raw.trim();
  // `unknown` is the spine saying it could not read an owner. Naming it as the
  // next mover would turn an unmeasurable into an instruction.
  if (!actor || actor === "unknown") return null;
  const why = (r?.next_actor_why ?? "").trim();
  return { actor, why: why || null };
}
