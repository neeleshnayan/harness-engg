import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowUp, ArrowDown, Info } from "lucide-react";
import TransactionStatusIndicator from "./TransactionStatusIndicator";
import {
  estimateTransactionLikelihood,
  TransactionLikelihoodResult,
  TransactionStatusUpdate,
} from "../../services/transactionLikelihood";
import { StrategyName } from "@/hooks/useStrategyConfig";

interface StrategyModalProps {
  visible: boolean;
  onClose: () => void;
  action: 'deposit' | 'withdraw';
  strategyName: StrategyName;
  strategyBalance: string;
  usdcBalance: string;
  onDeposit: (amount: string) => void;
  onWithdraw: (amount: string) => void;
  loading: boolean;
  error: string | null;
  success: string | null;
  price?: string; // For MAVC/MAVP price in USDC
  pricePerShare?: number; // For MAVC_YEARN vault price per share
  walletAddress?: string;
  tokenAddress?: string;
  vaultAddress?: string;
}

const getTokenSymbol = (strategyName: StrategyName): string => {
  switch (strategyName) {
    case 'MAVC':
      return 'MAVC';
    case 'MAVP':
      return 'MAVP';
    case 'MAVC_YEARN':
      return 'ysMAVC';
    default:
      return 'TOKEN';
  }
};

// Format balance based on strategy (preserves decimal conversion)
const formatStrategyBalance = (balance: string, strategyName: StrategyName): string => {
  const numBalance = parseFloat(balance);
  if (!Number.isFinite(numBalance) || numBalance === 0) return '0.00';

  switch (strategyName) {
    case 'MAVP':
      // MAVP needs more precision (shows like MAVC / 10^12, so very small numbers)
      if (numBalance < 0.00000001) return numBalance.toExponential(4);
      if (numBalance < 0.0001) return numBalance.toFixed(10);
      if (numBalance < 0.01) return numBalance.toFixed(8);
      if (numBalance < 1) return numBalance.toFixed(6);
      if (numBalance < 100) return numBalance.toFixed(4);
      return numBalance.toFixed(2);
    case 'MAVC':
    case 'MAVC_YEARN':
      // Standard formatting for MAVC and Yearn
      return numBalance.toFixed(2);
    default:
      return numBalance.toFixed(2);
  }
};

const StrategyModal: React.FC<StrategyModalProps> = ({
  visible,
  onClose,
  action,
  strategyName,
  strategyBalance,
  usdcBalance,
  onDeposit,
  onWithdraw,
  loading,
  error,
  success,
  price,
  pricePerShare = 1.0,
  walletAddress,
  tokenAddress,
  vaultAddress,
}) => {
  const tokenSymbol = getTokenSymbol(strategyName);
  const isDeposit = action === 'deposit';
  const [amount, setAmount] = useState("");
  const [likelihoodResult, setLikelihoodResult] = useState<TransactionLikelihoodResult | null>(null);
  const [transactionStatus, setTransactionStatus] = useState<TransactionStatusUpdate>({
    stage: 'validating',
    likelihood: 'very_likely',
    message: 'Ready to process',
  });

  // Reset state when modal closes
  useEffect(() => {
    if (!visible) {
      setAmount("");
      setLikelihoodResult(null);
      setTransactionStatus({
        stage: 'validating',
        likelihood: 'very_likely',
        message: 'Ready to process',
      });
    }
  }, [visible]);

  // Estimate transaction likelihood when amount changes (for MAVC/MAVP)
  useEffect(() => {
    const estimateLikelihood = async () => {
      if (!amount || parseFloat(amount) <= 0 || strategyName === 'MAVC_YEARN') {
        setLikelihoodResult(null);
        return;
      }

      const currentBalance = isDeposit ? usdcBalance : strategyBalance;

      const result = await estimateTransactionLikelihood({
        walletAddress: walletAddress || '',
        tokenAddress: tokenAddress || '',
        amount,
        currentBalance,
        transactionType: action,
      });

      setLikelihoodResult(result);
      setTransactionStatus({
        stage: result.likelihood === 'very_unlikely' ? 'error' : 'validating',
        likelihood: result.likelihood,
        message: result.message || 'Ready to process',
      });
    };

    estimateLikelihood();
  }, [amount, isDeposit, usdcBalance, strategyBalance, walletAddress, tokenAddress, action, strategyName]);

  // For Yearn: Calculate share/asset estimates
  const [estimatedShares, setEstimatedShares] = useState<number>(0);
  const [estimatedAssets, setEstimatedAssets] = useState<number>(0);

  useEffect(() => {
    if (strategyName === 'MAVC_YEARN') {
      const amountFloat = parseFloat(amount || "0");
      if (isDeposit) {
        const shares = amountFloat / pricePerShare;
        setEstimatedShares(shares);
      } else {
        const assets = amountFloat * pricePerShare;
        setEstimatedAssets(assets);
      }
    }
  }, [amount, isDeposit, pricePerShare, strategyName]);

  if (!visible) return null;

  const handleSubmit = () => {
    if (!amount || parseFloat(amount) <= 0) {
      return;
    }
    if (isDeposit) {
      onDeposit(amount);
    } else {
      onWithdraw(amount);
    }
  };

  const handleMaxClick = () => {
    if (isDeposit) {
      setAmount(usdcBalance);
    } else {
      setAmount(strategyBalance);
    }
  };

  const maxAmount = isDeposit ? parseFloat(usdcBalance) : parseFloat(strategyBalance);
  const amountFloat = parseFloat(amount || "0");
  const isInsufficientBalance = amountFloat > maxAmount;
  const isButtonDisabled = loading || amountFloat <= 0 || isInsufficientBalance;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <Card className="w-full max-w-md bg-zinc-900 border-zinc-700 shadow-2xl">
        <CardHeader className="border-b border-zinc-700">
          <div className="flex items-center justify-between">
            <CardTitle className="text-xl font-bold text-white">
              {isDeposit ? `Deposit ${tokenSymbol}` : `Withdraw ${tokenSymbol}`}
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={onClose}
              className="text-zinc-400 hover:text-white"
              disabled={loading}
            >
              <ArrowUp className="w-4 h-4 rotate-45" />
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          {/* Success Screen */}
          {success && (
            <div className="flex flex-col items-center justify-center py-8">
              <svg
                className="w-20 h-20 text-green-400 mb-4"
                viewBox="0 0 100 100"
                xmlns="http://www.w3.org/2000/svg"
              >
                <circle cx="50" cy="50" r="45" fill="none" stroke="#22c55e" strokeWidth="4" />
                <path
                  d="M30 50 L45 65 L70 35"
                  fill="none"
                  stroke="#22c55e"
                  strokeWidth="4"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="checkmark-path"
                />
              </svg>
              <div className="text-green-400 text-lg font-semibold mb-2">Transaction Successful!</div>
              <div className="text-zinc-300 text-sm text-center max-w-sm">{success}</div>
              <Button
                onClick={onClose}
                className="mt-6 px-8 py-2 bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white"
              >
                Done
              </Button>
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

              {/* Balance Display */}
              <div className="bg-zinc-800/50 border border-zinc-700 rounded-lg p-4">
                <div className="text-sm text-zinc-400 mb-1">
                  {isDeposit ? 'Available USDC' : `${tokenSymbol} Balance`}
                </div>
                <div className="text-2xl font-bold text-white">
                  {isDeposit
                    ? (Number.isFinite(parseFloat(usdcBalance)) ? parseFloat(usdcBalance).toFixed(2) : '0.00')
                    : formatStrategyBalance(strategyBalance, strategyName)}
                  <span className="text-zinc-400 text-lg ml-1">
                    {isDeposit ? 'USDC' : tokenSymbol}
                  </span>
                </div>
                {!isDeposit && price && (
                  <div className="text-sm text-zinc-400 mt-2">
                    ≈ ${(Number.isFinite(parseFloat(strategyBalance)) && Number.isFinite(parseFloat(price))
                      ? (parseFloat(strategyBalance) * parseFloat(price)).toFixed(2)
                      : '0.00')} USDC
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">
                    Amount ({isDeposit ? 'USDC to deposit' : `${tokenSymbol} to withdraw`})
                  </label>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    step={strategyName === 'MAVP' ? "0.00000001" : "0.000001"}
                    min="0"
                    max={maxAmount}
                    className="w-full px-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                    disabled={loading}
                  />
                  
                  {/* Show estimates */}
                  {strategyName === 'MAVC_YEARN' && amount && parseFloat(amount) > 0 && (
                    <div className="mt-2 p-3 bg-blue-900/20 border border-blue-700/30 rounded-lg">
                      {isDeposit ? (
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-zinc-300">You will receive approximately:</span>
                          <span className="text-lg font-semibold text-blue-400">
                            {estimatedShares.toFixed(6)} {tokenSymbol}
                          </span>
                        </div>
                      ) : (
                        <div className="flex justify-between items-center">
                          <span className="text-sm text-zinc-300">You will receive approximately:</span>
                          <span className="text-lg font-semibold text-blue-400">
                            ${estimatedAssets.toFixed(2)} USDC
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                  
                  {/* Show approximate USDC for withdrawal (MAVC/MAVP) */}
                  {!isDeposit && amount && price && parseFloat(amount) > 0 && strategyName !== 'MAVC_YEARN' && (
                    <div className="mt-2 p-3 bg-green-900/20 border border-green-700/30 rounded-lg">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-zinc-300">You will receive approximately:</span>
                        <span className="text-lg font-semibold text-green-400">
                          ${(parseFloat(amount) * parseFloat(price)).toFixed(2)} USDC
                        </span>
                      </div>
                    </div>
                  )}
                </div>

                {/* Quick Amount Buttons */}
                <div className="grid grid-cols-4 gap-2">
                  {isDeposit ? (
                    ['100', '500', '1000', '5000'].map((value) => (
                      <Button
                        key={value}
                        variant="outline"
                        size="sm"
                        onClick={() => setAmount(value)}
                        className="text-xs"
                        disabled={loading}
                      >
                        ${value}
                      </Button>
                    ))
                  ) : (
                    ['25%', '50%', '75%', '100%'].map((percent) => (
                      <Button
                        key={percent}
                        variant="outline"
                        size="sm"
                        onClick={() => {
                          const percentage = parseFloat(percent) / 100;
                          const balanceNum = parseFloat(strategyBalance);
                          setAmount(formatStrategyBalance((balanceNum * percentage).toString(), strategyName));
                        }}
                        className="text-xs"
                        disabled={loading}
                      >
                        {percent}
                      </Button>
                    ))
                  )}
                </div>
              </div>

              {/* Transaction Status Indicator - Show during processing or when there's a likelihood estimate */}
              {(loading || (likelihoodResult && amount && parseFloat(amount) > 0 && strategyName !== 'MAVC_YEARN')) && (
                <TransactionStatusIndicator
                  likelihoodResult={likelihoodResult || undefined}
                  status={transactionStatus}
                  showDetails={!loading}
                />
              )}

              {strategyName === 'MAVC_YEARN' && (
                <Alert className="bg-blue-900/20 border-blue-700/30 text-blue-200">
                  <Info className="h-4 w-4" />
                  <AlertDescription>
                    Yearn vaults use a share-based system. Your deposit will be converted to vault shares based on the current share price.
                  </AlertDescription>
                </Alert>
              )}

              <div className="flex space-x-3 pt-4">
                <Button
                  onClick={handleSubmit}
                  disabled={isButtonDisabled}
                  className={`flex-1 py-3 rounded-lg text-lg font-semibold shadow-md ${
                    isDeposit
                      ? 'bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700 text-white'
                      : 'bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700 text-white'
                  }`}
                >
                  {loading ? "Processing..." : `${isDeposit ? 'Deposit' : 'Withdraw'} ${tokenSymbol}`}
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
    </div>
  );
};

export default StrategyModal;

