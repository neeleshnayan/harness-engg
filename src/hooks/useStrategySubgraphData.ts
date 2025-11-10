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

type MetricData = {
  totalDeposits: string;
  totalWithdrawals: string;
  mintedShares: string;
  burnedShares: string;
  uniqueDepositors: number;
  uniqueWithdrawers: number;
  lastUpdated: string;
};

type Deposit = {
  id: string;
  owner: string;
  assets: string;
  shares: string;
  timestamp: string;
};

type Withdrawal = {
  id: string;
  owner: string;
  receiver: string;
  assets: string;
  shares: string;
  timestamp: string;
};

type MetricResult = {
  [key: string]: MetricData | null | Deposit[] | Withdrawal[] | any;
  deposits: Deposit[];
  withdrawals: Withdrawal[];
};

const createQuery = (strategyName: StrategyName, withOwner: boolean) => {
  const metricId = getMetricId(strategyName);
  const metricField = getMetricFieldName(strategyName);
  
  if (withOwner) {
    return gql`
      query ${strategyName}VaultAnalytics($owner: String!) {
        ${metricField}(id: "${metricId}") {
          totalDeposits
          totalWithdrawals
          mintedShares
          burnedShares
          uniqueDepositors
          uniqueWithdrawers
          lastUpdated
        }
        deposits(
          first: 1000
          where: { owner: $owner }
          orderBy: timestamp
          orderDirection: desc
        ) {
          id
          owner
          assets
          shares
          timestamp
        }
        withdrawals(
          first: 1000
          where: { owner: $owner }
          orderBy: timestamp
          orderDirection: desc
        ) {
          id
          owner
          receiver
          assets
          shares
          timestamp
        }
      }
    `;
  }
  
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

const fetchSubgraph = async (subgraphUrl: string, strategyName: StrategyName, walletAddress?: string): Promise<MetricResult> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    const query = createQuery(strategyName, !!walletAddress);
    const variables = walletAddress ? { owner: walletAddress.toLowerCase() } : {};
    const data = await client.request<MetricResult>(query, variables);
    
    const filterPattern = getFilterPattern(strategyName);
    const filteredDeposits = data.deposits.filter(d => d.id.includes(filterPattern));
    const filteredWithdrawals = data.withdrawals.filter(w => w.id.includes(filterPattern));
    
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

export const useStrategySubgraphData = (strategyName: StrategyName, subgraphUrl?: string, walletAddress?: string) => {
  const enabled = Boolean(subgraphUrl);
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', `${strategyName.toLowerCase()}-vault-analytics`, subgraphUrl, walletAddress],
    queryFn: () => fetchSubgraph(subgraphUrl!, strategyName, walletAddress),
    enabled,
    refetchInterval: enabled ? 5_000 : false,
    staleTime: 2_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

// Backward compatibility exports
export const useSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVC', subgraphUrl, walletAddress);
export const useMAVPSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVP', subgraphUrl, walletAddress);
export const useMAVCYearnSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVC_YEARN', subgraphUrl, walletAddress);

