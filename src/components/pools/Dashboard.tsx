'use client';

import { useState, useEffect } from 'react';
import CLPoolMonitor from './CLPoolMonitor';
import { nettingPoolsApi, PoolInfo, TokenBalance } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

export default function Dashboard() {
  const { username, walletAddress, isAuthenticated, loading: authLoading } = useNettingPoolsAuth();
  const [mainTab, setMainTab] = useState<'tokens' | 'pools'>('pools');
  const [balances, setBalances] = useState<Record<string, string>>({});
  const [pools, setPools] = useState<PoolInfo[]>([]);
  const [selectedPool, setSelectedPool] = useState<PoolInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>('');

  useEffect(() => {
    if (isAuthenticated && !authLoading) {
      fetchPools();
      if (walletAddress) {
        fetchBalances();
      }
    }
  }, [isAuthenticated, authLoading, walletAddress]);

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

  const fetchBalances = async () => {
    if (!walletAddress) return;
    try {
      const balanceData = await nettingPoolsApi.getBalances(walletAddress);
      const balanceMap: Record<string, string> = {};
      balanceData.forEach((b: TokenBalance) => {
        balanceMap[b.symbol] = b.balance;
      });
      setBalances(balanceMap);
    } catch (err: any) {
      console.error('Error fetching balances:', err);
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
                <div className="mb-8">
                  <h2 className="text-3xl font-light text-white mb-3 tracking-tight">
                    Token Balances
                  </h2>
                  <p className="text-gray-500 text-sm font-light">
                    Your wallet balances
                  </p>
                </div>

                {loading ? (
                  <div className="text-gray-400 text-center py-12">Loading balances...</div>
                ) : (
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
                    {['kUSD', 'kEUR', 'kGBP', 'kAED', 'USDC'].map((symbol) => (
                      <div
                        key={symbol}
                        className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6 hover:bg-white/[0.04] transition-all duration-300"
                      >
                        <div className="text-gray-400 text-xs mb-2">{symbol}</div>
                        <div className="text-2xl font-light text-white">
                          {parseFloat(balances[symbol] || '0').toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={fetchBalances}
                  disabled={loading}
                  className="mt-6 px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
                >
                  {loading ? 'Refreshing...' : 'Refresh Balances'}
                </button>
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

