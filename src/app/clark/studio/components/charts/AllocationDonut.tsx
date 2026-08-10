"use client";

import React from "react";
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { NavPosition } from "@/lib/fund_api";

interface Props {
  positions: NavPosition[];
  cash: number;
  totalNav: number;
  height?: number;
  className?: string;
}

const COLORS = [
  "#2dd4bf", // teal-400
  "#38bdf8", // sky-400
  "#818cf8", // indigo-400
  "#a78bfa", // violet-400
  "#fbbf24", // amber-400
  "#f472b6", // pink-400
  "#34d399", // emerald-400
];
const CASH_COLOR = "#52525b"; // zinc-500

export function AllocationDonut({ positions, cash, totalNav, height = 240, className }: Props) {
  const data = [
    ...positions.map((p) => ({
      name: p.symbol,
      value: p.usd_value,
      pct: totalNav > 0 ? (p.usd_value / totalNav) * 100 : 0,
    })),
  ];

  // Only add cash if it's meaningful
  if (cash > 0.01) {
    data.push({
      name: "CASH",
      value: cash,
      pct: totalNav > 0 ? (cash / totalNav) * 100 : 0,
    });
  }

  // Sort largest to smallest for better rendering
  data.sort((a, b) => b.value - a.value);

  const fmtValue = (n: number) =>
    `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (data.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center text-xs text-zinc-500 ${className || ""}`}
        style={{ height }}
      >
        No positions
      </div>
    );
  }

  return (
    <div className={className} style={{ width: "100%", height }}>
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={85}
            paddingAngle={2}
            dataKey="value"
            stroke="none"
          >
            {data.map((entry, index) => (
              <Cell 
                key={`cell-${index}`} 
                fill={entry.name === "CASH" ? CASH_COLOR : COLORS[index % COLORS.length]} 
              />
            ))}
          </Pie>
          <Tooltip
            cursor={false}
            contentStyle={{
              background: "#09090b",
              border: "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
            }}
            itemStyle={{ color: "#f4f4f5" }}
            formatter={(value: number, name: string, props: any) => [
              `${fmtValue(value)} (${props.payload.pct.toFixed(1)}%)`,
              name,
            ]}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
