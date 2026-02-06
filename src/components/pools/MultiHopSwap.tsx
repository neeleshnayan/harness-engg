'use client';

import { useState, useEffect } from 'react';
import { nettingPoolsApi, PoolInfo, TokenBalance } from '@/lib/nettingPoolsApi';
import { useNettingPoolsAuth } from '@/hooks/useNettingPoolsAuth';

interface SwapRoute {
  path: string[];
  description: string;
}

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
  const [estimatedOutput, setEstimatedOutput] = useState('');
  const [route, setRoute] = useState<SwapRoute | null>(null);
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
        const kTokens = data.k_tokens || {};

        // Filter out placeholder addresses and build token list
        const tokenList = Object.keys(kTokens).filter(
          symbol => kTokens[symbol]?.address && kTokens[symbol].address !== '0x0000000000000000000000000000000000000000'
        );
        setTokens(tokenList);

        // Set default selections if not already set
        if (tokenList.length >= 2 && !fromToken && !toToken) {
          // Default to kEUR -> kGBP if available, otherwise first two tokens
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

  // Find the route when tokens change
  useEffect(() => {
    if (fromToken === toToken) {
      setRoute(null);
      return;
    }

    // All tokens route through kUSD hub
    if (fromToken === 'kUSD' || toToken === 'kUSD') {
      // Direct swap
      setRoute({
        path: [fromToken, toToken],
        description: `Direct: ${fromToken} → ${toToken}`,
      });
    } else {
      // Multi-hop through kUSD
      setRoute({
        path: [fromToken, 'kUSD', toToken],
        description: `Multi-hop: ${fromToken} → kUSD → ${toToken}`,
      });
    }
  }, [fromToken, toToken]);

  // Estimate output when amount changes
  useEffect(() => {
    if (!amount || parseFloat(amount) <= 0 || !route) {
      setEstimatedOutput('');
      return;
    }

    const estimateOutput = async () => {
      setEstimating(true);
      try {
        // For multi-hop, we need to estimate each leg
        // This is a simplified estimation - actual output may vary
        let currentAmount = parseFloat(amount);

        for (let i = 0; i < route.path.length - 1; i++) {
          const pools = await nettingPoolsApi.getPools();
          const currentToken = route.path[i];
          const nextToken = route.path[i + 1];

          // Find pool for this leg
          const pool = pools.find(
            (p: PoolInfo) =>
              (p.token0_symbol === currentToken && p.token1_symbol === nextToken) ||
              (p.token0_symbol === nextToken && p.token1_symbol === currentToken)
          );

          if (!pool) {
            setEstimatedOutput('No route found');
            return;
          }

          // Get quote for this leg
          const tokenInAddr =
            pool.token0_symbol === currentToken ? pool.token0_address : pool.token1_address;
          const tokenOutAddr =
            pool.token0_symbol === nextToken ? pool.token0_address : pool.token1_address;

          const quote = await nettingPoolsApi.quoteSwap({
            pool_address: pool.pool_address,
            token_in_address: tokenInAddr,
            token_out_address: tokenOutAddr,
            amount_in: currentAmount,
          });

          currentAmount = parseFloat(quote.estimated_output);
        }

        setEstimatedOutput(currentAmount.toFixed(6));
      } catch (err) {
        console.error('Error estimating output:', err);
        setEstimatedOutput('Error');
      } finally {
        setEstimating(false);
      }
    };

    const debounce = setTimeout(estimateOutput, 500);
    return () => clearTimeout(debounce);
  }, [amount, route]);

  const handleSwap = async () => {
    if (!route || route.path.length < 2) {
      setError('Invalid route');
      return;
    }

    if (!amount || parseFloat(amount) <= 0) {
      setError('Please enter a valid amount');
      return;
    }

    if (!estimatedOutput || estimatedOutput === 'Error' || estimatedOutput === 'No route found') {
      setError('Unable to estimate output');
      return;
    }

    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const minAmountOut = parseFloat(estimatedOutput) * 0.95; // 5% slippage

      const result = await nettingPoolsApi.multiHopSwap({
        token_path: route.path,
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

  return (
    <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-white text-sm">
          🔄
        </div>
        <h3 className="text-xl font-light text-white">Multi-Hop Swap</h3>
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
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M7 16V4m0 0L3 8m4-4l4 4m6 0v12m0 0l4-4m-4 4l-4-4"
            />
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
      {route && (
        <div className="mb-4 p-3 bg-white/[0.02] border border-white/[0.05] rounded-xl">
          <p className="text-xs text-gray-400 mb-2">Route</p>
          <p className="text-sm text-gray-300">{route.description}</p>
          <div className="mt-2 flex items-center gap-2">
            {route.path.map((token, index) => (
              <div key={index} className="flex items-center gap-2">
                <span className="text-sm font-medium text-blue-400">{token}</span>
                {index < route.path.length - 1 && <span className="text-gray-500">→</span>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Slippage Info */}
      {estimatedOutput && estimatedOutput !== 'Error' && estimatedOutput !== 'No route found' && (
        <div className="text-gray-400 text-xs text-center mb-4">
          Max slippage: 5% • Minimum received: {(parseFloat(estimatedOutput) * 0.95).toFixed(6)}{' '}
          {toToken}
        </div>
      )}

      {/* Swap Button */}
      <button
        onClick={handleSwap}
        disabled={
          loading ||
          !route ||
          !amount ||
          parseFloat(amount) <= 0 ||
          !estimatedOutput ||
          estimatedOutput === 'Error' ||
          estimatedOutput === 'No route found' ||
          fromToken === toToken
        }
        className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 disabled:from-gray-600 disabled:to-gray-600 text-white rounded-xl font-medium transition-all"
      >
        {loading ? '⏳ Swapping...' : '🔄 Execute Multi-Hop Swap'}
      </button>

      <p className="text-xs text-gray-500 mt-3 text-center">
        Note: Multi-hop swaps route through kUSD and require admin permissions
      </p>
    </div>
  );
}

