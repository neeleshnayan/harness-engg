import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { kryptonWeb3Api } from "@/lib/api";
import { K_TOKEN_ADDRESSES_LOWERCASE, K_TOKEN_SYMBOL_LIST } from "@/lib/kTokens";
import { getPoolRate } from "@/lib/priceCache";
import { ArrowUpDown } from "lucide-react";

interface SwapModalProps {
  visible: boolean;
  /** Called when modal closes. autoClose=true means countdown auto-closed, false means user manually closed */
  onClose: (autoClose?: boolean) => void;
  userAddress?: string;
  username?: string; // Added for Krypton_Web3 endpoints
  balance?: any;
}

// Countdown toast timeout in seconds
const CLOSE_COUNTDOWN_SECONDS = 5;

const SwapModal: React.FC<SwapModalProps> = ({ visible, onClose, userAddress, username, balance }) => {
  const [fromAmount, setFromAmount] = useState<string>("");
  const [fromCurrency, setFromCurrency] = useState<string>("kUSD");
  const [toCurrency, setToCurrency] = useState<string>("kEUR");
  const [toAmount, setToAmount] = useState<string>("");
  const [loading, setLoading] = useState<boolean>(false);
  const [isCalculatingFrom, setIsCalculatingFrom] = useState<boolean>(false);
  const [isCalculatingTo, setIsCalculatingTo] = useState<boolean>(false);
  const [exchangeRate, setExchangeRate] = useState<number | null>(null);
  const [exchangeRateLoading, setExchangeRateLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [closeCountdown, setCloseCountdown] = useState<number>(0);
  const isUpdatingFromRef = useRef<boolean>(false);
  const isUpdatingToRef = useRef<boolean>(false);
  const focusedFieldRef = useRef<"from" | "to" | null>(null);
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null);

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

  const balances = useMemo(() => {
    const result: Record<string, number> = {};
    if (!balance || !Array.isArray(balance?.tokenBalances)) {
      return result;
    }

    for (const tb of balance.tokenBalances) {
      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const tokenSymbol = tb?.token?.symbol;
      const kSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;

      if (kSymbol) {
        result[kSymbol] = (result[kSymbol] || 0) + rawAmount;
      } else if (tokenSymbol === "USDC" || tokenSymbol === "TRNSK") {
        result["USDC"] = (result["USDC"] || 0) + rawAmount;
      }
    }

    return result;
  }, [balance]);

  const supportedTokens = useMemo(() => {
    const tokens = new Set<string>(["kUSD"]);
    K_TOKEN_SYMBOL_LIST.forEach((token) => tokens.add(token));
    return Array.from(tokens);
  }, []);

  useEffect(() => {
    if (!visible) {
      setFromAmount("");
      setToAmount("");
      setError(null);
      setSuccess(null);
      setExchangeRate(null);
      setExchangeRateLoading(false);
      setCloseCountdown(0);
      focusedFieldRef.current = null;
      // Clear countdown
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
      return;
    }
  }, [visible]);

  // Calculate To amount when From amount changes
  useEffect(() => {
    // Don't update if user is currently typing in the "to" field
    if (focusedFieldRef.current === "to") {
      return;
    }

    if (!visible || !fromCurrency || !toCurrency || !fromAmount) {
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

    // If currencies are the same, just set equal amounts
    if (fromCurrency === toCurrency) {
      isUpdatingToRef.current = true;
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
        const price = await getPoolRate(toCurrency, fromCurrency);
        if (cancelled) return;
        if (price > 0) {
          isUpdatingToRef.current = true;
          const calculatedTo = amountNum * price;
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
  }, [fromAmount, fromCurrency, toCurrency, visible]);

  // Calculate From amount when To amount changes
  useEffect(() => {
    // Don't update if user is currently typing in the "from" field
    if (focusedFieldRef.current === "from") {
      return;
    }

    if (!visible || !fromCurrency || !toCurrency || !toAmount) {
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

    // If currencies are the same, just set equal amounts
    if (fromCurrency === toCurrency) {
      isUpdatingFromRef.current = true;
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
        const price = await getPoolRate(toCurrency, fromCurrency);
        if (cancelled) return;
        if (price > 0) {
          isUpdatingFromRef.current = true;
          const calculatedFrom = amountNum / price;
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
  }, [toAmount, fromCurrency, toCurrency, visible]);

  // Calculate exchange rate for display
  useEffect(() => {
    if (!visible || !fromCurrency || !toCurrency) {
      setExchangeRate(null);
      setExchangeRateLoading(false);
      return;
    }

    if (fromCurrency === toCurrency) {
      setExchangeRate(1);
      setExchangeRateLoading(false);
      return;
    }

    let cancelled = false;

    const fetchExchangeRate = async () => {
      setExchangeRateLoading(true);
      try {
        const price = await getPoolRate(fromCurrency, toCurrency);
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
  }, [fromCurrency, toCurrency, visible]);

  // Handle swap currencies
  const handleSwapCurrencies = () => {
    const tempCurrency = fromCurrency;
    setFromCurrency(toCurrency);
    setToCurrency(tempCurrency);
    const tempAmount = fromAmount;
    setFromAmount(toAmount);
    setToAmount(tempAmount);
  };

  const amountValue = parseFloat(fromAmount);
  const fromBalance = balances[fromCurrency] || 0;
  const canSwap =
    !isCalculatingFrom &&
    !isCalculatingTo &&
    !loading &&
    fromAmount !== "" &&
    toAmount !== "" &&
    !isNaN(amountValue) &&
    amountValue > 0 &&
    fromBalance >= amountValue &&
    fromCurrency !== toCurrency;

  const handleSwap = async () => {
    setError(null);
    setSuccess(null);

    if (!userAddress) {
      setError("Wallet address unavailable.");
      return;
    }

    if (isNaN(amountValue) || amountValue <= 0) {
      setError("Enter a valid amount to swap.");
      return;
    }

    if (fromCurrency === toCurrency) {
      setError("Select different currencies to swap.");
      return;
    }

    const availableBalance = balances[fromCurrency] || 0;
    if (availableBalance < amountValue) {
      setError(`Insufficient ${fromCurrency.replace(/^k/, "")} balance. Available: ${availableBalance.toFixed(4)}`);
      return;
    }

    try {
      setLoading(true);

      // Use Krypton_Web3 endpoint (Circle-based transaction)
      const swapResponse = await kryptonWeb3Api.post("/pools/swap", {
        from_token: fromCurrency,
        to_token: toCurrency,
        amount: amountValue,
        wallet_address: userAddress,
        wallet_username: username,
      });

      const estimatedOutput = swapResponse.data?.estimated_output || toAmount;

      // Show success with countdown (non-blocking)
      setSuccess(`Swap submitted: ${amountValue.toFixed(2)} ${fromCurrency.replace(/^k/, "")} → ${parseFloat(estimatedOutput).toFixed(2)} ${toCurrency.replace(/^k/, "")}`);
      setFromAmount("");
      setToAmount("");
      startCloseCountdown();
    } catch (err: any) {
      console.error("Swap failed:", err);
      setError(err?.response?.data?.detail || err?.response?.data?.message || err?.message || "Swap failed. Try again.");
    } finally {
      setLoading(false);
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

  if (!visible) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
      style={{ cursor: success ? 'pointer' : 'default' }}
    >
      <div className="bg-zinc-900/95 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-white">Swap Assets</h3>
          <button className="text-zinc-400 hover:text-white" onClick={() => onClose(false)} disabled={loading}>
            ✕
          </button>
        </div>

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
            <div className="text-green-400 text-lg font-semibold mb-2">Swap Submitted!</div>
            <div className="text-zinc-300 text-sm text-center">{success}</div>
            <div className="mt-6 text-zinc-500 text-xs">
              Tap anywhere to close{closeCountdown > 0 && ` (${closeCountdown}s)`}
            </div>
          </div>
        )}

        {/* Form (hide if success) */}
        {!success && (
          <>
            {error && <div className="mb-3 rounded-xl border border-red-500/40 bg-red-500/10 text-red-200 px-4 py-2 text-sm">{error}</div>}

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
                    Balance: <span className="text-zinc-300">{fromBalance.toFixed(2)}</span>
                  </div>
                </div>
                {/* Currency Dropdown Overlay - Bottom Center */}
                <div className="absolute bottom-0 left-1/2 transform -translate-x-1/2 translate-y-1/2 z-10">
                  <div className="relative">
                    <select
                      value={fromCurrency}
                      onChange={(e) => {
                        const newValue = e.target.value;
                        setFromCurrency(newValue);
                        setFromAmount("");
                        setToAmount("");
                        if (newValue === toCurrency) {
                          const alternative = supportedTokens.find((token) => token !== newValue);
                          if (alternative) {
                            setToCurrency(alternative);
                          }
                        }
                      }}
                      className="appearance-none bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 rounded-xl px-4 py-2 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-8 shadow-lg"
                      disabled={loading}
                    >
                      {supportedTokens.map((token) => (
                        <option key={token} value={token}>
                          {token.replace(/^k/, "")}
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
                disabled={loading || !fromCurrency || !toCurrency}
                className="absolute left-1/2 top-1/2 transform -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed z-30 shadow-lg"
              >
                <ArrowUpDown className="w-5 h-5 text-white rotate-90" />
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
                        1 {toCurrency.replace(/^k/, "")} = <span className="text-zinc-300">{exchangeRate.toFixed(2)}</span> {fromCurrency.replace(/^k/, "")}
                      </>
                    ) : fromCurrency && toCurrency ? (
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
                        const newValue = e.target.value;
                        setToCurrency(newValue);
                        setFromAmount("");
                        setToAmount("");
                        if (newValue === fromCurrency) {
                          const alternative = supportedTokens.find((token) => token !== newValue);
                          if (alternative) {
                            setFromCurrency(alternative);
                          }
                        }
                      }}
                      className="appearance-none bg-zinc-700 hover:bg-zinc-600 border-2 border-zinc-600 rounded-xl px-4 py-2 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-8 shadow-lg"
                      disabled={loading}
                    >
                      {supportedTokens.map((token) => (
                        <option key={token} value={token}>
                          {token.replace(/^k/, "")}
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

            <button
              onClick={handleSwap}
              disabled={!canSwap}
              className="mt-10 w-full bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white font-semibold py-3 rounded-2xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? "Swapping..." : "Swap"}
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default SwapModal;
