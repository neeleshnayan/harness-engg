"use client";

import React, { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/hooks/use-toast";
import api, { hedgeFundApi } from "@/lib/api";
import { TrendingUp, TrendingDown } from "lucide-react";

interface TradingSignalsProps {
    strategyName: string;
}

export const TradingSignals: React.FC<TradingSignalsProps> = ({ strategyName }) => {
    const { toast } = useToast();
    const [buyAmount, setBuyAmount] = useState("");
    const [sellAmount, setSellAmount] = useState("");
    const [loading, setLoading] = useState(false);

    const handleBuySignal = async () => {
        if (!buyAmount || parseFloat(buyAmount) <= 0) {
            toast({
                title: "❌ Invalid Amount",
                description: "Please enter a valid USDC amount",
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
            const amountWei = Math.floor(parseFloat(buyAmount) * Math.pow(10, 6)).toString();

            const response = await hedgeFundApi.post(`/api/v1/strategy/${strategyName}/buy`, {
                amount: amountWei,
                wallet_address: parsedData.wallet_address,
                user_id: parsedData.user_id,
            });

            if (response.data.status === 'success') {
                toast({
                    title: "✅ Buy Signal Executed",
                    description: `Successfully swapped ${buyAmount} USDC for ${strategyName === 'YEARN_PAXG' ? 'PAXG' : 'WETH'}`,
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
                description: "Please enter a valid WETH amount",
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
                    description: `Successfully swapped ${sellAmount} ${strategyName === 'YEARN_PAXG' ? 'PAXG' : 'WETH'} for USDC`,
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
                <CardTitle className="text-white">Trading Signals</CardTitle>
                <CardDescription className="text-zinc-400">
                    Execute buy/sell signals to trade USDC/WETH using executeSignal()
                </CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Buy Signal */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 mb-2">
                            <TrendingUp className="w-5 h-5 text-green-400" />
                            <h3 className="text-white font-semibold">Buy Signal (USDC → {strategyName === 'YEARN_PAXG' ? 'PAXG' : 'WETH'})</h3>
                        </div>
                        <Input
                            type="number"
                            placeholder="Enter USDC amount"
                            value={buyAmount}
                            onChange={(e) => setBuyAmount(e.target.value)}
                            className="bg-zinc-700/50 border-zinc-600 text-white"
                            disabled={loading}
                        />
                        <Button
                            onClick={handleBuySignal}
                            disabled={loading || !buyAmount}
                            className="w-full bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700"
                        >
                            {loading ? "Executing..." : "Execute Buy"}
                        </Button>
                    </div>

                    {/* Sell Signal */}
                    <div className="space-y-3">
                        <div className="flex items-center gap-2 mb-2">
                            <TrendingDown className="w-5 h-5 text-red-400" />
                            <h3 className="text-white font-semibold">Sell Signal ({strategyName === 'YEARN_PAXG' ? 'PAXG' : 'WETH'} → USDC)</h3>
                        </div>
                        <Input
                            type="number"
                            placeholder={`Enter ${strategyName === 'YEARN_PAXG' ? 'PAXG' : 'WETH'} amount`}
                            value={sellAmount}
                            onChange={(e) => setSellAmount(e.target.value)}
                            className="bg-zinc-700/50 border-zinc-600 text-white"
                            disabled={loading}
                        />
                        <Button
                            onClick={handleSellSignal}
                            disabled={loading || !sellAmount}
                            className="w-full bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700"
                        >
                            {loading ? "Executing..." : "Execute Sell"}
                        </Button>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
};
