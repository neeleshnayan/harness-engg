import React, { useMemo, useState } from "react";
import { AreaChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { MAVCPriceUpdate } from "@/hooks/useMAVCPrice";
import { MAVPPriceUpdate } from "@/hooks/useMAVPPrice";
import { useMAVCConfig } from "@/hooks/useMAVCConfig";
import { useMAVCPriceHistory } from "@/hooks/useMAVCPrice";
import { useMAVPConfig } from "@/hooks/useMAVPConfig";
import { useMAVPPriceHistory } from "@/hooks/useMAVPPrice";
import { useSubgraphData } from "@/hooks/useSubgraphData";
import { useMAVPSubgraphData } from "@/hooks/useMAVPSubgraphData";
import { useMAVCYearnSubgraphData } from "@/hooks/useMAVCYearnSubgraphData";
import { useMAVCYearnConfig } from "@/hooks/useMAVCYearnConfig";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

interface Deposit {
  id: string;
  owner: string;
  assets: string;
  shares: string;
  timestamp: string;
}

interface Withdrawal {
  id: string;
  owner: string;
  receiver: string;
  assets: string;
  shares: string;
  timestamp: string;
}

interface CumulativeAUMChartProps {
  userWalletAddress?: string;
  mavcCurrentBalance?: number;
  mavpCurrentBalance?: number;
  mavcYearnCurrentBalance?: number;
}

type AUMDataPoint = {
  date: string;
  timestamp: number;
  aum: number;
  mavcAUM: number;
  mavpAUM: number;
  mavcYearnAUM: number;
  formattedAUM: string;
};

type CombinedPriceUpdate = {
  timestamp: number;
  price: number;
  strategy: string;
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
    case "15m":
      return now - 15 * 60;
    case "1h":
      return now - 60 * 60;
    case "1d":
      return now - 24 * 60 * 60;
    case "30d":
      return now - 30 * 24 * 60 * 60;
    case "1mo":
      return now - 30 * 24 * 60 * 60;
    default:
      return 0;
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

const getPriceAtTimestamp = (timestamp: number, priceHistory: CombinedPriceUpdate[]): { mavc: number; mavp: number } => {
  let mavcPrice = 0;
  let mavpPrice = 0;

  for (const priceUpdate of priceHistory) {
    const priceTimestamp = priceUpdate.timestamp;
    if (priceTimestamp <= timestamp) {
      if (priceUpdate.strategy === 'MAVC') {
        mavcPrice = priceUpdate.price;
      } else if (priceUpdate.strategy === 'MAVP') {
        mavpPrice = priceUpdate.price;
      }
    }
  }

  return { mavc: mavcPrice, mavp: mavpPrice };
};

const buildCumulativeAUMTimeline = (
  mavcDeposits: Deposit[],
  mavcWithdrawals: Withdrawal[],
  mavpDeposits: Deposit[],
  mavpWithdrawals: Withdrawal[],
  mavcYearnDeposits: Deposit[],
  mavcYearnWithdrawals: Withdrawal[],
  priceHistory: CombinedPriceUpdate[],
  userWalletAddress?: string,
  mavcCurrentBalance?: number,
  mavpCurrentBalance?: number,
  mavcYearnCurrentBalance?: number
): AUMDataPoint[] => {
  if (!userWalletAddress) return [];

  const normalizedAddress = userWalletAddress.toLowerCase();

  const mavcUserDeposits = mavcDeposits
    .filter((d) => d.owner.toLowerCase() === normalizedAddress)
    .map(d => ({
      timestamp: Number(d.timestamp),
      shares: Number(d.shares) / 1e12,
      strategy: 'MAVC' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const mavcUserWithdrawals = mavcWithdrawals
    .filter((w) => w.owner.toLowerCase() === normalizedAddress)
    .map(w => ({
      timestamp: Number(w.timestamp),
      shares: Number(w.shares) / 1e12,
      strategy: 'MAVC' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const mavpUserDeposits = mavpDeposits
    .filter((d) => d.owner.toLowerCase() === normalizedAddress)
    .map(d => ({
      timestamp: Number(d.timestamp),
      shares: Number(d.shares) / 1e12,
      strategy: 'MAVP' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const mavpUserWithdrawals = mavpWithdrawals
    .filter((w) => w.owner.toLowerCase() === normalizedAddress)
    .map(w => ({
      timestamp: Number(w.timestamp),
      shares: Number(w.shares) / 1e12,
      strategy: 'MAVP' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const mavcYearnUserDeposits = mavcYearnDeposits
    .filter((d) => d.owner.toLowerCase() === normalizedAddress)
    .map(d => ({
      timestamp: Number(d.timestamp),
      shares: Number(d.shares) / 1e18,
      strategy: 'MAVC_YEARN' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const mavcYearnUserWithdrawals = mavcYearnWithdrawals
    .filter((w) => w.owner.toLowerCase() === normalizedAddress)
    .map(w => ({
      timestamp: Number(w.timestamp),
      shares: Number(w.shares) / 1e18,
      strategy: 'MAVC_YEARN' as const
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  if (mavcUserDeposits.length === 0 && mavpUserDeposits.length === 0 && mavcYearnUserDeposits.length === 0 && 
      (!mavcCurrentBalance || mavcCurrentBalance === 0) && (!mavpCurrentBalance || mavpCurrentBalance === 0) && 
      (!mavcYearnCurrentBalance || mavcYearnCurrentBalance === 0)) return [];

  const allTimestamps = new Set<number>();
  mavcUserDeposits.forEach(d => allTimestamps.add(d.timestamp));
  mavcUserWithdrawals.forEach(w => allTimestamps.add(w.timestamp));
  mavpUserDeposits.forEach(d => allTimestamps.add(d.timestamp));
  mavpUserWithdrawals.forEach(w => allTimestamps.add(w.timestamp));
  mavcYearnUserDeposits.forEach(d => allTimestamps.add(d.timestamp));
  mavcYearnUserWithdrawals.forEach(w => allTimestamps.add(w.timestamp));

  const dataPoints: AUMDataPoint[] = [];
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

  let mavcCumulativeShares = 0;
  let mavpCumulativeShares = 0;
  let mavcYearnCumulativeShares = 0;

  for (const timestamp of sortedTimestamps) {
    const mavcDepositsAtTime = mavcUserDeposits.filter(d => d.timestamp === timestamp);
    const mavcWithdrawalsAtTime = mavcUserWithdrawals.filter(w => w.timestamp === timestamp);
    const mavpDepositsAtTime = mavpUserDeposits.filter(d => d.timestamp === timestamp);
    const mavpWithdrawalsAtTime = mavpUserWithdrawals.filter(w => w.timestamp === timestamp);
    const mavcYearnDepositsAtTime = mavcYearnUserDeposits.filter(d => d.timestamp === timestamp);
    const mavcYearnWithdrawalsAtTime = mavcYearnUserWithdrawals.filter(w => w.timestamp === timestamp);

    mavcDepositsAtTime.forEach(d => {
      mavcCumulativeShares += d.shares;
    });

    mavcWithdrawalsAtTime.forEach(w => {
      mavcCumulativeShares -= w.shares;
    });

    mavpDepositsAtTime.forEach(d => {
      mavpCumulativeShares += d.shares;
    });

    mavpWithdrawalsAtTime.forEach(w => {
      mavpCumulativeShares -= w.shares;
    });

    mavcYearnDepositsAtTime.forEach(d => {
      mavcYearnCumulativeShares += d.shares;
    });

    mavcYearnWithdrawalsAtTime.forEach(w => {
      mavcYearnCumulativeShares -= w.shares;
    });

    const prices = getPriceAtTimestamp(timestamp, priceHistory);
    
    let mavcAUM = 0;
    let mavpAUM = 0;
    let mavcYearnAUM = 0;
    
    if (mavcCumulativeShares > 0 && prices.mavc > 0) {
      mavcAUM = mavcCumulativeShares * prices.mavc;
    }
    if (mavpCumulativeShares > 0 && prices.mavp > 0) {
      mavpAUM = mavpCumulativeShares * prices.mavp;
    }
    if (mavcYearnCumulativeShares > 0) {
      mavcYearnAUM = mavcYearnCumulativeShares * 1;
    }
    
    const totalAUM = mavcAUM + mavpAUM + mavcYearnAUM;

    if (totalAUM > 0) {
      dataPoints.push({
        date: formatDate(timestamp),
        timestamp,
        aum: totalAUM,
        mavcAUM,
        mavpAUM,
        mavcYearnAUM,
        formattedAUM: formatAUM(totalAUM)
      });
    }
  }

  if ((mavcCurrentBalance !== undefined || mavpCurrentBalance !== undefined || mavcYearnCurrentBalance !== undefined)) {
    const currentTimestamp = Math.floor(Date.now() / 1000);
    const latestMavcPrice = priceHistory.filter(p => p.strategy === 'MAVC').slice(-1)[0]?.price || 0;
    const latestMavpPrice = priceHistory.filter(p => p.strategy === 'MAVP').slice(-1)[0]?.price || 0;
    
    const mavcBalance = mavcCurrentBalance || 0;
    const mavpBalance = mavpCurrentBalance || 0;
    const mavcYearnBalance = mavcYearnCurrentBalance || 0;
    
    let mavcAUM = 0;
    let mavpAUM = 0;
    let mavcYearnAUM = 0;
    
    if (mavcBalance > 0 && latestMavcPrice > 0) {
      mavcAUM = mavcBalance * latestMavcPrice;
    }
    if (mavpBalance > 0 && latestMavpPrice > 0) {
      mavpAUM = mavpBalance * latestMavpPrice;
    }
    if (mavcYearnBalance > 0) {
      mavcYearnAUM = mavcYearnBalance * 1;
    }
    
    console.log('📊 Current AUM Calculation:', {
      mavcBalance,
      mavpBalance,
      mavcYearnBalance,
      latestMavcPrice,
      latestMavpPrice,
      mavcAUM,
      mavpAUM,
      mavcYearnAUM
    });
    
    const totalAUM = mavcAUM + mavpAUM + mavcYearnAUM;

    if (totalAUM > 0) {
      const existingLatestPoint = dataPoints[dataPoints.length - 1];
      
      if (!existingLatestPoint || existingLatestPoint.timestamp < currentTimestamp - 3600) {
        dataPoints.push({
          date: formatDate(currentTimestamp),
          timestamp: currentTimestamp,
          aum: totalAUM,
          mavcAUM,
          mavpAUM,
          mavcYearnAUM,
          formattedAUM: formatAUM(totalAUM)
        });
      } else {
        existingLatestPoint.aum = totalAUM;
        existingLatestPoint.mavcAUM = mavcAUM;
        existingLatestPoint.mavpAUM = mavpAUM;
        existingLatestPoint.mavcYearnAUM = mavcYearnAUM;
        existingLatestPoint.formattedAUM = formatAUM(totalAUM);
      }
    }
  }

  return dataPoints;
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0]?.payload as AUMDataPoint;
  if (!data) return null;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-sm font-bold text-green-400 mb-2">
        Total: {data.formattedAUM}
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
        {data.mavcYearnAUM !== undefined && data.mavcYearnAUM > 0 && (
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
            <span className="text-xs text-zinc-300">MAVC Yearn: {formatAUM(data.mavcYearnAUM)}</span>
          </div>
        )}
      </div>
    </div>
  );
};

export const CumulativeAUMChart: React.FC<CumulativeAUMChartProps> = ({
  userWalletAddress,
  mavcCurrentBalance,
  mavpCurrentBalance,
  mavcYearnCurrentBalance
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");
  const { data: mavcConfig, isLoading: mavcConfigLoading } = useMAVCConfig();
  const { data: mavpConfig, isLoading: mavpConfigLoading } = useMAVPConfig();
  const { data: mavcYearnConfig, isLoading: mavcYearnConfigLoading } = useMAVCYearnConfig();
  const { data: mavcPriceHistory, isLoading: mavcPriceLoading } = useMAVCPriceHistory(mavcConfig?.subgraph_url);
  const { data: mavpPriceHistory, isLoading: mavpPriceLoading } = useMAVPPriceHistory(mavpConfig?.subgraph_url);
  const { data: mavcSubgraphData, isLoading: mavcSubgraphLoading } = useSubgraphData(mavcConfig?.subgraph_url);
  const { data: mavpSubgraphData, isLoading: mavpSubgraphLoading } = useMAVPSubgraphData(mavpConfig?.subgraph_url);
  const { data: mavcYearnSubgraphData, isLoading: mavcYearnSubgraphLoading } = useMAVCYearnSubgraphData(mavcYearnConfig?.subgraph_url);

  const isLoading = mavcConfigLoading || mavpConfigLoading || mavcYearnConfigLoading || mavcPriceLoading || mavpPriceLoading || mavcSubgraphLoading || mavpSubgraphLoading || mavcYearnSubgraphLoading;

  const combinedPriceHistory = useMemo(() => {
    const combined: CombinedPriceUpdate[] = [];
    
    if (mavcPriceHistory) {
      mavcPriceHistory.forEach(update => {
        combined.push({
          timestamp: Number(update.timestamp),
          price: Number(update.price),
          strategy: 'MAVC'
        });
      });
    }

    if (mavpPriceHistory) {
      mavpPriceHistory.forEach(update => {
        combined.push({
          timestamp: Number(update.timestamp),
          price: Number(update.price),
          strategy: 'MAVP'
        });
      });
    }

    return combined.sort((a, b) => a.timestamp - b.timestamp);
  }, [mavcPriceHistory, mavpPriceHistory]);

  const aumTimeline = useMemo(
    () => {
      const timeline = buildCumulativeAUMTimeline(
        mavcSubgraphData?.deposits || [],
        mavcSubgraphData?.withdrawals || [],
        mavpSubgraphData?.deposits || [],
        mavpSubgraphData?.withdrawals || [],
        mavcYearnSubgraphData?.deposits || [],
        mavcYearnSubgraphData?.withdrawals || [],
        combinedPriceHistory,
        userWalletAddress,
        mavcCurrentBalance,
        mavpCurrentBalance,
        mavcYearnCurrentBalance
      );
      
      if (timeline.length === 0) return [];
      
      const timescaleStart = getTimescaleSeconds(selectedTimescale);
      const pointsAfterStart = timeline.filter(point => point.timestamp >= timescaleStart);
      
      if (pointsAfterStart.length === 0) return [];
      
      let filteredTimeline = pointsAfterStart.map(point => ({
        ...point,
        date: formatDate(point.timestamp, selectedTimescale)
      }));
      
      const firstPointBeforeStart = timeline.filter(point => point.timestamp < timescaleStart).slice(-1)[0];
      if (firstPointBeforeStart && filteredTimeline[0].timestamp !== timescaleStart) {
        const startPoint: AUMDataPoint = {
          date: formatDate(timescaleStart, selectedTimescale),
          timestamp: timescaleStart,
          aum: firstPointBeforeStart.aum,
          mavcAUM: firstPointBeforeStart.mavcAUM,
          mavpAUM: firstPointBeforeStart.mavpAUM,
          mavcYearnAUM: firstPointBeforeStart.mavcYearnAUM,
          formattedAUM: formatAUM(firstPointBeforeStart.aum)
        };
        filteredTimeline = [startPoint, ...filteredTimeline];
      }
      
      return filteredTimeline;
    },
    [mavcSubgraphData, mavpSubgraphData, mavcYearnSubgraphData, combinedPriceHistory, userWalletAddress, mavcCurrentBalance, mavpCurrentBalance, mavcYearnCurrentBalance, selectedTimescale]
  );

  const stats = useMemo(() => {
    if (aumTimeline.length === 0) return null;

    const latestDataPoint = aumTimeline[aumTimeline.length - 1];
    const firstDataPoint = aumTimeline[0];
    const aumChange = latestDataPoint.aum - firstDataPoint.aum;
    
    const threshold = 0.01;
    let aumChangePercent: string;
    
    if (firstDataPoint.aum < threshold) {
      if (latestDataPoint.aum > threshold) {
        aumChangePercent = Math.round(latestDataPoint.aum).toString();
      } else {
        aumChangePercent = '0';
      }
    } else {
      const percent = (aumChange / firstDataPoint.aum) * 100;
      aumChangePercent = percent.toFixed(2);
    }

    return {
      currentAUM: latestDataPoint.aum,
      startAUM: firstDataPoint.aum,
      aumChange,
      aumChangePercent,
      isPositive: aumChange >= 0
    };
  }, [aumTimeline]);

  if (isLoading) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <div className="mb-6">
          <div className="flex items-start justify-between mb-4">
            <div className="flex-1">
              <h3 className="text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
              <p className="text-zinc-400 text-sm mb-4">Total Assets Under Management Across All Strategies</p>
              <div className="text-3xl font-bold text-green-400 mb-2">
                <Skeleton className="h-10 w-32 bg-zinc-700/50" />
              </div>
            </div>
            <Skeleton className="h-10 w-[160px] bg-zinc-700/50" />
          </div>
        </div>

        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-zinc-400">PORTFOLIO PERFORMANCE OVER TIME</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <Skeleton className="h-3 w-3 rounded-full bg-zinc-700/50" />
            <Skeleton className="h-4 w-12 bg-zinc-700/50" />
          </div>
        </div>

        <div className="h-64">
          <Skeleton className="h-full w-full bg-zinc-700/50 rounded-lg" />
        </div>

        <div className="flex justify-between mt-4 text-xs">
          <Skeleton className="h-4 w-24 bg-zinc-700/50" />
          <Skeleton className="h-4 w-24 bg-zinc-700/50" />
        </div>
      </div>
    );
  }

  if (aumTimeline.length === 0) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-center py-6 text-zinc-500">
          <Activity className="w-4 h-4 mr-2" />
          <span className="text-sm">No portfolio performance history available</span>
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
              {formatAUM(stats.currentAUM)}
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
                <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                <span className="text-xs text-zinc-400">MAVC Yearn</span>
              </div>
            </div>
          </div>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.aumChangePercent}%
          </span>
        </div>
      </div>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart 
            data={aumTimeline} 
            margin={{ top: 5, right: 5, left: 5, bottom: 20 }}
          >
            <defs>
              <linearGradient id="mavcGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="mavpGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
              </linearGradient>
              <linearGradient id="mavcYearnGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.4}/>
                <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
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
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#mavcGradient)"
            />
            <Area
              type="monotone"
              dataKey="mavpAUM"
              stackId="1"
              stroke="#a855f7"
              strokeWidth={2}
              fill="url(#mavpGradient)"
            />
            <Area
              type="monotone"
              dataKey="mavcYearnAUM"
              stackId="1"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#mavcYearnGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex justify-between mt-4 text-xs">
        <div className="text-zinc-400">
          Start: {formatAUM(stats.startAUM)}
        </div>
        <div className="text-zinc-300 font-semibold">
          Current: {formatAUM(stats.currentAUM)}
        </div>
      </div>
    </div>
  );
};

