import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { FaArrowUp } from "react-icons/fa";
import api, { web3Api } from "@/lib/api";
import { K_TOKEN_SYMBOLS, K_TOKEN_ADDRESSES_LOWERCASE } from "@/lib/kTokens";
import { getPoolPrice } from "@/lib/priceCache";

interface SendERC20ModalProps {
  visible: boolean;
  onClose: () => void;
  userAddress: string;
  balance?: any;
}

type SupportedToken = {
  symbol: string; // e.g., kUSD
  address: string;
  decimals?: number;
};

export default function SendERC20Modal({ visible, onClose, userAddress, balance }: SendERC20ModalProps) {
  const [receiverUsername, setReceiverUsername] = useState<string>("");
  const [selectedCurrency, setSelectedCurrency] = useState<string>("");
  const [sendAmount, setSendAmount] = useState<string>("");
  const [tokens, setTokens] = useState<SupportedToken[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [loadingMessage, setLoadingMessage] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [currentBalanceValue, setCurrentBalanceValue] = useState<number>(0);
  const [equivalentBalance, setEquivalentBalance] = useState<number | null>(null);
  const [equivalentBalanceLoading, setEquivalentBalanceLoading] = useState<boolean>(false);
  const [equivalentDebitAmount, setEquivalentDebitAmount] = useState<number | null>(null);
  const [equivalentDebitAmountLoading, setEquivalentDebitAmountLoading] = useState<boolean>(false);
  const [toCurrency, setToCurrency] = useState<string>("");
  const [availableTokens, setAvailableTokens] = useState<SupportedToken[]>([]);

  useEffect(() => {
    if (!visible) return;
    // Reset when opened
    setReceiverUsername("");
    setSendAmount("");
    setSelectedCurrency("");
    setToCurrency("");
    setCurrentBalanceValue(0);
    setEquivalentBalance(null);
    setEquivalentBalanceLoading(false);
    setEquivalentDebitAmount(null);
    setEquivalentDebitAmountLoading(false);
    setError(null);
    setSuccess(null);

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
          if (token.symbol === "USDC") {
            return false;
          }
          const tokenBalance = balances[token.symbol] || 0;
          return tokenBalance > 0;
        });

        setTokens(allTokens); // All tokens for "to" dropdown
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
  }, [visible, balance]);

  const isToUSDC = toCurrency === "USDC";

  const fromTokenSymbol = useMemo(() => {
    if (isToUSDC) {
      return "USDC";
    }
    if (!selectedCurrency) {
      return "";
    }
    return selectedCurrency === "USDC" ? "USDC" : `k${selectedCurrency}`;
  }, [selectedCurrency, isToUSDC]);

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
      const kSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;
      const tokenSymbol = tb?.token?.symbol;

      const rawAmount = parseFloat(tb?.amount ?? "0");
      if (isNaN(rawAmount) || rawAmount <= 0) {
        continue;
      }

      if (kSymbol) {
        balances[kSymbol] = (balances[kSymbol] || 0) + rawAmount;
        continue;
      }

      if (tokenSymbol === "USDC" || tokenSymbol === "TRNSK") {
        balances["USDC"] = (balances["USDC"] || 0) + rawAmount;
      }
    }

    return balances;
  };

  // Update balance when currency changes
  useEffect(() => {
    if (!visible) return;
    const updateBalance = async () => {
      if (!fromTokenSymbol) {
        setCurrentBalanceValue(0);
        setEquivalentBalance(null);
        setEquivalentBalanceLoading(false);
        setEquivalentDebitAmount(null);
        setEquivalentDebitAmountLoading(false);
        return;
      }
      const balances = await fetchUserBalances();
      setCurrentBalanceValue(balances[fromTokenSymbol] || 0);
    };
    updateBalance();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromTokenSymbol, balance, visible]);

  // Calculate equivalent debit amount (how much FROM currency will be debited)
  useEffect(() => {
    // Reset if currencies are same, invalid, or no amount entered
    if (
      !visible ||
      !fromTokenSymbol ||
      !toTokenSymbol ||
      fromTokenSymbol === toTokenSymbol ||
      !sendAmount ||
      !fromTokenSymbol.startsWith("k") ||
      !toTokenSymbol.startsWith("k")
    ) {
      setEquivalentDebitAmount(null);
      setEquivalentDebitAmountLoading(false);
      return;
    }

    const amountNum = parseFloat(sendAmount);
    if (isNaN(amountNum) || amountNum <= 0) {
      setEquivalentDebitAmount(null);
      setEquivalentDebitAmountLoading(false);
      return;
    }

    const calculateDebitAmount = async () => {
      setEquivalentDebitAmountLoading(true);
      try {
        // Get price: how much toCurrency per 1 fromCurrency
        const price = await getPoolPrice(fromTokenSymbol, toTokenSymbol);

        if (price > 0) {
          // Calculate how much FROM currency is needed to get the TO currency amount
          // amountNum is in TO currency, price is TO per FROM, so FROM needed = amountNum / price
          const debitAmount = amountNum / price;
          setEquivalentDebitAmount(debitAmount);
        } else {
          setEquivalentDebitAmount(null);
        }
      } catch (e) {
        console.error('Failed to fetch exchange rate for debit amount:', e);
        setEquivalentDebitAmount(null);
      } finally {
        setEquivalentDebitAmountLoading(false);
      }
    };

    calculateDebitAmount();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sendAmount, fromTokenSymbol, toTokenSymbol, visible]);

  // Calculate equivalent balance in toCurrency
  useEffect(() => {
    // Reset equivalent balance if currencies are same or invalid
    if (
      !visible ||
      !fromTokenSymbol ||
      !toTokenSymbol ||
      fromTokenSymbol === toTokenSymbol ||
      currentBalanceValue === 0 ||
      !fromTokenSymbol.startsWith("k") ||
      !toTokenSymbol.startsWith("k")
    ) {
      setEquivalentBalance(null);
      setEquivalentBalanceLoading(false);
      return;
    }

    const calculateEquivalent = async () => {
      setEquivalentBalanceLoading(true);
      try {
        const price = await getPoolPrice(fromTokenSymbol, toTokenSymbol); // toCurrency per 1 fromCurrency
        if (price > 0) {
          const equivalent = currentBalanceValue * price;
          setEquivalentBalance(equivalent);
        } else {
          setEquivalentBalance(null);
        }
      } catch (e) {
        console.error('Failed to fetch exchange rate:', e);
        setEquivalentBalance(null);
      } finally {
        setEquivalentBalanceLoading(false);
      }
    };

    calculateEquivalent();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fromTokenSymbol, toTokenSymbol, currentBalanceValue, visible]);

  // Set toCurrency to match fromCurrency initially
  useEffect(() => {
    if (selectedCurrency && !toCurrency) {
      setToCurrency(selectedCurrency);
    }
  }, [selectedCurrency, toCurrency]);

  const resolveReceiverAddress = async (username: string): Promise<string> => {
    // Reuse existing user API to resolve username to address
    try {
      const resp = await api.get(`/api/v1/resolve_username/${username}`);
      const addr = resp?.data?.wallet_address || resp?.data?.walletAddress;
      if (!addr || typeof addr !== "string") throw new Error("Wallet address not found for username");
      return addr;
    } catch (e) {
      throw new Error("Failed to resolve receiver address. Please check the username.");
    }
  };

  const performSwap = async (fromSymbol: string, toSymbol: string, requiredToAmount: number): Promise<void> => {
    setLoadingMessage(`Checking swap price from ${fromSymbol.replace(/^k/, "")} to ${toSymbol.replace(/^k/, "")}...`);
    const balances = await fetchUserBalances();

    // Get price: how much toCurrency per 1 fromCurrency
    const price = await getPoolPrice(fromSymbol, toSymbol); // toCurrency per 1 fromCurrency

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
    await web3Api.post(`/pools/swap`, {
      from_token: fromSymbol,
      to_token: toSymbol,
      amount: requiredFromAmount,
      user_address: userAddress,
    });
  };

  const transferTokens = async (targetSymbol: string, toAddress: string, amount: number): Promise<void> => {
    setLoadingMessage(`Transferring ${amount.toFixed(2)} ${targetSymbol.replace(/^k/, "")}...`);
    await web3Api.post(`/erc20/transfer`, {
      token_symbol: targetSymbol,
      from_address: userAddress,
      to_address: toAddress,
      amount,
    });
  };

  const handleSend = async () => {
    setError(null);
    setSuccess(null);

    if (!receiverUsername.trim()) {
      setError("Please enter receiver username.");
      return;
    }
    const amountNum = parseFloat(sendAmount);
    if (!sendAmount.trim() || isNaN(amountNum) || amountNum <= 0) {
      setError("Please enter a valid amount.");
      return;
    }
    if (!toTokenSymbol || !toCurrency) {
      setError("Please select a to currency.");
      return;
    }
    if (!isToUSDC && !fromTokenSymbol) {
      setError("Please select a from currency.");
      return;
    }

    setLoading(true);
    setLoadingMessage("Resolving receiver address...");

    try {
      const toAddress = await resolveReceiverAddress(receiverUsername.trim());

      // Get current balances
      setLoadingMessage("Checking your balance...");
      const balances = await fetchUserBalances();

      // Determine which currency to send (the "to" currency)
      const sendCurrency = toTokenSymbol;
      const sendCurrencyDisplay = sendCurrency === "USDC" ? "USDC" : sendCurrency.replace(/^k/, "");

      if (sendCurrency === "USDC") {
        const usdcBalance = balances["USDC"] || 0;
        if (usdcBalance < amountNum) {
          throw new Error(`Insufficient USDC balance. You have ${usdcBalance.toFixed(2)} USDC, but need ${amountNum.toFixed(2)}.`);
        }
        await transferTokens("USDC", toAddress, amountNum);
      } else {
        const fromCurrency = fromTokenSymbol;
        if (!fromCurrency) {
          throw new Error("Please select a from currency.");
        }

        if (fromCurrency !== sendCurrency) {
          await performSwap(fromCurrency, sendCurrency, amountNum);
        } else {
          const fromBalance = balances[fromCurrency] || 0;
          if (fromBalance < amountNum) {
            const fromDisplay = fromCurrency.replace(/^k/, "");
            throw new Error(`Insufficient balance. You have ${fromBalance.toFixed(4)} ${fromDisplay}, but need ${amountNum.toFixed(4)}.`);
          }
        }

        await transferTokens(sendCurrency, toAddress, amountNum);
      }

      setSuccess(`Successfully sent ${amountNum.toFixed(2)} ${sendCurrencyDisplay} to @${receiverUsername}`);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "Transaction failed. Please try again.");
    } finally {
      setLoading(false);
      setLoadingMessage("");
    }
  };

  if (!visible) return null;

  return (
    <div
      className="fixed inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      onClick={success ? onClose : undefined}
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
              onClick={onClose}
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
              <div className="text-green-400 text-lg font-semibold mb-2">Transaction Successful!</div>
              <div className="text-zinc-300 text-sm text-center">{success}</div>
              <div className="mt-6 text-zinc-500 text-xs">Tap anywhere to close</div>
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

              {/* Receiver Username */}
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

              {/* From Currency Card (Uniswap style) */}
              {!isToUSDC && (
                <div className="bg-zinc-800/50 rounded-2xl p-5 border border-zinc-700/50">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-zinc-400">From</span>
                  </div>

                  {/* From Currency Selector */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-3xl font-bold text-white">
                      {equivalentDebitAmountLoading ? (
                        <span className="text-zinc-500">...</span>
                      ) : equivalentDebitAmount !== null && fromTokenSymbol !== toTokenSymbol ? (
                        equivalentDebitAmount.toFixed(4)
                      ) : (
                        "-"
                      )}
                    </div>
                    <div className="relative">
                      <select
                        value={selectedCurrency}
                        onChange={(e) => {
                          setSelectedCurrency(e.target.value);
                          setSendAmount(""); // Reset amount when currency changes
                        }}
                        className="appearance-none bg-zinc-700/50 hover:bg-zinc-700 border border-zinc-600 rounded-xl px-4 py-2.5 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-10"
                        disabled={loading}
                      >
                        {availableTokens.length === 0 ? (
                          <option value="">No available balances</option>
                        ) : (
                          availableTokens.map((t) => (
                            <option key={t.symbol} value={t.symbol.replace(/^k/, "")}>
                              {t.symbol.replace(/^k/, "")}
                            </option>
                          ))
                        )}
                      </select>
                      <svg
                        className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400"
                        width="12"
                        height="12"
                        viewBox="0 0 12 12"
                        fill="none"
                      >
                        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                  </div>

                  {/* Balance Display */}
                  <div className="text-sm text-zinc-400">
                    <span>Balance: </span>
                    <span className="text-zinc-300 font-medium">{currentBalanceValue.toFixed(4)}</span>
                    {fromTokenSymbol !== toTokenSymbol && (
                      <>
                        {equivalentBalanceLoading ? (
                          <span className="text-zinc-500 ml-1">(...)</span>
                        ) : equivalentBalance !== null ? (
                          <span className="text-zinc-500 ml-1">
                            ({equivalentBalance.toFixed(4)} {toCurrency})
                          </span>
                        ) : null}
                      </>
                    )}
                  </div>
                </div>
              )}

              {/* Amount Input and To Currency Row */}
              <div className="bg-zinc-800/50 rounded-2xl p-5 border border-zinc-700/50">
                <div className="flex items-center justify-between gap-3">
                  {/* Amount Input */}
                  <div className="flex-1">
                    <input
                      type="number"
                      value={sendAmount}
                      onChange={(e) => setSendAmount(e.target.value)}
                      placeholder="0.00"
                      step="0.01"
                      min="0"
                      className="w-full text-2xl font-bold bg-transparent text-white placeholder-zinc-500 focus:outline-none"
                      disabled={loading}
                    />
                  </div>

                  {/* To Currency Dropdown */}
                  <div className="relative">
                    <select
                      value={toCurrency}
                      onChange={(e) => setToCurrency(e.target.value)}
                      className="appearance-none bg-zinc-700/50 hover:bg-zinc-700 border border-zinc-600 rounded-xl px-4 py-2.5 text-white font-medium cursor-pointer focus:outline-none focus:ring-2 focus:ring-emerald-500 pr-10"
                      disabled={loading}
                    >
                      {tokens.map((t) => (
                        <option key={t.symbol} value={t.symbol.replace(/^k/, "")}>
                          {t.symbol.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <svg
                      className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-400"
                      width="12"
                      height="12"
                      viewBox="0 0 12 12"
                      fill="none"
                    >
                      <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
                {isToUSDC && (
                  <div className="text-sm text-zinc-400 text-right mt-2">
                    <span>Balance: </span>
                    <span className="text-zinc-300 font-medium">{currentBalanceValue.toFixed(2)} USDC</span>
                  </div>
                )}
              </div>

              {/* Action Button */}
              <div className="pt-2">
                <Button
                  onClick={handleSend}
                  disabled={loading || !receiverUsername.trim() || !sendAmount.trim() || (!isToUSDC && !selectedCurrency)}
                  className="w-full bg-gradient-to-r from-pink-500 to-pink-600 hover:from-pink-600 hover:to-pink-700 text-white py-4 rounded-2xl text-lg font-semibold shadow-lg disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2"
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


