import axios from 'axios';
import http from 'http';
import https from 'https';
import { parseErrorMessage } from './parseError';

// Main backend: login, auth, user, wallet. Always api.kryptonfund.com.
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'https://api.kryptonfund.com';
const KRYPTON_WEB3_API_BASE_URL = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'http://127.0.0.1:8001';

const httpAgent = new http.Agent({
  keepAlive: true,
});

const httpsAgent = new https.Agent({
  keepAlive: true,
});

export const kryptonWeb3Api = axios.create({
  baseURL: KRYPTON_WEB3_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  httpAgent: httpAgent,
  httpsAgent: httpsAgent,
  timeout: 600000,
});

// Subgraph API client for Krypton liquidity pools
const SUBGRAPH_API_BASE_URL = process.env.NEXT_PUBLIC_SUBGRAPH_API_URL || 'https://api.studio.thegraph.com/query/1714038/krypton-liquidity-pools-sepolia/version/latest';

export const kryptonPoolsSubgraphApi = axios.create({
  baseURL: SUBGRAPH_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Hedge Fund API Client
// Helper to ensure URL has protocol
const ensureProtocol = (url: string) => {
  if (!url) return url;
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return `https://${url}`;
  }
  return url;
};

// Hedge Fund API Client
const HEDGE_FUND_API_BASE_URL = ensureProtocol(process.env.NEXT_PUBLIC_HEDGE_FUND_API_URL || 'http://127.0.0.1:8001');

/** Hedge fund / Grow page subgraph (strategy metrics, deposits, signals). Use NEXT_PUBLIC_HEDGE_FUND_SUBGRAPH_API_URL or NEXT_PUBLIC_SUBGRAPH_URL to override. */
export const HEDGE_FUND_SUBGRAPH_URL =
  process.env.NEXT_PUBLIC_HEDGE_FUND_SUBGRAPH_API_URL ||
  process.env.NEXT_PUBLIC_SUBGRAPH_URL ||
  'https://api.studio.thegraph.com/query/121450/hedge-fund-v-2/version/latest';

export const hedgeFundApi = axios.create({
  baseURL: HEDGE_FUND_API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Create axios instance with base URL
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for authentication if needed
api.interceptors.request.use(
  (config) => {
    // You can add auth headers here if needed
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors here
    if (error.response?.status === 401) {
      // Handle unauthorized
      console.error('Unauthorized request');
    }
    return Promise.reject(error);
  }
);

// Helper function to check KYC status
export const checkKycStatus = async (userId: string) => {
  try {
    const response = await api.post(`/api/v1/kyc/check-status/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Error checking KYC status:', error);
    throw error;
  }
};

// Helper function to get user info
export const getUserInfo = async (userId: string) => {
  try {
    const response = await api.get(`/api/v1/user/${userId}`);
    return response.data;
  } catch (error) {
    console.error('Error getting user info:', error);
    throw error;
  }
};

// Helper function to get token info
export const getTokenInfo = async (tokenAddress: string) => {
  try {
    const response = await api.get(`/api/v1/smarttoken/token_info/${tokenAddress}`);
    return response.data;
  } catch (error) {
    console.error('Error getting token info:', error);
    throw error;
  }
};

// Krypton Pay API Types
export type TokenName = 'kEUR' | 'kGBP' | 'kAED' | 'kUSD';

export interface DailyPriceHistoryParams {
  lookback_days?: number; // 1-365, default 30
  debug?: boolean; // Include debug info
}

export interface DailyPriceHistoryDataPoint {
  date: string; // YYYY-MM-DD format
  price: number; // Token price in USD
}

export interface DailyPriceHistoryResponse {
  token: TokenName;
  lookback_days: number;
  count: number;
  data: DailyPriceHistoryDataPoint[];
  debug_info?: {
    total_records: number;
    filtered_records: number;
    target_pair: string;
  };
}

export interface SwapRequest {
  from_token: string; // Source token symbol (EUR, kUSD, etc.)
  to_token: string; // Destination token symbol
  amount: number; // Amount of from_token to swap
  wallet_username: string; // Username of the swapper
  slippage_tolerance?: number; // Max allowed price impact (default 0.05 = 5%)
  min_amount_out?: number; // Manual minimum output override
}

export interface SwapResponse {
  status: 'submitted' | 'error';
  route?: string; // e.g., "EUR -> USD"
  estimated_output?: number;
  min_amount_out?: number;
  user_address?: string;
  transaction_id?: string;
  data?: {
    id: string;
    state: string;
  };
  detail?: string; // Error message
  message?: string; // Error message
}

/**
 * Get daily price history for a Krypton Pay token
 *
 * @param tokenName - Token name: kEUR, kGBP, kAED, kUSD
 * @param params - Optional parameters (lookback_days, debug)
 * @returns Promise resolving to daily price history response
 */
export const getDailyPriceHistory = async (
  tokenName: TokenName,
  params?: DailyPriceHistoryParams
): Promise<DailyPriceHistoryResponse> => {
  try {
    const { lookback_days, debug } = params || {};
    const queryParams = new URLSearchParams();

    if (lookback_days !== undefined) {
      queryParams.append('lookback_days', lookback_days.toString());
    }
    if (debug !== undefined) {
      queryParams.append('debug', debug.toString());
    }

    const queryString = queryParams.toString();
    const url = `/subgraph/token/${tokenName}/daily-prices${queryString ? `?${queryString}` : ''}`;

    const response = await kryptonWeb3Api.get<DailyPriceHistoryResponse>(url);
    return response.data;
  } catch (error: unknown) {
    console.error('Error getting daily price history:', error);
    throw new Error(parseErrorMessage(error, 'Failed to get daily price history'));
  }
};

/**
 * Execute a token swap
 *
 * @param swapRequest - Swap request parameters
 * @returns Promise resolving to swap response
 */
export const swap = async (swapRequest: SwapRequest): Promise<SwapResponse> => {
  try {
    const response = await kryptonWeb3Api.post<SwapResponse>('/pools/swap', swapRequest);
    return response.data;
  } catch (error: unknown) {
    console.error('Error executing swap:', error);
    throw new Error(parseErrorMessage(error, 'Failed to execute swap'));
  }
};

export default api;
