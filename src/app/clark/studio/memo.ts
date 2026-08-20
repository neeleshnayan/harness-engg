/**
 * Memo text discipline — one implementation, used by every surface that shows
 * a memo.
 *
 * `memoParts` was written inside ApprovalQueue.tsx for the approval card (CEO
 * direction 2026-08-20: "think the PM is submitting a memo to the CEO — a high
 * level view, expandable to dig deep as needed"). The office now renders traces
 * as memo threads and needs the SAME headline rule, so the function moved here
 * rather than being copied: two readings of the same rationale that drift apart
 * is how a reader ends up trusting whichever one is shorter.
 *
 * Pure string work, no React, no spine — so it is testable and cannot invent.
 */

export interface MemoParts {
  /** A leading ticket id ("B3:"), peeled off into chrome. */
  ticket: string | null;
  /** The one sentence a reader takes standing up. */
  headline: string;
  /** Everything after it; "" when there is nothing more. */
  rest: string;
}

/**
 * Read a memo body as headline + depth.
 *
 * The provenance marker (`[pm · rec 6]`) is stripped because a chip already
 * renders it; a leading ticket id is peeled off for the same reason. The
 * headline is the first sentence — and when there is no sentence boundary the
 * WHOLE text is the headline, never a truncation that could cut a "not" off
 * the front of a claim.
 */
export function memoParts(rationale?: string | null): MemoParts {
  let text = (rationale || "").trim();
  // strip the provenance marker — the chip already renders it
  text = text.replace(/^\[[^\]]+\]\s*/, "");
  const ticketMatch = /^([A-Z]\d+):\s*/.exec(text);
  const ticket = ticketMatch ? ticketMatch[1] : null;
  if (ticketMatch) text = text.slice(ticketMatch[0].length);
  const firstStop = text.search(/(?<=[.!?])\s/);
  if (firstStop === -1) return { ticket, headline: text, rest: "" };
  return {
    ticket,
    headline: text.slice(0, firstStop).trim(),
    rest: text.slice(firstStop).trim(),
  };
}

/**
 * The one-line SUBJECT of a memo card — the headline, ellipsised only when it
 * genuinely will not fit.
 *
 * Truncation is done here rather than with CSS `truncate` on the card so that
 * the ellipsis is part of the text a screen reader gets, and so the cut point
 * is the same on every surface. `max` is generous by default: a subject that
 * needs cutting usually means the seat wrote a paragraph where a subject
 * belonged, and hiding that is not this function's job.
 */
export function memoSubject(rationale?: string | null, max = 120): string {
  const { headline } = memoParts(rationale);
  const h = headline.replace(/\s+/g, " ").trim();
  if (!h) return "";
  if (h.length <= max) return h;
  return `${h.slice(0, max - 1).trimEnd()}…`;
}
