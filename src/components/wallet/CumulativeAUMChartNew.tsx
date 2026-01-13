import React, { useMemo, useState, useEffect } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, Line } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { useMAVCConfig, useMAVPConfig, useMAVCYearnConfig, useYearnWETHConfig } from "@/hooks/useStrategyConfig";
import { useMAVCPriceHistory, useMAVPPriceHistory } from "@/hooks/useStrategyPrice";
import { useSubgraphData, useMAVPSubgraphData, useMAVCYearnSubgraphData, useYearnWETHSubgraphData } from "@/hooks/useStrategySubgraphData";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  mavcCurrentBalance?: number;
  mavpCurrentBalance?: number;
  mavcYearnCurrentBalance?: number;
  yearnWethCurrentBalance?: number;
}

type DataPoint = {
  timestamp: number;
  date: string;
  totalAUM: number;
  mavcAUM: number;
  mavpAUM: number;
  mavcYearnAUM: number;
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
        {data.mavcAUM > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-blue-500"></div>
            <span className="text-xs text-zinc-300">MAVC: {formatAUM(data.mavcAUM)}</span>
          </div>
        )}
        {data.mavpAUM > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500"></div>
            <span className="text-xs text-zinc-300">MAVP: {formatAUM(data.mavpAUM)}</span>
          </div>
        )}
        {data.mavcYearnAUM > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-orange-500"></div>
            <span className="text-xs text-zinc-300">MAVC Yearn: {formatAUM(data.mavcYearnAUM)}</span>
          </div>
        )}
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
  mavcCurrentBalance,
  mavpCurrentBalance,
  mavcYearnCurrentBalance,
  yearnWethCurrentBalance
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");

  const { data: mavcConfig, isLoading: mavcConfigLoading } = useMAVCConfig();
  const { data: mavpConfig, isLoading: mavpConfigLoading } = useMAVPConfig();
  const { data: mavcYearnConfig, isLoading: mavcYearnConfigLoading } = useMAVCYearnConfig();
  const { data: yearnWethConfig, isLoading: yearnWethConfigLoading } = useYearnWETHConfig();

  const { data: mavcPriceHistory, isLoading: mavcPriceLoading } = useMAVCPriceHistory(mavcConfig?.subgraph_url);
  const { data: mavpPriceHistory, isLoading: mavpPriceLoading } = useMAVPPriceHistory(mavpConfig?.subgraph_url);

  const { data: mavcSubgraphData, isLoading: mavcSubgraphLoading } = useSubgraphData(mavcConfig?.subgraph_url, userWalletAddress);
  const { data: mavpSubgraphData, isLoading: mavpSubgraphLoading } = useMAVPSubgraphData(mavpConfig?.subgraph_url, userWalletAddress);
  const { data: mavcYearnSubgraphData, isLoading: mavcYearnSubgraphLoading } = useMAVCYearnSubgraphData(mavcYearnConfig?.subgraph_url, userWalletAddress);
  const { data: yearnWethSubgraphData, isLoading: yearnWethSubgraphLoading } = useYearnWETHSubgraphData(yearnWethConfig?.subgraph_url, userWalletAddress);

  const [actualMavcYearnBalance, setActualMavcYearnBalance] = useState<number | undefined>(undefined);
  const [actualYearnWethBalance, setActualYearnWethBalance] = useState<number | undefined>(undefined);

  // Fetch MAVC Yearn balance directly
  useEffect(() => {
    const fetchMavcYearnBalance = async () => {
      if (!userWalletAddress || !mavcYearnConfig?.vault_address) return;
      try {
        const response = await fetch(`/api/v1/strategy/MAVC_YEARN/balance/${userWalletAddress}`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.balance) {
          const balance = Number(data.balance) / Math.pow(10, data.decimals || 6);
          setActualMavcYearnBalance(balance);
        }
      } catch (error) { }
    };
    fetchMavcYearnBalance();
    const interval = setInterval(fetchMavcYearnBalance, 10000);
    return () => clearInterval(interval);
  }, [userWalletAddress, mavcYearnConfig?.vault_address]);

  // Fetch Yearn WETH balance directly
  useEffect(() => {
    const fetchYearnWethBalance = async () => {
      if (!userWalletAddress || !yearnWethConfig?.vault_address) return;
      try {
        const response = await fetch(`/api/v1/strategy/YEARN_WETH/balance/${userWalletAddress}`);
        if (!response.ok) return;
        const data = await response.json();
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

  const isLoading = mavcConfigLoading || mavpConfigLoading || mavcYearnConfigLoading || yearnWethConfigLoading ||
    mavcPriceLoading || mavpPriceLoading || mavcSubgraphLoading ||
    mavpSubgraphLoading || mavcYearnSubgraphLoading || yearnWethSubgraphLoading;

  // Build timeline data
  const chartData = useMemo(() => {
    if (!userWalletAddress) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Get all user transactions (already filtered by wallet address in GraphQL query)
    const mavcDeposits = mavcSubgraphData?.deposits || [];
    const mavcWithdrawals = mavcSubgraphData?.withdrawals || [];

    const mavpDeposits = mavpSubgraphData?.deposits || [];
    const mavpWithdrawals = mavpSubgraphData?.withdrawals || [];

    const mavcYearnDeposits = mavcYearnSubgraphData?.deposits || [];
    const mavcYearnWithdrawals = mavcYearnSubgraphData?.withdrawals || [];

    const yearnWethDeposits = yearnWethSubgraphData?.deposits || [];
    const yearnWethWithdrawals = yearnWethSubgraphData?.withdrawals || [];

    // Create combined price history
    const combinedPriceHistory: Array<{ timestamp: number; price: number; strategy: string }> = [];

    (mavcPriceHistory || []).forEach((p: any) => {
      combinedPriceHistory.push({
        timestamp: Number(p.timestamp),
        price: Number(p.price),
        strategy: 'MAVC'
      });
    });

    (mavpPriceHistory || []).forEach((p: any) => {
      combinedPriceHistory.push({
        timestamp: Number(p.timestamp),
        price: Number(p.price),
        strategy: 'MAVP'
      });
    });

    combinedPriceHistory.sort((a, b) => a.timestamp - b.timestamp);

    // Get price at specific timestamp
    const getPriceAt = (timestamp: number, strategy: string): number => {
      if (strategy === 'MAVC_YEARN' || strategy === 'YEARN_WETH') {
        return 1; // Treat as 1:1 with Asset(USDC) for calculation simplification
      }

      let price = 0;
      for (const p of combinedPriceHistory) {
        if (p.timestamp <= timestamp && p.strategy === strategy) {
          price = p.price;
        }
      }
      // Fallback to latest price if not found
      if (price === 0) {
        const latest = combinedPriceHistory.filter(p => p.strategy === strategy).slice(-1)[0];
        price = latest?.price || 0;
      }
      return price;
    };

    // Collect all transaction timestamps
    const allTimestamps = new Set<number>();
    mavcDeposits.forEach((d: any) => allTimestamps.add(Number(d.timestamp)));
    mavcWithdrawals.forEach((w: any) => allTimestamps.add(Number(w.timestamp)));
    mavpDeposits.forEach((d: any) => allTimestamps.add(Number(d.timestamp)));
    mavpWithdrawals.forEach((w: any) => allTimestamps.add(Number(w.timestamp)));
    mavcYearnDeposits.forEach((d: any) => allTimestamps.add(Number(d.timestamp)));
    mavcYearnWithdrawals.forEach((w: any) => allTimestamps.add(Number(w.timestamp)));
    yearnWethDeposits.forEach((d: any) => allTimestamps.add(Number(d.timestamp)));
    yearnWethWithdrawals.forEach((w: any) => allTimestamps.add(Number(w.timestamp)));

    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // Build cumulative balance over time
    const dataPoints: DataPoint[] = [];
    let mavcShares = 0;
    let mavpShares = 0;
    let mavcYearnShares = 0;
    let yearnWethShares = 0;

    for (const timestamp of sortedTimestamps) {
      // Process deposits
      mavcDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) mavcShares += Number(d.shares);
      });
      mavpDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) mavpShares += Number(d.shares);
      });
      mavcYearnDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) mavcYearnShares += (Number(d.assets) || 0);
      });
      yearnWethDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) yearnWethShares += (Number(d.assets) || 0);
      });

      // Process withdrawals
      mavcWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) mavcShares -= Number(w.shares);
      });
      mavpWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) mavpShares -= Number(w.shares);
      });
      mavcYearnWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) mavcYearnShares -= (Number(w.assets) || 0);
      });
      yearnWethWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) yearnWethShares -= (Number(w.assets) || 0);
      });

      // Get prices at this timestamp
      const mavcPrice = getPriceAt(timestamp, 'MAVC');
      const mavpPrice = getPriceAt(timestamp, 'MAVP');

      // Calculate AUM
      const mavcAUM = mavcShares * mavcPrice;
      const mavpAUM = mavpShares * mavpPrice;
      const mavcYearnAUM = mavcYearnShares; // 1:1 with USDC
      const yearnWethAUM = yearnWethShares; // Using USDC Assets as value
      const totalAUM = mavcAUM + mavpAUM + mavcYearnAUM + yearnWethAUM;

      dataPoints.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM,
        mavcAUM,
        mavpAUM,
        mavcYearnAUM,
        yearnWethAUM
      });
    }

    // Use current balances to ensure we show latest state
    const latestMavcPrice = getPriceAt(currentTime, 'MAVC');
    const latestMavpPrice = getPriceAt(currentTime, 'MAVP');

    // Use the actual current balances from the API as the source of truth
    const currentMavcShares = (mavcCurrentBalance !== undefined && mavcCurrentBalance > 0) ? mavcCurrentBalance : mavcShares;
    const currentMavpShares = (mavpCurrentBalance !== undefined && mavpCurrentBalance > 0) ? mavpCurrentBalance : mavpShares;
    const currentMavcYearnShares = (actualMavcYearnBalance !== undefined && actualMavcYearnBalance > 0) ? actualMavcYearnBalance : mavcYearnShares;
    const currentYearnWethShares = (actualYearnWethBalance !== undefined && actualYearnWethBalance > 0) ? actualYearnWethBalance : yearnWethShares;
    // ^ Assuming close to shares since we don't have price, but we used assets for history. 
    // If mismatch, chart might jump. But safe default.

    // Update last data point if actual balance differs significantly for MAVC Yearn
    if (dataPoints.length > 0 && actualMavcYearnBalance !== undefined && actualMavcYearnBalance > 0) {
      const lastPoint = dataPoints[dataPoints.length - 1];
      if (Math.abs(lastPoint.mavcYearnAUM - actualMavcYearnBalance) > 1) { // >1 USDC diff
        lastPoint.mavcYearnAUM = actualMavcYearnBalance;
        lastPoint.totalAUM = lastPoint.mavcAUM + lastPoint.mavpAUM + actualMavcYearnBalance + lastPoint.yearnWethAUM;
      }
    }

    // Add current point if needed
    if (dataPoints.length > 0) {
      const lastPoint = dataPoints[dataPoints.length - 1];
      if (currentTime - lastPoint.timestamp > 60) {
        // Logic to prevent adding point if nothing changed...
        // For simplicity in this large refactor, we just add the current point to ensure up-to-date look
        dataPoints.push({
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: (currentMavcShares * latestMavcPrice) + (currentMavpShares * latestMavpPrice) + currentMavcYearnShares + yearnWethShares, // Use yearnWethShares (assets) instead of currentYearnWethShares to avoid jump due to PPS
          mavcAUM: currentMavcShares * latestMavcPrice,
          mavpAUM: currentMavpShares * latestMavpPrice,
          mavcYearnAUM: currentMavcYearnShares,
          yearnWethAUM: yearnWethShares // Use accumulated assets
        });
      }
    } else if (mavcCurrentBalance || mavpCurrentBalance || actualMavcYearnBalance || yearnWethCurrentBalance) {
      // No transactions found in subgraph, but we have current balance
      const startAUM = 0;
      dataPoints.push({
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: 0,
        mavcAUM: 0,
        mavpAUM: 0,
        mavcYearnAUM: 0,
        yearnWethAUM: 0
      });

      // For Yearn WETH fallback to current balance (tokens) as value
      const fallbackYearnWethVal = actualYearnWethBalance || yearnWethCurrentBalance || 0;

      dataPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: (currentMavcShares * latestMavcPrice) + (currentMavpShares * latestMavpPrice) + currentMavcYearnShares + fallbackYearnWethVal,
        mavcAUM: currentMavcShares * latestMavcPrice,
        mavpAUM: currentMavpShares * latestMavpPrice,
        mavcYearnAUM: currentMavcYearnShares,
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
          mavcAUM: lastBeforeStart.mavcAUM,
          mavpAUM: lastBeforeStart.mavpAUM,
          mavcYearnAUM: lastBeforeStart.mavcYearnAUM,
          yearnWethAUM: lastBeforeStart.yearnWethAUM
        });
      }
    }

    return filteredPoints;
  }, [
    userWalletAddress,
    mavcCurrentBalance,
    mavpCurrentBalance,
    mavcYearnCurrentBalance,
    yearnWethCurrentBalance,
    actualMavcYearnBalance,
    actualYearnWethBalance,
    mavcPriceHistory,
    mavpPriceHistory,
    mavcSubgraphData,
    mavpSubgraphData,
    mavcYearnSubgraphData,
    yearnWethSubgraphData,
    mavcYearnConfig,
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
