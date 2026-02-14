
import React, { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

type TimeRange = '15m' | '1h' | '1d' | '1M' | '1y' | 'all';

const TIME_RANGES: { key: TimeRange; label: string; seconds: number }[] = [
    { key: '15m', label: '15m', seconds: 15 * 60 },
    { key: '1h', label: '1H', seconds: 60 * 60 },
    { key: '1d', label: '1D', seconds: 24 * 60 * 60 },
    { key: '1M', label: '1M', seconds: 30 * 24 * 60 * 60 },
    { key: '1y', label: '1Y', seconds: 365 * 24 * 60 * 60 },
    { key: 'all', label: 'ALL', seconds: 0 },
];

interface TokenPriceChartProps {
    data: Snapshot[];
    livePrice?: number | null;
    /** Daily share prices computed from pool closing rates + vault state */
    dailyPrices?: { timestamp: number; date: string; price: number }[];
}

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4
    }).format(value);

/** Format X-axis tick based on selected time range */
const formatXTick = (range: TimeRange, timestamp: number | string) => {
    if (timestamp === 'Now') return 'Now';
    const date = new Date(Number(timestamp) * 1000);
    if (range === '15m' || range === '1h') {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    if (range === '1d') {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }
    if (range === '1M') {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    if (range === '1y') {
        return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    }
    return date.toLocaleDateString();
};

export const TokenPriceChart: React.FC<TokenPriceChartProps> = ({ data, livePrice, dailyPrices }) => {
    const [selectedRange, setSelectedRange] = useState<TimeRange>('all');

    const allChartData = React.useMemo(() => {
        // 1. Event-level prices from subgraph data
        const eventPoints = data.map(s => {
            const sharePrice = Number((s as any).wethPrice ?? 0);
            let price: number;
            if (sharePrice > 0) {
                price = sharePrice;
            } else {
                const aum = Number(s.aum ?? '0');
                const minted = Number(s.mintedShares ?? '0');
                const burned = Number(s.burnedShares ?? '0');
                const totalTokens = minted - burned;
                price = totalTokens > 0 ? aum / totalTokens : 0;
            }
            return {
                timestamp: Number(s.timestamp),
                date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
                price,
            };
        }).filter(p => p.price > 0);

        // 2. Collect dates that already have event data
        const eventDates = new Set(eventPoints.map(p => p.date));

        // 3. Add daily interpolated points only for dates without event data
        const dailyPoints = (dailyPrices || [])
            .filter(p => !eventDates.has(p.date) && p.price > 0)
            .map(p => ({
                timestamp: p.timestamp,
                date: p.date,
                price: p.price,
            }));

        // 4. Merge and sort chronologically
        const merged = [...eventPoints, ...dailyPoints]
            .sort((a, b) => a.timestamp - b.timestamp);

        // 5. Append "Now" data point
        const now = Math.floor(Date.now() / 1000);
        const lastPrice = merged.length > 0 ? merged[merged.length - 1].price : 1;
        const currentPrice = (livePrice != null && livePrice > 0) ? livePrice : lastPrice;
        merged.push({ timestamp: now, date: 'Now', price: currentPrice });

        return merged;
    }, [data, livePrice, dailyPrices]);

    // Filter data based on selected time range
    const chartData = React.useMemo(() => {
        if (selectedRange === 'all') return allChartData;

        const rangeConfig = TIME_RANGES.find(r => r.key === selectedRange)!;
        const now = Math.floor(Date.now() / 1000);
        const cutoff = now - rangeConfig.seconds;

        const filtered = allChartData.filter(p => p.timestamp >= cutoff);

        // If no data points in range, show the last known point before cutoff + "Now"
        if (filtered.length <= 1) {
            const beforeCutoff = allChartData.filter(p => p.timestamp < cutoff);
            if (beforeCutoff.length > 0) {
                const lastBefore = beforeCutoff[beforeCutoff.length - 1];
                return [{ ...lastBefore, date: formatXTick(selectedRange, lastBefore.timestamp) }, ...filtered];
            }
        }

        return filtered;
    }, [allChartData, selectedRange]);

    // Compute price change for the selected range
    const priceChange = React.useMemo(() => {
        if (chartData.length < 2) return null;
        const first = chartData[0].price;
        const last = chartData[chartData.length - 1].price;
        if (first <= 0) return null;
        const change = last - first;
        const pct = (change / first) * 100;
        return { change, pct };
    }, [chartData]);

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-1">
                <div>
                    <h3 className="text-lg font-bold text-white">Token Price</h3>
                    <p className="text-xs text-zinc-400">ON-CHAIN SHARE PRICE (TOTAL ASSETS / TOTAL SUPPLY)</p>
                </div>
                {priceChange && (
                    <p className={`text-sm font-medium ${priceChange.change >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {priceChange.change >= 0 ? '+' : ''}{formatCurrency(priceChange.change)} ({priceChange.pct >= 0 ? '+' : ''}{priceChange.pct.toFixed(2)}%)
                    </p>
                )}
            </div>

            {/* Time range selector */}
            <div className="flex items-center gap-1 mb-6 mt-3">
                {TIME_RANGES.map(({ key, label }) => (
                    <button
                        key={key}
                        onClick={() => setSelectedRange(key)}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all duration-150 ${
                            selectedRange === key
                                ? 'bg-violet-500/20 text-violet-300 border border-violet-500/40'
                                : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700/40 border border-transparent'
                        }`}
                    >
                        {label}
                    </button>
                ))}
            </div>

            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorPrice" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis
                            dataKey="timestamp"
                            stroke="#71717a"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            tickFormatter={(val) => formatXTick(selectedRange, val)}
                        />
                        <YAxis
                            stroke="#71717a"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            domain={['auto', 'auto']}
                            tickFormatter={(val) => {
                                const num = Number(val);
                                if (num >= 1000000) return `$${(num / 1000000).toFixed(4)}M`;
                                if (num >= 1000) return `$${(num / 1000).toFixed(4)}K`;
                                return `$${num.toFixed(4)}`;
                            }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                            itemStyle={{ color: '#e4e4e7' }}
                            labelFormatter={(val) => {
                                if (val === 'Now') return 'Now';
                                const ts = Number(val);
                                if (!Number.isFinite(ts)) return String(val);
                                return new Date(ts * 1000).toLocaleString();
                            }}
                            formatter={(value: number) => [formatCurrency(value), 'Price']}
                        />
                        <Area type="monotone" dataKey="price" stroke="#8b5cf6" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
