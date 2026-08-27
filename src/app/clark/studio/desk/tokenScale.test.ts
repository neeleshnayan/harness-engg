import test from "node:test";
import assert from "node:assert/strict";

import {
  K, M, fmtTokens, fmtTokensCompact, fmtTokensShort, tokenScale, tokensAbsent,
} from "./tokenScale.ts";
import { fmtTokens as fromSeatLib } from "./seatLib.ts";
import { fmtTokensCompact as fromTelemetry } from "./deskTelemetry.ts";
import { fmtTokensShort as fromBriefing } from "./briefing.ts";

/**
 * THE CEO'S DEFECT, AS A TEST: `18863k` is not a number a person reads.
 *
 * And the three-implementations problem underneath it — every assertion below
 * that names a boundary is one all three old bodies got wrong.
 */

test("the reported defect: 18,863,000 reads as 18.9M, never 18863k", () => {
  assert.equal(tokenScale(18_863_000), "18.9M");
  assert.ok(!tokenScale(18_863_000).endsWith("k"),
            "a seven-figure count spoken in thousands is the reported bug");
});

test("the carry at 999,999 — the boundary all three bodies got wrong", () => {
  // Math.round(999999/1000) is 1000, which is a MILLION. Testing the raw
  // value against 1_000_000 (what all three old bodies did) prints `1000k`.
  assert.equal(tokenScale(999_999), "1.0M");
  assert.equal(tokenScale(999_500), "1.0M", "rounds up into the carry");
  assert.equal(tokenScale(999_499), "999k", "one below the carry stays in k");
});

test("the k boundary is inclusive and the sub-k range is spoken in full", () => {
  assert.equal(tokenScale(0), "0");
  assert.equal(tokenScale(1), "1");
  assert.equal(tokenScale(999), "999");
  assert.equal(tokenScale(K), "1k");
  assert.equal(tokenScale(K - 1), "999");
});

test("the M boundary is inclusive", () => {
  assert.equal(tokenScale(M), "1.0M");
  assert.equal(tokenScale(M - 1), "1.0M", "carries");
  assert.equal(tokenScale(1_240_000), "1.2M");
  assert.equal(tokenScale(540_438), "540k");
});

test("a negative count is spoken by magnitude with its sign", () => {
  // A token count should never be negative. If one is, `-18.9M` is a legible
  // symptom; `-18863k` would be a second bug printed on top of the first.
  assert.equal(tokenScale(-18_863_000), "-18.9M");
  assert.equal(tokenScale(-1500), "-2k");
  assert.equal(tokenScale(-999), "-999");
});

/* ------------------------------------------------ absence is not a zero --- */

test("ZERO IS A MEASUREMENT AND NULL IS NOT — the two never converge", () => {
  assert.equal(tokensAbsent(0), false, "a run reporting 0 tokens reported one");
  assert.equal(tokensAbsent(null), true);
  assert.equal(tokensAbsent(undefined), true);
  assert.equal(tokensAbsent(NaN), true);
  assert.equal(tokensAbsent(Infinity), true, "not a count anybody measured");

  assert.equal(fmtTokens(0), "0");
  assert.equal(fmtTokens(null), "—");
  assert.equal(fmtTokens(NaN), "—");
});

test("the three wrappers keep their OWN absence contracts", () => {
  // This is the whole reason there are three names and one scale. `cto/page`
  // prints "no token totals filed" for absent, which an em dash cannot say —
  // so `fmtTokensShort` must return null and the other two must not.
  assert.equal(fmtTokensShort(null), null);
  assert.equal(fmtTokensShort(undefined), null);
  assert.equal(fmtTokens(null), "—");
  assert.equal(fmtTokensCompact(null), "—");
  // ...and they agree about everything that is not absent.
  for (const n of [0, 1, 999, 1000, 999_999, 1_000_000, 18_863_000]) {
    assert.equal(fmtTokens(n), tokenScale(n), `fmtTokens ${n}`);
    assert.equal(fmtTokensCompact(n), tokenScale(n), `compact ${n}`);
    assert.equal(fmtTokensShort(n), tokenScale(n), `short ${n}`);
  }
});

/* -------------------------------------------- the unification, PROVEN ----- */

test("all three module-level names now resolve to ONE implementation", () => {
  /* THE UNIFICATION IS THE POINT, so it is asserted through the modules the
   * call sites actually import from — `seatLib`, `deskTelemetry` and
   * `briefing` — rather than through this module, which would prove only that
   * this module agrees with itself.
   *
   * On the BASE commit these three disagreed: seatLib said `18863k`,
   * deskTelemetry and briefing said `18.9M`, and all three said `1000k` at
   * 999,999. */
  assert.equal(fromSeatLib(18_863_000), "18.9M");
  assert.equal(fromTelemetry(18_863_000), "18.9M");
  assert.equal(fromBriefing(18_863_000), "18.9M");

  for (const n of [999, 1000, 540_438, 999_499, 999_999, 1_000_000, 18_863_000]) {
    assert.equal(fromSeatLib(n), fromTelemetry(n), `seatLib vs telemetry @ ${n}`);
    assert.equal(fromSeatLib(n), fromBriefing(n), `seatLib vs briefing @ ${n}`);
  }
});

test("A RE-EXPORT IS NOT AN IMPORT — the modules can call their own name", () => {
  /* `export { x } from "./y"` forwards x to CONSUMERS and leaves `x`
   * undefined inside the re-exporting module. The first unification shipped
   * exactly that and 25 tests went red with
   * `ReferenceError: fmtTokensShort is not defined` — while `tsc` stayed
   * silent, because a re-exported binding types as in-scope.
   *
   * `briefing.ts` and `deskTelemetry.ts` both CALL their own exported name
   * internally, so this exercises those internal call paths rather than the
   * exports: if the import form is ever reverted to a bare re-export, these
   * throw. */
  assert.equal(typeof fromBriefing, "function");
  assert.equal(typeof fromTelemetry, "function");
  assert.equal(typeof fromSeatLib, "function");
});

test("the unit constants are the ones the scale actually uses", () => {
  // A named constant that disagrees with the arithmetic beside it is a
  // comment wearing a type. Proven by MOVING the value rather than comparing
  // it: 1 below K must not carry, K exactly must.
  assert.equal(K, 1000);
  assert.equal(M, 1_000_000);
  assert.equal(tokenScale(K - 1), `${K - 1}`);
  assert.equal(tokenScale(K), "1k");
  assert.equal(tokenScale(M), "1.0M");
});
