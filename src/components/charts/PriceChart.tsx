
import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface PriceChartProps {
    data: Snapshot[];
    symbol?: string;
}

export const PriceChart: React.FC<PriceChartProps> = ({ data, symbol = "WETH" }) => {
    const chartData = data.map(s => ({
        timestamp: Number(s.timestamp),
        date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
        // Map to wethBalance * wethPrice to get USD value
        value: Number(s.wethBalance ?? '0') * Number(s.wethPrice ?? '0')
    })).sort((a, b) => a.timestamp - b.timestamp);

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Asset Allocation ({symbol} in USD)</h3>
            <p className="text-xs text-zinc-400 mb-6">HISTORICAL {symbol} VALUE</p>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} domain={['auto', 'auto']} tickFormatter={(val) => `$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 })}`} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                            itemStyle={{ color: '#e4e4e7' }}
                            formatter={(value: number) => [`$${value.toFixed(2)}`, 'Value']}
                        />
                        <Line type="monotone" dataKey="value" stroke="#ec4899" strokeWidth={2} dot={false} />
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
