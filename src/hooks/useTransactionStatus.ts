import { useState, useEffect } from 'react';
import { kryptonWeb3Api } from '@/lib/api';
import {
  TERMINAL_STATES,
  isTerminalState,
  getStateCategory,
  StateCategory,
  CircleTransactionState
} from '@/lib/circleStates';

export interface TransactionStatusResult {
  status: string;
  loading: boolean;
  error: string | null;
  stateCategory: StateCategory;
  isTerminal: boolean;
}

export function useTransactionStatus(transactionId: string | null): TransactionStatusResult {
  const [status, setStatus] = useState<string>(CircleTransactionState.SUBMITTED);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!transactionId) return;

    let interval: NodeJS.Timeout | null = null;
    let hideTimeout: NodeJS.Timeout | null = null;

    const pollStatus = async () => {
      try {
        const response = await kryptonWeb3Api.get(`/circle/transaction/${transactionId}`);
        // The response structure is: { transaction_id, tracked, data: { status/state, ... } }
        const transactionData = response.data.data;
        const transactionStatus = transactionData?.status || transactionData?.state;
        setStatus(transactionStatus || CircleTransactionState.UNKNOWN);
        setError(null);

        // Stop polling if transaction is in a terminal state
        if (transactionStatus && isTerminalState(transactionStatus)) {
          // Clear the polling interval immediately
          if (interval) {
            clearInterval(interval);
            interval = null;
          }

          // Wait 10 seconds before hiding the dialog
          hideTimeout = setTimeout(() => {
            setLoading(false);
          }, 10000);
        }
      } catch (err: any) {
        console.error('Error polling transaction:', err);
        setError(err.message || 'Failed to poll transaction status');
      }
    };

    setLoading(true);
    pollStatus(); // Initial poll
    interval = setInterval(pollStatus, 15000); // Poll every 15 seconds

    return () => {
      if (interval) clearInterval(interval);
      if (hideTimeout) clearTimeout(hideTimeout);
    };
  }, [transactionId]);

  return {
    status,
    loading,
    error,
    stateCategory: getStateCategory(status),
    isTerminal: isTerminalState(status),
  };
}
