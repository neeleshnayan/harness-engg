/**
 * The third dispatch state, on the telemetry surface.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskThirdState.test.ts`
 *
 * THE INCIDENT (live spine, 2026-08-22): the COO watched `seat_telemetry`
 * report `running_now: true` for the analyst and the builder while BOTH had
 * already returned and been recorded — 19 and 21 hours stale. It fired twice
 * during that seat's own triage. Two agents in parallel are permitted as of the
 * same week, so a chair reading this could not tell whether a slot was free.
 *
 * The floor and the desk page had already learned the third state; this file is
 * about the block the chair actually reads for "who is busy", and about the
 * chip that used to say "not running · No dispatch is open for this seat" over
 * a dispatch that was open and owed a review.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import type { DeskView } from "@/lib/fund_api";
import { seatTelemetry } from "./deskTelemetry.ts";

/* ------------------------------------------------------------- fixtures --- */

type Status = "working" | "idle" | "awaiting_review";

const roster = (
  over: Record<string, {
    status: Status; task?: string | null; since?: string | null;
    returned_run_id?: string | null;
  }>,
): DeskView["roster"] =>
  Object.entries(over).map(([agent, a]) => ({
    agent, lane: "l", emits: "e", exists_because: "x",
    activity: {
      status: a.status, task: a.task ?? null, since: a.since ?? null,
      returned_run_id: a.returned_run_id ?? null, last_delivered: null,
    },
  })) as unknown as DeskView["roster"];

const view = (o: Partial<DeskView>): DeskView => ({
  roster: [], protocol: [], artifacts: [], requests: [], runs: [],
  open_recommendations: [], open_requests: 0, kills: 0,
  execution_note: "", note: "", ...o,
} as unknown as DeskView);

const block = (seats: Record<string, unknown>, readable = true) => ({
  day: "2026-08-22", readable, seats, note: "n",
}) as unknown as DeskView["seat_telemetry"];

const row = (o: Record<string, unknown>) => ({
  running_now: false, running_task: null, running_since: null,
  runs_today: 0, tokens_today: null, tokens_partial: false,
  runs_missing_tokens: 0, tokens_by_model: {}, last_run_at: null, ...o,
});

/* ----------------------------------------------------------- the fold ----- */

test("a returned dispatch is AWAITING REVIEW and is not running", () => {
  const t = seatTelemetry(
    view({
      roster: roster({
        builder: {
          status: "awaiting_review", task: "Dispatch 9",
          since: "2026-08-22T09:00:00+00:00", returned_run_id: "run-builder-d9",
        },
      }),
      seat_telemetry: block({
        builder: row({
          running_now: false, awaiting_review: true,
          returned_run_id: "run-builder-d9",
          running_task: "Dispatch 9", running_since: "2026-08-22T09:00:00+00:00",
        }),
      }),
    }),
    "builder",
  );
  assert.equal(t.runningNow, false, "THE INCIDENT: a returned seat is not running");
  assert.equal(t.awaitingReview, true);
  assert.equal(t.returnedRunId, "run-builder-d9");
  // The DISPATCH is still open, so its task and its clock survive the return —
  // blanking them would erase what the chair now owes a review on.
  assert.equal(t.runningTask, "Dispatch 9");
  assert.equal(t.runningSince, "2026-08-22T09:00:00+00:00");
});

test("the two live states are mutually exclusive", () => {
  const busy = seatTelemetry(
    view({ roster: roster({ pm: { status: "working", task: "R25" } }) }),
    "pm",
  );
  assert.equal(busy.runningNow, true);
  assert.equal(busy.awaitingReview, false);
  assert.equal(busy.returnedRunId, null);
});

test("an idle seat is neither, and carries no dispatch", () => {
  const t = seatTelemetry(
    view({ roster: roster({ quant: { status: "idle" } }) }), "quant");
  assert.equal(t.runningNow, false);
  assert.equal(t.awaitingReview, false);
  assert.equal(t.runningTask, null);
  assert.equal(t.returnedRunId, null);
});

test("the roster fold survives a spine with no telemetry rollup at all", () => {
  // `running_now` has always survived the rollup's absence; the third state
  // must too, or a spine mid-upgrade renders every returned seat as idle.
  const t = seatTelemetry(
    view({
      roster: roster({
        analyst: { status: "awaiting_review", task: "cycle 3",
                   returned_run_id: "run-analyst-cycle3" },
      }),
    }),
    "analyst",
  );
  assert.equal(t.source, "unavailable");
  assert.equal(t.awaitingReview, true);
  assert.equal(t.returnedRunId, "run-analyst-cycle3");
});

test("an OLDER spine that omits awaiting_review falls back to the roster", () => {
  /* THE SUBTLE ONE. `awaiting_review` is optional on the wire. Reading a
   * missing key as `false` — which `??` protects against and `||` would not —
   * would make a spine that predates the split report every returned seat as
   * not awaiting, which is precisely the state this change exists to show. */
  const t = seatTelemetry(
    view({
      roster: roster({
        builder: { status: "awaiting_review", task: "D9",
                   returned_run_id: "run-b-d9" },
      }),
      // No `awaiting_review`, no `returned_run_id` — the old row shape.
      seat_telemetry: block({ builder: row({ running_now: false }) }),
    }),
    "builder",
  );
  assert.equal(t.source, "spine");
  assert.equal(t.awaitingReview, true);
  assert.equal(t.returnedRunId, "run-b-d9");
});

test("an unreadable recorder is still not a quiet bench", () => {
  const t = seatTelemetry(
    view({
      roster: roster({ builder: { status: "working", task: "D9" } }),
      seat_telemetry: block({}, false),
    }),
    "builder",
  );
  assert.equal(t.runningNow, true);
  assert.equal(t.awaitingReview, false);
});

/* ------------------------------------------------------------ the chip ---- */

test("the status chip renders three states, not two", () => {
  /* Read at the source because there is no DOM runner in this repo, and the
   * regression is a STRING: the two-state chip said "not running" with the
   * title "No dispatch is open for this seat" over a dispatch that WAS open
   * and owed the chair a review. That sentence must never be reachable for a
   * seat awaiting review. */
  const src = readFileSync(
    new URL("./components.tsx", import.meta.url), "utf8");
  const chip = src.slice(src.indexOf("export function SeatTelemetryChips"));
  assert.ok(chip.includes('"awaiting review"'),
    "the chip must have a word for the third state");
  assert.ok(chip.includes("t.awaitingReview"),
    "the chip must read the third state, not infer it from runningNow");
  // The false sentence is guarded behind the awaiting branch.
  const falseSentence = "No dispatch is open for this seat.";
  const at = chip.indexOf(falseSentence);
  assert.ok(at > 0, "the idle sentence should still exist for genuinely idle seats");
  assert.ok(chip.lastIndexOf("t.awaitingReview", at) > 0,
    "the idle sentence must sit inside a branch that has already excluded awaiting review");
  // A pulse says someone is at that desk; a returned dispatch means the
  // opposite. So the animation must appear exactly once, in the running
  // branch — checked by position rather than by matching an exact ternary,
  // which reformatting would break without any behaviour changing.
  const pulses = chip.split("kt-breathe").length - 1;
  assert.equal(pulses, 1, "the pulse belongs to exactly one state");
  const before = chip.slice(0, chip.indexOf("kt-breathe"));
  assert.ok(before.lastIndexOf("t.runningNow") > before.lastIndexOf("t.awaitingReview"),
    "the pulse must hang off runningNow, not off the returned state");
});

test("the COO chip shows work routed away from the CEO rather than dropping it", () => {
  /* The brief's guard rail: do not solve a counting problem by hiding work.
   * The spine stopped counting chair-owned rows on 2026-08-22; if the chip
   * then omitted them, the same work would have left the screen instead of
   * the number. */
  const src = readFileSync(
    new URL("./components.tsx", import.meta.url), "utf8");
  const chip = src.slice(src.indexOf("export function CooTriageChip"),
                         src.indexOf("desk telemetry"));
  assert.ok(chip.includes("open_elsewhere"), "the chip must render the chair's OPEN backlog");
  assert.ok(chip.includes("by_actor?.unknown"),
    "rows whose actor could not be determined must be named, not folded away");
  // An absent split must render as absent, never as a confident zero.
  assert.ok(chip.includes("load.open_elsewhere ?? 0"));
  assert.ok(chip.includes("{!!unknown &&"),
    "an absent or zero unknown count renders nothing rather than '0 unknown'");
});
