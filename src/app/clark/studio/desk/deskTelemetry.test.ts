/**
 * Desk telemetry — the guard against a floor rendered as a total.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/deskTelemetry.test.ts`
 *
 * The incident this file is written against is `desk_load`'s first live day: a
 * counter read 73 open items against 10 truly open — 3.65x — and fired a COO
 * triage whose own memo found the miscount. Same class as CDO D4, one layer
 * down. Every test below pins one way this surface could repeat it: a count
 * folded from a capped list, a token sum missing a run, a dollar figure priced
 * at the wrong model, an unreadable recorder rendered as a quiet day.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import type { DeskView } from "@/lib/fund_api";
import {
  costLabel,
  fmtTokensCompact,
  seatTelemetry,
  telemetryNote,
  tokensLabel,
} from "./deskTelemetry.ts";
import { isAbsent } from "./seatLib.ts";

/* ------------------------------------------------------------- fixtures --- */

const roster = (
  over: Record<string, { status: "working" | "idle"; task?: string | null; since?: string | null }>,
): DeskView["roster"] =>
  Object.entries(over).map(([agent, a]) => ({
    agent, lane: "l", emits: "e", exists_because: "x",
    activity: { status: a.status, task: a.task ?? null, since: a.since ?? null,
                last_delivered: null },
  }));

const view = (o: Partial<DeskView>): DeskView => ({
  roster: [], protocol: [], artifacts: [], requests: [], runs: [],
  open_recommendations: [], open_requests: 0, kills: 0,
  execution_note: "", note: "", ...o,
} as unknown as DeskView);

const block = (seats: Record<string, unknown>, readable = true) => ({
  day: "2026-08-21", readable, seats, note: "n",
}) as unknown as DeskView["seat_telemetry"];

const row = (o: Record<string, unknown>) => ({
  running_now: false, running_task: null, running_since: null,
  runs_today: 0, tokens_today: null, tokens_partial: false,
  runs_missing_tokens: 0, tokens_by_model: {}, last_run_at: null, ...o,
});

/* ------------------------------------------------------------- absences --- */

test("an unreadable DESK is an unknown, never a quiet seat", () => {
  const t = seatTelemetry(null, "pm");
  assert.equal(t.source, "unavailable");
  assert.ok(isAbsent(t.runsToday));
  assert.ok(isAbsent(t.tokensToday));
  assert.match((t.runsToday as { needs: string }).needs, /not a quiet desk/);
  // Not zero, not false-positive running.
  assert.equal(t.runningNow, false);
  assert.equal(t.costUsdToday, null, "null is not $0 — the seat may have cost money");
});

test("a spine without the rollup says so, and does NOT fold the capped run list", () => {
  // The defect this pins: `view.runs` is the 25 most recent ACROSS ALL SEATS,
  // so a per-seat day count folded from it is a floor. Folding it here would
  // be easy, would look right, and would be the desk_load bug again.
  const v = view({
    roster: roster({ pm: { status: "idle" } }),
    runs: Array.from({ length: 25 }, (_, i) => ({
      run_id: `r${i}`, seat: "pm", task: "t", tokens: 1000,
      resolved_at: "2026-08-21T10:00:00Z", recommendations: [],
    })),
  } as Partial<DeskView>);
  const t = seatTelemetry(v, "pm");
  assert.ok(isAbsent(t.runsToday));
  assert.match((t.runsToday as { needs: string }).needs, /seat_telemetry/);
  assert.match((t.runsToday as { needs: string }).needs, /floor .*dressed as a count/);
  assert.ok(isAbsent(t.tokensToday));
});

test("the source has no path that reads view.runs — the tempting fallback is absent by construction", () => {
  // A test on the SOURCE, because the fallback is a thing a future edit ADDS
  // rather than a thing a fixture can trigger. If `view.runs` is ever read in
  // this module, the count on screen stops being exact and nothing says so.
  const src = readFileSync(new URL("./deskTelemetry.ts", import.meta.url), "utf8");
  // Comments stripped first — the module DISCUSSES `view.runs` at length in
  // order to explain why it does not read it, and a check that cannot tell
  // prose from code would force the explanation out of the file.
  const code = src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.doesNotMatch(code, /view\.runs/,
    "deskTelemetry is reading the capped run list; the day count would become a floor");
  assert.match(src, /view\.runs/, "the explanation of why it is not read must stay");
});

test("an unreadable FLIGHT RECORDER is distinguished from a readable empty day", () => {
  const unread = seatTelemetry(
    view({ roster: roster({ pm: { status: "idle" } }),
           seat_telemetry: block({}, false) }), "pm");
  assert.ok(isAbsent(unread.runsToday));
  assert.match((unread.runsToday as { needs: string }).needs, /could not be read/);

  const quiet = seatTelemetry(
    view({ roster: roster({ pm: { status: "idle" } }),
           seat_telemetry: block({ pm: row({ runs_today: 0 }) }) }), "pm");
  // MEASURED zero: the window was queried and was empty. Different fact.
  assert.equal(quiet.runsToday, 0);
  assert.ok(isAbsent(quiet.tokensToday));
  assert.match((quiet.tokensToday as { needs: string }).needs, /no run resolved/);
});

test("a seat missing from a readable rollup is named, not silently zeroed", () => {
  const t = seatTelemetry(
    view({ roster: roster({ secretary: { status: "idle" } }),
           seat_telemetry: block({ pm: row({}) }) }), "secretary");
  assert.ok(isAbsent(t.runsToday));
  assert.match((t.runsToday as { needs: string }).needs, /secretary/);
});

/* ------------------------------------------------------------- the facts -- */

test("running now carries the task, and an idle seat carries none", () => {
  const v = view({
    roster: roster({
      builder: { status: "working", task: "D5: the floor", since: "2026-08-21T08:00:00Z" },
      pm: { status: "idle" },
    }),
    seat_telemetry: block({
      builder: row({ running_now: true, running_task: "D5: the floor",
                     running_since: "2026-08-21T08:00:00Z" }),
      pm: row({}),
    }),
  } as Partial<DeskView>);
  const b = seatTelemetry(v, "builder");
  assert.equal(b.runningNow, true);
  assert.equal(b.runningTask, "D5: the floor");
  assert.equal(b.runningSince, "2026-08-21T08:00:00Z");
  assert.equal(seatTelemetry(v, "pm").runningNow, false);
  assert.equal(seatTelemetry(v, "pm").runningTask, null);
});

test("running now survives a spine with no rollup at all", () => {
  // The dot has worked for a while; losing it because the day query is missing
  // would be a regression dressed as an absence.
  const t = seatTelemetry(view({
    roster: roster({ quant: { status: "working", task: "run the belt" } }),
  } as Partial<DeskView>), "quant");
  assert.equal(t.runningNow, true);
  assert.equal(t.runningTask, "run the belt");
  assert.ok(isAbsent(t.runsToday), "the counts are still absent, and say why");
});

test("tokens today sum, and the dollar estimate prices per model", () => {
  const t = seatTelemetry(view({
    roster: roster({ pm: { status: "idle" } }),
    seat_telemetry: block({
      pm: row({ runs_today: 2, tokens_today: 200_000,
                tokens_by_model: { opus: 200_000 } }),
    }),
  } as Partial<DeskView>), "pm");
  assert.equal(t.runsToday, 2);
  assert.equal(t.tokensToday, 200_000);
  assert.equal(t.tokensPartial, false);
  // 200k at the 90/10 blend: 180k in @ $5/M + 20k out @ $25/M = 0.9 + 0.5.
  assert.ok(Math.abs((t.costUsdToday ?? 0) - 1.4) < 1e-9);
  assert.equal(tokensLabel(t), "200k");
  assert.equal(costLabel(t), "≈$1.40");
});

test("a run with no token figure makes the sum a FLOOR, marked and explained", () => {
  const t = seatTelemetry(view({
    roster: roster({ pm: { status: "idle" } }),
    seat_telemetry: block({
      pm: row({ runs_today: 3, tokens_today: 100_000, tokens_partial: true,
                runs_missing_tokens: 2, tokens_by_model: { opus: 100_000 } }),
    }),
  } as Partial<DeskView>), "pm");
  assert.equal(t.runsToday, 3, "the unreported runs still happened and still count");
  assert.equal(tokensLabel(t), "≥100k");
  assert.equal(costLabel(t).startsWith("≥"), true,
    "a dollar figure over a partial token sum is a floor too");
  assert.match(telemetryNote(t), /2 of them recorded no token figure/);
  assert.match(telemetryNote(t), /floor, not a sum/);
});

test("an UNPRICED model contributes no dollars and makes the estimate a floor", () => {
  // The measured error this guards: pricing an unknown model at Opus rates for
  // a run that was actually Fable understates the bill by 2x. Never default.
  const t = seatTelemetry(view({
    roster: roster({ analyst: { status: "idle" } }),
    seat_telemetry: block({
      analyst: row({ runs_today: 2, tokens_today: 150_000,
                     tokens_by_model: { opus: 100_000, "mystery-model-9": 50_000 } }),
    }),
  } as Partial<DeskView>), "analyst");
  assert.equal(t.unpricedTokens, 50_000);
  assert.ok(Math.abs((t.costUsdToday ?? 0) - 0.7) < 1e-9, "only the opus half is priced");
  assert.equal(costLabel(t).startsWith("≥"), true);
  assert.match(telemetryNote(t), /50k tokens ran on a model with no row in the price table/);
});

test("local inference is a MEASURED zero, not an unpriced unknown", () => {
  const t = seatTelemetry(view({
    roster: roster({ quant: { status: "idle" } }),
    seat_telemetry: block({
      quant: row({ runs_today: 1, tokens_today: 40_000,
                   tokens_by_model: { "qwen3.8": 40_000 } }),
    }),
  } as Partial<DeskView>), "quant");
  assert.equal(t.unpricedTokens, 0, "the 4090 costs electricity, and that is a real zero");
  assert.equal(t.costUsdToday, 0);
  assert.equal(costLabel(t), "≈$0.00");
});

/* ---------------------------------------------------------- formatting ---- */

test("token compaction never turns an absence into a number", () => {
  assert.equal(fmtTokensCompact(null), "—");
  assert.equal(fmtTokensCompact(undefined), "—");
  assert.equal(fmtTokensCompact(NaN), "—");
  assert.equal(fmtTokensCompact(0), "0");
  assert.equal(fmtTokensCompact(900), "900");
  assert.equal(fmtTokensCompact(480_000), "480k");
  assert.equal(fmtTokensCompact(1_250_000), "1.3M");
});

test("the note is always present when the figures are, so the caveat line is not skippable", () => {
  const t = seatTelemetry(view({
    roster: roster({ pm: { status: "idle" } }),
    seat_telemetry: block({ pm: row({ runs_today: 0 }) }),
  } as Partial<DeskView>), "pm");
  assert.match(telemetryNote(t), /No run resolved for this seat on 2026-08-21/);
});
