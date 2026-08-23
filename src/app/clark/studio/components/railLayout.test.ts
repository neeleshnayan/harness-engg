/**
 * THE CLIP INVARIANT — the test that fails if the 2026-08-22 shell clip returns.
 *
 * THE INCIDENT, named because a regression test that does not name its
 * incident is a test nobody knows to keep. At a 1024px viewport with the Clark
 * rail open, the rail's left edge was at x=589 while every Studio page's
 * content ran to x=1009, `body` carried no inset, and a CDP probe found
 * **1,923 elements whose clicks the rail intercepted** — the risk bar's breach
 * sentence, the position ticker and the right half of every decision card
 * among them. At 1099 the count was 1,928. At 1280 and 1440 it was 0.
 *
 * The law these tests hold is one sentence: **the rail sits BESIDE the content
 * or it covers the viewport whole; it never covers part of it.** Everything
 * below is that sentence in a form that fails.
 *
 * Run: `node --experimental-strip-types --test src/app/clark/studio/components/railLayout.test.ts`
 */

import { strict as assert } from "node:assert";
import { test } from "node:test";
import { readFileSync } from "node:fs";

import {
  CONTENT_MIN, RAIL_MIN, RAIL_W, SHEET_BELOW, bodyPaddingRight, openByDefault,
  railLayout,
} from "./railLayout.ts";

/** Every integer width from a phone to a 4K panel, plus the exact boundaries
 *  and the two widths the incident was measured at.
 *
 *  Enumerated rather than sampled, and the reason is the incident: the defect
 *  was present at EVERY width below 1100 — not in a band — and it survived
 *  because the widths anyone actually looks at are 1280 and up, where the old
 *  code was correct. A handful of sampled widths would have missed it exactly
 *  the way every previous pass did. */
const DOMAIN: number[] = (() => {
  const w: number[] = [];
  for (let x = 240; x <= 3840; x += 1) w.push(x);
  return w;
})();

test("THE CLIP INVARIANT: content is never partly under the rail, at any width", () => {
  for (const w of DOMAIN) {
    const l = railLayout(w, true);
    // Content occupies [0, w - contentInset]; the rail occupies
    // [w - railWidth, w]. They are disjoint iff contentInset >= railWidth.
    // The one sanctioned exception is the rail covering the whole viewport,
    // where nothing is half-reachable.
    const beside = l.contentInset >= l.railWidth;
    const whole = l.railWidth === w && l.covers;
    assert.ok(
      beside || whole,
      `width ${w}: mode=${l.mode} railWidth=${l.railWidth} inset=${l.contentInset}`
      + " leaves a band of content under a click-eating panel — this is the"
      + " 2026-08-22 shell clip",
    );
  }
});

test("the incident's own widths: 1024 and 1099 inset the page by the rail's width", () => {
  // 1024 and 1099 are the two VIEWPORT widths the probe measured, at 1,923
  // and 1,928 intercepted elements; 1009 and 1084 are the LAYOUT widths they
  // resolved to on that machine and are what the code actually sees. The
  // defect was an inset of ZERO at all four, and that is what this pins.
  for (const w of [1024, 1009, 1099, 1084]) {
    const l = railLayout(w, true);
    assert.equal(l.mode, "push", `width ${w} must dock beside, not over`);
    assert.equal(l.contentInset, l.railWidth, `width ${w}: inset must equal rail width`);
    assert.ok(l.contentInset > 0, `width ${w}: a zero inset IS the defect`);
  }
  // Below 1060 the cockpit's measured floor binds and the RAIL is what gives
  // way — hardcoded, because this is the behaviour the fix adds and reading it
  // off the constants would let the constants move it.
  assert.equal(railLayout(1024, true).railWidth, 384);
  assert.equal(railLayout(1009, true).railWidth, 369);
  // At and above 1060 the rail keeps its full width and the page is inset by
  // it, which is the half the old code got right.
  assert.equal(railLayout(1099, true).railWidth, 420);
  assert.equal(railLayout(1084, true).railWidth, 420);
});

test("push always leaves the cockpit its measured minimum", () => {
  for (const w of DOMAIN) {
    const l = railLayout(w, true);
    if (l.mode !== "push") continue;
    assert.ok(w - l.railWidth >= CONTENT_MIN,
      `width ${w}: content column ${w - l.railWidth} is under the measured ${CONTENT_MIN} floor`);
  }
});

test("padding and rail width are ONE quantity in push, never two", () => {
  // The shipped defect wrote `${RAIL_W}px` of padding beside a `max-w-[92vw]`
  // rail: two expressions for one edge, which agree only while neither binds.
  for (const w of DOMAIN) {
    const l = railLayout(w, true);
    if (l.mode === "push") assert.equal(l.contentInset, l.railWidth);
  }
});

test("closed means nothing is covered and nothing is inset, at every width", () => {
  for (const w of DOMAIN) {
    const l = railLayout(w, false);
    assert.equal(l.mode, "pill");
    assert.equal(l.railWidth, 0);
    assert.equal(l.contentInset, 0);
    assert.equal(l.covers, false);
  }
});

test("the shipped desktop geometry is unchanged: 420px beside the cockpit", () => {
  // Hardcoded, not read from RAIL_W: a test parametrised by the constant it
  // guards moves with the constant and pins nothing (D21).
  for (const w of [1060, 1100, 1280, 1440, 1920, 2560]) {
    const l = railLayout(w, true);
    assert.equal(l.mode, "push");
    assert.equal(l.railWidth, 420, `width ${w} must keep the shipped 420px rail`);
    assert.equal(l.contentInset, 420);
  }
});

test("the sheet boundary is exact and the modes do not oscillate", () => {
  assert.equal(railLayout(SHEET_BELOW, true).mode, "push");
  assert.equal(railLayout(SHEET_BELOW - 1, true).mode, "sheet");
  // Hardcoded from the other side of the boundary — see above.
  assert.equal(railLayout(960, true).mode, "push");
  assert.equal(railLayout(959, true).mode, "sheet");
  assert.equal(railLayout(959, true).railWidth, 959);
  assert.equal(railLayout(959, true).covers, true);

  // Monotone: once a width pushes, every wider width pushes.
  let seenPush = false;
  for (const w of DOMAIN) {
    const m = railLayout(w, true).mode;
    if (m === "push") seenPush = true;
    else if (seenPush) assert.fail(`width ${w} fell back to ${m} after a narrower width pushed`);
  }
});

test("a fractional width rounds DOWN — the safe direction", () => {
  /* Found by mutation: `Math.floor` → `Math.ceil` SURVIVED, because every
   * width in the domain above is an integer. It is not an equivalent mutant:
   * rounding UP hands the rail a pixel of room the viewport does not have,
   * and it flips the sheet boundary on a fractional viewport. `clientWidth`
   * is an integer today, so this is a contract test, not a live one — which
   * is exactly why nothing else was going to catch it. */
  assert.equal(railLayout(959.9, true).mode, "sheet",
    "959.9 is 959 of usable width and must not push");
  assert.equal(railLayout(960.9, true).mode, "push");
  assert.equal(railLayout(1024.9, true).railWidth, 384,
    "the spare 0.9px is not room for the rail");
  assert.equal(railLayout(1059.99, true).railWidth, 419);
});

test("bodyPaddingRight is the ONLY thing that decides the page's inset", () => {
  /* Also from mutation: writing "" unconditionally — an inset of zero, which
   * IS the 1,923-element clip — SURVIVED while the expression lived inside a
   * React effect no runner here can execute. */
  assert.equal(bodyPaddingRight(railLayout(1440, true)), "420px");
  assert.equal(bodyPaddingRight(railLayout(1024, true)), "384px");
  assert.equal(bodyPaddingRight(railLayout(1009, true)), "369px");
  assert.equal(bodyPaddingRight(railLayout(900, true)), "",
    "a sheet covers the page rather than insetting it");
  assert.equal(bodyPaddingRight(railLayout(1440, false)), "",
    "a closed rail insets nothing");
  assert.equal(bodyPaddingRight(railLayout(Number.NaN, true)), "",
    "an unmeasured viewport insets nothing");
  // Over the whole domain: a push ALWAYS produces a non-empty inset.
  for (const w of DOMAIN) {
    const l = railLayout(w, true);
    if (l.mode === "push") {
      assert.equal(bodyPaddingRight(l), `${l.railWidth}px`,
        `width ${w}: the inset must be the rail's own width in px`);
    } else {
      assert.equal(bodyPaddingRight(l), "");
    }
  }
});

test("an unreadable viewport does not dock — absence is not 'wide'", () => {
  for (const bad of [0, -1, -1024, Number.NaN, Number.POSITIVE_INFINITY]) {
    const l = railLayout(bad, true);
    assert.equal(l.mode, "pill", `width ${String(bad)} must fail to the pill`);
    assert.equal(l.railWidth, 0);
    assert.equal(l.contentInset, 0);
  }
});

test("openByDefault is the push question, and it is not a second breakpoint", () => {
  for (const w of DOMAIN) {
    assert.equal(openByDefault(w), railLayout(w, true).mode === "push",
      `width ${w}: the default and the layout disagree`);
  }
  // Hardcoded both sides of the boundary.
  assert.equal(openByDefault(960), true);
  assert.equal(openByDefault(959), false);
  assert.equal(openByDefault(Number.NaN), false);
});

test("SHEET_BELOW is derived, and the numbers carry the basis their comments claim", () => {
  assert.equal(SHEET_BELOW, RAIL_MIN + CONTENT_MIN);
  // The measured floor, hardcoded: 640 is the narrowest width at which all six
  // Studio pages rendered with no horizontal overflow (CDP sweep 2026-08-23;
  // first overflow /clark/studio/desk at 600px, by 959px).
  assert.equal(CONTENT_MIN, 640);
  assert.equal(RAIL_W, 420);
  assert.equal(RAIL_MIN, 320);
});

/* ---------------------------------------------------------------------------
 * The component must READ this module. A pure function nothing calls is a
 * control with no caller, which is the failure family this firm names most
 * often. These are source-level because there is no DOM test runner here.
 * ------------------------------------------------------------------------ */

const CONSOLE_SRC = readFileSync(
  new URL("./ClarkConsole.tsx", import.meta.url), "utf8");

/** Source with comments removed.
 *
 *  Written because the first cut of the `max-w-[92vw]` check FAILED against a
 *  file that no longer carries the class: it matched the comment explaining
 *  why the class was removed. A text scan for a name finds the name in the
 *  prose about the name — the same trap as grepping source text for an import
 *  (D20). Anything asserting "this code does not do X" must read code. */
const code = (s: string) =>
  s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
const CONSOLE_CODE = code(CONSOLE_SRC);

test("ClarkConsole consumes railLayout and holds no breakpoint of its own", () => {
  assert.ok(/from "\.\/railLayout"/.test(CONSOLE_CODE),
    "ClarkConsole must import the layout law rather than restating it");
  assert.ok(/railLayout\(/.test(CONSOLE_CODE), "railLayout is never called");
  assert.ok(/openByDefault\(/.test(CONSOLE_CODE), "openByDefault is never called");
  // The retired constant, and any second copy of a breakpoint.
  assert.ok(!/PUSH_MIN_WIDTH/.test(CONSOLE_CODE),
    "PUSH_MIN_WIDTH decided two different questions and is retired");
  assert.ok(!/max-w-\[\d+vw\]/.test(CONSOLE_CODE),
    "a viewport-relative max-width is a SECOND owner of the rail's width;"
    + " in sheet mode it would leave exactly the clipped band this fix removes");
  // The width the rail RENDERS at must be the one the layout decided; a
  // literal beside it is how the two owners got there in the first place.
  assert.ok(/width:\s*layout\.railWidth/.test(CONSOLE_CODE),
    "the aside's width must come from layout.railWidth");
  assert.ok(/bodyPaddingRight\(layout\)/.test(CONSOLE_CODE),
    "the page's inset must come from the tested function, not an inline expression");
  // SOURCE-LEVEL, and stated as such: the dock choice happens inside a React
  // component and no runner here can render it. `!open` and
  // `layout.mode === "pill"` differ only when the width is unreadable, where
  // the second one refuses to dock and the first renders a zero-width rail.
  assert.ok(/const dock = layout\.mode === "pill" \?/.test(CONSOLE_CODE),
    "the dock choice must read the layout, not `open` — an unread width must "
    + "not produce a docked panel of zero width");
});

test("the rail is measured against the LAYOUT viewport, not innerWidth", () => {
  // 1024 innerWidth is 1009 of layout on a classic-scrollbar machine, and a
  // `right: 0` fixed panel sits at the layout edge. Deciding the layout with
  // the larger number is a 15px error in the direction that clips.
  assert.ok(/documentElement\.clientWidth/.test(CONSOLE_CODE),
    "the layout viewport must be read from documentElement.clientWidth");
  assert.ok(!/window\.innerWidth/.test(CONSOLE_CODE),
    "innerWidth includes the scrollbar and is the wrong edge for a fixed panel");
});
