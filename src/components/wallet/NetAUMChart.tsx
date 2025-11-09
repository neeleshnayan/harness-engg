import React, { useMemo } from "react";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, Area, AreaChart } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { MAVCPriceUpdate } from "@/hooks/useMAVCPrice";

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

interface NetAUMChartProps {
  deposits: Deposit[];
  withdrawals: Withdrawal[];
  priceHistory: MAVCPriceUpdate[];
  userWalletAddress?: string;
  tokenSymbol: string;
  currentBalance?: number;
}

type AUMDataPoint = {
  date: string;
  timestamp: number;
  netShares: number;
  price: number;
  aum: number;
  formattedAUM: string;
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

const getPriceAtTimestamp = (timestamp: number, priceHistory: MAVCPriceUpdate[]): number => {
  if (priceHistory.length === 0) return 0;
  
  let lastValidPrice = 0;
  for (const priceUpdate of priceHistory) {
    const priceTimestamp = Number(priceUpdate.timestamp);
    if (priceTimestamp <= timestamp) {
      lastValidPrice = Number(priceUpdate.price);
    } else {
      break;
    }
  }
  
  return lastValidPrice;
};

const buildNetAUMTimeline = (
  deposits: Deposit[],
  withdrawals: Withdrawal[],
  priceHistory: MAVCPriceUpdate[],
  userWalletAddress?: string,
  currentBalance?: number
): AUMDataPoint[] => {
  if (!userWalletAddress || priceHistory.length === 0) return [];

  const normalizedAddress = userWalletAddress.toLowerCase();
  
  const userDeposits = deposits
    .filter((d) => d.owner.toLowerCase() === normalizedAddress)
    .map(d => ({
      timestamp: Number(d.timestamp),
      shares: Number(d.shares) / 1e12
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  const userWithdrawals = withdrawals
    .filter((w) => w.owner.toLowerCase() === normalizedAddress)
    .map(w => ({
      timestamp: Number(w.timestamp),
      shares: Number(w.shares) / 1e12
    }))
    .sort((a, b) => a.timestamp - b.timestamp);

  if (userDeposits.length === 0 && (!currentBalance || currentBalance === 0)) return [];

  const allTimestamps = new Set<number>();
  userDeposits.forEach(d => allTimestamps.add(d.timestamp));
  userWithdrawals.forEach(w => allTimestamps.add(w.timestamp));

  const dataPoints: AUMDataPoint[] = [];
  const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);
  
  let cumulativeShares = 0;

  for (const timestamp of sortedTimestamps) {
    const depositsAtTime = userDeposits.filter(d => d.timestamp === timestamp);
    const withdrawalsAtTime = userWithdrawals.filter(w => w.timestamp === timestamp);
    
    depositsAtTime.forEach(d => {
      cumulativeShares += d.shares;
    });
    
    withdrawalsAtTime.forEach(w => {
      cumulativeShares -= w.shares;
    });

    const price = getPriceAtTimestamp(timestamp, priceHistory);
    const aum = cumulativeShares * price;

    if (price > 0) {
      dataPoints.push({
        date: formatDate(timestamp),
        timestamp,
        netShares: cumulativeShares,
        price,
        aum,
        formattedAUM: formatAUM(aum)
      });
    }
  }

  if (currentBalance !== undefined && priceHistory.length > 0) {
    const currentTimestamp = Math.floor(Date.now() / 1000);
    const latestPriceUpdate = priceHistory[priceHistory.length - 1];
    const currentPrice = Number(latestPriceUpdate.price);
    
    if (currentPrice > 0) {
      const currentAUM = (currentBalance || 0) * currentPrice;
      const existingLatestPoint = dataPoints[dataPoints.length - 1];
      
      if (!existingLatestPoint || existingLatestPoint.timestamp < currentTimestamp - 3600) {
        dataPoints.push({
          date: formatDate(currentTimestamp),
          timestamp: currentTimestamp,
          netShares: currentBalance || 0,
          price: currentPrice,
          aum: currentAUM,
          formattedAUM: formatAUM(currentAUM)
        });
      } else if (existingLatestPoint && existingLatestPoint.timestamp < currentTimestamp) {
        existingLatestPoint.netShares = currentBalance || 0;
        existingLatestPoint.price = currentPrice;
        existingLatestPoint.aum = currentAUM;
        existingLatestPoint.formattedAUM = formatAUM(currentAUM);
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
      <p className="text-xs text-zinc-500 mt-1">
        {data.netShares.toFixed(2)} tokens × ${data.price.toFixed(4)}
      </p>
    </div>
  );
};

export const NetAUMChart: React.FC<NetAUMChartProps> = ({
  deposits,
  withdrawals,
  priceHistory,
  userWalletAddress,
  tokenSymbol,
  currentBalance
}) => {
  const aumTimeline = useMemo(
    () => buildNetAUMTimeline(deposits, withdrawals, priceHistory, userWalletAddress, currentBalance),
    [deposits, withdrawals, priceHistory, userWalletAddress, currentBalance]
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
      <div className="mt-3 pt-3 border-t border-zinc-600/30">
        <div className="flex items-center justify-center py-6 text-zinc-500">
          <Activity className="w-4 h-4 mr-2" />
          <span className="text-xs">No AUM history available</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="mt-3 pt-3 border-t border-zinc-600/30">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">NET AUM Over Time</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.aumChangePercent}%
          </span>
        </div>
      </div>

      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart 
            data={aumTimeline} 
            margin={{ top: 5, right: 5, left: 5, bottom: 20 }}
          >
            <defs>
              <linearGradient id="aumGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
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
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#aumGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="flex justify-between mt-2 text-xs">
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




