import React, { useMemo } from "react";
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
}

type AUMDataPoint = {
  date: string;
  timestamp: number;
  aum: number;
  formattedAUM: string;
};

type CombinedPriceUpdate = {
  timestamp: number;
  price: number;
  strategy: string;
};

const formatDate = (timestamp: number): string => {
  const date = new Date(timestamp * 1000);
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
  priceHistory: CombinedPriceUpdate[],
  userWalletAddress?: string,
  mavcCurrentBalance?: number,
  mavpCurrentBalance?: number
): AUMDataPoint[] => {
  if (!userWalletAddress || priceHistory.length === 0) return [];

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

  if (mavcUserDeposits.length === 0 && mavpUserDeposits.length === 0 && (!mavcCurrentBalance || mavcCurrentBalance === 0) && (!mavpCurrentBalance || mavpCurrentBalance === 0)) return [];

  const allTimestamps = new Set<number>();
  mavcUserDeposits.forEach(d => allTimestamps.add(d.timestamp));
  mavcUserWithdrawals.forEach(w => allTimestamps.add(w.timestamp));
  mavpUserDeposits.forEach(d => allTimestamps.add(d.timestamp));
  mavpUserWithdrawals.forEach(w => allTimestamps.add(w.timestamp));

  const dataPoints: AUMDataPoint[] = [];
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

  let mavcCumulativeShares = 0;
  let mavpCumulativeShares = 0;

  for (const timestamp of sortedTimestamps) {
    const mavcDepositsAtTime = mavcUserDeposits.filter(d => d.timestamp === timestamp);
    const mavcWithdrawalsAtTime = mavcUserWithdrawals.filter(w => w.timestamp === timestamp);
    const mavpDepositsAtTime = mavpUserDeposits.filter(d => d.timestamp === timestamp);
    const mavpWithdrawalsAtTime = mavpUserWithdrawals.filter(w => w.timestamp === timestamp);

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

    const prices = getPriceAtTimestamp(timestamp, priceHistory);
    
    let totalAUM = 0;
    if (mavcCumulativeShares > 0 && prices.mavc > 0) {
      totalAUM += mavcCumulativeShares * prices.mavc;
    }
    if (mavpCumulativeShares > 0 && prices.mavp > 0) {
      totalAUM += mavpCumulativeShares * prices.mavp;
    }

    if (totalAUM > 0) {
      dataPoints.push({
        date: formatDate(timestamp),
        timestamp,
        aum: totalAUM,
        formattedAUM: formatAUM(totalAUM)
      });
    }
  }

  if ((mavcCurrentBalance !== undefined || mavpCurrentBalance !== undefined) && priceHistory.length > 0) {
    const currentTimestamp = Math.floor(Date.now() / 1000);
    const latestMavcPrice = priceHistory.filter(p => p.strategy === 'MAVC').slice(-1)[0]?.price || 0;
    const latestMavpPrice = priceHistory.filter(p => p.strategy === 'MAVP').slice(-1)[0]?.price || 0;
    
    const mavcBalance = mavcCurrentBalance || 0;
    const mavpBalance = mavpCurrentBalance || 0;
    
    let totalAUM = 0;
    if (mavcBalance > 0 && latestMavcPrice > 0) {
      totalAUM += mavcBalance * latestMavcPrice;
    }
    if (mavpBalance > 0 && latestMavpPrice > 0) {
      totalAUM += mavpBalance * latestMavpPrice;
    }

    if (totalAUM > 0) {
      const existingLatestPoint = dataPoints[dataPoints.length - 1];
      
      if (!existingLatestPoint || existingLatestPoint.timestamp < currentTimestamp - 3600) {
        dataPoints.push({
          date: formatDate(currentTimestamp),
          timestamp: currentTimestamp,
          aum: totalAUM,
          formattedAUM: formatAUM(totalAUM)
        });
      } else if (existingLatestPoint && existingLatestPoint.timestamp < currentTimestamp) {
        existingLatestPoint.aum = totalAUM;
        existingLatestPoint.formattedAUM = formatAUM(totalAUM);
      }
    }
  }

  return dataPoints;
};

const CustomTooltip = ({ active, payload }: any) => {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload as AUMDataPoint;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-1">{data.date}</p>
      <p className="text-sm font-bold text-green-400">
        {data.formattedAUM}
      </p>
    </div>
  );
};

export const CumulativeAUMChart: React.FC<CumulativeAUMChartProps> = ({
  userWalletAddress,
  mavcCurrentBalance,
  mavpCurrentBalance
}) => {
  const { data: mavcConfig } = useMAVCConfig();
  const { data: mavpConfig } = useMAVPConfig();
  const { data: mavcPriceHistory } = useMAVCPriceHistory(mavcConfig?.subgraph_url);
  const { data: mavpPriceHistory } = useMAVPPriceHistory(mavpConfig?.subgraph_url);
  const { data: mavcSubgraphData } = useSubgraphData(mavcConfig?.subgraph_url);
  const { data: mavpSubgraphData } = useMAVPSubgraphData(mavpConfig?.subgraph_url);

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
    () => buildCumulativeAUMTimeline(
      mavcSubgraphData?.deposits || [],
      mavcSubgraphData?.withdrawals || [],
      mavpSubgraphData?.deposits || [],
      mavpSubgraphData?.withdrawals || [],
      combinedPriceHistory,
      userWalletAddress,
      mavcCurrentBalance,
      mavpCurrentBalance
    ),
    [mavcSubgraphData, mavpSubgraphData, combinedPriceHistory, userWalletAddress, mavcCurrentBalance, mavpCurrentBalance]
  );

  const stats = useMemo(() => {
    if (aumTimeline.length === 0) return null;

    const latestDataPoint = aumTimeline[aumTimeline.length - 1];
    const firstDataPoint = aumTimeline[0];
    const aumChange = latestDataPoint.aum - firstDataPoint.aum;
    const aumChangePercent = firstDataPoint.aum > 0 
      ? ((aumChange / firstDataPoint.aum) * 100).toFixed(2)
      : '0';

    return {
      currentAUM: latestDataPoint.aum,
      startAUM: firstDataPoint.aum,
      aumChange,
      aumChangePercent,
      isPositive: aumChange >= 0
    };
  }, [aumTimeline]);

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
        <h3 className="text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
        <p className="text-zinc-400 text-sm mb-4">Total Assets Under Management Across All Strategies</p>
        <div className="text-3xl font-bold text-green-400 mb-2">
          {formatAUM(stats.currentAUM)}
        </div>
      </div>

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">PORTFOLIO PERFORMANCE OVER TIME</span>
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
              <linearGradient id="cumulativeAUMGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3}/>
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
              dataKey="aum"
              stroke="#10b981"
              strokeWidth={2}
              fill="url(#cumulativeAUMGradient)"
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

