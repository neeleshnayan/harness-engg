"use client";

import React, { useEffect, useMemo, useRef } from "react";
import { useChartColors } from "../chartColors";
import { KT } from "../theme";
import type { FactorMap } from "@/lib/fund_api";

/**
 * The book's holdings placed in the space of its own statistical factors.
 *
 * The correlation matrix says which PAIRS move together. This says something a
 * matrix cannot: which holdings are doing the *same thing*, as a group. Names
 * that cluster load on the same latent factor and are one bet however different
 * their tickers, sectors or parent strategies look — and a cluster is visible at
 * a glance where it is invisible in 81 pairwise numbers.
 *
 * Three dimensions are earned here: the first three components are genuinely
 * three independent axes of variation, and a 2D projection would hide whichever
 * one it dropped.
 *
 * Marker size is portfolio weight, so a large marker far from the origin is a
 * big position loading hard on a common factor — the thing you most want to
 * notice and the thing a weight table cannot show you.
 */
export function FactorMap3D({ map }: { map?: FactorMap }) {
  const ref = useRef<HTMLDivElement>(null);
  const c = useChartColors();

  const pts = useMemo(() => {
    if (!map?.measurable || !map.points?.length) return null;
    return map.points.filter((p) => (p.loadings?.length ?? 0) >= 3);
  }, [map]);

  useEffect(() => {
    if (!pts?.length || !ref.current) return;
    let cancelled = false;
    const el = ref.current;

    (async () => {
      const Plotly = (await import("plotly.js-dist-min")).default;
      if (cancelled || !el) return;

      const x = pts.map((p) => p.loadings[0]);
      const y = pts.map((p) => p.loadings[1]);
      const z = pts.map((p) => p.loadings[2]);
      const w = pts.map((p) => p.weight_pct || 1);
      const maxW = Math.max(...w, 1);

      const traces: unknown[] = [
        {
          type: "scatter3d",
          mode: "markers+text",
          x, y, z,
          text: pts.map((p) => p.symbol),
          textposition: "top center",
          textfont: { color: c.textDim, size: 10 },
          marker: {
            size: w.map((v) => 8 + (v / maxW) * 18),
            color: w,
            colorscale: [[0, c.accentSoft], [1, c.accent]],
            opacity: 0.9,
            line: { color: c.surface, width: 1 },
          },
          hovertemplate:
            "<b>%{text}</b><br>weight %{marker.color:.1f}%<br>" +
            "PC1 %{x:.2f} · PC2 %{y:.2f} · PC3 %{z:.2f}<extra></extra>",
          showlegend: false,
        },
        // Stems to the PC1/PC2 floor make depth readable; without them a 3D
        // scatter is genuinely ambiguous about where a point sits.
        ...pts.map((p) => ({
          type: "scatter3d",
          mode: "lines",
          x: [p.loadings[0], p.loadings[0]],
          y: [p.loadings[1], p.loadings[1]],
          z: [Math.min(...z, 0), p.loadings[2]],
          line: { color: c.grid, width: 1 },
          hoverinfo: "skip",
          showlegend: false,
        })),
      ];

      const axis = (title: string, pctVar?: number) => ({
        title: {
          text: pctVar != null ? `${title} (${(pctVar * 100).toFixed(0)}%)` : title,
          font: { size: 10, color: c.textMuted },
        },
        gridcolor: c.grid,
        zerolinecolor: c.axis,
        color: c.textMuted,
        backgroundcolor: "rgba(0,0,0,0)",
        showbackground: false,
      });

      await Plotly.newPlot(
        el,
        traces,
        {
          autosize: true,
          margin: { l: 0, r: 0, t: 0, b: 0 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
          font: { color: c.textDim, size: 10, family: "ui-monospace, monospace" },
          scene: {
            xaxis: axis("PC1", map?.explained_variance?.[0]),
            yaxis: axis("PC2", map?.explained_variance?.[1]),
            zaxis: axis("PC3", map?.explained_variance?.[2]),
            camera: { eye: { x: 1.6, y: 1.6, z: 1.1 } },
            aspectmode: "cube",
          },
        },
        { displayModeBar: false, responsive: true },
      );
    })();

    return () => {
      cancelled = true;
      import("plotly.js-dist-min").then((m) => {
        try {
          m.default.purge(el);
        } catch {
          /* element already gone */
        }
      });
    };
  }, [pts, c, map]);

  if (!map?.measurable) {
    return (
      <div className={`px-5 py-10 text-sm ${KT.muted}`}>
        Factor map unavailable — {map?.reason ?? "no measurable book"}.
      </div>
    );
  }

  return (
    <div>
      <div ref={ref} className="h-[420px] w-full" />
      <div className={`mt-2 space-y-1 px-1 text-[11px] ${KT.muted}`}>
        {(map.interpretation ?? []).map((line, i) => (
          <p key={i}>· {line}</p>
        ))}
      </div>
    </div>
  );
}
