
import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';

interface AumChartProps {
    data: Snapshot[];
}

const formatCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        compactDisplay: 'short',
        maximumFractionDigits: 0
    }).format(value);

export const AumChart: React.FC<AumChartProps> = ({ data }) => {
    const chartData = data.map(s => ({
        timestamp: Number(s.timestamp),
        date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
        // Use the explicit AUM field if available, fallback to totalDeposits - totalWithdrawals for robustness/comparison
        // But the user specifically asked for "AUM: Calculated as USDC + (WETH * Price)" which is new 'aum' field.
        aum: Number(s.aum ?? '0')
    })).sort((a, b) => a.timestamp - b.timestamp);

    return (
        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
            <h3 className="text-lg font-bold text-white mb-1">Assets Under Management</h3>
            <p className="text-xs text-zinc-400 mb-6">CALCULATED FROM LIVE BALANCES & PRICES</p>
            <div className="h-[300px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorRealAum" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} tickFormatter={(val) => `$${val}`} />
                        <Tooltip
                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                            itemStyle={{ color: '#e4e4e7' }}
                            formatter={(value: number) => [formatCurrency(value), 'AUM']}
                        />
                        <Area type="monotone" dataKey="aum" stroke="#10b981" strokeWidth={2} fillOpacity={1} fill="url(#colorRealAum)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
