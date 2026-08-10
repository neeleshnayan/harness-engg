"use client";

import React from "react";
import { GlassPanel } from "./GlassPanel";
import { Sparkline } from "./Sparkline";
import { StatusPulse } from "./StatusPulse";
import { StrategyView } from "@/lib/fund_api";
import { AnimatedNumber } from "./AnimatedNumber";

interface StrategyCardProps {
  strategy: StrategyView;
  chartData?: number[];
  onClick?: () => void;
}

const STATE_COLORS: Record<string, "live" | "syncing" | "offline"> = {
  deployed: "live",
  backtested: "syncing",
  draft: "offline",
  paused: "offline",
};

export function StrategyCard({ strategy, chartData, onClick }: StrategyCardProps) {
  const isChild = !!strategy.parent_id;
  const exposureShown = strategy.is_container ? strategy.rolled_exposure_usd ?? strategy.exposure_usd : strategy.exposure_usd;
  const pnlShown = strategy.is_container ? strategy.rolled_pnl_usd ?? strategy.pnl_usd : strategy.pnl_usd;
  const actual = Math.min(100, (strategy.is_container ? strategy.rolled_actual_pct : strategy.actual_pct) ?? 0);
  const target = Math.min(100, strategy.allocation_pct ?? 0);
  const sharpe = strategy.backtest?.sharpe;
  const ret = strategy.backtest?.total_return;

  return (
    <GlassPanel interactive onClick={onClick} className="p-4 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-zinc-100">{strategy.name}</h3>
            {strategy.is_container && (
              <span className="rounded bg-sky-500/15 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-sky-300 border border-sky-500/30">
                container
              </span>
            )}
          </div>
          <div className="mt-1 flex items-center gap-2">
            <StatusPulse state={STATE_COLORS[strategy.state] || "offline"} label={strategy.state} />
            {isChild && <span className="text-[10px] text-zinc-500">Child strategy</span>}
          </div>
        </div>
        {chartData && (
          <div className="flex-shrink-0">
            <Sparkline data={chartData} width={80} height={24} />
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Exposure</div>
          <AnimatedNumber
            value={exposureShown ?? 0}
            prefix="$"
            decimals={0}
            className="text-lg font-medium font-mono text-zinc-100"
          />
        </div>
        <div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-zinc-500 mb-1">Unrealized P&L</div>
          <AnimatedNumber
            value={Math.abs(pnlShown ?? 0)}
            prefix={pnlShown && pnlShown >= 0 ? "+$" : "-$"}
            decimals={0}
            className={`text-lg font-medium font-mono ${(pnlShown ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5 mt-2">
        <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
          <span>act {(actual).toFixed(1)}%</span>
          <span>tgt {(target).toFixed(1)}%</span>
        </div>
        <div className="relative h-1.5 rounded-full bg-zinc-800">
          <div
            className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-teal-500 to-sky-500"
            style={{ width: `${actual}%` }}
          />
          <div
            className="absolute -top-1 h-3.5 w-0.5 bg-zinc-100/80"
            style={{ left: `${target}%` }}
            title={`target ${target}%`}
          />
        </div>
      </div>

      <div className="flex justify-between items-center border-t border-white/5 pt-3 mt-1">
        <div className="flex gap-4">
          <div className="flex flex-col">
            <span className="text-[9px] uppercase tracking-wider text-zinc-500">Sharpe</span>
            <span className="font-mono text-xs text-zinc-300">{sharpe != null ? sharpe.toFixed(2) : "—"}</span>
          </div>
          <div className="flex flex-col">
            <span className="text-[9px] uppercase tracking-wider text-zinc-500">Return</span>
            <span className={`font-mono text-xs ${ret != null && ret >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {ret != null ? `${(ret * 100).toFixed(1)}%` : "—"}
            </span>
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}
