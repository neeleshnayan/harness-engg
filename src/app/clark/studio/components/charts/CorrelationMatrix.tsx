"use client";

import React from "react";

interface Props {
  correlation?: Record<string, Record<string, number>> | null;
  assets?: string[];
  className?: string;
  theme?: "dark" | "light";
}

export function CorrelationMatrix({ correlation, assets, className, theme = "dark" }: Props) {
  const isLight = theme === "light";

  const safeMap = correlation || {};
  const symbols = Object.keys(safeMap).sort();

  if (symbols.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs py-8 ${isLight ? "text-[#78716C]" : "text-zinc-500"} ${className || ""}`}>
        No correlation data available
      </div>
    );
  }

  // Anthropic Emerald Green (#10B981) vs Sage Green (#276749) for correlation intensity
  const getColor = (val: number) => {
    if (val < 0) {
      return isLight ? `rgba(217, 119, 87, ${Math.abs(val) * 0.85})` : `rgba(249, 115, 22, ${Math.abs(val) * 0.8})`;
    } else {
      return isLight ? `rgba(39, 103, 73, ${val * 0.85})` : `rgba(16, 185, 129, ${val * 0.8})`;
    }
  };

  return (
    <div className={`overflow-x-auto ${className || ""}`}>
      <table className="w-full text-xs font-mono border-collapse">
        <thead>
          <tr>
            <th className="p-1"></th>
            {symbols.map((sym) => (
              <th key={sym} className={`p-1 font-medium text-center ${isLight ? "text-[#44403C]" : "text-zinc-400"}`}>
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym) => (
            <tr key={rowSym}>
              <td className={`p-1 font-medium text-right pr-3 ${isLight ? "text-[#44403C]" : "text-zinc-400"}`}>{rowSym}</td>
              {symbols.map((colSym) => {
                const val = safeMap[rowSym]?.[colSym];

                if (val === undefined) {
                  return <td key={colSym} className={`p-1 text-center ${isLight ? "text-[#A8A29E]" : "text-zinc-600"}`}>—</td>;
                }

                return (
                  <td key={colSym} className="p-1 text-center">
                    <div
                      className="rounded-lg flex items-center justify-center text-[10px] text-white w-9 h-9 mx-auto border border-black/10 font-bold shadow-sm"
                      style={{ backgroundColor: getColor(val) }}
                    >
                      {val.toFixed(2)}
                    </div>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
