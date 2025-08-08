import React, { useState, useEffect } from "react";
import { ChevronDown, ChevronUp, Coins } from "lucide-react";
import api from "@/lib/api";

interface TokenBalance {
  token: {
    id: string;
    symbol: string;
    name: string;
    decimals: number;
    blockchain: string;
    tokenAddress?: string;
  };
  amount: string;
}

interface TokenWithValue extends TokenBalance {
  price: number;
  value: number;
}

interface GrowBalanceCardProps {
  balance: any;
  error: string | null;
  balanceLoading?: boolean;
  className?: string;
}

const USDC_SVG = (
  <svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" className="ml-2">
    <circle cx="16" cy="16" r="16" fill="#2775CA"/>
    <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
    <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
    <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
  </svg>
);

const getTokenIcon = (symbol: string) => {
  switch (symbol.toUpperCase()) {
    case 'USDC':
      return (
        <svg width="24" height="24" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="16" cy="16" r="16" fill="#2775CA"/>
          <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white"/>
          <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA"/>
          <text x="10" y="22" fill="white" fontSize="10" fontWeight="bold">$</text>
        </svg>
      );
    default:
      return <Coins className="w-6 h-6 text-yellow-400" />;
  }
};

const GrowBalanceCard: React.FC<GrowBalanceCardProps> = ({
  balance,
  error,
  balanceLoading = false,
  className
}) => {
  const [estimatedValue, setEstimatedValue] = useState<number>(0);
  const [valueLoading, setValueLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [tokenDetails, setTokenDetails] = useState<TokenWithValue[]>([]);

  useEffect(() => {
    if (balance && Array.isArray(balance.tokenBalances)) {
      calculateEstimatedValue();
    }
  }, [balance]);

  const calculateEstimatedValue = async () => {
    if (!balance || !Array.isArray(balance.tokenBalances)) {
      setEstimatedValue(0);
      setTokenDetails([]);
      return;
    }

    setValueLoading(true);
    let totalValue = 0;
    const tokensWithValues: TokenWithValue[] = [];

    try {
      // Process each token balance
      for (const tokenBalance of balance.tokenBalances) {
        const { amount, token } = tokenBalance;
        const tokenAmount = parseFloat(amount || "0");

        // Skip tokens with zero or negative amounts
        if (tokenAmount <= 0) continue;

        // Skip tokens with extremely small amounts (less than 0.000001) to avoid noise
        if (tokenAmount < 0.000001) continue;

        let tokenPrice = 1; // Default price for tokens without address

        // Special case for USDC - it's always worth 1 USDC
        if (token.symbol === 'USDC') {
          tokenPrice = 1;
        }
        // If token has an address, query the Firebase price endpoint
        else if (token.tokenAddress) {
          try {
            const response = await api.get(`/api/v1/smarttoken/firebase_price/${token.tokenAddress}`);
            if (response.data && response.data.current_price) {
              tokenPrice = response.data.current_price;
            }
          } catch (err) {
            console.warn(`Failed to get Firebase price for token ${token.symbol}:`, err);
            // Keep default price of 1 if API call fails
          }
        } else if (token.symbol !== 'USDC') {
          // For tokens without address (except USDC), assume price of 1
          console.log(`Token ${token.symbol} has no address, using default price of 1`);
        }

        // Calculate value for this token
        const tokenValue = tokenAmount * tokenPrice;
        totalValue += tokenValue;

        // Add to tokens with values array
        tokensWithValues.push({
          ...tokenBalance,
          price: tokenPrice,
          value: tokenValue
        });

        console.log(`Token: ${token.symbol}, Amount: ${tokenAmount}, Price: ${tokenPrice}, Value: ${tokenValue}`);
      }

      // Sort tokens by value (highest first)
      tokensWithValues.sort((a, b) => b.value - a.value);

      setEstimatedValue(totalValue);
      setTokenDetails(tokensWithValues);
      console.log(`Total estimated value: ${totalValue}`);
    } catch (err) {
      console.error('Error calculating estimated value:', err);
      setEstimatedValue(0);
      setTokenDetails([]);
    } finally {
      setValueLoading(false);
    }
  };

  const formatTokenAmount = (amount: string, decimals: number, symbol: string) => {
    try {
      const numAmount = parseFloat(amount);
      if (isNaN(numAmount)) return "0";

      // For USDC, show with 2 decimal places
      if (symbol.toUpperCase() === 'USDC') {
        return `${numAmount.toFixed(2)}`;
      }

      // For other tokens, show with appropriate decimals
      return `${numAmount.toFixed(4)}`;
    } catch (error) {
      return `${amount}`;
    }
  };

  const formatValue = (value: number) => {
    return `$${value.toFixed(2)}`;
  };

  return (
    <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-6 sm:p-8 shadow-2xl border border-zinc-800 mb-8 ${className || ''}`}>
      <div className="text-center">
        <div className="flex items-center justify-center mb-4">
          {USDC_SVG}
          <h3 className="text-xl sm:text-2xl font-bold text-white ml-2">Estimated USDC Holdings</h3>
        </div>

        <div className="flex items-center justify-center mb-4">
          <div className="text-4xl sm:text-6xl font-bold text-white">
            {balanceLoading || valueLoading ? (
              <div className="flex items-center justify-center">
                <div className="animate-spin rounded-full h-6 w-6 sm:h-8 sm:w-8 border-2 border-blue-500 border-t-transparent mr-3"></div>
                <span className="text-lg sm:text-2xl">Loading...</span>
              </div>
            ) : error ? (
              <span className="text-red-400 text-lg sm:text-2xl font-semibold">{error}</span>
            ) : (
              `${estimatedValue.toFixed(2)}`
            )}
          </div>
        </div>

        <p className="text-zinc-400 font-medium text-sm sm:text-base mb-6">
          Total estimated value of your token portfolio
        </p>

        {/* Expandable Token List */}
        {tokenDetails.length > 0 && (
          <div className="border-t border-zinc-700/50 pt-6">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center justify-center space-x-2 text-zinc-400 hover:text-zinc-300 transition-colors text-sm sm:text-base w-full"
            >
              <span>View Token Details</span>
              {isExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </button>

            {/* Token List */}
            {isExpanded && (
              <div className="mt-4 space-y-3 max-h-96 overflow-y-auto">
                {tokenDetails.map((tokenDetail, index) => (
                  <div
                    key={`${tokenDetail.token.id}-${index}`}
                    className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-xl p-4 hover:bg-zinc-700/50 transition-all duration-200"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3 flex-1 min-w-0">
                        <div className="flex-shrink-0">
                          {getTokenIcon(tokenDetail.token.symbol)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <h4 className="text-sm sm:text-base font-bold text-white truncate">
                            {tokenDetail.token.name || tokenDetail.token.symbol}
                          </h4>
                          <p className="text-zinc-400 text-xs sm:text-sm truncate">
                            {tokenDetail.token.symbol} • {tokenDetail.token.blockchain}
                          </p>
                        </div>
                      </div>
                      <div className="flex flex-col items-end space-y-1 flex-shrink-0">
                        <div className="text-sm sm:text-base font-bold text-white">
                          {formatTokenAmount(tokenDetail.amount, tokenDetail.token.decimals, tokenDetail.token.symbol)}
                        </div>
                        <div className="text-xs sm:text-sm text-zinc-400">
                          @ ${tokenDetail.price.toFixed(4)}
                        </div>
                        <div className="text-xs sm:text-sm font-semibold text-green-400">
                          {formatValue(tokenDetail.value)}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default GrowBalanceCard;