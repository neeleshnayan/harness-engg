'use client';

import { useState, useEffect } from 'react';
import { subgraphApi, PoolRateHistoryEntry, PoolBalanceHistoryEntry } from '@/lib/subgraphApi';

export interface PoolTransaction {
  id: string;
  type: 'rate_update' | 'balance_change';
  timestamp: number;
  blockNumber: string;
  details: {
    tokenPair?: string;
    rate?: number | null;
    balances?: number[];
    tokens?: string[];
  };
}

interface TransactionHistoryProps {
  poolAddress: string;
  title?: string;
  maxShow?: number;
  showFilters?: boolean;
}

export default function TransactionHistory({
  poolAddress,
  title = 'Pool Activity',
  maxShow = 20,
  showFilters = true,
}: TransactionHistoryProps) {
  const [transactions, setTransactions] = useState<PoolTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState<'all' | 'rate_update' | 'balance_change'>('all');
  const [showAll, setShowAll] = useState(false);

  useEffect(() => {
    if (!poolAddress) return;

    const fetchTransactions = async () => {
      setLoading(true);
      setError('');

      try {
        // Fetch both rate history and balance history
        const [rateResponse, balanceResponse] = await Promise.all([
          subgraphApi.getPoolRateHistory(poolAddress, maxShow * 2, 'desc'),
          subgraphApi.getPoolBalanceHistory(poolAddress, maxShow * 2, 'desc'),
        ]);

        // Convert rate history to transactions
        const rateTransactions: PoolTransaction[] = rateResponse.rates.map(
          (entry: PoolRateHistoryEntry) => ({
            id: entry.id,
            type: 'rate_update' as const,
            timestamp: parseInt(entry.blockTimestamp) * 1000,
            blockNumber: entry.blockNumber,
            details: {
              tokenPair: entry.tokenPair,
              rate: entry.rate,
            },
          })
        );

        // Convert balance history to transactions
        const balanceTransactions: PoolTransaction[] = balanceResponse.balances.map(
          (entry: PoolBalanceHistoryEntry) => ({
            id: entry.id,
            type: 'balance_change' as const,
            timestamp: parseInt(entry.blockTimestamp) * 1000,
            blockNumber: entry.blockNumber,
            details: {
              balances: entry.balances,
              tokens: entry.tokens,
            },
          })
        );

        // Merge and sort by timestamp
        const allTransactions = [...rateTransactions, ...balanceTransactions].sort(
          (a, b) => b.timestamp - a.timestamp
        );

        setTransactions(allTransactions);
      } catch (err: any) {
        console.error('Error fetching transaction history:', err);
        setError('Failed to load transaction history');
      } finally {
        setLoading(false);
      }
    };

    fetchTransactions();
  }, [poolAddress, maxShow]);

  const filteredTransactions = transactions.filter(
    (tx) => filter === 'all' || tx.type === filter
  );

  const displayedTransactions = showAll
    ? filteredTransactions
    : filteredTransactions.slice(0, maxShow);

  if (loading) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <h4 className="text-lg font-medium text-white mb-4">{title}</h4>
        <div className="text-gray-400 text-sm text-center py-8">Loading transactions...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
        <h4 className="text-lg font-medium text-white mb-4">{title}</h4>
        <div className="text-red-400 text-sm text-center py-8">{error}</div>
      </div>
    );
  }

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center justify-between mb-4">
        <h4 className="text-lg font-medium text-white">{title}</h4>
        <span className="text-xs bg-white/[0.05] text-gray-400 px-2 py-1 rounded-lg">
          {filteredTransactions.length} event{filteredTransactions.length !== 1 ? 's' : ''}
        </span>
      </div>

      {showFilters && (
        <div className="flex gap-2 mb-4">
          {['all', 'rate_update', 'balance_change'].map((filterType) => (
            <button
              key={filterType}
              onClick={() => setFilter(filterType as typeof filter)}
              className={`px-3 py-1.5 text-xs rounded-lg transition-all ${
                filter === filterType
                  ? 'bg-blue-600 text-white'
                  : 'bg-white/[0.05] text-gray-400 hover:bg-white/[0.1]'
              }`}
            >
              {filterType === 'all' ? 'All' : filterType === 'rate_update' ? 'Rate Updates' : 'Balance Changes'}
            </button>
          ))}
        </div>
      )}

      {displayedTransactions.length === 0 ? (
        <div className="text-center py-8 text-gray-400">
          <p className="text-sm">No transactions found</p>
          <p className="text-xs mt-2">Pool activity will appear here</p>
        </div>
      ) : (
        <div className="space-y-2">
          {displayedTransactions.map((tx) => (
            <div
              key={tx.id}
              className="flex items-center justify-between p-3 bg-white/[0.02] border border-white/[0.03] rounded-xl hover:bg-white/[0.04] transition-all"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span
                    className={`text-xs font-medium px-2 py-0.5 rounded ${
                      tx.type === 'rate_update'
                        ? 'bg-purple-500/20 text-purple-300'
                        : 'bg-green-500/20 text-green-300'
                    }`}
                  >
                    {tx.type === 'rate_update' ? '📊 Rate' : '💧 Balance'}
                  </span>
                  {tx.details.tokenPair && (
                    <span className="text-sm text-gray-300">{tx.details.tokenPair}</span>
                  )}
                  {tx.details.rate !== null && tx.details.rate !== undefined && (
                    <span className="text-sm text-blue-400">
                      {tx.details.rate.toFixed(6)}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>Block #{tx.blockNumber}</span>
                  <span>{new Date(tx.timestamp).toLocaleString()}</span>
                </div>
              </div>
              {tx.details.balances && (
                <div className="text-right">
                  <div className="text-xs text-gray-400">
                    {tx.details.balances.map((b, i) => (
                      <div key={i}>{b.toFixed(2)}</div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {filteredTransactions.length > maxShow && (
        <div className="mt-4 text-center">
          <button
            onClick={() => setShowAll(!showAll)}
            className="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors"
          >
            {showAll
              ? 'Show Less'
              : `Show All (${filteredTransactions.length - maxShow} more)`}
          </button>
        </div>
      )}
    </div>
  );
}

