"use client";

import React from "react";
import { useChartColors } from "../../chartColors";
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


export function AllocationDonut({ positions = [], cash = 0, totalNav = 0, height = 240, className }: Props) {
  const c = useChartColors();
  const palette = c.series;
  const cashColor = c.textMuted;

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
        className={`flex flex-col items-center justify-center text-xs ${"text-[var(--kt-text-muted)]"} ${className || ""}`}
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
                fill={entry.name === "CASH" ? cashColor : palette[index % palette.length]} 
              />
            ))}
          </Pie>
          <Tooltip
            cursor={false}
            contentStyle={{
              background: c.bg,
              border: "1px solid #1e293b",
              borderRadius: 8,
              fontSize: 12,
              color: c.text,
            }}
            itemStyle={{ color: c.text }}
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
