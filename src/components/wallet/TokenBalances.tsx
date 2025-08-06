import React from "react";
import { FaCoins, FaEthereum, FaSync } from "react-icons/fa";

interface TokenBalance {
  token: {
    id: string;
    symbol: string;
    name: string;
    decimals: number;
    blockchain: string;
  };
  amount: string;
}

interface TokenBalancesProps {
  balance: any;
  loading?: boolean;
  error?: string | null;
  className?: string;
  onRefresh?: () => void;
}

const TokenBalances: React.FC<TokenBalancesProps> = ({ 
  balance, 
  loading = false, 
  error = null, 
  className = "",
  onRefresh
}) => {
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
      // For USDC, show with 2 decimal places
      if (symbol.toUpperCase() === 'USDC') {
        return `$${numAmount.toFixed(2)}`;
      } else if (symbol.toUpperCase() === 'TRNSK') {
        return `$${numAmount.toFixed(2)} USDC`;
      }
      return `${numAmount.toFixed(2)}`;
      
      // // For ETH, show with 4 decimal places
      // if (symbol.toUpperCase() === 'ETH') {
      //   return `${numAmount.toFixed(4)} ETH`;
      // }
      
      // // For other tokens, show with appropriate decimals
      // return `${numAmount.toFixed(decimals || 2)} ${symbol}`;
    } catch (error) {
      return `${amount} ${symbol}`;
    }
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
  
  
  const getTokenBalances = () => {
    if (!balance || !Array.isArray(balance.tokenBalances)) {
      return [];
    }
    
    var balances = balance.tokenBalances.filter((tokenBalance: TokenBalance) => {
      const amount = parseFloat(tokenBalance.amount);
      return !isNaN(amount) && amount > 0;
    });
    balances = mergeTrnskIntoUsdc(balances)
    return balances
  };

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
      {/* <div className="text-center mb-6">
        <div className="flex items-center justify-center mb-4">
          <FaCoins className="text-2xl text-yellow-400 mr-3" />
          <h3 className="text-2xl font-bold text-white">Your Token Portfolio</h3>
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={loading}
              className="ml-4 p-2 bg-zinc-800/60 hover:bg-zinc-700/80 text-zinc-300 hover:text-white rounded-xl border border-zinc-700/50 hover:border-zinc-600/50 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Refresh token balances"
            >
              <FaSync className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          )}
        </div>
        <p className="text-zinc-400">All tokens in your wallet</p>
      </div> */}
      
      <div className="space-y-4">
        {tokenBalances.map((tokenBalance: TokenBalance, index: number) => (
          tokenBalance.token.symbol !== "ETH-SEPOLIA" && 
          <div 
            key={`${tokenBalance.token.id}-${index}`}
            className="bg-zinc-800/50 backdrop-blur-sm border border-zinc-700/50 rounded-2xl p-6 hover:bg-zinc-700/50 transition-all duration-200"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4">
                <div className="flex-shrink-0">
                  {getTokenIcon(tokenBalance.token.symbol)}
                </div>
                <div className="flex-1">
                  <h4 className="text-lg font-bold text-white">
                    {tokenBalance.token.name || tokenBalance.token.symbol}
                  </h4>
                  <p className="text-zinc-400 text-sm">
                    {tokenBalance.token.symbol} • {tokenBalance.token.blockchain}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <div className="text-xl font-bold text-white">
                  {formatTokenAmount(tokenBalance.amount, tokenBalance.token.decimals, tokenBalance.token.symbol)}
                </div>
                {/* <div className="text-zinc-400 text-sm">
                  Raw: {tokenBalance.amount}
                </div> */}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* <div className="mt-6 pt-4 border-t border-zinc-700/50">
        <div className="text-center">
          <p className="text-zinc-400 text-sm">
            Total tokens: {tokenBalances.length}
          </p>
        </div>
      </div> */}
    </div>
  );
};

export default TokenBalances; 