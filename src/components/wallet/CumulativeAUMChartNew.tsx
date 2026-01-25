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
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");

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

  // Build chart data from historical events + live balances
  const chartData = useMemo(() => {
    if (!userWalletAddress || validStrategies.length === 0) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Collect all deposit and withdrawal events
    const deposits: DepositEvent[] = [];
    const withdrawals: WithdrawalEvent[] = [];

    strategyQueries.forEach((query, index) => {
      if (!query.data) return;

      const strategy = validStrategies[index];

      (query.data.deposits || []).forEach((d: any) => {
        deposits.push({
          timestamp: d.timestamp,
          assets: d.assets,
          strategyId: strategy.id
        });
      });

      (query.data.withdrawals || []).forEach((w: any) => {
        withdrawals.push({
          timestamp: w.timestamp,
          assets: w.assets,
          strategyId: strategy.id
        });
      });
    });

    // Get all unique timestamps and sort them
    const timestamps = new Set<number>();
    deposits.forEach(d => timestamps.add(Number(d.timestamp)));
    withdrawals.forEach(w => timestamps.add(Number(w.timestamp)));
    const sortedTimestamps = Array.from(timestamps).sort((a, b) => a - b);

    // Replay history to build balance at each timestamp
    const historicalData: ChartDataPoint[] = [];
    const balanceTracker: Record<string, number> = {};

    sortedTimestamps.forEach(timestamp => {
      // Process deposits
      deposits.forEach(deposit => {
        if (Number(deposit.timestamp) === timestamp) {
          const strategy = validStrategies.find(s => s.id === deposit.strategyId);
          if (!strategy) return;

          const decimals = getStrategyDecimals(strategy);
          const amount = Number(deposit.assets) / Math.pow(10, decimals);

          if (isFinite(amount) && !isNaN(amount)) {
            balanceTracker[deposit.strategyId] = (balanceTracker[deposit.strategyId] || 0) + amount;
          }
        }
      });

      // Process withdrawals
      withdrawals.forEach(withdrawal => {
        if (Number(withdrawal.timestamp) === timestamp) {
          const strategy = validStrategies.find(s => s.id === withdrawal.strategyId);
          if (!strategy) return;

          const decimals = getStrategyDecimals(strategy);
          const amount = Number(withdrawal.assets) / Math.pow(10, decimals);

          if (isFinite(amount) && !isNaN(amount)) {
            balanceTracker[withdrawal.strategyId] = Math.max(
              0,
              (balanceTracker[withdrawal.strategyId] || 0) - amount
            );
          }
        }
      });

      // Calculate total AUM
      const totalAUM = Object.values(balanceTracker).reduce((sum, val) => {
        return isFinite(val) && !isNaN(val) ? sum + val : sum;
      }, 0);

      historicalData.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM: Math.max(0, totalAUM),
        ...balanceTracker
      });
    });

    // Filter to selected timescale
    let windowedData = historicalData.filter(d => d.timestamp >= timescaleStart);

    // Add start point if needed
    if (windowedData.length === 0 || windowedData[0].timestamp > timescaleStart) {
      const lastBeforeWindow = historicalData
        .filter(d => d.timestamp < timescaleStart)
        .pop();

      const startPoint: ChartDataPoint = {
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: lastBeforeWindow?.totalAUM || 0,
      };

      if (lastBeforeWindow) {
        Object.keys(lastBeforeWindow).forEach(key => {
          if (key !== 'timestamp' && key !== 'date' && key !== 'totalAUM') {
            startPoint[key] = lastBeforeWindow[key];
          }
        });
      }

      windowedData.unshift(startPoint);
    }

    // Add current point with live balances
    const liveTotalAUM = Object.values(liveBalances).reduce((sum, val) => {
      return isFinite(val) && !isNaN(val) ? sum + val : sum;
    }, 0);

    const lastPoint = windowedData[windowedData.length - 1];
    const shouldAddLivePoint = !lastPoint || (currentTime - lastPoint.timestamp > 60);

    if (windowedData.length === 0) {
      // No historical data - show flat line at current balance
      windowedData = [
        {
          timestamp: timescaleStart,
          date: formatDate(timescaleStart, selectedTimescale),
          totalAUM: liveTotalAUM,
          ...liveBalances
        },
        {
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: liveTotalAUM,
          ...liveBalances
        }
      ];
    } else if (shouldAddLivePoint) {
      windowedData.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveTotalAUM,
        ...liveBalances
      });
    }

    return windowedData;
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
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <Skeleton className="h-64 w-full bg-zinc-700/50 rounded-lg" />
      </div>
    );
  }

  if (chartData.length === 0 || !stats) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
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
    <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
      {/* Header */}
      <div className="mb-4 sm:mb-6">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4 mb-4">
          <div className="flex-1 w-full">
            <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">
              Portfolio Performance
            </h3>
            <p className="text-zinc-400 text-xs sm:text-sm mb-3 sm:mb-4">
              Total Assets Under Management Across All Strategies
            </p>
            <div className="text-2xl sm:text-3xl font-bold text-green-400 mb-2">
              {formatAUM(stats.current)}
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
            {hasErrors && (
              <div className="flex items-center gap-2 text-xs text-red-400 mt-2">
                <AlertCircle className="w-3 h-3 flex-shrink-0" />
                <span>Some data failed to load</span>
              </div>
            )}
          </div>

          {/* Timescale Selector */}
          <Select
            value={selectedTimescale}
            onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}
          >
            <SelectTrigger className="w-full sm:w-[160px] bg-zinc-800/50 border-zinc-700 text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-800 border-zinc-700">
              {TIMESCALE_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="text-white focus:bg-zinc-700 focus:text-white"
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
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
          </span>
        </div>
      </div>

      {/* Chart */}
      <div className="h-48 sm:h-56 md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 20 }}>
            <defs>
              <linearGradient id="totalAUMGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
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
              stroke="#22c55e"
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
