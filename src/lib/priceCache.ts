import { web3Api } from './api';

interface CachedPrice {
  price: number;
  timestamp: number; // Unix timestamp in milliseconds
}

// In-memory cache for pool prices
// Key format: "fromToken-toToken" (e.g., "kUSD-kEUR")
const priceCache: Map<string, CachedPrice> = new Map();

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

  // Fetch fresh price from API
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
  }
}

/**
 * Clear the entire price cache
 */
export function clearPriceCache(): void {
  priceCache.clear();
}

/**
 * Clear a specific price from cache
 */
export function clearCachedPrice(fromToken: string, toToken: string): void {
  const cacheKey = getCacheKey(fromToken, toToken);
  priceCache.delete(cacheKey);
}

/**
 * Get cache statistics (for debugging)
 */
export function getCacheStats(): {
  size: number;
  keys: string[];
} {
  return {
    size: priceCache.size,
    keys: Array.from(priceCache.keys()),
  };
}

