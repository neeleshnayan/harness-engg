
import React, { useMemo } from 'react';
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
} from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface AssetAllocationChartProps {
    data: Snapshot[];
    assetSymbol?: string;
    targetSymbol?: string;
}

const COLORS = {
    asset: '#2563eb',
    target: '#a855f7',
};

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        compactDisplay: 'short',
        maximumFractionDigits: 2,
    }).format(value);

export const AssetAllocationChart: React.FC<AssetAllocationChartProps> = ({
    data,
    assetSymbol = 'USDC',
    targetSymbol = 'WETH',
}) => {
    const timeSeriesData = useMemo(() => {
        if (!data || data.length === 0) return [];

        return data.map((snapshot: any) => {
            const aum = Number(snapshot.aum ?? 0);
            const cash = Number(snapshot.usdcBalance ?? snapshot.assetBalance ?? 0);

            // Asset (USDC) value = cash on hand
            const assetValue = isFinite(cash) && !isNaN(cash) ? Math.max(0, cash) : 0;
            // Target value = total AUM minus cash (reflects current market price, not cost basis)
            const targetValue = isFinite(aum) && aum > assetValue ? aum - assetValue : 0;

            return {
                date: snapshot.date ?? new Date(Number(snapshot.timestamp) * 1000).toLocaleDateString(),
                [assetSymbol]: assetValue,
                [targetSymbol]: targetValue,
                total: assetValue + targetValue,
            };
        });
    }, [data, assetSymbol, targetSymbol]);

    if (timeSeriesData.length === 0) {
        return (
            <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
                <p className="text-xs text-zinc-400 mb-6">NO DATA AVAILABLE</p>
            </div>
        );
    }

    const latest = timeSeriesData[timeSeriesData.length - 1];

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
            <p className="text-xs text-zinc-400 mb-4">COMPOSITION OF STRATEGY ASSETS OVER TIME</p>

            {/* Current allocation */}
            <div className="mb-6 flex items-baseline gap-4">
                <div>
                    <div className="text-2xl font-bold text-white">
                        {formatCurrency(latest.total)}
                    </div>
                    <div className="text-xs text-zinc-400 mt-1">Current Total Value</div>
                </div>
                <div className="flex gap-4 text-xs text-zinc-400">
                    <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS.asset }} />
                        {assetSymbol}: {formatCurrency(latest[assetSymbol] as number)}
                    </span>
                    <span className="flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: COLORS.target }} />
                        {targetSymbol}: {formatCurrency(latest[targetSymbol] as number)}
                    </span>
                </div>
            </div>

            <div className="h-[250px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={timeSeriesData} stackOffset="none">
                        <defs>
                            <linearGradient id="colorAssetAlloc" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={COLORS.asset} stopOpacity={0.6} />
                                <stop offset="95%" stopColor={COLORS.asset} stopOpacity={0.1} />
                            </linearGradient>
                            <linearGradient id="colorTargetAlloc" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor={COLORS.target} stopOpacity={0.6} />
                                <stop offset="95%" stopColor={COLORS.target} stopOpacity={0.1} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis
                            stroke="#71717a"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            tickFormatter={(val) => `$${val}`}
                        />
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#18181b',
                                borderColor: '#3f3f46',
                                borderRadius: '0.5rem',
                            }}
                            formatter={(value: number, name: string) => [formatCurrency(value), name]}
                        />
                        <Legend />
                        <Area
                            type="monotone"
                            dataKey={assetSymbol}
                            stackId="1"
                            stroke={COLORS.asset}
                            fill="url(#colorAssetAlloc)"
                            strokeWidth={2}
                        />
                        <Area
                            type="monotone"
                            dataKey={targetSymbol}
                            stackId="1"
                            stroke={COLORS.target}
                            fill="url(#colorTargetAlloc)"
                            strokeWidth={2}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
