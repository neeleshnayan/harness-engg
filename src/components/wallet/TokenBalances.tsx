import React, { useState, useEffect } from "react";
import { FaCoins, FaEthereum, FaSync } from "react-icons/fa";
import { ChevronDown, ChevronUp } from "lucide-react";
import api from "@/lib/api";
import { useMAVCConfig } from "@/hooks/useMAVCConfig";
import { useMAVCPrice, useMAVCPriceHistory } from "@/hooks/useMAVCPrice";
import { useMAVPPrice, useMAVPPriceHistory } from "@/hooks/useMAVPPrice";
import { useMAVPConfig } from "@/hooks/useMAVPConfig";
import { useSubgraphData } from "@/hooks/useSubgraphData";
import { useMAVPSubgraphData } from "@/hooks/useMAVPSubgraphData";
import { MAVCMiniChart } from "./MAVCMiniChart";
import { MAVPMiniChart } from "./MAVPMiniChart";
import { NetAUMChart } from "./NetAUMChart";
import { Skeleton } from "@/components/ui/skeleton";

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

interface TokenBalancesProps {
  balance: any;
  loading?: boolean;
  error?: string | null;
  className?: string;
  onRefresh?: () => void;
  subgraphUrl?: string;
  userWalletAddress?: string;
}

const TokenBalances: React.FC<TokenBalancesProps> = ({
  balance,
  loading = false,
  error = null,
  className = "",
  onRefresh,
  subgraphUrl,
  userWalletAddress
}) => {
  const { data: mavcConfig } = useMAVCConfig();
  const { data: mavcPriceData } = useMAVCPrice(subgraphUrl || mavcConfig?.subgraph_url);
  const { data: mavcPriceHistory } = useMAVCPriceHistory(subgraphUrl || mavcConfig?.subgraph_url);
  const { data: mavpConfig } = useMAVPConfig();
  const { data: mavpPriceData } = useMAVPPrice(mavpConfig?.subgraph_url);
  const { data: mavpPriceHistory } = useMAVPPriceHistory(mavpConfig?.subgraph_url);
  const { data: mavcSubgraphData } = useSubgraphData(subgraphUrl || mavcConfig?.subgraph_url);
  const { data: mavpSubgraphData } = useMAVPSubgraphData(mavpConfig?.subgraph_url);
  const [tokenDetails, setTokenDetails] = useState<TokenWithValue[]>([]);
  const [priceLoading, setPriceLoading] = useState(false);
  const [totalValue, setTotalValue] = useState<number>(0);
  const [isExpanded, setIsExpanded] = useState(false);

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
      case 'ETH':
        return <FaEthereum className="w-6 h-6 text-blue-400" />;
      default:
        return <FaCoins className="w-6 h-6 text-yellow-400" />;
    }
  };

  const formatTokenAmount = (amount: string, decimals: number, symbol: string) => {
    try {
      const numAmount = parseFloat(amount);
      if (isNaN(numAmount)) return "0";

      // Use the smart formatTokenBalance utility for better readability
      // For USDC, show with 2 decimal places
      if (symbol.toUpperCase() === 'USDC') {
        return `${numAmount.toFixed(2)}`;
      } else if (symbol.toUpperCase() === 'TRNSK') {
        return `${numAmount.toFixed(2)}`;
      }

      // For all other tokens including MAVC, use formatTokenBalance for smart formatting
      const formatted = parseFloat(amount);
      if (formatted < 0.0001) return formatted.toFixed(6);
      if (formatted < 0.01) return formatted.toFixed(4);
      if (formatted < 1) return formatted.toFixed(3);
      if (formatted < 100) return formatted.toFixed(2);
      return formatted.toFixed(1);
    } catch (error) {
      return `${amount}`;
    }
  };

  const formatValue = (value: number) => {
    return `$${value.toFixed(2)}`;
  };

  function mergeTrnskIntoUsdc(balances: any) {
    let mergedBalances = [];
    let usdcMerged = null;

    for (const entry of balances) {
      const symbol = entry.token.symbol;
      const amount = parseFloat(entry.amount);

      if (symbol === "USDC" || symbol === "TRNSK") {
        if (!usdcMerged) {
          // Start with the first USDC or TRNSK as base
          usdcMerged = JSON.parse(JSON.stringify(entry));
          usdcMerged.amount = amount;
          usdcMerged.token.symbol = "USDC";
          usdcMerged.token.name = "USDC";
        } else {
          // Add amount from TRNSK or additional USDC
          usdcMerged.amount += amount;
        }
      } else {
        // Leave other tokens unchanged
        mergedBalances.push(entry);
      }
    }

    if (usdcMerged) {
      // Convert amount back to string to match original format
      usdcMerged.amount = usdcMerged.amount.toString();
      mergedBalances.push(usdcMerged);
    }

    return mergedBalances;
  }

  const calculateTokenValues = async (tokenBalances: TokenBalance[]) => {
    setPriceLoading(true);
    let totalValue = 0;
    const tokensWithValues: TokenWithValue[] = [];

    try {
      for (const tokenBalance of tokenBalances) {
        const { amount, token } = tokenBalance;
        const tokenAmount = parseFloat(amount || "0");

        if (tokenAmount <= 0) continue;

        let tokenPrice = 1; // Default price for tokens without address

        // Special case for USDC - it's always worth 1 USDC
        if (token.symbol === 'USDC') {
          tokenPrice = 1;
        }
        // Special case for MAVC - use subgraph price
        else if (token.symbol === 'MAVC' && mavcPriceData?.price) {
          tokenPrice = Number(mavcPriceData.price);
          console.log('Using MAVC price from subgraph:', tokenPrice);
        }
        // Special case for MAVP - use subgraph price
        else if (token.symbol === 'MAVP' && mavpPriceData?.price) {
          tokenPrice = Number(mavpPriceData.price);
          console.log('Using MAVP price from subgraph:', tokenPrice);
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
        }

        // Calculate value for this token
        const tokenValue = tokenAmount * tokenPrice;
        totalValue += tokenValue;

        console.log(`Token ${token.symbol}: amount=${tokenAmount}, price=${tokenPrice}, value=${tokenValue}`);

        // Add to tokens with values array
        tokensWithValues.push({
          ...tokenBalance,
          price: tokenPrice,
          value: tokenValue
        });
      }

      // Sort tokens by value (highest first)
      tokensWithValues.sort((a, b) => b.value - a.value);

      setTokenDetails(tokensWithValues);
      setTotalValue(totalValue);
    } catch (err) {
      console.error('Error calculating token values:', err);
      setTokenDetails([]);
      setTotalValue(0);
    } finally {
      setPriceLoading(false);
    }
  };

  const convertMavcToHumanReadable = (balances: any[]) => {
    // Get the correct MAVC token address from Firestore config
    const mavcTokenAddress = mavcConfig?.token_address;

    return balances
      .filter((balance) => {
        // Filter out old MAVC tokens (keep only the correct one from config)
        if (balance.token.symbol === 'MAVC') {
          return mavcTokenAddress && balance.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase();
        }
        return true; // Keep all non-MAVC tokens
      })
      .map((balance) => {
        if (balance.token.symbol === 'MAVC' &&
            mavcTokenAddress &&
            balance.token.tokenAddress?.toLowerCase() === mavcTokenAddress.toLowerCase()) {
          // MAVC uses 12 decimals (10^12) - convert to human-readable format
          const rawAmount = parseFloat(balance.amount || "0");
          const humanReadable = rawAmount / Math.pow(10, 12);

          return {
            ...balance,
            amount: humanReadable.toString()
          };
        }
        // MAVP uses 12 decimals (10^12) - convert to human-readable format
        if (balance.token.symbol === 'MAVP') {
          const rawAmount = parseFloat(balance.amount || "0");
          const humanReadable = rawAmount / Math.pow(10, 12);

          return {
            ...balance,
            amount: humanReadable.toString()
          };
        }
        return balance;
      });
  };

  const getTokenBalances = () => {
    if (!balance || !Array.isArray(balance.tokenBalances)) {
      return [];
    }

    var balances = balance.tokenBalances.filter((tokenBalance: TokenBalance) => {
      const amount = parseFloat(tokenBalance.amount);
      return !isNaN(amount) && amount > 0;
    });
    balances = mergeTrnskIntoUsdc(balances);
    balances = convertMavcToHumanReadable(balances);
    return balances;
  };

  useEffect(() => {
    const tokenBalances = getTokenBalances();
    if (tokenBalances.length > 0) {
      calculateTokenValues(tokenBalances);
    }
  }, [balance, mavcPriceData, mavpPriceData]);

  const tokenBalances = getTokenBalances();

  if (loading) {
    return (
      <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 ${className}`}>
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-blue-500 border-t-transparent mx-auto mb-4"></div>
          <p className="text-zinc-400">Loading token balances...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 ${className}`}>
        <div className="text-center">
          <div className="w-16 h-16 bg-red-500/20 rounded-full flex items-center justify-center mx-auto mb-4">
            <FaCoins className="text-red-400 text-2xl" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">Error Loading Tokens</h3>
          <p className="text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  if (tokenBalances.length === 0) {
    return (
      <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 ${className}`}>
        <div className="text-center">
          <div className="w-16 h-16 bg-zinc-700/50 rounded-full flex items-center justify-center mx-auto mb-4">
            <FaCoins className="text-zinc-400 text-2xl" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">No Tokens Found</h3>
          <p className="text-zinc-400">You don't have any tokens in your wallet yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 ${className}`}>
      {/* Total Value Header */}
      <div className="text-center mb-6">
        <h3 className="text-2xl font-bold text-white mb-2">Token Portfolio</h3>
        <div className="text-3xl font-bold text-green-400 mb-2">
          {priceLoading || loading ? (
            <div className="flex items-center justify-center">
              <Skeleton className="h-8 w-32 bg-zinc-700/50" />
            </div>
          ) : (
            formatValue(totalValue)
          )}
        </div>
        <p className="text-zinc-400 text-sm mb-4">Total Estimated Value</p>

        {/* Expandable/Collapsible Toggle */}
        {tokenDetails.length > 0 && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center justify-center space-x-2 text-zinc-400 hover:text-zinc-300 transition-colors text-sm w-full"
          >
            <span>{isExpanded ? 'Hide Token Details' : 'View Token Details'}</span>
            {isExpanded ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
        )}
      </div>

      {/* Token List - Only show when expanded */}
      {isExpanded && tokenDetails.length > 0 && (
        <div className="space-y-4 mb-6">
          {tokenDetails
            .map((tokenDetail: TokenWithValue, index: number) => (
              <div
                key={`${tokenDetail.token.id}-${index}`}
                className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-6 hover:bg-zinc-700/50 transition-all duration-200"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="flex-shrink-0">
                      {getTokenIcon(tokenDetail.token.symbol)}
                    </div>
                    <div className="flex-1">
                      <h4 className="text-lg font-bold text-white">
                        {tokenDetail.token.name || tokenDetail.token.symbol}
                      </h4>
                      <p className="text-zinc-400 text-sm">
                        {tokenDetail.token.symbol} • {tokenDetail.token.blockchain}
                      </p>
                    </div>
                  </div>
                  <div className="text-right">
                    {(tokenDetail.token.symbol === 'MAVC' || tokenDetail.token.symbol === 'MAVP') ? (
                      <>
                        <div className="text-2xl font-bold text-green-400">
                          {formatValue(tokenDetail.value)}
                        </div>
                        <div className="text-zinc-400 text-sm mt-1">
                          {formatTokenAmount(tokenDetail.amount, tokenDetail.token.decimals, tokenDetail.token.symbol)} × ${tokenDetail.price.toFixed(4)}
                        </div>
                      </>
                    ) : (
                      <>
                        <div className="text-xl font-bold text-white">
                          {formatTokenAmount(tokenDetail.amount, tokenDetail.token.decimals, tokenDetail.token.symbol)}
                        </div>
                        <div className="text-zinc-400 text-sm">
                          @ ${tokenDetail.price.toFixed(4)}
                        </div>
                        <div className="text-green-400 text-sm font-semibold">
                          {formatValue(tokenDetail.value)}
                        </div>
                      </>
                    )}
                  </div>
                </div>
                {/* Add mini chart for MAVC tokens */}
                {tokenDetail.token.symbol === 'MAVC' && mavcSubgraphData && mavcPriceHistory && (
                  <NetAUMChart
                    deposits={mavcSubgraphData.deposits || []}
                    withdrawals={mavcSubgraphData.withdrawals || []}
                    priceHistory={mavcPriceHistory || []}
                    userWalletAddress={userWalletAddress}
                    tokenSymbol="MAVC"
                    currentBalance={parseFloat(tokenDetail.amount)}
                  />
                )}
                {tokenDetail.token.symbol === 'MAVP' && mavpSubgraphData && mavpPriceHistory && (
                  <NetAUMChart
                    deposits={mavpSubgraphData.deposits || []}
                    withdrawals={mavpSubgraphData.withdrawals || []}
                    priceHistory={mavpPriceHistory || []}
                    userWalletAddress={userWalletAddress}
                    tokenSymbol="MAVP"
                    currentBalance={parseFloat(tokenDetail.amount)}
                  />
                )}
              </div>
            ))}
        </div>
      )}

      {/* Footer with token count */}
      <div className="pt-4 border-t border-zinc-700/50">
        <div className="text-center">
          <p className="text-zinc-400 text-sm">
            Total tokens: {tokenDetails.length}
          </p>
        </div>
      </div>
    </div>
  );
};

export default TokenBalances;