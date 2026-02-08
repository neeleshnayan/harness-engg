import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { kryptonWeb3Api } from "@/lib/api";
import { useRates } from "@/providers/RatesProvider";
import { getPoolRate } from "@/lib/ratesApi";
import { ArrowRight, ChevronDown } from "lucide-react";

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

  // Get token data from context 🚀
  const { tokens, getTokenAddressToSymbol } = useRates();
  const tokenAddressMap = useMemo(() => getTokenAddressToSymbol(), [getTokenAddressToSymbol]);
  const kTokenSymbolList = useMemo(() => Object.keys(tokens).filter(s => s.startsWith('k')), [tokens]);

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
      const kSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : undefined;

      if (kSymbol) {
        result[kSymbol] = (result[kSymbol] || 0) + rawAmount;
      } else if (tokenSymbol === "USDC") {
        result["USDC"] = (result["USDC"] || 0) + rawAmount;
      }
    }

    return result;
  }, [balance, tokenAddressMap]);

  const supportedTokens = useMemo(() => {
    const tokenSet = new Set<string>(["kUSD"]);
    kTokenSymbolList.forEach((token) => tokenSet.add(token));
    return Array.from(tokenSet);
  }, [kTokenSymbolList]);

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
        // Get rate: rate(from -> to) so we can multiply
        const price = await getPoolRate(fromCurrency, toCurrency);
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
        // Get rate: rate(to -> from) so we can multiply
        const price = await getPoolRate(toCurrency, fromCurrency);
        if (cancelled) return;
        if (price > 0) {
          isUpdatingFromRef.current = true;
          const calculatedFrom = amountNum * price;
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
        // Get rate: how much toCurrency per 1 fromCurrency (for display "1 From = X To")
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
    } else {
      onClose(false); // User cancelled
    }
  };

  if (!visible) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#001C1B]/60 backdrop-blur-md p-4 animate-in fade-in duration-200"
      onClick={handleBackdropClick}
    >
      <div
        className="w-full max-w-[440px] bg-[#001C1B] bg-cover bg-center shadow-2xl relative overflow-visible rounded-[32px] p-8 animate-in zoom-in-95 duration-200 border border-white/5"
        style={{ backgroundImage: "url('/wallet-bg.svg')" }}
        onClick={(e) => !success && e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-8">
           <h2 className="text-2xl font-bold text-white tracking-tight">Swap Assets</h2>
           <button
             onClick={() => onClose(false)}
             className="text-teal-200/60 hover:text-white transition-colors"
           >
             <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
           </button>
        </div>

        {/* Success Animation */}
        {success && (
          <div
            className="flex flex-col items-center justify-center py-8 cursor-pointer"
            onClick={handleBackdropClick}
          >
            <div className="mb-6 relative">
                 <div className="absolute inset-0 bg-green-500/20 blur-xl rounded-full"></div>
                 <img src="/tx-success.svg" alt="Success" width="100" height="100" className="relative animate-pulse drop-shadow-[0_0_15px_rgba(74,222,128,0.5)]" />
            </div>
            <div className="text-green-400 text-lg font-bold mb-2 tracking-wide">Swap Submitted!</div>
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
                <div className="bg-red-500/10 border border-red-500/20 text-red-200 text-sm p-3 rounded-2xl flex items-center gap-2">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                  <span>{error}</span>
                </div>
            )}

            {/* Swap Area */}
            <div className="flex gap-3 relative mb-4">
               {/* From Box */}
               <div
                  className="flex-1 rounded-2xl h-[150px] relative flex flex-col items-start justify-center p-4 border border-white/5 transition-colors group"
                  style={{ backgroundImage: "url('/glass-box.svg')", backgroundSize: 'cover', backgroundPosition: 'center' }}
                >
                   <span className="text-zinc-400 text-xs font-medium mb-1">From</span>
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
                      className="bg-transparent text-2xl font-bold text-white text-left w-full focus:outline-none placeholder-white/50"
                      disabled={loading}
                   />
                   <div className="text-[10px] text-zinc-400 mt-1 font-medium">
                       Balance: <span className="text-white">{fromBalance.toFixed(2)}</span>
                   </div>

                   {/* Selector */}
                   <div className="absolute -bottom-3.5 left-1/2 -translate-x-1/2 z-20">
                       <div className="relative shadow-xl">
                           <select
                               value={fromCurrency}
                               onChange={(e) => {
                                   const val = e.target.value;
                                   setFromCurrency(val);
                                   if (val === toCurrency) {
                                     const alt = supportedTokens.find(t => t !== val);
                                     if (alt) setToCurrency(alt);
                                   }
                               }}
                               className="appearance-none bg-[#115E59] hover:bg-[#134E4A] text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded-lg cursor-pointer focus:outline-none transition-colors border border-white/10"
                               disabled={loading}
                           >
                               {supportedTokens.map((token) => (
                                 <option key={token} value={token}>{token.replace(/^k/, "")}</option>
                               ))}
                           </select>
                           <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-teal-200/70">
                               <ChevronDown size={10} />
                           </div>
                       </div>
                   </div>
               </div>

               {/* Swap Button */}
               <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                   <button
                     onClick={handleSwapCurrencies}
                     disabled={loading}
                     className="w-8 h-8 rounded-full bg-[#557C82] border-2 border-[#001C1B] flex items-center justify-center shadow-lg hover:scale-110 transition-transform cursor-pointer"
                   >
                     <ArrowRight className="w-4 h-4 text-white" />
                   </button>
               </div>

               {/* To Box */}
               <div
                  className="flex-1 rounded-2xl h-[150px] relative flex flex-col items-start justify-center p-4 border border-white/5 transition-colors group"
                  style={{ backgroundImage: "url('/glass-box.svg')", backgroundSize: 'cover', backgroundPosition: 'center' }}
                >
                   <span className="text-zinc-400 text-xs font-medium mb-1">To</span>
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
                      className="bg-transparent text-2xl font-bold text-white text-left w-full focus:outline-none placeholder-white/50"
                      disabled={loading}
                   />
                   <div className={`text-[10px] mt-1 font-medium truncate max-w-[90px] h-[15px] flex items-center ${(isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'animate-pulse text-white/50' : 'text-white font-bold'}`}>
                     {exchangeRate ? `1 ${fromCurrency.replace(/^k/, '')} = ${exchangeRate.toFixed(2)} ${toCurrency.replace(/^k/, '')}` : ((isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'Updating...' : '')}
                   </div>

                   {/* Selector */}
                   <div className="absolute -bottom-3.5 left-1/2 -translate-x-1/2 z-20">
                       <div className="relative shadow-xl">
                           <select
                               value={toCurrency}
                               onChange={(e) => {
                                   const val = e.target.value;
                                   setToCurrency(val);
                                   if (val === fromCurrency) {
                                     const alt = supportedTokens.find(t => t !== val);
                                     if (alt) setFromCurrency(alt);
                                   }
                               }}
                               className="appearance-none bg-[#115E59] hover:bg-[#134E4A] text-white text-xs font-bold py-1.5 pl-3 pr-7 rounded-lg cursor-pointer focus:outline-none transition-colors border border-white/10"
                               disabled={loading}
                           >
                               {supportedTokens.map((token) => (
                                 <option key={token} value={token}>{token.replace(/^k/, "")}</option>
                               ))}
                           </select>
                           <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-teal-200/70">
                               <ChevronDown size={10} />
                           </div>
                       </div>
                   </div>

                   {(isCalculatingFrom || isCalculatingTo) && (
                      <div className="absolute top-3 right-3">
                         <svg className="animate-spin h-3 w-3 text-teal-500/50" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
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
               className="w-full h-14 bg-gradient-to-b from-[#557C82] to-[#3C5F63] hover:from-[#4A7A7E] hover:to-[#33565A] text-white text-lg font-bold rounded-2xl shadow-lg border border-white/10 transition-all duration-300 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-4 relative z-10"
            >
              {loading ? (
                   <>
                     <svg className="animate-spin h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                         <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                         <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                     </svg>
                     <span>Swapping...</span>
                   </>
               ) : "Swap"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
export default SwapModal;
