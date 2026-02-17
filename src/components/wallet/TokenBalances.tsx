import React, { useState, useEffect, useMemo } from "react";
import { FaCoins, FaEthereum } from "react-icons/fa";
import { ChevronDown, Triangle } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, YAxis, Tooltip } from "recharts";
import { StrategyChartTooltip } from "@/components/charts/StrategyChartTooltip";
import api, { kryptonWeb3Api } from "@/lib/api";
import { Skeleton } from "@/components/ui/skeleton";
import { useRates } from "@/providers/RatesProvider";
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
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const [supportedTokens, setSupportedTokens] = useState<SupportedTokensResponse | null>(null);
  const [supportedTokensLoading, setSupportedTokensLoading] = useState(true);

  // Get rates from context
  const { tokens, getTokenAddressToSymbol } = useRates();
  const tokenAddressMap = getTokenAddressToSymbol();

  const getTokenIcon = (symbol: string) => {
    const upperSymbol = symbol.toUpperCase();
    
    // Map currency symbols to their SVG icons
    const currencyIconMap: Record<string, string> = {
      'KGBP': '/currencies/GBP.svg',
      'KUSD': '/currencies/Dollar.svg',
      'KEUR': '/currencies/Euro.svg',
      'KAED': '/currencies/Dirham.svg',
      'KINR': '/currencies/Rupee.svg',
      'GC': '/currencies/Gold.svg',
      'XAG': '/currencies/Silver.svg',
      'NVDA': '/currencies/nvidia.svg',
    };

    // Check if it's a k-token (remove 'k' prefix for lookup)
    if (upperSymbol.startsWith('K') && upperSymbol.length > 1) {
      const currencyKey = upperSymbol; // e.g., 'KGBP'
      if (currencyIconMap[currencyKey]) {
        return (
          <img src={currencyIconMap[currencyKey]} alt={symbol} className="w-10 h-10" />
        );
      }
    }

    // Check direct symbol matches (for non-k tokens)
    if (currencyIconMap[upperSymbol]) {
      return (
        <img src={currencyIconMap[upperSymbol]} alt={symbol} className="w-10 h-10" />
      );
    }

    // Special cases
    switch (upperSymbol) {
      case 'USDC':
        return (
          <img src="/currencies/USDC.svg" alt="USDC" className="w-10 h-10" />
        );
      case 'ETH':
        return <img src="/currencies/Eth.svg" alt="ETH" className="w-10 h-10" />;
      default:
        return <img src="/hedge_fund/Coin-Stack_24px_icon.svg" alt="Token" className="w-10 h-10" />;
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

  // Group tokens by category (must be before early returns for hooks order)
  const groupedTokens = useMemo<Record<TabKey, TokenWithValue[]>>(() => ({
    k_tokens: tokenDetails.filter(t => t.category === 'k_tokens' || t.category === 'custom_tokens'),
    quant_strategies: tokenDetails.filter(t => t.category === 'quant_strategies'),
    other: tokenDetails.filter(t => t.category === 'other'),
  }), [tokenDetails]);

  // Calculate category totals (must be before early returns for hooks order)
  const ccyTotal = useMemo(() => {
    return groupedTokens.k_tokens.reduce((sum, token) => sum + token.value, 0);
  }, [groupedTokens]);

  const rwaTotal = useMemo(() => {
    return groupedTokens.other.reduce((sum, token) => sum + token.value, 0);
  }, [groupedTokens]);

  // Prepare timeseries data for the chart (must be before early returns for hooks order)
  const portfolioTimeseries = useMemo(() => {
    if (!userWalletAddress || Object.keys(portfolioHistory).length === 0) return [];

    // Get all unique dates from all token histories
    const allDates = new Set<string>();
    Object.values(portfolioHistory).forEach((history: PortfolioDataPoint[]) => {
      history.forEach(point => allDates.add(point.date));
    });

    const sortedDates = Array.from(allDates).sort();

    // Calculate totals for each date
    return sortedDates.map(date => {
      let ccyValue = 0;
      let rwaValue = 0;

      // Sum CCY tokens
      groupedTokens.k_tokens.forEach(token => {
        const history = portfolioHistory[token.token.symbol] || [];
        const point = history.find(p => p.date === date);
        if (point) {
          ccyValue += point.value || 0;
        }
      });

      // Sum RWA tokens
      groupedTokens.other.forEach(token => {
        const history = portfolioHistory[token.token.symbol] || [];
        const point = history.find(p => p.date === date);
        if (point) {
          rwaValue += point.value || 0;
        }
      });

      return {
        date,
        total: ccyValue + rwaValue,
        ccy: ccyValue,
        rwa: rwaValue
      };
    });
  }, [portfolioHistory, groupedTokens, userWalletAddress]);

  // Check if all data is still loading
  const isFullyLoaded = !loading && !supportedTokensLoading && !pricesLoading && !portfolioLoading && !priceLoading;

  if (loading || supportedTokensLoading || pricesLoading || portfolioLoading) {
    return (
      <div className={`relative rounded-3xl overflow-hidden backdrop-blur-3xl border border-white/10 shadow-2xl ${className}`}>
        <div className="relative p-8 sm:p-10 text-center">
          <div className="animate-spin rounded-full h-10 w-10 border-2 border-white/20 border-t-white/60 mx-auto mb-4"></div>
          <p className="text-zinc-400/70 text-sm font-medium">Loading token balances...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`relative rounded-3xl overflow-hidden backdrop-blur-3xl border border-white/10 shadow-2xl ${className}`}>
        <div className="relative p-8 sm:p-10 text-center">
          <div className="w-16 h-16 flex items-center justify-center mx-auto mb-4">
            <img src="/hedge_fund/Coin-Stack_24px_icon.svg" alt="Error" className="w-16 h-16 opacity-60" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2 tracking-tight">Error Loading Tokens</h3>
          <p className="text-red-400/80 text-sm font-medium">{error}</p>
        </div>
      </div>
    );
  }

  // Only show "No Supported Tokens" if everything is fully loaded and there are still no tokens
  if (tokenDetails.length === 0 && isFullyLoaded) {
    return (
      <div className={`relative rounded-3xl overflow-hidden backdrop-blur-3xl border border-white/10 shadow-2xl ${className}`}>
        <div className="relative p-8 sm:p-10 text-center">
          <div className="w-16 h-16 bg-white/5 backdrop-blur-sm rounded-full flex items-center justify-center mx-auto mb-4 border border-white/10">
            <FaCoins className="text-zinc-400/70 text-2xl" />
          </div>
          <h3 className="text-xl font-semibold text-white mb-2 tracking-tight">No Supported Tokens</h3>
          <p className="text-zinc-400/70 text-sm font-medium">You don't have any supported tokens in your wallet.</p>
        </div>
      </div>
    );
  }

  const getTabLabel = (key: TabKey): string => {
    switch (key) {
      case 'k_tokens': return 'CCY tokens';
      case 'quant_strategies': return 'Tokenized Strategies';
      case 'other': return 'RWA tokens';
    }
  };

  const tabs: TabKey[] = ['k_tokens', 'quant_strategies', 'other'];
  const availableTabs = tabs.filter(tab => groupedTokens[tab].length > 0);

  // Ensure activeTab is valid; if not, pick first available
  const currentTab = availableTabs.includes(activeTab) ? activeTab : (availableTabs[0] || 'k_tokens');
  const currentTokens = groupedTokens[currentTab] || [];

  return (
    <div className={`relative rounded-3xl overflow-hidden backdrop-blur-3xl border border-white/10 shadow-2xl ${className}`}>
      <div className="relative p-8 sm:p-10">
        {/* Total Value Header - Clickable */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full mb-6 group cursor-pointer"
        >
          <div className="flex items-center justify-center gap-3 mb-4">
            <h3 className="text-xl sm:text-2xl font-semibold text-white/90 tracking-tight group-hover:text-white transition-colors">
              Token Portfolio
            </h3>
            <ChevronDown
              className={`w-5 h-5 text-zinc-400/70 transition-transform duration-300 ${
                isExpanded ? 'rotate-180' : ''
              }`}
            />
          </div>
          
          {/* Balance Values */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-bold mb-1 tracking-tight" style={{ color: '#90E7EE' }}>
                {priceLoading || loading ? (
                  <Skeleton className="h-8 w-32 bg-white/10 mx-auto" />
                ) : (
                  formatValue(totalValue)
                )}
              </div>
              <p className="text-zinc-400/80 text-xs font-medium">Total</p>
            </div>
            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-bold mb-1 tracking-tight text-white">
                {priceLoading || loading ? (
                  <Skeleton className="h-8 w-32 bg-white/10 mx-auto" />
                ) : (
                  formatValue(ccyTotal)
                )}
              </div>
              <p className="text-zinc-400/80 text-xs font-medium">CCY</p>
            </div>
            <div className="text-center">
              <div className="text-2xl sm:text-3xl font-bold mb-1 tracking-tight text-white">
                {priceLoading || loading ? (
                  <Skeleton className="h-8 w-32 bg-white/10 mx-auto" />
                ) : (
                  formatValue(rwaTotal)
                )}
              </div>
              <p className="text-zinc-400/80 text-xs font-medium">RWA</p>
            </div>
          </div>

          {/* Timeseries Chart */}
          {portfolioTimeseries.length > 0 && (
            <div className="w-full h-32 mb-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={portfolioTimeseries} margin={{ top: 5, right: 0, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="colorTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#90E7EE" stopOpacity={0.4} />
                      <stop offset="100%" stopColor="#90E7EE" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorCCY" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#ffffff" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#ffffff" stopOpacity={0} />
                    </linearGradient>
                    <linearGradient id="colorRWA" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <YAxis hide domain={['dataMin', 'dataMax']} />
                  <Tooltip
                    content={(props) => {
                      if (!props.active || !props.payload || !props.payload.length) return null;
                      const data = props.payload[0].payload;
                      
                      // Format date for tooltip
                      const formatTooltipDate = (date: string) => {
                        if (!date) return '';
                        try {
                          const dateObj = new Date(date);
                          return dateObj.toLocaleDateString('en-US', { 
                            month: 'short', 
                            day: 'numeric',
                            year: dateObj.getFullYear() !== new Date().getFullYear() ? 'numeric' : undefined
                          });
                        } catch {
                          return date;
                        }
                      };
                      
                      return (
                        <StrategyChartTooltip
                          active={props.active}
                          payload={[
                            { name: 'Total', value: data.total, color: '#90E7EE' },
                            { name: 'CCY', value: data.ccy, color: '#ffffff' },
                            { name: 'RWA', value: data.rwa, color: '#a78bfa' }
                          ]}
                          label={props.label}
                          labelFormatted={formatTooltipDate(data.date)}
                          valueFormatter={(val) => formatValue(val)}
                        />
                      );
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="total"
                    stroke="#90E7EE"
                    strokeWidth={2}
                    fill="url(#colorTotal)"
                    fillOpacity={1}
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="ccy"
                    stroke="#ffffff"
                    strokeWidth={1.5}
                    fill="url(#colorCCY)"
                    fillOpacity={1}
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="rwa"
                    stroke="#a78bfa"
                    strokeWidth={1.5}
                    fill="url(#colorRWA)"
                    fillOpacity={1}
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </button>

        {/* Collapsible Content */}
        <div
          className={`overflow-hidden transition-all duration-500 ease-in-out ${
            isExpanded ? 'max-h-[5000px] opacity-100' : 'max-h-0 opacity-0'
          }`}
        >
          {/* Horizontal Tabs */}
          {availableTabs.length > 0 && (
            <div className="flex justify-center gap-2 mb-8">
              {availableTabs.map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`relative overflow-hidden px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${
                    currentTab === tab
                      ? 'shadow-lg backdrop-blur-sm'
                      : 'text-zinc-400/70 hover:text-zinc-300 bg-white/5 hover:bg-white/10 backdrop-blur-sm'
                  }`}
                  style={currentTab === tab ? { 
                    backgroundColor: '#90E7EE',
                    color: '#001C1B'
                  } : {}}
                >
                  {tab === 'k_tokens' && currentTab === tab && (
                    <img src="/hedge_fund/Tokens transparent box.svg" alt="" className="absolute inset-0 w-full h-full object-cover pointer-events-none opacity-60" />
                  )}
                  <span className="relative z-10">{getTabLabel(tab)}</span>
                </button>
              ))}
            </div>
          )}

          {/* Token List for Active Tab */}
          {currentTokens.length > 0 && (
          <div className="space-y-3 sm:space-y-4 lg:space-y-5 mb-6 lg:mb-8">
            {currentTokens.map((tokenDetail: TokenWithValue, index: number) => (
              <div
                key={`${tokenDetail.token.id}-${index}`}
                className="group relative rounded-2xl overflow-hidden bg-gradient-to-br from-white/[0.06] to-white/[0.02] backdrop-blur-xl border border-white/10 transition-all duration-300 hover:bg-white/[0.08] hover:border-white/20 "
                style={{
                  boxShadow: 'inset 0 1px 0 rgba(255, 255, 255, 0.1)'
                }}
              >
                <div className="relative p-4 sm:p-5 lg:p-7 xl:p-8">
                  {/* Mobile: Stacked Layout, Desktop: Side by Side */}
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 sm:gap-5 lg:gap-6 mb-5 lg:mb-6">
                    {/* Left: Icon and Token Info */}
                    <div className="flex items-start gap-3 sm:gap-4 lg:gap-5 flex-1 min-w-0">
                      <div className="flex-shrink-0">
                        {getTokenIcon(tokenDetail.token.symbol)}
                      </div>
                      <div className="flex-1 min-w-0 pt-0.5 lg:pt-1">
                        <h4 className="text-base sm:text-lg lg:text-xl xl:text-2xl font-semibold text-white mb-1 sm:mb-1.5 lg:mb-2 tracking-tight truncate drop-shadow-sm">
                          {tokenDetail.token.name || tokenDetail.token.symbol}
                        </h4>
                        <p className="text-zinc-300/80 text-xs sm:text-sm lg:text-base font-medium drop-shadow-sm">
                          {tokenDetail.token.symbol}
                        </p>
                      </div>
                    </div>

                    {/* Right: Balance and Value - Mobile: Full Width, Desktop: Right Aligned */}
                    <div className="flex flex-col sm:text-right sm:flex-shrink-0 w-full sm:w-auto space-y-2 sm:space-y-2.5 lg:space-y-3">
                      {/* Quantity with Label */}
                      <div>
                        <div className="text-xs text-zinc-400/70 mb-1 sm:hidden">Balance</div>
                        <div className="text-lg sm:text-xl lg:text-2xl xl:text-3xl font-semibold text-white tracking-tight drop-shadow-sm leading-tight">
                          {formatTokenAmount(tokenDetail.amount, tokenDetail.token.decimals, tokenDetail.token.symbol)} <span className="text-zinc-300/70 text-sm sm:text-base lg:text-lg xl:text-xl font-medium">{tokenDetail.token.symbol}</span>
                        </div>
                      </div>
                      
                      {/* Price and 24hr Change */}
                      <div className="sm:text-right">
                        <div className="text-xs text-zinc-400/70 mb-1 sm:hidden">Price</div>
                        <div className="flex items-baseline gap-2 sm:gap-2.5 lg:gap-3 sm:justify-end">
                          <div className="text-zinc-300/90 text-xs sm:text-sm lg:text-base font-medium drop-shadow-sm">
                            ${tokenDetail.price.toFixed(4)}
                          </div>
                          {(() => {
                            // Get token symbol - check address map first, then fallback to token symbol
                            const tokenAddress = tokenDetail.token.tokenAddress?.toLowerCase();
                            const rateSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : tokenDetail.token.symbol;
                            const tokenRate = rateSymbol ? tokens[rateSymbol] : null;
                            const percentChange = tokenRate?.percentage_change ?? null;
                            const direction = tokenRate?.direction ?? 'same';
                            
                            if (percentChange !== null && Math.abs(percentChange) >= 0.01) {
                              const isPositive = direction === 'up' || percentChange > 0;
                              return (
                                <div className={`flex items-center gap-1 text-xs sm:text-sm lg:text-base font-semibold ${
                                  isPositive ? 'text-emerald-400' : 'text-red-400'
                                }`}>
                                  <Triangle 
                                    className={`h-2.5 w-2.5 sm:h-3 sm:w-3 lg:h-3.5 lg:w-3.5 ${isPositive ? '' : 'rotate-180'}`}
                                    fill={isPositive ? '#22c55e' : '#ef4444'}
                                  />
                                  <span>{Math.abs(percentChange).toFixed(2)}%</span>
                                  <span className="text-zinc-400/60 text-[10px] ml-0.5 sm:hidden">24h</span>
                                </div>
                              );
                            }
                            return null;
                          })()}
                        </div>
                      </div>
                      
                      {/* Total Value with Label */}
                      <div>
                        <div className="text-xs text-zinc-400/70 mb-1 sm:hidden">Total Value</div>
                        <div className={`text-base sm:text-lg lg:text-xl xl:text-2xl font-semibold drop-shadow-sm leading-tight ${
                          (() => {
                            // Get rate change direction to determine color
                            const tokenAddress = tokenDetail.token.tokenAddress?.toLowerCase();
                            const rateSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : tokenDetail.token.symbol;
                            const tokenRate = rateSymbol ? tokens[rateSymbol] : null;
                            const direction = tokenRate?.direction ?? 'same';
                            const percentChange = tokenRate?.percentage_change ?? null;
                            
                            // Use rate direction if available, otherwise fallback to value >= 0
                            if (direction === 'up' || (percentChange !== null && percentChange > 0)) {
                              return 'text-emerald-400';
                            } else if (direction === 'down' || (percentChange !== null && percentChange < 0)) {
                              return 'text-red-400';
                            }
                            // Default: green for positive value, red for negative
                            return tokenDetail.value >= 0 ? 'text-emerald-400' : 'text-red-400';
                          })()
                        }`}>
                          {formatValue(tokenDetail.value)}
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Portfolio Chart */}
                  {tokenDetail.portfolioHistory && tokenDetail.portfolioHistory.length > 0 && (() => {
                    // Get rate change direction for chart color
                    const tokenAddress = tokenDetail.token.tokenAddress?.toLowerCase();
                    const rateSymbol = tokenAddress ? tokenAddressMap[tokenAddress] : tokenDetail.token.symbol;
                    const tokenRate = rateSymbol ? tokens[rateSymbol] : null;
                    const direction = tokenRate?.direction ?? 'same';
                    
                    return (
                      <div className="mt-5 lg:mt-6 pt-5 lg:pt-6 border-t border-white/10 lg:border-white/15">
                        <div className="w-full">
                          <TokenPortfolioChart 
                            data={tokenDetail.portfolioHistory} 
                            rateChangeDirection={direction}
                          />
                        </div>
                      </div>
                    );
                  })()}
                </div>
              </div>
            ))}
          </div>
          )}

          {/* Footer with token count */}
          <div className="pt-6 border-t border-white/5">
            <div className="text-center">
              <p className="text-zinc-400/60 text-xs font-medium">
                {tokenDetails.length} {tokenDetails.length === 1 ? 'token' : 'tokens'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TokenBalances;