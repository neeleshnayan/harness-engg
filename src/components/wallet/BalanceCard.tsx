import React, { useEffect, useState, useRef, useImperativeHandle, forwardRef, useCallback } from "react";
import TransactionHistory, { TransactionHistoryRef } from "@/components/wallet/TransactionHistory";
import ActiveTransactions from "@/components/wallet/ActiveTransactions";
import KTTokenBalances from "@/components/wallet/KTTokenBalances";
import { FaShieldAlt, FaPlus } from "react-icons/fa";
import { TbArrowsExchange2 } from "react-icons/tb";
import { FiRefreshCw } from "react-icons/fi";
import { getAllPoolRates, haveRatesAppreciated, PriceChangeDirection, PriceChangeInfo } from "@/lib/priceCache";
import { K_TOKEN_ADDRESSES_LOWERCASE, K_TOKEN_SYMBOL_LIST, CURRENCY_SYMBOLS } from "@/lib/kTokens";
import BuyUSDCModal from "@/components/wallet/BuyUSDCModal";
import SwapModal from "@/components/wallet/SwapModal";
import { Triangle } from "lucide-react";

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
}

const WALLET_ICON = (
  <div className="rounded-full p-1 flex items-center justify-center" style={{ backgroundColor: '#2775CA', width: '36px', height: '36px' }}>
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
  balanceFlickering = false
}, ref) => {
  const [localRefreshing, setLocalRefreshing] = useState(false);
  const [isFlickering, setIsFlickering] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState('USD');
  const [poolRates, setPoolRates] = useState<{ [key: string]: number }>({});
  const [poolRatesLoading, setPoolRatesLoading] = useState(true);
  const [priceChangeInfo, setPriceChangeInfo] = useState<PriceChangeInfo | null>(null);
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
  const poolRatesInitialFetch = useRef(true);

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


  const showKycSection = accountData?.username && kycStatus !== 'approved' && onKycClick;
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

  // Handle balance flickering when USDC is sent out
  useEffect(() => {
    if (balanceFlickering) {
      setIsFlickering(true);
    } else {
      setIsFlickering(false);
    }
  }, [balanceFlickering]);

  // Fetch pool rates and convert to map
  useEffect(() => {
    const fetchRates = async () => {
      try {
        if (poolRatesInitialFetch.current) {
          setPoolRatesLoading(true);
        }
        const rates = await getAllPoolRates();
        // Convert array to map for easier lookup: { "USD/EUR": 1.16251899, ... }
        const ratesMap: { [key: string]: number } = {};
        rates.forEach((rate) => {
          ratesMap[rate.pair] = rate.rate;
        });
        setPoolRates(ratesMap);
      } catch (error) {
        console.error('Failed to fetch pool rates:', error);
      } finally {
        if (poolRatesInitialFetch.current) {
          setPoolRatesLoading(false);
          poolRatesInitialFetch.current = false;
        }
      }
    };
    fetchRates();
    const interval = setInterval(fetchRates, 3600000); // Refresh every hour
    return () => clearInterval(interval);
  }, []);

  // Check if rates have appreciated when balance or pool rates change
  useEffect(() => {
    const checkRatesAppreciation = async () => {
      if (!balance || poolRatesLoading || !poolRates || Object.keys(poolRates).length === 0) {
        return;
      }

      try {
        const info = await haveRatesAppreciated(balance);
        setPriceChangeInfo(info);
      } catch (error) {
        console.error('Failed to check rates appreciation:', error);
        setPriceChangeInfo(null);
      }
    };

    checkRatesAppreciation();
  }, [balance, poolRates, poolRatesLoading]);

  // Calculate total balance in selected currency
  const calculateTotalBalance = (): number => {
    if (!balance || !Array.isArray(balance.tokenBalances) || balance.tokenBalances.length === 0) {
      return 0;
    }

    let totalInUSD = 0;

    // Get USDC balance
    const usdc = balance.tokenBalances.find(
      (b: any) => b.token && b.token.symbol === 'USDC'
    );
    const usdcAmount = parseFloat(usdc?.amount ?? "0");
    totalInUSD += usdcAmount;

    // Get kToken balances and convert to USD
    for (const tb of balance.tokenBalances) {
      const tokenAddress = tb?.token?.tokenAddress?.toLowerCase();
      const kTokenSymbol = tokenAddress ? K_TOKEN_ADDRESSES_LOWERCASE[tokenAddress] : undefined;

      if (kTokenSymbol && parseFloat(tb.amount) > 0) {
        const kTokenAmount = parseFloat(tb.amount || "0");
        let usdValue = 0;

        if (kTokenSymbol === 'kUSD') {
          // kUSD is 1:1 with USD
          usdValue = kTokenAmount;
        } else {
          // Get the rate pair for this kToken
          const ratePair = `kUSD/${kTokenSymbol}`;
          const rate = poolRates[ratePair];

          if (rate && rate > 0) {
            // Rate is already in format: USD/EUR = 1.16251899 means 1 EUR = 1.16251899 USD
            // So to convert kToken to USD: multiply by rate
            usdValue = kTokenAmount * rate;
          }
        }

        totalInUSD += usdValue;
      }
    }

    // Convert from USD to selected currency if needed
    if (selectedCurrency === 'USD') {
      return totalInUSD;
    }

    // Get conversion rate from USD to selected currency
    const ratePair = `kUSD/k${selectedCurrency}`;
    const rate = poolRates[ratePair];

    if (rate && rate > 0) {
      // Rate is USD/Currency, so to convert USD to Currency: divide by rate
      return totalInUSD / rate;
    }

    // If rate not available, return USD value
    return totalInUSD;
  };


  // Get available currencies for dropdown (USD + kToken currencies, excluding kUSD since it's USD)
  const availableCurrencies = [
    'USD',
    ...K_TOKEN_SYMBOL_LIST.filter(s => s !== 'kUSD').map(s => s.replace(/^k/, ''))
  ];
  const currencySymbol = CURRENCY_SYMBOLS[selectedCurrency] || '$';

  return (
    <>
      <div
        className={`backdrop-blur-xl rounded-3xl p-0 shadow-2xl border border-zinc-800 mb-8 transition-all duration-300 overflow-hidden ${localRefreshing ? 'ring-2 ring-green-500/30 ring-opacity-50' : ''} ${className || ''}`}
        style={{
          background:
            "radial-gradient(50% 50% at 50% 50%, rgba(255, 255, 255, 0.12) 0%, rgba(161, 207, 211, 0.08) 100%), #0d1315",
        }}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div
          className="flex transition-transform duration-300"
          style={{ transform: `translateX(-${activeSlide * 100}%)` }}
        >
          {/* Transaction History Tab */}
          <div className="w-full flex-shrink-0 p-8">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-white">Transaction History</h3>
              <button
                onClick={handleTransactionHistoryRefresh}
                className="p-2 bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 shadow-sm hover:shadow-md transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 group"
                title="Refresh transaction history"
              >
                <FiRefreshCw className="text-lg group-hover:rotate-180 transition-transform duration-500" />
              </button>
            </div>
            {showBalanceSection && isKycApproved ? (
              <div
                ref={scrollContainerRef}
                style={{
                  overflowY: 'scroll',
                  paddingRight: '8px',
                  WebkitOverflowScrolling: 'touch',
                  overscrollBehavior: 'contain'
                }}
                className="max-h-[250px] md:max-h-[200px] [&::-webkit-scrollbar]:w-2 [&::-webkit-scrollbar-track]:bg-transparent [&::-webkit-scrollbar-thumb]:bg-zinc-700 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:hover:bg-zinc-600"
                onWheel={(e) => {
                  e.stopPropagation();
                }}
              >
                {/* Active Transactions - Shows pending Circle transactions */}
                {/* Only poll when Transaction History tab is visible (activeSlide === 0) */}
                <ActiveTransactions
                  username={accountData.username}
                  className="mb-4"
                  onAllTransactionsComplete={handleTransactionHistoryRefresh}
                  refreshKey={activeTransactionsRefreshKey}
                  isVisible={activeSlide === 0}
                />
                <TransactionHistory
                  ref={transactionHistoryRef}
                  username={accountData.username}
                  userWalletAddress={accountData.wallet_address}
                  refresh={transactionHistoryRefresh || transactionHistoryRefreshKey > 0}
                />
              </div>
            ) : (
              <div className="flex items-center justify-center text-zinc-400 py-8">
                <p>Complete KYC to view transaction history</p>
              </div>
            )}
          </div>
          {/* Balance Tab */}
          <div className="w-full flex-shrink-0 p-8">
            <div className="text-center">
        <div className="flex items-center justify-center mb-4 gap-2">
          {WALLET_ICON}
          <h3 className="text-2xl font-bold text-white">
            Your Balance{' '}
            <span className="text-lg font-normal text-zinc-400">
              (in{' '}
              {showBalanceSection && isKycApproved ? (
                <span className="inline-flex items-center relative group cursor-pointer">
                  <select
                    value={selectedCurrency}
                    onChange={(e) => setSelectedCurrency(e.target.value)}
                    className="appearance-none bg-transparent text-cyan-400 hover:text-cyan-300 font-normal cursor-pointer focus:outline-none text-lg pr-4"
                  >
                    {availableCurrencies.map((currency) => (
                      <option key={currency} value={currency} className="bg-zinc-800">
                        {currency}
                      </option>
                    ))}
                  </select>
                  <svg
                    className="pointer-events-none absolute right-0 top-1/2 -translate-y-1/2 text-cyan-400 group-hover:text-cyan-300 transition-colors"
                    width="12"
                    height="12"
                    viewBox="0 0 12 12"
                    fill="none"
                  >
                    <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                </span>
              ) : (
                <span>USD</span>
              )}
              )
            </span>
          </h3>
        </div>

        {/* <div className={`mt-4 pt-4 border-t border-zinc-700/50 ${className || ''}`}></div> */}

        {/* Show KYC banner if username is set but KYC not approved */}
        {showKycSection && (
          <div className="mb-6">
            <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 border border-purple-500/30 rounded-2xl p-6 mb-4">
              <div className="flex items-center justify-center mb-4">
                <FaShieldAlt className="text-3xl text-purple-400 mr-3" />
                <h3 className="text-xl font-bold text-white">Complete KYC Verification</h3>
              </div>
              <p className="text-zinc-300 mb-4 text-center">
                Complete your identity verification to unlock full wallet functionality and start sending payments securely.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <button
                  onClick={onKycClick}
                  className="bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white font-semibold py-3 px-8 rounded-xl transition-all duration-200 transform hover:scale-105 shadow-lg"
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
                <div className={`mt-3 p-3 rounded-lg text-sm text-center ${
                  kycMessage.includes('approved')
                    ? 'bg-green-900/30 text-green-400 border border-green-500/30'
                    : kycMessage.includes('error') || kycMessage.includes('Failed')
                    ? 'bg-red-900/30 text-red-400 border border-red-500/30'
                    : 'bg-blue-900/30 text-blue-400 border border-blue-500/30'
                }`}>
                  {kycMessage}
                </div>
              )}
            </div>
          </div>
        )}



        {/* Show balance always if username exists, but blur if KYC not approved */}
        {showBalanceSection && (
          <div className={`flex items-center justify-center mb-4 ${!isKycApproved ? 'blur-sm' : ''}`}>
            <div className="flex items-center gap-3">
              <div className={`text-6xl font-bold text-white relative transition-all duration-200 ${
                isFlickering ? 'balance-flicker' : ''
              }`}>
                {balanceLoading || balanceRefreshing || localRefreshing || poolRatesLoading ? (
                  <div className="flex items-center justify-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mr-3"></div>
                    <span className="text-2xl">
                      {localRefreshing ? 'Updating...' : balanceRefreshing ? 'Refreshing...' : 'Loading...'}
                    </span>
                  </div>
                ) : error ? (
                  <span className="text-red-400 text-2xl font-semibold">{error}</span>
                ) : (() => {
                  const totalBalance = calculateTotalBalance();
                  if (totalBalance > 0) {
                    return `${currencySymbol}${totalBalance.toFixed(2)}`;
                  }
                  return '-';
                })()}
                {/* Subtle refresh indicator */}
                {localRefreshing && (
                  <div className="absolute -top-2 -right-2 w-4 h-4 bg-green-500 rounded-full animate-pulse"></div>
                )}
              </div>
              {/* Price change indicator */}
              {isKycApproved && !balanceLoading && !balanceRefreshing && !localRefreshing && !poolRatesLoading && priceChangeInfo && priceChangeInfo.direction !== PriceChangeDirection.SAME && (
                <div className={`flex flex-col items-center gap-0.5 ${
                  priceChangeInfo.direction === PriceChangeDirection.UP
                    ? 'text-green-400'
                    : 'text-red-400'
                }`}>
                  {priceChangeInfo.direction === PriceChangeDirection.UP ? (
                    <Triangle className="h-3 w-3 fill-emerald-400" />
                  ) : (
                    <Triangle className="h-3 w-3 rotate-180 fill-red-400" />
                  )}
                  <span className="text-sm font-semibold">
                    {Math.abs(priceChangeInfo.percentageChange).toFixed(2)}%
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Show message based on status */}
        {!showBalanceSection && (
          <div className="text-2xl font-bold text-zinc-400 mb-4">
            {!accountData?.username ? 'Set username to continue' : 'Complete KYC to view balance'}
          </div>
        )}

        <p className="text-zinc-400 font-medium">
          {showBalanceSection
            ? (isKycApproved
                ? 'Available for transactions'
                : 'Complete KYC to unlock full functionality')
            : 'Wallet functionality will be unlocked after verification'
          }
        </p>

        {/* K-Token Balances - Show at the bottom if KYC is approved */}
        {showBalanceSection && isKycApproved && balance && (
          <div className="text-left">
            <KTTokenBalances balance={balance} />
          </div>
        )}

            </div>
          </div>
          <div className="w-full flex-shrink-0 p-8">
            <div className="text-white">
              <h3 className="text-2xl font-bold mb-2">Quick Actions</h3>
              <p className="text-zinc-400 mb-6">Add funds or swap between currencies instantly.</p>
              <div className="flex flex-row gap-3 md:gap-6 justify-center items-center md:px-8">
                <button
                  onClick={openDepositModal}
                  className="w-[calc(50%-0.375rem)] md:w-[calc(50%-0.75rem)] max-w-xs h-40 flex flex-col justify-center items-center gap-3 bg-gradient-to-r from-blue-500/30 to-purple-500/30 border border-blue-400/30 rounded-2xl px-4 md:px-6 py-4 md:py-5 hover:from-blue-500/40 hover:to-purple-500/40 transition-all duration-200 overflow-hidden"
                >
                  <FaPlus className="text-3xl md:text-4xl text-white flex-shrink-0" />
                  <p className="text-2xl md:text-xl font-bold text-white text-center">Deposit</p>
                </button>
                <button
                  onClick={openSwapModal}
                  className="w-[calc(50%-0.375rem)] md:w-[calc(50%-0.75rem)] max-w-xs h-40 flex flex-col justify-center items-center gap-3 bg-gradient-to-r from-emerald-500/30 to-cyan-500/30 border border-emerald-400/30 rounded-2xl px-4 md:px-6 py-4 md:py-5 hover:from-emerald-500/40 hover:to-cyan-500/40 transition-all duration-200 overflow-hidden"
                >
                  <TbArrowsExchange2 className="text-3xl md:text-4xl text-white flex-shrink-0" />
                  <p className="text-2xl md:text-xl font-bold text-white text-center">Swap</p>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="flex justify-center gap-2 py-4 bg-transparent">
          {[0, 1, 2].map((index) => (
            <button
              key={index}
              onClick={() => setActiveSlide(index)}
              className={`w-2.5 h-2.5 rounded-full transition-all ${activeSlide === index ? 'bg-white' : 'bg-zinc-600/70'}`}
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
