"use client";

import React, { createContext, useContext, useRef, useMemo, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";

interface PendingTransaction {
  resolve: () => void;
  reject: (reason: Error) => void;
  timer: NodeJS.Timeout;
}

interface TransactionWebhookContextValue {
  waitForTransaction: (txId: string, timeoutMs?: number) => Promise<void>;
  connectionStatus: string;
}

const TransactionWebhookContext = createContext<TransactionWebhookContextValue | null>(null);

interface TransactionWebhookProviderProps {
  walletAddress: string | undefined;
  children: React.ReactNode;
}

export function TransactionWebhookProvider({ walletAddress, children }: TransactionWebhookProviderProps) {
  const pendingRef = useRef<Map<string, PendingTransaction>>(new Map());
  const processedEventsRef = useRef<Set<string>>(new Set());

  const wsUrl = useMemo(() => {
    if (!walletAddress) return "";
    const baseUrl =
      process.env.NEXT_PUBLIC_KRYPTON_WEB3_WS_URL ||
      (process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL
        ? process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL.replace("https://", "wss://").replace("http://", "ws://")
        : "wss://web3.kryptonfund.com");
    return `${baseUrl}/ws?wallet_address=${encodeURIComponent(walletAddress)}`;
  }, [walletAddress]);

  const handleMessage = useCallback((message: any) => {
    if (message.type !== "transaction_confirmed" && message.type !== "transaction_update") {
      return;
    }

    const transactionId = message.transaction_id as string | undefined;
    if (!transactionId) return;

    // Deduplicate
    if (processedEventsRef.current.has(transactionId)) {
      console.log(`[WebhookCtx] Skipping duplicate event for ${transactionId}`);
      return;
    }
    processedEventsRef.current.add(transactionId);
    setTimeout(() => {
      processedEventsRef.current.delete(transactionId);
    }, 5 * 60 * 1000);

    console.log(`[WebhookCtx] Received ${message.type} for tx ${transactionId}`);

    // Resolve any pending promise waiting on this txId
    const pending = pendingRef.current.get(transactionId);
    if (pending) {
      clearTimeout(pending.timer);
      pendingRef.current.delete(transactionId);
      pending.resolve();
    }
  }, []);

  const { connectionStatus } = useWebSocket(wsUrl, {
    onMessage: handleMessage,
    onOpen: () => console.log("[WebhookCtx] WebSocket connected"),
    onClose: () => console.log("[WebhookCtx] WebSocket disconnected"),
  });

  const waitForTransaction = useCallback((txId: string, timeoutMs = 60000): Promise<void> => {
    // If already processed (e.g. webhook arrived before we started waiting)
    if (processedEventsRef.current.has(txId)) {
      console.log(`[WebhookCtx] tx ${txId} already confirmed`);
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        pendingRef.current.delete(txId);
        reject(new Error(`Webhook timeout: no confirmation for tx ${txId} after ${timeoutMs / 1000}s`));
      }, timeoutMs);

      pendingRef.current.set(txId, { resolve, reject, timer });
    });
  }, []);

  const value = useMemo(
    () => ({ waitForTransaction, connectionStatus }),
    [waitForTransaction, connectionStatus]
  );

  return (
    <TransactionWebhookContext.Provider value={value}>
      {children}
    </TransactionWebhookContext.Provider>
  );
}

export function useTransactionWebhook() {
  const ctx = useContext(TransactionWebhookContext);
  if (!ctx) {
    throw new Error("useTransactionWebhook must be used within a TransactionWebhookProvider");
  }
  return ctx;
}
