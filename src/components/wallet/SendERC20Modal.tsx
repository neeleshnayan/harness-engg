import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowRight, Loader2, X, ArrowUp, ChevronDown } from "lucide-react";
import api, { kryptonWeb3Api } from "@/lib/api";
import { useRates } from "@/providers/RatesProvider";
import { getPoolRate } from "@/lib/ratesApi";

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
  const [success, setSuccess] = useState<string | null>(null);
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
          onClose(true); // Auto-close: switch to transaction history
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
        setLoadingMessage("Loading supported currencies...");

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
                   symbol: "--- Other Assets ---",
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
        // Filter tokens to only include those with non-zero balances (for "from" dropdown)
        // Ensure we don't include separators or RWA tokens in the "From" list for now (unless user has balance, but simpler to restrict to K-tokens/USDC as per "as are currently")
        const availableList: SupportedToken[] = allTokens.filter((token) => {
          if (token.isSeparator) return false;
          // Verify it's a K-token or USDC (existing logic implies K_TOKEN_SYMBOLS check or USDC)
          // Actually, let's just use balance check. If they have RWA balance, maybe they should be able to send it?
          // User said "not actually going to use these other tokens for swaps/payments... but let's just show them in dropdown".
          // This likely applies to "To" dropdown. "From" dropdown is usually what you hold.
          // Let's filter out separators for sure.
          const tokenBalance = balances[token.symbol] || 0;
          return tokenBalance > 0;
        });

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
    if (!selectedCurrency) {
      return "";
    }
    return selectedCurrency === "USDC" ? "USDC" : `k${selectedCurrency}`;
  }, [selectedCurrency]);

  const toTokenSymbol = useMemo(() => {
    if (!toCurrency) {
      return "";
    }
    return toCurrency === "USDC" ? "USDC" : `k${toCurrency}`;
  }, [toCurrency]);

  const fetchUserBalances = async (): Promise<Record<string, number>> => {
    // Extract k-token balances from the balance prop (similar to KTTokenBalances)
    const balances: Record<string, number> = {};

    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return balances;
    }

    for (const tb of balance.tokenBalances) {
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const kSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : undefined;
      const tokenSymbol = tb?.token?.symbol;

      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      if (kSymbol) {
        balances[kSymbol] = (balances[kSymbol] || 0) + rawAmount;
        continue;
      }

      if (tokenSymbol === "USDC") {
        balances["USDC"] = (balances["USDC"] || 0) + rawAmount;
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

  // Check if currency combination is valid (both USDC or both non-USDC)
  const isValidCurrencyCombination = useMemo(() => {
    if (!fromTokenSymbol || !toTokenSymbol) return false;

    const fromIsUSDC = fromTokenSymbol === "USDC";
    const toIsUSDC = toTokenSymbol === "USDC";

    // Valid if both are USDC or both are non-USDC
    return (fromIsUSDC && toIsUSDC) || (!fromIsUSDC && !toIsUSDC);
  }, [fromTokenSymbol, toTokenSymbol]);

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
   * Perform swap using Krypton_Web3 /pools/swap endpoint (Circle-based)
   */
  const performSwap = async (fromSymbol: string, toSymbol: string, requiredToAmount: number): Promise<string | null> => {
    setLoadingMessage(`Checking swap price from ${fromSymbol.replace(/^k/, "")} to ${toSymbol.replace(/^k/, "")}...`);
    const balances = await fetchUserBalances();

    // Get rate: rate(to -> from) to calculate input needed for exact output
    const price = await getPoolRate(toSymbol, fromSymbol);

    if (price <= 0) {
      throw new Error(`Cannot get price for swap ${fromSymbol.replace(/^k/, "")} → ${toSymbol.replace(/^k/, "")}`);
    }

    // Calculate how much fromCurrency we need to swap to get requiredToAmount of toCurrency
    const safety = 1.02; // +2% buffer for slippage/fees
    // requiredFrom = requiredTo * Rate(to->from)
    const requiredFromAmount = (requiredToAmount * price) * safety;

    const fromBalance = balances[fromSymbol] || 0;
    if (fromBalance < requiredFromAmount) {
      throw new Error(`Insufficient ${fromSymbol.replace(/^k/, "")} balance. Need ${requiredFromAmount.toFixed(4)}, have ${fromBalance.toFixed(4)}`);
    }

    setLoadingMessage(`Swapping ${requiredFromAmount.toFixed(4)} ${fromSymbol.replace(/^k/, "")} → ${toSymbol.replace(/^k/, "")}...`);

    // Use Krypton_Web3 endpoint with wallet_address (Circle-based transaction)
    const response = await kryptonWeb3Api.post(`/pools/swap`, {
      from_token: fromSymbol,
      to_token: toSymbol,
      amount: requiredFromAmount,
      wallet_address: userAddress,
      wallet_username: username,
    });

    // Return transaction ID for tracking
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
    const toAmountNum = parseFloat(toAmount);
    if (!toAmount.trim() || isNaN(toAmountNum) || toAmountNum <= 0) {
      setError("Please enter a valid amount.");
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

      // Determine which currency to send (the "to" currency)
      const sendCurrency = toTokenSymbol;
      const sendCurrencyDisplay = sendCurrency === "USDC" ? "USDC" : sendCurrency.replace(/^k/, "");

      if (sendCurrency === "USDC") {
        // Use the USDC send endpoint (same as SendUSDCModal)
        if (!userId) {
          throw new Error("User ID is required to send USDC.");
        }

        const usdcBalance = balances["USDC"] || 0;
        if (usdcBalance < toAmountNum) {
          throw new Error(`Insufficient USDC balance. You have ${usdcBalance.toFixed(2)} USDC, but need ${toAmountNum.toFixed(2)}.`);
        }

        setLoadingMessage(`Sending ${toAmountNum.toFixed(2)} USDC...`);
        await api.post("/api/v1/send_usdc", {
          sender_user_id: userId,
          receiver_username: receiverUsername.trim(),
          amount: toAmountNum
        });
      } else {
        // For k-tokens, resolve address and use swap/transfer flow
        setLoadingMessage("Resolving receiver address...");
        const toAddress = await resolveReceiverAddress(receiverUsername.trim());

        const fromCurrency = fromTokenSymbol;
        if (!fromCurrency) {
          throw new Error("Please select a from currency.");
        }

        if (fromCurrency !== sendCurrency) {
          await performSwap(fromCurrency, sendCurrency, toAmountNum);

          // Small delay to allow backend to propagate swap status and UI to update
          // This improves UX (user sees "Swap Submitted") and helps avoid race conditions
          await new Promise(resolve => setTimeout(resolve, 1000));
        } else {
          const fromBalance = balances[fromCurrency] || 0;
          const fromAmountNum = parseFloat(fromAmount);
          if (fromBalance < fromAmountNum) {
            const fromDisplay = fromCurrency.replace(/^k/, "");
            throw new Error(`Insufficient balance. You have ${fromBalance.toFixed(4)} ${fromDisplay}, but need ${fromAmountNum.toFixed(4)}.`);
          }
        }

        setLoadingMessage(`Transferring ${toAmountNum.toFixed(2)} ${sendCurrencyDisplay} to @${receiverUsername}...`);
        await transferTokens(sendCurrency, toAddress, toAmountNum);
      }

      // Show success with countdown (non-blocking)
      setSuccess(`Transaction submitted: ${toAmountNum.toFixed(2)} ${sendCurrencyDisplay} to @${receiverUsername}`);
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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#001C1B]/60 backdrop-blur-md p-4 animate-in fade-in duration-200"
      onClick={handleBackdropClick}
    >
      <div
        className="w-full max-w-[440px] bg-[#001C1B] bg-cover bg-center shadow-2xl relative overflow-visible rounded-xl p-6 animate-in zoom-in-95 duration-200 border border-white/5"
        style={{ backgroundImage: "url('/wallet-bg.svg')" }}
        onClick={(e) => !success && e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-8">
           <h2 className="text-2xl font-bold text-white tracking-tight">Send Currency</h2>
           <button
             onClick={() => onClose(false)}
             className="text-teal-200/60 hover:text-white transition-colors"
           >
             <X size={24} />
           </button>
        </div>

          {/* Success Animation */}
          {success && (
            <div
              className="flex flex-col items-center justify-center py-8 cursor-pointer"
            >
              <div className="mb-6 relative">
                <div className="absolute inset-0 bg-green-500/20 blur-xl rounded-full"></div>
                <img src="/tx-success.svg" alt="Success" width="100" height="100" className="relative animate-pulse drop-shadow-[0_0_15px_rgba(74,222,128,0.5)]" />
              </div>
              <div className="text-green-400 text-lg font-bold mb-2 tracking-wide">Transaction Submitted!</div>
              <div className="text-teal-200/80 text-sm text-center max-w-[80%] leading-relaxed">{success}</div>
              <div className="mt-8 text-teal-200/60 text-xs font-medium">
                Tap anywhere to close{closeCountdown > 0 && ` (${closeCountdown}s)`}
              </div>
            </div>
          )}

          {/* Form */}
          {!success && (
            <div className="space-y-6">
              {error && (
                <div className="bg-red-500/10 border border-red-500/20 text-red-200 text-sm p-3 rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Receiver Input */}
              <div>
                <label className="block text-sm font-bold mb-2 ml-1 text-white tracking-tight">Receiver</label>
                <div className="relative group">
                  <span className="absolute left-3 top-1/2 -translate-y-1/2 text-base group-focus-within:text-white transition-colors z-10 pointer-events-none" style={{ color: 'rgba(161, 207, 211, 0.7)' }}>@</span>
                  <input
                    type="text"
                    value={receiverUsername}
                    onChange={(e) => setReceiverUsername(e.target.value)}
                    placeholder="username"
                    className="w-full pl-8 pr-3 py-3 backdrop-blur-sm rounded-md focus:outline-none text-white transition-all font-medium text-base"
                    style={{
                      background: 'rgba(58, 96, 97, 0.5)',
                      border: '1px solid rgba(255, 255, 255, 0.1)'
                    }}
                    disabled={loading}
                    autoFocus
                  />
                </div>
              </div>

               {/* From/To Section */}
               <div className="flex justify-between relative mb-4">
                  {/* From Box */}
                  <div
                    className="w-[130px] md:w-[160px] rounded-md h-[130px] md:h-[160px] relative flex flex-col items-start justify-center p-4 transition-colors group"
                    style={{
                      background: 'linear-gradient(180deg, rgba(58, 96, 97, 0.6) 0%, rgba(125, 160, 161, 0.6) 100%)',
                      backdropFilter: 'blur(10px)',
                      border: '1px solid rgba(255, 255, 255, 0.1)'
                    }}
                  >
                     <span className="text-[10px] font-medium mb-1.5" style={{ color: 'rgba(161, 207, 211, 0.8)' }}>From</span>
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
                        className="bg-transparent text-2xl font-bold text-white text-left w-full focus:outline-none placeholder-white/30"
                        disabled={loading}
                     />
                     <div className="text-[10px] mt-1 font-medium truncate w-full" style={{ color: 'rgba(161, 207, 211, 0.7)' }}>
                        Balance: <span className="text-white">{fromBalanceValue.toFixed(2)}</span>
                     </div>

                     {/* Currency Selector Pill */}
                     <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 z-20">
                        <div className="relative shadow-xl">
                            <select
                                value={selectedCurrency}
                                onChange={(e) => setSelectedCurrency(e.target.value)}
                                className="appearance-none text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded cursor-pointer focus:outline-none transition-colors w-[85px]"
                                style={{
                                  background: '#115E59',
                                  border: '1px solid rgba(255, 255, 255, 0.15)'
                                }}
                                disabled={loading}
                            >
                                {availableTokens.map((token) => (
                                <option key={token.symbol} value={token.symbol.replace(/^k/, "")}>
                                    {token.symbol.replace(/^k/, "")}
                                </option>
                                ))}
                            </select>
                            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2" style={{ color: 'rgba(161, 207, 211, 0.7)' }}>
                                <ChevronDown size={12} />
                            </div>
                        </div>
                     </div>
                  </div>

                  {/* Arrow Button */}
                  <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                     <button
                        onClick={handleSwapCurrencies}
                        className="w-10 h-10 md:w-12 md:h-12 rounded-full flex items-center justify-center shadow-lg hover:scale-110 transition-all cursor-pointer"
                        style={{
                          background: 'rgba(85, 124, 130, 1)'
                        }}
                        disabled={loading}
                     >
                        <ArrowRight className="w-4 h-4 md:w-5 md:h-5 text-white" strokeWidth={2.5} />
                     </button>
                  </div>

                  {/* To Box */}
                  <div
                    className="w-[130px] md:w-[160px] rounded-md h-[130px] md:h-[160px] relative flex flex-col items-start justify-center p-4 transition-colors group"
                    style={{
                      background: 'linear-gradient(180deg, rgba(58, 96, 97, 0.6) 0%, rgba(125, 160, 161, 0.6) 100%)',
                      backdropFilter: 'blur(10px)',
                      border: '1px solid rgba(255, 255, 255, 0.1)'
                    }}
                  >
                     <span className="text-[10px] font-medium mb-1.5" style={{ color: 'rgba(161, 207, 211, 0.8)' }}>To</span>
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
                        className="bg-transparent text-2xl font-bold text-white text-left w-full focus:outline-none placeholder-white/30"
                        disabled={loading}
                     />
                     <div className={`text-[10px] mt-1 font-medium h-[15px] flex items-center truncate w-full ${(isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'animate-pulse text-white/50' : ''}`}>
                        {exchangeRate && !exchangeRateLoading ? (
                          <>
                            <span style={{ color: 'rgba(161, 207, 211, 0.7)' }}>1 {selectedCurrency && selectedCurrency.replace(/^k/, '')} =&nbsp;</span>
                            <span className="text-white">{exchangeRate.toFixed(2)} {toCurrency && toCurrency.replace(/^k/, '')}</span>
                          </>
                        ) : ((isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'Updating...' : '')}
                     </div>

                     {/* Currency Selector Pill */}
                     <div className="absolute -bottom-3 left-1/2 -translate-x-1/2 z-20">
                        <div className="relative shadow-xl">
                            <select
                                value={toCurrency}
                                onChange={(e) => setToCurrency(e.target.value)}
                                className="appearance-none text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded cursor-pointer focus:outline-none transition-colors w-[85px]"
                                style={{
                                  background: '#115E59',
                                  border: '1px solid rgba(255, 255, 255, 0.15)'
                                }}
                                disabled={loading}
                            >
                                {supportedTokensList.map((token) => (
                                <option key={token.symbol} value={token.isSeparator ? "" : token.symbol.replace(/^k/, "")} disabled={token.isSeparator}>
                                    {token.symbol.replace(/^k/, "")}
                                </option>
                                ))}
                            </select>
                            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2" style={{ color: 'rgba(161, 207, 211, 0.7)' }}>
                                <ChevronDown size={12} />
                            </div>
                        </div>
                     </div>
                  </div>
               </div>

               <Button
                 onClick={handleSend}
                 disabled={loading || !isValidCurrencyCombination || isCalculatingFrom || isCalculatingTo || !hasSufficientBalance}
                 className="w-full h-11 text-white text-sm font-bold rounded-md shadow-lg transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed mt-5 relative z-10"
                 style={{
                   background: 'rgba(85, 124, 130, 0.9)',
                   border: '1px solid rgba(255, 255, 255, 0.15)'
                 }}
               >
                 {loading ? (
                   <div className="flex items-center gap-2">
                       <Loader2 className="h-5 w-5 animate-spin" />
                       <span>Processing...</span>
                   </div>
                 ) : (
                    <div className="flex items-center gap-2">
                        <ArrowUp className="w-5 h-5" />
                        <span>Send</span>
                    </div>
                 )}
               </Button>

               {loading && loadingMessage && (
                  <p className="text-teal-200/60 text-xs text-center animate-pulse">{loadingMessage}</p>
               )}
            </div>
          )}
      </div>
    </div>
  );
}
