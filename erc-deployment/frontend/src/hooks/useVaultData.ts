import { useCallback, useMemo } from 'react';
import { useAccount, useReadContracts } from 'wagmi';
import type { Address } from 'viem';
import { env } from '@/config/env';
import { vaultAbi } from '@/abi/vault';
import { erc20Abi } from '@/abi/erc20';

export const useVaultData = () => {
  const { address } = useAccount();
  const vaultAddress = env.addresses.vault as Address | undefined;
  const usdcAddress = env.addresses.usdc as Address | undefined;

  const vaultContracts = useMemo(() => {
    if (!vaultAddress) return [];
    return [
      { address: vaultAddress, abi: vaultAbi, functionName: 'totalAssets' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'totalSupply' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'usdcHeld' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'wethHeld' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'getActualBalances' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'getCurrentAllocation' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'name' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'symbol' } as const,
      { address: vaultAddress, abi: vaultAbi, functionName: 'decimals' } as const,
    ];
  }, [vaultAddress]);

  const {
    data: vaultData,
    refetch: refetchVault,
    isLoading: vaultLoading,
    isFetching: vaultFetching,
  } = useReadContracts({
    contracts: vaultContracts,
    query: { enabled: vaultContracts.length > 0 },
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
    query: { enabled: tokenContracts.length > 0 },
  });

  const userContracts = useMemo(() => {
    if (!address || !vaultAddress || !usdcAddress) return [];
    return [
      { address: vaultAddress, abi: vaultAbi, functionName: 'balanceOf', args: [address] } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'balanceOf', args: [address] } as const,
      { address: usdcAddress, abi: erc20Abi, functionName: 'allowance', args: [address, vaultAddress] } as const,
    ];
  }, [address, vaultAddress, usdcAddress]);

  const {
    data: userData,
    refetch: refetchUser,
    isLoading: userLoading,
    isFetching: userFetching,
  } = useReadContracts({
    contracts: userContracts,
    query: { enabled: userContracts.length > 0 },
  });

  const totalAssets = vaultData?.[0]?.result as bigint | undefined;
  const totalSupply = vaultData?.[1]?.result as bigint | undefined;
  const usdcHeld = vaultData?.[2]?.result as bigint | undefined;
  const wethHeld = vaultData?.[3]?.result as bigint | undefined;
  const actualBalances = vaultData?.[4]?.result as readonly [bigint, bigint] | undefined;
  const allocation = vaultData?.[5]?.result as readonly [bigint, bigint] | undefined;
  const vaultName = vaultData?.[6]?.result as string | undefined;
  const vaultSymbol = vaultData?.[7]?.result as string | undefined;
  const shareDecimals = (vaultData?.[8]?.result as number | undefined) ?? 18;

  const usdcDecimals = (tokenData?.[0]?.result as number | undefined) ?? 6;
  const usdcSymbol = (tokenData?.[1]?.result as string | undefined) ?? 'USDC';
  const usdcName = (tokenData?.[2]?.result as string | undefined) ?? 'USD Coin';

  const userShares = userData?.[0]?.result as bigint | undefined;
  const userUsdcBalance = userData?.[1]?.result as bigint | undefined;
  const userAllowance = userData?.[2]?.result as bigint | undefined;

  const userShareValue = useMemo(() => {
    if (!userShares || !totalSupply || !totalAssets || totalSupply === 0n) return 0n;
    return (userShares * totalAssets) / totalSupply;
  }, [totalAssets, totalSupply, userShares]);

  const allocationPercentages = allocation
    ? { usdc: Number(allocation[0]), weth: Number(allocation[1]) }
    : undefined;

  const refetchAll = useCallback(() => {
    void refetchVault();
    void refetchToken();
    void refetchUser();
  }, [refetchToken, refetchUser, refetchVault]);

  return {
    isReady: Boolean(vaultAddress && usdcAddress),
    vaultAddress,
    usdcAddress,
    vault: {
      name: vaultName,
      symbol: vaultSymbol,
      totalAssets,
      totalSupply,
      usdcHeld,
      wethHeld,
      actual: {
        usdc: actualBalances?.[0],
        weth: actualBalances?.[1],
      },
      allocation: allocationPercentages,
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
