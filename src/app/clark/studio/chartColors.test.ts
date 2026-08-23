import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

/**
 * THE CHART PALETTE MUST BE THE PAGE'S PALETTE.
 *
 * THE DEFECT THIS PINS, measured 2026-08-23 and fixed in the same commit.
 * `chartColors.ts` exists because charting libraries PARSE colour strings in
 * JavaScript, where `var(--kt-accent)` throws — so it holds literal hexes, and
 * its docstring said *"Values MUST mirror `studio-theme.css`"*. Nothing checked
 * it, and every dark-theme value had drifted:
 *
 *   | token   | chartColors.ts | studio-theme.css |
 *   |---------|----------------|------------------|
 *   | accent  | #34d399        | #79a98c          |
 *   | down    | #fb7185        | #ce7681          |
 *   | warn    | #fbbf24        | #c9a227          |
 *   | bg      | #0a0a0b        | #0b0c0e          |
 *   | text    | #f4f4f5        | #c9ccd1          |
 *
 * Every chart in the Studio was drawn in a brighter palette than the page it
 * sat on — theme.ts's own header says the CSS-variable split exists so "the
 * palettes [do not] drift apart the way they did before", and they had.
 *
 * A NOTE ON WHY THIS IS THE RIGHT SHAPE OF TEST. The house rule is that to
 * prove a value is READ rather than COPIED you MOVE it, and an assertion that
 * two values are equal cannot distinguish a hardcoded duplicate that happens
 * to agree today. Here the value CANNOT be read at runtime — that is the whole
 * reason the module exists. So the next-strongest thing is done instead: the
 * test PARSES `studio-theme.css` and derives the expectation from it, so
 * editing the stylesheet alone turns this file red. The duplicate still
 * exists; it can no longer drift in silence.
 */

const HERE = dirname(fileURLToPath(import.meta.url));
const CSS = readFileSync(join(HERE, "studio-theme.css"), "utf8");
const TS = readFileSync(join(HERE, "chartColors.ts"), "utf8");

/** Every `--kt-*` declaration inside one `[data-kt-theme="X"]` block. */
function themeVars(theme: "dark" | "light"): Record<string, string> {
  const start = CSS.indexOf(`[data-kt-theme="${theme}"]`);
  assert.ok(start > 0, `no ${theme} block in studio-theme.css`);
  const open = CSS.indexOf("{", start);
  const end = CSS.indexOf("\n}", open);
  assert.ok(end > open, `unterminated ${theme} block`);
  const body = CSS.slice(open, end);
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/--(kt-[a-z-]+)\s*:\s*([^;]+);/g)) {
    out[m[1]] = m[2].trim();
  }
  return out;
}

/** The literal object for one theme, as written in `chartColors.ts`. */
function chartLiterals(name: "DARK" | "LIGHT"): Record<string, string> {
  const start = TS.indexOf(`const ${name}: ChartColors = {`);
  assert.ok(start > 0, `no ${name} literal in chartColors.ts`);
  const end = TS.indexOf("\n};", start);
  const body = TS.slice(start, end);
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/^\s*([a-zA-Z]+):\s*"(#[0-9a-fA-F]{6})"/gm)) {
    out[m[1]] = m[2].toLowerCase();
  }
  return out;
}

/** `rgb(34 37 43 / 1)` → `#22252b`. Only the opaque form; anything else is a
 *  translucent token that has no business being a chart's grid colour. */
function rgbToHex(v: string): string | null {
  const m = /^rgb\(\s*(\d+)\s+(\d+)\s+(\d+)\s*\/\s*1\s*\)$/.exec(v.trim());
  if (!m) return null;
  return `#${[1, 2, 3].map((i) => Number(m[i]).toString(16).padStart(2, "0")).join("")}`;
}

/** chartColors field → the stylesheet token it must equal. */
const MAP: Record<string, string> = {
  bg: "kt-bg",
  surface: "kt-surface",
  grid: "kt-border",
  axis: "kt-border-strong",
  text: "kt-text",
  textDim: "kt-text-dim",
  textMuted: "kt-text-muted",
  accent: "kt-accent",
  accentSoft: "kt-accent-soft",
  up: "kt-up",
  down: "kt-down",
  warn: "kt-warn",
};

test("the parsers actually parse something — the instrument's null test", () => {
  /* Every assertion below is "these two agree", and two empty objects agree
   * perfectly. Without this, a renamed block or a reformatted literal would
   * turn the whole file green while checking nothing. */
  const dark = themeVars("dark");
  assert.ok(Object.keys(dark).length >= 15, `parsed ${Object.keys(dark).length} vars`);
  assert.equal(Object.keys(chartLiterals("DARK")).length, 12);
  assert.equal(Object.keys(chartLiterals("LIGHT")).length, 12);
  assert.equal(rgbToHex("rgb(34 37 43 / 1)"), "#22252b");
  assert.equal(rgbToHex("rgb(121 169 140 / 0.10)"), null,
    "a translucent token must not be silently flattened into a chart colour");
});

for (const [theme, literal] of [["dark", "DARK"], ["light", "LIGHT"]] as const) {
  test(`every ${theme} chart colour is the stylesheet's own value`, () => {
    const vars = themeVars(theme);
    const lits = chartLiterals(literal);
    for (const [field, token] of Object.entries(MAP)) {
      const raw = vars[token];
      assert.ok(raw, `studio-theme.css has no --${token} in the ${theme} block`);
      const want = raw.startsWith("#") ? raw.toLowerCase() : rgbToHex(raw);
      assert.ok(want, `--${token} is ${raw}, which is not an opaque colour`);
      assert.equal(lits[field], want,
        `chartColors.${literal}.${field} is ${lits[field]} but --${token} is `
        + `${want} — the chart palette has drifted from the page's. Change the `
        + "stylesheet and this test tells you which literal to follow.");
    }
  });
}

test("every series colour is a token the Studio already uses", () => {
  /* The categorical ramp has no semantic counterpart, so it cannot be mapped
   * field-for-field. What it CAN be held to is membership: a donut slice must
   * not introduce a hue the rest of the Studio has never used, which is how a
   * third accent arrives without anyone deciding on one. */
  for (const [theme, literal] of [["dark", "DARK"], ["light", "LIGHT"]] as const) {
    const vars = themeVars(theme);
    const known = new Set(Object.values(vars)
      .map((v) => (v.startsWith("#") ? v.toLowerCase() : rgbToHex(v)))
      .filter((v): v is string => v !== null));
    const start = TS.indexOf(`const ${literal}: ChartColors = {`);
    const body = TS.slice(start, TS.indexOf("\n};", start));
    const m = /series:\s*\[([^\]]+)\]/.exec(body);
    assert.ok(m, `${literal} has no series ramp`);
    const series = [...m[1].matchAll(/"(#[0-9a-fA-F]{6})"/g)].map((x) => x[1].toLowerCase());
    assert.equal(series.length, 6);
    for (const c of series) {
      assert.ok(known.has(c),
        `${theme} series colour ${c} is in no --kt-* token; a chart must not `
        + "introduce a hue the Studio has never used");
    }
    assert.equal(new Set(series).size, 6, "six slices need six distinguishable colours");
  }
});

test("the module still says WHY it holds literals at all", () => {
  /* Traceability, separate from behaviour: the exemption in
   * `designAuthority.test.ts` is only legitimate while this reason holds. */
  assert.match(TS, /charting libraries/i);
  assert.match(TS, /Cannot parse color/);
  assert.match(TS, /chartColors\.test\.ts/,
    "the module must point at the test that keeps its promise, or the promise "
    + "is a comment again");
});
