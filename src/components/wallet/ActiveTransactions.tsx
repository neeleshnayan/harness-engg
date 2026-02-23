'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { kryptonWeb3Api } from '@/lib/api';
import {
  isTerminalState,
  isErrorState,
  CircleTransactionState,
} from '@/lib/circleStates';
import { ArrowRight, Check, X, Loader2, ArrowLeftRight, RefreshCw, ArrowUp } from 'lucide-react';

// Poll interval in milliseconds (10 seconds for better UX)
const POLL_INTERVAL_MS = 10000;
const WS_SAFETY_POLL_INTERVAL_MS = 20000;
const INITIAL_ONLY_STALE_HIDE_MS = 90000;

// How long to keep terminal transactions visible (12 seconds)
const COMPLETED_TX_DISPLAY_TIME = 12000;

/** Exported for use by TransactionStatus (Clark) when seeding from agent flow */
export interface ActiveTransaction {
  transaction_id: string;
  status: string;
  kind: string | null;
  tx_type: string;
  operation?: string | null;
  created_at: number | null;
  updated_at: number | null;
  from_token: string | null;
  to_token: string | null;
  token_symbol: string | null;
  amount: number | null;
  received_amount?: number | null;
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
  /**
   * When true, the WebSocket connection is live and will deliver push updates.
   * The polling interval is suppressed; polling only runs as a fallback when WS is disconnected.
   */
  isWebSocketConnected?: boolean;
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

function toMsTimestamp(value: number | null | undefined): number | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null;
  return value < 1e12 ? value * 1000 : value;
}

function formatElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) return `${hours}h ${minutes}m ${seconds}s`;
  if (minutes > 0) return `${minutes}m ${seconds}s`;
  return `${seconds}s`;
}

function isFinishedStatus(status: string): boolean {
  const normalized = status.toLowerCase();
  return (
    isTerminalState(status) ||
    normalized === CircleTransactionState.CONFIRMED ||
    normalized === CircleTransactionState.CLEARED
  );
}

function getRecipient(tx: ActiveTransaction, currentUsername?: string): string {
  const normalizedUsername = tx.to_username?.trim().toLowerCase();
  const normalizedCurrent = (currentUsername || '').trim().toLowerCase();
  if (normalizedUsername && normalizedCurrent && normalizedUsername === normalizedCurrent) {
    return '';
  }
  if (normalizedUsername && normalizedUsername !== 'unknown' && normalizedUsername !== 'n/a') {
    return `@${tx.to_username}`;
  }
  if (tx.to_address) return `${tx.to_address.slice(0, 6)}...${tx.to_address.slice(-4)}`;
  return '';
}

function isSwapAndTransferTx(tx: ActiveTransaction, currentUsername?: string): boolean {
  return tx.tx_type === 'swap' && Boolean(getRecipient(tx, currentUsername));
}

/**
 * Get transaction description
 */
function getTransactionDescription(tx: ActiveTransaction, currentUsername?: string): string {
  if (tx.tx_type === 'swap' && tx.from_token && tx.to_token) {
    const fromSymbol = cleanTokenSymbol(tx.from_token);
    const toSymbol = cleanTokenSymbol(tx.to_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    return `${amountStr} ${fromSymbol} → ${toSymbol}`.trim();
  }

  if (tx.tx_type === 'transfer') {
    const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
    const amountStr = tx.amount ? formatAmount(tx.amount) : '';
    const recipient = getRecipient(tx, currentUsername);
    return `Send ${amountStr} ${symbol}${recipient ? ` to ${recipient}` : ''}`;
  }

  // Fallback
  const symbol = cleanTokenSymbol(tx.token_symbol || tx.from_token);
  const amountStr = tx.amount ? formatAmount(tx.amount) : '';
  return amountStr && symbol ? `${amountStr} ${symbol}` : 'Transaction';
}

function getTransactionPhaseCopy(tx: ActiveTransaction, currentUsername?: string): { title: string; subtitle: string } {
  const isSwapAndTransfer = isSwapAndTransferTx(tx, currentUsername);
  const step = getProgressStep(tx.status, isSwapAndTransfer);
  const isError = isErrorState(tx.status);
  const isDone = isFinishedStatus(tx.status) && !isError;
  const fromSymbol = cleanTokenSymbol(tx.from_token || tx.token_symbol);
  const toSymbol = cleanTokenSymbol(tx.to_token || tx.token_symbol);
  const amount = tx.amount ? `${formatAmount(tx.amount)} ${fromSymbol}`.trim() : fromSymbol;
  const receivedAmount = tx.received_amount ? `${formatAmount(tx.received_amount)} ${toSymbol}`.trim() : toSymbol;
  const recipient = getRecipient(tx, currentUsername);

  if (tx.tx_type === 'swap') {
    if (isError) {
      return {
        title: 'Swap failed',
        subtitle: amount ? `Could not swap ${amount}` : 'Swap transaction failed',
      };
    }
    if (isDone) {
      if (!isSwapAndTransfer) {
        return {
          title: 'Swap completed',
          subtitle: receivedAmount ? `Received ${receivedAmount}` : 'Swap completed successfully',
        };
      }
      return {
        title: 'Transfer completed',
        subtitle: recipient ? `Delivered ${receivedAmount || toSymbol} to ${recipient}` : 'Swap and transfer completed',
      };
    }
    if (isSwapAndTransfer && step >= 2) {
      return {
        title: 'Sending swapped amount',
        subtitle: recipient ? `Sending ${receivedAmount || toSymbol} to ${recipient}` : `Sending ${receivedAmount || toSymbol}`,
      };
    }
    return {
      title: 'Swapping',
      subtitle: amount && toSymbol ? `${amount} → ${toSymbol}` : 'Executing token swap',
    };
  }

  if (tx.tx_type === 'transfer') {
    if (isError) {
      return {
        title: 'Transfer failed',
        subtitle: amount ? `Could not send ${amount}` : 'Transfer transaction failed',
      };
    }
    if (isDone) {
      return {
        title: 'Transfer completed',
        subtitle: recipient ? `Delivered ${amount} to ${recipient}` : `${amount} sent successfully`,
      };
    }
    return {
      title: 'Sending',
      subtitle: recipient ? `Sending ${amount} to ${recipient}` : `Sending ${amount}`,
    };
  }

  return {
    title: 'Processing transaction',
    subtitle: getTransactionDescription(tx),
  };
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
    case CircleTransactionState.CLEARED:
      return 'Completed';
    case CircleTransactionState.FAILED:
      return 'Failed';
    case CircleTransactionState.DENIED:
      return 'Denied';
    case CircleTransactionState.CANCELLED:
      return 'Cancelled';
    default:
      // For ongoing transactions, show what the final step will be
      return 'Completed';
  }
}

function getProgressStep(status: string, isSwapAndTransfer: boolean = true): number {
  const normalized = status.toLowerCase();

  if (normalized === 'local_queued' || normalized === CircleTransactionState.CREATED) {
    return 0;
  }

  if (
    normalized === CircleTransactionState.QUEUED ||
    normalized === CircleTransactionState.INITIATED ||
    normalized === CircleTransactionState.SENT ||
    normalized === CircleTransactionState.STUCK ||
    normalized === CircleTransactionState.SUBMITTED ||
    normalized === 'pending'
  ) {
    return 1;
  }

  if (
    normalized === CircleTransactionState.CLEARED ||
    normalized === CircleTransactionState.CONFIRMED ||
    normalized === CircleTransactionState.COMPLETE ||
    normalized === CircleTransactionState.SUCCESS ||
    normalized === CircleTransactionState.FAILED ||
    normalized === CircleTransactionState.DENIED ||
    normalized === CircleTransactionState.CANCELLED
  ) {
    return isSwapAndTransfer ? 3 : 2;
  }

  return 1;
}

function getProgressWidth(step: number, maxStep: number): string {
  if (maxStep <= 0) return '0%';
  const pct = Math.max(0, Math.min(100, (step / maxStep) * 100));
  return `${pct}%`;
}

function StepNode({
  active,
  loading,
  error,
  label,
}: {
  active: boolean;
  loading?: boolean;
  error?: boolean;
  label: string;
}) {
  return (
    <div className="flex flex-col items-center gap-2">
      <div className={`w-10 h-10 rounded-full flex items-center justify-center border-[3px] transition-all duration-300 ${active
        ? (error ? 'bg-red-500 border-red-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white shadow-[0_0_15px_rgba(16,185,129,0.4)]')
        : 'bg-zinc-800 border-zinc-700 text-zinc-500'
        }`}>
        {active ? (
          error ? <X className="w-5 h-5 stroke-[3]" /> : <Check className="w-5 h-5 stroke-[3]" />
        ) : loading ? (
          <Loader2 className="w-4 h-4 animate-spin text-emerald-500" />
        ) : (
          <div className="w-2 h-2 rounded-full bg-zinc-600" />
        )}
      </div>
      <span className={`text-[11px] font-semibold ${active ? (error ? 'text-red-500' : 'text-white') : 'text-zinc-500'}`}>{label}</span>
    </div>
  );
}

/**
 * Transaction Progress Tracker
 */
function TransactionProgressTracker({ tx }: { tx: ActiveTransaction }) {
  const isSwapAndTransfer = isSwapAndTransferTx(tx);
  const maxStep = isSwapAndTransfer ? 3 : 2;
  // Map status to step index (0: Queued, 1: Submitted, 2: Swapped, 3: Completed)
  const currentStep = getProgressStep(tx.status, isSwapAndTransfer);

  // Handle failure
  const isError = isErrorState(tx.status);

  return (
    <div className="w-full mt-6 mb-8">
      {/* Desktop: single-line 4-step track */}
      <div className="hidden sm:block px-6 relative">
        <div className="absolute top-[22px] left-[15%] right-[15%] h-[2px] bg-zinc-700/50 -z-0">
          <div
            className={`h-full transition-all duration-500 ease-out ${isError ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: getProgressWidth(currentStep, maxStep) }}
          />
        </div>

        {isSwapAndTransfer ? (
          <div className="flex justify-between relative z-10 text-center">
            <div className="w-1/4">
              <StepNode active={currentStep >= 0} label="Queued" />
            </div>
            <div className="w-1/4">
              <StepNode active={currentStep >= 1} loading={currentStep === 0 && !isError} label="Submitted" />
            </div>
            <div className="w-1/4">
              <StepNode active={currentStep >= 2} loading={currentStep === 1 && !isError} error={currentStep >= 2 && isError} label="Swapped" />
            </div>
            <div className="w-1/4">
              <StepNode
                active={currentStep >= 3}
                loading={currentStep === 2 && !isError}
                error={currentStep >= 3 && isError}
                label={currentStep >= 3 && isError ? getFinalStepLabel(tx.status) : 'Completed'}
              />
            </div>
          </div>
        ) : (
          <div className="flex justify-between relative z-10 text-center">
            <div className="w-1/3">
              <StepNode active={currentStep >= 0} label="Queued" />
            </div>
            <div className="w-1/3">
              <StepNode active={currentStep >= 1} loading={currentStep === 0 && !isError} label="Submitted" />
            </div>
            <div className="w-1/3">
              <StepNode
                active={currentStep >= 2}
                loading={currentStep === 1 && !isError}
                error={currentStep >= 2 && isError}
                label={currentStep >= 2 && isError ? getFinalStepLabel(tx.status) : 'Completed'}
              />
            </div>
          </div>
        )}
      </div>

      {/* Mobile: linear vertical flow for unambiguous execution order */}
      <div className="sm:hidden px-2 relative">
        <div className="relative pt-1">
          <div className="absolute left-[12%] right-[12%] top-[15px] h-[2px] bg-zinc-700/60" />
          <div
            className={`absolute left-[12%] top-[15px] h-[2px] transition-all duration-500 ease-out ${isError ? 'bg-red-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min(Math.max((currentStep / maxStep) * 76, 0), 76)}%` }}
          />

          <div className={`relative z-10 grid ${isSwapAndTransfer ? 'grid-cols-4' : 'grid-cols-3'} gap-1 text-center`}>
            <div className="flex flex-col items-center gap-1">
              <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${currentStep >= 0 ? 'bg-emerald-500 border-emerald-500 text-white' : 'bg-zinc-900 border-zinc-700 text-zinc-500'}`}>
                <Check className="w-3.5 h-3.5 stroke-[3]" />
              </div>
              <span className={`text-[10px] font-semibold ${currentStep >= 0 ? 'text-white' : 'text-zinc-500'}`}>Queued</span>
            </div>

            <div className="flex flex-col items-center gap-1">
              <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${currentStep >= 1 ? 'bg-emerald-500 border-emerald-500 text-white' : 'bg-zinc-900 border-zinc-700 text-zinc-500'}`}>
                {currentStep >= 1 ? <Check className="w-3.5 h-3.5 stroke-[3]" /> : currentStep === 0 && !isError ? <Loader2 className="w-3 h-3 animate-spin text-emerald-500" /> : <div className="w-1.5 h-1.5 rounded-full bg-zinc-600" />}
              </div>
              <span className={`text-[10px] font-semibold ${currentStep >= 1 ? 'text-white' : 'text-zinc-500'}`}>Submitted</span>
            </div>

            {isSwapAndTransfer ? (
              <>
                <div className="flex flex-col items-center gap-1">
                  <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${currentStep >= 2 ? (isError ? 'bg-red-500 border-red-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white') : 'bg-zinc-900 border-zinc-700 text-zinc-500'}`}>
                    {currentStep >= 2 ? (isError ? <X className="w-3.5 h-3.5 stroke-[3]" /> : <Check className="w-3.5 h-3.5 stroke-[3]" />) : currentStep === 1 && !isError ? <Loader2 className="w-3 h-3 animate-spin text-emerald-500" /> : <div className="w-1.5 h-1.5 rounded-full bg-zinc-600" />}
                  </div>
                  <span className={`text-[10px] font-semibold ${currentStep >= 2 ? (isError ? 'text-red-400' : 'text-white') : 'text-zinc-500'}`}>Swapped</span>
                </div>

                <div className="flex flex-col items-center gap-1">
                  <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${currentStep >= 3 ? (isError ? 'bg-red-500 border-red-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white') : 'bg-zinc-900 border-zinc-700 text-zinc-500'}`}>
                    {currentStep >= 3 ? (isError ? <X className="w-3.5 h-3.5 stroke-[3]" /> : <Check className="w-3.5 h-3.5 stroke-[3]" />) : currentStep === 2 && !isError ? <Loader2 className="w-3 h-3 animate-spin text-emerald-500" /> : <div className="w-1.5 h-1.5 rounded-full bg-zinc-600" />}
                  </div>
                  <span className={`text-[10px] font-semibold ${currentStep >= 3 ? (isError ? 'text-red-400' : 'text-white') : 'text-zinc-500'}`}>
                    {currentStep >= 3 && isError ? getFinalStepLabel(tx.status) : 'Completed'}
                  </span>
                </div>
              </>
            ) : (
              <div className="flex flex-col items-center gap-1">
                <div className={`w-7 h-7 rounded-full border-2 flex items-center justify-center ${currentStep >= 2 ? (isError ? 'bg-red-500 border-red-500 text-white' : 'bg-emerald-500 border-emerald-500 text-white') : 'bg-zinc-900 border-zinc-700 text-zinc-500'}`}>
                  {currentStep >= 2 ? (isError ? <X className="w-3.5 h-3.5 stroke-[3]" /> : <Check className="w-3.5 h-3.5 stroke-[3]" />) : currentStep === 1 && !isError ? <Loader2 className="w-3 h-3 animate-spin text-emerald-500" /> : <div className="w-1.5 h-1.5 rounded-full bg-zinc-600" />}
                </div>
                <span className={`text-[10px] font-semibold ${currentStep >= 2 ? (isError ? 'text-red-400' : 'text-white') : 'text-zinc-500'}`}>
                  {currentStep >= 2 && isError ? getFinalStepLabel(tx.status) : 'Completed'}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Single Transaction Card
 */
function TransactionCard({ tx, nowTs, currentUsername }: { tx: ActiveTransaction; nowTs: number; currentUsername?: string }) {
  const isError = isErrorState(tx.status);
  const phaseCopy = getTransactionPhaseCopy(tx, currentUsername);
  const description = getTransactionDescription(tx, currentUsername);
  const isSwapAndTransfer = isSwapAndTransferTx(tx, currentUsername);
  const totalSteps = isSwapAndTransfer ? 4 : 3;
  const step = getProgressStep(tx.status, isSwapAndTransfer);
  const createdAtMs = toMsTimestamp(tx.created_at);
  const updatedAtMs = toMsTimestamp(tx.updated_at);
  const completedAtMs = toMsTimestamp(tx.completed_at ?? null);
  const isFinished = isFinishedStatus(tx.status);
  const elapsedMs = createdAtMs
    ? Math.max(0, (isFinished ? (completedAtMs || updatedAtMs || nowTs) : nowTs) - createdAtMs)
    : 0;

  return (
    <div className="w-full bg-zinc-900/55 backdrop-blur-md rounded-[24px] border border-white/10 p-5 mb-4 shadow-xl shadow-black/20">
      {/* Header */}
      <div className="flex items-start justify-between mb-2 gap-3">
        <div className="flex items-start gap-3 min-w-0 flex-1 pr-2">
          <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center mt-0.5 shrink-0">
            {tx.tx_type === 'swap' ? <ArrowLeftRight className="w-5 h-5 text-white" /> : <ArrowUp className="w-5 h-5 text-white" />}
          </div>
          <div className="flex flex-col gap-0.5 min-w-0 flex-1">
            <span className="text-base sm:text-lg font-bold text-white tracking-tight truncate max-w-full">{phaseCopy.title}</span>
            <span className="text-xs sm:text-sm text-zinc-300 truncate max-w-full">{phaseCopy.subtitle}</span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2 shrink-0">
          <div className="h-10 rounded-xl border border-white/20 bg-white/8 backdrop-blur-md px-3 inline-flex items-center gap-2 shadow-[0_4px_14px_rgba(0,0,0,0.14)]">
            <div className="w-6 h-6 rounded-md bg-white/8 border border-white/20 flex items-center justify-center">
              {isError ? <X className="w-3.5 h-3.5 text-red-300" /> : isFinished ? <Check className="w-3.5 h-3.5 text-zinc-100" /> : <RefreshCw className="w-3.5 h-3.5 animate-spin text-zinc-100" />}
            </div>
            <span className={`text-xs font-medium tabular-nums ${isError ? 'text-red-200' : 'text-zinc-100'}`}>
              {createdAtMs ? formatElapsed(elapsedMs) : '--'}
            </span>
          </div>
        </div>
      </div>

      <div className="mb-1 flex items-center justify-between text-[10px] sm:text-xs text-zinc-400">
        <span className="truncate max-w-[70%]">{description}</span>
        <span className={`${isError ? 'text-red-300' : 'text-zinc-400'}`}>Step {Math.min(step + 1, totalSteps)}/{totalSteps}</span>
      </div>

      {/* Progress Tracker */}
      <TransactionProgressTracker tx={tx} />

      {/* Hash */}
      {tx.tx_hash && (
        <div className="pt-3 border-t border-white/10 flex items-center gap-2">
          <a
            href={`https://sepolia.etherscan.io/tx/${tx.tx_hash}`}
            target="_blank"
            rel="noreferrer"
            className="text-[11px] text-zinc-400 font-mono hover:text-white transition-colors flex items-center gap-1 group"
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
export default function ActiveTransactions({ username, className = '', onAllTransactionsComplete, refreshKey = 0, isVisible = true, initialTransactions, showHeader = true, persistCompleted = false, onlyShowInitial = false, isWebSocketConnected = false }: ActiveTransactionsProps) {
  const txDebugEnabled =
    process.env.NEXT_PUBLIC_TX_DEBUG === "1" ||
    (typeof window !== "undefined" && window.localStorage.getItem("krypton_tx_debug") === "1");
  const txDebug = useCallback((event: string, payload?: Record<string, unknown>) => {
    if (!txDebugEnabled) return;
    // eslint-disable-next-line no-console
    console.log(`[TX_DEBUG] ActiveTransactions:${event}`, payload || {});
  }, [txDebugEnabled]);

  const [transactions, setTransactions] = useState<ActiveTransaction[]>(() => initialTransactions ?? []);
  const [loading, setLoading] = useState(false);
  const [nowTs, setNowTs] = useState(() => Date.now());
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
      txDebug("fetch_success", {
        username,
        count: newTransactions.length,
        states: newTransactions.map((t) => `${t.transaction_id}:${t.status}`),
      });
      const now = Date.now();

      // Keep completed transactions visible for a short time, then remove them
      setTransactions(prev => {
        // onlyShowInitial: only show initial set and only update their status from API; never add other users' transactions
        if (onlyShowInitial && initialIds.current.size > 0) {
          const fromApi = newTransactions.filter(t => initialIds.current.has(t.transaction_id));
          if (fromApi.length === 0) {
            // Avoid indefinite spinner when initial-only cards miss updates (e.g. app restart
            // during webhook delivery). Hide stale entries after a grace window.
            return prev.filter((tx) => {
              const createdMs = toMsTimestamp(tx.created_at);
              if (!createdMs) return true;
              return (now - createdMs) < INITIAL_ONLY_STALE_HIDE_MS;
            });
          }
          const updated = prev.map(tx => {
            const fromApiMatch = fromApi.find(a => a.transaction_id === tx.transaction_id);
            if (!fromApiMatch) return tx;
            const isFinished = isFinishedStatus(fromApiMatch.status);
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
          const isFinished = isFinishedStatus(newTx.status);
          const isErrorTx = isErrorState(newTx.status);
          const isTracked = prev.some(p => p.transaction_id === newTx.transaction_id);

          // If finished+successful and not tracked, skip it.
          // Failed/denied/cancelled should always be surfaced to the user.
          if (isFinished && !isTracked && !isErrorTx) return false;
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
          const isFinished = isFinishedStatus(newTx.status);

          if (isFinished && !existing) {
            return { ...newTx, completed_at: now };
          }
          if (isFinished && existing && !existing.completed_at) {
            return { ...newTx, completed_at: now };
          }
          return existing?.completed_at ? { ...newTx, completed_at: existing.completed_at } : newTx;
        });

        // Drop terminal transactions after display window even if backend still returns them.
        const visibleUpdatedNew = persistCompleted
          ? updatedNew
          : updatedNew.filter(tx => {
            if (!tx.completed_at) return true;
            return now - tx.completed_at < COMPLETED_TX_DISPLAY_TIME;
          });

        // Combine and sort by created_at descending (newest first)
        const combined = [...visibleUpdatedNew, ...completedToKeep];
        combined.sort((a, b) => {
          const aTime = a.created_at || 0;
          const bTime = b.created_at || 0;
          return bTime - aTime; // Descending order (newest first)
        });
        return combined;
      });
    } catch (err: any) {
      txDebug("fetch_error", {
        username,
        status: err?.response?.status,
        message: err?.message,
      });
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
  }, [username, onlyShowInitial, persistCompleted, txDebug]);

  // Initial fetch when component becomes visible.
  useEffect(() => {
    if (!username) return;

    if (isVisible) {
      fetchActiveTransactions();
    }
  }, [username, fetchActiveTransactions, isVisible]);

  // Polling strategy:
  // - WS disconnected: normal poll cadence
  // - WS connected + pending tx visible: slower safety poll
  // - WS connected + no pending tx: no polling
  useEffect(() => {
    if (!username || !isVisible) {
      return;
    }

    const hasPendingVisible = transactions.some((tx) => !isFinishedStatus(tx.status));
    const shouldSafetyPoll = isWebSocketConnected && hasPendingVisible;
    if (isWebSocketConnected && !shouldSafetyPoll) {
      return;
    }

    const intervalMs = shouldSafetyPoll ? WS_SAFETY_POLL_INTERVAL_MS : POLL_INTERVAL_MS;
    const interval = setInterval(fetchActiveTransactions, intervalMs);
    return () => clearInterval(interval);
  }, [username, fetchActiveTransactions, isVisible, isWebSocketConnected, transactions]);

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
  }, [transactions, onAllTransactionsComplete]);

  // Live elapsed timer for transparency in the UI
  useEffect(() => {
    if (!transactions.length) return;
    const interval = setInterval(() => setNowTs(Date.now()), 1000);
    return () => clearInterval(interval);
  }, [transactions.length]);

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
          <TransactionCard key={tx.transaction_id} tx={tx} nowTs={nowTs} currentUsername={username} />
        ))}
      </div>
    </div>
  );
}

