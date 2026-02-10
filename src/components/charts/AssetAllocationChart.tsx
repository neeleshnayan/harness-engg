
import React from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface AssetAllocationChartProps {
    data: Snapshot[];
    assetSymbol?: string;
    targetSymbol?: string;
}

const COLORS = {
    USDC: '#2563eb',
    WETH: '#a855f7',
    default: ['#2563eb', '#a855f7', '#22c55e', '#f59e0b']
};

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        compactDisplay: 'short',
        maximumFractionDigits: 2
    }).format(value);

export const AssetAllocationChart: React.FC<AssetAllocationChartProps> = ({
    data,
    assetSymbol = "USDC",
    targetSymbol = "WETH"
}) => {
    // Get the latest snapshot for current allocation
    const latestSnapshot = data.length > 0 ? data[data.length - 1] : null;

    if (!latestSnapshot) {
        return (
            <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
                <p className="text-xs text-zinc-400 mb-6">NO DATA AVAILABLE</p>
            </div>
        );
    }

    // Calculate current allocation values
    const assetBal = Number((latestSnapshot as any).usdcBalance ?? (latestSnapshot as any).assetBalance ?? 0);
    const targetBal = Number((latestSnapshot as any).wethBalance ?? (latestSnapshot as any).targetBalance ?? 0);
    const targetPrice = Number((latestSnapshot as any).wethPrice ?? (latestSnapshot as any).targetPrice ?? 0);

    const assetValue = isFinite(assetBal) && !isNaN(assetBal) ? assetBal : 0;
    const targetValue = isFinite(targetBal) && isFinite(targetPrice) && !isNaN(targetBal) && !isNaN(targetPrice)
        ? targetBal * targetPrice
        : 0;

    const total = assetValue + targetValue;

    // Prepare pie chart data
    const pieData = [
        {
            name: assetSymbol,
            value: assetValue,
            percentage: total > 0 ? (assetValue / total) * 100 : 0
        },
        {
            name: targetSymbol,
            value: targetValue,
            percentage: total > 0 ? (targetValue / total) * 100 : 0
        }
    ].filter(item => item.value > 0); // Only show non-zero allocations

    const getColor = (name: string, index: number) => {
        if (name in COLORS) return (COLORS as any)[name];
        return COLORS.default[index % COLORS.default.length];
    };

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Asset Allocation</h3>
            <p className="text-xs text-zinc-400 mb-4">CURRENT COMPOSITION OF STRATEGY ASSETS</p>

            {/* Total Value Display */}
            <div className="mb-6">
                <div className="text-2xl font-bold text-white">
                    {formatCurrency(total)}
                </div>
                <div className="text-xs text-zinc-400 mt-1">Total Value</div>
            </div>

            <div className="h-[280px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={pieData}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percentage }) => `${name}: ${percentage.toFixed(1)}%`}
                            outerRadius={80}
                            fill="#8884d8"
                            dataKey="value"
                        >
                            {pieData.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={getColor(entry.name, index)} />
                            ))}
                        </Pie>
                        <Tooltip
                            contentStyle={{
                                backgroundColor: '#18181b',
                                borderColor: '#3f3f46',
                                borderRadius: '0.5rem'
                            }}
                            formatter={(value: number, name: string, props: any) => {
                                const percent = props.payload.percentage.toFixed(2);
                                return [`${formatCurrency(value)} (${percent}%)`, name];
                            }}
                        />
                        <Legend
                            verticalAlign="bottom"
                            height={36}
                            formatter={(value, entry: any) => {
                                const item = pieData.find(d => d.name === value);
                                return `${value}: ${formatCurrency(item?.value || 0)}`;
                            }}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
