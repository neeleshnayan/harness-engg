/**
 * LOADING IS NOT UNREADABLE — the third state of a read.
 *
 * THE DEFECT, reported by the CEO himself (ticket fccb9cf3, 2026-08-24).
 * During a recompile after the D42 merge his desk sat for about thirty seconds
 * saying *"The desk could not be read… UNKNOWN — not none"* — the fund's
 * loudest honesty sentence — while the fetch was merely PENDING. Nothing had
 * failed. The page had asked a question and had not yet been answered, and it
 * reported that as an outage.
 *
 * The cause is one expression repeated across three pages: `desk !== null`.
 * `null` is the initial state of the payload AND the value it is reset to when
 * a fetch rejects, so a boolean read off it cannot tell "not yet" from
 * "not ever". A page that collapses them is making an absence claim it has not
 * measured — the same class of error as absence-rendered-as-zero, one step
 * earlier: here it is UNCERTAINTY rendered as a failure.
 *
 * SO THE ABSENCE DISCIPLINE IS NOT WEAKENED BY THIS MODULE; IT IS SPLIT IN
 * TWO. Unknown-because-the-read-failed keeps every word of its loud sentence,
 * unchanged and still on the warn tone. Unknown-because-the-read-has-not-
 * returned gets its own true sentence, quiet, and it says what it is doing.
 * Neither state ever renders a count.
 *
 * WHERE THE DEADLINE LIVES, and why this module does not own one. A read that
 * hangs forever would sit on "loading" forever, so "loading" is only honest if
 * something eventually ends it. It does: `fundApi` is an axios client with
 * `timeout: 60000` (src/lib/fund_api.ts:24), so a request that never answers
 * REJECTS at sixty seconds with axios's own message, and the page then takes
 * the `failed` branch like any other failure. That is one deadline, owned by
 * the transport, measured in the source. A second stopwatch here — a UI
 * watchdog with an invented number — would be two clocks on one read, which is
 * the defect this desk has already shipped in its counters twice.
 */

/** The three things a page can know about one read. Never a boolean. */
export type DeskRead = "loading" | "unreadable" | "readable";

/**
 * @param got   the payload arrived and is what is on screen.
 * @param failed the read settled REJECTED (network, status, or the client's
 *   own 60s timeout). A boolean, never an error string: a rejection whose
 *   message happens to be empty is still a rejection, and a page that
 *   discriminated on the string would show "reading…" forever for it.
 *
 * PRECEDENCE, stated because the pages differ and both are defensible.
 * `got` wins over `failed`: `[seat]/page.tsx` keeps the last payload when a
 * later poll rejects, so it has both — and what is on screen there is real,
 * with the failure of the refresh reported separately in its own banner. The
 * CEO desk clears the payload on failure, so it never reaches this case.
 */
export function readState(got: boolean, failed: boolean): DeskRead {
  if (got) return "readable";
  if (failed) return "unreadable";
  return "loading";
}

/**
 * The message for a rejected read, GUARANTEED NON-EMPTY.
 *
 * Every page wrote `e instanceof Error ? e.message : "unreachable"` inline and
 * then fed the result to a `{err && …}` truthiness test. `new Error().message`
 * is `""`, so any rejection carrying an empty message would have silenced the
 * banner AND — now that a page discriminates three states — left it reading
 * "reading…" for a read that had already failed. That is a structural hole in
 * the discriminator, not a measured axios behaviour: it is closed here rather
 * than argued about, because the cost is one function.
 */
export function readError(reason: unknown): string {
  const raw = reason instanceof Error ? reason.message : String(reason ?? "");
  const t = raw.trim();
  return t || "unreachable";
}

/**
 * The one loading sentence, so three pages cannot phrase it three ways.
 *
 * IT IS SAID ONCE PER SURFACE, NOT ONCE PER SENTENCE. The first cut prefixed
 * it to every derived note — the hero's gloss, the shelf line, all five lane
 * notes — and the rendered page carried it ELEVEN TIMES in one screen, which
 * is the "generic AI slop" the CEO named as this desk's failure mode and is no
 * calmer for being quiet. Found by looking at the screenshot, not by any test.
 * The derived notes now state their own fact ("… has not been counted yet")
 * and let the greeting and the muted `…` in the hero carry the activity.
 */
export const READING_DESK = "Reading the desk…";
