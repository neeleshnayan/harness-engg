'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { kryptonWeb3Api } from '@/lib/api';
import {
  getProgressStepIndex,
  getStateLabel,
  isTerminalState,
  isSuccessState,
  isErrorState,
  CircleTransactionState,
} from '@/lib/circleStates';
import { ArrowRight, Check, X, Loader2, ArrowLeftRight, Send, RefreshCw, ArrowUpRight, ArrowDownLeft, Clock, CheckCircle, XCircle } from 'lucide-react';

interface ActiveTransaction {
  transaction_id: string;
  status: string;
  kind: string | null;
  tx_type: string;
  created_at: number | null;
  updated_at: number | null;
  from_token: string | null;
  to_token: string | null;
  token_symbol: string | null;
  amount: number | null;
  to_address: string | null;
  to_username: string | null;
  tx_hash: string | null;
}

interface ActiveTransactionsResponse {
  wallet_username: string;
  wallet_address: string;
  transactions: ActiveTransaction[];
  count: number;
}

// Minimal transaction details we can derive directly from the agent flow
// when the backend active-transactions API doesn't yet/any longer return it.
export interface InlineTransactionData {
  transaction_id?: string;
  status?: string;
  operation?: string;
  token?: string;
  amount?: number;
  from_address?: string;
  to_address?: string;
  tx_hash?: string | null;
  created_at?: number | null;
}

interface TransactionStatusProps {
  username: string;
  /** Optional initial transaction details from the agent flow */
  initialData?: InlineTransactionData;
}

function cleanTokenSymbol(symbol: string | null): string {
  if (!symbol) return '';
  return symbol.replace(/^k/, '');
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return '';
  return amount.toFixed(2);
}

function formatDateOnly(timestamp: number | null): string {
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
}

function formatTimeOnly(timestamp: number | null): string {
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
}

function TransactionTypeIcon({ txType, className }: { txType: string; className?: string }) {
  switch (txType) {
    case 'swap':
      return <ArrowLeftRight className={className} />;
    case 'transfer':
      return <ArrowUpRight className={className} />;
    default:
      return <Send className={className} />;
  }
}

function getTransactionDescription(tx: ActiveTransaction): string {
  if (tx.tx_type === 'swap' && tx.from_token && tx.to_token) {
    const fromSymbol = cleanTokenSymbol(tx.from_token);
    const toSymbol = cleanTokenSymbol(tx.to_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    return `Swap ${amountStr} ${fromSymbol} → ${toSymbol}`;
  }

  if (tx.tx_type === 'transfer') {
    const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    const recipient = tx.to_username ? `@${tx.to_username}` : (tx.to_address ? `${tx.to_address.slice(0, 6)}...` : '');
    return `${amountStr} ${symbol}${recipient ? ` to ${recipient}` : ''}`;
  }

  const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
  const amountStr = tx.amount ? formatAmount(tx.amount) : '';
  return amountStr && symbol ? `${amountStr} ${symbol}` : 'Transaction';
}

function ProgressStep({
  stepIndex,
  currentStep,
  label,
  isSuccess,
  isError,
  isTerminal,
}: {
  stepIndex: number;
  currentStep: number;
  label: string;
  isSuccess: boolean;
  isError: boolean;
  isTerminal: boolean;
}) {
  const isFinal = stepIndex === 2;
  const isPastStep = stepIndex < currentStep;
  const isCurrentStep = stepIndex === currentStep;

  let bgColor = 'bg-zinc-700';
  let borderColor = 'border-zinc-600';
  let textColor = 'text-zinc-500';
  let icon = null;

  if (isFinal && isTerminal) {
    if (isSuccess) {
      bgColor = 'bg-emerald-500';
      borderColor = 'border-emerald-400';
      textColor = 'text-emerald-400';
      icon = <Check className="w-3 h-3 text-white" />;
    } else if (isError) {
      bgColor = 'bg-red-500';
      borderColor = 'border-red-400';
      textColor = 'text-red-400';
      icon = <X className="w-3 h-3 text-white" />;
    }
  } else if (isPastStep) {
    bgColor = 'bg-emerald-500';
    borderColor = 'border-emerald-400';
    textColor = 'text-emerald-400';
    icon = <Check className="w-3 h-3 text-white" />;
  } else if (isCurrentStep && !isFinal) {
    if (currentStep === 0) {
      bgColor = 'bg-amber-500';
      borderColor = 'border-amber-400';
      textColor = 'text-amber-400';
      icon = <Loader2 className="w-3 h-3 text-white animate-spin" />;
    } else {
      bgColor = 'bg-emerald-500';
      borderColor = 'border-emerald-400';
      textColor = 'text-emerald-400';
      icon = <Check className="w-3 h-3 text-white" />;
    }
  } else if (isFinal && !isTerminal && currentStep >= 1) {
    bgColor = 'bg-amber-500';
    borderColor = 'border-amber-400';
    textColor = 'text-amber-400';
    icon = <Loader2 className="w-3 h-3 text-white animate-spin" />;
  }

  return (
    <div className="flex flex-col items-center">
      <div
        className={`
          w-6 h-6 rounded-full flex items-center justify-center
          border-2 ${borderColor} ${bgColor}
          transition-all duration-300
        `}
      >
        {icon}
      </div>
      <span className={`text-[10px] mt-1 font-medium ${textColor}`}>
        {label}
      </span>
    </div>
  );
}

function ProgressLine({
  isCompleted,
  isInProgress = false,
  isError = false,
  isLeadingToFinal = false,
}: {
  isCompleted: boolean;
  isInProgress?: boolean;
  isError?: boolean;
  isLeadingToFinal?: boolean;
}) {
  let bgColor = 'bg-zinc-700';

  if (isCompleted) {
    if (isLeadingToFinal && isError) {
      bgColor = 'bg-red-500';
    } else {
      bgColor = 'bg-emerald-500';
    }
  } else if (isInProgress) {
    bgColor = 'bg-amber-500';
  }

  return (
    <div className="flex-1 h-0.5 mx-1 mt-3">
      <div
        className={`
          h-full rounded-full transition-all duration-500
          ${bgColor}
        `}
      />
    </div>
  );
}

function getFinalStepLabel(status: string): string {
  const normalizedStatus = status.toLowerCase();

  switch (normalizedStatus) {
    case CircleTransactionState.SUCCESS:
    case CircleTransactionState.COMPLETE:
      return 'Complete';
    case CircleTransactionState.FAILED:
      return 'Failed';
    case CircleTransactionState.DENIED:
      return 'Denied';
    case CircleTransactionState.CANCELLED:
      return 'Cancelled';
    default:
      return 'Complete';
  }
}

function TransactionProgressTracker({ tx }: { tx: ActiveTransaction }) {
  const currentStep = getProgressStepIndex(tx.status);
  const isSuccess = isSuccessState(tx.status);
  const isError = isErrorState(tx.status);
  const isTerminal = isTerminalState(tx.status);

  const finalStepLabel = isTerminal ? getFinalStepLabel(tx.status) : 'Complete';

  const steps = [
    { index: 0, label: 'Queued' },
    { index: 1, label: 'Confirmed' },
    { index: 2, label: finalStepLabel },
  ];

  const getLineInProgress = (lineIndex: number): boolean => {
    if (lineIndex === 0) {
      return false;
    }
    if (lineIndex === 1) {
      return currentStep >= 1 && !isTerminal;
    }
    return false;
  };

  return (
    <div className="flex items-start justify-between w-full px-2">
      {steps.map((step, idx) => (
        <React.Fragment key={step.index}>
          <ProgressStep
            stepIndex={step.index}
            currentStep={currentStep}
            label={step.label}
            isSuccess={isSuccess}
            isError={isError}
            isTerminal={isTerminal}
          />
          {idx < steps.length - 1 && (
            <ProgressLine
              isCompleted={currentStep >= step.index + 1}
              isInProgress={getLineInProgress(idx)}
              isError={isError}
              isLeadingToFinal={idx === steps.length - 2}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

function getStatusIcon(status: string, txHash: string | null) {
  const upperStatus = status?.toUpperCase();
  const etherscanBase = 'https://sepolia.etherscan.io/tx/';

  const createClickableIcon = (IconComponent: any, color: string, title: string) => {
    if (txHash) {
      return (
        <a
          href={`${etherscanBase}${txHash}`}
          target="_blank"
          rel="noopener noreferrer"
          className="hover:text-cyan-400 cursor-pointer transition-all duration-200 hover:scale-110"
          title={`${title} - View on Etherscan`}
        >
          <IconComponent className={`h-5 w-5 ${color}`} />
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

  switch (upperStatus) {
    case 'INITIATED':
    case 'QUEUED':
    case 'PENDING_RISK_SCREENING':
      return createClickableIcon(Clock, 'text-zinc-400', 'Pending');
    case 'SENT':
    case 'ACCELERATED':
    case 'CONFIRMED':
      return createClickableIcon(Clock, 'text-cyan-400', 'Confirmed');
    case 'COMPLETE':
    case 'SUCCESS':
      return createClickableIcon(CheckCircle, 'text-green-500', 'Complete');
    case 'CANCELED':
    case 'CANCELLED':
      return createClickableIcon(XCircle, 'text-zinc-400', 'Canceled');
    case 'FAILED':
    case 'DENIED':
      return createClickableIcon(XCircle, 'text-red-500', 'Failed');
    default:
      return createClickableIcon(Clock, 'text-gray-500', 'Unknown Status');
  }
}

export default function TransactionStatus({ username, initialData }: TransactionStatusProps) {
  // Initialize with initialData immediately if available
  const [transactions, setTransactions] = useState<ActiveTransaction[]>(() => {
    if (initialData && (initialData.transaction_id || initialData.amount)) {
      const nowSeconds = Math.floor(Date.now() / 1000);
      // For swaps, we might not have to_address, so make it optional
      const tx: ActiveTransaction = {
        transaction_id: initialData.transaction_id || 'inline-transaction',
        status: (initialData.status || 'SUBMITTED') as string,
        kind: null,
        tx_type: initialData.operation === 'swap_and_transfer' || initialData.operation === 'swap' ? 'swap' : 'transfer',
        created_at: initialData.created_at ?? nowSeconds,
        updated_at: initialData.created_at ?? nowSeconds,
        from_token: initialData.token || null,
        to_token: null,
        token_symbol: initialData.token || null,
        amount: initialData.amount ?? null,
        to_address: initialData.to_address || null,
        to_username: null,
        tx_hash: initialData.tx_hash ?? null,
      };
      return [tx];
    }
    return [];
  });
  const [loading, setLoading] = useState(false);
  const [hasInitialData] = useState(!!initialData);

  const fetchActiveTransactions = useCallback(async () => {
    if (!username) return;

    try {
      setLoading(true);
      const response = await kryptonWeb3Api.get<ActiveTransactionsResponse>(
        `/circle/active-transactions/${encodeURIComponent(username)}`
      );

      const newTransactions = response.data.transactions || [];
      // If the backend returns transactions, prefer those.
      // Otherwise, keep any inline initial transaction we already have.
      if (newTransactions.length > 0) {
        setTransactions(newTransactions);
      }
    } catch (err: any) {
      console.error('Error fetching active transactions:', err);
      // If 404, no active transactions
      if (err.response?.status === 404) {
        // Only clear if we never had inline data
        if (!hasInitialData) {
          setTransactions([]);
        }
      }
    } finally {
      setLoading(false);
    }
  }, [username, hasInitialData]);

  useEffect(() => {
    if (username) {
      // Only fetch immediately if we don't have initialData
      // If we have initialData, show it immediately and fetch in background
      if (!hasInitialData) {
        fetchActiveTransactions();
      }
      // Poll every 10 seconds to update status
      const interval = setInterval(fetchActiveTransactions, 10000);
      return () => clearInterval(interval);
    }
  }, [username, fetchActiveTransactions, hasInitialData]);

  if (!username || transactions.length === 0) {
    return null;
  }

  // Show only the most recent transaction
  const latestTx = transactions[0];
  const isTerminal = isTerminalState(latestTx.status);
  const isSuccess = isSuccessState(latestTx.status);
  const isError = isErrorState(latestTx.status);

  // If transaction is complete, show simple row like TransactionHistory
  if (isTerminal) {
    const symbol = cleanTokenSymbol(latestTx.token_symbol || latestTx.from_token || 'USD');
    const amountStr = latestTx.amount ? formatAmount(latestTx.amount) : '';
    const recipient = latestTx.to_username ? `@${latestTx.to_username}` : (latestTx.to_address ? `${latestTx.to_address.slice(0, 6)}...` : '');
    
    return (
      <div className="px-3 py-2 flex items-start justify-between min-w-0 border border-white/10 bg-black/30 rounded-xl">
        <div className="flex items-start min-w-0 flex-1">
          <div className="flex items-center justify-center w-5 h-5 mr-2 flex-shrink-0 mt-0.5">
            <TransactionTypeIcon txType={latestTx.tx_type} className="h-5 w-5 text-red-600" />
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <span className="text-white font-semibold text-base tracking-tight whitespace-nowrap">
              {symbol === 'USD' || symbol === 'USDC' ? `$${amountStr}` : `${amountStr} ${symbol}`}
            </span>
            <span className="text-zinc-400 text-xs mt-0.5 whitespace-nowrap">
              To: <span className="text-cyan-400 font-medium">{recipient}</span>
            </span>
          </div>
        </div>
        <div className="flex flex-col text-zinc-400 text-xs text-right flex-shrink-0 ml-2 md:ml-4" style={{ minWidth: '70px' }}>
          <span className="whitespace-nowrap">{formatDateOnly(latestTx.created_at)}</span>
          <span className="whitespace-nowrap">{formatTimeOnly(latestTx.created_at)}</span>
        </div>
        <div className="flex items-center justify-center w-5 h-5 ml-2 flex-shrink-0">
          {getStatusIcon(latestTx.status, latestTx.tx_hash)}
        </div>
      </div>
    );
  }

  // If transaction is pending, show full card with progress tracker
  const stateLabel = getStateLabel(latestTx.status);
  let borderClass = 'border-amber-500/20';
  let bgClass = 'bg-amber-500/5';

  if (isSuccess) {
    borderClass = 'border-emerald-500/30';
    bgClass = 'bg-emerald-500/5';
  } else if (isError) {
    borderClass = 'border-red-500/30';
    bgClass = 'bg-red-500/5';
  }

  return (
    <div className={`rounded-xl border p-4 ${borderClass} ${bgClass} transition-all duration-300`}>
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`
            w-8 h-8 rounded-lg flex items-center justify-center
            ${isSuccess ? 'bg-emerald-500/20 text-emerald-400' :
              isError ? 'bg-red-500/20 text-red-400' :
              'bg-amber-500/20 text-amber-400'}
          `}>
            <TransactionTypeIcon txType={latestTx.tx_type} className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-zinc-100">
                {getTransactionDescription(latestTx)}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium bg-amber-500/20 text-amber-400`}>
                {stateLabel}
              </span>
            </div>
            {latestTx.tx_type === 'swap' && latestTx.from_token && latestTx.to_token && (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/50 text-zinc-400">
                  {cleanTokenSymbol(latestTx.from_token)}
                </span>
                <ArrowRight className="w-3 h-3 text-zinc-500" />
                <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/50 text-zinc-400">
                  {cleanTokenSymbol(latestTx.to_token)}
                </span>
              </div>
            )}
          </div>
        </div>
        <button
          onClick={fetchActiveTransactions}
          disabled={loading}
          className="p-1.5 bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white rounded-lg border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 disabled:opacity-50"
          title="Refresh status"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <TransactionProgressTracker tx={latestTx} />

      {latestTx.tx_hash && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <a
            href={`https://sepolia.etherscan.io/tx/${latestTx.tx_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-zinc-500 hover:text-cyan-400 transition-colors font-mono flex items-center gap-1"
          >
            <span>{latestTx.tx_hash.slice(0, 8)}...{latestTx.tx_hash.slice(-6)}</span>
            <ArrowRight className="w-3 h-3" />
          </a>
        </div>
      )}
    </div>
  );
}
