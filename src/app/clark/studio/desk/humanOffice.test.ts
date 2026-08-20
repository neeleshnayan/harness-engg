/**
 * Tests for the human office — faces, memo subjects, the production shelf.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/humanOffice.test.ts`
 * (Node 22.6+, no runner dependency; same arrangement as seatLib.test.ts, which
 * this file deliberately does not touch.)
 *
 * A separate file because seatLib.test.ts is the derivations' guard and the
 * brief for this work states its tests must pass UNCHANGED. Everything here
 * guards a way the new visual layer could lie:
 *
 *   - a face invented for an actor nobody registered (attributing work to
 *     someone who never did it)
 *   - a PREFIX match handing the CTO's face to `cto-stale-guard: the GLD
 *     position this ticket closes was already sold…`, which is a real actor
 *     string in the live log today, and is a note, not a person
 *   - two colleagues drawn identically, which the eye believes instantly
 *   - a sentence verdict compressed into a one-word stamp that reads cleaner
 *     than the verdict the seat actually delivered
 *   - a run that filed nothing rendered as if it had produced nothing
 */

import assert from "node:assert/strict";
import test from "node:test";

import { FACES, faceFor, faceKey } from "./faces.ts";
import { memoParts, memoSubject } from "../memo.ts";
import { SEATS, productionShelf, verdictStamp } from "./seatLib.ts";

/* ----------------------------------------------------------------- faces -- */

test("every seat on the bench has a face, and it is the same face every time", () => {
  for (const s of SEATS) {
    const a = faceFor(s);
    const b = faceFor(s);
    assert.ok(a, `no face registered for the ${s} seat`);
    assert.equal(a, b, "faceFor must be deterministic — the same object, forever");
    assert.equal(a!.kind, "seat");
  }
  // The humans and machines that act on the desk log.
  for (const actor of ["ceo", "cto"]) {
    assert.ok(faceFor(actor), `no face for ${actor}, who appears on every desk event`);
  }
});

test("no two colleagues are drawn the same", () => {
  const seen = new Map<string, string>();
  for (const f of Object.values(FACES)) {
    const k = faceKey(f);
    const clash = seen.get(k);
    assert.equal(clash, undefined,
      `${f.id} and ${clash} share the drawing ${k} — two colleagues with one face`);
    seen.set(k, f.id);
  }
});

test("humans and machines are different silhouettes, so a policy is never mistaken for a person", () => {
  for (const f of Object.values(FACES)) {
    if (f.kind === "machine") {
      assert.equal(f.head, "square", `${f.id} is a machine but is drawn with a human head`);
    } else {
      assert.notEqual(f.head, "square", `${f.id} is a person/seat but is drawn as a machine`);
    }
  }
});

test("an unregistered actor gets NO face — never a generated one", () => {
  assert.equal(faceFor("vishesh"), null);
  assert.equal(faceFor(""), null);
  assert.equal(faceFor(null), null);
  assert.equal(faceFor(undefined), null);
  assert.equal(faceFor("external:lean"), null);
});

test("matching is anchored: a note that BEGINS with an actor name is not that actor", () => {
  // Verbatim from GET /fund/events on 2026-08-20 — the log's `actor` field is
  // free text and this row is a sentence, not an identity. A prefix match would
  // have drawn the CTO's face on it and attributed a guard's note to a person.
  const noteAsActor =
    "cto-stale-guard: the GLD position this ticket closes was already sold by the " +
    "phantom-price exit fire at 08:01Z; approving now would SHORT 0.424471 GLD. " +
    "Declined pending the incident fix.";
  assert.equal(faceFor(noteAsActor), null);
  assert.equal(faceFor("cto-something-else"), null);
  assert.equal(faceFor("ceo-designate"), null);
  assert.equal(faceFor("pm-bot"), null);
  // The two versioned aliases, and only in their anchored form.
  assert.equal(faceFor("auto-policy-v1")?.id, "auto-policy");
  assert.equal(faceFor("auto-policy-v12")?.id, "auto-policy");
  assert.equal(faceFor("auto-policy-v1-experimental"), null);
  assert.equal(faceFor("claude:on-operator-instruction")?.id, "clark");
  assert.equal(faceFor("claudette"), null);
});

test("actor ids are matched case- and whitespace-insensitively, because the log is free text", () => {
  assert.equal(faceFor("  PM  ")?.id, "pm");
  assert.equal(faceFor("CTO")?.id, "cto");
});

/* ---------------------------------------------------------- memo subjects -- */

test("the memo subject is the first sentence, with the chip's markers peeled off", () => {
  const r = "[pm · rec 6] B3: Trim INTC to the mandate band. The position is 41% of gross.";
  const p = memoParts(r);
  assert.equal(p.ticket, "B3");
  assert.equal(p.headline, "Trim INTC to the mandate band.");
  assert.equal(p.rest, "The position is 41% of gross.");
  assert.equal(memoSubject(r), "Trim INTC to the mandate band.");
});

test("a subject with no sentence boundary is shown WHOLE, never cut mid-claim", () => {
  // The failure this guards: truncating "do not deploy" to "do not" — or worse,
  // to "do" — turns a refusal into an instruction.
  const s = "do not deploy this until the benchmark fix lands";
  assert.equal(memoSubject(s), s);
  assert.equal(memoParts(s).rest, "");
});

test("an over-long subject is ellipsised in the TEXT, so what was cut is legible to a reader and a screen reader alike", () => {
  const long = `${"a".repeat(300)} end.`;
  const out = memoSubject(long, 40);
  assert.equal(out.length, 40);
  assert.ok(out.endsWith("…"));
});

test("an absent rationale is an empty subject, not the string 'null'", () => {
  assert.equal(memoSubject(null), "");
  assert.equal(memoSubject(undefined), "");
  assert.equal(memoSubject("   "), "");
});

/* --------------------------------------------------------------- stamps ---- */

test("only a one-word verdict is stamped; a sentence verdict refuses the stamp", () => {
  assert.equal(verdictStamp("KILL"), "KILL");
  assert.equal(verdictStamp("KILLED — benchmark blind"), "KILL");
  assert.equal(verdictStamp("SURVIVES"), "SURVIVES");
  assert.equal(verdictStamp("CANNOT TELL"), "CANNOT TELL");
  // Verbatim from run-riskofficer-1 on the live desk. Stamping this "KILL"
  // would report a cleaner finding than the seat delivered; stamping it
  // "SURVIVES" would report the opposite of one. So: no stamp, verbatim text.
  assert.equal(
    verdictStamp("POLICY CORRECT, WORLD FALSE; FIX INCOMPLETE (F1); PREMISE FALSE (F2); MARKER FORGEABLE (F3)"),
    null,
  );
  assert.equal(verdictStamp("8 TICKETS"), null);
  assert.equal(verdictStamp(null), null);
  assert.equal(verdictStamp(""), null);
  assert.equal(
    verdictStamp("SURVIVES, though the kill list mentions KILL"), "SURVIVES",
    "a verdict is read from its head, exactly as isKillVerdict reads it",
  );
});

/* ------------------------------------------------------ production shelf --- */

const run = (over: Record<string, unknown> = {}) => ({
  run_id: "run-1",
  seat: "pm",
  task: "First portfolio review",
  model: "opus",
  tokens: 100_000,
  tool_uses: 12,
  dispatched_at: null,
  resolved_at: "2026-08-20T03:30:16.551269+00:00",
  artifact_path: "docs/pm/PM_REVIEW_2026-08-19.md",
  verdict: null,
  reasoning: null,
  trace_id: "trace-pm-review-1",
  recommendations: [],
  ...over,
}) as never;

// Shape copied from GET /api/v1/fund/desk on 2026-08-20.
const artifacts = [
  {
    kind: "proposal", path: "docs/proposals/VRP_XYLD_2026-08-19.md",
    title: "PROPOSAL: Equity index volatility risk premium",
    status: "killed",
    review: {
      review_path: "docs/reviews/ADVERSARY_VRP_XYLD_2026-08-19.md",
      review_title: "ADVERSARY VERDICT: KILL", verdict: "KILL",
    },
    note: null,
  },
] as never;

test("a shelf spine takes the artifact's own title when the fold has it, and says when it did not", () => {
  const [s] = productionShelf(
    [run({ artifact_path: "docs/proposals/VRP_XYLD_2026-08-19.md" })], artifacts,
  );
  assert.equal(s.title, "PROPOSAL: Equity index volatility risk premium");
  assert.equal(s.titleFrom, "artifact");
  assert.equal(s.kind, "proposal");
  assert.equal(s.status, "killed");
  assert.equal(s.verdict, "KILL", "the review's verdict stands in when the run recorded none");

  const [t] = productionShelf([run()], artifacts);
  assert.equal(t.title, "First portfolio review");
  assert.equal(t.titleFrom, "task",
    "a run's task must not be passed off as a filed document's title");
  assert.equal(t.status, null, "no matched artifact means no status, never a default one");
});

test("an adversarial review is found under review_path, not orphaned as an unknown document", () => {
  // The fold files a review under the artifact it reviewed, never as an
  // artifact of its own. Indexing by artifact.path alone left every review the
  // adversary has ever written reading "the fold does not carry this path".
  const [s] = productionShelf(
    [run({ seat: "adversary", artifact_path: "docs/reviews/ADVERSARY_VRP_XYLD_2026-08-19.md" })],
    artifacts,
  );
  assert.equal(s.title, "ADVERSARY VERDICT: KILL");
  assert.equal(s.titleFrom, "artifact");
  assert.equal(s.kind, "review");
  assert.equal(s.verdict, "KILL");
  assert.equal(s.status, null,
    "killed belongs to the proposal, not to the review of it — copying it across would say the review was killed");
});

test("a run that filed nothing appears on the shelf, marked as having filed nothing", () => {
  // "Delivered but filed nothing" and "produced nothing" are different facts
  // about the record. Dropping the row would report the second.
  const [s] = productionShelf([run({ artifact_path: null })], artifacts);
  assert.equal(s.path, null);
  assert.equal(s.title, "First portfolio review");
  assert.equal(s.kind, null);
});

test("the shelf is newest-first and undated spines sort LAST, not to the top", () => {
  const shelf = productionShelf([
    run({ run_id: "old", resolved_at: "2026-08-18T09:00:00Z" }),
    run({ run_id: "undated", resolved_at: null, dispatched_at: null }),
    run({ run_id: "new", resolved_at: "2026-08-20T09:00:00Z" }),
  ], []);
  assert.deepEqual(shelf.map((s) => s.runId), ["new", "old", "undated"],
    "an empty timestamp at the top of a time-ordered shelf reads as 'just now'");
});

test("an unresolved run dates from its dispatch rather than showing as undated", () => {
  const [s] = productionShelf(
    [run({ resolved_at: null, dispatched_at: "2026-08-20T08:00:00Z" })], [],
  );
  assert.equal(s.at, "2026-08-20T08:00:00Z");
});

test("a windows-style artifact path still matches the fold's forward-slash path", () => {
  const [s] = productionShelf(
    [run({ artifact_path: "docs\\proposals\\VRP_XYLD_2026-08-19.md" })], artifacts,
  );
  assert.equal(s.titleFrom, "artifact");
  assert.equal(s.path, "docs/proposals/VRP_XYLD_2026-08-19.md");
});

test("an empty desk produces an empty shelf, and no invented rows", () => {
  assert.deepEqual(productionShelf([], artifacts), []);
});
