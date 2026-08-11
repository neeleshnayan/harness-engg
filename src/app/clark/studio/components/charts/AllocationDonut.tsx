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
  theme?: "dark" | "light";
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
const CASH_COLOR_DARK = "#52525b";
const CASH_COLOR_LIGHT = "#A8A29E";

export function AllocationDonut({ positions = [], cash = 0, totalNav = 0, height = 240, className, theme = "dark" }: Props) {
  const isLight = theme === "light";

  const data = [
    ...(positions || []).map((p) => ({
      name: p.symbol || (p as any).name || "Asset",
      value: p.usd_value || (p as any).value || 0,
      pct: totalNav > 0 ? ((p.usd_value || (p as any).value || 0) / totalNav) * 100 : 0,
    })),
  ];

  if (cash > 0.01) {
    data.push({
      name: "CASH",
      value: cash,
      pct: totalNav > 0 ? (cash / totalNav) * 100 : 0,
    });
  }

  data.sort((a, b) => b.value - a.value);

  const fmtValue = (n: number) =>
    `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

  if (data.length === 0) {
    return (
      <div
        className={`flex flex-col items-center justify-center text-xs ${isLight ? "text-[#78716C]" : "text-zinc-500"} ${className || ""}`}
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
                fill={entry.name === "CASH" ? (isLight ? CASH_COLOR_LIGHT : CASH_COLOR_DARK) : COLORS[index % COLORS.length]} 
              />
            ))}
          </Pie>
          <Tooltip
            cursor={false}
            contentStyle={{
              background: isLight ? "#FFFFFF" : "#09090b",
              border: isLight ? "1px solid #D9D2C5" : "1px solid #27272a",
              borderRadius: 8,
              fontSize: 12,
              color: isLight ? "#1E1E1E" : "#f4f4f5",
            }}
            itemStyle={{ color: isLight ? "#1E1E1E" : "#f4f4f5" }}
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
