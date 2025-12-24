import React, { useMemo, useState } from "react";
import { useYearnWETHSubgraphData, Snapshot } from "@/hooks/useStrategySubgraphData";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    LineChart,
    Line,
    Legend
} from 'recharts';
import { ChevronDown, ChevronUp, Download } from "lucide-react";
import { TokenPriceChart } from '@/components/charts/TokenPriceChart';
import { AssetAllocationChart } from '@/components/charts/AssetAllocationChart';
import { PriceChart } from '@/components/charts/PriceChart';
import { AumChart } from '@/components/charts/AumChart';

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

const formatTokenAmount = (value: number, decimals: number = 4) =>
    new Intl.NumberFormat('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: decimals,
    }).format(value);

const formatTimestamp = (value?: string) => {
    if (!value) return '';
    const date = Number(value) * 1000;
    if (!Number.isFinite(date)) return '';
    return new Date(date).toLocaleString();
};

const formatTxHash = (hash?: string) => {
    if (!hash) return '';
    return `${hash.slice(0, 6)}...${hash.slice(-4)}`;
};

interface SubgraphAnalyticsYearnWETHProps {
    subgraphUrl?: string;
}
export const SubgraphAnalyticsYearnWETH: React.FC<SubgraphAnalyticsYearnWETHProps> = ({ subgraphUrl }) => {
    const { data, isLoading, isError, error, refetch, isFetching } = useYearnWETHSubgraphData(subgraphUrl);

    // Update to use correct field name from hook
    const metrics = data?.yearnWethStrategyMetric;
    const signals = data?.signalExecuteds ?? [];

    const [isExpanded, setIsExpanded] = useState(false);
    const displayedSignals = isExpanded ? signals : signals.slice(0, 5);

    const handleExportCSV = () => {
        if (!signals || signals.length === 0) return;

        const headers = ['Time', 'Type', 'Input', 'Output', 'WETH Price', 'Tx Hash'];
        const rows = signals.map(signal => {
            const date = new Date(Number(signal.timestamp) * 1000).toLocaleString().replace(/,/g, ''); // Remove commas to avoid CSV issues
            const type = signal.signalType === 1 ? 'BUY (USDC -> WETH)' : 'SELL (WETH -> USDC)';

            const inputAmount = Number(signal.amountIn);
            const outputAmount = Number(signal.amountOut);

            const inputLabel = signal.signalType === 1
                ? formatCurrency(inputAmount).replace(/,/g, '') // Remove currency commas
                : (formatTokenAmount(inputAmount) + ' WETH');

            const outputLabel = signal.signalType === 1
                ? (formatTokenAmount(outputAmount) + ' WETH')
                : formatCurrency(outputAmount).replace(/,/g, '');

            const price = signal.signalType === 1
                ? (outputAmount > 0 ? inputAmount / outputAmount : 0)
                : (inputAmount > 0 ? outputAmount / inputAmount : 0);

            const priceLabel = formatCurrency(price).replace(/,/g, '');

            return [
                date,
                type,
                inputLabel,
                outputLabel,
                priceLabel,
                signal.txHash
            ].join(',');
        });

        const csvContent = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `yearn-weth-signals-${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Process data for charts using snapshots
    const chartData = useMemo(() => {
        const snapshots = data?.snapshots ?? [];

        return snapshots.map(s => ({
            timestamp: Number(s.timestamp),
            date: new Date(Number(s.timestamp) * 1000).toLocaleDateString(),
            aum: Number(s.totalDeposits) - Number(s.totalWithdrawals),
            totalDeposits: Number(s.totalDeposits),
            totalWithdrawals: Number(s.totalWithdrawals),
            mintedShares: Number(s.mintedShares),
            burnedShares: Number(s.burnedShares),
            netShares: Number(s.mintedShares) - Number(s.burnedShares)
        })).sort((a, b) => a.timestamp - b.timestamp);
    }, [data?.snapshots]);

    if (!subgraphUrl) {
        return (
            <div className="mt-8 rounded-2xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
                <p className="font-semibold">Subgraph not configured.</p>
                <p className="mt-2 text-sm text-amber-50/80">
                    Configure the SUBGRAPH_URL field in Firestore (quant_strategies/YEARN_WETH) to enable analytics.
                </p>
            </div>
        );
    }

    return (
        <div className="space-y-6">
            {/* Recent Signals Section - Moved to top */}
            {
                signals.length > 0 && (
                    <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                        <div className="flex items-center justify-between mb-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Recent Signals</p>
                            {signals.length > 5 && (
                                <button
                                    onClick={() => setIsExpanded(!isExpanded)}
                                    className="flex items-center text-xs text-zinc-400 hover:text-white transition-colors mr-4"
                                >
                                    {isExpanded ? (
                                        <>
                                            Show Less <ChevronUp className="ml-1 h-3 w-3" />
                                        </>
                                    ) : (
                                        <>
                                            Show All <ChevronDown className="ml-1 h-3 w-3" />
                                        </>
                                    )}
                                </button>
                            )}
                            <button
                                onClick={handleExportCSV}
                                className="flex items-center text-xs text-zinc-400 hover:text-white transition-colors"
                            >
                                Export CSV <Download className="ml-1 h-3 w-3" />
                            </button>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-left text-sm text-zinc-400">
                                <thead className="text-xs uppercase text-zinc-500 border-b border-zinc-700/50">
                                    <tr>
                                        <th className="pb-3 font-medium">Time</th>
                                        <th className="pb-3 font-medium">Type</th>
                                        <th className="pb-3 font-medium">Input</th>
                                        <th className="pb-3 font-medium">Output</th>
                                        <th className="pb-3 font-medium">WETH Price</th>
                                        <th className="pb-3 font-medium">Tx Hash</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-700/30">
                                    {displayedSignals.map((signal) => {
                                        // Calculate Execution Price (USDC / WETH)
                                        const input = Number(signal.amountIn);
                                        const output = Number(signal.amountOut);
                                        // If Buy (1): Input=USDC, Output=WETH => Price = Input/Output
                                        // If Sell (2): Input=WETH, Output=USDC => Price = Output/Input
                                        const price = signal.signalType === 1
                                            ? (output > 0 ? input / output : 0)
                                            : (input > 0 ? output / input : 0);

                                        return (
                                            <tr key={signal.id} className="group hover:bg-zinc-700/20 transition-colors">
                                                <td className="py-3">{formatTimestamp(signal.timestamp)}</td>
                                                <td className="py-3">
                                                    <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${signal.signalType === 1
                                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                                        : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                                        }`}>
                                                        {signal.signalType === 1 ? 'BUY (USDC → WETH)' : 'SELL (WETH → USDC)'}
                                                    </span>
                                                </td>
                                                <td className="py-3 text-white font-medium">
                                                    {signal.signalType === 1
                                                        ? formatCurrency(Number(signal.amountIn))
                                                        : formatTokenAmount(Number(signal.amountIn)) + ' WETH'}
                                                </td>
                                                <td className="py-3 text-white font-medium">
                                                    {signal.signalType === 1
                                                        ? formatTokenAmount(Number(signal.amountOut)) + ' WETH'
                                                        : formatCurrency(Number(signal.amountOut))}
                                                </td>
                                                <td className="py-3 text-white font-medium">
                                                    {formatCurrency(price)}
                                                </td>
                                                <td className="py-3 font-mono text-xs">
                                                    <a
                                                        href={`https://sepolia.etherscan.io/tx/${signal.txHash}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="hover:text-blue-400 transition-colors"
                                                    >
                                                        {formatTxHash(signal.txHash)}
                                                    </a>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )
            }

            <header className="flex items-center justify-between">
                <h2 className="text-2xl font-bold text-white">Yearn WETH Strategy Analytics</h2>
                {data && (
                    <button
                        type="button"
                        onClick={() => refetch()}
                        className="self-start rounded-full border border-zinc-700/50 bg-zinc-800/50 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-zinc-300 transition hover:border-zinc-600/50 hover:text-white disabled:opacity-50"
                        disabled={isFetching}
                    >
                        Refresh
                    </button>
                )}
            </header>

            {isError && (
                <div className="rounded-2xl border border-red-500/30 bg-red-500/10 px-6 py-5 text-red-100">
                    <p className="font-semibold">Error querying subgraph</p>
                    <p className="mt-2 text-sm text-red-50/80">
                        {error instanceof Error ? error.message : 'Failed to query subgraph.'}
                    </p>
                    <p className="mt-2 text-xs text-red-50/60">
                        Endpoint: {subgraphUrl}
                    </p>
                </div>
            )}

            {
                !metrics && !isLoading && !isError && (
                    <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
                        <p className="font-semibold">No subgraph data detected.</p>
                        <p className="mt-2 text-sm text-amber-50/80">
                            The query succeeded but no metric data was found. This may indicate:
                        </p>
                        <ul className="mt-2 text-xs text-amber-50/60 list-disc list-inside space-y-1">
                            <li>The subgraph hasn't indexed any events yet</li>
                            <li>The metric entity hasn't been created (id: "yearn-weth-strategy")</li>
                            <li>No signals have been executed yet</li>
                        </ul>
                        <p className="mt-3 text-xs text-amber-50/60 break-all">
                            Endpoint: {subgraphUrl}
                        </p>
                    </div>
                )
            }

            {
                isLoading && (
                    <p className="text-sm text-zinc-400">Loading analytics...</p>
                )
            }

            {
                metrics && (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total AUM</p>
                            <p className="mt-3 text-3xl font-bold text-white">
                                {formatCurrency(
                                    (Number(metrics.totalDeposits ?? '0') - Number(metrics.totalWithdrawals ?? '0'))
                                )}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Net Share Supply</p>
                            <p className="mt-3 text-3xl font-bold text-white">
                                {formatTokenAmount(
                                    (Number(metrics.mintedShares ?? '0') - Number(metrics.burnedShares ?? '0'))
                                )}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Deposits</p>
                            <p className="mt-3 text-3xl font-bold text-emerald-400">{formatCurrency(Number(metrics.totalDeposits ?? '0'))}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Withdrawals</p>
                            <p className="mt-3 text-3xl font-bold text-rose-400">{formatCurrency(Number(metrics.totalWithdrawals ?? '0'))}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Buy Signals</p>
                            <p className="mt-3 text-3xl font-bold text-emerald-400">{metrics.totalBuySignals}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Sell Signals</p>
                            <p className="mt-3 text-3xl font-bold text-rose-400">{metrics.totalSellSignals}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total USDC Swapped</p>
                            <p className="mt-3 text-3xl font-bold text-white">{formatCurrency(Number(metrics.totalUsdcSwapped ?? '0'))}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total WETH Swapped</p>
                            <p className="mt-3 text-3xl font-bold text-white">{formatTokenAmount(Number(metrics.totalWethSwapped ?? '0'))}</p>
                        </div>
                    </div>
                )
            }

            {/* Charts Section */}
            {
                chartData.length > 0 && (
                    <div className="grid gap-6 lg:grid-cols-2">
                        {/* AUM Chart */}
                        {/* AUM Chart */}
                        <div className="lg:col-span-1">
                            <AumChart data={data?.snapshots ?? []} />
                        </div>

                        {/* Token Price Chart */}
                        <div className="lg:col-span-1">
                            <TokenPriceChart data={data?.snapshots ?? []} />
                        </div>

                        {/* Asset Allocation Chart */}
                        <div className="lg:col-span-1">
                            <AssetAllocationChart data={data?.snapshots ?? []} />
                        </div>

                        {/* Price Chart */}
                        <div className="lg:col-span-1">
                            <PriceChart data={data?.snapshots ?? []} />
                        </div>



                        {/* USD Flow Chart */}
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <h3 className="text-lg font-bold text-white mb-1">USD Flow</h3>
                            <p className="text-xs text-zinc-400 mb-6">CUMULATIVE DEPOSITS VS WITHDRAWALS</p>
                            <div className="h-[250px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={chartData}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                                        />
                                        <Legend />
                                        <Line type="monotone" dataKey="totalDeposits" name="Deposits" stroke="#a78bfa" strokeWidth={2} dot={false} />
                                        <Line type="monotone" dataKey="totalWithdrawals" name="Withdrawals" stroke="#f43f5e" strokeWidth={2} dot={false} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        {/* Share Mint vs Burn Chart */}
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <h3 className="text-lg font-bold text-white mb-1">Share Mint vs Burn</h3>
                            <p className="text-xs text-zinc-400 mb-6">CUMULATIVE SHARES MINTED AND BURNED</p>
                            <div className="h-[250px] w-full">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={chartData}>
                                        <defs>
                                            <linearGradient id="colorMint" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                                            </linearGradient>
                                            <linearGradient id="colorBurn" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" vertical={false} />
                                        <XAxis dataKey="date" stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                                        />
                                        <Area type="monotone" dataKey="mintedShares" name="Minted" stroke="#3b82f6" fill="url(#colorMint)" />
                                        <Area type="monotone" dataKey="burnedShares" name="Burned" stroke="#f97316" fill="url(#colorBurn)" />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                )
            }
        </div >
    );
};
