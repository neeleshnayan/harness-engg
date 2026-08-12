"use client";

import React from "react";
import { KT } from "../../theme";
import { Sparkline } from "./Sparkline";
import { StatusPulse } from "./StatusPulse";
import { StrategyView } from "@/lib/fund_api";

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

  const formattedPnl = pnlShown != null
    ? `${pnlShown >= 0 ? "+" : "-"}$${Math.abs(pnlShown).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : "—";

  return (
    <div
      onClick={onClick}
      className={`${KT.card} ${KT.cardHover} cursor-pointer flex flex-col gap-4`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h3 className={KT.title}>{strategy.name}</h3>
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
          <div className={KT.label}>Exposure</div>
          <div className={KT.numberLg}>
            ${(exposureShown ?? 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div>
          <div className={KT.label}>Unrealized P&L</div>
          <div className={`font-mono tabular-nums text-2xl font-light ${(pnlShown ?? 0) >= 0 ? KT.up : KT.down}`}>
            {formattedPnl}
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-1.5 mt-2">
        <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
          <span>act {actual.toFixed(1)}%</span>
          <span>tgt {target.toFixed(1)}%</span>
        </div>
        <div className={KT.barTrack}>
          <div className={KT.barFill} style={{ width: `${actual}%` }} />
        </div>
      </div>

      <div className="flex justify-between items-center border-t border-zinc-800/60 pt-3 mt-1">
        <div className="flex gap-4">
          <div className="flex flex-col">
            <span className={KT.label}>Sharpe</span>
            <span className={KT.number}>{sharpe != null ? sharpe.toFixed(2) : "—"}</span>
          </div>
          <div className="flex flex-col">
            <span className={KT.label}>Return</span>
            <span className={`font-mono text-sm ${ret != null && ret >= 0 ? KT.up : KT.down}`}>
              {ret != null ? `${(ret * 100).toFixed(1)}%` : "—"}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
