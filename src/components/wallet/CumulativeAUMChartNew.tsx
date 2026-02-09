import React, { useMemo, useState } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { TrendingUp, Activity, AlertCircle } from "lucide-react";
import { useQueries } from '@tanstack/react-query';
import { fetchSubgraph } from "@/hooks/useStrategySubgraphData";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const DEFAULT_SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_URL || '';

// ============================================================================
// Types
// ============================================================================

interface Strategy {
  id: string;
  name?: string;
  symbol?: string;
  address?: string;
  vault_address?: string;
  contract_address?: string;
  subgraph_url?: string;
  asset_decimals?: number;
  decimals?: number;
}

interface TokenBalance {
  amount: string;
  token: {
    symbol: string;
  };
}

interface BalanceData {
  tokenBalances?: TokenBalance[];
}

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  strategies?: Strategy[];
  balanceData?: BalanceData;
}

type TimescaleOption = "15m" | "1h" | "1d" | "30d" | "1y";

interface ChartDataPoint {
  timestamp: number;
  date: string;
  totalAUM: number;
  [strategyId: string]: number | string;
}

interface DepositEvent {
  timestamp: string;
  assets: string;
  strategyId: string;
}

interface WithdrawalEvent {
  timestamp: string;
  assets: string;
  strategyId: string;
}

// ============================================================================
// Constants
// ============================================================================

const TIMESCALE_OPTIONS: { value: TimescaleOption; label: string }[] = [
  { value: "15m", label: "Past 15 mins" },
  { value: "1h", label: "Past 1 hr" },
  { value: "1d", label: "Past 1 day" },
  { value: "30d", label: "Past 1 month" },
  { value: "1y", label: "Past 1 year" },
];

// ============================================================================
// Utility Functions
// ============================================================================

const getTimescaleSeconds = (timescale: TimescaleOption): number => {
  const now = Math.floor(Date.now() / 1000);
  const intervals = {
    "15m": 15 * 60,
    "1h": 60 * 60,
    "1d": 24 * 60 * 60,
    "30d": 30 * 24 * 60 * 60,
    "1y": 365 * 24 * 60 * 60,
  };
  return now - intervals[timescale];
};

const formatDate = (timestamp: number, timescale?: TimescaleOption): string => {
  const date = new Date(timestamp * 1000);

  if (timescale === "15m" || timescale === "1h") {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  }

  if (timescale === "1d") {
    return date.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  }

  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric'
  });
};

const formatAUM = (value: number): string => {
  if (!isFinite(value) || isNaN(value)) return '$0.00';

  const absValue = Math.abs(value);

  if (absValue >= 1_000_000) {
    return `$${(value / 1_000_000).toFixed(2)}M`;
  }

  if (absValue >= 1_000) {
    return `$${(value / 1_000).toFixed(2)}K`;
  }

  return `$${value.toFixed(2)}`;
};

const getStrategyAddress = (strategy: Strategy): string | null => {
  return strategy.address || strategy.vault_address || strategy.contract_address || null;
};

const getStrategyDecimals = (strategy: Strategy): number => {
  return strategy.asset_decimals ?? strategy.decimals ?? 6;
};

// ============================================================================
// Custom Tooltip Component
// ============================================================================

const CustomTooltip = ({ active, payload, strategies }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload as ChartDataPoint;
  if (!data) return null;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-sm font-bold text-green-400 mb-2">
        Total: {formatAUM(data.totalAUM)}
      </p>
      <div className="space-y-1 pt-2 border-t border-zinc-700/50">
        {strategies?.map((strategy: Strategy) => {
          const balance = data[strategy.id];
          if (typeof balance !== 'number' || balance <= 0) return null;

          return (
            <div key={strategy.id} className="flex items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-zinc-400"></div>
                <span className="text-zinc-300">{strategy.name || strategy.id}</span>
              </div>
              <span className="text-zinc-200 font-mono">{formatAUM(balance)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// Main Component
// ============================================================================

export const CumulativeAUMChartNew: React.FC<CumulativeAUMChartNewProps> = ({
  userWalletAddress,
  strategies = [],
  balanceData
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("1d");

  // Filter out invalid strategies
  const validStrategies = useMemo(() => {
    return strategies.filter(strategy => {
      const hasId = !!strategy.id;
      const hasAddress = !!getStrategyAddress(strategy);
      const hasSubgraph = !!strategy.subgraph_url || !!DEFAULT_SUBGRAPH_URL;
      return hasId && hasAddress && hasSubgraph;
    });
  }, [strategies]);

  // Fetch subgraph data for all valid strategies
  const strategyQueries = useQueries({
    queries: validStrategies.map(strategy => {
      const address = getStrategyAddress(strategy)!;
      const subgraphUrl = strategy.subgraph_url || DEFAULT_SUBGRAPH_URL;

      return {
        queryKey: ['strategy-aum', strategy.id, address, userWalletAddress],
        queryFn: () => fetchSubgraph(subgraphUrl, strategy.id, address, userWalletAddress),
        enabled: !!userWalletAddress && !!address && !!subgraphUrl,
        staleTime: 30_000,
        retry: 2,
      };
    })
  });

  const isLoading = strategyQueries.some(q => q.isLoading);
  const hasErrors = strategyQueries.some(q => q.isError);

  // Extract live balances from parent's balance data
  const liveBalances = useMemo(() => {
    if (!balanceData?.tokenBalances) return {};

    const balances: Record<string, number> = {};

    validStrategies.forEach(strategy => {
      const tokenBalance = balanceData.tokenBalances!.find(tb => {
        const symbol = tb.token.symbol?.toUpperCase();
        const strategySymbol = strategy.symbol?.toUpperCase();
        const strategyId = strategy.id?.toUpperCase();
        return symbol === strategySymbol || symbol === strategyId;
      });

      if (tokenBalance) {
        const amount = parseFloat(tokenBalance.amount);
        if (!isNaN(amount) && isFinite(amount)) {
          balances[strategy.id] = Math.max(0, amount);
        }
      }
    });

    return balances;
  }, [balanceData, validStrategies]);

  // Build chart data using price updates × user balances for true portfolio value
  const chartData = useMemo(() => {
    if (!userWalletAddress || validStrategies.length === 0) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Collect all price updates, deposits, and withdrawals
    interface PriceUpdateEvent {
      timestamp: number;
      price: number;
      strategyId: string;
    }

    const priceUpdates: PriceUpdateEvent[] = [];
    const deposits: DepositEvent[] = [];
    const withdrawals: WithdrawalEvent[] = [];

    strategyQueries.forEach((query, index) => {
      if (!query.data) return;

      const strategy = validStrategies[index];

      // Collect price updates
      (query.data.priceUpdates || []).forEach((p: any) => {
        const timestamp = Number(p.timestamp);
        const price = parseFloat(p.price);
        if (isFinite(timestamp) && isFinite(price) && timestamp >= timescaleStart) {
          priceUpdates.push({
            timestamp,
            price,
            strategyId: strategy.id
          });
        }
      });

      // Collect deposits (track shares, not assets)
      (query.data.deposits || []).forEach((d: any) => {
        deposits.push({
          timestamp: d.timestamp,
          assets: d.shares, // Use shares field (already BigDecimal from subgraph)
          strategyId: strategy.id
        });
      });

      // Collect withdrawals (track shares, not assets)
      (query.data.withdrawals || []).forEach((w: any) => {
        withdrawals.push({
          timestamp: w.timestamp,
          assets: w.shares, // Use shares field (already BigDecimal from subgraph)
          strategyId: strategy.id
        });
      });
    });

    // Get all unique price update timestamps and sort them
    const priceTimestamps = new Set<number>();
    priceUpdates.forEach(p => priceTimestamps.add(p.timestamp));
    const sortedPriceTimestamps = Array.from(priceTimestamps).sort((a, b) => a - b);

    if (sortedPriceTimestamps.length === 0) {
      // No price updates yet - use current balances as flat line
      const liveTotalValue = Object.values(liveBalances).reduce((sum, val) => {
        return isFinite(val) && !isNaN(val) ? sum + val : sum;
      }, 0);

      return [
        {
          timestamp: timescaleStart,
          date: formatDate(timescaleStart, selectedTimescale),
          totalAUM: liveTotalValue,
          ...liveBalances
        },
        {
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: liveTotalValue,
          ...liveBalances
        }
      ];
    }

    // Build portfolio value history
    const historicalData: ChartDataPoint[] = [];

    // For each price update timestamp, calculate portfolio value
    sortedPriceTimestamps.forEach(timestamp => {
      // Calculate user's share balance at this timestamp
      const shareBalances: Record<string, number> = {};

      validStrategies.forEach(strategy => {
        let balance = 0;

        // Replay all deposits/withdrawals up to this timestamp
        // Note: subgraph returns BigDecimal (already scaled), no division needed
        deposits
          .filter(d => d.strategyId === strategy.id && Number(d.timestamp) <= timestamp)
          .forEach(d => {
            const amount = parseFloat(d.assets); // Already BigDecimal from subgraph
            if (isFinite(amount) && !isNaN(amount)) {
              balance += amount;
            }
          });

        withdrawals
          .filter(w => w.strategyId === strategy.id && Number(w.timestamp) <= timestamp)
          .forEach(w => {
            const amount = parseFloat(w.assets); // Already BigDecimal from subgraph
            if (isFinite(amount) && !isNaN(amount)) {
              balance = Math.max(0, balance - amount);
            }
          });

        shareBalances[strategy.id] = balance;
      });

      // Calculate portfolio value at this timestamp
      const strategyValues: Record<string, number> = {};
      let totalPortfolioValue = 0;

      validStrategies.forEach((strategy, index) => {
        const userShares = shareBalances[strategy.id] || 0;
        if (userShares <= 0) return;

        const queryData = strategyQueries[index]?.data;
        if (!queryData) return;

        // Find the most recent snapshot at or before this timestamp
        const snapshots = (queryData.strategySnapshots || [])
          .filter((s: any) => Number(s.timestamp) <= timestamp)
          .sort((a: any, b: any) => Number(b.timestamp) - Number(a.timestamp));

        const snapshot = snapshots[0];

        if (snapshot) {
          // Calculate share price: sharePrice = AUM / totalShares
          const aum = parseFloat(snapshot.aum || '0');
          const mintedShares = parseFloat(snapshot.mintedShares || '0');
          const burnedShares = parseFloat(snapshot.burnedShares || '0');
          const totalShares = mintedShares - burnedShares;

          if (totalShares > 0 && isFinite(aum)) {
            const sharePrice = aum / totalShares;
            const value = userShares * sharePrice;

            if (isFinite(value) && !isNaN(value)) {
              strategyValues[strategy.id] = value;
              totalPortfolioValue += value;
            }
          }
        } else {
          // No snapshot available, use shares at face value (1:1 with USDC)
          strategyValues[strategy.id] = userShares;
          totalPortfolioValue += userShares;
        }
      });

      historicalData.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM: Math.max(0, totalPortfolioValue),
        ...strategyValues
      });
    });

    // Add current point with live balances
    const liveTotalValue = Object.values(liveBalances).reduce((sum, val) => {
      return isFinite(val) && !isNaN(val) ? sum + val : sum;
    }, 0);

    const lastPoint = historicalData[historicalData.length - 1];
    const shouldAddLivePoint = !lastPoint || (currentTime - lastPoint.timestamp > 60);

    if (shouldAddLivePoint) {
      historicalData.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveTotalValue,
        ...liveBalances
      });
    }

    return historicalData;
  }, [strategyQueries, liveBalances, validStrategies, selectedTimescale, userWalletAddress]);

  // Calculate stats
  const stats = useMemo(() => {
    if (chartData.length === 0) return null;

    const latest = chartData[chartData.length - 1];
    const first = chartData[0];
    const change = latest.totalAUM - first.totalAUM;
    const changePercent = first.totalAUM > 0 ? (change / first.totalAUM) * 100 : 0;

    return {
      current: isFinite(latest.totalAUM) ? latest.totalAUM : 0,
      start: isFinite(first.totalAUM) ? first.totalAUM : 0,
      change: isFinite(change) ? change : 0,
      changePercent: isFinite(changePercent) ? changePercent : 0,
      isPositive: change >= 0
    };
  }, [chartData]);

  const invalidStrategiesCount = strategies.length - validStrategies.length;

  // ============================================================================
  // Render States
  // ============================================================================

  if (isLoading) {
    return (
      <div className="bg-transparent bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-3xl p-8 shadow-2xl border border-white/10" style={{ backgroundImage: "url('/wallet-bg.svg')" }}>
        <Skeleton className="h-64 w-full bg-zinc-700/50 rounded-lg" />
      </div>
    );
  }

  if (chartData.length === 0 || !stats) {
    return (
      <div className="bg-transparent bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-white/10" style={{ backgroundImage: "url('/wallet-bg.svg')" }}>
        <div className="flex flex-col items-center justify-center py-12 text-zinc-500">
          <Activity className="w-8 h-8 mb-3 text-zinc-600" />
          <span className="text-sm font-medium">No portfolio data available</span>
          <span className="text-xs text-zinc-600 mt-1">
            {validStrategies.length === 0 ? 'No valid strategies configured' : 'Try selecting a different time period'}
          </span>
        </div>
        {hasErrors && (
          <div className="flex items-center justify-center mt-4 text-amber-500">
            <AlertCircle className="w-4 h-4 mr-2" />
            <span className="text-xs">Some data failed to load. Please try again.</span>
          </div>
        )}
      </div>
    );
  }

  // ============================================================================
  // Main Render
  // ============================================================================

  return (
    <div className="bg-transparent bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-white/10" style={{ backgroundImage: "url('/wallet-bg.svg')" }}>
      {/* Header */}
      <div className="mb-4 sm:mb-6">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4 mb-4">
          <div className="flex-1 w-full">
            <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Portfolio Performance
            </h3>
            <p className="text-white text-xs sm:text-sm mb-3 sm:mb-4">
              Total Assets Under Management Across All Strategies
            </p>
            <div className="flex items-center gap-3 mb-2">
              <div className="text-2xl sm:text-3xl font-bold text-green-400">
                {formatAUM(stats.current)}
              </div>
              <div className="flex items-center gap-2 text-xs">
                <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
                <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
                  {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Warnings */}
            {invalidStrategiesCount > 0 && (
              <div className="flex items-center gap-2 text-xs text-amber-500 mt-2">
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                <span>
                  {invalidStrategiesCount} {invalidStrategiesCount === 1 ? 'strategy is' : 'strategies are'} missing configuration
                </span>
              </div>
            )}
            {/* {hasErrors && (
              <div className="flex items-center gap-2 text-xs text-red-400 mt-2">
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                <span>Some data failed to load</span>
              </div>
            )} */}
          </div>

          {/* Timescale Selector */}
          <Select
            value={selectedTimescale}
            onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}
          >
            <SelectTrigger
              className="w-full sm:w-[160px] rounded-xl backdrop-blur-sm border border-white/10 text-white transition-all duration-200"
              style={{
                background: 'linear-gradient(180deg, rgba(255, 255, 255, 0.24) 0%, rgba(161, 207, 211, 0.06) 100%)',
              }}
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent
              className="rounded-xl backdrop-blur-sm border border-white/10"
              style={{
                background: 'linear-gradient(180deg, rgba(28, 47, 47, 0.95) 0%, rgba(11, 21, 21, 0.98) 100%)',
              }}
            >
              {TIMESCALE_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="text-white focus:text-white focus:bg-white/10 rounded-lg"
                >
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Performance Label and Change */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
        <span className="text-xs text-zinc-400 whitespace-nowrap">
          PORTFOLIO PERFORMANCE OVER TIME
        </span>
      </div>

      {/* Chart */}
      <div className="h-48 sm:h-56 md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 20 }}>
            <defs>
              <linearGradient id="totalAUMGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#90E7EE" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#90E7EE" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              tickFormatter={(value) => formatDate(value, selectedTimescale)}
              angle={-45}
              textAnchor="end"
              height={50}
              minTickGap={30}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              tickFormatter={(value) => formatAUM(value)}
              domain={[0, 'auto']}
            />
            <Tooltip content={<CustomTooltip strategies={validStrategies} />} />
            <Area
              type="monotone"
              dataKey="totalAUM"
              fill="url(#totalAUMGradient)"
              stroke="#90E7EE"
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
