"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { TrendingUp, TrendingDown, ArrowUp, ArrowDown, Wallet, Users, Percent, BarChart, Clock, Shield } from "lucide-react";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/lib/utils";
import MAVCModal from "./MAVCModal";
import api from "@/lib/api";

interface MAVCStrategyCardProps {
  onRefresh?: () => void;
}

const MAVCStrategyCard: React.FC<MAVCStrategyCardProps> = ({ onRefresh }) => {
  const router = useRouter();
  const [mavcBalance, setMavcBalance] = useState("0");
  const [usdcBalance, setUsdcBalance] = useState("0");
  const [showModal, setShowModal] = useState(false);
  const [modalAction, setModalAction] = useState<'deposit' | 'withdraw'>('deposit');
  const [transactionLoading, setTransactionLoading] = useState(false);
  const [transactionError, setTransactionError] = useState<string | null>(null);
  const [transactionSuccess, setTransactionSuccess] = useState<string | null>(null);

  const mockData = {
    name: "Multi Asset Vault",
    description: "Advanced 50/50 USDC/WETH allocation with high-frequency rebalancing.",
    netApy: 135.3,
    aum: 8.9,
    sharpe: 0.85,
    maxDrawdown: 65.50,
    lockInPeriod: "14d",
    participants: 121,
    performanceFee: 30.0,
    riskGrade: "D" as const
  };

  const gradeStyles = {
    A: 'bg-green-500/20 text-green-400 border-green-500/20 hover:bg-green-500/30',
    B: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/30',
    C: 'bg-orange-500/20 text-orange-400 border-orange-500/20 hover:bg-orange-500/30',
    D: 'bg-red-500/20 text-red-400 border-red-500/20 hover:bg-red-500/30',
  };

  useEffect(() => {
    fetchBalances();
  }, []);

  const fetchBalances = async () => {
    try {
      const userData = localStorage.getItem('userData');
      if (userData) {
        const parsedData = JSON.parse(userData);
        console.log('🔍 User Data from localStorage:', parsedData);
        console.log('🔍 Wallet Address being used:', parsedData.wallet_address);

        if (parsedData.wallet_address) {
          // Fetch wallet balances (includes both USDC and MAVC tokens)
          try {
            console.log(`🔍 Fetching wallet balances for: ${parsedData.wallet_address}`);
            const walletResponse = await api.get(`/api/v1/wallet_balance/${parsedData.wallet_address}`);
            console.log('✅ Wallet Balance Response:', walletResponse.data);

            // The API returns tokenBalances array
            if (walletResponse.data && Array.isArray(walletResponse.data.tokenBalances)) {
              // Find USDC tokens (also merge TRNSK which is treated as USDC)
              const allUSDCTokens = walletResponse.data.tokenBalances.filter((b: any) =>
                b.token && (b.token.symbol === 'USDC' || b.token.symbol === 'TRNSK')
              );

              if (allUSDCTokens.length > 0) {
                const totalUSDC = allUSDCTokens.reduce((sum: number, token: any) => {
                  return sum + parseFloat(token.amount || "0");
                }, 0);
                setUsdcBalance(totalUSDC.toString());
                console.log('✅ USDC Balance set to:', totalUSDC);
              } else {
                setUsdcBalance("0");
                console.log('⚠️ No USDC or TRNSK token found');
              }

              // Find MAVC tokens
              const mavcToken = walletResponse.data.tokenBalances.find((b: any) =>
                b.token && b.token.symbol === 'MAVC'
              );

              if (mavcToken) {
                console.log('🔍 MAVC Token Object:', mavcToken);
                console.log('🔍 MAVC Amount (raw Wei):', mavcToken.amount);
                console.log('🔍 MAVC Token Details:', mavcToken.token);
                console.log('🔍 MAVC Decimals:', mavcToken.token?.decimals);

                // MAVC has 6 decimals - convert from Wei to human-readable format
                const rawAmount = parseFloat(mavcToken.amount || "0");
                const decimals = mavcToken.token?.decimals || 6;
                const humanReadable = rawAmount / Math.pow(10, decimals);

                setMavcBalance(humanReadable.toString());
                console.log('✅ MAVC Balance converted:', rawAmount, '/', Math.pow(10, decimals), '=', humanReadable);
              } else {
                setMavcBalance("0");
                console.log('⚠️ No MAVC token found in wallet');
              }
            } else {
              setUsdcBalance("0");
              setMavcBalance("0");
              console.warn('⚠️ Invalid response format - no tokenBalances array');
            }
          } catch (err) {
            console.warn('❌ Wallet balances not available:', err);
            setUsdcBalance("0");
            setMavcBalance("0");
          }
        }
      }
    } catch (err: any) {
      console.error('Error fetching balances:', err);
    }
  };

  const handleDeposit = async (amount: string) => {
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      
      const userData = localStorage.getItem('userData');
      if (!userData) {
        throw new Error('User data not found');
      }
      
      const parsedData = JSON.parse(userData);
      
      if (!parsedData.wallet_address) {
        throw new Error('Wallet address not found');
      }
      
      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };
      
      const approveResponse = await api.post('/api/v1/mavc/approve', payload);
      
      if (approveResponse.data.status !== 'success') {
        throw new Error('USDC approval failed');
      }
      
      setTransactionSuccess(`Approval submitted! Now depositing...`);
      
      await new Promise(resolve => setTimeout(resolve, 2000));
      
      const response = await api.post('/api/v1/mavc/deposit', payload);
      
      if (response.data.status === 'success') {
        setTransactionSuccess(`Successfully deposited ${amount} USDC to MAVC!`);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances();
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Deposit failed');
      }
    } catch (err: any) {
      console.error('MAVC Deposit Error:', err);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to deposit to MAVC vault';
      setTransactionError(errorMsg);
    } finally {
      setTransactionLoading(false);
    }
  };

  const handleWithdraw = async (amount: string) => {
    try {
      setTransactionLoading(true);
      setTransactionError(null);
      
      const userData = localStorage.getItem('userData');
      if (!userData) {
        throw new Error('User data not found');
      }
      
      const parsedData = JSON.parse(userData);
      
      if (!parsedData.wallet_address) {
        throw new Error('Wallet address not found');
      }
      
      const payload = {
        amount: amount,
        wallet_address: parsedData.wallet_address,
        user_id: parsedData.user_id
      };
      
      const response = await api.post('/api/v1/mavc/withdraw', payload);
      
      if (response.data.status === 'success') {
        setTransactionSuccess(`Successfully withdrew ${amount} MAVC tokens!`);
        
        if (onRefresh) onRefresh();
        setTimeout(() => {
          fetchBalances();
        }, 1000);
      } else {
        throw new Error(response.data.message || 'Withdrawal failed');
      }
    } catch (err: any) {
      console.error('MAVC Withdraw Error:', err);
      const errorMsg = err.response?.data?.detail 
        ? (typeof err.response.data.detail === 'string' 
          ? err.response.data.detail 
          : JSON.stringify(err.response.data.detail))
        : err.message || 'Failed to withdraw from MAVC vault';
      setTransactionError(errorMsg);
    } finally {
      setTransactionLoading(false);
    }
  };

  const openDepositModal = (e: React.MouseEvent) => {
    e.stopPropagation();
    setModalAction('deposit');
    setShowModal(true);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const openWithdrawModal = (e: React.MouseEvent) => {
    e.stopPropagation();
    setModalAction('withdraw');
    setShowModal(true);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setTransactionError(null);
    setTransactionSuccess(null);
  };

  const handleCardClick = () => {
    router.push('/customer/grow/hedge-fund-v2/mavc');
  };

  const formatBalance = (balance: string): string => {
    try {
      const numBalance = parseFloat(balance);
      console.log('📊 formatBalance input:', balance, '-> parsed:', numBalance);

      if (isNaN(numBalance) || numBalance === 0) return '0';

      // Display the balance as-is (should already be in correct format from tokenBalances)
      if (numBalance < 0.01) return numBalance.toFixed(4);
      if (numBalance < 1) return numBalance.toFixed(3);
      if (numBalance < 100) return numBalance.toFixed(2);
      return numBalance.toFixed(1);
    } catch {
      return '0';
    }
  };

  return (
    <>
      <Card 
        className="flex flex-col h-full overflow-hidden transition-all duration-300 ease-in-out hover:shadow-xl hover:-translate-y-1 bg-zinc-800/50 backdrop-blur-sm border-zinc-700/50 cursor-pointer"
        onClick={handleCardClick}
      >
        <CardHeader className="pb-4">
          <div className="flex justify-between items-start gap-4">
            <CardTitle className="text-xl text-white">{mockData.name}</CardTitle>
            <div className="flex items-center gap-2 bg-purple-500/20 text-purple-300 px-3 py-1 rounded-lg border border-purple-500/30">
              <Wallet className="w-4 h-4" />
              <span className="text-sm font-semibold">{formatBalance(mavcBalance)} MAVC</span>
            </div>
          </div>
          <CardDescription className="pt-2 text-sm text-zinc-400">{mockData.description}</CardDescription>
        </CardHeader>
        
        <CardContent className="flex-grow space-y-5">
          <div className="space-y-4">
            <h4 className="text-sm font-semibold text-zinc-400">Key Metrics</h4>
            <div className="space-y-4 text-sm">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <TrendingUp className="w-6 h-6 text-green-400" />
                  <div>
                    <p className="text-xs text-zinc-500">Net APY</p>
                    <span className="font-semibold text-lg text-white">{mockData.netApy.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="flex items-center gap-3 text-right">
                  <div>
                    <p className="text-xs text-zinc-500">AUM</p>
                    <span className="font-semibold text-lg text-white">${mockData.aum.toLocaleString()}M</span>
                  </div>
                  <Wallet className="w-6 h-6 text-zinc-500" />
                </div>
              </div>

              <Separator className="bg-zinc-700" />

              <div className="flex justify-between items-center text-center">
                <div className="flex flex-col items-center gap-1">
                  <BarChart className="w-5 h-5 text-blue-400" />
                  <span className="font-semibold text-white">{mockData.sharpe.toFixed(2)}</span>
                  <span className="text-xs text-zinc-500">Sharpe</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <TrendingDown className="w-5 h-5 text-red-400" />
                  <span className="font-semibold text-white">{mockData.maxDrawdown.toFixed(2)}%</span>
                  <span className="text-xs text-zinc-500">Max Drawdown</span>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <Clock className="w-5 h-5 text-zinc-500" />
                  <span className="font-semibold text-white">{mockData.lockInPeriod}</span>
                  <span className="text-xs text-zinc-500">Lock-in Period</span>
                </div>
              </div>
            </div>
          </div>
        </CardContent>
        
        <CardFooter className="p-4 bg-black/20 flex flex-col gap-3 mt-auto">
          <div className="flex items-center justify-between w-full text-sm text-zinc-400">
            <div className="flex items-center gap-4 flex-wrap">
              <div className="flex items-center gap-2">
                <Users className="w-5 h-5" />
                <span className="font-semibold text-white">{mockData.participants.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                <Percent className="w-5 h-5" />
                <span className="font-semibold text-white">{mockData.performanceFee.toFixed(1)}%</span>
              </div>
            </div>
          </div>
          <div className="flex gap-2 w-full">
            <Button 
              size="sm" 
              className="flex-1 font-bold bg-gradient-to-r from-green-500 to-emerald-600 hover:from-green-600 hover:to-emerald-700" 
              onClick={openDepositModal}
            >
              <ArrowDown className="w-4 h-4 mr-1" />
              Deposit
            </Button>
            <Button 
              size="sm" 
              className="flex-1 font-bold bg-gradient-to-r from-red-500 to-pink-600 hover:from-red-600 hover:to-pink-700" 
              onClick={openWithdrawModal}
            >
              <ArrowUp className="w-4 h-4 mr-1" />
              Withdraw
            </Button>
          </div>
        </CardFooter>
      </Card>

      <MAVCModal
        visible={showModal}
        onClose={closeModal}
        action={modalAction}
        mavcBalance={mavcBalance}
        usdcBalance={usdcBalance}
        onDeposit={handleDeposit}
        onWithdraw={handleWithdraw}
        loading={transactionLoading}
        error={transactionError}
        success={transactionSuccess}
      />
    </>
  );
};

export default MAVCStrategyCard;

