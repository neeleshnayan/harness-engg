/**
 * THE CARD'S PICTURE — what a reader learns before reading a word.
 *
 * THE CEO, 2026-08-27, on the desk as it stood: *"I still dont quite like
 * it... like visually how it represents."* The rows were truthful, ranked,
 * clamped and plain-English, and they were still a **wall of text**. Every
 * fact a decision needs — how urgent, how big, how old, what kind of thing it
 * is — was a word, and words are read serially. A desk of 39 rows read
 * serially is a desk nobody scans.
 *
 * So four facts move OUT of the prose and into geometry:
 *
 *   | fact       | encoding                    | learned without reading |
 *   |------------|-----------------------------|-------------------------|
 *   | priority   | the spine's TONE            | is anything on fire     |
 *   | age        | the spine's FILL            | how long has it waited  |
 *   | money      | a proportional BAR          | which one is the big one|
 *   | kind       | an inline-stroke SVG glyph  | what species is this    |
 *
 * ONE FUNCTION, ONE INPUT, FOUR ENCODINGS — and that is a correctness
 * property, not tidiness. They describe one row; computed separately in the
 * component they drift, and a card whose spine says "overdue" beside a bar
 * that says "unpriced" beside a glyph that says "research" is four opinions
 * with no owner. The ENG1 rule, applied to pixels: several fields describing
 * one condition are computed once from one input, and the unreadable case is
 * an INPUT VALUE rather than a patch afterwards.
 *
 * FOUR RULES THE ENCODINGS OBEY, each from a standing lesson:
 *
 *   1. **ZERO IS QUIET.** `$0.00` at stake is a real measurement and it earns
 *      NO bar. 124 of the 200 priced rows on the live desk are exactly zero;
 *      a bar on each would be 124 pieces of furniture carrying no information.
 *   2. **ABSENT IS NOT ZERO AND MUST NOT LOOK LIKE IT.** An unpriced row gets
 *      a *different rendering*, never a zero-width bar — a zero-width bar and
 *      a missing bar are the same pixels, which is absence-as-zero drawn
 *      instead of written.
 *   3. **AGE NEVER DIMS THE CARD.** A progressive fade was the obvious
 *      encoding and it is backwards: the row that has waited longest is the
 *      one that most needs reading, and fading it makes the oldest thing on
 *      the desk the hardest to see. Age fills the spine instead — information
 *      with no legibility cost.
 *   4. **COLOUR IS SPENT ONCE.** Hierarchy comes from type and space; the
 *      warn tone is reserved for the one condition on this desk that is true
 *      whether or not anybody clicks — a dated commitment already past. The
 *      CEO desk already spends amber on exactly that, on the count in its
 *      header, and this spends it on the same rows and no others.
 *
 * Every field carries a `why`. The illumination principle says a figure with
 * no path back to the record is decoration, and that binds a RECTANGLE just
 * as hard as a number: the component puts each `why` in a `title`, so a
 * reader who wonders why a spine is amber can ask the spine.
 */

/* ------------------------------------------------------------ the input --- */

/**
 * One row's facts, as the desk already holds them.
 *
 * DELIBERATELY NOT `DeskItem`. This module must be callable from the CEO
 * desk, the chair desk, the seat pages and the ticket board, whose row types
 * agree about nothing except these five facts — and a geometry module that
 * imported one page's type would have to be forked for the next page, which
 * is how a shared component stops being shared.
 */
export interface CardFacts {
  /** `YYYY-MM-DD`, or absent. The desk's own `due_date`. */
  dueDate?: string | null;
  /** Dollars at stake. `0` is a MEASUREMENT; `null`/`undefined` is not. */
  moneyAtStake?: number | null;
  /** How long this row has been waiting, in hours. Absent when the record
   *  carries no usable timestamp — which is a finding, not a zero. */
  ageHours?: number | null;
  /** The spine's free-text `kind`. 23 distinct values across 39 live rows, so
   *  this is matched by FAMILY and never enumerated. */
  kind?: string | null;
  /** How hard the decision is to take back. Drives the existing type scale
   *  (`deskCardStyle.ts`) and is read here only to break a band tie. */
  reversibility?: string | null;
}

/** The instant the row is judged against, and the denominator its money bar
 *  is drawn against. Both are the CALLER'S, never the browser's clock or a
 *  guess: the desk threads the FUND's `now` everywhere for the same reason. */
export interface CardScale {
  /** ISO instant. The date half is compared against `dueDate`. */
  now: string;
  /**
   * The dollar figure a full-width money bar represents.
   *
   * `null` when the caller could not compute one — an empty set, or a set in
   * which nothing is priced. The bar is then NOT DRAWN and says why, because
   * a bar with no denominator is a rectangle pretending to be a measurement.
   */
  moneyFullScaleUsd: number | null;
  /** Where that denominator came from, in words, for the bar's `title`. */
  moneyScaleWhy: string;
}

/* ------------------------------------------------------------- the band --- */

/**
 * Three tones and no fourth. `blocker` is the only one that spends colour.
 *
 * `unknown` is deliberately absent: a row with no date is not an unreadable
 * row, it is a row with no date, and it is `quiet`. Where a row's date CANNOT
 * be read — a malformed string in the record — the band reports `quiet` and
 * `bandWhy` says the date was unreadable, so the failure is stated in words
 * rather than given a tone the eye would read as a severity.
 */
export type BandTone = "blocker" | "dated" | "quiet";

export interface CardBand {
  tone: BandTone;
  /** The word for the tone, for a screen reader and for the `title`. */
  label: string;
  /** The same fact in a form that fits a 7.5rem column at 10px — `3d late`,
   *  `today`, `28 Aug`. Its own field rather than a truncation at the render
   *  site: a label the component clips is a label whose meaning the component
   *  decided. */
  short: string | null;
  why: string;
  /** How many whole days past due. `null` unless the tone is `blocker`. */
  daysOverdue: number | null;
  /** The VALIDATED `YYYY-MM-DD`, or null when the row states none or states
   *  one that could not be read. The card prints this; nothing re-validates
   *  the raw string a second time. */
  due: string | null;
}

/**
 * Is the day part of `iso` a readable `YYYY-MM-DD`?
 *
 * String comparison is what the spine's own `_overdue` does, so this uses the
 * same comparison rather than parsing to Date — two implementations of "is it
 * late" is exactly the pattern this desk has been repaired from twice. But it
 * VALIDATES the shape first: `"soon"` sorts after `"2026-08-27"` and would
 * read as a future date forever.
 */
function readableDay(v: string | null | undefined): string | null {
  const s = (v ?? "").slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s : null;
}

/** Whole days between two `YYYY-MM-DD` strings, `b - a`. UTC by construction:
 *  both operands are dates, never instants, so there is no zone to get wrong. */
function daysBetween(a: string, b: string): number {
  const ms = Date.parse(`${b}T00:00:00Z`) - Date.parse(`${a}T00:00:00Z`);
  return Math.round(ms / 86_400_000);
}

//: Month names for the compact form. `28 Aug` reads at a glance where
//: `2026-08-28` does not; the full ISO date stays in `due` and in the title,
//: so nothing is lost and nobody has to parse a number back into a month.
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** `2026-08-28` -> `28 Aug`. The input is already shape-validated by
 *  `readableDay`, so this does no parsing of its own beyond the slice. */
function shortDay(iso: string): string {
  const m = Number(iso.slice(5, 7));
  const d = Number(iso.slice(8, 10));
  return `${d} ${MONTHS[m - 1] ?? iso.slice(5, 7)}`;
}

export function cardBand(facts: CardFacts, scale: CardScale): CardBand {
  const today = readableDay(scale.now);
  const due = readableDay(facts.dueDate);

  if (!due) {
    const stated = (facts.dueDate ?? "").trim();
    return {
      tone: "quiet",
      label: "no date",
      short: null,
      daysOverdue: null,
      due: null,
      why: stated
        ? `this row states a due date the desk cannot read ("${stated}") — `
          + "unreadable, so it is not treated as dated and not treated as late"
        : "this row carries no due date, so nothing about it is late",
    };
  }
  if (!today) {
    // The CALLER's clock is unreadable. Every row would otherwise silently
    // become "not overdue", which is the permissive direction on the one
    // condition that spends colour.
    return {
      tone: "dated",
      label: "dated",
      short: shortDay(due),
      daysOverdue: null,
      due,
      why: `due ${due}, but the instant to judge it against could not be read, `
        + "so whether it is late is UNKNOWN — shown as dated, not as on time",
    };
  }

  const over = daysBetween(due, today);
  if (over > 0) {
    return {
      tone: "blocker",
      label: over === 1 ? "1 day overdue" : `${over} days overdue`,
      short: `${over}d late`,
      daysOverdue: over,
      due,
      why: `due ${due}, and today is ${today} — this is the one condition on `
        + "this desk that is true whether or not anybody clicks, which is why "
        + "it is the only one that spends colour",
    };
  }
  return {
    tone: "dated",
    label: over === 0 ? "due today" : `due ${due}`,
    short: over === 0 ? "today" : shortDay(due),
    daysOverdue: null,
    due,
    why: over === 0
      ? `due ${due}, which is today`
      : `due ${due}, ${-over} day(s) from ${today}`,
  };
}

/* ------------------------------------------------------------- the money -- */

/**
 * Three renderings, because there are three facts and they are not degrees of
 * one another.
 *
 *   * `bar`       — a priced figure above zero. Width is proportional.
 *   * `zero`      — priced AT zero. No bar at all: zero is quiet.
 *   * `unpriced`  — nobody put a figure on this. NOT a bar of width zero.
 *   * `unscaled`  — priced, but the caller had no denominator to draw against.
 */
export type MoneyRender = "bar" | "zero" | "unpriced" | "unscaled";

export interface CardMoney {
  render: MoneyRender;
  /** The figure itself, `null` when unpriced. Printed beside the bar — the
   *  bar answers "which is the big one", the number answers "how big". */
  usd: number | null;
  /** `0`..`1`, and ONLY meaningful when `render === "bar"`. It is `0` on every
   *  other branch and a component must not draw it: a zero-width rectangle and
   *  an absent one are the same pixels. */
  fraction: number;
  label: string;
  why: string;
}

export function cardMoney(facts: CardFacts, scale: CardScale): CardMoney {
  const m = facts.moneyAtStake;
  if (m == null || !Number.isFinite(m)) {
    return {
      render: "unpriced", usd: null, fraction: 0,
      label: "not priced",
      why: "no dollar figure was filed with this row — which is not the same "
        + "as a figure of zero, and is rendered differently so the two can "
        + "never be confused at a glance",
    };
  }
  if (m === 0) {
    return {
      render: "zero", usd: 0, fraction: 0,
      label: "no money at stake",
      why: "this row was priced, and the price is zero — a measurement, drawn "
        + "as nothing because zero is quiet",
    };
  }
  const full = scale.moneyFullScaleUsd;
  if (full == null || !Number.isFinite(full) || full <= 0) {
    return {
      render: "unscaled", usd: m, fraction: 0,
      label: fmtUsdCompact(m),
      why: "this row is priced, but nothing on this list gave the bar a "
        + "denominator, so the figure is stated and no bar is drawn — a "
        + "rectangle with no scale is not a measurement",
    };
  }
  // Clamped, not wrapped: a figure above the denominator (a caller passing NAV
  // as the scale, with a row larger than NAV) draws full and says so, rather
  // than overflowing its track.
  const raw = Math.abs(m) / full;
  const fraction = Math.min(1, raw);
  return {
    render: "bar", usd: m, fraction,
    label: fmtUsdCompact(m),
    why: `${fmtUsdCompact(m)} of ${scale.moneyScaleWhy}`
      + (raw > 1 ? " — larger than the scale, drawn full" : ""),
  };
}

/** Money, short, for a chip beside a bar. `$1.8k`, `$630`, `$0.50`.
 *  Its own function rather than `format.money` because that one always prints
 *  cents and a card face is not a ledger line. */
export function fmtUsdCompact(n: number): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  if (a >= 1_000_000) return `${sign}$${(a / 1_000_000).toFixed(1)}M`;
  if (a >= 1_000) return `${sign}$${(a / 1_000).toFixed(1)}k`;
  if (a >= 10) return `${sign}$${Math.round(a)}`;
  return `${sign}$${a.toFixed(2)}`;
}

/**
 * The denominator, computed ONCE for a whole list.
 *
 * The bar's job is COMPARATIVE — "which of these is the big one" — so the
 * scale is the list's own largest priced figure rather than NAV. Scaling to
 * NAV was tried on paper and is worse for this list: the live desk's largest
 * row is $1,847 against a $2,003 fund, which would draw one bar at 92% and
 * thirty at under 5% — technically true and visually a single bar.
 *
 * Returns `null` when nothing on the list is priced, which the caller must
 * pass through rather than substituting a number: a bar drawn against an
 * invented denominator is a picture of nothing.
 */
export function moneyScale(rows: readonly CardFacts[]): Pick<
  CardScale, "moneyFullScaleUsd" | "moneyScaleWhy"> {
  const priced = rows
    .map((r) => r.moneyAtStake)
    .filter((v): v is number => v != null && Number.isFinite(v) && v !== 0)
    .map(Math.abs);
  if (priced.length === 0) {
    return {
      moneyFullScaleUsd: null,
      moneyScaleWhy: "nothing on this list carries a dollar figure above zero",
    };
  }
  const max = Math.max(...priced);
  return {
    moneyFullScaleUsd: max,
    moneyScaleWhy: `${fmtUsdCompact(max)}, the largest figure on this list `
      + `(${priced.length} of ${rows.length} rows are priced above zero)`,
  };
}

/* --------------------------------------------------------------- the age -- */

/**
 * Age fills the spine from the top. Four steps, not a continuum.
 *
 * A continuum would be honest and unreadable: the eye cannot compare two
 * nearly-equal fills, and the question the fill answers is categorical — has
 * this been here an hour, a day, a week, or longer than anyone should admit.
 * The exact hours ride the `title`, so nothing is lost.
 *
 * WHY NOT A FADE. The first draft dimmed the card with age. It is backwards:
 * the row that has waited longest is the one that most needs reading, and a
 * fade makes the oldest thing on the desk the hardest thing to see.
 */
export type AgeStep = 0 | 1 | 2 | 3 | 4;

export interface CardAge {
  /** `0` = unknown, `1` = today, `2` = days, `3` = a week, `4` = longer. */
  step: AgeStep;
  /** `0`..`1`, the fraction of the spine that is filled. `0` at step 0, and
   *  the component draws NOTHING there rather than an empty spine — an
   *  unfilled spine and an unknown age must not be the same picture. */
  fill: number;
  known: boolean;
  label: string;
  why: string;
}

//: The step boundaries, in hours. Named because two of them appear in the
//: labels below and a literal repeated in a sentence goes stale silently.
export const AGE_DAY_HOURS = 24;
export const AGE_WEEK_HOURS = 24 * 7;
export const AGE_LONG_HOURS = 24 * 21;

export function cardAge(facts: CardFacts): CardAge {
  const h = facts.ageHours;
  if (h == null || !Number.isFinite(h) || h < 0) {
    return {
      step: 0, fill: 0, known: false,
      label: "age unknown",
      why: "the record carries no usable timestamp for this row, so how long "
        + "it has waited is UNKNOWN — not new",
    };
  }
  const hours = h;
  const said = hours < 1 ? "under an hour"
    : hours < AGE_DAY_HOURS ? `${Math.round(hours)}h`
    : `${(hours / 24).toFixed(hours < AGE_WEEK_HOURS ? 1 : 0)}d`;

  if (hours < AGE_DAY_HOURS) {
    return { step: 1, fill: 0.25, known: true, label: said,
             why: `${said} old — filed today` };
  }
  if (hours < AGE_WEEK_HOURS) {
    return { step: 2, fill: 0.5, known: true, label: said,
             why: `${said} old — more than a day, less than a week` };
  }
  if (hours < AGE_LONG_HOURS) {
    return { step: 3, fill: 0.75, known: true, label: said,
             why: `${said} old — over a week` };
  }
  return { step: 4, fill: 1, known: true, label: said,
           why: `${said} old — over three weeks on the desk` };
}

/* ------------------------------------------------------------- the glyph -- */

/**
 * What species of thing this is, as a shape.
 *
 * `kind` IS FREE TEXT AND IS NOT ENUMERABLE. The live desk carries 23
 * distinct values across 39 rows — `awaits-ceo`, `threshold-proposal`,
 * `harness_defect`, `universe_decision`, `written-reason-update` — with both
 * hyphens and underscores, filed by whichever seat wrote the run record. A
 * lookup table keyed on the exact string would match `awaits-ceo` (16 rows)
 * and fall through on the other 22 values, which is a glyph that says
 * "unclassified" on more than half the desk.
 *
 * So kinds are matched by KEYWORD, in a stated order, and the fallthrough is
 * VISIBLE: `unclassified` has its own shape and its own word, and
 * `glyphBasis` says whether the family was matched or defaulted. A default
 * silently wearing another family's shape is the failure this arrangement
 * exists to prevent.
 */
export type GlyphFamily =
  | "decision" | "threshold" | "defect" | "research"
  | "position" | "challenge" | "unclassified";

export interface CardGlyph {
  family: GlyphFamily;
  label: string;
  /** `"matched"` when a keyword fired, `"default"` when nothing did, and
   *  `"absent"` when the row carried no kind at all. Three inputs, three
   *  answers — an absent kind and an unrecognised one are different facts
   *  about the filing seat. */
  basis: "matched" | "default" | "absent";
  why: string;
}

/**
 * Keyword -> family, in precedence order. FIRST MATCH WINS and the order is
 * load-bearing: `threshold_question` contains both "threshold" and
 * "question", and it is a threshold matter before it is a question.
 */
const GLYPH_KEYWORDS: readonly (readonly [string, GlyphFamily])[] = [
  ["challenge", "challenge"],
  ["threshold", "threshold"],
  ["risk", "threshold"],
  ["limit", "threshold"],
  ["defect", "defect"],
  ["alarm", "defect"],
  ["incident", "defect"],
  ["exit", "position"],
  ["position", "position"],
  ["allocation", "position"],
  ["order", "position"],
  ["universe", "research"],
  ["research", "research"],
  ["data", "research"],
  ["probe", "research"],
  ["menu", "research"],
  ["decision", "decision"],
  ["awaits", "decision"],
  ["approval", "decision"],
  ["policy", "decision"],
  ["governance", "decision"],
  ["question", "decision"],
  // `written-reason-update` was the ONE live kind that reached the
  // fallthrough when this table was first written against the record. A
  // written reason attaches to a decision — the constitution requires one
  // with every threshold move — so it belongs with decisions rather than
  // wearing the "kind not recognised" shape on the CEO's desk.
  ["reason", "decision"],
];

export const GLYPH_LABEL: Readonly<Record<GlyphFamily, string>> = {
  decision: "a decision",
  threshold: "a threshold or a limit",
  defect: "a defect or an alarm",
  research: "research or data",
  position: "the book",
  challenge: "a challenge",
  unclassified: "kind not recognised",
};

export function cardGlyph(facts: CardFacts): CardGlyph {
  const raw = (facts.kind ?? "").trim();
  if (!raw) {
    return {
      family: "unclassified", basis: "absent",
      label: "no kind filed",
      why: "this row was filed with no kind, so what species of thing it is "
        + "is UNKNOWN — the shape says so rather than guessing",
    };
  }
  const hay = raw.toLowerCase();
  for (const [word, family] of GLYPH_KEYWORDS) {
    if (hay.includes(word)) {
      return {
        family, basis: "matched", label: GLYPH_LABEL[family],
        why: `kind ${raw} — matched on ${word}`,
      };
    }
  }
  return {
    family: "unclassified", basis: "default",
    label: GLYPH_LABEL.unclassified,
    why: `kind ${raw} — no family recognises it, so it gets its own shape `
      + "rather than borrowing one",
  };
}

/* ------------------------------------------------------------ the whole --- */

export interface CardGeometry {
  band: CardBand;
  money: CardMoney;
  age: CardAge;
  glyph: CardGlyph;
}

/**
 * THE ONE CALL. Four encodings of one row, from one input, in one place.
 *
 * A component that assembled these itself would be four call sites able to
 * disagree — and the disagreement would be invisible, because nothing on a
 * rendered card says which fact each rectangle came from.
 */
export function cardGeometry(facts: CardFacts, scale: CardScale): CardGeometry {
  return {
    band: cardBand(facts, scale),
    money: cardMoney(facts, scale),
    age: cardAge(facts),
    glyph: cardGlyph(facts),
  };
}

/**
 * The band's sort weight — `0` first.
 *
 * Published so a caller that ALSO sorts cannot invent a second opinion about
 * which band outranks which. It is not a ranking of rows (the desk's own
 * `rankDeskItems` owns that, on due date then money); it is the tie-break
 * inside one visual language, and it exists so a page that groups by band
 * groups in the order the tones read.
 */
export const BAND_ORDER: Readonly<Record<BandTone, number>> = {
  blocker: 0, dated: 1, quiet: 2,
};
