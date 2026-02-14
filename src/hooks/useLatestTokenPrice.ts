import { useQuery } from '@tanstack/react-query';
import { JsonRpcProvider, Contract, isAddress } from 'ethers';

const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com";

let providerInstance: JsonRpcProvider | null = null;
const getProvider = () => {
    if (!providerInstance) {
        providerInstance = new JsonRpcProvider(RPC_URL);
    }
    return providerInstance;
};

const VAULT_ABI = [
    "function totalAssets() view returns (uint256)",
    "function totalSupply() view returns (uint256)"
];

const fetchTokenPrice = async (strategyAddress: string): Promise<number> => {
    const provider = getProvider();
    const contract = new Contract(strategyAddress, VAULT_ABI, provider);

    let totalAssets: bigint;
    let totalSupply: bigint;

    try {
        [totalAssets, totalSupply] = await Promise.all([
            contract.totalAssets(),
            contract.totalSupply(),
        ]);
    } catch (err) {
        // If the provider connection went stale, reset and retry once
        providerInstance = null;
        const freshProvider = getProvider();
        const freshContract = new Contract(strategyAddress, VAULT_ABI, freshProvider);
        [totalAssets, totalSupply] = await Promise.all([
            freshContract.totalAssets(),
            freshContract.totalSupply(),
        ]);
    }

    if (totalSupply.toString() === '0') return 1.0;
    // Both totalAssets and totalSupply use 6 decimals (USDC-based vaults),
    // so they cancel out and the ratio is the price directly.
    return Number(totalAssets) / Number(totalSupply);
};

export const useLatestTokenPrice = (strategyAddress?: string) => {
    const enabled = Boolean(strategyAddress && isAddress(strategyAddress));
    const { data: price, isLoading, error, dataUpdatedAt, isFetching } = useQuery<number, Error>({
        queryKey: ['liveTokenPrice', strategyAddress],
        queryFn: () => fetchTokenPrice(strategyAddress!),
        enabled,
        refetchInterval: enabled ? 15_000 : false,
        staleTime: 10_000,
        refetchOnWindowFocus: false,
        retry: 2,
    });
    return { price: price ?? null, isLoading, error, dataUpdatedAt, isFetching, enabled };
};
