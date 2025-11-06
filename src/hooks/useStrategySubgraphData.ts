import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';
import { StrategyName } from './useStrategyConfig';

const getMetricId = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavc-vault';
    case 'MAVP':
      return 'mavp-vault';
    case 'MAVC_YEARN':
      return 'mavc-yearn-vault';
    default:
      return '';
  }
};

const getMetricFieldName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavcvaultMetric';
    case 'MAVP':
      return 'mavpvaultMetric';
    case 'MAVC_YEARN':
      return 'mavcyearnVaultMetric';
    default:
      return '';
  }
};

const getFilterPattern = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return '-MAVC-';
    case 'MAVP':
      return '-MAVP-';
    case 'MAVC_YEARN':
      return 'MAVC-YEARN';
    default:
      return '';
  }
};

type MetricResult = {
  [key: string]: {
    totalDeposits: string;
    totalWithdrawals: string;
    mintedShares: string;
    burnedShares: string;
    uniqueDepositors: number;
    uniqueWithdrawers: number;
    lastUpdated: string;
  } | null;
  deposits: Array<{
    id: string;
    owner: string;
    assets: string;
    shares: string;
    timestamp: string;
  }>;
  withdrawals: Array<{
    id: string;
    owner: string;
    receiver: string;
    assets: string;
    shares: string;
    timestamp: string;
  }>;
};

const createQuery = (strategyName: StrategyName) => {
  const metricId = getMetricId(strategyName);
  const metricField = getMetricFieldName(strategyName);
  
  return gql`
    query ${strategyName}VaultAnalytics {
      ${metricField}(id: "${metricId}") {
        totalDeposits
        totalWithdrawals
        mintedShares
        burnedShares
        uniqueDepositors
        uniqueWithdrawers
        lastUpdated
      }
      deposits(first: 1000, orderBy: timestamp, orderDirection: desc) {
        id
        owner
        assets
        shares
        timestamp
      }
      withdrawals(first: 1000, orderBy: timestamp, orderDirection: desc) {
        id
        owner
        receiver
        assets
        shares
        timestamp
      }
    }
  `;
};

const fetchSubgraph = async (subgraphUrl: string, strategyName: StrategyName): Promise<MetricResult> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const query = createQuery(strategyName);
    const data = await client.request<MetricResult>(query);
    
    const filterPattern = getFilterPattern(strategyName);
    const filteredDeposits = data.deposits.filter(d => d.id.includes(filterPattern)).slice(0, 5);
    const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes(filterPattern)).slice(0, 5);
    
    return {
      ...data,
      deposits: filteredDeposits,
      withdrawals: filteredWithdrawals
    };
  } catch (error: any) {
    const errorMessage = error?.response?.errors?.[0]?.message || error?.message || 'Unknown error';
    throw new Error(`Subgraph query failed for ${strategyName}: ${errorMessage}`);
  }
};

export const useStrategySubgraphData = (strategyName: StrategyName, subgraphUrl?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', `${strategyName.toLowerCase()}-vault-analytics`, subgraphUrl],
    queryFn: () => fetchSubgraph(subgraphUrl!, strategyName),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

// Backward compatibility exports
export const useSubgraphData = (subgraphUrl?: string) => useStrategySubgraphData('MAVC', subgraphUrl);
export const useMAVPSubgraphData = (subgraphUrl?: string) => useStrategySubgraphData('MAVP', subgraphUrl);
export const useMAVCYearnSubgraphData = (subgraphUrl?: string) => useStrategySubgraphData('MAVC_YEARN', subgraphUrl);

