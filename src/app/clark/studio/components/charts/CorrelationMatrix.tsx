"use client";

import React from "react";

interface Props {
  correlation: Record<string, Record<string, number>>;
  className?: string;
}

export function CorrelationMatrix({ correlation, className }: Props) {
  const symbols = Object.keys(correlation).sort();

  if (symbols.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs text-zinc-500 ${className || ""}`}>
        No correlation data
      </div>
    );
  }

  // Get color based on correlation value (-1 to 1)
  const getColor = (val: number) => {
    // red for negative, green for positive
    if (val < 0) {
      // 0 to -1 -> opacity 0 to 1
      return `rgba(248, 113, 113, ${Math.abs(val) * 0.8})`; // red-400
    } else {
      return `rgba(52, 211, 153, ${val * 0.8})`; // emerald-400
    }
  };

  return (
    <div className={`overflow-x-auto ${className || ""}`}>
      <table className="w-full text-xs font-mono border-collapse">
        <thead>
          <tr>
            <th className="p-1"></th>
            {symbols.map((sym) => (
              <th key={sym} className="p-1 text-zinc-400 font-medium text-center">
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym) => (
            <tr key={rowSym}>
              <td className="p-1 text-zinc-400 font-medium text-right pr-3">{rowSym}</td>
              {symbols.map((colSym) => {
                const val = correlation[rowSym]?.[colSym];
                const isSelf = rowSym === colSym;
                
                if (val === undefined) {
                  return <td key={colSym} className="p-1 text-center text-zinc-600">—</td>;
                }

                return (
                  <td key={colSym} className="p-1 text-center">
                    <div
                      className="rounded flex items-center justify-center text-[10px] text-white w-9 h-9 mx-auto border border-zinc-800/30"
                      style={{ backgroundColor: isSelf ? "rgba(255,255,255,0.05)" : getColor(val) }}
                      title={`${rowSym} vs ${colSym}: ${val.toFixed(3)}`}
                    >
                      {isSelf ? "1.0" : val.toFixed(2)}
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
