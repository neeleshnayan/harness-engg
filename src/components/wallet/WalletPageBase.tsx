"use client";

import React, { useState, useEffect, ReactNode, useCallback, useRef } from "react";
import { getAuth, signOut } from "firebase/auth";
import { useRouter } from "next/navigation";
import { FaArrowUp, FaCheck, FaTimes } from "react-icons/fa";
import { getFirebaseApp } from "@/lib/firebaseClient";
import UsernameCard from "@/components/wallet/UsernameCard";
import BalanceCard from "@/components/wallet/BalanceCard";
import SendUSDCModal from "@/components/wallet/SendUSDCModal";
import HamburgerMenu from "@/components/wallet/HamburgerMenu";
import api from "@/lib/api";
import BuyUSDCModal from "@/components/wallet/BuyUSDCModal";
import WalletHeader from "@/components/wallet/WalletHeader";
import SumsubKYCModal from "@/components/wallet/SumsubKYCModal";
import axios from "axios";
import { useWebSocket } from "@/hooks/useWebSocket";
import SendERC20Modal from "@/components/wallet/SendERC20Modal";

// Configuration: Delay before fetching balance after webhook event (in milliseconds)
// Increase this if Circle API hasn't updated the balance yet when webhook arrives
const WEBHOOK_BALANCE_REFRESH_DELAY_MS = 1000; // 1 second

import {
  setUserContext,
  clearUserContext,
  captureError,
  captureAPIError,
  captureWebSocketError,
  captureWalletError,
  captureKYCError,
  addBreadcrumb,
} from "@/lib/sentry";

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
  const [sendCurrency, setSendCurrency] = useState<string>("");
  const [sendAmount, setSendAmount] = useState<string>("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);
  const [sendSuccess, setSendSuccess] = useState<string | null>(null);
  const [sendERC20Loading, setSendERC20Loading] = useState(false);
  const [sendERC20Error, setSendERC20Error] = useState<string | null>(null);
  const [sendERC20Success, setSendERC20Success] = useState<string | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [showTransactions, setShowTransactions] = useState(false);
  const [refreshingBalance, setRefreshingBalance] = useState(false);
  const [showTransakModal, setShowTransakModal] = useState(false);
  const [transactionHistoryRefresh, setTransactionHistoryRefresh] = useState(false);
  const [kycModalVisible, setKycModalVisible] = useState(false);
  const [kycAccessToken, setKycAccessToken] = useState<string | null>(null);
  const [kycStatus, setKycStatus] = useState<string | null>(null);
  const [kycChecking, setKycChecking] = useState(false);
  const [kycMessage, setKycMessage] = useState<string | null>(null);
  const [fiatData, setFiatData] = useState<any>([]);
  const [webhookNotification, setWebhookNotification] = useState<string | null>(null);
  const [balanceCardRefresh, setBalanceCardRefresh] = useState(false);
  const [balanceRefreshing, setBalanceRefreshing] = useState(false);
  const [balanceFlickering, setBalanceFlickering] = useState(false);
  const [showClarkChat, setShowClarkChat] = useState(false);
  const router = useRouter();

  // Refs to prevent excessive balance fetches
  const balanceFetchInProgressRef = useRef(false);
  const balanceDebounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const accountDataRef = useRef(accountData);
  const showTransactionsRef = useRef(showTransactions);
  const fetchBalanceRef = useRef<((address: string, options?: { background?: boolean }) => Promise<void>) | null>(null);
  const processedWebhookEventsRef = useRef<Set<string>>(new Set()); // Track processed webhook event IDs

  // Update refs when state changes
  useEffect(() => {
    accountDataRef.current = accountData;
  }, [accountData]);

  useEffect(() => {
    showTransactionsRef.current = showTransactions;
  }, [showTransactions]);

  // Debounced balance fetch function
  const debouncedFetchBalance = useCallback((address: string, options?: { background?: boolean }, delay: number = 500) => {
    // Clear existing timer
    if (balanceDebounceTimerRef.current) {
      clearTimeout(balanceDebounceTimerRef.current);
      balanceDebounceTimerRef.current = null;
    }

    // Set new timer
    const timerId = `timer-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    const timerStartTime = Date.now();
    console.log(`⏱️ [${timerId}] Debounce timer started at ${new Date().toISOString()} - Will wait ${delay}ms before fetching, Address: ${address}`);
    console.log(`⏱️ [${timerId}] Expected fetch time: ${new Date(Date.now() + delay).toISOString()}`);

    balanceDebounceTimerRef.current = setTimeout(() => {
      const actualDelay = Date.now() - timerStartTime;
      console.log(`⏱️ [${timerId}] Debounce timer expired at ${new Date().toISOString()} - Actual delay: ${actualDelay}ms (expected: ${delay}ms)`);
      console.log(`⏱️ [${timerId}] Debounce timer expired - Checking if fetch should proceed...`);

      if (!balanceFetchInProgressRef.current && address && fetchBalanceRef.current) {
        console.log(`✅ [${timerId}] Conditions met - Proceeding with balance fetch`);
        balanceFetchInProgressRef.current = true;
        fetchBalanceRef.current(address, options)
          .then(() => {
            console.log(`✅ [${timerId}] Debounced fetch completed successfully`);
            // Ensure refreshing state is cleared after successful fetch
            if (options?.background) {
              setBalanceRefreshing(false);
            }
          })
          .catch((err) => {
            console.error(`❌ [${timerId}] Debounced fetch failed:`, err);
            // Ensure refreshing state is cleared even on error
            if (options?.background) {
              setBalanceRefreshing(false);
            }
          })
          .finally(() => {
            balanceFetchInProgressRef.current = false;
            console.log(`🏁 [${timerId}] Debounced fetch finished - InProgress flag cleared`);
          });
      } else {
        // If fetch was skipped (already in progress or missing address/function), clear refreshing state
        console.log(`⏭️ [${timerId}] Debounced fetch SKIPPED - Conditions:`, {
          inProgress: balanceFetchInProgressRef.current,
          hasAddress: !!address,
          hasFetchFunction: !!fetchBalanceRef.current
        });
        if (options?.background) {
          setBalanceRefreshing(false);
          console.log(`🏁 [${timerId}] Refreshing state cleared after skip`);
        }
      }
      balanceDebounceTimerRef.current = null;
    }, delay);
  }, []);

  // WebSocket message handler - stabilized with useCallback and refs
  const handleWebSocketMessage = useCallback((message: any) => {
    if (message.type === 'circle_webhook') {
      const eventId = message.event_id;

      // Deduplicate: Skip if we've already processed this webhook event
      if (eventId && processedWebhookEventsRef.current.has(eventId)) {
        console.log(`Skipping duplicate webhook event: ${eventId}`);
        return;
      }

      // Mark this event as processed
      if (eventId) {
        processedWebhookEventsRef.current.add(eventId);
        // Clean up old event IDs after 5 minutes to prevent memory leak
        setTimeout(() => {
          processedWebhookEventsRef.current.delete(eventId);
        }, 5 * 60 * 1000);
      }

      // Show notification to user
      let notificationText = '';
      if (message.event_type === 'INBOUND') {
        notificationText = 'New transaction received! Refreshing balance...';
      } else if (message.event_type === 'OUTBOUND') {
        notificationText = 'Transaction sent! Refreshing balance...';
      } else if (message.event_type === 'wallet.created') {
        notificationText = 'Wallet created! Refreshing balance...';
      } else if (message.event_type === 'wallet.updated') {
        notificationText = 'Wallet updated! Refreshing balance...';
      }

      if (notificationText && config.showWebhookNotification) {
        setWebhookNotification(notificationText);
        setTimeout(() => setWebhookNotification(null), 5000);
      }

      // Only refresh balance when WebSocket message is received and address matches
      const currentAccountData = accountDataRef.current;
      const webhookAddress = message.address?.toLowerCase()?.trim();
      const walletAddress = currentAccountData?.wallet_address?.toLowerCase()?.trim();

      // For wallet.created and wallet.updated, refresh balance if we have a wallet address
      // (even if webhook doesn't have address, these events are about the user's own wallet)
      const shouldRefreshBalance =
        (walletAddress && webhookAddress && webhookAddress === walletAddress) || // Address matches
        (walletAddress && (message.event_type === 'wallet.created' || message.event_type === 'wallet.updated')); // Wallet events

      if (shouldRefreshBalance) {
        console.log(`✅ Processing webhook for ${message.event_type} - Address: ${walletAddress}, Event ID: ${eventId}`);
        console.log(`⏳ Will wait ${WEBHOOK_BALANCE_REFRESH_DELAY_MS}ms before fetching balance to allow Circle API to update...`);

        // Use configurable delay to allow Circle API time to update balance after webhook
        const debounceDelay = WEBHOOK_BALANCE_REFRESH_DELAY_MS;

        // Clear any existing debounce timer (this resets the delay if multiple webhooks arrive quickly)
        if (balanceDebounceTimerRef.current) {
          console.log(`🔄 Clearing existing debounce timer - will restart with ${debounceDelay}ms delay`);
          clearTimeout(balanceDebounceTimerRef.current);
          balanceDebounceTimerRef.current = null;
        }

        // Set refreshing state to show UI feedback, but actual fetch will happen after delay
        setBalanceRefreshing(true);
        console.log(`📊 Balance refreshing state set to true - UI will show "Refreshing..." but API call will wait ${debounceDelay}ms`);

        // Use debounced fetch to prevent excessive calls - this will wait the full delay
        debouncedFetchBalance(currentAccountData.wallet_address, { background: true }, debounceDelay);

        // Safety timeout: Clear refreshing state after 5 seconds if it's still stuck
        setTimeout(() => {
          setBalanceRefreshing(prev => {
            if (prev) {
              console.warn('⚠️ Balance refreshing state was stuck - forcing clear after 5s timeout');
              return false;
            }
            return prev;
          });
        }, 5000);

        // Trigger BalanceCard refresh by toggling the refresh flag
        setBalanceCardRefresh(prev => !prev);
      } else {
        console.log(`❌ Webhook address mismatch - Webhook: ${webhookAddress || 'EMPTY'}, Wallet: ${walletAddress || 'EMPTY'}, Event ID: ${eventId}, Type: ${message.event_type}`);
      }

      // Also refresh transaction history if it's open
      if (showTransactionsRef.current) {
        setTransactionHistoryRefresh(prev => !prev);
      }
    }
  }, [config.showWebhookNotification, debouncedFetchBalance]);

  // WebSocket open handler - stabilized
  const handleWebSocketOpen = useCallback(() => {
    if (config.showWebhookNotification) {
      setWebhookNotification('WebSocket connected successfully!');
      setTimeout(() => setWebhookNotification(null), 3000);
    }
    addBreadcrumb('WebSocket connected', 'websocket', { status: 'connected' });
  }, [config.showWebhookNotification]);

  // WebSocket close handler - stabilized
  const handleWebSocketClose = useCallback(() => {
    addBreadcrumb('WebSocket disconnected', 'websocket', { status: 'disconnected' });
  }, []);

  // Ref to track connection status for error handler
  const connectionStatusRef = useRef<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');

  // WebSocket error handler - stabilized with ref
  const handleWebSocketError = useCallback((error: Event) => {
    console.error('WebSocket error:', error);
    console.error('WebSocket error details:', {
      error,
      errorType: error.type,
      errorTarget: error.target,
      timestamp: new Date().toISOString()
    });

    // Capture WebSocket error with Sentry
    captureWebSocketError(error, {
      status: connectionStatusRef.current,
      url: `${process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL.replace('https://', 'wss://').replace('http://', 'ws://') : 'wss://api.kryptonfund.com'}/api/v1/ws`
    });
  }, []);

  // WebSocket connection for real-time webhook updates
  const wsUrl = `${process.env.NEXT_PUBLIC_API_URL ? process.env.NEXT_PUBLIC_API_URL.replace('https://', 'wss://').replace('http://', 'ws://') : 'wss://api.kryptonfund.com'}/api/v1/ws`;
  const { isConnected: wsConnected, connectionStatus, reconnect: wsReconnect } = useWebSocket(
    wsUrl,
    {
      onMessage: handleWebSocketMessage,
      onOpen: handleWebSocketOpen,
      onClose: handleWebSocketClose,
      onError: handleWebSocketError
    }
  );

  // Update connection status ref when it changes
  useEffect(() => {
    connectionStatusRef.current = connectionStatus;
  }, [connectionStatus]);

  // Cleanup debounce timer and reset processed events on unmount
  useEffect(() => {
    return () => {
      if (balanceDebounceTimerRef.current) {
        clearTimeout(balanceDebounceTimerRef.current);
      }
      // Clear processed events set on unmount
      processedWebhookEventsRef.current.clear();
    };
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

      // Set user context in Sentry
      setUserContext(data);

      // Fetch fresh KYC status from backend instead of relying on localStorage
      if (data.user_id) {
        fetchUserData(data.user_id);
      }
      if (data.wallet_address) {
        fetchBalance(data.wallet_address, { background: config.pageType === 'business' });
      }
      // Don't show error if wallet address is missing - it will be fetched by fetchUserData
    } catch (err) {
      const error = err as Error;
      setError('Invalid user data.');
      captureError(error, { context: 'parsing_user_data', userData });
    } finally {
      setLoading(false);
    }
  }, [router]);

  const fetchUserData = async (userId: string) => {
    try {
      setUserDataLoading(true);
      addBreadcrumb('Fetching user data', 'api', { user_id: userId });

      const response = await api.get(`/api/v1/user/${userId}`);
      const userData = response.data;
      setKycStatus(userData.kyc_status || 'pending');

      var res = await axios.get('https://api-stg.transak.com/fiat/public/v1/currencies/fiat-currencies?apiKey=f4c10825-55fd-4ccc-bd3f-40fc021468e5');
      var fiatDataMap = []
      for (const currency of res.data.response) {
        fiatDataMap.push({
          name: currency.name,
          code: currency.symbol,
          symbol: currency.logoSymbol
        });
      }
      setFiatData(fiatDataMap);
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

      setAccountData(updatedData);
      localStorage.setItem('userData', JSON.stringify(updatedData));

      // Update Sentry user context with fresh data
      setUserContext(updatedData);

      // If we have a wallet address and it's not already being fetched, fetch balance
      // Only fetch if balance is null (initial load) or if wallet address changed
      if (updatedData.wallet_address && (!balance || accountDataRef.current?.wallet_address !== updatedData.wallet_address)) {
        fetchBalance(updatedData.wallet_address, { background: true });
      }

      // If user has username but KYC is not approved, check status
      if (updatedData.username && userData.kyc_status !== 'approved') {
        setTimeout(() => {
          checkKycStatus(userId);
        }, 1000);
      }

      addBreadcrumb('User data fetched successfully', 'api', {
        user_id: userId,
        kyc_status: userData.kyc_status,
        has_wallet: !!updatedData.wallet_address
      });

    } catch (err) {
      console.error('Failed to fetch user data:', err);
      captureAPIError(err, `/api/v1/user/${userId}`, { user_id: userId });
      // Fallback to localStorage data
      const data = JSON.parse(localStorage.getItem('userData') || '{}');
      setKycStatus(data.kyc_status || 'pending');
    } finally {
      setUserDataLoading(false);
    }
  };

  const fetchBalance = useCallback(async (
    address: string,
    options?: { background?: boolean }
  ) => {
    const isBackground = options?.background === true;
    const fetchId = `fetch-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;

    console.log(`📊 [${fetchId}] Balance fetch STARTED - Address: ${address}, Background: ${isBackground}`);

    // Prevent duplicate concurrent fetches
    if (balanceFetchInProgressRef.current && options?.background) {
      console.log(`⏭️ [${fetchId}] Balance fetch SKIPPED - Already in progress`);
      return;
    }

    // Set fetching flag
    if (isBackground) {
      balanceFetchInProgressRef.current = true;
    }

    try {
      if (!isBackground) {
        setBalanceLoading(true);
      }
      addBreadcrumb('Fetching wallet balance', 'api', { wallet_address: address, background: isBackground });

      console.log(`🔄 [${fetchId}] Calling API: /api/v1/wallet_balance/${address}`);
      const response = await api.get(`/api/v1/wallet_balance/${address}`);

      // Log balance data received
      const balanceData = response.data;
      if (balanceData && balanceData.tokenBalances) {
        const tokenCount = balanceData.tokenBalances.length;
        console.log(`✅ [${fetchId}] Balance API response received - ${tokenCount} token(s) found`);

        // Log each token balance
        balanceData.tokenBalances.forEach((tb: any, idx: number) => {
          const symbol = tb?.token?.symbol || 'UNKNOWN';
          const amount = tb?.amount || '0';
          console.log(`  💰 [${fetchId}] Token ${idx + 1}: ${symbol} = ${amount}`);
        });
      } else {
        console.log(`✅ [${fetchId}] Balance API response received - No tokenBalances array found`, balanceData);
      }

      // Log previous balance for comparison
      const previousBalance = balance;
      if (previousBalance && previousBalance.tokenBalances) {
        console.log(`📊 [${fetchId}] Previous balance had ${previousBalance.tokenBalances.length} token(s)`);
      } else {
        console.log(`📊 [${fetchId}] No previous balance data`);
      }

      // Set the new balance
      console.log(`💾 [${fetchId}] Setting new balance in state...`);
      setBalance(balanceData);
      console.log(`✅ [${fetchId}] Balance state updated successfully`);

      addBreadcrumb('Balance fetched successfully', 'api', {
        wallet_address: address,
        background: isBackground,
        balance: response.data
      });

    } catch (err) {
      console.error(`❌ [${fetchId}] Balance fetch FAILED:`, err);
      setError('Failed to fetch balance.');
      captureAPIError(err, `/api/v1/wallet_balance/${address}`, { wallet_address: address, background: isBackground });
    } finally {
      if (isBackground) {
        setBalanceRefreshing(false);
        balanceFetchInProgressRef.current = false;
        console.log(`🏁 [${fetchId}] Background fetch completed - Refreshing state cleared`);
        // Stop flickering when balance refresh is complete
        if (balanceFlickering) {
          setBalanceFlickering(false);
          console.log(`🏁 [${fetchId}] Balance flickering stopped`);
        }
      } else {
        setBalanceLoading(false);
        balanceFetchInProgressRef.current = false;
        console.log(`🏁 [${fetchId}] Foreground fetch completed - Loading state cleared`);
        // Stop flickering when balance loading is complete
        if (balanceFlickering) {
          setBalanceFlickering(false);
          console.log(`🏁 [${fetchId}] Balance flickering stopped`);
        }
      }
    }
  }, [balanceFlickering, balance]);

  // Update fetchBalance ref when it changes
  useEffect(() => {
    fetchBalanceRef.current = fetchBalance;
  }, [fetchBalance]);

  // Log when balance state changes
  useEffect(() => {
    if (balance) {
      const tokenCount = balance.tokenBalances?.length || 0;
      console.log(`🔄 Balance state CHANGED - ${tokenCount} token(s) in balance`);
      if (balance.tokenBalances) {
        balance.tokenBalances.forEach((tb: any, idx: number) => {
          const symbol = tb?.token?.symbol || 'UNKNOWN';
          const amount = tb?.amount || '0';
          console.log(`  💰 Balance Token ${idx + 1}: ${symbol} = ${amount}`);
        });
      }
    } else {
      console.log(`🔄 Balance state CHANGED - Balance is now null/undefined`);
    }
  }, [balance]);

  const handleLogout = async () => {
    try {
      const app = getFirebaseApp();
      if (app) {
        const auth = getAuth(app);
        await signOut(auth);
      }
      localStorage.removeItem('userData');

      // Clear Sentry user context on logout
      clearUserContext();

      addBreadcrumb('User logged out', 'auth', { user_id: accountData?.user_id });

      router.push('/');
    } catch (err) {
      const error = err as Error;
      captureError(error, { context: 'logout', user_id: accountData?.user_id });
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      addBreadcrumb('Address copied to clipboard', 'wallet', { address: text });
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      addBreadcrumb('Address copied to clipboard (fallback)', 'wallet', { address: text });
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
      addBreadcrumb('Setting username', 'api', {
        user_id: accountData.user_id,
        username: cleanUsername.trim()
      });

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

      // Update Sentry user context
      setUserContext(updatedAccountData);

      addBreadcrumb('Username set successfully', 'api', {
        user_id: accountData.user_id,
        username: cleanUsername.trim()
      });

    } catch (err: any) {
      let errorMsg = err.response?.data?.detail || "Failed to set username";
      if (typeof errorMsg === 'object' && errorMsg !== null) {
        if (Array.isArray(errorMsg)) {
          errorMsg = errorMsg.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else if (errorMsg.msg) {
        } else {
          errorMsg = JSON.stringify(errorMsg);
        }
      }
      setUsernameError(errorMsg);

      captureAPIError(err, '/api/v1/set_username', {
        user_id: accountData.user_id,
        username: cleanUsername.trim()
      });
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
      addBreadcrumb('Sending USDC', 'api', {
        sender_id: accountData.user_id,
        receiver: receiverUsername.trim(),
        amount: amount
      });

      const response = await api.post("/api/v1/send_usdc", {
        sender_user_id: accountData.user_id,
        receiver_username: receiverUsername.trim(),
        amount: amount
      });
      setSendSuccess(`Successfully sent $${amount} USDC to @${receiverUsername.trim()}`);
      setReceiverUsername("");
      setSendAmount("");

      // Trigger balance flickering effect
      setBalanceFlickering(true);

      // Don't immediately fetch balance - wait for WebSocket webhook to trigger refresh
      // The webhook will arrive when Circle confirms the transaction
      // This prevents fetching stale balance before transaction is confirmed
      setTransactionHistoryRefresh(prev => !prev);

      addBreadcrumb('USDC sent successfully', 'api', {
        sender_id: accountData.user_id,
        receiver: receiverUsername.trim(),
        amount: amount
      });

    } catch (err: any) {
      let errorMsg = err.response?.data?.detail || "Failed to send USDC";
      if (typeof errorMsg === 'object' && errorMsg !== null) {
        if (Array.isArray(errorMsg)) {
          errorMsg = errorMsg.map(e => e.msg || JSON.stringify(e)).join('; ');
        } else if (errorMsg.msg) {
        } else {
          errorMsg = JSON.stringify(errorMsg);
        }
      }
      setSendError(errorMsg);

      captureWalletError(err, 'send_usdc', amount.toString(), receiverUsername.trim());
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

  const handleCancelSendERC20 = () => {
    setShowSendERC20Form(false);
    setReceiverUsername("");
    setSendAmount("");
    setSendCurrency("");
    setSendERC20Error(null);
    setSendERC20Success(null);
    setSendERC20Loading(false);
  };

  const openKycModal = async (userId: string) => {
    try {
      addBreadcrumb('Opening KYC modal', 'kyc', { user_id: userId });

      // 1. Create applicant if needed
      await api.post('/api/v1/kyc/applicant', { user_id: userId });

      // 2. Get access token
      const tokenRes = await api.post('/api/v1/kyc/access-token', { user_id: userId });
      setKycAccessToken(tokenRes.data.token || tokenRes.data.accessToken || tokenRes.data.access_token);
      setKycModalVisible(true);

      addBreadcrumb('KYC modal opened successfully', 'kyc', { user_id: userId });

    } catch (err) {
      captureKYCError(err, 'open_modal', userId);
    }
  };

  const checkKycStatus = async (userId: string) => {
    setKycChecking(true);
    setKycMessage(null);

    try {
      addBreadcrumb('Checking KYC status', 'kyc', { user_id: userId });

      const response = await api.post(`/api/v1/kyc/check-status/${userId}`);

      if (response.data.status === 'success') {
        const newStatus = response.data.kyc_status;
        setKycStatus(newStatus);
        const updatedData = { ...accountData, kyc_status: newStatus };
        setAccountData(updatedData);
        localStorage.setItem('userData', JSON.stringify(updatedData));

        // Update Sentry user context
        setUserContext(updatedData);

        if (newStatus === 'approved') {
          setKycMessage('KYC verification completed successfully!');
          setTimeout(() => setKycMessage(null), 3000);
        } else if (newStatus === 'rejected') {
          setKycMessage('KYC verification was rejected. Please try again.');
          setTimeout(() => setKycMessage(null), 5000);
        } else {
          setKycMessage(`KYC status: ${newStatus}`);
          setTimeout(() => setKycMessage(null), 3000);
        }

        addBreadcrumb('KYC status checked', 'kyc', {
          user_id: userId,
          status: newStatus
        });

      } else {
        setKycMessage(response.data.message || 'Failed to check KYC status');
        setTimeout(() => setKycMessage(null), 5000);
      }
    } catch (err: any) {
      console.error('Failed to check KYC status:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to check KYC status');
      setTimeout(() => setKycMessage(null), 5000);

      captureKYCError(err, 'check_status', userId);
    } finally {
      setKycChecking(false);
    }
  };

  const skipKyc = async (userId: string) => {
    try {
      addBreadcrumb('Skipping KYC', 'kyc', { user_id: userId });

      // Use accountData.id as fallback if userId is not provided
      const actualUserId = userId || accountData?.id;

      if (!actualUserId) {
        console.error('No user ID provided for skip KYC');
        setKycMessage('No user ID found');
        return;
      }

      // Update KYC status to approved in the backend
      const response = await api.post(`/api/v1/kyc/skip/${actualUserId}`);

      if (response.data.status === 'success') {
        setKycStatus('approved');
        const updatedData = { ...accountData, kyc_status: 'approved' };
        setAccountData(updatedData);
        localStorage.setItem('userData', JSON.stringify(updatedData));
        setKycMessage('KYC skipped successfully');

        // Update Sentry user context
        setUserContext(updatedData);

        addBreadcrumb('KYC skipped successfully', 'kyc', { user_id: actualUserId });
      } else {
        setKycMessage(response.data.message || 'Failed to skip KYC');
      }
    } catch (err: any) {
      console.error('Failed to skip KYC:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to skip KYC');

      captureKYCError(err, 'skip_kyc', userId);
    } finally {
      // Clear message after 5 seconds
      setTimeout(() => setKycMessage(null), 5000);
    }
  };

  const pollKycStatus = async (userId: string) => {
    addBreadcrumb('Starting KYC status polling', 'kyc', { user_id: userId });

    // Poll user data for KYC status
    for (let i = 0; i < 15; i++) { // Increased attempts
      try {
        const res = await api.get(`/api/v1/user/${userId}`);
        const status = res.data.kyc_status;

        if (status === 'approved') {
          setKycStatus('approved');
          const updated = { ...accountData, kyc_status: 'approved' };
          setAccountData(updated);
          localStorage.setItem('userData', JSON.stringify(updated));
          setKycMessage('KYC verification completed successfully!');

          // Update Sentry user context
          setUserContext(updated);

          // Clear success message after 3 seconds
          setTimeout(() => setKycMessage(null), 3000);
          break;
        } else if (status === 'rejected') {
          setKycStatus('rejected');
          setKycMessage('KYC verification was rejected. Please try again.');
          // Clear error message after 5 seconds
          setTimeout(() => setKycMessage(null), 5000);
          break;
        } else {
          // Update status even if pending to ensure UI reflects current state
          setKycStatus(status || 'pending');
        }

        // Wait 2 seconds between checks (reduced from 3)
        await new Promise(r => setTimeout(r, 2000));
      } catch (err) {
        console.error(`Error polling KYC status (attempt ${i + 1}):`, err);
        // Don't break on first error, continue polling
        await new Promise(r => setTimeout(r, 2000));
      }
    }

    // If we've exhausted all attempts, try one final manual check
    try {
      const finalRes = await api.post(`/api/v1/kyc/check-status/${userId}`);
      if (finalRes.data.status === 'success') {
        const finalStatus = finalRes.data.kyc_status;
        setKycStatus(finalStatus);
        const updated = { ...accountData, kyc_status: finalStatus };
        setAccountData(updated);
        localStorage.setItem('userData', JSON.stringify(updated));

        // Update Sentry user context
        setUserContext(updated);

        if (finalStatus === 'approved') {
          setKycMessage('KYC verification completed successfully!');
          setTimeout(() => setKycMessage(null), 3000);
        }
      }
    } catch (err) {
      console.error('Error in final KYC status check:', err);
      captureKYCError(err, 'final_status_check', userId);
    }

    addBreadcrumb('KYC status polling completed', 'kyc', {
      user_id: userId,
      final_status: accountData?.kyc_status
    });
  };

  const handleKycModalClose = () => {
    setKycModalVisible(false);

    // Immediately check status once
    if (accountData?.user_id) {
      checkKycStatus(accountData.user_id);
    }

    // Add a small delay to allow webhook processing, then start polling
    setTimeout(() => {
      if (accountData?.user_id) {
        pollKycStatus(accountData.user_id);
      }
    }, 2000);
  };

  if (loading || userDataLoading || balanceLoading) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-4 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400 font-medium">
            {loading ? "Loading wallet..." : userDataLoading ? "Fetching user data..." : balanceLoading ? "Loading balance..." : "Loading..."}
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden flex items-center justify-center p-4">
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
      <SumsubKYCModal
        accessToken={kycAccessToken || ''}
        visible={kycModalVisible}
        onClose={handleKycModalClose}
        applicantEmail={accountData?.email}
      />
      <div className="min-h-screen w-full bg-gradient-to-br from-black via-zinc-900 to-neutral-900 dark overflow-x-hidden">
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
              <h2 className="text-3xl font-bold text-white mb-2">Welcome back</h2>
              <div className="flex items-center justify-center mb-3 gap-2">
                <h3 className="text-2xl font-bold" style={{ color: '#a259f7' }}>
                  @{accountData.username}
                </h3>
                {config.showKycStatusBadge ? (
                  kycStatus === 'approved' ? (
                    <span className="flex items-center gap-1 bg-green-900/30 text-green-400 text-xs font-semibold px-3 py-1.5 rounded-full">
                      <FaCheck className="text-green-400 text-base" /> Active
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 bg-yellow-900/30 text-yellow-400 text-xs font-semibold px-3 py-1.5 rounded-full">
                      KYC needed
                    </span>
                  )
                ) : (
                  <span className="flex items-center gap-1 bg-green-900/30 text-green-400 text-xs font-semibold px-2 py-1 rounded-full">
                    <FaCheck className="text-green-400 text-base" /> Active
                  </span>
                )}
              </div>
              {!config.showKycStatusBadge && (
                <p className="text-zinc-400">
                  {kycStatus === 'approved' ? 'Your secure digital wallet is ready' : 'Complete KYC to unlock full wallet functionality'}
                </p>
              )}
            </div>
          )}
          <BalanceCard
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
          />
          {accountData?.username && kycStatus === 'approved' && (
            <>
              <div className="flex flex-row gap-4 mb-8 w-full justify-center mt-8">
                <button
                  type="button"
                  onClick={() => {
                    if (config.useERC20Modal) {
                      setShowSendERC20Form(true);
                    } else {
                      setShowSendForm(true);
                    }
                  }}
                  className="flex-1 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white py-5 px-10 rounded-full font-bold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-xl"
                >
                  <FaArrowUp className="mr-3 text-lg" />
                  Pay
                </button>
                <button
                  type="button"
                  onClick={() => router.push(config.growRoute)}
                  className="flex-1 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white py-5 px-10 rounded-full font-bold transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-[1.02] active:scale-[0.98] flex items-center justify-center text-xl"
                >
                  <FaArrowUp className="mr-3 text-lg transform rotate-45 text-green-400" />
                  Grow
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
                        onBalanceRefresh: () => {
                          if (accountData?.wallet_address) {
                            debouncedFetchBalance(accountData.wallet_address, { background: true }, 500);
                          }
                        },
                        onBalanceFlicker: () => {
                          setBalanceFlickering(true);
                        },
                        onTransactionRefresh: () => {
                          setTransactionHistoryRefresh(prev => !prev);
                        },
                      })}
                    </div>
                  )}
                  {!showClarkChat && (
                    <div className="flex justify-end mt-8 mb-4">
                      <button
                        type="button"
                        onClick={() => setShowClarkChat(true)}
                        className="flex items-center gap-2 px-3 py-2 rounded-full bg-zinc-800/60 hover:bg-zinc-700/80 border border-zinc-700/50 hover:border-purple-500/50 transition-all duration-300 shadow-lg hover:shadow-xl transform hover:scale-105 active:scale-95"
                        aria-label="Open Clark Chat"
                      >
                        <img src="/clark plain.svg" alt="Clark" className="h-7 w-7 flex-shrink-0" />
                        <div className="flex flex-col items-start leading-tight">
                          <span className="text-white font-medium text-xs">Ask</span>
                          <span className="text-white font-medium text-xs">Clark</span>
                        </div>
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div>
                  {config.renderChatComponent({
                    userId: accountData?.user_id,
                    onBalanceRefresh: () => {
                      if (accountData?.wallet_address) {
                        debouncedFetchBalance(accountData.wallet_address, { background: true }, 500);
                      }
                    },
                    onBalanceFlicker: () => {
                      setBalanceFlickering(true);
                    },
                    onTransactionRefresh: () => {
                      setTransactionHistoryRefresh(prev => !prev);
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
            balance={balance}
          />
        )}
        {showTransakModal && (
          <BuyUSDCModal
            fiatData={fiatData}
            onClose={() => setShowTransakModal(false)}
            walletAddress={accountData?.wallet_address}
          />
        )}
      </div>
    </>
  );
}

