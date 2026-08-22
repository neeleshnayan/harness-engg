/**
 * Tests for the mode presentation decisions.
 *
 * Run: node --experimental-strip-types --test src/app/clark/studio/fundMode.test.ts
 *
 * The failure this surface prevents is a human reading a test number as a real
 * one, so the properties guarded here are the ones that would let that happen:
 * an unknown mode rendering as a known one, a warning that is quieter than the
 * risk, and a prod precondition that reads as passing when nothing checked it.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import type { FundModeName, FundModeReport, FundModeSpec } from "@/lib/fund_api";
import {
  confirmEcho, preconditionTone, presentMode, selectability,
} from "./fundMode.ts";

const spec = (mode: FundModeName, over: Partial<FundModeSpec> = {}): FundModeSpec => ({
  mode,
  label: mode,
  caution: "",
  wired: mode !== "alpaca-prod",
  venue: {
    kind: mode === "test" ? "simulated" : "alpaca_paper",
    label: mode === "test" ? "paper" : "alpaca",
    permitted_connectors: [mode === "test" ? "paper" : "alpaca"],
    real_broker: mode !== "test",
    real_money: mode === "alpaca-prod",
  },
  store: {
    pg_database:
      mode === "test" ? "krypton_fund_test"
        : mode === "alpaca-paper" ? "krypton_fund" : "krypton_fund_prod",
  },
  ...over,
});

const report = (
  active: FundModeSpec | null,
  over: Partial<FundModeReport> = {},
): FundModeReport => ({
  active,
  declared: { env: null, file: null, file_path: ".fund_mode", file_error: null },
  modes: [spec("test"), spec("alpaca-paper"), spec("alpaca-prod")],
  prod_gate: {
    code_lock: { constant: "app.fund.mode.PROD_UNLOCKED", value: false, open: false },
    preconditions: [],
    n_preconditions: 5,
    n_met: 0,
    n_blocking: 5,
    reachable: false,
  },
  receipt: { order_id: "17d64dcd", note: "" },
  ...over,
});

// --- absence is never a mode -------------------------------------------------

test("an unreachable spine is NOT rendered as any mode", () => {
  const p = presentMode(null);
  assert.equal(p.key, "unreachable");
  assert.notEqual(p.key, "test");
  assert.notEqual(p.key, "alpaca-paper");
});

test("an unreachable spine is ALARMING, not quiet", () => {
  // Not knowing whether the numbers are real is not a calmer state than
  // knowing they are. A silent unknown is how a rehearsal gets read as a book.
  assert.equal(presentMode(null).volume, "alarming");
  assert.equal(presentMode(null).frameSurface, true);
});

test("a spine that declares no mode is a DIFFERENT unknown, and is loud", () => {
  const p = presentMode(report(null));
  assert.equal(p.key, "unknown");
  assert.equal(p.volume, "alarming");
  assert.notEqual(p.headline, presentMode(null).headline);
});

test("neither unknown ever claims real money", () => {
  assert.equal(presentMode(null).realMoney, false);
  assert.equal(presentMode(report(null)).realMoney, false);
});

// --- the three modes ---------------------------------------------------------

test("test mode is loud and frames the surface", () => {
  const p = presentMode(report(spec("test")));
  assert.equal(p.key, "test");
  assert.equal(p.volume, "loud");
  assert.equal(p.frameSurface, true);
  assert.equal(p.realMoney, false);
});

test("test mode names the store, so the record is findable", () => {
  assert.match(presentMode(report(spec("test"))).detail, /krypton_fund_test/);
});

test("test mode does NOT overstate — the prices are real and it says so", () => {
  // A warning that claims more than is true gets discounted, and then the true
  // part goes with it.
  assert.match(presentMode(report(spec("test"))).detail, /prices are real/);
});

test("alpaca-paper is QUIET — the fund's normal state must not shout", () => {
  const p = presentMode(report(spec("alpaca-paper")));
  assert.equal(p.volume, "quiet");
  assert.equal(p.frameSurface, false);
});

test("alpaca-paper still says it is not real money", () => {
  assert.equal(presentMode(report(spec("alpaca-paper"))).realMoney, false);
  assert.match(presentMode(report(spec("alpaca-paper"))).headline, /paper money/);
});

test("alpaca-prod is the loudest thing on the surface", () => {
  const p = presentMode(report(spec("alpaca-prod")));
  assert.equal(p.volume, "alarming");
  assert.equal(p.realMoney, true);
  assert.equal(p.frameSurface, true);
});

test("every state produces a badge and a headline — none renders blank", () => {
  const states = [null, report(null), report(spec("test")),
                  report(spec("alpaca-paper")), report(spec("alpaca-prod"))];
  for (const s of states) {
    const p = presentMode(s);
    assert.ok(p.badge.length > 0, JSON.stringify(p));
    assert.ok(p.headline.length > 0, JSON.stringify(p));
    assert.ok(p.detail.length > 0, JSON.stringify(p));
  }
});

// --- selectability -----------------------------------------------------------

test("alpaca-prod is never selectable while the code lock is shut", () => {
  const s = selectability(report(spec("test")), "alpaca-prod");
  assert.equal(s.selectable, false);
  assert.match(s.reason, /locked in code/);
  assert.match(s.reason, /5 of 5/);
});

test("alpaca-prod stays unselectable even if the code lock opens but preconditions do not", () => {
  // Two independent locks. Opening one must not open the gate.
  const r = report(spec("test"), {
    prod_gate: {
      code_lock: { constant: "c", value: true, open: true },
      preconditions: [], n_preconditions: 5, n_met: 3, n_blocking: 2,
      reachable: false,
    },
  });
  const s = selectability(r, "alpaca-prod");
  assert.equal(s.selectable, false);
  assert.match(s.reason, /2 of 5/);
});

test("a disabled control always carries a reason", () => {
  for (const target of ["test", "alpaca-paper", "alpaca-prod"] as FundModeName[]) {
    const s = selectability(null, target);
    assert.equal(s.selectable, false);
    assert.ok(s.reason.length > 0);
  }
});

test("the current mode is not selectable, and says why", () => {
  const s = selectability(report(spec("test")), "test");
  assert.equal(s.selectable, false);
  assert.match(s.reason, /already/);
});

test("switching between the two wired modes is allowed", () => {
  assert.equal(selectability(report(spec("test")), "alpaca-paper").selectable, true);
  assert.equal(selectability(report(spec("alpaca-paper")), "test").selectable, true);
});

test("an unwired mode is refused even when nothing else blocks it", () => {
  const r = report(spec("test"), {
    modes: [spec("test"), spec("alpaca-paper", { wired: false }), spec("alpaca-prod")],
  });
  const s = selectability(r, "alpaca-paper");
  assert.equal(s.selectable, false);
  assert.match(s.reason, /never been wired/);
});

// --- the approval echo -------------------------------------------------------

test("the echo is the first 8 characters of the target mode", () => {
  // The spine's guard computes target_id[:8]; if these two ever disagree every
  // switch is refused, so they are pinned together here.
  assert.equal(confirmEcho("test"), "test");
  assert.equal(confirmEcho("alpaca-paper"), "alpaca-p");
  assert.equal(confirmEcho("alpaca-prod"), "alpaca-p");
});

test("the two alpaca modes share an echo — the UI must send the MODE, not just the echo", () => {
  // Documented as a property rather than a bug: the echo proves the operator
  // read something, and the `mode` field is what actually selects. If a future
  // change made the echo the selector, this test says why that is wrong.
  assert.equal(confirmEcho("alpaca-paper"), confirmEcho("alpaca-prod"));
});

// --- preconditions -----------------------------------------------------------

test("an unchecked precondition BLOCKS and never reads as passing", () => {
  const t = preconditionTone("unchecked");
  assert.equal(t.blocking, true);
  assert.match(t.word, /unchecked/);
  assert.notEqual(t.symbol, preconditionTone("met").symbol);
});

test("met is the only non-blocking status", () => {
  assert.equal(preconditionTone("met").blocking, false);
  assert.equal(preconditionTone("unmet").blocking, true);
  assert.equal(preconditionTone("unchecked").blocking, true);
});
