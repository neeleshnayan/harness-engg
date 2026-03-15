"use client";

import React, { createContext, useContext, useRef, useMemo, useCallback } from "react";
import { useWebSocket } from "@/hooks/useWebSocket";
import { kryptonWeb3Api } from "@/lib/api";
import { isErrorState, isSuccessState, isTerminalState } from "@/lib/circleStates";

interface PendingTransaction {
  resolve: () => void;
  reject: (reason: Error) => void;
  timer: NodeJS.Timeout;
  poller?: NodeJS.Timeout;
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
    const rawStatus = (message.status || message.state || "").toString().toLowerCase();
    const eventKey = message.type === "transaction_update"
      ? `${message.type}:${transactionId}:${rawStatus}`
      : `${message.type}:${transactionId}`;

    // Deduplicate
    if (processedEventsRef.current.has(eventKey)) {
      return;
    }
    processedEventsRef.current.add(eventKey);
    setTimeout(() => {
      processedEventsRef.current.delete(eventKey);
    }, 5 * 60 * 1000);

    // Resolve/reject from websocket updates, not only explicit "transaction_confirmed".
    const pending = pendingRef.current.get(transactionId);
    if (!pending) return;

    if (message.type === "transaction_confirmed" || (rawStatus && isSuccessState(rawStatus))) {
      clearTimeout(pending.timer);
      if (pending.poller) clearInterval(pending.poller);
      pendingRef.current.delete(transactionId);
      pending.resolve();
      return;
    }

    if (rawStatus && isErrorState(rawStatus)) {
      clearTimeout(pending.timer);
      if (pending.poller) clearInterval(pending.poller);
      pendingRef.current.delete(transactionId);
      pending.reject(new Error(`Transaction ${transactionId} failed with status: ${rawStatus}`));
    }
  }, []);

  const { connectionStatus } = useWebSocket(wsUrl, {
    onMessage: handleMessage,
    onOpen: () => {},
    onClose: () => {},
  });

  const waitForTransaction = useCallback((txId: string, timeoutMs = 60000): Promise<void> => {
    // If already confirmed (e.g. webhook arrived before we started waiting)
    if (processedEventsRef.current.has(`transaction_confirmed:${txId}`)) {
      return Promise.resolve();
    }

    return new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => {
        const pending = pendingRef.current.get(txId);
        if (pending?.poller) clearInterval(pending.poller);
        pendingRef.current.delete(txId);
        reject(new Error(`Webhook timeout: no confirmation for tx ${txId} after ${timeoutMs / 1000}s`));
      }, timeoutMs);

      pendingRef.current.set(txId, { resolve, reject, timer });

      // Fallback polling: handles missed websocket events and queued/promoted transactions.
      const startedAt = Date.now();
      const pollIntervalMs = 4000;
      const interval = setInterval(async () => {
        try {
          const response = await kryptonWeb3Api.get(`/circle/transaction/${txId}`);
          const data = response.data?.data || {};
          const status = (data.status || data.state || "").toString().toLowerCase();
          if (!status) {
            if (Date.now() - startedAt >= timeoutMs) {
              clearInterval(interval);
            }
            return;
          }

          if (isSuccessState(status) || (isTerminalState(status) && !isErrorState(status))) {
            const pending = pendingRef.current.get(txId);
            if (pending) {
              clearTimeout(pending.timer);
              if (pending.poller) clearInterval(pending.poller);
              pendingRef.current.delete(txId);
              pending.resolve();
            }
            clearInterval(interval);
            return;
          }

          if (isErrorState(status)) {
            const pending = pendingRef.current.get(txId);
            if (pending) {
              clearTimeout(pending.timer);
              if (pending.poller) clearInterval(pending.poller);
              pendingRef.current.delete(txId);
              pending.reject(new Error(`Transaction ${txId} failed with status: ${status}`));
            }
            clearInterval(interval);
            return;
          }

          if (Date.now() - startedAt >= timeoutMs) {
            clearInterval(interval);
          }
        } catch {
          if (Date.now() - startedAt >= timeoutMs) {
            clearInterval(interval);
          }
        }
      }, pollIntervalMs);

      const pending = pendingRef.current.get(txId);
      if (pending) {
        pending.poller = interval;
        pendingRef.current.set(txId, pending);
      }
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
