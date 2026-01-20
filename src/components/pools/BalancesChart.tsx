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
  height?: number;
  limit?: number;
}

export default function BalancesChart({
  poolAddress,
  token0Symbol,
  token1Symbol,
  height = 280,
  limit = 100,
}: BalancesChartProps) {
  const [data, setData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!poolAddress) return;

    const fetchChartData = async () => {
      setLoading(true);
      setError('');

      try {
        const response = await subgraphApi.getPoolBalanceHistory(poolAddress, limit, 'desc');

        if (!response.balances || response.balances.length === 0) {
          setData([]);
          return;
        }

        const chartData: ChartDataPoint[] = response.balances
          .filter((entry: PoolBalanceHistoryEntry) =>
            entry.balances && entry.balances.length >= 2
          )
          .map((entry: PoolBalanceHistoryEntry) => {
            const timestamp = parseInt(entry.blockTimestamp) * 1000;
            // Balances are in token order: balances[0] = first token, balances[1] = second token
            // The order matches the tokens array from the subgraph
            return {
              timestamp,
              formattedTime: new Date(timestamp).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              }),
              balance0: entry.balances[0], // First token (token0)
              balance1: entry.balances[1], // Second token (token1)
              blockNumber: entry.blockNumber,
            };
          })
          .reverse(); // Show oldest first for chart (chronological order)

        setData(chartData);
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

  // Calculate Y-axis domain with padding
  const allBalances = data.flatMap((d) => [d.balance0, d.balance1]);
  const minBalance = Math.min(...allBalances);
  const maxBalance = Math.max(...allBalances);
  const range = maxBalance - minBalance;
  const padding = range > 0 ? range * 0.1 : 1000;

  // Format large numbers
  const formatBalance = (value: number) => {
    if (value >= 1000000) return `${(value / 1000000).toFixed(2)}M`;
    if (value >= 1000) return `${(value / 1000).toFixed(2)}K`;
    return value.toFixed(2);
  };

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-medium text-white">Token Balances History</h4>
        <span className="text-xs text-gray-500">{data.length} data points</span>
      </div>
      <div className="w-full" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
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
              domain={[minBalance - padding, maxBalance + padding]}
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
              formatter={(value: number, name: string) => [
                formatBalance(value),
                name === 'balance0' ? `${token0Symbol} Balance` : `${token1Symbol} Balance`,
              ]}
              labelFormatter={(label) => `${label}`}
            />
            <Legend
              wrapperStyle={{ color: '#e2e8f0', fontSize: '12px' }}
              formatter={(value) => (value === 'balance0' ? `${token0Symbol} Balance` : `${token1Symbol} Balance`)}
            />
            <Line
              type="monotone"
              dataKey="balance0"
              stroke="#60a5fa"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
              name="balance0"
            />
            <Line
              type="monotone"
              dataKey="balance1"
              stroke="#34d399"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#10b981' }}
              name="balance1"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

