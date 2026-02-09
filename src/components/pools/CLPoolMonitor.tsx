'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { nettingPoolsApi, PoolState } from '@/lib/nettingPoolsApi';
import { kryptonWeb3Api } from '@/lib/api';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';
import { useWebSocket } from '@/hooks/useWebSocket';
import { isTerminalState, CircleTransactionState } from '@/lib/circleStates';
import SwapForm from './SwapForm';
import InitializePoolForm from './InitializePoolForm';
import AddLiquidityForm from './AddLiquidityForm';
import PriceChart from './PriceChart';
import BalancesChart from './BalancesChart';
import TransactionHistory from './TransactionHistory';

interface CLPoolMonitorProps {
  poolAddress: string;
  token0Symbol: string;
  token1Symbol: string;
  token0Address: string;
  token1Address: string;
  rateProviderAddress: string;
  onRefresh?: () => void;
}

// Pending transaction tracking
interface PendingTransaction {
  id: string;
  type: 'syncRate' | 'swap' | 'liquidity';
  status: string;
  timestamp: number;
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
  const { username, walletAddress } = useNettingPoolsAuth();
  const [poolState, setPoolState] = useState<PoolState | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeTab, setActiveTab] = useState<'history' | 'swap' | 'liquidity' | 'initialize'>('history');
  const [chartsRefreshKey, setChartsRefreshKey] = useState(0);

  // Pending transactions - event-based, no polling
  const [pendingTransactions, setPendingTransactions] = useState<Map<string, PendingTransaction>>(new Map());
  const processedEventsRef = useRef<Set<string>>(new Set());

  // Track the current pool address to prevent stale data
  const currentPoolRef = useRef(poolAddress);

  // WebSocket URL for receiving transaction events
  const wsUrl = walletAddress
    ? `${process.env.NEXT_PUBLIC_KRYPTON_WEB3_WS_URL || 'ws://localhost:8001'}/ws/${walletAddress}`
    : '';

  // Handle WebSocket messages for transaction status updates
  const handleWebSocketMessage = useCallback((message: any) => {
    // Handle transaction events
    if (message.type === 'transaction_confirmed' || message.type === 'transaction_failed') {
      const transactionId = message.data?.transaction_id || message.transaction_id;

      if (!transactionId) return;

      // Prevent duplicate processing
      const eventKey = `${transactionId}-${message.type}`;
      if (processedEventsRef.current.has(eventKey)) return;
      processedEventsRef.current.add(eventKey);

      // Clear after 60 seconds to prevent memory leak
      setTimeout(() => {
        processedEventsRef.current.delete(eventKey);
      }, 60000);

      // Update pending transaction status
      setPendingTransactions(prev => {
        const updated = new Map(prev);
        const existing = updated.get(transactionId);
        if (existing) {
          if (message.type === 'transaction_confirmed') {
            updated.delete(transactionId); // Remove from pending
            setSuccess(`Transaction confirmed: ${existing.type}`);
            // Refresh pool state after confirmation
            setTimeout(() => fetchPoolState(true), 2000);
          } else if (message.type === 'transaction_failed') {
            updated.delete(transactionId);
            setError(`Transaction failed: ${existing.type}`);
          }
        }
        return updated;
      });
    }
  }, []);

  // Use WebSocket for transaction events
  const { connectionStatus } = useWebSocket(wsUrl, {
    onMessage: handleWebSocketMessage,
    onOpen: () => console.log('Pool Monitor WebSocket connected'),
    onClose: () => console.log('Pool Monitor WebSocket disconnected'),
  });

  // Reset state when pool changes to prevent stale data
  useEffect(() => {
    if (currentPoolRef.current !== poolAddress) {
      // Pool changed - clear state immediately
      setPoolState(null);
      setError('');
      setSuccess('');
      setPendingTransactions(new Map());
      currentPoolRef.current = poolAddress;
    }
    fetchPoolState();
  }, [poolAddress]);

  const fetchPoolState = async (forceRefresh = false) => {
    // Capture the poolAddress at call time to check for stale responses
    const requestedPool = poolAddress;

    setLoading(true);
    setError('');

    // Don't show partial/incorrect data while loading
    // Keep previous state or null until full data is ready
    if (!poolState) {
      setPoolState(null);
    }

    try {
      // Fetch complete pool state from RPC
      // This ensures we always have accurate, complete data
      const fullState = await nettingPoolsApi.getPoolState(requestedPool);

      // Only update state if we're still viewing the same pool
      if (currentPoolRef.current === requestedPool) {
        setPoolState(fullState);
      }
    } catch (err: any) {
      if (currentPoolRef.current === requestedPool) {
        setError('Failed to fetch pool state: ' + (err.message || 'Unknown error'));
        console.error('Error fetching pool state:', err);
        setPoolState(null);
      }
    } finally {
      if (currentPoolRef.current === requestedPool) {
        setLoading(false);
      }
    }
  };

  const handleSyncRate = async (manualRate?: number) => {
    if (!username) {
      setError('Please log in to sync rate');
      return;
    }

    setError('');
    setSuccess('');
    setLoading(true);
    try {
      const result = await nettingPoolsApi.syncRate({
        token_symbol: token1Symbol,
        manual_rate: manualRate,
        username: username,
      });

      // Add to pending transactions - WebSocket events will handle completion
      const txId = result.transaction_id;
      setPendingTransactions(prev => {
        const updated = new Map(prev);
        updated.set(txId, {
          id: txId,
          type: 'syncRate',
          status: CircleTransactionState.SUBMITTED,
          timestamp: Date.now(),
        });
        return updated;
      });

      setSuccess(`Rate sync submitted! Waiting for confirmation...`);
    } catch (err: any) {
      setError('Failed to sync rate: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshCharts = () => {
    setChartsRefreshKey((prev) => prev + 1);
  };

  const formatNumber = (value: string | number | null | undefined, decimals = 2) => {
    if (value === null || value === undefined) return '0';
    const num = typeof value === 'string' ? parseFloat(value) : value;
    if (isNaN(num)) return '0';
    return num.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  };

  const formatTime = (timestamp: number | null | undefined) => {
    if (!timestamp) return '';
    const date = new Date(timestamp * 1000);
    return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  };

  const tabButtonClasses = (tab: string) => {
    const baseClasses = 'px-4 py-2 rounded-lg text-sm font-medium transition-all';
    if (activeTab === tab) {
      return `${baseClasses} bg-blue-600 text-white`;
    }
    return `${baseClasses} bg-white/[0.05] text-gray-400 hover:text-white hover:bg-white/[0.1]`;
  };

  // Check if any pending transactions exist
  const hasPendingTxs = pendingTransactions.size > 0;

  return (
    <div className="space-y-6">
      {/* Pool Header Card */}
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <h3 className="text-xl font-semibold text-white">
              {token0Symbol}/{token1Symbol}
            </h3>
            {poolState?.pool_parameters && (
              <span className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-400 rounded-full">
                {poolState.pool_parameters.pool_type === 'Gyro2CLP' ? 'Auto' : 'Stable'}
              </span>
            )}
            {connectionStatus === 'connected' && (
              <span className="px-2 py-0.5 text-xs bg-green-500/20 text-green-400 rounded-full flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-400 rounded-full animate-pulse" />
                Live
              </span>
            )}
          </div>
          <button
            onClick={() => fetchPoolState(true)}
            disabled={loading}
            className="p-2 hover:bg-white/[0.05] rounded-lg transition-all disabled:opacity-50"
          >
            <svg className={`w-5 h-5 text-gray-400 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
          </button>
        </div>

        <p className="text-gray-500 text-sm">
          {poolState?.pool_parameters?.pool_type || 'Gyro2CLP'} Pool
        </p>

        {error && (
          <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="mt-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
            {success}
          </div>
        )}

        {hasPendingTxs && (
          <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-400 text-sm">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              <span className="inline-flex items-center gap-1">
                {pendingTransactions.size} transaction(s) pending
                <span className="inline-flex">
                  <span className="animate-[pulse_1.5s_ease-in-out_infinite]">.</span>
                  <span className="animate-[pulse_1.5s_ease-in-out_0.2s_infinite]">.</span>
                  <span className="animate-[pulse_1.5s_ease-in-out_0.4s_infinite]">.</span>
                </span>
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Main Stats Grid */}
      {loading && !poolState ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4 animate-pulse">
              <div className="h-4 bg-white/[0.05] rounded w-1/2 mb-3"></div>
              <div className="space-y-2">
                <div className="h-6 bg-white/[0.05] rounded"></div>
                <div className="h-6 bg-white/[0.05] rounded"></div>
              </div>
            </div>
          ))}
        </div>
      ) : poolState ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Pool Liquidity Card */}
          <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
            <div className="text-gray-400 text-xs mb-3 font-medium">Pool Liquidity</div>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">{token0Symbol}</span>
                <span className="text-blue-400 font-mono text-lg">
                  {/* Reserves are already in token amounts, no conversion needed */}
                  {formatNumber(poolState.reserves[0], 0)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400 text-sm">{token1Symbol}</span>
                <span className="text-green-400 font-mono text-lg">
                  {/* Reserves are already in token amounts, no conversion needed */}
                  {formatNumber(poolState.reserves[1], 0)}
                </span>
              </div>
              <div className="pt-2 border-t border-white/[0.05]">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-xs">Value (scaled)</span>
                  <span className="text-white font-mono">{formatNumber(poolState.total_value, 0)}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Reserve (Wallet) Card */}
          <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
            <div className="text-gray-400 text-xs mb-3 font-medium">Reserve (Wallet)</div>
            <div className="space-y-2">
              {poolState.reserve_balances ? (
                <>
                  {poolState.reserve_balances.map((balance, idx) => (
                    <div key={idx} className="flex justify-between items-center">
                      <span className="text-gray-400 text-sm">{balance.symbol}</span>
                      <span className="text-white font-mono text-lg">{formatNumber(balance.balance, 0)}</span>
                    </div>
                  ))}
                </>
              ) : (
                <>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-sm">{token0Symbol}</span>
                    <span className="text-white font-mono text-lg">-</span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-sm">{token1Symbol}</span>
                    <span className="text-white font-mono text-lg">-</span>
                  </div>
                </>
              )}
              <div className="pt-2 border-t border-white/[0.05]">
                <div className="flex justify-between items-center">
                  <span className="text-gray-500 text-xs">For Rebalancing</span>
                  <span className="text-gray-500 text-xs">{poolState.rebalance_status?.strategy || '50/50'} strategy</span>
                </div>
              </div>
            </div>
          </div>

          {/* Pool Rebalance Card */}
          <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
            <div className="text-gray-400 text-xs mb-3 font-medium">Pool Rebalance</div>
            {poolState.rebalance_status ? (
              <div className="space-y-2">
                <div className="text-xs text-gray-500">
                  {token0Symbol} Thresholds: ≤{(poolState.rebalance_status.threshold_lower * 100).toFixed(0)}% or ≥{(poolState.rebalance_status.threshold_upper * 100).toFixed(0)}%
                </div>
                <div className="text-xs text-gray-500">
                  {token1Symbol} Thresholds: ≤{(poolState.rebalance_status.threshold_lower * 100).toFixed(0)}% or ≥{(poolState.rebalance_status.threshold_upper * 100).toFixed(0)}%
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">{token0Symbol}</span>
                  <span className={`font-mono ${poolState.rebalance_status.token0_percent >= 80 && poolState.rebalance_status.token0_percent <= 120 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {poolState.rebalance_status.token0_percent.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">{token1Symbol}</span>
                  <span className={`font-mono ${poolState.rebalance_status.token1_percent >= 80 && poolState.rebalance_status.token1_percent <= 120 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {poolState.rebalance_status.token1_percent.toFixed(1)}%
                  </span>
                </div>
                <button className={`w-full mt-2 py-2 rounded-lg text-sm font-medium ${poolState.rebalance_status.is_balanced ? 'bg-white/[0.05] text-gray-400' : 'bg-yellow-500/20 text-yellow-400'}`}>
                  {poolState.rebalance_status.is_balanced ? '✓ Pool Balanced' : '⚠ Needs Rebalance'}
                </button>
              </div>
            ) : (
              <div className="text-gray-500 text-sm">No rebalance data</div>
            )}
          </div>

          {/* Pool Parameters Card */}
          <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
            <div className="text-gray-400 text-xs mb-3 font-medium">Pool Parameters</div>
            {poolState.pool_parameters ? (
              <div className="space-y-3">
                {poolState.pool_parameters.range_lower && poolState.pool_parameters.range_upper && (
                  <div className="flex justify-between items-center">
                    <span className="text-gray-400 text-sm">Range</span>
                    <span className="text-white font-mono">
                      {poolState.pool_parameters.range_lower.toFixed(4)} - {poolState.pool_parameters.range_upper.toFixed(4)}
                    </span>
                  </div>
                )}
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">Swap Fee</span>
                  <span className="text-white font-mono">{(poolState.pool_parameters.swap_fee * 100).toFixed(1)}%</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">Deviation</span>
                  <span className={`font-mono ${poolState.oracle_info?.deviation_percent && Math.abs(poolState.oracle_info.deviation_percent) > 1 ? 'text-yellow-400' : 'text-green-400'}`}>
                    {poolState.oracle_info?.deviation_percent?.toFixed(2) || '0.00'}%
                  </span>
                </div>
              </div>
            ) : (
              <div className="text-gray-500 text-sm">No parameters data</div>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Skeleton Cards */}
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-xl p-4 animate-pulse">
              <div className="h-4 bg-white/[0.08] rounded w-24 mb-4" />
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <div className="h-4 bg-white/[0.05] rounded w-16" />
                  <div className="h-6 bg-white/[0.08] rounded w-24" />
                </div>
                <div className="flex justify-between items-center">
                  <div className="h-4 bg-white/[0.05] rounded w-16" />
                  <div className="h-6 bg-white/[0.08] rounded w-24" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Price Tracking Section */}
      {poolState && (
        <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h4 className="text-lg font-medium text-white">Price Tracking</h4>
            <div className="flex gap-2">
              <button className="px-3 py-1.5 bg-orange-500/20 hover:bg-orange-500/30 text-orange-400 rounded-lg text-sm font-medium transition-all">
                ⚙ Fix Bounds
              </button>
              <button
                onClick={() => handleSyncRate()}
                disabled={loading || !username}
                className="px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
              >
                🔄 Sync Oracle
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Oracle Rate */}
            <div>
              <div className="text-gray-400 text-xs mb-1">Oracle Rate (Cached)</div>
              {poolState.oracle_rate && parseFloat(poolState.oracle_rate) > 0 ? (
                <div className="flex items-baseline gap-2">
                  <span className="text-2xl font-mono text-green-400">
                    ${formatNumber(poolState.oracle_rate, 6)}
                  </span>
                  <span className="text-gray-500 text-xs">
                    {formatTime(poolState.oracle_info?.timestamp)}
                  </span>
                </div>
              ) : (
                <div className="text-gray-500 text-sm">Loading...</div>
              )}
              {poolState.oracle_info?.live_rate && (
                <div className="mt-2">
                  <span className="text-gray-500 text-xs">Live KryptonFXOracle ({poolState.token0_symbol}/{token1Symbol.replace('k', '')})</span>
                  <div className="flex items-center gap-2">
                    <span className="text-blue-400 font-mono">${formatNumber(poolState.oracle_info.live_rate, 6)}</span>
                    {poolState.oracle_info.deviation_percent !== null && poolState.oracle_info.deviation_percent !== undefined && (
                      <span className={`text-xs ${poolState.oracle_info.deviation_percent > 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {poolState.oracle_info.deviation_percent > 0 ? '▲' : '▼'} {Math.abs(poolState.oracle_info.deviation_percent).toFixed(2)}%
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Pool Price */}
            <div>
              <div className="text-gray-400 text-xs mb-1">Pool Price</div>
              <div className="text-2xl font-mono text-blue-400">
                ${formatNumber(poolState.spot_price, 6)}
              </div>
              {poolState.oracle_info?.deviation_percent !== null && poolState.oracle_info?.deviation_percent !== undefined && (
                <div className="mt-2">
                  <span className={`text-sm ${Math.abs(poolState.oracle_info?.deviation_percent ?? 0) < 0.5 ? 'text-green-400' : 'text-yellow-400'}`}>
                    {(poolState.oracle_info?.deviation_percent ?? 0) > 0 ? '+' : ''}{(poolState.oracle_info?.deviation_percent ?? 0).toFixed(2)}%
                  </span>
                  <span className="text-gray-500 text-xs ml-2">vs Oracle</span>
                </div>
              )}
            </div>

            {/* Pool Health */}
            <div>
              <div className="text-gray-400 text-xs mb-1">Pool Health</div>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-400 text-sm">Status</span>
                  <span className={`font-medium ${poolState.is_initialized ? 'text-green-400' : 'text-yellow-400'}`}>
                    {poolState.is_initialized ? 'In Range' : 'Not Initialized'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400 text-sm">Fee APR</span>
                  <span className="text-white font-mono">
                    {((poolState.pool_parameters?.swap_fee || 0.001) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              <div
                className={`w-full mt-3 py-2 rounded-lg text-sm font-medium text-center ${poolState.rate_synced ? 'bg-green-500/20 text-green-400' : 'bg-yellow-500/20 text-yellow-400'}`}
              >
                {poolState.rate_synced ? '✓ Rate Synced' : '⚠ Rate Out of Sync'}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Charts Section - Token Balances History */}
      <div className="relative">
        <button
          onClick={handleRefreshCharts}
          className="absolute top-4 right-4 z-10 px-3 py-1 bg-white/[0.05] hover:bg-white/[0.1] text-gray-400 hover:text-white rounded-lg text-xs transition-all flex items-center gap-1"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          Refresh
        </button>
        <BalancesChart
          key={`balances-${poolAddress}-${chartsRefreshKey}`}
          poolAddress={poolAddress}
          token0Symbol={token0Symbol}
          token1Symbol={token1Symbol}
          token0Address={token0Address}
          token1Address={token1Address}
          height={280}
          limit={100}
        />
      </div>

      {/* Charts Section - Pool Price History with Oracle Rate */}
      <PriceChart
        key={`price-${poolAddress}-${chartsRefreshKey}`}
        poolAddress={poolAddress}
        tokenPair={`${token0Symbol}/${token1Symbol}`}
        height={280}
        limit={100}
      />

      {/* Operations Tabs */}
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <div className="flex gap-2 mb-6 overflow-x-auto">
          <button onClick={() => setActiveTab('history')} className={tabButtonClasses('history')}>
            Transaction History
          </button>
          {poolState?.is_initialized ? (
            <>
              <button onClick={() => setActiveTab('initialize')} className={tabButtonClasses('initialize')}>
                Initialize Pool
              </button>
              <button onClick={() => setActiveTab('liquidity')} className={tabButtonClasses('liquidity')}>
                Add Liquidity
              </button>
              <button onClick={() => setActiveTab('swap')} className={tabButtonClasses('swap')}>
                Swap
              </button>
            </>
          ) : (
            <button onClick={() => setActiveTab('initialize')} className={tabButtonClasses('initialize')}>
              Initialize Pool
            </button>
          )}
        </div>

        <div>
          {activeTab === 'history' && (
            <TransactionHistory
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              title=""
              maxShow={15}
              showFilters={true}
            />
          )}

          {activeTab === 'swap' && poolState?.is_initialized && (
            <SwapForm
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              token0Symbol={token0Symbol}
              token1Symbol={token1Symbol}
              onSuccess={() => {
                fetchPoolState(true);
                setSuccess('Swap completed successfully!');
                handleRefreshCharts();
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
                fetchPoolState(true);
                setSuccess('Liquidity added successfully!');
                handleRefreshCharts();
                onRefresh?.();
              }}
            />
          )}

          {activeTab === 'initialize' && (
            <InitializePoolForm
              poolAddress={poolAddress}
              token0Address={token0Address}
              token1Address={token1Address}
              token0Symbol={token0Symbol}
              token1Symbol={token1Symbol}
              onSuccess={() => {
                fetchPoolState(true);
                setSuccess('Pool initialized successfully!');
                handleRefreshCharts();
                onRefresh?.();
              }}
            />
          )}
        </div>
      </div>
    </div>
  );
}
