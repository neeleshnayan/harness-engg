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
 * Values MUST mirror `studio-theme.css`. If you change a color there, change it
 * here too — these are the same palette expressed for a different consumer.
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
  bg: "#0a0a0b",
  surface: "#111113",
  grid: "#27272a",
  axis: "#3f3f46",
  text: "#f4f4f5",
  textDim: "#a1a1aa",
  textMuted: "#71717a",
  accent: "#34d399",
  accentSoft: "#6ee7b7",
  up: "#34d399",
  down: "#fb7185",
  warn: "#fbbf24",
  series: ["#34d399", "#10b981", "#6ee7b7", "#38bdf8", "#a78bfa", "#fbbf24"],
};

const LIGHT: ChartColors = {
  bg: "#fafaf9",
  surface: "#ffffff",
  grid: "#e7e5e4",
  axis: "#d6d3d1",
  text: "#27272a",
  textDim: "#57534e",
  textMuted: "#78716c",
  accent: "#047857",
  accentSoft: "#059669",
  up: "#047857",
  down: "#be123c",
  warn: "#b45309",
  series: ["#047857", "#059669", "#0d9488", "#0369a1", "#6d28d9", "#b45309"],
};

export function useChartColors(): ChartColors {
  const { theme } = useKtTheme();
  return useMemo(() => (theme === "light" ? LIGHT : DARK), [theme]);
}
