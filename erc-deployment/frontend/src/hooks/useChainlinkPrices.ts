import { useMemo } from 'react';
import { useReadContracts } from 'wagmi';
import type { Address } from 'viem';

// Chainlink price feeds on Sepolia (from chainlink-sepolia-feeds.json)
const CHAINLINK_FEEDS = {
  ETH_USD: '0x694AA1769357215DE4FAC081bf1f309aDC325306' as Address,
  USDC_USD: '0xA2F78ab2355fe2f984D808B5CeE7FD0A93D5270E' as Address,
};

export const useChainlinkPrices = () => {

  // Contracts to fetch prices directly from Chainlink feeds
  const priceContracts = useMemo(() => {
    return [
      {
        address: CHAINLINK_FEEDS.ETH_USD,
        abi: [
          {
            inputs: [],
            name: 'latestRoundData',
            outputs: [
              { internalType: 'uint80', name: 'roundId', type: 'uint80' },
              { internalType: 'int256', name: 'answer', type: 'int256' },
              { internalType: 'uint256', name: 'startedAt', type: 'uint256' },
              { internalType: 'uint256', name: 'updatedAt', type: 'uint256' },
              { internalType: 'uint80', name: 'answeredInRound', type: 'uint80' },
            ],
            stateMutability: 'view',
            type: 'function',
          },
        ],
        functionName: 'latestRoundData',
      } as const,
      {
        address: CHAINLINK_FEEDS.USDC_USD,
        abi: [
          {
            inputs: [],
            name: 'latestRoundData',
            outputs: [
              { internalType: 'uint80', name: 'roundId', type: 'uint80' },
              { internalType: 'int256', name: 'answer', type: 'int256' },
              { internalType: 'uint256', name: 'startedAt', type: 'uint256' },
              { internalType: 'uint256', name: 'updatedAt', type: 'uint256' },
              { internalType: 'uint80', name: 'answeredInRound', type: 'uint80' },
            ],
            stateMutability: 'view',
            type: 'function',
          },
        ],
        functionName: 'latestRoundData',
      } as const,
    ];
  }, []);

  const {
    data: priceData,
    refetch: refetchPrices,
    isLoading: pricesLoading,
    isFetching: pricesFetching,
  } = useReadContracts({
    contracts: priceContracts,
    query: { 
      enabled: priceContracts.length > 0,
      refetchInterval: 10000, // Refresh every 10 seconds
      refetchIntervalInBackground: true, // Continue refreshing when tab is not active
      staleTime: 5000, // Consider data stale after 5 seconds
    },
  });

  const ethPrice = useMemo(() => {
    const ethData = priceData?.[0]?.result as readonly [bigint, bigint, bigint, bigint, bigint] | undefined;
    if (!ethData || ethData[1] <= 0) return null;
    // Chainlink ETH/USD has 8 decimals
    return Number(ethData[1]) / 1e8;
  }, [priceData]);

  const usdcPrice = useMemo(() => {
    const usdcData = priceData?.[1]?.result as readonly [bigint, bigint, bigint, bigint, bigint] | undefined;
    if (!usdcData || usdcData[1] <= 0) return null;
    // Chainlink USDC/USD has 8 decimals
    return Number(usdcData[1]) / 1e8;
  }, [priceData]);

  const wethUsdcPrice = useMemo(() => {
    if (!ethPrice || !usdcPrice || usdcPrice === 0) return null;
    // WETH/USDC = (ETH/USD) / (USDC/USD)
    return ethPrice / usdcPrice;
  }, [ethPrice, usdcPrice]);

  // Calculate vault share price using the formula: 1 MAV = (0.5*USDC) + (0.5*WETH/USDC_value)
  const calculateVaultSharePrice = useMemo(() => {
    return (totalAssets?: bigint, totalSupply?: bigint, usdcDecimals = 6, shareDecimals = 18) => {
      // Always use Chainlink-based theoretical price if available
      if (wethUsdcPrice && ethPrice && usdcPrice) {
        // 1 MAV = (0.5*USDC) + (0.5*WETH/USDC_value)
        // This means: 0.5 USDC worth + 0.5 WETH worth (converted to USDC terms)
        const usdcComponent = 0.5; // 0.5 USDC worth
        const wethComponent = 0.5 * wethUsdcPrice; // 0.5 WETH worth in USDC terms
        return usdcComponent + wethComponent;
      }

      // Fallback: If vault has real data, use it
      if (totalAssets && totalSupply && totalSupply > 0n) {
        const assets = Number(totalAssets) / 10 ** usdcDecimals;
        const shares = Number(totalSupply) / 10 ** shareDecimals;
        if (shares > 0) {
          return assets / shares;
        }
      }

      // Final fallback
      return 1;
    };
  }, [wethUsdcPrice, ethPrice, usdcPrice]);

  const isLoading = pricesLoading || pricesFetching;

  return {
    ethPrice,
    usdcPrice,
    wethUsdcPrice,
    calculateVaultSharePrice,
    isLoading,
    isFetching: pricesFetching,
    refetchPrices,
    isHealthy: Boolean(ethPrice && usdcPrice && wethUsdcPrice),
  };
};
