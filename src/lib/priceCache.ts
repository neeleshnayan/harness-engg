import { kryptonPoolsSubgraphApi } from './api';
import { K_TOKEN_ADDRESSES_LOWERCASE } from './kTokens';

interface CachedPrice {
  price: number;
  timestamp: number; // Unix timestamp in milliseconds
}

export interface PoolRate {
  pair: string;
  rate: number;
}

export interface HistoricalPricePoint {
  date: string; // ISO date string (YYYY-MM-DD)
  timestamp: number; // Unix timestamp in milliseconds
  price: number; // USD price of the token
}

export enum PriceChangeDirection {
  UP = "UP",
  DOWN = "DOWN",
  SAME = "SAME"
}

export interface PriceChangeInfo {
  direction: PriceChangeDirection;
  percentageChange: number;
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

interface ClosingPoolRateHistory {
  id: string;
  blockNumber: string;
  blockTimestamp: string;
  history: {
    id: string;
    tokenPair: string;
    pool: string;
    blockTimestamp: string;
    blockNumber: string;
    tokenRates: string[];
  };
}

interface SubgraphResponseClosingPoolRates {
  data: {
    closingPoolRateHistories: ClosingPoolRateHistory[];
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

// In-memory cache for all closing pool rates
let cachedClosingPoolRates: PoolRate[] | null = null;
let cachedClosingPoolRatesTimestamp: number = 0;

// Track ongoing requests to prevent duplicate API calls
let pendingPoolRatesRequest: Promise<PoolRate[]> | null = null;
let pendingClosingPoolRatesRequest: Promise<PoolRate[]> | null = null;

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

async function fetchClosingPoolRatesFromSubgraph(numEntries: number = 4): Promise<ClosingPoolRateHistory[]> {
  const query = `
    query {
      closingPoolRateHistories(
        first: ${numEntries},
        orderBy: blockNumber,
        orderDirection: desc
      ) {
        id
        blockNumber
        blockTimestamp
        history {
          id
          tokenPair
          pool
          blockTimestamp
          blockNumber
          tokenRates
        }
      }
    }
  `;

  try {
    const response = await kryptonPoolsSubgraphApi.post<SubgraphResponseClosingPoolRates>('', {
      query,
    });

    return response.data?.data?.closingPoolRateHistories || [];
  } catch (error) {
    console.error('Failed to fetch closing pool rates from subgraph:', error);
    return [];
  }
}

/**
 * Fetch all closing pool rates from subgraph and convert to PoolRate format
 */
async function fetchAllClosingPoolRatesFromSubgraph(numEntries: number = 4): Promise<PoolRate[]> {
  try {
    const closingRates = await fetchClosingPoolRatesFromSubgraph(numEntries);
    const rates: PoolRate[] = [];

    // Create a lowercase lookup map for case-insensitive matching
    const poolToTokenLowercase: Record<string, string> = {};
    for (const [address, token] of Object.entries(POOL_TO_TOKEN)) {
      poolToTokenLowercase[address.toLowerCase()] = token;
    }

    // Convert closing pool rates to PoolRate format
    for (const closingRateHistory of closingRates) {
      const poolRate = closingRateHistory.history;
      const poolAddress = poolRate.pool.toLowerCase();
      const token = poolToTokenLowercase[poolAddress];

      if (!token) {
        continue;
      }

      // Extract rate: amount of kUSD per 1 token
      const usdPerToken = extractRate(poolRate.tokenRates);
      // Calculate inverse: amount of token per 1 kUSD
      const tokenPerUsd = 1 / usdPerToken;

      if (usdPerToken > 0) {
        // Only add if we haven't already added this token pair
        // Since results are sorted desc, the first occurrence is the latest closing rate
        if (!rates.find(r => r.pair === `kUSD/${token}`)) {
          rates.push({
            pair: `kUSD/${token}`,
            rate: usdPerToken, // USD per token
          });

          rates.push({
            pair: `${token}/kUSD`,
            rate: tokenPerUsd, // token per kUSD
          });
        }
      }
    }

    return rates;
  } catch (error) {
    console.error('Failed to fetch all closing pool rates from subgraph:', error);
    throw error;
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
 * Get historical closing pool rates for a specific token
 * Fetches closing rates over time and formats them for charting
 *
 * @param tokenSymbol - Token symbol (e.g., "kEUR", "kGBP", "kAED")
 * @param numEntries - Number of historical entries to fetch (default: 1000)
 * @returns Promise resolving to array of HistoricalPricePoint sorted by date (oldest first)
 */
export async function getHistoricalClosingPoolRates(
  tokenSymbol: string,
  numEntries: number = 1000
): Promise<HistoricalPricePoint[]> {
  try {
    // Strip 'k' prefix to match tokenPair format in subgraph
    const tokenWithoutK = stripKPrefix(tokenSymbol);
    const tokenPair = `USD/${tokenWithoutK}`; // Format in subgraph: "USD/EUR"

    // Fetch closing pool rates from subgraph
    const closingRates = await fetchClosingPoolRatesFromSubgraph(numEntries);

    // Get pool address for this token to match
    const poolAddress = Object.entries(POOL_TO_TOKEN).find(
      ([_, symbol]) => symbol === tokenSymbol
    )?.[0];

    if (!poolAddress) {
      console.warn(`No pool address found for token ${tokenSymbol}`);
      return [];
    }

    // Filter and map historical data
    const historicalData: HistoricalPricePoint[] = [];

    for (const closingRateHistory of closingRates) {
      const poolRate = closingRateHistory.history;

      // Match by pool address and tokenPair
      if (
        poolRate.pool.toLowerCase() === poolAddress.toLowerCase() &&
        poolRate.tokenPair === tokenPair
      ) {
        const rate = extractRate(poolRate.tokenRates);

        if (rate > 0) {
          // poolRate.blockTimestamp is in yyyy-mm-dd format, parse it directly
          // closingRateHistory.blockTimestamp is in seconds since epoch
          const dateString = poolRate.blockTimestamp; // Already in yyyy-mm-dd format

          // Parse the date string and convert to timestamp
          const date = new Date(dateString + 'T00:00:00Z'); // Add time to ensure UTC parsing
          const timestamp = date.getTime();

          historicalData.push({
            date: dateString,
            timestamp: timestamp,
            price: rate, // USD per token
          });
        }
      }
    }

    // Sort by date (oldest first) and remove duplicates by date (keep first occurrence)
    const uniqueByDate = new Map<string, HistoricalPricePoint>();
    for (const point of historicalData.sort((a, b) => a.timestamp - b.timestamp)) {
      if (!uniqueByDate.has(point.date)) {
        uniqueByDate.set(point.date, point);
      }
    }

    const sortedHistorical = Array.from(uniqueByDate.values()).sort((a, b) => a.timestamp - b.timestamp);

    // Fetch current pool rate and add it as the last data point
    try {
      const currentRate = await getPoolRate("kUSD", tokenSymbol);
      if (currentRate > 0) {
        const now = Date.now();
        const today = new Date(now);
        const todayDateString = today.toISOString().split('T')[0];

        // Check if today's date already exists in historical data
        const existingIndex = sortedHistorical.findIndex(p => p.date === todayDateString);

        if (existingIndex !== -1) {
          // If today's date exists, update it with the current rate (which is more up-to-date than closing rate)
          sortedHistorical[existingIndex] = {
            date: todayDateString,
            timestamp: now,
            price: currentRate, // USD per token
          };
        } else {
          // If today's date doesn't exist, add the current rate as the last data point
          sortedHistorical.push({
            date: todayDateString,
            timestamp: now,
            price: currentRate, // USD per token
          });
        }
      }
    } catch (error) {
      console.warn(`Failed to fetch current pool rate for ${tokenSymbol}:`, error);
      // Continue without current rate if it fails
    }

    // Return sorted by timestamp (oldest to newest)
    return sortedHistorical.sort((a, b) => a.timestamp - b.timestamp);
  } catch (error) {
    console.error(`Failed to fetch historical closing pool rates for ${tokenSymbol}:`, error);
    return [];
  }
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
export async function getClosingPoolRate(fromToken: string, toToken: string, numEntries: number = 4): Promise<number> {
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
      // Fetch closing pool rates from subgraph (already sorted desc by blockNumber)
      const closingRates = await fetchClosingPoolRatesFromSubgraph(numEntries);

      // Find the rate where tokenPair matches (e.g., "USD/GBP" format without 'k' prefix)
      // Since results are sorted desc, the first match will be the latest closing rate
      const matchingRate = closingRates.find(
        (rate) => rate.history.tokenPair === tokenPair
      );

      if (!matchingRate) {
        console.warn(`No closing rate found for token pair ${cacheKey} (matched as ${tokenPair} in subgraph)`);
        return 0;
      }

      const closingRate = extractRate(matchingRate.history.tokenRates);

      if (closingRate === 0) {
        console.warn(`No valid closing rate found for token pair ${cacheKey}`);
        return 0;
      }

      // Cache the closing rate
      closingPoolRateCache.set(cacheKey, {
        price: closingRate,
        timestamp: Date.now(),
      });

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
 * Get all closing pool rates
 * Fetches from subgraph if cache is stale or missing
 * Internal function used by haveRatesAppreciated
 *
 * @returns Promise resolving to an array of closing pool rates
 */
async function getAllClosingPoolRates(numEntries: number = 4): Promise<PoolRate[]> {
  // Check if we have valid cached closing rates
  if (cachedClosingPoolRates && isCacheValid(cachedClosingPoolRatesTimestamp)) {
    return cachedClosingPoolRates;
  }

  // Check if there's already a pending request
  if (pendingClosingPoolRatesRequest) {
    return pendingClosingPoolRatesRequest;
  }

  // Create a new request promise
  const requestPromise = (async () => {
    try {
      const rates = await fetchAllClosingPoolRatesFromSubgraph(numEntries);

      // Update cache
      cachedClosingPoolRates = rates;
      cachedClosingPoolRatesTimestamp = Date.now();

      return rates;
    } catch (error) {
      console.error('Failed to fetch closing pool rates:', error);

      // If we have stale cache, return it as fallback
      if (cachedClosingPoolRates) {
        console.warn('Using stale cached closing pool rates');
        return cachedClosingPoolRates;
      }

      throw error;
    } finally {
      // Clear pending request
      pendingClosingPoolRatesRequest = null;
    }
  })();

  // Store the pending request
  pendingClosingPoolRatesRequest = requestPromise;

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
 * Calculate total balance value in USD using given pool rates
 */
function calculateTotalBalanceInUSD(
  balance: any,
  poolRatesMap: { [key: string]: number }
): number {
  if (!balance || !Array.isArray(balance.tokenBalances) || balance.tokenBalances.length === 0) {
    return 0;
  }

  let totalInUSD = 0;

  // Get USDC balance (both are in USD)
  const usdc = balance.tokenBalances.find(
    (b: any) => b.token && b.token.symbol === 'USDC'
  );
  const usdcAmount = parseFloat(usdc?.amount ?? "0");
  totalInUSD += usdcAmount;

  // Get kToken balances and convert to USD
  for (const tb of balance.tokenBalances) {
    const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
    const kTokenSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;

    if (kTokenSymbol && parseFloat(tb.amount) > 0) {
      const kTokenAmount = parseFloat(tb.amount || "0");
      let usdValue = 0;

      if (kTokenSymbol === 'kUSD') {
        // kUSD is 1:1 with USD
        usdValue = kTokenAmount;
      } else {
        // Get the rate pair for this kToken
        const ratePair = `kUSD/${kTokenSymbol}`;
        const rate = poolRatesMap[ratePair];

        if (rate && rate > 0) {
          // Rate is already in format: USD/EUR = 1.16251899 means 1 EUR = 1.16251899 USD
          // So to convert kToken to USD: multiply by rate
          usdValue = kTokenAmount * rate;
        }
      }

      totalInUSD += usdValue;
    }
  }

  return totalInUSD;
}

/**
 * Compare total balance value between current and closing rates
 * Returns UP if current > closing, DOWN if current < closing, SAME if equal
 *
 * @param balance - Balance data object containing tokenBalances array
 * @returns Promise resolving to PriceChangeDirection enum
 */
export async function haveRatesAppreciated(balance: any): Promise<PriceChangeInfo> {
  try {
    // Fetch both current and closing pool rates
    const [currentRates, closingRates] = await Promise.all([
      getAllPoolRates(),
      getAllClosingPoolRates(),
    ]);

    // Convert arrays to maps for easier lookup
    const currentRatesMap: { [key: string]: number } = {};
    currentRates.forEach((rate) => {
      currentRatesMap[rate.pair] = rate.rate;
    });

    const closingRatesMap: { [key: string]: number } = {};
    closingRates.forEach((rate) => {
      closingRatesMap[rate.pair] = rate.rate;
    });

    // Calculate total balance in USD using both rate sets
    const currentTotalUSD = calculateTotalBalanceInUSD(balance, currentRatesMap);
    const closingTotalUSD = calculateTotalBalanceInUSD(balance, closingRatesMap);

    // Compare with small threshold to handle floating point precision
    const threshold = 0.01; // $0.01 threshold
    const diff = currentTotalUSD - closingTotalUSD;

    // Calculate percentage change
    let percentageChange = 0;
    if (closingTotalUSD > 0) {
      percentageChange = (diff / closingTotalUSD) * 100;
    }

    let direction: PriceChangeDirection;
    if (Math.abs(diff) < threshold) {
      direction = PriceChangeDirection.SAME;
    } else if (diff > 0) {
      direction = PriceChangeDirection.UP;
    } else {
      direction = PriceChangeDirection.DOWN;
    }

    return {
      direction,
      percentageChange
    };
  } catch (error) {
    console.error('Failed to compare rates appreciation:', error);
    // Return SAME on error to avoid showing incorrect indicators
    return {
      direction: PriceChangeDirection.SAME,
      percentageChange: 0
    };
  }
}

