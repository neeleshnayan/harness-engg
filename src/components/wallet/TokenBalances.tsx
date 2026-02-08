import React, { useState, useEffect } from "react";
import { FaCoins, FaEthereum } from "react-icons/fa";
import api, { kryptonWeb3Api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import TokenPortfolioChart from "./TokenPortfolioChart";

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

interface PortfolioDataPoint {
  date: string;
  value: number;
  balance: number;
  price: number;
}

interface TokenWithValue extends TokenBalance {
  price: number;
  value: number;
  category: string; // "k_tokens" | "quant_strategies" | "other"
  portfolioHistory?: PortfolioDataPoint[];
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

interface SupportedTokensResponse {
  k_tokens: Record<string, { address: string } | any> | string[];
  custom_tokens: Record<string, { address: string } | any> | string[];
  quant_strategies: string[];
}

type TabKey = "k_tokens" | "quant_strategies" | "other";

const TokenBalances: React.FC<TokenBalancesProps> = ({
  balance,
  loading = false,
  error = null,
  className = "",
  onRefresh,
  subgraphUrl,
  userWalletAddress
}) => {

  const [tokenDetails, setTokenDetails] = useState<TokenWithValue[]>([]);
  const [priceLoading, setPriceLoading] = useState(false);
  const [totalValue, setTotalValue] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<TabKey>("k_tokens");
  const [tokenPrices, setTokenPrices] = useState<Record<string, number>>({});
  const [portfolioHistory, setPortfolioHistory] = useState<Record<string, PortfolioDataPoint[]>>({});
  const [pricesLoading, setPricesLoading] = useState(true);
  const [portfolioLoading, setPortfolioLoading] = useState(true);

  const [supportedTokens, setSupportedTokens] = useState<SupportedTokensResponse | null>(null);
  const [supportedTokensLoading, setSupportedTokensLoading] = useState(true);

  const getTokenIcon = (symbol: string) => {
    switch (symbol.toUpperCase()) {
      case 'USDC':
        return (
          <svg width="24" height="24" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="16" cy="16" r="16" fill="#2775CA" />
            <path d="M16 23.5C19.866 23.5 23 20.366 23 16.5C23 12.634 19.866 9.5 16 9.5C12.134 9.5 9 12.634 9 16.5C9 20.366 12.134 23.5 16 23.5Z" fill="white" />
            <path d="M16 21.5C18.4853 21.5 20.5 19.4853 20.5 17C20.5 14.5147 18.4853 12.5 16 12.5C13.5147 12.5 11.5 14.5147 11.5 17C11.5 19.4853 13.5147 21.5 16 21.5Z" fill="#2775CA" />
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

      if (symbol === "USDC") {
        if (!usdcMerged) {
          // Start with the first USDC as base
          usdcMerged = JSON.parse(JSON.stringify(entry));
          usdcMerged.amount = amount;
          usdcMerged.token.symbol = "USDC";
          usdcMerged.token.name = "USDC";
        } else {
          // Add amount from additional USDC
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

  // Fetch supported tokens
  useEffect(() => {
    const fetchSupportedTokens = async () => {
      try {
        setSupportedTokensLoading(true);
        const response = await kryptonWeb3Api.get('/erc20/supported-tokens');
        setSupportedTokens(response.data);
      } catch (err) {
        console.error("Failed to fetch supported tokens", err);
        // Fallback or handle error - maybe don't filter if fetch fails?
        // For now, let's just keep supportedTokens null
      } finally {
        setSupportedTokensLoading(false);
      }
    };
    fetchSupportedTokens();
  }, []);

  // Fetch token prices
  useEffect(() => {
    const fetchTokenPrices = async () => {
      try {
        setPricesLoading(true);
        const response = await kryptonWeb3Api.get('/subgraph/token-prices');
        const prices = response.data?.prices || {};
        setTokenPrices(prices);
      } catch (err) {
        console.error("Failed to fetch token prices", err);
      } finally {
        setPricesLoading(false);
      }
    };
    fetchTokenPrices();
  }, []);

  // Fetch portfolio history
  useEffect(() => {
    const fetchPortfolioHistory = async () => {
      if (!userWalletAddress) {
        setPortfolioLoading(false);
        return;
      }

      try {
        setPortfolioLoading(true);
        const response = await kryptonWeb3Api.get(`/subgraph/user/${userWalletAddress}/portfolio-history`, {
          params: { days: 30 }
        });
        const history = response.data?.token_history || {};
        setPortfolioHistory(history);
      } catch (err) {
        console.error("Failed to fetch portfolio history", err);
      } finally {
        setPortfolioLoading(false);
      }
    };
    fetchPortfolioHistory();
  }, [userWalletAddress]);

  const calculateTokenValues = async (tokenBalances: TokenBalance[], supportedData: SupportedTokensResponse) => {
    setPriceLoading(true);
    let totalValue = 0;
    const tokensWithValues: TokenWithValue[] = [];

    // Helper to extract addresses from either array of strings or object values
    const getAddresses = (data: any): string[] => {
      if (Array.isArray(data)) {
        return data.filter(item => typeof item === 'string');
      }
      if (typeof data === 'object' && data !== null) {
        return Object.values(data)
          .map((item: any) => item?.address)
          .filter((addr): addr is string => typeof addr === 'string');
      }
      return [];
    };

    // Extract addresses using helper
    const kTokensArr = getAddresses(supportedData.k_tokens);
    const customTokensArr = getAddresses(supportedData.custom_tokens);
    const strategyArr = getAddresses(supportedData.quant_strategies);

    const kTokensSet = new Set(kTokensArr.map(a => a.toLowerCase()));
    const customTokensSet = new Set(customTokensArr.map(a => a.toLowerCase()));
    const strategySet = new Set(strategyArr.map(a => a.toLowerCase()));

    try {
      for (const tokenBalance of tokenBalances) {
        const { amount, token } = tokenBalance;
        const tokenAmount = parseFloat(amount || "0");

        if (tokenAmount <= 0) continue;

        // Determine category and filter
        const address = token.tokenAddress?.toLowerCase();
        let category = "other";

        if (address) {
          if (kTokensSet.has(address)) category = "k_tokens";
          else if (customTokensSet.has(address)) category = "custom_tokens";
          else if (strategySet.has(address)) category = "quant_strategies";
        }

        // Get price from fetched prices or default to 0
        const tokenPrice = tokenPrices[token.symbol] || 0;

        // Calculate value for this token
        const tokenValue = tokenAmount * tokenPrice;
        totalValue += tokenValue;

        // Get portfolio history for this token
        const history = portfolioHistory[token.symbol] || [];

        // Add to tokens with values array
        tokensWithValues.push({
          ...tokenBalance,
          price: tokenPrice,
          value: tokenValue,
          category,
          portfolioHistory: history
        });
      }

      // Sort tokens by value (highest first)
      tokensWithValues.sort((a, b) => b.value - a.value);

      setTokenDetails(tokensWithValues);
      setTotalValue(totalValue);
    } catch (err) {
      setTokenDetails([]);
      setTotalValue(0);
    } finally {
      setPriceLoading(false);
    }
  };

  const convertMavcToHumanReadable = (balances: any[]) => {
    return balances;
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
    if (tokenBalances.length > 0 && supportedTokens && !supportedTokensLoading && Object.keys(tokenPrices).length > 0) {
      calculateTokenValues(tokenBalances, supportedTokens);
    } else if (!supportedTokensLoading && supportedTokens) {
      // If no balances but we have supported tokens data, clear details
      setTokenDetails([]);
      setTotalValue(0);
    }
  }, [balance, supportedTokens, supportedTokensLoading, tokenPrices, portfolioHistory]);

  const tokenBalances = getTokenBalances();

  // Check if all data is still loading
  const isFullyLoaded = !loading && !supportedTokensLoading && !pricesLoading && !portfolioLoading && !priceLoading;

  if (loading || supportedTokensLoading || pricesLoading || portfolioLoading) {
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

  // Only show "No Supported Tokens" if everything is fully loaded and there are still no tokens
  if (tokenDetails.length === 0 && isFullyLoaded) {
    return (
      <div className={`bg-zinc-900/80 backdrop-blur-xl rounded-3xl p-8 shadow-2xl border border-zinc-800 ${className}`}>
        <div className="text-center">
          <div className="w-16 h-16 bg-zinc-700/50 rounded-full flex items-center justify-center mx-auto mb-4">
            <FaCoins className="text-zinc-400 text-2xl" />
          </div>
          <h3 className="text-xl font-bold text-white mb-2">No Supported Tokens</h3>
          <p className="text-zinc-400">You don't have any supported tokens in your wallet.</p>
        </div>
      </div>
    );
  }

  const getTabLabel = (key: TabKey): string => {
    switch (key) {
      case 'k_tokens': return 'Krypton Tokens';
      case 'quant_strategies': return 'Tokenized Strategies';
      case 'other': return 'Other';
    }
  };

  const groupedTokens: Record<TabKey, TokenWithValue[]> = {
    k_tokens: tokenDetails.filter(t => t.category === 'k_tokens' || t.category === 'custom_tokens'),
    quant_strategies: tokenDetails.filter(t => t.category === 'quant_strategies'),
    other: tokenDetails.filter(t => t.category === 'other'),
  };

  const tabs: TabKey[] = ['k_tokens', 'quant_strategies', 'other'];
  const availableTabs = tabs.filter(tab => groupedTokens[tab].length > 0);

  // Ensure activeTab is valid; if not, pick first available
  const currentTab = availableTabs.includes(activeTab) ? activeTab : (availableTabs[0] || 'k_tokens');
  const currentTokens = groupedTokens[currentTab] || [];

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
      </div>

      {/* Horizontal Tabs */}
      {availableTabs.length > 0 && (
        <div className="flex justify-center space-x-2 mb-6">
          {availableTabs.map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all duration-200 ${
                currentTab === tab
                  ? 'bg-blue-600 text-white'
                  : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-300'
              }`}
            >
              {getTabLabel(tab)}
            </button>
          ))}
        </div>
      )}

      {/* Token List for Active Tab */}
      {currentTokens.length > 0 && (
        <div className="space-y-4 mb-6">
          {currentTokens.map((tokenDetail: TokenWithValue, index: number) => (
            <div
              key={`${tokenDetail.token.id}-${index}`}
              className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-6 hover:bg-zinc-700/50 transition-all duration-200"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="flex-shrink-0">
                    {getTokenIcon(tokenDetail.token.symbol)}
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-semibold text-white">
                      {tokenDetail.token.name || tokenDetail.token.symbol}
                    </h4>
                    <p className="text-zinc-400 text-xs">
                      {tokenDetail.token.symbol}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <>
                    <div className="text-base font-semibold text-white">
                      {formatTokenAmount(tokenDetail.amount, tokenDetail.token.decimals, tokenDetail.token.symbol)}
                    </div>
                    <div className="text-zinc-400 text-xs">
                      @ ${tokenDetail.price.toFixed(4)}
                    </div>
                    <div className="text-green-400 text-xs font-medium">
                      {formatValue(tokenDetail.value)}
                    </div>
                  </>
                </div>
              </div>

              {/* Portfolio Chart */}
              {tokenDetail.portfolioHistory && tokenDetail.portfolioHistory.length > 0 && (
                <div className="mt-4 flex justify-center">
                  <div className="w-full max-w-md">
                    <TokenPortfolioChart data={tokenDetail.portfolioHistory} />
                  </div>
                </div>
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