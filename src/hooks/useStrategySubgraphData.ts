import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';
import { StrategyName } from './useStrategyConfig';

const getMetricId = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return 'yearn-weth-strategy';
    default:
      return '';
  }
};

const getMetricFieldName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return 'yearnWethStrategyMetric';
    default:
      return '';
  }
};

const getFilterPattern = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return 'YEARN-WETH';
    default:
      return '';
  }
};

const getSnapshotFieldName = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'YEARN_WETH':
      return 'yearnWethStrategySnapshots';
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
  currentAum?: string;
};

type Deposit = {
  id: string;
  owner: string;
  assets: string;
  shares: string;
  timestamp: string;
  txHash: string;
};

type Withdrawal = {
  id: string;
  owner: string;
  receiver: string;
  assets: string;
  shares: string;
  timestamp: string;
  txHash: string;
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
  usdcBalance?: string;
  wethBalance?: string;
  wethPrice?: string;
  aum?: string;
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
          currentAum
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
          usdcBalance
          wethBalance
          wethPrice
          aum
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
          txHash
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
          txHash
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
          txHash
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
          txHash
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
        txHash
        owner
        assets
        shares
        timestamp
      }
      withdrawals(first: 1000, orderBy: timestamp, orderDirection: desc) {
        id
        txHash
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

    if (!data) {
      console.warn(`[useStrategySubgraphData] No data returned for ${strategyName}`);
      return {
        deposits: [],
        withdrawals: [],
        signalExecuteds: [],
        snapshots: [],
      } as unknown as MetricResult;
    }

    const filterPattern = getFilterPattern(strategyName);
    const rawDeposits = data.deposits || [];
    const rawWithdrawals = data.withdrawals || [];

    const filteredDeposits = rawDeposits.filter(d => d.id && d.id.includes(filterPattern));
    const filteredWithdrawals = rawWithdrawals.filter(w => w.id && w.id.includes(filterPattern));

    const signalFilterPattern = getSignalFilterPattern(strategyName);
    const rawSignals = data.signalExecuteds || [];
    const filteredSignals = signalFilterPattern
      ? rawSignals.filter(s => s.id && s.id.includes(signalFilterPattern))
      : rawSignals;

    const snapshotField = getSnapshotFieldName(strategyName);
    const snapshots = (data as any)[snapshotField] as Snapshot[] || [];

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

export const useYearnWETHSubgraphData = (subgraphUrl?: string, walletAddress?: string) => useStrategySubgraphData('YEARN_WETH', subgraphUrl, walletAddress);

