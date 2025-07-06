'use client';

import React, { useState, useEffect } from 'react';
import { ArrowUpRight, ArrowDownLeft, Clock, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

interface Transaction {
  id: string;
  amount: string;
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
}

interface TransactionHistoryProps {
  username: string;
  userWalletAddress: string;
}

const TransactionHistory: React.FC<TransactionHistoryProps> = ({ username, userWalletAddress }) => {
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nextPageToken, setNextPageToken] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    const fetchTransactions = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://kryptonpaybackend-production.up.railway.app'}/api/v1/latest_transactions_by_username/${username}`);
        const data = await response.json();
        console.log('TransactionHistory initial fetch:', data);
        if (data.error) {
          setError(data.error);
        } else {
          setTransactions(data.transactions || []);
          setNextPageToken(data.next_page_after || null);
        }
      } catch (err) {
        setError('Failed to fetch transactions');
      } finally {
        setLoading(false);
      }
    };
    fetchTransactions();
  }, [username]);

  const loadMore = async () => {
    if (!nextPageToken) return;
    try {
      setLoadingMore(true);
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'https://kryptonpaybackend-production.up.railway.app'}/api/v1/latest_transactions_by_username/${username}?page_after=${encodeURIComponent(nextPageToken)}`);
      const data = await response.json();
      console.log('TransactionHistory load more:', data);
      if (data.error) {
        setError(data.error);
      } else {
        setTransactions(prev => [...prev, ...(data.transactions || [])]);
        setNextPageToken(data.next_page_after || null);
      }
    } catch (err) {
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
    // Clickable on-chain statuses
    const clickableStatuses = ['INITIATED', 'SENT', 'ACCELERATED', 'CONFIRMED'];
    // Status mapping
    switch (upperStatus) {
      case 'INITIATED':
        return txHash ? (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 cursor-pointer"
            title="Initiated - View on Etherscan"
          >
            <Clock className="h-5 w-5 text-zinc-400" />
          </a>
        ) : (
          <span title="Initiated">
            <Clock className="h-5 w-5 text-zinc-400" />
          </span>
        );
      case 'QUEUED':
        return (
          <span title="Queued">
            <Clock className="h-5 w-5 text-zinc-400" />
          </span>
        );
      case 'PENDING_RISK_SCREENING':
        return (
          <span title="Pending Risk Screening">
            <Clock className="h-5 w-5 text-zinc-400" />
          </span>
        );
      case 'SENT':
        return txHash ? (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 cursor-pointer"
            title="Sent - View on Etherscan"
          >
            <Clock className="h-5 w-5 text-cyan-400" />
          </a>
        ) : (
          <span title="Sent">
            <Clock className="h-5 w-5 text-cyan-400" />
          </span>
        );
      case 'ACCELERATED':
        return txHash ? (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 cursor-pointer"
            title="Accelerated - View on Etherscan"
          >
            <Clock className="h-5 w-5 text-cyan-400" />
          </a>
        ) : (
          <span title="Accelerated">
            <Clock className="h-5 w-5 text-cyan-400" />
          </span>
        );
      case 'CONFIRMED':
        return txHash ? (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-green-400 cursor-pointer"
            title="Confirmed - View on Etherscan"
          >
            <CheckCircle className="h-5 w-5 text-cyan-400" />
          </a>
        ) : (
          <span title="Confirmed">
            <CheckCircle className="h-5 w-5 text-cyan-400" />
          </span>
        );
      case 'COMPLETE':
        return (
          <span title="Complete">
            <CheckCircle className="h-5 w-5 text-green-500" />
          </span>
        );
      case 'CANCELED':
        return (
          <span title="Canceled">
            <XCircle className="h-5 w-5 text-zinc-400" />
          </span>
        );
      case 'FAILED':
        return (
          <span title="Failed">
            <XCircle className="h-5 w-5 text-red-500" />
          </span>
        );
      case 'DENIED':
        return (
          <span title="Denied">
            <XCircle className="h-5 w-5 text-red-500" />
          </span>
        );
      default:
        return txHash ? (
          <a
            href={`${etherscanBase}${txHash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-cyan-400 cursor-pointer"
            title="Unknown Status - View on Etherscan"
          >
            <AlertCircle className="h-5 w-5 text-gray-500" />
          </a>
        ) : (
          <span title="Unknown Status">
            <AlertCircle className="h-5 w-5 text-gray-500" />
          </span>
        );
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

  const formatAmount = (amount: string, inbound: boolean) => {
    if (!amount) return inbound ? '+ $0.00' : '- $0.00';
    const num = parseFloat(amount);
    const sign = inbound ? '+' : '-';
    return `${sign} $${num.toFixed(2)}`;
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

  const isInbound = (transaction: Transaction) => {
    return transaction.transaction_type?.toUpperCase() === 'INBOUND' || 
           transaction.to_address === userWalletAddress;
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

  if (transactions.length > 0 && nextPageToken) {
    return (
      <>
        <div className="rounded-xl border border-white/10 bg-black/30">
          {transactions.map((tx, idx) => {
            const inbound = isInbound(tx);
            const counterparty = inbound ? tx.from_address : tx.to_address;
            const counterpartyUsername = inbound ? tx.from_username : tx.to_username;
            const displayCounterparty = counterpartyUsername
              ? <span className="text-cyan-400 font-medium">@{counterpartyUsername}</span>
              : shortenAddress(counterparty);
            const amount = tx.amount || '0';
            return (
              <div
                key={tx.id}
                className={`px-3 py-2 flex flex-col ${idx !== transactions.length - 1 ? 'border-b border-white/10' : ''}`}
              >
                <div className="flex items-center justify-between min-w-0">
                  {/* First line: Arrow, Amount, From/To, Status icon */}
                  <div className="flex items-center min-w-0 flex-1">
                    <div className="flex items-center justify-center w-5 h-5 mr-2">
                      {getTransactionTypeIcon(tx.transaction_type, false)}
                    </div>
                    <span className="text-white font-semibold text-base tracking-tight mr-3">
                      {formatAmount(amount, inbound)}
                    </span>
                    <span className="text-zinc-400 text-xs truncate">
                      {inbound ? 'From' : 'To'}: {displayCounterparty}
                    </span>
                  </div>
                  <div className="flex items-center justify-center w-5 h-5 ml-2">
                    {getStatusIcon(tx.status, tx.tx_hash, tx.blockchain)}
                  </div>
                </div>
                {/* Second line: timestamp and chain, aligned with amount */}
                <div className="flex items-center gap-2 text-zinc-500 text-[11px] ml-6 mt-0.5">
                  <span>{formatDate(tx.created_at)}</span>
                  <span>•</span>
                  <span>{tx.blockchain}</span>
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
            {loadingMore ? 'Loading...' : 'Load more'}
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="rounded-xl border border-white/10 bg-black/30">
      {transactions.map((tx, idx) => {
        const inbound = isInbound(tx);
        const counterparty = inbound ? tx.from_address : tx.to_address;
        const counterpartyUsername = inbound ? tx.from_username : tx.to_username;
        const displayCounterparty = counterpartyUsername
          ? <span className="text-cyan-400 font-medium">@{counterpartyUsername}</span>
          : shortenAddress(counterparty);
        const amount = tx.amount || '0';
        return (
          <div
            key={tx.id}
            className={`px-3 py-2 flex flex-col ${idx !== transactions.length - 1 ? 'border-b border-white/10' : ''}`}
          >
            <div className="flex items-center justify-between min-w-0">
              {/* First line: Arrow, Amount, From/To, Status icon */}
              <div className="flex items-center min-w-0 flex-1">
                <div className="flex items-center justify-center w-5 h-5 mr-2">
                  {getTransactionTypeIcon(tx.transaction_type, false)}
                </div>
                <span className="text-white font-semibold text-base tracking-tight mr-3">
                  {formatAmount(amount, inbound)}
                </span>
                <span className="text-zinc-400 text-xs truncate">
                  {inbound ? 'From' : 'To'}: {displayCounterparty}
                </span>
              </div>
              <div className="flex items-center justify-center w-5 h-5 ml-2">
                {getStatusIcon(tx.status, tx.tx_hash, tx.blockchain)}
              </div>
            </div>
            {/* Second line: timestamp and chain, aligned with amount */}
            <div className="flex items-center gap-2 text-zinc-500 text-[11px] ml-6 mt-0.5">
              <span>{formatDate(tx.created_at)}</span>
              <span>•</span>
              <span>{tx.blockchain}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default TransactionHistory; 