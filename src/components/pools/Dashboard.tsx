'use client';

import { useState, useEffect } from 'react';
import CLPoolMonitor from './CLPoolMonitor';
import PriceFeedCard from './PriceFeedCard';
import MultiHopSwap from './MultiHopSwap';
import { nettingPoolsApi, PoolInfo, TokenBalance } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

export default function Dashboard() {
  const { username, walletAddress, isAuthenticated, loading: authLoading } = useNettingPoolsAuth();
  const [mainTab, setMainTab] = useState<'tokens' | 'pools'>('tokens'); // Default to tokens tab
  const [supplies, setSupplies] = useState<Record<string, string>>({});
  const [pools, setPools] = useState<PoolInfo[]>([]);
  const [selectedPool, setSelectedPool] = useState<PoolInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [suppliesLoading, setSuppliesLoading] = useState(true);
  const [error, setError] = useState<string>('');

  // Dynamic token configuration from API
  const [tokenSymbols, setTokenSymbols] = useState<string[]>([]);
  const [fxPairs, setFxPairs] = useState<{ fxPair: string; symbol: string }[]>([]);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      fetchTokenConfigs();
      fetchPools();
      fetchTotalSupply();
    }
  }, [isAuthenticated, authLoading]);

  const fetchTokenConfigs = async () => {
    try {
      const data = await nettingPoolsApi.getSupportedTokens();
      const kTokens = data.k_tokens || {};

      // Build token symbols list (filter out placeholder addresses)
      const symbols = Object.keys(kTokens).filter(
        symbol => kTokens[symbol]?.address && kTokens[symbol].address !== '0x0000000000000000000000000000000000000000'
      );
      setTokenSymbols(symbols);

      // Build FX pairs list from tokens that have fx_pair configured
      const pairs: { fxPair: string; symbol: string }[] = [];
      for (const symbol of symbols) {
        const config = kTokens[symbol];
        if (config?.fx_pair) {
          pairs.push({ fxPair: config.fx_pair, symbol });
        }
      }
      setFxPairs(pairs);
    } catch (err: any) {
      console.error('Error fetching token configs:', err);
    }
  };

  const fetchPools = async () => {
    setLoading(true);
    setError('');
    try {
      const poolData = await nettingPoolsApi.getPools();
      setPools(poolData);
      if (poolData.length > 0 && !selectedPool) {
        setSelectedPool(poolData[0]);
      }
    } catch (err: any) {
      setError('Failed to load pools: ' + (err.message || 'Unknown error'));
      console.error('Error fetching pools:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchTotalSupply = async () => {
    setSuppliesLoading(true);
    try {
      const supplyData = await nettingPoolsApi.getTotalSupply();
      const supplyMap: Record<string, string> = {};
      supplyData.forEach((b: TokenBalance) => {
        supplyMap[b.symbol] = b.balance;
      });
      setSupplies(supplyMap);
    } catch (err: any) {
      console.error('Error fetching total supply:', err);
    } finally {
      setSuppliesLoading(false);
    }
  };

  const poolTabClasses = (pool: PoolInfo) => {
    const baseClasses = 'px-6 py-3 rounded-xl text-sm font-medium tracking-wide transition-all duration-300';
    if (selectedPool?.pool_address === pool.pool_address) {
      return `${baseClasses} bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20`;
    }
    return `${baseClasses} bg-white/[0.02] text-gray-400 hover:text-white hover:bg-white/[0.05]`;
  };

  /** Format a supply string with comma-separated thousands and 2 decimal places. */
  const formatSupply = (value: string | undefined): string => {
    const num = parseFloat(value || '0');
    return new Intl.NumberFormat('en', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-black flex items-center justify-center">
        <div className="text-white">Please sign in to access liquidity pools</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-black">
      <div className="max-w-7xl mx-auto px-8 py-16">
        {/* Header */}
        <div className="mb-16 flex items-start justify-between">
          <div>
            <h1 className="text-5xl font-light tracking-tight bg-gradient-to-r from-blue-400 to-indigo-300 bg-clip-text text-transparent mb-3 pb-1 leading-tight">
              Liquidity Pools
            </h1>
            <p className="text-gray-500 text-sm font-light tracking-wide">
              Monitor and manage pool liquidity
            </p>
          </div>
          <div className="text-right">
            <div className="text-gray-400 text-xs mb-1">Signed in as</div>
            <div className="text-blue-400 font-mono text-sm">{username}</div>
            {walletAddress && (
              <div className="text-gray-500 font-mono text-xs mt-1">
                {walletAddress.slice(0, 6)}...{walletAddress.slice(-4)}
              </div>
            )}
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
            {error}
          </div>
        )}

        {/* Main Tab Selector */}
        <div className="backdrop-blur-xl bg-slate-900/40 border border-slate-700/30 rounded-2xl overflow-hidden mb-8 shadow-2xl">
          <div className="flex p-2 gap-3">
            <button
              onClick={() => setMainTab('tokens')}
              className={`flex-1 px-8 py-6 rounded-xl text-base font-medium tracking-wide transition-all duration-300 ${
                mainTab === 'tokens'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-xl shadow-blue-500/20'
                  : 'text-gray-400 hover:text-white hover:bg-slate-800/30 border border-transparent hover:border-slate-600/30'
              }`}
            >
              <div className="flex items-center justify-center gap-3">
                <span className="text-2xl">💎</span>
                <span className="text-base">Tokens</span>
              </div>
            </button>
            <button
              onClick={() => setMainTab('pools')}
              className={`flex-1 px-8 py-6 rounded-xl text-base font-medium tracking-wide transition-all duration-300 ${
                mainTab === 'pools'
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-xl shadow-blue-500/20'
                  : 'text-gray-400 hover:text-white hover:bg-slate-800/30 border border-transparent hover:border-slate-600/30'
              }`}
            >
              <div className="flex items-center justify-center gap-3">
                <span className="text-2xl">○</span>
                <span className="text-base">Pools</span>
              </div>
            </button>
          </div>

          {/* Main Tab Content */}
          <div className="p-6">
            {mainTab === 'tokens' ? (
              <div>
                <div className="mb-8">
                  <h2 className="text-3xl font-light text-white mb-3 tracking-tight">
                    Token Balances
                  </h2>
                  <p className="text-gray-500 text-sm font-light">
                    Total tokens in circulation
                  </p>
                </div>

                {tokenSymbols.length === 0 ? (
                  /* Skeleton grid while loading token config */
                  <div className="flex flex-wrap gap-6">
                    {[1, 2, 3, 4, 5].map((i) => (
                      <div
                        key={i}
                        className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6 animate-pulse min-w-[160px]"
                      >
                        <div className="h-4 bg-white/[0.08] rounded w-12 mb-4" />
                        <div className="h-8 bg-white/[0.08] rounded w-20" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-6">
                    {tokenSymbols.map((symbol) => (
                      <div
                        key={symbol}
                        className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6 hover:bg-white/[0.04] transition-all duration-300 min-w-[160px]"
                      >
                        <div className="text-gray-400 text-xs mb-2">{symbol}</div>
                        {suppliesLoading ? (
                          <div className="h-8 bg-white/[0.08] rounded w-20 animate-pulse" />
                        ) : (
                          <div className="text-2xl font-light text-white whitespace-nowrap">
                            {formatSupply(supplies[symbol])}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={fetchTotalSupply}
                  disabled={suppliesLoading}
                  className="mt-6 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
                >
                  {suppliesLoading ? 'Refreshing...' : 'Refresh'}
                </button>

                {/* Oracle Price Feeds Section */}
                <div className="mt-12">
                  <div className="mb-6">
                    <h3 className="text-xl font-light text-white mb-2">Live Oracle Rates</h3>
                    <p className="text-gray-500 text-sm font-light">
                      Current FX rates from KryptonFXOracle
                    </p>
                  </div>
                  {fxPairs.length === 0 ? (
                    <div className="text-gray-400 text-center py-6">Loading FX pairs...</div>
                  ) : (
                    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
                      {fxPairs.map((pair) => (
                        <PriceFeedCard
                          key={pair.fxPair}
                          fxPair={pair.fxPair}
                          symbol={pair.symbol}
                        />
                      ))}
                    </div>
                  )}
                </div>

                {/* Multi-Hop Swap Section */}
                <div className="mt-12">
                  <div className="mb-6">
                    <h3 className="text-xl font-light text-white mb-2">Multi-Hop Swap</h3>
                    <p className="text-gray-500 text-sm font-light">
                      Swap between any tokens through kUSD hub
                    </p>
                  </div>
                  <MultiHopSwap onSuccess={fetchTotalSupply} />
                </div>
              </div>
            ) : (
              <div>
                <div className="mb-8">
                  <h2 className="text-3xl font-light text-white mb-3 tracking-tight">
                    Liquidity Pools
                  </h2>
                  <p className="text-gray-500 text-sm font-light">
                    Select a pool to monitor
                  </p>
                </div>

                {/* Pool Selection Tabs */}
                {pools.length > 0 && (
                  <div className="flex gap-3 mb-8 overflow-x-auto pb-2">
                    {pools.map((pool) => (
                      <button
                        key={pool.pool_address}
                        onClick={() => setSelectedPool(pool)}
                        className={poolTabClasses(pool)}
                      >
                        {pool.token0_symbol}/{pool.token1_symbol}
                        {!pool.is_initialized && (
                          <span className="ml-2 text-xs text-yellow-400">●</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}

                {loading ? (
                  <div className="text-gray-400 text-center py-12">Loading pools...</div>
                ) : selectedPool ? (
                  <CLPoolMonitor
                    poolAddress={selectedPool.pool_address}
                    token0Symbol={selectedPool.token0_symbol}
                    token1Symbol={selectedPool.token1_symbol}
                    token0Address={selectedPool.token0_address}
                    token1Address={selectedPool.token1_address}
                    rateProviderAddress={selectedPool.rate_provider || ''}
                    onRefresh={fetchPools}
                  />
                ) : (
                  <div className="text-gray-400 text-center py-12">No pools available</div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

