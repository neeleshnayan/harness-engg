'use client';

import { useState, useEffect } from 'react';
import { nettingPoolsApi } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

interface SwapFormProps {
  poolAddress: string;
  token0Address: string;
  token1Address: string;
  token0Symbol: string;
  token1Symbol: string;
  onSuccess?: () => void;
}

export default function SwapForm({
  poolAddress,
  token0Address,
  token1Address,
  token0Symbol,
  token1Symbol,
  onSuccess,
}: SwapFormProps) {
  const { username } = useNettingPoolsAuth();
  const [fromToken, setFromToken] = useState<'token0' | 'token1'>('token0');
  const [amount, setAmount] = useState('');
  const [estimatedOutput, setEstimatedOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fromTokenAddr = fromToken === 'token0' ? token0Address : token1Address;
  const toTokenAddr = fromToken === 'token0' ? token1Address : token0Address;
  const fromSymbol = fromToken === 'token0' ? token0Symbol : token1Symbol;
  const toSymbol = fromToken === 'token0' ? token1Symbol : token0Symbol;

  useEffect(() => {
    if (amount && parseFloat(amount) > 0) {
      estimateSwap();
    } else {
      setEstimatedOutput('');
    }
  }, [amount, fromToken]);

  const estimateSwap = async () => {
    try {
      const quote = await nettingPoolsApi.quoteSwap({
        pool_address: poolAddress,
        token_in_address: fromTokenAddr,
        token_out_address: toTokenAddr,
        amount_in: parseFloat(amount),
      });
      setEstimatedOutput(quote.estimated_output);
    } catch (err: any) {
      console.error('Error estimating swap:', err);
      setEstimatedOutput('');
    }
  };

  const handleSwap = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    if (!estimatedOutput) {
      setError('Unable to estimate output');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const minAmountOut = parseFloat(estimatedOutput) * 0.95; // 5% slippage
      const result = await nettingPoolsApi.executeSwap({
        pool_address: poolAddress,
        token_in_address: fromTokenAddr,
        token_out_address: toTokenAddr,
        amount_in: parseFloat(amount),
        min_amount_out: minAmountOut,
        username: username,
      });

      setSuccess(`Swap submitted! Transaction ID: ${result.transaction_id}`);
      setAmount('');
      setEstimatedOutput('');
      setTimeout(() => {
        onSuccess?.();
      }, 2000);
    } catch (err: any) {
      setError('Swap failed: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const switchDirection = () => {
    setFromToken(fromToken === 'token0' ? 'token1' : 'token0');
    setAmount('');
    setEstimatedOutput('');
  };

  return (
    <div className="space-y-4">
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm">
          {success}
        </div>
      )}

      {/* From Token */}
      <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
        <div className="text-gray-400 text-xs mb-2">From</div>
        <div className="flex items-center gap-3">
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            placeholder="0.0"
            className="flex-1 bg-transparent text-white text-2xl outline-none"
            disabled={loading}
          />
          <div className="text-white font-medium">{fromSymbol}</div>
        </div>
      </div>

      {/* Swap Direction Button */}
      <div className="flex justify-center">
        <button
          onClick={switchDirection}
          className="p-2 bg-white/[0.05] hover:bg-white/[0.1] rounded-lg transition-all"
          disabled={loading}
        >
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
        </button>
      </div>

      {/* To Token */}
      <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
        <div className="text-gray-400 text-xs mb-2">To (estimated)</div>
        <div className="flex items-center gap-3">
          <div className="flex-1 text-white text-2xl">
            {estimatedOutput ? parseFloat(estimatedOutput).toFixed(6) : '0.0'}
          </div>
          <div className="text-white font-medium">{toSymbol}</div>
        </div>
      </div>

      {/* Slippage Info */}
      <div className="text-gray-400 text-xs text-center">
        Max slippage: 5% • Minimum received: {estimatedOutput ? (parseFloat(estimatedOutput) * 0.95).toFixed(6) : '0.0'} {toSymbol}
      </div>

      {/* Execute Button */}
      <button
        onClick={handleSwap}
        disabled={loading || !amount || !estimatedOutput}
        className="w-full px-6 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-xl font-medium transition-all"
      >
        {loading ? 'Submitting Swap...' : 'Swap'}
      </button>
    </div>
  );
}

