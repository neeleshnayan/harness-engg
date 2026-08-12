"use client";

import React from "react";
import { ResponsiveContainer, LineChart, Line, YAxis } from "recharts";

interface SparklineProps {
  data: number[];
  up?: boolean;
  width?: number | string;
  height?: number;
  className?: string;
}

export function Sparkline({ data, up, width = 60, height = 24, className = "" }: SparklineProps) {
  if (!data || data.length < 2) {
    return <div style={{ width, height }} className={`bg-[var(--kt-inset)] rounded ${className}`} />;
  }

  // Infer trend if not explicitly provided
  const isUp = typeof up === "boolean" ? up : data[data.length - 1] >= data[0];
  const color = isUp ? "#34d399" : "var(--kt-down)"; // emerald-400 / rose-400

  // Format for recharts
  const chartData = data.map((val, i) => ({ val, i }));

  return (
    <div style={{ width, height }} className={className}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
          <YAxis domain={["dataMin", "dataMax"]} hide />
          <Line
            type="monotone"
            dataKey="val"
            stroke={color}
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
