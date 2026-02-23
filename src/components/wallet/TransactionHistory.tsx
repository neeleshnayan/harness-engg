'use client';

import React, { useState, useEffect, useImperativeHandle, forwardRef, useRef, useCallback } from 'react';
import { Clock, AlertCircle, ArrowRightLeft } from 'lucide-react';
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
  status?: string;
  raw?: any;
}

interface TransactionHistoryProps {
  username: string;
  userWalletAddress: string;
  refreshKey?: number;
  scrollRoot?: React.RefObject<HTMLDivElement | null>;
  /** Pre-fetched first page — skips the initial network call when provided. */
  initialData?: {
    transactions: Transaction[];
    count: number;
    has_more: boolean;
  };
}

export interface TransactionHistoryRef {
  refresh: () => void;
}

const PAGE_SIZE = 10;
const MAX_ITEMS = 50;

const TransactionHistory = forwardRef<TransactionHistoryRef, TransactionHistoryProps>(
  ({ username, userWalletAddress, refreshKey, scrollRoot, initialData }, ref) => {
    const txDebugEnabled =
      process.env.NEXT_PUBLIC_TX_DEBUG === "1" ||
      (typeof window !== "undefined" && window.localStorage.getItem("krypton_tx_debug") === "1");
    const txDebug = useCallback((event: string, payload?: Record<string, unknown>) => {
      if (!txDebugEnabled) return;
      // eslint-disable-next-line no-console
      console.log(`[TX_DEBUG] TransactionHistory:${event}`, payload || {});
    }, [txDebugEnabled]);

    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [totalCount, setTotalCount] = useState<number>(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [hasMore, setHasMore] = useState(true);
    const offsetRef = useRef(0);
    const sentinelRef = useRef<HTMLDivElement>(null);
    // Track whether we have already consumed the one-shot initialData
    const initialDataUsedRef = useRef(false);

    const fetchTransactions = useCallback(async () => {
      try {
        setLoading(true);
        setError(null);
        offsetRef.current = 0;
        const response = await kryptonWeb3Api.get(`/subgraph/transactions/${username}?limit=${PAGE_SIZE}&skip=0`);
        const data = response.data;
        if (data.error) {
          setError(data.error);
        } else {
          const txs = data.transactions || [];
          txDebug("fetch_page", {
            username,
            page: 0,
            count: txs.length,
            usdc_count: txs.filter((t: Transaction) => t.token === "USDC").length,
            hashes: txs.map((t: Transaction) => t.hash),
          });
          setTransactions(txs);
          setTotalCount(data.count || 0);
          offsetRef.current = txs.length;
          // Use has_more from API, fallback to checking tx array size against MAX_ITEMS
          setHasMore(data.has_more ?? (txs.length < Math.min(data.count || 0, MAX_ITEMS)));
        }
      } catch (err) {
        txDebug("fetch_error", { username, page: 0 });
        console.error('Error fetching transactions:', err);
        setError('Failed to fetch transactions');
      } finally {
        setLoading(false);
      }
    }, [username, txDebug]);

    useImperativeHandle(ref, () => ({
      refresh: fetchTransactions
    }), [fetchTransactions]);

    useEffect(() => {
      // On first mount: use the pre-fetched initialData to avoid a duplicate network
      // call. Once consumed, any subsequent refreshKey change triggers a real fetch.
      if (initialData && !initialDataUsedRef.current) {
        initialDataUsedRef.current = true;
        const txs = initialData.transactions || [];
        setTransactions(txs);
        setTotalCount(initialData.count || 0);
        offsetRef.current = txs.length;
        setHasMore(initialData.has_more ?? txs.length < Math.min(initialData.count || 0, MAX_ITEMS));
        setLoading(false);
        return;
      }
      fetchTransactions();
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [fetchTransactions, refreshKey]);

    const loadMore = useCallback(async () => {
      if (loadingMore || !hasMore) return;
      const currentOffset = offsetRef.current;
      if (currentOffset >= MAX_ITEMS) {
        setHasMore(false);
        return;
      }
      try {
        setLoadingMore(true);
        const response = await kryptonWeb3Api.get(`/subgraph/transactions/${username}?limit=${PAGE_SIZE}&skip=${currentOffset}`);
        const data = response.data;
        if (data.error) {
          setError(data.error);
        } else {
          const newTxs = data.transactions || [];
          txDebug("fetch_page", {
            username,
            page: Math.floor(currentOffset / PAGE_SIZE),
            count: newTxs.length,
            usdc_count: newTxs.filter((t: Transaction) => t.token === "USDC").length,
            hashes: newTxs.map((t: Transaction) => t.hash),
          });
          setTransactions(prev => {
            const combined = [...prev, ...newTxs];
            return combined.slice(0, MAX_ITEMS);
          });
          offsetRef.current = currentOffset + newTxs.length;
          // Use has_more from API, falling back to basic checks
          setHasMore(data.has_more ?? (newTxs.length === PAGE_SIZE && (currentOffset + newTxs.length) < Math.min(data.count || totalCount, MAX_ITEMS)));
        }
      } catch (err) {
        txDebug("fetch_error", { username, page: Math.floor(currentOffset / PAGE_SIZE) });
        console.error('Error loading more transactions:', err);
      } finally {
        setLoadingMore(false);
      }
    }, [loadingMore, hasMore, username, totalCount, txDebug]);

    // IntersectionObserver for infinite scroll
    useEffect(() => {
      const sentinel = sentinelRef.current;
      if (!sentinel) return;

      const observer = new IntersectionObserver(
        (entries) => {
          if (entries[0].isIntersecting && hasMore && !loadingMore && !loading) {
            loadMore();
          }
        },
        { root: scrollRoot?.current || null, rootMargin: '100px' }
      );

      observer.observe(sentinel);
      return () => observer.disconnect();
    }, [hasMore, loadingMore, loading, loadMore]);

    const getStatusIcon = (tx: Transaction) => {
      const isFailed = tx.status === 'failed';
      const iconSrc = isFailed ? "/check-circle-failed.svg" : "/check-circle-succeeded.svg";

      return (
        <a
          href={`https://sepolia.etherscan.io/tx/${tx.hash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="cursor-pointer transition-all duration-200 hover:scale-110 group"
          title="View on Etherscan"
        >
          <img src={iconSrc} alt={isFailed ? "Failed" : "Succeeded"} className="w-6 h-6" />
        </a>
      );
    };

    const getTransactionTypeIcon = (type: string, large = false) => {
      if (type === 'swap') {
        const containerSize = large ? 'w-16 h-16' : 'w-10 h-10';
        const iconSize = large ? 'w-8 h-8' : 'w-5 h-5';
        return (
          <div className={`flex items-center justify-center ${containerSize} bg-white/10 rounded-md`}>
            <ArrowRightLeft className={`${iconSize} text-white`} />
          </div>
        );
      }
      const size = large ? 'w-16 h-16' : 'w-10 h-10';
      return type === 'transfer_in' ?
        <img src="/receive-icon.svg" alt="Received" className={size} /> :
        <img src="/sent-icon.svg" alt="Sent" className={size} />;
    };

    const shortenAddress = (address?: string) => {
      if (!address) return 'Unknown';
      return `${address.slice(0, 6)}...${address.slice(-4)}`;
    };
    const displayIdentity = (username?: string, address?: string) => {
      const normalized = (username || '').trim().toLowerCase();
      if (normalized && normalized !== 'unknown' && normalized !== 'n/a') {
        return `@${username}`;
      }
      return shortenAddress(address);
    };

    const getSwapCounterparty = (tx: Transaction): { label: string; value: string; highlight: boolean } | null => {
      const userAddr = (userWalletAddress || '').toLowerCase();
      const userName = (username || '').trim().toLowerCase();
      const fromAddr = (tx.from || '').toLowerCase();
      const toAddr = (tx.to || '').toLowerCase();
      const fromUser = (tx.from_username || '').trim().toLowerCase();
      const toUser = (tx.to_username || '').trim().toLowerCase();

      // Self-swap: suppress counterparty labels and keep "Pool Swap".
      if (
        (userAddr && fromAddr === userAddr && toAddr === userAddr) ||
        (userName && (
          (fromUser && fromUser === userName && toUser && toUser === userName) ||
          (toUser && toUser === userName)
        ))
      ) {
        return null;
      }

      if (userAddr && fromAddr === userAddr && tx.to && toAddr !== userAddr) {
        const value = displayIdentity(tx.to_username, tx.to);
        const highlight = !!(tx.to_username && tx.to_username.trim().toLowerCase() !== 'unknown' && tx.to_username.trim().toLowerCase() !== 'n/a');
        return { label: 'To: ', value, highlight };
      }

      if (userAddr && toAddr === userAddr && tx.from && fromAddr !== userAddr) {
        const value = displayIdentity(tx.from_username, tx.from);
        const highlight = !!(tx.from_username && tx.from_username.trim().toLowerCase() !== 'unknown' && tx.from_username.trim().toLowerCase() !== 'n/a');
        return { label: 'From: ', value, highlight };
      }

      if (tx.to_username || tx.to) {
        const value = displayIdentity(tx.to_username, tx.to);
        const highlight = !!(tx.to_username && tx.to_username.trim().toLowerCase() !== 'unknown' && tx.to_username.trim().toLowerCase() !== 'n/a');
        return { label: 'To: ', value, highlight };
      }

      return null;
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
        const date = new Date(timestamp * 1000);
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
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-[hsl(var(--brand-accent))]"></div>
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
        <div className="text-center py-4 text-zinc-400 text-xs flex items-center justify-center gap-2">
          <Clock className="h-4 w-4" />
          <span>No transactions yet</span>
        </div>
      );
    }

    return (
      <div className="flex flex-col">
        <div className="flex flex-col">
          {transactions.map((tx, idx) => {
            let amountDisplay = '';

            if (tx.type === 'swap') {
              const inToken = formatToken(tx.token_in);
              const outToken = formatToken(tx.token_out);
              amountDisplay = `${formatAmount(tx.amount_in)} ${inToken} → ${formatAmount(tx.amount_out)} ${outToken}`;
            } else {
              const token = formatToken(tx.token);
              const amount = formatAmount(tx.amount);
              amountDisplay = `${amount} ${token}`;
            }

            return (
              <div
                key={`${tx.hash}-${idx}`}
                className="py-2.5 flex items-center justify-between min-w-0"
              >
                {/* First column: Icon, Amount/Title, From/To */}
                <div className="flex items-center min-w-0 flex-1 overflow-hidden">
                  <div className="mr-3 flex-shrink-0">
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
                          (() => {
                            const cp = getSwapCounterparty(tx);
                            if (!cp) return 'Pool Swap';
                            return (
                              <>
                                {cp.label}
                                <span className={cp.highlight ? "text-cyan-400 font-medium" : "text-zinc-300"}>
                                  {cp.value}
                                </span>
                              </>
                            );
                          })()
                        ) : (
                          <span
                            className={
                              ((tx.type === 'transfer_in' && tx.from_username && tx.from_username.trim().toLowerCase() !== 'unknown' && tx.from_username.trim().toLowerCase() !== 'n/a')) ||
                                ((tx.type === 'transfer_out' && tx.to_username && tx.to_username.trim().toLowerCase() !== 'unknown' && tx.to_username.trim().toLowerCase() !== 'n/a'))
                                ? "text-cyan-400 font-medium"
                                : "text-zinc-300"
                            }
                          >
                            {tx.type === 'transfer_in'
                              ? displayIdentity(tx.from_username, tx.from)
                              : displayIdentity(tx.to_username, tx.to)
                            }
                          </span>
                        )}
                      </span>
                    </span>
                  </div>
                </div>
                {/* Second column: Timestamp */}
                <div className="flex flex-col text-right flex-shrink-0 ml-2 md:ml-4 justify-center" style={{ minWidth: '60px' }}>
                  <span className="whitespace-nowrap text-zinc-200 text-xs font-semibold">{formatDateOnly(tx.timestamp)}</span>
                  <span className="whitespace-nowrap text-zinc-500 text-[10px] font-medium">{formatTimeOnly(tx.timestamp)}</span>
                </div>
                {/* Status icon */}
                <div className="flex items-center justify-center w-5 h-5 ml-2 flex-shrink-0 self-center">
                  {getStatusIcon(tx)}
                </div>
              </div>
            );
          })}
        </div>

        {/* Infinite scroll sentinel */}
        <div ref={sentinelRef} className="py-2 flex justify-center">
          {loadingMore && (
            <div className="flex items-center gap-2 text-zinc-400 text-xs">
              <div className="animate-spin rounded-full h-4 w-4 border-2 border-zinc-600 border-t-[hsl(var(--brand-accent))]"></div>
              <span>Loading more...</span>
            </div>
          )}
          {!hasMore && transactions.length > PAGE_SIZE && (
            <span className="text-zinc-600 text-xs">All transactions loaded</span>
          )}
        </div>
      </div>
    );
  }
);

TransactionHistory.displayName = 'TransactionHistory';

export default TransactionHistory;


