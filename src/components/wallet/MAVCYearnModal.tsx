import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowUp, ArrowDown, Info } from "lucide-react";

interface MAVCYearnModalProps {
  visible: boolean;
  onClose: () => void;
  action: 'deposit' | 'withdraw';
  vaultBalance: string;
  usdcBalance: string;
  onDeposit: (amount: string) => void;
  onWithdraw: (amount: string) => void;
  loading: boolean;
  error: string | null;
  success: string | null;
  pricePerShare?: number;
  walletAddress?: string;
  vaultAddress?: string;
}

const MAVCYearnModal: React.FC<MAVCYearnModalProps> = ({
  visible,
  onClose,
  action,
  vaultBalance,
  usdcBalance,
  onDeposit,
  onWithdraw,
  loading,
  error,
  success,
  pricePerShare = 1.0,
  walletAddress,
  vaultAddress,
}) => {
  const [amount, setAmount] = useState("");
  const [estimatedShares, setEstimatedShares] = useState<number>(0);
  const [estimatedAssets, setEstimatedAssets] = useState<number>(0);

  // Reset state when modal closes
  useEffect(() => {
    if (!visible) {
      setAmount("");
      setEstimatedShares(0);
      setEstimatedAssets(0);
    }
  }, [visible]);

  // Calculate estimates when amount changes
  useEffect(() => {
    const amountFloat = parseFloat(amount || "0");

    if (action === 'deposit') {
      // Depositing USDC -> get vault shares
      // shares = assets / pricePerShare
      const shares = amountFloat / pricePerShare;
      setEstimatedShares(shares);
    } else {
      // Withdrawing vault shares -> get USDC
      // assets = shares * pricePerShare
      const assets = amountFloat * pricePerShare;
      setEstimatedAssets(assets);
    }
  }, [amount, action, pricePerShare]);

  const handleSubmit = () => {
    if (!amount || parseFloat(amount) <= 0) {
      return;
    }

    if (action === 'deposit') {
      onDeposit(amount);
    } else {
      onWithdraw(amount);
    }
  };

  const handleMaxClick = () => {
    if (action === 'deposit') {
      setAmount(usdcBalance);
    } else {
      setAmount(vaultBalance);
    }
  };

  const getAvailableBalance = () => {
    return action === 'deposit' ? usdcBalance : vaultBalance;
  };

  const getBalanceLabel = () => {
    return action === 'deposit' ? 'USDC' : 'ysMAVC';
  };

  const isInsufficientBalance = () => {
    const amountFloat = parseFloat(amount || "0");
    const balance = parseFloat(getAvailableBalance());
    return amountFloat > balance;
  };

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-md p-4">
        <Card className="bg-zinc-900 border-zinc-700">
          <CardHeader className="border-b border-zinc-700">
            <CardTitle className="flex items-center gap-2 text-white">
              {action === 'deposit' ? (
                <>
                  <ArrowDown className="w-5 h-5 text-green-400" />
                  Deposit to MAVC Yearn
                </>
              ) : (
                <>
                  <ArrowUp className="w-5 h-5 text-red-400" />
                  Withdraw from MAVC Yearn
                </>
              )}
            </CardTitle>
          </CardHeader>

          <CardContent className="pt-6 space-y-4">
            {/* Info Alert */}
            <Alert className="bg-blue-500/10 border-blue-500/30">
              <Info className="h-4 w-4 text-blue-400" />
              <AlertDescription className="text-blue-300 text-sm">
                {action === 'deposit'
                  ? 'Deposits use ERC-4626 deposit() function. You will receive ysMAVC (Yearn Strategy MAVC) shares representing your USDC.'
                  : 'Withdrawals use ERC-4626 redeem() function. Your ysMAVC shares will be burned and you will receive USDC.'}
              </AlertDescription>
            </Alert>

            {/* Balance Display */}
            <div className="flex justify-between items-center text-sm">
              <span className="text-zinc-400">Available {getBalanceLabel()}:</span>
              <span className="font-semibold text-white">
                {parseFloat(getAvailableBalance()).toFixed(6)}
              </span>
            </div>

            {/* Price Per Share */}
            <div className="flex justify-between items-center text-sm">
              <span className="text-zinc-400">Price per share:</span>
              <span className="font-semibold text-white">
                {pricePerShare.toFixed(6)} USDC
              </span>
            </div>

            {/* Amount Input */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">
                {action === 'deposit' ? 'Amount (USDC)' : 'Amount (ysMAVC)'}
              </label>
              <div className="relative">
                <input
                  type="number"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-4 py-3 bg-zinc-800 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  disabled={loading}
                />
                <button
                  onClick={handleMaxClick}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-semibold text-blue-400 hover:text-blue-300"
                  disabled={loading}
                >
                  MAX
                </button>
              </div>
            </div>

            {/* Estimate Display */}
            {amount && parseFloat(amount) > 0 && (
              <div className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-400">
                    {action === 'deposit' ? 'Estimated ysMAVC:' : 'Estimated USDC:'}
                  </span>
                  <span className="font-semibold text-green-400">
                    {action === 'deposit'
                      ? `${estimatedShares.toFixed(6)} ysMAVC`
                      : `${estimatedAssets.toFixed(6)} USDC`}
                  </span>
                </div>
              </div>
            )}

            {/* Error Display */}
            {error && (
              <Alert className="bg-red-500/10 border-red-500/30">
                <AlertCircle className="h-4 w-4 text-red-400" />
                <AlertDescription className="text-red-300 text-sm">
                  {error}
                </AlertDescription>
              </Alert>
            )}

            {/* Success Display */}
            {success && (
              <Alert className="bg-green-500/10 border-green-500/30">
                <AlertCircle className="h-4 w-4 text-green-400" />
                <AlertDescription className="text-green-300 text-sm">
                  {success}
                </AlertDescription>
              </Alert>
            )}

            {/* Insufficient Balance Warning */}
            {isInsufficientBalance() && (
              <Alert className="bg-yellow-500/10 border-yellow-500/30">
                <AlertCircle className="h-4 w-4 text-yellow-400" />
                <AlertDescription className="text-yellow-300 text-sm">
                  Insufficient {getBalanceLabel()} balance
                </AlertDescription>
              </Alert>
            )}

            {/* Action Buttons */}
            <div className="flex gap-3 pt-4">
              <Button
                variant="outline"
                onClick={onClose}
                disabled={loading}
                className="flex-1 border-zinc-700 text-zinc-300 hover:bg-zinc-800"
              >
                Cancel
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={loading || !amount || parseFloat(amount) <= 0 || isInsufficientBalance()}
                className={`flex-1 font-semibold ${
                  action === 'deposit'
                    ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700'
                    : 'bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700'
                }`}
              >
                {loading ? (
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Processing...
                  </div>
                ) : (
                  action === 'deposit' ? 'Deposit' : 'Withdraw'
                )}
              </Button>
            </div>

            {/* Contract Info */}
            {vaultAddress && (
              <div className="pt-4 border-t border-zinc-700">
                <p className="text-xs text-zinc-500">
                  Vault: <span className="text-zinc-400 font-mono">{vaultAddress.slice(0, 6)}...{vaultAddress.slice(-4)}</span>
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default MAVCYearnModal;
