import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle } from "lucide-react";
import { FaArrowUp } from "react-icons/fa";
import api, { web3Api } from "@/lib/api";
import { K_TOKEN_SYMBOLS, K_TOKEN_ADDRESSES } from "@/lib/kTokens";

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

  useEffect(() => {
    if (!visible) return;
    // Reset when opened
    setReceiverUsername("");
    setSendAmount("");
    setSelectedCurrency("");
    setError(null);
    setSuccess(null);

    // Load supported currencies from static mapping
    try {
      setLoading(true);
      setLoadingMessage("Loading supported currencies...");
      const list: SupportedToken[] = Object.entries(K_TOKEN_SYMBOLS).map(([symbol, address]) => ({
        symbol,
        address,
        decimals: 18, // Most ERC20 tokens use 18 decimals
      }));
      setTokens(list);
      // Default select first if available
      if (list.length > 0) {
        const first = list[0].symbol.replace(/^k/, "");
        setSelectedCurrency(first);
      }
    } catch (e) {
      console.error(e);
      setError("Failed to load supported currencies.");
    } finally {
      setLoading(false);
      setLoadingMessage("");
    }
  }, [visible]);

  const kSymbol = useMemo(() => (selectedCurrency ? `k${selectedCurrency}` : ""), [selectedCurrency]);

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

  const fetchUserBalances = async (): Promise<Record<string, number>> => {
    // Extract k-token balances from the balance prop (similar to KTTokenBalances)
    const balances: Record<string, number> = {};

    if (!balance || !balance.tokenBalances || !Array.isArray(balance.tokenBalances)) {
      return balances;
    }

    for (const tb of balance.tokenBalances) {
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const symbol = tokenAddress ? K_TOKEN_ADDRESSES[tokenAddress] : undefined;
      if (symbol) {
        const amount = parseFloat(tb.amount || "0");
        if (!isNaN(amount) && amount > 0) {
          balances[symbol] = amount;
        }
      }
    }

    return balances;
  };

  const performSwapIfNeeded = async (targetSymbol: string, requiredTargetAmount: number): Promise<void> => {
    setLoadingMessage(`Checking balances and prices for swap...`);
    const balances = await fetchUserBalances();

    const safety = 1.02; // +2% buffer for slippage/fees

    // Find the first source token that can cover the required target amount
    for (const [sym, amt] of Object.entries(balances)) {
      if (sym === targetSymbol || amt <= 0) continue;
      try {
        const priceResp = await web3Api.get(`/pools/price/${sym}/${targetSymbol}`);
        const price = Number(priceResp?.data?.price) || 0; // target per 1 source
        if (price <= 0) continue;

        const requiredSourceAmount = (requiredTargetAmount / price) * safety;
        if (amt >= requiredSourceAmount) {
          const amountToSwap = requiredSourceAmount;
          setLoadingMessage(`Swapping ${amountToSwap.toFixed(4)} ${sym.replace(/^k/, "")} → ${targetSymbol.replace(/^k/, "")}...`);
          await web3Api.post(`/pools/swap`, {
            from_token: sym,
            to_token: targetSymbol,
            amount: amountToSwap,
            user_address: userAddress,
          });
          return;
        }
      } catch (e) {
        // Ignore this token and try next
      }
    }

    throw new Error("Insufficient funds to perform swap for the requested currency.");
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
    if (!kSymbol) {
      setError("Please select a currency.");
      return;
    }

    setLoading(true);
    setLoadingMessage("Resolving receiver address...");

    try {
      const toAddress = await resolveReceiverAddress(receiverUsername.trim());

      // Check current balance in the selected currency
      setLoadingMessage("Checking your balance...");
      const balances = await fetchUserBalances();
      const current = balances[kSymbol] || 0;

      if (current < amountNum) {
        const deficitTarget = amountNum - current;
        await performSwapIfNeeded(kSymbol, deficitTarget);
      }

      await transferTokens(kSymbol, toAddress, amountNum);

      setSuccess(`Successfully sent ${amountNum.toFixed(2)} ${kSymbol.replace(/^k/, "")} to @${receiverUsername}`);
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
        className="w-full max-w-md bg-zinc-900/95 backdrop-blur-xl border border-zinc-800 shadow-2xl relative overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <CardHeader>
          <CardTitle className="text-xl font-bold text-white flex items-center">
            <FaArrowUp className="mr-3 text-emerald-400" />
            Send Currency
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
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
                <Alert variant="destructive" className="bg-red-900/80 border-red-700 text-red-200">
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              <div className="space-y-4">
                {/* Receiver Username */}
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">Receiver Username</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 transform -translate-y-1/2 text-zinc-500">@</span>
                    <input
                      type="text"
                      value={receiverUsername}
                      onChange={(e) => setReceiverUsername(e.target.value)}
                      placeholder="username"
                      className="w-full pl-8 pr-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                      disabled={loading}
                    />
                  </div>
                </div>

                {/* Amount */}
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">Amount ({selectedCurrency || "Currency"})</label>
                  <input
                    type="number"
                    value={sendAmount}
                    onChange={(e) => setSendAmount(e.target.value)}
                    placeholder="0.00"
                    step="0.01"
                    min="0"
                    className="w-full px-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                    disabled={loading}
                  />
                </div>

                {/* Currency Dropdown */}
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">Currency</label>
                  <div className="relative">
                    <select
                      value={selectedCurrency}
                      onChange={(e) => setSelectedCurrency(e.target.value)}
                      className="w-full appearance-none px-4 py-3 border border-zinc-800 rounded-lg bg-zinc-800 text-white focus:ring-2 focus:ring-emerald-500 focus:border-transparent"
                      disabled={loading}
                    >
                      {tokens.map((t) => (
                        <option key={t.symbol} value={t.symbol.replace(/^k/, "")}>
                          {t.symbol.replace(/^k/, "")}
                        </option>
                      ))}
                    </select>
                    <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500">▾</span>
                  </div>
                </div>
              </div>

              <div className="flex space-x-3 pt-4">
                <Button
                  onClick={handleSend}
                  disabled={loading || !receiverUsername.trim() || !sendAmount.trim() || !selectedCurrency}
                  className="flex-1 bg-gradient-to-r from-emerald-500 via-cyan-500 to-emerald-600 hover:from-emerald-600 hover:to-cyan-700 text-white py-3 rounded-lg text-lg font-semibold shadow-md"
                >
                  {loading ? (loadingMessage || "Processing...") : `Send ${selectedCurrency || "Currency"}`}
                </Button>
                <Button
                  onClick={onClose}
                  variant="outline"
                  className="flex-1 py-3 rounded-lg text-lg font-semibold"
                  disabled={loading}
                >
                  Cancel
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {/* Global Loading Overlay for long operations (swap/transfer) */}
      {loading && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-2xl flex items-center justify-center z-50">
          <div className="bg-gradient-to-br from-zinc-900/90 via-zinc-800/80 to-emerald-900/60 border border-emerald-400/20 rounded-3xl p-10 w-full max-w-md mx-4 shadow-2xl ring-2 ring-emerald-400/10">
            <div className="flex flex-col items-center space-y-6">
              <div className="relative">
                <svg className="animate-spin" width="48" height="48" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="10" stroke="#10b981" strokeWidth="2" fill="none" opacity="0.2" />
                  <path d="M22 12a10 10 0 0 1-10 10" stroke="#22d3ee" strokeWidth="2" fill="none" />
                </svg>
                <div className="absolute inset-0 bg-emerald-400/20 rounded-full animate-pulse"></div>
              </div>
              <div className="text-center">
                <h3 className="text-2xl font-extrabold text-white mb-2 tracking-tight drop-shadow-lg">
                  Processing Transaction
                </h3>
                <p className="text-zinc-300 text-lg">{loadingMessage || "Working..."}</p>
                <p className="text-zinc-400 text-sm mt-2">This may take a few moments</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}


