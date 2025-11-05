import React, { useMemo } from "react";
import { AreaChart, Area, ResponsiveContainer, YAxis } from "recharts";
import { TrendingUp, TrendingDown } from "lucide-react";
import { useMAVPPriceHistory } from "@/hooks/useMAVPPrice";

interface MAVPMiniChartProps {
  subgraphUrl?: string;
  tokenAddress?: string;
  userBalance?: number;  // User's MAVP token balance
}

type PricePoint = {
  timestamp: number;
  price: number;
};

const buildPriceTimeline = (priceUpdates: any[], userBalance?: number): PricePoint[] => {
  const THIRTY_MINUTES = 30 * 60 * 1000; // 30 minutes in milliseconds
  const bucket = new Map<number, number[]>();

  // Bucket prices into 30-minute intervals
  priceUpdates.forEach((update) => {
    const ts = Number(update.timestamp) * 1000; // Convert to milliseconds
    if (!Number.isFinite(ts)) return;

    const price = Number(update.price);
    if (!Number.isFinite(price)) return;

    // Round down to nearest 30-minute interval
    const bucketKey = Math.floor(ts / THIRTY_MINUTES) * THIRTY_MINUTES;

    const prices = bucket.get(bucketKey) ?? [];
    prices.push(price);
    bucket.set(bucketKey, prices);
  });

  // Average prices in each bucket and sort by timestamp
  return Array.from(bucket.entries())
    .map(([timestamp, prices]) => {
      const avgPrice = prices.reduce((sum, p) => sum + p, 0) / prices.length;
      // If userBalance is provided, multiply price by balance to show portfolio value
      const value = userBalance && userBalance > 0 ? avgPrice * userBalance : avgPrice;
      return {
        timestamp,
        price: value
      };
    })
    .sort((a, b) => a.timestamp - b.timestamp);
};

export const MAVPMiniChart: React.FC<MAVPMiniChartProps> = ({ subgraphUrl, tokenAddress, userBalance }) => {
  const { data: priceHistory, isLoading } = useMAVPPriceHistory(subgraphUrl);

  const priceTimeline = useMemo(() => buildPriceTimeline(priceHistory ?? [], userBalance), [priceHistory, userBalance]);

  // Calculate price statistics
  const priceStats = useMemo(() => {
    if (priceTimeline.length === 0) return null;

    const prices = priceTimeline.map(p => p.price);
    const firstPrice = prices[0];
    const lastPrice = prices[prices.length - 1];
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    const change = lastPrice - firstPrice;
    const changePercent = (change / firstPrice) * 100;

    return {
      firstPrice,
      lastPrice,
      minPrice,
      maxPrice,
      change,
      changePercent,
      isPositive: change >= 0
    };
  }, [priceTimeline]);

  // Calculate dynamic y-axis domain for price chart
  const priceDomain = useMemo(() => {
    if (!priceStats) return [0, 20];

    const { minPrice, maxPrice } = priceStats;

    // If all prices are the same, create a small range around that price
    if (minPrice === maxPrice) {
      const padding = minPrice * 0.01; // 1% padding
      return [minPrice - padding, maxPrice + padding];
    }

    // Add 5% padding to top and bottom for better visualization
    const range = maxPrice - minPrice;
    const padding = range * 0.05;

    return [
      Math.max(0, minPrice - padding), // Don't go below 0
      maxPrice + padding
    ];
  }, [priceStats]);

  if (isLoading || priceTimeline.length === 0 || !priceStats) {
    return null;
  }

  return (
    <div className="mt-3 pt-3 border-t border-zinc-600/30">
      {/* Price Change Summary */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-400">
            {userBalance && userBalance > 0 ? 'Portfolio Change' : 'Price Change'}
          </span>
          {priceStats.isPositive ? (
            <TrendingUp className="w-3 h-3 text-green-400" />
          ) : (
            <TrendingDown className="w-3 h-3 text-red-400" />
          )}
        </div>
        <div className="flex items-center gap-3">
          <span className={`text-sm font-semibold ${priceStats.isPositive ? 'text-green-400' : 'text-red-400'}`}>
            {priceStats.isPositive ? '+' : ''}{priceStats.changePercent.toFixed(2)}%
          </span>
          <span className="text-xs text-zinc-400">
            ${priceStats.firstPrice.toFixed(4)} → ${priceStats.lastPrice.toFixed(4)}
          </span>
        </div>
      </div>

      {/* Mini Chart */}
      <div className="h-16">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={priceTimeline} margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="miniMAVPPriceArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.4} />
                <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.05} />
              </linearGradient>
            </defs>
            <YAxis domain={priceDomain} hide />
            <Area
              type="monotone"
              dataKey="price"
              stroke="#3b82f6"
              strokeWidth={1.5}
              fill="url(#miniMAVPPriceArea)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Price Range */}
      <div className="flex justify-between mt-1 text-xs text-zinc-500">
        <span>Low: ${priceStats.minPrice.toFixed(4)}</span>
        <span>High: ${priceStats.maxPrice.toFixed(4)}</span>
      </div>
    </div>
  );
};
