"use client";

import React, { useMemo } from "react";
import { ResponsiveContainer, Treemap, Tooltip } from "recharts";

interface PositionData {
  symbol: string;
  usd_value: number;
}

interface ConcentrationTreemapProps {
  positions: PositionData[];
  totalNav: number;
  height?: number;
}

const COLORS = [
  "#2dd4bf", // teal-400
  "#34d399", // emerald-400
  "#38bdf8", // sky-400
  "#fbbf24", // amber-400
  "#a78bfa", // violet-400
  "#f472b6", // pink-400
  "#fb7185", // rose-400
];

const CustomizedContent = (props: any) => {
  const { root, depth, x, y, width, height, index, name, value, totalNav } = props;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        style={{
          fill: COLORS[index % COLORS.length],
          stroke: "#0f0f16",
          strokeWidth: 2,
          strokeOpacity: 1,
          fillOpacity: 0.8,
        }}
        className="transition-opacity hover:opacity-100 cursor-pointer"
      />
      {width > 40 && height > 30 && (
        <text
          x={x + width / 2}
          y={y + height / 2}
          textAnchor="middle"
          fill="#fff"
          fontSize={12}
          fontWeight="600"
          dominantBaseline="middle"
        >
          {name}
        </text>
      )}
      {width > 50 && height > 50 && (
        <text
          x={x + width / 2}
          y={y + height / 2 + 15}
          textAnchor="middle"
          fill="#fff"
          fontSize={10}
          opacity={0.8}
          dominantBaseline="middle"
        >
          {((value / totalNav) * 100).toFixed(1)}%
        </text>
      )}
    </g>
  );
};

export function ConcentrationTreemap({ positions, totalNav, height = 300 }: ConcentrationTreemapProps) {
  const data = useMemo(() => {
    if (!positions || positions.length === 0) return [];
    return positions.map((p) => ({
      name: p.symbol,
      size: p.usd_value,
      totalNav, // Pass totalNav to the node for percentage calculation
    })).sort((a, b) => b.size - a.size);
  }, [positions, totalNav]);

  if (data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-sm text-zinc-500">
        No position data available for treemap.
      </div>
    );
  }

  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer width="100%" height="100%">
        <Treemap
          data={data}
          dataKey="size"
          stroke="#fff"
          fill="#8884d8"
          content={<CustomizedContent totalNav={totalNav} />}
        >
          <Tooltip
            content={({ active, payload }) => {
              if (active && payload && payload.length) {
                const data = payload[0].payload;
                return (
                  <div className="rounded-lg border border-zinc-800 bg-zinc-950/90 p-3 shadow-xl backdrop-blur-md">
                    <div className="mb-1 text-sm font-semibold text-zinc-100">{data.name}</div>
                    <div className="flex justify-between gap-4 text-xs">
                      <span className="text-zinc-400">Value:</span>
                      <span className="font-mono text-zinc-100">
                        ${data.size.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                      </span>
                    </div>
                    <div className="flex justify-between gap-4 text-xs">
                      <span className="text-zinc-400">% NAV:</span>
                      <span className="font-mono text-teal-400">
                        {((data.size / totalNav) * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                );
              }
              return null;
            }}
          />
        </Treemap>
      </ResponsiveContainer>
    </div>
  );
}
