import { useEffect, useState } from 'react';

export type TransactionType = 'deposit' | 'withdraw' | 'approve';
export type TransactionStatus = 'idle' | 'pending' | 'success' | 'failed';

export interface TransactionState {
  type: TransactionType | null;
  status: TransactionStatus;
  hash?: `0x${string}`;
  error?: string;
  timestamp?: number;
}

export const useTransactionStatus = () => {
  const [transaction, setTransaction] = useState<TransactionState>({
    type: null,
    status: 'idle',
  });

  const startTransaction = (type: TransactionType, hash?: `0x${string}`) => {
    setTransaction({
      type,
      status: 'pending',
      hash,
      timestamp: Date.now(),
    });
  };

  const completeTransaction = () => {
    setTransaction(prev => ({
      ...prev,
      status: 'success',
    }));

    // Auto-reset to idle after 3 seconds
    setTimeout(() => {
      setTransaction({
        type: null,
        status: 'idle',
      });
    }, 3000);
  };

  const failTransaction = (error?: string) => {
    setTransaction(prev => ({
      ...prev,
      status: 'failed',
      error,
    }));

    // Auto-reset to idle after 5 seconds
    setTimeout(() => {
      setTransaction({
        type: null,
        status: 'idle',
      });
    }, 5000);
  };

  const resetTransaction = () => {
    setTransaction({
      type: null,
      status: 'idle',
    });
  };

  return {
    transaction,
    startTransaction,
    completeTransaction,
    failTransaction,
    resetTransaction,
  };
};
