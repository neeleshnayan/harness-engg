'use client';

import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import { subgraphApi, PoolBalanceHistoryEntry } from '@/lib/subgraphApi';

interface ChartDataPoint {
  timestamp: number;
  formattedTime: string;
  balance0: number;
  balance1: number;
  blockNumber: string;
}

interface BalancesChartProps {
  poolAddress: string;
  token0Symbol: string;
  token1Symbol: string;
  token0Address: string;  // Display order token0 address
  token1Address: string;  // Display order token1 address
  height?: number;
  limit?: number;
}

// Cache for chart data to avoid refetching when switching pools
const balanceChartCache: Map<string, { data: ChartDataPoint[]; timestamp: number }> = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes cache

export default function BalancesChart({
  poolAddress,
  token0Symbol,
  token1Symbol,
  token0Address,
  token1Address,
  height = 280,
  limit = 100,
}: BalancesChartProps) {
  const [data, setData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!poolAddress) return;

    // Check cache first
    const cacheKey = `${poolAddress}-${limit}`;
    const cached = balanceChartCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp) < CACHE_TTL_MS) {
      setData(cached.data);
      setLoading(false);
      return;
    }

    // Clear previous data before fetching new pool data
    setData([]);

    const fetchChartData = async () => {
      setLoading(true);
      setError('');

      try {
        const response = await subgraphApi.getPoolBalanceHistory(poolAddress, limit, 'desc');

        if (!response.balances || response.balances.length === 0) {
          setData([]);
          balanceChartCache.set(cacheKey, { data: [], timestamp: Date.now() });
          return;
        }

        // Check if we need to swap balances to match display order
        // The first entry's tokens array tells us the pool's native order
        const firstEntry = response.balances.find((e: PoolBalanceHistoryEntry) =>
          e.tokens && e.tokens.length >= 2
        );
        let needsSwap = false;
        if (firstEntry && firstEntry.tokens) {
          // Subgraph stores tokens in pool's native order
          // Check if native token0 matches display token0
          const nativeToken0 = firstEntry.tokens[0].toLowerCase();
          const displayToken0 = token0Address.toLowerCase();
          needsSwap = (nativeToken0 !== displayToken0);
        }

        const chartData: ChartDataPoint[] = response.balances
          .filter((entry: PoolBalanceHistoryEntry) =>
            entry.balances && entry.balances.length >= 2
          )
          .map((entry: PoolBalanceHistoryEntry) => {
            const timestamp = parseInt(entry.blockTimestamp) * 1000;
            // Swap balances if needed to match display order (kUSD first)
            const displayBalance0 = needsSwap ? entry.balances[1] : entry.balances[0];
            const displayBalance1 = needsSwap ? entry.balances[0] : entry.balances[1];

            return {
              timestamp,
              formattedTime: new Date(timestamp).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              }),
              balance0: displayBalance0, // Display order token0 (kUSD)
              balance1: displayBalance1, // Display order token1 (other)
              blockNumber: entry.blockNumber,
            };
          })
          .reverse(); // Show oldest first for chart (chronological order)

        setData(chartData);
        // Update cache
        balanceChartCache.set(cacheKey, { data: chartData, timestamp: Date.now() });
      } catch (err: any) {
        console.error('Error fetching balance chart data:', err);
        setError('Failed to load balance chart data');
      } finally {
        setLoading(false);
      }
    };

    fetchChartData();
  }, [poolAddress, limit]);

  if (loading) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-lg font-medium text-white">Token Balances History</h4>
        </div>
        <div className="flex items-center justify-center" style={{ height }}>
          <div className="text-gray-400 text-sm">Loading chart...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-lg font-medium text-white">Token Balances History</h4>
        </div>
        <div className="flex items-center justify-center" style={{ height }}>
          <div className="text-red-400 text-sm">{error}</div>
        </div>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-lg font-medium text-white">Token Balances History</h4>
        </div>
        <div className="flex items-center justify-center" style={{ height }}>
          <div className="text-gray-400 text-sm">No balance data available yet</div>
        </div>
      </div>
    );
  }

  // Calculate Y-axis domains for each token separately with tight ranges
  const balance0Values = data.map((d) => d.balance0);
  const balance1Values = data.map((d) => d.balance1);

  const minBalance0 = Math.min(...balance0Values);
  const maxBalance0 = Math.max(...balance0Values);
  const minBalance1 = Math.min(...balance1Values);
  const maxBalance1 = Math.max(...balance1Values);

  // Tight y-axis range with 5k padding for sensitivity to small changes
  const padding = 5000;
  const domain0 = [Math.max(0, minBalance0 - padding), maxBalance0 + padding];
  const domain1 = [Math.max(0, minBalance1 - padding), maxBalance1 + padding];

  // Format large numbers
  const formatBalance = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(2)}K`;
    return value.toFixed(0);
  };

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-medium text-white">Token Balances History</h4>
        <span className="text-xs text-gray-500">{data.length} data points</span>
      </div>
      <div className="grid grid-cols-2 gap-4">
        {/* Token 0 Chart */}
        <div className="w-full" style={{ height }}>
          <div className="text-center mb-2">
            <span className="text-sm font-medium text-blue-400">{token0Symbol} Balance</span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="formattedTime"
                stroke="#94a3b8"
                fontSize={10}
                tickMargin={8}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#94a3b8"
                fontSize={10}
                tickMargin={8}
                domain={domain0}
                tickFormatter={formatBalance}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                  fontSize: '12px',
                }}
                formatter={(value: number) => [formatBalance(value), `${token0Symbol} Balance`]}
                labelFormatter={(label) => `${label}`}
              />
              <Line
                type="monotone"
                dataKey="balance0"
                stroke="#60a5fa"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#3b82f6' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Token 1 Chart */}
        <div className="w-full" style={{ height }}>
          <div className="text-center mb-2">
            <span className="text-sm font-medium text-green-400">{token1Symbol} Balance</span>
          </div>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 5, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis
                dataKey="formattedTime"
                stroke="#94a3b8"
                fontSize={10}
                tickMargin={8}
                interval="preserveStartEnd"
              />
              <YAxis
                stroke="#94a3b8"
                fontSize={10}
                tickMargin={8}
                domain={domain1}
                tickFormatter={formatBalance}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #475569',
                  borderRadius: '8px',
                  color: '#e2e8f0',
                  fontSize: '12px',
                }}
                formatter={(value: number) => [formatBalance(value), `${token1Symbol} Balance`]}
                labelFormatter={(label) => `${label}`}
              />
              <Line
                type="monotone"
                dataKey="balance1"
                stroke="#34d399"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#10b981' }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

