import React, { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { AlertCircle, ArrowUp, ArrowDown } from "lucide-react";

interface MAVCModalProps {
  visible: boolean;
  onClose: () => void;
  action: 'deposit' | 'withdraw';
  mavcBalance: string;
  usdcBalance: string;
  onDeposit: (amount: string) => void;
  onWithdraw: (amount: string) => void;
  loading: boolean;
  error: string | null;
  success: string | null;
  mavcPrice?: string | null;
}

const MAVCModal: React.FC<MAVCModalProps> = ({
  visible,
  onClose,
  action,
  mavcBalance,
  usdcBalance,
  onDeposit,
  onWithdraw,
  loading,
  error,
  success,
  mavcPrice,
}) => {
  const [amount, setAmount] = useState("");

  useEffect(() => {
    if (!visible) {
      setAmount("");
    }
  }, [visible]);

  if (!visible) return null;

  const handleSubmit = () => {
    console.log('🔘 Modal Submit Button Clicked');
    console.log('📋 Action:', action);
    console.log('💵 Amount:', amount);
    console.log('🔓 Loading state:', loading);
    console.log('✔️ Amount validation:', {
      trimmed: amount.trim(),
      parsed: parseFloat(amount),
      isValid: parseFloat(amount) > 0
    });
    
    if (action === 'deposit') {
      console.log('✅ Calling onDeposit...');
      onDeposit(amount);
    } else {
      console.log('✅ Calling onWithdraw...');
      onWithdraw(amount);
    }
  };

  const isDeposit = action === 'deposit';
  const maxAmount = isDeposit ? "1000000" : mavcBalance;
  const isButtonDisabled = loading || !amount.trim() || parseFloat(amount) <= 0;
  
  console.log('🔍 Modal State:', {
    visible,
    action,
    amount,
    loading,
    error,
    success,
    isButtonDisabled,
    mavcBalance
  });

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
            {isDeposit ? (
              <ArrowDown className="mr-3 text-green-400" />
            ) : (
              <ArrowUp className="mr-3 text-red-400" />
            )}
            {isDeposit ? 'Deposit' : 'Withdraw'} MAVC
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
                  {isDeposit ? 'Available USDC' : 'MAVC Balance'}
                </div>
                <div className="text-2xl font-bold text-white">
                  {isDeposit
                    ? (Number.isFinite(parseFloat(usdcBalance)) ? parseFloat(usdcBalance).toFixed(2) : '0.00')
                    : (Number.isFinite(parseFloat(mavcBalance)) ? parseFloat(mavcBalance).toFixed(2) : '0.00')}
                  <span className="text-zinc-400 text-lg ml-1">
                    {isDeposit ? 'USDC' : 'MAVC'}
                  </span>
                </div>
                {!isDeposit && mavcPrice && (
                  <div className="text-sm text-zinc-400 mt-2">
                    ≈ ${(Number.isFinite(parseFloat(mavcBalance)) && Number.isFinite(parseFloat(mavcPrice))
                      ? (parseFloat(mavcBalance) * parseFloat(mavcPrice)).toFixed(2)
                      : '0.00')} USDC
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-zinc-200 mb-2">
                    Amount ({isDeposit ? 'USDC to deposit' : 'MAVC to withdraw'})
                  </label>
                  <input
                    type="number"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="0.00"
                    step="0.000001"
                    min="0"
                    max={maxAmount}
                    className="w-full px-4 py-3 border border-zinc-800 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 bg-zinc-800 text-white"
                    disabled={loading}
                  />
                  {/* Show approximate USDC for withdrawal */}
                  {!isDeposit && amount && mavcPrice && parseFloat(amount) > 0 && (
                    <div className="mt-2 p-3 bg-green-900/20 border border-green-700/30 rounded-lg">
                      <div className="flex justify-between items-center">
                        <span className="text-sm text-zinc-300">You will receive approximately:</span>
                        <span className="text-lg font-semibold text-green-400">
                          ${(parseFloat(amount) * parseFloat(mavcPrice)).toFixed(2)} USDC
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
                          setAmount((parseFloat(mavcBalance) * percentage).toFixed(2));
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

              {loading && (
                <div className="bg-blue-900/20 border border-blue-700/30 rounded-lg p-4 mb-4">
                  <div className="flex items-center space-x-3">
                    <div className="animate-spin rounded-full h-6 w-6 border-3 border-blue-500 border-t-transparent"></div>
                    <div className="flex-1">
                      <div className="text-sm font-medium text-blue-300">Processing transaction...</div>
                      <div className="text-xs text-zinc-400 mt-1">Waiting for balance to update on-chain</div>
                    </div>
                  </div>
                </div>
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
                  {loading ? "Processing..." : `${isDeposit ? 'Deposit' : 'Withdraw'} MAVC`}
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

export default MAVCModal;

