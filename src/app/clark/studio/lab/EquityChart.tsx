"use client";

import React, { useMemo } from "react";
import { useChartColors } from "../chartColors";
import { rebase } from "./candidateAnalytics";

/**
 * Strategy equity vs benchmark, with the drawdown underneath.
 *
 * Drawn as plain SVG rather than through a charting library: the only
 * interaction needed is reading it. Both curves share one axis because the
 * comparison is the point — a strategy that trails buy & hold should look like
 * it trails.
 *
 * REBASED HERE, at the boundary, since 2026-08-21. This component's own
 * docstring used to assert "the series are already normalised to 1.0" and its
 * axis formatter (`(v - 1) * 100`%) depended on it. They never were: LEAN
 * reports raw account equity (~100,000) and the benchmark in the underlying's
 * own price (~684). The axis printed "10346705%" and the benchmark was drawn
 * flat against the floor, so the comparison this chart exists to make was
 * invisible. Fixed in ONE place rather than at each call site, because both
 * callers — LeanResults and RunAnalytics — pass the engine's raw arrays and
 * a per-caller fix is a per-caller chance to forget.
 *
 * Passing an ALREADY rebased series is harmless: rebasing a series that starts
 * at 1.0 is the identity.
 */
export function EquityChart({
  equity,
  benchmark,
  dates,
  height = 260,
}: {
  equity: number[];
  benchmark?: number[];
  dates?: string[] | null;
  height?: number;
}) {
  const c = useChartColors();
  const W = 1000;
  const H = height;
  const PAD = { t: 10, r: 8, b: 18, l: 44 };

  const { path, benchPath, lo, hi, ddPath, maxDD } = useMemo(() => {
    const eq = rebase(equity);
    const bm = rebase(benchmark);
    if (!eq) {
      return { path: "", benchPath: "", lo: 0, hi: 1, ddPath: "", maxDD: 0 };
    }
    const series = bm ? [...eq, ...bm] : eq;
    const lo = Math.min(...series);
    const hi = Math.max(...series);
    const span = hi - lo || 1;

    const x = (i: number, n: number) =>
      PAD.l + (i / Math.max(1, n - 1)) * (W - PAD.l - PAD.r);
    const y = (v: number) =>
      PAD.t + (1 - (v - lo) / span) * (H - PAD.t - PAD.b);

    const toPath = (arr: number[]) =>
      arr.map((v, i) => `${i ? "L" : "M"}${x(i, arr.length).toFixed(1)},${y(v).toFixed(1)}`).join("");

    // Drawdown from running peak — the shape of the pain, not just its worst
    // value. Computed on the rebased series, which changes nothing: a drawdown
    // is a ratio and is invariant under scaling. Using `eq` anyway so no raw
    // array survives past the rebase, which is how the mismatch above started.
    let peak = eq[0];
    const dd = eq.map((v) => {
      peak = Math.max(peak, v);
      return v / peak - 1;
    });
    const worst = Math.min(...dd, 0);
    const ddH = 46;
    const ddY = (v: number) => H - PAD.b - ddH * (worst < 0 ? v / worst : 0);
    const ddPath =
      `M${x(0, dd.length).toFixed(1)},${(H - PAD.b).toFixed(1)}` +
      dd.map((v, i) => `L${x(i, dd.length).toFixed(1)},${ddY(v).toFixed(1)}`).join("") +
      `L${x(dd.length - 1, dd.length).toFixed(1)},${(H - PAD.b).toFixed(1)}Z`;

    return {
      path: toPath(eq),
      benchPath: bm ? toPath(bm) : "",
      lo, hi, ddPath, maxDD: worst,
    };
  }, [equity, benchmark, H]);

  if (!path) {
    // Keyed on the PATH, not on `equity.length`: a one-point series, or one
    // starting at zero, has a length and still cannot be drawn. Saying so beats
    // rendering an empty axis that reads as a flat result.
    return (
      <div className="flex items-center justify-center text-xs" style={{ height, color: c.textMuted }}>
        {equity?.length
          ? "The equity series cannot be plotted — fewer than two points, or a zero starting value."
          : "Run a backtest to see the equity curve"}
      </div>
    );
  }

  // The series are rebased to 1.0 above, so this reads as growth from the start
  // of the window. It is the ONE place the rebase is assumed, and the assumption
  // is now true by construction rather than by comment.
  const fmt = (v: number) => `${((v - 1) * 100).toFixed(0)}%`;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ height }} preserveAspectRatio="none">
      {[hi, (hi + lo) / 2, lo].map((v, i) => {
        const yy = PAD.t + (1 - (v - lo) / ((hi - lo) || 1)) * (H - PAD.t - PAD.b);
        return (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={yy} y2={yy} stroke={c.grid} strokeWidth={1} />
            <text x={4} y={yy + 3} fill={c.textMuted} fontSize={10} fontFamily="monospace">{fmt(v)}</text>
          </g>
        );
      })}

      {/* break-even — above it the strategy made money, below it lost */}
      {lo <= 1 && hi >= 1 && (
        <line
          x1={PAD.l} x2={W - PAD.r}
          y1={PAD.t + (1 - (1 - lo) / ((hi - lo) || 1)) * (H - PAD.t - PAD.b)}
          y2={PAD.t + (1 - (1 - lo) / ((hi - lo) || 1)) * (H - PAD.t - PAD.b)}
          stroke={c.axis} strokeDasharray="3 3" strokeWidth={1}
        />
      )}

      <path d={ddPath} fill={c.down} opacity={0.14} />
      {benchPath && <path d={benchPath} fill="none" stroke={c.textDim} strokeWidth={1.5} strokeDasharray="4 3" />}
      <path d={path} fill="none" stroke={c.accent} strokeWidth={2} />

      {dates?.length ? (
        <>
          <text x={PAD.l} y={H - 4} fill={c.textMuted} fontSize={10} fontFamily="monospace">{dates[0]}</text>
          <text x={W - PAD.r} y={H - 4} fill={c.textMuted} fontSize={10} fontFamily="monospace" textAnchor="end">
            {dates[dates.length - 1]}
          </text>
        </>
      ) : null}

      <text x={W - PAD.r} y={PAD.t + 10} fill={c.textMuted} fontSize={10} fontFamily="monospace" textAnchor="end">
        max drawdown {(maxDD * 100).toFixed(1)}%
      </text>
    </svg>
  );
}
