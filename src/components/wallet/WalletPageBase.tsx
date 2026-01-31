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
import api from "@/lib/api";
import WalletHeader from "@/components/wallet/WalletHeader";
import axios from "axios";
import { useWebSocket } from "@/hooks/useWebSocket";

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

// Configuration: Delay before fetching balance after webhook event (in milliseconds)
// Increase this if Circle API hasn't updated the balance yet when webhook arrives
const WEBHOOK_BALANCE_REFRESH_DELAY_MS = 5000; // 5 seconds - wait for Circle/subgraph to update

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
  const balanceCardRef = useRef<BalanceCardRef | null>(null); // Ref to BalanceCard for switching tabs

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
    balanceDebounceTimerRef.current = setTimeout(() => {
      if (!balanceFetchInProgressRef.current && address && fetchBalanceRef.current) {
        balanceFetchInProgressRef.current = true;
        fetchBalanceRef.current(address, options)
          .then(() => {
            // Ensure refreshing state is cleared after successful fetch
            if (options?.background) {
              setBalanceRefreshing(false);
            }
          })
          .catch((err) => {
            console.error('Error fetching balance:', err);
            // Ensure refreshing state is cleared even on error
            if (options?.background) {
              setBalanceRefreshing(false);
            }
          })
          .finally(() => {
            balanceFetchInProgressRef.current = false;
          });
      } else {
        // If fetch was skipped, clear refreshing state
        if (options?.background) {
          setBalanceRefreshing(false);
        }
      }
      balanceDebounceTimerRef.current = null;
    }, delay);
  }, []);

  // WebSocket message handler - stabilized with useCallback and refs
  const handleWebSocketMessage = useCallback((message: any) => {
    // Handle new Krypton_Web3 event format (from webhook.py)
    if (message.type === 'transaction_confirmed' || message.type === 'transaction_update') {
      const transactionId = message.transaction_id;

      // Deduplicate: Skip if we've already processed this transaction event
      if (transactionId && processedWebhookEventsRef.current.has(transactionId)) {
        return;
      }

      // Mark this event as processed
      if (transactionId) {
        processedWebhookEventsRef.current.add(transactionId);
        // Clean up old event IDs after 5 minutes to prevent memory leak
        setTimeout(() => {
          processedWebhookEventsRef.current.delete(transactionId);
        }, 5 * 60 * 1000);
      }

      // Show notification to user
      if (message.type === 'transaction_confirmed' && config.showWebhookNotification) {
        setWebhookNotification('Transaction confirmed! Refreshing balance...');
        setTimeout(() => setWebhookNotification(null), 5000);
      }

      // Refresh balance - no need to check address since we're receiving user-specific events
      const currentAccountData = accountDataRef.current;
      if (currentAccountData?.wallet_address) {
        // Use configurable delay to allow Circle API time to update balance
        const debounceDelay = WEBHOOK_BALANCE_REFRESH_DELAY_MS;

        // Clear any existing debounce timer
        if (balanceDebounceTimerRef.current) {
          clearTimeout(balanceDebounceTimerRef.current);
          balanceDebounceTimerRef.current = null;
        }

        // Set refreshing state to show UI feedback
        setBalanceRefreshing(true);

        // Use debounced fetch
        debouncedFetchBalance(currentAccountData.wallet_address, { background: true }, debounceDelay);

        // Trigger BalanceCard refresh
        setBalanceCardRefresh(prev => !prev);

        // Safety timeout: Clear refreshing state after 20 seconds if stuck
        setTimeout(() => {
          setBalanceRefreshing(prev => {
            if (prev) {
              console.warn('Balance refreshing state was stuck - forcing clear after 20s timeout');
              return false;
            }
            return prev;
          });
        }, 20000);
      }

      // Also refresh transaction history if it's open
      if (showTransactionsRef.current) {
        setTransactionHistoryRefresh(prev => !prev);
      }

      return;
    }

    // Handle legacy circle_webhook format (from KryptonPay_Backend) for backward compatibility
    if (message.type === 'circle_webhook') {
      const eventId = message.event_id;

      // Deduplicate: Skip if we've already processed this webhook event
      if (eventId && processedWebhookEventsRef.current.has(eventId)) {
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
        // Use configurable delay to allow Circle API time to update balance after webhook
        const debounceDelay = WEBHOOK_BALANCE_REFRESH_DELAY_MS;

        // Clear any existing debounce timer
        if (balanceDebounceTimerRef.current) {
          clearTimeout(balanceDebounceTimerRef.current);
          balanceDebounceTimerRef.current = null;
        }

        // Set refreshing state to show UI feedback
        setBalanceRefreshing(true);

        // Use debounced fetch to prevent excessive calls
        debouncedFetchBalance(currentAccountData.wallet_address, { background: true }, debounceDelay);

        // Safety timeout: Clear refreshing state after 20 seconds if it's still stuck
        setTimeout(() => {
          setBalanceRefreshing(prev => {
            if (prev) {
              console.warn('Balance refreshing state was stuck - forcing clear after 20s timeout');
              return false;
            }
            return prev;
          });
        }, 20000);

        // Trigger BalanceCard refresh by toggling the refresh flag
        setBalanceCardRefresh(prev => !prev);
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
  }, [config.showWebhookNotification]);

  // WebSocket close handler - stabilized
  const handleWebSocketClose = useCallback(() => {}, []);

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

  const { isConnected: wsConnected, connectionStatus, reconnect: wsReconnect } = useWebSocket(
    wsUrl || '',
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

      // Fetch fresh KYC status from backend instead of relying on localStorage
      if (data.user_id) {
        fetchUserData(data.user_id);
      }
      if (data.wallet_address) {
        fetchBalance(data.wallet_address, { background: config.pageType === 'business' });
      }
      // Don't show error if wallet address is missing - it will be fetched by fetchUserData
    } catch (err) {
      setError('Invalid user data.');
    } finally {
      setLoading(false);
    }
  }, [router]);

  const fetchUserData = async (userId: string) => {
    try {
      setUserDataLoading(true);

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

    } catch (err) {
      console.error('Failed to fetch user data:', err);
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
    // Prevent duplicate concurrent fetches
    if (balanceFetchInProgressRef.current && options?.background) {
      return;
    }

    const isBackground = options?.background === true;

    // Set fetching flag
    if (isBackground) {
      balanceFetchInProgressRef.current = true;
    }

    try {
      if (!isBackground) {
        setBalanceLoading(true);
      }

      // Use the new subgraph API endpoint
      const kryptonWeb3ApiUrl = process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL || 'http://localhost:8001';
      const response = await fetch(`${kryptonWeb3ApiUrl}/subgraph/user/${address}/balances`);

      if (!response.ok) {
        throw new Error(`Failed to fetch balance: ${response.statusText}`);
      }

      const subgraphResponse = await response.json();

      // Transform subgraph response to frontend format
      const transformedBalance = {
        tokenBalances: subgraphResponse.balances.map((balance: any) => ({
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
      };

      console.log('Balance fetch complete:', {
        address,
        balanceCount: transformedBalance.tokenBalances.length,
        balances: transformedBalance.tokenBalances.map((b: any) => `${b.token.symbol}: ${b.amount}`)
      });

      setBalance(transformedBalance);

    } catch (err) {
      console.error('Failed to fetch balance from subgraph:', err);
      setError('Failed to fetch balance.');
    } finally {
      if (isBackground) {
        setBalanceRefreshing(false);
        balanceFetchInProgressRef.current = false;
        // Stop flickering when balance refresh is complete
        if (balanceFlickering) {
          setBalanceFlickering(false);
        }
      } else {
        setBalanceLoading(false);
        balanceFetchInProgressRef.current = false;
        // Stop flickering when balance loading is complete
        if (balanceFlickering) {
          setBalanceFlickering(false);
        }
      }
    }
  }, [balanceFlickering]);

  // Update fetchBalance ref when it changes
  useEffect(() => {
    fetchBalanceRef.current = fetchBalance;
  }, [fetchBalance]);

  /**
   * Called when all active transactions complete (from BalanceCard/ActiveTransactions).
   * Triggers balance refresh with blinking effect.
   */
  const handleTransactionsComplete = useCallback(() => {
    const currentAccountData = accountDataRef.current;
    if (currentAccountData?.wallet_address) {
      // Start blinking immediately
      setBalanceRefreshing(true);

      // Clear any existing timer
      if (balanceDebounceTimerRef.current) {
        clearTimeout(balanceDebounceTimerRef.current);
      }

      // First refresh after 5 seconds (give subgraph time to index)
      const firstDelay = WEBHOOK_BALANCE_REFRESH_DELAY_MS; // 5 seconds
      debouncedFetchBalance(currentAccountData.wallet_address, { background: true }, firstDelay);

      // Second refresh after 10 seconds (for slow subgraph indexing)
      setTimeout(() => {
        const accountData = accountDataRef.current;
        if (accountData?.wallet_address) {
          console.log('Transaction complete: Second balance refresh attempt');
          setBalanceRefreshing(true);
          debouncedFetchBalance(accountData.wallet_address, { background: true }, 0);
        }
      }, 10000);

      // Toggle balance card refresh
      setBalanceCardRefresh(prev => !prev);
    }
  }, [debouncedFetchBalance]);

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
    } catch (err) {
      const textArea = document.createElement('textarea');
      textArea.value = text;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
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
    setSendCurrency("");
    setSendERC20Error(null);
    setSendERC20Success(null);
    setSendERC20Loading(false);
    // Only switch to Transaction History tab on auto-close (success), not on manual X button close
    if (autoClose) {
      balanceCardRef.current?.showTransactionHistory();
    }
    setTransactionHistoryRefresh(prev => !prev);
  };

  const openKycModal = async (userId: string) => {
    try {
      // 1. Create applicant if needed
      await api.post('/api/v1/kyc/applicant', { user_id: userId });

      // 2. Get access token
      const tokenRes = await api.post('/api/v1/kyc/access-token', { user_id: userId });
      setKycAccessToken(tokenRes.data.token || tokenRes.data.accessToken || tokenRes.data.access_token);
      setKycModalVisible(true);

    } catch (err) {
      console.error('Failed to open KYC modal:', err);
    }
  };

  const checkKycStatus = async (userId: string) => {
    setKycChecking(true);
    setKycMessage(null);

    try {
      const response = await api.post(`/api/v1/kyc/check-status/${userId}`);

      if (response.data.status === 'success') {
        const newStatus = response.data.kyc_status;
        setKycStatus(newStatus);
        const updatedData = { ...accountData, kyc_status: newStatus };
        setAccountData(updatedData);
        localStorage.setItem('userData', JSON.stringify(updatedData));

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

      } else {
        setKycMessage(response.data.message || 'Failed to check KYC status');
        setTimeout(() => setKycMessage(null), 5000);
      }
    } catch (err: any) {
      console.error('Failed to check KYC status:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to check KYC status');
      setTimeout(() => setKycMessage(null), 5000);
    } finally {
      setKycChecking(false);
    }
  };

  const skipKyc = async (userId: string) => {
    try {
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
      } else {
        setKycMessage(response.data.message || 'Failed to skip KYC');
      }
    } catch (err: any) {
      console.error('Failed to skip KYC:', err);
      setKycMessage(err.response?.data?.detail || 'Failed to skip KYC');
    } finally {
      // Clear message after 5 seconds
      setTimeout(() => setKycMessage(null), 5000);
    }
  };

  const pollKycStatus = async (userId: string) => {
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

        if (finalStatus === 'approved') {
          setKycMessage('KYC verification completed successfully!');
          setTimeout(() => setKycMessage(null), 3000);
        }
      }
    } catch (err) {
      console.error('Error in final KYC status check:', err);
    }
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
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden flex items-center justify-center">
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
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden flex items-center justify-center p-4">
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
      <div className="min-h-screen w-full bg-[#001C1B] dark overflow-x-hidden">
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
                <span className="text-[#90E7EE] text-3xl">@{accountData.username}</span>
              <div className="flex items-center justify-center gap-1.5 text-base">
                {config.showKycStatusBadge ? (
                  kycStatus === 'approved' ? (
                    <>
                      <span className="text-zinc-400">Active</span>
                      <FaCheck className="text-green-500 shrink-0" />
                    </>
                  ) : (
                    <span className="text-zinc-400">KYC needed</span>
                  )
                ) : (
                  <>
                    <span className="text-zinc-400">Active</span>
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
          />
          {accountData?.username && kycStatus === 'approved' && (
            <>
              <div className="flex flex-row gap-4 mb-8 w-full justify-center md:justify-stretch mt-8 items-center">
                <button
                  type="button"
                  onClick={() => {
                    if (config.useERC20Modal) {
                      setShowSendERC20Form(true);
                    } else {
                      setShowSendForm(true);
                    }
                  }}
                  className="p-0 border-0 bg-transparent cursor-pointer inline-flex md:flex-1 md:min-w-0 md:flex md:items-center md:justify-center focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity"
                  aria-label="Pay"
                >
                  <img
                    src="/Pay.svg"
                    alt="Pay"
                    className="h-12 w-auto max-w-[10rem] md:w-3/4 md:h-auto md:max-w-none md:object-contain"
                  />
                </button>
                <button
                  type="button"
                  onClick={() => router.push(config.growRoute)}
                  className="p-0 border-0 bg-transparent cursor-pointer inline-flex md:flex-1 md:min-w-0 md:flex md:items-center md:justify-center focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity"
                  aria-label="Grow"
                >
                  <img
                    src="/Grow.svg"
                    alt="Grow"
                    className="h-12 w-auto max-w-[10rem] md:w-3/4 md:h-auto md:max-w-none md:object-contain"
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
                        className="p-0 border-0 bg-transparent cursor-pointer inline-flex focus:outline-none focus:ring-0 hover:opacity-90 active:opacity-80 transition-opacity"
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
            username={accountData?.username}
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

