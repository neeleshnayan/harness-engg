import { useMemo } from 'react';
import { formatUsd, formatPercent } from '@/lib/format';
import { useChainlinkPrices } from '@/hooks/useChainlinkPrices';
import { usePriceTimestamp } from '@/hooks/usePriceTimestamp';

type MAVPVaultOverviewProps = {
  totalAssets?: bigint;
  totalSupply?: bigint;
  usdcHeld?: bigint;
  assetCount?: number;
  assets?: Array<{
    index: number;
    token: string;
    allocationBps: bigint;
    tokenBalance: bigint;
    usdcBookValue: bigint;
  }> | null;
  allocation?: Array<{
    token: string;
    allocationBps: number;
    percentage: number;
  }>;
  shareDecimals: number;
  usdcDecimals: number;
  vaultName?: string;
  vaultSymbol?: string;
};

const formatSharePrice = (price: number) => {
  if (!Number.isFinite(price)) return '$0.0000';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(price);
};

export const MAVPVaultOverview = ({
  totalAssets,
  totalSupply,
  usdcHeld,
  assetCount,
  assets,
  allocation,
  shareDecimals,
  usdcDecimals,
  vaultName,
  vaultSymbol,
}: MAVPVaultOverviewProps) => {
  const { isHealthy, isLoading, isFetching } = useChainlinkPrices();
  const { formatLastUpdated } = usePriceTimestamp(isFetching);
  
  // For MAVP, we use a simple calculation since it's a diversified 5-token portfolio
  const sharePrice = useMemo(() => {
    if (totalAssets && totalSupply && totalSupply > 0n) {
      const assets = Number(totalAssets) / 10 ** usdcDecimals;
      const shares = Number(totalSupply) / 10 ** shareDecimals;
      if (shares > 0) {
        return assets / shares;
      }
    }
    return 1; // Default price for empty vault
  }, [totalAssets, totalSupply, usdcDecimals, shareDecimals]);

  // Get token symbols for display - Sepolia testnet addresses
  const getTokenSymbol = (tokenAddress: string) => {
    const knownTokens: Record<string, string> = {
      // Sepolia testnet token addresses (from TestMultiAssetVaultPortfolio.s.sol)
      '0x1c7d4b196cb0c7b01d743fbc6116a902379c7238': 'USDC', // USDC
      '0xfff9976782d46cc05630d1f6ebab18b2324d6b14': 'WETH', // WETH
      '0x29f2d40b0605204364af54ec677bd022da425d03': 'WBTC', // WBTC
      '0xaa8e23fb1079ea71e0a56f48a2aa51851d8433d0': 'USDT', // USDT
      '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984': 'UNI', // UNI token
      '0x824cb8fc742f8d3300d29f16ca8bee94471169f5': 'SOL (OLD)', // Old SOL - needs contract redeploy
      '0x779877a7b0d9e8603169ddbd7836e478b4624789': 'LINK', // Chainlink
    };
    return knownTokens[tokenAddress.toLowerCase()] || `${tokenAddress.slice(0, 6)}...${tokenAddress.slice(-4)}`;
  };

  return (
    <section className="mt-10 grid gap-6 lg:grid-cols-3">
      <div className="rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl shadow-indigo-500/20 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-white/60">Portfolio TVL</p>
        <h3 className="mt-4 font-display text-3xl text-white">
          {formatUsd(totalAssets, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
        </h3>
        <p className="mt-3 text-sm text-white/60">
          {vaultName ?? 'MAVP'} ({vaultSymbol ?? 'MAVP'}) manages a diversified 5-token portfolio.
        </p>
      </div>

      <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-accent/40 to-accentSoft/20 p-6 shadow-2xl shadow-accent/20 backdrop-blur">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-[0.2em] text-white/80">Share Price (1 token)</p>
          <div className="flex items-center gap-1">
            <div className={`h-2 w-2 rounded-full ${isHealthy ? 'bg-green-400' : 'bg-amber-400'} ${isFetching ? 'animate-pulse' : ''}`} />
            <span className="text-xs text-white/60">
              {isLoading ? 'Loading...' : isFetching ? 'Updating...' : 'Portfolio'}
            </span>
          </div>
        </div>
        <h3 className="mt-4 font-display text-3xl text-white">{formatSharePrice(sharePrice)}</h3>
        <p className="mt-3 text-sm text-white/70">
          1 {vaultSymbol ?? 'MAVP'} = Diversified 5-token basket = {formatSharePrice(sharePrice)}
        </p>
        <div className="mt-3 text-xs text-white/60">
          {assetCount} assets • 20% allocation each
        </div>
        <div className="mt-2 text-xs text-white/40">
          {formatLastUpdated()}
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/30 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-white/60">Portfolio Allocation</p>
        <div className="mt-4 space-y-3">
          {allocation && allocation.length > 0 ? (
            allocation.slice(0, 6).map((item) => (
              <div key={item.token} className="flex items-center justify-between text-sm">
                <span className="text-white/80">
                  {getTokenSymbol(item.token)}
                </span>
                <span className="font-semibold text-white">{formatPercent(item.percentage)}</span>
              </div>
            ))
          ) : (
            <div className="text-center text-white/50 text-sm">
              No allocation data available
            </div>
          )}
        </div>
      </div>

      <div className="lg:col-span-3 grid gap-6 md:grid-cols-2">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h4 className="font-display text-lg text-white">Internal Accounting</h4>
          <p className="mt-2 text-sm text-white/60">
            How the portfolio tracks value internally for its diversified strategy.
          </p>
          <dl className="mt-6 space-y-4 text-sm text-white/70">
            <div className="flex items-center justify-between">
              <dt>USDC held (liquid)</dt>
              <dd className="font-semibold text-white">
                {formatUsd(usdcHeld, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>Assets in portfolio</dt>
              <dd className="font-semibold text-white">
                {assetCount} tokens
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>Target allocation</dt>
              <dd className="font-semibold text-white">
                20% each asset
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h4 className="font-display text-lg text-white">Portfolio Assets</h4>
          <p className="mt-2 text-sm text-white/60">
            Individual token balances and their USDC book values.
          </p>
          <div className="mt-6 space-y-3 text-sm text-white/70">
            {assets && assets.length > 0 ? (
              assets.slice(0, 5).map((asset) => (
                <div key={asset.index} className="flex items-center justify-between">
                  <dt>{getTokenSymbol(asset.token)}</dt>
                  <dd className="font-semibold text-white">
                    {formatUsd(asset.usdcBookValue, usdcDecimals, { maximumFractionDigits: 2 })}
                  </dd>
                </div>
              ))
            ) : (
              <div className="text-center text-white/50">
                No assets loaded
              </div>
            )}
            {assets && assets.length > 5 && (
              <div className="text-center text-xs text-white/50">
                +{assets.length - 5} more assets
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
};
