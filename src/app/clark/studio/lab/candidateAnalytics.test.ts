/**
 * The Lab's reading of the belt's evidence.
 *
 * Every test here guards an ABSENCE from turning into a number. The incidents
 * behind them, all 2026-08-21:
 *
 *   * the CEO could see `monthend_rebalance_flow` and not the analytics behind
 *     it, because the belt stored none;
 *   * six engine-killed folds entered the quant's report as findings about a
 *     rule (run-quant-entry11) — a killed container and a strategy that declined
 *     to trade had the same shape;
 *   * `dates_honoured` is nullable, and both falsy-coalescings of it are wrong.
 */

import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  NOT_CAPTURED, PRUNED, NOT_TESTABLE, UNAVAILABLE,
  RETENTION_FLOOR,
  absenceLabel, absenceOf, breakevenSentence, costBand,
  foldTally, foldVerdict, gateSentence, honoured, rebase, windowLine,
  type CandidateRow, type FoldRow,
} from "./candidateAnalytics.ts";

const measurable = (retention: number): FoldRow => ({
  fold: 1, measurable: true, retention,
  train_start: "2024-01-01", train_end: "2024-12-31",
  test_start: "2025-01-01", test_end: "2025-03-31",
  test_window: ["2025-01-02", "2025-03-28"], dates_honoured: true,
});

describe("a fold that produced no figure", () => {
  it("is never rendered as a retention of zero", () => {
    const v = foldVerdict({ measurable: false, retention: null,
      reason: "the test leg placed no trades, so it says nothing either way" });
    assert.equal(v.label, "not measured");
    assert.notEqual(v.label, "0%");
    assert.ok(v.reason?.includes("no trades"));
  });

  it("separates OUR clock running out from the strategy's own silence", () => {
    const killed = foldVerdict({ measurable: false, timed_out: true,
      reason: "the engine hit its wall-clock ceiling" });
    const quiet = foldVerdict({ measurable: false,
      reason: "the test leg placed no trades" });
    assert.equal(killed.ours, true);
    assert.equal(quiet.ours, false);
    assert.notEqual(killed.tone, quiet.tone);
    assert.notEqual(killed.label, quiet.label);
    assert.ok(killed.label.includes("engine"));
  });

  it("refuses to print a zero when a fold claims measurable with no figure", () => {
    const v = foldVerdict({ measurable: true, retention: null });
    assert.notEqual(v.label, "0%");
    assert.ok(v.reason?.includes("defect in the record"));
  });
});

describe("a fold that did produce a figure", () => {
  it("is coloured against the same floor the gate uses", () => {
    assert.equal(foldVerdict(measurable(RETENTION_FLOOR)).tone, "kept");
    assert.equal(foldVerdict(measurable(RETENTION_FLOOR - 0.0001)).tone, "lost");
    assert.equal(foldVerdict(measurable(0.9)).label, "90%");
  });

  it("does not treat a negative retention as absent", () => {
    const v = foldVerdict(measurable(-0.3));
    assert.equal(v.tone, "lost");
    assert.equal(v.label, "-30%");
  });
});

describe("dates_honoured has three states, not two", () => {
  it("reads null as UNCHECKED — neither a validation nor an accusation", () => {
    assert.equal(honoured({ dates_honoured: null }), "unchecked");
    assert.equal(honoured({}), "unchecked");
    assert.equal(honoured({ dates_honoured: undefined }), "unchecked");
  });

  it("reads true and false as themselves", () => {
    assert.equal(honoured({ dates_honoured: true }), "honoured");
    assert.equal(honoured({ dates_honoured: false }), "dishonoured");
  });
});

describe("the window line", () => {
  it("shows requested and covered separately", () => {
    const l = windowLine(measurable(0.8));
    assert.equal(l.requested, "2025-01-01 → 2025-03-31");
    assert.equal(l.covered, "2025-01-02 → 2025-03-28");
  });

  it("says the engine reported nothing rather than echoing the request", () => {
    const l = windowLine({ test_start: "2025-01-01", test_end: "2025-03-31",
      test_window: null });
    assert.equal(l.covered, "engine reported none");
    assert.notEqual(l.covered, l.requested);
  });
});

describe("the tally", () => {
  it("counts engine kills apart from the other unmeasurables", () => {
    const t = foldTally([
      measurable(0.9), measurable(0.2),
      { measurable: false, timed_out: true },
      { measurable: false, reason: "the test leg placed no trades" },
    ]);
    assert.deepEqual(t, { attempted: 4, measurable: 2, retained: 1, timedOut: 1 });
  });

  it("is zero everywhere for no rows, without throwing", () => {
    assert.deepEqual(foldTally(null),
      { attempted: 0, measurable: 0, retained: 0, timedOut: 0 });
  });
});

describe("the cost band", () => {
  const points = [
    { parameters: { slip: "0.0005" }, state: "done", total_return_pct: 42.4 },
    { parameters: { slip: "0.0001" }, state: "done", total_return_pct: 49.8 },
    { parameters: { slip: "0.0003" }, state: "failed", total_return_pct: null,
      error: "timed out after 900s — engine killed" },
  ];

  it("orders by cost and converts the fraction to basis points", () => {
    const rows = costBand(points);
    assert.deepEqual(rows.map((r) => r.bps), [1, 3, 5]);
    assert.equal(rows[0].returnPct, 49.8);
  });

  it("keeps a FAILED point in the band with its error", () => {
    // Dropping it would silently narrow the band and make a partial sweep look
    // complete — the exact shape of the entry-11 timeouts.
    const rows = costBand(points);
    assert.equal(rows.length, 3);
    assert.equal(rows[1].state, "failed");
    assert.equal(rows[1].returnPct, null);
    assert.ok(rows[1].error?.includes("timed out"));
  });

  it("ignores points that never carried the swept parameter", () => {
    assert.equal(costBand([{ parameters: { fast: "10" } }]).length, 0);
  });
});

describe("the breakeven sentence", () => {
  it("states the crossing when there is one", () => {
    assert.ok(breakevenSentence({ breakeven_bps: 5.92 }, 3).includes("5.92bps"));
  });

  it("passes the spine's own reason through rather than inventing one", () => {
    const s = breakevenSentence(
      { breakeven_bps: null, reason: "still profitable at every cost tested" }, 3);
    assert.equal(s, "still profitable at every cost tested");
  });

  it("says a one-point grid is NOT MEASURED, never robust", () => {
    const s = breakevenSentence(null, 1);
    assert.ok(s.includes("NOT MEASURED"));
    assert.ok(!/robust\b(?!er)/.test(s.replace("as robust", "")));
  });
});

describe("the four absences stay four", () => {
  const bare = (over: Partial<CandidateRow>): CandidateRow =>
    ({ candidate_id: "c1", algorithm: "a", ...over });

  it("returns null when analytics are present", () => {
    assert.equal(absenceOf(bare({ analytics_available: true })), null);
    assert.equal(absenceOf(bare({ analytics: { available: true } })), null);
  });

  it("carries the spine's sentence, never a client-side 'no data'", () => {
    const a = absenceOf(bare({
      analytics_available: false,
      analytics_absence: { reason: NOT_CAPTURED,
        note: "this candidate was judged before the belt kept its analytics" },
    }));
    assert.equal(a?.reason, NOT_CAPTURED);
    assert.ok(a?.note.includes("before the belt kept its analytics"));
  });

  it("gives each absence its own badge", () => {
    const labels = [NOT_CAPTURED, PRUNED, NOT_TESTABLE, UNAVAILABLE].map(absenceLabel);
    assert.equal(new Set(labels).size, 4, "two absences share a badge");
    assert.equal(absenceLabel(PRUNED), "aged out");
    assert.equal(absenceLabel(undefined), "unknown");
  });

  it("names a MISSING reason as missing rather than guessing", () => {
    const a = absenceOf(bare({ analytics_available: false }));
    assert.equal(a?.reason, UNAVAILABLE);
    assert.ok(a?.note.includes("gap is in the record"));
  });

  it("keeps the pruned timestamp so 'aged out when' is answerable", () => {
    const a = absenceOf(bare({
      analytics_available: false,
      analytics_absence: { reason: PRUNED, note: "aged out",
        pruned_at: "2026-11-19T00:00:00+00:00" },
    }));
    assert.equal(a?.prunedAt, "2026-11-19T00:00:00+00:00");
  });
});

describe("rebasing the curve", () => {
  it("puts a raw equity series and a raw price series on one comparable axis", () => {
    // The measured shapes from job 53ef3e67d89a: equity in dollars, benchmark
    // in the underlying's price. Before this, both were plotted RAW on one
    // axis and the benchmark lay flat on the floor beneath the equity.
    const eq = rebase([100000, 93496.73, 102746.1]);
    const bm = rebase([683.68, 630.35, 734.3]);
    assert.equal(eq![0], 1);
    assert.equal(bm![0], 1);
    assert.ok(Math.abs(eq![2] - 1.02746) < 1e-4);
    assert.ok(Math.abs(bm![2] - 1.0741) < 1e-3);
    // Both now sit in the same neighbourhood — which is the whole point.
    assert.ok(Math.max(...eq!, ...bm!) < 1.2);
  });

  it("makes the axis label read as a percentage rather than as raw dollars", () => {
    const eq = rebase([100000, 103468.05])!;
    const label = `${((eq[1] - 1) * 100).toFixed(0)}%`;
    assert.equal(label, "3%");
    assert.notEqual(label, "10346705%");
  });

  it("is the identity on a series that already starts at 1.0", () => {
    assert.deepEqual(rebase([1, 1.2, 0.9]), [1, 1.2, 0.9]);
  });

  it("refuses rather than emitting Infinity or NaN into an SVG path", () => {
    assert.equal(rebase([0, 5, 7]), null);
    assert.equal(rebase([Number.NaN, 1]), null);
    assert.equal(rebase([100]), null, "one point is not a curve");
    assert.equal(rebase([]), null);
    assert.equal(rebase(null), null);
  });
});

describe("the gate's sentence", () => {
  it("is passed through verbatim, never paraphrased", () => {
    const g = gateSentence({ candidate_id: "c", algorithm: "a",
      verdict: { verdict: "fails 3 of the bar", passed: false,
        failures: ["probabilistic Sharpe 0.584% is below 65.0%"],
        gate_version: "v4.1" } });
    assert.equal(g.sentence, "fails 3 of the bar");
    assert.equal(g.version, "v4.1");
    assert.equal(g.failures.length, 1);
  });

  it("says ORPHANED is neither passed nor killed", () => {
    const g = gateSentence({ candidate_id: "c", algorithm: "a",
      state: "orphaned", passed: null });
    assert.ok(g.sentence.includes("ORPHANED"));
    assert.ok(g.sentence.includes("Neither passed nor killed"));
    assert.equal(g.passed, null);
  });

  it("surfaces an error as the reason there is no verdict", () => {
    const g = gateSentence({ candidate_id: "c", algorithm: "a", state: "failed",
      error: "sweep failed" });
    assert.ok(g.sentence.includes("sweep failed"));
    assert.equal(g.passed, null);
  });

  it("never reports a failed candidate as passed", () => {
    const g = gateSentence({ candidate_id: "c", algorithm: "a", state: "failed",
      passed: null, error: "verification run timeout" });
    assert.notEqual(g.passed, true);
  });
});
