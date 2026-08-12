"use client";

import React from "react";
import { useChartColors } from "../../chartColors";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { StrategyView } from "@/lib/fund_api";

interface Props {
  strategies: StrategyView[];
  height?: number;
  className?: string;
}

export function StrategyPerformanceBar({ strategies, height = 240, className }: Props) {
  const c = useChartColors();
  // Only show strategies that are active/deployed or have actual PnL
  const activeStrategies = strategies.filter(
    (s) => s.state === "deployed" || Math.abs(s.pnl_usd || 0) > 0.01 || Math.abs(s.exposure_usd || 0) > 0.01
  );

  const data = activeStrategies.map((s) => ({
    name: s.name,
    pnl: s.pnl_usd || 0,
    exposure: s.exposure_usd || 0,
  }));

  // Sort by exposure then PnL
  data.sort((a, b) => b.exposure - a.exposure || b.pnl - a.pnl);

  const fmtValue = (n: number) =>
    `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (data.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center text-xs text-[var(--kt-text-muted)] ${className || ""}`}
        style={{ height }}
      >
        No deployed strategies
      </div>
    );
  }

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
          <CartesianGrid stroke={c.grid} strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: c.textDim, fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: c.grid }}
          />
          <YAxis
            tick={{ fill: c.textMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(v) => `$${v > 1000 ? (v / 1000).toFixed(1) + "k" : v}`}
            width={60}
          />
          <Tooltip
            cursor={{ fill: c.grid, opacity: 0.4 }}
            contentStyle={{
              background: c.bg,
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: "#e4e4e7", fontWeight: 600, marginBottom: 4 }}
            formatter={(value: number, name: string) => [
              fmtValue(value),
              name === "exposure" ? "Exposure" : "Unrealized P&L",
            ]}
          />
          {/* Exposure bar */}
          <Bar dataKey="exposure" fill="#3f3f46" radius={[4, 4, 0, 0]} barSize={32} />
          {/* PnL bar (overlaid or side-by-side, let's do side-by-side by not stacking) */}
          <Bar dataKey="pnl" radius={[4, 4, 0, 0]} barSize={32}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.pnl >= 0 ? "#34d399" : c.down} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
