'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { kryptonWeb3Api } from '@/lib/api';
import {
  getStateCategory,
  getProgressStepIndex,
  getStateLabel,
  isTerminalState,
  isSuccessState,
  isErrorState,
  CircleTransactionState,
} from '@/lib/circleStates';
import { ArrowRight, Check, X, Loader2, ArrowLeftRight, Send, RefreshCw } from 'lucide-react';

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

interface TransactionConfirmationCardProps {
  username: string;
  onClose?: () => void;
}

function cleanTokenSymbol(symbol: string | null): string {
  if (!symbol) return '';
  return symbol.replace(/^k/, '');
}

function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return '';
  return amount.toFixed(2);
}

function formatRelativeTime(timestamp: number | null): string {
  if (!timestamp) return '';

  const now = Date.now() / 1000;
  const diff = now - timestamp;

  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function TransactionTypeIcon({ txType, className }: { txType: string; className?: string }) {
  switch (txType) {
    case 'swap':
      return <ArrowLeftRight className={className} />;
    case 'transfer':
      return <Send className={className} />;
    default:
      return <RefreshCw className={className} />;
  }
}

function getTransactionDescription(tx: ActiveTransaction): string {
  if (tx.tx_type === 'swap' && tx.from_token && tx.to_token) {
    const fromSymbol = cleanTokenSymbol(tx.from_token);
    const toSymbol = cleanTokenSymbol(tx.to_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    return `${amountStr} ${fromSymbol} \u2192 ${toSymbol}`.trim();
  }

  if (tx.tx_type === 'transfer') {
    const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    const recipient = tx.to_username ? `@${tx.to_username}` : (tx.to_address ? `${tx.to_address.slice(0, 6)}...` : '');
    return `Send ${amountStr} ${symbol}${recipient ? ` to ${recipient}` : ''}`;
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

  let bgColor = 'bg-[var(--kt-hover)]';
  let borderColor = 'border-[var(--kt-border)]';
  let textColor = 'text-[var(--kt-text-muted)]';
  let icon = null;

  if (isFinal && isTerminal) {
    if (isSuccess) {
      bgColor = 'bg-emerald-500';
      borderColor = 'border-emerald-400';
      textColor = 'text-[var(--kt-up)]';
      icon = <Check className="w-3 h-3 text-[var(--kt-text-strong)]" />;
    } else if (isError) {
      bgColor = 'bg-red-500';
      borderColor = 'border-red-400';
      textColor = 'text-[var(--kt-down)]';
      icon = <X className="w-3 h-3 text-[var(--kt-text-strong)]" />;
    }
  } else if (isPastStep) {
    bgColor = 'bg-emerald-500';
    borderColor = 'border-emerald-400';
    textColor = 'text-[var(--kt-up)]';
    icon = <Check className="w-3 h-3 text-[var(--kt-text-strong)]" />;
  } else if (isCurrentStep && !isFinal) {
    if (currentStep === 0) {
      bgColor = 'bg-amber-500';
      borderColor = 'border-amber-400';
      textColor = 'text-[var(--kt-warn)]';
      icon = <Loader2 className="w-3 h-3 text-[var(--kt-text-strong)] animate-spin" />;
    } else {
      bgColor = 'bg-emerald-500';
      borderColor = 'border-emerald-400';
      textColor = 'text-[var(--kt-up)]';
      icon = <Check className="w-3 h-3 text-[var(--kt-text-strong)]" />;
    }
  } else if (isFinal && !isTerminal && currentStep >= 1) {
    bgColor = 'bg-amber-500';
    borderColor = 'border-amber-400';
    textColor = 'text-[var(--kt-warn)]';
    icon = <Loader2 className="w-3 h-3 text-[var(--kt-text-strong)] animate-spin" />;
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
  let bgColor = 'bg-[var(--kt-hover)]';

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
    case CircleTransactionState.CONFIRMED:
      return 'Confirmed';
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

function getStatusBadgeClasses(status: string): { bg: string; text: string } {
  const normalizedStatus = status.toLowerCase();

  switch (normalizedStatus) {
    case CircleTransactionState.CONFIRMED:
    case CircleTransactionState.SUCCESS:
    case CircleTransactionState.COMPLETE:
      return { bg: 'bg-emerald-500/20', text: 'text-[var(--kt-up)]' };
    case CircleTransactionState.FAILED:
      return { bg: 'bg-red-500/20', text: 'text-[var(--kt-down)]' };
    case CircleTransactionState.DENIED:
      return { bg: 'bg-orange-500/20', text: 'text-[var(--kt-warn)]' };
    case CircleTransactionState.CANCELLED:
      return { bg: 'bg-zinc-500/20', text: 'text-[var(--kt-text-dim)]' };
    case CircleTransactionState.QUEUED:
    case CircleTransactionState.SUBMITTED:
    case CircleTransactionState.CLEARED:
    case CircleTransactionState.CREATED:
      return { bg: 'bg-blue-500/20', text: 'text-[var(--kt-agent)]' };
    case CircleTransactionState.SENT:
      return { bg: 'bg-amber-500/20', text: 'text-[var(--kt-warn)]' };
    case CircleTransactionState.STUCK:
      return { bg: 'bg-yellow-500/20', text: 'text-[var(--kt-warn)]' };
    default:
      return { bg: 'bg-zinc-500/20', text: 'text-[var(--kt-text-dim)]' };
  }
}

export default function TransactionConfirmationCard({ username, onClose }: TransactionConfirmationCardProps) {
  const [transactions, setTransactions] = useState<ActiveTransaction[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchActiveTransactions = useCallback(async () => {
    if (!username) return;

    try {
      setLoading(true);
      const response = await kryptonWeb3Api.get<ActiveTransactionsResponse>(
        `/circle/active-transactions/${encodeURIComponent(username)}`
      );

      const newTransactions = response.data.transactions || [];
      setTransactions(newTransactions);

    } catch (err: any) {
      console.error('Error fetching active transactions:', err);
      // If 404, transaction might have completed already - keep card visible briefly
      if (err.response?.status === 404) {
        console.log('Transaction not found (404) - may have completed already');
      }
    } finally {
      setLoading(false);
    }
  }, [username]);

  useEffect(() => {
    if (username) {
      fetchActiveTransactions();
      // Poll every 10 seconds
      const interval = setInterval(fetchActiveTransactions, 10000);
      return () => clearInterval(interval);
    }
  }, [username, fetchActiveTransactions]);

  // Auto-close when all transactions are terminal
  useEffect(() => {
    if (transactions.length > 0 && transactions.every(tx => isTerminalState(tx.status))) {
      // Wait 3 seconds before auto-closing
      const timer = setTimeout(() => {
        if (onClose) {
          onClose();
        }
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [transactions, onClose]);

  // Show card even if no transactions found initially (transaction might have completed quickly)
  // But hide after a few failed attempts
  const [failedAttempts, setFailedAttempts] = useState(0);

  useEffect(() => {
    if (transactions.length === 0) {
      setFailedAttempts(prev => prev + 1);
    } else {
      setFailedAttempts(0);
    }
  }, [transactions.length]);

  // Hide card after 3 failed attempts (30 seconds of polling)
  if (!username || (transactions.length === 0 && failedAttempts >= 3)) {
    return null;
  }

  // If no transactions yet but we haven't given up, show a loading state
  if (transactions.length === 0) {
    return (
      <div className="rounded-xl border p-4 border-amber-500/20 bg-amber-500/5 mb-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Loader2 className="w-5 h-5 text-[var(--kt-warn)] animate-spin" />
            <span className="text-sm font-medium text-[var(--kt-text)]">
              Checking transaction status...
            </span>
          </div>
          <button
            onClick={fetchActiveTransactions}
            disabled={loading}
            className="p-1.5 bg-[var(--kt-hover)] hover:bg-[var(--kt-hover)] text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)] rounded-lg border border-[var(--kt-border)] hover:border-[var(--kt-border)] transition-all duration-200 disabled:opacity-50"
            title="Refresh status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>
    );
  }

  // Show only the most recent transaction
  const latestTx = transactions[0];
  const isTerminal = isTerminalState(latestTx.status);
  const isSuccess = isSuccessState(latestTx.status);
  const isError = isErrorState(latestTx.status);
  const stateLabel = getStateLabel(latestTx.status);
  const badgeClasses = getStatusBadgeClasses(latestTx.status);

  let borderClass = 'border-[var(--kt-border)]';
  let bgClass = 'bg-[var(--kt-hover)]';

  if (isSuccess) {
    borderClass = 'border-emerald-500/30';
    bgClass = 'bg-emerald-500/5';
  } else if (isError) {
    borderClass = 'border-red-500/30';
    bgClass = 'bg-red-500/5';
  } else {
    borderClass = 'border-amber-500/20';
    bgClass = 'bg-amber-500/5';
  }

  return (
    <div
      className={`
        rounded-xl border p-4 ${borderClass} ${bgClass}
        transition-all duration-300 mb-4
      `}
    >
      {/* Header: Type icon + Description + Status Badge + Refresh + Close */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <div className={`
            w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0
            ${isSuccess ? 'bg-emerald-500/20 text-[var(--kt-up)]' :
              isError ? 'bg-red-500/20 text-[var(--kt-down)]' :
              'bg-amber-500/20 text-[var(--kt-warn)]'}
          `}>
            <TransactionTypeIcon txType={latestTx.tx_type} className="w-4 h-4" />
          </div>
          <div className="flex flex-col min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-[var(--kt-text)] truncate">
                {getTransactionDescription(latestTx)}
              </span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium flex-shrink-0 ${badgeClasses.bg} ${badgeClasses.text}`}>
                {stateLabel}
              </span>
            </div>
            {latestTx.tx_type === 'swap' && latestTx.from_token && latestTx.to_token && (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--kt-hover)] text-[var(--kt-text-dim)]">
                  {cleanTokenSymbol(latestTx.from_token)}
                </span>
                <ArrowRight className="w-3 h-3 text-[var(--kt-text-muted)]" />
                <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--kt-hover)] text-[var(--kt-text-dim)]">
                  {cleanTokenSymbol(latestTx.to_token)}
                </span>
              </div>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={fetchActiveTransactions}
            disabled={loading}
            className="p-1.5 bg-[var(--kt-hover)] hover:bg-[var(--kt-hover)] text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)] rounded-lg border border-[var(--kt-border)] hover:border-[var(--kt-border)] transition-all duration-200 disabled:opacity-50"
            title="Refresh status"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 bg-[var(--kt-hover)] hover:bg-[var(--kt-hover)] text-[var(--kt-text-dim)] hover:text-[var(--kt-text-strong)] rounded-lg border border-[var(--kt-border)] hover:border-[var(--kt-border)] transition-all duration-200"
              title="Close"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Tracker */}
      <TransactionProgressTracker tx={latestTx} />

      {/* Transaction Hash Link (if available) */}
      {latestTx.tx_hash && (
        <div className="mt-3 pt-3 border-t border-[var(--kt-border)]">
          <a
            href={`https://sepolia.etherscan.io/tx/${latestTx.tx_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-[var(--kt-text-muted)] hover:text-[var(--kt-agent)] transition-colors font-mono flex items-center gap-1"
          >
            <span>{latestTx.tx_hash.slice(0, 8)}...{latestTx.tx_hash.slice(-6)}</span>
            <ArrowRight className="w-3 h-3" />
          </a>
        </div>
      )}
    </div>
  );
}

