'use client';

/**
 * Rates Context - THE central state for all token rates 🎯
 *
 * Fetches once on mount, provides data to entire app.
 * No cache logic, no complexity - just React state!
 */

import React, { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { fetchRatesSummary, TokenRateInfo, RatesSummaryResponse, CURRENCY_SYMBOLS } from '@/lib/ratesApi';

export type PriceDirection = 'up' | 'down' | 'same';

interface RatesContextValue {
  // Data
  tokens: Record<string, TokenRateInfo>;

  // Status
  isLoading: boolean;
  error: string | null;
  lastUpdated: Date | null;

  // Actions
  refresh: () => Promise<void>;

  // Helpers
  getTokenRate: (symbol: string) => TokenRateInfo | undefined;
  getTokenDirection: (symbol: string) => PriceDirection;
  getTokenAddressToSymbol: () => Record<string, string>;
  calculateBalanceInUSD: (tokenBalances: any[]) => number;
  getOverallPriceChange: (tokenBalances: any[]) => { direction: PriceDirection; percentageChange: number };
}

const RatesContext = createContext<RatesContextValue | null>(null);

interface RatesProviderProps {
  children: ReactNode;
}

export function RatesProvider({ children }: RatesProviderProps) {
  const [tokens, setTokens] = useState<Record<string, TokenRateInfo>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const refresh = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await fetchRatesSummary();
      setTokens(data.tokens || {});
      setLastUpdated(new Date());
    } catch (err) {
      console.error('Failed to fetch rates summary:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch rates');
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Helper: Get token rate by symbol
  const getTokenRate = useCallback((symbol: string): TokenRateInfo | undefined => {
    return tokens[symbol];
  }, [tokens]);

  // Helper: Get price direction for a token
  const getTokenDirection = useCallback((symbol: string): PriceDirection => {
    const token = tokens[symbol];
    return token?.direction || 'same';
  }, [tokens]);

  // Helper: Build address -> symbol map
  const getTokenAddressToSymbol = useCallback((): Record<string, string> => {
    const map: Record<string, string> = {};
    for (const [symbol, token] of Object.entries(tokens)) {
      if (token.address) {
        map[token.address.toLowerCase()] = symbol;
      }
    }
    return map;
  }, [tokens]);

  // Helper: Calculate total balance in USD
  const calculateBalanceInUSD = useCallback((tokenBalances: any[]): number => {
    if (!tokenBalances || tokenBalances.length === 0) return 0;

    const addressMap = getTokenAddressToSymbol();
    let totalUSD = 0;

    for (const tb of tokenBalances) {
      const amount = parseFloat(tb?.amount ?? "0");
      if (isNaN(amount) || amount <= 0) continue;

      const tokenSymbol = tb?.token?.symbol;
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const symbol = tokenAddress ? addressMap[tokenAddress] : undefined;

      // USDC is 1:1 with USD
      if (tokenSymbol === 'USDC') {
        totalUSD += amount;
        continue;
      }

      // kUSD is 1:1 with USD
      if (symbol === 'kUSD') {
        totalUSD += amount;
        continue;
      }

      // Get rate for this token
      if (symbol && tokens[symbol]) {
        const rate = tokens[symbol].current_rate;
        if (rate && rate > 0) {
          // Rate is base_token per token, so multiply to get USD value
          totalUSD += amount * rate;
        }
      }
    }

    return totalUSD;
  }, [tokens, getTokenAddressToSymbol]);

  // Helper: Calculate overall price change weighted by balance
  const getOverallPriceChange = useCallback((tokenBalances: any[]): { direction: PriceDirection; percentageChange: number } => {
    if (!tokenBalances || tokenBalances.length === 0) {
      return { direction: 'same', percentageChange: 0 };
    }

    const addressMap = getTokenAddressToSymbol();
    let totalCurrentUSD = 0;
    let totalClosingUSD = 0;

    for (const tb of tokenBalances) {
      const amount = parseFloat(tb?.amount ?? "0");
      if (isNaN(amount) || amount <= 0) continue;

      const tokenSymbol = tb?.token?.symbol;
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const symbol = tokenAddress ? addressMap[tokenAddress] : undefined;

      // USDC - no rate change
      if (tokenSymbol === 'USDC') {
        totalCurrentUSD += amount;
        totalClosingUSD += amount;
        continue;
      }

      // kUSD - no rate change
      if (symbol === 'kUSD') {
        totalCurrentUSD += amount;
        totalClosingUSD += amount;
        continue;
      }

      // Other tokens - use rates
      if (symbol && tokens[symbol]) {
        const token = tokens[symbol];
        const currentRate = token.current_rate;
        const closingRate = token.closing_rate;

        if (currentRate && currentRate > 0) {
          totalCurrentUSD += amount * currentRate;
        }
        if (closingRate && closingRate > 0) {
          totalClosingUSD += amount * closingRate;
        } else if (currentRate && currentRate > 0) {
          // Use current as fallback if no closing
          totalClosingUSD += amount * currentRate;
        }
      }
    }

    const threshold = 0.01; // $0.01 threshold
    const diff = totalCurrentUSD - totalClosingUSD;

    let percentageChange = 0;
    if (totalClosingUSD > 0) {
      percentageChange = (diff / totalClosingUSD) * 100;
    }

    let direction: PriceDirection = 'same';
    if (Math.abs(diff) >= threshold) {
      direction = diff > 0 ? 'up' : 'down';
    }

    return { direction, percentageChange };
  }, [tokens, getTokenAddressToSymbol]);

  const value: RatesContextValue = {
    tokens,
    isLoading,
    error,
    lastUpdated,
    refresh,
    getTokenRate,
    getTokenDirection,
    getTokenAddressToSymbol,
    calculateBalanceInUSD,
    getOverallPriceChange,
  };

  return (
    <RatesContext.Provider value={value}>
      {children}
    </RatesContext.Provider>
  );
}

/**
 * Hook to use rates context - the ONLY thing components need! 🎉
 */
export function useRates(): RatesContextValue {
  const context = useContext(RatesContext);
  if (!context) {
    throw new Error('useRates must be used within a RatesProvider');
  }
  return context;
}

// Re-export for convenience
export { CURRENCY_SYMBOLS };
export type { TokenRateInfo };
