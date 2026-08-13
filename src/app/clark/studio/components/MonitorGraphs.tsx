"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Area, AreaChart, Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import { useChartColors } from "../chartColors";
import { KT } from "../theme";
import { IntradayNavSeries, RiskLimitsConfig, RiskMonitorResponse, fundApiClient } from "@/lib/fund_api";

/**
 * Three pictures, each answering a question a number cannot.
 *
 *   1. Session P&L    — is it winning right now, and how did it get there?
 *   2. Limit headroom — how close is the fund to a wall it must not hit?
 *   3. Book shape     — what is it actually holding, and what does a bad day cost?
 *
 * Deliberately not a dashboard of everything measurable. Headroom is the one
 * that earns its place: the fund publishes a dozen limits and a breach list, but
 * a breach list only ever says "fine" or "not fine" — it cannot show a limit
 * being approached, which is the only moment you can still act cheaply.
 *
 * Every bar is measured against a limit the spine actually holds. Nothing here
 * invents a threshold.
 */

const money = (n?: number | null, dp = 0) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: dp, maximumFractionDigits: dp })}`;
const pct = (n?: number | null, dp = 1) => (n == null ? "—" : `${Number(n).toFixed(dp)}%`);

type Gauge = {
  label: string;
  used: number;        // current value, in the same unit as `limit`
  limit: number;
  kind: "ceiling" | "floor";
  detail: string;
};

export function MonitorGraphs({ m }: { m: RiskMonitorResponse | null }) {
  const c = useChartColors();
  const [limits, setLimits] = useState<RiskLimitsConfig | null>(null);
  const [intraday, setIntraday] = useState<IntradayNavSeries | null>(null);

  const load = useCallback(async () => {
    const [l, i] = await Promise.all([
      fundApiClient.getRiskLimits().catch(() => null),
      fundApiClient.getIntradayNav(360).catch(() => null),
    ]);
    setLimits(l);
    setIntraday(i);
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 60000);
    return () => clearInterval(t);
  }, [load]);

  // --- 1. session P&L ------------------------------------------------------
  const trace = useMemo(() => {
    const s = intraday?.samples ?? [];
    return s.map((p) => ({ ts: p.ts.slice(11, 16), nav: p.total_nav_usd }));
  }, [intraday]);
  const change = intraday?.change_usd ?? null;
  const up = (change ?? 0) >= 0;

  // --- 2. limit headroom ---------------------------------------------------
  // Only limits with a measured current value. A gauge whose "used" side we
  // cannot observe would be a picture of an assumption.
  const gauges: Gauge[] = useMemo(() => {
    if (!m || !limits) return [];
    const g: Gauge[] = [];
    const biggest = (m.positions ?? []).reduce(
      (w, p) => (p.weight_pct > (w?.weight_pct ?? -1) ? p : w),
      null as null | { symbol: string; weight_pct: number },
    );

    if (m.drawdown?.limit_pct) {
      g.push({
        label: "Drawdown", used: m.drawdown.drawdown_pct ?? 0, limit: m.drawdown.limit_pct,
        kind: "ceiling", detail: `halt at ${pct(m.drawdown.limit_pct, 0)}`,
      });
    }
    if (biggest && limits.max_position_pct) {
      g.push({
        label: `Largest position (${biggest.symbol})`, used: biggest.weight_pct,
        limit: limits.max_position_pct * 100, kind: "ceiling",
        detail: `cap ${pct(limits.max_position_pct * 100, 0)}`,
      });
    }
    if (limits.min_cash_pct != null) {
      g.push({
        label: "Cash", used: m.cash_pct ?? 0, limit: limits.min_cash_pct * 100,
        kind: "floor", detail: `floor ${pct(limits.min_cash_pct * 100, 0)}`,
      });
    }
    return g;
  }, [m, limits]);

  // --- 3. book shape -------------------------------------------------------
  const book = useMemo(() => {
    const rows = [...(m?.positions ?? [])].sort((a, b) => b.weight_pct - a.weight_pct);
    return rows.map((p) => ({
      symbol: p.symbol,
      weight: p.weight_pct,
      value: p.value_usd,
      pnl: p.unrealized_pnl_pct,
      shock: p.shock_20_usd,
    }));
  }, [m]);
  const capPct = limits?.max_position_pct ? limits.max_position_pct * 100 : null;
  const totalShock = book.reduce((a, r) => a + (r.shock ?? 0), 0);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      {/* 1 — session P&L */}
      <div className={KT.panel}>
        <div className="flex items-baseline justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>Session P&amp;L</span>
          {change != null && (
            <span className={`font-mono text-[12px] tabular-nums ${up ? KT.up : KT.down}`}>
              {up ? "+" : "−"}{money(Math.abs(change), 2)}
            </span>
          )}
        </div>
        {trace.length < 3 ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            {trace.length === 0
              ? "No intraday samples yet — the spine samples once a minute."
              : `Only ${trace.length} samples so far; two points is a line, not a trace.`}
          </div>
        ) : (
          <div className="h-[132px] w-full px-1 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trace} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="monNav" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={up ? c.up : c.down} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={up ? c.up : c.down} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="ts" tick={{ fill: c.textMuted, fontSize: 9 }}
                       stroke={c.axis} tickLine={false} minTickGap={40} />
                <YAxis domain={["auto", "auto"]} hide />
                <Tooltip
                  contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`,
                                  borderRadius: 8, fontSize: 11, color: c.text }}
                  formatter={(v: number) => [money(v, 2), "NAV"]} />
                {trace[0] && (
                  <ReferenceLine y={trace[0].nav} stroke={c.textMuted} strokeDasharray="3 3" />
                )}
                <Area type="monotone" dataKey="nav" stroke={up ? c.up : c.down}
                      strokeWidth={1.75} fill="url(#monNav)" dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        <p className={`px-4 pb-2 text-[10px] ${KT.muted}`}>
          In-memory samples, lost on restart — telemetry, not the NAV record.
        </p>
      </div>

      {/* 2 — limit headroom */}
      <div className={KT.panel}>
        <div className="border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>Limit headroom</span>
        </div>
        {gauges.length === 0 ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            Limits unreadable — headroom unknown.
          </div>
        ) : (
          <div className="space-y-3 px-4 py-3">
            {gauges.map((g) => {
              // A ceiling is breached above the limit; a floor, below it.
              const ratio = g.kind === "ceiling"
                ? (g.limit ? g.used / g.limit : 0)
                : (g.used ? g.limit / g.used : 2);
              const breached = g.kind === "ceiling" ? g.used > g.limit : g.used < g.limit;
              const near = !breached && ratio > 0.75;
              const fill = breached ? c.down : near ? c.warn : c.up;
              return (
                <div key={g.label}>
                  <div className="flex items-baseline justify-between text-[11px]">
                    <span className={breached ? KT.down : ""}>{g.label}</span>
                    <span className={`font-mono tabular-nums ${breached ? KT.down : KT.muted}`}>
                      {pct(g.used)} <span className={KT.muted}>/ {g.detail}</span>
                    </span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded bg-[var(--kt-hover)]">
                    <div className="h-full rounded transition-all"
                         style={{ width: `${Math.min(100, Math.max(2, ratio * 100))}%`,
                                  background: fill }} />
                  </div>
                </div>
              );
            })}
            <p className={`pt-1 text-[10px] ${KT.muted}`}>
              A breach list only says fine or not fine. This shows a limit being
              approached — the last point where acting is still cheap.
            </p>
          </div>
        )}
      </div>

      {/* 3 — book shape */}
      <div className={KT.panel}>
        <div className="flex items-baseline justify-between border-b border-[var(--kt-border)] px-4 py-2.5">
          <span className={KT.label}>Book shape</span>
          {totalShock !== 0 && (
            <span className={`font-mono text-[11px] tabular-nums ${KT.muted}`}>
              −20% costs {money(Math.abs(totalShock))}
            </span>
          )}
        </div>
        {book.length === 0 ? (
          <div className={`px-4 py-10 text-center text-[12px] ${KT.muted}`}>
            No positions held.
          </div>
        ) : (
          <div className="h-[150px] w-full px-1 pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={book} layout="vertical"
                        margin={{ top: 2, right: 12, bottom: 2, left: 4 }}>
                <XAxis type="number" tick={{ fill: c.textMuted, fontSize: 9 }}
                       stroke={c.axis} tickLine={false}
                       tickFormatter={(v) => `${v}%`} />
                <YAxis type="category" dataKey="symbol" width={46}
                       tick={{ fill: c.textMuted, fontSize: 10 }}
                       stroke={c.axis} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: c.surface, border: `1px solid ${c.grid}`,
                                  borderRadius: 8, fontSize: 11, color: c.text }}
                  formatter={(v: number, _n, p) => [
                    `${Number(v).toFixed(1)}% · ${money(p.payload.value)} · ` +
                    `${p.payload.pnl >= 0 ? "+" : ""}${Number(p.payload.pnl).toFixed(2)}% unreal.`,
                    "weight",
                  ]} />
                {/* The concentration cap, drawn where it actually is. */}
                {capPct != null && (
                  <ReferenceLine x={capPct} stroke={c.down} strokeDasharray="3 3"
                                 label={{ value: `cap ${capPct}%`, position: "top",
                                          fill: c.down, fontSize: 9 }} />
                )}
                <Bar dataKey="weight" radius={[0, 3, 3, 0]}>
                  {book.map((r, i) => (
                    <Cell key={i}
                          fill={capPct != null && r.weight > capPct ? c.down : c.accent} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  );
}
