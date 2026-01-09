import { useState, useEffect } from 'react';
import { kryptonWeb3Api } from '@/lib/api';

export function useTransactionStatus(transactionId: string | null) {
  const [status, setStatus] = useState<string>('SUBMITTED');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!transactionId) return;

    const pollStatus = async () => {
      try {
        const response = await kryptonWeb3Api.get(`/circle/transaction/${transactionId}`);
        // The response structure is: { transaction_id, tracked, data: { status/state, ... } }
        const transactionData = response.data.data;
        const transactionStatus = transactionData?.status || transactionData?.state;
        setStatus(transactionStatus || 'UNKNOWN');
        setError(null);

        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(transactionStatus)) {
          setLoading(false);
        }
      } catch (err: any) {
        console.error('Error polling transaction:', err);
        setError(err.message || 'Failed to poll transaction status');
      }
    };

    setLoading(true);
    pollStatus(); // Initial poll
    const interval = setInterval(pollStatus, 3000); // Poll every 3 seconds

    return () => clearInterval(interval);
  }, [transactionId]);

  return { status, loading, error };
}

