import { useState, useEffect, useCallback } from 'react';
import { subgraphApi, PoolSwapEntry } from '@/lib/subgraphApi';
import { ArrowUpDown, AlertCircle, RefreshCw } from 'lucide-react';

interface TransactionHistoryProps {
  poolAddress: string;
  token0Address?: string; // Optional for now to maintain compatibility if not passed immediately
  token1Address?: string;
  title?: string;
  maxShow?: number;
  showFilters?: boolean;
}

export default function TransactionHistory({
  poolAddress,
  token0Address,
  token1Address,
  title = 'Recent Swaps',
  maxShow = 20,
}: TransactionHistoryProps) {
  const [swaps, setSwaps] = useState<PoolSwapEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showAll, setShowAll] = useState(false);

  const fetchSwaps = useCallback(async () => {
    if (!poolAddress) return;

    setLoading(true);
    setError('');

    try {
      console.log(`[TransactionHistory] Fetching swaps for pool: ${poolAddress}`);
      console.log(`[TransactionHistory] Token addresses: ${token0Address} / ${token1Address}`);

      // Fetch up to 50 swaps
      const response = await subgraphApi.getPoolSwaps(poolAddress, 50, 0, token0Address, token1Address);

      console.log(`[TransactionHistory] Raw response:`, response);

      let fetchedSwaps = response.swaps || [];
      console.log(`[TransactionHistory] Fetched ${fetchedSwaps.length} swaps`);

      // Sort just in case API didn't
      fetchedSwaps.sort((a, b) => b.timestamp - a.timestamp);

      setSwaps(fetchedSwaps);
    } catch (err: any) {
      console.error('[TransactionHistory] Error fetching pool swaps:', err);
      setError('Failed to load swaps');
    } finally {
      setLoading(false);
    }
  }, [poolAddress, token0Address, token1Address]);

  useEffect(() => {
    fetchSwaps();
  }, [fetchSwaps]);

  const displayedSwaps = showAll ? swaps : swaps.slice(0, maxShow);

  const formatUsername = (swap: PoolSwapEntry) => {
      // Assuming 'username' field is added to PoolSwapEntry via backend enrichment
      if ((swap as any).username) return `@${(swap as any).username}`;
      if (swap.user) return `${swap.user.substring(0, 6)}...${swap.user.substring(swap.user.length - 4)}`;
      return 'Unknown';
  };

  if (loading && swaps.length === 0) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <h4 className="text-lg font-medium text-white mb-4">{title}</h4>
        <div className="flex justify-center py-8">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-cyan-400"></div>
        </div>
      </div>
    );
  }

  if (error && swaps.length === 0) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
            <h4 className="text-lg font-medium text-white">{title}</h4>
            <button
                onClick={fetchSwaps}
                className="p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-gray-400 hover:text-white transition-colors"
                title="Refresh"
            >
                <RefreshCw className="h-4 w-4" />
            </button>
        </div>
        <div className="text-red-400 text-sm text-center py-8 flex items-center justify-center gap-2">
            <AlertCircle className="h-4 w-4" />
            {error}
        </div>
      </div>
    );
  }

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-medium text-white">{title}</h4>
        <div className="flex items-center gap-2">
            <span className="text-[10px] bg-white/[0.05] text-gray-500 px-2 py-1 rounded font-mono truncate max-w-[100px]" title={poolAddress}>
                {poolAddress.substring(0,6)}...
            </span>
            <span className="text-xs bg-white/[0.05] text-gray-400 px-2 py-1 rounded-lg">
                {swaps.length} swap{swaps.length !== 1 ? 's' : ''}
            </span>
            <button
                onClick={fetchSwaps}
                className={`p-1.5 rounded-lg bg-white/[0.05] hover:bg-white/[0.1] text-gray-400 hover:text-white transition-colors ${loading ? 'animate-spin' : ''}`}
                title="Refresh"
                disabled={loading}
            >
                <RefreshCw className="h-3.5 w-3.5" />
            </button>
        </div>
      </div>

      {displayedSwaps.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p className="text-sm">No recent swaps</p>
          <p className="text-xs mt-2">Pool swaps will appear here</p>
          {token0Address && token1Address && (
            <p className="text-[10px] mt-1 text-gray-600 font-mono">
              Querying: {token0Address.substring(0,6)}...{token0Address.substring(38)} ↔ {token1Address.substring(0,6)}...{token1Address.substring(38)}
            </p>
          )}
        </div>
      ) : (
        <div className="space-y-0">
          {displayedSwaps.map((tx, idx) => (
            <div
              key={`${tx.hash}-${idx}`}
              className={`flex items-center justify-between p-3 hover:bg-white/[0.04] transition-all border-b border-white/[0.03] last:border-0`}
            >
              {/* Left Column: Icon + Primary Info */}
              <div className="flex items-center gap-3 flex-1 overflow-hidden">
                 <div className="w-8 h-8 rounded-full bg-white/[0.03] flex items-center justify-center flex-shrink-0">
                    <ArrowUpDown className="h-4 w-4 text-cyan-400 rotate-90" />
                 </div>

                 <div className="flex flex-col overflow-hidden">
                    <div className="flex items-center text-sm font-medium text-white gap-1.5 flex-wrap">
                        <span className="whitespace-nowrap">{tx.amount_in.toLocaleString(undefined, { maximumFractionDigits: 4 })} <span className="text-gray-400 text-xs">{tx.token_in}</span></span>
                        <span className="text-gray-500">→</span>
                        <span className="whitespace-nowrap">{tx.amount_out.toLocaleString(undefined, { maximumFractionDigits: 4 })} <span className="text-gray-400 text-xs">{tx.token_out}</span></span>
                    </div>
                    <div className="text-xs text-blue-400/80 mt-0.5 truncate flex items-center gap-1">
                        By <span className="font-medium text-blue-300">{formatUsername(tx)}</span>
                    </div>
                 </div>
              </div>

              {/* Right Column: Time + Link */}
              <div className="flex flex-col items-end gap-1 ml-4 min-w-[80px]">
                 <span className="text-xs text-gray-500 font-mono text-right">
                    {new Date(tx.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                 </span>
                 <a
                    href={`https://sepolia.etherscan.io/tx/${tx.hash}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1 text-[10px] text-blue-500 hover:text-blue-300 font-mono bg-blue-500/10 px-1.5 py-0.5 rounded"
                 >
                    {tx.hash.substring(0,6)}...
                 </a>
                 <span className="text-[10px] text-gray-600">
                    {new Date(tx.timestamp * 1000).toLocaleDateString([], {month:'short', day:'numeric'})}
                 </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {swaps.length > maxShow && (
         <div className="text-center mt-3 pt-2 border-t border-white/[0.05]">
            <button
                onClick={() => setShowAll(!showAll)}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors"
            >
                {showAll ? 'Show Less' : `Show All (${swaps.length - maxShow} more)`}
            </button>
         </div>
      )}
    </div>
  );
}
