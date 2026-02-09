
import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface TokenPriceChartProps {
    data: Snapshot[];
}

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4
    }).format(value);

export const TokenPriceChart: React.FC<TokenPriceChartProps> = ({ data }) => {
    const chartData = data.map(s => {
        // Calculate Token Price = AUM / (MintedShares - BurnedShares)
        const aum = Number(s.aum ?? '0');
        const minted = Number(s.mintedShares ?? '0');
        const burned = Number(s.burnedShares ?? '0');
        const totalTokens = minted - burned;

        // Avoid division by zero
        const tokenPrice = totalTokens > 0 ? aum / totalTokens : 0;

        return {
            timestamp: Number(s.timestamp),
            date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
            price: tokenPrice
        };
    }).sort((a, b) => a.timestamp - b.timestamp);

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Token Price</h3>
            <p className="text-xs text-zinc-400 mb-6">ESTIMATED PRICE BASED ON AUM / SUPPLY</p>
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
                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis
                            stroke="#71717a"
                            tick={{ fontSize: 12 }}
                            tickLine={false}
                            domain={['auto', 'auto']}
                            tickFormatter={(val) => {
                                const num = Number(val);
                                if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`;
                                if (num >= 1000) return `$${(num / 1000).toFixed(2)}K`;
                                if (num >= 1) return `$${num.toFixed(2)}`;
                                return `$${num.toFixed(4)}`;
                            }}
                        />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                            itemStyle={{ color: '#e4e4e7' }}
                            formatter={(value: number) => [formatCurrency(value), 'Price']}
                        />
                        <Area type="monotone" dataKey="price" stroke="#8b5cf6" strokeWidth={2} fillOpacity={1} fill="url(#colorPrice)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
