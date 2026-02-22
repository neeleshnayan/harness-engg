'use client';

import React, { useMemo, useRef, useEffect, useState } from "react";
import { FaCoins } from "react-icons/fa";
import { useRates, CURRENCY_SYMBOLS } from "@/providers/RatesProvider";
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
  const { tokens, getTokenAddressToSymbol, getTokenDirection, isLoading } = useRates();

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
  }, [balance, tokenAddressMap, (balance as any)?._fetchedAt]);

  const containerRef = useRef<HTMLDivElement>(null);
  const [itemsPerRow, setItemsPerRow] = useState<number>(Math.ceil(tokenBalances.length / 2));
  const [selectedTokenForModal, setSelectedTokenForModal] = useState<string | null>(null);

  // Measure and calculate how many items fit per row
  useEffect(() => {
    if (!containerRef.current || tokenBalances.length === 0) return;

    const measureItems = () => {
      const container = containerRef.current;
      if (!container) return;

      const containerWidth = container.offsetWidth;
      const estimatedItemWidth = 140;
      const itemsPerRow = Math.max(1, Math.floor(containerWidth / estimatedItemWidth));
      setItemsPerRow(itemsPerRow);
    };

    measureItems();
    window.addEventListener('resize', measureItems);
    return () => window.removeEventListener('resize', measureItems);
  }, [tokenBalances.length]);

  if (tokenBalances.length === 0) {
    return null;
  }

  // Split based on calculated items per row
  const firstRow = tokenBalances.slice(0, itemsPerRow);
  const secondRow = tokenBalances.slice(itemsPerRow, itemsPerRow * 2);
  const remainingItems = tokenBalances.slice(itemsPerRow * 2);

  const finalFirstRow = [...firstRow];
  const finalSecondRow = [...secondRow];

  remainingItems.forEach((item, idx) => {
    if (idx % 2 === 0) {
      finalFirstRow.push(item);
    } else {
      finalSecondRow.push(item);
    }
  });

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

    // USDC and kUSD are stable — neutral fill
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

  const renderToken = (token: TokenBalance, idx: number, rowSuffix: string = "") => {
    const style = getTokenStyle(token.symbol);
    const clickable = isClickable(token.symbol);

    return (
      <div
        key={`${token.symbol}-${rowSuffix}${idx}`}
        onClick={() => handleTokenClick(token.symbol)}
        className={`${style.bg} ${style.border} rounded-lg px-3 py-1.5 flex items-center flex-shrink-0 transition-all duration-200 ${clickable
          ? "cursor-pointer hover:brightness-110 hover:shadow-lg hover:shadow-black/20 active:scale-95"
          : ""
          }`}
      >
        <span className="text-white/90 font-medium text-xs whitespace-nowrap tracking-wide">
          {parseFloat(token.balance).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          <span className="text-white/40 ml-1 font-normal text-[11px]">{formatDisplaySymbol(token.symbol)}</span>
        </span>
      </div>
    );
  };

  const half = Math.ceil(tokenBalances.length / 2);

  return (
    <>
      <div className={className}>
        <div className="flex items-center gap-2.5 mb-4">
          <div className="flex items-center text-zinc-500 text-sm font-medium whitespace-nowrap">
            <img src="/coin-stack.svg" alt="" className="mr-2 w-5 h-5 opacity-60" />
            All Currencies
          </div>
          <div className="h-[1.5px] bg-gradient-to-r from-zinc-600/80 to-transparent flex-1 rounded-full"></div>
        </div>

        {/* Desktop: single row, wraps naturally */}
        <div className="hidden sm:flex flex-wrap gap-2">
          {tokenBalances.map((token, idx) => renderToken(token, idx, "desktop-"))}
        </div>

        {/* Mobile: two rows, horizontal scroll with fade hint */}
        <div className="sm:hidden relative">
          <div
            ref={containerRef}
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
