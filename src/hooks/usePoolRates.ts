import { useQuery } from '@tanstack/react-query';

const API_BASE = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'https://kryptonweb3-production.up.railway.app';

// ── Types ──────────────────────────────────────────────────────────

export interface TokenPrices {
    [symbol: string]: number;
}

export interface ClosingRate {
    id: string;
    pool: string;
    blockNumber: string;
    blockTimestamp: string; // date string like "2026-02-12"
    tokenPair: string;
    poolRate: number;
    oracleRate: number;
    deviation: number;
    tokenRates: string[];
}

export interface RateSummaryToken {
    symbol: string;
    address: string;
    pool_address: string;
    decimals: number;
    base_token: string;
    current_rate: number;
    closing_rate: number;
    direction: string;
    percentage_change: number;
}

// ── Hooks ──────────────────────────────────────────────────────────

/** Current prices for every token tracked by the liquidity pool subgraph. Polls every 15 s. */
export const useTokenPrices = () => {
    return useQuery<TokenPrices, Error>({
        queryKey: ['poolTokenPrices'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/subgraph/token-prices`);
            if (!res.ok) throw new Error(`Token prices fetch failed: ${res.status}`);
            const data = await res.json();
            return data.prices;
        },
        refetchInterval: 15_000,
        staleTime: 10_000,
        refetchOnWindowFocus: false,
    });
};

/** Daily closing pool rates for a specific pool address. */
export const usePoolClosingRates = (poolAddress?: string, limit = 60) => {
    return useQuery<ClosingRate[], Error>({
        queryKey: ['poolClosingRates', poolAddress, limit],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/subgraph/pool/${poolAddress}/closing-rates?limit=${limit}`);
            if (!res.ok) throw new Error(`Closing rates fetch failed: ${res.status}`);
            const data = await res.json();
            return data.rates;
        },
        enabled: Boolean(poolAddress),
        staleTime: 5 * 60_000,
        refetchOnWindowFocus: false,
    });
};

/** All-in-one rates summary — current rate, closing rate, direction, % change per token. */
export const useRatesSummary = () => {
    return useQuery<{ tokens: Record<string, RateSummaryToken> }, Error>({
        queryKey: ['ratesSummary'],
        queryFn: async () => {
            const res = await fetch(`${API_BASE}/subgraph/rates-summary`);
            if (!res.ok) throw new Error(`Rates summary fetch failed: ${res.status}`);
            return res.json();
        },
        refetchInterval: 30_000,
        staleTime: 15_000,
        refetchOnWindowFocus: false,
    });
};
