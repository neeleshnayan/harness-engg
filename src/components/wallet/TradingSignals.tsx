"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import api, { hedgeFundApi } from "@/lib/api";
import { TrendingUp, TrendingDown } from "lucide-react";
import { useTokenSymbol } from "@/hooks/useTokenSymbol";

interface TradingSignalsProps {
    strategyName: string;
    assetSymbol?: string;
    targetSymbol?: string;
    assetAddress?: string;
    targetAddress?: string;
}

export const TradingSignals: React.FC<TradingSignalsProps> = ({
    strategyName,
    assetSymbol = "USDC",
    targetSymbol = "WETH",
    assetAddress,
    targetAddress
}) => {
    const { toast } = useToast();
    const { symbol: fetchedAssetSymbol } = useTokenSymbol(assetAddress);
    const { symbol: fetchedTargetSymbol } = useTokenSymbol(targetAddress);

    const displayAsset = fetchedAssetSymbol || assetSymbol;
    const displayTarget = fetchedTargetSymbol || targetSymbol;

    const [buyAmount, setBuyAmount] = useState("");
    const [sellAmount, setSellAmount] = useState("");
    const [loading, setLoading] = useState(false);

    const handleBuySignal = async () => {
        if (!buyAmount || parseFloat(buyAmount) <= 0) {
            toast({
                title: "❌ Invalid Amount",
                description: `Please enter a valid ${displayAsset} amount`,
            });
            return;
        }

        setLoading(true);
        try {
            const userData = localStorage.getItem('userData');
            if (!userData) throw new Error('User data not found');

            const parsedData = JSON.parse(userData);
            if (!parsedData.wallet_address) throw new Error('Wallet address not found');

            // Convert USDC amount to wei (6 decimals)
            // TODO: Use dynamic decimals if asset is not USDC (6)
            const amountWei = Math.floor(parseFloat(buyAmount) * Math.pow(10, 6)).toString();

            const response = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/buy`, {
                amount: amountWei,
                wallet_address: parsedData.wallet_address,
                user_id: parsedData.user_id,
            });

            if (response.data.status === 'success') {
                toast({
                    title: "✅ Buy Signal Executed",
                    description: `Successfully swapped ${buyAmount} ${displayAsset} for ${displayTarget}`,
                });
                setBuyAmount("");
            }
        } catch (err: any) {
            const errorMsg = err.response?.data?.detail || err.message || 'Failed to execute buy signal';
            toast({
                title: "❌ Buy Signal Failed",
                description: errorMsg,
            });
        } finally {
            setLoading(false);
        }
    };

    const handleSellSignal = async () => {
        if (!sellAmount || parseFloat(sellAmount) <= 0) {
            toast({
                title: "❌ Invalid Amount",
                description: `Please enter a valid ${displayTarget} amount`,
            });
            return;
        }

        setLoading(true);
        try {
            const userData = localStorage.getItem('userData');
            if (!userData) throw new Error('User data not found');

            const parsedData = JSON.parse(userData);
            if (!parsedData.wallet_address) throw new Error('Wallet address not found');

            // Convert token amount to wei (18 decimals for PAXG and WETH)
            // TODO: Use dynamic decimals
            const decimals = 18;
            const amountWei = Math.floor(parseFloat(sellAmount) * Math.pow(10, decimals)).toString();

            const response = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/sell`, {
                amount: amountWei,
                wallet_address: parsedData.wallet_address,
                user_id: parsedData.user_id,
            });

            if (response.data.status === 'success') {
                toast({
                    title: "✅ Sell Signal Executed",
                    description: `Successfully swapped ${sellAmount} ${displayTarget} for ${displayAsset}`,
                });
                setSellAmount("");
            }
        } catch (err: any) {
            const errorMsg = err.response?.data?.detail || err.message || 'Failed to execute sell signal';
            toast({
                title: "❌ Sell Signal Failed",
                description: errorMsg,
            });
        } finally {
            setLoading(false);
        }
    };

    return (
        <Card className="bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 mb-6">
            <CardHeader>
                <CardTitle className="text-white text-xl">Trading Signals</CardTitle>
                <CardDescription className="text-zinc-400 text-sm">
                    Execute buy/sell signals to trade {displayAsset}/{displayTarget} using executeSignal()
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Buy Signal */}
                    <div className="flex flex-col gap-3">
                        <div className="flex items-center gap-2 mb-2">
                            <TrendingUp className="w-4 h-4 text-green-400" />
                            <h3 className="text-white font-medium text-sm">Buy Signal ({displayAsset} → {displayTarget})</h3>
                        </div>
                        <Input
                            type="number"
                            placeholder={`Enter ${displayAsset} amount`}
                            value={buyAmount}
                            onChange={(e) => setBuyAmount(e.target.value)}
                            className="bg-zinc-700/50 border-zinc-600 text-white text-sm h-10"
                            disabled={loading}
                        />
                        <div className="flex justify-center pt-2">
                            <button
                                onClick={handleBuySignal}
                                disabled={loading || !buyAmount}
                                className={`p-0 border-0 bg-transparent cursor-pointer focus:outline-none focus:ring-0 transition-opacity duration-200 ${loading || !buyAmount ? 'opacity-40 cursor-not-allowed' : 'hover:opacity-80'}`}
                                aria-label="Execute Buy"
                            >
                                {loading ? (
                                    <div className="py-2 px-6 text-center text-sm font-semibold text-white">Executing...</div>
                                ) : (
                                    <img src="/hedge_fund/Execute Buy.svg" alt="Execute Buy" className="h-12 w-auto" />
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Sell Signal */}
                    <div className="flex flex-col gap-3">
                        <div className="flex items-center gap-2 mb-2">
                            <TrendingDown className="w-4 h-4 text-red-400" />
                            <h3 className="text-white font-medium text-sm">Sell Signal ({displayTarget} → {displayAsset})</h3>
                        </div>
                        <Input
                            type="number"
                            placeholder={`Enter ${displayTarget} amount`}
                            value={sellAmount}
                            onChange={(e) => setSellAmount(e.target.value)}
                            className="bg-zinc-700/50 border-zinc-600 text-white text-sm h-10"
                            disabled={loading}
                        />
                        <div className="flex justify-center pt-2">
                            <button
                                onClick={handleSellSignal}
                                disabled={loading || !sellAmount}
                                className={`p-0 border-0 bg-transparent cursor-pointer focus:outline-none focus:ring-0 transition-opacity duration-200 ${loading || !sellAmount ? 'opacity-40 cursor-not-allowed' : 'hover:opacity-80'}`}
                                aria-label="Execute Sell"
                            >
                                {loading ? (
                                    <div className="py-2 px-6 text-center text-sm font-semibold text-white">Executing...</div>
                                ) : (
                                    <img src="/hedge_fund/Execute Sell.svg" alt="Execute Sell" className="h-12 w-auto" />
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
