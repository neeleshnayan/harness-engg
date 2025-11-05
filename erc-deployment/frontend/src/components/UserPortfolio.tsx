import { formatToken, formatUsd } from '@/lib/format';
import type { TransactionStatus } from '@/hooks/useTransactionStatus';
import { useEffect, useState } from 'react';

type Props = {
  shares?: bigint;
  shareValue?: bigint;
  usdcBalance?: bigint;
  allowance?: bigint;
  shareDecimals: number;
  usdcDecimals: number;
  vaultSymbol?: string;
  usdcSymbol: string;
  transactionStatus?: TransactionStatus;
  transactionType?: 'deposit' | 'withdraw' | 'approve' | null;
};

export const UserPortfolio = ({
  shares,
  shareValue,
  usdcBalance,
  allowance,
  shareDecimals,
  usdcDecimals,
  vaultSymbol,
  usdcSymbol,
  transactionStatus = 'idle',
  transactionType,
}: Props) => {
  const shareTicker = vaultSymbol ?? 'MAVC';
  const stableTicker = usdcSymbol ?? 'USDC';

  // Track previous values for animation
  const [prevShares, setPrevShares] = useState<bigint | undefined>(shares);
  const [prevShareValue, setPrevShareValue] = useState<bigint | undefined>(shareValue);
  const [showSuccessFlash, setShowSuccessFlash] = useState(false);

  // Update previous values when transaction completes
  useEffect(() => {
    if (transactionStatus === 'success') {
      setShowSuccessFlash(true);
      setTimeout(() => setShowSuccessFlash(false), 1000);
    }

    if (transactionStatus === 'idle') {
      setPrevShares(shares);
      setPrevShareValue(shareValue);
    }
  }, [transactionStatus, shares, shareValue]);

  // Calculate delta for deposit/withdraw
  const sharesDelta = shares && prevShares ? shares - prevShares : 0n;
  const valueDelta = shareValue && prevShareValue ? shareValue - prevShareValue : 0n;

  const getCardBorderClass = (cardType: 'shares' | 'value') => {
    const isAffected =
      (cardType === 'shares' && (transactionType === 'deposit' || transactionType === 'withdraw')) ||
      (cardType === 'value' && (transactionType === 'deposit' || transactionType === 'withdraw'));

    if (!isAffected) return 'border-white/10';

    if (transactionStatus === 'pending') {
      return 'border-blue-400/50 animate-pulse-border';
    }
    if (transactionStatus === 'success' && showSuccessFlash) {
      return 'border-green-400/50 animate-success-flash';
    }
    if (transactionStatus === 'failed') {
      return 'border-red-400/50';
    }
    return 'border-white/10';
  };

  const getStatusIndicator = (cardType: 'shares' | 'value') => {
    const isAffected =
      (cardType === 'shares' && (transactionType === 'deposit' || transactionType === 'withdraw')) ||
      (cardType === 'value' && (transactionType === 'deposit' || transactionType === 'withdraw'));

    if (!isAffected || transactionStatus === 'idle') return null;

    return (
      <div className="flex items-center gap-1 mt-2">
        <div className={`h-2 w-2 rounded-full ${
          transactionStatus === 'pending' ? 'bg-blue-400 animate-pulse' :
          transactionStatus === 'success' ? 'bg-green-400' :
          transactionStatus === 'failed' ? 'bg-red-400' :
          'bg-gray-400'
        }`} />
        <span className="text-xs text-white/60">
          {transactionStatus === 'pending' ? 'Updating...' :
           transactionStatus === 'success' ? 'Updated' :
           transactionStatus === 'failed' ? 'Failed' :
           'Ready'}
        </span>
      </div>
    );
  };

  return (
    <section className="mt-12 rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl shadow-indigo-500/10 backdrop-blur">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-display text-xl text-white">Your Portfolio Snapshot</h2>
          <p className="text-sm text-white/60">Track your vault tokens and available {stableTicker}.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-white/70">
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            Allowance: {formatUsd(allowance, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </span>
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1">
            Wallet {stableTicker}: {formatUsd(usdcBalance, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </span>
        </div>
      </div>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <div className={`rounded-2xl border ${getCardBorderClass('shares')} bg-white/5 p-6 transition-all duration-300`}>
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Vault Shares</p>
            {getStatusIndicator('shares')}
          </div>
          <h3 className="mt-4 font-display text-3xl text-white">
            {formatToken(shares ?? 0n, shareDecimals, { maximumFractionDigits: 4, minimumFractionDigits: 4 })} {shareTicker}
          </h3>
          {transactionStatus === 'success' && sharesDelta !== 0n && (
            <p className={`mt-2 text-sm font-medium ${sharesDelta > 0n ? 'text-green-400' : 'text-red-400'}`}>
              {sharesDelta > 0n ? '+' : ''}{formatToken(sharesDelta, shareDecimals, { maximumFractionDigits: 4 })} {shareTicker}
            </p>
          )}
          <p className="mt-3 text-sm text-white/70">
            {shareTicker} tokens minted to your wallet. Each represents your slice of the vault.
          </p>
        </div>
        <div className={`rounded-2xl border ${getCardBorderClass('value')} bg-white/5 p-6 transition-all duration-300`}>
          <div className="flex items-center justify-between">
            <p className="text-xs uppercase tracking-[0.2em] text-white/60">Vault Value</p>
            {getStatusIndicator('value')}
          </div>
          <h3 className="mt-4 font-display text-3xl text-white">
            {formatUsd(shareValue, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </h3>
          {transactionStatus === 'success' && valueDelta !== 0n && (
            <p className={`mt-2 text-sm font-medium ${valueDelta > 0n ? 'text-green-400' : 'text-red-400'}`}>
              {valueDelta > 0n ? '+' : ''}{formatUsd(valueDelta, usdcDecimals, { maximumFractionDigits: 2 })}
            </p>
          )}
          <p className="mt-3 text-sm text-white/70">
            Approximate amount of {stableTicker} you can withdraw at this moment.
          </p>
        </div>
      </div>
    </section>
  );
};
