import { kryptonWeb3Api } from '@/lib/api';

// Response types for subgraph data
export interface PoolRateHistoryEntry {
  id: string;
  pool: string;
  blockNumber: string;
  blockTimestamp: string;
  tokenPair: string;
  rate: number | null;
  tokenRates: string[];
}

export interface PoolRateHistoryResponse {
  pool_address: string;
  count: number;
  rates: PoolRateHistoryEntry[];
}

export interface PoolBalanceHistoryEntry {
  id: string;
  pool: string;
  blockNumber: string;
  blockTimestamp: string;
  tokens: string[];
  balances: number[];
}

export interface PoolBalanceHistoryResponse {
  pool_address: string;
  count: number;
  balances: PoolBalanceHistoryEntry[];
}

export interface ClosingPoolRateEntry {
  id: string;
  pool: string;
  blockNumber: string;
  blockTimestamp: string;
  tokenPair: string;
  poolRate: number | null;
  oracleRate: number | null;
  deviation: number | null;
  tokenRates: string[];
}

export interface ClosingPoolRatesResponse {
  pool_address: string;
  count: number;
  rates: ClosingPoolRateEntry[];
}

export interface PoolBalancesLatestResponse {
  id: string;
  pool: string;
  blockNumber: string;
  blockTimestamp: string;
  tokens: string[];
  balances: number[];
}

export interface LatestPoolRate {
  id: string;
  pool: string;
  blockNumber: string;
  tokenPair: string;
  rate: number;
  tokenRates: string[];
}

export interface LatestPoolRatesResponse {
  rates: LatestPoolRate[];
}

// Subgraph API client
export const subgraphApi = {
  /**
   * Fetch historical pool rates for building price charts
   */
  async getPoolRateHistory(
    poolAddress: string,
    limit: number = 100,
    order: 'asc' | 'desc' = 'desc'
  ): Promise<PoolRateHistoryResponse> {
    const response = await kryptonWeb3Api.get(`/subgraph/pool/${poolAddress}/rate-history`, {
      params: { limit, order },
    });
    return response.data;
  },

  /**
   * Fetch historical pool balances
   */
  async getPoolBalanceHistory(
    poolAddress: string,
    limit: number = 100,
    order: 'asc' | 'desc' = 'desc'
  ): Promise<PoolBalanceHistoryResponse> {
    const response = await kryptonWeb3Api.get(`/subgraph/pool/${poolAddress}/balance-history`, {
      params: { limit, order },
    });
    return response.data;
  },

  /**
   * Fetch daily closing pool rates with oracle comparison
   */
  async getClosingPoolRates(
    poolAddress: string,
    limit: number = 30
  ): Promise<ClosingPoolRatesResponse> {
    const response = await kryptonWeb3Api.get(`/subgraph/pool/${poolAddress}/closing-rates`, {
      params: { limit },
    });
    return response.data;
  },

  /**
   * Fetch current pool balances from subgraph
   */
  async getPoolBalancesLatest(poolAddress: string): Promise<PoolBalancesLatestResponse> {
    const response = await kryptonWeb3Api.get(`/subgraph/pool/${poolAddress}/balances-latest`);
    return response.data;
  },

  /**
   * Fetch all latest pool rates
   */
  async getLatestPoolRates(): Promise<LatestPoolRatesResponse> {
    const response = await kryptonWeb3Api.get('/subgraph/latest-pool-rates');
    return response.data;
  },

  /**
   * Fetch pool price for a specific token pair
   */
  async getPoolPrice(tokenPair: string): Promise<{ token_pair: string; price: number }> {
    const response = await kryptonWeb3Api.get(`/subgraph/pool-price/${encodeURIComponent(tokenPair)}`);
    return response.data;
  },
};

