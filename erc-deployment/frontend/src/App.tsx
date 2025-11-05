import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { ConnectButton } from '@/components/ConnectButton';
import { VaultOverview } from '@/components/VaultOverview';
import { ActionPanel } from '@/components/ActionPanel';
import { SubgraphInsights } from '@/components/SubgraphInsights';
import { UserPortfolio } from '@/components/UserPortfolio';
import { MAVPPage } from '@/components/MAVPPage';
import { useVaultData } from '@/hooks/useVaultData';
import { isEnvReady } from '@/config/env';

const Navigation = () => {
  const location = useLocation();
  
  return (
    <nav className="mb-8 flex gap-2 rounded-2xl bg-white/5 p-1">
      <Link
        to="/"
        className={`flex-1 rounded-xl px-4 py-2 text-center text-sm font-medium transition-colors ${
          location.pathname === '/'
            ? 'bg-accent text-white'
            : 'text-white/70 hover:text-white'
        }`}
      >
        MAVC Vault (50/50)
      </Link>
      <Link
        to="/mavp"
        className={`flex-1 rounded-xl px-4 py-2 text-center text-sm font-medium transition-colors ${
          location.pathname === '/mavp'
            ? 'bg-accent text-white'
            : 'text-white/70 hover:text-white'
        }`}
      >
        MAVP Portfolio (5-Token)
      </Link>
    </nav>
  );
};

const MAVCVaultPage = () => {
  const { vault, usdc, user, vaultAddress, usdcAddress, states, refetchAll } = useVaultData();

  return (
    <>
      <header className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-white/50">MAVC Vault Control Center</p>
          <h1 className="mt-3 font-display text-4xl text-white sm:text-5xl">
            50/50 USDC {"<->"} WETH Yield Vault
          </h1>
          <p className="mt-4 max-w-xl text-sm text-white/70">
            Connect your wallet, deposit USDC, and receive MAVC shares. The vault automatically maintains a
            balanced USDC/WETH position using the on-chain strategy defined in the smart contracts.
          </p>
        </div>
        <ConnectButton />
      </header>

      {!isEnvReady() && (
        <div className="mt-8 rounded-3xl border border-amber-500/30 bg-amber-500/10 px-6 py-5 text-amber-100">
          Missing environment configuration. Set VITE_VAULT_ADDRESS and token addresses in your .env file.
        </div>
      )}

      <VaultOverview
        totalAssets={vault.totalAssets}
        totalSupply={vault.totalSupply}
        usdcHeld={vault.usdcHeld}
        wethHeld={vault.wethHeld}
        actualUsdc={vault.actual.usdc}
        actualWeth={vault.actual.weth}
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
      />

      <ActionPanel
        vaultAddress={vaultAddress}
        usdcAddress={usdcAddress}
        usdcDecimals={usdc.decimals}
        shareDecimals={vault.shareDecimals}
        totalAssets={vault.totalAssets}
        totalSupply={vault.totalSupply}
        userShareValue={user.shareValue}
        usdcBalance={usdc.balance}
        allowance={usdc.allowance}
        usdcSymbol={usdc.symbol}
        vaultSymbol={vault.symbol}
        refetchAll={refetchAll}
      />

      <SubgraphInsights />

      {states.vaultLoading && (
        <p className="mt-8 text-center text-sm text-white/50">Fetching live vault data...</p>
      )}
    </>
  );
};

function App() {
  return (
    <Router>
      <div className="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,#1d1b4b_0%,#05070f_60%,#010209_100%)] text-foreground">
        <div className="pointer-events-none absolute -left-32 top-20 h-72 w-72 rounded-full bg-accent/25 blur-3xl sm:h-96 sm:w-96" />
        <div className="pointer-events-none absolute bottom-0 right-0 h-96 w-96 translate-x-1/3 rounded-full bg-accentSoft/20 blur-3xl" />

        <main className="relative z-10 mx-auto max-w-6xl px-6 py-12">
          <Navigation />
          
          <Routes>
            <Route path="/" element={<MAVCVaultPage />} />
            <Route path="/mavp" element={<MAVPPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;






