import test from "node:test";
import assert from "node:assert/strict";

import { readState, readError, READING_DESK } from "./deskRead.ts";

/**
 * THE THREE STATES.
 *
 * The property under test is the precedence rule stated in the module's own
 * docstring: `got` wins over `failed`, unconditionally. The four input
 * combinations are tested individually — including the one combination
 * (got=true, failed=true) that a naive `failed ? "unreadable" : ...` ordering
 * would get wrong — because a switch-order bug that silently regressed the
 * precedence would only show up in that specific cell of the truth table.
 */

test("readState(got=true, failed=false) is readable", () => {
  assert.equal(readState(true, false), "readable");
});

test("readState(got=true, failed=true) is STILL readable — got wins", () => {
  // This is the cell the docstring calls out by name: a page that keeps the
  // last payload when a later poll rejects has something real on screen, and
  // the precedence says so must not be shadowed by the failed flag.
  assert.equal(readState(true, true), "readable");
});

test("readState(got=false, failed=true) is unreadable", () => {
  assert.equal(readState(false, true), "unreadable");
});

test("readState(got=false, failed=false) is loading", () => {
  assert.equal(readState(false, false), "loading");
});

/* --------------------------------------------------------------- readError */

/**
 * THE NON-EMPTY GUARANTEE.
 *
 * The callers feed the result to a truthiness test (`{err && …}`), so the one
 * property that matters above all others is: never empty. Each test below
 * targets a distinct branch of the function so that a regression in one
 * branch cannot hide behind an assertion that another branch would also
 * satisfy.
 */

test("an Error with a message returns that exact message", () => {
  // The message is deliberately distinctive — not a string any fallback
  // branch could also produce — so this assertion can only pass if the
  // Error branch actually read `.message` rather than falling through.
  const e = new Error("network timeout after 60000ms");
  assert.equal(readError(e), "network timeout after 60000ms");
});

test("new Error('') returns 'unreachable' — an empty message is still a rejection", () => {
  // This is the whole point of the module: `new Error().message` is `""`,
  // and a page discriminating on the raw string would show nothing for a
  // rejection that truly happened.
  assert.equal(readError(new Error("")), "unreachable");
});

test("new Error('   ') (whitespace only) also returns 'unreachable'", () => {
  // A message that is present but blank is functionally the same failure as
  // an absent one; the function trims before deciding, so this must not slip
  // through as a "real" message consisting only of spaces.
  assert.equal(readError(new Error("   ")), "unreachable");
});

test("a non-Error string reason is returned verbatim, not coerced to 'unreachable'", () => {
  // Proves the non-Error branch actually stringifies the reason instead of
  // just always falling back — a distinct claim from the two tests above,
  // which only exercise the Error branch.
  assert.equal(readError("boom"), "boom");
});

test("a non-Error, non-string reason is stringified, not coerced to 'unreachable'", () => {
  assert.equal(readError(42), "42");
  assert.equal(readError({ code: 7 }), "[object Object]");
});

test("null and undefined reasons fall back to 'unreachable' via the non-Error branch", () => {
  // `String(reason ?? "")` collapses both to "", so this exercises the same
  // fallback text as the empty-Error tests above, but through the OTHER
  // branch of the ternary — a distinct code path producing the same word.
  assert.equal(readError(null), "unreachable");
  assert.equal(readError(undefined), "unreachable");
});

test("readError(reason) is always a non-empty string, over a table of varied inputs", () => {
  const table: unknown[] = [
    new Error("a real failure"),
    new Error(""),
    new Error("   "),
    "a plain string reason",
    "",
    "   ",
    42,
    0,
    null,
    undefined,
    { message: "looks like an error but isn't one" },
    ["array", "reason"],
    false,
  ];
  for (const reason of table) {
    const msg = readError(reason);
    assert.equal(typeof msg, "string", `readError(${String(reason)}) must return a string`);
    assert.ok(msg.length > 0, `readError(${String(reason)}) must never be empty`);
  }
});

/* ------------------------------------------------------------ READING_DESK */

test("READING_DESK is non-empty and cannot be mistaken for the failure language", () => {
  assert.ok(READING_DESK.length > 0);
  // The loading sentence and the failure sentence must never share vocabulary
  // a reader could misread as "it already failed" — "could not" and "unknown"
  // are the fund's own words for a settled failure (per the module's
  // docstring on the split between the two unknown states).
  const lower = READING_DESK.toLowerCase();
  assert.ok(!lower.includes("could not"), "must not read like the failure sentence");
  assert.ok(!lower.includes("unknown"), "must not read like the failure sentence");
});
