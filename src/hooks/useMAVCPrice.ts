import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';

interface MAVCPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
  strategy?: string;
}

export interface MAVCPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
  strategy?: string;
}

const PRICE_QUERY = gql`
  query {
    strategyPriceCurrent(id: "mavc-strategy-current") {
      price
      lastUpdate
      updateCount
      strategy
    }
  }
`;

const PRICE_HISTORY_QUERY = gql`
  query {
    strategyPriceUpdates(
      first: 1000
      where: { strategy: "MAVC" }
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

const fetchMAVCPrice = async (subgraphUrl: string): Promise<MAVCPriceCurrent | null> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceCurrent: MAVCPriceCurrent | null }>(PRICE_QUERY);
    return data.strategyPriceCurrent;
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    try {
      const fallbackQuery = gql`
        query {
          mavcpriceCurrent(id: "current") {
            price
            lastUpdate
            updateCount
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ mavcpriceCurrent: MAVCPriceCurrent | null }>(fallbackQuery);
      return fallbackData.mavcpriceCurrent;
    } catch (fallbackError) {
      console.error('Error fetching MAVC price from subgraph (both new and legacy failed):', error, fallbackError);
      return null; // Return null instead of throwing to prevent crashes
    }
  }
};

const fetchMAVCPriceHistory = async (subgraphUrl: string): Promise<MAVCPriceUpdate[]> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceUpdates: MAVCPriceUpdate[] }>(PRICE_HISTORY_QUERY);
    return data.strategyPriceUpdates || [];
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    try {
      const fallbackQuery = gql`
        query {
          mavcpriceUpdates(first: 1000, orderBy: timestamp, orderDirection: asc) {
            id
            txHash
            price
            timestamp
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ mavcpriceUpdates: MAVCPriceUpdate[] }>(fallbackQuery);
      return fallbackData.mavcpriceUpdates || [];
    } catch (fallbackError) {
      console.error('Error fetching MAVC price history from subgraph (both new and legacy failed):', error, fallbackError);
      return []; // Return empty array instead of throwing to prevent crashes
    }
  }
};

export const useMAVCPrice = (subgraphUrl?: string) => {
  return useQuery<MAVCPriceCurrent | null, Error>({
    queryKey: ['mavc-price', subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return null;
      }
      try {
        return await fetchMAVCPrice(subgraphUrl);
      } catch (error) {
        console.error('useMAVCPrice error:', error);
        return null; // Return null on error instead of throwing
      }
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 60 seconds
    staleTime: 30_000, // Data fresh for 30 seconds
    retry: false, // Don't retry since we handle errors gracefully
    refetchOnWindowFocus: false,
  });
};

export const useMAVCPriceHistory = (subgraphUrl?: string) => {
  return useQuery<MAVCPriceUpdate[], Error>({
    queryKey: ['mavc-price-history', subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return [];
      }
      try {
        return await fetchMAVCPriceHistory(subgraphUrl);
      } catch (error) {
        console.error('useMAVCPriceHistory error:', error);
        return []; // Return empty array on error instead of throwing
      }
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 1 minute (60 seconds)
    staleTime: 50_000, // Data fresh for 50 seconds
    retry: false, // Don't retry since we handle errors gracefully
    refetchOnWindowFocus: false,
  });
};
