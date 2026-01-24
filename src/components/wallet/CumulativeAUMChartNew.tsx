import React, { useMemo, useState, useEffect } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { useQueries } from '@tanstack/react-query';
import { fetchSubgraph } from "@/hooks/useStrategySubgraphData";
import { hedgeFundApi } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatTokenBalance } from "@/lib/utils";

const DEFAULT_SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_URL || '';

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  yearnWethCurrentBalance?: number;
  strategies?: any[];
}

type DataPoint = {
  timestamp: number;
  date: string;
  totalAUM: number;
  [key: string]: any;
};

type TimescaleOption = "15m" | "1h" | "1d" | "30d" | "1y";

const TIMESCALE_OPTIONS: { value: TimescaleOption; label: string }[] = [
  { value: "15m", label: "Past 15 mins" },
  { value: "1h", label: "Past 1 hr" },
  { value: "1d", label: "Past 1 day" },
  { value: "30d", label: "Past 1 month" },
  { value: "1y", label: "Past 1 year" },
];

const getTimescaleSeconds = (timescale: TimescaleOption): number => {
  const now = Math.floor(Date.now() / 1000);
  switch (timescale) {
    case "15m": return now - 15 * 60;
    case "1h": return now - 60 * 60;
    case "1d": return now - 24 * 60 * 60;
    case "30d": return now - 30 * 24 * 60 * 60;
    case "1y": return now - 365 * 24 * 60 * 60;
    default: return 0;
  }
};

const formatDate = (timestamp: number, timescale?: TimescaleOption): string => {
  const date = new Date(timestamp * 1000);
  if (timescale === "15m" || timescale === "1h") {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }
  if (timescale === "1d") {
    return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const formatAUM = (aum: number): string => {
  if (aum >= 1000000) return `$${(aum / 1000000).toFixed(2)}M`;
  if (aum >= 1000) return `$${(aum / 1000).toFixed(2)}K`;
  return `$${aum.toFixed(2)}`;
};

const CustomTooltip = ({ active, payload, strategies }: any) => {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload as DataPoint;
  if (!data) return null;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-sm font-bold text-green-400 mb-2">
        Total: {formatAUM(data.totalAUM)}
      </p>
      <div className="space-y-1 pt-2 border-t border-zinc-700/50">
        {strategies?.map((strategy: any) => {
          const balance = data[strategy.id];
          if (!balance || balance <= 0) return null;

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

export const CumulativeAUMChartNew: React.FC<CumulativeAUMChartNewProps> = ({
  userWalletAddress,
  strategies = []
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");
  const [activeStrategyBalances, setActiveStrategyBalances] = useState<Record<string, number>>({});

  // 1. Fetch Subgraph Data for ALL active strategies
  const strategyQueries = useQueries({
    queries: strategies.map(strategy => {
      const targetAddress = strategy.address || strategy.vault_address || strategy.contract_address;
      const subgraphUrl = strategy.subgraph_url || DEFAULT_SUBGRAPH_URL;

      console.log(`[Chart] Query params for ${strategy.id}: Address=${targetAddress}, URL=${subgraphUrl}`);

      return {
        queryKey: ['subgraph', 'analytics', strategy.id, targetAddress, userWalletAddress],
        queryFn: () => fetchSubgraph(subgraphUrl, strategy.id, targetAddress, userWalletAddress),
        enabled: !!userWalletAddress && !!targetAddress,
        staleTime: 60000,
      };
    })
  });

  const isLoading = strategyQueries.some(q => q.isLoading);

  // 2. Fetch Live Balances for ALL active strategies
  useEffect(() => {
    const fetchAllBalances = async () => {
      if (!userWalletAddress || strategies.length === 0) return;

      const balanceMap: Record<string, number> = {};

      await Promise.all(strategies.map(async (strategy) => {
        try {
          if (!strategy.id) return;

          const response = await hedgeFundApi.get(`/api/v1/strategy/${strategy.id}/balance/${userWalletAddress}`);
          const data = response.data;
          if (data.balance) {
            const contractDecimals = data.decimals || 18;
            const balance = Number(data.balance) / Math.pow(10, contractDecimals);
            balanceMap[strategy.id] = balance;
          }
        } catch (e) {
          // Ignore errors for individual strategies
        }
      }));

      setActiveStrategyBalances(balanceMap);
    };

    fetchAllBalances();
    const interval = setInterval(fetchAllBalances, 15000);
    return () => clearInterval(interval);
  }, [userWalletAddress, strategies]);


  // 3. Aggregate Data and Build Timeline with Extrapolation
  const chartData = useMemo(() => {
    if (!userWalletAddress || strategies.length === 0) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Collect all events from all successful queries
    let allDeposits: any[] = [];
    let allWithdrawals: any[] = [];
    const strategiesWithHistory = new Set<string>();

    strategyQueries.forEach((query, index) => {
      if (query.data) {
        const strategy = strategies[index];
        const strategyId = strategy?.id;

        const deposits = (query.data.deposits || []).map(d => ({ ...d, strategyId }));
        const withdrawals = (query.data.withdrawals || []).map(w => ({ ...w, strategyId }));

        if (deposits.length > 0 || withdrawals.length > 0) {
          strategiesWithHistory.add(strategyId);
        }

        console.log(`[Chart] Data for ${strategyId}: Deposits: ${deposits.length}, Withdrawals: ${withdrawals.length}`);

        allDeposits = [...allDeposits, ...deposits];
        allWithdrawals = [...allWithdrawals, ...withdrawals];
      }
    });

    // BASELINE: Strategies with live balance but no history (steady state assumption)
    let baselineAUM = 0;
    const baselineBalances: Record<string, number> = {};

    strategies.forEach(s => {
      const liveBal = activeStrategyBalances[s.id] || 0;
      if (liveBal > 0 && !strategiesWithHistory.has(s.id)) {
        baselineAUM += liveBal;
        baselineBalances[s.id] = liveBal;
        console.log(`[Chart] Strategy ${s.id} has live balance ${liveBal} but no history. Using as baseline.`);
      }
    });

    // Collect all unique timestamps
    const allTimestamps = new Set<number>();
    allDeposits.forEach(d => allTimestamps.add(Number(d.timestamp)));
    allWithdrawals.forEach(w => allTimestamps.add(Number(w.timestamp)));

    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // Replay history
    const dataPoints: DataPoint[] = [];
    const currentBalances: Record<string, number> = { ...baselineBalances };

    for (const timestamp of sortedTimestamps) {
      // Process deposits at this timestamp
      allDeposits.forEach(d => {
        if (Number(d.timestamp) === timestamp) {
          const stratId = d.strategyId;
          const rawAmount = Number(d.assets) || 0;

          const strategy = strategies.find(s => s.id === stratId);
          const decimals = strategy?.asset_decimals || strategy?.decimals || 6;
          const normalizedVal = rawAmount / Math.pow(10, decimals);

          currentBalances[stratId] = (currentBalances[stratId] || 0) + normalizedVal;
        }
      });

      // Process withdrawals at this timestamp
      allWithdrawals.forEach(w => {
        if (Number(w.timestamp) === timestamp) {
          const stratId = w.strategyId;
          const rawAmount = Number(w.assets) || 0;

          const strategy = strategies.find(s => s.id === stratId);
          const decimals = strategy?.asset_decimals || strategy?.decimals || 6;
          const normalizedVal = rawAmount / Math.pow(10, decimals);

          currentBalances[stratId] = (currentBalances[stratId] || 0) - normalizedVal;
        }
      });

      // Sum all balances
      let total = 0;
      Object.values(currentBalances).forEach(val => total += val);
      if (total < 0) total = 0;

      dataPoints.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM: total,
        yearnWethAUM: 0,
        ...currentBalances,
      });
    }

    // Filter to range
    let windowedPoints = dataPoints.filter(p => p.timestamp >= timescaleStart);

    // EXTRAPOLATION: Inject Start Point if needed
    if (windowedPoints.length === 0 || windowedPoints[0].timestamp > timescaleStart) {
      const lastEventBeforeStart = dataPoints.filter(p => p.timestamp < timescaleStart).pop();

      let startBalance = baselineAUM;
      let startStrategies: any = { ...baselineBalances };

      if (lastEventBeforeStart) {
        startBalance = lastEventBeforeStart.totalAUM;
        startStrategies = { ...lastEventBeforeStart };
        delete startStrategies.timestamp;
        delete startStrategies.date;
        delete startStrategies.totalAUM;
        delete startStrategies.yearnWethAUM;
      }

      windowedPoints.unshift({
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: startBalance,
        yearnWethAUM: 0,
        ...startStrategies,
      });
    }

    // EXTRAPOLATION: Add Live Point at current time
    const liveTotal = Object.values(activeStrategyBalances).reduce((a, b) => a + b, 0);
    const lastPoint = windowedPoints[windowedPoints.length - 1];

    if (lastPoint && (currentTime - lastPoint.timestamp > 60)) {
      windowedPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveTotal,
        yearnWethAUM: 0,
        ...activeStrategyBalances
      });
    } else if (windowedPoints.length === 1) {
      // Only start point exists, add end point for flat line
      windowedPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveTotal,
        yearnWethAUM: 0,
        ...activeStrategyBalances
      });
    }

    console.log("[Chart] Final Windowed Points:", windowedPoints);

    return windowedPoints;
  }, [strategyQueries, activeStrategyBalances, strategies, selectedTimescale, userWalletAddress]);


  const stats = useMemo(() => {
    if (chartData.length === 0) return null;
    const latest = chartData[chartData.length - 1];
    const first = chartData[0];
    const change = latest.totalAUM - first.totalAUM;
    const changePercent = first.totalAUM > 0 ? (change / first.totalAUM) * 100 : 0;

    return {
      current: latest.totalAUM,
      start: first.totalAUM,
      change,
      changePercent,
      isPositive: change >= 0
    };
  }, [chartData]);


  if (isLoading) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <Skeleton className="h-64 w-full bg-zinc-700/50 rounded-lg" />
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-center py-6 text-zinc-500">
          <Activity className="w-4 h-4 mr-2" />
          <span className="text-xs sm:text-sm">No portfolio data available for selected time period</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
      <div className="mb-4 sm:mb-6">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4 mb-4">
          <div className="flex-1 w-full">
            <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
            <p className="text-zinc-400 text-xs sm:text-sm mb-3 sm:mb-4">Total Assets Under Management Across All Strategies</p>
            <div className="text-2xl sm:text-3xl font-bold text-green-400 mb-2">
              {formatAUM(stats.current)}
            </div>
          </div>
          <Select value={selectedTimescale} onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}>
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

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
        <span className="text-xs text-zinc-400 whitespace-nowrap">PORTFOLIO PERFORMANCE OVER TIME</span>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
          </span>
        </div>
      </div>

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
              domain={[getTimescaleSeconds(selectedTimescale), Math.floor(Date.now() / 1000)]}
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
            />
            <Tooltip content={<CustomTooltip strategies={strategies} />} />
            <Area
              type="stepAfter"
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
