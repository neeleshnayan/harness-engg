import { useMemo } from 'react';
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
} from 'recharts';
import { formatAddress } from '@/lib/format';
import { useSubgraphData } from '@/hooks/useSubgraphData';

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

const ChartTooltip = ({ label, payload }: { label?: string | number; payload?: any[] }) => {
  if (!payload?.length) return null;
  return (
    <div className="space-y-1 rounded-2xl border border-white/10 bg-surface px-4 py-3 text-xs text-white/80 shadow-xl">
      <p className="font-semibold text-white">{typeof label === 'number' ? formatShortDate(label) : label}</p>
      {payload.map((item) => (
        <div key={item.name} className="flex justify-between gap-4">
          <span className="uppercase tracking-wide text-white/60">{item.name}</span>
          <span className="font-semibold text-white/90">
            {item.dataKey?.toString().includes('Share') ? formatShare(item.value ?? 0) : formatNumber(item.value ?? 0)}
          </span>
        </div>
      ))}
    </div>
  );
};

export const SubgraphInsights = () => {
  const { data, isLoading, isError, error, refetch, isFetching } = useSubgraphData();

  const metrics = data?.vaultMetric;
  const mavcPrice = data?.mavcPriceCurrent;
  const deposits = data?.deposits ?? [];
  const withdrawals = data?.withdrawals ?? [];

  const netShares = useMemo(() => {
    if (!metrics) return 0;
    const minted = Number(metrics.mintedShares ?? '0');
    const burned = Number(metrics.burnedShares ?? '0');
    return minted - burned;
  }, [metrics]);

  const timeline = useMemo(() => buildTimeline(deposits, withdrawals), [deposits, withdrawals]);

  const hasChartData = timeline.length > 0;

  return (
    <section className="mt-12 space-y-6">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="font-display text-2xl text-white">On-Chain Analytics via The Graph</h2>
          <p className="text-sm text-white/60">
            Live MAVC share metrics powered by your Sepolia subgraph. Update VITE_SUBGRAPH_URL once deployment is complete.
          </p>
        </div>
        {data && (
          <button
            type="button"
            onClick={() => refetch()}
            className="self-start rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-white/70 transition hover:border-white/40 hover:text-white"
            disabled={isFetching}
          >
            {isFetching ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </header>

      {!metrics && !isLoading && (
        <div className="rounded-3xl border border-amber-400/40 bg-amber-500/10 px-6 py-5 text-amber-100">
          <p className="font-semibold">No subgraph data detected.</p>
          <p className="mt-2 text-sm text-amber-50/80">
            Deploy the subgraph in subgraph/ and point VITE_SUBGRAPH_URL to the query endpoint to activate this dashboard.
          </p>
          {isError && (
            <p className="mt-2 text-xs text-amber-50/60">{error instanceof Error ? error.message : 'Failed to query subgraph.'}</p>
          )}
        </div>
      )}

      {isLoading && (
        <p className="text-sm text-white/60">Loading analytics...</p>
      )}

      {mavcPrice && (
        <div className="rounded-3xl border border-emerald-400/30 bg-gradient-to-br from-emerald-500/20 to-cyan-500/10 p-6 backdrop-blur">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.2em] text-white/70">Current MAVC Price</p>
              <p className="mt-2 font-display text-4xl text-white">{formatCurrency(Number(mavcPrice.price ?? '0'))}</p>
              <p className="mt-2 text-xs text-white/60">
                Formula: 1 MAVC = 0.005 × USDC price + 0.005 × WETH price
              </p>
            </div>
            <div className="text-right">
              <p className="text-xs text-white/50">Last Updated</p>
              <p className="mt-1 text-sm text-white/80">{formatTimestamp(mavcPrice.lastUpdate)}</p>
              <p className="mt-2 text-xs text-white/40">{mavcPrice.updateCount} updates</p>
            </div>
          </div>
        </div>
      )}

      {metrics && (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-3xl border border-white/10 bg-white/10 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Total Deposits</p>
            <p className="mt-3 font-display text-3xl text-white">{formatCurrency(Number(metrics.totalDeposits ?? '0'))}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/10 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Total Withdrawals</p>
            <p className="mt-3 font-display text-3xl text-white">{formatCurrency(Number(metrics.totalWithdrawals ?? '0'))}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/10 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">MAVC Minted</p>
            <p className="mt-3 font-display text-3xl text-white">{formatShare(Number(metrics.mintedShares ?? '0'))}</p>
          </div>
          <div className="rounded-3xl border border-white/10 bg-white/10 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Net MAVC Supply</p>
            <p className="mt-3 font-display text-3xl text-white">{formatShare(netShares)}</p>
          </div>
        </div>
      )}

      {hasChartData && (
        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-3xl border border-white/10 bg-surface p-6 shadow-2xl shadow-black/30 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-display text-xl text-white">USD Flow</h3>
                <p className="text-xs uppercase tracking-[0.2em] text-white/50">Cumulative deposits vs withdrawals</p>
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

          <div className="rounded-3xl border border-white/10 bg-surface p-6 shadow-2xl shadow-black/30 backdrop-blur">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-display text-xl text-white">MAVC Mint vs Burn</h3>
                <p className="text-xs uppercase tracking-[0.2em] text-white/50">Cumulative shares minted and burned</p>
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

      {metrics && (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Recent Deposits</p>
            <ul className="mt-4 space-y-3 text-sm text-white/70">
              {deposits.length === 0 && <li>No deposits indexed yet.</li>}
              {deposits.slice(0, 6).map((entry) => (
                <li key={entry.id} className="rounded-2xl bg-white/5 px-4 py-3">
                  <div className="flex justify-between text-xs text-white/50">
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

          <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Recent Withdrawals</p>
            <ul className="mt-4 space-y-3 text-sm text-white/70">
              {withdrawals.length === 0 && <li>No withdrawals indexed yet.</li>}
              {withdrawals.slice(0, 6).map((entry) => (
                <li key={entry.id} className="rounded-2xl bg-white/5 px-4 py-3">
                  <div className="flex justify-between text-xs text-white/50">
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
    </section>
  );
};
