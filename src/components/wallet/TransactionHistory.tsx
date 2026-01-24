'use client';

import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import { ArrowUpRight, ArrowDownLeft, Clock, CheckCircle, XCircle, AlertCircle, ArrowUpDown } from 'lucide-react';
import { kryptonWeb3Api } from '@/lib/api';

interface Transaction {
  type: 'transfer_in' | 'transfer_out' | 'swap';
  timestamp: number;
  hash: string;
  // Transfer fields
  token?: string;
  amount?: number;
  from?: string;
  to?: string;
  from_username?: string;
  to_username?: string;
  // Swap fields
  token_in?: string;
  token_out?: string;
  amount_in?: number;
  amount_out?: number;
  pool?: string;
  // Common
  status?: string; // Derived or future use
  raw?: any;
}

interface TransactionHistoryProps {
  username: string;
  userWalletAddress: string;
  refresh?: boolean;
}

export interface TransactionHistoryRef {
  refresh: () => void;
}

const TransactionHistory = forwardRef<TransactionHistoryRef, TransactionHistoryProps>(
  ({ username, userWalletAddress, refresh }, ref) => {
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [totalCount, setTotalCount] = useState<number>(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [offset, setOffset] = useState(0);
    const [loadingMore, setLoadingMore] = useState(false);
    const LIMIT = 20;

    const fetchTransactions = async () => {
      try {
        setLoading(true);
        setError(null);
        // Reset offset on fresh fetch
        setOffset(0);
        const response = await kryptonWeb3Api.get(`/subgraph/transactions/${username}?limit=${LIMIT}&skip=0`);
        const data = response.data;
        if (data.error) {
          setError(data.error);
        } else {
          setTransactions(data.transactions || []);
          setTotalCount(data.count || 0);
          setOffset(LIMIT);
        }
      } catch (err) {
        console.error('Error fetching transactions:', err);
        setError('Failed to fetch transactions');
      } finally {
        setLoading(false);
      }
    };

    useImperativeHandle(ref, () => ({
      refresh: fetchTransactions
    }));

    useEffect(() => {
      fetchTransactions();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [username, refresh]);

    const loadMore = async () => {
      if (transactions.length >= totalCount) return;
      try {
        setLoadingMore(true);
        const response = await kryptonWeb3Api.get(`/subgraph/transactions/${username}?limit=${LIMIT}&skip=${offset}`);
        const data = response.data;
        if (data.error) {
          setError(data.error);
        } else {
          setTransactions(prev => [...prev, ...(data.transactions || [])]);
          setOffset(prev => prev + LIMIT);
        }
      } catch (err) {
        console.error('Error loading more transactions:', err);
        setError('Failed to load more transactions');
      } finally {
        setLoadingMore(false);
      }
    };

    const getStatusIcon = (tx: Transaction) => {
      return (
        <a
          href={`https://sepolia.etherscan.io/tx/${tx.hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-cyan-400 cursor-pointer transition-all duration-200 hover:scale-110 group"
          title="View on Etherscan"
        >
          <CheckCircle className="h-5 w-5 text-green-500 group-hover:drop-shadow-sm" />
        </a>
      );
    };

    const getTransactionTypeIcon = (type: string, large = false) => {
      if (type === 'swap') {
        return (
          <ArrowUpDown className={large ? 'h-5 w-5 text-cyan-400' : 'h-4 w-4 text-cyan-400'} style={{ transform: 'rotate(90deg)' }} />
        );
      }
      return type === 'transfer_in' ?
        <ArrowDownLeft className={large ? 'h-6 w-6 text-green-600' : 'h-5 w-5 text-green-600'} /> :
        <ArrowUpRight className={large ? 'h-6 w-6 text-red-600' : 'h-5 w-5 text-red-600'} />;
    };

    const shortenAddress = (address?: string) => {
      if (!address) return 'Unknown';
      return `${address.slice(0, 6)}...${address.slice(-4)}`;
    };

    const formatToken = (symbol?: string) => {
      if (!symbol) return '';
      if (symbol.startsWith('k') && symbol.length > 1) {
        return symbol.substring(1);
      }
      return symbol;
    };

    const formatAmount = (val?: number) => {
      if (val === undefined || val === null) return '0.00';
      return val.toFixed(2);
    };

    const formatDateOnly = (timestamp: number) => {
      if (!timestamp) return '';
      try {
        const date = new Date(timestamp * 1000); // Subgraph returns seconds
        return date.toLocaleDateString('en-US', {
          month: 'short',
          day: 'numeric'
        });
      } catch {
        return '';
      }
    };

    const formatTimeOnly = (timestamp: number) => {
      if (!timestamp) return '';
      try {
        const date = new Date(timestamp * 1000);
        return date.toLocaleTimeString('en-US', {
          hour: '2-digit',
          minute: '2-digit'
        });
      } catch {
        return '';
      }
    };

    if (loading) {
      return (
        <div className="flex items-center justify-center py-4">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-cyan-400"></div>
        </div>
      );
    }

    if (error) {
      return (
        <div className="text-center py-4 text-red-400 text-xs flex items-center justify-center gap-2">
          <AlertCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      );
    }

    if (transactions.length === 0) {
      return (
        <div className="text-center py-4 text-gray-400 text-xs flex items-center justify-center gap-2">
          <Clock className="h-4 w-4" />
          <span>No transactions yet</span>
        </div>
      );
    }

    return (
      <div className="flex flex-col">
        <div className="rounded-t-none rounded-b-xl border border-white/10 bg-black/30">
          {transactions.map((tx, idx) => {
            let titleText = '';
            let subText = '';
            let amountDisplay = '';

            if (tx.type === 'swap') {
              const inToken = formatToken(tx.token_in);
              const outToken = formatToken(tx.token_out);
              titleText = `Swap ${inToken} to ${outToken}`;
              amountDisplay = `${formatAmount(tx.amount_in)} ${inToken} -> ${formatAmount(tx.amount_out)} ${outToken}`;
              subText = 'Pool Swap';
            } else {
              const token = formatToken(tx.token);
              const amount = formatAmount(tx.amount);
              amountDisplay = `${amount} ${token}`;

              if (tx.type === 'transfer_in') {
                titleText = 'Received';
                const name = tx.from_username ? `@${tx.from_username}` : 'Unknown';
                subText = name;
              } else {
                titleText = 'Sent';
                const name = tx.to_username ? `@${tx.to_username}` : 'Unknown';
                subText = name;
              }
            }

            return (
              <div
                key={`${tx.hash}-${idx}`}
                className={`px-3 py-2 flex items-start justify-between min-w-0 ${idx !== transactions.length - 1 ? 'border-b border-white/10' : ''}`}
              >
                {/* First column: Icon, Amount/Title, From/To */}
                <div className="flex items-start min-w-0 flex-1 overflow-hidden">
                  <div className="flex items-center justify-center w-8 h-8 mr-2 flex-shrink-0">
                    {getTransactionTypeIcon(tx.type, false)}
                  </div>
                  <div className="flex flex-col min-w-0 flex-1 overflow-hidden justify-center">
                    <span className="text-white font-semibold text-sm md:text-base tracking-tight whitespace-nowrap truncate" title={amountDisplay}>
                      {amountDisplay}
                    </span>
                    <span className="text-zinc-400 text-xs mt-0.5 whitespace-nowrap overflow-hidden text-ellipsis">
                      <span className="text-zinc-400 inline-flex items-center gap-1">
                        {tx.type === 'transfer_in' ? 'From: ' : tx.type === 'transfer_out' ? 'To: ' : ''}
                        {tx.type === 'swap' ? (
                          'Pool Swap'
                        ) : (
                          <span
                              className={
                                (tx.type === 'transfer_in' && tx.from_username) ||
                                  (tx.type === 'transfer_out' && tx.to_username)
                                  ? "text-cyan-400 font-medium"
                                  : "text-zinc-300"
                              }
                            >
                              {tx.type === 'transfer_in'
                                ? (tx.from_username ? `@${tx.from_username}` : 'Unknown')
                                : (tx.to_username ? `@${tx.to_username}` : 'Unknown')
                              }
                            </span>
                        )}
                      </span>
                    </span>
                  </div>
                </div>
                {/* Second column: Timestamp */}
                <div className="flex flex-col text-zinc-500 text-[10px] md:text-xs text-right flex-shrink-0 ml-2 md:ml-4 justify-center" style={{ minWidth: '60px' }}>
                  <span className="whitespace-nowrap">{formatDateOnly(tx.timestamp)}</span>
                  <span className="whitespace-nowrap">{formatTimeOnly(tx.timestamp)}</span>
                </div>
                {/* Status icon */}
                <div className="flex items-center justify-center w-5 h-5 ml-2 flex-shrink-0 self-center">
                  {getStatusIcon(tx)}
                </div>
              </div>
            );
          })}
        </div>

        {transactions.length < totalCount && (
          <div className="flex justify-center mt-4">
            <button
              onClick={loadMore}
              disabled={loadingMore}
              className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 hover:bg-zinc-700 disabled:opacity-60 text-sm"
            >
              {loadingMore ? 'Loading...' : 'Load more'}
            </button>
          </div>
        )}
      </div>
    );
  }
);

TransactionHistory.displayName = 'TransactionHistory';

export default TransactionHistory;