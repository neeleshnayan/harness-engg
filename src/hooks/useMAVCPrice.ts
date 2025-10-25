import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';

interface MAVCPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
}

interface MAVCPriceData {
  mavcpriceCurrent: MAVCPriceCurrent | null;
}

export interface MAVCPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
}

interface MAVCPriceHistoryData {
  mavcpriceUpdates: MAVCPriceUpdate[];
}

const PRICE_QUERY = gql`
  query {
    mavcpriceCurrent(id: "current") {
      price
      lastUpdate
      updateCount
    }
  }
`;

const PRICE_HISTORY_QUERY = gql`
  query {
    mavcpriceUpdates(first: 1000, orderBy: timestamp, orderDirection: asc) {
      id
      txHash
      price
      timestamp
    }
  }
`;

const fetchMAVCPrice = async (subgraphUrl: string): Promise<MAVCPriceCurrent | null> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<MAVCPriceData>(PRICE_QUERY);
    return data.mavcpriceCurrent;
  } catch (error) {
    console.error('Error fetching MAVC price from subgraph:', error);
    throw error;
  }
};

const fetchMAVCPriceHistory = async (subgraphUrl: string): Promise<MAVCPriceUpdate[]> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<MAVCPriceHistoryData>(PRICE_HISTORY_QUERY);
    return data.mavcpriceUpdates;
  } catch (error) {
    console.error('Error fetching MAVC price history from subgraph:', error);
    throw error;
  }
};

export const useMAVCPrice = (subgraphUrl?: string) => {
  return useQuery<MAVCPriceCurrent | null, Error>({
    queryKey: ['mavc-price', subgraphUrl],
    queryFn: () => {
      if (!subgraphUrl) {
        throw new Error('Subgraph URL is not configured');
      }
      return fetchMAVCPrice(subgraphUrl);
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 60 seconds
    staleTime: 30_000, // Data fresh for 30 seconds
    retry: 3, // Retry failed requests 3 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
  });
};

export const useMAVCPriceHistory = (subgraphUrl?: string) => {
  return useQuery<MAVCPriceUpdate[], Error>({
    queryKey: ['mavc-price-history', subgraphUrl],
    queryFn: () => {
      if (!subgraphUrl) {
        throw new Error('Subgraph URL is not configured');
      }
      return fetchMAVCPriceHistory(subgraphUrl);
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 1 minute (60 seconds)
    staleTime: 50_000, // Data fresh for 50 seconds
    retry: 3, // Retry failed requests 3 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
  });
};
