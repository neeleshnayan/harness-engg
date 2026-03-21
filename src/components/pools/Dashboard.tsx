'use client';

import { useState, useEffect, useRef } from 'react';
import CLPoolMonitor from './CLPoolMonitor';
import PriceFeedCard from './PriceFeedCard';
import MultiHopSwap from './MultiHopSwap';
import TokenControlsSection from './TokenControlsSection';
import { nettingPoolsApi, PoolInfo, RwaPoolLink, TokenBalance } from '@/lib/nettingPoolsApi';
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
  const [rwaPoolLinks, setRwaPoolLinks] = useState<RwaPoolLink[]>([]);
  const [rwaPoolsOpen, setRwaPoolsOpen] = useState(false);
  const rwaPopoverRef = useRef<HTMLDivElement | null>(null);

  // Dynamic token configuration from API
  const [tokenSymbols, setTokenSymbols] = useState<string[]>([]);
  const [fxPairs, setFxPairs] = useState<{ fxPair: string; symbol: string }[]>([]);

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      fetchTokenConfigs();
      fetchPools();
      fetchTotalSupply();
      fetchRwaPoolLinks();
    }
  }, [isAuthenticated, authLoading]);

  useEffect(() => {
    if (!rwaPoolsOpen) {
      return;
    }

    const onPointerDown = (event: MouseEvent) => {
      if (!rwaPopoverRef.current) {
        return;
      }
      if (!rwaPopoverRef.current.contains(event.target as Node)) {
        setRwaPoolsOpen(false);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setRwaPoolsOpen(false);
      }
    };

    document.addEventListener('mousedown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('mousedown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [rwaPoolsOpen]);

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

  const fetchRwaPoolLinks = async () => {
    try {
      const links = await nettingPoolsApi.getRwaPoolLinks();
      setRwaPoolLinks(Array.isArray(links) ? links : []);
    } catch (err: any) {
      console.error('Error fetching RWA pool links:', err);
      setRwaPoolLinks([]);
    }
  };

  const poolTabClasses = (pool: PoolInfo) => {
    const baseClasses = 'px-6 py-3 rounded-xl text-sm font-medium tracking-wide transition-all duration-300';
    if (selectedPool?.pool_address === pool.pool_address) {
      return `${baseClasses} bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg shadow-blue-500/20`;
    }
    return `${baseClasses} bg-white/[0.02] text-gray-400 hover:text-white hover:bg-white/[0.05]`;
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
                <TokenControlsSection
                  tokenSymbols={tokenSymbols}
                  supplies={supplies}
                  suppliesLoading={suppliesLoading}
                  username={username}
                  walletAddress={walletAddress}
                  onRefreshSupplies={fetchTotalSupply}
                />

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
                  <div className="mb-8 flex items-start gap-3">
                    <div className="flex-1 overflow-x-auto pb-2">
                      <div className="flex gap-3 min-w-max">
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
                    </div>

                    <div className="relative shrink-0" ref={rwaPopoverRef}>
                      <button
                        type="button"
                        onClick={() => setRwaPoolsOpen(prev => !prev)}
                        disabled={rwaPoolLinks.length === 0}
                        className={`px-4 py-3 rounded-xl text-sm font-medium tracking-wide transition-all duration-300 border ${
                          rwaPoolLinks.length === 0
                            ? 'bg-white/[0.02] text-gray-500 border-slate-700/40 cursor-not-allowed'
                            : 'bg-white/[0.02] text-gray-200 border-slate-600/40 hover:text-white hover:bg-white/[0.06]'
                        }`}
                      >
                        RWA Pools
                      </button>

                      {rwaPoolsOpen && rwaPoolLinks.length > 0 && (
                        <div className="absolute right-0 top-full mt-2 w-64 rounded-xl border border-slate-700/40 bg-slate-950/95 backdrop-blur-xl shadow-2xl p-2 z-40">
                          <div className="mb-2 px-2 py-1 text-xs text-gray-400 tracking-wide">
                            Uniswap Sepolia
                          </div>
                          <div className="flex flex-col gap-1">
                            {rwaPoolLinks.map((link) => (
                              <button
                                key={link.pool_address}
                                type="button"
                                onClick={() => window.open(link.uniswap_url, '_blank', 'noopener,noreferrer')}
                                className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-200 hover:text-white hover:bg-slate-800/70 transition-colors"
                              >
                                {link.symbol}/USDC
                                <span className="ml-2 text-xs text-gray-500">{link.name}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
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

