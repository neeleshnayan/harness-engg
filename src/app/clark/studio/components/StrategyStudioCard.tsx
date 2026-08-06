"use client";

import React from "react";
import { Button } from "@/components/ui/button";
import { StrategyView } from "@/lib/fund_api";

const STATE_STYLES: Record<string, string> = {
  deployed: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  backtested: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  draft: "bg-zinc-500/15 text-zinc-300 border-zinc-500/30",
  paused: "bg-amber-500/15 text-amber-300 border-amber-500/30",
};

const money = (n?: number) =>
  n == null ? "—" : `$${Number(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const pct = (n?: number) => (n == null ? "0.0%" : `${Number(n).toFixed(1)}%`);

interface Props {
  s: StrategyView;
  onBacktest: (s: StrategyView) => void;
  onDeploy: (s: StrategyView) => void;
  onPause: (s: StrategyView) => void;
  onAllocate: (s: StrategyView) => void;
}

export function StrategyStudioCard({ s, onBacktest, onDeploy, onPause, onAllocate }: Props) {
  const pnl = s.pnl_usd ?? 0;
  const up = pnl >= 0;
  const actual = Math.min(100, s.actual_pct ?? 0);
  const target = Math.min(100, s.allocation_pct ?? 0);
  const sharpe = s.backtest ? (s.backtest as { sharpe?: number }).sharpe : undefined;

  return (
    <div className="rounded-2xl border border-zinc-800 bg-zinc-900/70 p-5 flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="font-semibold text-white">{s.name}</span>
        <span
          className={`text-[10px] uppercase tracking-wide px-2 py-0.5 rounded-full border ${
            STATE_STYLES[s.state] || STATE_STYLES.draft
          }`}
        >
          {s.state}
        </span>
        <span className={`ml-auto font-mono text-sm ${up ? "text-emerald-400" : "text-red-400"}`}>
          {up ? "+" : ""}
          {money(pnl)}
        </span>
      </div>

      <div>
        <div className="relative h-2 rounded-full bg-zinc-800 overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-blue-600 to-purple-600"
            style={{ width: `${actual}%` }}
          />
          <div
            className="absolute -top-1 h-4 w-0.5 bg-white/80"
            style={{ left: `${target}%` }}
            title="target"
          />
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-zinc-400 font-mono">
          <span>
            actual {pct(s.actual_pct)} · exp {money(s.exposure_usd)}
          </span>
          <span>target {pct(s.allocation_pct)}</span>
        </div>
      </div>

      {sharpe != null && (
        <div className="text-xs text-zinc-400 font-mono">backtest sharpe {Number(sharpe).toFixed(2)}</div>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="outline"
          className="bg-transparent border-zinc-700 text-zinc-200"
          onClick={() => onBacktest(s)}
        >
          Backtest
        </Button>
        {s.state !== "deployed" ? (
          <Button
            size="sm"
            className="bg-gradient-to-r from-blue-600 to-purple-600 text-white"
            onClick={() => onDeploy(s)}
          >
            Deploy
          </Button>
        ) : (
          <Button
            size="sm"
            variant="outline"
            className="bg-transparent border-amber-700/50 text-amber-300"
            onClick={() => onPause(s)}
          >
            Pause
          </Button>
        )}
        <Button
          size="sm"
          variant="outline"
          className="bg-transparent border-zinc-700 text-zinc-200"
          onClick={() => onAllocate(s)}
        >
          Allocate
        </Button>
      </div>
    </div>
  );
}
