import test from "node:test";
import assert from "node:assert/strict";

import {
  EMPTY_LINGER, LINGER_LABEL, LINGER_MS, isLingering, lingering, trackDecisions,
} from "./justDecided.ts";

/**
 * APPROVED → MOVING TO EXECUTION.
 *
 * CEO 2026-08-27: *"if I approve something then lets move it out of awaiting
 * for you (we can keep a 30secs timer before it clears out and it can be
 * tagged visually that approved ->moving to execution or something)"*.
 *
 * THE DEFECT THIS FILE EXISTS AGAINST is the obvious implementation: tag
 * anything whose status is approved. That version un-clears the desk on every
 * reload — thirty seconds of already-decided rows, for ever, on a page whose
 * whole purpose is to stop showing him things he has finished with.
 * `a row already decided on FIRST SIGHT never lingers` is the test that
 * separates the two, and no other test in this file can tell them apart.
 */

const rows = (...pairs: [string, string][]) =>
  pairs.map(([id, status]) => ({ id, status }));

test("a row already decided on FIRST SIGHT never lingers", () => {
  // THE RELOAD CASE. The page opens on a desk that already holds approvals.
  const s = trackDecisions(EMPTY_LINGER, rows(["a", "accepted"], ["b", "done"]), 1000);
  assert.deepEqual(lingering(s, 1000), []);
  assert.equal(isLingering(s, "a", 1000), false);
  // And it still does not linger on the next poll.
  const s2 = trackDecisions(s, rows(["a", "accepted"], ["b", "done"]), 2000);
  assert.deepEqual(lingering(s2, 2000), []);
});

test("a row watched leaving `open` lingers", () => {
  const seen = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 1000);
  const after = trackDecisions(seen, rows(["a", "accepted"]), 5000);
  assert.deepEqual(lingering(after, 5000), ["a"]);
  assert.equal(isLingering(after, "a", 5000), true);
});

test("the linger ends after exactly thirty seconds, and not before", () => {
  const seen = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0);
  const after = trackDecisions(seen, rows(["a", "accepted"]), 0);
  assert.equal(isLingering(after, "a", LINGER_MS - 1), true);
  assert.equal(isLingering(after, "a", LINGER_MS), false,
    "the boundary is exclusive — at exactly 30s it is gone");
  assert.equal(isLingering(after, "a", LINGER_MS + 1), false);
});

test("polling does NOT restart the clock — the linger would never end", () => {
  // The page refetches every 15s. A fold that re-stamped `decidedAt` on every
  // render where the status is still decided would make the tag permanent.
  let s = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0);
  s = trackDecisions(s, rows(["a", "accepted"]), 1000);
  s = trackDecisions(s, rows(["a", "accepted"]), 16_000);
  s = trackDecisions(s, rows(["a", "accepted"]), 31_000);
  assert.equal(s.decidedAt["a"], 1000, "the stamp is the moment it was watched");
  assert.equal(isLingering(s, "a", 31_500), false);
});

test("every decided status counts, and `open` never does", () => {
  for (const status of ["accepted", "approved", "rejected", "declined",
    "staged", "done", "noted"]) {
    const seen = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0);
    const after = trackDecisions(seen, rows(["a", status]), 100);
    assert.equal(isLingering(after, "a", 100), true, status);
  }
  const stillOpen = trackDecisions(
    trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0), rows(["a", "open"]), 100);
  assert.equal(isLingering(stillOpen, "a", 100), false);
});

test("an unrecognised new status does not linger — it is not a decision", () => {
  const seen = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0);
  const after = trackDecisions(seen, rows(["a", "in_flight"]), 100);
  assert.equal(isLingering(after, "a", 100), false);
});

test("an absent status is not a decision and does not throw", () => {
  const seen = trackDecisions(EMPTY_LINGER,
    [{ id: "a", status: "open" }], 0);
  const after = trackDecisions(seen,
    [{ id: "a", status: null }, { id: "b", status: undefined }], 100);
  assert.equal(isLingering(after, "a", 100), false);
  assert.equal(after.seen["b"], "");
});

test("a row that vanishes is DROPPED from both maps — no unbounded growth", () => {
  let s = trackDecisions(EMPTY_LINGER, rows(["a", "open"], ["b", "open"]), 0);
  s = trackDecisions(s, rows(["a", "accepted"]), 100);
  assert.deepEqual(Object.keys(s.seen), ["a"]);
  assert.deepEqual(Object.keys(s.decidedAt), ["a"]);
  // And a row returning after an absence is a FIRST SIGHT again, so it is not
  // compared against a stale status from an hour ago.
  const back = trackDecisions(s, rows(["a", "accepted"], ["b", "accepted"]), 200);
  assert.equal(isLingering(back, "b", 200), false);
});

test("the fold returns a NEW state — a mutation would be missed by React", () => {
  const before = trackDecisions(EMPTY_LINGER, rows(["a", "open"]), 0);
  const after = trackDecisions(before, rows(["a", "accepted"]), 100);
  assert.notEqual(before, after);
  assert.notEqual(before.seen, after.seen);
  assert.equal(before.seen["a"], "open", "the previous state is untouched");
});

test("the tag names BOTH halves — what happened and what happens next", () => {
  assert.match(LINGER_LABEL, /approved/);
  assert.match(LINGER_LABEL, /moving to execution/);
});
