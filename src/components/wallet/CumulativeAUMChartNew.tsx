import React, { useMemo, useState, useEffect } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, Line } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { useYearnWETHConfig } from "@/hooks/useStrategyConfig";
import { useYearnWETHSubgraphData } from "@/hooks/useStrategySubgraphData";
import { hedgeFundApi } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  yearnWethCurrentBalance?: number;
}

type DataPoint = {
  timestamp: number;
  date: string;
  totalAUM: number;
  yearnWethAUM: number;
};

type TimescaleOption = "15m" | "1h" | "1d" | "30d" | "1mo";

const TIMESCALE_OPTIONS: { value: TimescaleOption; label: string }[] = [
  { value: "15m", label: "Past 15 mins" },
  { value: "1h", label: "Past 1 hr" },
  { value: "1d", label: "Past 1 day" },
  { value: "30d", label: "Past 30 days" },
  { value: "1mo", label: "Past 1 month" },
];

const getTimescaleSeconds = (timescale: TimescaleOption): number => {
  const now = Math.floor(Date.now() / 1000);
  switch (timescale) {
    case "15m": return now - 15 * 60;
    case "1h": return now - 60 * 60;
    case "1d": return now - 24 * 60 * 60;
    case "30d": return now - 30 * 24 * 60 * 60;
    case "1mo": return now - 30 * 24 * 60 * 60;
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

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload as DataPoint;
  if (!data) return null;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-sm font-bold text-green-400 mb-2">
        Total: {formatAUM(data.totalAUM)}
      </p>
      <div className="space-y-1">
        {data.yearnWethAUM > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-cyan-500"></div>
            <span className="text-xs text-zinc-300">Yearn WETH: {formatAUM(data.yearnWethAUM)}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export const CumulativeAUMChartNew: React.FC<CumulativeAUMChartNewProps> = ({
  userWalletAddress,
  yearnWethCurrentBalance
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");

  const { data: yearnWethConfig, isLoading: yearnWethConfigLoading } = useYearnWETHConfig();

  const { data: yearnWethSubgraphData, isLoading: yearnWethSubgraphLoading } = useYearnWETHSubgraphData(yearnWethConfig?.subgraph_url, userWalletAddress);

  const [actualYearnWethBalance, setActualYearnWethBalance] = useState<number | undefined>(undefined);

  // Fetch Yearn WETH balance directly
  useEffect(() => {
    const fetchYearnWethBalance = async () => {
      if (!userWalletAddress || !yearnWethConfig?.vault_address) return;

      try {
        const response = await hedgeFundApi.get(`/api/v1/strategy/YEARN_WETH/balance/${userWalletAddress}`);
        const data = response.data;
        if (data.balance) {
          const balance = Number(data.balance) / Math.pow(10, data.decimals || 6);
          setActualYearnWethBalance(balance);
        }
      } catch (error) { }
    };
    fetchYearnWethBalance();
    const interval = setInterval(fetchYearnWethBalance, 10000);
    return () => clearInterval(interval);
  }, [userWalletAddress, yearnWethConfig?.vault_address]);

  const isLoading = yearnWethConfigLoading || yearnWethSubgraphLoading;

  // Build timeline data
  const chartData = useMemo(() => {
    if (!userWalletAddress) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Get all user transactions (already filtered by wallet address in GraphQL query)
    const yearnWethDeposits = yearnWethSubgraphData?.deposits || [];
    const yearnWethWithdrawals = yearnWethSubgraphData?.withdrawals || [];

    // Collect all transaction timestamps
    const allTimestamps = new Set<number>();
    yearnWethDeposits.forEach((d: any) => allTimestamps.add(Number(d.timestamp)));
    yearnWethWithdrawals.forEach((w: any) => allTimestamps.add(Number(w.timestamp)));

    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // Build cumulative balance over time
    const dataPoints: DataPoint[] = [];
    let yearnWethShares = 0;

    for (const timestamp of sortedTimestamps) {
      // Process deposits
      yearnWethDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) yearnWethShares += (Number(d.assets) || 0);
      });

      // Process withdrawals
      yearnWethWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) yearnWethShares -= (Number(w.assets) || 0);
      });

      // Calculate AUM (USDC assets as value)
      const yearnWethAUM = yearnWethShares;
      const totalAUM = yearnWethAUM;

      dataPoints.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM,
        yearnWethAUM
      });
    }

    // Use the actual current balances from the API as the source of truth
    const currentYearnWethShares = (actualYearnWethBalance !== undefined && actualYearnWethBalance > 0) ? actualYearnWethBalance : yearnWethShares;

    // Add current point if needed
    if (dataPoints.length > 0) {
      const lastPoint = dataPoints[dataPoints.length - 1];
      if (currentTime - lastPoint.timestamp > 60) {
        dataPoints.push({
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: yearnWethShares, // Use yearnWethShares (assets)
          yearnWethAUM: yearnWethShares
        });
      }
    } else if (yearnWethCurrentBalance || actualYearnWethBalance) {
      const startAUM = 0;
      dataPoints.push({
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: 0,
        yearnWethAUM: 0
      });

      // For Yearn WETH fallback to current balance (tokens) as value
      const fallbackYearnWethVal = actualYearnWethBalance || yearnWethCurrentBalance || 0;

      dataPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: fallbackYearnWethVal,
        yearnWethAUM: fallbackYearnWethVal
      });
    }

    // Filter by timescale
    let filteredPoints = dataPoints.filter(p => p.timestamp >= timescaleStart);

    // Add starting point
    if (filteredPoints.length > 0) {
      const pointsBeforeStart = dataPoints.filter(p => p.timestamp < timescaleStart);
      if (pointsBeforeStart.length > 0) {
        const lastBeforeStart = pointsBeforeStart[pointsBeforeStart.length - 1];
        filteredPoints.unshift({
          timestamp: timescaleStart,
          date: formatDate(timescaleStart, selectedTimescale),
          totalAUM: lastBeforeStart.totalAUM,
          yearnWethAUM: lastBeforeStart.yearnWethAUM
        });
      }
    }

    return filteredPoints;
  }, [
    userWalletAddress,
    yearnWethCurrentBalance,
    actualYearnWethBalance,
    yearnWethSubgraphData,
    yearnWethConfig,
    selectedTimescale
  ]);

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
        <div className="mb-4 sm:mb-6">
          <div className="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4 mb-4">
            <div className="flex-1 w-full">
              <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
              <p className="text-zinc-400 text-xs sm:text-sm mb-3 sm:mb-4">Total Assets Under Management Across All Strategies</p>
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
              dataKey="date"
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              tickFormatter={(value) => formatAUM(value)}
            />
            <Tooltip content={<CustomTooltip />} />
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
