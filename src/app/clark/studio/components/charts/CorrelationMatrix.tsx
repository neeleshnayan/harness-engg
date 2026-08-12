"use client";

import React from "react";

interface Props {
  correlation?: Record<string, Record<string, number>> | null;
  assets?: string[];
  className?: string;
}

export function CorrelationMatrix({ correlation, assets, className }: Props) {

  const safeMap = correlation || {};
  const symbols = Object.keys(safeMap).sort();

  if (symbols.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs py-8 ${"text-zinc-500"} ${className || ""}`}>
        No correlation data available
      </div>
    );
  }

  // Anthropic Emerald Green (#10B981) vs Sage Green (#276749) for correlation intensity
  const getColor = (val: number) => {
    if (val < 0) {
      return `rgba(249, 115, 22, ${Math.abs(val) * 0.8})`;
    } else {
      return `rgba(16, 185, 129, ${val * 0.8})`;
    }
  };

  return (
    <div className={`overflow-x-auto ${className || ""}`}>
      <table className="w-full text-xs font-mono border-collapse">
        <thead>
          <tr>
            <th className="p-1"></th>
            {symbols.map((sym) => (
              <th key={sym} className={`p-1 font-medium text-center ${"text-zinc-400"}`}>
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym) => (
            <tr key={rowSym}>
              <td className={`p-1 font-medium text-right pr-3 ${"text-zinc-400"}`}>{rowSym}</td>
              {symbols.map((colSym) => {
                const val = safeMap[rowSym]?.[colSym];

                if (val === undefined) {
                  return <td key={colSym} className={`p-1 text-center ${"text-zinc-600"}`}>—</td>;
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
