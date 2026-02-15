import React, { useMemo, useState } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { TrendingUp, Activity, AlertCircle, Filter } from "lucide-react";
import { useQueries } from '@tanstack/react-query';
import { fetchSubgraph } from "@/hooks/useStrategySubgraphData";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { HEDGE_FUND_SUBGRAPH_URL } from "@/lib/api";

const DEFAULT_SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_URL || HEDGE_FUND_SUBGRAPH_URL;

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

/** Shares for balance replay; amountUsd for time-weighted return (cash flow in dollars). */
interface DepositEvent {
  timestamp: string;
  strategyId: string;
  shares: string;
  amountUsd: number;
}

interface WithdrawalEvent {
  timestamp: string;
  strategyId: string;
  shares: string;
  amountUsd: number;
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

/**
 * Time-Weighted Return (TWR) — industry standard for portfolio performance.
 * Removes the impact of deposits/withdrawals so the % reflects investment returns only.
 * Formula: compound sub-period returns where each R_i = EMV / (BMV + C) - 1,
 * with C = net cash flow (deposits - withdrawals) in the sub-period.
 */
function computeTimeWeightedReturn(
  dataPoints: { timestamp: number; totalAUM: number }[],
  deposits: DepositEvent[],
  withdrawals: WithdrawalEvent[],
  periodStart: number,
  periodEnd: number
): number | null {
  if (dataPoints.length < 2) return null;

  const sorted = [...dataPoints].filter(
    (p) => p.timestamp >= periodStart && p.timestamp <= periodEnd
  ).sort((a, b) => a.timestamp - b.timestamp);
  if (sorted.length < 2) return null;

  let compound = 1;

  for (let i = 0; i < sorted.length - 1; i++) {
    const tStart = sorted[i].timestamp;
    const tEnd = sorted[i + 1].timestamp;
    const BMV = sorted[i].totalAUM;
    const EMV = sorted[i + 1].totalAUM;

    // Net cash flow in (tStart, tEnd]: deposits add, withdrawals subtract
    const depositsInPeriod = deposits.filter(
      (d) => { const ts = Number(d.timestamp); return ts > tStart && ts <= tEnd; }
    ).reduce((sum, d) => sum + d.amountUsd, 0);
    const withdrawalsInPeriod = withdrawals.filter(
      (w) => { const ts = Number(w.timestamp); return ts > tStart && ts <= tEnd; }
    ).reduce((sum, w) => sum + w.amountUsd, 0);
    const C = depositsInPeriod - withdrawalsInPeriod;

    const denominator = BMV + C;
    if (denominator <= 0 || !isFinite(EMV) || !isFinite(denominator)) continue;
    const R = EMV / denominator - 1;
    compound *= 1 + R;
  }

  return compound - 1;
}

// ============================================================================
// Custom Tooltip Component
// ============================================================================

const CustomTooltip = ({ active, payload, strategies }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload as ChartDataPoint;
  if (!data) return null;

  return (
    <div className="rounded-lg border border-white/10 bg-[#0a1414]/95 backdrop-blur-md p-3 shadow-lg">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-base font-semibold text-white mb-3">
        {formatAUM(data.totalAUM)}
      </p>
      {strategies && strategies.length > 0 && (
        <div className="space-y-2 pt-2 border-t border-white/10">
          {strategies.map((strategy: Strategy) => {
            const balance = data[strategy.id];
            if (typeof balance !== 'number' || balance <= 0) return null;
            return (
              <div key={strategy.id} className="flex items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-[#90E7EE]" />
                  <span className="text-zinc-300">{strategy.symbol || strategy.name || strategy.id}</span>
                </div>
                <span className="text-white font-medium tabular-nums">{formatAUM(balance)}</span>
              </div>
            );
          })}
        </div>
      )}
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
  const [selectedStrategyFilter, setSelectedStrategyFilter] = useState<string>("all");

  // Filter out invalid strategies
  const validStrategies = useMemo(() => {
    return strategies.filter(strategy => {
      const hasId = !!strategy.id;
      const hasAddress = !!getStrategyAddress(strategy);
      const hasSubgraph = !!strategy.subgraph_url || !!DEFAULT_SUBGRAPH_URL;
      return hasId && hasAddress && hasSubgraph;
    });
  }, [strategies]);

  // Strategies to include in chart (all or single strategy)
  const filteredStrategies = useMemo(() => {
    if (selectedStrategyFilter === "all") return validStrategies;
    return validStrategies.filter((s) => s.id === selectedStrategyFilter || s.symbol === selectedStrategyFilter);
  }, [validStrategies, selectedStrategyFilter]);

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

  // Extract live balances (shares) from parent's balance data
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

  // Convert share balances to USD: tokens × token price per strategy (filtered)
  // Portfolio performance = strategy positions only (no USDC)
  const liveBalancesUsd = useMemo(() => {
    const usd: Record<string, number> = {};
    let totalUsd = 0;

    filteredStrategies.forEach((strategy) => {
      const index = validStrategies.findIndex((s) => s.id === strategy.id || s.symbol === strategy.symbol);
      const shares = liveBalances[strategy.id] ?? liveBalances[strategy.symbol ?? ""];
      const queryData = index >= 0 ? strategyQueries[index]?.data : null;
      const sharePrice = queryData?.strategyMetric?.lastSharePrice != null
        ? parseFloat(String(queryData.strategyMetric.lastSharePrice))
        : 0;

      const valueUsd = (shares ?? 0) * (sharePrice > 0 ? sharePrice : 1);
      if (isFinite(valueUsd) && !isNaN(valueUsd)) {
        usd[strategy.id] = Math.max(0, valueUsd);
        totalUsd += usd[strategy.id];
      }
    });

    return { byStrategy: usd, total: totalUsd };
  }, [balanceData, liveBalances, validStrategies, filteredStrategies, strategyQueries]);

  // Build chart data using price updates × user balances (filtered by strategy)
  const chartResult = useMemo((): { data: ChartDataPoint[]; deposits: DepositEvent[]; withdrawals: WithdrawalEvent[] } => {
    if (!userWalletAddress || filteredStrategies.length === 0) {
      return { data: [], deposits: [], withdrawals: [] };
    }

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Collect all price updates, deposits, and withdrawals (only for filtered strategies)
    interface PriceUpdateEvent {
      timestamp: number;
      price: number;
      strategyId: string;
    }

    const priceUpdates: PriceUpdateEvent[] = [];
    const deposits: DepositEvent[] = [];
    const withdrawals: WithdrawalEvent[] = [];

    filteredStrategies.forEach((strategy) => {
      const index = validStrategies.findIndex((s) => s.id === strategy.id || s.symbol === strategy.symbol);
      const query = index >= 0 ? strategyQueries[index] : null;
      if (!query?.data) return;

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

      // Collect deposits: shares for balance replay, amountUsd for TWR (cash flow)
      (query.data.deposits || []).forEach((d: any) => {
        const amountUsd = parseFloat(d.assets);
        deposits.push({
          timestamp: d.timestamp,
          strategyId: strategy.id,
          shares: d.shares ?? "0",
          amountUsd: isFinite(amountUsd) ? amountUsd : 0
        });
      });

      // Collect withdrawals: shares for balance replay, amountUsd for TWR
      (query.data.withdrawals || []).forEach((w: any) => {
        const amountUsd = parseFloat(w.assets);
        withdrawals.push({
          timestamp: w.timestamp,
          strategyId: strategy.id,
          shares: w.shares ?? "0",
          amountUsd: isFinite(amountUsd) ? amountUsd : 0
        });
      });
    });

    // Get all unique price update timestamps and sort them
    const priceTimestamps = new Set<number>();
    priceUpdates.forEach(p => priceTimestamps.add(p.timestamp));
    const sortedPriceTimestamps = Array.from(priceTimestamps).sort((a, b) => a - b);

    if (sortedPriceTimestamps.length === 0) {
      // No price updates - build chart from deposit/withdrawal cash flows so the graph reflects user activity
      const liveTotalValue = liveBalancesUsd.total;

      const depositsInPeriod = deposits.filter((d) => {
        const ts = Number(d.timestamp);
        return ts >= timescaleStart && ts <= currentTime;
      });
      const withdrawalsInPeriod = withdrawals.filter((w) => {
        const ts = Number(w.timestamp);
        return ts >= timescaleStart && ts <= currentTime;
      });
      const netDeposits = depositsInPeriod.reduce((s, d) => s + d.amountUsd, 0);
      const netWithdrawals = withdrawalsInPeriod.reduce((s, w) => s + w.amountUsd, 0);
      const netCashFlow = netDeposits - netWithdrawals;
      const startingValue = Math.max(0, liveTotalValue - netCashFlow);

      const cashFlowEvents = [
        ...depositsInPeriod.map((d) => ({ timestamp: Number(d.timestamp), delta: d.amountUsd, type: 'deposit' as const })),
        ...withdrawalsInPeriod.map((w) => ({ timestamp: Number(w.timestamp), delta: -w.amountUsd, type: 'withdrawal' as const }))
      ].sort((a, b) => a.timestamp - b.timestamp);

      const dataPoints: ChartDataPoint[] = [];
      let runningValue = startingValue;
      dataPoints.push({
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: runningValue,
        ...liveBalancesUsd.byStrategy
      });
      cashFlowEvents.forEach((ev) => {
        runningValue = Math.max(0, runningValue + ev.delta);
        dataPoints.push({
          timestamp: ev.timestamp,
          date: formatDate(ev.timestamp, selectedTimescale),
          totalAUM: runningValue,
          ...liveBalancesUsd.byStrategy
        });
      });
      if (dataPoints[dataPoints.length - 1]?.timestamp !== currentTime) {
        dataPoints.push({
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: liveTotalValue,
          ...liveBalancesUsd.byStrategy
        });
      }

      return { data: dataPoints, deposits, withdrawals };
    }

    // Build portfolio value history
    const historicalData: ChartDataPoint[] = [];

    // For each price update timestamp, calculate portfolio value
    sortedPriceTimestamps.forEach(timestamp => {
      // Calculate user's share balance at this timestamp
      const shareBalances: Record<string, number> = {};

      filteredStrategies.forEach(strategy => {
        let balance = 0;

        // Replay all deposits/withdrawals up to this timestamp (share amounts)
        deposits
          .filter(d => d.strategyId === strategy.id && Number(d.timestamp) <= timestamp)
          .forEach(d => {
            const amount = parseFloat(d.shares);
            if (isFinite(amount) && !isNaN(amount)) {
              balance += amount;
            }
          });

        withdrawals
          .filter(w => w.strategyId === strategy.id && Number(w.timestamp) <= timestamp)
          .forEach(w => {
            const amount = parseFloat(w.shares);
            if (isFinite(amount) && !isNaN(amount)) {
              balance = Math.max(0, balance - amount);
            }
          });

        shareBalances[strategy.id] = balance;
      });

      // Calculate portfolio value at this timestamp
      const strategyValues: Record<string, number> = {};
      let totalPortfolioValue = 0;

      filteredStrategies.forEach((strategy) => {
        const userShares = shareBalances[strategy.id] || 0;
        if (userShares <= 0) return;

        const idx = validStrategies.findIndex((s) => s.id === strategy.id || s.symbol === strategy.symbol);
        const queryData = idx >= 0 ? strategyQueries[idx]?.data : null;
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

    // Add current point with live balances (USD, using token prices)
    const lastPoint = historicalData[historicalData.length - 1];
    const shouldAddLivePoint = !lastPoint || (currentTime - lastPoint.timestamp > 60);

    if (shouldAddLivePoint) {
      historicalData.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveBalancesUsd.total,
        ...liveBalancesUsd.byStrategy
      });
    }

    return { data: historicalData, deposits, withdrawals };
  }, [strategyQueries, liveBalances, liveBalancesUsd, validStrategies, filteredStrategies, selectedTimescale, userWalletAddress]);

  const chartData = chartResult.data;
  const chartDeposits = chartResult.deposits;
  const chartWithdrawals = chartResult.withdrawals;

  // Restrict to selected time window so stats and chart always match the filter
  const periodStart = getTimescaleSeconds(selectedTimescale);
  const periodEnd = Math.floor(Date.now() / 1000);
  const dataInRange = useMemo(() => {
    return chartData.filter(
      (p) => p.timestamp >= periodStart && p.timestamp <= periodEnd
    );
  }, [chartData, periodStart, periodEnd]);

  const chartDataToRender = dataInRange.length >= 2 ? dataInRange : chartData;

  // Calculate stats from the same filtered data we render (so filter is consistent)
  const stats = useMemo(() => {
    if (chartDataToRender.length === 0) return null;

    const latest = chartDataToRender[chartDataToRender.length - 1];
    const first = chartDataToRender[0];

    const twr = computeTimeWeightedReturn(
      chartDataToRender,
      chartDeposits,
      chartWithdrawals,
      periodStart,
      periodEnd
    );

    const change = latest.totalAUM - first.totalAUM;
    const simplePercent = first.totalAUM > 0 ? (change / first.totalAUM) * 100 : 0;
    const changePercent = twr !== null ? twr * 100 : simplePercent;

    return {
      current: isFinite(latest.totalAUM) ? latest.totalAUM : 0,
      start: isFinite(first.totalAUM) ? first.totalAUM : 0,
      change: isFinite(change) ? change : 0,
      changePercent: isFinite(changePercent) ? changePercent : 0,
      isPositive: changePercent >= 0,
      isTwr: twr !== null
    };
  }, [chartDataToRender, chartDeposits, chartWithdrawals, periodStart, periodEnd]);

  const invalidStrategiesCount = strategies.length - validStrategies.length;

  // ============================================================================
  // Render States
  // ============================================================================

  if (isLoading) {
    return (
      <div className="relative">
        <Skeleton className="h-64 w-full bg-zinc-700/30 rounded-lg" />
      </div>
    );
  }

  if (chartDataToRender.length === 0 || !stats) {
    return (
      <div className="relative flex flex-col items-center justify-center py-12 text-zinc-500">
        <Activity className="w-8 h-8 mb-3 text-zinc-600" />
        <span className="text-sm font-medium">No portfolio data available</span>
        <span className="text-xs text-zinc-600 mt-1">
          {validStrategies.length === 0 ? 'No valid strategies configured' : 'Try selecting a different time period'}
        </span>
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
    <div className="relative min-w-0 overflow-hidden">
      {/* Header + filters — matches Available Strategies section styling */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <h3 className="text-lg sm:text-xl font-semibold text-white mb-1 tracking-tight">
            Portfolio Performance
          </h3>
          <p className="text-zinc-400 text-xs sm:text-sm mb-3 leading-relaxed">
            {selectedStrategyFilter === "all"
              ? "Strategy positions · TWR excludes deposits & withdrawals"
              : `${validStrategies.find(s => s.id === selectedStrategyFilter || s.symbol === selectedStrategyFilter)?.symbol || selectedStrategyFilter} · tokens × price`}
          </p>
          <div className="flex flex-wrap items-baseline gap-3">
            <span className="text-2xl sm:text-3xl md:text-4xl font-bold text-white tracking-tight">
              {formatAUM(stats.current)}
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
                stats.isPositive
                  ? 'bg-emerald-500/15 text-emerald-400'
                  : 'bg-red-500/15 text-red-400'
              }`}
            >
              <TrendingUp className={`w-3 h-3 ${!stats.isPositive && 'rotate-180'}`} />
              {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
              {stats.isTwr && (
                <span className="text-zinc-500/80 ml-0.5" title="Time-weighted return">
                  TWR
                </span>
              )}
            </span>
          </div>
          {invalidStrategiesCount > 0 && (
            <div className="flex items-center gap-2 text-xs text-amber-400/90 mt-3">
              <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
              <span>{invalidStrategiesCount} strategy(ies) missing config</span>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-2 sm:gap-2.5">
          {validStrategies.length > 1 && (
            <Select value={selectedStrategyFilter} onValueChange={setSelectedStrategyFilter}>
              <SelectTrigger
                className="h-9 flex-1 min-w-0 sm:flex-initial sm:w-[180px] rounded-lg border border-white/10 bg-white/5 text-white text-sm hover:bg-white/10 hover:border-white/20 transition-colors"
              >
                <Filter className="w-3.5 h-3.5 mr-2 opacity-70 flex-shrink-0" />
                <SelectValue placeholder="All strategies" />
              </SelectTrigger>
              <SelectContent
                className="rounded-lg border border-white/10 bg-[#0a1414]"
              >
                <SelectItem value="all" className="text-white focus:bg-white/10 rounded-md">
                  All strategies
                </SelectItem>
                {validStrategies.map((s) => (
                  <SelectItem
                    key={s.id}
                    value={s.id}
                    className="text-white focus:bg-white/10 rounded-md"
                  >
                    {s.symbol || s.name || s.id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Select value={selectedTimescale} onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}>
            <SelectTrigger
              className="h-9 flex-1 min-w-0 sm:flex-initial sm:w-[130px] rounded-lg border border-white/10 bg-white/5 text-white text-sm hover:bg-white/10 hover:border-white/20 transition-colors"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent
              className="rounded-lg border border-white/10 bg-[#0a1414]"
            >
              {TIMESCALE_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="text-white focus:bg-white/10 rounded-md"
                >
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {/* Chart — no bounded box */}
      <div className="h-56 min-w-0">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartDataToRender} margin={{ top: 8, right: 8, left: 8, bottom: 28 }}>
            <defs>
              <linearGradient id="totalAUMGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#90E7EE" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#90E7EE" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="timestamp"
              type="number"
              domain={['dataMin', 'dataMax']}
              tick={{ fill: '#94a3b8', fontSize: 10 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
              tickLine={{ stroke: 'rgba(255,255,255,0.05)' }}
              tickFormatter={(value) => formatDate(value, selectedTimescale)}
              angle={-35}
              textAnchor="end"
              height={44}
              minTickGap={24}
            />
            <YAxis
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              axisLine={{ stroke: 'rgba(255,255,255,0.08)' }}
              tickLine={{ stroke: 'rgba(255,255,255,0.05)' }}
              tickFormatter={(value) => formatAUM(value)}
              domain={[0, 'auto']}
              width={58}
            />
            <Tooltip content={<CustomTooltip strategies={filteredStrategies} />} />
            <Area
              type="monotone"
              dataKey="totalAUM"
              fill="url(#totalAUMGradient)"
              stroke="#90E7EE"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
