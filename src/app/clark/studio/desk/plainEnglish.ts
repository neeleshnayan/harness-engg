/**
 * PLAIN ENGLISH, CHECKED — the CEO-facing layer says what happened in words a
 * person reads once.
 *
 * CEO instruction, 2026-08-27, verbatim: *"plain english should be a direction
 * for all teams writing memo's for CEO"*. Applied to this surface: any text he
 * reads on a seat page, a console row or the room leads with what happened;
 * no file paths, no function names, no internal codenames; a number carries
 * its meaning before its digits; an ask reads as a question he can answer.
 *
 * **The register changes, the rigor never does.** The technical record stays
 * verbatim ONE TAP DOWN — this module is not a licence to be vague, and every
 * sentence it passes still has to be true. A plain sentence that hides a
 * caveat is worse than a technical one that states it.
 *
 * WHY A CHECKER RATHER THAN CARE. A style direction that lives only in a brief
 * decays at the first hurry, and nothing goes red. This gives it a test. It is
 * DELIBERATELY NARROW — it sweeps the strings this slice's own modules emit,
 * named in `plainEnglish.test.ts`, and makes no claim about the hundreds of
 * pre-existing strings elsewhere in the studio. A checker that went red on
 * ninety files nobody was editing would be turned off in a week, and a turned-
 * off checker is the unwired kill switch this firm keeps paying for.
 *
 * WHAT IT CANNOT SEE, said plainly so nobody reads a green run as a proof of
 * good writing: it cannot tell whether a sentence is CLEAR, whether it leads
 * with the point, or whether it is true. It catches the mechanical half —
 * paths, identifiers, and a named list of house codenames the CEO does not
 * use. The other half is the look-pass and a human's judgement.
 */

/** House words that mean something precise to an engineer and nothing to the
 *  person reading the page. Each one has a plain replacement in use:
 *  spine -> "the fund's record" · payload -> "what it sent" ·
 *  fold -> "below" / "one tap down" · endpoint -> "the record". */
export const CODENAMES = [
  "spine", "payload", "endpoint", "envelope", "the fold", "in the fold",
  "flight recorder", "event log", "desk_load", "open_dispatches", "activity",
  "renderer", "fixture", "null", "undefined", "boolean",
];

export interface PlainFinding {
  kind: "path" | "identifier" | "call" | "codename" | "code_quote";
  found: string;
}

/** A file path, or a bare filename with a source/document extension. */
const PATH = /\b[\w./-]*\.(py|ts|tsx|js|jsx|json|md|css|sql|yml|yaml)\b|\b(?:app|src|docs|tests|scripts)\/[\w./-]+/gi;
/** `snake_case` — the shape every field name on this record takes. */
const SNAKE = /\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/g;
/** `camelCase` and `PascalCase` compounds. `A` single capitalised word is a
 *  name, not an identifier, so the pattern needs a lower-then-upper hinge. */
const CAMEL = /\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b[A-Z][a-z]+[A-Z][A-Za-z0-9]*\b/g;
/** A function call, with or without arguments. */
const CALL = /\b[\w.]+\([^)]*\)/g;
/** Backticked code, which is a technical register by construction. */
const QUOTED = /`[^`]+`/g;

/**
 * Everything in `text` that does not belong in front of the CEO.
 *
 * Returns the findings rather than a boolean, because a checker that says
 * "no" without saying what is a checker people route around.
 */
export function jargonIn(text: string): PlainFinding[] {
  const out: PlainFinding[] = [];
  const push = (kind: PlainFinding["kind"], re: RegExp) => {
    for (const m of text.matchAll(re)) out.push({ kind, found: m[0] });
  };
  push("path", PATH);
  push("call", CALL);
  push("code_quote", QUOTED);
  // Identifiers are checked AFTER paths so that `desk.py` is reported once, as
  // a path, rather than twice under two names.
  const withoutPaths = text.replace(PATH, " ").replace(CALL, " ");
  for (const m of withoutPaths.matchAll(SNAKE)) out.push({ kind: "identifier", found: m[0] });
  for (const m of withoutPaths.matchAll(CAMEL)) out.push({ kind: "identifier", found: m[0] });
  const lower = ` ${text.toLowerCase()} `;
  for (const w of CODENAMES) {
    // Word-bounded so "activity" does not fire inside "inactivity", and so a
    // codename ending a sentence is still caught.
    if (new RegExp(`(^|[^a-z])${w.replace(/ /g, "\\s+")}([^a-z]|$)`).test(lower)) {
      out.push({ kind: "codename", found: w });
    }
  }
  return out;
}

/** True when the text is fit to put in front of the CEO, mechanically. */
export function isPlain(text: string): boolean {
  return jargonIn(text).length === 0;
}

/**
 * A number said the way a person says it: meaning first, digits in brackets.
 *
 * The CEO's direction, verbatim: *numbers carry their meaning ("a quarter of
 * marks arrive late", raw figure in parentheses after, never leading)*. So
 * `meaning("2 of the 4 need you", "2/4")` reads "2 of the 4 need you (2/4)".
 * The raw form is OPTIONAL and omitted when it would only repeat the meaning —
 * a bracket that echoes the sentence is chrome.
 */
export function meaning(sentence: string, raw?: string | null): string {
  const r = raw?.trim();
  return r ? `${sentence} (${r})` : sentence;
}
