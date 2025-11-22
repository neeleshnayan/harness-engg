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
    case 'YEARN_WBTC':
      return 'yearn-strategy';
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
    case 'YEARN_WBTC':
      return 'yearnStrategyMetric';
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
    case 'YEARN_WBTC':
      return ''; // Yearn strategy uses its own entities, no filter needed on generic deposits/withdrawals if they aren't used the same way
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
  // Yearn specific
  totalBuySignals?: string;
  totalSellSignals?: string;
  totalUsdcSwapped?: string;
  totalWbtcSwapped?: string;
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

type SignalExecuted = {
  id: string;
  txHash: string;
  signalType: number;
  amountIn: string;
  amountOut: string;
  timestamp: string;
};

type MetricResult = {
  [key: string]: MetricData | null | Deposit[] | Withdrawal[] | SignalExecuted[] | any;
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  signalExecuteds?: SignalExecuted[];
};

const createQuery = (strategyName: StrategyName, withOwner: boolean) => {
  const metricId = getMetricId(strategyName);
  const metricField = getMetricFieldName(strategyName);

  if (strategyName === 'YEARN_WBTC') {
    return gql`
      query ${strategyName}Analytics {
        ${metricField}(id: "${metricId}") {
          totalDeposits
          totalWithdrawals
          mintedShares
          burnedShares
          uniqueDepositors
          uniqueWithdrawers
          totalBuySignals
          totalSellSignals
          totalUsdcSwapped
          totalWbtcSwapped
          lastUpdated
        }
        signalExecuteds(first: 1000, orderBy: timestamp, orderDirection: desc) {
          id
          txHash
          signalType
          amountIn
          amountOut
          timestamp
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
  }

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

    // if (strategyName === 'YEARN_WBTC') {
    //   return {
    //     ...data,
    //     deposits: [], 
    //     withdrawals: []
    //   };
    // }

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
export const useYearnWBTCSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('YEARN_WBTC', subgraphUrl, walletAddress);

