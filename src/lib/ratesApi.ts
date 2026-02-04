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

/**
 * Fetch rates summary from backend - THE ONLY API CALL WE NEED! 🔥
 */
export async function fetchRatesSummary(): Promise<RatesSummaryResponse> {
  const response = await kryptonWeb3Api.get<RatesSummaryResponse>('/subgraph/rates-summary');
  return response.data;
}

/**
 * Get pool rate between two tokens.
 * Used by SwapModal and SendERC20Modal for rate calculations.
 *
 * For K-tokens, kUSD is the base token - so subgraph only has rates like kEUR/kUSD.
 * For cross-rates (like kEUR/kGBP), we calculate using:
 *   kEUR/kGBP = (kEUR/kUSD) / (kGBP/kUSD)
 *
 * @param fromToken - Source token (e.g., 'kUSD', 'kEUR')
 * @param toToken - Target token (e.g., 'kEUR', 'kGBP')
 * @returns Rate (how much toToken per 1 fromToken) or 0 if not found
 */
export async function getPoolRate(fromToken: string, toToken: string): Promise<number> {
  if (fromToken === toToken) {
    return 1;
  }

  // Determine base token (kUSD for k-tokens, USDC for RWA tokens)
  const isKToken = (token: string) => token.startsWith('k') || token === 'USDC';
  const baseToken = isKToken(fromToken) && isKToken(toToken) ? 'kUSD' : 'USDC';

  try {
    // Case 1: One of the tokens IS the base token - direct rate
    if (fromToken === baseToken) {
      // fromToken is kUSD, toToken is kEUR => need kEUR/kUSD rate (how much kUSD per 1 kEUR)
      // But we want how much kEUR per 1 kUSD = 1 / (kEUR/kUSD)
      const tokenPair = `${toToken}/${baseToken}`;
      const result = await subgraphApi.getPoolPrice(tokenPair);
      return result.price > 0 ? 1 / result.price : 0;
    }

    if (toToken === baseToken) {
      // fromToken is kEUR, toToken is kUSD => need kEUR/kUSD rate
      const tokenPair = `${fromToken}/${baseToken}`;
      const result = await subgraphApi.getPoolPrice(tokenPair);
      return result.price;
    }

    // Case 2: Neither token is base - calculate cross-rate
    // For kEUR -> kGBP:
    //   kEUR/kUSD = how much kUSD per 1 kEUR
    //   kGBP/kUSD = how much kUSD per 1 kGBP
    //   kEUR/kGBP = kEUR/kUSD / kGBP/kUSD = how much kGBP per 1 kEUR
    const [fromResult, toResult] = await Promise.all([
      subgraphApi.getPoolPrice(`${fromToken}/${baseToken}`),
      subgraphApi.getPoolPrice(`${toToken}/${baseToken}`),
    ]);

    const fromRate = fromResult.price; // e.g., kEUR/kUSD
    const toRate = toResult.price;     // e.g., kGBP/kUSD

    if (fromRate > 0 && toRate > 0) {
      // Cross-rate: kEUR -> kGBP = (kEUR/kUSD) / (kGBP/kUSD)
      return fromRate / toRate;
    }

    return 0;
  } catch (error) {
    console.error(`Failed to get pool rate for ${fromToken}/${toToken}:`, error);
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
  'GC': '',
  'XAG': '',
  'NVDA': '',
  'ETH': '',
  'kUSD': '$',
  'kEUR': '€',
  'kGBP': '£',
  'kAED': 'د.إ',
  'USDC': '$',
};
