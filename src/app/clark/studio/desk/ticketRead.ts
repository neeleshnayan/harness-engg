/**
 * THE FOURTH READ STATE — "this spine does not serve the highway yet".
 *
 * `deskRead.ts` split a read into three because `desk !== null` could not tell
 * "not yet" from "not ever", and the CEO watched his desk report a recompile as
 * an outage. The ticket endpoint adds a fact those three cannot express: it
 * ships with the ticket highway, and **a spine without that build answers 404**.
 *
 * A 404 IS NOT AN UNREADABLE RECORD. "The desk could not be read — UNKNOWN, not
 * none" is the fund's loudest honesty sentence and it means *something is
 * wrong*. Nothing is wrong when a spine simply does not carry an endpoint yet;
 * the honest sentence is "this build has no ticket highway", and printing the
 * alarm instead would train a reader to ignore it — which is how a real outage
 * gets missed later.
 *
 * DELIBERATELY NOT A NEW READ MODULE. `readState`/`readError` are unchanged and
 * still own the three states; this adds one discriminator on the failure and
 * one sentence, and nothing else. Two read vocabularies would be two answers to
 * one question, which is the defect this desk has already shipped twice.
 */

import { type DeskRead, readError } from "./deskRead.ts";

export type TicketReadFailure = "absent_endpoint" | "unreadable";

/**
 * Did this rejection mean "no such endpoint" or "the record could not be read"?
 *
 * READS THE STATUS OFF THE AXIOS ERROR, never the message string. A rejection
 * whose message happens to contain "404" is not the same fact as a response
 * that carried status 404, and a discriminator on prose would fire on the
 * former — the same class of error as `"import Event" in src` matching
 * `import EventType`.
 */
export function ticketFailureKind(reason: unknown): TicketReadFailure {
  const status = (reason as { response?: { status?: unknown } } | null)
    ?.response?.status;
  return status === 404 ? "absent_endpoint" : "unreadable";
}

/**
 * The sentence a ticket surface prints when it has no rows.
 *
 * `null` means the read succeeded — the caller then states what it MEASURED,
 * which is the only case where a count is a true thing to say.
 */
export function ticketReadNote(
  read: DeskRead, failure: TicketReadFailure, reason: unknown,
): string | null {
  if (read === "loading") return "Reading the ticket fold…";
  if (read !== "unreadable") return null;
  if (failure === "absent_endpoint") {
    return "This spine does not serve `GET /fund/tickets` — the ticket "
      + "highway ships on a build the chair has not merged. Nothing is wrong "
      + "with the record; there is simply no fold to read here yet. Every "
      + "count on this page is UNKNOWN, not zero.";
  }
  return `The ticket fold could not be read — ${readError(reason)}. Every `
    + "count on this page is UNKNOWN, not zero.";
}

/** Whether a surface may print numbers at all. One expression, so a page
 *  cannot render a count on one block and an absence sentence on another from
 *  the same read. */
export function ticketsCountable(read: DeskRead): boolean {
  return read === "readable";
}
