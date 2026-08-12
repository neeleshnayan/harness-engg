"use client";

import React from "react";
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceDot,
} from "recharts";

interface BarData {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  sma20?: number;
  sma50?: number;
  signal?: "BUY" | "SELL" | null;
}

interface Props {
  symbol: string;
  barsData?: BarData[];
  height?: number;
  className?: string;
}

export function QuantConnectChart({ symbol, barsData, height = 320, className }: Props) {

  let data: BarData[] = barsData && barsData.length > 0 ? barsData : [];

  if (data.length === 0) {
    return (
      <div className={`rounded-2xl border font-mono shadow-2xl p-8 text-center text-xs ${
        "bg-[var(--kt-surface)]/90 border-emerald-500/20 text-[var(--kt-text-muted)]"
      } ${className || ""}`}>
        No price bars available for symbol {symbol}
      </div>
    );
  }

  const buySignals = data.filter((d) => d.signal === "BUY");
  const sellSignals = data.filter((d) => d.signal === "SELL");

  const minPrice = Math.min(...data.map((d) => d.low || d.close)) * 0.97;
  const maxPrice = Math.max(...data.map((d) => d.high || d.close)) * 1.03;

  return (
    <div
      className={`rounded-2xl border font-mono shadow-2xl space-y-3 p-5 transition-all ${
        "bg-[var(--kt-surface)]/90 border-emerald-500/20 backdrop-blur-xl"
      } ${className || ""}`}
    >
      {/* Chart Header Bar */}
      <div className={`flex flex-wrap items-center justify-between gap-3 border-b pb-3 text-xs ${
        "border-emerald-950/40"
      }`}>
        <div className="flex items-center gap-3">
          <span className={`font-extrabold text-sm px-3 py-1 rounded-lg border ${
            "bg-emerald-950/80 text-[var(--kt-accent)] border-emerald-700/50"
          }`}>
            {symbol}
          </span>
          <div className="flex items-center gap-2 font-bold">
            <span className={`text-base font-black ${"text-[var(--kt-accent)]"}`}>
              ${data[data.length - 1]?.close.toFixed(2)}
            </span>
            <span className={`text-[10px] ${"text-[var(--kt-text-muted)]"}`}>
              TradingView Live Feed
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 font-medium">
          <span className={`text-[10px] uppercase font-bold ${"text-[var(--kt-text-dim)]"}`}>Indicators:</span>
          <span className={`text-[10px] px-2.5 py-0.5 rounded-md border ${
            "bg-emerald-950/80 text-[var(--kt-accent)] border-emerald-700/40"
          }`}>
            Close Terracotta
          </span>
          <span className={`text-[10px] px-2.5 py-0.5 rounded-md border ${
            "bg-emerald-950/80 text-[var(--kt-accent)] border-emerald-700/40"
          }`}>
            SMA(20) Sage
          </span>
          <span className={`text-[10px] px-2.5 py-0.5 rounded-md border ${
            "bg-sky-950/80 text-sky-300 border-sky-700/40"
          }`}>
            SMA(50) Blue
          </span>
        </div>
      </div>

      {/* Main Chart Canvas */}
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid stroke={"var(--kt-border)"} strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "var(--kt-text-muted)", fontSize: 10 }}
              axisLine={{ stroke: "var(--kt-border-strong)" }}
              tickLine={false}
            />
            <YAxis
              yAxisId="price"
              domain={[minPrice, maxPrice]}
              tick={{ fill: "var(--kt-text-dim)", fontSize: 10 }}
              axisLine={{ stroke: "var(--kt-border-strong)" }}
              tickLine={false}
              orientation="right"
              tickFormatter={(v) => `$${v}`}
            />
            <YAxis yAxisId="volume" orientation="left" domain={[0, "auto"]} hide />
            <Tooltip
              contentStyle={{
                background: "var(--kt-bg)",
                border: "1px solid #1e293b",
                borderRadius: 8,
                fontSize: 11,
                fontFamily: "monospace",
                color: "var(--kt-text)",
              }}
              formatter={(val: any, name: string) => [
                name === "volume" ? val.toLocaleString() : `$${Number(val).toFixed(2)}`,
                name.toUpperCase(),
              ]}
            />

            <Bar yAxisId="volume" dataKey="volume" fill={"var(--kt-border)"} opacity={0.6} barSize={6} />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke="var(--kt-accent)"
              strokeWidth={2.4}
              dot={false}
              name="Close Price"
            />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="sma20"
              stroke="#276749"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="SMA 20"
            />
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="sma50"
              stroke="#2563EB"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="SMA 50"
            />

            {buySignals.map((s, idx) => (
              <ReferenceDot
                key={`buy-${idx}`}
                yAxisId="price"
                x={s.date}
                y={s.close}
                r={6}
                fill="#276749"
                stroke="var(--kt-text-strong)"
                strokeWidth={2}
              />
            ))}

            {sellSignals.map((s, idx) => (
              <ReferenceDot
                key={`sell-${idx}`}
                yAxisId="price"
                x={s.date}
                y={s.close}
                r={6}
                fill="var(--kt-accent)"
                stroke="var(--kt-text-strong)"
                strokeWidth={2}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
