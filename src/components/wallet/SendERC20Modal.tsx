import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { ArrowRight } from "lucide-react";
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
        const allTokens: SupportedToken[] = [
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

        // Filter tokens to only include those with non-zero balances (for "from" dropdown)
        const availableList: SupportedToken[] = allTokens.filter((token) => {
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
        // Get rate: how much toCurrency per 1 fromCurrency
        const price = await getPoolRate(toTokenSymbol, fromTokenSymbol);

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
        // Get rate: how much toCurrency per 1 fromCurrency
        const price = await getPoolRate(toTokenSymbol, fromTokenSymbol);

        if (cancelled) return;

        if (price > 0) {
          isUpdatingFromRef.current = true;
          // To get FROM amount: TO amount / price
          const calculatedFrom = amountNum / price;
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
        // Get rate: how much toCurrency per 1 fromCurrency
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
    const tempCurrency = selectedCurrency;
    setSelectedCurrency(toCurrency);
    setToCurrency(tempCurrency);
    const tempAmount = fromAmount;
    setFromAmount(toAmount);
    setToAmount(tempAmount);
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

    // Get rate: how much toCurrency per 1 fromCurrency
    const price = await getPoolRate(toSymbol, fromSymbol); // toCurrency per 1 fromCurrency

    if (price <= 0) {
      throw new Error(`Cannot get price for swap ${fromSymbol.replace(/^k/, "")} → ${toSymbol.replace(/^k/, "")}`);
    }

    // Calculate how much fromCurrency we need to swap to get requiredToAmount of toCurrency
    const safety = 1.02; // +2% buffer for slippage/fees
    const requiredFromAmount = (requiredToAmount / price) * safety;

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
    }
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
      style={{ cursor: success ? 'pointer' : 'default' }}
    >
      <Card
        className="w-full max-w-lg bg-zinc-900/95 backdrop-blur-xl border border-zinc-800 shadow-2xl relative overflow-hidden rounded-3xl"
        onClick={e => e.stopPropagation()}
      >
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-bold text-white">
              Send Currency
            </CardTitle>
            <button
              onClick={() => onClose(false)}
              className="text-zinc-400 hover:text-white transition-colors"
              disabled={loading}
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Success Animation with Countdown */}
          {success && (
            <div
              className="flex flex-col items-center justify-center py-8 cursor-pointer"
              onClick={handleBackdropClick}
            >
              <div className="mb-4">
                <svg className="animate-checkmark" width="72" height="72" viewBox="0 0 72 72">
                  <circle cx="36" cy="36" r="34" fill="#1a2e22" stroke="#22c55e" strokeWidth="3" />
                  <path
                    d="M22 38l10 10 18-18"
                    fill="none"
                    stroke="#22c55e"
                    strokeWidth="4"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="checkmark-path"
                  />
                </svg>
              </div>
              <div className="text-green-400 text-lg font-semibold mb-2">Transaction Submitted!</div>
              <div className="text-zinc-300 text-sm text-center">{success}</div>
              <div className="mt-6 text-zinc-500 text-xs">
                Tap anywhere to close{closeCountdown > 0 && ` (${closeCountdown}s)`}
              </div>
            </div>
          )}

          {/* Form (hide if success) */}
          {!success && (
            <>
              {error && (
                <Alert variant="destructive" className="bg-red-900/80 border-red-700 text-red-200 rounded-xl">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {/* Receiver Username - At Top */}
              <div>
                <label className="block text-sm font-medium text-zinc-300 mb-2">Receiver</label>
                <div className="relative">
                  <span className="absolute left-4 top-1/2 transform -translate-y-1/2 text-zinc-500 text-lg">@</span>
                  <input
                    type="text"
                    value={receiverUsername}
                    onChange={(e) => setReceiverUsername(e.target.value)}
                    placeholder="username"
                    className="w-full pl-8 pr-4 py-3.5 border border-zinc-700 rounded-2xl focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all duration-200 bg-zinc-800/50 text-white placeholder-zinc-500"
                    disabled={loading}
                  />
                </div>
              </div>

              {/* From and To Boxes Row */}
              <div className="relative flex items-center gap-2">
                {/* From Box */}
                <div className="flex-1 relative">
                  <div className="bg-zinc-800/50 rounded-2xl p-5 border border-zinc-700/50 pb-12">
                    <div className="text-xs font-medium text-zinc-400 mb-2">From</div>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={fromAmount}
                      onChange={(e) => {
                        // Set focus immediately to prevent auto-updates while typing
                        focusedFieldRef.current = "from";
                        // Only allow numbers and decimal point
                        const value = e.target.value.replace(/[^0-9.]/g, '');
                        // Prevent multiple decimal points
                        const parts = value.split('.');
                        const filteredValue = parts.length > 2
                          ? parts[0] + '.' + parts.slice(1).join('')
                          : value;
                        isUpdatingToRef.current = false;
                        setFromAmount(filteredValue);
                      }}
                      onFocus={() => {
                        focusedFieldRef.current = "from";
                      }}
                      onBlur={() => {
                        // Delay clearing focus to allow any pending calculations to complete
                        setTimeout(() => {
                          focusedFieldRef.current = null;
                        }, 200);
                      }}
                      placeholder="0.00"
                      className="w-full text-2xl font-bold bg-transparent text-white placeholder-zinc-500 focus:outline-none"
                      disabled={loading}
                    />
                    <div className="text-xs text-zinc-400 mt-2">
                      Balance: <span className="text-zinc-300">{fromBalanceValue.toFixed(2)}</span>
                    </div>
                  </div>
                  {/* Currency Dropdown Overlay - Bottom Center */}
                  <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-1/2 z-10">
                    <div className="relative">
                      <select
                        value={selectedCurrency}
                        onChange={(e) => {
                          setSelectedCurrency(e.target.value);
                          setFromAmount("");
                          setToAmount("");
                        }}
                        className="appearance-none bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 rounded-xl px-4 py-2 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-8 shadow-lg"
                        disabled={loading}
                      >
                        {availableTokens.length === 0 ? (
                          <option value="">No balances</option>
                        ) : (
                          availableTokens.map((t) => (
                            <option key={t.symbol} value={t.symbol.replace(/^k/, "")}>
                              {t.symbol.replace(/^k/, "")}
                            </option>
                          ))
                        )}
                      </select>
                      <svg
                        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400"
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                      >
                        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  </div>
                  {isCalculatingTo && (
                    <div className="absolute top-2 right-2">
                      <svg className="animate-spin h-4 w-4 text-zinc-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </div>
                  )}
                </div>

                {/* Swap Button - Overlay */}
                <button
                  onClick={handleSwapCurrencies}
                  disabled={loading || !fromTokenSymbol || !toTokenSymbol}
                  className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed z-30 shadow-lg"
                >
                  <ArrowRight className="w-5 h-5 text-white" />
                </button>

                {/* To Box */}
                <div className="flex-1 relative">
                  <div className="bg-zinc-800/50 rounded-2xl p-5 border border-zinc-700/50 pb-12">
                    <div className="text-xs font-medium text-zinc-400 mb-2">To</div>
                    <input
                      type="text"
                      inputMode="decimal"
                      value={toAmount}
                      onChange={(e) => {
                        // Set focus immediately to prevent auto-updates while typing
                        focusedFieldRef.current = "to";
                        // Only allow numbers and decimal point
                        const value = e.target.value.replace(/[^0-9.]/g, '');
                        // Prevent multiple decimal points
                        const parts = value.split('.');
                        const filteredValue = parts.length > 2
                          ? parts[0] + '.' + parts.slice(1).join('')
                          : value;
                        isUpdatingFromRef.current = false;
                        setToAmount(filteredValue);
                      }}
                      onFocus={() => {
                        focusedFieldRef.current = "to";
                      }}
                      onBlur={() => {
                        // Delay clearing focus to allow any pending calculations to complete
                        setTimeout(() => {
                          focusedFieldRef.current = null;
                        }, 200);
                      }}
                      placeholder="0.00"
                      className="w-full text-2xl font-bold bg-transparent text-white placeholder-zinc-500 focus:outline-none"
                      disabled={loading}
                    />
                    <div className="text-xs text-zinc-400 mt-2">
                      {exchangeRateLoading ? (
                        <span className="text-zinc-500">Loading rate...</span>
                      ) : exchangeRate !== null ? (
                        <>
                          1 {toTokenSymbol.replace(/^k/, "")} = <span className="text-zinc-300">{exchangeRate.toFixed(2)}</span> {fromTokenSymbol.replace(/^k/, "")}
                        </>
                      ) : fromTokenSymbol && toTokenSymbol ? (
                        <span className="text-zinc-500">Rate unavailable</span>
                      ) : null}
                    </div>
                  </div>
                  {/* Currency Dropdown Overlay - Bottom Center */}
                  <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-1/2 z-10">
                    <div className="relative">
                      <select
                        value={toCurrency}
                        onChange={(e) => {
                          setToCurrency(e.target.value);
                          setFromAmount("");
                          setToAmount("");
                        }}
                        className="appearance-none bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 rounded-xl px-4 py-2 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-8 shadow-lg"
                        disabled={loading}
                      >
                        {supportedTokensList.map((t: SupportedToken) => (
                          <option key={t.symbol} value={t.symbol.replace(/^k/, "")}>
                            {t.symbol.replace(/^k/, "")}
                          </option>
                        ))}
                      </select>
                      <svg
                        className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-zinc-400"
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                      >
                        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  </div>
                  {isCalculatingFrom && (
                    <div className="absolute top-2 right-2">
                      <svg className="animate-spin h-4 w-4 text-zinc-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                    </div>
                  )}
                </div>
              </div>

              {/* Action Button */}
              <div className="pt-8">
                <Button
                  onClick={handleSend}
                  disabled={loading || !receiverUsername.trim() || !fromAmount.trim() || !toAmount.trim() || !selectedCurrency || !toCurrency || !hasSufficientBalance || !isValidCurrencyCombination}
                  className="w-full bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white py-4 rounded-2xl text-lg font-semibold shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
                >
                  {loading && (
                    <svg className="animate-spin h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  )}
                  Send
                </Button>
              </div>

              {/* Loading Message Display at Bottom */}
              {loading && loadingMessage && (
                <div className="pt-4 text-center">
                  <p className="text-zinc-300 text-sm">{loadingMessage}</p>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
