import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import {
  RESIDUAL_TOLERANCE, type BookSource,
  bookHeadline, bookStrip,
} from "./bookStrip.ts";

/**
 * THE BOOK AS A PICTURE — the tests that fail if the strip starts lying.
 *
 * THE LIVE PAYLOAD IS A FIXTURE, not a hand-built ideal. `__fixtures__/
 * liveNav.json` is `GET /fund/nav` and `GET /fund/nav/history` as served by
 * the running spine on 2026-08-27, saved verbatim. A strip that works on
 * seven tidy positions and breaks on the fund's own book is not tested.
 */

const LIVE = JSON.parse(readFileSync(
  fileURLToPath(new URL("./__fixtures__/liveNav.json", import.meta.url)),
  "utf8")) as { nav_live: BookSource; nav_last_struck: BookSource };

/* -------------------------------------------------- against the real book -- */

test("the fund's OWN book draws, and the weights are the spine's figures", () => {
  const s = bookStrip(LIVE.nav_live);
  assert.equal(s.state, "book");
  assert.equal(s.positionCount, 7);
  // Seven positions plus the cash void.
  assert.equal(s.segments.length, 8);
  assert.equal(s.segments.filter((x) => x.kind === "cash").length, 1);

  // WEIGHTS COME FROM `usd_value`, NEVER FROM `qty * mark`. Proven by
  // arithmetic against the payload's own numbers rather than by asserting a
  // constant, which a hardcoded duplicate would satisfy.
  const spy = s.segments.find((x) => x.symbol === "SPY")!;
  const raw = LIVE.nav_live.positions!.find((p) => p.symbol === "SPY")!;
  assert.equal(spy.usd, raw.usd_value);
  assert.equal(spy.weight, raw.usd_value! / LIVE.nav_live.total_nav_usd!);
});

test("the parts reconcile with the whole on the live payload", () => {
  const s = bookStrip(LIVE.nav_live);
  assert.ok(Math.abs(s.residualPct!) <= RESIDUAL_TOLERANCE,
    `cash + positions must account for NAV; residual was ${s.residualPct}`);
  assert.doesNotMatch(s.note, /do not add up/);
  // The weights sum to one, within the same tolerance — the strip fills its
  // track because the record says it should, not because it was scaled to.
  const sum = s.segments.reduce((a, x) => a + x.weight, 0);
  assert.ok(Math.abs(sum - 1) <= RESIDUAL_TOLERANCE, `weights summed to ${sum}`);
});

test("the segments are ordered LARGEST FIRST and cash is last", () => {
  const s = bookStrip(LIVE.nav_live);
  const pos = s.segments.filter((x) => x.kind === "position");
  for (let i = 1; i < pos.length; i += 1) {
    assert.ok(pos[i - 1].usd >= pos[i].usd, `out of order at ${i}`);
  }
  assert.equal(s.segments[s.segments.length - 1].kind, "cash",
               "the void reads as the tail of the fund, not as a holding");
});

test("concentration is answered without the reader doing arithmetic", () => {
  const s = bookStrip(LIVE.nav_live);
  assert.equal(s.topSymbol, "SPY");
  assert.ok(s.topWeight! > 0.1 && s.topWeight! < 0.2);
  assert.match(bookHeadline(s), /SPY is the largest holding/);
  assert.match(bookHeadline(s), /is cash/);
});

/* --------------------------------------------- absence, three ways --------- */

test("an UNREADABLE book is not an empty one", () => {
  const s = bookStrip(null);
  assert.equal(s.state, "unreadable");
  assert.deepEqual(s.segments, []);
  assert.equal(s.totalUsd, null);
  assert.equal(s.topWeight, null);
  assert.match(s.note, /UNKNOWN/);
  assert.match(s.note, /not empty/);
});

test("a FLAT fund — all cash, no positions — is its own state and says so", () => {
  const s = bookStrip({ ts: "2026-08-13T13:16:57+00:00", total_nav_usd: 2000,
                        positions: [], breakdown: { cash: 2000, positions: 0 } });
  assert.equal(s.state, "flat");
  assert.equal(s.positionCount, 0);
  assert.equal(s.topWeight, null);
  assert.equal(s.cashWeight, 1);
  assert.match(s.note, /holds no positions/);
  // The strip is NOT empty: the whole track is the cash void, which is the
  // picture "this fund is doing nothing" is supposed to make.
  assert.equal(s.segments.length, 1);
  assert.equal(s.segments[0].kind, "cash");
  assert.equal(s.segments[0].weight, 1);
});

test("a fund with NO STATED TOTAL is unreadable, not zero", () => {
  const s = bookStrip({ positions: [{ symbol: "SPY", usd_value: 100 }] });
  assert.equal(s.state, "unreadable");
  assert.match(s.note, /no total NAV/);
  assert.deepEqual(s.segments, []);
  // A non-positive total is the same failure — a weight against zero has no
  // meaning and dividing by it would produce Infinity-wide segments.
  assert.equal(bookStrip({ total_nav_usd: 0, positions: [] }).state, "unreadable");
  assert.equal(bookStrip({ total_nav_usd: -5, positions: [] }).state, "unreadable");
});

test("a position with NO usd_value is dropped and shows up in the residual", () => {
  /* An invisible zero-width segment is a lie with no pixels. The row leaves
   * the strip and the money it represents becomes an explicit hole in the
   * reconciliation, where a reader can see it. */
  const s = bookStrip({
    total_nav_usd: 1000,
    positions: [{ symbol: "SPY", usd_value: 400 },
                { symbol: "TLT", usd_value: null },
                { symbol: "", usd_value: 100 }],
    breakdown: { cash: 200 },
  });
  assert.equal(s.positionCount, 1, "only SPY is drawable");
  assert.equal(s.segments.filter((x) => x.kind === "position").length, 1);
  // 1000 - (400 + 200) = 400 unaccounted.
  assert.ok(Math.abs(s.residualPct! - 0.4) < 1e-9);
  assert.match(s.note, /do not add up/);
  assert.match(s.note, /40\.0%/);
});

test("THE DISAGREEMENT IS PUBLISHED, NEVER ABSORBED", () => {
  // A strip renormalised to fill its track cannot be wrong, which is exactly
  // why this one is not. The weights are against the STATED total and the
  // shortfall is a number on the payload.
  const s = bookStrip({ total_nav_usd: 1000,
                        positions: [{ symbol: "SPY", usd_value: 300 }],
                        breakdown: { cash: 100 } });
  const sum = s.segments.reduce((a, x) => a + x.weight, 0);
  assert.ok(Math.abs(sum - 0.4) < 1e-9, "the strip does NOT fill its track");
  assert.ok(Math.abs(s.residualPct! - 0.6) < 1e-9);
});

test("the residual tolerance discriminates — it is not a rubber band", () => {
  // Just inside: silent. Just outside: stated. A tolerance that never fires
  // and one that always fires are the same non-instrument.
  const inside = bookStrip({ total_nav_usd: 1000,
    positions: [{ symbol: "S", usd_value: 998 }], breakdown: { cash: 0 } });
  assert.doesNotMatch(inside.note, /do not add up/);
  const outside = bookStrip({ total_nav_usd: 1000,
    positions: [{ symbol: "S", usd_value: 993 }], breakdown: { cash: 0 } });
  assert.match(outside.note, /do not add up/);
  assert.equal(RESIDUAL_TOLERANCE, 0.005);
});

test("an unreadable CASH figure does not silently become a full book", () => {
  /* Cash absent and cash zero are different: the first means the breakdown
   * could not be read, the second means the fund is fully invested. Merging
   * them would draw a fund with an unknown cash position as one with none. */
  const s = bookStrip({ total_nav_usd: 1000,
                        positions: [{ symbol: "SPY", usd_value: 400 }],
                        breakdown: { cash: null } });
  assert.equal(s.cashUsd, null);
  assert.equal(s.cashWeight, null);
  assert.equal(s.segments.filter((x) => x.kind === "cash").length, 0);
  assert.match(bookHeadline(s), /cash figure could not be read/);
  // ...and a fund with genuinely zero cash draws no void either, but its
  // cashWeight is a MEASURED zero.
  const zero = bookStrip({ total_nav_usd: 1000,
                           positions: [{ symbol: "SPY", usd_value: 1000 }],
                           breakdown: { cash: 0 } });
  assert.equal(zero.cashUsd, 0);
  assert.equal(zero.cashWeight, 0);
  assert.notEqual(zero.cashWeight, s.cashWeight);
});

test("the strip carries HOW OLD its reading is", () => {
  // Illumination principle 4. The live block and the last struck block are
  // two different instants and a strip that dropped the stamp would let a
  // reader treat yesterday's marks as now.
  assert.equal(bookStrip(LIVE.nav_live).asOf, LIVE.nav_live.ts);
  assert.equal(bookStrip(LIVE.nav_last_struck).asOf, LIVE.nav_last_struck.ts);
  assert.notEqual(bookStrip(LIVE.nav_live).asOf,
                  bookStrip(LIVE.nav_last_struck).asOf);
});

/* ------------------------------- branches the mutation pass found bare ---- */

test("a position worth EXACTLY ZERO is dropped, not drawn at zero width", () => {
  /* M31 SURVIVED. An invisible segment is a lie with no pixels: it counts in
   * `positionCount`, it appears in the caption, and it occupies none of the
   * track. The row leaves the strip and its (zero) money lands in the
   * reconciliation, where it costs nothing and can be seen. */
  const s = bookStrip({
    total_nav_usd: 1000,
    positions: [{ symbol: "SPY", usd_value: 400 },
                { symbol: "DEAD", usd_value: 0 }],
    breakdown: { cash: 600 },
  });
  assert.equal(s.positionCount, 1, "the zero position is not counted");
  assert.deepEqual(s.segments.map((x) => x.symbol), ["SPY", null]);
  assert.ok(!s.segments.some((x) => x.weight === 0),
            "no segment may have zero width");
  // A NEGATIVE value is the same refusal — a short marked this way would
  // otherwise draw a negative-width segment.
  const neg = bookStrip({ total_nav_usd: 1000,
    positions: [{ symbol: "SHORT", usd_value: -50 }], breakdown: { cash: 1050 } });
  assert.equal(neg.positionCount, 0);
});

test("a fund with EXACTLY ZERO cash draws no void, and says zero not unknown", () => {
  /* M32 SURVIVED. Three states again: cash absent (unreadable), cash zero
   * (fully invested), cash positive (a void). The middle one must produce no
   * segment — a zero-width void is the same pixels as no void — while still
   * reporting a MEASURED zero on `cashWeight`, which is what separates it
   * from the unreadable case. */
  const s = bookStrip({ total_nav_usd: 1000,
    positions: [{ symbol: "SPY", usd_value: 1000 }], breakdown: { cash: 0 } });
  assert.equal(s.segments.length, 1, "no cash segment at all");
  assert.ok(!s.segments.some((x) => x.kind === "cash"));
  assert.equal(s.cashUsd, 0);
  assert.equal(s.cashWeight, 0, "a MEASURED zero, not null");
  assert.match(bookHeadline(s), /0% is cash/);
  // A NEGATIVE cash figure (an overdrawn account) also draws no void — a bar
  // cannot have negative width — and the number survives for the caption.
  const od = bookStrip({ total_nav_usd: 1000,
    positions: [{ symbol: "SPY", usd_value: 1100 }], breakdown: { cash: -100 } });
  assert.ok(!od.segments.some((x) => x.kind === "cash"));
  assert.equal(od.cashUsd, -100);
});
