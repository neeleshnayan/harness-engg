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
  return '';
};

const createPriceQuery = (strategyName: StrategyName) => {
  return null;
};

const createPriceHistoryQuery = (strategyName: StrategyName) => {
  return null;
};

const fetchStrategyPrice = async (subgraphUrl: string, strategyName: StrategyName): Promise<StrategyPriceCurrent | null> => {
  return null;
};

const fetchStrategyPriceHistory = async (subgraphUrl: string, strategyName: StrategyName): Promise<StrategyPriceUpdate[]> => {
  return [];
};

export const useStrategyPrice = (strategyName: StrategyName, subgraphUrl?: string) => {
  return useQuery<StrategyPriceCurrent | null, Error>({
    queryKey: [`${strategyName.toLowerCase()}-price`, subgraphUrl],
    queryFn: async () => null,
    enabled: false,
    staleTime: Infinity,
  });
};

export const useStrategyPriceHistory = (strategyName: StrategyName, subgraphUrl?: string) => {
  return useQuery<StrategyPriceUpdate[], Error>({
    queryKey: [`${strategyName.toLowerCase()}-price-history`, subgraphUrl],
    queryFn: async () => [],
    enabled: false,
    staleTime: Infinity,
  });
};

// Backward compatibility type exports
export type MAVPPriceUpdate = StrategyPriceUpdate;
