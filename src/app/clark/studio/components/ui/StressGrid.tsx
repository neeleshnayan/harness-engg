"use client";

import React from "react";
import { GlassPanel } from "./GlassPanel";
import { AnimatedNumber } from "./AnimatedNumber";

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
      <GlassPanel title="Stress Scenarios">
        <div className="flex h-32 items-center justify-center text-sm text-zinc-500">
          No stress scenarios configured.
        </div>
      </GlassPanel>
    );
  }

  return (
    <GlassPanel title="Stress Scenarios" className="!p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/5 text-[10px] uppercase tracking-wider text-zinc-500 bg-zinc-950/20">
              <th className="px-4 py-3 text-left font-medium">Scenario</th>
              <th className="px-4 py-3 text-left font-medium">Type</th>
              <th className="px-4 py-3 text-right font-medium">Impact (%)</th>
              <th className="px-4 py-3 text-right font-medium">Impact (USD)</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5 font-mono">
            {scenarios.map((s) => (
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
                <td className="px-4 py-3 text-right">
                  <AnimatedNumber
                    value={Math.abs(s.impact_pct)}
                    prefix={s.impact_pct >= 0 ? "+" : "-"}
                    suffix="%"
                    decimals={1}
                    className={s.impact_pct >= 0 ? "text-emerald-400" : "text-rose-400"}
                  />
                </td>
                <td className="px-4 py-3 text-right">
                  <AnimatedNumber
                    value={Math.abs(s.impact_usd)}
                    prefix={s.impact_usd >= 0 ? "+$" : "-$"}
                    decimals={0}
                    className={s.impact_usd >= 0 ? "text-emerald-400" : "text-rose-400"}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassPanel>
  );
}
