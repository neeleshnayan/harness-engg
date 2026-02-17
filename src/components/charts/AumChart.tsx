import React from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Snapshot } from '@/hooks/useStrategySubgraphData';
import { StrategyChartTooltip } from './StrategyChartTooltip';

interface AumChartProps {
    data: Snapshot[];
}

const formatTooltipCurrency = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4
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
        <div 
            className="group relative rounded-2xl overflow-hidden bg-gradient-to-br from-white/[0.06] to-white/[0.02] backdrop-blur-xl border border-white/10 transition-all duration-300 hover:bg-white/[0.08] hover:border-white/20  p-6 flex flex-col h-full"
            style={{
                boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.1)'
            }}
        >
            <div className="min-h-[7rem] mb-4">
                <h3 className="text-lg font-bold text-white mb-1">Assets Under Management</h3>
                <p className="text-xs text-zinc-400">CALCULATED FROM LIVE BALANCES & PRICES</p>
            </div>
            <div className="h-[280px] w-full shrink-0">
                <ResponsiveContainer width="100%" height={280}>
                    <AreaChart data={chartData}>
                        <defs>
                            <linearGradient id="colorRealAum" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="5%" stopColor="#90E7EE" stopOpacity={0.4} />
                                <stop offset="95%" stopColor="#90E7EE" stopOpacity={0} />
                            </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(255, 255, 255, 0.05)" vertical={false} />
                        <XAxis dataKey="date" stroke="rgba(255, 255, 255, 0.3)" tick={{ fontSize: 12 }} tickLine={false} />
                        <YAxis stroke="rgba(255, 255, 255, 0.3)" tick={{ fontSize: 12 }} tickLine={false} tickFormatter={(val) => `$${val}`} />
                        <Tooltip
                            content={(props) => (
                                <StrategyChartTooltip
                                    active={props.active}
                                    payload={props.payload}
                                    label={props.label}
                                    valueFormatter={formatTooltipCurrency}
                                />
                            )}
                        />
                        <Area type="monotone" dataKey="aum" stroke="#90E7EE" strokeWidth={2.5} fillOpacity={1} fill="url(#colorRealAum)" />
                    </AreaChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};
