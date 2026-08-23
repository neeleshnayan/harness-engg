"use client";

import { useMemo } from "react";
import { useKtTheme } from "./ThemeToggle";

/**
 * Literal colors for charting libraries.
 *
 * DOM elements style themselves from KT tokens (CSS variables) and need nothing
 * here. Charting libraries are different: lightweight-charts and parts of
 * Recharts *parse* color strings in JavaScript, where `var(--kt-accent)` is not
 * a color — it throws "Cannot parse color". So charts read literal hexes from
 * this hook instead.
 *
 * Values MUST mirror `studio-theme.css`, and `chartColors.test.ts` PARSES that
 * file and asserts it, token by token, in both themes. That test exists because
 * the sentence above shipped as a comment and nothing checked it: measured
 * 2026-08-23, EVERY dark-theme value here had drifted from the stylesheet —
 * `accent` was `#34d399` against the theme's `#79a98c`, `down` `#fb7185`
 * against `#ce7681`, `bg` `#0a0a0b` against `#0b0c0e`. Every chart in the
 * Studio was being drawn in a brighter palette than the page it sat on, which
 * is exactly the drift theme.ts's own header says the CSS-variable split
 * exists to prevent. A rule kept by a comment is not kept.
 *
 * `series` is the one field with no counterpart in the stylesheet — a
 * categorical ramp has no semantic token — so it is literal by necessity and
 * the test says so rather than pretending otherwise.
 */
export interface ChartColors {
  bg: string;
  surface: string;
  grid: string;
  axis: string;
  text: string;
  textDim: string;
  textMuted: string;
  accent: string;
  accentSoft: string;
  up: string;
  down: string;
  warn: string;
  /** Categorical series palette (allocation donut, multi-series charts). */
  series: string[];
}

const DARK: ChartColors = {
  bg: "#0b0c0e",            // --kt-bg
  surface: "#14161a",       // --kt-surface
  grid: "#22252b",          // --kt-border, as hex
  axis: "#343941",          // --kt-border-strong, as hex
  text: "#c9ccd1",          // --kt-text
  textDim: "#9ba0a8",       // --kt-text-dim
  textMuted: "#6c727a",     // --kt-text-muted
  accent: "#79a98c",        // --kt-accent
  accentSoft: "#9cc2ac",    // --kt-accent-soft
  up: "#79a98c",            // --kt-up
  down: "#ce7681",          // --kt-down
  warn: "#c9a227",          // --kt-warn
  // The categorical ramp: accent, accent-soft, up, the agent hue, its soft
  // form, and warn. Every entry is a token from the stylesheet, so a donut
  // slice cannot be a colour the rest of the Studio has never used.
  series: ["#79a98c", "#9cc2ac", "#a5b4d4", "#c3cee4", "#c9a227", "#ce7681"],
};

const LIGHT: ChartColors = {
  bg: "#fafaf8",            // --kt-bg
  surface: "#ffffff",       // --kt-surface
  grid: "#e3e1db",          // --kt-border, as hex
  axis: "#cfccc4",          // --kt-border-strong, as hex
  text: "#33373d",          // --kt-text
  textDim: "#565b63",       // --kt-text-dim
  textMuted: "#8a8f97",     // --kt-text-muted
  accent: "#2f6b48",        // --kt-accent
  accentSoft: "#3f7a57",    // --kt-accent-soft
  up: "#2f6b48",            // --kt-up
  down: "#9c3742",          // --kt-down
  warn: "#8a6410",          // --kt-warn
  series: ["#2f6b48", "#3f7a57", "#4a5878", "#5b6b8f", "#8a6410", "#9c3742"],
};

export function useChartColors(): ChartColors {
  const { theme } = useKtTheme();
  return useMemo(() => (theme === "light" ? LIGHT : DARK), [theme]);
}
