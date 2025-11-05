import { useState, useEffect } from 'react';
import { useAccount, useWriteContract, useWaitForTransactionReceipt } from 'wagmi';
import { parseUnits } from 'viem';
import { mavpVaultAbi } from '@/abi/mavpVault';
import { erc20Abi } from '@/abi/erc20';
import { formatUsd } from '@/lib/format';
import { TransactionStatusIndicator } from './TransactionStatusIndicator';
import { TransactionProgressBar } from './TransactionProgressBar';
import { useTransactionStatus } from '@/hooks/useTransactionStatus';
import type { TransactionType } from '@/hooks/useTransactionStatus';

type MAVPActionPanelProps = {
  mavpVaultAddress?: string;
  usdcAddress?: string;
  usdcDecimals: number;
  shareDecimals: number;
  userShareValue?: bigint;
  usdcBalance?: bigint;
  allowance?: bigint;
  usdcSymbol: string;
  vaultSymbol: string;
  refetchAll?: () => void;
  onTransactionStatusChange?: (status: 'idle' | 'pending' | 'success' | 'failed', type: TransactionType | null) => void;
};

export const MAVPActionPanel = ({
  mavpVaultAddress,
  usdcAddress,
  usdcDecimals,
  shareDecimals,
  userShareValue,
  usdcBalance,
  allowance,
  usdcSymbol,
  vaultSymbol,
  refetchAll,
  onTransactionStatusChange,
}: MAVPActionPanelProps) => {
  const { address } = useAccount();
  const [depositAmount, setDepositAmount] = useState('');
  const [redeemAmount, setRedeemAmount] = useState('');
  const [approveAmount, setApproveAmount] = useState('');
  const [activeTab, setActiveTab] = useState<'deposit' | 'redeem' | 'approve'>('deposit');
  const { transaction, startTransaction, completeTransaction, failTransaction } = useTransactionStatus();

  const { writeContract: writeDeposit, data: depositHash } = useWriteContract();
  const { writeContract: writeRedeem, data: redeemHash } = useWriteContract();
  const { writeContract: writeApprove, data: approveHash } = useWriteContract();

  const { isLoading: depositPending, isSuccess: depositSuccess, isError: depositError } = useWaitForTransactionReceipt({ hash: depositHash });
  const { isLoading: redeemPending, isSuccess: redeemSuccess, isError: redeemError } = useWaitForTransactionReceipt({ hash: redeemHash });
  const { isLoading: approvePending, isSuccess: approveSuccess, isError: approveError } = useWaitForTransactionReceipt({ hash: approveHash });

  // Track transaction status and notify parent
  useEffect(() => {
    if (depositPending) {
      startTransaction('deposit', depositHash);
      onTransactionStatusChange?.('pending', 'deposit');
    }
  }, [depositPending, depositHash, onTransactionStatusChange]);

  useEffect(() => {
    if (redeemPending) {
      startTransaction('withdraw', redeemHash);
      onTransactionStatusChange?.('pending', 'withdraw');
    }
  }, [redeemPending, redeemHash, onTransactionStatusChange]);

  useEffect(() => {
    if (approvePending) {
      startTransaction('approve', approveHash);
      onTransactionStatusChange?.('pending', 'approve');
    }
  }, [approvePending, approveHash, onTransactionStatusChange]);

  // Handle transaction success
  useEffect(() => {
    if (depositSuccess) {
      completeTransaction();
      onTransactionStatusChange?.('success', 'deposit');
      refetchAll?.();
      setDepositAmount('');
    }
  }, [depositSuccess, refetchAll, onTransactionStatusChange]);

  useEffect(() => {
    if (redeemSuccess) {
      completeTransaction();
      onTransactionStatusChange?.('success', 'withdraw');
      refetchAll?.();
      setRedeemAmount('');
    }
  }, [redeemSuccess, refetchAll, onTransactionStatusChange]);

  useEffect(() => {
    if (approveSuccess) {
      completeTransaction();
      onTransactionStatusChange?.('success', 'approve');
      refetchAll?.();
      setApproveAmount('');
    }
  }, [approveSuccess, refetchAll, onTransactionStatusChange]);

  // Handle transaction errors
  useEffect(() => {
    if (depositError) {
      failTransaction('Deposit transaction failed');
      onTransactionStatusChange?.('failed', 'deposit');
    }
  }, [depositError, onTransactionStatusChange]);

  useEffect(() => {
    if (redeemError) {
      failTransaction('Withdrawal transaction failed');
      onTransactionStatusChange?.('failed', 'withdraw');
    }
  }, [redeemError, onTransactionStatusChange]);

  useEffect(() => {
    if (approveError) {
      failTransaction('Approval transaction failed');
      onTransactionStatusChange?.('failed', 'approve');
    }
  }, [approveError, onTransactionStatusChange]);

  const handleDeposit = () => {
    console.log('MAVP Deposit Debug:', {
      mavpVaultAddress,
      depositAmount,
      address,
      usdcDecimals,
      canDeposit,
      needsApproval: needsApproval(depositAmount),
      allowance: allowance?.toString(),
    });

    if (!mavpVaultAddress || !depositAmount || !address) {
      console.log('MAVP Deposit: Missing required parameters');
      return;
    }

    const amount = parseUnits(depositAmount, usdcDecimals);
    console.log('MAVP Deposit: Calling deposit with amount:', amount.toString());

    writeDeposit({
      address: mavpVaultAddress as `0x${string}`,
      abi: mavpVaultAbi,
      functionName: 'deposit',
      args: [amount, address], // Pass user's address as receiver
      gas: 500000n, // Optimized: deposit only transfers USDC, no swaps (swaps done via rebalance)
    });
  };

  const handleRedeem = () => {
    console.log('MAVP Redeem Debug:', {
      mavpVaultAddress,
      redeemAmount,
      address,
      shareDecimals,
      canRedeem,
      userShareValue: userShareValue?.toString(),
    });

    if (!mavpVaultAddress || !redeemAmount || !address) {
      console.log('MAVP Redeem: Missing required parameters');
      return;
    }

    const shares = parseUnits(redeemAmount, shareDecimals);
    console.log('MAVP Redeem: Calling redeem with shares:', shares.toString());

    writeRedeem({
      address: mavpVaultAddress as `0x${string}`,
      abi: mavpVaultAbi,
      functionName: 'redeem',
      args: [shares, address, address], // Pass user's address as both receiver and owner
      gas: 3000000n, // Redeem may still need to swap assets back to USDC
    });
  };

  const handleApprove = () => {
    console.log('MAVP Approve Debug:', {
      usdcAddress,
      mavpVaultAddress,
      approveAmount,
      usdcDecimals,
    });
    
    if (!usdcAddress || !mavpVaultAddress || !approveAmount) {
      console.log('MAVP Approve: Missing required parameters');
      return;
    }
    
    const amount = parseUnits(approveAmount, usdcDecimals);
    console.log('MAVP Approve: Calling approve with amount:', amount.toString());
    
    writeApprove({
      address: usdcAddress as `0x${string}`,
      abi: erc20Abi,
      functionName: 'approve',
      args: [mavpVaultAddress as `0x${string}`, amount],
    });
  };

  const needsApproval = (amount: string) => {
    if (!amount) return false;
    if (!allowance) return true; // No allowance means approval needed
    try {
      const requiredAmount = parseUnits(amount, usdcDecimals);
      return allowance < requiredAmount;
    } catch {
      return true; // If parsing fails, assume approval needed
    }
  };

  const canDeposit = depositAmount && usdcBalance && !needsApproval(depositAmount) && address;
  const canRedeem = redeemAmount && userShareValue && userShareValue > 0n && address;

  return (
    <section className="mt-12 rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl shadow-indigo-500/10 backdrop-blur">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="font-display text-xl text-white">Portfolio Actions</h2>
          <p className="text-sm text-white/60">Deposit {usdcSymbol} to get diversified {vaultSymbol} portfolio shares.</p>
        </div>
      </div>

      <div className="mt-6 flex gap-2 rounded-2xl bg-white/5 p-1">
        <button
          onClick={() => setActiveTab('deposit')}
          className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'deposit'
              ? 'bg-accent text-white'
              : 'text-white/70 hover:text-white'
          }`}
        >
          Deposit
        </button>
        <button
          onClick={() => setActiveTab('redeem')}
          className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'redeem'
              ? 'bg-accent text-white'
              : 'text-white/70 hover:text-white'
          }`}
        >
          Redeem
        </button>
        <button
          onClick={() => setActiveTab('approve')}
          className={`flex-1 rounded-xl px-4 py-2 text-sm font-medium transition-colors ${
            activeTab === 'approve'
              ? 'bg-accent text-white'
              : 'text-white/70 hover:text-white'
          }`}
        >
          Approve
        </button>
      </div>

      <div className="mt-6">
        {activeTab === 'deposit' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/80">
                Deposit Amount ({usdcSymbol})
              </label>
              <input
                type="number"
                value={depositAmount}
                onChange={(e) => setDepositAmount(e.target.value)}
                placeholder="0.00"
                className="mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-4 py-3 text-white placeholder-white/50 focus:border-accent focus:outline-none"
              />
              <p className="mt-1 text-xs text-white/50">
                Balance: {formatUsd(usdcBalance, usdcDecimals, { maximumFractionDigits: 2 })}
              </p>
            </div>
            
            {/* Transaction Status Indicator */}
            {transaction.type === 'deposit' && transaction.status !== 'idle' && (
              <TransactionStatusIndicator
                status={transaction.status}
                hash={depositHash}
                message={
                  transaction.status === 'pending' ? 'Waiting for blockchain confirmation...' :
                  transaction.status === 'success' ? 'Deposit confirmed! Your balance will update shortly.' :
                  'Deposit failed. Please try again.'
                }
              />
            )}

            {/* Multi-step progress for approval + deposit flow */}
            {needsApproval(depositAmount) && depositAmount && (
              <TransactionProgressBar
                steps={[
                  { label: 'Approve', status: approveSuccess ? 'completed' : approvePending ? 'active' : 'pending' },
                  { label: 'Deposit', status: 'pending' },
                  { label: 'Confirm', status: 'pending' },
                ]}
              />
            )}

            {!address ? (
              <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4">
                <p className="text-sm text-red-200">
                  Please connect your wallet to deposit.
                </p>
              </div>
            ) : needsApproval(depositAmount) ? (
              <div className="rounded-xl bg-amber-500/10 border border-amber-500/30 p-4">
                <p className="text-sm text-amber-200">
                  You need to approve {usdcSymbol} spending first. Switch to the Approve tab.
                </p>
              </div>
            ) : (
              <>
                <button
                  onClick={handleDeposit}
                  disabled={!canDeposit || depositPending}
                  className="w-full rounded-xl bg-accent px-6 py-3 font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {depositPending && (
                    <svg className="h-5 w-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                  )}
                  {depositPending ? 'Depositing...' : `Deposit ${usdcSymbol}`}
                </button>
              </>
            )}
          </div>
        )}

        {activeTab === 'redeem' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/80">
                Redeem Amount ({vaultSymbol} shares)
              </label>
              <input
                type="number"
                value={redeemAmount}
                onChange={(e) => setRedeemAmount(e.target.value)}
                placeholder="0.00"
                className="mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-4 py-3 text-white placeholder-white/50 focus:border-accent focus:outline-none"
              />
              <p className="mt-1 text-xs text-white/50">
                Portfolio Value: {formatUsd(userShareValue, usdcDecimals, { maximumFractionDigits: 2 })}
              </p>
            </div>
            
            {/* Transaction Status Indicator for Redeem */}
            {transaction.type === 'withdraw' && transaction.status !== 'idle' && (
              <TransactionStatusIndicator
                status={transaction.status}
                hash={redeemHash}
                message={
                  transaction.status === 'pending' ? 'Waiting for blockchain confirmation...' :
                  transaction.status === 'success' ? 'Withdrawal confirmed! Your USDC will arrive shortly.' :
                  'Withdrawal failed. Please try again.'
                }
              />
            )}

            {!address ? (
              <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4">
                <p className="text-sm text-red-200">
                  Please connect your wallet to redeem.
                </p>
              </div>
            ) : (
              <button
                onClick={handleRedeem}
                disabled={!canRedeem || redeemPending}
                className="w-full rounded-xl bg-accent px-6 py-3 font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {redeemPending && (
                  <svg className="h-5 w-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                  </svg>
                )}
                {redeemPending ? 'Redeeming...' : `Redeem ${vaultSymbol}`}
              </button>
            )}
          </div>
        )}

        {activeTab === 'approve' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-white/80">
                Approve Amount ({usdcSymbol})
              </label>
              <input
                type="number"
                value={approveAmount}
                onChange={(e) => setApproveAmount(e.target.value)}
                placeholder="0.00"
                className="mt-1 w-full rounded-xl border border-white/20 bg-white/5 px-4 py-3 text-white placeholder-white/50 focus:border-accent focus:outline-none"
              />
              <p className="mt-1 text-xs text-white/50">
                Current Allowance: {formatUsd(allowance, usdcDecimals, { maximumFractionDigits: 2 })}
              </p>
            </div>
            
            {/* Transaction Status Indicator for Approve */}
            {transaction.type === 'approve' && transaction.status !== 'idle' && (
              <TransactionStatusIndicator
                status={transaction.status}
                hash={approveHash}
                message={
                  transaction.status === 'pending' ? 'Waiting for blockchain confirmation...' :
                  transaction.status === 'success' ? 'Approval confirmed! You can now deposit.' :
                  'Approval failed. Please try again.'
                }
              />
            )}

            <button
              onClick={handleApprove}
              disabled={!approveAmount || approvePending}
              className="w-full rounded-xl bg-accent px-6 py-3 font-medium text-white transition-colors hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {approvePending && (
                <svg className="h-5 w-5 animate-spin" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
              )}
              {approvePending ? 'Approving...' : `Approve ${usdcSymbol}`}
            </button>
          </div>
        )}
      </div>
    </section>
  );
};
