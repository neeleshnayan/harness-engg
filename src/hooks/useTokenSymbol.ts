import { useState, useEffect } from 'react';
import { JsonRpcProvider, Contract, isAddress } from 'ethers';
import { DEFAULT_SEPOLIA_RPC_URL, USDC_ADDRESS, WETH_ADDRESS, XAG_RWA_ADDRESS } from '@/lib/constants';

// Simple in-memory cache to prevent redundant network calls across components.
// Keys are normalized to lowercase addresses for consistency.
const symbolCache: Record<string, string> = {
    [USDC_ADDRESS]: "USDC",
    [WETH_ADDRESS]: "WETH",
    [XAG_RWA_ADDRESS]: "XAG",
};

// Use a shared default Sepolia RPC URL (with env override).
// Note: Public RPCs can be rate-limited.
const RPC_URL = DEFAULT_SEPOLIA_RPC_URL;

const ERC20_ABI = [
    "function symbol() view returns (string)"
];

// Singleton provider instance to reuse connection
let providerInstance: JsonRpcProvider | null = null;
const getProvider = () => {
    if (!providerInstance) {
        providerInstance = new JsonRpcProvider(RPC_URL);
    }
    return providerInstance;
};

// Rate limiting: Max concurrent requests and request queue
let activeRequests = 0;
const MAX_CONCURRENT_REQUESTS = 3;
const requestQueue: Array<() => void> = [];

const executeWithRateLimit = async <T>(fn: () => Promise<T>): Promise<T> => {
    // If we're at the limit, queue this request
    if (activeRequests >= MAX_CONCURRENT_REQUESTS) {
        await new Promise<void>(resolve => requestQueue.push(resolve));
    }

    activeRequests++;
    try {
        return await fn();
    } finally {
        activeRequests--;
        // Process next queued request
        const next = requestQueue.shift();
        if (next) next();
    }
};

export const useTokenSymbol = (tokenAddress?: string) => {
    const [symbol, setSymbol] = useState<string>('');
    const [loading, setLoading] = useState<boolean>(false);

    useEffect(() => {
        if (!tokenAddress || !isAddress(tokenAddress)) {
            setSymbol('');
            return;
        }

        const normalizedAddress = tokenAddress.toLowerCase();

        // Check cache first
        if (symbolCache[normalizedAddress]) {
            setSymbol(symbolCache[normalizedAddress]);
            return;
        }

        let mounted = true;

        const fetchSymbol = async () => {
            setLoading(true);
            try {
                // Use rate limiting to prevent overwhelming the RPC endpoint
                await executeWithRateLimit(async () => {
                    // Use singleton provider instance to reuse connection
                    const provider = getProvider();
                    const contract = new Contract(tokenAddress, ERC20_ABI, provider);
                    const fetchedSymbol = await contract.symbol();

                    if (mounted) {
                        symbolCache[normalizedAddress] = fetchedSymbol;
                        setSymbol(fetchedSymbol);
                    }
                });
            } catch (error) {
                console.warn(`Failed to fetch symbol for ${tokenAddress}`, error);
                // Fallback: Use abbreviated address if fetch fails? Or just empty string.
                // Or maybe just let the caller handle default.
            } finally {
                if (mounted) setLoading(false);
            }
        };

        fetchSymbol();

        return () => {
            mounted = false;
        };
    }, [tokenAddress]);

    return { symbol, loading };
};
