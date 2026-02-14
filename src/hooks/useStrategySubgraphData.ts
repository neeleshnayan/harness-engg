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
  // Token addresses from subgraph Strategy entity
  assetAddress?: string;
  targetTokenAddress?: string;
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

// Computed performance metrics derived from subgraph share price history
export type ComputedMetrics = {
  netApy: number;        // Annualized return based on share price appreciation (%)
  maxDrawdown: number;   // Maximum peak-to-trough decline in share price (%, negative)
  sharpeRatio: number;   // Risk-adjusted return (annualized)
};

type MetricResult = {
  strategyMetric: MetricData | null;
  strategySnapshots: Snapshot[];
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  signalExecuteds?: SignalExecuted[];
  priceUpdates?: { timestamp: string; price: string }[];
  computedMetrics: ComputedMetrics;
  // Legacy aliases for UI compatibility
  yearnWethStrategyMetric?: MetricData | null;
  yearnWethStrategySnapshots?: Snapshot[];
  snapshots: Snapshot[]; // Restored for component compatibility
};

/**
 * Compute Net APY, Max Drawdown, and Sharpe Ratio from share price time series.
 * Uses all events (signals, deposits, withdrawals) that carry a sharePrice.
 */
function computePerformanceMetrics(
  signals: { sharePrice?: string; timestamp: string }[],
  deposits: { sharePrice?: string; timestamp: string }[],
  withdrawals: { sharePrice?: string; timestamp: string }[],
): ComputedMetrics {
  const defaultMetrics: ComputedMetrics = { netApy: 0, maxDrawdown: 0, sharpeRatio: 0 };

  // Merge all events with a valid sharePrice into a single sorted time series
  const allEvents = [...(signals || []), ...(deposits || []), ...(withdrawals || [])];
  const priceSeries = allEvents
    .filter((e) => e.sharePrice && Number(e.sharePrice) > 0)
    .map((e) => ({ timestamp: Number(e.timestamp), price: Number(e.sharePrice) }))
    .sort((a, b) => a.timestamp - b.timestamp);

  if (priceSeries.length < 2) return defaultMetrics;

  // --- Net APY ---
  const first = priceSeries[0];
  const last = priceSeries[priceSeries.length - 1];
  const daysElapsed = (last.timestamp - first.timestamp) / 86400;
  let netApy = 0;
  if (daysElapsed > 0 && first.price > 0) {
    const totalReturn = last.price / first.price;
    if (daysElapsed >= 7) {
      // Enough history to annualize meaningfully
      netApy = (Math.pow(totalReturn, 365 / daysElapsed) - 1) * 100;
    } else {
      // Too little history — show simple (non-annualized) return to avoid absurd numbers
      netApy = (totalReturn - 1) * 100;
    }
    // Cap at ±999% to prevent display issues
    netApy = Math.max(-999, Math.min(999, netApy));
  }

  // --- Max Drawdown ---
  let peak = priceSeries[0].price;
  let maxDrawdown = 0;
  for (const point of priceSeries) {
    if (point.price > peak) peak = point.price;
    const drawdown = (peak - point.price) / peak;
    if (drawdown > maxDrawdown) maxDrawdown = drawdown;
  }
  // Express as negative percentage (e.g., -12.5)
  const maxDrawdownPct = -(maxDrawdown * 100);

  // --- Sharpe Ratio ---
  // Compute per-event returns and annualize
  const returns: number[] = [];
  for (let i = 1; i < priceSeries.length; i++) {
    if (priceSeries[i - 1].price > 0) {
      returns.push(priceSeries[i].price / priceSeries[i - 1].price - 1);
    }
  }

  let sharpeRatio = 0;
  if (returns.length >= 2) {
    const meanReturn = returns.reduce((sum, r) => sum + r, 0) / returns.length;
    const variance = returns.reduce((sum, r) => sum + (r - meanReturn) ** 2, 0) / (returns.length - 1);
    const stdDev = Math.sqrt(variance);

    if (stdDev > 0) {
      // Annualize: assume average interval between events
      const avgIntervalDays = daysElapsed / (priceSeries.length - 1);
      const periodsPerYear = avgIntervalDays > 0 ? 365 / avgIntervalDays : 1;
      const riskFreePerPeriod = 0.05 / periodsPerYear; // ~5% annual risk-free rate
      sharpeRatio = ((meanReturn - riskFreePerPeriod) / stdDev) * Math.sqrt(periodsPerYear);
    }
  }

  return {
    netApy: isFinite(netApy) ? netApy : 0,
    maxDrawdown: isFinite(maxDrawdownPct) ? maxDrawdownPct : 0,
    sharpeRatio: isFinite(sharpeRatio) ? sharpeRatio : 0,
  };
}

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
        asset
        targetToken
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
        sharePrice
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
      return { deposits: [], withdrawals: [], strategySnapshots: [], strategyMetric: null, snapshots: [], computedMetrics: { netApy: 0, maxDrawdown: 0, sharpeRatio: 0 } } as any;
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
        snapshots: [],
        computedMetrics: { netApy: 0, maxDrawdown: 0, sharpeRatio: 0 },
      } as unknown as MetricResult;
    }

    // Map V2 "strategy" entity fields to the UI-expected MetricData shape
    const rawStrategy = data.strategy;
    // Count unique depositors/withdrawers from actual owner addresses (depositCount is total txs, not unique)
    const uniqueDepositOwners = new Set((data.deposits || []).map((d: any) => d.owner?.toLowerCase())).size;
    const uniqueWithdrawOwners = new Set((data.withdrawals || []).map((w: any) => w.owner?.toLowerCase())).size;
    const mappedMetric: MetricData | null = rawStrategy ? {
      totalDeposits: rawStrategy.totalDeposited,
      totalWithdrawals: rawStrategy.totalWithdrawn,
      mintedShares: rawStrategy.sharesMinted,
      burnedShares: rawStrategy.sharesBurned,
      uniqueDepositors: uniqueDepositOwners,
      uniqueWithdrawers: uniqueWithdrawOwners,
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
      assetAddress: rawStrategy.asset,
      targetTokenAddress: rawStrategy.targetToken,
    } : null;

    // Map V2 "signals" to the UI-expected "signalExecuteds" shape
    const mappedSignals = (data.signals || []).map((s: any) => ({
      ...s,
      signalType: s.signalType,
    }));

    // Compute APY, Max Drawdown, Sharpe from share price history
    const computedMetrics = computePerformanceMetrics(
      data.signals || [],
      data.deposits || [],
      data.withdrawals || [],
    );

    return {
      strategyMetric: mappedMetric,
      yearnWethStrategyMetric: mappedMetric,
      strategySnapshots: [],
      yearnWethStrategySnapshots: [],
      snapshots: [],
      deposits: data.deposits || [],
      withdrawals: data.withdrawals || [],
      signalExecuteds: mappedSignals,
      computedMetrics,
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

