
import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface AssetAllocationChartProps {
    data: Snapshot[];
    assetSymbol?: string;
    targetSymbol?: string;
}

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        compactDisplay: 'short',
        maximumFractionDigits: 0
    }).format(value);

export const AssetAllocationChart: React.FC<AssetAllocationChartProps> = ({
    data,
    assetSymbol = "USDC",
    targetSymbol = "WETH"
}) => {
    const chartData = data.map(s => {
        // Both balances are already in their respective decimals? 
        // Wait, the subgraph stores BigDecimal. But the hook types are strings. 
        // Need to verify if 'usdcBalance' and 'wethBalance' are raw amounts (like 1000.50) or formatted.
        // In schema.graphql they are BigDecimal, so they are likely float-like strings "1000.5".
        // USDC is usually 6 decimals, WETH 18.
        // AUM calculation was: USDC + (WETH * Price).
        // So to stack them in USD terms:
        // USDC Value = usdcBalance
        // WETH Value = wethBalance * wethPrice

        const usdcBal = Number(s.usdcBalance ?? '0');
        const wethBal = Number(s.wethBalance ?? '0');
        const wethPrice = Number(s.wethPrice ?? '0');

        const usdcValue = usdcBal;
        const wethValue = wethBal * wethPrice;

        return {
            timestamp: Number(s.timestamp),
            date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
            [assetSymbol]: usdcValue,
            [targetSymbol]: wethValue
        };
    }).sort((a, b) => a.timestamp - b.timestamp);

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Asset Allocation (USD)</h3>
            <p className="text-xs text-zinc-400 mb-6">COMPOSITION OF STRATEGY ASSETS</p>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorUsdc" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#2563eb" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#2563eb" stopOpacity={0} />
                            </linearGradient>

                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} tickFormatter={(val) => `$${val}`} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                            itemStyle={{ color: '#e4e4e7' }}
                            formatter={(value: number) => [formatCurrency(value), '']}
                        />
                        <Legend />
                        <Area type="monotone" dataKey={assetSymbol} stackId="1" stroke="#2563eb" fill="url(#colorUsdc)" />
                        <Area type="monotone" dataKey={targetSymbol} stackId="1" stroke="#a855f7" fill="#a855f7" fillOpacity={0.3} />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
