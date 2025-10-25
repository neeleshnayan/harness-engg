import React, { useMemo } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
} from "recharts";
import { useSubgraphData } from "@/hooks/useSubgraphData";
import { useMAVCPriceHistory, MAVCPriceUpdate } from "@/hooks/useMAVCPrice";

const formatNumber = (value?: string | number, options?: Intl.NumberFormatOptions) => {
  if (value === undefined || value === null) return '0';
  const parsed = typeof value === 'string' ? Number(value) : value;
  if (!Number.isFinite(parsed)) return '0';
  return new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 2,
    minimumFractionDigits: 0,
    ...options,
  }).format(parsed);
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);

const formatShare = (value: number) =>
  new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 4,
  }).format(value);

const formatTimestamp = (value?: string) => {
  if (!value) return '';
  const date = Number(value) * 1000;
  if (!Number.isFinite(date)) return '';
  return new Date(date).toLocaleString();
};

const formatShortDate = (timestamp: number) =>
  new Date(timestamp).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

const formatDateTime = (timestamp: number) => {
  const date = new Date(timestamp);
  return date.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  });
};

const formatAddress = (address?: string) => {
  if (!address) return '';
  return `${address.slice(0, 6)}...${address.slice(-4)}`;
};

type TimelinePoint = {
  timestamp: number;
  deposits: number;
  withdrawals: number;
  minted: number;
  burned: number;
  cumDeposits: number;
  cumWithdrawals: number;
  cumMinted: number;
  cumBurned: number;
};

const buildTimeline = (
  deposits: Array<{ assets: string; shares: string; timestamp: string }>,
  withdrawals: Array<{ assets: string; shares: string; timestamp: string }>,
): TimelinePoint[] => {
  const bucket = new Map<number, { deposits: number; withdrawals: number; minted: number; burned: number }>();

  deposits.forEach((entry) => {
    const ts = Number(entry.timestamp) * 1000;
    if (!Number.isFinite(ts)) return;
    const assets = Number(entry.assets);
    const shares = Number(entry.shares);
    const current = bucket.get(ts) ?? { deposits: 0, withdrawals: 0, minted: 0, burned: 0 };
    current.deposits += Number.isFinite(assets) ? assets : 0;
    current.minted += Number.isFinite(shares) ? shares : 0;
    bucket.set(ts, current);
  });

  withdrawals.forEach((entry) => {
    const ts = Number(entry.timestamp) * 1000;
    if (!Number.isFinite(ts)) return;
    const assets = Number(entry.assets);
    const shares = Number(entry.shares);
    const current = bucket.get(ts) ?? { deposits: 0, withdrawals: 0, minted: 0, burned: 0 };
    current.withdrawals += Number.isFinite(assets) ? assets : 0;
    current.burned += Number.isFinite(shares) ? shares : 0;
    bucket.set(ts, current);
  });

  const sorted = Array.from(bucket.entries())
    .sort(([a], [b]) => a - b)
    .map(([timestamp, values]) => ({ timestamp, ...values }));

  let cumDeposits = 0;
  let cumWithdrawals = 0;
  let cumMinted = 0;
  let cumBurned = 0;

  return sorted.map(({ timestamp, deposits: dep, withdrawals: wit, minted, burned }) => {
    cumDeposits += dep;
    cumWithdrawals += wit;
    cumMinted += minted;
    cumBurned += burned;
    return {
      timestamp,
      deposits: dep,
      withdrawals: wit,
      minted,
      burned,
      cumDeposits,
      cumWithdrawals,
      cumMinted,
      cumBurned,
    };
  });
};

type PricePoint = {
  timestamp: number;
  price: number;
};

const buildPriceTimeline = (priceUpdates: MAVCPriceUpdate[]): PricePoint[] => {
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
    .map(([timestamp, prices]) => ({
      timestamp,
      price: prices.reduce((sum, p) => sum + p, 0) / prices.length, // Average price
    }))
    .sort((a, b) => a.timestamp - b.timestamp);
};

const ChartTooltip = ({ label, payload }: { label?: string | number; payload?: any[] }) => {
  if (!payload?.length) return null;
  return (
    <div className="space-y-1 rounded-2xl border border-zinc-700/50 bg-zinc-800/90 px-4 py-3 text-xs text-zinc-200 shadow-xl">
      <p className="font-semibold text-white">{typeof label === 'number' ? formatShortDate(label) : label}</p>
      {payload.map((item) => (
        <div key={item.name} className="flex justify-between gap-4">
          <span className="uppercase tracking-wide text-zinc-400">{item.name}</span>
          <span className="font-semibold text-white">
            {item.dataKey?.toString().includes('Share') ? formatShare(item.value ?? 0) : formatNumber(item.value ?? 0)}
          </span>
        </div>
      ))}
    </div>
  );
};

interface SubgraphAnalyticsProps {
  subgraphUrl?: string;
}

export const SubgraphAnalytics: React.FC<SubgraphAnalyticsProps> = ({ subgraphUrl }) => {
  const { data, isLoading, isError, error, refetch, isFetching } = useSubgraphData(subgraphUrl);
  const { data: priceHistory } = useMAVCPriceHistory(subgraphUrl);

  const metrics = data?.vaultMetric;
  const deposits = data?.deposits ?? [];
  const withdrawals = data?.withdrawals ?? [];

  const netShares = useMemo(() => {
    if (!metrics) return 0;
    const minted = Number(metrics.mintedShares ?? '0');
    const burned = Number(metrics.burnedShares ?? '0');
    return minted - burned;
  }, [metrics]);

  const timeline = useMemo(() => buildTimeline(deposits, withdrawals), [deposits, withdrawals]);
  const priceTimeline = useMemo(() => buildPriceTimeline(priceHistory ?? []), [priceHistory]);

  // Calculate dynamic y-axis domain for price chart
  const priceDomain = useMemo(() => {
    if (priceTimeline.length === 0) return [0, 20];

    const prices = priceTimeline.map(p => p.price);
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);

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
  }, [priceTimeline]);

  const hasChartData = timeline.length > 0;
  const hasPriceData = priceTimeline.length > 0;

  if (!subgraphUrl) {
    return (
      <div className="mt-8 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
        <p className="font-semibold">Subgraph not configured.</p>
        <p className="mt-2 text-sm text-amber-50/80">
          Set VITE_SUBGRAPH_URL in your environment to enable analytics.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-8 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-2xl font-bold text-white">On-Chain Analytics</h2>
          <p className="text-sm text-zinc-400">
            Live MAVC vault metrics powered by The Graph subgraph.
          </p>
        </div>
        {data && (
          <button
            type="button"
            onClick={() => refetch()}
            className="self-start rounded-full border border-zinc-700/50 bg-zinc-800/50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-zinc-300 transition hover:border-zinc-600/50 hover:text-white disabled:opacity-50"
            disabled={isFetching}
          >
            Refresh
          </button>
        )}
      </header>

      {!metrics && !isLoading && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
          <p className="font-semibold">No subgraph data detected.</p>
          <p className="mt-2 text-sm text-amber-50/80">
            Deploy the subgraph and point VITE_SUBGRAPH_URL to the query endpoint to activate analytics.
          </p>
          {isError && (
            <p className="mt-2 text-xs text-amber-50/60">{error instanceof Error ? error.message : 'Failed to query subgraph.'}</p>
          )}
        </div>
      )}

      {isLoading && (
        <p className="text-sm text-zinc-400">Loading analytics...</p>
      )}

      {metrics && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Deposits</p>
            <p className="mt-3 text-3xl font-bold text-white">{formatCurrency(Number(metrics.totalDeposits ?? '0'))}</p>
          </div>
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Withdrawals</p>
            <p className="mt-3 text-3xl font-bold text-white">{formatCurrency(Number(metrics.totalWithdrawals ?? '0'))}</p>
          </div>
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">MAVC Minted</p>
            <p className="mt-3 text-3xl font-bold text-white">{formatShare(Number(metrics.mintedShares ?? '0'))}</p>
          </div>
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Net MAVC Supply</p>
            <p className="mt-3 text-3xl font-bold text-white">{formatShare(netShares)}</p>
          </div>
        </div>
      )}

      {hasChartData && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 shadow-2xl backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white">USD Flow</h3>
                <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Cumulative deposits vs withdrawals</p>
              </div>
            </div>
            <div className="mt-6 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeline} margin={{ left: -8, right: 8 }}>
                  <defs>
                    <linearGradient id="depositLine" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#6366f1" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#6366f1" stopOpacity={0.1} />
                    </linearGradient>
                    <linearGradient id="withdrawLine" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f472b6" stopOpacity={0.9} />
                      <stop offset="100%" stopColor="#f472b6" stopOpacity={0.1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={formatShortDate}
                    stroke="rgba(255,255,255,0.4)"
                  />
                  <YAxis
                    tickFormatter={(value) => formatNumber(value, { maximumFractionDigits: 0 })}
                    stroke="rgba(255,255,255,0.4)"
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="cumDeposits"
                    name="Deposits (USD)"
                    stroke="url(#depositLine)"
                    strokeWidth={3}
                    dot={false}
                  />
                  <Line
                    type="monotone"
                    dataKey="cumWithdrawals"
                    name="Withdrawals (USD)"
                    stroke="url(#withdrawLine)"
                    strokeWidth={3}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 shadow-2xl backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-xl font-bold text-white">MAVC Mint vs Burn</h3>
                <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Cumulative shares minted and burned</p>
              </div>
            </div>
            <div className="mt-6 h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline} margin={{ left: -8, right: 8 }}>
                  <defs>
                    <linearGradient id="mintedArea" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#34d399" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#34d399" stopOpacity={0.1} />
                    </linearGradient>
                    <linearGradient id="burnedArea" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#f97316" stopOpacity={0.8} />
                      <stop offset="100%" stopColor="#f97316" stopOpacity={0.1} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                  <XAxis
                    dataKey="timestamp"
                    tickFormatter={formatShortDate}
                    stroke="rgba(255,255,255,0.4)"
                  />
                  <YAxis
                    tickFormatter={(value) => formatNumber(value, { maximumFractionDigits: 0 })}
                    stroke="rgba(255,255,255,0.4)"
                  />
                  <Tooltip content={<ChartTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="cumMinted"
                    name="Minted (MAVC)"
                    stroke="#34d399"
                    strokeWidth={2}
                    fill="url(#mintedArea)"
                  />
                  <Area
                    type="monotone"
                    dataKey="cumBurned"
                    name="Burned (MAVC)"
                    stroke="#f97316"
                    strokeWidth={2}
                    fill="url(#burnedArea)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {hasPriceData && (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 shadow-2xl backdrop-blur">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-xl font-bold text-white">MAVC Price Over Time</h3>
              <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">30-minute interval average</p>
            </div>
          </div>
          <div className="mt-6 h-80">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={priceTimeline} margin={{ left: 0, right: 20, bottom: 60, top: 10 }}>
                <defs>
                  <linearGradient id="priceArea" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.8} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.1} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
                <XAxis
                  dataKey="timestamp"
                  tickFormatter={formatDateTime}
                  stroke="rgba(255,255,255,0.4)"
                  angle={-45}
                  textAnchor="end"
                  height={60}
                  tick={{ fontSize: 11 }}
                  minTickGap={50}
                />
                <YAxis
                  domain={priceDomain}
                  tickFormatter={(value) => formatCurrency(value)}
                  stroke="rgba(255,255,255,0.4)"
                />
                <Tooltip
                  content={({ label, payload }) => {
                    if (!payload?.length) return null;
                    return (
                      <div className="space-y-1 rounded-2xl border border-zinc-700/50 bg-zinc-800/90 px-4 py-3 text-xs text-zinc-200 shadow-xl">
                        <p className="font-semibold text-white">
                          {typeof label === 'number' ? formatDateTime(label) : label}
                        </p>
                        <div className="flex justify-between gap-4">
                          <span className="uppercase tracking-wide text-zinc-400">MAVC Price</span>
                          <span className="font-semibold text-white">
                            {formatCurrency(payload[0].value as number)}
                          </span>
                        </div>
                      </div>
                    );
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="price"
                  name="Price (USD)"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  fill="url(#priceArea)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {metrics && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Recent Deposits</p>
            <ul className="mt-4 space-y-3 text-sm text-zinc-300">
              {deposits.length === 0 && <li>No deposits indexed yet.</li>}
              {deposits.slice(0, 6).map((entry) => (
                <li key={entry.id} className="rounded-xl bg-zinc-700/50 px-4 py-3">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>{formatTimestamp(entry.timestamp)}</span>
                    <span>{formatAddress(entry.owner)}</span>
                  </div>
                  <div className="mt-2 flex justify-between text-sm text-white">
                    <span>{formatCurrency(Number(entry.assets ?? '0'))}</span>
                    <span>{formatShare(Number(entry.shares ?? '0'))} MAVC</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Recent Withdrawals</p>
            <ul className="mt-4 space-y-3 text-sm text-zinc-300">
              {withdrawals.length === 0 && <li>No withdrawals indexed yet.</li>}
              {withdrawals.slice(0, 6).map((entry) => (
                <li key={entry.id} className="rounded-xl bg-zinc-700/50 px-4 py-3">
                  <div className="flex justify-between text-xs text-zinc-400">
                    <span>{formatTimestamp(entry.timestamp)}</span>
                    <span>{formatAddress(entry.owner)}</span>
                  </div>
                  <div className="mt-2 flex justify-between text-sm text-white">
                    <span>{formatCurrency(Number(entry.assets ?? '0'))}</span>
                    <span>{formatShare(Number(entry.shares ?? '0'))} MAVC</span>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
};

