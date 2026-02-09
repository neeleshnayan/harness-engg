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
import { subgraphApi, PoolRateHistoryEntry } from '@/lib/subgraphApi';
import { nettingPoolsApi } from '@/lib/nettingPoolsApi';

interface ChartDataPoint {
  timestamp: number;
  formattedTime: string;
  poolRate: number | null;
  oracleRate: number | null;
  blockNumber: string;
}

interface PriceChartProps {
  poolAddress: string;
  tokenPair: string;
  height?: number;
  limit?: number;
}

// Cache for chart data to avoid refetching when switching pools
const priceChartCache: Map<string, { data: ChartDataPoint[]; oracleRate: number | null; timestamp: number }> = new Map();
const CACHE_TTL_MS = 5 * 60 * 1000; // 5 minutes cache

export default function PriceChart({
  poolAddress,
  tokenPair,
  height = 280,
  limit = 100,
}: PriceChartProps) {
  const [data, setData] = useState<ChartDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [currentOracleRate, setCurrentOracleRate] = useState<number | null>(null);

  useEffect(() => {
    if (!poolAddress) return;

    // Check cache first
    const cacheKey = `${poolAddress}-${tokenPair}-${limit}`;
    const cached = priceChartCache.get(cacheKey);
    if (cached && (Date.now() - cached.timestamp) < CACHE_TTL_MS) {
      setData(cached.data);
      setCurrentOracleRate(cached.oracleRate);
      setLoading(false);
      return;
    }

    // Clear previous data before fetching new pool data
    setData([]);
    setCurrentOracleRate(null);

    const fetchChartData = async () => {
      setLoading(true);
      setError('');

      try {
        // Fetch pool rate history
        const response = await subgraphApi.getPoolRateHistory(poolAddress, limit, 'desc');

        if (!response.rates || response.rates.length === 0) {
          setData([]);
          priceChartCache.set(cacheKey, { data: [], oracleRate: null, timestamp: Date.now() });
          return;
        }

        // Get the FX pair from tokenPair prop (e.g., "kUSD/kEUR" -> "USD/EUR")
        const fxPair = tokenPair
          .replace(/k/g, '')
          .toUpperCase();

        // Fetch current oracle rate
        let oracleRateValue: number | null = null;
        try {
          const oracleResponse = await nettingPoolsApi.getOracleRate(fxPair);
          if (oracleResponse && oracleResponse.rate) {
            oracleRateValue = parseFloat(oracleResponse.rate);
            setCurrentOracleRate(oracleRateValue);
          }
        } catch (oracleErr) {
          console.warn('Could not fetch oracle rate:', oracleErr);
        }

        const chartData: ChartDataPoint[] = response.rates
          .filter((entry: PoolRateHistoryEntry) => entry.rate !== null && entry.rate !== undefined && entry.rate !== 0)
          .map((entry: PoolRateHistoryEntry) => {
            const timestamp = parseInt(entry.blockTimestamp) * 1000;
            // Invert rates: show counter-token per USD instead of USD per counter-token
            // e.g., for USD/INR, show INR per USD (87.5) instead of USD per INR (0.0114)
            const invertedPoolRate = (entry.rate !== 0 && entry.rate !== null) ? 1 / entry.rate : null;
            const invertedOracleRate = (oracleRateValue !== 0 && oracleRateValue !== null) ? 1 / oracleRateValue : null;

            return {
              timestamp,
              formattedTime: new Date(timestamp).toLocaleString('en-US', {
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
              }),
              poolRate: invertedPoolRate,
              oracleRate: invertedOracleRate,
              blockNumber: entry.blockNumber,
            };
          })
          .reverse(); // Show oldest first for chart (chronological order)

        setData(chartData);
        // Update cache
        priceChartCache.set(cacheKey, { data: chartData, oracleRate: oracleRateValue, timestamp: Date.now() });
      } catch (err: any) {
        console.error('Error fetching chart data:', err);
        setError('Failed to load chart data');
      } finally {
        setLoading(false);
      }
    };

    fetchChartData();
  }, [poolAddress, tokenPair, limit]);

  if (loading) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h4 className="text-lg font-medium text-white">Pool Price History</h4>
          <span className="text-xs text-gray-500">{tokenPair}</span>
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
          <h4 className="text-lg font-medium text-white">Pool Price History</h4>
          <span className="text-xs text-gray-500">{tokenPair}</span>
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
          <h4 className="text-lg font-medium text-white">Pool Price History</h4>
          <span className="text-xs text-gray-500">{tokenPair}</span>
        </div>
        <div className="flex items-center justify-center" style={{ height }}>
          <div className="text-gray-400 text-sm">No historical data available yet</div>
        </div>
      </div>
    );
  }

  // Calculate Y-axis domain with padding
  const rates = data
    .flatMap((d) => [d.poolRate, d.oracleRate])
    .filter((r): r is number => r !== null);
  const minRate = Math.min(...rates);
  const maxRate = Math.max(...rates);
  const range = maxRate - minRate;
  const padding = range > 0 ? range * 0.1 : 0.01;

  // Invert tokenPair label for display (e.g., "kUSD/kINR" becomes "kINR/kUSD")
  // This reflects that we're showing counter-token per USD (e.g., INR per USD)
  const invertedTokenPair = tokenPair.includes('/')
    ? tokenPair.split('/').reverse().join('/')
    : tokenPair;

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-medium text-white">Pool Price History</h4>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{invertedTokenPair}</span>
          <span className="text-xs text-gray-600">{data.length} data points</span>
        </div>
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
              domain={[minRate - padding, maxRate + padding]}
              tickFormatter={(value) => value.toFixed(4)}
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
                value?.toFixed(6) || 'N/A',
                name === 'poolRate' ? `${invertedTokenPair} Rate` : 'Oracle Rate',
              ]}
              labelFormatter={(label) => `${label}`}
            />
            <Legend
              wrapperStyle={{ color: '#e2e8f0', fontSize: '12px' }}
              formatter={(value) => (value === 'poolRate' ? `${invertedTokenPair} Rate` : 'Oracle Rate')}
            />
            <Line
              type="monotone"
              dataKey="poolRate"
              stroke="#60a5fa"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
              name="poolRate"
            />
            {currentOracleRate && (
              <Line
                type="monotone"
                dataKey="oracleRate"
                stroke="#34d399"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4, fill: '#10b981' }}
                name="oracleRate"
                strokeDasharray="5 5"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
