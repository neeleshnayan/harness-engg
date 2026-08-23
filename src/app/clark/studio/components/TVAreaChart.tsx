"use client";

import React, { useMemo } from "react";
import { useChartColors } from "../chartColors";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface TVPoint {
  t: string; // label (date)
  v: number; // value (price / equity)
}

interface Props {
  data: TVPoint[];
  height?: number;
  /** Color hint: up = teal, down = red. If omitted, inferred from first/last. */
  up?: boolean;
  valuePrefix?: string;
  className?: string;
}

/**
 * A TradingView-style area chart: gradient fill, thin line, crosshair tooltip,
 * minimal right-aligned price axis, sparse date ticks. Built on recharts to stay
 * aligned with the rest of the KryptonPay chart stack.
 */
export function TVAreaChart({ data, height = 220, up, valuePrefix = "", className }: Props) {
  const c = useChartColors();
  const trendUp = useMemo(() => {
    if (typeof up === "boolean") return up;
    if (data.length < 2) return true;
    return data[data.length - 1].v >= data[0].v;
  }, [data, up]);

  const stroke = trendUp ? c.accent : c.down; // teal-400 / red-400
  const id = useMemo(() => `tvgrad-${Math.random().toString(36).slice(2, 8)}`, []);

  const fmt = (n: number) =>
    `${valuePrefix}${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

  // Sparse ticks: ~6 evenly spaced date labels.
  const ticks = useMemo(() => {
    if (data.length <= 6) return data.map((d) => d.t);
    const step = Math.floor(data.length / 6);
    return data.filter((_, i) => i % step === 0).map((d) => d.t);
  }, [data]);

  if (!data.length) {
    return (
      <div
        className={`flex items-center justify-center text-xs text-[var(--kt-text-muted)] ${className || ""}`}
        style={{ height }}
      >
        No series
      </div>
    );
  }

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 6, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={stroke} stopOpacity={0.28} />
              <stop offset="100%" stopColor={stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke={c.grid} strokeDasharray="0" vertical={false} />
          <XAxis
            dataKey="t"
            ticks={ticks}
            tick={{ fill: c.textMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: c.grid }}
            minTickGap={20}
          />
          <YAxis
            orientation="right"
            domain={["auto", "auto"]}
            tick={{ fill: c.textMuted, fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={54}
            tickFormatter={(v) => fmt(Number(v))}
          />
          <Tooltip
            cursor={{ stroke: c.axis, strokeWidth: 1 }}
            contentStyle={{
              background: c.bg,
              border: `1px solid ${c.grid}`,
              borderRadius: 8,
              fontSize: 12,
            }}
            labelStyle={{ color: c.textDim }}
            itemStyle={{ color: stroke }}
            formatter={(v: number) => [fmt(Number(v)), "px"]}
          />
          <Area
            type="monotone"
            dataKey="v"
            stroke={stroke}
            strokeWidth={1.75}
            fill={`url(#${id})`}
            dot={false}
            isAnimationActive={false}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
