import { useState } from 'react';
import { ConnectButton } from '@/components/ConnectButton';
import { MAVPVaultOverview } from '@/components/MAVPVaultOverview';
import { MAVPActionPanel } from '@/components/MAVPActionPanel';
import { UserPortfolio } from '@/components/UserPortfolio';
import { SubgraphInsights } from '@/components/SubgraphInsights';
import { useMAVPData } from '@/hooks/useMAVPData';
import { isMAVPEnvReady } from '@/config/env';
import type { TransactionStatus } from '@/hooks/useTransactionStatus';

export const MAVPPage = () => {
  const { vault, usdc, user, mavpVaultAddress, usdcAddress, states, refetchAll } = useMAVPData();
  const [transactionStatus, setTransactionStatus] = useState<TransactionStatus>('idle');
  const [transactionType, setTransactionType] = useState<'deposit' | 'withdraw' | 'approve' | null>(null);

  const handleTransactionStatusChange = (status: TransactionStatus, type: 'deposit' | 'withdraw' | 'approve' | null) => {
    setTransactionStatus(status);
    setTransactionType(type);
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,#1d1b4b_0%,#05070f_60%,#010209_100%)] text-foreground">
      <div className="pointer-events-none absolute -left-32 top-20 h-72 w-72 rounded-full bg-accent/25 blur-3xl sm:h-96 sm:w-96" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-96 w-96 translate-x-1/3 rounded-full bg-accentSoft/20 blur-3xl" />

      <main className="relative z-10 mx-auto max-w-6xl px-6 py-12">
        <header className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-white/50">MAVP Portfolio Vault</p>
            <h1 className="mt-3 font-display text-4xl text-white sm:text-5xl">
              Multi-Asset Vault Portfolio
            </h1>
            <p className="mt-4 max-w-xl text-sm text-white/70">
              Connect your wallet, deposit USDC, and receive MAVP shares. The vault automatically maintains a
              balanced 5-token diversified portfolio using automated rebalancing strategies.
            </p>
          </div>
          <ConnectButton />
        </header>

        {!isMAVPEnvReady() && (
          <div className="mt-8 rounded-3xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
            Missing environment configuration. Set VITE_MAVP_VAULT_ADDRESS and token addresses in your .env file.
          </div>
        )}

        <MAVPVaultOverview
          totalAssets={vault.totalAssets}
          totalSupply={vault.totalSupply}
          usdcHeld={vault.usdcHeld}
          assetCount={vault.assetCount}
          assets={vault.assets}
          allocation={vault.allocation}
          shareDecimals={vault.shareDecimals}
          usdcDecimals={usdc.decimals}
          vaultName={vault.name}
          vaultSymbol={vault.symbol}
        />

        <UserPortfolio
          shares={user.shares}
          shareValue={user.shareValue}
          usdcBalance={usdc.balance}
          allowance={usdc.allowance}
          shareDecimals={vault.shareDecimals}
          usdcDecimals={usdc.decimals}
          vaultSymbol={vault.symbol}
          usdcSymbol={usdc.symbol}
          transactionStatus={transactionStatus}
          transactionType={transactionType}
        />

        <MAVPActionPanel
          mavpVaultAddress={mavpVaultAddress}
          usdcAddress={usdcAddress}
          usdcDecimals={usdc.decimals}
          shareDecimals={vault.shareDecimals}
          userShareValue={user.shareValue}
          usdcBalance={usdc.balance}
          allowance={usdc.allowance}
          usdcSymbol={usdc.symbol}
          vaultSymbol={vault.symbol ?? 'MAVP'}
          refetchAll={refetchAll}
          onTransactionStatusChange={handleTransactionStatusChange}
        />

        <SubgraphInsights />

        {states.vaultLoading && (
          <p className="mt-8 text-center text-sm text-white/50">Fetching live portfolio data...</p>
        )}
      </main>
    </div>
  );
};
