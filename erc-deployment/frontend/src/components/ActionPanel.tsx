import { useEffect, useMemo, useState } from 'react';
import { useAccount, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import type { Address } from 'viem';
import { erc20Abi } from '@/abi/erc20';
import { vaultAbi } from '@/abi/vault';
import { formatToken, formatUsd, toBaseUnit } from '@/lib/format';

const differenceInDecimals = (shareDecimals: number, usdcDecimals: number) => {
  const diff = shareDecimals - usdcDecimals;
  return BigInt(diff > 0 ? diff : 0);
};

const estimateDepositShares = (
  amount: bigint,
  totalAssets?: bigint,
  totalSupply?: bigint,
  shareDecimals = 18,
  usdcDecimals = 6,
) => {
  if (amount === 0n) return 0n;
  if (!totalAssets || totalAssets === 0n || !totalSupply || totalSupply === 0n) {
    const exponent = differenceInDecimals(shareDecimals, usdcDecimals);
    return amount * 10n ** exponent;
  }
  return (amount * totalSupply) / totalAssets;
};

const estimateWithdrawShares = (
  amount: bigint,
  totalAssets?: bigint,
  totalSupply?: bigint,
) => {
  if (amount === 0n || !totalAssets || totalAssets === 0n || !totalSupply || totalSupply === 0n) {
    return 0n;
  }
  return (amount * totalSupply) / totalAssets;
};

type Props = {
  vaultAddress?: Address;
  usdcAddress?: Address;
  usdcDecimals: number;
  shareDecimals: number;
  totalAssets?: bigint;
  totalSupply?: bigint;
  userShareValue?: bigint;
  usdcBalance?: bigint;
  allowance?: bigint;
  usdcSymbol: string;
  vaultSymbol?: string;
  refetchAll: () => void;
};

export const ActionPanel = ({
  vaultAddress,
  usdcAddress,
  usdcDecimals,
  shareDecimals,
  totalAssets,
  totalSupply,
  userShareValue,
  usdcBalance,
  allowance,
  usdcSymbol,
  vaultSymbol,
  refetchAll,
}: Props) => {
  const { address, isConnected } = useAccount();
  const [depositAmount, setDepositAmount] = useState('');
  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [feedback, setFeedback] = useState<string>();
  const { writeContractAsync, isPending } = useWriteContract();

  const [approvalHash, setApprovalHash] = useState<`0x${string}` | undefined>();
  const [depositHash, setDepositHash] = useState<`0x${string}` | undefined>();
  const [withdrawHash, setWithdrawHash] = useState<`0x${string}` | undefined>();

  const { isLoading: approvalLoading, isSuccess: approvalSuccess } = useWaitForTransactionReceipt({ hash: approvalHash });
  const { isLoading: depositLoading, isSuccess: depositSuccess } = useWaitForTransactionReceipt({ hash: depositHash });
  const { isLoading: withdrawLoading, isSuccess: withdrawSuccess } = useWaitForTransactionReceipt({ hash: withdrawHash });

  const shareTicker = vaultSymbol ?? 'MAVC';
  const stableTicker = usdcSymbol ?? 'USDC';

  useEffect(() => {
    if (approvalSuccess) {
      setApprovalHash(undefined);
      setFeedback('Approval confirmed.');
      refetchAll();
    }
  }, [approvalSuccess, refetchAll]);

  useEffect(() => {
    if (depositSuccess) {
      setDepositHash(undefined);
      setFeedback('Deposit confirmed.');
      refetchAll();
    }
  }, [depositSuccess, refetchAll]);

  useEffect(() => {
    if (withdrawSuccess) {
      setWithdrawHash(undefined);
      setFeedback('Withdrawal confirmed.');
      refetchAll();
    }
  }, [withdrawSuccess, refetchAll]);

  const depositAmountBase = useMemo(() => {
    try {
      return toBaseUnit(depositAmount || '0', usdcDecimals);
    } catch (error) {
      return 0n;
    }
  }, [depositAmount, usdcDecimals]);

  const withdrawAmountBase = useMemo(() => {
    try {
      return toBaseUnit(withdrawAmount || '0', usdcDecimals);
    } catch (error) {
      return 0n;
    }
  }, [withdrawAmount, usdcDecimals]);

  const estimatedDepositShares = useMemo(
    () => estimateDepositShares(depositAmountBase, totalAssets, totalSupply, shareDecimals, usdcDecimals),
    [depositAmountBase, totalAssets, totalSupply, shareDecimals, usdcDecimals],
  );

  const estimatedWithdrawShares = useMemo(
    () => estimateWithdrawShares(withdrawAmountBase, totalAssets, totalSupply),
    [withdrawAmountBase, totalAssets, totalSupply],
  );

  const needsApproval = useMemo(() => {
    if (depositAmountBase === 0n) return false;
    if (allowance === undefined) return true;
    return allowance < depositAmountBase;
  }, [allowance, depositAmountBase]);

  const lacksBalance = useMemo(() => {
    if (!usdcBalance) return false;
    return depositAmountBase > usdcBalance;
  }, [depositAmountBase, usdcBalance]);

  const exceedsShareValue = useMemo(() => {
    if (!userShareValue) return false;
    return withdrawAmountBase > userShareValue;
  }, [withdrawAmountBase, userShareValue]);

  const disabledDeposit =
    !isConnected || !vaultAddress || !usdcAddress || depositAmountBase === 0n || lacksBalance || isPending;

  const disabledWithdraw =
    !isConnected || !vaultAddress || withdrawAmountBase === 0n || exceedsShareValue || isPending;

  const handleApprove = async () => {
    if (!vaultAddress || !usdcAddress || depositAmountBase === 0n) return;
    try {
      setFeedback('Submitting approval...');
      const hash = await writeContractAsync({
        address: usdcAddress,
        abi: erc20Abi,
        functionName: 'approve',
        args: [vaultAddress, depositAmountBase],
      });
      setApprovalHash(hash);
      setFeedback('Approval sent. Waiting for confirmation...');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Approval failed.');
    }
  };

  const handleDeposit = async () => {
    if (!vaultAddress || depositAmountBase === 0n || !address) return;
    try {
      setFeedback('Submitting deposit...');
      const hash = await writeContractAsync({
        address: vaultAddress,
        abi: vaultAbi,
        functionName: 'deposit',
        args: [depositAmountBase, address],
      });
      setDepositHash(hash);
      setFeedback('Deposit sent. Waiting for confirmation...');
      setDepositAmount('');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Deposit failed.');
    }
  };

  const handleWithdraw = async () => {
    if (!vaultAddress || withdrawAmountBase === 0n || !address) return;
    try {
      setFeedback('Submitting withdrawal...');
      const hash = await writeContractAsync({
        address: vaultAddress,
        abi: vaultAbi,
        functionName: 'withdraw',
        args: [withdrawAmountBase, address, address],
      });
      setWithdrawHash(hash);
      setFeedback('Withdrawal sent. Waiting for confirmation...');
      setWithdrawAmount('');
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : 'Withdrawal failed.');
    }
  };

  return (
    <section className="mt-12 grid gap-8 lg:grid-cols-2">
      <div className="rounded-3xl border border-white/10 bg-surface p-8 shadow-2xl shadow-black/30 backdrop-blur">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl text-white">Deposit {stableTicker}</h2>
          <span className="text-sm text-white/60">
            Wallet: {formatUsd(usdcBalance, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </span>
        </div>
        <div className="mt-6 space-y-6">
          <div>
            <label className="text-sm font-semibold text-white/70">Amount</label>
            <div className="mt-2 flex items-center gap-3 rounded-2xl bg-white/5 px-4 py-3 shadow-inner shadow-black/40 focus-within:ring-2 focus-within:ring-accent/60">
              <input
                type="number"
                min="0"
                placeholder="0.00"
                value={depositAmount}
                onChange={(event) => setDepositAmount(event.target.value)}
                className="w-full bg-transparent text-2xl font-semibold text-white outline-none"
              />
              <span className="text-base font-semibold text-white/60">{stableTicker}</span>
            </div>
            {lacksBalance && (
              <p className="mt-2 text-sm text-amber-300/80">Not enough balance.</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3 text-sm text-white/70">
            <span>{shareTicker} you will mint</span>
            <span className="font-semibold text-white">
              {formatToken(estimatedDepositShares, shareDecimals, { maximumFractionDigits: 4, minimumFractionDigits: 2 })} {shareTicker}
            </span>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row">
            {needsApproval ? (
              <button
                type="button"
                onClick={handleApprove}
                className="flex-1 rounded-2xl border border-accent/30 bg-accent/20 px-6 py-3 font-semibold text-accent transition hover:bg-accent/30"
                disabled={disabledDeposit || depositAmountBase === 0n}
              >
                {isPending || approvalLoading ? 'Approving...' : `Approve ${stableTicker}`}
              </button>
            ) : (
              <button
                type="button"
                onClick={handleDeposit}
                className="flex-1 rounded-2xl bg-gradient-to-r from-accent to-accentSoft px-6 py-3 font-semibold text-white shadow-glow transition hover:opacity-90"
                disabled={disabledDeposit}
              >
                {isPending || depositLoading ? 'Depositing...' : 'Deposit'}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-surface p-8 shadow-2xl shadow-black/30 backdrop-blur">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-xl text-white">Withdraw {stableTicker}</h2>
          <span className="text-sm text-white/60">
            Vault value: {formatUsd(userShareValue, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
          </span>
        </div>
        <div className="mt-6 space-y-6">
          <div>
            <label className="text-sm font-semibold text-white/70">Amount</label>
            <div className="mt-2 flex items-center gap-3 rounded-2xl bg-white/5 px-4 py-3 shadow-inner shadow-black/40 focus-within:ring-2 focus-within:ring-accent/60">
              <input
                type="number"
                min="0"
                placeholder="0.00"
                value={withdrawAmount}
                onChange={(event) => setWithdrawAmount(event.target.value)}
                className="w-full bg-transparent text-2xl font-semibold text-white outline-none"
              />
              <span className="text-base font-semibold text-white/60">{stableTicker}</span>
            </div>
            {exceedsShareValue && (
              <p className="mt-2 text-sm text-amber-300/80">Exceeds your vault balance.</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-2xl bg-white/5 px-4 py-3 text-sm text-white/70">
            <span>{shareTicker} you will burn</span>
            <span className="font-semibold text-white">
              {formatToken(estimatedWithdrawShares, shareDecimals, { maximumFractionDigits: 4, minimumFractionDigits: 2 })} {shareTicker}
            </span>
          </div>

          <button
            type="button"
            onClick={handleWithdraw}
            className="w-full rounded-2xl border border-rose-500/50 bg-rose-500/20 px-6 py-3 font-semibold text-rose-100 transition hover:bg-rose-500/30"
            disabled={disabledWithdraw}
          >
            {isPending || withdrawLoading ? 'Withdrawing...' : 'Withdraw'}
          </button>
        </div>
      </div>

      {feedback && (
        <div className="lg:col-span-2">
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/80">
            {feedback}
          </div>
        </div>
      )}
    </section>
  );
};
