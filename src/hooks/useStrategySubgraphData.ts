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
    case 'YEARN_WETH':
      return 'yearn-weth-strategy';
    case 'YEARN_PAXG':
      return 'yearn-paxg-strategy';
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
    case 'YEARN_WETH':
      return 'yearnWethStrategyMetric';
    case 'YEARN_PAXG':
      return 'yearnPaxgStrategyMetric';
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
    case 'YEARN_WETH':
      return 'YEARN-WETH';
    case 'YEARN_PAXG':
      return 'YEARN-PAXG';
    default:
      return '';
  }
};

const getSnapshotFieldName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'mavcvaultSnapshots';
    case 'MAVP':
      return 'mavpvaultSnapshots';
    case 'MAVC_YEARN':
      return 'mavcyearnVaultSnapshots';
    case 'YEARN_WETH':
      return 'yearnWethStrategySnapshots';
    case 'YEARN_PAXG':
      return 'yearnPaxgStrategySnapshots';
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
  totalWethSwapped?: string;
  totalPaxgSwapped?: string;
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

export type Snapshot = {
  timestamp: string;
  totalDeposits: string;
  totalWithdrawals: string;
  mintedShares: string;
  burnedShares: string;
  // Yearn specific
  totalBuySignals?: string;
  totalSellSignals?: string;
  totalUsdcSwapped?: string;
  totalWethSwapped?: string;
  totalPaxgSwapped?: string;
};

type MetricResult = {
  [key: string]: MetricData | null | Deposit[] | Withdrawal[] | SignalExecuted[] | Snapshot[] | any;
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  signalExecuteds?: SignalExecuted[];
  snapshots: Snapshot[];
};

const getSignalFilterPattern = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return '-WETH-';
    case 'YEARN_PAXG':
      return '-PAXG-';
    default:
      return '';
  }
};

const createQuery = (strategyName: StrategyName, withOwner: boolean) => {
  const metricId = getMetricId(strategyName);
  const metricField = getMetricFieldName(strategyName);
  const snapshotField = getSnapshotFieldName(strategyName);

  if (strategyName === 'YEARN_WETH') {
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
          totalWethSwapped
          lastUpdated
        }
        ${snapshotField}(first: 100, orderBy: timestamp, orderDirection: desc) {
          timestamp
          totalDeposits
          totalWithdrawals
          mintedShares
          burnedShares
          totalBuySignals
          totalSellSignals
          totalUsdcSwapped
          totalWethSwapped
        }
        signalExecuteds(
          first: 1000
          orderBy: timestamp
          orderDirection: desc
        ) {
          id
          txHash
          signalType
          amountIn
          amountOut
          timestamp
        }
        deposits(
          first: 1000
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

  if (strategyName === 'YEARN_PAXG') {
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
          totalPaxgSwapped
          lastUpdated
        }
        ${snapshotField}(first: 100, orderBy: timestamp, orderDirection: desc) {
          timestamp
          totalDeposits
          totalWithdrawals
          mintedShares
          burnedShares
          totalBuySignals
          totalSellSignals
          totalUsdcSwapped
          totalPaxgSwapped
        }
        signalExecuteds(
          first: 1000
          orderBy: timestamp
          orderDirection: desc
        ) {
          id
          txHash
          signalType
          amountIn
          amountOut
          timestamp
        }
        deposits(
          first: 1000
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
        ${snapshotField}(first: 100, orderBy: timestamp, orderDirection: desc) {
          timestamp
          totalDeposits
          totalWithdrawals
          mintedShares
          burnedShares
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
      ${snapshotField}(first: 100, orderBy: timestamp, orderDirection: desc) {
        timestamp
        totalDeposits
        totalWithdrawals
        mintedShares
        burnedShares
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

    const signalFilterPattern = getSignalFilterPattern(strategyName);
    const filteredSignals = signalFilterPattern
      ? (data.signalExecuteds || []).filter(s => s.id.includes(signalFilterPattern))
      : (data.signalExecuteds || []);

    const snapshotField = getSnapshotFieldName(strategyName);
    const snapshots = data[snapshotField] as Snapshot[] || [];

    return {
      ...data,
      deposits: filteredDeposits,
      withdrawals: filteredWithdrawals,
      signalExecuteds: filteredSignals,
      snapshots: snapshots
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
    refetchInterval: enabled ? 30_000 : false,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

// Backward compatibility exports
export const useSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVC', subgraphUrl, walletAddress);
export const useMAVPSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVP', subgraphUrl, walletAddress);
export const useMAVCYearnSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('MAVC_YEARN', subgraphUrl, walletAddress);
export const useYearnWETHSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('YEARN_WETH', subgraphUrl, walletAddress);
export const useYearnPAXGSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('YEARN_PAXG', subgraphUrl, walletAddress);

