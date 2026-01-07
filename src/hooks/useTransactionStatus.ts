import { useState, useEffect } from 'react';
import api from '@/lib/api';

export function useTransactionStatus(transactionId: string | null) {
  const [status, setStatus] = useState<string>('SUBMITTED');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!transactionId) return;

    const pollStatus = async () => {
      try {
        const response = await api.get(`/dev/request/${transactionId}`);
        setStatus(response.data.status);
        setError(null);

        if (['COMPLETED', 'FAILED', 'CANCELLED'].includes(response.data.status)) {
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

