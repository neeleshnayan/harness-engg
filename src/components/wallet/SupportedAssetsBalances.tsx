'use client';

import React, { useMemo, useState } from "react";
import { useRates } from "@/providers/RatesProvider";
import TokenPriceHistoryModal from "./TokenPriceHistoryModal";

interface TokenBalance {
  symbol: string;
  balance: string;
}

interface SupportedAssetsBalancesProps {
  balance: any;
  className?: string;
}

/**
 * Displays currency token balances with color-coded price indicators.
 *
 * Shows only currencies: k-tokens (kUSD, kEUR, kGBP, kAED, kINR) and USDC.
 * RWA tokens (GC, XAG, NVDA, ETH, etc.) are excluded.
 *
 * Uses RatesContext for all rate data - no direct API calls here!
 */
const SupportedAssetsBalances: React.FC<SupportedAssetsBalancesProps> = ({ balance, className = "" }) => {
  const { tokens, getTokenAddressToSymbol, getTokenDirection } = useRates();

  // Get address -> symbol map
  const tokenAddressMap = useMemo(() => getTokenAddressToSymbol(), [getTokenAddressToSymbol]);

  // Extract token balances from the balance data - only currencies (k-tokens and USDC), exclude RWA tokens
  const tokenBalances = useMemo(() => {
    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    const aggregatedBalances: Record<string, number> = {};
    let usdcTotal = 0;

    for (const tb of balance.tokenBalances) {
      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) continue;

      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const symbolFromBalance = tb?.token?.symbol;
      const tokenSymbol = (tokenAddress ? tokenAddressMap[tokenAddress] : undefined) || symbolFromBalance;

      // Only include currencies: k-tokens (start with 'k') and USDC
      // Exclude RWA tokens (GC, XAG, NVDA, ETH, etc. - tokens that don't start with 'k')
      if (tokenSymbol === "USDC") {
        usdcTotal += rawAmount;
      } else if (tokenSymbol && tokenSymbol.startsWith('k')) {
        // Only include k-tokens (currencies)
        aggregatedBalances[tokenSymbol] = (aggregatedBalances[tokenSymbol] || 0) + rawAmount;
      }
      // RWA tokens (non-k tokens) are excluded
    }

    const balances: TokenBalance[] = Object.entries(aggregatedBalances).map(([symbol, amount]) => ({
      symbol,
      balance: amount.toString(),
    }));

    if (usdcTotal > 0) {
      balances.push({ symbol: "USDC", balance: usdcTotal.toString() });
    }

    return balances;
  }, [balance, tokenAddressMap]);

  const [selectedTokenForModal, setSelectedTokenForModal] = useState<string | null>(null);

  if (tokenBalances.length === 0) {
    return null;
  }

  const handleTokenClick = (tokenSymbol: string) => {
    if (tokenSymbol !== "USDC" && tokenSymbol !== "kUSD") {
      setSelectedTokenForModal(tokenSymbol);
    }
  };

  const isClickable = (tokenSymbol: string) => {
    return tokenSymbol !== "USDC" && tokenSymbol !== "kUSD";
  };

  const formatDisplaySymbol = (symbol: string) => {
    if (symbol.startsWith('k')) {
      return symbol.replace(/^k/, '');
    }
    return symbol;
  };

  // Uniform border for all; color applied inside based on price direction
  // Solid-ish backgrounds avoid backdrop blur artifacts / 3D pattern bleed-through
  const getTokenStyle = (symbol: string) => {
    const neutralBorder = "border border-white/12";

    // USDC and kUSD are stable - neutral fill
    if (symbol === "USDC" || symbol === "kUSD") {
      return { bg: "bg-zinc-800/95", border: neutralBorder };
    }

    const direction = getTokenDirection(symbol);
    switch (direction) {
      case "up":
        return { bg: "bg-emerald-700/30", border: "border border-emerald-400/40" };
      case "down":
        return { bg: "bg-red-700/30", border: "border border-red-400/40" };
      default:
        return { bg: "bg-zinc-800/95", border: neutralBorder };
    }
  };

  const renderToken = (
    token: TokenBalance,
    idx: number,
    rowSuffix: string = "",
    size: "mobile" | "desktop" = "mobile",
  ) => {
    const style = getTokenStyle(token.symbol);
    const clickable = isClickable(token.symbol);
    const isDesktop = size === "desktop";

    return (
      <div
        key={`${token.symbol}-${rowSuffix}${idx}`}
        onClick={() => handleTokenClick(token.symbol)}
        className={`${style.bg} ${style.border} ${isDesktop ? "rounded-xl px-4 py-2.5" : "rounded-lg px-3 py-1.5"} flex items-center flex-shrink-0 transition-all duration-200 ${clickable
          ? "cursor-pointer hover:brightness-110 hover:shadow-lg hover:shadow-black/20 active:scale-95"
          : ""
          }`}
      >
        <span className={`text-white/90 font-medium whitespace-nowrap tracking-wide ${isDesktop ? "text-base" : "text-xs"}`}>
          {parseFloat(token.balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          <span className={`text-white/40 ml-1 font-normal ${isDesktop ? "text-sm" : "text-[11px]"}`}>{formatDisplaySymbol(token.symbol)}</span>
        </span>
      </div>
    );
  };

  const half = Math.ceil(tokenBalances.length / 2);

  return (
    <>
      <div className={className}>
        <div className="flex items-center gap-2.5 sm:gap-3 mb-4 sm:mb-5">
          <div className="flex items-center text-zinc-500 text-sm sm:text-base font-medium whitespace-nowrap">
            <img src="/coin-stack.svg" alt="" className="mr-2 sm:mr-2.5 w-5 h-5 sm:w-6 sm:h-6 opacity-60" />
            All Currencies
          </div>
          <div className="h-[1.5px] bg-gradient-to-r from-zinc-600/80 to-transparent flex-1 rounded-full"></div>
        </div>

        {/* Desktop: single row, wraps naturally */}
        <div className="hidden sm:flex flex-wrap gap-3">
          {tokenBalances.map((token, idx) => renderToken(token, idx, "desktop-", "desktop"))}
        </div>

        {/* Mobile: two rows, horizontal scroll with fade hint */}
        <div className="sm:hidden relative">
          <div
            className="overflow-x-auto overflow-y-hidden pb-3 [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/20 [&::-webkit-scrollbar-thumb]:rounded-full"
            style={{
              WebkitOverflowScrolling: 'touch',
              scrollbarWidth: 'thin',
              overscrollBehavior: 'contain'
            }}
            onTouchStart={(e) => e.stopPropagation()}
            onTouchMove={(e) => e.stopPropagation()}
            onTouchEnd={(e) => e.stopPropagation()}
          >
            <div className="inline-flex flex-col gap-2 min-w-max">
              <div className="flex gap-2">
                {tokenBalances.slice(0, half).map((token, idx) => renderToken(token, idx, "row1-"))}
              </div>
              {tokenBalances.length > half && (
                <div className="flex gap-2">
                  {tokenBalances.slice(half).map((token, idx) => renderToken(token, idx, "row2-"))}
                </div>
              )}
            </div>
          </div>

        </div>
      </div>

      {selectedTokenForModal && (
        <TokenPriceHistoryModal
          open={!!selectedTokenForModal}
          onClose={() => setSelectedTokenForModal(null)}
          tokenSymbol={selectedTokenForModal}
        />
      )}
    </>
  );
};

export default SupportedAssetsBalances;
