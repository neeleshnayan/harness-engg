import { useQuery } from '@tanstack/react-query';
import { gql, GraphQLClient } from 'graphql-request';
import { StrategyName } from './useStrategyConfig';

// Types matching V2 subgraph schema (Strategy entity)
type MetricData = {
  totalDeposits: string;
  totalWithdrawals: string;
  mintedShares: string;
  burnedShares: string;
  uniqueDepositors: number;
  uniqueWithdrawers: number;
  lastUpdated: string;
  totalBuySignals?: string;
  totalSellSignals?: string;
  totalAssetSwapped?: string;
  totalTargetSwapped?: string;
  // Legacy mappings for UI compatibility
  totalUsdcSwapped?: string;
  totalWethSwapped?: string;
  currentAum?: string;
  currentSupply?: string;
  lastSharePrice?: string;
  lastTargetPrice?: string;
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
  targetPrice: string;
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
  priceUpdates?: { timestamp: string; price: string }[];
  // Legacy aliases for UI compatibility
  yearnWethStrategyMetric?: MetricData | null;
  yearnWethStrategySnapshots?: Snapshot[];
  snapshots: Snapshot[]; // Restored for component compatibility
};

const createQuery = (withOwner: boolean) => {
  // V2 subgraph: Strategy (not StrategyMetric), Signal (not SignalExecuted), no Snapshots/PriceUpdates
  // IDs are Bytes! (strategy address)

  const baseQuery = `
    query StrategyAnalytics($id: Bytes!, $strategyAddress: Bytes!${withOwner ? ', $owner: Bytes!' : ''}) {
      strategy(id: $id) {
        totalDeposited
        totalWithdrawn
        sharesMinted
        sharesBurned
        depositCount
        withdrawCount
        buySignalCount
        sellSignalCount
        totalAssetSwapped
        totalTargetSwapped
        currentAum
        currentSupply
        lastSharePrice
        lastTargetPrice
        lastUpdated
      }
      signals(
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
        targetPrice
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
        sharePrice
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
        sharePrice
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

    const data = await client.request<any>(query, variables);

    if (!data) {
      console.warn(`[useStrategySubgraphData] No data returned for ${strategyName}`);
      return {
        deposits: [],
        withdrawals: [],
        signalExecuteds: [],
        strategySnapshots: [],
        strategyMetric: null,
        snapshots: []
      } as unknown as MetricResult;
    }

    // Map V2 "strategy" entity fields to the UI-expected MetricData shape
    const rawStrategy = data.strategy;
    const mappedMetric: MetricData | null = rawStrategy ? {
      totalDeposits: rawStrategy.totalDeposited,
      totalWithdrawals: rawStrategy.totalWithdrawn,
      mintedShares: rawStrategy.sharesMinted,
      burnedShares: rawStrategy.sharesBurned,
      uniqueDepositors: rawStrategy.depositCount,
      uniqueWithdrawers: rawStrategy.withdrawCount,
      totalBuySignals: String(rawStrategy.buySignalCount),
      totalSellSignals: String(rawStrategy.sellSignalCount),
      totalAssetSwapped: rawStrategy.totalAssetSwapped,
      totalTargetSwapped: rawStrategy.totalTargetSwapped,
      totalUsdcSwapped: rawStrategy.totalAssetSwapped,
      totalWethSwapped: rawStrategy.totalTargetSwapped,
      currentAum: rawStrategy.currentAum,
      currentSupply: rawStrategy.currentSupply,
      lastSharePrice: rawStrategy.lastSharePrice,
      lastTargetPrice: rawStrategy.lastTargetPrice,
      lastUpdated: rawStrategy.lastUpdated,
    } : null;

    // Map V2 "signals" to the UI-expected "signalExecuteds" shape
    const mappedSignals = (data.signals || []).map((s: any) => ({
      ...s,
      signalType: s.signalType,
    }));

    return {
      strategyMetric: mappedMetric,
      yearnWethStrategyMetric: mappedMetric,
      strategySnapshots: [],
      yearnWethStrategySnapshots: [],
      snapshots: [],
      deposits: data.deposits || [],
      withdrawals: data.withdrawals || [],
      signalExecuteds: mappedSignals,
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

