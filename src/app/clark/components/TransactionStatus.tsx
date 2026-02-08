'use client';

import React from 'react';
import ActiveTransactions, { type ActiveTransaction } from '@/components/wallet/ActiveTransactions';

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

/**
 * Converts inline transaction data from the agent flow into the shape
 * expected by ActiveTransactions.
 */
function inlineDataToActiveTransaction(data: InlineTransactionData): ActiveTransaction {
  const nowSeconds = Math.floor(Date.now() / 1000);
  return {
    transaction_id: data.transaction_id || 'inline-transaction',
    status: (data.status || 'SUBMITTED') as string,
    kind: null,
    tx_type: data.operation === 'swap_and_transfer' || data.operation === 'swap' ? 'swap' : 'transfer',
    created_at: data.created_at ?? nowSeconds,
    updated_at: data.created_at ?? nowSeconds,
    from_token: data.token || null,
    to_token: null,
    token_symbol: data.token || null,
    amount: data.amount ?? null,
    to_address: data.to_address || null,
    to_username: null,
    tx_hash: data.tx_hash ?? null,
  };
}

/**
 * Clark transaction status card. Uses the shared ActiveTransactions component
 * so the UI matches the wallet experience. Seeded with agent-flow data when
 * available and continues polling the active-transactions API for live status.
 */
export default function TransactionStatus({ username, initialData }: TransactionStatusProps) {
  const initialTransactions =
    initialData && (initialData.transaction_id || initialData.amount)
      ? [inlineDataToActiveTransaction(initialData)]
      : undefined;

  return (
    <ActiveTransactions
      username={username}
      initialTransactions={initialTransactions}
      showHeader={false}
    />
  );
}
