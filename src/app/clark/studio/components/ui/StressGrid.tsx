"use client";

import React from "react";
import { KT } from "../../theme";

export interface StressScenario {
  id: string;
  name: string;
  description: string;
  impact_pct: number;
  impact_usd: number;
  is_historical: boolean;
}

interface StressGridProps {
  scenarios: StressScenario[];
}

export function StressGrid({ scenarios }: StressGridProps) {
  if (!scenarios || scenarios.length === 0) {
    return (
      <div className={`${KT.panel} p-6`}>
        <h3 className={KT.title}>Stress Scenarios</h3>
        <div className="flex h-32 items-center justify-center text-sm text-zinc-500">
          No stress scenarios configured.
        </div>
      </div>
    );
  }

  return (
    <div className={`${KT.panel} p-5 space-y-4`}>
      <h3 className={KT.title}>Stress Scenarios</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className={`border-b ${KT.border} ${KT.label} bg-zinc-950/40`}>
              <th className="px-4 py-3 text-left font-medium">Scenario</th>
              <th className="px-4 py-3 text-left font-medium">Type</th>
              <th className="px-4 py-3 text-right font-medium">Impact (%)</th>
              <th className="px-4 py-3 text-right font-medium">Impact (USD)</th>
            </tr>
          </thead>
          <tbody className={`divide-y divide-zinc-800/50 ${KT.number}`}>
            {scenarios.map((s) => {
              const formattedPct = `${s.impact_pct >= 0 ? "+" : "-"}${Math.abs(s.impact_pct).toFixed(1)}%`;
              const formattedUsd = `${s.impact_usd >= 0 ? "+$" : "-$"}${Math.abs(s.impact_usd).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
              return (
                <tr key={s.id} className="hover:bg-zinc-800/30 transition-colors">
                  <td className="px-4 py-3 font-sans">
                    <div className="font-medium text-zinc-200">{s.name}</div>
                    <div className="text-[11px] text-zinc-500 mt-0.5">{s.description}</div>
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[9px] uppercase font-semibold ${
                        s.is_historical
                          ? "bg-sky-500/15 text-sky-400 border border-sky-500/20"
                          : "bg-amber-500/15 text-amber-400 border border-amber-500/20"
                      }`}
                    >
                      {s.is_historical ? "Historical" : "Hypothetical"}
                    </span>
                  </td>
                  <td className={`px-4 py-3 text-right font-bold ${s.impact_pct >= 0 ? KT.up : KT.down}`}>
                    {formattedPct}
                  </td>
                  <td className={`px-4 py-3 text-right font-bold ${s.impact_usd >= 0 ? KT.up : KT.down}`}>
                    {formattedUsd}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
