/**
 * Tests for the desk derivations.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/desk/seatLib.test.ts`
 * (Node 22.6+; no test dependency is added to package.json — node:test is built
 * in, and this repo had no runner before.)
 *
 * Every case here guards a specific way a dashboard lies. Named, because a test
 * whose failure message does not say what belief broke gets deleted by the next
 * person who sees it go red:
 *
 *   - absence rendered as zero (the harness's oldest recurring defect: an
 *     unreadable subsystem showing 0 and reading as "nothing wrong")
 *   - a cost priced at the wrong model's rate (the cost model caught exactly
 *     this once: two dispatches billed at Fable rates, ~2× overpay, invisible
 *     until the tokens were priced per-model)
 *   - a funnel built on a list that structurally cannot contain rejections,
 *     which would show a fund that has never said no
 *   - untraced runs merged into one thread, drawing a conversation that never
 *     happened
 */

import assert from "node:assert/strict";
import test from "node:test";

import {
  absent,
  activeDays,
  artifactsForRuns,
  autopolicyAudit,
  dayKey,
  dispatchStats,
  estimateCostUsd,
  foldDay,
  isAbsent,
  isKillVerdict,
  isSeat,
  killBoard,
  priceRowFor,
  recFunnel,
  SEATS,
  SEAT_REQUEST_KIND,
  tokenStats,
  traceThreads,
  wireFeed,
} from "./seatLib.ts";

/* ------------------------------------------------------------- fixtures --- */

// Shapes copied from a live response (GET /api/v1/fund/desk and
// /api/v1/fund/events on 2026-08-20), trimmed to the fields the derivations
// read. Fabricating a shape is how a consumer ends up reading a key the
// endpoint never returns.
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

const ev = (over: Record<string, unknown> = {}) => ({
  seq: 1,
  event_id: "e1",
  aggregate_id: "a1",
  aggregate_type: "desk_request",
  type: "DeskDispatched",
  actor: "cto",
  ts: "2026-08-20T03:30:54.943542+00:00",
  payload: { seat: "pm", task: "review", trace_id: "t1" },
  ...over,
}) as never;

/* ---------------------------------------------------------------- seats --- */

test("the seat whitelist is the route guard, and rejects anything not on the bench", () => {
  assert.equal(SEATS.length, 9);   // coo seated 2026-08-20
  assert.ok(isSeat("riskofficer"));
  assert.ok(!isSeat("cto"));       // the CTO is not a seat page
  assert.ok(!isSeat(""));
  assert.ok(!isSeat(undefined));
  // Every seat can be asked for work, or its composer would render a kind the
  // spine rejects with a 422.
  for (const s of SEATS) assert.ok(SEAT_REQUEST_KIND[s], `no request kind for ${s}`);
});

/* --------------------------------------------------- absence discipline --- */

test("absence is a sentence naming the missing endpoint, never a zero", () => {
  const a = absent("mind-changers", "no field records a verdict that changed a design");
  assert.ok(isAbsent(a));
  assert.ok(!isAbsent(0));
  assert.ok(!isAbsent(null));
});

test("a seat with no runs reports null tokens, not zero tokens", () => {
  const s = tokenStats([]);
  assert.equal(s.runs, 0);
  assert.equal(s.total, null, "an unmeasured total must not read as $0 of work");
  assert.equal(s.avg, null);
  assert.equal(s.min, null);
  assert.equal(s.costUsd, null);
});

test("runs that recorded no token count are excluded from the average, and said so", () => {
  const s = tokenStats([run({ tokens: 100_000 }), run({ tokens: null }), run({ tokens: 50_000 })]);
  assert.equal(s.runs, 3);
  assert.equal(s.reported, 2, "the page must be able to say 2 of 3 runs reported tokens");
  assert.equal(s.total, 150_000);
  assert.equal(s.avg, 75_000);
  assert.equal(s.min, 50_000);
  assert.equal(s.max, 100_000);
});

test("a seat never dispatched has null dispatches, so the page can say 'never dispatched'", () => {
  const d = dispatchStats([ev()], "adversary");
  assert.equal(d.dispatches, null);
  assert.equal(d.lastAt, null);
  const p = dispatchStats([ev()], "pm");
  assert.equal(p.dispatches, 1);
  assert.deepEqual(p.actors, ["cto"]);
});

/* ----------------------------------------------------------------- wire --- */

test("the wire is the trace nodes flattened newest-first — same data, no third source", () => {
  const events = [
    ev({ type: "DeskRequested", actor: "ceo", ts: "2026-08-20T01:00:00+00:00",
         payload: { request_id: "rq1", serves: "pm", subject: "review the book", trace_id: "t1" } }),
    ev({ ts: "2026-08-20T02:00:00+00:00" }),   // dispatch on t1
  ];
  const feed = wireFeed(events, [run({ trace_id: "t1", resolved_at: "2026-08-20T03:00:00+00:00" })]);
  assert.equal(feed.length, 3);
  assert.deepEqual(feed.map((f) => f.kind), ["run", "dispatch", "request"],
    "newest first — the top of the wire is the latest thing that happened");
  assert.ok(feed.every((f) => f.traceId === "t1"));
});

test("the wire caps at the limit instead of rendering the whole log", () => {
  const events = Array.from({ length: 10 }, (_, i) =>
    ev({ event_id: `e${i}`, ts: `2026-08-20T0${i % 10}:00:00+00:00`,
         payload: { seat: "pm", task: `t${i}`, trace_id: `t${i}` } }));
  assert.equal(wireFeed(events, [], 4).length, 4);
});

/* ------------------------------------------------------------ economics --- */

test("cost is priced per model, and an unpriced model yields no figure at all", () => {
  assert.equal(priceRowFor("opus"), "opus");
  assert.equal(priceRowFor("claude-fable-5"), "fable");
  assert.equal(priceRowFor("qwen3.8:local"), "local");
  assert.equal(priceRowFor("some-model-we-never-priced"), null);
  assert.equal(priceRowFor(null), null);

  // The incident this guards: two dispatches ran on Fable while the desk
  // assumed Opus. Same tokens, twice the money — so the estimate must move
  // with the model, and must refuse to guess when the model is unknown.
  const opus = estimateCostUsd("opus", 100_000);
  const fable = estimateCostUsd("fable", 100_000);
  assert.ok(opus != null && fable != null);
  assert.ok(Math.abs(fable! / opus! - 2) < 1e-9, "Fable is 2x Opus on both legs");
  assert.equal(estimateCostUsd("mystery-model", 100_000), null,
    "an unknown model must produce no cost, not a default-priced one");
  assert.equal(estimateCostUsd("opus", null), null,
    "no tokens recorded means no cost, and never $0.00");
  // Local inference is a MEASURED zero: no API call is made.
  assert.equal(estimateCostUsd("qwen3.8", 100_000), 0);
});

test("the Opus working number matches the published cost model (~$0.70 / 100k)", () => {
  // docs/COST_MODEL_2026-08-20.md: 90/10 in/out blend, Opus $5/$25 per MTok.
  const c = estimateCostUsd("opus", 100_000);
  assert.ok(c != null);
  assert.ok(Math.abs(c! - 0.7) < 0.01, `expected ~0.70, got ${c}`);
});

/* ---------------------------------------------------------------- funnel -- */

test("the decision funnel counts rejections, which open_recommendations cannot", () => {
  const runs = [
    run({
      recommendations: [
        { rec_id: 1, seat: "pm", status: "open", text: "a" },
        { rec_id: 2, seat: "pm", status: "rejected", text: "b" },
        { rec_id: 3, seat: "pm", status: "accepted", text: "c" },
        { rec_id: 4, seat: "pm", status: "staged", text: "d" },
        { rec_id: 5, seat: "pm", status: "done", text: "e" },
      ],
    }),
  ];
  const f = recFunnel(runs);
  assert.equal(f.made, 5);
  assert.equal(f.rejected, 1,
    "built from open_recommendations this would be 0 — that list omits rejected");
  assert.equal(f.open + f.accepted + f.rejected + f.staged + f.done, f.made,
    "every recommendation lands in exactly one bucket");
});

/* ------------------------------------------------------------ kill board -- */

test("an unreviewed artifact is not a survivor", () => {
  const artifacts = [
    { kind: "proposal", path: "docs/proposals/a.md", title: "A", status: "killed",
      review: { review_path: "docs/reviews/r.md", review_title: "R", verdict: "KILL" },
      note: null },
    { kind: "proposal", path: "docs/proposals/b.md", title: "B", status: "under_review",
      review: null, note: "no adversarial review on file" },
  ] as never;
  const b = killBoard([], artifacts);
  assert.equal(b.kill, 1);
  assert.equal(b.survives, 0, "the unreviewed artifact must not be counted as surviving");
  assert.equal(b.unreviewed.length, 1);
  assert.equal(b.reviewed.length, 1);
});

test("CANNOT TELL is its own verdict and is never folded into a kill", () => {
  const b = killBoard([run({ verdict: "CANNOT TELL" }), run({ verdict: "KILL" })], []);
  assert.equal(b.cannotTell, 1);
  assert.equal(b.kill, 1);
  assert.equal(b.survives, 0);
  assert.ok(!isKillVerdict("CANNOT TELL"));
  assert.ok(isKillVerdict("KILLED - benchmark blind"));
  assert.ok(!isKillVerdict(null));
  assert.ok(!isKillVerdict("SURVIVES, though the kill list mentions KILL"),
    "a verdict is read from its head, not from a word appearing anywhere in it");
});

/* ---------------------------------------------------------------- traces -- */

test("runs without a trace_id get their own thread instead of being merged", () => {
  const threads = traceThreads([], [
    run({ run_id: "r1", trace_id: null }),
    run({ run_id: "r2", trace_id: null }),
    run({ run_id: "r3", trace_id: "t-shared" }),
    run({ run_id: "r4", trace_id: "t-shared", seat: "adversary" }),
  ]);
  assert.equal(threads.length, 3, "two untraced runs are two chains, not one");
  const shared = threads.find((t) => t.traceId === "t-shared");
  assert.ok(shared);
  assert.equal(shared!.synthetic, false);
  assert.deepEqual(shared!.seats.sort(), ["adversary", "pm"]);
  const orphan = threads.find((t) => t.traceId === "r1");
  assert.ok(orphan);
  assert.equal(orphan!.synthetic, true, "a synthetic thread must be labelled as one");
});

test("a thread replays request -> dispatch -> run -> decision in time order", () => {
  const events = [
    ev({ type: "DeskRecommendationDecided", ts: "2026-08-20T04:00:00Z", actor: "ceo",
         payload: { trace_id: "t1", seat: "pm", text: "close INTC", status: "accepted",
                    run_id: "run-1" } }),
    ev({ type: "DeskRequested", ts: "2026-08-20T01:00:00Z", actor: "ceo",
         payload: { trace_id: "t1", serves: "pm", subject: "review the book" } }),
    ev({ type: "DeskDispatched", ts: "2026-08-20T02:00:00Z", actor: "cto",
         payload: { trace_id: "t1", seat: "pm", task: "first review" } }),
  ];
  const runs = [run({ trace_id: "t1", resolved_at: "2026-08-20T03:00:00Z", verdict: "8 TICKETS" })];
  const [t] = traceThreads(events, runs);
  assert.deepEqual(t.nodes.map((n) => n.kind), ["request", "dispatch", "run", "decision"]);
  assert.equal(t.nodes[0].actor, "ceo");
  assert.equal(t.nodes[3].actor, "ceo", "who decided is part of the audit view");
  assert.equal(t.nodes[2].verdict, "8 TICKETS");
  assert.equal(t.first, "2026-08-20T01:00:00Z");
  assert.equal(t.last, "2026-08-20T04:00:00Z");
});

/* ------------------------------------------------------------------ days -- */

test("days bucket in UTC, so a dispatch does not move day with the reader", () => {
  assert.equal(dayKey("2026-08-20T23:59:59+00:00"), "2026-08-20");
  assert.equal(dayKey("2026-08-21T00:00:01+00:00"), "2026-08-21");
  assert.equal(dayKey(null), null);
  assert.equal(dayKey("not a date"), null);
});

test("the day fold counts only what happened on that day", () => {
  const events = [
    ev({ ts: "2026-08-20T03:30:54Z", payload: { seat: "builder", task: "build" } }),
    ev({ ts: "2026-08-19T18:45:14Z", payload: { seat: "pm", task: "review" } }),
    ev({ type: "DeskRecommendationDecided", ts: "2026-08-20T03:15:34Z", actor: "cto",
         payload: { seat: "validator", status: "done" } }),
  ];
  const runs = [
    run({ run_id: "a", resolved_at: "2026-08-20T03:30:16Z", tokens: 118_621, verdict: "KILL" }),
    run({ run_id: "b", resolved_at: "2026-08-19T20:00:00Z", tokens: 50_000 }),
  ];
  const d = foldDay(events, runs, "2026-08-20");
  assert.equal(d.dispatches, 1);
  assert.equal(d.decisions, 1);
  assert.equal(d.runs.length, 1);
  assert.equal(d.tokens, 118_621, "yesterday's tokens must not leak into today");
  assert.equal(d.kills, 1);
  assert.deepEqual(d.actors, ["cto"]);
  assert.ok(d.seats.includes("builder"));

  // A day the desk did nothing is a measured zero — but only for a day that is
  // inside the window the caller fetched, which the page states beside it.
  const quiet = foldDay(events, runs, "2026-08-18");
  assert.equal(quiet.dispatches, 0);
  assert.equal(quiet.tokens, null, "no runs is null tokens, not zero tokens");
});

test("active days lists only days with desk activity, newest first", () => {
  const days = activeDays(
    [ev({ ts: "2026-08-19T18:45:14Z" }), ev({ type: "NavStruck", ts: "2026-08-01T00:00:00Z" })],
    [run({ resolved_at: "2026-08-20T03:30:16Z" })],
  );
  assert.deepEqual(days, ["2026-08-20", "2026-08-19"],
    "a NavStruck day is not a desk day — the office view is about the firm's work");
});

/* ------------------------------------------------------------ autopolicy -- */

test("auto-approvals are identified by the approver field, never assumed", () => {
  const events = [
    ev({ type: "OrderApproved", actor: "rushi", payload: { approver: "rushi" } }),
    ev({ type: "OrderApproved", actor: "worker", payload: { approver: "auto-policy-v1" } }),
    ev({ type: "ExitRuleTriggered", payload: { symbol: "INTC" } }),
  ];
  const a = autopolicyAudit(events);
  assert.equal(a.approvals, 2);
  assert.equal(a.auto.length, 1, "a human approval must never be counted as an auto-approval");
  assert.equal(a.exitsFired, 1);
});

/* ------------------------------------------------------------- artifacts -- */

test("artifacts are attached to a seat only where a path proves it", () => {
  const artifacts = [
    { kind: "proposal", path: "docs/proposals/vrp.md", title: "VRP", status: "killed",
      review: { review_path: "docs/reviews/adv.md", review_title: "kill", verdict: "KILL" },
      note: null },
    { kind: "design", path: "docs/GATE_V5_DESIGN_2026-08-19.md", title: "v5", status: "under_review",
      review: null, note: "unreviewed" },
  ] as never;
  const mine = artifactsForRuns([run({ artifact_path: "docs/proposals/vrp.md" })], artifacts);
  assert.equal(mine.length, 1);
  assert.equal(mine[0].path, "docs/proposals/vrp.md");
  assert.equal(artifactsForRuns([run({ artifact_path: null })], artifacts).length, 0,
    "a run with no artifact claims no artifact");
});
