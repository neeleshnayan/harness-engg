import { useQuery } from '@tanstack/react-query';
import { GraphQLClient, gql } from 'graphql-request';

interface MAVPPriceCurrent {
  price: string;
  lastUpdate: string;
  updateCount?: number;
}

interface MAVPPriceData {
  mavppriceCurrent: MAVPPriceCurrent | null;
}

export interface MAVPPriceUpdate {
  id: string;
  txHash: string;
  price: string;
  timestamp: string;
}

interface MAVPPriceHistoryData {
  mavppriceUpdates: MAVPPriceUpdate[];
}

const PRICE_QUERY = gql`
  query {
    mavppriceCurrent(id: "current") {
      price
      lastUpdate
      updateCount
    }
  }
`;

const PRICE_HISTORY_QUERY = gql`
  query {
    mavppriceUpdates(first: 1000, orderBy: timestamp, orderDirection: asc) {
      id
      txHash
      price
      timestamp
    }
  }
`;

const fetchMAVPPrice = async (subgraphUrl: string): Promise<MAVPPriceCurrent | null> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<MAVPPriceData>(PRICE_QUERY);
    return data.mavppriceCurrent;
  } catch (error) {
    console.error('Error fetching MAVP price from subgraph:', error);
    throw error;
  }
};

const fetchMAVPPriceHistory = async (subgraphUrl: string): Promise<MAVPPriceUpdate[]> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const data = await client.request<MAVPPriceHistoryData>(PRICE_HISTORY_QUERY);
    return data.mavppriceUpdates;
  } catch (error) {
    console.error('Error fetching MAVP price history from subgraph:', error);
    throw error;
  }
};

export const useMAVPPrice = (subgraphUrl?: string) => {
  return useQuery<MAVPPriceCurrent | null, Error>({
    queryKey: ['mavp-price', subgraphUrl],
    queryFn: () => {
      if (!subgraphUrl) {
        throw new Error('Subgraph URL is not configured');
      }
      return fetchMAVPPrice(subgraphUrl);
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 60 seconds
    staleTime: 30_000, // Data fresh for 30 seconds
    retry: 3, // Retry failed requests 3 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
  });
};

export const useMAVPPriceHistory = (subgraphUrl?: string) => {
  return useQuery<MAVPPriceUpdate[], Error>({
    queryKey: ['mavp-price-history', subgraphUrl],
    queryFn: () => {
      if (!subgraphUrl) {
        throw new Error('Subgraph URL is not configured');
      }
      return fetchMAVPPriceHistory(subgraphUrl);
    },
    enabled: !!subgraphUrl, // Only run query if subgraphUrl is available
    refetchInterval: 60_000, // Refresh every 1 minute (60 seconds)
    staleTime: 50_000, // Data fresh for 50 seconds
    retry: 3, // Retry failed requests 3 times
    retryDelay: (attemptIndex) => Math.min(1000 * 2 ** attemptIndex, 30000), // Exponential backoff
  });
};
