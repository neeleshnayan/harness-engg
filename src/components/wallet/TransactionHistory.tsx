'use client';

import React, { useState, useEffect, useImperativeHandle, forwardRef } from 'react';
import { ArrowUpRight, ArrowDownLeft, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import api from '@/lib/api';
import { K_TOKEN_ADDRESSES_LOWERCASE } from '@/lib/kTokens';

interface Transaction {
  id: string;
  amount: string;
  token_name: string;
  contract_address?: string | null;  // Contract address for k-tokens
  status: string;
  to_address: string | null;
  from_address: string | null;
  to_username: string | null;
  from_username: string | null;
  created_at: string | null;
  transaction_type: string | null;
  operation: string;
  tx_hash: string | null;
  blockchain: string;
  block_height: number | null;
  from_name: string | null;
  to_name: string | null;
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
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [nextPageToken, setNextPageToken] = useState<string | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);

    const fetchTransactions = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.get(`/api/v1/latest_transactions_by_username/${username}`);
        const data = response.data;
        if (data.error) {
          setError(data.error);
        } else {
          setTransactions(data.transactions || []);
          setNextPageToken(data.next_page_after || null);
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
    if (!nextPageToken) return;
    try {
      setLoadingMore(true);
      const response = await api.get(`/api/v1/latest_transactions_by_username/${username}?page_after=${encodeURIComponent(nextPageToken)}`);
      const data = response.data;
      if (data.error) {
        setError(data.error);
      } else {
        setTransactions(prev => [...prev, ...(data.transactions || [])]);
        setNextPageToken(data.next_page_after || null);
      }
    } catch (err) {
      console.error('Error loading more transactions:', err);
      setError('Failed to load more transactions');
    } finally {
      setLoadingMore(false);
    }
  };

  const getStatusIcon = (status: string, txHash: string | null, blockchain: string) => {
    const etherscanBase = blockchain === 'ETH-SEPOLIA'
      ? 'https://sepolia.etherscan.io/tx/'
      : '';
    const upperStatus = status?.toUpperCase();

    // Helper function to create clickable icon
    const createClickableIcon = (IconComponent: any, color: string, title: string) => {
      if (txHash) {
        return (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 cursor-pointer transition-all duration-200 hover:scale-110 group"
            title={`${title} - View on Etherscan`}
          >
            <IconComponent className={`h-5 w-5 ${color} group-hover:drop-shadow-sm`} />
          </a>
        );
      } else {
        return (
          <span title={title} className="cursor-default">
            <IconComponent className={`h-5 w-5 ${color}`} />
          </span>
        );
      }
    };

    // Status mapping
    switch (upperStatus) {
      case 'INITIATED':
        return createClickableIcon(Clock, 'text-zinc-400', 'Initiated');
      case 'QUEUED':
        return createClickableIcon(Clock, 'text-zinc-400', 'Queued');
      case 'PENDING_RISK_SCREENING':
        return createClickableIcon(Clock, 'text-zinc-400', 'Pending Risk Screening');
      case 'SENT':
        return createClickableIcon(Clock, 'text-cyan-400', 'Sent');
      case 'ACCELERATED':
        return createClickableIcon(Clock, 'text-cyan-400', 'Accelerated');
      case 'CONFIRMED':
        return createClickableIcon(CheckCircle, 'text-cyan-400', 'Confirmed');
      case 'COMPLETE':
        return createClickableIcon(CheckCircle, 'text-green-500', 'Complete');
      case 'CANCELED':
        return createClickableIcon(XCircle, 'text-zinc-400', 'Canceled');
      case 'FAILED':
        return createClickableIcon(XCircle, 'text-red-500', 'Failed');
      case 'DENIED':
        return createClickableIcon(XCircle, 'text-red-500', 'Denied');
      default:
        return createClickableIcon(AlertCircle, 'text-gray-500', 'Unknown Status');
    }
  };

  const getTransactionTypeIcon = (type: string | null, large = false) => {
    if (!type) return null;
    return type.toUpperCase() === 'INBOUND' ?
      <ArrowDownLeft className={large ? 'h-6 w-6 text-green-600' : 'h-5 w-5 text-green-600'} /> :
      <ArrowUpRight className={large ? 'h-6 w-6 text-red-600' : 'h-5 w-5 text-red-600'} />;
  };

  const shortenAddress = (address: string | null) => {
    if (!address) return 'Unknown';
    return `${address.slice(0, 6)}...${address.slice(-4)}`;
  };

  const getDisplayName = (address: string | null, username: string | null) => {
    if (username) {
      return {
        display: `@${username}`,
        fullAddress: address,
        isUsername: true
      };
    } else if (address) {
      return {
        display: shortenAddress(address),
        fullAddress: address,
        isUsername: false
      };
    } else {
      return {
        display: 'Unknown',
        fullAddress: null,
        isUsername: false
      };
    }
  };

  const getTokenSymbol = (tx: Transaction): string => {
    // If contract_address is provided (for k-tokens from CONTRACT_EXECUTION), map it
    if (tx.contract_address) {
      const mapped = K_TOKEN_ADDRESSES_LOWERCASE[tx.contract_address.toLowerCase()];
      if (mapped) return mapped;
    }
    // Otherwise use token_name from backend
    return tx.token_name || 'UNKNOWN';
  };

  const formatAmount = (amount: string, tx: Transaction, inbound: boolean) => {
    const token_symbol = getTokenSymbol(tx);

    if (!amount) return inbound ? `0.00 ${token_symbol}` : `0.00 ${token_symbol}`;
    const num = parseFloat(amount);

    if (token_symbol === 'USDC') {
      return `$${num.toFixed(2)}`;
    }

    // For k-tokens, remove the 'k' prefix for display
    return `${num.toFixed(2)} ${token_symbol.replace(/^k/, "")}`;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return '';
    }
  };

  const formatDateOnly = (dateString: string | null) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return '';
    }
  };

  const formatTimeOnly = (dateString: string | null) => {
    if (!dateString) return '';
    try {
      const date = new Date(dateString);
      return date.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return '';
    }
  };

  const isInbound = (transaction: Transaction) => {
    // For CONTRACT_EXECUTION, rely on transaction_type that's now properly set by backend
    if (transaction.operation === 'CONTRACT_EXECUTION') {
      return transaction.transaction_type?.toUpperCase() === 'INBOUND';
    }
    // For regular transfers, check transaction_type or compare addresses
    return transaction.transaction_type?.toUpperCase() === 'INBOUND' ||
           transaction.to_address?.toLowerCase() === userWalletAddress?.toLowerCase();
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

  var zeroAddress = '0x0000000000000000000000000000000000000000';
  if (transactions.length > 0 && nextPageToken) {
    return (
      <div className="flex flex-col">
        <div className="rounded-t-none rounded-b-xl border border-white/10 bg-black/30">
          {transactions.map((tx, idx) => {
            const inbound = isInbound(tx);
            const counterpartyAddress = inbound ? (tx.from_address == zeroAddress ? tx.from_name : tx.from_address) : tx.to_address;
            const counterpartyUsername = inbound ? tx.from_username : tx.to_username;
            const displayInfo = getDisplayName(counterpartyAddress, counterpartyUsername);
            const amount = tx.amount || '0';
            return (
              <div
                key={tx.id}
                className={`px-3 py-2 flex items-start justify-between min-w-0 overflow-visible ${idx !== transactions.length - 1 ? 'border-b border-white/10' : ''}`}
              >
                {/* First column: Arrow, Amount, To/From */}
                <div className="flex items-start min-w-0 flex-1">
                  <div className="flex items-center justify-center w-5 h-5 mr-2 flex-shrink-0 mt-0.5">
                    {getTransactionTypeIcon(tx.transaction_type, false)}
                  </div>
                  <div className="flex flex-col min-w-0 flex-1">
                    <span className="text-white font-semibold text-base tracking-tight whitespace-nowrap">
                      {formatAmount(amount, tx, inbound)}
                    </span>
                    <span className="text-zinc-400 text-xs mt-0.5 whitespace-nowrap">
                      {inbound ? 'From: ' : 'To: '}
                      <span
                        className={`${displayInfo.isUsername ? 'text-cyan-400 font-medium' : 'text-zinc-300'} inline-flex items-center gap-1`}
                        title={displayInfo.fullAddress ? `Wallet: ${displayInfo.fullAddress}` : undefined}
                      >
                        {displayInfo.display}
                        {displayInfo.isUsername && (
                          <span className="inline-block w-1.5 h-1.5 bg-cyan-400 rounded-full flex-shrink-0" title="Krypton User"></span>
                        )}
                      </span>
                    </span>
                  </div>
                </div>
                {/* Second column: Timestamp (fixed width for alignment) */}
                <div className="flex flex-col text-zinc-400 text-xs text-right flex-shrink-0 ml-2 md:ml-4" style={{ minWidth: '70px' }}>
                  <span className="whitespace-nowrap">{formatDateOnly(tx.created_at)}</span>
                  <span className="whitespace-nowrap">{formatTimeOnly(tx.created_at)}</span>
                </div>
                {/* Status icon */}
                <div className="flex items-center justify-center w-5 h-5 ml-2 flex-shrink-0">
                  {getStatusIcon(tx.status, tx.tx_hash, tx.blockchain)}
                </div>
              </div>
            );
          })}
        </div>
        <div className="flex justify-center mt-4">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="px-4 py-2 rounded-lg bg-zinc-800 text-zinc-200 hover:bg-zinc-700 disabled:opacity-60"
          >
            {loadingMore ? '-' : 'Load more'}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col">
    <div className="rounded-t-none rounded-b-xl border border-white/10 bg-black/30">
      {transactions.map((tx, idx) => {
        const inbound = isInbound(tx);
        const counterpartyAddress = inbound ? (tx.from_address == zeroAddress ? tx.from_name : tx.from_address) : tx.to_address;
        const counterpartyUsername = inbound ? tx.from_username : tx.to_username;
        const displayInfo = getDisplayName(counterpartyAddress, counterpartyUsername);
        const amount = tx.amount || '0';
        return (
          <div
            key={tx.id}
            className={`px-3 py-2 flex items-start justify-between min-w-0 ${idx !== transactions.length - 1 ? 'border-b border-white/10' : ''}`}
          >
            {/* First column: Arrow, Amount, To/From */}
            <div className="flex items-start min-w-0 flex-1 overflow-hidden">
              <div className="flex items-center justify-center w-5 h-5 mr-2 flex-shrink-0 mt-0.5">
                {getTransactionTypeIcon(tx.transaction_type, false)}
              </div>
              <div className="flex flex-col min-w-0 flex-1 overflow-hidden">
                <span className="text-white font-semibold text-base tracking-tight whitespace-nowrap">
                  {formatAmount(amount, tx, inbound)}
                </span>
                <span className="text-zinc-400 text-xs mt-0.5 whitespace-nowrap overflow-visible">
                  {inbound ? 'From: ' : 'To: '}
                  <span
                    className={`${displayInfo.isUsername ? 'text-cyan-400 font-medium' : 'text-zinc-300'} inline-flex items-center gap-1`}
                    title={displayInfo.fullAddress ? `Wallet: ${displayInfo.fullAddress}` : undefined}
                  >
                    {displayInfo.display}
                    {displayInfo.isUsername}
                  </span>
                </span>
              </div>
            </div>
            {/* Second column: Timestamp (fixed width for alignment) */}
            <div className="flex flex-col text-zinc-400 text-xs text-right flex-shrink-0 ml-2 md:ml-4" style={{ minWidth: '70px' }}>
              <span className="whitespace-nowrap">{formatDateOnly(tx.created_at)}</span>
              <span className="whitespace-nowrap">{formatTimeOnly(tx.created_at)}</span>
            </div>
            {/* Status icon */}
            <div className="flex items-center justify-center w-5 h-5 ml-2 flex-shrink-0">
              {getStatusIcon(tx.status, tx.tx_hash, tx.blockchain)}
            </div>
          </div>
        );
      })}
      </div>
    </div>
  );
});

TransactionHistory.displayName = 'TransactionHistory';

export default TransactionHistory;