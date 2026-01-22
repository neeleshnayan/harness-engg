import { useQuery } from '@tanstack/react-query';
import { getDailyPriceHistory, DailyPriceHistoryResponse, DailyPriceHistoryParams } from '@/lib/api';

export type TokenName = 'kEUR' | 'kGBP' | 'kAED' | 'kUSD';

export interface UseKryptonPayPriceHistoryOptions extends DailyPriceHistoryParams {
  enabled?: boolean; // Whether the query should run automatically
  refetchInterval?: number; // Auto-refetch interval in milliseconds
}

/**
 * React hook for fetching daily price history for Krypton Pay tokens
 * 
 * @param tokenName - Token name: kEUR, kGBP, kAED, kUSD
 * @param options - Optional parameters (lookback_days, debug, enabled, refetchInterval)
 * @returns React Query result with price history data
 * 
 * @example
 * ```tsx
 * const { data, isLoading, error } = useKryptonPayPriceHistory('kEUR', {
 *   lookback_days: 90,
 *   enabled: true
 * });
 * ```
 */
export const useKryptonPayPriceHistory = (
  tokenName: TokenName,
  options?: UseKryptonPayPriceHistoryOptions
) => {
  const {
    lookback_days,
    debug,
    enabled = true,
    refetchInterval,
  } = options || {};

  return useQuery<DailyPriceHistoryResponse, Error>({
    queryKey: ['krypton-pay-price-history', tokenName, lookback_days, debug],
    queryFn: async () => {
      return await getDailyPriceHistory(tokenName, {
        lookback_days,
        debug,
      });
    },
    enabled: enabled && !!tokenName,
    staleTime: 5 * 60 * 1000, // 5 minutes - price data doesn't change frequently
    refetchInterval: refetchInterval,
    refetchOnWindowFocus: false, // Don't refetch when window regains focus
  });
};
