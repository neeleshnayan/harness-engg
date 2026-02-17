import React, { useMemo } from 'react';
import { StrategyChartTooltip } from './StrategyChartTooltip';
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
    asset: '#60A5FA', // Softer blue for USDC
    target: '#90E7EE', // Cyan for ETH/target assets
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
            <div 
                className="group relative rounded-2xl overflow-hidden bg-gradient-to-br from-white/[0.06] to-white/[0.02] backdrop-blur-xl border border-white/10 transition-all duration-300 p-6 flex flex-col h-full"
                style={{
                    boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.1)'
                }}
            >
                <div className="min-h-[7rem] mb-4">
                    <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
                    <p className="text-xs text-zinc-400">NO DATA AVAILABLE</p>
                </div>
                <div className="h-[280px] w-full flex-1 min-h-0 flex items-center justify-center text-zinc-500 text-sm">No data to display</div>
            </div>
        );
    }

    const latest = timeSeriesData[timeSeriesData.length - 1];

    return (
        <div 
            className="group relative rounded-2xl overflow-hidden bg-gradient-to-br from-white/[0.06] to-white/[0.02] backdrop-blur-xl border border-white/10 transition-all duration-300 hover:bg-white/[0.08] hover:border-white/20  p-6 flex flex-col h-full"
            style={{
                boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.1)'
            }}
        >
            <div className="min-h-[7rem] mb-4">
                <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
                <p className="text-xs text-zinc-400 mb-2">COMPOSITION OF STRATEGY ASSETS OVER TIME</p>
                <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
                    <div>
                        <span className="text-2xl font-bold text-white">{formatCurrency(latest.total)}</span>
                        <span className="text-xs text-zinc-400 ml-2">Current Total Value</span>
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
            </div>
            <div className="h-[280px] w-full shrink-0">
                <ResponsiveContainer width="100%" height={280}>
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
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" vertical={false} />
                        <XAxis dataKey="date" stroke="rgba(255, 255, 255, 0.3)" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis
                            stroke="rgba(255, 255, 255, 0.3)"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            tickFormatter={(val) => `$${val}`}
                        />
                        <Tooltip
                            content={(props) => {
                                if (!props.active || !props.payload?.length) return null;
                                const rows = props.payload
                                    .filter((p) => p.value !== undefined)
                                    .map((p) => ({
                                        label: String(p.name ?? p.dataKey ?? ''),
                                        value: formatCurrency(Number(p.value)),
                                        color: p.color,
                                    }));
                                return (
                                    <StrategyChartTooltip
                                        active={props.active}
                                        payload={props.payload}
                                        label={props.label}
                                        rows={rows}
                                    />
                                );
                            }}
                        />
                        <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                        <Area
                            type="monotone"
                            dataKey={assetSymbol}
                            stackId="1"
                            stroke={COLORS.asset}
                            fill="url(#colorAssetAlloc)"
                            strokeWidth={2.5}
                        />
                        <Area
                            type="monotone"
                            dataKey={targetSymbol}
                            stackId="1"
                            stroke={COLORS.target}
                            fill="url(#colorTargetAlloc)"
                            strokeWidth={2.5}
                        />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
