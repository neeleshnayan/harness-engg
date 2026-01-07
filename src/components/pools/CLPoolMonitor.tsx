'use client';

import { useState, useEffect } from 'react';
import { nettingPoolsApi, PoolState } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';
import { useTransactionStatus } from '@/hooks/useTransactionStatus';
import SwapForm from './SwapForm';
import InitializePoolForm from './InitializePoolForm';
import AddLiquidityForm from './AddLiquidityForm';

interface CLPoolMonitorProps {
  poolAddress: string;
  token0Symbol: string;
  token1Symbol: string;
  token0Address: string;
  token1Address: string;
  rateProviderAddress: string;
  onRefresh?: () => void;
}

export default function CLPoolMonitor({
  poolAddress,
  token0Symbol,
  token1Symbol,
  token0Address,
  token1Address,
  rateProviderAddress,
  onRefresh,
}: CLPoolMonitorProps) {
  const { username } = useNettingPoolsAuth();
  const [poolState, setPoolState] = useState<PoolState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeTab, setActiveTab] = useState<'info' | 'swap' | 'liquidity' | 'initialize'>('info');
  const [lastTxId, setLastTxId] = useState<string | null>(null);
  const { status: txStatus, loading: txLoading } = useTransactionStatus(lastTxId);

  useEffect(() => {
    fetchPoolState();
    const interval = setInterval(fetchPoolState, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [poolAddress]);

  const fetchPoolState = async () => {
    setLoading(true);
    setError('');
    try {
      const state = await nettingPoolsApi.getPoolState(poolAddress);
      setPoolState(state);
    } catch (err: any) {
      setError('Failed to fetch pool state: ' + (err.message || 'Unknown error'));
      console.error('Error fetching pool state:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSyncRate = async (manualRate?: number) => {
    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const result = await nettingPoolsApi.syncRate({
        token_symbol: token1Symbol,
        manual_rate: manualRate,
        username: username,
      });
      setSuccess(`Rate sync submitted! Transaction ID: ${result.transaction_id}`);
      setLastTxId(result.transaction_id);
      setTimeout(fetchPoolState, 5000); // Refresh after 5 seconds
    } catch (err: any) {
      setError('Failed to sync rate: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const calculateDeviation = () => {
    if (!poolState || !poolState.oracle_rate) return null;
    const poolPrice = parseFloat(poolState.spot_price);
    const oracleRate = parseFloat(poolState.oracle_rate);
    const deviation = ((poolPrice / oracleRate) - 1) * 100;
    return deviation.toFixed(2);
  };

  const tabButtonClasses = (tab: string) => {
    const baseClasses = 'px-4 py-2 rounded-lg text-sm font-medium transition-all';
    if (activeTab === tab) {
      return `${baseClasses} bg-blue-600 text-white`;
    }
    return `${baseClasses} bg-white/[0.05] text-gray-400 hover:text-white hover:bg-white/[0.1]`;
  };

  return (
    <div className="space-y-6">
      {/* Pool Info Card */}
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-2xl font-light text-white">
            {token0Symbol}/{token1Symbol} Pool
          </h3>
          <button
            onClick={fetchPoolState}
            disabled={loading}
            className="p-2 hover:bg-white/[0.05] rounded-lg transition-all disabled:opacity-50"
          >
            <svg className={`w-5 h-5 text-gray-400 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
            {success}
          </div>
        )}

        {txLoading && lastTxId && (
          <div className="mb-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
            Transaction Status: {txStatus} (Polling...)
          </div>
        )}

        {poolState ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Pool Status */}
            <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
              <div className="text-gray-400 text-xs mb-2">Status</div>
              <div className={`text-lg font-medium ${poolState.is_initialized ? 'text-green-400' : 'text-yellow-400'}`}>
                {poolState.is_initialized ? '✓ Initialized' : '○ Not Initialized'}
              </div>
            </div>

            {/* Reserves */}
            <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
              <div className="text-gray-400 text-xs mb-2">Reserves</div>
              <div className="space-y-1">
                <div className="text-sm text-white">
                  {token0Symbol}: {parseFloat(poolState.reserves[0] || '0').toFixed(2)}
                </div>
                <div className="text-sm text-white">
                  {token1Symbol}: {parseFloat(poolState.reserves[1] || '0').toFixed(2)}
                </div>
              </div>
            </div>

            {/* Prices */}
            <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
              <div className="text-gray-400 text-xs mb-2">Prices</div>
              <div className="space-y-1">
                <div className="text-sm text-white">
                  Spot: {parseFloat(poolState.spot_price).toFixed(6)}
                </div>
                {poolState.oracle_rate && (
                  <>
                    <div className="text-sm text-white">
                      Oracle: {parseFloat(poolState.oracle_rate).toFixed(6)}
                    </div>
                    <div className={`text-sm ${parseFloat(calculateDeviation() || '0') > 1 ? 'text-yellow-400' : 'text-green-400'}`}>
                      Deviation: {calculateDeviation()}%
                    </div>
                  </>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400 text-center py-8">
            {loading ? 'Loading pool state...' : 'No pool data available'}
          </div>
        )}

        {/* Quick Actions */}
        {poolState && (
          <div className="mt-6 pt-6 border-t border-white/[0.05]">
            <div className="flex gap-3 flex-wrap">
              <button
                onClick={() => handleSyncRate()}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-lg text-sm transition-all"
              >
                Sync Oracle Rate
              </button>
              <button
                onClick={fetchPoolState}
                disabled={loading}
                className="px-4 py-2 bg-white/[0.05] hover:bg-white/[0.1] text-gray-300 rounded-lg text-sm transition-all"
              >
                Refresh Data
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Operations Tabs */}
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex gap-2 mb-6 overflow-x-auto">
          <button onClick={() => setActiveTab('info')} className={tabButtonClasses('info')}>
            Info
          </button>
          {poolState?.is_initialized ? (
            <>
              <button onClick={() => setActiveTab('swap')} className={tabButtonClasses('swap')}>
                Swap
              </button>
              <button onClick={() => setActiveTab('liquidity')} className={tabButtonClasses('liquidity')}>
                Add Liquidity
              </button>
            </>
          ) : (
            <button onClick={() => setActiveTab('initialize')} className={tabButtonClasses('initialize')}>
              Initialize Pool
            </button>
          )}
        </div>

        <div>
          {activeTab === 'info' && (
            <div className="space-y-4">
              <div className="text-gray-400 text-sm">
                <p className="mb-2"><strong className="text-white">Pool Address:</strong></p>
                <p className="font-mono text-xs break-all">{poolAddress}</p>
              </div>
              <div className="text-gray-400 text-sm">
                <p className="mb-2"><strong className="text-white">Token Addresses:</strong></p>
                <p className="font-mono text-xs break-all mb-1">{token0Symbol}: {token0Address}</p>
                <p className="font-mono text-xs break-all">{token1Symbol}: {token1Address}</p>
              </div>
              {rateProviderAddress && (
                <div className="text-gray-400 text-sm">
                  <p className="mb-2"><strong className="text-white">Rate Provider:</strong></p>
                  <p className="font-mono text-xs break-all">{rateProviderAddress}</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'swap' && poolState?.is_initialized && (
            <SwapForm
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              token0Symbol={token0Symbol}
              token1Symbol={token1Symbol}
              onSuccess={() => {
                fetchPoolState();
                setSuccess('Swap completed successfully!');
              }}
            />
          )}

          {activeTab === 'liquidity' && poolState?.is_initialized && (
            <AddLiquidityForm
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              token0Symbol={token0Symbol}
              token1Symbol={token1Symbol}
              onSuccess={() => {
                fetchPoolState();
                setSuccess('Liquidity added successfully!');
                onRefresh?.();
              }}
            />
          )}

          {activeTab === 'initialize' && !poolState?.is_initialized && (
            <InitializePoolForm
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              token0Symbol={token0Symbol}
              token1Symbol={token1Symbol}
              onSuccess={() => {
                fetchPoolState();
                setSuccess('Pool initialized successfully!');
                setActiveTab('info');
                onRefresh?.();
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}

