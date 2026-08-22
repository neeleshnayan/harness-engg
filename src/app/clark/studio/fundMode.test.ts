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
  confirmEcho, declarationConflict, preconditionTone, presentMode,
  selectability,
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
      mode === "test" ? "krypton_fund_dev"
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
  assert.match(presentMode(report(spec("test"))).detail, /krypton_fund_dev/);
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

// --- KP repair: a fourth mode must not blank the screen ----------------------
//
// Adversary review of builder D11, 2026-08-22 — the one named repair on the
// KryptonPay half. `presentMode` was a switch over a three-member union with
// no `default:`, so a spine reporting a fourth mode returned `undefined` and
// `ModeBar` dereferenced it unguarded. The failure mode is a blank Studio at
// exactly the moment the fund has grown a mode this build cannot name.
//
// The union is a claim about THIS BUILD, not about the world: `active.mode`
// arrives over the wire from a spine that may be a different version. Every
// test below feeds a value the type forbids, deliberately, through a cast.

const fourth = (name: string): FundModeReport =>
  report({ ...spec("test"), mode: name as FundModeName });

test("a mode this build has never heard of does not return undefined", () => {
  const p = presentMode(fourth("alpaca-margin"));
  assert.ok(p, "presentMode returned undefined — ModeBar dereferences this");
  assert.equal(typeof p.badge, "string");
  assert.equal(typeof p.headline, "string");
  assert.equal(typeof p.detail, "string");
});

test("an unrecognised mode is ALARMING and frames the surface", () => {
  // Same judgement the rest of this file makes about every unknown: a UI and
  // a spine disagreeing about which fund this is, is precisely the state where
  // a human reads a test number as a real one. And a mode nobody recognises
  // could be a real-money one.
  const p = presentMode(fourth("alpaca-margin"));
  assert.equal(p.key, "unrecognised");
  assert.equal(p.volume, "alarming");
  assert.equal(p.frameSurface, true);
});

test("an unrecognised mode NAMES the value it could not read", () => {
  // Without the name this is an unactionable warning: the operator cannot tell
  // a typo in a mode file from a spine that has genuinely moved ahead.
  assert.match(presentMode(fourth("alpaca-margin")).headline, /alpaca-margin/);
});

test("an unrecognised mode is never mistaken for a known one", () => {
  const p = presentMode(fourth("alpaca-paper-2"));
  for (const known of ["test", "alpaca-paper", "alpaca-prod"]) {
    assert.notEqual(p.key, known);
  }
});

test("every mode value produces a usable presentation, including junk", () => {
  // The property, rather than one example. If a future edit reintroduces a
  // switch arm without a default, one of these returns undefined.
  const values = ["test", "alpaca-paper", "alpaca-prod", "alpaca-margin",
                  "", "TEST", "ibkr-live", "undefined"];
  for (const v of values) {
    const p = presentMode(fourth(v));
    assert.ok(p, `presentMode(${JSON.stringify(v)}) returned undefined`);
    assert.ok(p.badge.length > 0);
    assert.ok(["quiet", "loud", "alarming"].includes(p.volume));
  }
});

test("an unrecognised precondition status BLOCKS rather than passing", () => {
  // The same missing-default hazard, in the same file, on another string that
  // arrives over the wire. The one thing a precondition row must never do is
  // read as passing because this build has not heard of its status.
  const t = preconditionTone("pending" as "met");
  assert.ok(t);
  assert.equal(t.blocking, true);
  assert.match(t.word, /unrecognised/);
});

// --- K7: the two declarations, and the restart they have armed ---------------

test("no conflict when the two authorities agree", () => {
  const r = report(spec("test"), {
    declared: {
      env: "test",
      file: { mode: "test" },
      file_path: ".fund_mode",
      file_error: null,
      conflict: null,
    },
  });
  assert.equal(declarationConflict(r), null);
});

test("no conflict when only one authority has spoken", () => {
  const envOnly = report(spec("test"), {
    declared: { env: "test", file: null, file_path: ".fund_mode", file_error: null },
  });
  const fileOnly = report(spec("test"), {
    declared: {
      env: null, file: { mode: "test" }, file_path: ".fund_mode", file_error: null,
    },
  });
  assert.equal(declarationConflict(envOnly), null);
  assert.equal(declarationConflict(fileOnly), null);
});

test("the spine's own conflict block is used verbatim when present", () => {
  const r = report(spec("test"), {
    declared: {
      env: "alpaca-paper",
      file: { mode: "test" },
      file_path: ".fund_mode",
      file_error: null,
      conflict: {
        env: "alpaca-paper", file: "test",
        effect: "the next spine start will REFUSE with ModeConflict",
        remedy: "either start with FUND_MODE=test or switch back",
      },
    },
  });
  const c = declarationConflict(r);
  assert.ok(c);
  assert.match(c.effect, /REFUSE with ModeConflict/);
  assert.match(c.remedy, /FUND_MODE=test/);
});

test("a spine too old to send `conflict` still gets the disagreement rendered", () => {
  // A missing key must not read as "no conflict". This is the absence rule
  // applied to a version skew: the UI can see both declarations itself, so it
  // does, rather than falling silent because the spine did not compute it.
  const r = report(spec("test"), {
    declared: {
      env: "alpaca-paper",
      file: { mode: "test" },
      file_path: ".fund_mode",
      file_error: null,
    },
  });
  const c = declarationConflict(r);
  assert.ok(c, "the UI must detect the disagreement without the spine's help");
  assert.equal(c.env, "alpaca-paper");
  assert.equal(c.file, "test");
  assert.match(c.effect, /ModeConflict/);
  assert.match(c.remedy, /FUND_MODE=test/);
});

test("an unreachable spine reports no conflict rather than inventing one", () => {
  assert.equal(declarationConflict(null), null);
});

// --- the current mode is not a warning ---------------------------------------

test("the CURRENT mode is flagged isCurrent, not as a problem", () => {
  // Found by SCREENSHOTTING the dialog: every unavailable row wore the warning
  // colour, so the one row that is unavailable on every single reading — the
  // mode you are already in — shouted as loudly as "locked in code, 5 of 5
  // preconditions not met". A palette where the ordinary case is amber is a
  // palette where nobody reads the amber.
  const s = selectability(report(spec("test")), "test");
  assert.equal(s.selectable, false);
  assert.equal(s.isCurrent, true);
});

test("every OTHER refusal is not isCurrent", () => {
  const r = report(spec("test"));
  assert.equal(selectability(r, "alpaca-prod").isCurrent, false);
  assert.equal(selectability(null, "test").isCurrent, false);
  const unwired = report(spec("test"), {
    modes: [spec("test"), spec("alpaca-paper", { wired: false }),
            spec("alpaca-prod")],
  });
  assert.equal(selectability(unwired, "alpaca-paper").isCurrent, false);
});

test("a selectable mode is never isCurrent", () => {
  const s = selectability(report(spec("test")), "alpaca-paper");
  assert.equal(s.selectable, true);
  assert.equal(s.isCurrent, false);
});
