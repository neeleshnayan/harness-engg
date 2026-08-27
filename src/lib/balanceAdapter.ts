// Utility to transform subgraph balance response to frontend format
// This adapter ensures compatibility between the new subgraph API and existing frontend components

export interface SubgraphBalance {
  symbol: string;
  address: string;
  decimals: number;
  balance: number;
  raw_balance: string;
  updated_at: number;
}

export interface SubgraphBalanceResponse {
  wallet_address: string;
  balances: SubgraphBalance[];
}

export interface TokenBalance {
  amount: string;
  token: {
    id?: string;
    name: string;
    blockchain: string;
    decimals: number;
    isNative?: boolean;
    symbol: string;
    tokenAddress?: string;
    standard?: string;
    updateDate?: string;
    createDate?: string;
  };
  updateDate?: string;
}

export interface FrontendBalanceFormat {
  tokenBalances: TokenBalance[];
}

/**
 * Transform subgraph balance response to the format expected by frontend components
 * @param subgraphResponse - Response from the subgraph API
 * @returns Balance data in the format expected by frontend components
 */
export function transformSubgraphBalanceToFrontend(
  subgraphResponse: SubgraphBalanceResponse
): FrontendBalanceFormat {
  const tokenBalances: TokenBalance[] = subgraphResponse.balances.map((balance) => {
    // Determine blockchain based on symbol or default to ETH-SEPOLIA
    const blockchain = "ETH-SEPOLIA";

    // Determine if token is native (ETH)
    const isNative = balance.symbol === "ETH" || balance.symbol === "ETH-SEPOLIA";

    // Determine token standard
    const standard = isNative ? undefined : "ERC20";

    // Create token name from symbol
    const tokenName = balance.symbol === "USDC"
      ? "USD Coin"
      : balance.symbol.startsWith("k")
      ? `Krypton ${balance.symbol.substring(1).toUpperCase()}`
      : balance.symbol;

    return {
      amount: balance.balance.toString(),
      token: {
        name: tokenName,
        blockchain: blockchain,
        decimals: balance.decimals,
        isNative: isNative,
        symbol: balance.symbol,
        tokenAddress: balance.address,
        standard: standard,
      },
    };
  });

  return {
    tokenBalances,
  };
}

/**
 * Fetch balance from subgraph API and transform to frontend format
 * @param walletAddress - Wallet address to fetch balance for
 * @param kryptonWeb3ApiBaseUrl - Base URL for Krypton Web3 API (e.g., process.env.NEXT_PUBLIC_KRYPTON_WEB3_API_URL)
 * @returns Balance data in frontend format
 */
/* `fetchBalanceFromSubgraph` removed 2026-08-27: no consumer. It was the only
   caller of `transformSubgraphBalanceToFrontend` from outside this module;
   that transform stays, because it IS consumed here. */
