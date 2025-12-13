import React, { useMemo, useRef, useEffect, useState } from "react";
import { FaCoins } from "react-icons/fa";
import { K_TOKEN_ADDRESSES_LOWERCASE } from "@/lib/kTokens";
import { getPoolRate, getClosingPoolRate } from "@/lib/priceCache";
import TokenPriceHistoryModal from "./TokenPriceHistoryModal";

interface KTTokenBalance {
  symbol: string;
  balance: string;
}

interface KTTokenBalancesProps {
  balance: any;
  className?: string;
}

const KTTokenBalances: React.FC<KTTokenBalancesProps> = ({ balance, className = "" }) => {
  // Extract k-token balances from the balance data
  const kTokenBalances = useMemo(() => {
    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    const aggregatedBalances: Record<string, number> = {};
    let usdcTotal = 0;

    for (const tb of balance.tokenBalances) {
      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const kTokenSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;
      const tokenSymbol = tb?.token?.symbol;

      if (kTokenSymbol) {
        aggregatedBalances[kTokenSymbol] = (aggregatedBalances[kTokenSymbol] || 0) + rawAmount;
        continue;
      }

      if (tokenSymbol === "USDC" || tokenSymbol === "TRNSK") {
        usdcTotal += rawAmount;
      }
    }

    const balances: KTTokenBalance[] = Object.entries(aggregatedBalances).map(([symbol, amount]) => ({
      symbol,
      balance: amount.toString(),
    }));

    if (usdcTotal > 0) {
      balances.push({ symbol: "USDC", balance: usdcTotal.toString() });
    }

    return balances;
  }, [balance]);

  const containerRef = useRef<HTMLDivElement>(null);
  const [itemsPerRow, setItemsPerRow] = useState<number>(Math.ceil(kTokenBalances.length / 2));
  // Track price comparisons: "up" if current > closing (green), "down" if current < closing (red), undefined if same or no data
  const [priceComparisons, setPriceComparisons] = useState<Record<string, "up" | "down" | undefined>>({});
  const [selectedTokenForModal, setSelectedTokenForModal] = useState<string | null>(null);

  // Fetch and compare closing vs current pool prices for each token
  useEffect(() => {
    const fetchPriceComparisons = async () => {
      const comparisons: Record<string, "up" | "down" | undefined> = {};

      for (const token of kTokenBalances) {
        // Skip USDC and kUSD as they're always 1:1 with USD
        if (token.symbol === "USDC" || token.symbol === "kUSD") {
          continue;
        }

        try {
          // Get rates for kUSD/token pair
          const [currentRate, closingRate] = await Promise.all([
            getPoolRate("kUSD", token.symbol == "kUSD" ? "USDC" : token.symbol),
            getClosingPoolRate("kUSD", token.symbol == "kUSD" ? "USDC" : token.symbol),
          ]);

          console.log(`Current rate for ${token.symbol}: ${currentRate}, Closing rate: ${closingRate}`);

          // Compare prices: green if current > closing, red if current < closing, undefined if same
          if (currentRate > 0 && closingRate > 0) {
            if (currentRate > closingRate) {
              comparisons[token.symbol] = "up"; // Green - price went up
            } else if (currentRate < closingRate) {
              comparisons[token.symbol] = "down"; // Red - price went down
            }
            // If prices are equal, leave undefined (will show normal/uncolored)
          }
        } catch (error) {
          console.error(`Failed to fetch prices for ${token.symbol}:`, error);
        }
      }

      setPriceComparisons(comparisons);
    };

    if (kTokenBalances.length > 0) {
      fetchPriceComparisons();
    }
  }, [kTokenBalances]);

  // Measure and calculate how many items fit per row
  useEffect(() => {
    if (!containerRef.current || kTokenBalances.length === 0) return;

    const measureItems = () => {
      const container = containerRef.current;
      if (!container) return;

      const containerWidth = container.offsetWidth;
      // Approximate item width (adjust based on your actual item width + gap)
      const estimatedItemWidth = 130; // rough estimate including gap
      const itemsPerRow = Math.max(1, Math.floor(containerWidth / estimatedItemWidth));

      setItemsPerRow(itemsPerRow);
    };

    measureItems();
    window.addEventListener('resize', measureItems);
    return () => window.removeEventListener('resize', measureItems);
  }, [kTokenBalances.length]);

  if (kTokenBalances.length === 0) {
    return null; // Don't show anything if user has no k-tokens
  }

  // Split based on calculated items per row
  const firstRow = kTokenBalances.slice(0, itemsPerRow);
  const secondRow = kTokenBalances.slice(itemsPerRow, itemsPerRow * 2);
  const remainingItems = kTokenBalances.slice(itemsPerRow * 2);

  // Distribute remaining items between first and second row
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
    // Only allow clicking on tokens that aren't USDC or kUSD
    if (tokenSymbol !== "USDC" && tokenSymbol !== "kUSD") {
      setSelectedTokenForModal(tokenSymbol);
    }
  };

  const isClickable = (tokenSymbol: string) => {
    return tokenSymbol !== "USDC" && tokenSymbol !== "kUSD";
  };

  return (
    <>
      <div className={`mt-4 pt-4 border-t border-zinc-700/50 ${className}`}>
        <div className="mb-2">
          <div className="flex items-center text-zinc-400 text-sm">
            <FaCoins className="mr-2" />
            All Currencies
          </div>
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
              {finalFirstRow.map((token, idx) => {
                const priceComparison = priceComparisons[token.symbol];
                const bgColor = token.symbol !== "USDC" && token.symbol !== "kUSD" && priceComparison
                  ? priceComparison === "up"
                    ? "bg-green-950/40 border-green-800/50"
                    : "bg-red-950/40 border-red-800/50"
                  : "bg-zinc-800/60 border-zinc-700/50";
                const clickable = isClickable(token.symbol);

                return (
                  <div
                    key={`${token.symbol}-${idx}`}
                    onClick={() => handleTokenClick(token.symbol)}
                    className={`${bgColor} border rounded-lg px-3 py-2 flex items-center flex-shrink-0 ${
                      clickable
                        ? "cursor-pointer hover:opacity-80 transition-opacity"
                        : ""
                    }`}
                  >
                    <span className="text-white font-medium text-sm whitespace-nowrap">
                      {parseFloat(token.balance).toFixed(2)} {token.symbol.replace(/^k/, '')}
                    </span>
                  </div>
                );
              })}
            </div>
            {finalSecondRow.length > 0 && (
              <div className="flex gap-2">
                {finalSecondRow.map((token, idx) => {
                  const priceComparison = priceComparisons[token.symbol];
                  const bgColor = token.symbol !== "USDC" && token.symbol !== "kUSD" && priceComparison
                    ? priceComparison === "up"
                      ? "bg-green-950/40 border-green-800/50"
                      : "bg-red-950/40 border-red-800/50"
                    : "bg-zinc-800/60 border-zinc-700/50";
                  const clickable = isClickable(token.symbol);

                  return (
                    <div
                      key={`${token.symbol}-row2-${idx}`}
                      onClick={() => handleTokenClick(token.symbol)}
                      className={`${bgColor} border rounded-lg px-3 py-2 flex items-center flex-shrink-0 ${
                        clickable
                          ? "cursor-pointer hover:opacity-80 transition-opacity"
                          : ""
                      }`}
                    >
                      <span className="text-white font-medium text-sm whitespace-nowrap">
                        {parseFloat(token.balance).toFixed(2)} {token.symbol.replace(/^k/, '')}
                      </span>
                    </div>
                  );
                })}
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

export default KTTokenBalances;

