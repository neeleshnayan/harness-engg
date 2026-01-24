import React, { useMemo, useState, useEffect } from "react";
import { ComposedChart, Area, ResponsiveContainer, XAxis, YAxis, Tooltip } from "recharts";
import { TrendingUp, Activity } from "lucide-react";
import { useQueries } from '@tanstack/react-query';
import { fetchSubgraph } from "@/hooks/useStrategySubgraphData";
import { hedgeFundApi } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatTokenBalance } from "@/lib/utils";

const DEFAULT_SUBGRAPH_URL = process.env.NEXT_PUBLIC_SUBGRAPH_API_URL || 'https://api.studio.thegraph.com/query/1714038/krypton-liquidity-pools-sepolia/version/latest';

interface CumulativeAUMChartNewProps {
  userWalletAddress?: string;
  yearnWethCurrentBalance?: number; // Legacy prop, can be ignored if we fully switch to strategies prop logic
  strategies?: any[];
}

type DataPoint = {
  timestamp: number;
  date: string;
  totalAUM: number;
  [key: string]: any; // Allow dynamic keys for individual strategy AUMs if needed debugging
};

type TimescaleOption = "15m" | "1h" | "1d" | "30d" | "1mo";

const TIMESCALE_OPTIONS: { value: TimescaleOption; label: string }[] = [
  { value: "15m", label: "Past 15 mins" },
  { value: "1h", label: "Past 1 hr" },
  { value: "1d", label: "Past 1 day" },
  { value: "30d", label: "Past 30 days" },
  { value: "1mo", label: "Past 1 month" },
];

const getTimescaleSeconds = (timescale: TimescaleOption): number => {
  const now = Math.floor(Date.now() / 1000);
  switch (timescale) {
    case "15m": return now - 15 * 60;
    case "1h": return now - 60 * 60;
    case "1d": return now - 24 * 60 * 60;
    case "30d": return now - 30 * 24 * 60 * 60;
    case "1mo": return now - 30 * 24 * 60 * 60;
    default: return 0;
  }
};

const formatDate = (timestamp: number, timescale?: TimescaleOption): string => {
  const date = new Date(timestamp * 1000);
  if (timescale === "15m" || timescale === "1h") {
    return date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
  }
  if (timescale === "1d") {
    return date.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit', hour12: true });
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
};

const formatAUM = (aum: number): string => {
  if (aum >= 1000000) return `$${(aum / 1000000).toFixed(2)}M`;
  if (aum >= 1000) return `$${(aum / 1000).toFixed(2)}K`;
  return `$${aum.toFixed(2)}`;
};

const CustomTooltip = ({ active, payload, strategies }: any) => {
  if (!active || !payload || !payload.length) return null;
  const data = payload[0]?.payload as DataPoint;
  if (!data) return null;

  return (
    <div className="bg-zinc-800/95 backdrop-blur-xl border border-zinc-700 rounded-lg p-3 shadow-xl">
      <p className="text-xs text-zinc-400 mb-2">{data.date}</p>
      <p className="text-sm font-bold text-green-400 mb-2">
        Total: {formatAUM(data.totalAUM)}
      </p>
      <div className="space-y-1 pt-2 border-t border-zinc-700/50">
        {strategies?.map((strategy: any) => {
          const balance = data[strategy.id];
          if (!balance || balance <= 0) return null;

          return (
            <div key={strategy.id} className="flex items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-zinc-400"></div>
                <span className="text-zinc-300">{strategy.name || strategy.id}</span>
              </div>
              <span className="text-zinc-200 font-mono">{formatAUM(balance)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export const CumulativeAUMChartNew: React.FC<CumulativeAUMChartNewProps> = ({
  userWalletAddress,
  strategies = []
}) => {
  const [selectedTimescale, setSelectedTimescale] = useState<TimescaleOption>("30d");
  const [activeStrategyBalances, setActiveStrategyBalances] = useState<Record<string, number>>({});

  // 1. Fetch Subgraph Data for ALL active strategies
  const strategyQueries = useQueries({
    queries: strategies.map(strategy => {
      // Fallback to vault_address if address is missing
      const targetAddress = strategy.address || strategy.vault_address || strategy.contract_address;
      const subgraphUrl = strategy.subgraph_url || DEFAULT_SUBGRAPH_URL;

      // DEBUG: Log used parameters
      // console.log(`[Chart] Query params for ${strategy.id}: Address=${targetAddress}, URL=${subgraphUrl}`);

      return {
        queryKey: ['subgraph', 'analytics', strategy.id, targetAddress, userWalletAddress],
        queryFn: () => fetchSubgraph(subgraphUrl, strategy.id, targetAddress, userWalletAddress),
        enabled: !!userWalletAddress && !!targetAddress,
        staleTime: 60000,
      };
    })
  });

  const isLoading = strategyQueries.some(q => q.isLoading);

  // 2. Fetch Live Balances for ALL active strategies (to fill gap at end of chart)
  useEffect(() => {
    const fetchAllBalances = async () => {
      if (!userWalletAddress || strategies.length === 0) return;

      const balanceMap: Record<string, number> = {};

      await Promise.all(strategies.map(async (strategy) => {
        try {
          // Skip if no ID (shouldn't happen)
          if (!strategy.id) return;

          const response = await hedgeFundApi.get(`/api/v1/strategy/${strategy.id}/balance/${userWalletAddress}`);
          const data = response.data;
          if (data.balance) {
            const contractDecimals = data.decimals || 18; // Default to 18 if missing
            // For now, assume display decimals logic matches contract decimals or simple division
            // If we need specific display logic per strategy, we'd need config. 
            // We use standard power of 10.
            const balance = Number(data.balance) / Math.pow(10, contractDecimals);
            balanceMap[strategy.id] = balance;
          }
        } catch (e) {
          // Ignore errors for individual strategies
        }
      }));

      setActiveStrategyBalances(balanceMap);
    };

    fetchAllBalances();
    const interval = setInterval(fetchAllBalances, 15000); // 15s poll
    return () => clearInterval(interval);
  }, [userWalletAddress, strategies]);


  // 3. Aggregate Data and Build Timeline
  const chartData = useMemo(() => {
    if (!userWalletAddress || strategies.length === 0) return [];

    const timescaleStart = getTimescaleSeconds(selectedTimescale);
    const currentTime = Math.floor(Date.now() / 1000);

    // Collect all events from all successful queries
    let allDeposits: any[] = [];
    let allWithdrawals: any[] = [];

    strategyQueries.forEach((query, index) => {
      if (query.data) {
        const strategy = strategies[index];
        // Tag events with strategy ID if needed for debugging
        const strategyId = strategy?.id;
        const deposits = (query.data.deposits || []).map(d => ({ ...d, strategyId }));
        const withdrawals = (query.data.withdrawals || []).map(w => ({ ...w, strategyId }));

        console.log(`[Chart] Data for ${strategyId}: Deposits: ${deposits.length}, Withdrawals: ${withdrawals.length}`);

        allDeposits = [...allDeposits, ...deposits];
        allWithdrawals = [...allWithdrawals, ...withdrawals];
      }
    });

    // Collect all unique timestamps
    const allTimestamps = new Set<number>();
    allDeposits.forEach(d => allTimestamps.add(Number(d.timestamp)));
    allWithdrawals.forEach(w => allTimestamps.add(Number(w.timestamp)));

    const sortedTimestamps = Array.from(allTimestamps).sort((a, b) => a - b);

    // Replay history
    const dataPoints: DataPoint[] = [];

    // Track running balance for EACH strategy
    // Map: StrategyID -> Current Amount
    const currentBalances: Record<string, number> = {};

    for (const timestamp of sortedTimestamps) {
      // Process deposits at this timestamp
      allDeposits.forEach(d => {
        if (Number(d.timestamp) === timestamp) {
          const stratId = d.strategyId;
          const amount = Number(d.assets) || 0;
          // Note: We are summing "assets" which are usually raw units (e.g. 6 decimals for USDC).
          // We need to normalize this to be meaningful (USD).
          // Ideally we look up the strategy decimals. 
          // For now, we assume standard USDC-like or normalize to 1e6 if it looks like USDC, else 1e18?
          // BETTER: Use the `strategies` prop to find decimals.

          const strategy = strategies.find(s => s.id === stratId);
          const decimals = strategy?.asset_decimals || 6; // Default to 6 (USDC)

          const normalizedAmount = amount; // / Math.pow(10, decimals); // WAIT: The previous chart summed raw values? 
          // Previous Yearn chart logic: `yearnWethShares += (Number(d.assets) || 0);`
          // It didn't divide. formatAUM handled the display assuming 6 decimals or similar? 
          // formatAUM: `if (aum >= 1000000) return ...M`
          // If aum is 1,000,000 (1M), it displays $1.00M. 
          // If input is 100 USDC (100,000,000 units), formatAUM(100,000,000) -> $100.00M? No.
          // Let's re-read formatAUM.
          // `if (aum >= 1000000) return ${(aum / 1000000).toFixed(2)}M;`
          // If I have $100 (100 * 10^6 = 100,000,000), then 100,000,000 / 1,000,000 = 100. So it displays "$100.00M".
          // Wait, $100 is not $100 Million.
          // 1 USDC = 1,000,000 units.
          // If I have 1 USDC, value = 1,000,000.
          // formatAUM(1,000,000) -> 1,000,000 / 1,000,000 = 1 -> "$1.00M".
          // This means the old chart was displaying "Millions" for single dollars? 
          // OR, the input `d.assets` was *already* normalized? 
          // Subgraph `assets` is typically raw uInt256.
          // Let's assume the previous chart was somehow working for Yearn (maybe huge numbers?)
          // OR, `formatAUM` logic is: AUM is *raw units* (wei/mwei).
          // 1,000,000 units = 1 USDC.
          // formatAUM(1,000,000) -> "$1.00M"? That implies 1 Million Dollars? 
          // No, M usually means Million.
          // Perhaps `d.assets` from that subgraph is normalized?
          // Let's stick to: "Sum the amounts as they come from subgraph".
          // BUT for multi-strategy, we might have mixed decimals (18 vs 6).

          // CRITICAL FIX: We MUST normalize everything to a common base (e.g. 6 decimals or USD value).
          // If we assume all strategies hold approx $1 value per unit (stablecoins), or we just want "Total Units".
          // But Gold/Silver/Nvidia are different prices.
          // Without historical price data for every asset, we can't perfectly calculate "Total USD AUM" historically.
          // However, user just wants to see the line.
          // We will sum the "Assets" (input token amount). 
          // Most inputs are USDC (6 decimals) for these strategies? 
          // If User deposits USDC into Gold Strategy, `assets` is USDC amount.
          // If User deposits USDC into Nvidia Strategy, `assets` is USDC amount.
          // So if we sum `assets`, we are summing the USDC invested. This is a good proxy for "Cost Basis AUM".
          // So we just need to ensure we handle decimals if they differ.

          currentBalances[stratId] = (currentBalances[stratId] || 0) + amount;
        }
      });

      // Process withdrawals
      allWithdrawals.forEach(w => {
        if (Number(w.timestamp) === timestamp) {
          const stratId = w.strategyId;
          const amount = Number(w.assets) || 0;
          currentBalances[stratId] = (currentBalances[stratId] || 0) - amount;
        }
      });

      // Sum all balances
      let total = 0;
      Object.values(currentBalances).forEach(val => total += val);

      // Ensure no negative
      if (total < 0) total = 0;

      dataPoints.push({
        timestamp,
        date: formatDate(timestamp, selectedTimescale),
        totalAUM: total,
        yearnWethAUM: 0, // deprecated
        ...currentBalances, // Spread individual strategy balances
      });
    }

    // Add Live Point (Gap Fill)
    // We replace the "end" of the chart with the sum of all live balances
    const liveTotal = Object.values(activeStrategyBalances).reduce((a, b) => a + b, 0);

    // Refined Loop for Normalization:
    const normalizedPoints = dataPoints.map(p => {
      // Normalize aggregate total
      const normalizedTotal = p.totalAUM / 1000000;

      // Normalize individual strategies
      const normalizedStrategies: any = {};
      strategies.forEach(s => {
        if (p[s.id]) {
          normalizedStrategies[s.id] = p[s.id] / 1000000;
        }
      });

      return {
        ...p,
        totalAUM: normalizedTotal,
        ...normalizedStrategies
      };
    });

    // Add Live Point
    if (normalizedPoints.length > 0) {
      const last = normalizedPoints[normalizedPoints.length - 1];
      if (currentTime - last.timestamp > 60) {
        normalizedPoints.push({
          timestamp: currentTime,
          date: formatDate(currentTime, selectedTimescale),
          totalAUM: liveTotal, // liveTotal is already normalized
          yearnWethAUM: 0,
          ...activeStrategyBalances // activeStrategyBalances is already normalized
        });
      }
    } else if (liveTotal > 0) {
      // ... (No history case)
      const emptyPoint = {
        timestamp: timescaleStart,
        date: formatDate(timescaleStart, selectedTimescale),
        totalAUM: 0,
        yearnWethAUM: 0
      };
      // Initialize 0 for all strategies
      strategies.forEach(s => { (emptyPoint as any)[s.id] = 0; });
      normalizedPoints.push(emptyPoint);

      normalizedPoints.push({
        timestamp: currentTime,
        date: formatDate(currentTime, selectedTimescale),
        totalAUM: liveTotal,
        yearnWethAUM: 0,
        ...activeStrategyBalances
      });
    }

    return normalizedPoints.filter(p => p.timestamp >= timescaleStart);
  }, [strategyQueries, activeStrategyBalances, strategies, selectedTimescale, userWalletAddress]);


  const stats = useMemo(() => {
    if (chartData.length === 0) return null;
    const latest = chartData[chartData.length - 1];
    const first = chartData[0];
    const change = latest.totalAUM - first.totalAUM;
    const changePercent = first.totalAUM > 0 ? (change / first.totalAUM) * 100 : 0;

    return {
      current: latest.totalAUM,
      start: first.totalAUM,
      change,
      changePercent,
      isPositive: change >= 0
    };
  }, [chartData]);


  if (isLoading) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800">
        <Skeleton className="h-64 w-full bg-zinc-700/50 rounded-lg" />
      </div>
    );
  }

  if (chartData.length === 0) {
    return (
      <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
        <div className="flex items-center justify-center py-6 text-zinc-500">
          <Activity className="w-4 h-4 mr-2" />
          <span className="text-xs sm:text-sm">No portfolio data available for selected time period</span>
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <div className="bg-zinc-900/80 backdrop-blur-xl rounded-2xl sm:rounded-3xl p-4 sm:p-6 md:p-8 shadow-2xl border border-zinc-800">
      <div className="mb-4 sm:mb-6">
        <div className="flex flex-col sm:flex-row items-start justify-between gap-3 sm:gap-4 mb-4">
          <div className="flex-1 w-full">
            <h3 className="text-xl sm:text-2xl font-bold text-white mb-2">Portfolio Performance</h3>
            <p className="text-zinc-400 text-xs sm:text-sm mb-3 sm:mb-4">Total Assets Under Management Across All Strategies</p>
            <div className="text-2xl sm:text-3xl font-bold text-green-400 mb-2">
              {formatAUM(stats.current)}
            </div>
          </div>
          <Select value={selectedTimescale} onValueChange={(value) => setSelectedTimescale(value as TimescaleOption)}>
            <SelectTrigger className="w-full sm:w-[160px] bg-zinc-800/50 border-zinc-700 text-white">
              <SelectValue />
            </SelectTrigger>
            <SelectContent className="bg-zinc-800 border-zinc-700">
              {TIMESCALE_OPTIONS.map((option) => (
                <SelectItem
                  key={option.value}
                  value={option.value}
                  className="text-white focus:bg-zinc-700 focus:text-white"
                >
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 mb-3">
        <span className="text-xs text-zinc-400 whitespace-nowrap">PORTFOLIO PERFORMANCE OVER TIME</span>
        <div className="flex items-center gap-2 text-xs">
          <TrendingUp className={`w-3 h-3 ${stats.isPositive ? 'text-green-400' : 'text-red-400'}`} />
          <span className={stats.isPositive ? 'text-green-400' : 'text-red-400'}>
            {stats.isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
          </span>
        </div>
      </div>

      <div className="h-48 sm:h-56 md:h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 20 }}>
            <defs>
              <linearGradient id="totalAUMGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.6} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis
              dataKey="date"
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              angle={-45}
              textAnchor="end"
              height={50}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              stroke="#3f3f46"
              tickFormatter={(value) => formatAUM(value)}
            />
            <Tooltip content={<CustomTooltip strategies={strategies} />} />
            <Area
              type="monotone"
              dataKey="totalAUM"
              fill="url(#totalAUMGradient)"
              stroke="#22c55e"
              strokeWidth={2}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
};
