import { useState, useEffect } from 'react';
import { JsonRpcProvider, Contract, isAddress } from 'ethers';

// Simple in-memory cache to prevent redundant network calls across components
const symbolCache: Record<string, string> = {
    "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238": "USDC", // Common Sepolia USDC
    "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14": "WETH", // Common Sepolia WETH (one of them)
    "0x326251D13257939170769a8904614381736a0950": "XAG" // Known XAG from user request to pre-fill
};

// Use an environment variable or fallback to a reliable public Sepolia RPC
// Note: Public RPCs can be rate-limited.
const RPC_URL = process.env.NEXT_PUBLIC_RPC_URL || "https://ethereum-sepolia-rpc.publicnode.com";

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

        // Check cache first
        if (symbolCache[tokenAddress]) {
            setSymbol(symbolCache[tokenAddress]);
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
                        symbolCache[tokenAddress] = fetchedSymbol;
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
