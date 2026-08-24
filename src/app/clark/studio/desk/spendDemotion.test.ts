/**
 * THE SPEND-DEMOTION RULE, made enforceable.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/spendDemotion.test.ts`
 *
 * Spec: `docs/design/RUN_PAGE_2026-08-24.md`. CEO, verbatim: *"this puts the
 * spend on my focus lens; I am more interested in the work being done. this
 * can be a small mention per ticket not the focus."* Binding on ALL window
 * surfaces: **the work is the face; the spend is a footnote.**
 *
 * WHY A SOURCE-LEVEL TEST AND NOT A RENDER TEST. This repo's runner is node's
 * own type stripper, which REFUSES `.tsx`, so no test in this tree can mount a
 * component. That leaves two options: check nothing, or check the source. A
 * layout rule with nothing enforcing it is exactly the pattern
 * `designAuthority.test.ts` was written to stop — it found three live
 * violations of a rule that had been in a docstring the whole time.
 *
 * EVERY ASSERTION HERE IS PAIRED WITH A NULL TEST. A positional check that
 * cannot find its landmark passes vacuously and reads as a green rule; each
 * landmark below is asserted to exist and to sit where it is expected before
 * anything is concluded from a position.
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const COMPONENTS = readFileSync(join(HERE, "components.tsx"), "utf8");

/** The body of one exported component, so a landmark cannot be found in a
 *  neighbour. Fails loudly rather than returning "" — an empty haystack is how
 *  a source test starts passing for the wrong reason. */
function componentBody(src: string, name: string): string {
  const start = src.indexOf(`export function ${name}(`);
  assert.notEqual(start, -1, `${name} not found — this test has gone stale`);
  const next = src.indexOf("\nexport function ", start + 1);
  const body = src.slice(start, next === -1 ? src.length : next);
  assert.ok(body.length > 200, `${name}'s body did not parse out`);
  return body;
}

/* ------------------------------------------------------------- RunRow ----- */

test("RunRow's landmarks are where this test thinks they are (the null test "
  + "for every position asserted below)", () => {
  const body = componentBody(COMPONENTS, "RunRow");
  assert.ok(body.includes("{run.task}"), "the work must be on the row");
  assert.ok(body.includes("{open && ("), "the disclosed footer must exist");
  assert.ok(body.includes("fmtTokens(run.tokens)"),
    "THE FIGURE IS NOT DELETED — demotion is a move, not a removal");
});

test("THE WORK IS THE FACE: the task and the verdict render before the "
  + "disclosure boundary", () => {
  const body = componentBody(COMPONENTS, "RunRow");
  const fold = body.indexOf("{open && (");
  assert.ok(body.indexOf("{run.task}") < fold, "the task is on the face");
  assert.ok(body.indexOf("{run.verdict}") < fold, "the verdict is on the face");
});

test("THE SPEND IS A FOOTNOTE: the token figure renders BELOW the disclosure "
  + "boundary, in the metadata line beside the model and the trace. It sat on "
  + "the card's face next to the verdict until D42 — the second most "
  + "prominent thing on a row about a piece of work", () => {
  const body = componentBody(COMPONENTS, "RunRow");
  const fold = body.indexOf("{open && (");
  assert.ok(body.indexOf("fmtTokens(run.tokens)") > fold,
    "a token figure on the face is the focus-lens complaint");
});

test("an absent token figure still SAYS so — absence is never zero, and "
  + "never a silently missing element either", () => {
  const body = componentBody(COMPONENTS, "RunRow");
  assert.ok(body.includes("tokens not recorded"));
});

/* -------------------------------------------------- SeatTelemetryChips ---- */

test("SeatTelemetryChips renders the seat's tokens exactly once, and the "
  + "landmarks exist (null test)", () => {
  const body = componentBody(COMPONENTS, "SeatTelemetryChips");
  const hits = body.split("tokensLabel(t)").length - 1;
  assert.equal(hits, 1, `expected one token rendering, found ${hits}`);
  assert.ok(body.includes("rounded-full"), "chips are rendered as pills");
});

test("THE TOKEN FIGURE IS NOT A CHIP. A bordered pill at the same weight as "
  + "'running now' and '3 runs today' puts a seat's SPEND among the answers "
  + "to what that seat is DOING; the spec's amendment asks for one quiet line "
  + "instead. The enclosing element must be a paragraph", () => {
  const body = componentBody(COMPONENTS, "SeatTelemetryChips");
  const at = body.indexOf("tokensLabel(t)");
  assert.notEqual(at, -1);
  // The nearest opening tag before the figure decides what it looks like.
  const before = body.slice(0, at);
  const lastP = before.lastIndexOf("<p ");
  const lastSpan = before.lastIndexOf("<span ");
  assert.ok(lastP > lastSpan,
    "the token figure is inside a chip again — see RUN_PAGE_2026-08-24.md");
});

test("RUNS STAY A CHIP. The demotion applies to spend, not to the work — a "
  + "pass that came from deleting the whole chip row would be a different "
  + "defect wearing this test's green", () => {
  const body = componentBody(COMPONENTS, "SeatTelemetryChips");
  const at = body.indexOf("run{runs === 1");
  assert.notEqual(at, -1, "the runs-today chip must still exist");
  const before = body.slice(0, at);
  assert.ok(before.lastIndexOf("<span ") > before.lastIndexOf("<p "),
    "runs today is still rendered as a chip");
});
