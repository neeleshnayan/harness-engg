/**
 * Tests for the retired pattern-day-trader rule.
 *
 * THE INCIDENT (2026-08-27): the PDT rule was retired and `SystemStatus` kept
 * rendering a green row that said *"above $25k — the rule does not restrict
 * this account"* over an account holding **$2,008.99**. The row was green for
 * the right reason and it stated the wrong one, which is the more dangerous
 * shape: a reader learns a fact about the account that is false.
 *
 * Every test names what it prevents.
 */

import { test } from "node:test";
import assert from "node:assert/strict";

import { readPdt, PDT_LABEL } from "./pdtRule.ts";
import type { ComplianceStatus } from "@/lib/fund_api";

/** The live payload of 2026-08-27, verbatim in shape. */
function comp(over: {
  account?: Partial<ComplianceStatus["account"]>;
  pdt?: Partial<ComplianceStatus["pdt"]>;
} = {}): ComplianceStatus {
  return {
    account: {
      known: true, equity: 2008.99, daytrade_count: null, pattern_day_trader: null,
      trading_blocked: false, account_blocked: false, shorting_enabled: false,
      status: "AccountStatus.ACTIVE", error: null,
      ...over.account,
    },
    pdt: {
      retired: true,
      retired_note: "the pattern-day-trader rule ended 2026-06-04; this block was " +
        "retired 2026-08-27 on the CEO's signature after an adversary-verified " +
        "review — the counts below are history, not a constraint",
      applies: false, equity_threshold: 25000, max_day_trades: 4, used: 0,
      remaining: null, broker_count: null, our_count: 0,
      source: "our event log", diverges: false,
      ...over.pdt,
    },
  } as ComplianceStatus;
}

test("a RETIRED rule is not a live constraint, and says so in the fund's own words", () => {
  const r = readPdt(comp());
  assert.equal(r.state, "retired");
  assert.equal(r.live, false);
  assert.equal(r.level, "ok");
  assert.equal(r.remaining, null);
  // The words come from the SPINE's `retired_note`, not from a sentence this
  // file wrote: the reason a control was retired is the record's to state.
  assert.equal(r.detail, comp().pdt.retired_note);
});

test("RETIRED is read from its own field, not inferred from `applies: false`", () => {
  // KILLS M-PDT-1, THE ACTUAL SHIPPED DEFECT. A retired rule also reports
  // `applies: false`. A reading that branched on `applies` first would land in
  // the exemption case and then have to guess a cause — which is exactly how
  // "above $25k" got printed over a $2,008.99 account.
  const r = readPdt(comp());
  assert.equal(r.state, "retired");
  assert.doesNotMatch(r.detail, /25,?000|above \$/);
});

test("an exemption with no stated cause does NOT invent one", () => {
  // KILLS M-PDT-2. This is the false sentence, isolated: `applies: false` with
  // no retirement and an account well under the threshold.
  const r = readPdt(comp({ pdt: { retired: false, retired_note: undefined, applies: false } }));
  assert.equal(r.state, "exempt");
  assert.equal(r.live, false);
  assert.equal(r.detail, "the rule does not apply, and the payload does not say why");
  assert.doesNotMatch(r.detail, /above/);
});

test("the threshold sentence is allowed EXACTLY when the equity clears it", () => {
  // A boundary table, because this is an inequality and the seat has shipped
  // strict-vs-non-strict survivors before.
  const at = (equity: number | null) =>
    readPdt(comp({ account: { equity }, pdt: { retired: false, applies: false } })).detail;
  assert.match(at(25000), /above \$25,000/);        // exactly at the threshold clears
  assert.match(at(25000.01), /above \$25,000/);
  assert.equal(at(24999.99), "the rule does not apply, and the payload does not say why");
  // An UNREADABLE equity gives no cause at all. It must never fall through to
  // the flattering branch.
  assert.equal(at(null), "the rule does not apply, and the payload does not say why");
});

test("an UNREADABLE compliance payload is UNKNOWN, never 'unrestricted'", () => {
  for (const bad of [null, undefined]) {
    const r = readPdt(bad);
    assert.equal(r.state, "unreadable");
    assert.equal(r.level, "unknown");
    assert.equal(r.live, false);
    assert.match(r.detail, /UNKNOWN, not unrestricted/);
  }
});

test("a LIVE rule still renders its cliff, with the levels it always had", () => {
  // The rule was retired, not deleted. If it ever returns, `live` is what the
  // surfaces switch on, and nothing about the cliff's arithmetic changed.
  const live = (remaining: number | null) =>
    readPdt(comp({ pdt: { retired: false, applies: true, used: 4 - (remaining ?? 0), remaining } }));
  assert.equal(live(3).level, "ok");
  assert.equal(live(2).level, "ok");
  assert.equal(live(1).level, "warn");
  assert.equal(live(0).level, "bad");
  assert.equal(live(3).live, true);
  assert.equal(live(3).remaining, 3);
  assert.match(live(2).detail, /2 left before a 90-day restriction/);
  // An unreadable remaining count is a WARNING, not a comfortable four: a
  // cliff whose distance is unknown is not a cliff you are far from.
  assert.equal(live(null).level, "warn");
  assert.match(live(null).detail, /remaining UNKNOWN/);
});

test("only a live rule is ever `live`", () => {
  // The one property every surface depends on. Asserted over all four states
  // rather than spot-checked, so a fifth state added later cannot default to
  // rendering a cliff.
  const states: [string, ComplianceStatus | null][] = [
    ["retired", comp()],
    ["exempt", comp({ pdt: { retired: false, applies: false } })],
    ["applies", comp({ pdt: { retired: false, applies: true, remaining: 2 } })],
    ["unreadable", null],
  ];
  for (const [name, c] of states) {
    const r = readPdt(c);
    assert.equal(r.state, name);
    assert.equal(r.live, name === "applies", `${name}: live must be ${name === "applies"}`);
    assert.ok(r.detail.length > 0, `${name} shipped a blank detail`);
  }
});

test("the row label lives in one place", () => {
  // Three surfaces render this rule. A label copied into each is how they
  // start disagreeing about what the reader is looking at.
  assert.equal(PDT_LABEL, "Day-trade budget");
});

// ------------------------- source pins: the three surfaces that render this

/**
 * SOURCE-LEVEL PINS, and the reason they are here rather than in three files.
 *
 * KryptonPay has no DOM runner, so a `.tsx` call site is unverifiable by
 * execution. What matters about this rule is a FAMILY property — three
 * surfaces render it and the measured defect was that only one of them was
 * wrong — so the pin is the family: every one of the three reads `readPdt`,
 * and none of them branches on `pdt.applies` on its own again.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const FAMILY = ["SystemStatus.tsx", "MonitorVerdict.tsx", "ClarkConsole.tsx"];
const src = (f: string) => readFileSync(join(HERE, f), "utf8");
/** Comments stripped: a negative scan that reads prose fails on the very
 *  comment that explains the fix. Measured on the engine page, same day. */
const code = (f: string) => src(f).replace(/\/\*[\s\S]*?\*\//g, "")
  .split("\n").filter((l) => !l.trim().startsWith("//")).join("\n");

test("all three surfaces read the rule through readPdt", () => {
  for (const f of FAMILY) {
    assert.match(code(f), /readPdt\(/, `${f} must read the shared reading`);
    assert.match(src(f), /from "\.\/pdtRule"/, `${f} must import it`);
  }
});

test("no surface branches on pdt.applies by itself any more", () => {
  // KILLS M-PDT-3, the family defect. `applies` is a field; `live` is the
  // question. A surface reading the field directly is one that will render a
  // retired rule as a constraint the next time the record changes under it.
  for (const f of FAMILY) {
    assert.doesNotMatch(code(f), /pdt\?*\.applies/, `${f} still reads applies directly`);
  }
});

test("no surface prints a day-trade count through `?? 0`", () => {
  // MonitorVerdict rendered `remaining ?? 0` and ClarkConsole `remaining ?? 0`:
  // "0 day trades left" for a budget nobody could read — the most alarming
  // possible rendering of an absence, on the fund's one-line verdict.
  for (const f of FAMILY) {
    assert.doesNotMatch(code(f), /remaining \?\? 0/, `${f} still defaults an absent count to zero`);
  }
});

test("the retired rule is not offered to the CEO as a standing question", () => {
  // The quietest way a dead control stays alive: not as a number, as a QUESTION
  // the operator is invited to ask. The prompt rotation kept offering "What can
  // I still do today without burning a day trade?" after the rule ceased to
  // exist.
  assert.doesNotMatch(code("ClarkConsole.tsx"), /burning a day trade/);
  // And the rotation did not simply SHRINK — a prompt removed without a
  // replacement quietly narrows what the surface teaches an operator Clark can
  // do, which is the rotation's entire job.
  //
  // THE SCAN IS BOUNDED TO THE ARRAY, not to an indentation. The first version
  // of this counted every six-space-indented string literal in the file and
  // returned 15 over a ten-item list — a count with the wrong domain, which is
  // this seat's most-repeated own defect and was caught here by the count
  // simply disagreeing with the source.
  const body = code("ClarkConsole.tsx");
  const from = body.indexOf("const standing = [");
  assert.ok(from > 0, "the standing rotation must still exist");
  const arr = body.slice(from, body.indexOf("];", from));
  const prompts = [...arr.matchAll(/"[^"]+"/g)];
  assert.equal(prompts.length, 10, "the standing rotation is still ten prompts");
  // The replacement points at the surface this dispatch built, so the prompt
  // that went is replaced by one that leads somewhere real.
  assert.ok(arr.includes("Is the engine running"));
});
