'use client';

import { useState, useEffect } from 'react';
import { nettingPoolsApi, TokenBalance } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

interface MultiHopSwapProps {
  onSuccess?: () => void;
}

export default function MultiHopSwap({ onSuccess }: MultiHopSwapProps) {
  const { username, walletAddress } = useNettingPoolsAuth();

  // Dynamic token list from API
  const [tokens, setTokens] = useState<string[]>([]);
  const [fromToken, setFromToken] = useState<string>('');
  const [toToken, setToToken] = useState<string>('');
  const [amount, setAmount] = useState('');

  // Estimation state
  const [estimatedOutput, setEstimatedOutput] = useState('');
  const [minAmountOut, setMinAmountOut] = useState('');
  const [routePath, setRoutePath] = useState<string>('');
  const [isCrossEcosystem, setIsCrossEcosystem] = useState(false);

  const [loading, setLoading] = useState(false);
  const [estimating, setEstimating] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [balances, setBalances] = useState<Record<string, string>>({});

  // Fetch token configs on mount
  useEffect(() => {
    const fetchTokens = async () => {
      try {
        const data = await nettingPoolsApi.getSupportedTokens();
        // Support all tokens (k-tokens and others if they exist in config)
        // Combine k_tokens and any other future categories
        const kTokens = data.k_tokens || {};

        // Filter out placeholder addresses
        const tokenList = Object.keys(kTokens).filter(
          symbol => kTokens[symbol]?.address && kTokens[symbol].address !== '0x0000000000000000000000000000000000000000'
        );
        setTokens(tokenList);

        // Set default selections
        if (tokenList.length >= 2 && !fromToken && !toToken) {
          const defaultFrom = tokenList.includes('kEUR') ? 'kEUR' : tokenList[0];
          const defaultTo = tokenList.includes('kGBP') ? 'kGBP' : (tokenList[1] || tokenList[0]);
          setFromToken(defaultFrom);
          setToToken(defaultTo);
        }
      } catch (err) {
        console.error('Error fetching token configs:', err);
      }
    };

    fetchTokens();
  }, []);

  // Fetch user balances
  useEffect(() => {
    if (!walletAddress) return;

    const fetchBalances = async () => {
      try {
        const balanceData = await nettingPoolsApi.getBalances(walletAddress);
        const balanceMap: Record<string, string> = {};
        balanceData.forEach((b: TokenBalance) => {
          balanceMap[b.symbol] = b.balance;
        });
        setBalances(balanceMap);
      } catch (err) {
        console.error('Error fetching balances:', err);
      }
    };

    fetchBalances();
  }, [walletAddress]);

  // Estimate swap output
  useEffect(() => {
    if (!amount || parseFloat(amount) <= 0 || fromToken === toToken) {
      setEstimatedOutput('');
      setRoutePath('');
      return;
    }

    const estimate = async () => {
      setEstimating(true);
      setError('');
      try {
        // Use Standard Estimator from backend
        const result = await nettingPoolsApi.estimateSwap({
          from_token: fromToken,
          to_token: toToken,
          amount: parseFloat(amount),
          slippage_tolerance: 0.05 // 5% default
        });

        setEstimatedOutput(result.estimated_output.toFixed(6));
        setMinAmountOut(result.min_amount_out.toFixed(6));
        // Standard Pools API doesn't return route details
        setRoutePath('');
        setIsCrossEcosystem(false);
      } catch (err: any) {
        console.error('Error estimating output:', err);
        setEstimatedOutput('Error');
        setRoutePath('');
      } finally {
        setEstimating(false);
      }
    };

    const debounce = setTimeout(estimate, 500);
    return () => clearTimeout(debounce);
  }, [amount, fromToken, toToken]);

  const handleSwap = async () => {
    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      // Execute using Standard Pools API
      const result = await nettingPoolsApi.executeSwap({
        from_token: fromToken,
        to_token: toToken,
        amount: parseFloat(amount),
        wallet_username: username || '',
        slippage_tolerance: 0.05
      });

      setSuccess(`Swap confirmed! Transaction ID: ${result.transaction_id}`);
      setAmount('');
      setEstimatedOutput('');
      setRoutePath('');

      // Refresh balances
      setTimeout(() => {
        onSuccess?.();
      }, 2000);
    } catch (err: any) {
      setError('Swap failed: ' + (err.response?.data?.detail || err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  };

  const switchTokens = () => {
    setFromToken(toToken);
    setToToken(fromToken);
    setAmount('');
    setEstimatedOutput('');
  };

  // Helper to parse route string "A -> B -> C" into array
  const parseRoute = (routeStr: string) => {
    return routeStr.split(' -> ');
  };

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm">
          🔄
        </div>
        <h3 className="text-xl font-light text-white">Universal Swap</h3>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      {success && (
        <div className="mb-4 p-3 bg-green-500/10 border border-green-500/30 rounded-lg text-green-400 text-sm whitespace-pre-line">
          {success}
        </div>
      )}

      {/* From Token */}
      <div className="mb-4">
        <div className="text-gray-400 text-xs mb-2">From</div>
        <div className="flex gap-3">
          <select
            value={fromToken}
            onChange={(e) => setFromToken(e.target.value)}
            className="flex-1 px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            disabled={loading || tokens.length === 0}
          >
            {tokens.map((symbol) => (
              <option key={symbol} value={symbol} className="bg-slate-900">
                {symbol}
              </option>
            ))}
          </select>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="flex-1 px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            placeholder="Amount"
            disabled={loading}
          />
        </div>
        {walletAddress && balances[fromToken] && (
          <p className="text-xs text-gray-500 mt-1">
            Balance: {parseFloat(balances[fromToken]).toFixed(2)} {fromToken}
          </p>
        )}
      </div>

      {/* Switch Button */}
      <div className="flex justify-center mb-4">
        <button
          onClick={switchTokens}
          disabled={loading}
          className="p-2 bg-white/[0.05] hover:bg-white/[0.1] rounded-lg transition-colors disabled:opacity-50"
          title="Switch tokens"
        >
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4" />
          </svg>
        </button>
      </div>

      {/* To Token */}
      <div className="mb-4">
        <div className="text-gray-400 text-xs mb-2">To (estimated)</div>
        <div className="flex gap-3">
          <select
            value={toToken}
            onChange={(e) => setToToken(e.target.value)}
            className="flex-1 px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
            disabled={loading || tokens.length === 0}
          >
            {tokens.map((symbol) => (
              <option key={symbol} value={symbol} className="bg-slate-900">
                {symbol}
              </option>
            ))}
          </select>
          <input
            type="text"
            value={estimating ? 'Estimating...' : estimatedOutput}
            readOnly
            className="flex-1 px-4 py-3 bg-white/[0.03] border border-white/[0.05] text-gray-300 rounded-xl"
            placeholder="Estimated output"
          />
        </div>
        {walletAddress && balances[toToken] && (
          <p className="text-xs text-gray-500 mt-1">
            Balance: {parseFloat(balances[toToken]).toFixed(2)} {toToken}
          </p>
        )}
      </div>

      {/* Route Information */}
      {routePath && (
        <div className="mb-4 p-3 bg-white/[0.02] border border-white/[0.05] rounded-xl">
          <div className="flex justify-between items-center mb-2">
            <p className="text-xs text-gray-400">Route</p>
            {isCrossEcosystem && (
              <span className="text-[10px] bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full border border-purple-500/30">
                Cross-Ecosystem
              </span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            {parseRoute(routePath).map((token, index) => (
              <div key={index} className="flex items-center gap-2">
                <span className={`text-sm font-medium ${index === 0 || index === parseRoute(routePath).length - 1 ? 'text-white' : 'text-blue-400'}`}>
                  {token}
                </span>
                {index < parseRoute(routePath).length - 1 && <span className="text-gray-500">→</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slippage Info */}
      {estimatedOutput && estimatedOutput !== 'Error' && minAmountOut && (
        <div className="text-gray-400 text-xs text-center mb-4">
          Max slippage: 5% • Minimum received: {minAmountOut} {toToken}
        </div>
      )}

      {/* Swap Button */}
      <button
        onClick={handleSwap}
        disabled={
          loading ||
          !amount ||
          parseFloat(amount) <= 0 ||
          !estimatedOutput ||
          estimatedOutput === 'Error' ||
          fromToken === toToken
        }
        className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-xl font-medium transition-all"
      >
        {loading ? '⏳ Swapping...' : '🔄 Execute Swap'}
      </button>
    </div>
  );
}

