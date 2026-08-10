/**
 * Rates API - Simple wrapper for the rates-summary endpoint
 *
 * This is all we need! One fetch, done. 🚀
 */

import { kryptonWeb3Api } from './api';
import { subgraphApi } from './subgraphApi';

export interface TokenRateInfo {
  symbol: string;
  address: string;
  pool_address: string;
  decimals: number;
  base_token: 'kUSD' | 'USDC';
  current_rate: number | null;
  closing_rate: number | null;
  direction: 'up' | 'down' | 'same';
  percentage_change: number;
}

export interface RatesSummaryResponse {
  tokens: Record<string, TokenRateInfo>;
}

const DEFAULT_FALLBACK_RATES: Record<string, TokenRateInfo> = {
  kUSD: { symbol: 'kUSD', address: '', pool_address: '', decimals: 18, base_token: 'kUSD', current_rate: 1.0, closing_rate: 1.0, direction: 'same', percentage_change: 0 },
  kEUR: { symbol: 'kEUR', address: '', pool_address: '', decimals: 18, base_token: 'kUSD', current_rate: 1.08, closing_rate: 1.08, direction: 'same', percentage_change: 0 },
  kGBP: { symbol: 'kGBP', address: '', pool_address: '', decimals: 18, base_token: 'kUSD', current_rate: 1.27, closing_rate: 1.27, direction: 'same', percentage_change: 0 },
  USDC: { symbol: 'USDC', address: '', pool_address: '', decimals: 6, base_token: 'USDC', current_rate: 1.0, closing_rate: 1.0, direction: 'same', percentage_change: 0 },
};

/**
 * Fetch rates summary from backend — with graceful fallback on backend 500 error.
 */
export async function fetchRatesSummary(): Promise<RatesSummaryResponse> {
  try {
    const response = await kryptonWeb3Api.get<RatesSummaryResponse>('/subgraph/rates-summary');
    if (response.data && response.data.tokens) {
      return response.data;
    }
    return { tokens: DEFAULT_FALLBACK_RATES };
  } catch (error) {
    console.warn('Rates summary endpoint error — using fallback rates:', error);
    return { tokens: DEFAULT_FALLBACK_RATES };
  }
}

/**
 * Classify a token as k-token, USDC, or RWA.
 */
function tokenEcosystem(token: string): 'k' | 'usdc' | 'rwa' {
  if (token === 'USDC') return 'usdc';
  if (token.startsWith('k')) return 'k';
  return 'rwa';
}

/**
 * Get pool rate between two tokens.
 * Used by SwapModal and SendERC20Modal for rate calculations.
 *
 * For K-tokens, kUSD is the base token - so subgraph only has rates like kEUR/kUSD.
 * For cross-rates (like kEUR/kGBP), we calculate using:
 *   kEUR/kGBP = (kEUR/kUSD) / (kGBP/kUSD)
 *
 * For cross-ecosystem pairs (k-token <-> RWA), uses the universal estimate endpoint.
 *
 * @param fromToken - Source token (e.g., 'kUSD', 'kEUR', 'XAG', 'USDC')
 * @param toToken - Target token (e.g., 'kEUR', 'kGBP', 'NVDA', 'USDC')
 * @returns Rate (how much toToken per 1 fromToken) or 0 if not found
 */
export async function getPoolRate(fromToken: string, toToken: string): Promise<number> {
  if (fromToken === toToken) {
    return 1;
  }

  const fromEco = tokenEcosystem(fromToken);
  const toEco = tokenEcosystem(toToken);

  // Same ecosystem: k-token <-> k-token (including kUSD, USDC treated as k-ecosystem)
  const isSameEcosystem =
    (fromEco === 'k' || fromEco === 'usdc') && (toEco === 'k' || toEco === 'usdc');

  if (isSameEcosystem) {
    return getPoolRateSubgraph(fromToken, toToken);
  }

  // RWA <-> RWA: try subgraph first (USDC-base pairs), fallback to universal estimate if no rate
  if (fromEco === 'rwa' && toEco === 'rwa') {
    const subgraphRate = await getPoolRateSubgraph(fromToken, toToken);
    if (subgraphRate > 0) return subgraphRate;
    return getPoolRateUniversal(fromToken, toToken);
  }

  // Cross-ecosystem or involving RWA+USDC: use universal estimate
  return getPoolRateUniversal(fromToken, toToken);
}

/**
 * Get rate via subgraph pool-price (Balancer pools for k-tokens, works for same-ecosystem).
 */
async function getPoolRateSubgraph(fromToken: string, toToken: string): Promise<number> {
  const isKEco = (token: string) => token.startsWith('k') || token === 'USDC';
  const baseToken = isKEco(fromToken) && isKEco(toToken) ? 'kUSD' : 'USDC';

  try {
    // Case 1: One of the tokens IS the base token - direct rate
    if (fromToken === baseToken) {
      const tokenPair = `${toToken}/${baseToken}`;
      const result = await subgraphApi.getPoolPrice(tokenPair);
      return result.price > 0 ? result.price : 0;
    }

    if (toToken === baseToken) {
      const tokenPair = `${baseToken}/${fromToken}`;
      const result = await subgraphApi.getPoolPrice(tokenPair);
      return result.price;
    }

    // Case 2: Neither token is base - calculate cross-rate
    const [fromResult, toResult] = await Promise.all([
      subgraphApi.getPoolPrice(`${baseToken}/${fromToken}`),
      subgraphApi.getPoolPrice(`${baseToken}/${toToken}`),
    ]);

    const fromRate = fromResult.price;
    const toRate = toResult.price;

    if (fromRate > 0 && toRate > 0) {
      return fromRate / toRate;
    }

    return 0;
  } catch (error) {
    console.error(`Failed to get pool rate for ${fromToken}/${toToken}:`, error);
    return 0;
  }
}

/**
 * Get rate via universal estimate endpoint (for cross-ecosystem pairs).
 * Sends amount=1 to get the per-unit rate.
 */
async function getPoolRateUniversal(fromToken: string, toToken: string): Promise<number> {
  try {
    const response = await kryptonWeb3Api.post('/pools/universal/estimate', {
      from_token: fromToken,
      to_token: toToken,
      amount: 1.0,
      slippage_tolerance: 0.05,
    });
    const estimated = response.data?.estimated_output;
    if (estimated && estimated > 0) {
      return estimated;
    }
    return 0;
  } catch (error) {
    console.error(`Failed to get universal rate for ${fromToken}/${toToken}:`, error);
    return 0;
  }
}

/**
 * Currency symbols for display
 */
export const CURRENCY_SYMBOLS: Record<string, string> = {
  'USD': '$',
  'EUR': '€',
  'GBP': '£',
  'AED': 'د.إ',
  'INR': '₹',
  'GC': '',
  'XAG': '',
  'NVDA': '',
  'ETH': '',
  'kUSD': '$',
  'kEUR': '€',
  'kGBP': '£',
  'kAED': 'د.إ',
  'kINR': '₹',
  'USDC': '$',
};
