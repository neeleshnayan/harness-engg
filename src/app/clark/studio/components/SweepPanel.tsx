"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import { Grid3x3, Loader2 } from "lucide-react";
import { KT } from "../theme";
import { fundApi } from "@/lib/fund_api";

/**
 * The question a single backtest cannot answer.
 *
 * One good parameter set proves nothing. If the winner sits alone among losers
 * it is a fit to this particular history; if its neighbours also work, there
 * may be something there. A single number cannot tell those apart, and the
 * single number an operator sees is always the winner — which is exactly the
 * one that flatters a fit.
 *
 * So the whole neighbourhood is shown, and the best cell is reported BESIDE
 * the median rather than alone. With two parameters the grid is drawn as a
 * matrix, because "island or plateau" is a shape, and a shape should be looked
 * at rather than inferred from a column of numbers.
 */

export interface SweepPoint {
  parameters: Record<string, string>;
  state?: string;
  error?: string | null;
  total_return_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  psr_pct?: number | null;
  total_orders?: number | null;
}

export interface SweepSummary {
  scored?: number;
  failed?: number;
  best?: SweepPoint;
  best_return_pct?: number;
  median_return_pct?: number;
  worst_return_pct?: number;
  positive_share?: number;
  best_minus_median_pct?: number;
}

interface Sweep {
  sweep_id: string;
  state: string;
  total: number;
  completed: number;
  error?: string | null;
  points: SweepPoint[];
  summary?: SweepSummary;
}

const f2 = (n?: number | null) => (n == null ? "—" : n.toFixed(2));

export function SweepPanel({ algorithm, disabled }: { algorithm: string; disabled?: boolean }) {
  const [rows, setRows] = useState([
    { name: "fast", values: "10, 20, 40" },
    { name: "slow", values: "60, 120" },
  ]);
  const [sweep, setSweep] = useState<Sweep | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const points = sweep?.points ?? [];
  const names = rows.map((r) => r.name.trim()).filter(Boolean);

  const combos = rows.reduce((acc, r) => {
    const n = r.values.split(",").map((v) => v.trim()).filter(Boolean).length;
    return r.name.trim() && n ? acc * n : acc;
  }, 1);

  const run = useCallback(async () => {
    setErr(null);
    setBusy(true);
    setSweep(null);
    try {
      const grid: Record<string, string[]> = {};
      for (const r of rows) {
        const name = r.name.trim();
        const values = r.values.split(",").map((v) => v.trim()).filter(Boolean);
        if (name && values.length) grid[name] = values;
      }
      const sub = (await fundApi.post("/api/v1/fund/lean/sweeps", { algorithm, grid })).data;
      pollRef.current = setInterval(async () => {
        try {
          const s = (await fundApi.get(`/api/v1/fund/lean/sweeps/${sub.sweep_id}`)).data as Sweep;
          setSweep(s);
          if (s.state === "done" || s.state === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setBusy(false);
          }
        } catch { /* keep polling */ }
      }, 3000);
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setErr(detail ?? String(e));
      setBusy(false);
    }
  }, [algorithm, rows]);

  const summary = sweep?.summary;
  const done = points.filter((p) => p.state === "done" && p.total_return_pct != null);
  const returns = done.map((p) => p.total_return_pct as number);
  const lo = returns.length ? Math.min(...returns) : 0;
  const hi = returns.length ? Math.max(...returns) : 1;

  /** Shade by rank within the grid — the SHAPE is the message, not the hue. */
  const shade = (v?: number | null) => {
    if (v == null || hi === lo) return "var(--kt-inset)";
    const t = (v - lo) / (hi - lo);
    return `color-mix(in srgb, var(--kt-accent) ${Math.round(t * 55)}%, var(--kt-inset))`;
  };

  const twoD = names.length === 2 && done.length > 0;
  const xs = twoD ? [...new Set(points.map((p) => p.parameters[names[0]]))] : [];
  const ys = twoD ? [...new Set(points.map((p) => p.parameters[names[1]]))] : [];
  const at = (x: string, y: string) =>
    points.find((p) => p.parameters[names[0]] === x && p.parameters[names[1]] === y);

  return (
    <div className={`mt-4 ${KT.panel}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--kt-border)] px-5 py-3">
        <div className="min-w-0">
          <span className={KT.label}>Parameter sweep</span>
          <div className={`mt-1 text-[11px] ${KT.muted}`}>
            One good setting proves nothing — the neighbourhood is the evidence.
            Read the values with <code>self.get_parameter(&quot;fast&quot;)</code> in your
            algorithm.
          </div>
        </div>
        <button onClick={run} disabled={busy || disabled || combos < 2}
                className={`ml-auto flex h-9 items-center gap-1.5 ${KT.btn} disabled:opacity-40`}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Grid3x3 size={14} />}
          {busy && sweep ? `Running · ${sweep.completed}/${sweep.total}` : `Sweep ${combos} runs`}
        </button>
      </div>

      <div className="flex flex-wrap gap-4 px-5 py-3">
        {rows.map((r, i) => (
          <div key={i} className="flex items-center gap-2">
            <input
              value={r.name}
              onChange={(e) => setRows((v) => v.map((x, j) => j === i ? { ...x, name: e.target.value } : x))}
              className={`w-28 ${KT.input}`} placeholder="name" aria-label="Parameter name"
            />
            <input
              value={r.values}
              onChange={(e) => setRows((v) => v.map((x, j) => j === i ? { ...x, values: e.target.value } : x))}
              className={`w-52 ${KT.input}`} placeholder="10, 20, 40" aria-label="Values to try"
            />
          </div>
        ))}
        <p className={`w-full text-[10px] ${KT.muted}`}>
          Each point is a full engine run of roughly ten seconds, so the grid
          costs minutes. Leave a name blank to drop that parameter.
        </p>
      </div>

      {err && <div className={`px-5 pb-3 text-sm ${KT.down}`}>{err}</div>}
      {sweep?.state === "failed" && (
        <div className={`px-5 pb-3 text-sm ${KT.down}`}>Sweep failed: {sweep.error}</div>
      )}

      {summary && (summary.scored ?? 0) > 0 && (
        <div className="border-t border-[var(--kt-border)] px-5 py-3">
          <div className="flex flex-wrap gap-x-8 gap-y-1 font-mono text-[13px] tabular-nums">
            <span>best <span className={KT.up}>{f2(summary.best_return_pct)}%</span></span>
            <span className={KT.muted}>median {f2(summary.median_return_pct)}%</span>
            <span className={KT.muted}>worst {f2(summary.worst_return_pct)}%</span>
            <span className={KT.muted}>
              {Math.round((summary.positive_share ?? 0) * 100)}% of the grid positive
            </span>
          </div>
          <p className={`mt-2 text-[11px] ${
            (summary.best_minus_median_pct ?? 0) > Math.abs(summary.median_return_pct ?? 0)
              ? KT.down : KT.muted
          }`}>
            {(summary.best_minus_median_pct ?? 0) > Math.abs(summary.median_return_pct ?? 0)
              ? `The best setting beats the median by ${f2(summary.best_minus_median_pct)}% — it stands alone, which is what a fit to this history looks like. Treat the median as the honest expectation.`
              : `The best setting is ${f2(summary.best_minus_median_pct)}% above the median — the neighbourhood broadly agrees with it, which is what a real effect looks like.`}
          </p>
          {summary.best?.parameters && (
            <p className={`mt-1 text-[10px] ${KT.muted}`}>
              best at {Object.entries(summary.best.parameters).map(([k, v]) => `${k}=${v}`).join(", ")}
              {summary.best.psr_pct != null && ` · confidence the edge is real ${f2(summary.best.psr_pct)}%`}
            </p>
          )}
        </div>
      )}

      {twoD && (
        <div className="overflow-x-auto border-t border-[var(--kt-border)] px-5 py-4">
          <table className="text-[11px]">
            <thead>
              <tr>
                <th className={`px-2 py-1 text-left font-normal ${KT.label}`}>
                  {names[1]} \ {names[0]}
                </th>
                {xs.map((x) => (
                  <th key={x} className={`px-3 py-1 text-right font-normal ${KT.label}`}>{x}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ys.map((y) => (
                <tr key={y}>
                  <td className={`px-2 py-1 ${KT.label}`}>{y}</td>
                  {xs.map((x) => {
                    const p = at(x, y);
                    const v = p?.total_return_pct;
                    return (
                      <td key={x} className="px-1 py-1">
                        <div
                          className="min-w-[74px] rounded-md px-2 py-1.5 text-right font-mono tabular-nums"
                          style={{ background: shade(v) }}
                          title={p ? `${names[0]}=${x}, ${names[1]}=${y} · sharpe ${f2(p.sharpe)} · PSR ${f2(p.psr_pct)}%` : undefined}
                        >
                          {p?.state === "failed" ? "—" : v == null ? "·" : `${v.toFixed(1)}%`}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className={`mt-2 text-[10px] ${KT.muted}`}>
            Total return per cell. A single bright cell among dull ones is a
            fit; a bright region is a plateau. Hover for Sharpe and confidence.
          </p>
        </div>
      )}

      {!twoD && done.length > 0 && (
        <div className="border-t border-[var(--kt-border)] px-5 py-3">
          <table className="w-full text-[11px]">
            <thead>
              <tr className={KT.label}>
                <th className="py-1 text-left font-normal">Parameters</th>
                <th className="py-1 text-right font-normal">Return</th>
                <th className="py-1 text-right font-normal">Sharpe</th>
                <th className="py-1 text-right font-normal">Confidence</th>
                <th className="py-1 text-right font-normal">Fills</th>
              </tr>
            </thead>
            <tbody>
              {points.map((p, i) => (
                <tr key={i} className="border-t border-[var(--kt-border)]">
                  <td className="py-1">
                    {Object.entries(p.parameters).map(([k, v]) => `${k}=${v}`).join("  ")}
                  </td>
                  <td className={`py-1 text-right font-mono tabular-nums ${(p.total_return_pct ?? 0) >= 0 ? KT.up : KT.down}`}>
                    {p.state === "failed" ? "failed" : `${f2(p.total_return_pct)}%`}
                  </td>
                  <td className="py-1 text-right font-mono tabular-nums">{f2(p.sharpe)}</td>
                  <td className={`py-1 text-right font-mono tabular-nums ${KT.muted}`}>
                    {p.psr_pct == null ? "—" : `${f2(p.psr_pct)}%`}
                  </td>
                  <td className={`py-1 text-right font-mono tabular-nums ${KT.muted}`}>
                    {p.total_orders ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
