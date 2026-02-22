import React, { useEffect, useState, useRef, useImperativeHandle, forwardRef, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import TransactionHistory, { TransactionHistoryRef } from "@/components/wallet/TransactionHistory";
import ActiveTransactions from "@/components/wallet/ActiveTransactions";
import SupportedAssetsBalances from "@/components/wallet/SupportedAssetsBalances";
import { FaShieldAlt } from "react-icons/fa";
import { useRates, CURRENCY_SYMBOLS, PriceDirection } from "@/providers/RatesProvider";
import { Triangle, ChevronDown, Wallet } from "lucide-react";

// Dynamically import modals to reduce initial bundle size
const BuyUSDCModal = dynamic(() => import("@/components/wallet/BuyUSDCModal"), {
  loading: () => null,
  ssr: false,
});

const SwapModal = dynamic(() => import("@/components/wallet/SwapModal"), {
  loading: () => null,
  ssr: false,
});

export interface BalanceCardRef {
  /** Switch to Transaction History tab and refresh */
  showTransactionHistory: () => void;
}

interface BalanceCardProps {
  balance: any;
  error: string | null;
  accountData: any;
  showTransactions: boolean;
  setShowTransactions: (show: boolean) => void;
  className?: string;
  transactionHistoryRefresh?: boolean;
  kycStatus?: string | null;
  onKycClick?: () => void;
  onRefreshKyc?: () => void;
  onCheckKycStatus?: () => void;
  kycChecking?: boolean;
  kycMessage?: string | null;
  onBuyClick?: () => void;
  onSkipKyc?: () => void;
  balanceLoading?: boolean;
  balanceCardRefresh?: boolean;
  balanceRefreshing?: boolean;
  balanceFlickering?: boolean;
  onTransactionsComplete?: () => void;
  /** Pre-fetched transactions from background bootstrap — skips TransactionHistory's initial fetch. */
  initialTransactions?: {
    transactions: any[];
    count: number;
    has_more: boolean;
  };
  /** WebSocket connection status from WalletPageBase — used to suppress ActiveTransactions polling when WS is live. */
  wsConnectionStatus?: 'connecting' | 'connected' | 'disconnected' | 'error';
  /** Incremented by WalletPageBase on balance_update (post-subgraph indexing).
   * Directly triggers TransactionHistory re-fetch when new data is available. */
  txHistoryForceRefresh?: number;
}

const WALLET_ICON = (
  <div className="rounded-full p-1 flex items-center justify-center" style={{ width: '36px', height: '36px' }}>
    <img src="/wallet.svg" alt="Wallet" width="24" height="24" style={{ filter: 'brightness(0) invert(1)' }} />
  </div>
);

const DEFAULT_FIAT_DATA = [
  { code: "USD", symbol: "$" },
  { code: "EUR", symbol: "€" },
  { code: "GBP", symbol: "£" },
];

const BalanceCard = forwardRef<BalanceCardRef, BalanceCardProps>(({
  balance,
  error,
  accountData,
  showTransactions,
  setShowTransactions,
  className,
  transactionHistoryRefresh,
  kycStatus,
  onKycClick,
  onRefreshKyc,
  onCheckKycStatus,
  kycChecking = false,
  kycMessage,
  onBuyClick,
  onSkipKyc,
  balanceLoading = false,
  balanceCardRefresh = false,
  balanceRefreshing = false,
  balanceFlickering = false,
  onTransactionsComplete,
  initialTransactions,
  wsConnectionStatus,
  txHistoryForceRefresh,
}, ref) => {
  const [localRefreshing, setLocalRefreshing] = useState(false);
  const [isFlickering, setIsFlickering] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState('USD');
  const [activeSlide, setActiveSlide] = useState(1); // Start at balance (middle slide)
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchEndX, setTouchEndX] = useState<number | null>(null);
  const [touchStartY, setTouchStartY] = useState<number | null>(null);
  const [isScrolling, setIsScrolling] = useState(false);
  const [showDepositModal, setShowDepositModal] = useState(false);
  const [showSwapModal, setShowSwapModal] = useState(false);
  const [transactionHistoryRefreshKey, setTransactionHistoryRefreshKey] = useState(0);
  const [activeTransactionsRefreshKey, setActiveTransactionsRefreshKey] = useState(0);
  const transactionHistoryRef = useRef<TransactionHistoryRef | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);

  // 🚀 THE MAGIC - All rates from context!
  const {
    tokens,
    isLoading: ratesLoading,
    calculateBalanceInUSD,
    getOverallPriceChange,
    getTokenAddressToSymbol
  } = useRates();
  const balanceVersion = (balance as any)?._fetchedAt;

  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;

    // Check if touch started inside a modal/dialog
    // Radix UI Dialog uses [role="dialog"] and data attributes
    const isInModal = target.closest('[role="dialog"]') ||
      target.closest('[data-radix-portal]') ||
      target.closest('[data-state="open"]');

    if (isInModal) {
      return; // Ignore touches when modal is open
    }

    // Check if touch started inside the scroll container
    if (scrollContainerRef.current?.contains(target)) {
      setIsScrolling(true);
      return;
    }
    setTouchStartX(e.touches[0].clientX);
    setTouchStartY(e.touches[0].clientY);
    setIsScrolling(false);
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;

    // Check if touch is inside a modal/dialog
    const isInModal = target.closest('[role="dialog"]') ||
      target.closest('[data-radix-portal]') ||
      target.closest('[data-state="open"]');

    if (isInModal) {
      // Reset touch state if moved into modal
      setTouchStartX(null);
      setTouchEndX(null);
      setTouchStartY(null);
      setIsScrolling(false);
      return;
    }

    // If already determined to be scrolling, ignore
    if (isScrolling) return;

    if (touchStartX === null || touchStartY === null) return;

    const currentX = e.touches[0].clientX;
    const currentY = e.touches[0].clientY;
    const deltaX = Math.abs(currentX - touchStartX);
    const deltaY = Math.abs(currentY - touchStartY);

    // If vertical movement is greater than horizontal, it's a scroll
    if (deltaY > deltaX && deltaY > 10) {
      setIsScrolling(true);
      return;
    }

    setTouchEndX(currentX);
  };

  const handleTouchEnd = (e: React.TouchEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement;

    // Check if touch ended inside a modal/dialog
    const isInModal = target.closest('[role="dialog"]') ||
      target.closest('[data-radix-portal]') ||
      target.closest('[data-state="open"]');

    if (isInModal) {
      // Reset touch state if ended in modal
      setTouchStartX(null);
      setTouchEndX(null);
      setTouchStartY(null);
      setIsScrolling(false);
      return;
    }

    if (touchStartX === null || touchEndX === null || isScrolling) {
      setTouchStartX(null);
      setTouchEndX(null);
      setTouchStartY(null);
      setIsScrolling(false);
      return;
    }

    const delta = touchStartX - touchEndX;
    const threshold = 50;
    if (delta > threshold && activeSlide < 2) {
      setActiveSlide(activeSlide + 1);
    } else if (delta < -threshold && activeSlide > 0) {
      setActiveSlide(activeSlide - 1);
    }

    setTouchStartX(null);
    setTouchEndX(null);
    setTouchStartY(null);
    setIsScrolling(false);
  };

  const handleTransactionHistoryRefresh = useCallback(() => {
    setTransactionHistoryRefreshKey(prev => prev + 1);
    setActiveTransactionsRefreshKey(prev => prev + 1);
    if (transactionHistoryRef.current?.refresh) {
      transactionHistoryRef.current.refresh();
    }
  }, []);

  /**
   * Called when all active transactions complete.
   * Notifies parent to refresh balance with green box effect.
   */
  const handleAllTransactionsComplete = useCallback(() => {
    // Notify parent to refresh balance with blinking effect
    if (onTransactionsComplete) {
      onTransactionsComplete();
    }
    // Also refresh transaction history
    handleTransactionHistoryRefresh();
  }, [onTransactionsComplete, handleTransactionHistoryRefresh]);

  /**
   * Switch to Transaction History tab and refresh
   * Called when modals close after submitting a transaction
   */
  const showTransactionHistoryTab = useCallback(() => {
    setActiveSlide(0); // Switch to Transaction History tab
    handleTransactionHistoryRefresh();
  }, [handleTransactionHistoryRefresh]);

  const handleModalClose = useCallback((modalSetter: React.Dispatch<React.SetStateAction<boolean>>, autoClose?: boolean) => {
    modalSetter(false);
    // Only switch to Transaction History tab on auto-close (success), not on manual X button close
    if (autoClose) {
      showTransactionHistoryTab();
    }
  }, [showTransactionHistoryTab]);

  // Expose methods to parent via ref
  useImperativeHandle(ref, () => ({
    showTransactionHistory: showTransactionHistoryTab,
  }), [showTransactionHistoryTab]);

  const openDepositModal = () => {
    setShowDepositModal(true);
  };

  const openSwapModal = () => {
    setShowSwapModal(true);
  };


  const showKycSection = accountData?.username && !!kycStatus && kycStatus !== 'approved' && onKycClick;
  const showBalanceSection = accountData?.username; // Always show balance if username exists
  const isKycApproved = kycStatus === 'approved';

  // Handle balance card refresh from WebSocket
  useEffect(() => {
    if (balanceCardRefresh) {
      setLocalRefreshing(true);
      // Reset local refreshing state after a short delay to show the refresh animation
      const timer = setTimeout(() => {
        setLocalRefreshing(false);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [balanceCardRefresh]);

  // Sync active transactions refresh with transactionHistoryRefresh prop from parent
  useEffect(() => {
    if (transactionHistoryRefresh) {
      setActiveTransactionsRefreshKey(prev => prev + 1);
    }
  }, [transactionHistoryRefresh]);

  // On balance_update (post-subgraph): directly refresh TransactionHistory.
  // This bypasses the 3s ActiveTransactions drain chain, fetching new data
  // exactly when the subgraph confirms it's indexed.
  useEffect(() => {
    if (txHistoryForceRefresh && txHistoryForceRefresh > 0) {
      setTransactionHistoryRefreshKey(prev => prev + 1);
    }
  }, [txHistoryForceRefresh]);

  // Handle balance flickering when USDC is sent out
  useEffect(() => {
    if (balanceFlickering) {
      setIsFlickering(true);
    } else {
      setIsFlickering(false);
    }
  }, [balanceFlickering]);

  // Get price change info from context
  const priceChangeInfo = useMemo(() => {
    if (!balance) return null;
    const raw = getOverallPriceChange(balance.tokenBalances || []);
    // Treat tiny moves as neutral so users don't see noisy red/green flicker.
    if (Math.abs(raw.percentageChange) < 0.05) {
      return { ...raw, direction: 'same' as PriceDirection, percentageChange: 0 };
    }
    return raw;
  }, [balance, getOverallPriceChange]);

  // Calculate total balance - now uses context! 🎯
  // useMemo ensures this recalculates when balance or selectedCurrency changes
  const totalBalance = useMemo(() => {
    if (!balance || !Array.isArray(balance.tokenBalances) || balance.tokenBalances.length === 0) {
      return 0;
    }

    const totalInUSD = calculateBalanceInUSD(balance.tokenBalances);

    // Convert from USD to selected currency if needed
    if (selectedCurrency === 'USD') {
      return totalInUSD;
    }

    // Get conversion rate from USD to selected currency
    const kTokenSymbol = `k${selectedCurrency}`;
    const tokenInfo = tokens[kTokenSymbol];
    const rate = tokenInfo?.current_rate;

    if (rate && rate > 0) {
      // Rate is USD/Currency, so to convert USD to Currency: divide by rate
      return totalInUSD / rate;
    }

    // If rate not available, return USD value
    return totalInUSD;
  }, [balance, selectedCurrency, tokens, calculateBalanceInUSD]);

  const formattedTotalBalance = useMemo(() => {
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(totalBalance);
  }, [totalBalance]);

  // Get available currencies for dropdown - from context tokens! 🎉
  const kTokenSymbols = Object.keys(tokens).filter(s => s.startsWith('k'));
  const availableCurrencies = [
    'USD',
    ...kTokenSymbols.filter(s => s !== 'kUSD').map(s => s.replace(/^k/, ''))
  ];
  const currencySymbol = CURRENCY_SYMBOLS[selectedCurrency] || '$';

  return (
    <>
      <div
        className={`bg-no-repeat bg-cover bg-center backdrop-blur-3xl rounded-3xl p-0 shadow-2xl border mb-8 transition-all duration-300 overflow-hidden ${(balanceRefreshing || localRefreshing)
          ? 'ring-2 ring-green-500 ring-opacity-70 border-green-500/50 shadow-green-500/20'
          : 'border-white/10'
          } ${className || ''}`}
        style={{ backgroundImage: "url('/wallet-bg.svg')" }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div
          className="flex w-full transition-transform duration-300"
          style={{ transform: `translateX(-${activeSlide * 100}%)` }}
        >
          {/* Transaction History Tab */}
          <div className="w-full shrink-0 min-w-0 overflow-hidden pt-8 px-6 pb-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-white">Transactions</h3>
              <button
                onClick={handleTransactionHistoryRefresh}
                className="p-2 hover:opacity-70 transition-opacity duration-200 focus:outline-none"
                title="Refresh transaction history"
              >
                <img src="/refresh.svg" alt="Refresh" className="w-5 h-5" />
              </button>
            </div>
            {showBalanceSection && isKycApproved ? (
              <div
                ref={scrollContainerRef}
                style={{
                  overflowY: 'auto',
                  paddingRight: '4px',
                  WebkitOverflowScrolling: 'touch',
                  overscrollBehavior: 'contain'
                }}
                className="max-h-[260px] [&::-webkit-scrollbar]:w-1 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-white/40 [&::-webkit-scrollbar-thumb]:rounded-full hover:[&::-webkit-scrollbar-thumb]:bg-white/60"
                onWheel={(e) => {
                  e.stopPropagation();
                }}
              >
                {/* Active Transactions - Shows pending Circle transactions */}
                {/* Only poll when Transaction History tab is visible (activeSlide === 0) */}
                <ActiveTransactions
                  username={accountData.username}
                  className="mb-4"
                  onAllTransactionsComplete={handleAllTransactionsComplete}
                  refreshKey={activeTransactionsRefreshKey}
                  isVisible={activeSlide === 0}
                  isWebSocketConnected={wsConnectionStatus === 'connected'}
                />
                <TransactionHistory
                  ref={transactionHistoryRef}
                  username={accountData.username}
                  userWalletAddress={accountData.wallet_address}
                  refreshKey={transactionHistoryRefreshKey}
                  scrollRoot={scrollContainerRef}
                  initialData={initialTransactions}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center text-zinc-400 py-8">
                <p>Complete KYC to view transaction history</p>
              </div>
            )}
          </div>
          {/* Balance Tab */}
          <div className="w-full shrink-0 min-w-0 overflow-hidden px-8 pt-5 pb-3 flex flex-col" style={{ minHeight: '340px' }}>
            <div className="text-center mb-5">
              <div className="flex items-center justify-center gap-3">
                <Wallet className="w-8 h-8 text-zinc-300" />
                <h3 className="text-xl font-bold text-zinc-300 tracking-wide">Your Balance</h3>
              </div>
            </div>

            {/* <div className={`mt-4 pt-4 border-t border-zinc-700/50 ${className || ''}`}></div> */}

            {/* Show KYC banner if username is set but KYC not approved */}
            {showKycSection && (
              <div className="mb-6">
                <div className="bg-gradient-to-r from-teal-900/40 to-cyan-900/40 border border-teal-500/30 rounded-2xl p-6 mb-4">
                  <div className="flex items-center justify-center mb-4">
                    <FaShieldAlt className="text-3xl text-teal-400 mr-3" />
                    <h3 className="text-xl font-bold text-white">Complete KYC Verification</h3>
                  </div>
                  <p className="text-zinc-300 mb-4 text-center">
                    Complete your identity verification to unlock full wallet functionality and start sending payments securely.
                  </p>
                  <div className="flex flex-col sm:flex-row gap-3 justify-center">
                    <button
                      onClick={onKycClick}
                      className="bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-700 hover:to-cyan-700 text-white font-semibold py-3 px-8 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
                    >
                      <FaShieldAlt className="inline mr-2" />
                      Continue KYC
                    </button>
                    <button
                      onClick={() => {
                        if (onSkipKyc) {
                          onSkipKyc();
                        } else {
                          console.error('onSkipKyc function is not provided');
                        }
                      }}
                      className="bg-gradient-to-r from-gray-600 to-gray-700 hover:from-gray-700 hover:to-gray-800 text-white font-semibold py-3 px-8 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
                    >
                      Skip for Now
                    </button>

                  </div>
                  <p className="text-xs text-zinc-500 mt-3 text-center">
                    You can complete KYC later to unlock full functionality
                  </p>
                  {kycMessage && (
                    <div className={`mt-3 p-3 rounded-lg text-sm text-center ${kycMessage.includes('approved')
                      ? 'bg-green-900/30 text-green-400 border border-green-500/30'
                      : kycMessage.includes('error') || kycMessage.includes('Failed')
                        ? 'bg-red-900/30 text-red-400 border border-red-500/30'
                        : 'bg-teal-900/30 text-teal-400 border border-teal-500/30'
                      }`}>
                      {kycMessage}
                    </div>
                  )}
                </div>
              </div>
            )}



            {showBalanceSection && (
              <div className="flex flex-col items-center justify-center mb-4 relative z-10 flex-[6]">
                {/* Balance Display */}
                <div className={`relative transition-all duration-200 ${!isKycApproved ? 'blur-sm' : ''} ${isFlickering || balanceRefreshing || localRefreshing ? 'balance-flicker' : ''
                  }`}>
                  {balanceLoading || ratesLoading ? (
                    <div className="flex items-center justify-center h-16">
                      <div className="animate-spin rounded-full h-8 w-8 border-2 border-[hsl(var(--brand-accent))] border-t-transparent mr-3"></div>
                      <span className="text-xl text-zinc-400">Loading...</span>
                    </div>
                  ) : error ? (
                    <span className="text-red-400 text-xl font-semibold">{error}</span>
                  ) : (
                    <div className="relative group cursor-pointer flex items-baseline justify-center" aria-live="polite">
                      {/* Hidden Select Overlay */}
                      <select
                        value={selectedCurrency}
                        onChange={(e) => setSelectedCurrency(e.target.value)}
                        className="absolute inset-0 w-full h-full opacity-0 z-20 cursor-pointer"
                        aria-label="Select Currency"
                      >
                        {availableCurrencies.map((currency) => (
                          <option key={currency} value={currency} className="bg-zinc-800 text-white">
                            {currency} ({CURRENCY_SYMBOLS[currency]})
                          </option>
                        ))}
                      </select>

                      {/* Visual Display: Chevron -> Symbol -> Amount */}
                      <div className="flex items-baseline justify-center w-full">
                        <div className="flex items-center mr-1 sm:mr-2 shrink-0">
                          <ChevronDown className="w-6 h-6 sm:w-7 sm:h-7 text-zinc-500 mr-0.5 group-hover:text-white transition-colors" />
                          <span className="text-5xl sm:text-6xl font-medium text-white tracking-normal leading-none">{currencySymbol}</span>
                        </div>
                        <span className="font-bold text-white tracking-tight leading-none" style={{ fontSize: 'calc(clamp(3rem, 12vw, 5.5rem) * var(--balance-amount-scale))' }}>
                          {(() => {
                            const val = totalBalance > 0 ? formattedTotalBalance : '0.00';
                            const [int, dec] = val.split('.');
                            return (
                              <>
                                {int}<span className="font-medium text-zinc-400 tracking-normal leading-none" style={{ fontSize: '0.6em' }}>.{dec}</span>
                              </>
                            );
                          })()}
                        </span>
                      </div>
                    </div>
                  )}

                  {/* Subtle refresh indicator */}
                  {(localRefreshing || balanceRefreshing) && (
                    <div className="absolute -top-1 -right-4 w-3 h-3 bg-green-500 rounded-full animate-pulse shadow-[0_0_10px_#22c55e]"></div>
                  )}
                </div>

                {/* Price change indicator */}
                {isKycApproved && !balanceLoading && !ratesLoading && priceChangeInfo && (
                  <div className={`flex items-center gap-1.5 mt-2 px-3 py-1 rounded-full ${priceChangeInfo.direction === 'down'
                    ? 'bg-red-500/10 text-red-400'
                    : priceChangeInfo.direction === 'up'
                      ? 'bg-emerald-500/10 text-emerald-400'
                      : 'bg-zinc-500/10 text-zinc-300'
                    }`}>
                    {priceChangeInfo.direction === 'down' ? (
                      <Triangle className="h-3 w-3 rotate-180 fill-red-400" />
                    ) : priceChangeInfo.direction === 'up' ? (
                      <Triangle className="h-3 w-3 fill-emerald-400" />
                    ) : null}
                    <span className="text-sm font-bold">
                      {Math.abs(priceChangeInfo.percentageChange).toFixed(2)}%
                    </span>
                  </div>
                )}
              </div>
            )}

            {/* Show message based on status */}
            {!showBalanceSection && (
              <div className="text-2xl font-bold text-zinc-400 mb-4">
                {!accountData?.username ? 'Set username to continue' : 'Complete KYC to view balance'}
              </div>
            )}

            {!isKycApproved && (
              <p className="text-zinc-400 font-medium my-4">
                {showBalanceSection
                  ? 'Complete KYC to unlock full functionality'
                  : 'Wallet functionality will be unlocked after verification'
                }
              </p>
            )}

            {showBalanceSection && isKycApproved && balance && (
              <div className="text-left flex-[4] flex flex-col justify-end">
                <SupportedAssetsBalances balance={balance} className="mt-4" />
              </div>
            )}

          </div>
          <div className="w-full shrink-0 min-w-0 overflow-hidden p-8">
            <div className="text-white h-full flex flex-col justify-center">
              <div className="flex flex-col items-start w-full mb-8">
                <h3 className="text-2xl font-bold mb-2">Quick Actions</h3>
                <p className="text-zinc-400 text-lg leading-snug">
                  Add funds or swap between<br />currencies instantly
                </p>
              </div>
              <div className="flex flex-row gap-6 w-full justify-center items-center">
                <button
                  type="button"
                  onClick={openDepositModal}
                  className="group hover:scale-105 transition-transform duration-200 focus:outline-none"
                  aria-label="Deposit"
                >
                  <img
                    src="/deposit-icon.svg"
                    alt="Deposit"
                    className="w-36 h-36 drop-shadow-lg"
                  />
                </button>
                <button
                  type="button"
                  onClick={openSwapModal}
                  className="group hover:scale-105 transition-transform duration-200 focus:outline-none"
                  aria-label="Swap"
                >
                  <img
                    src="/swap-icon.svg"
                    alt="Swap"
                    className="w-36 h-36 drop-shadow-lg"
                  />
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="flex justify-center gap-2 py-4 bg-transparent" aria-label="Wallet sections">
          {[0, 1, 2].map((index) => (
            <button
              key={index}
              onClick={() => setActiveSlide(index)}
              className={`w-3 h-3 rounded-full transition-all ${activeSlide === index ? 'bg-white' : 'bg-zinc-600/70'}`}
              aria-label={`Go to slide ${index + 1}`}
            />
          ))}
        </div>
      </div>

      {showDepositModal && (
        <BuyUSDCModal
          fiatData={DEFAULT_FIAT_DATA}
          onClose={() => setShowDepositModal(false)}
          walletAddress={accountData?.wallet_address}
        />
      )}

      {showSwapModal && (
        <SwapModal
          visible={showSwapModal}
          onClose={(autoClose) => handleModalClose(setShowSwapModal, autoClose)}
          userAddress={accountData?.wallet_address}
          username={accountData?.username}
          balance={balance}
        />
      )}
    </>
  );
});

BalanceCard.displayName = 'BalanceCard';

export default BalanceCard;
