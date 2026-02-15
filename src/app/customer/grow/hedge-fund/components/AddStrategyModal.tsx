import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, CheckCircle, AlertCircle } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { ethers } from "ethers";

// Add specific type for window.ethereum to avoid TS errors
declare global {
    interface Window {
        ethereum?: any;
    }
}

interface AddStrategyModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export function AddStrategyModal({ isOpen, onClose, onSuccess }: AddStrategyModalProps) {
    const [step, setStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [txHash, setTxHash] = useState<string | null>(null);
    const [factoryAddress, setFactoryAddress] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        name: "",
        symbol: "",
        assetAddress: "0x1c7D4B196Cb0C7B01d743Fbc6116a902379C7238", // USDC Sepolia
        targetAddress: "", // Token B
        vaultAddress: "", // Underlying Yearn Vault - Not used in UI but kept for type compatibility if needed
        poolAddress: "", // Specific Uniswap V3 Pool
    });

    const { toast } = useToast();

    // Fetch Factory Address on mount
    useEffect(() => {
        const fetchConfig = async () => {
            if (!isOpen) return;
            try {
                const { hedgeFundApi } = await import("@/lib/api");
                const res = await hedgeFundApi.get("/api/v1/config/contracts");
                if (res.data && res.data.data && res.data.data.yearn_factory_address) {
                    setFactoryAddress(res.data.data.yearn_factory_address);
                } else {
                    console.error("Config missing factory address", res.data);
                    setError("Failed to load system configuration.");
                }
            } catch (err) {
                console.error("Failed to fetch config:", err);
                setError("Could not connect to backend server.");
            }
        };
        fetchConfig();
    }, [isOpen]);

    const checkAndSwitchNetwork = async () => {
        if (!window.ethereum) return;
        const SEPOLIA_CHAIN_ID = "0xaa36a7"; // 11155111

        try {
            const currentChainId = await window.ethereum.request({ method: 'eth_chainId' });
            if (currentChainId !== SEPOLIA_CHAIN_ID) {
                try {
                    await window.ethereum.request({
                        method: 'wallet_switchEthereumChain',
                        params: [{ chainId: SEPOLIA_CHAIN_ID }],
                    });
                } catch (switchError: any) {
                    if (switchError.code === 4902) {
                        await window.ethereum.request({
                            method: 'wallet_addEthereumChain',
                            params: [
                                {
                                    chainId: SEPOLIA_CHAIN_ID,
                                    chainName: 'Sepolia Testnet',
                                    nativeCurrency: {
                                        name: 'SepoliaETH',
                                        symbol: 'SEP',
                                        decimals: 18,
                                    },
                                    rpcUrls: ['https://sepolia.infura.io/v3/'],
                                    blockExplorerUrls: ['https://sepolia.etherscan.io'],
                                },
                            ],
                        });
                    } else {
                        throw switchError;
                    }
                }
            }
        } catch (error) {
            console.error("Failed to switch network:", error);
            throw new Error("Please switch to Sepolia Testnet to proceed.");
        }
    };

    const validateSymbol = (symbol: string): boolean => {
        const regex = /^[A-Z0-9]{3,8}$/;
        return regex.test(symbol);
    };

    const handleDeploy = async () => {
        try {
            setLoading(true);
            setError(null);

            if (!factoryAddress) {
                throw new Error("Factory Address not loaded. Please refresh.");
            }

            await checkAndSwitchNetwork();

            if (!formData.name || !formData.symbol || !formData.assetAddress || !formData.targetAddress || !formData.poolAddress) {
                throw new Error("Please fill all required fields");
            }

            if (!validateSymbol(formData.symbol)) {
                throw new Error("Symbol must be 3-8 uppercase letters/numbers, no spaces");
            }

            if (!window.ethereum) throw new Error("No wallet found");

            const provider = new ethers.BrowserProvider(window.ethereum);
            const signer = await provider.getSigner();

            const factoryAbi = [
                "function deployStrategy(address _asset, string memory _name, string memory _symbol, address _targetToken, address _pool) external returns (address)"
            ];

            const factory = new ethers.Contract(factoryAddress, factoryAbi, signer);

            const tx = await factory.deployStrategy(
                formData.assetAddress,
                formData.name,
                formData.symbol.toUpperCase(),
                formData.targetAddress,
                formData.poolAddress
            );

            setTxHash(tx.hash);

            const receipt = await tx.wait();

            const iface = new ethers.Interface(factoryAbi.concat([
                "event StrategyDeployed(address indexed strategy, string name, string symbol, address indexed asset, address indexed targetToken, address pool)"
            ]));

            let strategyAddress = null;
            if (receipt && receipt.logs) {
                for (const log of receipt.logs) {
                    try {
                        const parsed = iface.parseLog(log);
                        if (parsed && parsed.name === 'StrategyDeployed') {
                            strategyAddress = parsed.args.strategy;
                            break;
                        }
                    } catch (e) { }
                }
            }

            if (!strategyAddress) {
                strategyAddress = "0x0000000000000000000000000000000000000000";
            }

            const { hedgeFundApi } = await import("@/lib/api");

            let userId = "user_from_context";
            try {
                const stored = localStorage.getItem("userData");
                if (stored) {
                    const parsed = JSON.parse(stored);
                    if (parsed?.user_id) userId = parsed.user_id;
                }
            } catch { /* ignore */ }

            await hedgeFundApi.post("/api/v1/strategies", {
                name: formData.name,
                symbol: formData.symbol.toUpperCase(),
                address: strategyAddress,
                asset_address: formData.assetAddress,
                target_address: formData.targetAddress,
                pool_address: formData.poolAddress,
                user_id: userId,
                tx_hash: tx.hash
            });

            toast({
                title: "Strategy Deployed!",
                description: "Your strategy has been created and registered.",
            });

            onSuccess();
            onClose();

        } catch (err: any) {
            console.error(err);
            setError(err.message || "Failed to deploy strategy");
        } finally {
            setLoading(false);
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={onClose}>
            <DialogContent className="bg-zinc-900 border-zinc-800 text-white sm:max-w-[425px]">
                <DialogHeader>
                    <DialogTitle>Create New Strategy</DialogTitle>
                </DialogHeader>

                <div className="grid gap-4 py-4">
                    <div className="grid gap-2">
                        <Label htmlFor="name">Strategy Name</Label>
                        <Input
                            id="name"
                            value={formData.name}
                            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                            placeholder="e.g. Yearn WBTC Strategy"
                            className="bg-zinc-800 border-zinc-700"
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="symbol">Symbol (3-8 chars, no spaces)</Label>
                        <Input
                            id="symbol"
                            value={formData.symbol}
                            onChange={(e) => setFormData({ ...formData, symbol: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '') })}
                            placeholder="e.g. YSWETH"
                            maxLength={8}
                            className="bg-zinc-800 border-zinc-700 uppercase"
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="asset">Asset Token (Token A)</Label>
                        <Input
                            id="asset"
                            value={formData.assetAddress}
                            onChange={(e) => setFormData({ ...formData, assetAddress: e.target.value })}
                            placeholder="0x... (e.g. USDC)"
                            className="bg-zinc-800 border-zinc-700"
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="target">Target Token (Token B)</Label>
                        <Input
                            id="target"
                            value={formData.targetAddress}
                            onChange={(e) => setFormData({ ...formData, targetAddress: e.target.value })}
                            placeholder="0x... (e.g. WETH)"
                            className="bg-zinc-800 border-zinc-700"
                        />
                    </div>

                    <div className="grid gap-2">
                        <Label htmlFor="pool">A/B Pool Address</Label>
                        <Input
                            id="pool"
                            value={formData.poolAddress}
                            onChange={(e) => setFormData({ ...formData, poolAddress: e.target.value })}
                            placeholder="0x... (e.g. USDC/WETH Pool)"
                            className="bg-zinc-800 border-zinc-700"
                        />
                    </div>

                    {error && (
                        <div className="text-red-400 text-sm flex items-center gap-2">
                            <AlertCircle size={16} /> {error}
                        </div>
                    )}
                </div>

                <DialogFooter>
                    <Button type="button" variant="outline" onClick={onClose} className="bg-transparent border-zinc-700 text-zinc-300">
                        Cancel
                    </Button>
                    <Button onClick={handleDeploy} disabled={loading} className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
                        {loading ? <Loader2 className="animate-spin mr-2" /> : null}
                        {loading ? "Deploying..." : "Deploy Strategy"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
