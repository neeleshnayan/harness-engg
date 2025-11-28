import { kryptonPoolsSubgraphApi } from './api';

interface CachedPrice {
  price: number;
  timestamp: number; // Unix timestamp in milliseconds
}

export interface PoolRate {
  pair: string;
  rate: number;
}

interface PoolRateData {
  id: string;
  pool: string;
  blockNumber: string;
  tokenRates: string[];
  tokenPair: string;
  blockTimestamp: string;
}

interface SubgraphResponseLatest {
  data: {
    latestPoolRates: PoolRateData[];
  };
}

interface SubgraphResponseHistorical {
  data: {
    poolRates: PoolRateData[];
  };
}

// Mapping of pool addresses to token (non-kUSD token in the pool)
// Format: poolAddress -> tokenSymbol
// kUSD is always 1, so we only need to track the other token
// Addresses maintain their original casing for GraphQL queries
const POOL_TO_TOKEN: Record<string, string> = {
  '0x266D3085674B06ecaC9128AB7c7B29d8C495e88B': 'kEUR',
  '0x1E2f986761Db2d62C5b6C14c02Eb826C58AA44a4': 'kGBP',
  '0x3B5A2A4ea314eEDD5a45c9F0a6163dB60eB985d9': 'kAED',
  '0x347b207913954b1f2fd26a4e3aB0B82990F80d81': 'USDC',
};

// In-memory cache for pool prices
// Key format: "fromToken-toToken" (e.g., "kUSD-kEUR")
const priceCache: Map<string, CachedPrice> = new Map();

// In-memory cache for all pool rates
let cachedPoolRates: PoolRate[] | null = null;
let cachedPoolRatesTimestamp: number = 0;

// Track ongoing requests to prevent duplicate API calls
let pendingPoolRatesRequest: Promise<PoolRate[]> | null = null;

// Track pending requests for individual pool prices
// Key format: "fromToken-toToken", Value: Promise<number>
const pendingPriceRequests: Map<string, Promise<number>> = new Map();

// In-memory cache for closing pool rates (previous day's closing rate)
// Key format: "fromToken/toToken" (e.g., "kUSD/kEUR"), Value: CachedPrice
const closingPoolRateCache: Map<string, CachedPrice> = new Map();

// Track pending requests for closing pool rates
// Key format: "fromToken/toToken", Value: Promise<number>
const pendingClosingPoolRateRequests: Map<string, Promise<number>> = new Map();

// Cache duration: 1 hour in milliseconds
const CACHE_DURATION = 60 * 60 * 1000; // 1 hour

/**
 * Check if a cached timestamp is still valid (less than 1 hour old)
 */
function isCacheValid(timestamp: number): boolean {
  const now = Date.now();
  const age = now - timestamp;
  return age < CACHE_DURATION;
}

/**
 * Get cache key for a price pair
 */
function getCacheKey(fromToken: string, toToken: string): string {
  return `${fromToken}/${toToken}`;
}

/**
 * Extract exchange rate from tokenRates array
 * Returns the non-1 value, which represents amount of kUSD per 1 token
 * If tokenRates has only 1 value, use that. Else, pick the value that is not 1
 */
function extractRate(tokenRates: string[]): number {
  if (tokenRates.length === 0) {
    return 0;
  }

  if (tokenRates.length === 1) {
    return Number(tokenRates[0]) || 0;
  }

  if (tokenRates.length === 2) {
    // kUSD is always 1, so return the other value
    return (Number(tokenRates[0]) === 1) ? Number(tokenRates[1]) : Number(tokenRates[0]);
  }

  return 0;
}

/**
 * Fetch all pool rates from subgraph and convert to PoolRate format
 */
async function fetchAllPoolRatesFromSubgraph(): Promise<PoolRate[]> {
  // Get pool addresses from the map keys (maintains original casing)
  const poolAddresses = Object.keys(POOL_TO_TOKEN);
  // Format pool addresses for GraphQL query
  const poolAddressesList = poolAddresses.map(addr => `"${addr}"`).join(', ');
  const query = `
    query {
      latestPoolRates(
        where: {
          pool_in: [${poolAddressesList}]
        }
      ) {
        id
        pool
        blockNumber
        tokenRates
        tokenPair
        blockTimestamp
      }
    }
  `;

  try {
    const response = await kryptonPoolsSubgraphApi.post<SubgraphResponseLatest>('', {
      query,
    });

    const poolRates = response.data?.data?.latestPoolRates || [];
    const rates: PoolRate[] = [];

    // Create a lowercase lookup map for case-insensitive matching
    const poolToTokenLowercase: Record<string, string> = {};
    for (const [address, token] of Object.entries(POOL_TO_TOKEN)) {
      poolToTokenLowercase[address.toLowerCase()] = token;
    }

    // Convert pool rates to PoolRate format
    for (const poolRate of poolRates) {
      const poolAddress = poolRate.pool.toLowerCase();
      const token = poolToTokenLowercase[poolAddress];

      if (!token) {
        console.warn(`No token mapping found for pool ${poolAddress}`);
        continue;
      }

      // Extract rate: amount of kUSD per 1 token
      const usdPerToken = extractRate(poolRate.tokenRates);
      // Calculate inverse: amount of token per 1 kUSD
      const tokenPerUsd = 1 / usdPerToken;
      if (usdPerToken > 0) {
        rates.push({
          pair: `kUSD/${token}`,
          rate: usdPerToken, // USD per token
        });

        rates.push({
          pair: `${token}/kUSD`,
          rate: tokenPerUsd, // token per kUSD
        });

        // Cache both directions:
        // 1. kUSD-token: amount of kUSD per 1 token (e.g., 1.31238934 kUSD per 1 kGBP)
        const usdToTokenKey = getCacheKey('kUSD', token);
        priceCache.set(usdToTokenKey, {
          price: usdPerToken,
          timestamp: Date.now(),
        });

        // 2. token-kUSD: amount of token per 1 kUSD (e.g., 0.7619 kGBP per 1 kUSD)
        const tokenToUsdKey = getCacheKey(token, 'kUSD');
        priceCache.set(tokenToUsdKey, {
          price: tokenPerUsd,
          timestamp: Date.now(),
        });
      }
    }

    return rates;
  } catch (error) {
    console.error('Failed to fetch pool rates from subgraph:', error);
    throw error;
  }
}

async function fetchHistoricalPoolRatesFromSubgraph(): Promise<PoolRateData[]> {
  // Get pool addresses from the map keys (maintains original casing)
  const poolAddresses = Object.keys(POOL_TO_TOKEN);
  // Format pool addresses for GraphQL query
  const poolAddressesList = poolAddresses.map(addr => `"${addr}"`).join(', ');
  const query = `
    query {
      poolRates(
        where: {
          pool_in: [${poolAddressesList}],
        },
        orderBy: blockNumber,
        orderDirection: asc,
        first: 1000
      ) {
        id
        pool
        blockNumber
        blockTimestamp
        tokenRates
        tokenPair
      }
    }
  `;

  try {
    const response = await kryptonPoolsSubgraphApi.post<SubgraphResponseHistorical>('', {
      query,
    });

    return response.data?.data?.poolRates || [];
  } catch (error) {
      console.error('Failed to fetch closing pool rates from subgraph:', error);
      return [];
  }
}

/**
 * Strip the 'k' prefix from token symbol if present
 * tokenPair in subgraph response uses format like "USD/GBP" without 'k' prefix
 *
 * @param token - Token symbol (e.g., "kUSD" or "USD")
 * @returns Token without 'k' prefix (e.g., "USD")
 */
function stripKPrefix(token: string): string {
  return token.startsWith('k') ? token.substring(1) : token;
}

/**
 * Get the closing pool rate from the previous day
 * Uses cache and fetches historical data from subgraph if needed
 *
 * Note: The tokenPair in the subgraph response uses format like "USD/GBP" without the 'k' prefix,
 * so tokens with 'k' prefix (e.g., "kUSD", "kEUR") will be automatically converted.
 *
 * @param fromToken - Source token symbol (e.g., "kUSD" or "USD")
 * @param toToken - Destination token symbol (e.g., "kEUR" or "EUR")
 * @returns Promise resolving to the closing rate (number)
 */
export async function getClosingPoolRate(fromToken: string, toToken: string): Promise<number> {
  const cacheKey = getCacheKey(fromToken, toToken);
  // Strip 'k' prefix from tokens to match tokenPair format in subgraph response (e.g., "USD/GBP")
  const tokenPair = `${stripKPrefix(fromToken)}/${stripKPrefix(toToken)}`;
  const cached = closingPoolRateCache.get(cacheKey);

  // Check if we have a valid cached closing rate
  if (cached && isCacheValid(cached.timestamp)) {
    return cached.price;
  }

  // Check if there's already a pending request for this token pair
  const pendingRequest = pendingClosingPoolRateRequests.get(cacheKey);
  if (pendingRequest) {
    return pendingRequest;
  }

  // Create a new request promise
  const requestPromise = (async () => {
    try {
      // Fetch historical pool rates from subgraph
      const historicalRates = await fetchHistoricalPoolRatesFromSubgraph();

      // Filter rates where tokenPair matches (e.g., "USD/GBP" format without 'k' prefix)
      const poolRates = historicalRates.filter(
        (rate) => rate.tokenPair === tokenPair
      );

      if (poolRates.length === 0) {
        console.warn(`No historical rates found for token pair ${cacheKey} (matched as ${tokenPair} in subgraph)`);
        return 0;
      }

      // Get the first entry (oldest, since rates are ordered asc by blockNumber)
      const firstRate = poolRates[0];
      const closingRate = extractRate(firstRate.tokenRates);

      if (closingRate === 0) {
        console.warn(`No valid closing rate found for token pair ${cacheKey}`);
        return 0;
      }

      // Cache the closing rate
      closingPoolRateCache.set(cacheKey, {
        price: closingRate,
        timestamp: Date.now(),
      });

      console.log(`Closing rate for ${cacheKey}: ${closingRate}`);
      return closingRate;
    } catch (error) {
      console.error(`Failed to fetch closing pool rate for ${cacheKey}:`, error);

      // If we have a stale cache, return it as fallback
      if (cached) {
        console.warn(`Using stale cached closing rate for ${cacheKey}`);
        return cached.price;
      }

      throw error;
    } finally {
      // Remove from pending requests once done
      pendingClosingPoolRateRequests.delete(cacheKey);
    }
  })();

  // Store the pending request
  pendingClosingPoolRateRequests.set(cacheKey, requestPromise);

  return requestPromise;
}

/**
 * Get all pool rates
 * Fetches from subgraph if cache is stale or missing
 *
 * @returns Promise resolving to an array of pool rates
 */
export async function getAllPoolRates(): Promise<PoolRate[]> {
  // Check if we have valid cached rates
  if (cachedPoolRates && isCacheValid(cachedPoolRatesTimestamp)) {
    return cachedPoolRates;
  }

  // Check if there's already a pending request
  if (pendingPoolRatesRequest) {
    return pendingPoolRatesRequest;
  }

  // Create a new request promise
  const requestPromise = (async () => {
    try {
      const rates = await fetchAllPoolRatesFromSubgraph();

      // Update cache
      cachedPoolRates = rates;
      cachedPoolRatesTimestamp = Date.now();

      return rates;
    } catch (error) {
      console.error('Failed to fetch pool rates:', error);

      // If we have stale cache, return it as fallback
      if (cachedPoolRates) {
        console.warn('Using stale cached pool rates');
        return cachedPoolRates;
      }

      throw error;
    } finally {
      // Clear pending request
      pendingPoolRatesRequest = null;
    }
  })();

  // Store the pending request
  pendingPoolRatesRequest = requestPromise;

  return requestPromise;
}

/**
 * Get pool rate from cache or fetch all rates if needed
 * Returns the rate (amount of toToken per 1 fromToken)
 * Implements request deduplication to prevent multiple simultaneous API calls
 *
 * @param fromToken - Source token symbol (e.g., "kUSD")
 * @param toToken - Destination token symbol (e.g., "kEUR")
 * @returns Promise resolving to the rate (number)
 */
export async function getPoolRate(fromToken: string, toToken: string): Promise<number> {
  const cacheKey = getCacheKey(fromToken, toToken);
  const cached = priceCache.get(cacheKey);

  // Check if we have a valid cached price
  if (cached && isCacheValid(cached.timestamp)) {
    return cached.price;
  }

  // Check if there's already a pending request for this price pair
  const pendingRequest = pendingPriceRequests.get(cacheKey);
  if (pendingRequest) {
    // Return the existing promise instead of making a new request
    return pendingRequest;
  }

  // Create a new request promise
  const requestPromise = (async () => {
    try {
      // Fetch all pool rates (this will update the cache)
      // This ensures we only make one API call even if multiple getPoolRate calls are made
      await getAllPoolRates();

      // Check cache again after fetching
      const updatedCache = priceCache.get(cacheKey);
      if (updatedCache) {
        return updatedCache.price;
      }

      // Try to calculate cross-token rate using kUSD as intermediary
      // We need: fromToken/kUSD and kUSD/toToken, or their inverses
      const fromTokenToUsdKey = getCacheKey(fromToken, 'kUSD');
      const usdToToTokenKey = getCacheKey('kUSD', toToken);
      const usdToFromTokenKey = getCacheKey('kUSD', fromToken);
      const toTokenToUsdKey = getCacheKey(toToken, 'kUSD');

      const fromTokenToUsd = priceCache.get(fromTokenToUsdKey);
      const usdToToToken = priceCache.get(usdToToTokenKey);
      const usdToFromToken = priceCache.get(usdToFromTokenKey);
      const toTokenToUsd = priceCache.get(toTokenToUsdKey);

      let calculatedRate: number | null = null;

      // Case 1: fromToken/kUSD and kUSD/toToken
      if (fromTokenToUsd && isCacheValid(fromTokenToUsd.timestamp) &&
          usdToToToken && isCacheValid(usdToToToken.timestamp)) {
        // fromToken/kUSD * kUSD/toToken = fromToken/toToken
        calculatedRate = fromTokenToUsd.price * usdToToToken.price;
      }
      // Case 2: kUSD/fromToken and kUSD/toToken
      else if (usdToFromToken && isCacheValid(usdToFromToken.timestamp) &&
               usdToToToken && isCacheValid(usdToToToken.timestamp)) {
        // (kUSD/toToken) / (kUSD/fromToken) = fromToken/toToken
        calculatedRate = usdToToToken.price / usdToFromToken.price;
      }
      // Case 3: fromToken/kUSD and toToken/kUSD
      else if (fromTokenToUsd && isCacheValid(fromTokenToUsd.timestamp) &&
               toTokenToUsd && isCacheValid(toTokenToUsd.timestamp)) {
        // (fromToken/kUSD) / (toToken/kUSD) = fromToken/toToken
        calculatedRate = fromTokenToUsd.price / toTokenToUsd.price;
      }
      // Case 4: kUSD/fromToken and toToken/kUSD
      else if (usdToFromToken && isCacheValid(usdToFromToken.timestamp) &&
               toTokenToUsd && isCacheValid(toTokenToUsd.timestamp)) {
        // (1 / (kUSD/fromToken)) * (1 / (toToken/kUSD)) = fromToken/toToken
        calculatedRate = (1 / usdToFromToken.price) * (1 / toTokenToUsd.price);
      }

      if (calculatedRate !== null && calculatedRate > 0) {
        // Cache the calculated rate for future use
        priceCache.set(cacheKey, {
          price: calculatedRate,
          timestamp: Date.now(),
        });
        return calculatedRate;
      }

      console.warn(`No price found for ${fromToken}/${toToken} after fetching all rates`);
      return 0;
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
      pendingPriceRequests.delete(cacheKey);
    }
  })();

  // Store the pending request
  pendingPriceRequests.set(cacheKey, requestPromise);

  return requestPromise;
}

/**
 * Clear the entire price cache
 */
export function clearPriceCache(): void {
  priceCache.clear();
  cachedPoolRates = null;
  cachedPoolRatesTimestamp = 0;
  pendingPoolRatesRequest = null;
  pendingPriceRequests.clear();
  closingPoolRateCache.clear();
  pendingClosingPoolRateRequests.clear();
}

/**
 * Clear a specific price from cache
 */
export function clearCachedPrice(fromToken: string, toToken: string): void {
  const cacheKey = getCacheKey(fromToken, toToken);
  priceCache.delete(cacheKey);
  // Note: We don't clear the full pool rates cache here as it may be used by other functions
}

/**
 * Clear the pool rates cache
 */
export function clearOracleRatesCache(): void {
  cachedPoolRates = null;
  cachedPoolRatesTimestamp = 0;
  pendingPoolRatesRequest = null;
  pendingPriceRequests.clear();
}

/**
 * Get cache statistics (for debugging)
 */
export function getCacheStats(): {
  size: number;
  keys: string[];
  poolRatesCached: boolean;
} {
  return {
    size: priceCache.size,
    keys: Array.from(priceCache.keys()),
    poolRatesCached: cachedPoolRates !== null,
  };
}
