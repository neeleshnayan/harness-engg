import React, { useEffect, useState } from "react";
import TransactionHistory from "@/components/wallet/TransactionHistory";
import KTTokenBalances from "@/components/wallet/KTTokenBalances";
import { FaShieldAlt, FaPlus } from "react-icons/fa";
import { TbArrowsExchange2 } from "react-icons/tb";
import { getAllPoolRates } from "@/lib/priceCache";
import { K_TOKEN_ADDRESSES_LOWERCASE, K_TOKEN_SYMBOL_LIST, CURRENCY_SYMBOLS } from "@/lib/kTokens";
import BuyUSDCModal from "@/components/wallet/BuyUSDCModal";
import SwapModal from "@/components/wallet/SwapModal";

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

const USDC_SVG = (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="ml-2">
    <circle cx="16" cy="16" r="16" fill="#2775CA"/>
    <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
    <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
    <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
  </svg>
);

const DEFAULT_FIAT_DATA = [
  { code: "USD", symbol: "$" },
  { code: "EUR", symbol: "€" },
  { code: "GBP", symbol: "£" },
];

const BalanceCard: React.FC<BalanceCardProps> = ({
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
}) => {
  const [localRefreshing, setLocalRefreshing] = useState(false);
  const [isFlickering, setIsFlickering] = useState(false);
  const [selectedCurrency, setSelectedCurrency] = useState('USD');
  const [poolRates, setPoolRates] = useState<{ [key: string]: number }>({});
  const [activeSlide, setActiveSlide] = useState(0);
  const [touchStartX, setTouchStartX] = useState<number | null>(null);
  const [touchEndX, setTouchEndX] = useState<number | null>(null);
  const [showDepositModal, setShowDepositModal] = useState(false);
  const [showSwapModal, setShowSwapModal] = useState(false);
  const handleTouchStart = (e: React.TouchEvent<HTMLDivElement>) => {
    setTouchStartX(e.touches[0].clientX);
  };

  const handleTouchMove = (e: React.TouchEvent<HTMLDivElement>) => {
    setTouchEndX(e.touches[0].clientX);
  };

  const handleTouchEnd = () => {
    if (touchStartX === null || touchEndX === null) {
      setTouchStartX(null);
      setTouchEndX(null);
      return;
    }

    const delta = touchStartX - touchEndX;
    const threshold = 50;
    if (delta > threshold && activeSlide < 1) {
      setActiveSlide(1);
    } else if (delta < -threshold && activeSlide > 0) {
      setActiveSlide(0);
    }

    setTouchStartX(null);
    setTouchEndX(null);
  };

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
        const rates = await getAllPoolRates();
        // Convert array to map for easier lookup: { "USD/EUR": 1.16251899, ... }
        const ratesMap: { [key: string]: number } = {};
        rates.forEach((rate) => {
          ratesMap[rate.pair] = rate.rate;
        });
        setPoolRates(ratesMap);
      } catch (error) {
        console.error('Failed to fetch pool rates:', error);
      }
    };
    fetchRates();
    const interval = setInterval(fetchRates, 3600000); // Refresh every hour
    return () => clearInterval(interval);
  }, []);

  // Calculate total balance in selected currency
  const calculateTotalBalance = (): number => {
    if (!balance || !Array.isArray(balance.tokenBalances) || balance.tokenBalances.length === 0) {
      return 0;
    }

    let totalInUSD = 0;

    // Get USDC and TRNSK balances (both are in USD)
    const transakToken = balance.tokenBalances.find(
      (b: any) => b.token && b.token.symbol === 'TRNSK'
    );
    const usdc = balance.tokenBalances.find(
      (b: any) => b.token && b.token.symbol === 'USDC'
    );
    const transakAmount = parseFloat(transakToken?.amount ?? "0");
    const usdcAmount = parseFloat(usdc?.amount ?? "0");
    totalInUSD += transakAmount + usdcAmount;

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
        className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-0 shadow-2xl border border-zinc-800 mb-8 transition-all duration-300 overflow-hidden ${localRefreshing ? 'ring-2 ring-green-500/30 ring-opacity-50' : ''} ${className || ''}`}
        onTouchStart={handleTouchStart}
        onTouchMove={handleTouchMove}
        onTouchEnd={handleTouchEnd}
      >
        <div
          className="flex transition-transform duration-300"
          style={{ transform: `translateX(-${activeSlide * 100}%)` }}
        >
          <div className="w-full flex-shrink-0 p-8">
            <div className="text-center">
        <div className="flex items-center justify-center mb-4 gap-2">
          {USDC_SVG}
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
            <div className={`text-6xl font-bold text-white relative transition-all duration-200 ${
              isFlickering ? 'balance-flicker' : ''
            }`}>
              {balanceLoading || balanceRefreshing || localRefreshing ? (
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
            {onBuyClick && isKycApproved && !balanceLoading && !balanceRefreshing && !localRefreshing && (
              <button
                onClick={onBuyClick}
                className="ml-6 p-3 bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 shadow-sm hover:shadow-md transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-blue-500/50 group"
                title="Add USDC to your wallet"
              >
                <FaPlus className="text-lg group-hover:scale-110 transition-transform duration-200" />
              </button>
            )}
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
          <KTTokenBalances balance={balance} />
        )}

        {/* Transaction History Toggle - Only show if KYC is approved */}
        {showBalanceSection && isKycApproved && (
          <div className="mt-6 pt-4 border-t border-zinc-700/50">
            <button
              onClick={() => {
                setShowTransactions(!showTransactions);
              }}
              className="flex items-center justify-center space-x-2 text-zinc-400 hover:text-zinc-300 transition-colors text-sm"
            >
              <span>Transaction History</span>
              <svg
                className={`w-3 h-3 transition-transform duration-200 ${showTransactions ? 'rotate-180' : ''}`}
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
            {/* Transaction History Dropdown */}
            {showTransactions && (
              <div className="mt-4">
                <TransactionHistory
                  username={accountData.username}
                  userWalletAddress={accountData.wallet_address}
                  refresh={transactionHistoryRefresh}
                />
              </div>
            )}
          </div>
        )}
            </div>
          </div>
          <div className="w-full flex-shrink-0 p-8">
            <div className="text-white">
              <h3 className="text-2xl font-bold mb-2">Quick Actions</h3>
              <p className="text-zinc-400 mb-6">Deposit USDC or swap between currencies instantly.</p>
              <div className="flex flex-col md:flex-row gap-4 md:gap-8 justify-center md:px-6">
                <button
                  onClick={openDepositModal}
                  className="w-full md:w-64 h-36 flex flex-col justify-between bg-gradient-to-r from-blue-500/30 to-purple-500/30 border border-blue-400/30 rounded-2xl px-6 py-5 hover:from-blue-500/40 hover:to-purple-500/40 transition-all duration-200"
                >
                  <div className="flex items-start justify-between">
                    <p className="text-xl font-semibold text-white">Deposit</p>
                    <FaPlus className="text-2xl text-white" />
                  </div>
                  <p className="text-sm text-zinc-200">Add USDC to your wallet</p>
                </button>
                <button
                  onClick={openSwapModal}
                  className="w-full md:w-64 h-36 flex flex-col justify-between bg-gradient-to-r from-emerald-500/30 to-cyan-500/30 border border-emerald-400/30 rounded-2xl px-6 py-5 hover:from-emerald-500/40 hover:to-cyan-500/40 transition-all duration-200"
                >
                  <div className="flex items-start justify-between">
                    <p className="text-xl font-semibold text-white">Swap</p>
                    <TbArrowsExchange2 className="text-2xl text-white" />
                  </div>
                  <p className="text-sm text-zinc-200">Move between supported currencies</p>
                </button>
              </div>
            </div>
          </div>
        </div>
        <div className="flex justify-center gap-2 py-4 border-t border-zinc-800 bg-zinc-900/70">
          {[0, 1].map((index) => (
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
          onClose={() => setShowSwapModal(false)}
          userAddress={accountData?.wallet_address}
          balance={balance}
        />
      )}
    </>
  );
};

export default BalanceCard;
