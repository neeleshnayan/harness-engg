import { web3Api } from './api';

interface CachedPrice {
  price: number;
  timestamp: number; // Unix timestamp in milliseconds
}

interface OracleRate {
  pair: string;
  rate: number;
  rate_wei: string;
}

interface CachedOracleRates {
  rates: OracleRate[];
  timestamp: number; // Unix timestamp in milliseconds
}

// In-memory cache for pool prices
// Key format: "fromToken-toToken" (e.g., "kUSD-kEUR")
const priceCache: Map<string, CachedPrice> = new Map();

// In-memory cache for oracle rates
let cachedOracleRates: CachedOracleRates | null = null;

// Track ongoing requests to prevent duplicate API calls for the same price pair
// Key format: "fromToken-toToken", Value: Promise<number>
const pendingRequests: Map<string, Promise<number>> = new Map();

// Cache duration: 1 hour in milliseconds
const CACHE_DURATION = 60 * 60 * 1000; // 1 hour

/**
 * Check if a cached price is still valid (less than 1 hour old)
 */
function isCacheValid(cachedPrice: CachedPrice): boolean {
  const now = Date.now();
  const age = now - cachedPrice.timestamp;
  return age < CACHE_DURATION;
}

/**
 * Get cache key for a price pair
 */
function getCacheKey(fromToken: string, toToken: string): string {
  return `${fromToken}-${toToken}`;
}

/**
 * Get price from cache or API
 * Returns the price (amount of toToken per 1 fromToken)
 * Implements request deduplication to prevent multiple simultaneous API calls for the same pair
 *
 * @param fromToken - Source token symbol (e.g., "kUSD")
 * @param toToken - Destination token symbol (e.g., "kEUR")
 * @returns Promise resolving to the price (number)
 */
export async function getPoolPrice(fromToken: string, toToken: string): Promise<number> {
  const cacheKey = getCacheKey(fromToken, toToken);
  const cached = priceCache.get(cacheKey);

  // Check if we have a valid cached price
  if (cached && isCacheValid(cached)) {
    return cached.price;
  }

  // Check if there's already a pending request for this price pair
  const pendingRequest = pendingRequests.get(cacheKey);
  if (pendingRequest) {
    // Return the existing promise instead of making a new request
    return pendingRequest;
  }

  // Create a new request promise
  const requestPromise = (async () => {
    try {
      const response = await web3Api.get(`/pools/price/${fromToken}/${toToken}`);
      let price = Number(response?.data?.price) || 0;

      // Validate price is in reasonable range (not a percentage or scaled incorrectly)
      // Exchange rates should typically be between 0.001 and 1000 for most currency pairs
      // If price seems too small (< 0.01) or too large (> 10000), log a warning
      if (price > 0 && (price < 0.01 || price > 10000)) {
        console.warn(`Unusual price detected for ${fromToken}/${toToken}: ${price}. This might indicate a format issue.`);
      }

      if (price > 0) {
        // Update cache with new price and timestamp
        priceCache.set(cacheKey, {
          price,
          timestamp: Date.now(),
        });
      }

      return price;
    } catch (error) {
      console.error(`Failed to fetch price for ${fromToken}/${toToken}:`, error);

      // If we have a stale cache, return it as fallback
      if (cached) {
        console.warn(`Using stale cached price for ${fromToken}/${toToken}`);
        return cached.price;
      }

      throw error;
    } finally {
      // Remove from pending requests once done (success or error)
      pendingRequests.delete(cacheKey);
    }
  })();

  // Store the pending request
  pendingRequests.set(cacheKey, requestPromise);

  return requestPromise;
}

/**
 * Get oracle rates from cache or API
 * Returns the latest oracle rates, fetching from API if cache is stale or missing
 *
 * @returns Promise resolving to an array of oracle rates
 */
export async function getOracleRates(): Promise<OracleRate[]> {
  // Check if we have valid cached oracle rates
  if (cachedOracleRates && isCacheValid({ price: 0, timestamp: cachedOracleRates.timestamp })) {
    return cachedOracleRates.rates;
  }

  // Fetch fresh oracle rates from API
  try {
    const response = await web3Api.get('/pools/oracle/rates');
    const rates = response?.data?.rates || [];

    // Validate rates structure
    if (!Array.isArray(rates)) {
      console.error('Invalid oracle rates format received from API');
      throw new Error('Invalid oracle rates format');
    }

    // Update cache with new rates and timestamp
    cachedOracleRates = {
      rates,
      timestamp: Date.now(),
    };

    return rates;
  } catch (error) {
    console.error('Failed to fetch oracle rates:', error);

    // If we have stale cache, return it as fallback
    if (cachedOracleRates) {
      console.warn('Using stale cached oracle rates');
      return cachedOracleRates.rates;
    }

    throw error;
  }
}

/**
 * Clear the entire price cache
 */
export function clearPriceCache(): void {
  priceCache.clear();
  pendingRequests.clear();
}

/**
 * Clear a specific price from cache
 */
export function clearCachedPrice(fromToken: string, toToken: string): void {
  const cacheKey = getCacheKey(fromToken, toToken);
  priceCache.delete(cacheKey);
  // Note: We don't clear pending requests here as they may still be in flight
  // The request will complete and update the cache, or fail gracefully
}

/**
 * Clear the oracle rates cache
 */
export function clearOracleRatesCache(): void {
  cachedOracleRates = null;
}

/**
 * Get cache statistics (for debugging)
 */
export function getCacheStats(): {
  size: number;
  keys: string[];
  oracleRatesCached: boolean;
} {
  return {
    size: priceCache.size,
    keys: Array.from(priceCache.keys()),
    oracleRatesCached: cachedOracleRates !== null,
  };
}
