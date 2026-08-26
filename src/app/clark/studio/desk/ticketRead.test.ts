/**
 * THE FOURTH READ STATE — the tests the mutation pass proved were missing.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/ticketRead.test.ts`
 *
 * THIS FILE EXISTS BECAUSE TWO MUTANTS SURVIVED A GREEN SUITE OF 882 TESTS.
 * `ticketRead.ts` had no test at all, so both of its judgements could be
 * inverted without a single failure:
 *
 *   M59 — `ticketFailureKind` reading the ERROR MESSAGE instead of the HTTP
 *         status. The module's own comment warns against exactly this ("a
 *         rejection whose message happens to contain 404 is not the same fact
 *         as a response that carried status 404") and nothing enforced it. It
 *         is the `"import Event" in src` matching `import EventType` defect,
 *         one layer up.
 *   M60 — `ticketsCountable` accepting a LOADING read. A page that counted
 *         while the read was in flight would render "0 decisions await you"
 *         over an unanswered question, which is ticket fccb9cf3 in reverse.
 *
 * The discrimination matters because the two failures deserve OPPOSITE tones.
 * "The record could not be read" is the fund's loudest honesty sentence and it
 * means something is wrong. Nothing is wrong when a spine simply has not
 * merged the ticket highway yet, and printing the alarm for that trains a
 * reader to ignore it — which is how a real outage gets missed later.
 */

import assert from "node:assert/strict";
import test from "node:test";

import { readState, type DeskRead } from "./deskRead.ts";
import {
  ticketFailureKind, ticketReadNote, ticketsCountable,
} from "./ticketRead.ts";

/** An axios-shaped rejection: the error carries the response, and the status
 *  lives on it. Built to the shape the client actually throws, not to a
 *  convenient one. */
function axiosError(status: number, message = "Request failed"): Error {
  const e = new Error(`${message} with status code ${status}`);
  (e as unknown as { response: { status: number } }).response = { status };
  return e;
}

/* --------------------------------------------------- the discriminator --- */

test("a 404 response is an absent endpoint, not an unreadable record", () => {
  assert.equal(ticketFailureKind(axiosError(404)), "absent_endpoint");
});

test("a 500 response IS an unreadable record", () => {
  assert.equal(ticketFailureKind(axiosError(500)), "unreadable");
  assert.equal(ticketFailureKind(axiosError(502)), "unreadable");
  assert.equal(ticketFailureKind(axiosError(503)), "unreadable");
});

test("THE STATUS IS READ, NOT THE MESSAGE — a 500 that mentions 404", () => {
  // THE MUTANT THIS KILLS. A message-matching discriminator would call this an
  // absent endpoint and print "nothing is wrong" over a server error. The
  // string "404" appears in real error prose more often than anyone expects —
  // proxy chains quote upstream statuses.
  const e = axiosError(500, "upstream /fund/tickets returned 404 to the proxy");
  assert.equal(ticketFailureKind(e), "unreadable");
});

test("AND A 404 WITH NO NUMBER IN ITS MESSAGE is still an absent endpoint", () => {
  // The other direction of the same mutant: a status-reading discriminator
  // does not need the number to appear in the prose at all.
  const e = new Error("Not Found");
  (e as unknown as { response: { status: number } }).response = { status: 404 };
  assert.equal(ticketFailureKind(e), "absent_endpoint");
});

test("a rejection with NO response at all is unreadable, not absent", () => {
  // A network failure, a DNS failure, or the client's own 60s timeout. None of
  // them means "this spine has no such endpoint", and defaulting to the
  // reassuring answer is the loosening direction.
  assert.equal(ticketFailureKind(new Error("ECONNREFUSED")), "unreadable");
  assert.equal(ticketFailureKind(null), "unreadable");
  assert.equal(ticketFailureKind(undefined), "unreadable");
  assert.equal(ticketFailureKind("404"), "unreadable");
  assert.equal(ticketFailureKind({ status: 404 }), "unreadable",
    "a bare object is not an axios rejection — the status lives on `response`");
});

/* --------------------------------------------------------- countability -- */

test("ONLY a readable payload may be counted", () => {
  // THE MUTANT THIS KILLS: `read !== "unreadable"` lets a LOADING page render
  // numbers, so "0 decisions await you" would appear over an unanswered fetch.
  assert.equal(ticketsCountable("readable"), true);
  assert.equal(ticketsCountable("loading"), false);
  assert.equal(ticketsCountable("unreadable"), false);
});

test("the three read states are walked, not sampled", () => {
  // A boundary table: every value of the union has a verdict here, so adding a
  // fourth state cannot slip through with an implicit answer.
  const states: DeskRead[] = ["loading", "unreadable", "readable"];
  const verdicts = states.map(ticketsCountable);
  assert.deepEqual(verdicts, [false, false, true]);
});

test("readState still owns the three states — this module adds none", () => {
  // Two read vocabularies would be two answers to one question. `ticketRead`
  // discriminates a FAILURE; it does not invent a fourth read state.
  assert.equal(readState(true, false), "readable");
  assert.equal(readState(false, true), "unreadable");
  assert.equal(readState(false, false), "loading");
});

/* ------------------------------------------------------------ the notes --- */

test("a readable page gets NO note, so it must state what it measured", () => {
  assert.equal(ticketReadNote("readable", "unreadable", null), null);
  assert.equal(ticketReadNote("readable", "absent_endpoint", null), null);
});

test("a loading page says it is reading, and says nothing about zero", () => {
  const n = ticketReadNote("loading", "unreadable", null)!;
  assert.match(n, /Reading the ticket fold/);
  assert.doesNotMatch(n, /could not be read/);
  assert.doesNotMatch(n, /UNKNOWN, not zero/);
});

test("an ABSENT endpoint says nothing is wrong, and still refuses zero", () => {
  // The two halves that make this sentence honest: it must NOT raise an alarm,
  // and it must still refuse to let a count be read as zero.
  const n = ticketReadNote("unreadable", "absent_endpoint", axiosError(404))!;
  assert.match(n, /Nothing is wrong with the record/);
  assert.match(n, /UNKNOWN, not zero/);
  assert.doesNotMatch(n, /could not be read/,
    "the alarm sentence is reserved for a record that genuinely failed");
});

test("an UNREADABLE record keeps every word of the alarm sentence", () => {
  const n = ticketReadNote("unreadable", "unreadable",
    new Error("ECONNREFUSED"))!;
  assert.match(n, /could not be read/);
  assert.match(n, /ECONNREFUSED/);
  assert.match(n, /UNKNOWN, not zero/);
  assert.doesNotMatch(n, /Nothing is wrong/);
});

test("SHARED-WORD AUDIT: the two failure sentences cannot satisfy each other", () => {
  // Both sentences contain "UNKNOWN, not zero" on purpose — that clause is the
  // invariant, not the discriminator. This test states which phrases are
  // shared and asserts each branch carries one phrase the other cannot.
  const absent = ticketReadNote("unreadable", "absent_endpoint", null)!;
  const broken = ticketReadNote("unreadable", "unreadable", new Error("x"))!;
  const shared = "UNKNOWN, not zero";
  assert.ok(absent.includes(shared) && broken.includes(shared));
  assert.ok(absent.includes("Nothing is wrong") && !broken.includes("Nothing is wrong"));
  assert.ok(broken.includes("could not be read") && !absent.includes("could not be read"));
});

test("an empty rejection message still produces a non-empty sentence", () => {
  // `new Error().message` is "" and a `{err && …}` truthiness test would then
  // silence the banner entirely. `readError` guarantees a word; this pins that
  // the guarantee survives the trip through here.
  const n = ticketReadNote("unreadable", "unreadable", new Error(""))!;
  assert.match(n, /unreachable/);
  assert.ok(n.trim().length > 40);
});
