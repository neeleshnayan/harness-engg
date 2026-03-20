"use client";

import React, { useState, useEffect, ReactNode, useCallback, useRef } from "react";
import dynamic from "next/dynamic";
import { getAuth, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import { FaArrowUp, FaCheck, FaTimes } from "react-icons/fa";
import { getFirebaseApp } from "@/lib/firebaseClient";
import UsernameCard from "@/components/wallet/UsernameCard";
import BalanceCard, { BalanceCardRef } from "@/components/wallet/BalanceCard";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import api, { kryptonWeb3Api } from "@/lib/api";
import { parseErrorMessage } from "@/lib/parseError";
import WalletHeader from "@/components/wallet/WalletHeader";
import { useWebSocket } from "@/hooks/useWebSocket";
import { useWalletKyc } from "@/hooks/useWalletKyc";

// Dynamically import heavy modals to reduce initial bundle size
const SendUSDCModal = dynamic(() => import("@/components/wallet/SendUSDCModal"), {
  loading: () => null,
  ssr: false,
});

const BuyUSDCModal = dynamic(() => import("@/components/wallet/BuyUSDCModal"), {
  loading: () => null,
  ssr: false,
});

const SumsubKYCModal = dynamic(() => import("@/components/wallet/SumsubKYCModal"), {
  loading: () => null,
  ssr: false,
});

const SendERC20Modal = dynamic(() => import("@/components/wallet/SendERC20Modal"), {
  loading: () => null,
  ssr: false,
});


// Guardrail to prevent repeated background fetch bursts from overlapping UI triggers.
const MIN_BACKGROUND_BALANCE_FETCH_INTERVAL_MS = 15000;

export interface WalletPageConfig {
  // Page type identifier
  pageType: 'customer' | 'business';

  // Route configurations
  growRoute: string;
  manageRoute?: string;

  // UI customizations
  showKycStatusBadge?: boolean; // Customer shows KYC status, business always shows "Active"
  welcomeMessageMargin?: string; // Customer has -mt-4, business has default

  // Component customizations
  renderChatComponent?: (props: {
    userId?: string;
    onBalanceRefresh: () => void;
    onBalanceFlicker: () => void;
    onTransactionRefresh: () => void;
  }) => ReactNode; // Both customer and business use MiniClarkChat
  showChatToggle?: boolean; // Customer has toggle button, business always shows

  // Payment modal configuration
  useERC20Modal?: boolean; // Customer uses SendERC20Modal, business uses SendUSDCModal

  // Additional action buttons (e.g., "Manage Business")
  renderAdditionalActionButtons?: (push: (path: string) => void) => ReactNode;

  // Webhook notification display
  showWebhookNotification?: boolean; // Business shows it, customer doesn't
}

interface WalletPageBaseProps {
  config: WalletPageConfig;
}

export default function WalletPageBase({ config }: WalletPageBaseProps) {
  const txDebugEnabled =
    process.env.NEXT_PUBLIC_TX_DEBUG === "1" ||
    (typeof window !== "undefined" && window.localStorage.getItem("krypton_tx_debug") === "1");
  const txDebug = useCallback((event: string, payload?: Record<string, unknown>) => {
    if (!txDebugEnabled) return;
    // eslint-disable-next-line no-console
    console.log(`[TX_DEBUG] ${event}`, payload || {});
  }, [txDebugEnabled]);

  const [accountData, setAccountData] = useState<any>(null);
  const [balance, setBalance] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [userDataLoading, setUserDataLoading] = useState(false);
  const [balanceLoading, setBalanceLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [username, setUsername] = useState<string>("");
  const [showUsernameForm, setShowUsernameForm] = useState(false);
  const [usernameLoading, setUsernameLoading] = useState(false);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSuccess, setUsernameSuccess] = useState<string | null>(null);
  const [showSendForm, setShowSendForm] = useState(false);
  const [showSendERC20Form, setShowSendERC20Form] = useState(false);
  const [receiverUsername, setReceiverUsername] = useState<string>("");
  const [sendAmount, setSendAmount] = useState<string>("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);
  const [refreshingBalance, setRefreshingBalance] = useState(false);
  const [showTransakModal, setShowTransakModal] = useState(false);
  const [transactionHistoryRefresh, setTransactionHistoryRefresh] = useState(0);
  const [webhookNotification, setWebhookNotification] = useState<string | null>(null);
  const [balanceCardRefresh, setBalanceCardRefresh] = useState(false);
  const [balanceRefreshing, setBalanceRefreshing] = useState(false);
  const [balanceFlickering, setBalanceFlickering] = useState(false);
  const [showClarkChat, setShowClarkChat] = useState(false);
  const [initialTransactions, setInitialTransactions] = useState<{
    transactions: any[];
    count: number;
    has_more: boolean;
  } | undefined>(undefined);
  // Incremented only on balance_update (post-subgraph indexing) to directly
  // refresh TransactionHistory without waiting for the ActiveTransactions drain.
  const [txHistoryForceRefresh, setTxHistoryForceRefresh] = useState(0);
  const [latestWsTransaction, setLatestWsTransaction] = useState<any | null>(null);
  const [latestWsTransactionVersion, setLatestWsTransactionVersion] = useState(0);
  const [latestWsActiveEvent, setLatestWsActiveEvent] = useState<any | null>(null);
  const [latestWsActiveEventVersion, setLatestWsActiveEventVersion] = useState(0);
  const router = useRouter();
  const {
    kycModalVisible,
    kycAccessToken,
    kycStatus,
    kycChecking,
    kycMessage,
    setKycStatus,
    openKycModal,
    checkKycStatus,
    skipKyc,
    handleKycModalClose,
  } = useWalletKyc({ accountData, setAccountData });

  // Refs to prevent excessive balance fetches
  const balanceFetchInProgressRef = useRef(false);
  const lastBackgroundBalanceFetchAtRef = useRef(0);
  const accountDataRef = useRef(accountData);
  const showTransactionsRef = useRef(showTransactions);
  const balanceRef = useRef<any>(balance);
  const fetchBalanceRef = useRef<((address: string, options?: { background?: boolean }) => Promise<void>) | null>(null);
  const processedWebhookEventsRef = useRef<Set<string>>(new Set()); // Track processed webhook event keys (type+txId)
  const processedBalanceUpdatesRef = useRef<Map<string, { ts: number; hadBalances: boolean }>>(new Map()); // Track processed balance_update keys (txId/txHash)
  const balanceCardRef = useRef<BalanceCardRef | null>(null); // Ref to BalanceCard for switching tabs
  const sawWsBalanceUpdateRef = useRef(false); // Gate refresh on real WS updates since page load
  const balanceFlickerTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Update refs when state changes
  useEffect(() => {
    accountDataRef.current = accountData;
  }, [accountData]);

  useEffect(() => {
    showTransactionsRef.current = showTransactions;
  }, [showTransactions]);

  useEffect(() => {
    balanceRef.current = balance;
  }, [balance]);

  const triggerBalanceFlicker = useCallback((durationMs = 900) => {
    if (balanceFlickerTimerRef.current) {
      clearTimeout(balanceFlickerTimerRef.current);
    }
    setBalanceFlickering(true);
    balanceFlickerTimerRef.current = setTimeout(() => {
      setBalanceFlickering(false);
      balanceFlickerTimerRef.current = null;
    }, durationMs);
  }, []);

  const buildBalanceSignatureFromState = useCallback((currentBalance: any): string | null => {
    const items = Array.isArray(currentBalance?.tokenBalances) ? currentBalance.tokenBalances : [];
    if (!items.length) return null;
    const normalized = [];
    for (const tb of items) {
      try {
        const symbol = String(tb?.token?.symbol || "");
        const address = String(tb?.token?.tokenAddress || "").toLowerCase();
        const amountVal = parseFloat(tb?.amount ?? "0");
        normalized.push(`${symbol}:${address}:${Number.isFinite(amountVal) ? amountVal.toFixed(8) : "0.00000000"}`);
      } catch {
        continue;
      }
    }
    if (!normalized.length) return null;
    normalized.sort();
    return normalized.join("|");
  }, []);

  const buildBalanceSignatureFromWs = useCallback((balances: any[]): string | null => {
    if (!Array.isArray(balances) || balances.length === 0) return null;
    const normalized = [];
    for (const b of balances) {
      try {
        const symbol = String(b?.symbol || "");
        const address = String(b?.address || "").toLowerCase();
        const amountVal = parseFloat(String(b?.balance ?? "0"));
        normalized.push(`${symbol}:${address}:${Number.isFinite(amountVal) ? amountVal.toFixed(8) : "0.00000000"}`);
      } catch {
        continue;
      }
    }
    if (!normalized.length) return null;
    normalized.sort();
    return normalized.join("|");
  }, []);


  // WebSocket message handler - stabilized with useCallback and refs
  const handleWebSocketMessage = useCallback((message: any) => {
    txDebug("ws_message", {
      type: message?.type,
      transaction_id: message?.transaction_id,
      tx_hash: message?.tx_hash,
      has_balances: Array.isArray(message?.balances),
    });

    // Handle transaction_failed - trigger immediate ActiveTransactions refresh
    if (message.type === 'transaction_failed') {
      setLatestWsActiveEvent(message);
      setLatestWsActiveEventVersion(prev => prev + 1);
      setTransactionHistoryRefresh(prev => prev + 1);  // Trigger ActiveTransactions poll
      txDebug("tx_failed_refresh_triggered", {
        transaction_id: message?.transaction_id,
        state: message?.state,
      });
      if (config.showWebhookNotification) {
        setWebhookNotification(`Transaction failed: ${message.state || 'Error'}`);
        setTimeout(() => setWebhookNotification(null), 5000);
      }
      return;
    }

    // Handle new Krypton_Web3 event format (from webhook.py)
    if (message.type === 'transaction_confirmed' || message.type === 'transaction_update') {
      const transactionId = message.transaction_id;
      const txHash = message.tx_hash;

      const rawStatus = String(message?.state || message?.status || '').toLowerCase();
      const eventKey = message.type === 'transaction_update'
        ? `${message.type}:${transactionId || ''}:${rawStatus}`
        : `${message.type}:${transactionId || ''}`;

      // Deduplicate per event type + tx id.
      // This allows transaction_update and transaction_confirmed for the same tx
      // to both be processed in order.
      if (transactionId && processedWebhookEventsRef.current.has(eventKey)) {
        return;
      }

      // Mark this event as processed
      if (transactionId) {
        processedWebhookEventsRef.current.add(eventKey);
        // Clean up old event IDs after 5 minutes to prevent memory leak
        setTimeout(() => {
          processedWebhookEventsRef.current.delete(eventKey);
        }, 5 * 60 * 1000);
      }

      // Show notification to user
      if (message.type === 'transaction_confirmed' && config.showWebhookNotification) {
        setWebhookNotification('Transaction confirmed!');
        setTimeout(() => setWebhookNotification(null), 5000);
      }

      // transaction_confirmed is status/history-only.
      // The unified balance-authoritative event is balance_update.
      const currentAccountData = accountDataRef.current;
      if (currentAccountData?.wallet_address) {
        setLatestWsActiveEvent({
          type: message.type,
          transaction_id: transactionId,
          state: rawStatus || 'confirmed',
          status: rawStatus || 'confirmed',
        });
        setLatestWsActiveEventVersion(prev => prev + 1);
        const singleTx = message.transaction;

        if (singleTx && singleTx.hash) {
          setLatestWsTransaction(singleTx);
          setLatestWsTransactionVersion(prev => prev + 1);
        } else {
          // Fallback: ensure sender/receiver history still updates even if webhook
          // did not include a single transaction payload.
          setTxHistoryForceRefresh(prev => prev + 1);
        }

        setTransactionHistoryRefresh(prev => prev + 1);
        txDebug("tx_confirmed_refresh_triggered", {
          transaction_id: transactionId,
          tx_hash: txHash,
          has_transaction: !!(singleTx && singleTx.hash),
        });
      }

      return;
    }

    // Handle balance_update event - sent by backend AFTER subgraph indexes the tx
    // This is separate from transaction_confirmed to bypass the dedup check above
    if (message.type === 'balance_update') {
      const transactionId = message?.transaction_id ? String(message.transaction_id) : '';
      const txHash = message?.tx_hash ? String(message.tx_hash).toLowerCase() : '';
      const balanceUpdateKey = (transactionId || txHash) ? `${transactionId}:${txHash}` : '';
      const hasBalances = Array.isArray(message?.balances) && message.balances.length > 0;
      if (balanceUpdateKey) {
        const existing = processedBalanceUpdatesRef.current.get(balanceUpdateKey);
        if (existing) {
          // If we already processed a balance-bearing update, always skip duplicates.
          if (existing.hadBalances) {
            return;
          }
          // If this update also has no balances, skip to prevent reload loops.
          if (!hasBalances) {
            return;
          }
        }
        processedBalanceUpdatesRef.current.set(balanceUpdateKey, {
          ts: Date.now(),
          hadBalances: hasBalances,
        });
        setTimeout(() => {
          processedBalanceUpdatesRef.current.delete(balanceUpdateKey);
        }, 5 * 60 * 1000);
      }
      const currentAccountData = accountDataRef.current;
      if (currentAccountData?.wallet_address) {
        const balances = message.balances;
        const singleTx = message.transaction;
        if (Array.isArray(balances) && balances.length > 0) {
          const currentSig = buildBalanceSignatureFromState(balanceRef.current);
          const incomingSig = buildBalanceSignatureFromWs(balances);
          const isSameBalance = currentSig && incomingSig && currentSig === incomingSig;
          sawWsBalanceUpdateRef.current = true;
          if (!isSameBalance) {
            triggerBalanceFlicker();
          }
          const incoming = balances.map((b: { symbol: string; balance: number; decimals?: number; address?: string }) => ({
            amount: String(b.balance ?? 0),
            token: {
              name: b.symbol === 'USDC' ? 'USD Coin' : b.symbol?.startsWith('k') ? `Krypton ${b.symbol.substring(1).toUpperCase()}` : b.symbol ?? '',
              blockchain: 'ETH-SEPOLIA',
              decimals: b.decimals,
              isNative: b.symbol === 'ETH' || b.symbol === 'ETH-SEPOLIA',
              symbol: b.symbol ?? '',
              tokenAddress: b.address,
              standard: (b.symbol === 'ETH' || b.symbol === 'ETH-SEPOLIA') ? undefined : 'ERC20',
            },
          }));
          if (!isSameBalance) {
            setBalance((prev: any) => {
              const existing = Array.isArray(prev?.tokenBalances) ? prev.tokenBalances : [];
              const bySymbol = new Map<string, any>();
              for (const tb of existing) {
                const sym = tb?.token?.symbol;
                if (sym) bySymbol.set(sym, tb);
              }
              for (const tb of incoming) {
                const sym = tb?.token?.symbol;
                if (sym) bySymbol.set(sym, tb);
              }
              return {
                tokenBalances: Array.from(bySymbol.values()),
                _fetchedAt: Date.now(),
              };
            });
          }
        } else {
          // No balances in WS message — skip; balance will update on next WS event or page reload.
        }
        // Keep ActiveTransactions in sync.
        setTransactionHistoryRefresh(prev => prev + 1);
        // Prefer one-row append; fallback to full history fetch if payload missing.
        if (singleTx && singleTx.hash) {
          setLatestWsTransaction(singleTx);
          setLatestWsTransactionVersion(prev => prev + 1);
        } else {
          setTxHistoryForceRefresh(prev => prev + 1);
        }
        txDebug("balance_update_refresh_triggered", {
          transaction_id: message?.transaction_id,
          tx_hash: message?.tx_hash,
          has_balances: Array.isArray(message?.balances),
          has_transaction: !!(singleTx && singleTx.hash),
        });
      }
      return;
    }

    if (message.type === 'connection_established') {
      // Ignore this message, it's just a connection confirmation
      return;
    }

  }, [config.showWebhookNotification, txDebug]);

  // WebSocket open handler - stabilized
  const handleWebSocketOpen = useCallback(() => {
    if (config.showWebhookNotification) {
      setWebhookNotification('WebSocket connected successfully!');
      setTimeout(() => setWebhookNotification(null), 3000);
    }
  }, [config.showWebhookNotification]);

  // WebSocket close handler - stabilized
  const handleWebSocketClose = useCallback((event?: CloseEvent) => {
    if (!event) return;
    // Common close codes are expected during reconnects/navigation.
    if (event.code !== 1000) {
      console.warn('WebSocket closed:', {
        code: event.code,
        reason: event.reason || '(no reason)',
        wasClean: event.wasClean
      });
    }
  }, []);

  // WebSocket error handler - stabilized with ref
  const handleWebSocketError = useCallback((error: Event | Record<string, unknown>) => {
    const diagnostic = (error && typeof error === 'object')
      ? {
        type: (error as any).type || 'websocket_error',
        readyState: (error as any).readyState,
        lastCloseCode: (error as any).lastCloseCode,
        lastCloseReason: (error as any).lastCloseReason,
        lastCloseWasClean: (error as any).lastCloseWasClean,
        url: (error as any).url,
      }
      : { type: 'websocket_error' };
    console.warn('WebSocket error (diagnostic):', diagnostic);
  }, []);

  // WebSocket connection for real-time transaction updates from Krypton_Web3
  // Uses user-specific events - only receives events for the connected wallet
  const wsUrl = React.useMemo(() => {
    const walletAddress = accountData?.wallet_address;
    if (!walletAddress) return null;
    const baseUrl = process.env.NEXT_PUBLIC_KRYPTON_WEB3_WS_URL ||
      (process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL ?
        process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL.replace('https://', 'wss://').replace('http://', 'ws://') :
        'wss://web3.kryptonfund.com');
    return `${baseUrl}/ws?wallet_address=${encodeURIComponent(walletAddress)}`;
  }, [accountData?.wallet_address]);

  const { connectionStatus } = useWebSocket(
    wsUrl || '',
    {
      onMessage: handleWebSocketMessage,
      onOpen: handleWebSocketOpen,
      onClose: handleWebSocketClose,
      onError: handleWebSocketError
    }
  );

  // Cleanup: reset processed webhook events on unmount
  useEffect(() => {
    return () => {
      processedWebhookEventsRef.current.clear();
      processedBalanceUpdatesRef.current.clear();
      if (balanceFlickerTimerRef.current) {
        clearTimeout(balanceFlickerTimerRef.current);
        balanceFlickerTimerRef.current = null;
      }
    };
  }, []);


  const fetchUserData = async (userId: string) => {
    try {
      setUserDataLoading(true);

      const response = await api.get(`/api/v1/user/${userId}`);
      const userData = response.data;

      // Preserve existing wallet data if not in the response
      const currentData = accountData || {};
      const updatedData = {
        ...currentData,
        ...userData,
        // Ensure wallet data is preserved
        wallet_address: userData.wallet_address || currentData.wallet_address,
        wallet_id: userData.wallet_id || currentData.wallet_id,
        blockchain: userData.blockchain || currentData.blockchain,
        // Ensure user_id is preserved (Firestore returns 'id' but we need 'user_id')
        user_id: userData.id || currentData.user_id || userId
      };
      const resolvedKycStatus = userData.kyc_status || currentData.kyc_status || null;
      setKycStatus(resolvedKycStatus);

      setAccountData(updatedData);
      localStorage.setItem('userData', JSON.stringify(updatedData));

      // Only fetch balance when wallet address changed (initial effect already fetches on load)
      if (updatedData.wallet_address && accountDataRef.current?.wallet_address !== updatedData.wallet_address) {
        fetchBalance(updatedData.wallet_address, { background: true });
      }

      // If user has username but KYC is not approved, check status
      if (updatedData.username && resolvedKycStatus && resolvedKycStatus !== 'approved') {
        setTimeout(() => {
          checkKycStatus(userId);
        }, 1000);
      }

    } catch (err) {
      console.error('Failed to fetch user data:', err);
      // Fallback to localStorage data
      const data = JSON.parse(localStorage.getItem('userData') || '{}');
      setKycStatus(data.kyc_status || null);
    } finally {
      setUserDataLoading(false);
    }
  };

  const fetchBalance = useCallback(async (
    address: string,
    options?: { background?: boolean }
  ) => {
    // Prevent duplicate concurrent fetches
    if (balanceFetchInProgressRef.current && options?.background) {
      return;
    }

    const isBackground = options?.background === true;
    const now = Date.now();

    // Throttle background fetches to avoid continuous /wallet-overview calls when
    // multiple UI hooks trigger refresh close together.
    if (
      isBackground &&
      lastBackgroundBalanceFetchAtRef.current > 0 &&
      now - lastBackgroundBalanceFetchAtRef.current < MIN_BACKGROUND_BALANCE_FETCH_INTERVAL_MS
    ) {
      return;
    }

    // Set fetching flag
    if (isBackground) {
      balanceFetchInProgressRef.current = true;
      lastBackgroundBalanceFetchAtRef.current = now;
    }

    try {
      if (!isBackground) {
        setBalanceLoading(true);
      }

      // Use wallet-overview (balances + rates) with cache-busting timestamp.
      // Rates are returned for backend-driven bootstrap consistency; this component
      // currently consumes balances directly.
      const kryptonWeb3ApiUrl = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'https://kryptonweb3-production.up.railway.app';
      const cacheBuster = Date.now();
      const response = await fetch(`${kryptonWeb3ApiUrl}/subgraph/wallet-overview?address=${encodeURIComponent(address)}&_t=${cacheBuster}`, {
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          'Pragma': 'no-cache',
          'Expires': '0',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch balance: ${response.statusText}`);
      }

      const subgraphResponse = await response.json();
      const balances = Array.isArray(subgraphResponse?.balances) ? subgraphResponse.balances : [];

      const transformedBalance = {
        tokenBalances: balances.map((balance: any) => ({
          amount: balance.balance.toString(),
          token: {
            name: balance.symbol === "USDC"
              ? "USD Coin"
              : balance.symbol.startsWith("k")
                ? `Krypton ${balance.symbol.substring(1).toUpperCase()}`
                : balance.symbol,
            blockchain: "ETH-SEPOLIA",
            decimals: balance.decimals,
            isNative: balance.symbol === "ETH" || balance.symbol === "ETH-SEPOLIA",
            symbol: balance.symbol,
            tokenAddress: balance.address,
            standard: (balance.symbol === "ETH" || balance.symbol === "ETH-SEPOLIA") ? undefined : "ERC20",
          },
        })),
        // Add timestamp to force React to recognize this as a new object
        _fetchedAt: Date.now(),
      };

      setBalance(transformedBalance);

    } catch (err) {
      console.error('Failed to fetch balance from subgraph:', err);
      setError('Failed to fetch balance.');
    } finally {
      if (isBackground) {
        setBalanceRefreshing(false);
      } else {
        setBalanceLoading(false);
      }
      balanceFetchInProgressRef.current = false;
      // Stop flickering when balance request completes.
      setBalanceFlickering(false);
    }
  }, []);

  /**
   * Background hydration: fetch initial transaction history only.
   * Balance is fetched separately via fetchBalance for faster first paint.
   */
  const fetchInitialTransactions = useCallback(async (
    _address: string,
    username: string,
    options?: { background?: boolean }
  ) => {
    const isBackground = options?.background === true;
    if (!isBackground) setBalanceLoading(true);

    try {
      if (!username) return;
      const response = await kryptonWeb3Api.get(
        `/subgraph/transactions/${encodeURIComponent(username)}?limit=10&skip=0`
      );
      if (response?.data) {
        setInitialTransactions(response.data);
      }
    } catch (err) {
      console.error('Failed initial transactions fetch:', err);
      if (!isBackground) {
        setError('Failed to load wallet data.');
      }
    } finally {
      if (!isBackground) setBalanceLoading(false);
      balanceFetchInProgressRef.current = false;
    }
  }, []);

  useEffect(() => {
    const userData = localStorage.getItem('userData');
    if (!userData) {
      router.push('/');
      return;
    }
    try {
      const data = JSON.parse(userData);
      setAccountData(data);
      setKycStatus(data.kyc_status || null);

      if (data.user_id) {
        fetchUserData(data.user_id);
      }

      if (data.wallet_address) {
        // Fast path: render wallet with live balance first.
        fetchBalance(data.wallet_address, { background: false });

        // Background hydration: seed transactions/rates without blocking first paint.
        if (data.username) {
          fetchInitialTransactions(data.wallet_address, data.username, {
            background: true,
          });
        }
      }
    } catch (err) {
      setError('Invalid user data.');
    } finally {
      setLoading(false);
    }
  }, [router, fetchBalance, fetchInitialTransactions]);

  // Update fetchBalance ref when it changes
  useEffect(() => {
    fetchBalanceRef.current = fetchBalance;
  }, [fetchBalance]);

  /**
   * Called when all active transactions complete (from BalanceCard/ActiveTransactions).
   * Triggers explicit backend polling via websocket wait before fetching logic.
   */
  const handleTransactionsComplete = useCallback((_txHash?: string) => {
    // Don't fetch balance from API — wait for WebSocket balance_update event
    // or user page reload to avoid hitting rate-limited subgraph.
    if (sawWsBalanceUpdateRef.current) {
      setBalanceCardRefresh(prev => !prev);
    }
  }, []);

  const handleLogout = async () => {
    try {
      const app = getFirebaseApp();
      if (app) {
        const auth = getAuth(app);
        await signOut(auth);
      }
      localStorage.removeItem('userData');

      router.push('/');
    } catch (err) {
      console.error('Logout error:', err);
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API not available (e.g. insecure context) - silently skip
    }
  };

  const handleSetUsername = async () => {
    if (!username.trim()) {
      setUsernameError("Username cannot be empty");
      return;
    }
    const cleanUsername = username.replace(/^@/, '');
    if (cleanUsername.length < 3) {
      setUsernameError("Username must be at least 3 characters long");
      return;
    }
    if (cleanUsername.length > 20) {
      setUsernameError("Username must be less than 20 characters");
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(cleanUsername)) {
      setUsernameError("Username can only contain letters, numbers, and underscores");
      return;
    }
    setUsernameLoading(true);
    setUsernameError(null);
    setUsernameSuccess(null);

    try {
      const response = await api.post("/api/v1/set_username", {
        user_id: accountData.user_id,
        username: cleanUsername.trim()
      });
      setUsernameSuccess(`Username set to @${cleanUsername.trim()} successfully!`);
      setShowUsernameForm(false);
      setUsername("");
      const updatedAccountData = {
        ...accountData,
        username: cleanUsername.trim()
      };
      setAccountData(updatedAccountData);
      localStorage.setItem('userData', JSON.stringify(updatedAccountData));

    } catch (err) {
      setUsernameError(parseErrorMessage(err, "Failed to set username"));
    } finally {
      setUsernameLoading(false);
    }
  };

  const handleCancelUsername = () => {
    setShowUsernameForm(false);
    setUsername("");
    setUsernameError(null);
    setUsernameSuccess(null);
  };

  const handleSendUSDC = async () => {
    if (!receiverUsername.trim()) {
      setSendError("Receiver username is required");
      return;
    }
    if (!sendAmount.trim() || parseFloat(sendAmount) <= 0) {
      setSendError("Please enter a valid amount");
      return;
    }
    const amount = parseFloat(sendAmount);
    if (isNaN(amount)) {
      setSendError("Please enter a valid number");
      return;
    }
    setSendLoading(true);
    setSendError(null);
    setSendSuccess(null);

    try {
      const response = await kryptonWeb3Api.post("/erc20/send-usdc", {
        sender_user_id: accountData.user_id,
        receiver_username: receiverUsername.trim(),
        amount: amount
      });
      setSendSuccess(`Successfully sent $${amount} USDC to @${receiverUsername.trim()}`);
      setReceiverUsername("");
      setSendAmount("");

      // Don't immediately fetch balance - wait for WebSocket webhook to trigger refresh
      // The webhook will arrive when Circle confirms the transaction
      // This prevents fetching stale balance before transaction is confirmed
      setTransactionHistoryRefresh(prev => prev + 1);

    } catch (err) {
      setSendError(parseErrorMessage(err, "Failed to send USDC"));
    } finally {
      setSendLoading(false);
    }
  };

  const handleCancelSendUSDC = () => {
    setShowSendForm(false);
    setReceiverUsername("");
    setSendAmount("");
    setSendError(null);
    setSendSuccess(null);
    setSendLoading(false);
  };

  const handleCancelSendERC20 = (autoClose?: boolean) => {
    setShowSendERC20Form(false);
    setReceiverUsername("");
    setSendAmount("");
    // Only switch to Transaction History tab on auto-close (success), not on manual X button close
    if (autoClose) {
      balanceCardRef.current?.showTransactionHistory();
      setTransactionHistoryRefresh(prev => prev + 1);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen w-full bg-[hsl(var(--brand-bg))] dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-[hsl(var(--brand-accent))] border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">
            Loading wallet...
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full bg-[hsl(var(--brand-bg))] dark overflow-x-hidden flex items-center justify-center p-4">
        <div className="text-center max-w-md mx-auto">
          <div className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-8 shadow-2xl">
            <div className="mb-6">
              <div className="w-16 h-16 bg-gradient-to-br from-red-500 to-red-600 rounded-full flex items-center justify-center mx-auto mb-4">
                <FaTimes className="text-white text-2xl" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-3">Error Loading Wallet</h2>
              <p className="text-zinc-400 leading-relaxed">{error}</p>
            </div>
            <button
              onClick={() => router.push('/')}
              className="w-full bg-gradient-to-r from-red-600 to-red-700 hover:from-red-700 hover:to-red-800 text-white font-semibold py-3 px-6 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
            >
              Go Back to Login
            </button>
          </div>
        </div>
      </div>
    );
  }

  const welcomeMargin = config.welcomeMessageMargin || '';

  return (
    <>
      {kycModalVisible && kycStatus !== 'approved' && kycAccessToken && (
        <SumsubKYCModal
          accessToken={kycAccessToken}
          visible={kycModalVisible}
          onClose={() => handleKycModalClose(accountData?.user_id)}
          applicantEmail={accountData?.email}
        />
      )}
      <div className="min-h-screen w-full bg-[hsl(var(--brand-bg))] dark overflow-x-hidden">
        <WalletHeader
          accountData={accountData}
          onLogout={handleLogout}
          onMenuToggle={() => setShowMenu(!showMenu)}
        />
        <HamburgerMenu
          visible={showMenu}
          onClose={() => setShowMenu(false)}
          onLogout={handleLogout}
          accountData={accountData}
          onCopyAddress={() => copyToClipboard(accountData?.wallet_address || '')}
        />
        <div className="container mx-auto px-4 py-8 max-w-4xl">
          {/* WebSocket Notification */}
          {webhookNotification && config.showWebhookNotification && (
            <div className="fixed top-4 right-4 z-50 bg-green-600 text-white px-4 py-2 rounded-lg shadow-lg animate-pulse">
              {webhookNotification}
            </div>
          )}
          {!accountData?.username && (
            <UsernameCard
              accountData={accountData}
              showUsernameForm={showUsernameForm}
              username={username}
              usernameLoading={usernameLoading}
              usernameError={usernameError}
              usernameSuccess={usernameSuccess}
              setShowUsernameForm={setShowUsernameForm}
              setUsername={setUsername}
              handleSetUsername={handleSetUsername}
              handleCancelUsername={handleCancelUsername}
            />
          )}
          {accountData?.username && (
            <div className={`text-center mb-8 ${welcomeMargin}`}>
              <span className="text-white text-3xl">Hello </span>
              <span className="text-[hsl(var(--brand-accent))] text-3xl">@{accountData.username}</span>
              <div className="flex items-center justify-center gap-1.5 text-base" aria-live="polite">
                {config.showKycStatusBadge ? (
                  kycStatus === 'approved' ? (
                    <>
                      <span className="text-zinc-300">Active</span>
                      <FaCheck className="text-green-500 shrink-0" />
                    </>
                  ) : (
                    <span className="text-zinc-300">Verification required</span>
                  )
                ) : (
                  <>
                    <span className="text-zinc-300">Active</span>
                    <FaCheck className="text-green-500 shrink-0" />
                  </>
                )}
              </div>
            </div>
          )}
          <BalanceCard
            ref={balanceCardRef}
            balance={balance}
            error={error}
            accountData={accountData}
            showTransactions={showTransactions}
            setShowTransactions={setShowTransactions}
            transactionHistoryRefresh={transactionHistoryRefresh}
            kycStatus={kycStatus}
            onKycClick={() => openKycModal(accountData?.user_id)}
            onRefreshKyc={() => accountData?.user_id && fetchUserData(accountData.user_id)}
            onCheckKycStatus={() => accountData?.user_id && checkKycStatus(accountData.user_id)}
            kycChecking={kycChecking}
            kycMessage={kycMessage}
            onBuyClick={() => setShowTransakModal(true)}
            onSkipKyc={() => accountData?.user_id && skipKyc(accountData.user_id)}
            balanceLoading={balanceLoading}
            balanceCardRefresh={balanceCardRefresh}
            balanceRefreshing={balanceRefreshing}
            balanceFlickering={balanceFlickering}
            onTransactionsComplete={handleTransactionsComplete}
            initialTransactions={initialTransactions}
            wsConnectionStatus={connectionStatus}
            txHistoryForceRefresh={txHistoryForceRefresh}
            latestWsTransaction={latestWsTransaction}
            latestWsTransactionVersion={latestWsTransactionVersion}
            latestWsActiveEvent={latestWsActiveEvent}
            latestWsActiveEventVersion={latestWsActiveEventVersion}
          />
          {accountData?.username && kycStatus === 'approved' && (
            <>
              <div className="flex flex-row gap-3 mb-8 w-full mt-8 items-center justify-center">
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (config.useERC20Modal) {
                      setShowSendERC20Form(true);
                    } else {
                      setShowSendForm(true);
                    }
                  }}
                  className="p-0 border-0 bg-transparent cursor-pointer focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity min-h-[56px] min-w-[140px] rounded-full"
                  aria-label="Pay"
                >
                  <img
                    src="/Pay.svg"
                    alt="Pay"
                    className="h-14 w-auto pointer-events-none"
                  />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    router.push(config.growRoute);
                  }}
                  className="p-0 border-0 bg-transparent cursor-pointer focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity min-h-[56px] min-w-[140px] rounded-full"
                  aria-label="Grow"
                >
                  <img
                    src="/Grow.svg"
                    alt="Grow"
                    className="h-14 w-auto pointer-events-none"
                  />
                </button>
              </div>
              {config.renderAdditionalActionButtons && (
                <div className="flex flex-row gap-4 w-full justify-center mt-4">
                  {config.renderAdditionalActionButtons((path) => router.push(path))}
                </div>
              )}
            </>
          )}
          {/* Chat component - conditionally rendered based on config */}
          {config.renderChatComponent && (
            <>
              {config.showChatToggle ? (
                <>
                  {showClarkChat && (
                    <div>
                      {config.renderChatComponent({
                        userId: accountData?.user_id,
                        onBalanceRefresh: () => {},
                        onBalanceFlicker: () => {},
                        onTransactionRefresh: () => {
                          setTransactionHistoryRefresh(prev => prev + 1);
                        },
                      })}
                    </div>
                  )}
                  {!showClarkChat && (
                    <div className="flex justify-end mt-8 mb-4">
                      <button
                        type="button"
                        onClick={() => setShowClarkChat(true)}
                        className="p-0 border-0 bg-transparent cursor-pointer inline-flex focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity min-h-[48px] min-w-[120px] rounded-full"
                        aria-label="Open Clark Chat"
                      >
                        <img
                          src="/Ask Clark.svg"
                          alt="Ask Clark"
                          className="h-12 w-auto max-w-[8rem] md:w-11/12 md:h-auto md:max-w-none md:object-contain"
                        />
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div>
                  {config.renderChatComponent({
                    userId: accountData?.user_id,
                    onBalanceRefresh: () => {},
                    onBalanceFlicker: () => {},
                    onTransactionRefresh: () => {
                      setTransactionHistoryRefresh(prev => prev + 1);
                    },
                  })}
                </div>
              )}
            </>
          )}
        </div>
        {showSendForm && (
          <SendUSDCModal
            visible={showSendForm}
            onClose={handleCancelSendUSDC}
            receiverUsername={receiverUsername}
            setReceiverUsername={setReceiverUsername}
            sendAmount={sendAmount}
            setSendAmount={setSendAmount}
            sendLoading={sendLoading}
            sendError={sendError}
            sendSuccess={sendSuccess}
            onSend={handleSendUSDC}
          />
        )}
        {showSendERC20Form && (
          <SendERC20Modal
            visible={showSendERC20Form}
            onClose={handleCancelSendERC20}
            userAddress={accountData?.wallet_address}
            userId={accountData?.user_id}
            username={accountData?.username}
            balance={balance}
          />
        )}
        {showTransakModal && (
          <BuyUSDCModal
            fiatData={[]}
            onClose={() => setShowTransakModal(false)}
            walletAddress={accountData?.wallet_address}
          />
        )}
      </div>
    </>
  );
}

