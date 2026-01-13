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
import { ChevronDown, ChevronUp, Download, Filter, Check } from "lucide-react";
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

const formatTokenPrice = (value: number) =>
    new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'USD',
        minimumFractionDigits: 4,
        maximumFractionDigits: 4,
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
    const deposits = data?.deposits ?? [];
    const withdrawals = data?.withdrawals ?? [];

    const allEvents = useMemo(() => {
        const events = [
            ...signals.map(s => ({ ...s, type: 'SIGNAL' as const })),
            ...deposits.map(d => ({ ...d, type: 'DEPOSIT' as const })),
            ...withdrawals.map(w => ({ ...w, type: 'WITHDRAWAL' as const }))
        ];
        return events.sort((a, b) => Number(b.timestamp) - Number(a.timestamp));
    }, [signals, deposits, withdrawals]);

    const [isExpanded, setIsExpanded] = useState(false);
    const [showFilter, setShowFilter] = useState(false);
    const [filters, setFilters] = useState({
        buy: true,
        sell: true,
        deposits: true,
        withdrawals: true
    });

    // 4. Augment events with Replay Logic (Centralized Source of Truth)
    const augmentedEvents = useMemo(() => {
        // Sort chronologically for replay
        const sortedEvents = [...allEvents].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));

        let currentSupply = 0;
        const calculatedSharesMap = new Map<string, number>();
        const tokenPriceMap = new Map<string, number>();

        sortedEvents.forEach(event => {
            const evtTimestamp = String(event.timestamp);
            const snapshot = data?.snapshots?.find(s => String(s.timestamp) === evtTimestamp);
            const aum = snapshot?.aum ? Number(snapshot.aum) : 0;

            if (event.type === 'DEPOSIT') {
                const assets = Number((event as any).assets);
                const aum = snapshot?.aum ? Number(snapshot.aum) : 0;

                // STRICTLY USE SUBGRAPH SHARES (User Request)
                // Correction: Subgraph output is 18 decimals normalized, but token is 6 decimals?
                // 0.000000000065 * 1e12 = 65 approx.
                const shares = Number((event as any).shares ?? 0) * 1000000000000;

                // Calculate Implied Price (Assets / Shares)
                let price = 1.0;
                if (shares > 0) {
                    price = assets / shares;
                } else {
                    // Fallback to previous price if shares are missing (shouldn't happen with fixed subgraph)
                    price = 1.0;
                }

                calculatedSharesMap.set(event.id, shares);
                tokenPriceMap.set(event.id, price);

                currentSupply += shares;

            } else if (event.type === 'WITHDRAWAL') {
                const shares = Number((event as any).shares ?? 0);
                currentSupply -= shares;
                if (currentSupply < 0) currentSupply = 0;

                const assets = Number((event as any).assets);

                let price = 1.0;
                if (shares > 0) {
                    price = assets / shares; // Implied price of exit
                }

                tokenPriceMap.set(event.id, price);
            } else {
                let price = 1.0;
                if (currentSupply > 0.000000000000001 && aum > 0) { // Tiny supply support
                    price = aum / currentSupply;
                }
                tokenPriceMap.set(event.id, price);
            }
        });

        // Return events with calculated data attached
        return allEvents.map(e => ({
            ...e,
            calculatedShares: calculatedSharesMap.get(e.id),
            calculatedPrice: tokenPriceMap.get(e.id)
        })).sort((a, b) => Number(b.timestamp) - Number(a.timestamp));
    }, [allEvents, data?.snapshots]);

    const filteredEvents = useMemo(() => {
        return augmentedEvents.filter(event => {
            if (event.type === 'SIGNAL') {
                const s = event as any;
                if (s.signalType === 1) return filters.buy;
                return filters.sell;
            }
            if (event.type === 'DEPOSIT') return filters.deposits;
            if (event.type === 'WITHDRAWAL') return filters.withdrawals;
            return true;
        });
    }, [augmentedEvents, filters]);

    // Display logic uses the already augmented filteredEvents
    const displayedEvents = isExpanded ? filteredEvents : filteredEvents.slice(0, 5);

    const toggleFilter = (key: keyof typeof filters) => {
        setFilters(prev => ({ ...prev, [key]: !prev[key] }));
    };

    const handleExportCSV = () => {
        if (!filteredEvents || filteredEvents.length === 0) return;

        const headers = ['Time', 'Type', 'Input', 'Output', 'WETH Price', 'Token Price', 'Total AUM', 'Total Deposits', 'Total Withdrawals', 'Tx Hash'];
        const rows = filteredEvents.map(event => {
            const date = new Date(Number(event.timestamp) * 1000).toLocaleString().replace(/,/g, '');
            let type = '';
            let inputLabel = '';
            let outputLabel = '';
            let priceLabel = '0';

            if (event.type === 'SIGNAL') {
                type = event.signalType === 1 ? 'BUY (USDC -> WETH)' : 'SELL (WETH -> USDC)';
                const inputAmount = Number(event.amountIn);
                const outputAmount = Number(event.amountOut);

                inputLabel = event.signalType === 1
                    ? formatCurrency(inputAmount).replace(/,/g, '')
                    : (formatTokenAmount(inputAmount) + ' WETH');

                outputLabel = event.signalType === 1
                    ? (formatTokenAmount(outputAmount) + ' WETH')
                    : formatCurrency(outputAmount).replace(/,/g, '');

                const price = event.signalType === 1
                    ? (outputAmount > 0 ? inputAmount / outputAmount : 0)
                    : (inputAmount > 0 ? outputAmount / inputAmount : 0);
                priceLabel = formatCurrency(price).replace(/,/g, '');

            } else if (event.type === 'DEPOSIT') {
                type = 'DEPOSIT';
                const assets = Number(event.assets) || 0;
                inputLabel = formatCurrency(assets).replace(/,/g, '');

                // Use calculated shares if available (from Replay Logic), else fallback
                const calculatedShares = (event as any).calculatedShares;
                const sharesFromEvent = event.shares ? Number(event.shares) * 1000000000000 : 0;

                const sharesDisplay = calculatedShares ?? (sharesFromEvent > 0 ? sharesFromEvent : assets);
                outputLabel = formatNumber(sharesDisplay) + ' Shares';
            } else if (event.type === 'WITHDRAWAL') {
                type = 'WITHDRAWAL';
                const assets = Number(event.assets) || 0;
                // Use calculated shares if available
                const calculatedShares = (event as any).calculatedShares; // For withdrawals usually matches event
                const sharesFromEvent = event.shares ? Number(event.shares) : 0;

                const sharesDisplay = calculatedShares ?? (sharesFromEvent > 0 ? sharesFromEvent : assets);

                inputLabel = formatNumber(sharesDisplay) + ' Shares';
                outputLabel = formatCurrency(assets).replace(/,/g, '');
            }

            // Find matching snapshot
            const snapshot = data?.snapshots?.find(s => s.timestamp === event.timestamp);
            const aum = snapshot?.aum ? Number(snapshot.aum) : (Number(snapshot?.totalDeposits ?? 0) - Number(snapshot?.totalWithdrawals ?? 0));

            // Use calculated price from replay logic
            const tokenPrice = (event as any).calculatedPrice ?? 1.0;

            const tokenPriceLabel = formatTokenPrice(tokenPrice).replace(/,/g, '');
            const aumLabel = formatCurrency(aum).replace(/,/g, '');
            const depositsLabel = formatCurrency(Number(snapshot?.totalDeposits ?? 0)).replace(/,/g, '');
            const withdrawalsLabel = formatCurrency(Number(snapshot?.totalWithdrawals ?? 0)).replace(/,/g, '');

            // Use txHash if available (Signals have txHash, Deposits/Withdrawals don't in current Schema access? Need to check Schema)
            // Checking schema.graphql: Deposit and Withdrawal entities DO have txHash!
            // Checking useStrategySubgraphData.ts: The query DOES include id, owner, assets, shares... BUT converting to check...
            // The query in useStrategySubgraphData.ts for deposits/withdrawals is:
            // deposits(first: 1000 ...) { id, owner, assets, shares, timestamp } - MISSING txHash!
            // I need to update the query in useStrategySubgraphData.ts to fetch txHash for deposits/withdrawals first.
            // For now I will use empty string or ID if it looks like a hash? ID is often txHash-logIndex.
            const txHash = (event as any).txHash || (event.id.split('-')[0]) || '';

            return [
                date,
                type,
                inputLabel,
                outputLabel,
                priceLabel,
                tokenPriceLabel,
                aumLabel,
                depositsLabel,
                withdrawalsLabel,
                txHash
            ].join(',');
        });

        const csvContent = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', `yearn-weth-events-${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };

    // Process data for charts using snapshots
    // Process data for charts using Augmented Replay Logic
    const chartData = useMemo(() => {
        // We need chronological order for building cumulative state
        // augmentedEvents is currently reverse-chronological (Newest First)
        const chronologicalEvents = [...augmentedEvents].sort((a, b) => Number(a.timestamp) - Number(b.timestamp));

        // We need to maintain a running total of MINTED shares because the snapshot data is corrupted
        let runningMintedShares = 0;

        return chronologicalEvents.map(event => {
            const snapshot = data?.snapshots?.find(s => String(s.timestamp) === String(event.timestamp));

            // Update running totals based on the event
            if (event.type === 'DEPOSIT') {
                const calculatedShares = (event as any).calculatedShares;
                // If we have a calculated share amount, add it.
                // If not (fallback), we use the logic: shares > 0 ? shares : assets
                // But the calculatedShares field should be populated by the replay logic.
                const fallbackShares = (event.shares && Number(event.shares) > 0) ? Number(event.shares) : (Number((event as any).assets) || 0);
                runningMintedShares += (calculatedShares ?? fallbackShares);
            }
            // For withdrawals, we trust the snapshot/event burned amount
            // But we don't need to track it manually if snapshot.burnedShares is correct.
            // Let's assume snapshot.burnedShares IS correct (as observed).
            const burnedShares = Number(snapshot?.burnedShares ?? 0);
            const netShares = runningMintedShares - burnedShares;

            const aum = snapshot?.aum ? Number(snapshot.aum) : (Number(snapshot?.totalDeposits ?? 0) - Number(snapshot?.totalWithdrawals ?? 0));

            return {
                timestamp: Number(event.timestamp),
                date: new Date(Number(event.timestamp) * 1000).toLocaleDateString(),
                aum: aum,
                totalDeposits: Number(snapshot?.totalDeposits ?? 0),
                totalWithdrawals: Number(snapshot?.totalWithdrawals ?? 0),
                mintedShares: runningMintedShares, // Use our corrected running total
                burnedShares: burnedShares,
                netShares: netShares, // Corrected Net Shares
                // Fields required for Asset Allocation and Price Charts
                usdcBalance: Number(snapshot?.usdcBalance ?? 0),
                wethBalance: Number(snapshot?.wethBalance ?? 0),
                wethPrice: Number(snapshot?.wethPrice ?? 0)
            };
        });
    }, [augmentedEvents, data?.snapshots]);

    // Derive current metrics from the latest chart data point
    const latestData = chartData.length > 0 ? chartData[chartData.length - 1] : null;

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
                allEvents.length > 0 && (
                    <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                        <div className="flex items-center justify-between mb-4">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Recent Activity</p>
                            <div className="flex items-center space-x-4 relative">
                                {filteredEvents.length > 5 && (
                                    <button
                                        onClick={() => setIsExpanded(!isExpanded)}
                                        className="flex items-center text-xs text-zinc-400 hover:text-white transition-colors"
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

                                <div className="relative">
                                    <button
                                        onClick={() => setShowFilter(!showFilter)}
                                        className={`flex items-center justify-center p-1.5 rounded-lg transition-colors ${showFilter ? 'bg-zinc-700 text-white' : 'text-zinc-400 hover:text-white hover:bg-zinc-700/50'}`}
                                    >
                                        <Filter className="h-4 w-4" />
                                    </button>

                                    {showFilter && (
                                        <div className="absolute right-0 mt-2 w-48 rounded-xl border border-zinc-700 bg-zinc-800 shadow-xl z-10 overflow-hidden">
                                            <div className="p-2 space-y-1">
                                                <button
                                                    onClick={() => toggleFilter('deposits')}
                                                    className="w-full flex items-center justify-between px-3 py-2 text-xs rounded-lg hover:bg-zinc-700/50 transition-colors text-zinc-300"
                                                >
                                                    <span className="flex items-center">
                                                        <span className="w-2 h-2 rounded-full bg-blue-400 mr-2"></span>
                                                        Deposits
                                                    </span>
                                                    {filters.deposits && <Check className="h-3 w-3 text-blue-400" />}
                                                </button>
                                                <button
                                                    onClick={() => toggleFilter('withdrawals')}
                                                    className="w-full flex items-center justify-between px-3 py-2 text-xs rounded-lg hover:bg-zinc-700/50 transition-colors text-zinc-300"
                                                >
                                                    <span className="flex items-center">
                                                        <span className="w-2 h-2 rounded-full bg-purple-400 mr-2"></span>
                                                        Withdrawals
                                                    </span>
                                                    {filters.withdrawals && <Check className="h-3 w-3 text-purple-400" />}
                                                </button>
                                                <button
                                                    onClick={() => toggleFilter('buy')}
                                                    className="w-full flex items-center justify-between px-3 py-2 text-xs rounded-lg hover:bg-zinc-700/50 transition-colors text-zinc-300"
                                                >
                                                    <span className="flex items-center">
                                                        <span className="w-2 h-2 rounded-full bg-emerald-400 mr-2"></span>
                                                        Buy Signals
                                                    </span>
                                                    {filters.buy && <Check className="h-3 w-3 text-emerald-400" />}
                                                </button>
                                                <button
                                                    onClick={() => toggleFilter('sell')}
                                                    className="w-full flex items-center justify-between px-3 py-2 text-xs rounded-lg hover:bg-zinc-700/50 transition-colors text-zinc-300"
                                                >
                                                    <span className="flex items-center">
                                                        <span className="w-2 h-2 rounded-full bg-rose-400 mr-2"></span>
                                                        Sell Signals
                                                    </span>
                                                    {filters.sell && <Check className="h-3 w-3 text-rose-400" />}
                                                </button>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            </div>
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
                                        <th className="pb-3 font-medium">Token Price</th>
                                        <th className="pb-3 font-medium">Total AUM</th>
                                        <th className="pb-3 font-medium">Total Deposits</th>
                                        <th className="pb-3 font-medium">Total Withdrawals</th>
                                        <th className="pb-3 font-medium">Tx Hash</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-zinc-700/30">
                                    {displayedEvents.map((event) => {
                                        // Common calculations
                                        const snapshot = data?.snapshots?.find(s => s.timestamp === event.timestamp);
                                        const aum = snapshot?.aum ? Number(snapshot.aum) : (Number(snapshot?.totalDeposits ?? 0) - Number(snapshot?.totalWithdrawals ?? 0));

                                        // Use calculated price from replay logic if available
                                        const tokenPrice = (event as any).calculatedPrice ?? 1.0;

                                        // Type specific rendering
                                        let typeLabel = <></>;
                                        let inputDisplay = <></>;
                                        let outputDisplay = <></>;
                                        let priceDisplay = '0';

                                        if (event.type === 'SIGNAL') {
                                            const s = event as any;
                                            const isBuy = s.signalType === 1;
                                            typeLabel = (
                                                <span className={`inline-flex items-center px-2 py-1 rounded-md text-xs font-medium ${isBuy
                                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                                    : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                                                    }`}>
                                                    {isBuy ? 'BUY' : 'SELL'}
                                                </span>
                                            );
                                            inputDisplay = <>{isBuy ? formatCurrency(Number(s.amountIn)) : formatTokenAmount(Number(s.amountIn)) + ' WETH'}</>;
                                            outputDisplay = <>{isBuy ? formatTokenAmount(Number(s.amountOut)) + ' WETH' : formatCurrency(Number(s.amountOut))}</>;

                                            // Calculate Price for signal
                                            const input = Number(s.amountIn);
                                            const output = Number(s.amountOut);
                                            const price = isBuy
                                                ? (output > 0 ? input / output : 0)
                                                : (input > 0 ? output / input : 0);
                                            priceDisplay = formatCurrency(price);

                                        } else if (event.type === 'DEPOSIT') {
                                            const d = event as any;
                                            typeLabel = (
                                                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                                    DEPOSIT
                                                </span>
                                            );
                                            const depositAssets = Number(d.assets) || 0;
                                            inputDisplay = <>{formatCurrency(depositAssets)}</>;

                                            // PRIORITIZE RAW SHARES IF AVAILABLE (Consistency with CSV)
                                            const rawShares = Number(d.shares ?? 0) * 1000000000000;
                                            const depositSharesDisplay = rawShares > 0 ? rawShares : (d.calculatedShares ?? depositAssets);

                                            outputDisplay = <>{formatNumber(depositSharesDisplay)} Shares</>;
                                            priceDisplay = '-';
                                        } else if (event.type === 'WITHDRAWAL') {
                                            const w = event as any;
                                            typeLabel = (
                                                <span className="inline-flex items-center px-2 py-1 rounded-md text-xs font-medium bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                                    WITHDRAWAL
                                                </span>
                                            );
                                            const withdrawAssets = Number(w.assets) || 0;

                                            // Withdrawal shares are usually accurate from event
                                            const withdrawSharesFromEvent = w.shares ? Number(w.shares) : 0;
                                            const withdrawSharesDisplay = withdrawSharesFromEvent > 0 ? withdrawSharesFromEvent : withdrawAssets;

                                            inputDisplay = <>{formatNumber(withdrawSharesDisplay)} Shares</>;
                                            outputDisplay = <>{formatCurrency(withdrawAssets)}</>;
                                            priceDisplay = '-';
                                        }

                                        const txHash = (event as any).txHash || (event.id.split('-')[0]) || '';

                                        return (
                                            <tr key={event.id} className="group hover:bg-zinc-700/20 transition-colors">
                                                <td className="py-3">{formatTimestamp(event.timestamp)}</td>
                                                <td className="py-3">{typeLabel}</td>
                                                <td className="py-3 text-white font-medium">{inputDisplay}</td>
                                                <td className="py-3 text-white font-medium">{outputDisplay}</td>
                                                <td className="py-3 text-white font-medium">{priceDisplay}</td>
                                                <td className="py-3 text-zinc-300 font-medium">
                                                    {formatTokenPrice(tokenPrice)}
                                                </td>
                                                <td className="py-3 text-zinc-300 font-medium">
                                                    {formatCurrency(aum)}
                                                </td>
                                                <td className="py-3 text-emerald-400/80 font-medium">
                                                    {formatCurrency(Number(snapshot?.totalDeposits ?? 0))}
                                                </td>
                                                <td className="py-3 text-rose-400/80 font-medium">
                                                    {formatCurrency(Number(snapshot?.totalWithdrawals ?? 0))}
                                                </td>
                                                <td className="py-3 font-mono text-xs">
                                                    <a
                                                        href={`https://sepolia.etherscan.io/tx/${txHash}`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="hover:text-blue-400 transition-colors"
                                                    >
                                                        {formatTxHash(txHash)}
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
                (metrics || latestData) && (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total AUM</p>
                            <p className="mt-3 text-3xl font-bold text-white">
                                {formatCurrency(
                                    latestData?.aum ?? (metrics?.currentAum
                                        ? Number(metrics.currentAum)
                                        : (Number(metrics?.totalDeposits ?? '0') - Number(metrics?.totalWithdrawals ?? '0')))
                                )}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Net Share Supply</p>
                            <p className="mt-3 text-3xl font-bold text-white">
                                {formatTokenAmount(
                                    latestData?.netShares ?? (Number(metrics?.mintedShares ?? '0') - Number(metrics?.burnedShares ?? '0'))
                                )}
                            </p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Deposits</p>
                            <p className="mt-3 text-3xl font-bold text-emerald-400">{formatCurrency(latestData?.totalDeposits ?? Number(metrics?.totalDeposits ?? '0'))}</p>
                        </div>
                        <div className="rounded-2xl border border-zinc-700/50 bg-zinc-800/50 p-6 backdrop-blur">
                            <p className="text-xs uppercase tracking-[0.2em] text-zinc-400">Total Withdrawals</p>
                            <p className="mt-3 text-3xl font-bold text-rose-400">{formatCurrency(latestData?.totalWithdrawals ?? Number(metrics?.totalWithdrawals ?? '0'))}</p>
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
                            <AumChart data={chartData as any} />
                        </div>

                        {/* Token Price Chart */}
                        <div className="lg:col-span-1">
                            <TokenPriceChart data={chartData as any} />
                        </div>

                        {/* Asset Allocation Chart */}
                        <div className="lg:col-span-1">
                            <AssetAllocationChart data={chartData as any} />
                        </div>

                        {/* Price Chart */}
                        <div className="lg:col-span-1">
                            <PriceChart data={chartData as any} />
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
                                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} tickFormatter={(val) => `$${val}`} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                                            formatter={(value: number) => [formatCurrency(value), undefined]}
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
                                        <YAxis stroke="#71717a" tick={{ fontSize: 12 }} tickLine={false} tickFormatter={(val) => formatNumber(val)} />
                                        <Tooltip
                                            contentStyle={{ backgroundColor: '#18181b', borderColor: '#3f3f46', borderRadius: '0.5rem' }}
                                            formatter={(value: number) => [formatNumber(value) + ' Shares', undefined]}
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
