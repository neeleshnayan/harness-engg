import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowRight, Loader2, X, ArrowUp, ChevronDown } from "lucide-react";
import api, { kryptonWeb3Api } from "@/lib/api";
import { useRates } from "@/providers/RatesProvider";
import { getPoolRate } from "@/lib/ratesApi";
import WalletProgressState from "@/components/wallet/WalletProgressState";
import WalletModalShell from "@/components/wallet/WalletModalShell";

interface SendERC20ModalProps {
  visible: boolean;
  /** Called when modal closes. autoClose=true means countdown auto-closed, false means user manually closed */
  onClose: (autoClose?: boolean) => void;
  userAddress: string;
  userId?: string;
  username?: string; // Added for Krypton_Web3 endpoints
  balance?: any;
}

type SupportedToken = {
  symbol: string; // e.g., kUSD
  address: string;
  decimals?: number;
  isSeparator?: boolean;
};

// Countdown toast timeout in seconds
const CLOSE_COUNTDOWN_SECONDS = 5;

export default function SendERC20Modal({ visible, onClose, userAddress, userId, username, balance }: SendERC20ModalProps) {
  const [receiverUsername, setReceiverUsername] = useState<string>("");
  const [selectedCurrency, setSelectedCurrency] = useState<string>("");
  const [fromAmount, setFromAmount] = useState<string>("");
  const [toAmount, setToAmount] = useState<string>("");
  const [supportedTokensList, setSupportedTokensList] = useState<SupportedToken[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<{ heading: string; detail: string } | null>(null);
  const [fromBalanceValue, setFromBalanceValue] = useState<number>(0);
  const [toBalanceValue, setToBalanceValue] = useState<number>(0);
  const [toCurrency, setToCurrency] = useState<string>("");
  const [availableTokens, setAvailableTokens] = useState<SupportedToken[]>([]);
  const [isCalculatingFrom, setIsCalculatingFrom] = useState<boolean>(false);
  const [isCalculatingTo, setIsCalculatingTo] = useState<boolean>(false);
  const [exchangeRate, setExchangeRate] = useState<number | null>(null);
  const [exchangeRateLoading, setExchangeRateLoading] = useState<boolean>(false);
  const [closeCountdown, setCloseCountdown] = useState<number>(0);
  const isTransactionInProgress = useRef<boolean>(false);
  const isUpdatingFromRef = useRef<boolean>(false);
  const isUpdatingToRef = useRef<boolean>(false);
  const focusedFieldRef = useRef<"from" | "to" | null>(null);
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get token data from context 🚀
  const { tokens: ratesTokens, getTokenAddressToSymbol } = useRates();
  const tokenAddressMap = useMemo(() => getTokenAddressToSymbol(), [getTokenAddressToSymbol]);

  // Build K_TOKEN_SYMBOLS equivalent from context
  const K_TOKEN_SYMBOLS = useMemo(() => {
    const result: Record<string, string> = {};
    for (const [symbol, token] of Object.entries(ratesTokens)) {
      if (symbol.startsWith('k') && token.address) {
        result[symbol] = token.address;
      }
    }
    return result;
  }, [ratesTokens]);

  // Cleanup countdown on unmount
  useEffect(() => {
    return () => {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
      }
    };
  }, []);

  // Start countdown and auto-close
  const startCloseCountdown = useCallback(() => {
    setCloseCountdown(CLOSE_COUNTDOWN_SECONDS);

    if (countdownIntervalRef.current) {
      clearInterval(countdownIntervalRef.current);
    }

    countdownIntervalRef.current = setInterval(() => {
      setCloseCountdown(prev => {
        if (prev <= 1) {
          if (countdownIntervalRef.current) {
            clearInterval(countdownIntervalRef.current);
            countdownIntervalRef.current = null;
          }
          // Fix React warning: "Cannot update a component while rendering a different component"
          // We schedule the onClose side-effect to happen outside of the setState render cycle.
          setTimeout(() => onClose(true), 0);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  }, [onClose]);

  useEffect(() => {
    if (!visible) {
      // Reset transaction flag when modal closes
      isTransactionInProgress.current = false;
      // Clear countdown
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
      setCloseCountdown(0);
      return;
    }

    // Don't reset state if a transaction is in progress (balance might be refreshing)
    if (isTransactionInProgress.current) {
      return;
    }

    // Reset when opened (only if not in transaction)
    setReceiverUsername("");
    setFromAmount("");
    setToAmount("");
    setSelectedCurrency("");
    setToCurrency("");
    setFromBalanceValue(0);
    setToBalanceValue(0);
    setIsCalculatingFrom(false);
    setIsCalculatingTo(false);
    setExchangeRate(null);
    setExchangeRateLoading(false);
    setError(null);
    setSuccess(null);
    setCloseCountdown(0);

    // Load supported currencies and filter by balance
    const loadAvailableTokens = async () => {
      try {
        setLoading(true);
        // setLoadingMessage("Loading supported currencies...");

        // Get user balances
        const balances = await fetchUserBalances();

        // All supported tokens (for "to" dropdown)
        let allTokens: SupportedToken[] = [
          ...Object.entries(K_TOKEN_SYMBOLS).map(([symbol, address]) => ({
            symbol,
            address,
            decimals: 18, // Most ERC20 tokens use 18 decimals
          })),
          {
            symbol: "USDC",
            address: "",
            decimals: 6,
          },
        ];

        // Fetch RWA tokens
        try {
          const rwaRes = await kryptonWeb3Api.get("/erc20/supported-tokens");
          const rwaTokensData = rwaRes.data?.rwa_tokens || {};
          const rwaList: SupportedToken[] = Object.entries(rwaTokensData).map(([symbol, conf]: [string, any]) => ({
            symbol,
            address: conf.address,
            decimals: conf.decimals || 18,
          }));

          if (rwaList.length > 0) {
            allTokens.push({
              symbol: "--- RWA Tokens ---",
              address: "SEPARATOR",
              decimals: 0,
              isSeparator: true
            });
            allTokens = [...allTokens, ...rwaList];
          }
        } catch (err) {
          console.error("Failed to fetch RWA tokens", err);
        }

        // Filter tokens to only include those with non-zero balances (for "from" dropdown)
        // Build from list with separator before RWA tokens if any RWA tokens have balance
        const kTokensWithBalance: SupportedToken[] = [];
        const rwaTokensWithBalance: SupportedToken[] = [];

        for (const token of allTokens) {
          if (token.isSeparator) continue;
          const tokenBalance = balances[token.symbol] || 0;
          if (tokenBalance > 0) {
            // Check if it's an RWA token (not a k-token and not USDC from K_TOKEN_SYMBOLS)
            const isRWA = !token.symbol.startsWith('k') && token.symbol !== 'USDC' &&
              !Object.keys(K_TOKEN_SYMBOLS).includes(token.symbol);
            if (isRWA) {
              rwaTokensWithBalance.push(token);
            } else {
              kTokensWithBalance.push(token);
            }
          }
        }

        // Build availableList with separator if RWA tokens exist
        const availableList: SupportedToken[] = [...kTokensWithBalance];
        if (rwaTokensWithBalance.length > 0) {
          availableList.push({
            symbol: "--- RWA Tokens ---",
            address: "SEPARATOR",
            decimals: 0,
            isSeparator: true
          });
          availableList.push(...rwaTokensWithBalance);
        }

        setSupportedTokensList(allTokens); // All tokens for "to" dropdown
        setAvailableTokens(availableList); // Only available tokens for "from" dropdown

        // Default selections based on available balances
        if (availableList.length > 0) {
          const first = availableList[0].symbol.replace(/^k/, "");
          setSelectedCurrency(first);
          setToCurrency(first);
        } else {
          setSelectedCurrency("");
          if ((balances["USDC"] || 0) > 0) {
            setToCurrency("USDC");
          }
        }
      } catch (e) {
        console.error(e);
        setError("Failed to load supported currencies.");
      } finally {
        setLoading(false);
        setLoadingMessage("");
      }
    };

    loadAvailableTokens();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]); // Only depend on visible, not balance - prevents reset during transactions

  const fromTokenSymbol = useMemo(() => {
    if (!selectedCurrency) return "";
    if (selectedCurrency === "USDC") return "USDC";
    // If a k-prefixed version exists in rates, it's a k-token (e.g., "EUR" -> "kEUR")
    if (ratesTokens[`k${selectedCurrency}`]) return `k${selectedCurrency}`;
    // Otherwise it's an RWA token, use as-is (e.g., "GC", "XAG")
    return selectedCurrency;
  }, [selectedCurrency, ratesTokens]);

  const toTokenSymbol = useMemo(() => {
    if (!toCurrency) return "";
    if (toCurrency === "USDC") return "USDC";
    if (ratesTokens[`k${toCurrency}`]) return `k${toCurrency}`;
    return toCurrency;
  }, [toCurrency, ratesTokens]);

  const fetchUserBalances = async (): Promise<Record<string, number>> => {
    // Extract token balances from the balance prop (similar to SupportedAssetsBalances)
    const balances: Record<string, number> = {};

    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return balances;
    }

    for (const tb of balance.tokenBalances) {
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const resolvedSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : undefined;
      const tokenSymbol = tb?.token?.symbol;

      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      const symbol = resolvedSymbol || tokenSymbol;
      if (symbol) {
        balances[symbol] = (balances[symbol] || 0) + rawAmount;
      }
    }

    return balances;
  };

  // Update balances when currencies change
  useEffect(() => {
    if (!visible || loading || isTransactionInProgress.current) return;
    const updateBalances = async () => {
      const balances = await fetchUserBalances();
      if (fromTokenSymbol) {
        setFromBalanceValue(balances[fromTokenSymbol] || 0);
      } else {
        setFromBalanceValue(0);
      }
      if (toTokenSymbol) {
        setToBalanceValue(balances[toTokenSymbol] || 0);
      } else {
        setToBalanceValue(0);
      }
    };
    updateBalances();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromTokenSymbol, toTokenSymbol, balance, visible, loading]);

  // Calculate To amount when From amount changes
  useEffect(() => {
    // Don't update "to" field if user is currently typing in it
    // Never update the field the user is currently editing
    if (focusedFieldRef.current === "to") {
      return;
    }

    if (
      !visible ||
      loading ||
      isTransactionInProgress.current ||
      isUpdatingToRef.current ||
      !fromTokenSymbol ||
      !toTokenSymbol ||
      !fromAmount
    ) {
      if (!fromAmount) {
        setToAmount("");
      }
      return;
    }

    const amountNum = parseFloat(fromAmount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setToAmount("");
      return;
    }

    // If currencies are the same, just set equal amounts (keep as string to preserve user input format)
    if (fromTokenSymbol === toTokenSymbol) {
      isUpdatingToRef.current = true;
      // Keep the same format as input, but ensure it's a valid number string
      setToAmount(fromAmount);
      setTimeout(() => {
        isUpdatingToRef.current = false;
      }, 100);
      return;
    }

    let cancelled = false;

    const calculateToAmount = async () => {
      setIsCalculatingTo(true);
      try {
        // Get rate: rate(from -> to) so we can multiply
        const price = await getPoolRate(fromTokenSymbol, toTokenSymbol);

        if (cancelled) return;

        if (price > 0) {
          isUpdatingToRef.current = true;
          const calculatedTo = amountNum * price;
          // Format to 2 decimals for display
          setToAmount(calculatedTo.toFixed(2));
          setTimeout(() => {
            isUpdatingToRef.current = false;
          }, 100);
        } else {
          setToAmount("");
        }
      } catch (e) {
        if (cancelled) return;
        console.error('Failed to fetch exchange rate for To amount:', e);
        setToAmount("");
      } finally {
        if (!cancelled) {
          setIsCalculatingTo(false);
        }
      }
    };

    calculateToAmount();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromAmount, fromTokenSymbol, toTokenSymbol, visible, loading]);

  // Calculate From amount when To amount changes
  useEffect(() => {
    // Don't update "from" field if user is currently typing in it
    // Never update the field the user is currently editing
    if (focusedFieldRef.current === "from") {
      return;
    }

    if (
      !visible ||
      loading ||
      isTransactionInProgress.current ||
      isUpdatingFromRef.current ||
      !fromTokenSymbol ||
      !toTokenSymbol ||
      !toAmount
    ) {
      if (!toAmount) {
        setFromAmount("");
      }
      return;
    }

    const amountNum = parseFloat(toAmount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setFromAmount("");
      return;
    }

    // If currencies are the same, just set equal amounts (keep as string to preserve user input format)
    if (fromTokenSymbol === toTokenSymbol) {
      isUpdatingFromRef.current = true;
      // Keep the same format as input, but ensure it's a valid number string
      setFromAmount(toAmount);
      setTimeout(() => {
        isUpdatingFromRef.current = false;
      }, 100);
      return;
    }

    let cancelled = false;

    const calculateFromAmount = async () => {
      setIsCalculatingFrom(true);
      try {
        // Get rate: rate(to -> from) so we can multiply to get from amount
        const price = await getPoolRate(toTokenSymbol, fromTokenSymbol);

        if (cancelled) return;

        if (price > 0) {
          isUpdatingFromRef.current = true;
          // To get FROM amount: TO amount * price (since price is Rate(to->from))
          const calculatedFrom = amountNum * price;
          // Format to 2 decimals for display
          setFromAmount(calculatedFrom.toFixed(2));
          setTimeout(() => {
            isUpdatingFromRef.current = false;
          }, 100);
        } else {
          setFromAmount("");
        }
      } catch (e) {
        if (cancelled) return;
        console.error('Failed to fetch exchange rate for From amount:', e);
        setFromAmount("");
      } finally {
        if (!cancelled) {
          setIsCalculatingFrom(false);
        }
      }
    };

    calculateFromAmount();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [toAmount, fromTokenSymbol, toTokenSymbol, visible, loading]);

  // Calculate exchange rate for display
  useEffect(() => {
    if (
      !visible ||
      !fromTokenSymbol ||
      !toTokenSymbol
    ) {
      setExchangeRate(null);
      setExchangeRateLoading(false);
      return;
    }

    // Don't recalculate during transaction, but preserve existing rate
    if (isTransactionInProgress.current || loading) {
      return;
    }

    if (fromTokenSymbol === toTokenSymbol) {
      setExchangeRate(1);
      setExchangeRateLoading(false);
      return;
    }

    let cancelled = false;

    const fetchExchangeRate = async () => {
      setExchangeRateLoading(true);
      try {
        // Get rate: how much toCurrency per 1 fromCurrency (for display "1 From = X To")
        const price = await getPoolRate(fromTokenSymbol, toTokenSymbol);

        if (cancelled) return;

        if (price > 0) {
          setExchangeRate(price);
        } else {
          setExchangeRate(null);
        }
      } catch (e) {
        if (cancelled) return;
        console.error('Failed to fetch exchange rate:', e);
        setExchangeRate(null);
      } finally {
        if (!cancelled) {
          setExchangeRateLoading(false);
        }
      }
    };

    fetchExchangeRate();

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromTokenSymbol, toTokenSymbol, visible, loading]);

  // Set toCurrency to match fromCurrency initially
  useEffect(() => {
    if (selectedCurrency && !toCurrency) {
      setToCurrency(selectedCurrency);
    }
  }, [selectedCurrency, toCurrency]);

  // Check if balance is sufficient for the transaction
  const hasSufficientBalance = useMemo(() => {
    if (!fromAmount) return false;
    const amountNum = parseFloat(fromAmount);
    if (isNaN(amountNum) || amountNum <= 0) return false;

    if (!fromTokenSymbol) return false;

    // Check if from balance >= from amount
    return fromBalanceValue >= amountNum;
  }, [fromAmount, fromTokenSymbol, fromBalanceValue]);

  // Check if currency combination is valid
  const isValidCurrencyCombination = useMemo(() => {
    if (!fromTokenSymbol || !toTokenSymbol) return false;
    // All token combinations are now valid via universal swap
    return true;
  }, [fromTokenSymbol, toTokenSymbol]);

  // Receiver validation for button state
  const normalizedReceiverUsername = receiverUsername.trim().replace(/^@/, "").toLowerCase();
  const normalizedSelfUsername = (username || "").trim().replace(/^@/, "").toLowerCase();
  const hasReceiverUsername = normalizedReceiverUsername.length > 0;
  const isReceiverSelf = normalizedSelfUsername.length > 0 && normalizedReceiverUsername === normalizedSelfUsername;
  const isReceiverValid = hasReceiverUsername && !isReceiverSelf;

  // Handle swap currencies
  const handleSwapCurrencies = () => {
    const prevFrom = selectedCurrency;
    const prevTo = toCurrency;
    setSelectedCurrency(prevTo);
    setToCurrency(prevFrom);
  };

  const resolveReceiverAddress = async (usernameToResolve: string): Promise<string> => {
    // Reuse existing user API to resolve username to address
    try {
      const resp = await api.get(`/api/v1/resolve_username/${usernameToResolve}`);
      const addr = resp?.data?.wallet_address || resp?.data?.walletAddress;
      if (!addr || typeof addr !== "string") throw new Error("Wallet address not found for username");
      return addr;
    } catch (e) {
      throw new Error("Failed to resolve receiver address. Please check the username.");
    }
  };

  /**
   * Perform swap using Krypton_Web3 endpoints (Circle-based).
   * Routes to /pools/swap for k-token pairs, /pools/universal/swap for cross-ecosystem.
   */
  const performSwap = async (fromSymbol: string, toSymbol: string, requiredToAmount: number): Promise<string | null> => {
    const fromDisplay = fromSymbol.replace(/^k/, "");
    const toDisplay = toSymbol.replace(/^k/, "");

    setLoadingMessage(`Checking swap price from ${fromDisplay} to ${toDisplay}...`);
    const balances = await fetchUserBalances();

    // Get rate: rate(to -> from) to calculate input needed for exact output
    const price = await getPoolRate(toSymbol, fromSymbol);

    if (price <= 0) {
      throw new Error(`Cannot get price for swap ${fromDisplay} → ${toDisplay}`);
    }

    // Calculate how much fromCurrency we need to swap to get requiredToAmount of toCurrency
    const safety = 1.02; // +2% buffer for slippage/fees
    const requiredFromAmount = (requiredToAmount * price) * safety;

    const fromBalance = balances[fromSymbol] || 0;
    if (fromBalance < requiredFromAmount) {
      throw new Error(`Insufficient ${fromDisplay} balance. Need ${requiredFromAmount.toFixed(4)}, have ${fromBalance.toFixed(4)}`);
    }

    setLoadingMessage(`Swapping ${requiredFromAmount.toFixed(4)} ${fromDisplay} → ${toDisplay}...`);

    // Determine if this is a cross-ecosystem swap
    const isKToken = (t: string) => t.startsWith('k');
    const needsUniversal = !isKToken(fromSymbol) || !isKToken(toSymbol);
    const endpoint = needsUniversal ? "/pools/universal/swap" : "/pools/swap";

    const response = await kryptonWeb3Api.post(endpoint, {
      from_token: fromSymbol,
      to_token: toSymbol,
      amount: requiredFromAmount,
      wallet_address: userAddress,
      wallet_username: username,
    });

    return response?.data?.transaction_id || null;
  };



  /**
   * Transfer tokens using Krypton_Web3 /erc20/transfer endpoint (Circle-based)
   */
  const transferTokens = async (targetSymbol: string, toAddress: string, amount: number): Promise<string | null> => {
    setLoadingMessage(`Transferring ${amount.toFixed(2)} ${targetSymbol.replace(/^k/, "")}...`);

    // Use Krypton_Web3 transfer endpoint (Circle-based transaction)
    const response = await kryptonWeb3Api.post(`/erc20/transfer`, {
      token_symbol: targetSymbol,
      from_address: userAddress,
      from_username: username,
      to_address: toAddress,
      to_username: receiverUsername.trim(),
      amount,
    });

    // Return transaction ID for tracking
    return response?.data?.transaction_id || null;
  };

  const handleSend = async () => {
    setError(null);
    setSuccess(null);

    if (!receiverUsername.trim()) {
      setError("Please enter receiver username.");
      return;
    }
    const fromAmountNum = parseFloat(fromAmount);
    if (!fromAmount.trim() || isNaN(fromAmountNum) || fromAmountNum <= 0) {
      setError("Please enter a valid amount to send.");
      return;
    }
    if (!toTokenSymbol || !toCurrency) {
      setError("Please select a to currency.");
      return;
    }
    if (!fromTokenSymbol || !selectedCurrency) {
      setError("Please select a from currency.");
      return;
    }

    // Set transaction flag to prevent UI resets during the transaction
    isTransactionInProgress.current = true;
    setLoading(true);

    try {
      // Get current balances
      setLoadingMessage("Checking your balance...");
      const balances = await fetchUserBalances();

      const sendCurrency = toTokenSymbol;
      const sendCurrencyDisplay = sendCurrency === "USDC" ? "USDC" : sendCurrency.replace(/^k/, "");
      const fromCurrency = fromTokenSymbol;
      if (!fromCurrency) {
        throw new Error("Please select a from currency.");
      }

      // Use universal swapIfNeededAndPay when swap is required. This ensures the transfer
      // is queued behind the swap on the backend (via circle_client) and only executes
      // after the swap is submitted/confirmed - fixing the race where transfer went before swap.
      if (fromCurrency !== sendCurrency) {
        if (!username) {
          throw new Error("Username is required for swap and send.");
        }
        setLoadingMessage(`Swapping and sending ${fromAmountNum.toFixed(2)} ${fromCurrency.replace(/^k/, "")} to @${receiverUsername}...`);
        await kryptonWeb3Api.post("/pools/universal/swapIfNeededAndPay", {
          from_token: fromCurrency,
          to_token: sendCurrency,
          input_amount: fromAmountNum,
          quote_mode: "exact_input",
          sender_username: username,
          receiver_username: receiverUsername.trim(),
          slippage_tolerance: 0.05,
        });
        await new Promise(resolve => setTimeout(resolve, 1000));
      } else {
        // Direct send (no swap): ensure sufficient balance of krypton pay
        const fromBalance = balances[fromCurrency] || 0;
        if (fromBalance < fromAmountNum) {
          const fromDisplay = fromCurrency.replace(/^k/, "");
          throw new Error(`Insufficient balance. You have ${fromBalance.toFixed(4)} ${fromDisplay}, but need ${fromAmountNum.toFixed(4)}.`);
        }

        // Send the target currency to the receiver (no preceding swap)
        if (sendCurrency === "USDC") {
          if (!userId) {
            throw new Error("User ID is required to send USDC.");
          }
          setLoadingMessage(`Sending ${fromAmountNum.toFixed(2)} USDC...`);
          await kryptonWeb3Api.post("/erc20/send-usdc", {
            sender_user_id: userId,
            receiver_username: receiverUsername.trim(),
            amount: fromAmountNum
          });
          await new Promise(resolve => setTimeout(resolve, 1000));
        } else {
          setLoadingMessage("Resolving receiver address...");
          const toAddress = await resolveReceiverAddress(receiverUsername.trim());
          setLoadingMessage(`Transferring ${fromAmountNum.toFixed(2)} ${sendCurrencyDisplay} to @${receiverUsername}...`);
          await transferTokens(sendCurrency, toAddress, fromAmountNum);
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      // Show success with countdown (non-blocking)
      const convertedAmount = parseFloat(toAmount);
      const transferAmount = fromCurrency === sendCurrency || isNaN(convertedAmount) ? fromAmountNum : convertedAmount;
      setSuccess({
        heading: "Transferring...",
        detail: `Sending ${transferAmount.toFixed(2)} ${sendCurrencyDisplay} to @${receiverUsername}`,
      });
      startCloseCountdown();
    } catch (e: any) {
      console.error(e);
      setError(e?.response?.data?.detail || e?.message || "Transaction failed. Please try again.");
    } finally {
      // Clear transaction flag after transaction completes (success or error)
      isTransactionInProgress.current = false;
      setLoading(false);
      setLoadingMessage("");
    }
  };

  // Handle clicking anywhere to close on success (user tapping to dismiss success screen)
  const handleBackdropClick = () => {
    if (success) {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
      onClose(true); // Transaction was successful, switch to transaction history
    } else {
      onClose(false); // User cancelled
    }
  };

  if (!visible) return null;

  const optionStyle: React.CSSProperties = {
    color: '#0f172a',
    backgroundColor: '#f8fafc',
  };
  const optionSeparatorStyle: React.CSSProperties = {
    color: '#334155',
    backgroundColor: '#f8fafc',
    fontStyle: 'italic',
    opacity: 0.7,
  };

  return (
    <WalletModalShell
      open={visible}
      onDismiss={handleBackdropClick}
      screenReaderTitle="Krypton Pay"
      onContentClick={success ? handleBackdropClick : undefined}
      contentClassName="w-[calc(100%-2rem)] max-w-[440px] max-h-[calc(100dvh-2rem)] shadow-2xl relative overflow-x-visible overflow-y-auto rounded-xl p-4 sm:p-6 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 duration-200"
      contentStyle={{
        background: 'linear-gradient(135deg, rgba(0, 28, 27, 0.50) 0%, rgba(0, 40, 38, 0.40) 50%, rgba(0, 20, 20, 0.55) 100%)',
        backdropFilter: 'blur(32px) saturate(180%)',
        WebkitBackdropFilter: 'blur(32px) saturate(180%)',
        border: '1px solid rgba(255, 255, 255, 0.08)',
        boxShadow: '0 0 0 1px rgba(45, 212, 191, 0.08), 0 32px 64px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.06)',
      }}
    >
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-2xl font-bold text-white tracking-tight">Krypton Pay</h2>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClose(false);
            }}
            className="w-8 h-8 rounded-full flex items-center justify-center text-white/60 hover:text-white transition-all hover:scale-105 active:scale-95"
            style={{
              background: 'rgba(255,255,255,0.06)',
              border: '1px solid rgba(255,255,255,0.1)',
            }}
          >
            <X size={15} strokeWidth={2.5} />
          </button>
        </div>

        {/* Success Animation */}
        {success && (
          <WalletProgressState
            heading={success.heading}
            detail={success.detail}
            animationPath="/animations/pay/pay-animation.json"
            closeCountdown={closeCountdown}
          />
        )}

        {/* Form */}
        {!success && (
          <div className="space-y-5">
            {error && (
              <div className="rounded-xl p-3 flex items-center gap-2.5 text-sm" style={{
                background: 'rgba(239,68,68,0.07)',
                backdropFilter: 'blur(12px)',
                WebkitBackdropFilter: 'blur(12px)',
                border: '1px solid rgba(239,68,68,0.18)',
                boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.04)',
              }}>
                <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                <span className="text-red-200">{error}</span>
              </div>
            )}

            {/* Receiver Input */}
            <div>
              <label className="block text-[9px] font-semibold mb-2 ml-1 tracking-widest uppercase" style={{ color: 'rgba(144,231,238,0.6)' }}>Receiver</label>
              <div className="relative group">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-sm font-semibold z-10 pointer-events-none transition-colors" style={{ color: 'rgba(144,231,238,0.6)' }}>@</span>
                <input
                  type="text"
                  value={receiverUsername}
                  onChange={(e) => setReceiverUsername(e.target.value)}
                  placeholder="username"
                  className="w-full pl-9 pr-4 py-3.5 rounded-xl focus:outline-none text-white transition-all font-medium text-sm placeholder-white/25"
                  style={{
                    background: 'linear-gradient(145deg, rgba(255,255,255,0.05) 0%, rgba(0,36,34,0.55) 100%)',
                    backdropFilter: 'blur(20px)',
                    WebkitBackdropFilter: 'blur(20px)',
                    border: '1px solid rgba(255,255,255,0.11)',
                    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.07), 0 4px 16px rgba(0,0,0,0.2)',
                  }}
                  disabled={loading}
                  autoFocus
                />
              </div>
            </div>

            {/* From/To Section */}
            <div className="flex justify-between relative mb-7 sm:mb-10">
              {/* From Box */}
              <div
                className="w-[138px] md:w-[168px] rounded-2xl h-[142px] md:h-[166px] relative flex flex-col items-start justify-center p-4 transition-all"
                style={{
                  background: 'linear-gradient(145deg, rgba(255,255,255,0.055) 0%, rgba(0,36,34,0.62) 100%)',
                  backdropFilter: 'blur(24px) saturate(160%)',
                  WebkitBackdropFilter: 'blur(24px) saturate(160%)',
                  border: '1px solid rgba(255,255,255,0.11)',
                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 32px rgba(0,0,0,0.35)',
                }}
              >
                <span className="text-[9px] font-semibold mb-2 tracking-widest uppercase" style={{ color: 'rgba(144,231,238,0.6)' }}>From</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={fromAmount}
                  onChange={(e) => {
                    focusedFieldRef.current = "from";
                    const val = e.target.value.replace(/[^0-9.]/g, '');
                    isUpdatingToRef.current = false;
                    setFromAmount(val);
                  }}
                  onFocus={() => { focusedFieldRef.current = "from"; }}
                  placeholder="0"
                  className="bg-transparent text-3xl font-bold text-white text-left w-full focus:outline-none placeholder-white/20 leading-none"
                  disabled={loading}
                />
                <div className="text-[10px] mt-2 font-medium truncate w-full" style={{ color: 'rgba(144,231,238,0.55)' }}>
                  Balance: <span style={{ color: 'rgba(255,255,255,0.75)' }}>{fromBalanceValue.toFixed(2)}</span>
                </div>

                {/* Currency Selector Pill */}
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-20">
                  <div className="relative">
                    <select
                      value={selectedCurrency}
                      onChange={(e) => {
                        if (e.target.value !== "") {
                          setSelectedCurrency(e.target.value);
                        }
                      }}
                      className="appearance-none text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded-full cursor-pointer focus:outline-none transition-all w-[90px]"
                      style={{
                        background: 'linear-gradient(135deg, rgba(20,184,166,0.28) 0%, rgba(13,148,136,0.38) 100%)',
                        backdropFilter: 'blur(16px)',
                        WebkitBackdropFilter: 'blur(16px)',
                        border: '1px solid rgba(45,212,191,0.35)',
                        boxShadow: '0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.12)',
                      }}
                      disabled={loading}
                    >
                      {availableTokens.map((token) => (
                        <option
                          key={token.symbol}
                          value={token.isSeparator ? "" : token.symbol.replace(/^k/, "")}
                          disabled={token.isSeparator}
                          style={token.isSeparator ? optionSeparatorStyle : optionStyle}
                        >
                          {token.symbol.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5" style={{ color: 'rgba(144,231,238,0.8)' }}>
                      <ChevronDown size={11} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Arrow Button */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                <button
                  onClick={handleSwapCurrencies}
                  className="w-10 h-10 md:w-11 md:h-11 rounded-full flex items-center justify-center transition-all cursor-pointer hover:scale-110 active:scale-95"
                  style={{
                    background: 'linear-gradient(135deg, rgba(20,184,166,0.75) 0%, rgba(13,148,136,0.9) 100%)',
                    border: '1px solid rgba(45,212,191,0.45)',
                    boxShadow: '0 0 20px rgba(20,184,166,0.3), 0 4px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.2)',
                  }}
                  disabled={loading}
                >
                  <ArrowRight className="w-4 h-4 text-white" strokeWidth={2.5} />
                </button>
              </div>

              {/* To Box */}
              <div
                className="w-[138px] md:w-[168px] rounded-2xl h-[142px] md:h-[166px] relative flex flex-col items-start justify-center p-4 transition-all"
                style={{
                  background: 'linear-gradient(145deg, rgba(255,255,255,0.055) 0%, rgba(0,36,34,0.62) 100%)',
                  backdropFilter: 'blur(24px) saturate(160%)',
                  WebkitBackdropFilter: 'blur(24px) saturate(160%)',
                  border: '1px solid rgba(255,255,255,0.11)',
                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1), 0 8px 32px rgba(0,0,0,0.35)',
                }}
              >
                <span className="text-[9px] font-semibold mb-2 tracking-widest uppercase" style={{ color: 'rgba(144,231,238,0.6)' }}>To</span>
                <input
                  type="text"
                  inputMode="decimal"
                  value={toAmount}
                  onChange={(e) => {
                    focusedFieldRef.current = "to";
                    const val = e.target.value.replace(/[^0-9.]/g, '');
                    isUpdatingFromRef.current = false;
                    setToAmount(val);
                  }}
                  onFocus={() => { focusedFieldRef.current = "to"; }}
                  placeholder="0"
                  className="bg-transparent text-3xl font-bold text-white text-left w-full focus:outline-none placeholder-white/20 leading-none"
                  disabled={loading}
                />
                <div className={`text-[10px] mt-2 font-medium h-[15px] flex items-center truncate w-full ${(isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'animate-pulse' : ''}`} style={{ color: 'rgba(144,231,238,0.55)' }}>
                  {exchangeRate && !exchangeRateLoading ? (
                    <>
                      <span>1 {selectedCurrency && selectedCurrency.replace(/^k/, '')} =&nbsp;</span>
                      <span style={{ color: 'rgba(255,255,255,0.75)' }}>{exchangeRate.toFixed(2)} {toCurrency && toCurrency.replace(/^k/, '')}</span>
                    </>
                  ) : ((isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'Updating...' : '')}
                </div>

                {/* Currency Selector Pill */}
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-20">
                  <div className="relative">
                    <select
                      value={toCurrency}
                      onChange={(e) => {
                        if (e.target.value !== "") {
                          setToCurrency(e.target.value);
                        }
                      }}
                      className="appearance-none text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded-full cursor-pointer focus:outline-none transition-all w-[90px]"
                      style={{
                        background: 'linear-gradient(135deg, rgba(20,184,166,0.28) 0%, rgba(13,148,136,0.38) 100%)',
                        backdropFilter: 'blur(16px)',
                        WebkitBackdropFilter: 'blur(16px)',
                        border: '1px solid rgba(45,212,191,0.35)',
                        boxShadow: '0 4px 16px rgba(0,0,0,0.3), inset 0 1px 0 rgba(255,255,255,0.12)',
                      }}
                      disabled={loading}
                    >
                      {supportedTokensList.map((token) => (
                        <option
                          key={token.symbol}
                          value={token.isSeparator ? "" : token.symbol.replace(/^k/, "")}
                          disabled={token.isSeparator}
                          style={token.isSeparator ? optionSeparatorStyle : optionStyle}
                        >
                          {token.symbol.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5" style={{ color: 'rgba(144,231,238,0.8)' }}>
                      <ChevronDown size={11} />
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <div className="h-4 md:h-1" />
            <Button
              onClick={handleSend}
              disabled={
                loading ||
                !isValidCurrencyCombination ||
                isCalculatingFrom ||
                isCalculatingTo ||
                !hasSufficientBalance ||
                !isReceiverValid
              }
              className="w-full h-12 text-white text-sm font-bold rounded-xl transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed mt-5 sm:mt-8 relative z-10 hover:opacity-90 active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, rgba(20,184,166,0.82) 0%, rgba(13,148,136,0.92) 50%, rgba(8,110,102,0.88) 100%)',
                border: '1px solid rgba(45,212,191,0.3)',
                boxShadow: '0 0 24px rgba(20,184,166,0.2), 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.15)',
              }}
            >
              {loading ? (
                <div className="flex items-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  <span>Processing...</span>
                </div>
              ) : (
                <div className="flex items-center gap-2">
                  <ArrowUp className="w-4 h-4" />
                  <span>Send</span>
                </div>
              )}
            </Button>

            {loading && loadingMessage && (
              <p className="text-xs text-center animate-pulse" style={{ color: 'rgba(144,231,238,0.5)' }}>{loadingMessage}</p>
            )}
          </div>
        )}
    </WalletModalShell>
  );
}
