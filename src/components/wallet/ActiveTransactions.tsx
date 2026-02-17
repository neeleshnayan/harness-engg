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
import { ArrowRight, Check, X, Loader2, ArrowLeftRight, Send, RefreshCw, ArrowUp } from 'lucide-react';

// Poll interval in milliseconds (10 seconds for better UX)
const POLL_INTERVAL_MS = 10000;

// How long to keep completed transactions visible (5 seconds)
const COMPLETED_TX_DISPLAY_TIME = 3000;

/** Exported for use by TransactionStatus (Clark) when seeding from agent flow */
export interface ActiveTransaction {
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
  /** Optional initial transactions (e.g. from Clark agent flow) to show before first API response */
  initialTransactions?: ActiveTransaction[];
  /** When false, hide the "Active Transactions" header (e.g. when embedded in Clark chat) */
  showHeader?: boolean;
  /** When true, keep completed transactions visible (e.g. in Clark feed). When false, remove after COMPLETED_TX_DISPLAY_TIME */
  persistCompleted?: boolean;
  /** When true (e.g. Clark inline card), only show initialTransactions and only update their status from API; never add other users' or other requests' transactions */
  onlyShowInitial?: boolean;
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
      return <img src="/swap-icon-small.svg" className={className} alt="Swap" />;
    case 'transfer':
      return <img src="/sent-icon.svg" className={className} alt="Transfer" />;
    default:
      return <img src="/swap-icon-small.svg" className={className} alt="Transaction" />;
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
    case CircleTransactionState.CONFIRMED:
      return 'Confirmed';
    case CircleTransactionState.FAILED:
      return 'Failed';
    case CircleTransactionState.DENIED:
      return 'Denied';
    case CircleTransactionState.CANCELLED:
      return 'Cancelled';
    default:
      // For ongoing transactions, show what the final step will be
      return 'Confirmed';
  }
}

/**
 * Transaction Progress Tracker
 */
function TransactionProgressTracker({ tx }: { tx: ActiveTransaction }) {
  // Map status to step index (0: Queued, 1: Submitted, 2: Confirmed)
  let currentStep = 0;
  const status = tx.status.toLowerCase();

  if (status === 'queued' || status === 'created') currentStep = 0;
  else if (status === 'submitted' || status === 'pending' || status === 'sent') currentStep = 1;
  else if (status === 'confirmed' || status === 'complete' || status === 'success' || status === 'cleared') currentStep = 2;

  // Handle failure
  const isError = isErrorState(tx.status);

  return (
    <div className="w-full px-6 mt-6 mb-8 relative">
       {/* Connecting Lines */}
       <div className="absolute top-[22px] left-[15%] right-[15%] h-[2px] bg-zinc-700/50 -z-0">
          <div
            className="h-full bg-emerald-500 transition-all duration-500 ease-out"
            style={{ width: currentStep === 0 ? '0%' : currentStep === 1 ? '50%' : '100%' }}
          />
       </div>

       <div className="flex justify-between relative z-10 text-center">
          {/* Step 1: Queued */}
          <div className="flex flex-col items-center gap-3 w-1/3">
             <div className={`w-12 h-12 rounded-full flex items-center justify-center border-[3px] transition-all duration-300 ${
                 currentStep >= 0
                 ? 'bg-emerald-500 border-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]'
                 : 'bg-zinc-800 border-zinc-700 text-zinc-500'
             }`}>
                {currentStep >= 0 ? <Check className="w-6 h-6 stroke-[3]" /> : <Loader2 className="w-5 h-5 animate-spin" />}
             </div>
             <span className={`text-xs font-semibold ${currentStep >= 0 ? 'text-white' : 'text-zinc-500'}`}>Queued</span>
          </div>

          {/* Step 2: Submitted */}
          <div className="flex flex-col items-center gap-3 w-1/3">
             <div className={`w-12 h-12 rounded-full flex items-center justify-center border-[3px] transition-all duration-300 ${
                 currentStep >= 1
                 ? 'bg-emerald-500 border-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]'
                 : 'bg-zinc-800 border-zinc-700 text-zinc-500'
             }`}>
                {currentStep >= 1 ? <Check className="w-6 h-6 stroke-[3]" /> : currentStep === 0 && !isError ? <Loader2 className="w-5 h-5 animate-spin text-emerald-500" /> : <div className="w-2 h-2 rounded-full bg-zinc-600" />}
             </div>
             <span className={`text-xs font-semibold ${currentStep >= 1 ? 'text-white' : 'text-zinc-500'}`}>Submitted</span>
          </div>

          {/* Step 3: Confirmed or Failed */}
          <div className="flex flex-col items-center gap-3 w-1/3">
             <div className={`w-12 h-12 rounded-full flex items-center justify-center border-[3px] transition-all duration-300 ${
                 currentStep >= 2
                 ? (isError ? 'bg-red-500 border-red-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]')
                 : 'bg-zinc-800 border-zinc-700 text-zinc-500'
             }`}>
                {currentStep >= 2 ? (isError ? <X className="w-6 h-6 stroke-[3]" /> : <Check className="w-6 h-6 stroke-[3]" />) : currentStep === 1 && !isError ? <Loader2 className="w-5 h-5 animate-spin text-emerald-500" /> : <div className="w-2 h-2 rounded-full bg-zinc-600" />}
             </div>
             <span className={`text-xs font-semibold ${currentStep >= 2 ? (isError ? 'text-red-500' : 'text-white') : 'text-zinc-500'}`}>
               {currentStep >= 2 && isError ? getFinalStepLabel(tx.status) : 'Confirmed'}
             </span>
          </div>
       </div>
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
  const isError = isErrorState(tx.status);

  const description = getTransactionDescription(tx);

  return (
    <div className="w-full bg-zinc-800/40 backdrop-blur-md rounded-[24px] border border-white/5 p-5 mb-4 shadow-xl">
       {/* Header */}
       <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-3">
             <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center">
                {tx.tx_type === 'swap' ? <ArrowLeftRight className="w-5 h-5 text-white" /> : <ArrowUp className="w-5 h-5 text-white" />}
             </div>
             <div className="flex flex-col">
                <span className="text-lg font-bold text-white tracking-tight">{description}</span>
             </div>
          </div>
          {/* Refresh/Status Icon - Top Right */}
          <div className="w-10 h-10 rounded-xl bg-white/5 flex items-center justify-center text-zinc-400">
             {isError ? <X className="w-5 h-5 text-red-500" /> : tx.status === 'confirmed' || isSuccessState(tx.status) ? <Check className="w-5 h-5 text-emerald-500" /> : <RefreshCw className="w-4 h-4 animate-spin" />}
          </div>
       </div>

       {/* Progress Tracker */}
       <TransactionProgressTracker tx={tx} />

       {/* Hash */}
       {tx.tx_hash && (
         <div className="pt-4 border-t border-white/5 flex items-center gap-2">
           <a
             href={`https://sepolia.etherscan.io/tx/${tx.tx_hash}`}
             target="_blank"
             rel="noreferrer"
             className="text-xs text-zinc-500 font-mono hover:text-white transition-colors flex items-center gap-1 group"
           >
             {tx.tx_hash.slice(0, 10)}...{tx.tx_hash.slice(-8)}
             <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
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
export default function ActiveTransactions({ username, className = '', onAllTransactionsComplete, refreshKey = 0, isVisible = true, initialTransactions, showHeader = true, persistCompleted = false, onlyShowInitial = false }: ActiveTransactionsProps) {
  const [transactions, setTransactions] = useState<ActiveTransaction[]>(() => initialTransactions ?? []);
  const [loading, setLoading] = useState(false);
  const initialFetch = useRef(true);
  const hadTransactions = useRef(false);
  const lastRefreshKey = useRef(refreshKey);
  const hadInitialTransactions = useRef(!!(initialTransactions?.length));
  const initialIds = useRef(new Set((initialTransactions ?? []).map(t => t.transaction_id)));

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
        // onlyShowInitial: only show initial set and only update their status from API; never add other users' transactions
        if (onlyShowInitial && initialIds.current.size > 0) {
          const fromApi = newTransactions.filter(t => initialIds.current.has(t.transaction_id));
          if (fromApi.length === 0) return prev;
          const updated = prev.map(tx => {
            const fromApiMatch = fromApi.find(a => a.transaction_id === tx.transaction_id);
            if (!fromApiMatch) return tx;
            const isFinished = isTerminalState(fromApiMatch.status) || fromApiMatch.status.toLowerCase() === CircleTransactionState.CONFIRMED;
            return {
              ...fromApiMatch,
              completed_at: isFinished && !tx.completed_at ? now : tx.completed_at,
            };
          });
          // Sort by created_at descending (newest first)
          updated.sort((a, b) => {
            const aTime = a.created_at || 0;
            const bTime = b.created_at || 0;
            return bTime - aTime;
          });
          return updated.length ? updated : prev;
        }
        // When API returns empty and we had initial data (e.g. Clark agent flow), keep showing it
        if (newTransactions.length === 0 && hadInitialTransactions.current) {
          return prev;
        }
        // Filter out incoming transactions that are already finished (Confirmed or Terminal)
        // AND are not currently tracked in our state. This implements "filter out on refresh".
        const filteredNewTransactions = newTransactions.filter(newTx => {
          const isFinished = isTerminalState(newTx.status) || newTx.status.toLowerCase() === CircleTransactionState.CONFIRMED;
          const isTracked = prev.some(p => p.transaction_id === newTx.transaction_id);

          // If finished and not tracked, skip it
          if (isFinished && !isTracked) return false;
          return true;
        });

        const newIds = new Set(filteredNewTransactions.map(tx => tx.transaction_id));

        // Keep completed transactions from previous state that should still be visible.
        // When persistCompleted (e.g. Clark), keep them indefinitely; otherwise only COMPLETED_TX_DISPLAY_TIME.
        const completedToKeep = prev.filter(tx => {
          if (tx.completed_at && !newIds.has(tx.transaction_id)) {
            return persistCompleted || now - tx.completed_at < COMPLETED_TX_DISPLAY_TIME;
          }
          return false;
        });

        // Mark transactions as completed if they just became terminal (or confirmed)
        const updatedNew = filteredNewTransactions.map(newTx => {
          const existing = prev.find(p => p.transaction_id === newTx.transaction_id);
          const isFinished = isTerminalState(newTx.status) || newTx.status.toLowerCase() === CircleTransactionState.CONFIRMED;

          if (isFinished && existing && !existing.completed_at) {
            return { ...newTx, completed_at: now };
          }
          return existing?.completed_at ? { ...newTx, completed_at: existing.completed_at } : newTx;
        });

        // Combine and sort by created_at descending (newest first)
        const combined = [...updatedNew, ...completedToKeep];
        combined.sort((a, b) => {
          const aTime = a.created_at || 0;
          const bTime = b.created_at || 0;
          return bTime - aTime; // Descending order (newest first)
        });
        return combined;
      });
    } catch (err: any) {
      console.error('Error fetching active transactions:', err);
      // On 404 or error, only clear if we never had initial data (e.g. Clark inline tx)
      if (err?.response?.status === 404 && hadInitialTransactions.current) {
        setTransactions(prev => prev);
      } else if (err?.response?.status === 404 && !hadInitialTransactions.current) {
        setTransactions([]);
      }
    } finally {
      if (initialFetch.current) {
        setLoading(false);
        initialFetch.current = false;
      }
    }
  }, [username, onlyShowInitial]);

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

  // Clean up old completed transactions periodically (skip when persistCompleted, e.g. Clark feed)
  useEffect(() => {
    if (persistCompleted) return;

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
  }, [persistCompleted]);

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
      {showHeader && (
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-medium text-zinc-400 tracking-wide uppercase">
            Active Transactions
          </h3>
          {loading && (
            <Loader2 className="w-3 h-3 text-zinc-500 animate-spin" />
          )}
        </div>
      )}

      {/* Transaction List */}
      <div className="space-y-3">
        {transactions.map((tx) => (
          <TransactionCard key={tx.transaction_id} tx={tx} />
        ))}
      </div>
    </div>
  );
}
