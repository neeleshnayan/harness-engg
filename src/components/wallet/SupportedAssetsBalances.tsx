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
 * Displays all supported token balances with color-coded price indicators.
 *
 * Covers k-tokens (kUSD, kEUR, kGBP, kAED, kINR),
 * RWA tokens (GC, XAG, NVDA, ETH), and USDC.
 *
 * Uses RatesContext for all rate data - no direct API calls here!
 */
const SupportedAssetsBalances: React.FC<SupportedAssetsBalancesProps> = ({ balance, className = "" }) => {
  const { tokens, getTokenAddressToSymbol, getTokenDirection, isLoading } = useRates();

  // Get address -> symbol map
  const tokenAddressMap = useMemo(() => getTokenAddressToSymbol(), [getTokenAddressToSymbol]);

  // Extract token balances from the balance data
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

      if (tokenSymbol === "USDC") {
        usdcTotal += rawAmount;
      } else if (tokenSymbol) {
        aggregatedBalances[tokenSymbol] = (aggregatedBalances[tokenSymbol] || 0) + rawAmount;
      }
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
      const estimatedItemWidth = 130;
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

  // Get background color based on price direction
  const getBgColor = (symbol: string) => {
    if (symbol === "USDC" || symbol === "kUSD") {
      return "bg-zinc-800/60 border-zinc-700/50";
    }

    const direction = getTokenDirection(symbol);
    switch (direction) {
      case "up":
        return "bg-[#6AFF90]/20 border-[#00FF40]/60";
      case "down":
        return "bg-[#FF3434]/20 border-[#FF0004]/60";
      default:
        return "bg-zinc-800/60 border-zinc-700/50";
    }
  };

  const renderToken = (token: TokenBalance, idx: number, rowSuffix: string = "") => {
    const bgColor = getBgColor(token.symbol);
    const clickable = isClickable(token.symbol);

    return (
      <div
        key={`${token.symbol}-${rowSuffix}${idx}`}
        onClick={() => handleTokenClick(token.symbol)}
        className={`${bgColor} border rounded-lg px-3 py-2 flex items-center flex-shrink-0 ${
          clickable ? "cursor-pointer hover:opacity-80 transition-opacity" : ""
        }`}
      >
        <span className="text-white font-medium text-sm whitespace-nowrap">
          {parseFloat(token.balance).toFixed(2)} {formatDisplaySymbol(token.symbol)}
        </span>
      </div>
    );
  };

  return (
    <>
      <div className={`mt-4 ${className}`}>
        <div className="flex items-center gap-3 mb-4">
           <div className="flex items-center text-zinc-400 text-sm font-medium whitespace-nowrap">
             <img src="/coin-stack.svg" alt="" className="mr-2 w-4 h-4 opacity-80" />
             All Assets
           </div>
           <div className="h-[1.5px] bg-zinc-600/80 flex-1 rounded-full"></div>
        </div>
        <div
          ref={containerRef}
          className="overflow-x-auto overflow-y-hidden pb-2 [&::-webkit-scrollbar]:h-1.5 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-zinc-700 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:hover:bg-zinc-600"
          style={{
            WebkitOverflowScrolling: 'touch',
            scrollbarWidth: 'thin',
            overscrollBehavior: 'contain'
          }}
          onTouchStart={(e) => e.stopPropagation()}
          onTouchMove={(e) => e.stopPropagation()}
          onTouchEnd={(e) => e.stopPropagation()}
        >
          <div className="inline-block">
            <div className="flex gap-2 mb-2">
              {finalFirstRow.map((token, idx) => renderToken(token, idx, "row1-"))}
            </div>
            {finalSecondRow.length > 0 && (
              <div className="flex gap-2">
                {finalSecondRow.map((token, idx) => renderToken(token, idx, "row2-"))}
              </div>
            )}
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
