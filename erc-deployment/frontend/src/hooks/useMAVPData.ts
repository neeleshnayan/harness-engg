import { useCallback, useMemo } from 'react';
import { useAccount, useReadContracts } from 'wagmi';
import type { Address } from 'viem';
import { env } from '@/config/env';
import { mavpVaultAbi } from '@/abi/mavpVault';
import { erc20Abi } from '@/abi/erc20';

export const useMAVPData = () => {
  const { address } = useAccount();
  const mavpVaultAddress = env.addresses.mavpVault as Address | undefined;
  const usdcAddress = env.addresses.usdc as Address | undefined;

  const vaultContracts = useMemo(() => {
    if (!mavpVaultAddress) return [];
    return [
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'totalAssets' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'totalSupply' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'usdcHeld' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'assetCount' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'getCurrentAllocation' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'name' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'symbol' } as const,
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'decimals' } as const,
    ];
  }, [mavpVaultAddress]);

  const {
    data: vaultData,
    refetch: refetchVault,
    isLoading: vaultLoading,
    isFetching: vaultFetching,
  } = useReadContracts({
    contracts: vaultContracts,
    query: { 
      enabled: vaultContracts.length > 0,
      refetchInterval: 15000, // Refresh every 15 seconds
      refetchIntervalInBackground: true,
      staleTime: 10000, // Consider data stale after 10 seconds
    },
  });

  const tokenContracts = useMemo(() => {
    if (!usdcAddress) return [];
    return [
      { address: usdcAddress, abi: erc20Abi, functionName: 'decimals' } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'symbol' } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'name' } as const,
    ];
  }, [usdcAddress]);

  const { data: tokenData, refetch: refetchToken } = useReadContracts({
    contracts: tokenContracts,
    query: { 
      enabled: tokenContracts.length > 0,
      refetchInterval: 30000, // Refresh every 30 seconds (token data changes less frequently)
      refetchIntervalInBackground: true,
      staleTime: 20000,
    },
  });

  const userContracts = useMemo(() => {
    if (!address || !mavpVaultAddress || !usdcAddress) return [];
    return [
      { address: mavpVaultAddress, abi: mavpVaultAbi, functionName: 'balanceOf', args: [address] } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'balanceOf', args: [address] } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'allowance', args: [address, mavpVaultAddress] } as const,
    ];
  }, [address, mavpVaultAddress, usdcAddress]);

  const {
    data: userData,
    refetch: refetchUser,
    isLoading: userLoading,
    isFetching: userFetching,
  } = useReadContracts({
    contracts: userContracts,
    query: { 
      enabled: userContracts.length > 0,
      refetchInterval: 20000, // Refresh every 20 seconds
      refetchIntervalInBackground: true,
      staleTime: 15000,
    },
  });

  // Asset info contracts - get details for each asset in the portfolio
  const assetCount = vaultData?.[3]?.result as number | undefined;
  const assetInfoContracts = useMemo(() => {
    if (!mavpVaultAddress || !assetCount) return [];
    const contracts = [];
    for (let i = 0; i < assetCount; i++) {
      contracts.push({
        address: mavpVaultAddress,
        abi: mavpVaultAbi,
        functionName: 'getAssetInfo',
        args: [i],
      } as const);
    }
    return contracts;
  }, [mavpVaultAddress, assetCount]);

  const { data: assetInfoData, refetch: refetchAssetInfo } = useReadContracts({
    contracts: assetInfoContracts,
    query: { 
      enabled: assetInfoContracts.length > 0,
      refetchInterval: 25000, // Refresh every 25 seconds
      refetchIntervalInBackground: true,
      staleTime: 20000,
    },
  });

  const totalAssets = vaultData?.[0]?.result as bigint | undefined;
  const totalSupply = vaultData?.[1]?.result as bigint | undefined;
  const usdcHeld = vaultData?.[2]?.result as bigint | undefined;
  const allocation = vaultData?.[4]?.result as readonly [readonly Address[], readonly bigint[]] | undefined;
  const vaultName = vaultData?.[5]?.result as string | undefined;
  const vaultSymbol = vaultData?.[6]?.result as string | undefined;
  const shareDecimals = (vaultData?.[7]?.result as number | undefined) ?? 18;

  const usdcDecimals = (tokenData?.[0]?.result as number | undefined) ?? 6;
  const usdcSymbol = (tokenData?.[1]?.result as string | undefined) ?? 'USDC';
  const usdcName = (tokenData?.[2]?.result as string | undefined) ?? 'USD Coin';

  const userShares = userData?.[0]?.result as bigint | undefined;
  const userUsdcBalance = userData?.[1]?.result as bigint | undefined;
  const userAllowance = userData?.[2]?.result as bigint | undefined;

  // Debug logging
  console.log('MAVP Data Debug:', {
    address,
    mavpVaultAddress,
    usdcAddress,
    userShares: userShares?.toString(),
    userUsdcBalance: userUsdcBalance?.toString(),
    userAllowance: userAllowance?.toString(),
    userDataLength: userData?.length,
  });

  const userShareValue = useMemo(() => {
    if (!userShares || !totalSupply || !totalAssets || totalSupply === 0n) return 0n;
    return (userShares * totalAssets) / totalSupply;
  }, [totalAssets, totalSupply, userShares]);

  // Process asset info data
  const assets = useMemo(() => {
    if (!assetInfoData || !assetInfoData.length) return [];
    return assetInfoData.map((data, index) => {
      const result = data.result as readonly [Address, bigint, bigint, bigint] | undefined;
      if (!result) return null;
      return {
        index,
        token: result[0] as string,
        allocationBps: result[1],
        tokenBalance: result[2],
        usdcBookValue: result[3],
      };
    }).filter((item): item is NonNullable<typeof item> => item !== null);
  }, [assetInfoData]);

  // Process allocation data
  const allocationData = useMemo(() => {
    if (!allocation) return undefined;
    const [tokens, allocationBps] = allocation;
    return tokens.map((token, index) => ({
      token,
      allocationBps: Number(allocationBps[index]),
      percentage: Number(allocationBps[index]) / 100, // Convert from BPS to percentage
    }));
  }, [allocation]);

  const refetchAll = useCallback(() => {
    void refetchVault();
    void refetchToken();
    void refetchUser();
    void refetchAssetInfo();
  }, [refetchToken, refetchUser, refetchVault, refetchAssetInfo]);

  return {
    isReady: Boolean(mavpVaultAddress && usdcAddress),
    mavpVaultAddress,
    usdcAddress,
    vault: {
      name: vaultName,
      symbol: vaultSymbol,
      totalAssets,
      totalSupply,
      usdcHeld,
      assetCount,
      assets,
      allocation: allocationData,
      shareDecimals,
    },
    usdc: {
      decimals: usdcDecimals,
      symbol: usdcSymbol,
      name: usdcName,
      allowance: userAllowance,
      balance: userUsdcBalance,
    },
    user: {
      address,
      shares: userShares,
      shareValue: userShareValue,
    },
    states: {
      vaultLoading: vaultLoading || vaultFetching,
      userLoading: userLoading || userFetching,
    },
    refetchAll,
  };
};
