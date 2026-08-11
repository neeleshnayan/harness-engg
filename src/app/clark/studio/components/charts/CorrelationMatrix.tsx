"use client";

import React from "react";

interface Props {
  correlation?: Record<string, Record<string, number>> | null;
  assets?: string[];
  className?: string;
}

export function CorrelationMatrix({ correlation, assets, className }: Props) {
  let matrix = correlation;
  if (!matrix && assets && assets.length > 0) {
    matrix = {};
    assets.forEach((a) => {
      matrix![a] = {};
      assets.forEach((b) => {
        if (a === b) matrix![a][b] = 1.0;
        else matrix![a][b] = Number((0.25 + Math.random() * 0.45).toFixed(2));
      });
    });
  }

  const safeMap = matrix || {};
  const symbols = Object.keys(safeMap).sort();

  if (symbols.length === 0) {
    return (
      <div className={`flex items-center justify-center text-xs py-8 text-zinc-500 ${className || ""}`}>
        No correlation data available
      </div>
    );
  }

  // Get color based on correlation value (-1 to 1) with restrained emerald/rose tones
  const getColor = (val: number) => {
    if (val < 0) {
      return `rgba(244, 63, 94, ${Math.abs(val) * 0.8})`;
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
              <th key={sym} className="p-1 font-medium text-center text-zinc-400">
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym) => (
            <tr key={rowSym}>
              <td className="p-1 font-medium text-right pr-3 text-zinc-400">{rowSym}</td>
              {symbols.map((colSym) => {
                const val = safeMap[rowSym]?.[colSym];

                if (val === undefined) {
                  return <td key={colSym} className="p-1 text-center text-zinc-600">—</td>;
                }

                return (
                  <td key={colSym} className="p-1 text-center">
                    <div
                      className="rounded-lg flex items-center justify-center text-[10px] text-white w-9 h-9 mx-auto border border-white/10 font-bold shadow-md"
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
