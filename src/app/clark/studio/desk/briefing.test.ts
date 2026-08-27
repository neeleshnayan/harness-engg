import test from "node:test";
import assert from "node:assert/strict";

import {
  MAX_CHIPS, briefingChips, briefingOf, briefingRows, fmtDuration,
  fmtTokensShort, nextActorOf, ranMinutes,
} from "./briefing.ts";
import type { DeskRun } from "./seatLib.ts";

/**
 * THE BRIEFING CONTRACT.
 *
 * The defect this guards: a run record rendered as PARAGRAPHS. The measured
 * precedent is the engine page's first version — nine paragraphs of honest
 * prose, and the CEO's verdict *"too much text; we need analytics and graphs
 * and meaningful and minimal UI"*.
 *
 * The tests that matter are the honesty ones, not the layout ones:
 *
 *  - an ABORTED run is never dressed as a delivery;
 *  - a missing verdict is a SENTENCE, never a blank headline;
 *  - a run with no recommendations is a RESULT, never an empty list;
 *  - money is summed only over rows that state a figure, with the denominator;
 *  - `next_actor` is READ, never inferred from the text.
 */

const RUN = (over: Record<string, unknown> = {}): DeskRun => ({
  run_id: "run-builder-mach1",
  seat: "builder",
  task: "MACH1 - v5 draft redesign",
  model: null,
  tokens: 540438,
  tool_uses: 236,
  dispatched_at: "2026-08-27T05:52:00+00:00",
  resolved_at: "2026-08-27T07:21:44+00:00",
  artifact_path: "docs/design/AUTOPOLICY_V5_2026-08-27.md",
  verdict: "both kills closed with the incident's own numbers as regressions",
  reasoning: "Both structural kills closed and pinned as tests.",
  trace_id: null,
  status: "delivered",
  recommendations: [],
  ...over,
}) as unknown as DeskRun;

const REC = (over: Record<string, unknown> = {}) => ({
  kind: "dispatch", seat: "builder", rec_id: 1, status: "open",
  text: "Route the v5 draft r2 to the adversary BLIND before anything else.",
  next_actor: "chair", reversibility: "reversible",
  money_at_stake: null, due_date: null, ...over,
});

/* --------------------------------------------------------- the headline --- */

test("the headline is the run's verdict, one line", () => {
  const b = briefingOf(RUN());
  assert.match(b.headline!, /both kills closed/);
  assert.equal(b.headlineNote, null);
  assert.equal(b.outcome, "delivered");
});

test("a run with NO verdict gets a sentence, never a blank headline", () => {
  const b = briefingOf(RUN({ verdict: null }));
  assert.equal(b.headline, null);
  assert.match(b.headlineNote!, /filed no verdict/);
  assert.match(b.headlineNote!, /not an empty conclusion/);
});

test("a blank-string verdict is ABSENT, not an empty headline", () => {
  assert.equal(briefingOf(RUN({ verdict: "   " })).headline, null);
});

test("an ABORTED run is never dressed as a delivery", () => {
  const stopped = briefingOf(RUN({ status: "aborted" }));
  assert.equal(stopped.outcome, "aborted");
  // The verdict is still shown — it is where the seat got to — but the note
  // refuses to let it read as a conclusion.
  assert.ok(stopped.headline);
  assert.match(stopped.headlineNote!, /ABORTED/);
  assert.match(stopped.headlineNote!, /not a delivered conclusion/);
});

test("an aborted run with no verdict says the seat STOPPED", () => {
  const b = briefingOf(RUN({ status: "aborted", verdict: null }));
  assert.match(b.headlineNote!, /the seat stopped/);
  assert.match(b.headlineNote!, /not the same as a seat that found nothing/);
});

test("an unrecognised status is `unstated`, not silently delivered", () => {
  assert.equal(briefingOf(RUN({ status: "in_flight" })).outcome, "unstated");
  assert.equal(briefingOf(RUN({ status: undefined })).outcome, "unstated");
});

/* ------------------------------------------------------------- the rows --- */

test("a recommendation row carries who-moves-next, READ not inferred", () => {
  const b = briefingOf(RUN({ recommendations: [REC(), REC({ rec_id: 2, next_actor: "ceo" })] }));
  assert.deepEqual(b.rows.map((r) => r.nextActor), ["chair", "ceo"]);
  assert.equal(b.rowsNote, null);
});

test("an unknown or missing next_actor is `unstated`, never guessed", () => {
  assert.equal(nextActorOf({}), "unstated");
  assert.equal(nextActorOf({ next_actor: "abhishek" } as never), "unstated");
  assert.equal(nextActorOf({ next_actor: "  CEO " } as never), "ceo");
  // The TEXT names the CEO and the field does not. The field wins — reading a
  // next actor out of prose is the same class of mistake as reading a deadline
  // out of one, which this desk has been repaired from twice.
  assert.equal(nextActorOf({
    text: "the CEO must click this", next_actor: null,
  } as never), "unstated");
});

test("a row with no readable text is DROPPED, not rendered blank", () => {
  const rows = briefingRows([REC(), REC({ rec_id: 2, text: "  " }), REC({ rec_id: 3, text: null })]);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].recId, 1);
});

test("text_display wins over text when the spine annotated one", () => {
  const rows = briefingRows([REC({ text: "raw", text_display: "annotated" })]);
  assert.equal(rows[0].text, "annotated");
});

test("no recommendations is a RESULT, with a sentence and no chip", () => {
  const b = briefingOf(RUN({ recommendations: [] }));
  assert.deepEqual(b.rows, []);
  assert.match(b.rowsNote!, /asked for nothing/);
  assert.match(b.rowsNote!, /a result, not an empty record/);
  assert.equal(b.chips.some((c) => c.label === "asks"), false);
});

test("money_at_stake absent is null, never zero", () => {
  const rows = briefingRows([REC(), REC({ rec_id: 2, money_at_stake: 0 })]);
  assert.equal(rows[0].moneyAtStake, null);
  assert.equal(rows[1].moneyAtStake, 0, "a stated zero is a stated zero");
});

/* ------------------------------------------------------------ the chips --- */

test("the chip cap is four and the ORDER is decision value", () => {
  const rows = briefingRows([
    REC({ next_actor: "ceo", money_at_stake: 501 }),
    REC({ rec_id: 2, next_actor: "chair" }),
  ]);
  const chips = briefingChips(rows, RUN());
  assert.equal(chips.length, MAX_CHIPS);
  assert.deepEqual(chips.map((c) => c.label),
    ["needs you", "at stake", "asks", "tokens"]);
  // "ran for" was earned and lost the fifth slot. Nothing is lost: it is in
  // the fold, which the card always renders.
  assert.equal(briefingOf(RUN({
    recommendations: [REC({ next_actor: "ceo", money_at_stake: 501 })],
  })).fold.ranMinutes! > 0, true);
});

test("only the who-must-move chip carries a tone", () => {
  const chips = briefingChips(briefingRows([REC({ next_actor: "ceo" })]), RUN());
  assert.equal(chips[0].label, "needs you");
  assert.equal(chips[0].tone, "warn");
  // Asserted as a COUNT of warn chips rather than a fixed-length list of
  // plains: the second form encodes how many chips this run happens to earn,
  // which is a different fact and made this test fail for the right code.
  assert.deepEqual(chips.map((c) => c.label),
    ["needs you", "asks", "tokens", "ran for"]);
  assert.equal(chips.filter((c) => c.tone === "warn").length, 1);
  assert.equal(chips.slice(1).every((c) => c.tone === "plain"), true);
});

test("zero is quiet: no CEO row means no `needs you` chip at all", () => {
  const chips = briefingChips(briefingRows([REC({ next_actor: "chair" })]), RUN());
  assert.equal(chips.some((c) => c.label === "needs you"), false);
  assert.equal(chips.find((c) => c.label === "asks")!.sub, "none need you");
});

test("the money chip states its DENOMINATOR when not every row is priced", () => {
  const rows = briefingRows([
    REC({ money_at_stake: 400 }), REC({ rec_id: 2 }), REC({ rec_id: 3 }),
  ]);
  const chip = briefingChips(rows, RUN()).find((c) => c.label === "at stake")!;
  assert.equal(chip.value, "$400");
  assert.equal(chip.sub, "1 of 3 rows priced");
});

test("an all-priced set says so rather than printing 3 of 3", () => {
  const rows = briefingRows([REC({ money_at_stake: 12.5 }), REC({ rec_id: 2, money_at_stake: 3 })]);
  const chip = briefingChips(rows, RUN()).find((c) => c.label === "at stake")!;
  assert.equal(chip.value, "$15.50");
  assert.equal(chip.sub, "all rows priced");
});

test("rows priced at zero earn NO money chip — zero is quiet", () => {
  // Measured on the live desk 2026-08-27: 200 of 272 open recommendations
  // carry `money_at_stake` and 124 of those are 0.0. A `$0 at stake` chip on
  // every card would be the loudest thing on the page and would say nothing.
  const rows = briefingRows([REC({ money_at_stake: 0 }), REC({ rec_id: 2, money_at_stake: 0 })]);
  assert.equal(briefingChips(rows, RUN()).some((c) => c.label === "at stake"), false);
});

test("an unpriced run earns no token chip rather than printing zero", () => {
  const chips = briefingChips([], RUN({ tokens: null, resolved_at: null }));
  assert.deepEqual(chips.map((c) => c.label), []);
});

test("tool calls ride the token chip's sub-line, absent when unrecorded", () => {
  assert.equal(briefingChips([], RUN()).find((c) => c.label === "tokens")!.sub,
    "236 tool calls");
  assert.equal(briefingChips([], RUN({ tool_uses: null }))
    .find((c) => c.label === "tokens")!.sub, null);
});

/* ------------------------------------------------------------ the clock --- */

test("duration is null when either stamp is missing or unreadable", () => {
  assert.equal(ranMinutes(null, "2026-08-27T07:00:00+00:00"), null);
  assert.equal(ranMinutes("2026-08-27T05:00:00+00:00", null), null);
  assert.equal(ranMinutes("not a date", "2026-08-27T07:00:00+00:00"), null);
  assert.equal(ranMinutes("", ""), null);
});

test("a NEGATIVE duration is reported absent, not as a negative number", () => {
  // The record disagreeing with itself is not a run that took minus an hour.
  assert.equal(ranMinutes("2026-08-27T07:00:00+00:00", "2026-08-27T05:00:00+00:00"), null);
});

test("durations read the way a human says them", () => {
  assert.equal(fmtDuration(null), null);
  assert.equal(fmtDuration(0.4), "<1m");
  assert.equal(fmtDuration(42), "42m");
  assert.equal(fmtDuration(60), "1h");
  assert.equal(fmtDuration(128), "2h 8m");
  assert.equal(fmtDuration(89.7333), "1h 30m");
});

test("token counts drop the digits that are noise", () => {
  assert.equal(fmtTokensShort(null), null);
  assert.equal(fmtTokensShort(0), "0");
  assert.equal(fmtTokensShort(999), "999");
  assert.equal(fmtTokensShort(540438), "540k");
  assert.equal(fmtTokensShort(1_240_000), "1.2M");
});

/* ------------------------------------------------------------- the fold --- */

test("the fold carries every number the chips could not fit", () => {
  const b = briefingOf(RUN());
  assert.equal(b.fold.tokens, 540438);
  assert.equal(b.fold.toolUses, 236);
  assert.equal(b.fold.artifactPath, "docs/design/AUTOPOLICY_V5_2026-08-27.md");
  assert.match(b.fold.reasoning!, /pinned as tests/);
  assert.equal(Math.round(b.fold.ranMinutes!), 90);
});

test("an empty fold is absent fields, never empty strings", () => {
  const b = briefingOf(RUN({
    reasoning: "", artifact_path: null, model: "  ", tokens: null,
  }));
  assert.equal(b.fold.reasoning, null);
  assert.equal(b.fold.artifactPath, null);
  assert.equal(b.fold.model, null);
  assert.equal(b.fold.tokens, null);
});
