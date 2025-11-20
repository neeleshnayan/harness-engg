import React, { useEffect, useMemo, useState } from "react";
import { web3Api } from "@/lib/api";
import { K_TOKEN_ADDRESSES_LOWERCASE, K_TOKEN_SYMBOL_LIST } from "@/lib/kTokens";
import { getPoolRate } from "@/lib/priceCache";

interface SwapModalProps {
  visible: boolean;
  onClose: () => void;
  userAddress?: string;
  balance?: any;
}

const SwapModal: React.FC<SwapModalProps> = ({ visible, onClose, userAddress, balance }) => {
  const [fromAmount, setFromAmount] = useState<string>("");
  const [fromCurrency, setFromCurrency] = useState<string>("kUSD");
  const [toCurrency, setToCurrency] = useState<string>("kEUR");
  const [toAmount, setToAmount] = useState<string>("0");
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingRate, setLoadingRate] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

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
      setToAmount("0");
      setError(null);
      setSuccess(null);
      return;
    }
  }, [visible]);

  useEffect(() => {
    let cancelled = false;
    const calculateRate = async () => {
      if (!fromAmount || isNaN(Number(fromAmount)) || Number(fromAmount) <= 0) {
        setToAmount("0");
        return;
      }
      setLoadingRate(true);
      try {
        const rate = await getPoolRate(toCurrency, fromCurrency);
        if (cancelled) return;
        if (rate > 0) {
          const calculated = Number(fromAmount) * rate;
          setToAmount(calculated.toFixed(4));
        } else {
          setToAmount("0");
        }
      } catch (err) {
        if (!cancelled) {
          console.error("Failed to fetch swap rate:", err);
          setToAmount("0");
        }
      } finally {
        if (!cancelled) {
          setLoadingRate(false);
        }
      }
    };

    calculateRate();
    return () => {
      cancelled = true;
    };
  }, [fromAmount, fromCurrency, toCurrency]);

  const amountValue = parseFloat(fromAmount);
  const fromBalance = balances[fromCurrency] || 0;
  const canSwap =
    !loadingRate &&
    !loading &&
    fromAmount !== "" &&
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
      let swapResponse = await web3Api.post("/pools/swap", {
        from_token: fromCurrency,
        to_token: toCurrency,
        amount: amountValue,
        user_address: userAddress,
      });

      setSuccess(`Swapped ${amountValue.toFixed(2)} ${fromCurrency.replace(/^k/, "")} to ${swapResponse.data.estimated_output.toFixed(2)} ${toCurrency.replace(/^k/, "")}`);
      setFromAmount("");
      setToAmount("0");
    } catch (err: any) {
      console.error("Swap failed:", err);
      setError(err?.response?.data?.message || err?.message || "Swap failed. Try again.");
    } finally {
      setLoading(false);
    }
  };

  if (!visible) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={success ? onClose : undefined}
      style={{ cursor: success ? 'pointer' : 'default' }}
    >
      <div className="bg-zinc-900/95 border border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-white">Swap Assets</h3>
          <button className="text-zinc-400 hover:text-white" onClick={onClose} disabled={loading}>
            ✕
          </button>
        </div>

        {/* Success Animation */}
        {success && (
          <div className="flex flex-col items-center justify-center py-8">
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
            <div className="text-green-400 text-lg font-semibold mb-2">Swap Successful!</div>
            <div className="text-zinc-300 text-sm text-center">{success}</div>
            <div className="mt-6 text-zinc-500 text-xs">Tap anywhere to close</div>
          </div>
        )}

        {/* Form (hide if success) */}
        {!success && (
          <>
            {error && <div className="mb-3 rounded-xl border border-red-500/40 bg-red-500/10 text-red-200 px-4 py-2 text-sm">{error}</div>}

            <div className="space-y-4">
          <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-zinc-400">From</span>
              <span className="text-xs text-zinc-500">Balance: {fromBalance.toFixed(4)}</span>
            </div>
            <div className="relative mt-3">
              <div className="bg-zinc-900/40 rounded-xl px-4 py-3">
                <input
                  type="text"
                  inputMode="decimal"
                  pattern="[0-9]*"
                  min="0"
                  value={fromAmount}
                  onChange={(e) => setFromAmount(e.target.value.replace(/[^0-9.]/g, ""))}
                  placeholder="0.00"
                  className="w-full bg-transparent text-3xl text-white font-bold focus:outline-none"
                />
              </div>
              <select
                value={fromCurrency}
                onChange={(e) => {
                  const newValue = e.target.value;
                  setFromCurrency(newValue);
                  if (newValue === toCurrency) {
                    const alternative = supportedTokens.find((token) => token !== newValue);
                    if (alternative) {
                      setToCurrency(alternative);
                    }
                  }
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-zinc-900/80 border border-zinc-700 rounded-xl px-4 py-2 text-white focus:outline-none"
              >
                {supportedTokens.map((token) => (
                  <option key={token} value={token} className="bg-zinc-900">
                    {token.replace(/^k/, "")}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="bg-zinc-800/40 border border-zinc-700/40 rounded-2xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-zinc-400">To (estimated)</span>
              <span className="text-xs text-zinc-500">
                {loadingRate ? "Fetching rate..." : `Rate updates as you type`}
              </span>
            </div>
            <div className="relative mt-3">
              <div className="bg-zinc-900/40 rounded-xl px-4 py-3 text-3xl font-bold text-white">
                {loadingRate ? <span className="text-zinc-500 animate-pulse">...</span> : Number(toAmount).toFixed(4)}
              </div>
              <select
                value={toCurrency}
                onChange={(e) => {
                  const newValue = e.target.value;
                  setToCurrency(newValue);
                  if (newValue === fromCurrency) {
                    const alternative = supportedTokens.find((token) => token !== newValue);
                    if (alternative) {
                      setFromCurrency(alternative);
                    }
                  }
                }}
                className="absolute right-3 top-1/2 -translate-y-1/2 bg-zinc-900/80 border border-zinc-700 rounded-xl px-4 py-2 text-white focus:outline-none"
              >
                {supportedTokens.map((token) => (
                  <option key={token} value={token} className="bg-zinc-900">
                    {token.replace(/^k/, "")}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>

            <button
              onClick={handleSwap}
              disabled={!canSwap}
              className="mt-6 w-full bg-gradient-to-r from-emerald-500 to-cyan-500 hover:from-emerald-600 hover:to-cyan-600 text-white font-semibold py-3 rounded-2xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
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

