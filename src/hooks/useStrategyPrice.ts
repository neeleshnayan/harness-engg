import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';
import { StrategyName } from './useStrategyConfig';

interface StrategyPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
  strategy?: string;
}

export interface StrategyPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
  strategy?: string;
}

const getStrategyPriceId = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavc-strategy-current';
    case 'MAVP':
      return 'mavp-strategy-current';
    case 'MAVC_YEARN':
      // Yearn might not have price oracle, return empty string
      return '';
    default:
      return '';
  }
};

const getLegacyPriceId = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'current';
    case 'MAVP':
      return 'current';
    default:
      return '';
  }
};

const getLegacyEntityName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavcpriceCurrent';
    case 'MAVP':
      return 'mavppriceCurrent';
    default:
      return '';
  }
};

const getLegacyUpdatesEntityName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavcpriceUpdates';
    case 'MAVP':
      return 'mavppriceUpdates';
    default:
      return '';
  }
};

const createPriceQuery = (strategyName: StrategyName) => {
  const priceId = getStrategyPriceId(strategyName);
  if (!priceId) return null; // MAVC_YEARN doesn't have price oracle
  
  return gql`
    query {
      strategyPriceCurrent(id: "${priceId}") {
        price
        lastUpdate
        updateCount
        strategy
      }
    }
  `;
};

const createPriceHistoryQuery = (strategyName: StrategyName) => {
  if (strategyName === 'MAVC_YEARN') return null; // Yearn doesn't have price oracle
  
  return gql`
    query {
      strategyPriceUpdates(
        first: 1000
        where: { strategy: "${strategyName}" }
        orderBy: timestamp
        orderDirection: asc
      ) {
        id
        txHash
        price
        timestamp
        strategy
      }
    }
  `;
};

const fetchStrategyPrice = async (subgraphUrl: string, strategyName: StrategyName): Promise<StrategyPriceCurrent | null> => {
  try {
    const query = createPriceQuery(strategyName);
    if (!query) return null; // MAVC_YEARN doesn't have price
    
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceCurrent: StrategyPriceCurrent | null }>(query);
    return data.strategyPriceCurrent;
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    if (strategyName === 'MAVC_YEARN') return null;
    
    try {
      const legacyEntity = getLegacyEntityName(strategyName);
      const legacyId = getLegacyPriceId(strategyName);
      const fallbackQuery = gql`
        query {
          ${legacyEntity}(id: "${legacyId}") {
            price
            lastUpdate
            updateCount
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ [key: string]: StrategyPriceCurrent | null }>(fallbackQuery);
      return fallbackData[legacyEntity];
    } catch (fallbackError) {
      return null;
    }
  }
};

const fetchStrategyPriceHistory = async (subgraphUrl: string, strategyName: StrategyName): Promise<StrategyPriceUpdate[]> => {
  try {
    const query = createPriceHistoryQuery(strategyName);
    if (!query) return []; // MAVC_YEARN doesn't have price history
    
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceUpdates: StrategyPriceUpdate[] }>(query);
    return data.strategyPriceUpdates || [];
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    if (strategyName === 'MAVC_YEARN') return [];
    
    try {
      const legacyEntity = getLegacyUpdatesEntityName(strategyName);
      const fallbackQuery = gql`
        query {
          ${legacyEntity}(first: 1000, orderBy: timestamp, orderDirection: asc) {
            id
            txHash
            price
            timestamp
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ [key: string]: StrategyPriceUpdate[] }>(fallbackQuery);
      return fallbackData[legacyEntity] || [];
    } catch (fallbackError) {
      return [];
    }
  }
};

export const useStrategyPrice = (strategyName: StrategyName, subgraphUrl?: string) => {
  return useQuery<StrategyPriceCurrent | null, Error>({
    queryKey: [`${strategyName.toLowerCase()}-price`, subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return null;
      }
      try {
        return await fetchStrategyPrice(subgraphUrl, strategyName);
      } catch (error) {
        return null;
      }
    },
    enabled: !!subgraphUrl && strategyName !== 'MAVC_YEARN', // Only run query if subgraphUrl is available and strategy has price oracle
    refetchInterval: 60_000, // Refresh every 60 seconds
    staleTime: 30_000, // Data fresh for 30 seconds
    retry: false, // Don't retry since we handle errors gracefully
    refetchOnWindowFocus: false,
  });
};

export const useStrategyPriceHistory = (strategyName: StrategyName, subgraphUrl?: string) => {
  return useQuery<StrategyPriceUpdate[], Error>({
    queryKey: [`${strategyName.toLowerCase()}-price-history`, subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return [];
      }
      try {
        return await fetchStrategyPriceHistory(subgraphUrl, strategyName);
      } catch (error) {
        return [];
      }
    },
    enabled: !!subgraphUrl && strategyName !== 'MAVC_YEARN', // Only run query if subgraphUrl is available and strategy has price oracle
    refetchInterval: 60_000, // Refresh every 1 minute (60 seconds)
    staleTime: 50_000, // Data fresh for 50 seconds
    retry: false, // Don't retry since we handle errors gracefully
    refetchOnWindowFocus: false,
  });
};

// Backward compatibility exports
export const useMAVCPrice = (subgraphUrl?: string) => useStrategyPrice('MAVC', subgraphUrl);
export const useMAVPPrice = (subgraphUrl?: string) => useStrategyPrice('MAVP', subgraphUrl);
export const useMAVCPriceHistory = (subgraphUrl?: string) => useStrategyPriceHistory('MAVC', subgraphUrl);
export const useMAVPPriceHistory = (subgraphUrl?: string) => useStrategyPriceHistory('MAVP', subgraphUrl);

// Backward compatibility type exports
export type MAVCPriceUpdate = StrategyPriceUpdate;
export type MAVPPriceUpdate = StrategyPriceUpdate;

