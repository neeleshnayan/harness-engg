import React, { useEffect, useMemo, useState, useRef, useCallback } from "react";
import { kryptonWeb3Api } from "@/lib/api";
import { useRates } from "@/providers/RatesProvider";
import { getPoolRate } from "@/lib/ratesApi";
import { ArrowRight, ChevronDown } from "lucide-react";
import WalletProgressState from "@/components/wallet/WalletProgressState";
import WalletModalShell from "@/components/wallet/WalletModalShell";

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
  const [success, setSuccess] = useState<{ heading: string; detail: string } | null>(null);
  const [closeCountdown, setCloseCountdown] = useState<number>(0);
  const isUpdatingFromRef = useRef<boolean>(false);
  const isUpdatingToRef = useRef<boolean>(false);
  const focusedFieldRef = useRef<"from" | "to" | null>(null);
  const lastEditedFieldRef = useRef<"from" | "to">("from");
  const countdownIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Get token data from context
  const { tokens, getTokenAddressToSymbol } = useRates();
  const tokenAddressMap = useMemo(() => getTokenAddressToSymbol(), [getTokenAddressToSymbol]);
  const allTokenSymbols = useMemo(() => Object.keys(tokens), [tokens]);

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
          // Defer to next tick to avoid "Cannot update parent while rendering child"
          setTimeout(() => onClose(true), 0);
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
      const resolvedSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : undefined;

      if (resolvedSymbol) {
        result[resolvedSymbol] = (result[resolvedSymbol] || 0) + rawAmount;
      } else if (tokenSymbol === "USDC") {
        result["USDC"] = (result["USDC"] || 0) + rawAmount;
      } else if (tokenSymbol) {
        result[tokenSymbol] = (result[tokenSymbol] || 0) + rawAmount;
      }
    }

    return result;
  }, [balance, tokenAddressMap]);

  const supportedTokens = useMemo(() => {
    const kTokens: string[] = [];
    const rwaTokens: string[] = [];
    for (const symbol of allTokenSymbols) {
      if (symbol.startsWith('k')) {
        kTokens.push(symbol);
      } else {
        rwaTokens.push(symbol);
      }
    }
    if (!kTokens.includes('kUSD')) kTokens.unshift('kUSD');
    const result = [...kTokens, 'USDC'];
    if (rwaTokens.length > 0) {
      result.push('--- RWA Tokens ---');
      result.push(...rwaTokens);
    }
    return result;
  }, [allTokenSymbols]);

  // From dropdown: only tokens the user has balance for (like SendERC20Modal)
  const fromTokens = useMemo(() => {
    const kTokensWithBalance: string[] = [];
    const rwaTokensWithBalance: string[] = [];

    for (const symbol of supportedTokens) {
      if (symbol === '--- RWA Tokens ---') continue; // Skip separator
      const balance = balances[symbol] || 0;
      if (balance > 0) {
        if (symbol.startsWith('k') || symbol === 'USDC') {
          kTokensWithBalance.push(symbol);
        } else {
          rwaTokensWithBalance.push(symbol);
        }
      }
    }

    const result = [...kTokensWithBalance];
    if (rwaTokensWithBalance.length > 0) {
      result.push('--- RWA Tokens ---');
      result.push(...rwaTokensWithBalance);
    }
    return result;
  }, [supportedTokens, balances]);

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
      lastEditedFieldRef.current = "from";
      // Clear countdown
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current);
        countdownIntervalRef.current = null;
      }
      return;
    }
  }, [visible]);

  // When modal opens or balances change, ensure from/to are valid (from must have balance)
  useEffect(() => {
    if (!visible || fromTokens.length === 0) return;
    const validFromTokens = fromTokens.filter(t => t !== '--- RWA Tokens ---');
    const validSupportedTokens = supportedTokens.filter(t => t !== '--- RWA Tokens ---');
    const fromValid = validFromTokens.includes(fromCurrency);
    if (!fromValid) {
      const firstValid = validFromTokens[0];
      if (firstValid) {
        setFromCurrency(firstValid);
        const other = validSupportedTokens.find((t) => t !== firstValid);
        if (other) setToCurrency(other);
      }
    } else if (toCurrency === fromCurrency) {
      const alt = validSupportedTokens.find((t) => t !== fromCurrency);
      if (alt) setToCurrency(alt);
    }
  }, [visible, fromTokens, supportedTokens, fromCurrency, toCurrency]);

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
      const toAmountValue = parseFloat(toAmount);
      const useExactOutput =
        lastEditedFieldRef.current === "to" &&
        !isNaN(toAmountValue) &&
        toAmountValue > 0;
      const requestAmount = useExactOutput ? toAmountValue : amountValue;

      const swapResponse = await kryptonWeb3Api.post("/pools/universal/swap", {
        from_token: fromCurrency,
        to_token: toCurrency,
        amount: requestAmount,
        quote_mode: useExactOutput ? "exact_output" : "exact_input",
        wallet_address: userAddress,
        wallet_username: username,
      });

      const estimatedOutput = swapResponse.data?.estimated_output || toAmount;
      const fromDisplay = fromCurrency.replace(/^k/, "");
      const toDisplay = toCurrency.replace(/^k/, "");
      const estimatedOutputNum = parseFloat(estimatedOutput);
      const displayOutput = !isNaN(estimatedOutputNum) ? estimatedOutputNum : toAmountValue;
      const displayInput = parseFloat(fromAmount);

      setSuccess({
        heading: "Swapping...",
        detail: `Swapping ${displayInput.toFixed(2)} ${fromDisplay} -> ${displayOutput.toFixed(2)} ${toDisplay}`,
      });
      setFromAmount("");
      setToAmount("");
      lastEditedFieldRef.current = "from";
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
    <WalletModalShell
      open={visible}
      onDismiss={handleBackdropClick}
      screenReaderTitle="Swap Assets"
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
          <h2 className="text-2xl font-bold text-white tracking-tight">Swap Assets</h2>
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
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6 6 18" /><path d="m6 6 12 12" /></svg>
          </button>
        </div>

        {/* Success Animation */}
        {success && (
          <WalletProgressState
            heading={success.heading}
            detail={success.detail}
            animationPath="/animations/swap/swap-animation.json"
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
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-red-400 flex-shrink-0"><circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" /></svg>
                <span className="text-red-200">{error}</span>
              </div>
            )}

            {/* Swap Area */}
            <div className="flex justify-between relative mb-10">
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
                    lastEditedFieldRef.current = "from";
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
                  Balance: <span style={{ color: 'rgba(255,255,255,0.75)' }}>{fromBalance.toFixed(2)}</span>
                </div>

                {/* Selector */}
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-20">
                  <div className="relative">
                    <select
                      value={fromCurrency}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val !== '--- RWA Tokens ---') {
                          setFromCurrency(val);
                          if (val === toCurrency) {
                            const alt = supportedTokens.find(t => t !== val && t !== '--- RWA Tokens ---');
                            if (alt) setToCurrency(alt);
                          }
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
                      {fromTokens.map((token) => (
                        <option
                          key={token}
                          value={token}
                          disabled={token === '--- RWA Tokens ---'}
                          style={token === '--- RWA Tokens ---' ? { opacity: 0.6, fontStyle: 'italic' } : {}}
                        >
                          {token.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5" style={{ color: 'rgba(144,231,238,0.8)' }}>
                      <ChevronDown size={11} />
                    </div>
                  </div>
                </div>
              </div>

              {/* Swap Button */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10">
                <button
                  onClick={handleSwapCurrencies}
                  disabled={loading}
                  className="w-10 h-10 md:w-11 md:h-11 rounded-full flex items-center justify-center transition-all cursor-pointer hover:scale-110 active:scale-95"
                  style={{
                    background: 'linear-gradient(135deg, rgba(20,184,166,0.75) 0%, rgba(13,148,136,0.9) 100%)',
                    border: '1px solid rgba(45,212,191,0.45)',
                    boxShadow: '0 0 20px rgba(20,184,166,0.3), 0 4px 16px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.2)',
                  }}
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
                    lastEditedFieldRef.current = "to";
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
                  {exchangeRate ? (
                    <>
                      <span>1 {fromCurrency.replace(/^k/, '')} =&nbsp;</span>
                      <span style={{ color: 'rgba(255,255,255,0.75)' }}>{exchangeRate.toFixed(2)} {toCurrency.replace(/^k/, '')}</span>
                    </>
                  ) : ((isCalculatingFrom || isCalculatingTo || exchangeRateLoading) ? 'Updating...' : '')}
                </div>

                {/* Selector */}
                <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 z-20">
                  <div className="relative">
                    <select
                      value={toCurrency}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val !== '--- RWA Tokens ---') {
                          setToCurrency(val);
                          if (val === fromCurrency) {
                            const alt = supportedTokens.find(t => t !== val && t !== '--- RWA Tokens ---');
                            if (alt) setFromCurrency(alt);
                          }
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
                      {supportedTokens.map((token) => (
                        <option
                          key={token}
                          value={token}
                          disabled={token === '--- RWA Tokens ---'}
                          style={token === '--- RWA Tokens ---' ? { opacity: 0.6, fontStyle: 'italic' } : {}}
                        >
                          {token.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2.5" style={{ color: 'rgba(144,231,238,0.8)' }}>
                      <ChevronDown size={11} />
                    </div>
                  </div>
                </div>

                {(isCalculatingFrom || isCalculatingTo) && (
                  <div className="absolute top-3 right-3">
                    <svg className="animate-spin h-3 w-3" style={{ color: 'rgba(45,212,191,0.6)' }} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
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
              className="w-full h-12 text-white text-sm font-bold rounded-xl transition-all duration-200 disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 mt-8 relative z-10 hover:opacity-90 active:scale-[0.98]"
              style={{
                background: 'linear-gradient(135deg, rgba(20,184,166,0.82) 0%, rgba(13,148,136,0.92) 50%, rgba(8,110,102,0.88) 100%)',
                border: '1px solid rgba(45,212,191,0.3)',
                boxShadow: '0 0 24px rgba(20,184,166,0.2), 0 4px 20px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.15)',
              }}
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                  <span>Swapping...</span>
                </>
              ) : "Swap"}
            </button>
          </div>
        )}
    </WalletModalShell>
  );
};
export default SwapModal;
