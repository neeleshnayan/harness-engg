import React, { useMemo, useState, useEffect } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip, Line } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { useMAVCConfig, useMAVPConfig, useMAVCYearnConfig } from "@/hooks/useStrategyConfig";
import { useMAVCPriceHistory, useMAVPPriceHistory } from "@/hooks/useStrategyPrice";
import { useSubgraphData, useMAVPSubgraphData, useMAVCYearnSubgraphData } from "@/hooks/useStrategySubgraphData";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  mavcCurrentBalance?: number;
  mavpCurrentBalance?: number;
  mavcYearnCurrentBalance?: number;
}

type DataPoint = {
  timestamp: number;
  date: string;
  totalAUM: number;
  mavcAUM: number;
  mavpAUM: number;
  mavcYearnAUM: number;
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
      </div>
    </div>
  );
};

export const CumulativeAUMChartNew: React.FC<CumulativeAUMChartNewProps> = ({
  userWalletAddress,
  mavcCurrentBalance,
  mavpCurrentBalance,
  mavcYearnCurrentBalance
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");
  const [actualMavcYearnBalance, setActualMavcYearnBalance] = useState<number | undefined>(undefined);

  const { data: mavcConfig, isLoading: mavcConfigLoading } = useMAVCConfig();
  const { data: mavpConfig, isLoading: mavpConfigLoading } = useMAVPConfig();
  const { data: mavcYearnConfig, isLoading: mavcYearnConfigLoading } = useMAVCYearnConfig();
  const { data: mavcPriceHistory, isLoading: mavcPriceLoading } = useMAVCPriceHistory(mavcConfig?.subgraph_url);
  const { data: mavpPriceHistory, isLoading: mavpPriceLoading } = useMAVPPriceHistory(mavpConfig?.subgraph_url);
  const { data: mavcSubgraphData, isLoading: mavcSubgraphLoading } = useSubgraphData(mavcConfig?.subgraph_url, userWalletAddress);
  const { data: mavpSubgraphData, isLoading: mavpSubgraphLoading } = useMAVPSubgraphData(mavpConfig?.subgraph_url, userWalletAddress);
  const { data: mavcYearnSubgraphData, isLoading: mavcYearnSubgraphLoading } = useMAVCYearnSubgraphData(mavcYearnConfig?.subgraph_url, userWalletAddress);

  // Fetch MAVC Yearn balance directly from the vault API using config
  // Uses the same endpoint as StrategyCard: /api/v1/strategy/MAVC_YEARN/balance/{wallet}
  useEffect(() => {
    const fetchMavcYearnBalance = async () => {
      if (!userWalletAddress || !mavcYearnConfig?.vault_address) return;

      try {
        const response = await fetch(`/api/v1/strategy/MAVC_YEARN/balance/${userWalletAddress}`);
        if (!response.ok) {
          console.error('Failed to fetch MAVC Yearn balance: HTTP', response.status);
          return;
        }

        const data = await response.json();
        if (data.balance) {
          const balance_wei = data.balance || "0";
          const contract_decimals = data.decimals || 6;

          // Convert from wei to human-readable
          const balance = Number(balance_wei) / Math.pow(10, contract_decimals);
          setActualMavcYearnBalance(balance);
          console.log('✅ Fetched MAVC Yearn Balance from Vault:', {
            balance,
            balance_wei,
            decimals: contract_decimals,
            vaultAddress: mavcYearnConfig.vault_address
          });
        }
      } catch (error) {
        console.error('Failed to fetch MAVC Yearn balance:', error);
      }
    };

    fetchMavcYearnBalance();
    // Refetch every 10 seconds
    const interval = setInterval(fetchMavcYearnBalance, 10000);
    return () => clearInterval(interval);
  }, [userWalletAddress, mavcYearnConfig?.vault_address]);

  const isLoading = mavcConfigLoading || mavpConfigLoading || mavcYearnConfigLoading ||
                    mavcPriceLoading || mavpPriceLoading || mavcSubgraphLoading ||
                    mavpSubgraphLoading || mavcYearnSubgraphLoading;

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

    console.log('🔍 MAVC Yearn Debug:', {
      deposits: mavcYearnDeposits.length,
      withdrawals: mavcYearnWithdrawals.length,
      sampleDeposit: mavcYearnDeposits[0],
      sampleDepositShares: mavcYearnDeposits[0]?.shares,
      sampleDepositAssets: mavcYearnDeposits[0]?.assets,
      sampleDepositSharesNumber: mavcYearnDeposits[0] ? Number(mavcYearnDeposits[0].shares) : undefined,
      sampleDepositAssetsNumber: mavcYearnDeposits[0] ? Number(mavcYearnDeposits[0].assets) : undefined,
      sampleWithdrawal: mavcYearnWithdrawals[0],
      sampleWithdrawalShares: mavcYearnWithdrawals[0]?.shares,
      sampleWithdrawalAssets: mavcYearnWithdrawals[0]?.assets,
      propBalance: mavcYearnCurrentBalance,
      actualVaultBalance: actualMavcYearnBalance,
      vaultAddressFromConfig: mavcYearnConfig?.vault_address,
      allDepositShares: mavcYearnDeposits.map(d => ({ shares: d.shares, assets: d.assets, timestamp: d.timestamp }))
    });

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
      // MAVC_YEARN is always 1:1 with USDC, no price history needed
      if (strategy === 'MAVC_YEARN') {
        return 1; // Fixed price
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

    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // Build cumulative balance over time
    const dataPoints: DataPoint[] = [];
    let mavcShares = 0;
    let mavpShares = 0;
    let mavcYearnShares = 0;

    for (const timestamp of sortedTimestamps) {
      // Process deposits
      mavcDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) {
          mavcShares += Number(d.shares); // Use directly, already normalized!
        }
      });

      mavpDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) {
          mavpShares += Number(d.shares); // Use directly, already normalized!
        }
      });

      mavcYearnDeposits.forEach((d: any) => {
        if (Number(d.timestamp) === timestamp) {
          // For MAVC Yearn, use assets (USDC amount) instead of shares
          // Shares represent vault fractions which can be very small decimals
          // Assets represent the actual USDC amount deposited
          const assetsAmount = Number(d.assets) || 0;
          mavcYearnShares += assetsAmount;
        }
      });

      // Process withdrawals
      mavcWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) {
          mavcShares -= Number(w.shares); // Use directly, already normalized!
        }
      });

      mavpWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) {
          mavpShares -= Number(w.shares); // Use directly, already normalized!
        }
      });

      mavcYearnWithdrawals.forEach((w: any) => {
        if (Number(w.timestamp) === timestamp) {
          // For MAVC Yearn, use assets (USDC amount) instead of shares
          // Shares represent vault fractions which can be very small decimals
          // Assets represent the actual USDC amount withdrawn
          const assetsAmount = Number(w.assets) || 0;
          mavcYearnShares -= assetsAmount;
        }
      });

      // Get prices at this timestamp
      const mavcPrice = getPriceAt(timestamp, 'MAVC');
      const mavpPrice = getPriceAt(timestamp, 'MAVP');

      // Calculate AUM
      const mavcAUM = mavcShares * mavcPrice;
      const mavpAUM = mavpShares * mavpPrice;
      const mavcYearnAUM = mavcYearnShares; // 1:1 with USDC
      const totalAUM = mavcAUM + mavpAUM + mavcYearnAUM;

      dataPoints.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM,
        mavcAUM,
        mavpAUM,
        mavcYearnAUM
      });
    }

    // Use current balances to ensure we show latest state
    // This handles cases where the user has a balance but no subgraph transactions yet
    const latestMavcPrice = getPriceAt(currentTime, 'MAVC');
    const latestMavpPrice = getPriceAt(currentTime, 'MAVP');

    // Use the actual current balances from the API as the source of truth
    // Important: Only use current balance if it's actually defined and > 0
    // Otherwise use accumulated shares from transactions
    const currentMavcShares = (mavcCurrentBalance !== undefined && mavcCurrentBalance > 0) ? mavcCurrentBalance : mavcShares;
    const currentMavpShares = (mavpCurrentBalance !== undefined && mavpCurrentBalance > 0) ? mavpCurrentBalance : mavpShares;
    // Use actualMavcYearnBalance from vault API, not the prop which aggregates all ysUSDC
    const currentMavcYearnShares = (actualMavcYearnBalance !== undefined && actualMavcYearnBalance > 0) ? actualMavcYearnBalance : mavcYearnShares;

    console.log('💎 Final Shares for Chart:', {
      mavcShares: currentMavcShares,
      mavpShares: currentMavpShares,
      mavcYearnShares: currentMavcYearnShares,
      fromCurrentBalance: {
        mavc: mavcCurrentBalance,
        mavp: mavpCurrentBalance,
        mavcYearnProp: mavcYearnCurrentBalance,
        mavcYearnActual: actualMavcYearnBalance
      },
      fromTransactions: {
        mavc: mavcShares,
        mavp: mavpShares,
        mavcYearn: mavcYearnShares
      }
    });

    // Update last data point's MAVC Yearn balance if actual balance exists and is different
    // This handles cases where transactions haven't been indexed yet or are missing
    if (dataPoints.length > 0 && actualMavcYearnBalance !== undefined && actualMavcYearnBalance > 0) {
      const lastPoint = dataPoints[dataPoints.length - 1];
      if (lastPoint.mavcYearnAUM !== actualMavcYearnBalance) {
        lastPoint.mavcYearnAUM = actualMavcYearnBalance;
        lastPoint.totalAUM = lastPoint.mavcAUM + lastPoint.mavpAUM + actualMavcYearnBalance;
      }
    }

    // Add current point if needed - only use transaction-derived shares to avoid false jumps
    // Only add if current balances match transaction-derived shares (within tolerance)
    // This ensures we don't show a jump that doesn't correspond to any transaction
    // Exception: MAVC Yearn uses actual balance from API since it's fetched directly
    if (dataPoints.length > 0) {
      const lastPoint = dataPoints[dataPoints.length - 1];
      if (currentTime - lastPoint.timestamp > 60) {
        // Check if current balances match transaction-derived shares (within 0.01% tolerance)
        const mavcMatches = !mavcCurrentBalance || Math.abs(mavcShares - mavcCurrentBalance) / Math.max(mavcShares, 1) < 0.0001;
        const mavpMatches = !mavpCurrentBalance || Math.abs(mavpShares - mavpCurrentBalance) / Math.max(mavpShares, 1) < 0.0001;
        // For MAVC Yearn, allow if actual balance exists (even if no transactions) since it's fetched directly from vault
        const mavcYearnMatches = !actualMavcYearnBalance || 
          (mavcYearnShares === 0 && actualMavcYearnBalance > 0) ||
          Math.abs(mavcYearnShares - actualMavcYearnBalance) / Math.max(mavcYearnShares, 1) < 0.0001;
        
        // Use actual MAVC Yearn balance from API if available, otherwise use transaction-derived
        const finalMavcYearnShares = (actualMavcYearnBalance !== undefined && actualMavcYearnBalance > 0) 
          ? actualMavcYearnBalance 
          : mavcYearnShares;
        
        // Only add current point if balances match - use transaction-derived shares to show price changes only
        if (mavcMatches && mavpMatches && mavcYearnMatches) {
          dataPoints.push({
            timestamp: currentTime,
            date: formatDate(currentTime, selectedTimescale),
            totalAUM: (mavcShares * latestMavcPrice) + (mavpShares * latestMavpPrice) + finalMavcYearnShares,
            mavcAUM: mavcShares * latestMavcPrice,
            mavpAUM: mavpShares * latestMavpPrice,
            mavcYearnAUM: finalMavcYearnShares
          });
        }
      }
    } else if (mavcCurrentBalance || mavpCurrentBalance || actualMavcYearnBalance) {
      // No transactions found in subgraph, but we have current balance - create points from current balance
      dataPoints.push({
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: 0,
        mavcAUM: 0,
        mavpAUM: 0,
        mavcYearnAUM: 0
      });

      dataPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: (currentMavcShares * latestMavcPrice) + (currentMavpShares * latestMavpPrice) + currentMavcYearnShares,
        mavcAUM: currentMavcShares * latestMavcPrice,
        mavpAUM: currentMavpShares * latestMavpPrice,
        mavcYearnAUM: currentMavcYearnShares
      });
    }

    // Filter by timescale
    let filteredPoints = dataPoints.filter(p => p.timestamp >= timescaleStart);

    // Add starting point if we have historical data before the timescale
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
          mavcYearnAUM: lastBeforeStart.mavcYearnAUM
        });
      }
    }

    // Extrapolation for short time periods (15m, 1h) when no data
    if (filteredPoints.length === 0 && (selectedTimescale === "15m" || selectedTimescale === "1h")) {
      const latestMavcPrice = mavcPriceHistory && mavcPriceHistory.length > 0 
        ? Number(mavcPriceHistory[mavcPriceHistory.length - 1].price) 
        : 0;
      const latestMavpPrice = mavpPriceHistory && mavpPriceHistory.length > 0 
        ? Number(mavpPriceHistory[mavpPriceHistory.length - 1].price) 
        : 0;
      
      const currentMavcShares = mavcCurrentBalance || 0;
      const currentMavpShares = mavpCurrentBalance || 0;
      const currentMavcYearnShares = actualMavcYearnBalance || mavcYearnCurrentBalance || 0;
      
      const currentAUM = (currentMavcShares * latestMavcPrice) + (currentMavpShares * latestMavpPrice) + currentMavcYearnShares;
      
      if (currentAUM > 0 && (latestMavcPrice > 0 || latestMavpPrice > 0 || currentMavcYearnShares > 0)) {
        filteredPoints = [
          {
            timestamp: timescaleStart,
            date: formatDate(timescaleStart, selectedTimescale),
            totalAUM: currentAUM,
            mavcAUM: currentMavcShares * latestMavcPrice,
            mavpAUM: currentMavpShares * latestMavpPrice,
            mavcYearnAUM: currentMavcYearnShares
          },
          {
            timestamp: currentTime,
            date: formatDate(currentTime, selectedTimescale),
            totalAUM: currentAUM,
            mavcAUM: currentMavcShares * latestMavcPrice,
            mavpAUM: currentMavpShares * latestMavpPrice,
            mavcYearnAUM: currentMavcYearnShares
          }
        ];
      }
    }

    console.log('📈 Timeline Built:', {
      totalTransactions: sortedTimestamps.length,
      totalDataPoints: dataPoints.length,
      filteredPoints: filteredPoints.length,
      timescale: selectedTimescale,
      extrapolated: filteredPoints.length === 2 && (selectedTimescale === "15m" || selectedTimescale === "1h") && dataPoints.length === 0
    });

    return filteredPoints;
  }, [
    userWalletAddress,
    mavcCurrentBalance,
    mavpCurrentBalance,
    mavcYearnCurrentBalance,
    actualMavcYearnBalance,
    mavcPriceHistory,
    mavpPriceHistory,
    mavcSubgraphData,
    mavpSubgraphData,
    mavcYearnSubgraphData,
    mavcYearnConfig,
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
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <div className="mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
              <p className="text-zinc-400 text-sm mb-4">Total Assets Under Management Across All Strategies</p>
            </div>
            <Select value={selectedTimescale} onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}>
              <SelectTrigger className="w-[160px] bg-zinc-800/50 border-zinc-700 text-white">
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
          <span className="text-sm">No portfolio data available for selected time period</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
      <div className="mb-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h3 className="text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
            <p className="text-zinc-400 text-sm mb-4">Total Assets Under Management Across All Strategies</p>
            <div className="text-3xl font-bold text-green-400 mb-2">
              {formatAUM(stats.current)}
            </div>
          </div>
          <Select value={selectedTimescale} onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}>
            <SelectTrigger className="w-[160px] bg-zinc-800/50 border-zinc-700 text-white">
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

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-4">
          <span className="text-xs text-zinc-400">PORTFOLIO PERFORMANCE OVER TIME</span>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <span className="text-xs text-zinc-400">MAVC</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-purple-500"></div>
              <span className="text-xs text-zinc-400">MAVP</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="w-3 h-3 rounded-full bg-orange-500"></div>
              <span className="text-xs text-zinc-400">MAVC Yearn</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
          </span>
        </div>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 5, bottom: 20 }}>
            <defs>
              <linearGradient id="mavcGradientNew" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="mavpGradientNew" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="mavcYearnGradientNew" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
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
              dataKey="mavcAUM"
              stackId="1"
              fill="url(#mavcGradientNew)"
            />
            <Area
              type="monotone"
              dataKey="mavpAUM"
              stackId="1"
              fill="url(#mavpGradientNew)"
            />
            <Area
              type="monotone"
              dataKey="mavcYearnAUM"
              stackId="1"
              fill="url(#mavcYearnGradientNew)"
            />
            <Line
              type="monotone"
              dataKey="totalAUM"
              stroke="#22c55e"
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 4 }}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
