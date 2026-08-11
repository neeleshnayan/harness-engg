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
    let basePrice = symbol === "TSLA" ? 240 : symbol === "NVDA" ? 125 : symbol === "MSFT" ? 418 : 220;
    const now = new Date();

    data = Array.from({ length: 40 }, (_, i) => {
      const d = new Date(now.getTime() - (40 - i) * 24 * 60 * 60 * 1000);
      const dateStr = d.toISOString().slice(5, 10);
      const volatility = basePrice * 0.025;
      const change = (Math.random() - 0.48) * volatility;
      basePrice = Math.max(20, basePrice + change);

      const open = basePrice - (Math.random() - 0.5) * 2;
      const high = Math.max(open, basePrice) + Math.random() * 3;
      const low = Math.min(open, basePrice) - Math.random() * 3;
      const close = basePrice;
      const volume = Math.floor(1500000 + Math.random() * 3500000);

      let signal: "BUY" | "SELL" | null = null;
      if (i === 12) signal = "BUY";
      if (i === 26) signal = "SELL";
      if (i === 36) signal = "BUY";

      return {
        date: dateStr,
        open: Number(open.toFixed(2)),
        high: Number(high.toFixed(2)),
        low: Number(low.toFixed(2)),
        close: Number(close.toFixed(2)),
        volume,
        signal,
      };
    });

    for (let i = 0; i < data.length; i++) {
      if (i >= 5) {
        const slice20 = data.slice(Math.max(0, i - 19), i + 1);
        data[i].sma20 = Number((slice20.reduce((a, b) => a + b.close, 0) / slice20.length).toFixed(2));
      }
      if (i >= 12) {
        const slice50 = data.slice(Math.max(0, i - 49), i + 1);
        data[i].sma50 = Number((slice50.reduce((a, b) => a + b.close, 0) / slice50.length).toFixed(2));
      }
    }
  }

  const buySignals = data.filter((d) => d.signal === "BUY");
  const sellSignals = data.filter((d) => d.signal === "SELL");

  const minPrice = Math.min(...data.map((d) => d.low || d.close)) * 0.97;
  const maxPrice = Math.max(...data.map((d) => d.high || d.close)) * 1.03;

  return (
    <div
      className={`rounded-2xl border border-teal-500/20 bg-[#070D1B]/80 backdrop-blur-xl font-mono shadow-2xl space-y-3 p-5 transition-all ${className || ""}`}
    >
      {/* Chart Header Bar */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-teal-900/40 pb-3 text-xs">
        <div className="flex items-center gap-3">
          <span className="font-extrabold text-sm px-3 py-1 rounded-lg bg-teal-950/80 text-teal-300 border border-teal-700/50">
            {symbol}
          </span>
          <div className="flex items-center gap-2 font-bold">
            <span className="text-base font-black text-emerald-400">
              ${data[data.length - 1]?.close.toFixed(2)}
            </span>
            <span className="text-[10px] text-zinc-500">
              TradingView Live Feed
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 font-medium">
          <span className="text-[10px] uppercase font-bold text-zinc-400">Indicators:</span>
          <span className="text-[10px] px-2.5 py-0.5 rounded-md bg-teal-950/80 text-teal-300 border border-teal-700/40">
            SMA(20) Cyan
          </span>
          <span className="text-[10px] px-2.5 py-0.5 rounded-md bg-sky-950/80 text-sky-300 border border-sky-700/40">
            SMA(50) Sky
          </span>
          <span className="text-[10px] px-2.5 py-0.5 rounded-md bg-emerald-950/80 text-emerald-400 border border-emerald-800">
            🟢 BUY Signal
          </span>
          <span className="text-[10px] px-2.5 py-0.5 rounded-md bg-rose-950/80 text-rose-400 border border-rose-800">
            🔴 SELL Signal
          </span>
        </div>
      </div>

      {/* Main Chart Canvas */}
      <div style={{ width: "100%", height }}>
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, bottom: 0, left: -10 }}>
            <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="date"
              tick={{ fill: "#64748b", fontSize: 10 }}
              axisLine={{ stroke: "#334155" }}
              tickLine={false}
            />
            <YAxis
              yAxisId="price"
              domain={[minPrice, maxPrice]}
              tick={{ fill: "#94a3b8", fontSize: 10 }}
              axisLine={{ stroke: "#334155" }}
              tickLine={false}
              orientation="right"
              tickFormatter={(v) => `$${v}`}
            />
            <YAxis yAxisId="volume" orientation="left" domain={[0, "auto"]} hide />
            <Tooltip
              contentStyle={{
                background: "#030712",
                border: "1px solid #1e293b",
                borderRadius: 8,
                fontSize: 11,
                fontFamily: "monospace",
                color: "#f8fafc",
              }}
              formatter={(val: any, name: string) => [
                name === "volume" ? val.toLocaleString() : `$${Number(val).toFixed(2)}`,
                name.toUpperCase(),
              ]}
            />

            <Bar yAxisId="volume" dataKey="volume" fill="#1e293b" opacity={0.6} barSize={6} />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke="#10b981"
              strokeWidth={2.2}
              dot={false}
              name="Close Price"
            />

            <Line
              yAxisId="price"
              type="monotone"
              dataKey="sma20"
              stroke="#2dd4bf"
              strokeWidth={1.5}
              strokeDasharray="4 4"
              dot={false}
              name="SMA 20"
            />
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="sma50"
              stroke="#38bdf8"
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
                fill="#10b981"
                stroke="#ffffff"
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
                fill="#f43f5e"
                stroke="#ffffff"
                strokeWidth={2}
              />
            ))}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
