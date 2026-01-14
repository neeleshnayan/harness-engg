'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { kryptonWeb3Api } from '@/lib/api';
import {
  getStateCategory,
  getProgressStepIndex,
  getProgressStepLabel,
  getStateLabel,
  StateCategory,
  isTerminalState,
  isSuccessState,
  isErrorState,
  CircleTransactionState,
} from '@/lib/circleStates';
import { ArrowRight, Check, X, Loader2, ArrowLeftRight, Send, RefreshCw } from 'lucide-react';

// Poll interval in milliseconds (10 seconds for better UX)
const POLL_INTERVAL_MS = 10000;

// How long to keep completed transactions visible (30 seconds)
const COMPLETED_TX_DISPLAY_TIME = 30000;

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
  // Local tracking
  completed_at?: number;
}

interface ActiveTransactionsResponse {
  wallet_username: string;
  wallet_address: string;
  transactions: ActiveTransaction[];
  count: number;
}

interface ActiveTransactionsProps {
  username: string;
  className?: string;
  /** Called when all active transactions complete and the section disappears */
  onAllTransactionsComplete?: () => void;
  /** Change this value to trigger a refresh of active transactions */
  refreshKey?: number;
  /** Whether the component is visible (controls polling - only poll when visible) */
  isVisible?: boolean;
}

/**
 * Clean token symbol for display (remove k prefix)
 */
function cleanTokenSymbol(symbol: string | null): string {
  if (!symbol) return '';
  return symbol.replace(/^k/, '');
}

/**
 * Format amount with symbol
 */
function formatAmount(amount: number | null): string {
  if (amount === null || amount === undefined) return '';
  return amount.toFixed(2);
}

/**
 * Format relative time
 */
function formatRelativeTime(timestamp: number | null): string {
  if (!timestamp) return '';

  const now = Date.now() / 1000;
  const diff = now - timestamp;

  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

/**
 * Get transaction type icon
 */
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

/**
 * Get transaction description
 */
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
    return `Send ${amountStr} ${symbol}${recipient ? ` to ${recipient}` : ''}`;
  }

  // Fallback
  const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
  const amountStr = tx.amount ? formatAmount(tx.amount) : '';
  return amountStr && symbol ? `${amountStr} ${symbol}` : 'Transaction';
}

/**
 * Progress Step Component
 *
 * Visual Logic:
 * - Step 0 (Queued):
 *   - If currentStep=0: yellow spinner (currently queued)
 *   - If currentStep>0: green checkmark (passed)
 * - Step 1 (Confirmed):
 *   - If currentStep<1: gray (not reached)
 *   - If currentStep=1: green checkmark (confirmed, waiting for completion)
 *   - If currentStep>1: green checkmark (passed)
 * - Step 2 (Complete/Failed):
 *   - If currentStep<2: gray or yellow spinner (if currentStep>=1)
 *   - If currentStep=2: green checkmark (success) or red X (error)
 */
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

  // Step is completed (green checkmark) if we're PAST it
  const isPastStep = stepIndex < currentStep;

  // Step is current (the one we're on right now)
  const isCurrentStep = stepIndex === currentStep;

  // Determine the visual state
  let bgColor = 'bg-zinc-700';
  let borderColor = 'border-zinc-600';
  let textColor = 'text-zinc-500';
  let icon = null;

  if (isFinal && isTerminal) {
    // Final step when transaction is terminal - show success/error
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
    // Steps we've already passed - green checkmark
    bgColor = 'bg-emerald-500';
    borderColor = 'border-emerald-400';
    textColor = 'text-emerald-400';
    icon = <Check className="w-3 h-3 text-white" />;
  } else if (isCurrentStep && !isFinal) {
    // Current non-final step
    if (currentStep === 0) {
      // At "Queued" step - show yellow spinner (waiting to be confirmed)
      bgColor = 'bg-amber-500';
      borderColor = 'border-amber-400';
      textColor = 'text-amber-400';
      icon = <Loader2 className="w-3 h-3 text-white animate-spin" />;
    } else {
      // At "Confirmed" step (currentStep=1) - show green (we've reached it)
      bgColor = 'bg-emerald-500';
      borderColor = 'border-emerald-400';
      textColor = 'text-emerald-400';
      icon = <Check className="w-3 h-3 text-white" />;
    }
  } else if (isFinal && !isTerminal && currentStep >= 1) {
    // Final step when not terminal but we've passed confirmed - show yellow spinner
    bgColor = 'bg-amber-500';
    borderColor = 'border-amber-400';
    textColor = 'text-amber-400';
    icon = <Loader2 className="w-3 h-3 text-white animate-spin" />;
  }
  // Otherwise: default gray (not reached yet)

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

/**
 * Progress Line Component
 *
 * Colors:
 * - Gray: Not reached yet
 * - Amber/Yellow: In progress (next step is pending/processing)
 * - Green: Completed successfully
 * - Red: Transaction ended in error (for line leading to error state)
 */
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
    // Line is completed - show green or red based on final state
    if (isLeadingToFinal && isError) {
      bgColor = 'bg-red-500';
    } else {
      bgColor = 'bg-emerald-500';
    }
  } else if (isInProgress) {
    // Line is in progress - show amber/yellow
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

/**
 * Get the final step label based on actual transaction status
 * Shows specific error types: Denied, Cancelled, Failed, etc.
 */
function getFinalStepLabel(status: string): string {
  const normalizedStatus = status.toLowerCase();

  // Show specific terminal state labels
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
      // For ongoing transactions, show what the final step will be
      return 'Complete';
  }
}

/**
 * Transaction Progress Tracker
 */
function TransactionProgressTracker({ tx }: { tx: ActiveTransaction }) {
  const currentStep = getProgressStepIndex(tx.status);
  const isSuccess = isSuccessState(tx.status);
  const isError = isErrorState(tx.status);
  const isTerminal = isTerminalState(tx.status);

  // Use the actual state label for terminal states
  const finalStepLabel = isTerminal ? getFinalStepLabel(tx.status) : 'Complete';

  const steps = [
    { index: 0, label: 'Queued' },
    { index: 1, label: 'Confirmed' },
    { index: 2, label: finalStepLabel },
  ];

  // Determine which line is "in progress" (leading to a step with yellow spinner)
  // Line at index i connects step i to step i+1
  // A line is "in progress" when the step it leads TO is showing a yellow spinner
  const getLineInProgress = (lineIndex: number): boolean => {
    // Line 0 (Queued→Confirmed): Never yellow - Confirmed step never shows spinner
    // It goes directly from gray (not reached) to green (reached)
    if (lineIndex === 0) {
      return false;
    }
    // Line 1 (Confirmed→Complete): Yellow when Complete step shows spinner
    // This happens when we've reached Confirmed (currentStep >= 1) but not terminal yet
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
              isLeadingToFinal={idx === steps.length - 2} // Last line leads to final step
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

/**
 * Get status badge color classes
 */
function getStatusBadgeClasses(status: string): { bg: string; text: string } {
  const normalizedStatus = status.toLowerCase();

  switch (normalizedStatus) {
    case CircleTransactionState.SUCCESS:
    case CircleTransactionState.COMPLETE:
      return { bg: 'bg-emerald-500/20', text: 'text-emerald-400' };
    case CircleTransactionState.FAILED:
      return { bg: 'bg-red-500/20', text: 'text-red-400' };
    case CircleTransactionState.DENIED:
      return { bg: 'bg-orange-500/20', text: 'text-orange-400' };
    case CircleTransactionState.CANCELLED:
      return { bg: 'bg-zinc-500/20', text: 'text-zinc-400' };
    case CircleTransactionState.QUEUED:
    case CircleTransactionState.SUBMITTED:
    case CircleTransactionState.CREATED:
      return { bg: 'bg-blue-500/20', text: 'text-blue-400' };
    case CircleTransactionState.CONFIRMED:
    case CircleTransactionState.SENT:
    case CircleTransactionState.CLEARED:
      return { bg: 'bg-amber-500/20', text: 'text-amber-400' };
    case CircleTransactionState.STUCK:
      return { bg: 'bg-yellow-500/20', text: 'text-yellow-400' };
    default:
      return { bg: 'bg-zinc-500/20', text: 'text-zinc-400' };
  }
}

/**
 * Single Transaction Card
 */
function TransactionCard({ tx }: { tx: ActiveTransaction }) {
  const category = getStateCategory(tx.status);
  const isTerminal = isTerminalState(tx.status);
  const isSuccess = isSuccessState(tx.status);
  const isError = isErrorState(tx.status);
  const stateLabel = getStateLabel(tx.status);
  const badgeClasses = getStatusBadgeClasses(tx.status);

  // Determine card style based on state
  let borderClass = 'border-zinc-700/50';
  let bgClass = 'bg-zinc-800/30';

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
        transition-all duration-300
      `}
    >
      {/* Header: Type icon + Description + Status Badge + Time */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`
            w-8 h-8 rounded-lg flex items-center justify-center
            ${isSuccess ? 'bg-emerald-500/20 text-emerald-400' :
              isError ? 'bg-red-500/20 text-red-400' :
              'bg-amber-500/20 text-amber-400'}
          `}>
            <TransactionTypeIcon txType={tx.tx_type} className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-zinc-100">
                {getTransactionDescription(tx)}
              </span>
              {/* Status Badge - shows specific state */}
              <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${badgeClasses.bg} ${badgeClasses.text}`}>
                {stateLabel}
              </span>
            </div>
            {tx.tx_type === 'swap' && tx.from_token && tx.to_token && (
              <div className="flex items-center gap-1 mt-0.5">
                <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/50 text-zinc-400">
                  {cleanTokenSymbol(tx.from_token)}
                </span>
                <ArrowRight className="w-3 h-3 text-zinc-500" />
                <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700/50 text-zinc-400">
                  {cleanTokenSymbol(tx.to_token)}
                </span>
              </div>
            )}
          </div>
        </div>
        <span className="text-xs text-zinc-500">
          {formatRelativeTime(tx.created_at)}
        </span>
      </div>

      {/* Progress Tracker */}
      <TransactionProgressTracker tx={tx} />

      {/* Transaction Hash Link (if available) */}
      {tx.tx_hash && (
        <div className="mt-3 pt-3 border-t border-white/5">
          <a
            href={`https://sepolia.etherscan.io/tx/${tx.tx_hash}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-zinc-500 hover:text-cyan-400 transition-colors font-mono flex items-center gap-1"
          >
            <span>{tx.tx_hash.slice(0, 8)}...{tx.tx_hash.slice(-6)}</span>
            <ArrowRight className="w-3 h-3" />
          </a>
        </div>
      )}
    </div>
  );
}

/**
 * ActiveTransactions Component
 *
 * Shows active (ongoing) transactions with a progress tracker.
 * Polls the backend every 10 seconds.
 * Persists transactions to localStorage to survive page refreshes.
 */
export default function ActiveTransactions({ username, className = '', onAllTransactionsComplete, refreshKey = 0, isVisible = true }: ActiveTransactionsProps) {
  const [transactions, setTransactions] = useState<ActiveTransaction[]>([]);
  const [loading, setLoading] = useState(false);
  const initialFetch = useRef(true);
  const hadTransactions = useRef(false);
  const lastRefreshKey = useRef(refreshKey);

  const fetchActiveTransactions = useCallback(async () => {
    if (!username) return;

    try {
      if (initialFetch.current) {
        setLoading(true);
      }

      const response = await kryptonWeb3Api.get<ActiveTransactionsResponse>(
        `/circle/active-transactions/${encodeURIComponent(username)}`
      );

      const newTransactions = response.data.transactions || [];
      const now = Date.now();

      // Keep completed transactions visible for a short time, then remove them
      setTransactions(prev => {
        const newIds = new Set(newTransactions.map(tx => tx.transaction_id));

        // Keep completed transactions from previous state that should still be visible
        const completedToKeep = prev.filter(tx => {
          if (tx.completed_at && !newIds.has(tx.transaction_id)) {
            return now - tx.completed_at < COMPLETED_TX_DISPLAY_TIME;
          }
          return false;
        });

        // Mark transactions as completed if they just became terminal
        const updatedNew = newTransactions.map(newTx => {
          const existing = prev.find(p => p.transaction_id === newTx.transaction_id);
          if (isTerminalState(newTx.status) && existing && !existing.completed_at) {
            return { ...newTx, completed_at: now };
          }
          return existing?.completed_at ? { ...newTx, completed_at: existing.completed_at } : newTx;
        });

        return [...updatedNew, ...completedToKeep];
      });
    } catch (err: any) {
      console.error('Error fetching active transactions:', err);
    } finally {
      if (initialFetch.current) {
        setLoading(false);
        initialFetch.current = false;
      }
    }
  }, [username]);

  // Initial fetch and polling - only poll when visible to save API calls
  useEffect(() => {
    if (!username) return;

    // Always do initial fetch when component mounts or becomes visible
    if (isVisible) {
      fetchActiveTransactions();
    }

    // Only set up polling interval when visible
    if (!isVisible) {
      return;
    }

    const interval = setInterval(fetchActiveTransactions, POLL_INTERVAL_MS);

    return () => {
      clearInterval(interval);
    };
  }, [username, fetchActiveTransactions, isVisible]);

  // Refresh when refreshKey changes (triggered by parent component)
  useEffect(() => {
    if (refreshKey !== lastRefreshKey.current) {
      lastRefreshKey.current = refreshKey;
      fetchActiveTransactions();
    }
  }, [refreshKey, fetchActiveTransactions]);

  // Clean up old completed transactions periodically
  useEffect(() => {
    const cleanup = setInterval(() => {
      const now = Date.now();
      setTransactions(prev =>
        prev.filter(tx => {
          if (tx.completed_at) {
            return now - tx.completed_at < COMPLETED_TX_DISPLAY_TIME;
          }
          return true;
        })
      );
    }, 5000);

    return () => clearInterval(cleanup);
  }, []);

  // Track when all transactions complete and call the callback
  useEffect(() => {
    if (transactions.length > 0) {
      hadTransactions.current = true;
    } else if (hadTransactions.current && transactions.length === 0) {
      // Transactions just became empty - trigger refresh
      hadTransactions.current = false;
      if (onAllTransactionsComplete) {
        onAllTransactionsComplete();
      }
    }
  }, [transactions.length, onAllTransactionsComplete]);

  // Don't render if no transactions or no username
  if (!username || transactions.length === 0) {
    return null;
  }

  return (
    <div className={`${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-zinc-400 tracking-wide uppercase">
          Active Transactions
        </h3>
        {loading && (
          <Loader2 className="w-3 h-3 text-zinc-500 animate-spin" />
        )}
      </div>

      {/* Transaction List */}
      <div className="space-y-3">
        {transactions.map((tx) => (
          <TransactionCard key={tx.transaction_id} tx={tx} />
        ))}
      </div>
    </div>
  );
}
