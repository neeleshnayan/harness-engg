import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';

interface MAVPPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
  strategy?: string;
}

export interface MAVPPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
  strategy?: string;
}

const PRICE_QUERY = gql`
  query {
    strategyPriceCurrent(id: "mavp-strategy-current") {
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
      where: { strategy: "MAVP" }
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

const fetchMAVPPrice = async (subgraphUrl: string): Promise<MAVPPriceCurrent | null> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceCurrent: MAVPPriceCurrent | null }>(PRICE_QUERY);
    return data.strategyPriceCurrent;
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    try {
      const fallbackQuery = gql`
        query {
          mavppriceCurrent(id: "current") {
            price
            lastUpdate
            updateCount
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ mavppriceCurrent: MAVPPriceCurrent | null }>(fallbackQuery);
      return fallbackData.mavppriceCurrent;
    } catch (fallbackError) {
      console.error('Error fetching MAVP price from subgraph (both new and legacy failed):', error, fallbackError);
      return null; // Return null instead of throwing to prevent crashes
    }
  }
};

const fetchMAVPPriceHistory = async (subgraphUrl: string): Promise<MAVPPriceUpdate[]> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<{ strategyPriceUpdates: MAVPPriceUpdate[] }>(PRICE_HISTORY_QUERY);
    return data.strategyPriceUpdates || [];
  } catch (error: any) {
    // If new entity doesn't exist, try fallback to legacy entity
    try {
      const fallbackQuery = gql`
        query {
          mavppriceUpdates(first: 1000, orderBy: timestamp, orderDirection: asc) {
            id
            txHash
            price
            timestamp
          }
        }
      `;
      const client = new GraphQLClient(subgraphUrl);
      const fallbackData = await client.request<{ mavppriceUpdates: MAVPPriceUpdate[] }>(fallbackQuery);
      return fallbackData.mavppriceUpdates || [];
    } catch (fallbackError) {
      console.error('Error fetching MAVP price history from subgraph (both new and legacy failed):', error, fallbackError);
      return []; // Return empty array instead of throwing to prevent crashes
    }
  }
};

export const useMAVPPrice = (subgraphUrl?: string) => {
  return useQuery<MAVPPriceCurrent | null, Error>({
    queryKey: ['mavp-price', subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return null;
      }
      try {
        return await fetchMAVPPrice(subgraphUrl);
      } catch (error) {
        console.error('useMAVPPrice error:', error);
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

export const useMAVPPriceHistory = (subgraphUrl?: string) => {
  return useQuery<MAVPPriceUpdate[], Error>({
    queryKey: ['mavp-price-history', subgraphUrl],
    queryFn: async () => {
      if (!subgraphUrl) {
        return [];
      }
      try {
        return await fetchMAVPPriceHistory(subgraphUrl);
      } catch (error) {
        console.error('useMAVPPriceHistory error:', error);
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
