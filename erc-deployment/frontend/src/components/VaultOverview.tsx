import { formatToken, formatUsd, formatPercent } from '@/lib/format';
import { useChainlinkPrices } from '@/hooks/useChainlinkPrices';
import { usePriceTimestamp } from '@/hooks/usePriceTimestamp';

type VaultOverviewProps = {
  totalAssets?: bigint;
  totalSupply?: bigint;
  usdcHeld?: bigint;
  wethHeld?: bigint;
  actualUsdc?: bigint;
  actualWeth?: bigint;
  allocation?: { usdc: number; weth: number } | undefined;
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

export const VaultOverview = ({
  totalAssets,
  totalSupply,
  usdcHeld,
  wethHeld,
  actualUsdc,
  actualWeth,
  allocation,
  shareDecimals,
  usdcDecimals,
  vaultName,
  vaultSymbol,
}: VaultOverviewProps) => {
  const { calculateVaultSharePrice, ethPrice, usdcPrice, wethUsdcPrice, isHealthy, isLoading, isFetching } = useChainlinkPrices();
  const { formatLastUpdated } = usePriceTimestamp(isFetching);
  const sharePrice = calculateVaultSharePrice(totalAssets, totalSupply, usdcDecimals, shareDecimals);

  return (
    <section className="mt-10 grid gap-6 lg:grid-cols-3">
      <div className="rounded-3xl border border-white/10 bg-white/10 p-6 shadow-2xl shadow-indigo-500/20 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-white/60">Vault TVL</p>
        <h3 className="mt-4 font-display text-3xl text-white">
          {formatUsd(totalAssets, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
        </h3>
        <p className="mt-3 text-sm text-white/60">
          {vaultName ?? 'Vault'} ({vaultSymbol ?? 'MAVC'}) currently manages assets in real time.
        </p>
      </div>

      <div className="rounded-3xl border border-white/10 bg-gradient-to-br from-accent/40 to-accentSoft/20 p-6 shadow-2xl shadow-accent/20 backdrop-blur">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-[0.2em] text-white/80">Vault Share Price (1 token)</p>
          <div className="flex items-center gap-1">
            <div className={`h-2 w-2 rounded-full ${isHealthy ? 'bg-green-400' : 'bg-amber-400'} ${isFetching ? 'animate-pulse' : ''}`} />
            <span className="text-xs text-white/60">
              {isLoading ? 'Loading...' : isFetching ? 'Updating...' : isHealthy ? 'Chainlink' : 'Fallback'}
            </span>
          </div>
        </div>
        <h3 className="mt-4 font-display text-3xl text-white">{formatSharePrice(sharePrice)}</h3>
        <p className="mt-3 text-sm text-white/70">
          1 {vaultSymbol ?? 'MAVC'} = (0.5×USDC) + (0.5×WETH/{formatSharePrice(wethUsdcPrice || 1).replace('$', '')}) = {formatSharePrice(sharePrice)}
        </p>
        {isHealthy && (
          <div className="mt-3 flex gap-4 text-xs text-white/60">
            <span>ETH: ${ethPrice?.toFixed(2)}</span>
            <span>USDC: ${usdcPrice?.toFixed(4)}</span>
          </div>
        )}
        <div className="mt-2 text-xs text-white/40">
          {formatLastUpdated()}
        </div>
      </div>

      <div className="rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/30 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.2em] text-white/60">Allocation</p>
        <div className="mt-4 space-y-3">
          <div className="flex items-center justify-between text-sm text-white/80">
            <span>USDC</span>
            <span className="font-semibold text-white">{formatPercent(allocation?.usdc)}</span>
          </div>
          <div className="h-2 rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${allocation?.usdc ?? 50}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-sm text-white/80">
            <span>WETH</span>
            <span className="font-semibold text-white">{formatPercent(allocation?.weth)}</span>
          </div>
        </div>
      </div>

      <div className="lg:col-span-3 grid gap-6 md:grid-cols-2">
        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h4 className="font-display text-lg text-white">Internal Accounting</h4>
          <p className="mt-2 text-sm text-white/60">
            How the vault tracks value internally for its 50/50 strategy.
          </p>
          <dl className="mt-6 space-y-4 text-sm text-white/70">
            <div className="flex items-center justify-between">
              <dt>USDC held (book value)</dt>
              <dd className="font-semibold text-white">
                {formatUsd(usdcHeld, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>WETH value (in USDC terms)</dt>
              <dd className="font-semibold text-white">
                {formatUsd(wethHeld, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
              </dd>
            </div>
          </dl>
        </div>

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6 backdrop-blur">
          <h4 className="font-display text-lg text-white">On-Chain Balances</h4>
          <p className="mt-2 text-sm text-white/60">
            Actual token balances available in the vault wallet.
          </p>
          <dl className="mt-6 space-y-4 text-sm text-white/70">
            <div className="flex items-center justify-between">
              <dt>USDC wallet balance</dt>
              <dd className="font-semibold text-white">
                {formatUsd(actualUsdc, usdcDecimals, { maximumFractionDigits: 2, minimumFractionDigits: 2 })}
              </dd>
            </div>
            <div className="flex items-center justify-between">
              <dt>WETH wallet balance</dt>
              <dd className="font-semibold text-white">
                {formatToken(actualWeth ?? 0n, 18, { maximumFractionDigits: 4, minimumFractionDigits: 4 })} WETH
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </section>
  );
};
