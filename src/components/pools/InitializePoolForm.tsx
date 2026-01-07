'use client';

import { useState } from 'react';
import { nettingPoolsApi } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

interface InitializePoolFormProps {
  poolAddress: string;
  token0Address: string;
  token1Address: string;
  token0Symbol: string;
  token1Symbol: string;
  onSuccess?: () => void;
}

export default function InitializePoolForm({
  poolAddress,
  token0Address,
  token1Address,
  token0Symbol,
  token1Symbol,
  onSuccess,
}: InitializePoolFormProps) {
  const { username } = useNettingPoolsAuth();
  const [amountToken0, setAmountToken0] = useState('');
  const [amountToken1, setAmountToken1] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleInitialize = async () => {
    if (!amountToken0 || !amountToken1) {
      setError('Please enter amounts for both tokens');
      return;
    }

    if (parseFloat(amountToken0) <= 0 || parseFloat(amountToken1) <= 0) {
      setError('Amounts must be greater than 0');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const result = await nettingPoolsApi.initializePool({
        token_symbol: token1Symbol, // Pool is always token1/kUSD
        token0_amount: parseFloat(amountToken0),
        token1_amount: parseFloat(amountToken1),
        username: username,
      });

      setSuccess(`Pool initialization submitted! Transaction ID: ${result.transaction_id}`);
      setAmountToken0('');
      setAmountToken1('');
      setTimeout(() => {
        onSuccess?.();
      }, 2000);
    } catch (err: any) {
      setError('Initialization failed: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="text-gray-400 text-sm mb-4">
        Initialize the pool by providing initial liquidity for both tokens. This creates the pool's first price point.
      </div>

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

      {/* Token 0 Amount */}
      <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
        <div className="text-gray-400 text-xs mb-2">{token0Symbol} Amount</div>
        <input
          type="number"
          value={amountToken0}
          onChange={(e) => setAmountToken0(e.target.value)}
          placeholder="0.0"
          className="w-full bg-transparent text-white text-xl outline-none"
          disabled={loading}
        />
      </div>

      {/* Token 1 Amount */}
      <div className="bg-white/[0.02] border border-white/[0.05] rounded-xl p-4">
        <div className="text-gray-400 text-xs mb-2">{token1Symbol} Amount</div>
        <input
          type="number"
          value={amountToken1}
          onChange={(e) => setAmountToken1(e.target.value)}
          placeholder="0.0"
          className="w-full bg-transparent text-white text-xl outline-none"
          disabled={loading}
        />
      </div>

      {/* Initial Price Info */}
      {amountToken0 && amountToken1 && parseFloat(amountToken0) > 0 && parseFloat(amountToken1) > 0 && (
        <div className="text-gray-400 text-xs text-center">
          Initial price: 1 {token0Symbol} = {(parseFloat(amountToken1) / parseFloat(amountToken0)).toFixed(6)} {token1Symbol}
        </div>
      )}

      {/* Initialize Button */}
      <button
        onClick={handleInitialize}
        disabled={loading || !amountToken0 || !amountToken1}
        className="w-full px-6 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-xl font-medium transition-all"
      >
        {loading ? 'Initializing Pool...' : 'Initialize Pool'}
      </button>

      <div className="text-gray-500 text-xs text-center">
        Note: This operation requires admin permissions
      </div>
    </div>
  );
}

