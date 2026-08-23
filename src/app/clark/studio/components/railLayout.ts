/**
 * WHERE THE CLARK RAIL SITS, AND HOW MUCH ROOM THE COCKPIT KEEPS.
 *
 * THE INCIDENT THIS MODULE EXISTS TO CLOSE (measured 2026-08-22 by CDP probe,
 * reproduced 2026-08-23 before this fix). At a 1024px viewport with the rail
 * open, the Studio rendered:
 *
 *   | viewport | layout width | body pad-right | rail left | content right | elements whose clicks the rail ate |
 *   |---------:|-------------:|---------------:|----------:|--------------:|-----------------------------------:|
 *   |     1024 |         1009 |          0px   |       589 |          1009 |                            **1923** |
 *   |     1099 |         1084 |          0px   |       664 |          1084 |                            **1928** |
 *   |     1280 |         1265 |        420px   |       845 |           845 |                                   0 |
 *   |     1440 |         1425 |        420px   |      1005 |          1005 |                                   0 |
 *
 * A 420px band of EVERY Studio page — the risk bar's breach sentence, the
 * position ticker, the right half of every decision card — rendered underneath
 * a fixed panel that intercepted every click in it. Not a cosmetic clip: the
 * page looked complete and 1,923 elements were unreachable.
 *
 * THE CAUSE was one condition doing two jobs. `PUSH_MIN_WIDTH = 1100` decided
 * BOTH "may the rail reflow the page" and, by omission, "what happens when it
 * may not" — and the answer to the second was *overlay a 420px opaque panel
 * over live controls and inset nothing*. The comment defending it called that
 * "a temporary overlap"; the probe says it is permanent for any operator whose
 * stored preference is open and whose window is under 1100, which is every
 * 1024 laptop and every docked-then-undocked session.
 *
 * THE RULE NOW, and it is one rule with one law:
 *
 *   **The rail either sits BESIDE the cockpit or it covers the viewport
 *   whole. It never covers part of it.**
 *
 * Three modes fall out of that, and `railLayout` is the only thing that
 * decides which:
 *
 *   * `pill`  — closed. Nothing is covered, nothing is inset.
 *   * `push`  — docked beside the cockpit. The page is inset by EXACTLY the
 *               rail's width, so the content column ends where the rail begins.
 *   * `sheet` — the viewport is too narrow to hold both, so the rail takes all
 *               of it. Nothing is half-visible and half-clickable; Esc and the
 *               chevron still close it.
 *
 * THE NUMBERS, and where each one comes from — because two of the three are
 * measured and the third is a judgement, and saying which is which is the
 * point:
 *
 *   * `RAIL_W = 420` — INHERITED, unchanged. The shipped rail width. Every
 *     viewport that pushes today (1100 and up) keeps exactly the geometry it
 *     has now; this module widens the set that pushes, it does not re-tune the
 *     ones that already did.
 *   * `CONTENT_MIN = 640` — MEASURED (2026-08-23, CDP sweep of six Studio
 *     pages at seventeen widths with the rail closed, comparing
 *     `documentElement.scrollWidth` against `clientWidth`). Every Studio page
 *     — Monitor, the CEO desk, the floor, Allocate, Risk, Lab — renders with
 *     no horizontal overflow down to 640px. The first page to overflow is the
 *     desk floor at 600px, by 959px. So 640 is the narrowest content column
 *     this app is known to render whole, not a round number.
 *   * `RAIL_MIN = 320` — A JUDGEMENT, and named as one. The measurement that
 *     would have set it FAILED to: the rail's own content is a fluid text
 *     column and does not overflow at any width down to 200px (same sweep,
 *     forcing the aside's width). So there is no measured floor to read, and
 *     320 is a decision: below the narrowest viewport this app supports at all,
 *     a docked column is not a column. Whoever disagrees should move this
 *     number and read `railLayout.test.ts`, which pins the consequences.
 *
 * `SHEET_BELOW` is DERIVED from those two rather than written a third time.
 * Care cannot hold three constants in step; construction can.
 */

/** The docked rail's preferred width. Unchanged from the shipped value. */
export const RAIL_W = 420;

/**
 * The narrowest content column every Studio page renders whole.
 *
 * MEASURED, not chosen — see the module header. Reproduce with:
 *   node scratchpad/cdp_minwidth.js   (sweeps six pages × seventeen widths)
 */
export const CONTENT_MIN = 640;

/** The narrowest a DOCKED rail may be before it stops being a column. A
 *  judgement (the overflow measurement returned no floor), see the header. */
export const RAIL_MIN = 320;

/** Below this the two cannot both have their minimum, so the rail takes the
 *  screen. DERIVED — never write this number down anywhere else. */
export const SHEET_BELOW = RAIL_MIN + CONTENT_MIN;

export type RailMode = "pill" | "push" | "sheet";

export interface RailLayout {
  mode: RailMode;
  /** CSS width for the rail element, in px. 0 when it is not rendered. */
  railWidth: number;
  /** `padding-right` for the page, in px. In `push` this IS `railWidth` — one
   *  quantity, not two that must be kept in agreement. */
  contentInset: number;
  /** True only when the rail occupies the whole viewport. Drives the dialog
   *  semantics: covered content must not be offered to a screen reader as
   *  though it were still reachable. */
  covers: boolean;
}

/**
 * Where the rail goes at this viewport width.
 *
 * `viewportWidth` must be the LAYOUT viewport (`documentElement.clientWidth`),
 * not `window.innerWidth`. They differ by the classic scrollbar — 1024 against
 * 1009 on the probe machine — and a fixed element anchored to `right: 0` sits
 * at the LAYOUT viewport's edge. The old code compared `innerWidth` against
 * the breakpoint and so decided the layout with a number 15px larger than the
 * space it was deciding about.
 *
 * An unreadable width returns `pill`, deliberately. Docking against a width we
 * could not measure is exactly how content ends up under something that eats
 * its clicks; the pill covers nothing and is always reachable. Absence is not
 * "wide".
 */
export function railLayout(viewportWidth: number, open: boolean): RailLayout {
  if (!open) return { mode: "pill", railWidth: 0, contentInset: 0, covers: false };
  if (!Number.isFinite(viewportWidth) || viewportWidth <= 0) {
    return { mode: "pill", railWidth: 0, contentInset: 0, covers: false };
  }
  const w = Math.floor(viewportWidth);
  if (w < SHEET_BELOW) {
    return { mode: "sheet", railWidth: w, contentInset: 0, covers: true };
  }
  // The cockpit keeps its measured minimum first; the rail takes what is left,
  // up to its preferred width. So a 1024 laptop docks a 369px rail beside a
  // 640px cockpit instead of covering 420px of live controls.
  const railWidth = Math.min(RAIL_W, w - CONTENT_MIN);
  return { mode: "push", railWidth, contentInset: railWidth, covers: false };
}

/**
 * The `padding-right` the page must carry, as a CSS value.
 *
 * A one-line function rather than an expression inside the effect, and the
 * reason is measured: the mutation pass restored the shipped defect — writing
 * `""` unconditionally, which is an inset of zero, which IS the 1,923-element
 * clip — and every test still passed, because the expression lived in a React
 * effect that no runner here can execute. There is no DOM test runner in this
 * repo, so a decision that only exists inside a component is a decision
 * nothing can check. Moving it out is how it gets checked.
 */
export function bodyPaddingRight(layout: RailLayout): string {
  return layout.contentInset > 0 ? `${layout.contentInset}px` : "";
}

/**
 * Should the rail be open when the operator has never said?
 *
 * DERIVED from the layout law rather than from a second breakpoint constant.
 * The old code carried `PUSH_MIN_WIDTH` for this and the reflow both, and the
 * two questions drifted apart the moment the reflow gained a third mode. The
 * question is the same one either way: can this viewport hold the rail BESIDE
 * the cockpit? If it cannot, a docked default would be a full-screen chat
 * panel over a cockpit the operator has not asked anything about yet.
 */
export function openByDefault(viewportWidth: number): boolean {
  return railLayout(viewportWidth, true).mode === "push";
}
