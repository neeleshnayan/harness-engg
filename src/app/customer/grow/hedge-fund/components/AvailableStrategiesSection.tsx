"use client";

import React from "react";
import { useRouter } from "next/navigation";
import StrategyCard from "./StrategyCard";
import { StrategyFilters } from "./StrategyFilters";

interface AvailableStrategiesSectionProps {
  strategies: any[];
  activeStrategies: any[];
  riskFilter: string;
  apyFilter: string;
  onRiskChange: (value: string) => void;
  onApyChange: (value: string) => void;
  onAddStrategy: () => void;
  onRefresh: () => void;
  tokenBalances: {
    usdc?: number;
    strategies: Record<string, string>;
    strategiesWei?: Record<string, string>;
  };
  walletAddress?: string;
}

export function AvailableStrategiesSection({
  strategies,
  activeStrategies,
  riskFilter,
  apyFilter,
  onRiskChange,
  onApyChange,
  onAddStrategy,
  onRefresh,
  tokenBalances,
  walletAddress,
}: AvailableStrategiesSectionProps) {
  const router = useRouter();

  return (
    <section className="w-full mb-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
        <h2 className="text-lg sm:text-xl font-semibold text-white tracking-tight">
          Available Strategies
        </h2>
        <StrategyFilters
          riskFilter={riskFilter}
          apyFilter={apyFilter}
          onRiskChange={onRiskChange}
          onApyChange={onApyChange}
        />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4 sm:gap-5">
        {activeStrategies.length === 0 && strategies.length > 0 && (
          <div className="col-span-full py-8 text-center text-zinc-400 text-sm">
            No strategies match your filters. Try &quot;All risk&quot; or &quot;All APY&quot;.
          </div>
        )}
        {activeStrategies.map((strat) => {
          const balanceKey = strat.symbol || strat.id || strat.address;
          return (
            <StrategyCard
              key={strat.id || strat.address}
              strategyName={strat.symbol || strat.id || "Unknown"}
              strategyData={strat}
              onRefresh={onRefresh}
              onCardClick={() => {
                router.push(`/customer/grow/hedge-fund/${strat.id || strat.symbol || "YEARN_WETH"}`);
              }}
              usdcBalance={tokenBalances.usdc?.toString()}
              strategyBalance={tokenBalances.strategies[balanceKey]}
              strategyBalanceWei={tokenBalances.strategiesWei?.[balanceKey]}
            />
          );
        })}

        <div
          onClick={onAddStrategy}
          className="flex flex-col items-center justify-center h-full min-h-[300px] border-2 border-dashed border-zinc-700 hover:border-blue-500 rounded-xl bg-zinc-900/30 hover:bg-zinc-900/50 cursor-pointer transition-all group"
        >
          <div className="w-16 h-16 rounded-full bg-zinc-800 group-hover:bg-blue-500/20 flex items-center justify-center mb-4 transition-all">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="text-zinc-400 group-hover:text-blue-500"
            >
              <path d="M5 12h14" />
              <path d="M12 5v14" />
            </svg>
          </div>
          <h3 className="text-lg font-semibold text-zinc-300 group-hover:text-white">
            Add New Strategy
          </h3>
          <p className="text-sm text-zinc-500 mt-2 text-center px-4">
            Deploy a new Yearn Strategy to the platform
          </p>
        </div>
      </div>
    </section>
  );
}
