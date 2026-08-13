"use client";

import React, { useEffect, useMemo, useRef } from "react";
import { useChartColors } from "../chartColors";
import { KT } from "../theme";
import type { AdvancedRiskView } from "@/lib/fund_api";

/**
 * Expected Shortfall as a 3D surface over correlation and holding horizon.
 *
 * The third dimension carries information here rather than decoration. A single
 * ES number answers one point on this surface; the surface shows the two things
 * that actually move it for a small book:
 *
 *   x — what happens when these names stop being different (correlation -> 1)
 *   y — what happens when you are still holding in a month
 *
 * The vertical marker is where the book sits *today*. The distance between that
 * marker and the right-hand edge is the diversification benefit currently being
 * assumed — and the wall the surface climbs toward rho = 1 is what a crisis
 * does to it. That gap is the whole point of drawing this.
 *
 * Plotly is loaded dynamically: it is a large bundle and nothing else in the
 * Studio needs it, so it must not sit in the main chunk.
 */
export function LossSurface({ surface }: { surface: AdvancedRiskView["loss_surface"] }) {
  const ref = useRef<HTMLDivElement>(null);
  const c = useChartColors();

  const data = useMemo(() => {
    if (!surface?.measurable) return null;
    const x = surface.x_correlation ?? [];
    const y = surface.y_horizon_days ?? [];
    const z = surface.z_loss_usd ?? [];
    if (!x.length || !y.length || !z.length) return null;
    return { x, y, z };
  }, [surface]);

  useEffect(() => {
    if (!data || !ref.current) return;
    let cancelled = false;
    const el = ref.current;

    (async () => {
      const Plotly = (await import("plotly.js-dist-min")).default as any;
      if (cancelled || !el) return;

      const traces: any[] = [
        {
          type: "surface",
          x: data.x,
          y: data.y,
          z: data.z,
          colorscale: [
            [0, c.accent],
            [0.5, c.warn],
            [1, c.down],
          ],
          opacity: 0.92,
          showscale: true,
          colorbar: {
            title: { text: "ES ($)", font: { color: c.textDim, size: 10 } },
            tickfont: { color: c.textMuted, size: 9 },
            outlinewidth: 0,
            thickness: 10,
            len: 0.6,
          },
          contours: {
            z: { show: true, usecolormap: true, project: { z: true }, width: 1 },
          },
          hovertemplate:
            "correlation %{x:.2f}<br>horizon %{y} days<br>" +
            "<b>expected shortfall $%{z:,.0f}</b><extra></extra>",
        },
      ];

      // Where the book actually is today — without this the surface is an
      // abstraction rather than a statement about this fund.
      const rho = surface.measured_correlation;
      if (rho != null) {
        const zs = data.z.flat();
        traces.push({
          type: "scatter3d",
          mode: "lines",
          x: [rho, rho],
          y: [data.y[0], data.y[data.y.length - 1]],
          z: [Math.min(...zs), Math.max(...zs)],
          line: { color: c.text, width: 5, dash: "dash" },
          hovertemplate: `measured correlation ${rho.toFixed(2)}<extra></extra>`,
          showlegend: false,
        });
      }

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
            xaxis: {
              title: { text: "avg correlation", font: { size: 10, color: c.textMuted } },
              gridcolor: c.grid, zerolinecolor: c.axis, color: c.textMuted,
              backgroundcolor: "rgba(0,0,0,0)", showbackground: false,
            },
            yaxis: {
              title: { text: "horizon (days)", font: { size: 10, color: c.textMuted } },
              gridcolor: c.grid, zerolinecolor: c.axis, color: c.textMuted,
              backgroundcolor: "rgba(0,0,0,0)", showbackground: false,
            },
            zaxis: {
              title: { text: "loss ($)", font: { size: 10, color: c.textMuted } },
              gridcolor: c.grid, zerolinecolor: c.axis, color: c.textMuted,
              backgroundcolor: "rgba(0,0,0,0)", showbackground: false,
            },
            camera: { eye: { x: 1.7, y: -1.5, z: 0.9 } },
            aspectratio: { x: 1.1, y: 1, z: 0.7 },
          },
        },
        { displayModeBar: false, responsive: true },
      );
    })();

    return () => {
      cancelled = true;
      import("plotly.js-dist-min").then((m) => {
        try {
          (m.default as any).purge(el);
        } catch {
          /* element already gone */
        }
      });
    };
  }, [data, c, surface?.measured_correlation]);

  if (!surface?.measurable) {
    return (
      <div className={`px-5 py-10 text-sm ${KT.muted}`}>
        Loss surface unavailable — {surface?.reason ?? "no measurable book"}.
      </div>
    );
  }

  return (
    <div>
      <div ref={ref} className="h-[420px] w-full" />
      <div className={`mt-2 space-y-1 px-1 text-[11px] ${KT.muted}`}>
        {surface.measured_correlation != null && (
          <p>
            Dashed line: this book&apos;s measured average correlation of{" "}
            <span className={KT.accent}>{surface.measured_correlation.toFixed(2)}</span>. The
            climb to the right is what a crisis does when names stop being different.
          </p>
        )}
        {(surface.caveats ?? []).map((c, i) => (
          <p key={i}>· {c}</p>
        ))}
      </div>
    </div>
  );
}
