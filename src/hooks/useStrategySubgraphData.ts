import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';
import { StrategyName } from './useStrategyConfig';

// Specific types for the new generic schema
type MetricData = {
  totalDeposits: string;
  totalWithdrawals: string;
  mintedShares: string;
  burnedShares: string;
  uniqueDepositors: number;
  uniqueWithdrawers: number;
  lastUpdated: string;
  // Yearn/Generic specific mappings
  totalBuySignals?: string;
  totalSellSignals?: string;
  totalAssetSwapped?: string; // Mapped to totalUsdcSwapped
  totalTargetSwapped?: string; // Mapped to totalWethSwapped
  // Legacy mappings
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

type PriceUpdate = {
  id: string;
  strategy: string;
  pool: string;
  targetToken: string;
  price: string;
  timestamp: string;
};

export type Snapshot = {
  timestamp: string;
  totalDeposits: string;
  totalWithdrawals: string;
  mintedShares: string;
  burnedShares: string;
  // Yearn/Generic specific mappings
  totalBuySignals?: string;
  totalSellSignals?: string;
  totalAssetSwapped?: string;
  totalTargetSwapped?: string;
  assetBalance?: string;
  targetBalance?: string;
  targetPrice?: string;
  aum?: string;
  // Legacy mappings for UI compatibility
  usdcBalance?: string;
  wethBalance?: string;
  wethPrice?: string;
  totalUsdcSwapped?: string;
  totalWethSwapped?: string;
};

type MetricResult = {
  strategyMetric: MetricData | null;
  strategySnapshots: Snapshot[];
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  signalExecuteds?: SignalExecuted[];
  priceUpdates?: PriceUpdate[];
  // Legacy aliases for UI compatibility
  yearnWethStrategyMetric?: MetricData | null;
  yearnWethStrategySnapshots?: Snapshot[];
  snapshots: Snapshot[]; // Restored for component compatibility
};

const createQuery = (withOwner: boolean) => {
  // We now use generic entity names 'strategyMetric' and 'strategySnapshots'
  // ID is passed as variable $id (strategy address)

  const baseQuery = `
    query StrategyAnalytics($id: ID!, $strategyAddress: Bytes!${withOwner ? ', $owner: Bytes!' : ''}) {
      strategyMetric(id: $id) {
        totalDeposits
        totalWithdrawals
        mintedShares
        burnedShares
        uniqueDepositors
        uniqueWithdrawers
        totalBuySignals
        totalSellSignals
        totalAssetSwapped
        totalTargetSwapped
        currentAum
        lastUpdated
      }
      strategySnapshots(first: 100, orderBy: timestamp, orderDirection: desc, where: { strategy: $id }) {
        timestamp
        totalDeposits
        totalWithdrawals
        mintedShares
        burnedShares
        totalBuySignals
        totalSellSignals
        totalAssetSwapped
        totalTargetSwapped
        assetBalance
        targetBalance
        targetPrice
        aum
      }
      signalExecuteds(
        first: 1000
        orderBy: timestamp
        orderDirection: desc
        where: { strategy: $strategyAddress }
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
        where: { strategy: $strategyAddress${withOwner ? ', owner: $owner' : ''} }
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
        where: { strategy: $strategyAddress${withOwner ? ', owner: $owner' : ''} }
      ) {
        id
        txHash
        owner
        receiver
        assets
        shares
        timestamp
      }
      priceUpdates(
        first: 1000
        orderBy: timestamp
        orderDirection: desc
        where: { strategy: $strategyAddress }
      ) {
        id
        strategy
        pool
        targetToken
        price
        timestamp
      }
    }
  `;
  return gql`${baseQuery}`;
};

export const fetchSubgraph = async (subgraphUrl: string, strategyName: StrategyName, strategyAddress?: string, walletAddress?: string): Promise<MetricResult> => {
  try {
    const client = new GraphQLClient(subgraphUrl);
    // Use provided strategy address or fallback to known legacy default if needed (though we should avoid hardcoding now)
    // For YEARN_WETH, if no address provided, we default to the known one.
    // However, the best practice is to require it.

    // Default fallback for legacy calls if strategyAddress is missing (TEMPORARY)
    const targetAddress = strategyAddress || (strategyName === 'YEARN_WETH' ? '0x6e2671D1B22b39d1b72a6A4E8Ed55309489BD448' : '');

    if (!targetAddress) {
      console.warn(`[useStrategySubgraphData] No strategy address provided for ${strategyName}`);
      return { deposits: [], withdrawals: [], strategySnapshots: [], strategyMetric: null, snapshots: [] } as any;
    }

    const query = createQuery(!!walletAddress);
    const variables = {
      id: targetAddress.toLowerCase(),
      strategyAddress: targetAddress.toLowerCase(),
      ...(walletAddress ? { owner: walletAddress.toLowerCase() } : {})
    };

    const data = await client.request<MetricResult>(query, variables);

    if (!data) {
      console.warn(`[useStrategySubgraphData] No data returned for ${strategyName}`);
      return {
        deposits: [],
        withdrawals: [],
        signalExecuteds: [],
        priceUpdates: [],
        strategySnapshots: [],
        strategyMetric: null,
        snapshots: []
      } as unknown as MetricResult;
    }

    // Map generic fields to specific names expected by UI (YearnWETH)
    // strategyMetric -> yearnWethStrategyMetric
    const mappedMetric = data.strategyMetric ? {
      ...data.strategyMetric,
      totalUsdcSwapped: data.strategyMetric.totalAssetSwapped,
      totalWethSwapped: data.strategyMetric.totalTargetSwapped
    } : null;

    const mappedSnapshots = (data.strategySnapshots || []).map(s => ({
      ...s,
      usdcBalance: s.assetBalance,
      wethBalance: s.targetBalance,
      wethPrice: s.targetPrice,
      totalUsdcSwapped: s.totalAssetSwapped,
      totalWethSwapped: s.totalTargetSwapped
    }));

    return {
      ...data,
      yearnWethStrategyMetric: mappedMetric, // Legacy alias
      yearnWethStrategySnapshots: mappedSnapshots, // Legacy alias
      strategyMetric: mappedMetric,
      strategySnapshots: mappedSnapshots,
      snapshots: mappedSnapshots, // Restored for component compatibility
      // Deposits/etc are already generic
      deposits: data.deposits || [],
      withdrawals: data.withdrawals || [],
      signalExecuteds: data.signalExecuteds || [],
      priceUpdates: data.priceUpdates || []
    };
  } catch (error: any) {
    const errorMessage = error?.response?.errors?.[0]?.message || error?.message || 'Unknown error';
    throw new Error(`Subgraph query failed for ${strategyName}: ${errorMessage}`);
  }
};

export const useStrategySubgraphData = (strategyName: StrategyName, subgraphUrl?: string, strategyAddress?: string, walletAddress?: string) => {
  const enabled = Boolean(subgraphUrl && strategyAddress); // Require strategyAddress
  return useQuery<MetricResult, Error>({
    queryKey: ['subgraph', `${strategyName.toLowerCase()}-vault-analytics`, subgraphUrl, strategyAddress, walletAddress],
    queryFn: () => fetchSubgraph(subgraphUrl!, strategyName, strategyAddress, walletAddress),
    enabled,
    refetchInterval: enabled ? 30_000 : false,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
    placeholderData: (previousData) => previousData,
  });
};

// Update legacy hook to accept optional address
export const useYearnWETHSubgraphData = (subgraphUrl?: string, walletAddress?: string, strategyAddress?: string) =>
  useStrategySubgraphData('YEARN_WETH', subgraphUrl, strategyAddress, walletAddress);

