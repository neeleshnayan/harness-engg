'use client';

import { useEffect, useMemo, useState } from 'react';
import { nettingPoolsApi } from '@/lib/nettingPoolsApi';

interface TokenControlsSectionProps {
  tokenSymbols: string[];
  supplies: Record<string, string>;
  suppliesLoading: boolean;
  username: string;
  walletAddress: string;
  onRefreshSupplies: () => Promise<void>;
}

type StringMap = Record<string, string>;
type BoolMap = Record<string, boolean>;

const ETH_ADDRESS_REGEX = /^0x[a-fA-F0-9]{40}$/;

export default function TokenControlsSection({
  tokenSymbols,
  supplies,
  suppliesLoading,
  username,
  walletAddress,
  onRefreshSupplies,
}: TokenControlsSectionProps) {
  const [selectedToken, setSelectedToken] = useState('');
  const [targetIdentity, setTargetIdentity] = useState('');
  const [amount, setAmount] = useState('');
  const [pausedByToken, setPausedByToken] = useState<BoolMap>({});
  const [pauseLoadingByToken, setPauseLoadingByToken] = useState<BoolMap>({});
  const [actionLoadingKey, setActionLoadingKey] = useState<string>('');
  const [refreshingAll, setRefreshingAll] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const formatSupply = (value: string | undefined): string => {
    const num = parseFloat(value || '0');
    return new Intl.NumberFormat('en', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(num);
  };

  const hasTokens = useMemo(() => tokenSymbols.length > 0, [tokenSymbols]);

  useEffect(() => {
    if (!hasTokens) return;
    setSelectedToken((prev) => (prev && tokenSymbols.includes(prev) ? prev : tokenSymbols[0]));
  }, [hasTokens, tokenSymbols]);

  useEffect(() => {
    if (targetIdentity) return;
    if (walletAddress) {
      setTargetIdentity(walletAddress);
      return;
    }
    if (username) {
      setTargetIdentity(username);
    }
  }, [targetIdentity, walletAddress, username]);

  const fetchPauseStatus = async (symbol: string) => {
    setPauseLoadingByToken((prev) => ({ ...prev, [symbol]: true }));
    try {
      const response = await nettingPoolsApi.getTokenPauseStatus(symbol);
      setPausedByToken((prev) => ({ ...prev, [symbol]: response.is_paused }));
    } catch (err) {
      setPausedByToken((prev) => ({ ...prev, [symbol]: false }));
      console.error(`Failed to fetch pause state for ${symbol}:`, err);
    } finally {
      setPauseLoadingByToken((prev) => ({ ...prev, [symbol]: false }));
    }
  };

  useEffect(() => {
    if (!hasTokens) return;
    Promise.all(tokenSymbols.map((symbol) => fetchPauseStatus(symbol))).catch((err) => {
      console.error('Failed to fetch pause statuses:', err);
    });
  }, [hasTokens, tokenSymbols]);

  const runAction = async (key: string, action: () => Promise<void>) => {
    setActionLoadingKey(key);
    setError('');
    setSuccess('');
    try {
      await action();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Token control action failed');
    } finally {
      setActionLoadingKey('');
    }
  };

  const resolveRecipient = (identityInput: string) => {
    const value = identityInput.trim();
    if (!value) return {};
    if (ETH_ADDRESS_REGEX.test(value)) {
      return { wallet_address: value, username: undefined as string | undefined };
    }
    return { wallet_address: undefined as string | undefined, username: value };
  };

  const resolveBurnSource = (identityInput: string) => {
    const value = identityInput.trim();
    if (!value) return {};
    if (ETH_ADDRESS_REGEX.test(value)) {
      return { from_address: value, username: undefined as string | undefined };
    }
    return { from_address: undefined as string | undefined, username: value };
  };

  const handleMint = async () => {
    const parsedAmount = parseFloat(amount || '0');
    if (!parsedAmount || parsedAmount <= 0) {
      setError(`Enter a valid mint amount for ${selectedToken}`);
      return;
    }

    const resolved = resolveRecipient(targetIdentity);
    await runAction(`${selectedToken}-mint`, async () => {
      const response = await nettingPoolsApi.mintToken({
        token_symbol: selectedToken,
        amount: parsedAmount,
        wallet_address: resolved.wallet_address,
        username: resolved.username || username,
      });
      setSuccess(`${selectedToken} mint submitted (${response.transaction_id})`);
      setAmount('');
      await onRefreshSupplies();
    });
  };

  const handleBurn = async () => {
    const parsedAmount = parseFloat(amount || '0');
    if (!parsedAmount || parsedAmount <= 0) {
      setError(`Enter a valid burn amount for ${selectedToken}`);
      return;
    }

    const resolved = resolveBurnSource(targetIdentity);
    await runAction(`${selectedToken}-burn`, async () => {
      const response = await nettingPoolsApi.burnToken({
        token_symbol: selectedToken,
        amount: parsedAmount,
        from_address: resolved.from_address,
        username: resolved.username || username,
      });
      setSuccess(`${selectedToken} burn submitted (${response.transaction_id})`);
      setAmount('');
      await onRefreshSupplies();
    });
  };

  const handlePauseToggle = async () => {
    const isPaused = !!pausedByToken[selectedToken];
    await runAction(`${selectedToken}-${isPaused ? 'unpause' : 'pause'}`, async () => {
      const response = isPaused
        ? await nettingPoolsApi.unpauseToken(selectedToken)
        : await nettingPoolsApi.pauseToken(selectedToken);
      setSuccess(`${selectedToken} ${isPaused ? 'unpause' : 'pause'} submitted (${response.transaction_id})`);
      await fetchPauseStatus(selectedToken);
    });
  };

  const refreshAll = async () => {
    setRefreshingAll(true);
    setError('');
    setSuccess('');
    try {
      await onRefreshSupplies();
      await Promise.all(tokenSymbols.map((symbol) => fetchPauseStatus(symbol)));
    } finally {
      setRefreshingAll(false);
    }
  };

  return (
    <div>
      <div className="mb-8 flex items-end justify-between gap-6">
        <div>
          <h2 className="text-3xl font-light text-white mb-3 tracking-tight">Token Controls</h2>
          <p className="text-gray-500 text-sm font-light">
            Tokens in circulation with mint, burn, pause, and unpause controls
          </p>
        </div>
        <button
          onClick={refreshAll}
          disabled={refreshingAll || suppliesLoading}
          className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
        >
          {refreshingAll || suppliesLoading ? 'Refreshing...' : 'Refresh All'}
        </button>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/30 rounded-xl text-green-400 text-sm">
          {success}
        </div>
      )}

      {!hasTokens ? (
        <div className="text-gray-400 text-center py-8">Loading token configuration...</div>
      ) : (
        <div>
          <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-5 gap-4 mb-8">
            {tokenSymbols.map((symbol) => {
              const pauseLoading = !!pauseLoadingByToken[symbol];
              const paused = !!pausedByToken[symbol];
              const isSelected = selectedToken === symbol;
              return (
                <button
                  key={symbol}
                  onClick={() => setSelectedToken(symbol)}
                  className={`text-left backdrop-blur-xl rounded-2xl p-4 border transition-all ${
                    isSelected
                      ? 'bg-blue-600/20 border-blue-500/40'
                      : 'bg-white/[0.02] border-white/[0.05] hover:bg-white/[0.04]'
                  }`}
                >
                  <div className="text-gray-400 text-xs mb-1">{symbol}</div>
                  <div className="text-white text-xl font-light whitespace-nowrap">
                    {suppliesLoading ? '...' : formatSupply(supplies[symbol])}
                  </div>
                  <div className="text-gray-500 text-xs mt-1">In circulation</div>
                  <div className="mt-2 text-[11px]">
                    {pauseLoading ? (
                      <span className="text-gray-400">Checking...</span>
                    ) : paused ? (
                      <span className="text-yellow-300">Paused</span>
                    ) : (
                      <span className="text-emerald-300">Active</span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>

          <div className="backdrop-blur-xl bg-white/[0.02] border border-white/[0.05] rounded-2xl p-6">
            <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
              <div>
                <div className="text-gray-400 text-xs">Selected token</div>
                <div className="text-white text-2xl font-light">{selectedToken}</div>
              </div>
              <select
                value={selectedToken}
                onChange={(e) => setSelectedToken(e.target.value)}
                className="px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              >
                {tokenSymbols.map((symbol) => (
                  <option key={symbol} value={symbol} className="bg-slate-900">
                    {symbol}
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-gray-400 text-xs mb-2">Target wallet / username</label>
                <input
                  type="text"
                  value={targetIdentity}
                  onChange={(e) => setTargetIdentity(e.target.value)}
                  className="w-full px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  placeholder="0x... or username"
                />
              </div>
              <div>
                <label className="block text-gray-400 text-xs mb-2">Amount (mint/burn)</label>
                <input
                  type="number"
                  min="0"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  className="w-full px-4 py-3 bg-white/[0.02] border border-white/[0.05] text-white rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500/50"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <button
                onClick={handleMint}
                disabled={!selectedToken || actionLoadingKey === `${selectedToken}-mint`}
                className="px-4 py-2.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
              >
                {actionLoadingKey === `${selectedToken}-mint` ? 'Submitting...' : 'Mint'}
              </button>
              <button
                onClick={handleBurn}
                disabled={!selectedToken || actionLoadingKey === `${selectedToken}-burn`}
                className="px-4 py-2.5 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
              >
                {actionLoadingKey === `${selectedToken}-burn` ? 'Submitting...' : 'Burn'}
              </button>
              <button
                onClick={handlePauseToggle}
                disabled={
                  !selectedToken ||
                  actionLoadingKey === `${selectedToken}-pause` ||
                  actionLoadingKey === `${selectedToken}-unpause` ||
                  !!pauseLoadingByToken[selectedToken]
                }
                className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 text-white rounded-xl transition-all"
              >
                {actionLoadingKey === `${selectedToken}-pause` || actionLoadingKey === `${selectedToken}-unpause`
                  ? 'Submitting...'
                  : pausedByToken[selectedToken]
                    ? 'Unpause'
                    : 'Pause'}
              </button>
              <button
                onClick={() => fetchPauseStatus(selectedToken)}
                disabled={!selectedToken || !!pauseLoadingByToken[selectedToken]}
                className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 disabled:bg-gray-600 text-white rounded-xl transition-all"
              >
                {pauseLoadingByToken[selectedToken] ? 'Checking...' : 'Refresh Status'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

