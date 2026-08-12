"use client";

import React, { useMemo, useState } from "react";
import { DollarSign, PieChart, ShieldAlert } from "lucide-react";

interface PositionData {
  symbol: string;
  usd_value: number;
}

interface ConcentrationTreemapProps {
  positions: PositionData[];
  totalNav: number;
  height?: number;
}

const TILE_PALETTE = [
  { bg: "bg-teal-950/70 border-teal-500/40 text-teal-200 hover:bg-teal-900/80", accent: "bg-teal-400" },
  { bg: "bg-emerald-950/70 border-emerald-500/40 text-emerald-200 hover:bg-emerald-900/80", accent: "bg-emerald-400" },
  { bg: "bg-sky-950/70 border-sky-500/40 text-sky-200 hover:bg-sky-900/80", accent: "bg-sky-400" },
  { bg: "bg-indigo-950/70 border-indigo-500/40 text-indigo-200 hover:bg-indigo-900/80", accent: "bg-indigo-400" },
  { bg: "bg-violet-950/70 border-violet-500/40 text-violet-200 hover:bg-violet-900/80", accent: "bg-violet-400" },
  { bg: "bg-amber-950/70 border-amber-500/40 text-amber-200 hover:bg-amber-900/80", accent: "bg-amber-400" },
  { bg: "bg-rose-950/70 border-rose-500/40 text-rose-200 hover:bg-rose-900/80", accent: "bg-rose-400" },
];

export function ConcentrationTreemap({ positions, totalNav, height = 320 }: ConcentrationTreemapProps) {
  const [hoveredSymbol, setHoveredSymbol] = useState<string | null>(null);

  const tiles = useMemo(() => {
    if (!positions || positions.length === 0) return [];
    const validNav = totalNav > 0 ? totalNav : positions.reduce((acc, p) => acc + Math.abs(p.usd_value), 0);
    if (validNav <= 0) return [];

    const items = positions.map((p) => {
      const val = Math.max(0, p.usd_value);
      const pct = (val / validNav) * 100;
      return {
        symbol: p.symbol,
        usd_value: val,
        pct: pct,
        isCash: p.symbol.toUpperCase() === "USD" || p.symbol.toUpperCase() === "CASH",
      };
    }).sort((a, b) => b.pct - a.pct);

    // Compute remaining unallocated cash if total position USD < validNav
    const totalAllocated = items.reduce((acc, i) => acc + i.usd_value, 0);
    const remainingCash = validNav - totalAllocated;

    if (remainingCash > 10 && !items.some((i) => i.isCash)) {
      items.push({
        symbol: "CASH / TREASURY",
        usd_value: remainingCash,
        pct: (remainingCash / validNav) * 100,
        isCash: true,
      });
    }

    return items;
  }, [positions, totalNav]);

  if (tiles.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-xs font-mono text-zinc-500 border border-zinc-800 rounded-xl bg-zinc-950/50">
        No active position exposure to display in treemap.
      </div>
    );
  }

  return (
    <div className="w-full space-y-3 font-mono">
      {/* Treemap Proportion Grid Canvas */}
      <div
        style={{ height }}
        className="w-full flex flex-wrap gap-2 p-2 rounded-2xl bg-[#060911] border border-zinc-800/80 overflow-hidden relative shadow-2xl"
      >
        {tiles.map((tile, idx) => {
          const style = TILE_PALETTE[idx % TILE_PALETTE.length];
          // Flex basis scale based on pct weight
          const flexGrow = Math.max(1, Math.round(tile.pct));
          const flexShrink = 1;
          const minWidth = tile.pct > 15 ? "220px" : tile.pct > 8 ? "150px" : "110px";

          return (
            <div
              key={tile.symbol}
              style={{ flexGrow, flexShrink, minWidth }}
              onMouseEnter={() => setHoveredSymbol(tile.symbol)}
              onMouseLeave={() => setHoveredSymbol(null)}
              className={`relative rounded-xl border p-3 flex flex-col justify-between transition-all duration-200 cursor-pointer shadow-lg group ${style.bg} ${
                hoveredSymbol === tile.symbol ? "scale-[1.01] z-20 ring-2 ring-teal-400/50 shadow-2xl" : ""
              }`}
            >
              {/* Tile Top Row: Symbol Badge & Percentage Weight */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`w-2 h-2 rounded-full ${style.accent}`} />
                  <span className="font-bold text-xs font-sans tracking-tight truncate text-white">
                    {tile.symbol}
                  </span>
                </div>
                <span className="text-xs font-black font-mono tracking-tight text-white bg-zinc-950/60 px-1.5 py-0.5 rounded border border-zinc-800">
                  {tile.pct.toFixed(1)}%
                </span>
              </div>

              {/* Tile Middle: USD Exposure Value */}
              <div className="my-2">
                <span className="text-[10px] text-zinc-400 block uppercase tracking-wider font-semibold">Exposure Value</span>
                <span className="text-sm font-bold font-mono text-zinc-100">
                  ${tile.usd_value.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}
                </span>
              </div>

              {/* Tile Bottom Progress Bar */}
              <div className="w-full h-1.5 rounded-full bg-zinc-950/80 overflow-hidden border border-zinc-900">
                <div
                  className={`h-full rounded-full ${style.accent}`}
                  style={{ width: `${Math.min(100, tile.pct)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Summary Footer Legend */}
      <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-zinc-400 px-1 pt-1">
        <div className="flex items-center gap-2">
          <PieChart size={13} className="text-teal-400" />
          <span>Total NAV Basis: <strong className="text-zinc-200">${(totalNav || 0).toLocaleString()}</strong></span>
        </div>
        <div className="flex items-center gap-4">
          <span>Positions: <strong className="text-teal-300">{tiles.length}</strong></span>
          <span>Max Single Asset Cap: <strong className="text-amber-300">20.0% NAV Limit</strong></span>
        </div>
      </div>
    </div>
  );
}
