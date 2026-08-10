"use client";

import React from "react";
import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { FrontierPoint } from "@/lib/fund_api";

interface Props {
  points: FrontierPoint[];
  optimalWeights?: Record<string, number>;
  height?: number;
  className?: string;
}

export function EfficientFrontierChart({ points, optimalWeights, height = 300, className }: Props) {
  if (!points || points.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-zinc-500 ${className || ""}`} style={{ height }}>
        No efficient frontier data
      </div>
    );
  }

  // Format data for Recharts
  const data = points.map((p) => ({
    volatility: p.volatility * 100, // convert to %
    return: p.return * 100, // convert to %
    sharpe: p.sharpe,
    weights: p.weights,
  }));

  // Find the max sharpe point to highlight
  let maxSharpePoint = data[0];
  for (const p of data) {
    if (p.sharpe > maxSharpePoint.sharpe) {
      maxSharpePoint = p;
    }
  }

  const fmtValue = (n: number) => `${n.toFixed(2)}%`;

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 0 }}>
          <CartesianGrid stroke="#27272a" strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="volatility"
            name="Volatility"
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
            domain={["auto", "auto"]}
          >
          </XAxis>
          <YAxis
            type="number"
            dataKey="return"
            name="Expected Return"
            tickFormatter={(v) => `${v.toFixed(0)}%`}
            tick={{ fill: "#a1a1aa", fontSize: 11 }}
            axisLine={{ stroke: "#27272a" }}
            tickLine={false}
            domain={["auto", "auto"]}
          />
          <ZAxis type="number" range={[40, 40]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{
              background: "#09090b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            formatter={(value: number, name: string) => [
              name === "sharpe" ? value.toFixed(2) : fmtValue(value),
              name === "volatility" ? "Volatility" : name === "return" ? "Return" : "Sharpe",
            ]}
            labelFormatter={() => ""}
          />
          <Scatter
            name="Efficient Frontier"
            data={data}
            fill="#0ea5e9" // sky-500
            line={{ stroke: "#0ea5e9", strokeWidth: 2 }}
            shape="circle"
          />
          <Scatter
            name="Max Sharpe"
            data={[maxSharpePoint]}
            fill="#34d399" // emerald-400
            shape="star"
            // Make the star slightly larger
            zAxisId={0}
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
