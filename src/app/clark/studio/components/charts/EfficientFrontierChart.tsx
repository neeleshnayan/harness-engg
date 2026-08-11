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
  points?: FrontierPoint[];
  assets?: string[];
  optimalWeights?: Record<string, number>;
  height?: number;
  className?: string;
  theme?: "dark" | "light";
}

export function EfficientFrontierChart({ points, assets, optimalWeights, height = 240, className, theme = "dark" }: Props) {
  const isLight = theme === "light";

  let activePoints: FrontierPoint[] = points && points.length > 0 ? points : [];

  if (activePoints.length === 0) {
    const baseVol = 0.12;
    const baseRet = 0.08;
    activePoints = Array.from({ length: 15 }, (_, i) => {
      const vol = baseVol + i * 0.015;
      const ret = baseRet + Math.sqrt(i) * 0.06;
      const sharpe = ret / vol;
      return {
        target_return: ret,
        return: ret,
        volatility: vol,
        sharpe: sharpe,
        weights: assets ? { [assets[0] || "TSLA"]: 0.5, [assets[1] || "AAPL"]: 0.5 } : {},
      };
    });
  }

  const data = activePoints.map((p) => ({
    volatility: Number((p.volatility * 100).toFixed(2)),
    return: Number((p.return * 100).toFixed(2)),
    sharpe: Number(p.sharpe.toFixed(2)),
    weights: p.weights,
  }));

  let maxSharpePoint = data[0];
  for (const p of data) {
    if (p.sharpe > maxSharpePoint.sharpe) {
      maxSharpePoint = p;
    }
  }

  let minVolPoint = data[0];
  for (const p of data) {
    if (p.volatility < minVolPoint.volatility) {
      minVolPoint = p;
    }
  }

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <ScatterChart margin={{ top: 10, right: 20, bottom: 20, left: -10 }}>
          <CartesianGrid stroke={isLight ? "#EAE5D9" : "#1e293b"} strokeDasharray="3 3" />
          <XAxis
            type="number"
            dataKey="volatility"
            name="Volatility"
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: isLight ? "#78716C" : "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: isLight ? "#D9D2C5" : "#334155" }}
            tickLine={false}
            domain={["auto", "auto"]}
          />
          <YAxis
            type="number"
            dataKey="return"
            name="Return"
            tickFormatter={(v) => `${v}%`}
            tick={{ fill: isLight ? "#78716C" : "#94a3b8", fontSize: 10 }}
            axisLine={{ stroke: isLight ? "#D9D2C5" : "#334155" }}
            tickLine={false}
            domain={["auto", "auto"]}
          />
          <ZAxis type="number" range={[40, 60]} />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={{
              background: isLight ? "#FFFFFF" : "#030712",
              border: isLight ? "1px solid #D9D2C5" : "1px solid #1e293b",
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "monospace",
              color: isLight ? "#1E1E1E" : "#e2e8f0",
            }}
            formatter={(value: number, name: string) => [
              name === "sharpe" ? value.toFixed(2) : `${value.toFixed(2)}%`,
              name === "volatility" ? "Volatility" : name === "return" ? "Return" : "Sharpe Ratio",
            ]}
          />
          <Scatter
            name="Efficient Frontier"
            data={data}
            fill={isLight ? "#D97757" : "#14b8a6"}
            line={{ stroke: isLight ? "#D97757" : "#14b8a6", strokeWidth: 2 }}
            shape="circle"
          />
          <Scatter
            name="Tangency Portfolio (Max Sharpe ⭐)"
            data={[maxSharpePoint]}
            fill={isLight ? "#276749" : "#34d399"}
            shape="star"
          />
          <Scatter
            name="Minimum Variance (Min Vol 🛡️)"
            data={[minVolPoint]}
            fill={isLight ? "#2B6CB0" : "#38bdf8"}
            shape="diamond"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
